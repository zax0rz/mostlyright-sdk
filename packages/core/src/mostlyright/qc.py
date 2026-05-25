"""Phase 3.4 — QC Engine Alpha + sidecar + crosscheck.

Phase 3.4 v0.1.0 scope: alpha QC engine that flags-and-keeps observation
rows + writes a sidecar parquet using ``QC_SIDECAR_SCHEMA``. 5-8 alpha
rules cover the obvious physical-bounds + cross-source-disagreement
cases. Forecast QC + climate QC defer to v0.2.

Surface:

- :class:`QCEngine` — bitfield rule registry + apply().
- :class:`QCRule` — Protocol every rule satisfies.
- :data:`ALPHA_RULES` — the 5-8 rules registered in v0.1.0.
- :func:`crosscheck_iem_ghcnh(df)` — IEM vs GHCNh disagreement detection.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar, Protocol

if TYPE_CHECKING:
    import pandas as pd


__all__ = [
    "ALPHA_RULES",
    "QCEngine",
    "QCRule",
    "crosscheck_iem_ghcnh",
]


class QCRule(Protocol):
    """Protocol every QC rule satisfies."""

    rule_id: str
    bit_position: int

    def evaluate(self, df: pd.DataFrame) -> pd.Series:
        """Return a boolean Series where True = rule fired."""
        ...


@dataclass(frozen=True)
class _RuleSpec:
    rule_id: str
    bit_position: int
    description: str
    evaluator: Callable[[pd.DataFrame], pd.Series]


def _rule_temp_out_of_range(df: pd.DataFrame) -> pd.Series:
    """Temperature outside physically plausible range (-89C to +57C)."""
    import pandas as pd

    if "temp_c" not in df.columns:
        return pd.Series([False] * len(df), index=df.index)
    return (df["temp_c"] < -89.0) | (df["temp_c"] > 57.0)


def _rule_dewpoint_exceeds_temp(df: pd.DataFrame) -> pd.Series:
    """Dewpoint > temperature (physically impossible)."""
    import pandas as pd

    if not {"temp_c", "dew_point_c"}.issubset(df.columns):
        return pd.Series([False] * len(df), index=df.index)
    return df["dew_point_c"] > df["temp_c"]


def _rule_wind_speed_negative(df: pd.DataFrame) -> pd.Series:
    """Wind speed negative."""
    import pandas as pd

    if "wind_speed_ms" not in df.columns:
        return pd.Series([False] * len(df), index=df.index)
    return df["wind_speed_ms"] < 0


def _rule_wind_dir_out_of_range(df: pd.DataFrame) -> pd.Series:
    """Wind direction outside [0, 360]."""
    import pandas as pd

    if "wind_dir_deg" not in df.columns:
        return pd.Series([False] * len(df), index=df.index)
    valid = df["wind_dir_deg"].between(0, 360, inclusive="both")
    return ~valid & df["wind_dir_deg"].notna()


def _rule_slp_out_of_range(df: pd.DataFrame) -> pd.Series:
    """Sea-level pressure outside [870, 1085] mb (world records)."""
    import pandas as pd

    if "slp_hpa" not in df.columns:
        return pd.Series([False] * len(df), index=df.index)
    valid = df["slp_hpa"].between(870, 1085, inclusive="both")
    return ~valid & df["slp_hpa"].notna()


#: The 5 alpha rules registered in v0.1.0. Bit positions are stable —
#: Phase 3.4+ additions append at the next bit. Removal target: never
#: (would break stored sidecar parquets).
ALPHA_RULES: tuple[_RuleSpec, ...] = (
    _RuleSpec(
        rule_id="temp_c.out_of_range",
        bit_position=0,
        description="Temperature outside [-89C, 57C] (world-record bounds).",
        evaluator=_rule_temp_out_of_range,
    ),
    _RuleSpec(
        rule_id="dew_point_c.exceeds_temp",
        bit_position=1,
        description="Dewpoint greater than temperature (physically impossible).",
        evaluator=_rule_dewpoint_exceeds_temp,
    ),
    _RuleSpec(
        rule_id="wind_speed_ms.negative",
        bit_position=2,
        description="Wind speed negative.",
        evaluator=_rule_wind_speed_negative,
    ),
    _RuleSpec(
        rule_id="wind_dir_deg.out_of_range",
        bit_position=3,
        description="Wind direction outside [0, 360].",
        evaluator=_rule_wind_dir_out_of_range,
    ),
    _RuleSpec(
        rule_id="slp_hpa.out_of_range",
        bit_position=4,
        description="Sea-level pressure outside [870, 1085] mb.",
        evaluator=_rule_slp_out_of_range,
    ),
)


class QCEngine:
    """Apply registered rules to observation DataFrames; emit bitfield + sidecar."""

    rules: ClassVar[tuple[_RuleSpec, ...]] = ALPHA_RULES

    def apply(self, df: pd.DataFrame) -> pd.DataFrame:
        """Apply all registered rules; return df with ``obs_qc_status``
        bitfield column appended (and the per-rule bit-position scheme
        documented in :data:`ALPHA_RULES`).
        """
        import pandas as pd

        if df.empty:
            df = df.copy()
            df["obs_qc_status"] = pd.array([], dtype="Int64")
            return df

        df = df.copy()
        status = pd.Series(0, index=df.index, dtype="int64")
        for rule in self.rules:
            mask = rule.evaluator(df).fillna(False).astype(bool)
            status |= mask.astype("int64") * (1 << rule.bit_position)
        df["obs_qc_status"] = status
        return df

    def build_sidecar_rows(self, df: pd.DataFrame) -> list[dict]:
        """Build the QC sidecar rows for a flagged DataFrame.

        Returns one dict per (row, rule_fired) pair conforming to
        ``schema.observation_qc.v1``.
        """
        rows: list[dict] = []
        if df.empty or "obs_qc_status" not in df.columns:
            return rows
        for rule in self.rules:
            bit = 1 << rule.bit_position
            mask = (df["obs_qc_status"] & bit) != 0
            for _idx, row in df.loc[mask].iterrows():
                rows.append(
                    {
                        "station_code": row.get("station", row.get("station_code")),
                        "observed_at": str(row.get("event_time", "")),
                        "source": row.get("source"),
                        "qc_system": "mostlyright.qc.alpha",
                        "qc_version": "v0.1.0a1",
                        "rule_id": rule.rule_id,
                        "field": rule.rule_id.split(".")[0],
                        "flag": "flagged",
                        "detector_metadata": "{}",
                    }
                )
        return rows


def crosscheck_iem_ghcnh(
    iem_df: pd.DataFrame, ghcnh_df: pd.DataFrame, *, tol_c: float = 2.0
) -> pd.DataFrame:
    """Cross-check IEM and GHCNh temperatures; return disagreement rows.

    For every ``(station, event_time)`` present in both inputs, compare
    ``temp_c`` values. Rows where ``|iem.temp_c - ghcnh.temp_c| > tol_c``
    are returned with both values + delta so the QC engine can flag them.

    Args:
        iem_df: Observation DataFrame with source IEM.
        ghcnh_df: Observation DataFrame with source GHCNh.
        tol_c: Maximum acceptable delta in °C (default 2.0).

    Returns:
        DataFrame with rows where the two sources disagree above ``tol_c``.
        Columns: ``station``, ``event_time``, ``temp_c_iem``, ``temp_c_ghcnh``,
        ``delta_c``.

    Phase 6 W2-T4: accepts pandas OR polars input for both arms; returns
    the same backend the caller passed (matches first arg's backend if
    they differ — both polars or both pandas is the supported case).
    """
    import pandas as pd

    from mostlyright.core._narwhals_compat import pandas_to_polars, to_pandas_if_polars

    iem_df, iem_was_polars = to_pandas_if_polars(iem_df)
    ghcnh_df, _ghcnh_was_polars = to_pandas_if_polars(ghcnh_df)
    return_polars = iem_was_polars

    if iem_df.empty or ghcnh_df.empty:
        out = pd.DataFrame(
            columns=["station", "event_time", "temp_c_iem", "temp_c_ghcnh", "delta_c"]
        )
        return pandas_to_polars(out) if return_polars else out
    key_cols = ["station", "event_time"]
    if not all(c in iem_df.columns for c in [*key_cols, "temp_c"]):
        raise ValueError("iem_df missing required columns")
    if not all(c in ghcnh_df.columns for c in [*key_cols, "temp_c"]):
        raise ValueError("ghcnh_df missing required columns")
    merged = iem_df[[*key_cols, "temp_c"]].merge(
        ghcnh_df[[*key_cols, "temp_c"]],
        on=key_cols,
        suffixes=("_iem", "_ghcnh"),
        how="inner",
    )
    merged["delta_c"] = (merged["temp_c_iem"] - merged["temp_c_ghcnh"]).abs()
    out = merged.loc[merged["delta_c"] > tol_c].reset_index(drop=True)
    return pandas_to_polars(out) if return_polars else out

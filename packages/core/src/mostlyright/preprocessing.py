"""Phase 3.5 — preprocessing primitives.

Standalone callable counterparts to the in-pipeline QC engine + transforms.
Quants can run these after :func:`mostlyright.research` (or any DataFrame
they constructed elsewhere) without going through the QC engine.

Surface:

- :func:`clip_outliers(df, column, *, bounds=None, std=3.0)` — winsorize
  to either physics-based bounds (default) or ``mean ± std * sigma``.
- :func:`iem_crosscheck(silver_df, *, tolerance="default")` — standalone
  IEM-vs-GHCNh disagreement detector. Thin re-export of
  :func:`mostlyright.qc.crosscheck_iem_ghcnh` with sensible defaults.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from mostlyright.core._narwhals_compat import (
    pandas_series_to_polars,
    pandas_to_polars,
    to_pandas_if_polars,
)

if TYPE_CHECKING:
    import pandas as pd


__all__ = [
    "PHYSICS_BOUNDS",
    "clip_outliers",
    "iem_crosscheck",
]


#: Physics-based clipping defaults for the canonical observation columns.
#: Values are ``(min, max)`` tuples in canonical units (°C for temp,
#: m/s for wind, hPa for pressure, percent for humidity).
PHYSICS_BOUNDS: dict[str, tuple[float, float]] = {
    "temp_c": (-89.0, 57.0),
    "dew_point_c": (-89.0, 35.0),
    "dewpoint_c": (-89.0, 35.0),
    "wind_speed_ms": (0.0, 100.0),
    "wind_speed_kt": (0.0, 200.0),
    "wind_dir_deg": (0.0, 360.0),
    "wind_dir_degrees": (0.0, 360.0),
    "slp_hpa": (870.0, 1085.0),
    "sea_level_pressure_mb": (870.0, 1085.0),
    "relative_humidity_pct_2m": (0.0, 100.0),
    "precip_mm_1h": (0.0, 305.0),
}


def clip_outliers(
    df: pd.DataFrame,
    column: str,
    *,
    bounds: tuple[float, float] | None = None,
    std: float = 3.0,
) -> pd.Series:
    """Winsorize ``df[column]`` to either physics-based or sigma-based bounds.

    If ``bounds`` is supplied, clip to that explicit ``(min, max)``.
    Else if ``column`` has a :data:`PHYSICS_BOUNDS` entry, clip to that.
    Else fall back to ``mean ± std * sigma`` (matches the historical
    behaviour of :func:`mostlyright.transforms.clip_outliers`).

    Returns a NEW Series; the input DataFrame is unchanged.

    Args:
        df: input DataFrame.
        column: name of the numeric column to clip.
        bounds: explicit ``(lower, upper)``. Overrides physics defaults.
        std: sigma multiplier for the fallback branch. Ignored when
            ``bounds`` or a physics entry applies.

    Raises:
        KeyError: ``column`` not in ``df``.

    Phase 6 W2-T3: accepts pandas OR polars input; returns the same
    backend the caller passed.
    """
    pdf, was_polars = to_pandas_if_polars(df)
    s = pdf[column]
    if bounds is not None:
        lower, upper = bounds
        out = s.clip(lower=lower, upper=upper)
    else:
        physics = PHYSICS_BOUNDS.get(column)
        if physics is not None:
            out = s.clip(lower=physics[0], upper=physics[1])
        else:
            # Architect iter-1 HIGH: std<=0 in the sigma fallback collapses
            # every row to the mean — silent dataset corruption. Refuse.
            if std <= 0:
                raise ValueError(
                    f"clip_outliers: std must be > 0 for the sigma fallback (got {std}); "
                    "pass bounds=(lo, hi) or use a physics-default column",
                )
            mu = s.mean()
            sigma = s.std()
            out = s.clip(lower=mu - std * sigma, upper=mu + std * sigma)
    if was_polars:
        return pandas_series_to_polars(out)
    return out


def iem_crosscheck(
    silver_df: pd.DataFrame,
    *,
    tolerance: str | float = "default",
) -> pd.DataFrame:
    """Standalone-callable IEM-vs-GHCNh crosscheck.

    Splits ``silver_df`` by source column (rows whose source starts with
    ``"iem"`` vs ``"ghcnh"``) and delegates to
    :func:`mostlyright.qc.crosscheck_iem_ghcnh`. Useful when a quant has
    already called :func:`mostlyright.research` (or another fetcher) and
    wants the disagreement table without going through the full QC engine.

    Args:
        silver_df: DataFrame with a ``source`` column and per-row
            ``(station, event_time, temp_c)`` (or production-shape
            ``station_code, observed_at`` — both are accepted, the
            former is auto-derived from the latter when missing).
        tolerance: either ``"default"`` (uses 2.0 °C from
            :func:`crosscheck_iem_ghcnh`) or an explicit float in °C.

    Returns:
        DataFrame with one row per disagreement
        (``station, event_time, temp_c_iem, temp_c_ghcnh, delta_c``).

    Raises:
        ValueError: ``silver_df`` lacks a ``source`` column.

    Phase 6 W2-T3: accepts pandas OR polars input; returns the same
    backend the caller passed.
    """
    import pandas as pd

    from mostlyright.qc import crosscheck_iem_ghcnh

    silver_df, was_polars = to_pandas_if_polars(silver_df)
    if "source" not in silver_df.columns:
        raise ValueError(
            "iem_crosscheck: silver_df must carry a 'source' column "
            "(use research(qc=True) output or another canonical adapter)"
        )
    # Normalize production column names so the underlying crosscheck
    # function (which reads station / event_time) sees what it expects.
    work = silver_df.copy()
    if "station" not in work.columns and "station_code" in work.columns:
        work["station"] = work["station_code"]
    if "event_time" not in work.columns and "observed_at" in work.columns:
        work["event_time"] = work["observed_at"]
    if "temp_c" not in work.columns and "tmpf" in work.columns:
        work["temp_c"] = pd.to_numeric(work["tmpf"], errors="coerce").apply(
            lambda f: (f - 32.0) * 5.0 / 9.0 if pd.notna(f) else None
        )

    iem_df = work.loc[work["source"].astype(str).str.startswith("iem")]
    ghcnh_df = work.loc[work["source"].astype(str).str.startswith("ghcnh")]
    if iem_df.empty or ghcnh_df.empty:
        out = pd.DataFrame(
            columns=["station", "event_time", "temp_c_iem", "temp_c_ghcnh", "delta_c"]
        )
    else:
        tol_c: float = 2.0 if tolerance == "default" else float(tolerance)
        out = crosscheck_iem_ghcnh(iem_df, ghcnh_df, tol_c=tol_c)
    if was_polars:
        return pandas_to_polars(out)
    return out

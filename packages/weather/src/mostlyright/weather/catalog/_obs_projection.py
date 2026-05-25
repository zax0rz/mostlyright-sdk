"""Shared row → canonical-schema projection for observation adapters.

All three observation adapters (IEM, AWC, GHCNh) take parser output in
v0.14.1 legacy units (knots, miles, feet, inches) and project to the
canonical ``schema.observation.v1`` column set in SI units (m/s, metres,
mm). This module centralises the projection mapping and per-column unit
conversion so a future contract change updates exactly one place.

Each entry in :data:`PROJECTION_SPEC` is ``(src_field, dst_field, converter)``.
``converter`` is one of:

- ``None`` — passthrough, no unit change.
- ``"kt_to_ms"`` / ``"mi_to_m"`` / ``"ft_to_m"`` / ``"in_to_mm"`` —
  named conversion from :mod:`tradewinds._internal._convert`.

The HIGH finding from codex Phase 2 review (Wave 4): without this
conversion, adapters silently emitted DataFrames where ``wind_speed_ms``
was actually in knots — passing schema-shape validation but feeding wrong
physical values into downstream research().
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import pandas as pd
from tradewinds._internal._convert import (
    ft_to_m,
    inches_to_mm,
    kt_to_ms,
    mi_to_m,
)

_CONVERTERS = {
    "kt_to_ms": kt_to_ms,
    "mi_to_m": mi_to_m,
    "ft_to_m": ft_to_m,
    "in_to_mm": inches_to_mm,
}


#: Parser output → canonical schema projection with per-column unit conversion.
#: Order matches the ``schema.observation.v1`` column order.
PROJECTION_SPEC: list[tuple[str, str, str | None]] = [
    ("station_code", "station", None),
    ("observed_at", "event_time", None),
    ("observation_type", "observation_type", None),
    ("temp_c", "temp_c", None),
    ("dewpoint_c", "dew_point_c", None),
    ("wind_speed_kt", "wind_speed_ms", "kt_to_ms"),
    ("wind_dir_degrees", "wind_dir_deg", None),
    ("wind_gust_kt", "wind_gust_ms", "kt_to_ms"),
    ("sea_level_pressure_mb", "slp_hpa", None),
    ("visibility_miles", "visibility_m", "mi_to_m"),
    ("precip_1hr_inches", "precip_mm_1h", "in_to_mm"),
    ("sky_cover_1", "sky_cover_1", None),
    ("sky_base_1_ft", "sky_base_1_m", "ft_to_m"),
    ("sky_cover_2", "sky_cover_2", None),
    ("sky_base_2_ft", "sky_base_2_m", "ft_to_m"),
    ("sky_cover_3", "sky_cover_3", None),
    ("sky_base_3_ft", "sky_base_3_m", "ft_to_m"),
    ("sky_cover_4", "sky_cover_4", None),
    ("sky_base_4_ft", "sky_base_4_m", "ft_to_m"),
    ("raw_metar", "metar_raw", None),
]


def project_row(row: dict[str, Any]) -> dict[str, Any]:
    """Project a single parser-output row to canonical-schema column names + units."""
    out: dict[str, Any] = {}
    for src_field, dst_field, converter_name in PROJECTION_SPEC:
        raw = row.get(src_field)
        if converter_name is None or raw is None:
            out[dst_field] = raw
        else:
            converter = _CONVERTERS[converter_name]
            out[dst_field] = converter(raw)
    return out


def canonical_columns() -> list[str]:
    """Return the ordered list of canonical column names this projection emits."""
    return [dst for _, dst, _ in PROJECTION_SPEC]


def empty_observation_df() -> pd.DataFrame:
    """Empty DataFrame with the canonical observation column set + overlay cols."""
    cols = [*canonical_columns(), "source", "retrieved_at", "knowledge_time"]
    return pd.DataFrame({c: [] for c in cols})


#: Canonical dtypes per ``schema.observation.v1`` column. Used by
#: :func:`coerce_canonical_dtypes` to ensure adapter output passes the
#: Validator dtype check even when an entire column is null (e.g. a
#: single METAR row with no gust + no cloud-base would otherwise infer
#: object dtype). codex iter-4 HIGH fix.
_CANONICAL_FLOAT_COLS: tuple[str, ...] = (
    "temp_c",
    "dew_point_c",
    "wind_speed_ms",
    "wind_gust_ms",
    "slp_hpa",
    "visibility_m",
    "precip_mm_1h",
    "sky_base_1_m",
    "sky_base_2_m",
    "sky_base_3_m",
    "sky_base_4_m",
)

_CANONICAL_INT_COLS: tuple[str, ...] = ("wind_dir_deg",)

_CANONICAL_STRING_COLS: tuple[str, ...] = (
    "station",
    "observation_type",
    "sky_cover_1",
    "sky_cover_2",
    "sky_cover_3",
    "sky_cover_4",
    "metar_raw",
)


def coerce_canonical_dtypes(df: pd.DataFrame) -> pd.DataFrame:
    """Coerce per-column dtypes to match ``schema.observation.v1`` declarations.

    Catalog adapters build DataFrames from row-dicts; pandas infers object
    dtype for any column that is fully null, which fails the Validator's
    float64/int64 dtype checks. This helper coerces:

    - numeric columns to ``float64`` (with ``pd.NA`` -> ``np.nan``)
    - ``wind_dir_deg`` to nullable ``Int64``
    - string columns to ``string`` dtype

    Idempotent — already-correctly-typed columns pass through unchanged.
    """
    for col in _CANONICAL_FLOAT_COLS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").astype("float64")
    for col in _CANONICAL_INT_COLS:
        if col in df.columns:
            df[col] = pd.array(df[col].tolist(), dtype="Int64")
    for col in _CANONICAL_STRING_COLS:
        if col in df.columns:
            df[col] = df[col].astype("string")
    return df


def add_overlay_columns(
    df: pd.DataFrame,
    *,
    source: str,
    retrieved_at: datetime,
    lag: pd.Timedelta,
) -> pd.DataFrame:
    """Add ``source`` / ``retrieved_at`` / ``knowledge_time`` overlay columns
    and coerce per-column dtypes to the canonical schema declarations.

    Also sets ``df.attrs["source"]`` and ``df.attrs["retrieved_at"]``.
    ``event_time`` is parsed to tz-aware UTC datetime64.
    """
    # Defensive: reject naive retrieved_at up front. Without this,
    # pd.Timestamp(naive_dt).tz_convert("UTC") raises a cryptic
    # "Cannot convert tz-naive Timestamp" deep inside pandas.
    if retrieved_at.tzinfo is None:
        raise ValueError(
            "retrieved_at must be a tz-aware datetime (e.g. datetime.now(UTC)); "
            f"got naive {retrieved_at!r}. Attach a tzinfo before calling "
            "the catalog adapter."
        )
    # PANDAS3: utc=True locks the conversion to tz-aware datetime64 on
    # both pandas 2.x and 3.x; resolution may shift ns → us on 3.x but
    # the timezone-aware shape stays Validator-compatible and the
    # coerce_pd3 bridge documents the accepted shift.
    df["event_time"] = pd.to_datetime(df["event_time"], utc=True, errors="coerce")
    df = coerce_canonical_dtypes(df)
    df["source"] = source
    df["retrieved_at"] = pd.Timestamp(retrieved_at).tz_convert("UTC")
    df["knowledge_time"] = df["event_time"] + lag
    df.attrs["source"] = source
    df.attrs["retrieved_at"] = retrieved_at
    return df


__all__ = [
    "PROJECTION_SPEC",
    "add_overlay_columns",
    "canonical_columns",
    "empty_observation_df",
    "project_row",
]

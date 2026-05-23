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


def add_overlay_columns(
    df: pd.DataFrame,
    *,
    source: str,
    retrieved_at: datetime,
    lag: pd.Timedelta,
) -> pd.DataFrame:
    """Add ``source`` / ``retrieved_at`` / ``knowledge_time`` overlay columns.

    Also sets ``df.attrs["source"]`` and ``df.attrs["retrieved_at"]``.
    ``event_time`` is parsed to tz-aware UTC datetime64.
    """
    df["event_time"] = pd.to_datetime(df["event_time"], utc=True, errors="coerce")
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

"""ECMWF IFS variable map — eccodes ``param`` keys.

ECMWF Open Data uses single-letter / digit-prefix param codes ("2t" for
2-m temperature, "msl" for mean sea level pressure, "tp" for total
precipitation, etc.). The level info comes from the ``.index`` line's
``levtype`` + optional ``levelist`` rather than a wgrib2-style human
string.

**Unit note:** ECMWF ``tp`` is in METERS, not millimeters. The downstream
projection layer is responsible for ``× 1000`` conversion if mm output
is desired. The canonical column name (``precip_mm_1h``) matches
``schema.forecast_nwp.v1`` so the row builder writes into the documented
column; the unit-conversion wiring lands in Phase 17 PLAN-09 (research
integration). Until then quants must convert tp (m) → mm themselves.
"""

from __future__ import annotations

VARIABLE_MAP: dict[str, tuple[str, str]] = {
    "temp_k_2m": ("2t", "sfc"),
    "dewpoint_k_2m": ("2d", "sfc"),
    "wind_u_ms_10m": ("10u", "sfc"),
    "wind_v_ms_10m": ("10v", "sfc"),
    "wind_gust_ms": ("10fg", "sfc"),
    "precip_mm_1h": ("tp", "sfc"),
    "pressure_pa_surface": ("sp", "sfc"),
    "pressure_pa_mslp": ("msl", "sfc"),
}

GRID_KIND: str = "regular_latlon_global_0p25"

__all__ = ["GRID_KIND", "VARIABLE_MAP"]

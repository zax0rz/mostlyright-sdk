"""ECMWF AIFS (AI single + ens) variable map.

AIFS does NOT publish 10-m wind gust (``10fg``) — surface gust is omitted.
Other variables match IFS.

**Unit note:** ECMWF ``tp`` is in METERS, not millimeters. The canonical
column name (``precip_mm_1h``) matches ``schema.forecast_nwp.v1``; the
unit-conversion wiring lands in Phase 17 PLAN-09 (research integration).
Until then quants must convert tp (m) → mm themselves.
"""

from __future__ import annotations

VARIABLE_MAP: dict[str, tuple[str, str]] = {
    "temp_k_2m": ("2t", "sfc"),
    "dewpoint_k_2m": ("2d", "sfc"),
    "wind_u_ms_10m": ("10u", "sfc"),
    "wind_v_ms_10m": ("10v", "sfc"),
    "precip_mm_1h": ("tp", "sfc"),
    "pressure_pa_surface": ("sp", "sfc"),
    "pressure_pa_mslp": ("msl", "sfc"),
}

GRID_KIND: str = "regular_latlon_global_0p25"

__all__ = ["GRID_KIND", "VARIABLE_MAP"]

"""ECMWF AIFS (AI single + ens) variable map.

AIFS does NOT publish 10-m wind gust (``10fg``) — surface gust is omitted.
Other variables match IFS.
"""

from __future__ import annotations

VARIABLE_MAP: dict[str, tuple[str, str]] = {
    "temp_k_2m": ("2t", "sfc"),
    "dewpoint_k_2m": ("2d", "sfc"),
    "wind_u_ms_10m": ("10u", "sfc"),
    "wind_v_ms_10m": ("10v", "sfc"),
    "precip_m_total": ("tp", "sfc"),
    "pressure_pa_surface": ("sp", "sfc"),
    "pressure_pa_mslp": ("msl", "sfc"),
}

GRID_KIND: str = "regular_latlon_global_0p25"

__all__ = ["GRID_KIND", "VARIABLE_MAP"]

"""HRDPS (Canadian continental 2.5km) — MSC per-variable file naming."""

from __future__ import annotations

VARIABLE_MAP: dict[str, tuple[str, str]] = {
    "temp_k_2m": ("TMP", "TGL_2"),
    "dewpoint_k_2m": ("DPT", "TGL_2"),
    "relative_humidity_pct_2m": ("RH", "TGL_2"),
    "wind_u_ms_10m": ("UGRD", "TGL_10"),
    "wind_v_ms_10m": ("VGRD", "TGL_10"),
    "wind_gust_ms": ("GUST", "TGL_10"),
    "precip_mm_1h": ("APCP", "Sfc"),
    "pressure_pa_surface": ("PRES", "Sfc"),
    "pressure_pa_mslp": ("PRMSL", "MSL"),
}

GRID_KIND: str = "rotated_latlon_continental_2p5km"

__all__ = ["GRID_KIND", "VARIABLE_MAP"]

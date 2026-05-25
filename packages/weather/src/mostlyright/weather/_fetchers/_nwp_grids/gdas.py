"""GDAS (Global Data Assimilation System) variable map — mirrors GFS."""

from __future__ import annotations

VARIABLE_MAP: dict[str, tuple[str, str]] = {
    "temp_k_2m": ("TMP", "2 m above ground"),
    "dewpoint_k_2m": ("DPT", "2 m above ground"),
    "wind_u_ms_10m": ("UGRD", "10 m above ground"),
    "wind_v_ms_10m": ("VGRD", "10 m above ground"),
    "precip_mm_1h": ("APCP", "surface"),
    "pressure_pa_surface": ("PRES", "surface"),
    "pressure_pa_mslp": ("PRMSL", "mean sea level"),
}

GRID_KIND: str = "regular_latlon_global_0p25"

__all__ = ["GRID_KIND", "VARIABLE_MAP"]

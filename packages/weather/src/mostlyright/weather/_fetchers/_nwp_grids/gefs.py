"""GEFS (Global Ensemble Forecast System) variable map + member enum."""

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

GRID_KIND: str = "regular_latlon_global_0p5"

#: GEFS members — c00 (control), p01..p30 (perturbations), avg (ensemble mean),
#: spr (spread). 33 values total.
GEFS_MEMBERS: frozenset[str] = frozenset(
    {"c00", "avg", "spr"} | {f"p{i:02d}" for i in range(1, 31)}
)

__all__ = ["GEFS_MEMBERS", "GRID_KIND", "VARIABLE_MAP"]

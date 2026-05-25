"""REPS (Canadian Regional Ensemble 10km) — 21 per-member files."""

from __future__ import annotations

VARIABLE_MAP: dict[str, tuple[str, str]] = {
    "temp_k_2m": ("TMP", "TGL_2"),
    "dewpoint_k_2m": ("DPT", "TGL_2"),
    "wind_u_ms_10m": ("UGRD", "TGL_10"),
    "wind_v_ms_10m": ("VGRD", "TGL_10"),
    "precip_mm_1h": ("APCP", "Sfc"),
    "pressure_pa_surface": ("PRES", "Sfc"),
    "pressure_pa_mslp": ("PRMSL", "MSL"),
}

GRID_KIND: str = "rotated_latlon_regional_10km"

#: REPS members — m001..m021 (21 perturbations).
REPS_MEMBERS: frozenset[str] = frozenset({f"m{i:03d}" for i in range(1, 22)})

__all__ = ["GRID_KIND", "REPS_MEMBERS", "VARIABLE_MAP"]

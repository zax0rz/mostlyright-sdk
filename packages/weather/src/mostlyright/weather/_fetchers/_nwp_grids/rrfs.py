"""RRFS (Rapid Refresh Forecast System) variable map + ensemble member enum."""

from __future__ import annotations

VARIABLE_MAP: dict[str, tuple[str, str]] = {
    "temp_k_2m": ("TMP", "2 m above ground"),
    "dewpoint_k_2m": ("DPT", "2 m above ground"),
    "relative_humidity_pct_2m": ("RH", "2 m above ground"),
    "wind_u_ms_10m": ("UGRD", "10 m above ground"),
    "wind_v_ms_10m": ("VGRD", "10 m above ground"),
    "wind_gust_ms": ("GUST", "surface"),
    "precip_mm_1h": ("APCP", "surface"),
    "pressure_pa_surface": ("PRES", "surface"),
    "pressure_pa_mslp": ("MSLMA", "mean sea level"),
}

GRID_KIND: str = "lambert_conformal_conus_3km"

#: RRFS ensemble members — m001..m005 (5 perturbed). Deterministic uses no member.
RRFS_ENSEMBLE_MEMBERS: frozenset[str] = frozenset({f"m{i:03d}" for i in range(1, 6)})

__all__ = ["GRID_KIND", "RRFS_ENSEMBLE_MEMBERS", "VARIABLE_MAP"]

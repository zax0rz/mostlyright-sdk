"""HAFS (Hurricane Analysis and Forecast System) — storm-following grid."""

from __future__ import annotations

VARIABLE_MAP: dict[str, tuple[str, str]] = {
    "temp_k_2m": ("TMP", "2 m above ground"),
    "dewpoint_k_2m": ("DPT", "2 m above ground"),
    "wind_u_ms_10m": ("UGRD", "10 m above ground"),
    "wind_v_ms_10m": ("VGRD", "10 m above ground"),
    "wind_gust_ms": ("GUST", "surface"),
    "precip_mm_1h": ("APCP", "surface"),
    "pressure_pa_surface": ("PRES", "surface"),
    "pressure_pa_mslp": ("MSLMA", "mean sea level"),
}

GRID_KIND: str = "rotated_latlon_storm_following"

#: HAFS flavors — A (operational) + B (experimental).
HAFS_FLAVORS: frozenset[str] = frozenset({"a", "b"})

#: HAFS products — parent (continental nest) vs storm (storm-centered nest);
#: atm (atmospheric) vs sfc (surface).
HAFS_PRODUCTS: frozenset[str] = frozenset({"parent.atm", "storm.atm", "parent.sfc", "storm.sfc"})

__all__ = ["GRID_KIND", "HAFS_FLAVORS", "HAFS_PRODUCTS", "VARIABLE_MAP"]

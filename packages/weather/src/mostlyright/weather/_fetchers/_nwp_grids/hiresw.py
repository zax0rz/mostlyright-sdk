"""HiResW (High Resolution Window) — retiring 2026-08-31."""

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

GRID_KIND: str = "lambert_conformal_conus_2p5km"

#: HiResW products — ARW + FV3 dynamical cores at 2.5km + 5km resolutions.
HIRESW_PRODUCTS: frozenset[str] = frozenset({"arw_2p5km", "fv3_2p5km", "arw_5km", "fv3_5km"})

#: HiResW domains.
HIRESW_DOMAINS: frozenset[str] = frozenset({"conus", "ak", "hi", "guam", "pr"})

#: HiResW members. ARW has a 2-member ensemble; FV3 is deterministic.
HIRESW_MEMBERS: frozenset[str] = frozenset({"", "mem2"})

__all__ = [
    "GRID_KIND",
    "HIRESW_DOMAINS",
    "HIRESW_MEMBERS",
    "HIRESW_PRODUCTS",
    "VARIABLE_MAP",
]

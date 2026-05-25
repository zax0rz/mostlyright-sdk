"""NAM (North American Mesoscale) — retiring 2026-08-31 per NWS scn26-47."""

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

GRID_KIND: str = "lambert_conformal_conus_12km"

#: NAM products — nest grids + parent grids.
NAM_PRODUCTS: frozenset[str] = frozenset(
    {
        "conusnest.hiresf",
        "firewxnest.hiresf",
        "alaskanest.hiresf",
        "hawaiinest.hiresf",
        "priconest.hiresf",
        "awphys",
        "awip12",
        "bgrdsf",
    }
)

__all__ = ["GRID_KIND", "NAM_PRODUCTS", "VARIABLE_MAP"]

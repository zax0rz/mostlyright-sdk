"""HREF (High-Resolution Ensemble Forecast) — retiring 2026-08-31."""

from __future__ import annotations

VARIABLE_MAP: dict[str, tuple[str, str]] = {
    "temp_k_2m": ("TMP", "2 m above ground"),
    "dewpoint_k_2m": ("DPT", "2 m above ground"),
    "wind_u_ms_10m": ("UGRD", "10 m above ground"),
    "wind_v_ms_10m": ("VGRD", "10 m above ground"),
    "precip_mm_1h": ("APCP", "surface"),
    "pressure_pa_mslp": ("MSLMA", "mean sea level"),
}

GRID_KIND: str = "lambert_conformal_conus_3km_ensemble"

#: HREF products — statistical aggregates over the 8-member ensemble.
HREF_PRODUCTS: frozenset[str] = frozenset({"mean", "pmmn", "lpmm", "avrg", "sprd", "prob", "eas"})

#: HREF domains.
HREF_DOMAINS: frozenset[str] = frozenset({"conus", "ak", "hi", "pr"})

__all__ = ["GRID_KIND", "HREF_DOMAINS", "HREF_PRODUCTS", "VARIABLE_MAP"]

"""GEPS (Canadian Global Ensemble) — member aggregates + raw layouts."""

from __future__ import annotations

VARIABLE_MAP: dict[str, tuple[str, str]] = {
    "temp_k_2m": ("TMP", "TGL_2"),
    "dewpoint_k_2m": ("DPT", "TGL_2"),
    "wind_u_ms_10m": ("UGRD", "TGL_10"),
    "wind_v_ms_10m": ("VGRD", "TGL_10"),
    # NOTE: APCP is accumulated precipitation; quants must verify the
    # accumulation window matches their 1h convention. Canonical column
    # name kept schema-aligned (``precip_mm_1h``) so the row builder writes
    # into the documented column instead of a rogue ``precip_mm_total`` one.
    "precip_mm_1h": ("APCP", "Sfc"),
    "pressure_pa_surface": ("PRES", "Sfc"),
    "pressure_pa_mslp": ("PRMSL", "MSL"),
}

GRID_KIND: str = "regular_latlon_global_0p5"

#: GEPS layouts. ``allmbrs`` / ``raw`` → ``ensemble/geps/grib2/raw/...``
#: (each file contains all 20 members stacked). ``prod`` →
#: ``ensemble/geps/grib2/products/...`` (statistical product files).
GEPS_MEMBERS: frozenset[str] = frozenset({"allmbrs", "raw", "prod"})

__all__ = ["GEPS_MEMBERS", "GRID_KIND", "VARIABLE_MAP"]

"""CFS (Climate Forecast System) 4-member ensemble — minimal climate variables."""

from __future__ import annotations

VARIABLE_MAP: dict[str, tuple[str, str]] = {
    "temp_k_2m": ("TMP", "2 m above ground"),
    "wind_u_ms_10m": ("UGRD", "10 m above ground"),
    "wind_v_ms_10m": ("VGRD", "10 m above ground"),
    # NOTE: PRATE is a precipitation RATE (kg m-2 s-1), not a 1h accumulation;
    # quants must convert to true accumulation if needed. Canonical column
    # name kept schema-aligned (``precip_mm_1h``) so the row builder writes
    # into the documented column instead of a rogue ``precip_mm_total`` one.
    "precip_mm_1h": ("PRATE", "surface"),
    "pressure_pa_mslp": ("PRMSL", "mean sea level"),
}

GRID_KIND: str = "regular_latlon_global_1p0"

#: CFS ensemble members — 4 perturbations (01..04).
CFS_MEMBERS: frozenset[str] = frozenset({"01", "02", "03", "04"})

__all__ = ["CFS_MEMBERS", "GRID_KIND", "VARIABLE_MAP"]

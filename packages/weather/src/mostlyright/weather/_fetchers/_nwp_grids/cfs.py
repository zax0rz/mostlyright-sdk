"""CFS (Climate Forecast System) 4-member ensemble — minimal climate variables."""

from __future__ import annotations

VARIABLE_MAP: dict[str, tuple[str, str]] = {
    "temp_k_2m": ("TMP", "2 m above ground"),
    "wind_u_ms_10m": ("UGRD", "10 m above ground"),
    "wind_v_ms_10m": ("VGRD", "10 m above ground"),
    "pressure_pa_mslp": ("PRMSL", "mean sea level"),
    # NOTE: CFS publishes precipitation as PRATE (kg m-2 s-1), a flux —
    # NOT a 1h accumulation. The row builder does NO unit conversion, so
    # writing PRATE directly into the canonical ``precip_mm_1h`` column
    # would under-report by the (rate x seconds) accumulation factor.
    # Precip omitted from CFS for Wave 2; PLAN-09 (research wiring) lands
    # the rate->accumulation conversion layer and re-introduces the
    # ``precip_mm_1h`` mapping with ``PRATE x 3600`` (or window-aware
    # conversion for >1h forecast steps).
}

GRID_KIND: str = "regular_latlon_global_1p0"

#: CFS ensemble members — 4 perturbations (01..04).
CFS_MEMBERS: frozenset[str] = frozenset({"01", "02", "03", "04"})

__all__ = ["CFS_MEMBERS", "GRID_KIND", "VARIABLE_MAP"]

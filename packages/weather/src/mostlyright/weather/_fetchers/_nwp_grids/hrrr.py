"""HRRR variable map + grid metadata.

HRRR (High-Resolution Rapid Refresh) is a 3 km Lambert Conformal Conic
CONUS model run hourly by NCEP. The sfcf product carries the 13 fields
mostlyright extracts at the 2-m / 10-m / surface levels.

The variable strings here must match exactly what appears in the ``.idx``
file produced by NCEP's wgrib2 indexer. mostlyright keeps a minimal set;
adding fields means lifting the corresponding GRIB2 record id from a
real cycle's ``.idx``.
"""

from __future__ import annotations

#: HRRR surface variables → ``(idx_variable, idx_level)``.
#:
#: Names on the left are mostlyright canonical output columns (also used
#: as keys in the returned DataFrame). Units are model-native (Kelvin
#: for temperature, m/s for wind, mm for precip, % for humidity / cloud
#: cover). Per Phase 3.2 lock #4 in 03.2-RESEARCH.md: NO unit conversion
#: helpers in v0.1 — quants do their own.
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


#: Grid label recorded on every extracted row for auditing.
GRID_KIND: str = "lambert_conformal_conus"


__all__ = ["GRID_KIND", "VARIABLE_MAP"]

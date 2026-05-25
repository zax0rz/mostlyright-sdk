"""GFS variable map + grid metadata.

GFS (Global Forecast System) is a 0.25-degree regular lat/lon model run
every 6 hours by NCEP. The pgrb2.0p25 product carries the same surface
fields mostlyright extracts from HRRR/NBM, but on a global regular grid
so the BallTree is built over the full ~1M grid cells once and reused.

Mean-sea-level pressure in GFS uses the ``PRMSL`` variable id (HRRR
uses ``MSLMA``). The mostlyright lift treats these as same logical
column (``pressure_pa_mslp``) because downstream consumers see one
canonical name regardless of source model.
"""

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
    "pressure_pa_mslp": ("PRMSL", "mean sea level"),
}


GRID_KIND: str = "regular_latlon_global_0p25"


__all__ = ["GRID_KIND", "VARIABLE_MAP"]

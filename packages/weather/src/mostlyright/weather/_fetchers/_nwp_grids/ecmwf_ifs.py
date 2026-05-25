"""ECMWF IFS variable map -- eccodes ``param`` keys.

ECMWF Open Data uses single-letter / digit-prefix param codes ("2t" for
2-m temperature, "msl" for mean sea level pressure, "tp" for total
precipitation, etc.). The level info comes from the ``.index`` line's
``levtype`` + optional ``levelist`` rather than a wgrib2-style human
string.

Precipitation deliberately omitted: ECMWF ``tp`` is in METERS, NOT mm.
Writing the raw decoded value into the canonical ``precip_mm_1h`` column
(which advertises millimeters) would under-report precipitation by 1000x.
PLAN-09 (research wiring) lands the unit-conversion layer (``tp * 1000``)
and re-introduces the mapping then.
"""

from __future__ import annotations

VARIABLE_MAP: dict[str, tuple[str, str]] = {
    "temp_k_2m": ("2t", "sfc"),
    "dewpoint_k_2m": ("2d", "sfc"),
    "wind_u_ms_10m": ("10u", "sfc"),
    "wind_v_ms_10m": ("10v", "sfc"),
    "wind_gust_ms": ("10fg", "sfc"),
    "pressure_pa_surface": ("sp", "sfc"),
    "pressure_pa_mslp": ("msl", "sfc"),
}

GRID_KIND: str = "regular_latlon_global_0p25"

__all__ = ["GRID_KIND", "VARIABLE_MAP"]

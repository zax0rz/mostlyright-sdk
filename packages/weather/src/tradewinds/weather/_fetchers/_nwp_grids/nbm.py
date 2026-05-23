"""NBM variable map + grid metadata.

NBM (National Blend of Models) is a 13-km Lambert Conformal CONUS blend
issued hourly. The core product carries deterministic guidance for the
same surface fields tradewinds extracts; v5.0 (cutover 2026-05-05) adds
probabilistic siblings without changing the deterministic field id or
level descriptors tradewinds reads.

See Pitfall 5 in ``.planning/phases/03.2-.../03.2-RESEARCH.md`` — the
``.idx`` and path layout are stable across the v4 → v5 cutover; no
date-dependent branching needed here.
"""

from __future__ import annotations

VARIABLE_MAP: dict[str, tuple[str, str]] = {
    "temp_k_2m": ("TMP", "2 m above ground"),
    "dewpoint_k_2m": ("DPT", "2 m above ground"),
    "relative_humidity_pct_2m": ("RH", "2 m above ground"),
    "wind_u_ms_10m": ("UGRD", "10 m above ground"),
    "wind_v_ms_10m": ("VGRD", "10 m above ground"),
    "wind_gust_ms": ("GUST", "10 m above ground"),
    "precip_mm_1h": ("APCP", "surface"),
    "pressure_pa_mslp": ("MSLMA", "mean sea level"),
}


GRID_KIND: str = "lambert_conformal_conus_blend"


__all__ = ["GRID_KIND", "VARIABLE_MAP"]

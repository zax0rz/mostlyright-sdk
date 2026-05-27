"""NCEP (NOAA, United States) Open-Meteo models — Phase 20 OM-03 Tier 1.

8 models: gfs_seamless, gfs_global, gfs_graphcast025, aigfs025, hgefs025,
ncep_hrrr_conus, ncep_nbm_conus, ncep_nam_conus.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

MODELS: frozenset[str] = frozenset(
    {
        "gfs_seamless",
        "gfs_global",
        "gfs_graphcast025",
        "aigfs025",
        "hgefs025",
        "ncep_hrrr_conus",
        "ncep_nbm_conus",
        "ncep_nam_conus",
    }
)

CYCLE_HOURS: dict[str, tuple[int, ...]] = {
    "gfs_seamless": (0, 6, 12, 18),
    "gfs_global": (0, 6, 12, 18),
    "gfs_graphcast025": (0, 6, 12, 18),
    "aigfs025": (0, 6, 12, 18),
    "hgefs025": (0, 6, 12, 18),
    "ncep_hrrr_conus": tuple(range(24)),
    "ncep_nbm_conus": tuple(range(24)),
    "ncep_nam_conus": (0, 6, 12, 18),
}

AVAILABILITY_FLOOR: dict[str, datetime] = {
    "gfs_seamless": datetime(2024, 1, 1, tzinfo=UTC),
    "gfs_global": datetime(2024, 1, 1, tzinfo=UTC),
    "gfs_graphcast025": datetime(2024, 1, 1, tzinfo=UTC),
    "aigfs025": datetime(2026, 1, 7, tzinfo=UTC),
    "hgefs025": datetime(2026, 1, 7, tzinfo=UTC),
    "ncep_hrrr_conus": datetime(2024, 1, 1, tzinfo=UTC),
    "ncep_nbm_conus": datetime(2024, 10, 8, tzinfo=UTC),
    "ncep_nam_conus": datetime(2024, 1, 1, tzinfo=UTC),
}

PUBLISH_LAG: dict[str, timedelta] = {
    "gfs_seamless": timedelta(hours=6),
    "gfs_global": timedelta(hours=6),
    "gfs_graphcast025": timedelta(hours=6),
    "aigfs025": timedelta(hours=6),
    "hgefs025": timedelta(hours=6),
    "ncep_nam_conus": timedelta(hours=2),
    "ncep_hrrr_conus": timedelta(hours=2),
    "ncep_nbm_conus": timedelta(hours=2),
}

__all__ = ["AVAILABILITY_FLOOR", "CYCLE_HOURS", "MODELS", "PUBLISH_LAG"]

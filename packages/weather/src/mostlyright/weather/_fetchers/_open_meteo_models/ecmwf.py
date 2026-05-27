"""ECMWF Open-Meteo models — Phase 20 OM-03 Tier 2.

3 models: ecmwf_ifs025, ecmwf_ifs_hres, ecmwf_aifs025_single.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

MODELS: frozenset[str] = frozenset(
    {
        "ecmwf_ifs025",
        "ecmwf_ifs_hres",
        "ecmwf_aifs025_single",
    }
)

CYCLE_HOURS: dict[str, tuple[int, ...]] = {
    "ecmwf_ifs025": (0, 6, 12, 18),
    "ecmwf_ifs_hres": (0, 6, 12, 18),
    "ecmwf_aifs025_single": (0, 6, 12, 18),
}

AVAILABILITY_FLOOR: dict[str, datetime] = {
    "ecmwf_ifs025": datetime(2024, 1, 1, tzinfo=UTC),
    "ecmwf_ifs_hres": datetime(2024, 1, 1, tzinfo=UTC),
    "ecmwf_aifs025_single": datetime(2024, 3, 14, tzinfo=UTC),
}

PUBLISH_LAG: dict[str, timedelta] = {
    "ecmwf_ifs025": timedelta(hours=6),
    "ecmwf_ifs_hres": timedelta(hours=6),
    "ecmwf_aifs025_single": timedelta(hours=6),
}

__all__ = ["AVAILABILITY_FLOOR", "CYCLE_HOURS", "MODELS", "PUBLISH_LAG"]

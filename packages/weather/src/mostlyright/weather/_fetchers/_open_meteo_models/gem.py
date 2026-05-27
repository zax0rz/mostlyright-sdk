"""GEM Canada (Environment Canada / CMC) Open-Meteo models — Phase 20 OM-03 Tier 7.

3 models: cmc_gem_gdps, cmc_gem_rdps, cmc_gem_hrdps.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

MODELS: frozenset[str] = frozenset(
    {
        "cmc_gem_gdps",
        "cmc_gem_rdps",
        "cmc_gem_hrdps",
    }
)

CYCLE_HOURS: dict[str, tuple[int, ...]] = {
    "cmc_gem_gdps": (0, 12),
    "cmc_gem_rdps": (0, 6, 12, 18),
    "cmc_gem_hrdps": (0, 6, 12, 18),
}

AVAILABILITY_FLOOR: dict[str, datetime] = {
    "cmc_gem_gdps": datetime(2024, 1, 1, tzinfo=UTC),
    "cmc_gem_rdps": datetime(2024, 1, 1, tzinfo=UTC),
    "cmc_gem_hrdps": datetime(2024, 1, 1, tzinfo=UTC),
}

PUBLISH_LAG: dict[str, timedelta] = {
    "cmc_gem_gdps": timedelta(hours=6),
    "cmc_gem_rdps": timedelta(hours=4),
    "cmc_gem_hrdps": timedelta(hours=2),
}

__all__ = ["AVAILABILITY_FLOOR", "CYCLE_HOURS", "MODELS", "PUBLISH_LAG"]

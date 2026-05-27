"""Asia + Oceania Open-Meteo models — Phase 20 OM-03 Tier 5.

8 models: jma_seamless, jma_gsm, jma_msm, kma_seamless, kma_gdps, kma_ldps,
cma_grapes_global, bom_access_global.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

MODELS: frozenset[str] = frozenset(
    {
        "jma_seamless",
        "jma_gsm",
        "jma_msm",
        "kma_seamless",
        "kma_gdps",
        "kma_ldps",
        "cma_grapes_global",
        "bom_access_global",
    }
)

CYCLE_HOURS: dict[str, tuple[int, ...]] = {
    "jma_seamless": (0, 6, 12, 18),
    "jma_gsm": (0, 6, 12, 18),
    "jma_msm": (0, 3, 6, 9, 12, 15, 18, 21),
    "kma_seamless": (0, 6, 12, 18),
    "kma_gdps": (0, 6, 12, 18),
    "kma_ldps": (0, 3, 6, 9, 12, 15, 18, 21),
    "cma_grapes_global": (0, 6, 12, 18),
    "bom_access_global": (0, 6, 12, 18),
}

AVAILABILITY_FLOOR: dict[str, datetime] = {
    "jma_seamless": datetime(2018, 1, 1, tzinfo=UTC),
    "jma_gsm": datetime(2018, 1, 1, tzinfo=UTC),
    "jma_msm": datetime(2018, 1, 1, tzinfo=UTC),
    "kma_seamless": datetime(2024, 1, 1, tzinfo=UTC),
    "kma_gdps": datetime(2024, 1, 1, tzinfo=UTC),
    "kma_ldps": datetime(2024, 1, 1, tzinfo=UTC),
    "cma_grapes_global": datetime(2024, 1, 1, tzinfo=UTC),
    "bom_access_global": datetime(2024, 1, 1, tzinfo=UTC),
}

PUBLISH_LAG: dict[str, timedelta] = {
    "jma_seamless": timedelta(hours=6),
    "jma_gsm": timedelta(hours=6),
    "jma_msm": timedelta(hours=2),
    "kma_seamless": timedelta(hours=6),
    "kma_gdps": timedelta(hours=6),
    "kma_ldps": timedelta(hours=2),
    "cma_grapes_global": timedelta(hours=6),
    "bom_access_global": timedelta(hours=6),
}

__all__ = ["AVAILABILITY_FLOOR", "CYCLE_HOURS", "MODELS", "PUBLISH_LAG"]

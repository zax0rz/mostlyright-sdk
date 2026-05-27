"""DWD (Germany) Open-Meteo models — Phase 20 OM-03 Tier 3.

5 models: dwd_icon_seamless, dwd_icon_global, dwd_icon_eu, dwd_icon_d2,
dwd_icon_d2_15min.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

MODELS: frozenset[str] = frozenset(
    {
        "dwd_icon_seamless",
        "dwd_icon_global",
        "dwd_icon_eu",
        "dwd_icon_d2",
        "dwd_icon_d2_15min",
    }
)

CYCLE_HOURS: dict[str, tuple[int, ...]] = {
    "dwd_icon_seamless": (0, 6, 12, 18),
    "dwd_icon_global": (0, 6, 12, 18),
    "dwd_icon_eu": (0, 6, 12, 18),
    "dwd_icon_d2": (0, 3, 6, 9, 12, 15, 18, 21),
    "dwd_icon_d2_15min": (0, 3, 6, 9, 12, 15, 18, 21),
}

AVAILABILITY_FLOOR: dict[str, datetime] = {
    "dwd_icon_seamless": datetime(2024, 1, 1, tzinfo=UTC),
    "dwd_icon_global": datetime(2024, 1, 1, tzinfo=UTC),
    "dwd_icon_eu": datetime(2024, 1, 1, tzinfo=UTC),
    "dwd_icon_d2": datetime(2024, 1, 1, tzinfo=UTC),
    "dwd_icon_d2_15min": datetime(2024, 1, 1, tzinfo=UTC),
}

PUBLISH_LAG: dict[str, timedelta] = {
    "dwd_icon_seamless": timedelta(hours=4),
    "dwd_icon_global": timedelta(hours=4),
    "dwd_icon_eu": timedelta(hours=4),
    "dwd_icon_d2": timedelta(hours=2),
    "dwd_icon_d2_15min": timedelta(hours=2),
}

__all__ = ["AVAILABILITY_FLOOR", "CYCLE_HOURS", "MODELS", "PUBLISH_LAG"]

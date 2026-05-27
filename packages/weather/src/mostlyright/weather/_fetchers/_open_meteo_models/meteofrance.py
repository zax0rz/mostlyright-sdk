"""Météo-France Open-Meteo models — Phase 20 OM-03 Tier 4.

6 models: meteofrance_seamless, meteofrance_arpege_world025,
meteofrance_arpege_europe, meteofrance_arome_france0025,
meteofrance_arome_france_hd, meteofrance_arome_france_hd_15min.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

MODELS: frozenset[str] = frozenset(
    {
        "meteofrance_seamless",
        "meteofrance_arpege_world025",
        "meteofrance_arpege_europe",
        "meteofrance_arome_france0025",
        "meteofrance_arome_france_hd",
        "meteofrance_arome_france_hd_15min",
    }
)

CYCLE_HOURS: dict[str, tuple[int, ...]] = {
    "meteofrance_seamless": (0, 6, 12, 18),
    "meteofrance_arpege_world025": (0, 6, 12, 18),
    "meteofrance_arpege_europe": (0, 6, 12, 18),
    "meteofrance_arome_france0025": (0, 3, 6, 9, 12, 15, 18, 21),
    "meteofrance_arome_france_hd": (0, 3, 6, 9, 12, 15, 18, 21),
    "meteofrance_arome_france_hd_15min": (0, 3, 6, 9, 12, 15, 18, 21),
}

AVAILABILITY_FLOOR: dict[str, datetime] = {
    "meteofrance_seamless": datetime(2024, 1, 1, tzinfo=UTC),
    "meteofrance_arpege_world025": datetime(2024, 1, 1, tzinfo=UTC),
    "meteofrance_arpege_europe": datetime(2024, 1, 1, tzinfo=UTC),
    "meteofrance_arome_france0025": datetime(2024, 1, 1, tzinfo=UTC),
    "meteofrance_arome_france_hd": datetime(2024, 1, 1, tzinfo=UTC),
    "meteofrance_arome_france_hd_15min": datetime(2024, 1, 1, tzinfo=UTC),
}

PUBLISH_LAG: dict[str, timedelta] = {
    "meteofrance_seamless": timedelta(hours=4),
    "meteofrance_arpege_world025": timedelta(hours=6),
    "meteofrance_arpege_europe": timedelta(hours=4),
    "meteofrance_arome_france0025": timedelta(hours=2),
    "meteofrance_arome_france_hd": timedelta(hours=2),
    "meteofrance_arome_france_hd_15min": timedelta(hours=2),
}

__all__ = ["AVAILABILITY_FLOOR", "CYCLE_HOURS", "MODELS", "PUBLISH_LAG"]

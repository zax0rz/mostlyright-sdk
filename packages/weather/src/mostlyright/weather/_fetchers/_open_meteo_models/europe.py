"""Europe (other) Open-Meteo models — Phase 20 OM-03 Tier 6.

3 models in the v0.1 catalog: ukmo_global_deterministic_10km,
ukmo_uk_deterministic_2km, metno_nordic_pp.

MeteoSwiss CH1/CH2, KNMI Harmonie variants, DMI Harmonie, and
ItaliaMeteo ICON appear in the open-meteo-data catalog but their cycle
metadata is less stable as of 2026-05-27. Reserved for a v0.3+
release per Phase 20 D-02.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

MODELS: frozenset[str] = frozenset(
    {
        "ukmo_global_deterministic_10km",
        "ukmo_uk_deterministic_2km",
        "metno_nordic_pp",
    }
)

CYCLE_HOURS: dict[str, tuple[int, ...]] = {
    "ukmo_global_deterministic_10km": (0, 6, 12, 18),
    "ukmo_uk_deterministic_2km": (0, 3, 6, 9, 12, 15, 18, 21),
    "metno_nordic_pp": tuple(range(24)),
}

AVAILABILITY_FLOOR: dict[str, datetime] = {
    "ukmo_global_deterministic_10km": datetime(2024, 1, 1, tzinfo=UTC),
    "ukmo_uk_deterministic_2km": datetime(2024, 1, 1, tzinfo=UTC),
    "metno_nordic_pp": datetime(2024, 1, 1, tzinfo=UTC),
}

PUBLISH_LAG: dict[str, timedelta] = {
    "ukmo_global_deterministic_10km": timedelta(hours=6),
    "ukmo_uk_deterministic_2km": timedelta(hours=2),
    "metno_nordic_pp": timedelta(hours=2),
}

__all__ = ["AVAILABILITY_FLOOR", "CYCLE_HOURS", "MODELS", "PUBLISH_LAG"]

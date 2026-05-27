"""Open-Meteo 36-model registry + cycle-math primitives (Phase 20 OM-03).

The public registry is built by merging per-family modules:

- ``ncep`` — NCEP (NOAA, United States) — 8 models
- ``ecmwf`` — ECMWF (European Centre) — 3 models
- ``dwd`` — DWD (Germany) — 5 models
- ``meteofrance`` — Météo-France — 6 models
- ``asia_oceania`` — JMA, KMA, CMA, BoM — 8 models
- ``europe`` — UKMO, MetNo — 3 models (MeteoSwiss/KNMI/DMI/ItaliaMeteo deferred per D-02)
- ``gem`` — GEM Canada (CMC) — 3 models

Total: 8 + 3 + 5 + 6 + 8 + 3 + 3 = 36 (Phase 20 D-02).

Pure-function cycle-math primitives are re-exported from
``cycle_math.py`` for direct import by the fetcher (PLAN-04) and Live
mode (PLAN-05).
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from . import (
    asia_oceania,
    dwd,
    ecmwf,
    europe,
    gem,
    meteofrance,
    ncep,
)
from .cycle_math import (
    floor_to_cycle,
    issued_at_from_live_cycle_math,
    issued_at_from_previous_day,
)

_FAMILIES = (ncep, ecmwf, dwd, meteofrance, asia_oceania, europe, gem)


def _merge_models() -> frozenset[str]:
    seen: set[str] = set()
    for fam in _FAMILIES:
        overlap = seen & fam.MODELS
        if overlap:
            raise RuntimeError(f"model keys duplicated across families: {overlap}")
        seen |= fam.MODELS
    return frozenset(seen)


def _merge_dict(attr: str) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for fam in _FAMILIES:
        for k, v in getattr(fam, attr).items():
            if k in merged:
                raise RuntimeError(f"{attr}: duplicate key {k!r} across families")
            merged[k] = v
    return merged


OPEN_METEO_MODELS: frozenset[str] = _merge_models()
CYCLE_HOURS: dict[str, tuple[int, ...]] = _merge_dict("CYCLE_HOURS")
AVAILABILITY_FLOOR: dict[str, datetime] = _merge_dict("AVAILABILITY_FLOOR")
PUBLISH_LAG: dict[str, timedelta] = _merge_dict("PUBLISH_LAG")


__all__ = [
    "AVAILABILITY_FLOOR",
    "CYCLE_HOURS",
    "OPEN_METEO_MODELS",
    "PUBLISH_LAG",
    "floor_to_cycle",
    "issued_at_from_live_cycle_math",
    "issued_at_from_previous_day",
]

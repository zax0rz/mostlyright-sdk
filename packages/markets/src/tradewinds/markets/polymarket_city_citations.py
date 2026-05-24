"""Per-Polymarket-city citation registry for the Phase 8 US-coverage additions.

Audit trail for the empirical proof that drove each US-city station
mapping in ``polymarket_city_stations.json``. The Polymarket event page
linked here is the canonical issuer-documented source whose
``resolutionSource`` field (or embedded description) carries the
Wunderground URL that pins the ICAO.

If a Polymarket market is renamed / deleted / relisted the citation MAY
rot — at that point an operator must re-verify against a live event and
either update the citation or carry an open parity ticket; never
silently mutate the station mapping.
"""

from __future__ import annotations

from typing import Final

#: Per-Polymarket-city citation URL: the canonical Polymarket event whose
#: ``resolutionSource`` field empirically proves the station mapping in
#: ``polymarket_city_stations.json``. The trailing parenthetical names the
#: Wunderground URL fragment + ICAO that completes the proof.
POLYMARKET_CITY_CITATIONS: Final[dict[str, str]] = {
    "nyc": (
        "https://polymarket.com/event/highest-temperature-in-nyc "
        "(resolves via wunderground.com/dashboard/pws/KLGA — NOT KNYC)"
    ),
    "chicago": (
        "https://polymarket.com/event/highest-temperature-in-chicago "
        "(resolves via wunderground.com/.../KORD — NOT KMDW)"
    ),
    "los_angeles": (
        "https://polymarket.com/event/highest-temperature-in-la "
        "(resolves via wunderground.com/.../KLAX)"
    ),
    "miami": (
        "https://polymarket.com/event/highest-temperature-in-miami (wunderground.com/.../KMIA)"
    ),
    "denver": (
        "https://polymarket.com/event/highest-temperature-in-denver (wunderground.com/.../KDEN)"
    ),
    "boston": (
        "https://polymarket.com/event/highest-temperature-in-boston (wunderground.com/.../KBOS)"
    ),
    "austin": (
        "https://polymarket.com/event/highest-temperature-in-austin (wunderground.com/.../KAUS)"
    ),
    "washington_dc": (
        "https://polymarket.com/event/highest-temperature-in-dc (wunderground.com/.../KDCA)"
    ),
    "philadelphia": (
        "https://polymarket.com/event/highest-temperature-in-philly (wunderground.com/.../KPHL)"
    ),
    "san_francisco": (
        "https://polymarket.com/event/highest-temperature-in-sf (wunderground.com/.../KSFO)"
    ),
    "seattle": (
        "https://polymarket.com/event/highest-temperature-in-seattle (wunderground.com/.../KSEA)"
    ),
    "atlanta": (
        "https://polymarket.com/event/highest-temperature-in-atlanta (wunderground.com/.../KATL)"
    ),
    "houston": (
        "https://polymarket.com/event/highest-temperature-in-houston (wunderground.com/.../KIAH)"
    ),
    "dallas": (
        "https://polymarket.com/event/highest-temperature-in-dallas (wunderground.com/.../KDFW)"
    ),
    "phoenix": (
        "https://polymarket.com/event/highest-temperature-in-phoenix (wunderground.com/.../KPHX)"
    ),
    "minneapolis": (
        "https://polymarket.com/event/highest-temperature-in-msp (wunderground.com/.../KMSP)"
    ),
    "detroit": (
        "https://polymarket.com/event/highest-temperature-in-detroit (wunderground.com/.../KDTW)"
    ),
}


__all__ = ["POLYMARKET_CITY_CITATIONS"]

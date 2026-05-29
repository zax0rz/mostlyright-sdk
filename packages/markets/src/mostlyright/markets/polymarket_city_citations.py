"""Per-Polymarket-city citation registry for the US-coverage roster.

Audit trail for the empirical proof that drove each US-city station
mapping in ``polymarket_city_stations.json``. The Polymarket event page
linked here is the canonical issuer-documented source whose
``resolutionSource`` field (or embedded description) carries the
Wunderground URL that pins the ICAO.

If a Polymarket market is renamed / deleted / relisted the citation MAY
rot — at that point an operator must re-verify against a live event and
either update the citation or carry an open parity ticket; never
silently mutate the station mapping.

Phase 23 (2026-05-29) reconciled this to the live 11-city US roster:
Houston moved KIAH→KHOU, Dallas KDFW→KDAL, Denver KDEN→KBKF, and six
cities (Boston, DC, Philadelphia, Phoenix, Minneapolis, Detroit) left the
Polymarket roster — their citations were removed (station records stay in
the catalog as bare weather stations).
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
    "austin": (
        "https://polymarket.com/event/highest-temperature-in-austin (wunderground.com/.../KAUS)"
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
        "https://polymarket.com/event/highest-temperature-in-houston "
        "(resolves via wunderground.com/.../KHOU — Phase 23 move off KIAH; KIAH stays Kalshi)"
    ),
    "dallas": (
        "https://polymarket.com/event/highest-temperature-in-dallas "
        "(resolves via wunderground.com/.../KDAL — Phase 23 move off KDFW; KDFW stays Kalshi)"
    ),
    "denver": (
        "https://polymarket.com/event/highest-temperature-in-denver "
        "(resolves via wunderground.com/.../KBKF — Phase 23 move off KDEN; KDEN stays Kalshi)"
    ),
}


__all__ = ["POLYMARKET_CITY_CITATIONS"]

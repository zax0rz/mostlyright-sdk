"""Per-event station resolution for multi-airport Polymarket cities.

Most Polymarket weather markets resolve against a single station per city
(e.g. ``london -> EGLL``). A few cities use distinct airports for high vs
low (e.g. Paris uses LFPG for "highest temperature" markets but LFPB for
"lowest temperature" markets — historically LFPB's open-rural exposure
produces colder overnight lows than CDG's tarmac).

This module implements that lookup against
``polymarket_city_stations.json``. It also gates the two markets whose
data source ships in v0.2 (Taipei CWA, Hong Kong-lowest HKO) by raising
:class:`tradewinds.international.DeferredMarketError`.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from tradewinds.international import DEFERRED_STATIONS, DeferredMarketError

__all__ = [
    "DEFERRED_HK_MEASURES",
    "DEFERRED_STATION_MEASURES",
    "load_polymarket_city_stations",
    "resolve_station_for_event",
]


#: Path to the bundled ``polymarket_city_stations.json``. Loaded lazily by
#: :func:`load_polymarket_city_stations` and cached in module state.
_CITY_STATIONS_PATH: Path = Path(__file__).parent / "polymarket_city_stations.json"

#: Process-level cache. ``None`` means "not yet loaded".
_CACHED_CITY_STATIONS: dict[str, dict[str, str]] | None = None

#: Hong Kong: only the "low" market defers (HKO is the issuer for daily
#: lows). The "high" market resolves fine against routine METAR.
DEFERRED_HK_MEASURES: frozenset[str] = frozenset({"low"})

#: Per-(icao, measure) defer table built from ``DEFERRED_STATIONS`` + the
#: HK-low carve-out. ``measure`` is one of ``"high"``, ``"low"``, or
#: ``"default"`` (matches the JSON keys + the resolver output).
DEFERRED_STATION_MEASURES: frozenset[tuple[str, str]] = frozenset(
    {
        # Hong Kong: only "low" defers — keep "high" and "default" routable.
        ("VHHH", "low"),
        # Taipei: every measure defers until the CWA client lands.
        ("RCTP", "high"),
        ("RCTP", "low"),
        ("RCTP", "default"),
    }
)

#: Regex selecting tokens that signal a "high" (daily-max) market.
_HIGH_RE = re.compile(r"\b(highest|high|hottest|warmest|max(?:imum)?)\b", re.IGNORECASE)

#: Regex selecting tokens that signal a "low" (daily-min) market.
_LOW_RE = re.compile(r"\b(lowest|low|coldest|coolest|min(?:imum)?)\b", re.IGNORECASE)


def load_polymarket_city_stations() -> dict[str, dict[str, str]]:
    """Load (and cache) the bundled city → station map.

    Returns a deep-copy on each call so callers cannot mutate the
    cached dict (one dict, many readers).

    Schema::

        {
            "london":  {"default": "EGLL"},
            "paris":   {"high": "LFPG", "low": "LFPB", "default": "LFPG"},
            ...
        }

    The ``"default"`` key is what the resolver falls back to when an event
    title has no high/low keyword. Cities with no split (single airport)
    only set ``"default"``.
    """
    global _CACHED_CITY_STATIONS
    if _CACHED_CITY_STATIONS is None:
        with _CITY_STATIONS_PATH.open() as f:
            _CACHED_CITY_STATIONS = json.load(f)
    # Defensive deep-copy: callers must not mutate the shared cache.
    return {city: dict(stations) for city, stations in _CACHED_CITY_STATIONS.items()}


def _detect_measure(text: str) -> str:
    """Return ``"high"``, ``"low"``, or ``"default"`` from event title/slug.

    Decision table:
      - Exactly one of {high, low} keyword present → that measure.
      - Both keywords present → ``"default"``. A title that mentions both
        "high" AND "low" is ambiguous (e.g. an explainer market like
        ``"Will Paris see a record-low AND record-high this week?"``) and
        the safer answer is to route to whichever airport the city map
        nominated as the default measure — silently picking ``low`` for
        such an event would tag the wrong airport for the wrong resolution.
      - Neither keyword present → ``"default"``.
    """
    has_low = _LOW_RE.search(text) is not None
    has_high = _HIGH_RE.search(text) is not None
    if has_low and not has_high:
        return "low"
    if has_high and not has_low:
        return "high"
    return "default"


def resolve_station_for_event(
    event: dict,
    city_map: dict[str, dict],
) -> tuple[str, str]:
    """Resolve a Polymarket event payload to ``(icao, measure)``.

    Args:
        event: Polymarket event dict. Must carry at least ``city``
            (lowercase city key matching ``city_map``). Optional
            ``title``/``slug`` fields are scanned for high/low keywords.
        city_map: Mapping returned by :func:`load_polymarket_city_stations`
            (or a test fixture with the same shape). Passing the map in
            explicitly keeps this function pure — no hidden global state —
            and lets tests inject minimal fixtures.

    Returns:
        Tuple of ``(icao, measure)`` where ``measure`` is ``"high"``,
        ``"low"``, or ``"default"``.

    Raises:
        KeyError: ``event["city"]`` is missing from ``city_map``.
        DeferredMarketError: the resolved (icao, measure) pair routes to a
            data source that's deferred to v0.2 (Taipei or HK-low).
    """
    city = event.get("city")
    if not city:
        raise KeyError(
            f"event missing 'city' field; got keys {sorted(event)!r}",
        )
    city_key = city.lower()
    if city_key not in city_map:
        raise KeyError(
            f"unknown city {city!r}; known cities: {sorted(city_map)!r}",
        )
    stations = city_map[city_key]

    text = " ".join(str(event.get(field, "")) for field in ("title", "slug", "name"))
    measure = _detect_measure(text)

    # Fall back to "default" when the city map doesn't list the detected
    # measure (e.g. a single-airport city + a "high" keyword in the title).
    if measure not in stations:
        measure = "default"
    if measure not in stations:
        raise KeyError(
            f"city {city_key!r} map missing both detected measure and "
            f"'default' key; entries: {sorted(stations)!r}",
        )

    icao = stations[measure]

    if (icao, measure) in DEFERRED_STATION_MEASURES or (
        # Whole-station defer: every measure for RCTP, plus any future
        # entry added to DEFERRED_STATIONS that's not in the per-measure
        # table. HK is intentionally NOT in this set so its "high" market
        # routes normally.
        icao in DEFERRED_STATIONS and icao != "VHHH"
    ):
        raise DeferredMarketError(
            f"market for ({icao}, {measure}) is deferred to v0.2 "
            f"(CWA/HKO source clients land then)",
        )

    return icao, measure

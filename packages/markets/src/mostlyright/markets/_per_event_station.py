"""Per-event station resolution for multi-airport Polymarket cities.

Most Polymarket weather markets resolve against a single station per city
(e.g. ``london -> EGLL``). A few cities use distinct airports for high vs
low (e.g. Paris uses LFPG for "highest temperature" markets but LFPB for
"lowest temperature" markets — historically LFPB's open-rural exposure
produces colder overnight lows than CDG's tarmac).

This module implements that lookup against
``polymarket_city_stations.json``. It also gates the markets whose data
source ships in v0.2 (Taipei RCSS via CWA, Hong Kong HKO via weather.gov.hk)
by raising :class:`mostlyright.international.DeferredMarketError`.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path

from mostlyright.international import DEFERRED_STATIONS, DeferredMarketError

log = logging.getLogger(__name__)

__all__ = [
    "DEFERRED_STATION_MEASURES",
    "extract_icao_from_resolution_source",
    "load_polymarket_city_stations",
    "resolve_station_for_event",
]


#: Path to the bundled ``polymarket_city_stations.json``. Loaded lazily by
#: :func:`load_polymarket_city_stations` and cached in module state.
_CITY_STATIONS_PATH: Path = Path(__file__).parent / "polymarket_city_stations.json"

#: Process-level cache. ``None`` means "not yet loaded".
_CACHED_CITY_STATIONS: dict[str, dict[str, str]] | None = None

#: Per-(icao, measure) defer table. ``measure`` is one of ``"high"``,
#: ``"low"``, or ``"default"`` (matches the JSON keys + the resolver output).
#: Phase 23: Hong Kong reconciled to HKO (the Observatory, ``weather.gov.hk``
#: source) — ALL HK measures now defer (previously only HK-low via VHHH).
#: Taipei moved RCTP→RCSS; every RCSS measure defers until the CWA client lands.
DEFERRED_STATION_MEASURES: frozenset[tuple[str, str]] = frozenset(
    {
        # Hong Kong: HKO is the issuer for every measure (no live source yet).
        ("HKO", "high"),
        ("HKO", "low"),
        ("HKO", "default"),
        # Taipei: every measure defers until the CWA client lands.
        ("RCSS", "high"),
        ("RCSS", "low"),
        ("RCSS", "default"),
    }
)

#: Regex selecting tokens that signal a "high" (daily-max) market.
_HIGH_RE = re.compile(r"\b(highest|high|hottest|warmest|max(?:imum)?)\b", re.IGNORECASE)

#: Regex selecting tokens that signal a "low" (daily-min) market.
_LOW_RE = re.compile(r"\b(lowest|low|coldest|coolest|min(?:imum)?)\b", re.IGNORECASE)

#: Wunderground PWS / airport / history URL pattern. Matches canonical
#: settlement URL anchor paths (`/pws/`, `/dashboard/pws/`, `/history/daily/`,
#: `/history/airport/`, `/weather-station/`, `/cat/forecasts/`), with zero or
#: more lowercase-slug segments before the trailing ICAO. Real Polymarket
#: settlement URLs carry country / state / city slugs between the anchor and
#: the ICAO (e.g. `/history/daily/us/ny/new-york-city/KLGA`); the prior
#: tighter version that required the ICAO to abut the anchor missed every
#: real Polymarket URL (codex iter-2 + python-architect iter-2 CRITICAL).
#:
#: ICAO is exactly 4 chars starting with K (US-only constraint — international
#: Wunderground URLs use lat/lng or alternate IDs and fall back to Tier 2).
#: The trailing ``\b`` (word boundary) allows the URL to end at common
#: Markdown / prose terminators (`)`, `.`, `,`, ` `, EOF, etc.) so embedded
#: URLs in event descriptions are not missed (codex iter-2 CRITICAL).
#:
#: Defense-in-depth against incidental K-prefix tokens: the anchor allowlist
#: (`/pws/`, `/history/daily/`, etc.) rejects arbitrary paths like
#: `/news/2024-summer-KIDS-overview`. The intermediate `[a-z0-9-]+/`
#: segments are LOWERCASE only — the uppercase ICAO can never collide with
#: a slug segment.
#: Iter-3 codex CRITICAL: the case-insensitive flag let `[a-z0-9-]+/`
#: consume uppercase segments, so `/history/daily/KORD/date/KLAX` extracted
#: `KLAX` (the LAST K-prefix segment) instead of `KORD` (the canonical
#: station slot). Fix: drop IGNORECASE entirely. Real Wunderground URLs
#: use lowercase paths + uppercase ICAOs (RFC 3986 scheme + Wunderground
#: convention). Case-sensitive matching pins the ICAO to the canonical
#: station slot — intermediate slugs (lowercase only) cannot consume
#: a K-prefix uppercase token.
_WUNDERGROUND_ICAO_RE = re.compile(
    r"https?://(?:www\.)?wunderground\.com/"
    r"(?:dashboard/)?(?:pws|history/daily|history/airport|weather-station|cat/forecasts)/"
    r"(?:[a-z0-9-]+/)*"
    r"(K[A-Z]{3})(?![A-Za-z0-9_-])"
)


def extract_icao_from_resolution_source(text: str | None) -> str | None:
    """Extract the canonical Wunderground PWS / airport ICAO from ``text``.

    Tier 1.5 of the resolver chain — runs between explicit ``event.city``
    and slug-derive. When a Polymarket event embeds a Wunderground PWS
    URL pointing at a specific station, the URL IS the source of truth;
    no catalog lookup needed.

    Multi-URL disambiguation: when the text contains MULTIPLE canonical
    Wunderground URLs, ALL extracted ICAOs MUST agree. If they don't, the
    function returns None (Tier 1.5 abstains; resolver falls through to
    Tier 2 city-derive). This prevents an issuer-side typo or an
    explanatory citation URL from silently swapping the settlement
    station — first-match-wins on disagreeing URLs would be silent
    corruption.

    Args:
        text: ``event.description`` / ``event.resolutionSource`` content.
            Tolerates None / empty / non-string for caller convenience.

    Returns:
        Uppercase ICAO (4 chars, leading K) when a canonical Wunderground
        URL is found AND any additional canonical URLs agree. None
        otherwise — including the disagreement case (caller falls
        through to Tier 2).
    """
    if not text or not isinstance(text, str):
        return None
    matches = _WUNDERGROUND_ICAO_RE.findall(text)
    if not matches:
        return None
    unique = {m.upper() for m in matches}
    if len(unique) > 1:
        # Disagreement — abstain. Caller falls through to Tier 2.
        log.warning(
            "extract_icao_from_resolution_source: %d disagreeing ICAOs in text "
            "(%s); abstaining (Tier 1.5 returns None)",
            len(unique),
            sorted(unique),
        )
        return None
    return next(iter(unique))


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
        KeyError: ``event["city"]`` is missing from ``city_map`` AND
            Tier 1.5 URL extraction did not resolve an ICAO.
        DeferredMarketError: the resolved (icao, measure) pair routes to a
            data source that's deferred to v0.2 (Taipei or HK-low).
    """
    # Pre-compute measure once — used by both Tier 1.5 and Tier 3.
    text = " ".join(str(event.get(field, "")) for field in ("title", "slug", "name"))
    measure = _detect_measure(text)

    # Tier 1.5: URL extraction from event.description / event.resolutionSource.
    # Wunderground URLs in Polymarket events are the issuer's canonical proof of
    # which PWS station settles — beats catalog lookup. Defer-check still applies
    # so a URL bypass cannot silently route an RCTP/HK-low market.
    url_text = " ".join(str(event.get(field, "")) for field in ("description", "resolutionSource"))
    extracted_icao = extract_icao_from_resolution_source(url_text)
    if extracted_icao is not None:
        if (extracted_icao, measure) in DEFERRED_STATION_MEASURES or (
            extracted_icao in DEFERRED_STATIONS
        ):
            raise DeferredMarketError(
                f"market for ({extracted_icao}, {measure}) is deferred to v0.2 "
                f"(CWA/HKO source clients land then)",
            )
        return extracted_icao, measure

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
        # Whole-station defer: every measure for a DEFERRED_STATIONS entry
        # (HKO, RCSS). Phase 23 — both fully defer, so no per-station carve-out
        # remains; the per-measure table and this set agree.
        icao in DEFERRED_STATIONS
    ):
        raise DeferredMarketError(
            f"market for ({icao}, {measure}) is deferred to v0.2 "
            f"(CWA/HKO source clients land then)",
        )

    return icao, measure

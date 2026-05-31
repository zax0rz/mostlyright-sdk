"""Phase 3.3 — Polymarket discovery + settlement (US + international).

Public surface:

- :func:`polymarket_discover()` — Gamma API discovery, no auth.
- :func:`polymarket_settle(event_id)` — settlement engine using
  internal :func:`mostlyright.international.daily_extremes` as the
  resolution source.

Security-adjacent boundary validation (all enforced before any HTTP
fetch or daily-extremes call):

- ``event_id`` MUST match the UUID4 pattern.
- ``description`` capped at 16 KB (Polymarket descriptions are concise;
  oversized payloads indicate hostile input).
- Resolution-source URLs in the description MUST resolve to a netloc in
  :data:`RESOLUTION_SOURCE_ALLOWLIST` (Wunderground or weather.gov).

Taipei + Hong Kong-lowest markets raise
:class:`mostlyright.international.DeferredMarketError` — v0.2 wires
CWA + HKO clients.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Mapping
from datetime import UTC, date, datetime
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, Final
from urllib.parse import urlparse

from mostlyright.core.exceptions import MostlyRightError
from mostlyright.international import (
    DEFERRED_STATIONS,
    DeferredMarketError,
    daily_extremes,
)

from ._per_event_station import (
    load_polymarket_city_stations,
    resolve_station_for_event,
)
from ._polymarket_client import fetch_event_by_id, fetch_events

if TYPE_CHECKING:
    import httpx
    import pandas as pd

log = logging.getLogger(__name__)


__all__ = [
    "KNOWN_WRONG_STATIONS",
    "POLYMARKET_RESOLUTION_SOURCE_TYPES",
    "RESOLUTION_SOURCE_ALLOWLIST",
    "PolymarketEventError",
    "PolymarketSettlementError",
    "TooEarlyToSettleError",
    "polymarket_discover",
    "polymarket_settle",
]


#: Per-city Polymarket denylist: stations that MUST NEVER resolve a
#: Polymarket event for that city. Namespace-isolated from Kalshi's
#: ``kalshi_stations.KNOWN_WRONG_STATIONS`` because the two issuers
#: disagree on station identity for the same city (Polymarket NYC =
#: KLGA, Kalshi NYC = KNYC; KNYC is correct for Kalshi and wrong for
#: Polymarket, KLGA is correct for Polymarket and wrong for Kalshi).
#:
#: Contract test in ``tests/test_cross_issuer_station_identity.py``
#: asserts no Polymarket catalog entry resolves to its own per-city
#: denylist value AND that the denylists are inverse-correct across
#: issuers for the disagreement cities (nyc, chicago).
#:
#: Per-city Mapping (NOT a flat set like Kalshi's) because Polymarket's
#: catalog is international + multi-city and the "wrong" station depends
#: on which city the event is for — KLGA is wrong for chicago but right
#: for nyc.
KNOWN_WRONG_STATIONS: Final[Mapping[str, frozenset[str]]] = MappingProxyType(
    {
        # NYC: Polymarket uses KLGA. KNYC/KJFK/KEWR are the common wrong answers.
        "nyc": frozenset({"KNYC", "KJFK", "KEWR"}),
        # Chicago: Polymarket uses KORD. KMDW is the common wrong answer (Kalshi's choice).
        "chicago": frozenset({"KMDW"}),
        # Houston: Phase 23 moved Polymarket to KHOU. KIAH (Kalshi's station) is
        # now the cross-venue wrong answer for a Polymarket Houston market.
        "houston": frozenset({"KIAH"}),
        # Dallas: Phase 23 moved Polymarket to KDAL. KDFW (Kalshi's station) is
        # now the cross-venue wrong answer.
        "dallas": frozenset({"KDFW"}),
        # SF: Polymarket uses KSFO. KOAK is the common wrong answer.
        "san_francisco": frozenset({"KOAK"}),
    }
)


#: Netloc allowlist for Polymarket resolution-source URLs. Anything else
#: raises :class:`PolymarketEventError` to prevent silent settlement
#: against an unknown / hostile source.
RESOLUTION_SOURCE_ALLOWLIST: frozenset[str] = frozenset(
    {"wunderground.com", "www.wunderground.com", "weather.gov", "www.weather.gov"}
)


#: Per-netloc classification — projects the raw URL into the
#: ``resolution_source_type`` enum on settlement records.
_NETLOC_TO_RESOLUTION_TYPE: dict[str, str] = {
    "wunderground.com": "wunderground",
    "www.wunderground.com": "wunderground",
    "weather.gov": "noaa_wrh",
    "www.weather.gov": "noaa_wrh",
}


#: Enum values for the ``resolution_source_type`` column on settlement
#: records. ``hko``, ``cwa`` predeclared for v0.2 (HKO/CWA clients).
POLYMARKET_RESOLUTION_SOURCE_TYPES: tuple[str, ...] = (
    "wunderground",
    "noaa_wrh",
    "hko",
    "cwa",
    "other",
)


#: Polymarket event_id pattern. Gamma uses numeric strings for production
#: event IDs (e.g. ``"12345"``) but condition-tag UUIDs and slugs also
#: appear in the wild. We accept anything that's a 1-128 char alphanumeric
#: + ``-`` / ``_`` string — narrow enough to defend against injection
#: into the URL path, wide enough to accept real Gamma payloads.
#:
#: Codex iter-2 P1 widened this from strict UUID4 (the seam's original
#: shape) because real Gamma IDs are numeric and the strict UUID4 check
#: rejected every id polymarket_discover would surface, breaking the
#: discover -> settle round-trip.
_EVENT_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,128}$")


#: Maximum size of a Polymarket event description we'll parse for
#: resolution-source URL (security-adjacent — ReDoS defense).
_MAX_DESCRIPTION_BYTES: int = 16 * 1024


#: Per-resolution-source upload-finalization delay. The settlement
#: refuses to settle until ``now - settlement_date >= delay`` to avoid
#: settling on values the issuer hasn't published yet.
_SETTLE_DELAY_HOURS: dict[str, int] = {
    "wunderground": 6,
    "noaa_wrh": 4,
    "other": 24,
}


#: ``YYYY-MM-DD`` date extractor for event slugs. Polymarket weather
#: slugs carry the resolution date in the slug, e.g.
#: ``"will-nyc-be-above-80f-on-2026-05-23"``. We pull the date from the
#: slug rather than ``event.endDate`` because endDate is the market
#: closing time, not necessarily the resolution date.
_SLUG_DATE_RE = re.compile(r"(\d{4})-(\d{2})-(\d{2})")


class PolymarketEventError(MostlyRightError):
    """Polymarket event payload is malformed (bad UUID, bad URL, oversized)."""

    default_error_code = "POLYMARKET_EVENT_INVALID"


class PolymarketSettlementError(MostlyRightError):
    """Settlement engine couldn't resolve an event to a bucket.

    Reasons: no buckets parseable from description, daily_extremes
    returned no rows for the resolution station/date, or the parsed
    value didn't match any bucket.
    """

    default_error_code = "POLYMARKET_SETTLEMENT_FAILED"


class TooEarlyToSettleError(MostlyRightError):
    """Settlement attempted before the resolution-source's finalization delay.

    Carries the wait time so the caller can schedule a retry.
    """

    default_error_code = "POLYMARKET_TOO_EARLY"

    def __init__(
        self,
        message: str = "",
        *,
        wait_hours: float,
        resolution_source_type: str,
        request_id: str | None = None,
        error_code: str | None = None,
    ) -> None:
        super().__init__(
            message,
            error_code=error_code,
            request_id=request_id,
        )
        self.wait_hours: float = wait_hours
        self.resolution_source_type: str = resolution_source_type

    def _payload(self) -> dict[str, Any]:
        payload = super()._payload()
        payload.update(
            wait_hours=self.wait_hours,
            resolution_source_type=self.resolution_source_type,
        )
        return payload


# ----------------------------------------------------------------------
# Description parsing
# ----------------------------------------------------------------------
def _validate_description(description: str) -> None:
    """Apply the 16 KB cap + netloc allowlist to a description string.

    Raises:
        PolymarketEventError: oversize description or URL outside the
            allowlist.
    """
    if not isinstance(description, str):
        raise PolymarketEventError(
            f"description must be a string; got {type(description).__name__}",
        )
    if len(description.encode("utf-8")) > _MAX_DESCRIPTION_BYTES:
        raise PolymarketEventError(
            "description exceeds 16 KB cap (Polymarket markets carry concise "
            "descriptions; oversized payloads indicate an issuer error or "
            "hostile input)",
        )
    urls = re.findall(r'https?://[^\s<>"\')]+', description)
    for url in urls:
        try:
            netloc = urlparse(url).netloc.lower()
        except ValueError as exc:
            raise PolymarketEventError(f"unparseable resolution-source URL {url!r}") from exc
        if netloc and netloc not in RESOLUTION_SOURCE_ALLOWLIST:
            raise PolymarketEventError(
                f"resolution-source URL {url!r} not in allowlist "
                f"{sorted(RESOLUTION_SOURCE_ALLOWLIST)}"
            )


#: Tokens that mark a market as resolving on the daily maximum temperature.
_HIGH_KEYWORDS_RE = re.compile(r"\b(highest|high|hottest|warmest|max(?:imum)?)\b", re.IGNORECASE)


#: Tokens that mark a market as resolving on the daily minimum temperature.
_LOW_KEYWORDS_RE = re.compile(r"\b(lowest|low|coldest|coolest|min(?:imum)?)\b", re.IGNORECASE)


def _detect_market_measure(event: dict[str, Any]) -> str:
    """Return ``"high"`` / ``"low"`` / ``"default"`` for the value-picking step.

    Scans the event title + slug + name for high/low keywords. This is
    distinct from the station-resolution measure produced by
    :func:`resolve_station_for_event` — single-airport cities (London,
    NYC, etc.) always return station_measure="default" from the
    resolver because the city map has no high/low split, but the
    *market itself* still resolves on either tmax or tmin and we need
    that signal to pick the correct value from the daily_extremes row.
    """
    text = " ".join(str(event.get(field, "")) for field in ("title", "slug", "name"))
    has_low = _LOW_KEYWORDS_RE.search(text) is not None
    has_high = _HIGH_KEYWORDS_RE.search(text) is not None
    if has_low and not has_high:
        return "low"
    if has_high and not has_low:
        return "high"
    return "default"


def _extract_resolution_source_type(description: str) -> str:
    """Return the ``resolution_source_type`` enum value for a description.

    Picks the first allowlisted netloc found in the description.
    Returns ``"other"`` when no allowlisted URL appears (the settlement
    engine falls back to the 24-hour delay for "other").
    """
    urls = re.findall(r'https?://[^\s<>"\')]+', description)
    for url in urls:
        try:
            netloc = urlparse(url).netloc.lower()
        except ValueError:
            continue
        if netloc in _NETLOC_TO_RESOLUTION_TYPE:
            return _NETLOC_TO_RESOLUTION_TYPE[netloc]
    return "other"


def _derive_city(event: dict[str, Any], city_keys: tuple[str, ...]) -> str | None:
    """Derive the city key from event slug + title + tags.

    Real Polymarket Gamma events don't carry a custom ``city`` field;
    mostlyright tests fabricate one to drive the resolver. To make
    discovery work against the live API, scan slug+title (lowercase)
    for a substring match against the city_map keys. Longest-first so
    ``london_gatwick`` matches before ``london``.

    Codex iter-2 P1 — previously every real Gamma event was dropped at
    the ``KeyError("event missing 'city'")`` boundary.
    """
    haystack_parts: list[str] = []
    slug = (event.get("slug") or "").lower()
    title = (event.get("title") or "").lower()
    haystack_parts.append(slug)
    haystack_parts.append(title)
    # Tags can be a list of {"label": str} or list of str.
    for tag in event.get("tags") or []:
        if isinstance(tag, dict):
            label = tag.get("label") or tag.get("slug")
            if isinstance(label, str):
                haystack_parts.append(label.lower())
        elif isinstance(tag, str):
            haystack_parts.append(tag.lower())
    haystack = " ".join(haystack_parts)
    for city_key in city_keys:
        # Match the underscore form ("hong_kong") and the spaced/hyphen
        # forms commonly seen in slugs ("hong-kong", "hong kong").
        needles = (city_key, city_key.replace("_", "-"), city_key.replace("_", " "))
        for needle in needles:
            if needle and needle in haystack:
                return city_key
    return None


def _station_local_end_of_day(icao: str, settlement_date: date) -> datetime:
    """Return the UTC instant corresponding to station-local 23:59:59.

    Resolves the station's IANA timezone via the registry and computes
    ``settlement_date 23:59:59 LOCAL`` then converts to UTC. Used by the
    ``TooEarlyToSettleError`` gate so the finalization window starts
    from the station-local day-end, not UTC day-end (architect iter-1
    HIGH-1).

    Falls back to UTC end-of-day if the station isn't in the registry
    (defensive — should never happen for icao values that resolved
    via ``resolve_station_for_event``).
    """
    from datetime import time as _time
    from zoneinfo import ZoneInfo

    from mostlyright._internal._stations import STATIONS

    info = STATIONS.get(icao)
    if info is None:
        for v in STATIONS.values():
            if v.icao == icao:
                info = v
                break
    if info is None:
        return datetime(
            settlement_date.year,
            settlement_date.month,
            settlement_date.day,
            23,
            59,
            59,
            tzinfo=UTC,
        )
    local_eod = datetime.combine(settlement_date, _time(23, 59, 59), tzinfo=ZoneInfo(info.tz))
    return local_eod.astimezone(UTC)


def _settlement_date_from_slug(slug: str) -> date:
    """Parse the resolution date out of an event slug.

    Polymarket weather slugs embed the resolution date, e.g.
    ``will-nyc-be-above-80f-on-2026-05-23``. Some slugs carry both
    a creation date AND a resolution date (``created-2026-01-01-resolves-
    2026-05-23``); we take the LAST ``YYYY-MM-DD`` match because the
    resolution date is typically rightmost in Polymarket's slug
    convention. Architect iter-1 HIGH-4: first-match-wins could silently
    settle on the wrong date.

    Raises:
        PolymarketSettlementError: no parseable date in the slug.
    """
    matches = list(_SLUG_DATE_RE.finditer(slug or ""))
    if not matches:
        raise PolymarketSettlementError(
            f"no resolution date in slug {slug!r} (expected YYYY-MM-DD)",
        )
    last = matches[-1]
    try:
        return date(int(last.group(1)), int(last.group(2)), int(last.group(3)))
    except ValueError as exc:
        raise PolymarketSettlementError(f"slug {slug!r} carries malformed date: {exc}") from exc


# ----------------------------------------------------------------------
# Dep guards (codex iter-1 P2)
# ----------------------------------------------------------------------
def _require_pandas() -> Any:
    """Lazy-import pandas with an actionable install hint on miss."""
    try:
        import pandas as _pandas
    except ImportError as exc:
        from mostlyright.core.exceptions import SourceUnavailableError

        raise SourceUnavailableError(
            "mostlyright.markets.polymarket requires pandas. Install with: "
            "pip install mostlyrightmd-markets[polymarket]",
            source="polymarket_gamma",
            retryable=False,
            underlying=str(exc),
        ) from None
    return _pandas


def _require_weather() -> None:
    """Lazy-check that mostlyright.weather is importable (daily_extremes uses it)."""
    try:
        import mostlyright.weather  # noqa: F401
    except ImportError as exc:
        from mostlyright.core.exceptions import SourceUnavailableError

        raise SourceUnavailableError(
            "mostlyright.markets.polymarket settlement requires the sibling "
            "mostlyrightmd-weather package (for daily_extremes). Install with: "
            "pip install mostlyrightmd-markets[polymarket]",
            source="polymarket_gamma",
            retryable=False,
            underlying=str(exc),
        ) from None


# ----------------------------------------------------------------------
# Public surface
# ----------------------------------------------------------------------
def polymarket_discover(
    *,
    client: httpx.Client | None = None,
    sleep_between: float | None = None,
    backend: str = "pandas",
    return_type: str = "dataframe",
) -> pd.DataFrame:
    """Discover active Polymarket weather markets via the Gamma API.

    Args:
        client: Optional ``httpx.Client`` for connection reuse.
        sleep_between: Optional per-request politeness sleep. Tests
            should pass ``0`` to skip the delay. Default uses the
            client module's built-in 0.2s.

    Returns:
        ``pd.DataFrame`` with one row per active weather event. Requires the
        ``[polymarket]`` extra (raises :class:`SourceUnavailableError`
        otherwise). Columns:

        - ``event_id`` (str): Polymarket event id (UUID4).
        - ``slug`` (str): Polymarket slug.
        - ``title`` (str): event title.
        - ``city`` (str | None): lowercased city key from
          ``polymarket_city_stations.json`` if a match was found, else
          None.
        - ``icao`` (str | None): resolved ICAO for the city (high vs
          low aware), or None if no city / unknown city.
        - ``measure`` (str | None): ``"high"`` / ``"low"`` / ``"default"``
          per the per-event resolver, or None if unresolved.
        - ``end_time`` (str | None): ``event.endDate`` ISO timestamp.
        - ``resolution_source_type`` (str | None): wunderground / noaa_wrh
          / other from the description URL.

    Raises:
        httpx.HTTPStatusError: Gamma API returned non-2xx.
        SourceUnavailableError: ``[polymarket]`` extra not installed.
    """
    # Codex iter-4 P2 fix: validate backend/return_type BEFORE the Gamma
    # API pagination + sleep cycles so a typo doesn't trigger any HTTP
    # work before raising ValueError.
    from mostlyright.core._backend_dispatch import validate_backend_kwargs

    validate_backend_kwargs(backend, return_type)  # type: ignore[arg-type]

    pd = _require_pandas()

    sleep_arg = sleep_between if sleep_between is not None else 0.2
    raw_events = fetch_events(client=client, sleep_between=sleep_arg)
    city_map = load_polymarket_city_stations()
    city_keys: tuple[str, ...] = tuple(sorted(city_map.keys(), key=len, reverse=True))

    rows: list[dict[str, Any]] = []
    for ev in raw_events:
        # Codex iter-2 P1: real Gamma events don't carry a `city` field —
        # only slug/title/description/tags. Derive city from slug+title
        # by scanning for known city keys (longest-first so e.g.
        # "london_gatwick" matches before "london"). The resolver still
        # raises KeyError on miss so unknown markets get logged + dropped.
        ev_enriched = dict(ev)
        if not ev_enriched.get("city"):
            ev_enriched["city"] = _derive_city(ev_enriched, city_keys)

        icao: str | None = None
        measure: str | None = None
        try:
            icao, _station_measure = resolve_station_for_event(ev_enriched, city_map)
            # Surface the market measure (high vs low from the event
            # title), not the station-resolution measure — single-airport
            # cities always get station_measure="default" but the market
            # still resolves on tmax XOR tmin.
            measure = _detect_market_measure(ev_enriched)
        except KeyError as exc:
            # No `city` field on the raw Gamma payload, OR the city
            # isn't in our map → not a mostlyright-known weather market.
            # Codex iter-1 P1: log at INFO so a quant who can't find
            # their market knows it was dropped (and which event).
            log.info(
                "polymarket_discover: dropping event slug=%r — %s",
                ev.get("slug"),
                exc,
            )
            continue
        except DeferredMarketError:
            # The market routes to a v0.2 source (Taipei / HK-low). Still
            # surface it in discovery so quants can SEE it exists; mark
            # icao + measure as None so the row carries the deferral.
            icao, measure = None, None

        description = ev.get("description") or ""
        resolution_source_type: str | None
        try:
            _validate_description(description)
            resolution_source_type = _extract_resolution_source_type(description)
        except PolymarketEventError:
            # Bad description on one event shouldn't poison discovery.
            resolution_source_type = None

        rows.append(
            {
                "event_id": ev.get("id"),
                "slug": ev.get("slug"),
                "title": ev.get("title"),
                "city": (ev_enriched.get("city") or "").lower() or None,
                "icao": icao,
                "measure": measure,
                "end_time": ev.get("endDate"),
                "resolution_source_type": resolution_source_type,
                # Architect iter-1 HIGH-5: per-row source overlay column
                # survives pd.concat (df.attrs does not). Stamping it
                # here keeps every row attributable even after
                # cross-frame merges in downstream analysis.
                "source": "polymarket_gamma",
            }
        )

    df = pd.DataFrame(
        rows,
        columns=[
            "event_id",
            "slug",
            "title",
            "city",
            "icao",
            "measure",
            "end_time",
            "resolution_source_type",
            "source",
        ],
    )
    retrieved_at = datetime.now(UTC)
    df.attrs["source"] = "polymarket_gamma"
    df.attrs["retrieved_at"] = retrieved_at

    # Phase 6 W3-T2: backend / return_type dispatch.
    from mostlyright.core._backend_dispatch import (
        validate_backend_kwargs,
        wrap_result,
    )

    validate_backend_kwargs(backend, return_type)  # type: ignore[arg-type]
    if backend == "pandas" and return_type == "dataframe":
        return df
    return wrap_result(
        df,
        backend=backend,  # type: ignore[arg-type]
        return_type=return_type,  # type: ignore[arg-type]
        source="polymarket_gamma",
        retrieved_at=retrieved_at,
    )


def polymarket_settle(
    event_id: str,
    *,
    description: str | None = None,
    event: dict[str, Any] | None = None,
    client: httpx.Client | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Resolve a Polymarket weather event to its settlement payload.

    Args:
        event_id: UUID4 event identifier (validated at the boundary).
        description: Optional event description. If passed, used in
            place of the upstream payload (lets tests skip the HTTP
            call). Still subject to the 16 KB cap + URL allowlist.
        event: Optional preloaded event payload (skips the HTTP call
            entirely). When omitted, fetched from Gamma by ``event_id``.
        client: Optional ``httpx.Client`` for connection reuse.
        now: Override wall-clock for tests. Defaults to ``datetime.now(UTC)``.

    Returns:
        Settlement payload dict with:

        - ``event_id`` (str), ``slug`` (str), ``title`` (str)
        - ``settlement_date`` (str, ``YYYY-MM-DD`` station-local).
        - ``icao`` (str), ``measure`` (str): resolution station + high/low.
        - ``resolution_source_type`` (str)
        - ``observed_value_c`` (float): the relevant tmin or tmax from
          :func:`daily_extremes`.
        - ``n_obs`` (int): hourly observation count backing the value.
        - ``source_tmin`` / ``source_tmax`` (str): per-source provenance
          from the daily_extremes row.

    Raises:
        PolymarketEventError: invalid event_id format, oversized description,
            or resolution URL outside the allowlist.
        DeferredMarketError: resolves to Taipei / HK-low (v0.2).
        PolymarketSettlementError: settlement date unparseable, or
            daily_extremes returned no usable row.
        TooEarlyToSettleError: not enough time has passed since the
            resolution date for the source to have published.
        httpx.HTTPStatusError: Gamma API returned non-2xx when no
            ``event`` was provided.
    """
    if not isinstance(event_id, str) or not _EVENT_ID_RE.match(event_id):
        raise PolymarketEventError(
            f"event_id must be 1-128 chars of [A-Za-z0-9_-]; got {event_id!r}",
        )

    if description is not None:
        _validate_description(description)

    if event is None:
        event = fetch_event_by_id(event_id, client=client)
    if not isinstance(event, dict):
        raise PolymarketEventError(
            f"event payload must be a dict; got {type(event).__name__}",
        )

    # Caller-supplied description takes precedence (lets a tester
    # validate event-id without a full upstream payload). Otherwise
    # pull from the upstream event.
    raw_description: str = (
        description if description is not None else (event.get("description") or "")
    )
    if description is None:
        # Validate the upstream-fetched description.
        _validate_description(raw_description)

    # Resolve station from the per-event resolver. ``station_measure``
    # is ``"high"``/``"low"``/``"default"`` — for single-airport cities
    # the resolver returns ``"default"`` even when the event title
    # clearly says "highest" because the city map only carries one
    # airport. We therefore detect the *market measure* (high vs low)
    # independently from the event title for the value-picking step,
    # and use the resolver's measure only for station selection.
    city_map = load_polymarket_city_stations()
    # Codex iter-2 P1: derive city from slug/title/tags for real Gamma
    # payloads that don't carry an explicit `city` field.
    event_for_resolution = dict(event)
    if not event_for_resolution.get("city"):
        event_for_resolution["city"] = _derive_city(
            event_for_resolution, tuple(sorted(city_map.keys(), key=len, reverse=True))
        )
    icao, _station_measure = resolve_station_for_event(event_for_resolution, city_map)
    measure = _detect_market_measure(event_for_resolution)  # surfaced on the settlement record

    # Architect iter-1 HIGH-3: ambiguous title (no high/low keyword OR
    # both) used to silently pick tmax. Refuse so the caller can either
    # disambiguate (e.g. via a structured field on the event) or audit.
    if measure == "default":
        raise PolymarketSettlementError(
            f"event title/slug for {event_id} is ambiguous about high vs low "
            "(neither keyword detected, or both detected together); "
            "mostlyright refuses to silently default to tmax — caller must "
            "either supply an unambiguous event payload or disambiguate "
            "manually before settlement",
        )

    # Architect iter-1 HIGH-2: defense-in-depth must consult the
    # per-measure table (the source of truth in _per_event_station.py),
    # not the coarser DEFERRED_STATIONS set. Otherwise an RCSS/"high"
    # market could bypass the gate if the resolver ever missed.
    from ._per_event_station import DEFERRED_STATION_MEASURES

    if (icao, measure) in DEFERRED_STATION_MEASURES or (icao in DEFERRED_STATIONS):
        raise DeferredMarketError(
            f"market for ({icao}, {measure}) is deferred to v0.2",
        )

    slug = event.get("slug") or ""
    settlement_date = _settlement_date_from_slug(slug)
    resolution_source_type = _extract_resolution_source_type(raw_description)

    # Refuse to settle before the source's finalization delay clears.
    # Architect iter-1 HIGH-1: must use station-LOCAL end-of-day, not
    # UTC. For LAX (UTC-7), the LAX day ends 7h after UTC midnight;
    # using UTC end-of-day would let the 6h Wunderground gate elapse
    # ~1h BEFORE the local day even closes.
    if now is None:
        now = datetime.now(UTC)
    delay_h = _SETTLE_DELAY_HOURS.get(resolution_source_type, 24)
    local_eod_utc = _station_local_end_of_day(icao, settlement_date)
    elapsed_h = (now - local_eod_utc).total_seconds() / 3600.0
    if elapsed_h < delay_h:
        raise TooEarlyToSettleError(
            f"settlement for {event_id} on {settlement_date.isoformat()} "
            f"refused: {elapsed_h:.1f}h elapsed since station-local end-of-day "
            f"< {delay_h}h finalization window for "
            f"resolution_source_type={resolution_source_type!r}",
            wait_hours=delay_h - elapsed_h,
            resolution_source_type=resolution_source_type,
        )

    # Pull the daily extreme for the resolution station + date.
    # Codex iter-1 P2: mostlyrightmd-weather (sibling package) is required
    # for daily_extremes -> cache I/O. The guard raises a friendly
    # SourceUnavailableError when the [polymarket] extra isn't installed.
    _require_weather()
    extremes = daily_extremes(icao, settlement_date, settlement_date)
    if not extremes:
        raise PolymarketSettlementError(
            f"daily_extremes returned no rows for {icao} on {settlement_date.isoformat()}; "
            "either the cache is cold (run research() first) or no observations exist",
        )
    row = extremes[0]
    if row.get("local_date") != settlement_date.isoformat():
        # Defensive — daily_extremes can return a slightly different
        # local-date row if tz conversion bumps a UTC observation into
        # the next local day. We refuse to silently settle on the wrong
        # day rather than guess.
        raise PolymarketSettlementError(
            f"daily_extremes returned row for {row.get('local_date')!r} "
            f"but caller asked for {settlement_date.isoformat()}",
        )

    if measure == "high":
        observed_value_c = row.get("tmax_c")
        observed_source = row.get("source_tmax")
    elif measure == "low":
        observed_value_c = row.get("tmin_c")
        observed_source = row.get("source_tmin")
    else:
        observed_value_c = row.get("tmax_c")  # default to high
        observed_source = row.get("source_tmax")

    if observed_value_c is None:
        raise PolymarketSettlementError(
            f"daily_extremes row for {icao} {settlement_date.isoformat()} "
            f"has no {measure} value (likely low_coverage; n_obs={row.get('n_obs')})",
        )

    return {
        "event_id": event_id,
        "slug": slug,
        "title": event.get("title"),
        "settlement_date": settlement_date.isoformat(),
        "icao": icao,
        "measure": measure,
        "resolution_source_type": resolution_source_type,
        "observed_value_c": observed_value_c,
        "observed_source": observed_source,
        "n_obs": row.get("n_obs"),
        "country": row.get("country"),
    }

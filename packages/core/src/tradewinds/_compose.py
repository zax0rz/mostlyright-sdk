"""Phase 10 — composable ``research()`` dispatcher.

Translates the new selectors (``city=``, ``contract=``, ``contracts=``)
into resolution metadata + station tuples that the existing
station-based ``research()`` machinery consumes. Cross-issuer annotation
(``settles_for``) is computed here so the dispatch layer is the single
source of truth for "which markets settle against which stations."

The dispatcher is intentionally pure (no I/O, no DataFrame
construction) so unit tests run instantly and the same logic can be
reused by ``discover()`` and the TS counterpart.
"""

from __future__ import annotations

import warnings
from typing import Any

#: The valid selector kwarg names. Exactly one must be provided on each
#: ``research()`` invocation; passing zero or >1 raises ``ValueError``.
_SELECTOR_NAMES: tuple[str, ...] = ("station", "city", "contract", "contracts")


class StationOverrideWarning(UserWarning):
    """Emitted when ``station_override=`` deliberately mismatches the
    contract's canonical settlement station.

    The output row carries ``settlement_mismatch=True`` so downstream
    backtest code can filter / flag these silently-divergent rows.
    """


def validate_selectors(
    *,
    station: str | None = None,
    city: str | None = None,
    contract: str | None = None,
    contracts: list[str] | tuple[str, ...] | None = None,
) -> str:
    """Validate that exactly one selector is provided; return the active name.

    Args:
        station, city, contract, contracts: the four mutually-exclusive
            selectors. Exactly one must be non-None / non-empty.

    Returns:
        The name of the active selector (``"station"`` / ``"city"`` /
        ``"contract"`` / ``"contracts"``).

    Raises:
        ValueError: zero or >1 selectors provided.
    """
    provided: list[str] = []
    if station is not None and station != "":
        provided.append("station")
    if city is not None and city != "":
        provided.append("city")
    if contract is not None and contract != "":
        provided.append("contract")
    if contracts is not None and len(contracts) > 0:
        provided.append("contracts")
    if not provided:
        raise ValueError(
            "research(): exactly one of station=, city=, contract=, contracts= "
            "must be provided"
        )
    if len(provided) > 1:
        raise ValueError(
            f"research(): selectors are mutually exclusive; got {provided!r}"
        )
    return provided[0]


def resolve_contract(contract_id: str) -> tuple[str, str]:
    """Resolve a ``"<issuer>:<id>"`` string to ``(station, issuer)``.

    Supported issuers:
    - ``kalshi:`` — ``KHIGH*``/``KXHIGH*``/``KLOW*``/``KXLOW*`` city tickers.
    - ``polymarket:`` — event/market ids. v0.2 raises NotImplementedError
      with an actionable message (the resolver lives in
      :mod:`tradewinds.markets._per_event_station` but requires a fetched
      event payload to identify the city; Phase 10 v0.2 surfaces this as
      a clear error and defers the integration to v0.3).

    Args:
        contract_id: ``"<issuer>:<id>"`` string (e.g.
            ``"kalshi:KXHIGHNYC"`` or ``"polymarket:0x..."``).

    Returns:
        Tuple of ``(station_icao, issuer_name)``.

    Raises:
        ValueError: malformed contract id or unknown issuer.
        NotImplementedError: Polymarket contract resolution (deferred).
    """
    if not isinstance(contract_id, str) or ":" not in contract_id:
        raise ValueError(
            f"contract id must be `<issuer>:<id>`; got {contract_id!r}"
        )
    issuer, raw = contract_id.split(":", 1)
    issuer = issuer.lower()
    raw_upper = raw.upper()
    if issuer == "kalshi":
        from datetime import date as _date

        from tradewinds.markets.catalog import kalshi_nhigh, kalshi_nlow

        # Kalshi tickers come in two prefix families:
        #   KHIGH<CITY>* / KXHIGH<CITY>* → NHIGH (daily-high)
        #   KLOW<CITY>*  / KXLOW<CITY>*  → NLOW (daily-low)
        # The existing kalshi_nhigh / kalshi_nlow resolvers were built for
        # the legacy KHIGH<CITY> / KLOW<CITY> shape. Modern Kalshi market
        # tickers use the KX-prefix exchange convention
        # (KXHIGH<CITY>-<DATE>-<STRIKE>); strip the `KX` to feed the
        # resolver and pass the bare city portion. The resolver's own
        # validation (`startswith("KHIGH")` / `startswith("KLOW")` +
        # length>5) does the city-ticker validity check.
        # Strip just the 'X' from the KX exchange prefix so KXHIGH<CITY>
        # becomes KHIGH<CITY> (the legacy resolver's expected format).
        # KX = position [0..1] but the literal 'K' is kept; drop position [1].
        normalized = raw_upper
        if normalized.startswith("KX"):
            normalized = "K" + normalized[2:]  # KXHIGHNYC → KHIGHNYC
        # Many full Kalshi tickers carry a trailing -DATE-STRIKE suffix
        # (e.g. KXHIGHNYC-25MAY26-T79 → KXHIGHNYC). Pull the city portion
        # by trimming at the first '-'.
        city_only = normalized.split("-", 1)[0]
        if city_only.startswith("KHIGH") and len(city_only) > 5:
            r = kalshi_nhigh.resolve(city_only, _date.today())
            return r.settlement_station, "kalshi"
        if city_only.startswith("KLOW") and len(city_only) > 4:
            r = kalshi_nlow.resolve(city_only, _date.today())
            return r.settlement_station, "kalshi"
        raise ValueError(
            f"unsupported kalshi contract format: {raw!r}; "
            "expected KHIGH<CITY>* / KXHIGH<CITY>* / KLOW<CITY>* / "
            "KXLOW<CITY>* prefix"
        )
    if issuer == "polymarket":
        raise NotImplementedError(
            "polymarket contract resolution requires event_id → station lookup "
            "via polymarket_discover() or polymarket_settle(); Phase 10 v0.2 "
            "defers this integration to v0.3. Use `city='nyc'` or pass the "
            "station explicitly via `station_override=` until then."
        )
    raise ValueError(f"unknown issuer prefix: {issuer!r}; expected kalshi or polymarket")


def resolve_city(city: str) -> tuple[str, ...]:
    """Resolve a city slug to all stations any issuer settles against.

    Returns a deduplicated tuple in stable order:
      1. Kalshi's settlement station (if the city is in the Kalshi catalog).
      2. Polymarket's default + high + low stations (if in Polymarket catalog).
      3. Polymarket per-city denylist entries (forbidden-but-known stations
         surfaced so quants can SEE the full neighborhood for explicit
         ``station_override=``).

    For ``"NYC"`` returns (``"KNYC"``, ``"KLGA"``, ``"KJFK"``, ``"KEWR"``)
    — KNYC is Kalshi's, KLGA is Polymarket's, KJFK + KEWR are the
    denylist backstops Polymarket forbids.

    Args:
        city: city slug. Accepts ``"NYC"`` (Kalshi upper) or ``"nyc"``
            (Polymarket lower); both are normalized.

    Returns:
        Tuple of station ICAOs.

    Raises:
        ValueError: city not in either catalog.
    """
    if not isinstance(city, str) or not city:
        raise ValueError(f"city must be a non-empty str; got {city!r}")

    from tradewinds.markets._per_event_station import load_polymarket_city_stations
    from tradewinds.markets.catalog.kalshi_stations import (
        KALSHI_SETTLEMENT_STATIONS,
    )
    from tradewinds.markets.polymarket import KNOWN_WRONG_STATIONS as POLY_WRONG

    out: list[str] = []
    city_upper = city.upper()
    city_lower = city.lower()
    if city_upper in KALSHI_SETTLEMENT_STATIONS:
        out.append(KALSHI_SETTLEMENT_STATIONS[city_upper].station)
    poly = load_polymarket_city_stations()
    if city_lower in poly:
        # Preserve insertion order across the measure keys.
        for measure in ("default", "high", "low"):
            st = poly[city_lower].get(measure)
            if st and st not in out:
                out.append(st)
    for st in sorted(POLY_WRONG.get(city_lower, frozenset())):
        if st not in out:
            out.append(st)
    if not out:
        raise ValueError(
            f"unknown city {city!r}; not in kalshi or polymarket catalogs"
        )
    return tuple(out)


def annotate_settles_for(station: str, city: str | None) -> list[str]:
    """Return the list of ``"<issuer>:<ticker>"`` markers that settle
    against ``station`` for ``city``.

    Empty list means no known issuer settles against this station for
    this city (typically a denylist entry surfaced by
    :func:`resolve_city` for the caller's awareness).

    Args:
        station: 4-char K-prefix ICAO.
        city: city slug (optional; when None, returns empty list).

    Returns:
        Sorted list of ``"kalshi:CITY"`` / ``"polymarket:city"`` markers.
    """
    out: list[str] = []
    if city is None:
        return out
    from tradewinds.markets._per_event_station import load_polymarket_city_stations
    from tradewinds.markets.catalog.kalshi_stations import (
        KALSHI_SETTLEMENT_STATIONS,
    )

    city_upper = city.upper()
    city_lower = city.lower()
    if (
        city_upper in KALSHI_SETTLEMENT_STATIONS
        and KALSHI_SETTLEMENT_STATIONS[city_upper].station == station
    ):
        out.append(f"kalshi:{city_upper}")
    poly = load_polymarket_city_stations()
    if city_lower in poly and station in poly[city_lower].values():
        out.append(f"polymarket:{city_lower}")
    return sorted(out)


def emit_override_warning(contract_station: str, override_station: str) -> None:
    """Helper: emit :class:`StationOverrideWarning` for a deliberate mismatch."""
    warnings.warn(
        f"station_override={override_station!r} differs from contract's "
        f"canonical settlement station {contract_station!r}; output row will "
        f"carry settlement_mismatch=True",
        StationOverrideWarning,
        stacklevel=3,
    )


__all__ = [
    "StationOverrideWarning",
    "annotate_settles_for",
    "emit_override_warning",
    "resolve_city",
    "resolve_contract",
    "validate_selectors",
]


# Silence the `Any` import warning — kept for ruff future-proofing if/when
# the dispatch layer needs to type DataFrame returns.
_ = Any

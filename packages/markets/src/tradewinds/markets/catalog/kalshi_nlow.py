"""Kalshi NLOW contract spec (daily LOW temperature settlement).

Mirror of :mod:`tradewinds.markets.catalog.kalshi_nhigh` — same station
whitelist + same source (cli.archive); only the metric differs.
NLOW markets resolve against the NWS CLI ``min_temp_f`` value for a
specific station on a specific date.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date as _date

from tradewinds.markets.catalog.kalshi_stations import KALSHI_SETTLEMENT_STATIONS


@dataclass(frozen=True)
class NLowResolution:
    """The (source, station) tuple a Kalshi NLOW contract resolves to."""

    settlement_source: str
    settlement_station: str
    city_ticker: str
    contract_date: _date


def resolve(contract_id: str, settlement_date: _date) -> NLowResolution:
    """Resolve a Kalshi NLOW contract to its settlement source + station.

    Args:
        contract_id: Kalshi market identifier ``KLOW<CITY>`` (e.g. ``KLOWNY``).
            Case-insensitive.
        settlement_date: The local calendar date the market settles for.

    Returns:
        :class:`NLowResolution` with settlement_source = ``"cli.archive"``.

    Raises:
        ValueError: ``contract_id`` doesn't follow ``KLOW<CITY>`` or the
            city ticker is unknown.
    """
    # codex iter-8/9 HIGH fix: validate settlement_date type; reject
    # datetime explicitly (a datetime carries a time component which would
    # break downstream date-equality matching).
    from datetime import datetime as _datetime

    if isinstance(settlement_date, _datetime):
        raise TypeError(
            "settlement_date must be a datetime.date instance (not datetime); "
            "the time component would break downstream settlement-date "
            f"matching. Got {type(settlement_date).__name__}={settlement_date!r}; "
            "call .date() if you have a datetime."
        )
    if not isinstance(settlement_date, _date):
        raise TypeError(
            "settlement_date must be a datetime.date instance "
            f"(got {type(settlement_date).__name__}={settlement_date!r})"
        )
    if not isinstance(contract_id, str):
        raise TypeError(
            f"contract_id must be a string (got {type(contract_id).__name__}={contract_id!r})"
        )

    cid = contract_id.upper()
    if not cid.startswith("KLOW") or len(cid) <= 4:
        raise ValueError(f"NLOW contract_id must follow 'KLOW<CITY>' format; got {contract_id!r}")
    city_ticker = cid[4:]
    citation = KALSHI_SETTLEMENT_STATIONS.get(city_ticker)
    if citation is None:
        raise ValueError(
            f"Unknown Kalshi city ticker {city_ticker!r}; "
            f"known: {sorted(KALSHI_SETTLEMENT_STATIONS)}"
        )
    return NLowResolution(
        settlement_source="cli.archive",
        settlement_station=citation.station,
        city_ticker=city_ticker,
        contract_date=settlement_date,
    )


__all__ = ["NLowResolution", "resolve"]

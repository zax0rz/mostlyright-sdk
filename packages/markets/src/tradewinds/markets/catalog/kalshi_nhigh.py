"""Kalshi NHIGH contract spec (daily HIGH temperature settlement).

NHIGH markets resolve against the NWS CLI ``max_temp_f`` value for a
specific station on a specific date. ``resolve(contract_id, date)`` is
the deterministic mapping from a Kalshi market identifier to the
``(settlement_source, settlement_station)`` tuple downstream code uses
to pull the right settlement row from the CLI catalog.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date as _date

from tradewinds.markets.catalog.kalshi_stations import KALSHI_SETTLEMENT_STATIONS


@dataclass(frozen=True)
class NHighResolution:
    """The (source, station) tuple a Kalshi NHIGH contract resolves to."""

    settlement_source: str
    settlement_station: str
    city_ticker: str
    contract_date: _date


def resolve(contract_id: str, settlement_date: _date) -> NHighResolution:
    """Resolve a Kalshi NHIGH contract to its settlement source + station.

    The contract_id is the Kalshi market identifier — for v0.1.0 the
    expected format is ``KHIGH<CITY>`` (e.g. ``KHIGHNY``, ``KHIGHCHI``).
    The city ticker is the suffix; we look it up in the whitelist.

    Args:
        contract_id: Kalshi market identifier. Case-insensitive.
        settlement_date: The local calendar date the market settles for.

    Returns:
        :class:`NHighResolution` with settlement_source = ``"cli.archive"``
        and settlement_station from the whitelist.

    Raises:
        ValueError: ``contract_id`` doesn't follow the ``KHIGH<CITY>`` format
            or the city ticker is not in :data:`KALSHI_SETTLEMENT_STATIONS`.
    """
    # codex iter-8 HIGH fix: validate settlement_date type up front.
    # Accepting arbitrary values lets invalid input escape the resolver
    # boundary and fail later inside the settlement lookup with a
    # confusing message.
    if not isinstance(settlement_date, _date):
        raise TypeError(
            "settlement_date must be a datetime.date instance "
            f"(got {type(settlement_date).__name__}={settlement_date!r})"
        )
    if not isinstance(contract_id, str):
        raise TypeError(
            "contract_id must be a string " f"(got {type(contract_id).__name__}={contract_id!r})"
        )

    cid = contract_id.upper()
    if not cid.startswith("KHIGH") or len(cid) <= 5:
        raise ValueError(f"NHIGH contract_id must follow 'KHIGH<CITY>' format; got {contract_id!r}")
    city_ticker = cid[5:]
    citation = KALSHI_SETTLEMENT_STATIONS.get(city_ticker)
    if citation is None:
        raise ValueError(
            f"Unknown Kalshi city ticker {city_ticker!r}; "
            f"known: {sorted(KALSHI_SETTLEMENT_STATIONS)}"
        )
    return NHighResolution(
        settlement_source="cli.archive",
        settlement_station=citation.station,
        city_ticker=city_ticker,
        contract_date=settlement_date,
    )


__all__ = ["NHighResolution", "resolve"]

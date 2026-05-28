"""Venue-agnostic station catalog (Phase 22).

A station is a physical fact; the prediction-market venue that settles on it
is metadata. Before Phase 22 the US-city universe lived in
``mostlyright.markets.catalog.kalshi_stations`` — coupling general-purpose
weather stations to a single venue even though the same cities trade on
Polymarket and are valid query targets with no market at all.

This module exposes the canonical registry (``mostlyright._internal._stations``)
as a venue-agnostic :class:`StationCatalog`. Markets derives its settlement
universe by filtering on venue tags; bare-data users ignore venues entirely.

``Station`` is an alias for the registry's ``StationInfo`` record — there is
one source of station truth, not two.
"""

from __future__ import annotations

from collections.abc import Iterator

from mostlyright._internal._stations import STATIONS, StationInfo

#: Public name for the station record. The registry dataclass IS the public
#: shape — re-exported (not duplicated) so there is a single source of truth.
Station = StationInfo

__all__ = ["CATALOG", "Station", "StationCatalog"]


class StationCatalog:
    """Read-only view over the station registry with venue/country filters.

    Lookups accept either the registry key (3-letter NWS code for US
    stations, ICAO for international) or the 4-letter ICAO directly, so
    ``get("NYC")``, ``get("KNYC")``, and ``get("EGLL")`` all resolve.
    """

    def __init__(self, stations: dict[str, Station] | None = None) -> None:
        self._stations: dict[str, Station] = dict(stations or STATIONS)
        # Secondary index by ICAO for O(1) ICAO lookups (registry is keyed
        # by NWS code for US entries, ICAO for international).
        self._by_icao: dict[str, Station] = {s.icao: s for s in self._stations.values()}

    def get(self, code: str) -> Station:
        """Return the station for ``code`` (registry key or ICAO).

        Raises:
            KeyError: when no station matches.
        """
        station = self._stations.get(code) or self._by_icao.get(code)
        if station is None:
            raise KeyError(
                f"Unknown station {code!r}. Expected a registry key "
                f"(e.g. 'NYC', 'EGLL') or a 4-letter ICAO (e.g. 'KNYC')."
            )
        return station

    def filter_by_venue(self, venue: str) -> list[Station]:
        """Return stations tagged with ``venue`` (e.g. ``"kalshi"``), sorted by ICAO."""
        return sorted(
            (s for s in self._stations.values() if venue in s.venues),
            key=lambda s: s.icao,
        )

    def filter_by_country(self, country: str) -> list[Station]:
        """Return stations whose ISO 3166-1 alpha-2 ``country`` matches, sorted by ICAO."""
        return sorted(
            (s for s in self._stations.values() if s.country == country),
            key=lambda s: s.icao,
        )

    def venues(self) -> frozenset[str]:
        """Return the union of all venue tags present in the catalog."""
        out: set[str] = set()
        for s in self._stations.values():
            out |= s.venues
        return frozenset(out)

    def __iter__(self) -> Iterator[Station]:
        return iter(self._stations.values())

    def __len__(self) -> int:
        return len(self._stations)

    def __contains__(self, code: object) -> bool:
        return isinstance(code, str) and (code in self._stations or code in self._by_icao)


#: Process-wide default catalog over the canonical registry.
CATALOG = StationCatalog()

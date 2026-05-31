"""Phase 22/23 — Polymarket venue tag ⟺ city-station settlement map.

Core (``mostlyright.stations``) is the venue-membership authority; the
Polymarket ``polymarket_city_stations.json`` is venue-specific provenance.
The settlement ICAOs Polymarket actually uses must equal the stations core
tags ``polymarket`` — once you intersect with the registry. Phase 23 added
KLGA/KORD as registry records, so the only settlement ICAO NOT in the catalog
is now HKO (Hong Kong Observatory — no airport ICAO, v0.2-deferred source).
"""

from __future__ import annotations

from mostlyright import CATALOG
from mostlyright.markets._per_event_station import load_polymarket_city_stations


def test_polymarket_venue_matches_city_station_map() -> None:
    city_map = load_polymarket_city_stations()
    settlement_icaos = {icao for stations in city_map.values() for icao in stations.values()}
    catalog_icaos = {s.icao for s in CATALOG}
    # Phase 23: HKO (Hong Kong) is the sole settlement ICAO not in the registry
    # — it has no airport ICAO and its weather.gov.hk source is v0.2-deferred.
    assert settlement_icaos - catalog_icaos == {"HKO"}

    expected = settlement_icaos & catalog_icaos
    tagged = {s.icao for s in CATALOG.filter_by_venue("polymarket")}
    assert tagged == expected


def test_nyc_chicago_polymarket_stations_differ_from_kalshi() -> None:
    # Guards the headline source-identity nuance: Polymarket and Kalshi do
    # NOT share a station for NYC or Chicago.
    city_map = load_polymarket_city_stations()
    assert city_map["nyc"]["default"] == "KLGA"
    assert city_map["chicago"]["default"] == "KORD"
    # Phase 23: KLGA/KORD are now registry stations, tagged polymarket-only;
    # KNYC/KMDW stay kalshi-only — the divergence is preserved on both sides.
    assert CATALOG.get("KLGA").venues == frozenset({"polymarket"})
    assert CATALOG.get("KORD").venues == frozenset({"polymarket"})
    assert "polymarket" not in CATALOG.get("KNYC").venues
    assert "polymarket" not in CATALOG.get("KMDW").venues

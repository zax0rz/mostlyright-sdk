"""Phase 22 — Polymarket venue tag ⟺ city-station settlement map.

Core (``mostlyright.stations``) is the venue-membership authority; the
Polymarket ``polymarket_city_stations.json`` is venue-specific provenance.
The settlement ICAOs Polymarket actually uses must equal the stations core
tags ``polymarket`` — once you intersect with the registry, since Polymarket
settles NYC→KLGA and Chicago→KORD against stations that are not in the
66-station catalog.
"""

from __future__ import annotations

from mostlyright import CATALOG
from mostlyright.markets._per_event_station import load_polymarket_city_stations


def test_polymarket_venue_matches_city_station_map() -> None:
    city_map = load_polymarket_city_stations()
    settlement_icaos = {icao for stations in city_map.values() for icao in stations.values()}
    catalog_icaos = {s.icao for s in CATALOG}
    # Polymarket settles NYC/Chicago against KLGA/KORD, which are not in the
    # registry; those are the only settlement ICAOs not represented as a tag.
    assert settlement_icaos - catalog_icaos == {"KLGA", "KORD"}

    expected = settlement_icaos & catalog_icaos
    tagged = {s.icao for s in CATALOG.filter_by_venue("polymarket")}
    assert tagged == expected


def test_nyc_chicago_polymarket_stations_differ_from_kalshi() -> None:
    # Guards the headline source-identity nuance: Polymarket and Kalshi do
    # NOT share a station for NYC or Chicago.
    city_map = load_polymarket_city_stations()
    assert city_map["nyc"]["default"] == "KLGA"
    assert city_map["chicago"]["default"] == "KORD"
    # Core knows neither as a polymarket station (they are not registry
    # stations), and tags KNYC/KMDW kalshi-only.
    assert "polymarket" not in CATALOG.get("KNYC").venues
    assert "polymarket" not in CATALOG.get("KMDW").venues

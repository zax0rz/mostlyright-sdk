"""Phase 22 — venue-agnostic StationCatalog tests.

The catalog is the single source of station truth. These tests pin the
venue-tag invariant and the lookup-by-code-or-ICAO contract.

The venue tags are NOT a US/international proxy. Kalshi and Polymarket
settle several shared cities against *different* stations, so the tag is
keyed by each issuer's actual settlement map:

  - Kalshi settles NYC against KNYC (Central Park), Polymarket against KLGA.
  - Kalshi settles Chicago against KMDW (Midway), Polymarket against KORD.
  - Houston trades on both venues but settles against KIAH, so KHOU (Hobby)
    is a registry weather station with no venue tag.

The markets-side tests (``test_kalshi_stations.py``,
``test_polymarket_stations.py``) close the loop by asserting the issuer
citation/settlement maps equal the corresponding ``filter_by_venue`` set.
"""

from __future__ import annotations

import pytest
from mostlyright import CATALOG, Station, StationCatalog
from mostlyright._internal._stations import STATIONS

# The 21 Kalshi NHIGH/NLOW settlement ICAOs (mirrors the markets citations).
_KALSHI_ICAOS = {
    "KATL",
    "KAUS",
    "KBOS",
    "KDCA",
    "KDEN",
    "KDFW",
    "KLAX",
    "KMDW",
    "KMIA",
    "KMSP",
    "KNYC",
    "KPHL",
    "KPHX",
    "KSEA",
    "KSFO",
    "KIAH",
    "KDTW",
    "KCVG",
    "KBNA",
    "KSLC",
    "KLAS",
}

# Registry stations no prediction-market venue settles against. Phase 23
# untagged 27 Polymarket cities (records kept) + move-sources, so the bare
# set grew from 4 to 29: 3 US (KHOU moved TO polymarket so it left this set)
# plus 26 intl (roster drops + the London/Moscow/Taipei/HK/Paris move-sources).
_NO_VENUE_ICAOS = {
    # US bare weather stations.
    "KMSY",
    "KOKC",
    "KSAT",
    # Intl untagged in Phase 23 (cities dropped from the roster).
    "EDDB",
    "EDDF",
    "EGKK",
    "EKCH",
    "ESSA",
    "LEBL",
    "LFPO",
    "LIRF",
    "LOWW",
    "LSZH",
    "NZAA",
    "OERK",
    "OMDB",
    "OTHH",
    "RJAA",
    "VABB",
    "VIDP",
    "VTBS",
    "YBBN",
    "YMML",
    "YSSY",
    # Intl move-sources (kept as records; Polymarket moved off them).
    "EGLL",  # London → EGLC
    "UUEE",  # Moscow → UUWW
    "RCTP",  # Taipei → RCSS
    "VHHH",  # Hong Kong → HKO (non-registry)
    "LFPG",  # Paris default → LFPB
}


def test_catalog_covers_full_registry() -> None:
    assert len(CATALOG) == len(STATIONS) == 94
    assert len(CATALOG) > 0


def test_station_is_registry_record() -> None:
    # Station is the registry dataclass — one source of truth, not a copy.
    assert Station is STATIONS["NYC"].__class__


def test_get_by_code_icao_and_intl() -> None:
    assert CATALOG.get("NYC").icao == "KNYC"
    assert CATALOG.get("KNYC").code == "NYC"
    assert CATALOG.get("EGLL").country == "GB"
    # Phase 22 — the five added Kalshi settlement stations resolve.
    assert CATALOG.get("IAH").icao == "KIAH"
    assert CATALOG.get("KDTW").code == "DTW"


def test_get_unknown_raises_keyerror() -> None:
    with pytest.raises(KeyError):
        CATALOG.get("ZZZZ")


def test_contains_accepts_code_and_icao() -> None:
    assert "NYC" in CATALOG
    assert "KNYC" in CATALOG
    assert "ZZZZ" not in CATALOG
    assert 123 not in CATALOG  # type: ignore[comparison-overlap]


def test_venues_union() -> None:
    assert CATALOG.venues() == frozenset({"kalshi", "polymarket"})


def test_kalshi_venue_equals_settlement_universe() -> None:
    # The kalshi tag is the Kalshi settlement universe — NOT "every US
    # station". Four US registry stations (KHOU/KMSY/KOKC/KSAT) are
    # NOT Kalshi settlement stations.
    kalshi = {s.icao for s in CATALOG.filter_by_venue("kalshi")}
    assert kalshi == _KALSHI_ICAOS
    assert len(kalshi) == 21


def test_polymarket_venue_is_the_explicit_roster() -> None:
    poly = {s.icao for s in CATALOG.filter_by_venue("polymarket")}
    # Phase 23: polymarket is an explicit 50-station roster, NOT "every intl".
    # Cities that left the roster keep their station records but lose the tag.
    assert len(poly) == 50
    # NYC→KLGA / Chicago→KORD are now registry stations and ARE tagged.
    assert {"KLGA", "KORD"} <= poly
    # Untagged examples: roster drops + move-sources are NOT polymarket.
    assert {"EGLL", "LFPG", "VHHH", "RJAA", "YSSY", "OMDB"}.isdisjoint(poly)


def test_kalshi_and_polymarket_diverge_on_nyc_chicago_houston() -> None:
    # The load-bearing nuance: KNYC/KMDW are Kalshi-only because Polymarket
    # settles NYC/Chicago against KLGA/KORD.
    assert "kalshi" in CATALOG.get("KNYC").venues
    assert "polymarket" not in CATALOG.get("KNYC").venues
    assert "kalshi" in CATALOG.get("KMDW").venues
    assert "polymarket" not in CATALOG.get("KMDW").venues
    # KLGA / KORD are Polymarket-only (the divergence partners).
    assert CATALOG.get("KLGA").venues == frozenset({"polymarket"})
    assert CATALOG.get("KORD").venues == frozenset({"polymarket"})
    # Houston (Phase 23): Kalshi settles KIAH, Polymarket moved to KHOU —
    # now divergent (previously both settled KIAH).
    assert CATALOG.get("KIAH").venues == frozenset({"kalshi"})
    assert CATALOG.get("KHOU").venues == frozenset({"polymarket"})


def test_international_stations_not_tagged_kalshi() -> None:
    intl_kalshi = [s.icao for s in CATALOG if s.country != "US" and "kalshi" in s.venues]
    assert intl_kalshi == []


def test_bare_weather_stations_have_no_venue() -> None:
    untagged = {s.icao for s in CATALOG if not s.venues}
    assert untagged == _NO_VENUE_ICAOS


def test_filter_by_country() -> None:
    us = CATALOG.filter_by_country("US")
    assert len(us) == 29
    assert all(s.country == "US" for s in us)
    intl = [s for s in CATALOG if s.country != "US"]
    assert len(intl) == 65
    assert CATALOG.filter_by_country("GB")[0].icao == "EGKK"


def test_filter_results_sorted_by_icao() -> None:
    icaos = [s.icao for s in CATALOG.filter_by_venue("polymarket")]
    assert icaos == sorted(icaos)


def test_explicit_catalog_construction() -> None:
    subset = {"NYC": STATIONS["NYC"]}
    cat = StationCatalog(subset)
    assert len(cat) == 1
    assert cat.get("KNYC").code == "NYC"

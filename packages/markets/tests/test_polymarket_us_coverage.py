"""Contract tests for the Phase 8 Polymarket US-city additions.

Mirrors the structure of tests/catalog/test_kalshi_stations.py — same
asserter-style contract tests, same severity (these are silent-corruption
guards, not nits).
"""

from __future__ import annotations

from collections.abc import Mapping

import pytest
from mostlyright.markets._per_event_station import load_polymarket_city_stations
from mostlyright.markets.polymarket import KNOWN_WRONG_STATIONS
from mostlyright.markets.polymarket_city_citations import POLYMARKET_CITY_CITATIONS

#: The Phase 8 US cities. Exact set — adding one requires a PLAN change.
# Phase 23 reduced Polymarket's US roster to 11 cities — Boston, DC,
# Philadelphia, Phoenix, Minneapolis, and Detroit left the live roster (their
# station records remain in the catalog as bare weather stations).
US_CITIES_PHASE_8 = frozenset(
    {
        "nyc",
        "chicago",
        "los_angeles",
        "miami",
        "denver",
        "austin",
        "san_francisco",
        "seattle",
        "atlanta",
        "houston",
        "dallas",
    }
)


@pytest.fixture()
def city_map():
    return load_polymarket_city_stations()


# ---------------------------------------------------------------------------
# US city catalog additions
# ---------------------------------------------------------------------------
class TestUSCoverage:
    def test_us_city_set_matches_expected(self, city_map):
        present = set(city_map) & US_CITIES_PHASE_8
        missing = US_CITIES_PHASE_8 - present
        assert missing == set(), f"missing US cities: {sorted(missing)}"

    def test_nyc_default_is_KLGA_not_KNYC(self, city_map):
        """The hard invariant — Polymarket uses LaGuardia, NOT Central Park."""
        assert city_map["nyc"]["default"] == "KLGA"
        assert city_map["nyc"]["default"] != "KNYC"

    def test_chicago_default_is_KORD_not_KMDW(self, city_map):
        """Cross-issuer divergence — Polymarket uses O'Hare; Kalshi uses Midway."""
        assert city_map["chicago"]["default"] == "KORD"

    def test_each_us_city_has_default_key(self, city_map):
        for c in US_CITIES_PHASE_8:
            assert "default" in city_map[c], f"{c!r} missing default key"

    def test_each_us_city_station_is_K_ICAO(self, city_map):
        for c in US_CITIES_PHASE_8:
            station = city_map[c]["default"]
            assert isinstance(station, str)
            assert len(station) == 4, f"{c!r}: station {station!r} not 4-char"
            assert station.startswith("K"), f"{c!r}: station {station!r} not K-prefix"

    def test_NYC_split_keys_all_KLGA(self, city_map):
        """The explicit high/low keys must also point at KLGA for asymmetric cities."""
        nyc = city_map["nyc"]
        assert nyc["high"] == "KLGA"
        assert nyc["low"] == "KLGA"

    def test_chicago_split_keys_all_KORD(self, city_map):
        chi = city_map["chicago"]
        assert chi["high"] == "KORD"
        assert chi["low"] == "KORD"


# ---------------------------------------------------------------------------
# Citation registry
# ---------------------------------------------------------------------------
class TestCitations:
    def test_each_us_city_has_a_citation(self):
        missing = US_CITIES_PHASE_8 - set(POLYMARKET_CITY_CITATIONS)
        assert missing == set(), f"cities without citation: {sorted(missing)}"

    def test_each_citation_references_wunderground(self):
        for city, citation in POLYMARKET_CITY_CITATIONS.items():
            assert "wunderground.com" in citation, (
                f"{city!r}: weak citation — must reference wunderground.com"
            )

    def test_citation_count_matches_us_cities(self):
        assert len(POLYMARKET_CITY_CITATIONS) == len(US_CITIES_PHASE_8)


# ---------------------------------------------------------------------------
# Per-issuer denylist
# ---------------------------------------------------------------------------
class TestKnownWrongStations:
    def test_KNOWN_WRONG_STATIONS_is_per_city_mapping(self):
        assert isinstance(KNOWN_WRONG_STATIONS, Mapping)

    def test_nyc_denylist_includes_KNYC_KJFK_KEWR(self):
        assert "KNYC" in KNOWN_WRONG_STATIONS["nyc"]
        assert "KJFK" in KNOWN_WRONG_STATIONS["nyc"]
        assert "KEWR" in KNOWN_WRONG_STATIONS["nyc"]

    def test_KLGA_NOT_in_nyc_denylist(self):
        """KLGA is the CORRECT NYC station for Polymarket — cannot be denied."""
        assert "KLGA" not in KNOWN_WRONG_STATIONS["nyc"]

    def test_chicago_denylist_includes_KMDW(self):
        assert "KMDW" in KNOWN_WRONG_STATIONS["chicago"]

    def test_KORD_NOT_in_chicago_denylist(self):
        assert "KORD" not in KNOWN_WRONG_STATIONS["chicago"]

    def test_KNOWN_WRONG_STATIONS_is_read_only(self):
        with pytest.raises(TypeError):
            KNOWN_WRONG_STATIONS["nyc"] = frozenset()  # type: ignore[index]

    def test_per_city_set_is_frozenset(self):
        for city, st in KNOWN_WRONG_STATIONS.items():
            assert isinstance(st, frozenset), f"{city!r}: not frozenset"


# ---------------------------------------------------------------------------
# Catalog vs denylist invariant
# ---------------------------------------------------------------------------
class TestCatalogVsDenylist:
    def test_no_us_catalog_entry_resolves_to_its_own_denylist(self, city_map):
        """Hard invariant: catalog's chosen station MUST NOT be in that city's denylist."""
        for city in US_CITIES_PHASE_8:
            entry = city_map[city]
            denylist = KNOWN_WRONG_STATIONS.get(city, frozenset())
            for measure_key, station in entry.items():
                assert station not in denylist, (
                    f"{city!r}[{measure_key!r}] = {station!r} appears in its own denylist "
                    f"{sorted(denylist)!r} — silent-corruption invariant violated"
                )

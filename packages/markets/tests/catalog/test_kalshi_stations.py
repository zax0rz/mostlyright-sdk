"""Contract tests for the Kalshi station whitelist + NHIGH/NLOW resolvers."""

from __future__ import annotations

from datetime import date

import pytest
from tradewinds.markets.catalog import kalshi_nhigh, kalshi_nlow
from tradewinds.markets.catalog.kalshi_stations import (
    KALSHI_SETTLEMENT_STATIONS,
    KNOWN_WRONG_STATIONS,
    StationCitation,
)


def test_whitelist_has_20_entries():
    """v0.1.0 scope — exactly 20 cities."""
    assert len(KALSHI_SETTLEMENT_STATIONS) == 20


def test_no_wrong_stations():
    """The known-wrong stations must NEVER appear in any whitelist value."""
    used_stations = {c.station for c in KALSHI_SETTLEMENT_STATIONS.values()}
    overlap = used_stations & KNOWN_WRONG_STATIONS
    assert overlap == set(), (
        f"Whitelist contains known-wrong stations: {overlap}. "
        f"Parity-critical — fix the whitelist."
    )


def test_each_station_is_icao_format():
    """Stations must be 4-character ICAO codes starting with 'K'."""
    for ticker, c in KALSHI_SETTLEMENT_STATIONS.items():
        assert isinstance(c.station, str)
        assert len(c.station) == 4, f"{ticker!r}: station {c.station!r}"
        assert c.station.startswith("K"), f"{ticker!r}: station {c.station!r}"


def test_each_entry_has_citation():
    """Every whitelist entry must have a non-empty citation URL."""
    for ticker, c in KALSHI_SETTLEMENT_STATIONS.items():
        assert c.citation, f"{ticker!r}: empty citation"
        assert "kalshi.com" in c.citation, f"{ticker!r}: weak citation"


def test_NYC_is_KNYC_not_LGA_or_JFK():
    """The most common settlement-station mistake."""
    assert KALSHI_SETTLEMENT_STATIONS["NYC"].station == "KNYC"


def test_CHI_is_KMDW_not_KORD():
    """The second most common mistake."""
    assert KALSHI_SETTLEMENT_STATIONS["CHI"].station == "KMDW"


def test_DCA_is_KDCA_not_KIAD_or_KBWI():
    assert KALSHI_SETTLEMENT_STATIONS["DCA"].station == "KDCA"


def test_StationCitation_rejects_bad_codes():
    with pytest.raises(ValueError, match="4-letter ICAO"):
        StationCitation("KNY", "")
    with pytest.raises(ValueError, match="4-letter ICAO"):
        StationCitation("MORD", "")  # doesn't start with K


# ---------------------------------------------------------------------------
# NHIGH / NLOW resolvers
# ---------------------------------------------------------------------------
class TestNHighResolve:
    def test_KHIGHNYC_resolves_to_KNYC(self):
        r = kalshi_nhigh.resolve("KHIGHNYC", date(2025, 1, 1))
        assert r.settlement_source == "cli.archive"
        assert r.settlement_station == "KNYC"
        assert r.city_ticker == "NYC"
        assert r.contract_date == date(2025, 1, 1)

    def test_lowercase_contract_id_accepted(self):
        r = kalshi_nhigh.resolve("khighchi", date(2025, 1, 1))
        assert r.settlement_station == "KMDW"

    def test_bad_format_raises(self):
        with pytest.raises(ValueError, match="KHIGH"):
            kalshi_nhigh.resolve("BOGUSNYC", date(2025, 1, 1))

    def test_unknown_city_raises(self):
        with pytest.raises(ValueError, match="Unknown Kalshi city ticker"):
            kalshi_nhigh.resolve("KHIGHHNL", date(2025, 1, 1))

    def test_deterministic(self):
        r1 = kalshi_nhigh.resolve("KHIGHNYC", date(2025, 1, 1))
        r2 = kalshi_nhigh.resolve("KHIGHNYC", date(2025, 1, 1))
        assert r1 == r2

    def test_all_whitelist_cities_resolve(self):
        for city in KALSHI_SETTLEMENT_STATIONS:
            r = kalshi_nhigh.resolve(f"KHIGH{city}", date(2025, 1, 1))
            assert r.settlement_station == KALSHI_SETTLEMENT_STATIONS[city].station


class TestNLowResolve:
    def test_KLOWNYC_resolves_to_KNYC(self):
        r = kalshi_nlow.resolve("KLOWNYC", date(2025, 1, 1))
        assert r.settlement_station == "KNYC"
        assert r.settlement_source == "cli.archive"

    def test_lowercase_contract_id_accepted(self):
        r = kalshi_nlow.resolve("klowchi", date(2025, 1, 1))
        assert r.settlement_station == "KMDW"

    def test_bad_format_raises(self):
        with pytest.raises(ValueError, match="KLOW"):
            kalshi_nlow.resolve("BOGUSNYC", date(2025, 1, 1))

    def test_unknown_city_raises(self):
        with pytest.raises(ValueError, match="Unknown Kalshi city ticker"):
            kalshi_nlow.resolve("KLOWXYZ", date(2025, 1, 1))

    def test_all_whitelist_cities_resolve(self):
        for city in KALSHI_SETTLEMENT_STATIONS:
            r = kalshi_nlow.resolve(f"KLOW{city}", date(2025, 1, 1))
            assert r.settlement_station == KALSHI_SETTLEMENT_STATIONS[city].station

"""Contract tests for the Kalshi station whitelist + NHIGH/NLOW resolvers."""

from __future__ import annotations

from datetime import date

import pytest
from mostlyright import CATALOG
from mostlyright.markets.catalog import kalshi_nhigh, kalshi_nlow
from mostlyright.markets.catalog.kalshi_stations import (
    KALSHI_SETTLEMENT_STATIONS,
    KNOWN_WRONG_STATIONS,
    StationCitation,
)


def test_whitelist_has_21_entries():
    """v0.1.0 scope — 20 original cities + Las Vegas (TLV, issue #39)."""
    assert len(KALSHI_SETTLEMENT_STATIONS) == 21


def test_citations_match_core_kalshi_venue_tags():
    """Phase 22 — markets citations and core venue tags must not drift.

    Core (``mostlyright.stations``) is the venue-membership authority; the
    Kalshi citation dict here is venue-specific provenance. The settlement
    ICAOs in the citations must equal the stations core tags ``kalshi``,
    or a backtest could settle against a station core doesn't recognize.
    """
    citation_icaos = {c.station for c in KALSHI_SETTLEMENT_STATIONS.values()}
    core_kalshi_icaos = {s.icao for s in CATALOG.filter_by_venue("kalshi")}
    assert citation_icaos == core_kalshi_icaos


def test_no_wrong_stations():
    """The known-wrong stations must NEVER appear in any whitelist value."""
    used_stations = {c.station for c in KALSHI_SETTLEMENT_STATIONS.values()}
    overlap = used_stations & KNOWN_WRONG_STATIONS
    assert overlap == set(), (
        f"Whitelist contains known-wrong stations: {overlap}. Parity-critical — fix the whitelist."
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


# ----------------------------------------------------------------------
# Type validation (codex iter-8 HIGH)
# ----------------------------------------------------------------------
class TestResolverTypeValidation:
    def test_nhigh_settlement_date_not_date_raises(self):
        with pytest.raises(TypeError, match="settlement_date"):
            kalshi_nhigh.resolve("KHIGHNYC", "2025-01-01")  # type: ignore[arg-type]

    def test_nlow_settlement_date_not_date_raises(self):
        with pytest.raises(TypeError, match="settlement_date"):
            kalshi_nlow.resolve("KLOWNYC", "2025-01-01")  # type: ignore[arg-type]

    def test_nhigh_settlement_date_int_raises(self):
        with pytest.raises(TypeError, match="settlement_date"):
            kalshi_nhigh.resolve("KHIGHNYC", 20250101)  # type: ignore[arg-type]

    def test_nlow_settlement_date_int_raises(self):
        with pytest.raises(TypeError, match="settlement_date"):
            kalshi_nlow.resolve("KLOWNYC", 20250101)  # type: ignore[arg-type]

    def test_nhigh_contract_id_not_str_raises(self):
        with pytest.raises(TypeError, match="contract_id"):
            kalshi_nhigh.resolve(123, date(2025, 1, 1))  # type: ignore[arg-type]

    def test_nlow_contract_id_not_str_raises(self):
        with pytest.raises(TypeError, match="contract_id"):
            kalshi_nlow.resolve(None, date(2025, 1, 1))  # type: ignore[arg-type]

    def test_datetime_rejected_by_nhigh(self):
        """codex iter-9 HIGH: datetime is a subclass of date but carries
        a time component — must be rejected explicitly because
        date(...) == datetime(...) is False, so downstream settlement-date
        matching would silently miss the row.
        """
        from datetime import datetime

        with pytest.raises(TypeError, match="not datetime"):
            kalshi_nhigh.resolve("KHIGHNYC", datetime(2025, 1, 1))

    def test_datetime_rejected_by_nlow(self):
        from datetime import datetime

        with pytest.raises(TypeError, match="not datetime"):
            kalshi_nlow.resolve("KLOWNYC", datetime(2025, 1, 1))

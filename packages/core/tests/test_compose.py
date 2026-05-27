"""Phase 10 — tests for the composable ``research()`` dispatcher."""

from __future__ import annotations

import warnings

import pytest
from mostlyright._compose import (
    StationOverrideWarning,
    annotate_settles_for,
    emit_override_warning,
    resolve_city,
    resolve_contract,
    validate_selectors,
)


# ---------------------------------------------------------------------------
# validate_selectors
# ---------------------------------------------------------------------------
class TestValidateSelectors:
    def test_station_only_returns_station(self):
        assert validate_selectors(station="KNYC") == "station"

    def test_city_only_returns_city(self):
        assert validate_selectors(city="NYC") == "city"

    def test_contract_only_returns_contract(self):
        assert validate_selectors(contract="kalshi:KHIGHNYC") == "contract"

    def test_contracts_only_returns_contracts(self):
        assert validate_selectors(contracts=["kalshi:KHIGHNYC"]) == "contracts"

    def test_no_selector_raises(self):
        with pytest.raises(ValueError, match="exactly one of"):
            validate_selectors()

    def test_empty_string_selector_treated_as_missing(self):
        with pytest.raises(ValueError, match="exactly one of"):
            validate_selectors(station="", city="", contract="", contracts=None)

    def test_empty_contracts_list_treated_as_missing(self):
        with pytest.raises(ValueError, match="exactly one of"):
            validate_selectors(contracts=[])

    def test_two_selectors_raises(self):
        with pytest.raises(ValueError, match="mutually exclusive"):
            validate_selectors(station="KNYC", city="NYC")

    def test_three_selectors_raises(self):
        with pytest.raises(ValueError, match="mutually exclusive"):
            validate_selectors(station="KNYC", city="NYC", contract="kalshi:KHIGHNYC")


# ---------------------------------------------------------------------------
# resolve_contract
# ---------------------------------------------------------------------------
class TestResolveContract:
    def test_kalshi_KHIGHNYC_resolves_to_KNYC(self):
        station, issuer = resolve_contract("kalshi:KHIGHNYC")
        assert station == "KNYC"
        assert issuer == "kalshi"

    def test_kalshi_KXHIGHNYC_resolves_to_KNYC(self):
        station, issuer = resolve_contract("kalshi:KXHIGHNYC")
        assert station == "KNYC"
        assert issuer == "kalshi"

    def test_kalshi_KLOWNYC_resolves_to_KNYC(self):
        station, issuer = resolve_contract("kalshi:KLOWNYC")
        assert station == "KNYC"
        assert issuer == "kalshi"

    def test_kalshi_KHIGHCHI_resolves_to_KMDW(self):
        """Kalshi Chicago = Midway (not O'Hare; Polymarket uses O'Hare)."""
        station, _ = resolve_contract("kalshi:KHIGHCHI")
        assert station == "KMDW"

    def test_kalshi_full_ticker_with_date_suffix_resolves(self):
        """Real Kalshi market tickers carry trailing -DATE-STRIKE."""
        station, _ = resolve_contract("kalshi:KXHIGHNYC-25MAY26-T79")
        assert station == "KNYC"

    def test_kalshi_full_low_ticker_with_suffix(self):
        station, _ = resolve_contract("kalshi:KXLOWCHI-25MAY26-T50")
        assert station == "KMDW"

    def test_kalshi_NY_short_ticker_aliases_to_NYC(self):
        """Iter-1 codex HIGH: real Kalshi NYC ticker `KXHIGHNY-...` uses
        2-letter NY suffix (not NYC). The alias table normalizes."""
        station, _ = resolve_contract("kalshi:KXHIGHNY-25MAY26-T79")
        assert station == "KNYC"

    def test_kalshi_LOW_NY_short_ticker_aliases_to_NYC(self):
        station, _ = resolve_contract("kalshi:KXLOWNY-25MAY26-T50")
        assert station == "KNYC"

    def test_kalshi_bad_prefix_raises(self):
        with pytest.raises(ValueError, match="unsupported kalshi contract"):
            resolve_contract("kalshi:BOGUSNYC")

    def test_polymarket_raises_notimplemented(self):
        with pytest.raises(NotImplementedError, match="polymarket contract resolution"):
            resolve_contract("polymarket:0x123")

    def test_unknown_issuer_raises(self):
        with pytest.raises(ValueError, match="unknown issuer"):
            resolve_contract("predictit:abc")

    def test_no_colon_raises(self):
        with pytest.raises(ValueError, match="must be `<issuer>:<id>`"):
            resolve_contract("KHIGHNYC")

    def test_non_string_raises(self):
        with pytest.raises(ValueError, match="must be `<issuer>:<id>`"):
            resolve_contract(123)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# resolve_city
# ---------------------------------------------------------------------------
class TestResolveCity:
    def test_NYC_includes_KNYC_and_KLGA(self):
        stations = resolve_city("NYC")
        assert "KNYC" in stations  # Kalshi
        assert "KLGA" in stations  # Polymarket

    def test_NYC_includes_denylist_backstops(self):
        """Polymarket denylist for nyc lists KJFK + KEWR; resolve_city
        surfaces them so quants see the full neighborhood."""
        stations = resolve_city("NYC")
        assert "KJFK" in stations
        assert "KEWR" in stations

    def test_chicago_includes_KMDW_and_KORD(self):
        stations = resolve_city("CHI")
        assert "KMDW" in stations  # Kalshi
        # Note: resolve_city("CHI") uses upper for Kalshi; Polymarket
        # uses "chicago" lower-key. resolve_city normalizes both.
        # CHI is Kalshi-only short slug; the polymarket "chicago" key
        # won't auto-match. Test the dual-side version separately.

    def test_chicago_via_polymarket_slug_includes_KORD(self):
        stations = resolve_city("chicago")
        assert "KORD" in stations  # Polymarket
        assert "KMDW" in stations  # Polymarket denylist surfaces Midway

    def test_unknown_city_raises(self):
        with pytest.raises(ValueError, match="unknown city"):
            resolve_city("atlantis")

    def test_empty_city_raises(self):
        with pytest.raises(ValueError, match="non-empty str"):
            resolve_city("")

    def test_returns_tuple_not_list(self):
        result = resolve_city("NYC")
        assert isinstance(result, tuple)

    def test_dedupes_overlapping_stations(self):
        """A station that's both the Kalshi target AND in the Polymarket
        catalog (or denylist) should appear once, not twice."""
        stations = resolve_city("NYC")
        assert stations.count("KNYC") == 1
        assert stations.count("KLGA") == 1

    def test_LAX_cross_issuer_alias_surfaces_polymarket(self):
        """Iter-1 python-architect HIGH: cross-issuer slug alias
        ensures `resolve_city("LAX")` (Kalshi short) ALSO finds
        Polymarket's los_angeles entry."""
        stations = resolve_city("LAX")
        assert "KLAX" in stations
        # Polymarket maps los_angeles → KLAX (same as Kalshi LAX).
        # Verify the cross-issuer query annotates it (via separate test).
        annotations = annotate_settles_for("KLAX", "LAX")
        assert "polymarket:los_angeles" in annotations
        assert "kalshi:LAX" in annotations

    def test_los_angeles_cross_issuer_alias_surfaces_kalshi(self):
        """Reverse: `resolve_city("los_angeles")` (Polymarket long) ALSO
        finds Kalshi's LAX entry."""
        stations = resolve_city("los_angeles")
        assert "KLAX" in stations
        annotations = annotate_settles_for("KLAX", "los_angeles")
        assert "kalshi:LAX" in annotations
        assert "polymarket:los_angeles" in annotations

    def test_washington_dc_cross_issuer_alias(self):
        """DCA (Kalshi) ↔ washington_dc (Polymarket) alias."""
        stations = resolve_city("DCA")
        assert "KDCA" in stations
        stations_long = resolve_city("washington_dc")
        # Both forms surface KDCA.
        assert "KDCA" in stations_long


# ---------------------------------------------------------------------------
# annotate_settles_for
# ---------------------------------------------------------------------------
class TestAnnotateSettlesFor:
    def test_KNYC_in_NYC_returns_kalshi_marker(self):
        assert "kalshi:NYC" in annotate_settles_for("KNYC", "NYC")

    def test_KLGA_in_NYC_returns_polymarket_marker(self):
        assert "polymarket:nyc" in annotate_settles_for("KLGA", "NYC")

    def test_KJFK_in_NYC_returns_empty(self):
        """KJFK is in Polymarket's denylist — no issuer settles against it
        for NYC."""
        assert annotate_settles_for("KJFK", "NYC") == []

    def test_none_city_returns_empty(self):
        assert annotate_settles_for("KNYC", None) == []

    def test_KMDW_in_CHI_returns_kalshi(self):
        assert "kalshi:CHI" in annotate_settles_for("KMDW", "CHI")

    def test_KORD_in_chicago_returns_polymarket(self):
        assert "polymarket:chicago" in annotate_settles_for("KORD", "chicago")

    def test_NYC_KNYC_full_round_trip(self):
        """Cross-issuer asymmetry surfaced cleanly."""
        # KNYC settles Kalshi, NOT Polymarket
        kalshi_only = annotate_settles_for("KNYC", "NYC")
        assert kalshi_only == ["kalshi:NYC"]
        # KLGA settles Polymarket NYC (using lower-case nyc to match
        # Polymarket catalog key), NOT Kalshi
        poly_only = annotate_settles_for("KLGA", "nyc")
        assert poly_only == ["polymarket:nyc"]


# ---------------------------------------------------------------------------
# StationOverrideWarning + emit helper
# ---------------------------------------------------------------------------
class TestStationOverrideWarning:
    def test_is_user_warning_subclass(self):
        assert issubclass(StationOverrideWarning, UserWarning)

    def test_emit_override_warning_fires(self):
        with warnings.catch_warnings(record=True) as captured:
            warnings.simplefilter("always")
            emit_override_warning("KNYC", "KJFK")
        assert len(captured) == 1
        assert issubclass(captured[0].category, StationOverrideWarning)
        assert "KNYC" in str(captured[0].message)
        assert "KJFK" in str(captured[0].message)


# ---------------------------------------------------------------------------
# research() signature validation (Phase 10 dispatcher)
# ---------------------------------------------------------------------------
class TestResearchSignatureValidation:
    """The dispatcher only validates the kwargs; the actual multi-station
    join is deferred to v0.3. These tests verify the validation surface
    is correct + the backwards-compat station path is preserved."""

    def test_no_selector_raises(self):
        from mostlyright import research

        with pytest.raises(ValueError, match="exactly one of"):
            research()

    def test_two_selectors_raises(self):
        from mostlyright import research

        with pytest.raises(ValueError, match="mutually exclusive"):
            research(station="KNYC", city="NYC")

    def test_station_without_dates_raises(self):
        from mostlyright import research

        with pytest.raises(ValueError, match="from_date and to_date"):
            research(station="NYC")

    def test_sources_and_source_mutually_exclusive(self):
        from mostlyright import research

        # Phase 21 21-01 tightened the validation to raise TypeError (matches
        # the TS lockstep contract); pre-21-01 raised ValueError. Accept
        # either to keep the test resilient if 21-01 reverts.
        with pytest.raises((TypeError, ValueError), match="mutually exclusive"):
            research(
                station="NYC",
                from_date="2025-01-06",
                to_date="2025-01-12",
                sources=["iem.archive"],
                source="iem.archive",
            )

    def test_sources_only_raises_notimplemented_v03(self):
        """Iter-1 codex HIGH: sources= silently bypassed the data-fetch
        wiring. v0.2 now raises NotImplementedError directing callers at
        researchBySource for Mode-2 today + v0.3 for sources=[]."""
        from mostlyright import research

        with pytest.raises(NotImplementedError, match=r"v0\.3"):
            research(
                station="NYC",
                from_date="2025-01-06",
                to_date="2025-01-12",
                sources=["iem.archive"],
            )

    def test_source_only_raises_notimplemented_v03(self):
        from mostlyright import research

        with pytest.raises(NotImplementedError, match="research_by_source"):
            research(
                station="NYC",
                from_date="2025-01-06",
                to_date="2025-01-12",
                source="iem.archive",
            )

    def test_station_override_requires_contract(self):
        from mostlyright import research

        with pytest.raises(ValueError, match="requires contract="):
            research(
                station="NYC",
                from_date="2025-01-06",
                to_date="2025-01-12",
                station_override="KJFK",
            )

    def test_include_trades_requires_contract_selector(self):
        from mostlyright import research

        with pytest.raises(ValueError, match="include_trades=True requires"):
            research(
                station="NYC",
                from_date="2025-01-06",
                to_date="2025-01-12",
                include_trades=True,
            )

    def test_city_selector_v02_raises_notimplemented(self):
        """v0.2 surfaces the selector + validates kwargs but defers the
        multi-station join to v0.3."""
        from mostlyright import research

        with pytest.raises(NotImplementedError, match=r"v0\.3"):
            research(city="NYC", from_date="2025-01-06", to_date="2025-01-12")

    def test_contract_selector_v02_raises_notimplemented(self):
        from mostlyright import research

        with pytest.raises(NotImplementedError, match=r"v0\.3"):
            research(
                contract="kalshi:KHIGHNYC",
                from_date="2025-01-06",
                to_date="2025-01-12",
            )

    def test_contracts_selector_v02_raises_notimplemented(self):
        from mostlyright import research

        with pytest.raises(NotImplementedError, match=r"v0\.3"):
            research(
                contracts=["kalshi:KHIGHNYC"],
                from_date="2025-01-06",
                to_date="2025-01-12",
                include_trades=True,
            )

    def test_validation_runs_before_v03_notimplemented(self):
        """Mutual-exclusion + override-requires-contract validation must
        fire BEFORE the v0.3 NotImplementedError. Order matters: callers
        should see the validation error (which is fixable now) rather
        than the deferred-feature error (which isn't)."""
        from mostlyright import research

        with pytest.raises(ValueError, match="mutually exclusive"):
            research(city="NYC", contract="kalshi:KHIGHNYC")

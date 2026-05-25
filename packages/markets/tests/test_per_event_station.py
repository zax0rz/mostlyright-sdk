"""Tests for the Phase 3.1 per-event station resolver.

Exercises ``mostlyright.markets._per_event_station.resolve_station_for_event``:

- Single-airport cities → ``default`` lookup.
- Paris LFPG/LFPB split via high/low keyword detection.
- Taipei + HK-low → ``DeferredMarketError``.
- HK-high → resolves cleanly (HK only defers the "low" measure).
- Unknown city → KeyError.
- City map loader sanity.
"""

from __future__ import annotations

import pytest
from mostlyright.international import DeferredMarketError
from mostlyright.markets._per_event_station import (
    DEFERRED_STATION_MEASURES,
    extract_icao_from_resolution_source,
    load_polymarket_city_stations,
    resolve_station_for_event,
)


@pytest.fixture()
def city_map():
    """Real bundled city map — used for end-to-end sanity tests."""
    return load_polymarket_city_stations()


# ---------------------------------------------------------------------------
# Loader.
# ---------------------------------------------------------------------------
def test_load_polymarket_city_stations_returns_dict(city_map):
    assert isinstance(city_map, dict)
    # 40-ICAO coverage means roughly 39 city keys (Paris collapses 2 airports
    # into one entry with a high/low split).
    assert len(city_map) >= 39
    # London is the canonical single-airport entry.
    assert city_map["london"] == {"default": "EGLL"}


def test_load_polymarket_city_stations_is_independent_copy(city_map):
    """Mutating the returned map MUST NOT corrupt the module cache."""
    city_map["london"]["default"] = "MUTATED"
    fresh = load_polymarket_city_stations()
    assert fresh["london"]["default"] == "EGLL"


def test_paris_entry_has_high_low_split(city_map):
    assert city_map["paris"] == {
        "high": "LFPG",
        "low": "LFPB",
        "default": "LFPG",
    }


# ---------------------------------------------------------------------------
# Single-airport cities: always resolve to "default".
# ---------------------------------------------------------------------------
def test_tokyo_resolves_to_rjtt_default(city_map):
    event = {"city": "tokyo", "title": "Tokyo Daily High"}
    icao, measure = resolve_station_for_event(event, city_map)
    assert icao == "RJTT"
    # Tokyo's map has "high"/"low"/"default" all set to RJTT (built that way
    # so the resolver still returns "high" when the title says high — same
    # ICAO).
    assert measure in {"high", "default"}


def test_london_resolves_default_even_with_high_keyword(city_map):
    """London map has no `high` key — falls back to default."""
    event = {"city": "london", "title": "Will London hit a record high?"}
    icao, measure = resolve_station_for_event(event, city_map)
    assert icao == "EGLL"
    assert measure == "default"


def test_sydney_default(city_map):
    event = {"city": "sydney"}
    icao, measure = resolve_station_for_event(event, city_map)
    assert icao == "YSSY"
    assert measure == "default"


# ---------------------------------------------------------------------------
# Paris split.
# ---------------------------------------------------------------------------
def test_paris_high_routes_to_lfpg(city_map):
    event = {"city": "paris", "title": "Paris HIGHEST temperature 12-Jul-2025"}
    icao, measure = resolve_station_for_event(event, city_map)
    assert icao == "LFPG"
    assert measure == "high"


def test_paris_low_routes_to_lfpb(city_map):
    event = {"city": "paris", "title": "Paris LOWEST temperature 12-Jul-2025"}
    icao, measure = resolve_station_for_event(event, city_map)
    assert icao == "LFPB"
    assert measure == "low"


def test_paris_neutral_title_uses_default(city_map):
    event = {"city": "paris", "title": "Paris temperature"}
    icao, measure = resolve_station_for_event(event, city_map)
    assert icao == "LFPG"  # default
    assert measure == "default"


def test_paris_keyword_in_slug(city_map):
    event = {"city": "paris", "slug": "paris-lowest-temp-2025-12-31"}
    icao, _ = resolve_station_for_event(event, city_map)
    assert icao == "LFPB"


def test_paris_ambiguous_high_AND_low_title_falls_back_to_default(city_map):
    """Ambiguous titles must route to default — never silently pick low.

    Architect review caught: the original implementation ran the "low" regex
    first, so any title with BOTH "low" and "high" tokens silently routed to
    LFPB. Fix: when both keywords are present, return "default" (let the city
    map decide), and the city's chosen default airport handles the event.
    """
    event = {
        "city": "paris",
        "title": "Will Paris see a record-LOW precipitation AND record-HIGH temperature?",
    }
    icao, measure = resolve_station_for_event(event, city_map)
    assert measure == "default"
    assert icao == "LFPG"  # default in the bundled map


# ---------------------------------------------------------------------------
# Deferred markets.
# ---------------------------------------------------------------------------
def test_taipei_defers(city_map):
    event = {"city": "taipei", "title": "Taipei Daily High"}
    with pytest.raises(DeferredMarketError, match="deferred"):
        resolve_station_for_event(event, city_map)


def test_taipei_default_defers(city_map):
    event = {"city": "taipei"}
    with pytest.raises(DeferredMarketError):
        resolve_station_for_event(event, city_map)


def test_hong_kong_low_defers(city_map):
    """HKO is the resolution source for HK daily lows → defer to v0.2."""
    event = {"city": "hong_kong", "title": "Hong Kong LOWEST temp 2025"}
    with pytest.raises(DeferredMarketError, match="deferred"):
        resolve_station_for_event(event, city_map)


def test_hong_kong_high_resolves_cleanly(city_map):
    """HK 'high' resolves via routine METAR — must NOT defer."""
    event = {"city": "hong_kong", "title": "Hong Kong HIGHEST temp 2025"}
    icao, measure = resolve_station_for_event(event, city_map)
    assert icao == "VHHH"
    assert measure == "high"


def test_deferred_station_measures_table_shape():
    """The defer table contains the canonical (icao, measure) pairs."""
    assert ("VHHH", "low") in DEFERRED_STATION_MEASURES
    # HK high is NOT in the table.
    assert ("VHHH", "high") not in DEFERRED_STATION_MEASURES
    # Taipei: every measure is deferred.
    assert ("RCTP", "high") in DEFERRED_STATION_MEASURES
    assert ("RCTP", "low") in DEFERRED_STATION_MEASURES
    assert ("RCTP", "default") in DEFERRED_STATION_MEASURES


# ---------------------------------------------------------------------------
# Error paths.
# ---------------------------------------------------------------------------
def test_unknown_city_raises_keyerror(city_map):
    event = {"city": "atlantis"}
    with pytest.raises(KeyError, match="unknown city"):
        resolve_station_for_event(event, city_map)


def test_missing_city_field_raises_keyerror(city_map):
    event = {"title": "no city here"}
    with pytest.raises(KeyError, match="missing 'city'"):
        resolve_station_for_event(event, city_map)


def test_city_lookup_is_case_insensitive(city_map):
    event = {"city": "LONDON"}
    icao, _ = resolve_station_for_event(event, city_map)
    assert icao == "EGLL"


# ---------------------------------------------------------------------------
# Custom city_map override (tests the dependency injection seam).
# ---------------------------------------------------------------------------
def test_custom_city_map_overrides_bundled_data():
    """Callers can pass a synthetic map for tests / future market additions."""
    custom = {"atlantis": {"default": "AAAA"}}
    icao, measure = resolve_station_for_event({"city": "atlantis"}, custom)
    assert icao == "AAAA"
    assert measure == "default"


# ---------------------------------------------------------------------------
# Phase 8 — Tier 1.5 URL extraction (POLY-US-03).
# ---------------------------------------------------------------------------
class TestExtractIcaoFromResolutionSource:
    def test_pws_url_returns_KLGA(self):
        assert (
            extract_icao_from_resolution_source("https://wunderground.com/dashboard/pws/KLGA")
            == "KLGA"
        )

    def test_bare_pws_path_returns_KLGA(self):
        assert extract_icao_from_resolution_source("https://wunderground.com/pws/KLGA") == "KLGA"

    def test_history_daily_url_with_date_returns_KLGA(self):
        assert (
            extract_icao_from_resolution_source(
                "see https://www.wunderground.com/history/daily/KLGA/date/2026-05-23"
            )
            == "KLGA"
        )

    def test_history_airport_url_returns_KORD(self):
        assert (
            extract_icao_from_resolution_source(
                "https://www.wunderground.com/history/airport/KORD/2026/5/23/DailyHistory.html"
            )
            == "KORD"
        )

    def test_weather_station_url_returns_KSFO(self):
        assert (
            extract_icao_from_resolution_source("https://wunderground.com/weather-station/KSFO")
            == "KSFO"
        )

    def test_noncanonical_news_path_returns_None(self):
        """Architect iter-1 HIGH: incidental K-prefix tokens in non-canonical
        Wunderground URL paths (news, dashboards, slugs) MUST NOT extract."""
        assert (
            extract_icao_from_resolution_source(
                "https://www.wunderground.com/news/2024-summer-KIDS-overview"
            )
            is None
        )

    def test_weather_gov_url_returns_None(self):
        """weather.gov is allowlisted for source-type classification
        but NOT for ICAO extraction."""
        assert extract_icao_from_resolution_source("https://weather.gov/nyc") is None

    def test_none_returns_None(self):
        assert extract_icao_from_resolution_source(None) is None

    def test_empty_returns_None(self):
        assert extract_icao_from_resolution_source("") is None

    def test_text_without_url_returns_None(self):
        assert extract_icao_from_resolution_source("no urls here") is None

    def test_lowercase_icao_does_not_match(self):
        """Iter-3 codex CRITICAL: dropped IGNORECASE to fix a silent-corruption
        path where the case-insensitive `[a-z0-9-]+/` consumed uppercase
        station slugs. Trade-off: synthetic lowercase ICAOs no longer match.
        Real Wunderground URLs use uppercase ICAOs by convention so this is
        production-correct."""
        assert (
            extract_icao_from_resolution_source("https://wunderground.com/dashboard/pws/klax")
            is None
        )

    def test_non_string_returns_None(self):
        # Defensive — callers occasionally pass back raw dict values.
        assert extract_icao_from_resolution_source(12345) is None  # type: ignore[arg-type]

    def test_disagreeing_multi_url_returns_None(self):
        """Architect iter-1 HIGH: multiple disagreeing canonical URLs → abstain."""
        text = (
            "Primary https://www.wunderground.com/dashboard/pws/KLAX "
            "or use https://www.wunderground.com/dashboard/pws/KSFO instead"
        )
        assert extract_icao_from_resolution_source(text) is None

    def test_agreeing_multi_url_returns_the_ICAO(self):
        text = (
            "Primary https://www.wunderground.com/dashboard/pws/KLAX "
            "and mirror https://www.wunderground.com/history/daily/KLAX/date/2026-05-23"
        )
        assert extract_icao_from_resolution_source(text) == "KLAX"

    # ---------------------------------------------------------------------
    # Iter-2 architect CRITICAL: real Polymarket URL shapes carry
    # country/state/city slugs between the anchor and the ICAO.
    # ---------------------------------------------------------------------
    def test_real_polymarket_nyc_url(self):
        """Real Polymarket NYC settlement URL with /us/ny/new-york-city/ slugs."""
        url = "https://www.wunderground.com/history/daily/us/ny/new-york-city/KLGA"
        assert extract_icao_from_resolution_source(url) == "KLGA"

    def test_real_polymarket_chicago_url(self):
        """Real Polymarket Chicago settlement URL with /us/il/chicago/ slugs."""
        url = "https://www.wunderground.com/history/daily/us/il/chicago/KORD"
        assert extract_icao_from_resolution_source(url) == "KORD"

    def test_real_polymarket_la_url(self):
        url = "https://www.wunderground.com/history/daily/us/ca/los-angeles/KLAX"
        assert extract_icao_from_resolution_source(url) == "KLAX"

    def test_cat_forecasts_url_with_state_slugs(self):
        url = "https://www.wunderground.com/cat/forecasts/us/ny/new-york/KLGA"
        assert extract_icao_from_resolution_source(url) == "KLGA"

    # ---------------------------------------------------------------------
    # Iter-2 codex CRITICAL: URL terminators in prose / Markdown.
    # ---------------------------------------------------------------------
    def test_markdown_url_with_trailing_paren(self):
        text = "see [station](https://www.wunderground.com/dashboard/pws/KLGA)"
        assert extract_icao_from_resolution_source(text) == "KLGA"

    def test_url_followed_by_period(self):
        text = "Settles via https://www.wunderground.com/dashboard/pws/KLGA."
        assert extract_icao_from_resolution_source(text) == "KLGA"

    def test_url_followed_by_comma(self):
        text = "Sources: https://www.wunderground.com/dashboard/pws/KLGA, plus others"
        assert extract_icao_from_resolution_source(text) == "KLGA"

    # ---------------------------------------------------------------------
    # Regression guard for the architect HIGH on incidental tokens.
    # ---------------------------------------------------------------------
    def test_pws_with_hyphenated_id_does_not_extract_prefix(self):
        """`/pws/KIDS-summer-2024` MUST NOT extract `KIDS`. The negative
        lookahead `(?![A-Za-z0-9_-])` rejects `K[A-Z]{3}-` continuations
        so a non-ICAO PWS ID with a K-prefix-like start is not silently
        truncated to a 4-char extraction."""
        url = "https://wunderground.com/pws/KIDS-summer-2024"
        assert extract_icao_from_resolution_source(url) is None

    def test_pws_with_longer_uppercase_id_does_not_extract_prefix(self):
        """`/pws/KORDX` MUST NOT extract `KORD`."""
        url = "https://wunderground.com/pws/KORDX"
        assert extract_icao_from_resolution_source(url) is None

    # ---------------------------------------------------------------------
    # Iter-3 codex CRITICAL: regex must NOT consume uppercase station slot
    # as an "intermediate slug" when IGNORECASE is dropped.
    # ---------------------------------------------------------------------
    def test_history_daily_uppercase_first_segment_is_canonical_station(self):
        """`/history/daily/KORD/date/KLAX` extracts `KORD`, not `KLAX`.
        The canonical station slot is the FIRST K[A-Z]{3} after the anchor;
        the intermediate-slug pattern is lowercase-only so it cannot
        consume an uppercase station segment."""
        url = "https://www.wunderground.com/history/daily/KORD/date/KLAX"
        assert extract_icao_from_resolution_source(url) == "KORD"

    def test_pws_with_trailing_uppercase_path_is_canonical(self):
        """`/dashboard/pws/KORD/nearby/KLAX` extracts `KORD`."""
        url = "https://wunderground.com/pws/KORD/nearby/KLAX"
        assert extract_icao_from_resolution_source(url) == "KORD"

    def test_history_airport_uppercase_trailing_is_canonical(self):
        """`/history/airport/KORD/2026/5/KLAX/DailyHistory.html` extracts `KORD`."""
        url = "https://www.wunderground.com/history/airport/KORD/2026/5/KLAX/DailyHistory.html"
        assert extract_icao_from_resolution_source(url) == "KORD"

    def test_real_polymarket_url_with_uppercase_trailing_path(self):
        """Real-shape URL with trailing uppercase path components."""
        url = "https://www.wunderground.com/history/daily/us/il/chicago/KORD/date/KLAX"
        assert extract_icao_from_resolution_source(url) == "KORD"


class TestResolverTier1_5:
    def test_url_extraction_overrides_catalog(self, city_map):
        """Tier 1.5 wins over catalog lookup — the URL is the issuer's proof.

        Architect iter-1 HIGH: prior version used city=chicago + URL=KORD,
        where catalog and URL both returned KORD — tautological. The bite-y
        fixture uses a city whose catalog ICAO disagrees with the URL, so the
        test only passes if Tier 1.5 actually fires.
        """
        event = {
            "city": "chicago",  # catalog → KORD
            "title": "Chicago daily high",
            "description": "Resolves via https://www.wunderground.com/dashboard/pws/KLAX",
        }
        icao, _ = resolve_station_for_event(event, city_map)
        # URL wins, NOT the chicago→KORD catalog default.
        assert icao == "KLAX"

    def test_url_extraction_works_without_city(self, city_map):
        """Tier 1.5 alone resolves an event with no city field."""
        event = {
            "title": "Daily high somewhere",
            "description": "https://www.wunderground.com/dashboard/pws/KLAX",
        }
        icao, _ = resolve_station_for_event(event, city_map)
        assert icao == "KLAX"

    def test_url_extraction_picks_up_resolution_source_field(self, city_map):
        event = {
            "title": "high",
            "resolutionSource": "https://wunderground.com/dashboard/pws/KLGA",
        }
        icao, _ = resolve_station_for_event(event, city_map)
        assert icao == "KLGA"

    def test_multi_url_disagreement_abstains(self, city_map):
        """Architect iter-1 HIGH #2: multiple disagreeing Wunderground URLs
        in description → Tier 1.5 abstains; resolver falls through to Tier 2.

        The bite-y check: this event has city=chicago (catalog→KORD) + two
        disagreeing URLs (KLAX + KSFO). Tier 1.5 must abstain so the
        resolver falls through to the chicago→KORD catalog answer.
        Otherwise first-match-wins would silently route to KLAX.
        """
        event = {
            "city": "chicago",
            "description": (
                "See https://www.wunderground.com/dashboard/pws/KLAX "
                "and historical https://www.wunderground.com/history/daily/KSFO/date/2026-01-01"
            ),
        }
        icao, _ = resolve_station_for_event(event, city_map)
        # Tier 1.5 abstains; resolver falls through to Tier 2 catalog (chicago → KORD).
        assert icao == "KORD"

    def test_multi_url_agreement_passes(self, city_map):
        """Multiple URLs that all extract the same ICAO → Tier 1.5 fires."""
        event = {
            "city": "chicago",
            "description": (
                "Primary https://www.wunderground.com/dashboard/pws/KLAX "
                "or alternate https://www.wunderground.com/history/daily/KLAX/date/2026-05-23"
            ),
        }
        icao, _ = resolve_station_for_event(event, city_map)
        assert icao == "KLAX"

    def test_noncanonical_url_path_falls_through_to_catalog(self, city_map):
        """Architect iter-1 HIGH #1: incidental K-tokens in non-canonical paths
        (news articles, weather alerts) MUST NOT trigger Tier 1.5 — the regex
        only matches canonical PWS / airport / weather-station paths."""
        event = {
            "city": "boston",
            "description": "See https://www.wunderground.com/news/2024-summer-KIDS-overview",
        }
        icao, _ = resolve_station_for_event(event, city_map)
        # Tier 1.5 should NOT fire on news path → catalog wins (boston → KBOS).
        assert icao == "KBOS"

    def test_url_extraction_carries_market_measure(self, city_map):
        """The 'high'/'low' measure still comes from title — URL only sets the ICAO."""
        event = {
            "title": "Will the LOWEST temperature in LA drop below 50?",
            "description": "https://wunderground.com/dashboard/pws/KLAX",
        }
        icao, measure = resolve_station_for_event(event, city_map)
        assert icao == "KLAX"
        assert measure == "low"

    def test_url_extraction_still_respects_defer_gate(self, city_map, monkeypatch):
        """Defense-in-depth — even when Tier 1.5 fires, defer gate runs.

        Inject a test-only deferred-station-measure for KLGA so we can
        exercise the gate without altering the production defer list.
        """
        from mostlyright.markets import _per_event_station as mod

        patched = frozenset(mod.DEFERRED_STATION_MEASURES | {("KLGA", "default")})
        monkeypatch.setattr(mod, "DEFERRED_STATION_MEASURES", patched)
        event = {"description": "https://wunderground.com/dashboard/pws/KLGA"}
        with pytest.raises(DeferredMarketError, match="deferred"):
            resolve_station_for_event(event, city_map)

    def test_no_url_falls_through_to_tier_2(self, city_map):
        """When no Wunderground URL, behavior unchanged — Tier 2 city derive."""
        event = {"city": "london", "title": "London temperature"}
        icao, _ = resolve_station_for_event(event, city_map)
        assert icao == "EGLL"

    def test_non_wunderground_url_falls_through_to_catalog(self, city_map):
        """Only wunderground.com URLs trigger Tier 1.5."""
        event = {
            "city": "boston",
            "description": "https://weather.gov/forecast/KBOS",
        }
        icao, _ = resolve_station_for_event(event, city_map)
        # Catalog lookup wins, but boston defaults to KBOS anyway —
        # the assertion is that we don't error AND we don't surface KBOS
        # via Tier 1.5 (weather.gov isn't allowlisted for extraction).
        assert icao == "KBOS"

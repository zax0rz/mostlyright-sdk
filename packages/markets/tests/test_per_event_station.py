"""Tests for the Phase 3.1 per-event station resolver.

Exercises ``tradewinds.markets._per_event_station.resolve_station_for_event``:

- Single-airport cities → ``default`` lookup.
- Paris LFPG/LFPB split via high/low keyword detection.
- Taipei + HK-low → ``DeferredMarketError``.
- HK-high → resolves cleanly (HK only defers the "low" measure).
- Unknown city → KeyError.
- City map loader sanity.
"""

from __future__ import annotations

import pytest
from tradewinds.international import DeferredMarketError
from tradewinds.markets._per_event_station import (
    DEFERRED_STATION_MEASURES,
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

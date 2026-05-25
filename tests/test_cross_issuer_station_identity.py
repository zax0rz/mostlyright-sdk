"""Phase 8 cross-issuer station-identity invariants.

The hard invariant: the same city resolves to DIFFERENT settlement stations
across Kalshi and Polymarket, AND each issuer's chosen station is forbidden
in the OTHER issuer's denylist (where applicable). Silent-corruption guard:
a refactor that conflates the two issuers' station maps would fail one of
the assertions below.

This file lives at repo-root ``tests/`` because the invariants span
``packages/markets`` modules (kalshi_stations vs polymarket) — it's a
cross-package contract.
"""

from __future__ import annotations

from mostlyright.markets._per_event_station import load_polymarket_city_stations
from mostlyright.markets.catalog.kalshi_stations import (
    KALSHI_SETTLEMENT_STATIONS,
)
from mostlyright.markets.catalog.kalshi_stations import (
    KNOWN_WRONG_STATIONS as KALSHI_KNOWN_WRONG_STATIONS,
)
from mostlyright.markets.polymarket import (
    KNOWN_WRONG_STATIONS as POLYMARKET_KNOWN_WRONG_STATIONS,
)


def test_nyc_kalshi_is_KNYC_polymarket_is_KLGA():
    """Phase 8 headline invariant — Kalshi NYC = KNYC, Polymarket NYC = KLGA."""
    poly = load_polymarket_city_stations()
    assert KALSHI_SETTLEMENT_STATIONS["NYC"].station == "KNYC"
    assert poly["nyc"]["default"] == "KLGA"
    assert KALSHI_SETTLEMENT_STATIONS["NYC"].station != poly["nyc"]["default"]


def test_chicago_kalshi_is_KMDW_polymarket_is_KORD():
    """Second-most-common disagreement — Kalshi uses Midway, Polymarket uses O'Hare."""
    poly = load_polymarket_city_stations()
    assert KALSHI_SETTLEMENT_STATIONS["CHI"].station == "KMDW"
    assert poly["chicago"]["default"] == "KORD"


def test_KLGA_is_kalshi_wrong_but_polymarket_right_for_nyc():
    """The cross-inverse invariant — KLGA is in Kalshi's global denylist
    AND KLGA is the CORRECT Polymarket NYC station (so NOT in its denylist).
    """
    assert "KLGA" in KALSHI_KNOWN_WRONG_STATIONS
    assert "KLGA" not in POLYMARKET_KNOWN_WRONG_STATIONS["nyc"]


def test_KNYC_is_polymarket_wrong_for_nyc():
    """The mirror — KNYC IS the Kalshi NYC station, but Polymarket lists
    it as wrong for nyc (Polymarket uses KLGA, never KNYC)."""
    assert KALSHI_SETTLEMENT_STATIONS["NYC"].station == "KNYC"
    assert "KNYC" in POLYMARKET_KNOWN_WRONG_STATIONS["nyc"]


def test_KMDW_is_polymarket_wrong_for_chicago():
    """KMDW IS the Kalshi Chicago station (KMDW = Midway) but Polymarket
    forbids it for chicago (Polymarket uses KORD)."""
    assert KALSHI_SETTLEMENT_STATIONS["CHI"].station == "KMDW"
    assert "KMDW" in POLYMARKET_KNOWN_WRONG_STATIONS["chicago"]


def test_KORD_is_kalshi_wrong_polymarket_right_for_chicago():
    """KORD is correct for Polymarket Chicago AND was historically wrong for
    Kalshi (Kalshi uses KMDW; KORD is in Kalshi's denylist)."""
    poly = load_polymarket_city_stations()
    assert "KORD" in KALSHI_KNOWN_WRONG_STATIONS
    assert poly["chicago"]["default"] == "KORD"
    assert "KORD" not in POLYMARKET_KNOWN_WRONG_STATIONS["chicago"]


def test_every_kalshi_city_station_not_in_kalshi_denylist():
    """Parametric mirror of test_no_wrong_stations in test_kalshi_stations.py —
    repeats here so the cross-issuer file is self-contained as a regression target."""
    used = {c.station for c in KALSHI_SETTLEMENT_STATIONS.values()}
    overlap = used & KALSHI_KNOWN_WRONG_STATIONS
    assert overlap == set(), f"Kalshi catalog overlaps denylist: {overlap}"


def test_every_polymarket_us_city_default_not_in_own_denylist():
    """Parametric — every Polymarket US-city default station is NOT in that
    city's own denylist. Mirrors test_no_us_catalog_entry_resolves_to_its_own_denylist."""
    poly = load_polymarket_city_stations()
    for city, denylist in POLYMARKET_KNOWN_WRONG_STATIONS.items():
        if city not in poly:
            continue  # international city without a denylist entry — skip
        default = poly[city]["default"]
        assert default not in denylist, (
            f"polymarket {city!r} default {default!r} appears in own denylist {sorted(denylist)!r}"
        )


def test_per_issuer_denylists_are_namespace_isolated():
    """The two denylists are DIFFERENT shapes (Kalshi = flat frozenset,
    Polymarket = per-city Mapping). Each issuer owns its own namespace —
    a refactor that 'unifies' them would fail this assertion."""
    from collections.abc import Mapping

    assert isinstance(KALSHI_KNOWN_WRONG_STATIONS, frozenset)
    assert isinstance(POLYMARKET_KNOWN_WRONG_STATIONS, Mapping)
    assert not isinstance(POLYMARKET_KNOWN_WRONG_STATIONS, frozenset)

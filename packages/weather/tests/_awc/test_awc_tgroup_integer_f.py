"""Phase 18 PREC-01 — RED tests for AWC integer-°F recovery from Tgroup.

Implementation lands in Task 2.

These tests pin the schema-conformant behaviour promised by observation.json:41
(``temp_f`` "recovers the internal whole-degree Fahrenheit value exactly"):

- When the raw METAR carries a Tgroup remark (``T########``) the row originated
  from an integer-°F ASOS sensor. ``temp_f`` / ``dewpoint_f`` MUST be emitted
  as integer-valued floats recovered via ``round(temp_c * 9 / 5 + 32)``.
- When no Tgroup is present (international stations, KNYC Central Park, any
  non-ASOS origin) the legacy ``celsius_to_fahrenheit`` float path is preserved
  for backward compatibility.

Tests A-E cover the branching matrix. Test F is the 12-station integer-°F
invariant. Test G is the round-trip invariant the schema promises.
"""

from __future__ import annotations

from typing import Any

import pytest
from mostlyright.weather._awc import awc_to_observation


def _make_awc_dict(**overrides: Any) -> dict[str, Any]:
    """Build a minimal valid AWC METAR dict with sensible defaults.

    The AWC parser only needs icaoId/obsTime/metarType + the fields the tests
    exercise. ``rawOb`` carries the Tgroup remark (or lack thereof).
    """
    base: dict[str, Any] = {
        "icaoId": "KLGA",
        "obsTime": 1730000000,  # 2024-10-27T03:33:20Z (irrelevant — must be valid)
        "metarType": "METAR",
        "temp": 27.0,
        "dewp": 11.0,
        "wdir": 250,
        "wspd": 8,
        "wgst": None,
        "altim": 1020.0,
        "slp": 1020.1,
        "visib": "10",
        "wxString": None,
        "clouds": [],
        "precip": None,
        "rawOb": "KLGA 251151Z 25008KT 10SM CLR 27/11 A3012 RMK AO2 SLP201 T02670111 10272 20217",
        "qcField": 6,
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Test A — KLGA happy path: Tgroup tenths-°C => integer-valued °F recovery.
# Raw METAR `T02670111` => temp_c = 26.7, dewpoint_c = 11.1.
# Expected: temp_f == 80.0, dewpoint_f == 52.0 (integer-valued floats).
# Current code emits 80.06 / 51.98 — these assertions WILL fail until Task 2.
# ---------------------------------------------------------------------------
def test_klga_tgroup_recovers_integer_temp_f() -> None:
    """Test A: KLGA Tgroup recovers integer-valued temp_f / dewpoint_f."""
    awc_dict = _make_awc_dict(
        icaoId="KLGA",
        temp=27.0,
        dewp=11.0,
        rawOb=("KLGA 251151Z 25008KT 10SM CLR 27/11 A3012 RMK AO2 SLP201 T02670111 10272 20217"),
    )
    obs = awc_to_observation(awc_dict)
    assert obs is not None
    # tenths-°C from Tgroup
    assert obs["temp_c"] == 26.7
    assert obs["dewpoint_c"] == 11.1
    # integer-valued float °F — this is the recovery contract
    assert obs["temp_f"] == 80.0, f"expected 80.0 integer-recovered, got {obs['temp_f']!r}"
    assert obs["temp_f"] == int(obs["temp_f"])
    assert obs["dewpoint_f"] == 52.0, f"expected 52.0 integer-recovered, got {obs['dewpoint_f']!r}"
    assert obs["dewpoint_f"] == int(obs["dewpoint_f"])


# ---------------------------------------------------------------------------
# Test B — Negative temp Tgroup recovery.
# T10390061 => temp_c = -3.9 (sign=1 => negative), dewpoint_c = 6.1.
# round(-3.9 * 9/5 + 32) = round(24.98) = 25 => temp_f == 25.0
# round( 6.1 * 9/5 + 32) = round(42.98) = 43 => dewpoint_f == 43.0
# ---------------------------------------------------------------------------
def test_negative_tgroup_recovers_integer_temp_f() -> None:
    """Test B: Negative Tgroup temp still recovers integer-°F."""
    awc_dict = _make_awc_dict(
        icaoId="KORD",
        temp=-4.0,
        dewp=6.0,
        rawOb="KORD 251151Z 18004KT 10SM CLR M04/06 A3012 RMK AO2 T10390061",
    )
    obs = awc_to_observation(awc_dict)
    assert obs is not None
    assert obs["temp_c"] == -3.9
    assert obs["dewpoint_c"] == 6.1
    assert obs["temp_f"] == 25.0
    assert obs["temp_f"] == int(obs["temp_f"])
    assert obs["dewpoint_f"] == 43.0
    assert obs["dewpoint_f"] == int(obs["dewpoint_f"])


# ---------------------------------------------------------------------------
# Test C — No Tgroup (international LFPG-like): celsius_to_fahrenheit float.
# METAR has no RMK section => parse_tgroup returns (None, None) => legacy path
# => temp_f = 18.0 * 9/5 + 32 = 64.4 (a float, NOT integer-valued).
# ---------------------------------------------------------------------------
def test_no_tgroup_international_uses_float_temp_f() -> None:
    """Test C: International (no RMK) preserves legacy float temp_f path."""
    awc_dict = _make_awc_dict(
        icaoId="LFPG",
        temp=18.0,
        dewp=12.0,
        rawOb="LFPG 251200Z 27010KT 9999 SCT040 18/12 Q1018 NOSIG",
    )
    obs = awc_to_observation(awc_dict)
    assert obs is not None
    assert obs["temp_c"] == 18.0
    assert obs["dewpoint_c"] == 12.0
    # No Tgroup => legacy celsius_to_fahrenheit; NOT integer-valued.
    assert obs["temp_f"] == pytest.approx(64.4, rel=0, abs=1e-9)
    assert obs["dewpoint_f"] == pytest.approx(53.6, rel=0, abs=1e-9)
    assert obs["temp_f"] != int(obs["temp_f"])
    assert obs["dewpoint_f"] != int(obs["dewpoint_f"])


# ---------------------------------------------------------------------------
# Test D — RMK present but no Tgroup remark (e.g. KNYC Central Park).
# RMK ... AO2 SLP123 — no T-group; parse_tgroup returns (None, None) =>
# legacy float path with body group temperature.
# ---------------------------------------------------------------------------
def test_rmk_without_tgroup_uses_float_temp_f() -> None:
    """Test D: RMK present but no Tgroup => legacy float temp_f path."""
    awc_dict = _make_awc_dict(
        icaoId="KNYC",
        temp=22.0,
        dewp=14.0,
        rawOb="KNYC 251151Z 18005KT 10SM CLR 22/14 A3000 RMK AO2 SLP123",
    )
    obs = awc_to_observation(awc_dict)
    assert obs is not None
    assert obs["temp_c"] == 22.0
    assert obs["dewpoint_c"] == 14.0
    assert obs["temp_f"] == pytest.approx(71.6, rel=0, abs=1e-9)
    assert obs["dewpoint_f"] == pytest.approx(57.2, rel=0, abs=1e-9)
    assert obs["temp_f"] != int(obs["temp_f"])


# ---------------------------------------------------------------------------
# Test E — Tgroup with out-of-bounds temperature.
# T07000000 => temp_c = 70.0 (> TEMP_MAX_C = 60.0) => bounded_float returns None
# => temp_f MUST also be None. Confirms the integer-°F branch respects the
# bounded_float gate (and doesn't crash on `round(None * 9/5 + 32)`).
# ---------------------------------------------------------------------------
def test_tgroup_out_of_bounds_yields_none_temp_f() -> None:
    """Test E: Out-of-bounds Tgroup => bounded_float nulls temp_c AND temp_f."""
    awc_dict = _make_awc_dict(
        icaoId="KJFK",
        temp=60.0,
        dewp=0.0,
        # T07000000 — temp tenths = 700/10 = 70.0°C (> 60°C max).
        rawOb="KJFK 251151Z 18005KT 10SM CLR 60/00 A3000 RMK AO2 T07000000",
    )
    obs = awc_to_observation(awc_dict)
    assert obs is not None
    assert obs["temp_c"] is None  # bounded out
    assert obs["temp_f"] is None  # MUST be None — does NOT crash on None input
    assert obs["dewpoint_c"] == 0.0
    # dewpoint Tgroup is 0 => 0.0°C => 32°F integer-recovered
    assert obs["dewpoint_f"] == 32.0
    assert obs["dewpoint_f"] == int(obs["dewpoint_f"])


# ---------------------------------------------------------------------------
# Test F — Parametrized 12-station Tgroup integer-°F invariant.
# For each known-good Tgroup METAR, temp_f / dewpoint_f MUST be integer-valued.
# These 12 stations are the empirical sample from 18-CONTEXT.md (4,594 readings,
# 100% integer-°F match).
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("icao", "raw_metar", "expected_temp_c", "expected_temp_f"),
    [
        # T0267 => 26.7 °C => round(26.7*9/5+32) = round(80.06) = 80
        ("KLGA", "KLGA RMK AO2 T02670111", 26.7, 80.0),
        # T0233 => 23.3 °C => round(23.3*9/5+32) = round(73.94) = 74
        ("KJFK", "KJFK RMK AO2 T02330133", 23.3, 74.0),
        # T0211 => 21.1 °C => round(21.1*9/5+32) = round(69.98) = 70
        ("KEWR", "KEWR RMK AO2 T02110100", 21.1, 70.0),
        # T0156 => 15.6 °C => round(15.6*9/5+32) = round(60.08) = 60
        ("KBOS", "KBOS RMK AO2 T01560106", 15.6, 60.0),
        # T0167 => 16.7 °C => round(16.7*9/5+32) = round(62.06) = 62
        ("KORD", "KORD RMK AO2 T01670111", 16.7, 62.0),
        # T0289 => 28.9 °C => round(28.9*9/5+32) = round(84.02) = 84
        ("KDFW", "KDFW RMK AO2 T02890172", 28.9, 84.0),
        # T0222 => 22.2 °C => round(22.2*9/5+32) = round(71.96) = 72
        ("KLAX", "KLAX RMK AO2 T02220150", 22.2, 72.0),
        # T0267 => 26.7 °C => 80
        ("KMIA", "KMIA RMK AO2 T02670222", 26.7, 80.0),
        # T1006 => -0.6 °C => round(-0.6*9/5+32) = round(30.92) = 31
        ("KDEN", "KDEN RMK AO2 T10061050", -0.6, 31.0),
        # T0117 => 11.7 °C => round(11.7*9/5+32) = round(53.06) = 53
        ("KSEA", "KSEA RMK AO2 T01170094", 11.7, 53.0),
        # T0244 => 24.4 °C => round(24.4*9/5+32) = round(75.92) = 76
        ("KATL", "KATL RMK AO2 T02440183", 24.4, 76.0),
        # T0367 => 36.7 °C => round(36.7*9/5+32) = round(98.06) = 98
        ("KPHX", "KPHX RMK AO2 T03670089", 36.7, 98.0),
    ],
)
def test_twelve_station_tgroup_emits_integer_temp_f(
    icao: str, raw_metar: str, expected_temp_c: float, expected_temp_f: float
) -> None:
    """Test F: 12-station Tgroup sample => all temp_f are integer-valued floats."""
    awc_dict = _make_awc_dict(icaoId=icao, temp=expected_temp_c, dewp=0.0, rawOb=raw_metar)
    obs = awc_to_observation(awc_dict)
    assert obs is not None, f"{icao}: parser returned None"
    assert obs["temp_c"] == expected_temp_c, f"{icao}: temp_c mismatch"
    assert (
        obs["temp_f"] == expected_temp_f
    ), f"{icao}: expected integer-°F {expected_temp_f}, got {obs['temp_f']!r}"
    # Integer-valued float invariants
    assert obs["temp_f"].is_integer(), f"{icao}: temp_f is not integer-valued"
    assert obs["temp_f"] == int(obs["temp_f"]), f"{icao}: float != int round-trip"


# ---------------------------------------------------------------------------
# Test G — Round-trip invariant: for any Tgroup-bearing observation,
# round(temp_c * 9 / 5 + 32) must equal int(temp_f). This is the schema's
# explicit promise at observation.json:41.
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "raw_metar",
    [
        "KLGA RMK AO2 T02670111",
        "KJFK RMK AO2 T10390061",
        "KORD RMK AO2 T11251089",
        "KMIA RMK AO2 T00000000",  # 0.0°C => 32°F
        "KDFW RMK AO2 T02890172",
        "KPHX RMK AO2 T03670089",
    ],
)
def test_tgroup_round_trip_invariant(raw_metar: str) -> None:
    """Test G: round(temp_c * 9/5 + 32) == int(temp_f) for every Tgroup row."""
    awc_dict = _make_awc_dict(
        icaoId=raw_metar.split()[0],
        temp=10.0,
        dewp=0.0,
        rawOb=raw_metar,
    )
    obs = awc_to_observation(awc_dict)
    assert obs is not None
    assert obs["temp_c"] is not None
    assert obs["temp_f"] is not None
    expected_int_f = round(obs["temp_c"] * 9 / 5 + 32)
    assert int(obs["temp_f"]) == expected_int_f, (
        f"schema round-trip violated: temp_c={obs['temp_c']} expected "
        f"int_f={expected_int_f}, got temp_f={obs['temp_f']!r}"
    )
    # And the float should be integer-valued
    assert obs["temp_f"].is_integer()

"""Issue 16 — GHCNh integer-°F recovery from T-group in REM (RED tests).

GHCNh stores U.S. ASOS temperatures in tenths-°C in the PSV `temperature`
field; the REM column carries the original raw METAR string which includes
the T-group remark (e.g. T01060067). When the T-group is present, the row
originated from an integer-°F ASOS sensor — `temp_f` MUST be emitted as an
integer-valued float recovered via ``round(temp_c * 9 / 5 + 32)``, identical
to the AWC path (Phase 18 PREC-01).

When no T-group is present (international stations, synoptic rows) the legacy
``celsius_to_fahrenheit`` float path is preserved.

Test layout mirrors packages/weather/tests/_awc/test_awc_tgroup_integer_f.py.
"""

from __future__ import annotations

import pytest
from mostlyright.weather._ghcnh import parse_ghcnh_row


def _make_row(**overrides: str) -> dict[str, str]:
    """Build a minimal valid GHCNh PSV row dict (as csv.DictReader produces)."""
    base: dict[str, str] = {
        "STATION": "USW00094789",
        "Station_name": "JFK INTL AP",
        "DATE": "2025-01-15T12:00:00",
        "temperature": "10.6",
        "temperature_Quality_Code": "5",
        "temperature_Report_Type": "FM15",
        "temperature_Source_Station_ID": "ICAO-KJFK",
        "dew_point_temperature": "6.7",
        "dew_point_temperature_Quality_Code": "5",
        "dew_point_temperature_Source_Station_ID": "ICAO-KJFK",
        "sea_level_pressure": "1002.4",
        "sea_level_pressure_Quality_Code": "5",
        "wind_direction": "090",
        "wind_direction_Quality_Code": "5",
        "wind_speed": "8.8",
        "wind_speed_Quality_Code": "5",
        "wind_gust": "",
        "wind_gust_Quality_Code": "",
        "altimeter": "1002.4",
        "altimeter_Quality_Code": "4",
        "visibility": "16.093",
        "visibility_Quality_Code": "5",
        "precipitation": "",
        "precipitation_Measurement_Code": "",
        "precipitation_Quality_Code": "",
        "snow_depth": "",
        "snow_depth_Quality_Code": "",
        "pres_wx_AW1": "",
        "pres_wx_AW2": "",
        "pres_wx_AW3": "",
        "sky_cover_summation_1": "",
        "sky_cover_summation_2": "",
        "sky_cover_summation_3": "",
        "sky_cover_summation_4": "",
        "sky_cover_summation_baseht_1": "",
        "sky_cover_summation_baseht_2": "",
        "sky_cover_summation_baseht_3": "",
        "sky_cover_summation_baseht_4": "",
        # REM contains the raw METAR string; T-group lives in the RMK section.
        "REM": (
            "MET14012/31/24 20:51:03 METAR KJFK 010151Z 09017G26KT 10SM "
            "SCT031 BKN045 BKN065 11/07 A2960 RMK AO2 SLP024 T01060067 (RR)"
        ),
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Test A — KJFK happy path from real GHCNh fixture data.
# temperature=10.6 (tenths-°C from T-group), REM has T01060067.
# round(10.6 * 9/5 + 32) = round(51.08) = 51 → temp_f == 51.0
# Current code emits 51.08 — these assertions WILL fail until the fix lands.
# ---------------------------------------------------------------------------
def test_kjfk_tgroup_in_rem_recovers_integer_temp_f() -> None:
    """Test A: REM T-group → integer-valued temp_f / dewpoint_f."""
    obs = parse_ghcnh_row(_make_row(temperature="10.6", dew_point_temperature="6.7"))
    assert obs is not None
    assert obs["temp_c"] == 10.6
    assert obs["dewpoint_c"] == 6.7
    assert obs["temp_f"] == 51.0, f"expected 51.0 integer-recovered, got {obs['temp_f']!r}"
    assert obs["temp_f"] == int(obs["temp_f"])
    # round(6.7 * 9/5 + 32) = round(44.06) = 44
    assert obs["dewpoint_f"] == 44.0, f"expected 44.0, got {obs['dewpoint_f']!r}"
    assert obs["dewpoint_f"] == int(obs["dewpoint_f"])


# ---------------------------------------------------------------------------
# Test B — Negative temp T-group recovery (KDEN-style cold reading).
# temperature=-3.9, REM has T10390061.
# round(-3.9 * 9/5 + 32) = round(24.98) = 25 → temp_f == 25.0
# ---------------------------------------------------------------------------
def test_negative_tgroup_in_rem_recovers_integer_temp_f() -> None:
    """Test B: Negative temp with T-group in REM → integer-°F recovery."""
    obs = parse_ghcnh_row(
        _make_row(
            temperature="-3.9",
            dew_point_temperature="6.1",
            temperature_Source_Station_ID="ICAO-KDEN",
            REM="MET METAR KDEN 010151Z 18006KT 10SM CLR M04/06 A3012 RMK AO2 T10390061",
        )
    )
    assert obs is not None
    assert obs["temp_c"] == -3.9
    assert obs["dewpoint_c"] == 6.1
    assert obs["temp_f"] == 25.0
    assert obs["temp_f"] == int(obs["temp_f"])
    # round(6.1 * 9/5 + 32) = round(42.98) = 43
    assert obs["dewpoint_f"] == 43.0
    assert obs["dewpoint_f"] == int(obs["dewpoint_f"])


# ---------------------------------------------------------------------------
# Test C — Empty REM (no T-group): legacy celsius_to_fahrenheit path.
# temperature=10.6, REM="" → no T-group → temp_f = 10.6*9/5+32 = 51.08 (float).
# ---------------------------------------------------------------------------
def test_empty_rem_uses_legacy_float_temp_f() -> None:
    """Test C: Empty REM → no T-group → legacy float temp_f preserved."""
    from mostlyright._internal._convert import celsius_to_fahrenheit

    obs = parse_ghcnh_row(_make_row(temperature="10.6", REM=""))
    assert obs is not None
    assert obs["temp_c"] == 10.6
    assert obs["temp_f"] == pytest.approx(celsius_to_fahrenheit(10.6), rel=0, abs=1e-9)
    # Legacy path: NOT integer-valued (would be 51.08...)
    assert obs["temp_f"] != int(obs["temp_f"])


# ---------------------------------------------------------------------------
# Test D — REM present but no T-group (synoptic or international METAR).
# The SYN-format REM row from real fixture (FM12) has no RMK T-group.
# ---------------------------------------------------------------------------
def test_rem_without_tgroup_uses_legacy_float_temp_f() -> None:
    """Test D: REM present but no T-group → legacy celsius_to_fahrenheit path."""
    from mostlyright._internal._convert import celsius_to_fahrenheit

    obs = parse_ghcnh_row(
        _make_row(
            temperature="9.4",
            temperature_Source_Station_ID="ICAO-KJFK",
            REM=(
                "SYN08674486 32766 60914 10094 20056 30060 40069 58030 "
                "92351 333 10122 20033 91021 555 90100="
            ),
        )
    )
    assert obs is not None
    assert obs["temp_c"] == 9.4
    assert obs["temp_f"] == pytest.approx(celsius_to_fahrenheit(9.4), rel=0, abs=1e-9)


# ---------------------------------------------------------------------------
# Test E — T-group present in REM but temp bounded out (out-of-range °C).
# temperature=500.0 (> 60°C max) → bounded_float returns None → temp_f MUST be None.
# Confirms the guard `temp_c is not None` prevents crash on round(None * 9/5 + 32).
# ---------------------------------------------------------------------------
def test_tgroup_rem_with_out_of_bounds_temp_yields_none_temp_f() -> None:
    """Test E: T-group in REM + out-of-bounds temp → temp_f is None (no crash)."""
    obs = parse_ghcnh_row(
        _make_row(
            temperature="500.0",
            REM="METAR KJFK 010151Z 00000KT 10SM CLR M00/M00 A3000 RMK AO2 T05000000",
        )
    )
    assert obs is not None
    assert obs["temp_c"] is None  # bounded out
    assert obs["temp_f"] is None  # MUST be None — does NOT crash


# ---------------------------------------------------------------------------
# Test F — Parametrized 12-station integer-°F invariant for GHCNh rows.
# Each row has a T-group in REM; temp_f MUST be integer-valued and match
# round(temp_c * 9/5 + 32). Values match the cross-source consistency fixture.
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("icao", "rem_tgroup", "temp_c", "expected_temp_f"),
    [
        # T02670111 → 26.7°C → round(26.7*9/5+32) = round(80.06) = 80
        ("ICAO-KLGA", "T02670111", 26.7, 80.0),
        # T02220139 → 22.2°C → round(22.2*9/5+32) = round(71.96) = 72
        ("ICAO-KJFK", "T02220139", 22.2, 72.0),
        # T02440117 → 24.4°C → round(24.4*9/5+32) = round(75.92) = 76
        ("ICAO-KEWR", "T02440117", 24.4, 76.0),
        # T01890089 → 18.9°C → round(18.9*9/5+32) = round(66.02) = 66
        ("ICAO-KBOS", "T01890089", 18.9, 66.0),
        # T02560150 → 25.6°C → round(25.6*9/5+32) = round(78.08) = 78
        ("ICAO-KORD", "T02560150", 25.6, 78.0),
        # T03110178 → 31.1°C → round(31.1*9/5+32) = round(88.0) = 88
        ("ICAO-KDFW", "T03110178", 31.1, 88.0),
        # T02170117 → 21.7°C → round(21.7*9/5+32) = round(71.06) = 71
        ("ICAO-KLAX", "T02170117", 21.7, 71.0),
        # T02890222 → 28.9°C → round(28.9*9/5+32) = round(84.02) = 84
        ("ICAO-KMIA", "T02890222", 28.9, 84.0),
        # T01501022 → 15.0°C → round(15.0*9/5+32) = round(59.0) = 59
        ("ICAO-KDEN", "T01501022", 15.0, 59.0),
        # T01330106 → 13.3°C → round(13.3*9/5+32) = round(55.94) = 56
        ("ICAO-KSEA", "T01330106", 13.3, 56.0),
        # T02440161 → 24.4°C → round(24.4*9/5+32) = round(75.92) = 76
        ("ICAO-KATL", "T02440161", 24.4, 76.0),
        # T03560111 → 35.6°C → round(35.6*9/5+32) = round(96.08) = 96
        ("ICAO-KPHX", "T03560111", 35.6, 96.0),
    ],
)
def test_twelve_station_ghcnh_tgroup_emits_integer_temp_f(
    icao: str, rem_tgroup: str, temp_c: float, expected_temp_f: float
) -> None:
    """Test F: 12-station GHCNh sample with T-group in REM → integer-valued temp_f."""
    obs = parse_ghcnh_row(
        _make_row(
            temperature=str(temp_c),
            temperature_Source_Station_ID=icao,
            REM=f"METAR {icao[5:]} 010151Z 00000KT 10SM CLR 00/00 A3000 RMK AO2 {rem_tgroup}",
        )
    )
    assert obs is not None, f"{icao}: parser returned None"
    assert obs["temp_c"] == temp_c, f"{icao}: temp_c mismatch"
    assert obs["temp_f"] == expected_temp_f, (
        f"{icao}: expected integer-°F {expected_temp_f}, got {obs['temp_f']!r}"
    )
    assert isinstance(obs["temp_f"], float)
    assert obs["temp_f"].is_integer(), f"{icao}: temp_f is not integer-valued"
    assert obs["temp_f"] == int(obs["temp_f"]), f"{icao}: float != int round-trip"


# ---------------------------------------------------------------------------
# Test G — Round-trip invariant: for any GHCNh row with T-group in REM,
# round(temp_c * 9 / 5 + 32) must equal int(temp_f). Schema promise.
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("temperature", "rem_tgroup"),
    [
        ("26.7", "T02670111"),
        ("-3.9", "T10390061"),
        ("0.0", "T00000000"),
        ("28.9", "T02890172"),
        ("36.7", "T03670089"),
        ("-17.8", "T11780000"),  # 0°F
    ],
)
def test_ghcnh_tgroup_round_trip_invariant(temperature: str, rem_tgroup: str) -> None:
    """Test G: round(temp_c * 9/5 + 32) == int(temp_f) for every GHCNh T-group row."""
    obs = parse_ghcnh_row(
        _make_row(
            temperature=temperature,
            REM=f"METAR KJFK 010151Z 00000KT 10SM CLR M00/M00 A3000 RMK AO2 {rem_tgroup}",
        )
    )
    assert obs is not None
    if obs["temp_c"] is None:
        return  # out-of-bounds; skip round-trip check
    assert obs["temp_f"] is not None
    expected_int_f = round(obs["temp_c"] * 9 / 5 + 32)
    assert int(obs["temp_f"]) == expected_int_f, (
        f"schema round-trip violated: temp_c={obs['temp_c']} expected "
        f"int_f={expected_int_f}, got temp_f={obs['temp_f']!r}"
    )
    assert obs["temp_f"].is_integer()


# ---------------------------------------------------------------------------
# Test H — Dewpoint T-group recovery (independent of temp).
# When the T-group specifies a dewpoint that rounds to a different integer °F
# than celsius_to_fahrenheit, we verify the dewpoint path uses recovery too.
# ---------------------------------------------------------------------------
def test_ghcnh_dewpoint_tgroup_recovery() -> None:
    """Test H: Dewpoint position in T-group also gets integer-°F recovery."""
    # T02670139: temp=26.7°C (80°F), dewp=13.9°C → round(13.9*9/5+32) = round(57.02) = 57
    obs = parse_ghcnh_row(
        _make_row(
            temperature="26.7",
            dew_point_temperature="13.9",
            REM="METAR KJFK 010151Z 00000KT 10SM CLR 27/14 A3000 RMK AO2 T02670139",
        )
    )
    assert obs is not None
    assert obs["temp_c"] == 26.7
    assert obs["dewpoint_c"] == 13.9
    assert obs["temp_f"] == 80.0
    assert obs["temp_f"].is_integer()
    assert obs["dewpoint_f"] == 57.0, f"expected 57.0, got {obs['dewpoint_f']!r}"
    assert obs["dewpoint_f"].is_integer()

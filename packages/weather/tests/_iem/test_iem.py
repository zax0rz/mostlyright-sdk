"""Tests for IEM METAR CSV parser.

TDD: tests written first, implementation follows.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from jsonschema import validate
from tradewinds._internal._capabilities import SPECS_DIR as _SPECS_DIR
from tradewinds._internal._convert import fahrenheit_to_celsius

FIXTURES = Path(__file__).parent / "fixtures"
SCHEMA_PATH = _SPECS_DIR / "observation.json"


def _load_schema() -> dict[str, Any]:
    return json.loads(SCHEMA_PATH.read_text())


def _make_row(**overrides: str) -> dict[str, str]:
    """Create a minimal valid IEM CSV row dict (as csv.DictReader produces)."""
    base: dict[str, str] = {
        "station": "JFK",
        "valid": "2025-01-01 00:51",
        "tmpf": "50.00",
        "dwpf": "43.00",
        "relh": "76.76",
        "drct": "90.00",
        "sknt": "14.00",
        "p01i": "0.00",
        "alti": "29.68",
        "mslp": "1004.90",
        "vsby": "10.00",
        "gust": "25.00",
        "skyc1": "SCT",
        "skyc2": "SCT",
        "skyc3": "BKN",
        "skyc4": "BKN",
        "skyl1": "4900.00",
        "skyl2": "10000.00",
        "skyl3": "15000.00",
        "skyl4": "25000.00",
        "wxcodes": "M",
        "ice_accretion_1hr": "M",
        "ice_accretion_3hr": "M",
        "ice_accretion_6hr": "M",
        "peak_wind_gust": "M",
        "peak_wind_drct": "M",
        "peak_wind_time": "M",
        "feel": "50.00",
        "metar": "KJFK 010051Z 09014G25KT 10SM SCT049 SCT100 BKN150 BKN250 10/06 A2968 RMK AO2 SLP049 T01000061",
        "snowdepth": "M",
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# fahrenheit_to_celsius
# ---------------------------------------------------------------------------
class TestFahrenheitToCelsius:
    def test_32f_is_0c(self):
        assert fahrenheit_to_celsius(32.0) == 0.0

    def test_212f_is_100c(self):
        assert fahrenheit_to_celsius(212.0) == 100.0

    def test_none_returns_none(self):
        assert fahrenheit_to_celsius(None) is None

    def test_no_rounding(self):
        """72°F should give 22.222... not a rounded value."""
        result = fahrenheit_to_celsius(72.0)
        assert result is not None
        assert abs(result - 22.222222222222221) < 1e-10

    def test_negative_temp(self):
        """-40°F = -40°C (the crossover point)."""
        assert fahrenheit_to_celsius(-40.0) == pytest.approx(-40.0)

    def test_inf_returns_none(self):
        assert fahrenheit_to_celsius(float("inf")) is None

    def test_nan_returns_none(self):
        assert fahrenheit_to_celsius(float("nan")) is None


# ---------------------------------------------------------------------------
# iem_to_observation — basic
# ---------------------------------------------------------------------------
class TestIemToObservation:
    def test_basic_valid_row(self):
        from tradewinds.weather._iem import iem_to_observation

        obs = iem_to_observation(_make_row())
        assert obs is not None
        assert obs["station_code"] == "JFK"
        assert obs["source"] == "iem"

    def test_all_30_fields_present(self):
        from tradewinds.weather._iem import iem_to_observation

        obs = iem_to_observation(_make_row())
        assert obs is not None
        assert len(obs) == 30

    def test_schema_validation(self):
        from tradewinds.weather._iem import iem_to_observation

        schema = _load_schema()
        obs = iem_to_observation(_make_row())
        assert obs is not None
        validate(instance=obs, schema=schema)

    def test_correct_field_names(self):
        from tradewinds.weather._iem import iem_to_observation

        schema = _load_schema()
        obs = iem_to_observation(_make_row())
        assert obs is not None
        expected_keys = set(schema["properties"].keys())
        assert set(obs.keys()) == expected_keys

    def test_source_always_iem(self):
        from tradewinds.weather._iem import iem_to_observation

        obs = iem_to_observation(_make_row())
        assert obs is not None
        assert obs["source"] == "iem"

    def test_qc_field_always_none(self):
        from tradewinds.weather._iem import iem_to_observation

        obs = iem_to_observation(_make_row())
        assert obs is not None
        assert obs["qc_field"] is None


# ---------------------------------------------------------------------------
# Station code
# ---------------------------------------------------------------------------
class TestStationCode:
    def test_bare_3letter(self):
        from tradewinds.weather._iem import iem_to_observation

        obs = iem_to_observation(_make_row(station="JFK"))
        assert obs is not None
        assert obs["station_code"] == "JFK"

    def test_icao_4letter(self):
        from tradewinds.weather._iem import iem_to_observation

        obs = iem_to_observation(_make_row(station="KJFK"))
        assert obs is not None
        assert obs["station_code"] == "JFK"

    def test_invalid_station(self):
        from tradewinds.weather._iem import iem_to_observation

        assert iem_to_observation(_make_row(station="12345")) is None

    def test_empty_station(self):
        from tradewinds.weather._iem import iem_to_observation

        assert iem_to_observation(_make_row(station="")) is None

    def test_m_station(self):
        from tradewinds.weather._iem import iem_to_observation

        assert iem_to_observation(_make_row(station="M")) is None


# ---------------------------------------------------------------------------
# Missing values ("M")
# ---------------------------------------------------------------------------
class TestMissingValues:
    def test_m_temp_is_none(self):
        from tradewinds.weather._iem import iem_to_observation

        obs = iem_to_observation(_make_row(tmpf="M"))
        assert obs is not None
        assert obs["temp_f"] is None
        assert obs["temp_c"] is None

    def test_m_dewpoint_is_none(self):
        from tradewinds.weather._iem import iem_to_observation

        obs = iem_to_observation(_make_row(dwpf="M"))
        assert obs is not None
        assert obs["dewpoint_f"] is None
        assert obs["dewpoint_c"] is None

    def test_m_wind_is_none(self):
        from tradewinds.weather._iem import iem_to_observation

        obs = iem_to_observation(_make_row(drct="M", sknt="M", gust="M"))
        assert obs is not None
        assert obs["wind_dir_degrees"] is None
        assert obs["wind_speed_kt"] is None
        assert obs["wind_gust_kt"] is None

    def test_m_pressure_is_none(self):
        from tradewinds.weather._iem import iem_to_observation

        obs = iem_to_observation(_make_row(alti="M", mslp="M"))
        assert obs is not None
        assert obs["altimeter_inhg"] is None
        assert obs["sea_level_pressure_mb"] is None

    def test_m_visibility_is_none(self):
        from tradewinds.weather._iem import iem_to_observation

        obs = iem_to_observation(_make_row(vsby="M"))
        assert obs is not None
        assert obs["visibility_miles"] is None

    def test_m_wxcodes_is_none(self):
        from tradewinds.weather._iem import iem_to_observation

        obs = iem_to_observation(_make_row(wxcodes="M"))
        assert obs is not None
        assert obs["weather_codes"] is None

    def test_m_snow_is_none(self):
        from tradewinds.weather._iem import iem_to_observation

        obs = iem_to_observation(_make_row(snowdepth="M"))
        assert obs is not None
        assert obs["snow_depth_inches"] is None

    def test_all_key_vars_m_returns_none(self):
        """If temp, dewpoint, wind_speed, AND SLP are all M → skip row."""
        from tradewinds.weather._iem import iem_to_observation

        obs = iem_to_observation(_make_row(tmpf="M", dwpf="M", sknt="M", mslp="M"))
        assert obs is None


# ---------------------------------------------------------------------------
# Trace precipitation
# ---------------------------------------------------------------------------
class TestTracePrecip:
    def test_trace_is_zero(self):
        from tradewinds.weather._iem import iem_to_observation

        obs = iem_to_observation(_make_row(p01i="T"))
        assert obs is not None
        assert obs["precip_1hr_inches"] == 0.0

    def test_numeric_precip_passthrough(self):
        from tradewinds.weather._iem import iem_to_observation

        obs = iem_to_observation(_make_row(p01i="0.14"))
        assert obs is not None
        assert obs["precip_1hr_inches"] == pytest.approx(0.14)

    def test_m_precip_is_none(self):
        from tradewinds.weather._iem import iem_to_observation

        obs = iem_to_observation(_make_row(p01i="M"))
        assert obs is not None
        assert obs["precip_1hr_inches"] is None


# ---------------------------------------------------------------------------
# Timestamp parsing
# ---------------------------------------------------------------------------
class TestTimestamp:
    def test_basic_parse(self):
        from tradewinds.weather._iem import iem_to_observation

        obs = iem_to_observation(_make_row(valid="2025-01-01 00:51"))
        assert obs is not None
        assert obs["observed_at"] == "2025-01-01T00:51:00Z"

    def test_midnight(self):
        from tradewinds.weather._iem import iem_to_observation

        obs = iem_to_observation(_make_row(valid="2025-01-01 00:00"))
        assert obs is not None
        assert obs["observed_at"] == "2025-01-01T00:00:00Z"

    def test_bad_format_returns_none(self):
        from tradewinds.weather._iem import iem_to_observation

        assert iem_to_observation(_make_row(valid="not-a-date")) is None

    def test_empty_timestamp_returns_none(self):
        from tradewinds.weather._iem import iem_to_observation

        assert iem_to_observation(_make_row(valid="")) is None

    def test_m_timestamp_returns_none(self):
        from tradewinds.weather._iem import iem_to_observation

        assert iem_to_observation(_make_row(valid="M")) is None

    def test_year_too_old(self):
        from tradewinds.weather._iem import iem_to_observation

        assert iem_to_observation(_make_row(valid="1900-01-01 00:00")) is None

    def test_year_too_future(self):
        from tradewinds.weather._iem import iem_to_observation

        assert iem_to_observation(_make_row(valid="2200-01-01 00:00")) is None


# ---------------------------------------------------------------------------
# Observation type detection
# ---------------------------------------------------------------------------
class TestObservationType:
    def test_speci_detected_from_metar_text(self):
        from tradewinds.weather._iem import iem_to_observation

        metar = "SPECI KJFK 010232Z 10017G26KT 7SM TSRA SCT033CB"
        obs = iem_to_observation(_make_row(metar=metar))
        assert obs is not None
        assert obs["observation_type"] == "SPECI"

    def test_default_metar(self):
        from tradewinds.weather._iem import iem_to_observation

        obs = iem_to_observation(_make_row())
        assert obs is not None
        assert obs["observation_type"] == "METAR"

    def test_metar_prefix(self):
        from tradewinds.weather._iem import iem_to_observation

        metar = "METAR KJFK 010000Z AUTO 09014KT 10SM"
        obs = iem_to_observation(_make_row(metar=metar))
        assert obs is not None
        assert obs["observation_type"] == "METAR"

    def test_empty_metar_defaults_metar(self):
        from tradewinds.weather._iem import iem_to_observation

        obs = iem_to_observation(_make_row(metar="M"))
        assert obs is not None
        assert obs["observation_type"] == "METAR"

    def test_observation_type_override(self):
        """When caller knows the type (from IEM report_type param), override wins."""
        from tradewinds.weather._iem import iem_to_observation

        # Raw METAR text has no SPECI prefix (IEM strips it), but caller says SPECI
        obs = iem_to_observation(
            _make_row(metar="KJFK 010232Z 10017G26KT 7SM TSRA SCT033CB"),
            observation_type_override="SPECI",
        )
        assert obs is not None
        assert obs["observation_type"] == "SPECI"

    def test_override_metar_explicit(self):
        from tradewinds.weather._iem import iem_to_observation

        obs = iem_to_observation(_make_row(), observation_type_override="METAR")
        assert obs is not None
        assert obs["observation_type"] == "METAR"

    def test_override_none_falls_back_to_detection(self):
        """When override is None, fall back to text detection."""
        from tradewinds.weather._iem import iem_to_observation

        obs = iem_to_observation(_make_row(), observation_type_override=None)
        assert obs is not None
        assert obs["observation_type"] == "METAR"


class TestParseIemFileObsType:
    """parse_iem_file passes observation_type_override through to each row."""

    def test_override_applied_to_all_rows(self, tmp_path: Path) -> None:
        from tradewinds.weather._iem import parse_iem_file

        csv_content = (
            "#DEBUG: comment\n"
            "station,valid,tmpf,dwpf,relh,drct,sknt,p01i,alti,mslp,vsby,gust,"
            "skyc1,skyc2,skyc3,skyc4,skyl1,skyl2,skyl3,skyl4,wxcodes,"
            "ice_accretion_1hr,ice_accretion_3hr,ice_accretion_6hr,"
            "peak_wind_gust,peak_wind_drct,peak_wind_time,feel,metar,snowdepth\n"
            "JFK,2025-01-01 00:51,50.00,43.00,76.76,90.00,14.00,0.00,29.68,"
            "1004.90,10.00,M,SCT,M,M,M,4900.00,M,M,M,M,M,M,M,M,M,M,50.00,"
            "KJFK 010051Z 09014KT 10SM SCT049 10/06 A2968,M\n"
            "JFK,2025-01-01 01:51,48.00,42.00,79.00,100.00,12.00,0.00,29.70,"
            "1005.10,10.00,M,FEW,M,M,M,3000.00,M,M,M,M,M,M,M,M,M,M,48.00,"
            "KJFK 010151Z 10012KT 10SM FEW030 09/06 A2970,M\n"
        )
        f = tmp_path / "speci.csv"
        f.write_text(csv_content)

        results = parse_iem_file(f, observation_type_override="SPECI")
        assert len(results) == 2
        assert all(r["observation_type"] == "SPECI" for r in results)

    def test_no_override_uses_detection(self, tmp_path: Path) -> None:
        from tradewinds.weather._iem import parse_iem_file

        csv_content = (
            "station,valid,tmpf,dwpf,relh,drct,sknt,p01i,alti,mslp,vsby,gust,"
            "skyc1,skyc2,skyc3,skyc4,skyl1,skyl2,skyl3,skyl4,wxcodes,"
            "ice_accretion_1hr,ice_accretion_3hr,ice_accretion_6hr,"
            "peak_wind_gust,peak_wind_drct,peak_wind_time,feel,metar,snowdepth\n"
            "JFK,2025-01-01 00:51,50.00,43.00,76.76,90.00,14.00,0.00,29.68,"
            "1004.90,10.00,M,SCT,M,M,M,4900.00,M,M,M,M,M,M,M,M,M,M,50.00,"
            "KJFK 010051Z 09014KT 10SM SCT049 10/06 A2968,M\n"
        )
        f = tmp_path / "metar.csv"
        f.write_text(csv_content)

        results = parse_iem_file(f)
        assert len(results) == 1
        assert results[0]["observation_type"] == "METAR"


# ---------------------------------------------------------------------------
# Unit conversions
# ---------------------------------------------------------------------------
class TestUnitConversions:
    def test_temp_f_direct(self):
        from tradewinds.weather._iem import iem_to_observation

        obs = iem_to_observation(_make_row(tmpf="50.00"))
        assert obs is not None
        assert obs["temp_f"] == 50.0

    def test_temp_c_converted(self):
        """50°F → 10°C exactly."""
        from tradewinds.weather._iem import iem_to_observation

        obs = iem_to_observation(_make_row(tmpf="50.00"))
        assert obs is not None
        assert obs["temp_c"] == 10.0

    def test_temp_no_rounding(self):
        """49°F → (49-32)*5/9 = 9.4444... not rounded."""
        from tradewinds.weather._iem import iem_to_observation

        obs = iem_to_observation(_make_row(tmpf="49.00"))
        assert obs is not None
        assert abs(obs["temp_c"] - 9.444444444444445) < 1e-10

    def test_tgroup_precision(self):
        """46.4°F (T-group) → 8.0°C exactly."""
        from tradewinds.weather._iem import iem_to_observation

        obs = iem_to_observation(_make_row(tmpf="46.40"))
        assert obs is not None
        assert obs["temp_f"] == 46.4
        assert obs["temp_c"] == 8.0

    def test_dewpoint_conversion(self):
        from tradewinds.weather._iem import iem_to_observation

        obs = iem_to_observation(_make_row(dwpf="43.00"))
        assert obs is not None
        assert obs["dewpoint_f"] == 43.0
        assert obs["dewpoint_c"] is not None
        assert abs(obs["dewpoint_c"] - 6.111111111111111) < 1e-10

    def test_wind_speed_integer(self):
        from tradewinds.weather._iem import iem_to_observation

        obs = iem_to_observation(_make_row(sknt="14.00"))
        assert obs is not None
        assert obs["wind_speed_kt"] == 14
        assert isinstance(obs["wind_speed_kt"], int)

    def test_wind_dir_integer(self):
        from tradewinds.weather._iem import iem_to_observation

        obs = iem_to_observation(_make_row(drct="90.00"))
        assert obs is not None
        assert obs["wind_dir_degrees"] == 90
        assert isinstance(obs["wind_dir_degrees"], int)

    def test_gust_integer(self):
        from tradewinds.weather._iem import iem_to_observation

        obs = iem_to_observation(_make_row(gust="25.00"))
        assert obs is not None
        assert obs["wind_gust_kt"] == 25
        assert isinstance(obs["wind_gust_kt"], int)

    def test_altimeter_direct(self):
        from tradewinds.weather._iem import iem_to_observation

        obs = iem_to_observation(_make_row(alti="29.68"))
        assert obs is not None
        assert obs["altimeter_inhg"] == 29.68

    def test_slp_direct(self):
        from tradewinds.weather._iem import iem_to_observation

        obs = iem_to_observation(_make_row(mslp="1004.90"))
        assert obs is not None
        assert obs["sea_level_pressure_mb"] == 1004.9

    def test_visibility_direct(self):
        from tradewinds.weather._iem import iem_to_observation

        obs = iem_to_observation(_make_row(vsby="10.00"))
        assert obs is not None
        assert obs["visibility_miles"] == 10.0

    def test_snow_direct(self):
        from tradewinds.weather._iem import iem_to_observation

        obs = iem_to_observation(_make_row(snowdepth="5.00"))
        assert obs is not None
        assert obs["snow_depth_inches"] == 5.0


# ---------------------------------------------------------------------------
# Bounds validation
# ---------------------------------------------------------------------------
class TestBounds:
    def test_slp_below_range(self):
        from tradewinds.weather._iem import iem_to_observation

        obs = iem_to_observation(_make_row(mslp="800.00"))
        assert obs is not None
        assert obs["sea_level_pressure_mb"] is None

    def test_slp_above_range(self):
        from tradewinds.weather._iem import iem_to_observation

        obs = iem_to_observation(_make_row(mslp="1100.00"))
        assert obs is not None
        assert obs["sea_level_pressure_mb"] is None

    def test_slp_at_min(self):
        from tradewinds.weather._iem import iem_to_observation

        obs = iem_to_observation(_make_row(mslp="870.00"))
        assert obs is not None
        assert obs["sea_level_pressure_mb"] == 870.0

    def test_slp_at_max(self):
        from tradewinds.weather._iem import iem_to_observation

        obs = iem_to_observation(_make_row(mslp="1084.00"))
        assert obs is not None
        assert obs["sea_level_pressure_mb"] == 1084.0

    def test_negative_wind_speed(self):
        from tradewinds.weather._iem import iem_to_observation

        obs = iem_to_observation(_make_row(sknt="-5"))
        assert obs is not None
        assert obs["wind_speed_kt"] is None

    def test_excessive_wind_speed(self):
        from tradewinds.weather._iem import iem_to_observation

        obs = iem_to_observation(_make_row(sknt="999"))
        assert obs is not None
        assert obs["wind_speed_kt"] is None

    def test_excessive_gust(self):
        from tradewinds.weather._iem import iem_to_observation

        obs = iem_to_observation(_make_row(gust="999"))
        assert obs is not None
        assert obs["wind_gust_kt"] is None

    def test_negative_visibility(self):
        from tradewinds.weather._iem import iem_to_observation

        obs = iem_to_observation(_make_row(vsby="-1.00"))
        assert obs is not None
        assert obs["visibility_miles"] is None

    def test_visibility_capped(self):
        from tradewinds.weather._iem import iem_to_observation

        obs = iem_to_observation(_make_row(vsby="150.00"))
        assert obs is not None
        assert obs["visibility_miles"] == 99.99

    def test_negative_precip(self):
        from tradewinds.weather._iem import iem_to_observation

        obs = iem_to_observation(_make_row(p01i="-0.01"))
        assert obs is not None
        assert obs["precip_1hr_inches"] is None

    def test_negative_snow(self):
        from tradewinds.weather._iem import iem_to_observation

        obs = iem_to_observation(_make_row(snowdepth="-1.00"))
        assert obs is not None
        assert obs["snow_depth_inches"] is None

    def test_wind_dir_out_of_range(self):
        from tradewinds.weather._iem import iem_to_observation

        obs = iem_to_observation(_make_row(drct="400"))
        assert obs is not None
        assert obs["wind_dir_degrees"] is None

    def test_sky_base_out_of_range(self):
        from tradewinds.weather._iem import iem_to_observation

        obs = iem_to_observation(_make_row(skyl1="99999"))
        assert obs is not None
        assert obs["sky_base_1_ft"] is None

    def test_sky_base_negative(self):
        from tradewinds.weather._iem import iem_to_observation

        obs = iem_to_observation(_make_row(skyl1="-100"))
        assert obs is not None
        assert obs["sky_base_1_ft"] is None


# ---------------------------------------------------------------------------
# Sky cover
# ---------------------------------------------------------------------------
class TestSkyCover:
    def test_cover_mapping(self):
        from tradewinds.weather._iem import iem_to_observation

        obs = iem_to_observation(_make_row(skyc1="SCT", skyc2="BKN", skyc3="OVC"))
        assert obs is not None
        assert obs["sky_cover_1"] == "SCT"
        assert obs["sky_cover_2"] == "BKN"
        assert obs["sky_cover_3"] == "OVC"

    def test_base_heights_integer(self):
        from tradewinds.weather._iem import iem_to_observation

        obs = iem_to_observation(_make_row(skyl1="4900.00", skyl2="10000.00"))
        assert obs is not None
        assert obs["sky_base_1_ft"] == 4900
        assert isinstance(obs["sky_base_1_ft"], int)
        assert obs["sky_base_2_ft"] == 10000

    def test_m_cover_is_none(self):
        from tradewinds.weather._iem import iem_to_observation

        obs = iem_to_observation(_make_row(skyc1="M", skyl1="M"))
        assert obs is not None
        assert obs["sky_cover_1"] is None
        assert obs["sky_base_1_ft"] is None

    def test_few_cover(self):
        from tradewinds.weather._iem import iem_to_observation

        obs = iem_to_observation(_make_row(skyc1="FEW"))
        assert obs is not None
        assert obs["sky_cover_1"] == "FEW"

    def test_clr_cover(self):
        from tradewinds.weather._iem import iem_to_observation

        obs = iem_to_observation(_make_row(skyc1="CLR"))
        assert obs is not None
        assert obs["sky_cover_1"] == "CLR"

    def test_vv_cover(self):
        from tradewinds.weather._iem import iem_to_observation

        obs = iem_to_observation(_make_row(skyc1="VV"))
        assert obs is not None
        assert obs["sky_cover_1"] == "VV"


# ---------------------------------------------------------------------------
# Peak wind
# ---------------------------------------------------------------------------
class TestPeakWind:
    def test_peak_wind_fields(self):
        from tradewinds.weather._iem import iem_to_observation

        obs = iem_to_observation(
            _make_row(
                peak_wind_gust="28.00",
                peak_wind_drct="90.00",
                peak_wind_time="2025-01-01 01:31",
            )
        )
        assert obs is not None
        assert obs["peak_wind_gust_kt"] == 28
        assert obs["peak_wind_dir"] == 90
        assert obs["peak_wind_time"] == "0131"

    def test_peak_wind_time_format(self):
        from tradewinds.weather._iem import iem_to_observation

        obs = iem_to_observation(_make_row(peak_wind_time="2025-01-01 02:19"))
        assert obs is not None
        assert obs["peak_wind_time"] == "0219"

    def test_m_peak_wind(self):
        from tradewinds.weather._iem import iem_to_observation

        obs = iem_to_observation(
            _make_row(
                peak_wind_gust="M",
                peak_wind_drct="M",
                peak_wind_time="M",
            )
        )
        assert obs is not None
        assert obs["peak_wind_gust_kt"] is None
        assert obs["peak_wind_dir"] is None
        assert obs["peak_wind_time"] is None

    def test_peak_gust_bounded(self):
        from tradewinds.weather._iem import iem_to_observation

        obs = iem_to_observation(_make_row(peak_wind_gust="999"))
        assert obs is not None
        assert obs["peak_wind_gust_kt"] is None

    def test_peak_dir_bounded(self):
        from tradewinds.weather._iem import iem_to_observation

        obs = iem_to_observation(_make_row(peak_wind_drct="400"))
        assert obs is not None
        assert obs["peak_wind_dir"] is None


# ---------------------------------------------------------------------------
# Weather codes
# ---------------------------------------------------------------------------
class TestWeatherCodes:
    def test_passthrough(self):
        from tradewinds.weather._iem import iem_to_observation

        obs = iem_to_observation(_make_row(wxcodes="TSRA"))
        assert obs is not None
        assert obs["weather_codes"] == "TSRA"

    def test_multiple_codes(self):
        from tradewinds.weather._iem import iem_to_observation

        obs = iem_to_observation(_make_row(wxcodes="+TSRA BR"))
        assert obs is not None
        assert obs["weather_codes"] == "+TSRA BR"

    def test_m_is_none(self):
        from tradewinds.weather._iem import iem_to_observation

        obs = iem_to_observation(_make_row(wxcodes="M"))
        assert obs is not None
        assert obs["weather_codes"] is None

    def test_truncation(self):
        from tradewinds.weather._iem import iem_to_observation

        long_wx = "X" * 300
        obs = iem_to_observation(_make_row(wxcodes=long_wx))
        assert obs is not None
        assert len(obs["weather_codes"]) == 256


# ---------------------------------------------------------------------------
# Raw METAR
# ---------------------------------------------------------------------------
class TestRawMetar:
    def test_passthrough(self):
        from tradewinds.weather._iem import iem_to_observation

        obs = iem_to_observation(_make_row())
        assert obs is not None
        assert obs["raw_metar"] is not None
        assert "KJFK" in obs["raw_metar"]

    def test_m_metar_is_none(self):
        from tradewinds.weather._iem import iem_to_observation

        obs = iem_to_observation(_make_row(metar="M"))
        assert obs is not None
        assert obs["raw_metar"] is None

    def test_truncation(self):
        from tradewinds.weather._iem import iem_to_observation

        long_metar = "KJFK " + "X" * 3000
        obs = iem_to_observation(_make_row(metar=long_metar))
        assert obs is not None
        assert len(obs["raw_metar"]) == 2048


# ---------------------------------------------------------------------------
# parse_iem_file
# ---------------------------------------------------------------------------
class TestParseIemFile:
    def test_reads_fixture(self):
        from tradewinds.weather._iem import parse_iem_file

        fixture = FIXTURES / "iem_jfk_metar_sample.csv"
        if not fixture.exists():
            pytest.skip("IEM fixture not available")
        results = parse_iem_file(fixture)
        assert len(results) > 0

    def test_all_have_30_fields(self):
        from tradewinds.weather._iem import parse_iem_file

        fixture = FIXTURES / "iem_jfk_metar_sample.csv"
        if not fixture.exists():
            pytest.skip("IEM fixture not available")
        results = parse_iem_file(fixture)
        for obs in results:
            assert len(obs) == 30

    def test_all_source_iem(self):
        from tradewinds.weather._iem import parse_iem_file

        fixture = FIXTURES / "iem_jfk_metar_sample.csv"
        if not fixture.exists():
            pytest.skip("IEM fixture not available")
        results = parse_iem_file(fixture)
        for obs in results:
            assert obs["source"] == "iem"

    def test_schema_validation_all_rows(self):
        from tradewinds.weather._iem import parse_iem_file

        fixture = FIXTURES / "iem_jfk_metar_sample.csv"
        if not fixture.exists():
            pytest.skip("IEM fixture not available")
        schema = _load_schema()
        results = parse_iem_file(fixture)
        for obs in results:
            validate(instance=obs, schema=schema)

    def test_skips_comment_lines(self, tmp_path: Path):
        from tradewinds.weather._iem import parse_iem_file

        csv_content = (
            "#DEBUG: this is a comment\n"
            "#DEBUG: another comment\n"
            "station,valid,tmpf,dwpf,relh,drct,sknt,p01i,alti,mslp,vsby,gust,"
            "skyc1,skyc2,skyc3,skyc4,skyl1,skyl2,skyl3,skyl4,wxcodes,"
            "ice_accretion_1hr,ice_accretion_3hr,ice_accretion_6hr,"
            "peak_wind_gust,peak_wind_drct,peak_wind_time,feel,metar,snowdepth\n"
            "JFK,2025-01-01 00:51,50.00,43.00,76.76,90.00,14.00,0.00,29.68,"
            "1004.90,10.00,25.00,SCT,SCT,BKN,BKN,4900.00,10000.00,15000.00,"
            "25000.00,M,M,M,M,M,M,M,50.00,KJFK 010051Z 09014G25KT,M\n"
        )
        f = tmp_path / "test.csv"
        f.write_text(csv_content)
        results = parse_iem_file(f)
        assert len(results) == 1

    def test_empty_file(self, tmp_path: Path):
        from tradewinds.weather._iem import parse_iem_file

        f = tmp_path / "empty.csv"
        f.write_text("#DEBUG: comments only\n")
        results = parse_iem_file(f)
        assert len(results) == 0

    def test_fixture_station_codes_valid(self):
        """Every parsed row should have a valid 3-4 letter station code."""
        import re

        from tradewinds.weather._iem import parse_iem_file

        fixture = FIXTURES / "iem_jfk_metar_sample.csv"
        if not fixture.exists():
            pytest.skip("IEM fixture not available")
        results = parse_iem_file(fixture)
        pattern = re.compile(r"^[A-Z]{3,4}$")
        for obs in results:
            assert pattern.match(obs["station_code"])


# ---------------------------------------------------------------------------
# Temperature bounds
# ---------------------------------------------------------------------------
class TestTempBounds:
    def test_extreme_hot_temp_is_none(self):
        """500°F (260°C) is well above the 60°C max. Both °C and °F are None."""
        from tradewinds.weather._iem import iem_to_observation

        obs = iem_to_observation(_make_row(tmpf="500.00"))
        assert obs is not None
        assert obs["temp_c"] is None
        assert obs["temp_f"] is None

    def test_extreme_cold_temp_is_none(self):
        """-200°F (-128.9°C) is below the -90°C min."""
        from tradewinds.weather._iem import iem_to_observation

        obs = iem_to_observation(_make_row(tmpf="-200.00"))
        assert obs is not None
        assert obs["temp_c"] is None

    def test_extreme_dewpoint_is_none(self):
        from tradewinds.weather._iem import iem_to_observation

        obs = iem_to_observation(_make_row(dwpf="500.00"))
        assert obs is not None
        assert obs["dewpoint_c"] is None

    def test_valid_temp_within_bounds(self):
        from tradewinds.weather._iem import iem_to_observation

        obs = iem_to_observation(_make_row(tmpf="72.00"))
        assert obs is not None
        assert obs["temp_c"] is not None

    def test_cold_but_within_bounds(self):
        """-40°F = -40°C, within [-90, 60]."""
        from tradewinds.weather._iem import iem_to_observation

        obs = iem_to_observation(_make_row(tmpf="-40.00"))
        assert obs is not None
        assert obs["temp_c"] == pytest.approx(-40.0)

    def test_extreme_dewpoint_f_also_none(self):
        """When dewpoint_c is bounded to None, dewpoint_f is also None (consistency)."""
        from tradewinds.weather._iem import iem_to_observation

        obs = iem_to_observation(_make_row(dwpf="500.00"))
        assert obs is not None
        assert obs["dewpoint_c"] is None
        assert obs["dewpoint_f"] is None

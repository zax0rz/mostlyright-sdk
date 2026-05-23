"""Tests for GHCNh PSV parser.

TDD: tests written first, implementation follows.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from jsonschema import validate
from tradewinds._internal._capabilities import SPECS_DIR as _SPECS_DIR

FIXTURES = Path(__file__).parent / "fixtures"
SCHEMA_PATH = _SPECS_DIR / "observation.json"


def _load_schema() -> dict[str, Any]:
    return json.loads(SCHEMA_PATH.read_text())


def _make_row(**overrides: str) -> dict[str, str]:
    """Create a minimal valid GHCNh PSV row dict (as csv.DictReader produces)."""
    base: dict[str, str] = {
        "STATION": "USW00094789",
        "Station_name": "JFK INTL AP",
        "DATE": "2025-01-15T12:00:00",
        "temperature": "5.0",
        "temperature_Quality_Code": "1",
        "temperature_Report_Type": "FM15",
        "temperature_Source_Station_ID": "ICAO-KJFK",
        "dew_point_temperature": "2.0",
        "dew_point_temperature_Quality_Code": "1",
        "dew_point_temperature_Source_Station_ID": "ICAO-KJFK",
        "sea_level_pressure": "1013.2",
        "sea_level_pressure_Quality_Code": "1",
        "wind_direction": "270",
        "wind_direction_Quality_Code": "1",
        "wind_speed": "5.1",
        "wind_speed_Quality_Code": "1",
        "wind_gust": "",
        "wind_gust_Quality_Code": "",
        "altimeter": "1013.0",
        "altimeter_Quality_Code": "1",
        "visibility": "16.093",
        "visibility_Quality_Code": "1",
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
        "REM": "",
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# ghcnh_station_to_code
# ---------------------------------------------------------------------------


class TestGhcnhStationToCode:
    def test_icao_kjfk(self):
        from tradewinds.weather._ghcnh import ghcnh_station_to_code

        assert ghcnh_station_to_code("ICAO-KJFK") == "JFK"

    def test_icao_katl(self):
        from tradewinds.weather._ghcnh import ghcnh_station_to_code

        assert ghcnh_station_to_code("ICAO-KATL") == "ATL"

    def test_icao_ksfo(self):
        from tradewinds.weather._ghcnh import ghcnh_station_to_code

        assert ghcnh_station_to_code("ICAO-KSFO") == "SFO"

    def test_icao_three_letter(self):
        from tradewinds.weather._ghcnh import ghcnh_station_to_code

        assert ghcnh_station_to_code("ICAO-DEN") == "DEN"

    def test_wmo_format_returns_none(self):
        from tradewinds.weather._ghcnh import ghcnh_station_to_code

        assert ghcnh_station_to_code("744860-94789") is None

    def test_empty_returns_none(self):
        from tradewinds.weather._ghcnh import ghcnh_station_to_code

        assert ghcnh_station_to_code("") is None

    def test_malformed_icao_returns_none(self):
        from tradewinds.weather._ghcnh import ghcnh_station_to_code

        assert ghcnh_station_to_code("ICAO-K1") is None

    def test_path_traversal_returns_none(self):
        from tradewinds.weather._ghcnh import ghcnh_station_to_code

        assert ghcnh_station_to_code("ICAO-../etc") is None
        assert ghcnh_station_to_code("ICAO-K../X") is None


# ---------------------------------------------------------------------------
# parse_ghcnh_row — basic structure
# ---------------------------------------------------------------------------


class TestParseGhcnhRow:
    def test_basic_valid_row_returns_dict(self):
        from tradewinds.weather._ghcnh import parse_ghcnh_row

        obs = parse_ghcnh_row(_make_row())
        assert obs is not None
        assert isinstance(obs, dict)

    def test_exactly_30_fields(self):
        from tradewinds.weather._ghcnh import parse_ghcnh_row

        obs = parse_ghcnh_row(_make_row())
        assert obs is not None
        assert len(obs) == 30

    def test_validates_against_schema(self):
        from tradewinds.weather._ghcnh import parse_ghcnh_row

        obs = parse_ghcnh_row(_make_row())
        assert obs is not None
        schema = _load_schema()
        validate(instance=obs, schema=schema)

    def test_source_is_ghcnh(self):
        from tradewinds.weather._ghcnh import parse_ghcnh_row

        obs = parse_ghcnh_row(_make_row())
        assert obs is not None
        assert obs["source"] == "ghcnh"

    def test_station_code_jfk(self):
        from tradewinds.weather._ghcnh import parse_ghcnh_row

        obs = parse_ghcnh_row(_make_row())
        assert obs is not None
        assert obs["station_code"] == "JFK"

    def test_observed_at_appends_z(self):
        from tradewinds.weather._ghcnh import parse_ghcnh_row

        obs = parse_ghcnh_row(_make_row(DATE="2025-01-15T12:00:00"))
        assert obs is not None
        assert obs["observed_at"] == "2025-01-15T12:00:00Z"

    def test_observed_at_no_double_z(self):
        from tradewinds.weather._ghcnh import parse_ghcnh_row

        obs = parse_ghcnh_row(_make_row(DATE="2025-01-15T12:00:00Z"))
        assert obs is not None
        assert obs["observed_at"] == "2025-01-15T12:00:00Z"

    def test_report_type_fm15_is_metar(self):
        from tradewinds.weather._ghcnh import parse_ghcnh_row

        obs = parse_ghcnh_row(_make_row(temperature_Report_Type="FM15"))
        assert obs is not None
        assert obs["observation_type"] == "METAR"

    def test_report_type_fm16_is_speci(self):
        from tradewinds.weather._ghcnh import parse_ghcnh_row

        obs = parse_ghcnh_row(_make_row(temperature_Report_Type="FM16"))
        assert obs is not None
        assert obs["observation_type"] == "SPECI"

    def test_report_type_fm12_is_metar(self):
        from tradewinds.weather._ghcnh import parse_ghcnh_row

        obs = parse_ghcnh_row(_make_row(temperature_Report_Type="FM12"))
        assert obs is not None
        assert obs["observation_type"] == "METAR"

    def test_peak_wind_always_none(self):
        from tradewinds.weather._ghcnh import parse_ghcnh_row

        obs = parse_ghcnh_row(_make_row())
        assert obs is not None
        assert obs["peak_wind_gust_kt"] is None
        assert obs["peak_wind_dir"] is None
        assert obs["peak_wind_time"] is None

    def test_qc_field_always_none(self):
        from tradewinds.weather._ghcnh import parse_ghcnh_row

        obs = parse_ghcnh_row(_make_row())
        assert obs is not None
        assert obs["qc_field"] is None

    def test_missing_date_returns_none(self):
        from tradewinds.weather._ghcnh import parse_ghcnh_row

        obs = parse_ghcnh_row(_make_row(DATE=""))
        assert obs is None

    def test_malformed_date_returns_none(self):
        from tradewinds.weather._ghcnh import parse_ghcnh_row

        assert parse_ghcnh_row(_make_row(DATE="../../../etc")) is None
        assert parse_ghcnh_row(_make_row(DATE="not-a-date")) is None

    def test_date_year_out_of_range_returns_none(self):
        from tradewinds.weather._ghcnh import parse_ghcnh_row

        assert parse_ghcnh_row(_make_row(DATE="1800-01-01T00:00:00")) is None
        assert parse_ghcnh_row(_make_row(DATE="9999-12-31T23:59:59")) is None

    def test_no_icao_station_returns_none(self):
        from tradewinds.weather._ghcnh import parse_ghcnh_row

        row = _make_row(temperature_Source_Station_ID="744860-94789")
        row["dew_point_temperature_Source_Station_ID"] = "744860-94789"
        obs = parse_ghcnh_row(row)
        assert obs is None


# ---------------------------------------------------------------------------
# Unit conversions
# ---------------------------------------------------------------------------


class TestUnitConversions:
    def test_temperature_no_rounding(self):
        from tradewinds._internal._convert import celsius_to_fahrenheit
        from tradewinds.weather._ghcnh import parse_ghcnh_row

        obs = parse_ghcnh_row(_make_row(temperature="10.6"))
        assert obs is not None
        assert obs["temp_c"] == 10.6
        assert obs["temp_f"] == celsius_to_fahrenheit(10.6)

    def test_dewpoint_no_rounding(self):
        from tradewinds._internal._convert import celsius_to_fahrenheit
        from tradewinds.weather._ghcnh import parse_ghcnh_row

        obs = parse_ghcnh_row(_make_row(dew_point_temperature="6.7"))
        assert obs is not None
        assert obs["dewpoint_c"] == 6.7
        assert obs["dewpoint_f"] == celsius_to_fahrenheit(6.7)

    def test_wind_speed_ms_to_kt_rounded(self):
        from tradewinds.weather._ghcnh import parse_ghcnh_row

        obs = parse_ghcnh_row(_make_row(wind_speed="7.2"))
        assert obs is not None
        assert obs["wind_speed_kt"] == round(7.2 / 0.514444)
        assert isinstance(obs["wind_speed_kt"], int)

    def test_wind_gust_ms_to_kt_rounded(self):
        from tradewinds.weather._ghcnh import parse_ghcnh_row

        obs = parse_ghcnh_row(_make_row(wind_gust="12.9", wind_gust_Quality_Code="1"))
        assert obs is not None
        assert obs["wind_gust_kt"] == round(12.9 / 0.514444)
        assert isinstance(obs["wind_gust_kt"], int)

    def test_wind_gust_empty_is_none(self):
        from tradewinds.weather._ghcnh import parse_ghcnh_row

        obs = parse_ghcnh_row(_make_row(wind_gust=""))
        assert obs is not None
        assert obs["wind_gust_kt"] is None

    def test_visibility_km_to_miles(self):
        from tradewinds.weather._ghcnh import parse_ghcnh_row

        obs = parse_ghcnh_row(_make_row(visibility="16.093"))
        assert obs is not None
        expected = 16.093 / 1.60934
        assert obs["visibility_miles"] == pytest.approx(expected, rel=1e-6)

    def test_visibility_capped_at_99_99(self):
        from tradewinds.weather._ghcnh import parse_ghcnh_row

        obs = parse_ghcnh_row(_make_row(visibility="200.0"))
        assert obs is not None
        assert obs["visibility_miles"] == 99.99

    def test_negative_visibility_is_none(self):
        from tradewinds.weather._ghcnh import parse_ghcnh_row

        obs = parse_ghcnh_row(_make_row(visibility="-3.0"))
        assert obs is not None
        assert obs["visibility_miles"] is None

    def test_slp_direct_passthrough(self):
        from tradewinds.weather._ghcnh import parse_ghcnh_row

        obs = parse_ghcnh_row(_make_row(sea_level_pressure="1006.9"))
        assert obs is not None
        assert obs["sea_level_pressure_mb"] == 1006.9

    def test_slp_below_870_is_none(self):
        from tradewinds.weather._ghcnh import parse_ghcnh_row

        obs = parse_ghcnh_row(_make_row(sea_level_pressure="800.0"))
        assert obs is not None
        assert obs["sea_level_pressure_mb"] is None

    def test_slp_above_1084_is_none(self):
        from tradewinds.weather._ghcnh import parse_ghcnh_row

        obs = parse_ghcnh_row(_make_row(sea_level_pressure="1100.0"))
        assert obs is not None
        assert obs["sea_level_pressure_mb"] is None

    def test_altimeter_conversion(self):
        from tradewinds._internal._convert import hpa_to_inhg
        from tradewinds.weather._ghcnh import parse_ghcnh_row

        obs = parse_ghcnh_row(_make_row(altimeter="1013.0"))
        assert obs is not None
        assert obs["altimeter_inhg"] == hpa_to_inhg(1013.0)

    def test_precipitation_mm_to_inches(self):
        from tradewinds.weather._ghcnh import parse_ghcnh_row

        obs = parse_ghcnh_row(_make_row(precipitation="4.8", precipitation_Quality_Code="1"))
        assert obs is not None
        expected = 4.8 / 25.4
        assert obs["precip_1hr_inches"] == pytest.approx(expected, rel=1e-6)

    def test_precipitation_trace_is_zero(self):
        from tradewinds.weather._ghcnh import parse_ghcnh_row

        obs = parse_ghcnh_row(
            _make_row(
                precipitation="0.0",
                precipitation_Measurement_Code="T",
                precipitation_Quality_Code="5",
            )
        )
        assert obs is not None
        assert obs["precip_1hr_inches"] == 0.0

    def test_precipitation_empty_is_none(self):
        from tradewinds.weather._ghcnh import parse_ghcnh_row

        obs = parse_ghcnh_row(_make_row(precipitation=""))
        assert obs is not None
        assert obs["precip_1hr_inches"] is None

    def test_snow_depth_cm_to_inches(self):
        from tradewinds.weather._ghcnh import parse_ghcnh_row

        obs = parse_ghcnh_row(_make_row(snow_depth="10.0", snow_depth_Quality_Code="1"))
        assert obs is not None
        expected = 10.0 / 2.54
        assert obs["snow_depth_inches"] == pytest.approx(expected, rel=1e-6)

    def test_snow_depth_empty_is_none(self):
        from tradewinds.weather._ghcnh import parse_ghcnh_row

        obs = parse_ghcnh_row(_make_row(snow_depth=""))
        assert obs is not None
        assert obs["snow_depth_inches"] is None

    def test_negative_wind_speed_is_none(self):
        from tradewinds.weather._ghcnh import parse_ghcnh_row

        obs = parse_ghcnh_row(_make_row(wind_speed="-5.0"))
        assert obs is not None
        assert obs["wind_speed_kt"] is None

    def test_negative_wind_dir_is_none(self):
        from tradewinds.weather._ghcnh import parse_ghcnh_row

        obs = parse_ghcnh_row(_make_row(wind_direction="-10"))
        assert obs is not None
        assert obs["wind_dir_degrees"] is None

    def test_negative_precip_is_none(self):
        from tradewinds.weather._ghcnh import parse_ghcnh_row

        obs = parse_ghcnh_row(_make_row(precipitation="-1.0", precipitation_Quality_Code="1"))
        assert obs is not None
        assert obs["precip_1hr_inches"] is None

    def test_negative_snow_is_none(self):
        from tradewinds.weather._ghcnh import parse_ghcnh_row

        obs = parse_ghcnh_row(_make_row(snow_depth="-5.0", snow_depth_Quality_Code="1"))
        assert obs is not None
        assert obs["snow_depth_inches"] is None

    def test_negative_sky_baseht_is_none(self):
        from tradewinds.weather._ghcnh import parse_ghcnh_row

        obs = parse_ghcnh_row(
            _make_row(
                sky_cover_summation_1="SCT:04;",
                sky_cover_summation_baseht_1="-100",
            )
        )
        assert obs is not None
        assert obs["sky_base_1_ft"] is None

    def test_extreme_sky_baseht_is_none(self):
        from tradewinds.weather._ghcnh import parse_ghcnh_row

        obs = parse_ghcnh_row(
            _make_row(
                sky_cover_summation_1="OVC:08;",
                sky_cover_summation_baseht_1="99999",
            )
        )
        assert obs is not None
        assert obs["sky_base_1_ft"] is None


# ---------------------------------------------------------------------------
# Sky cover parsing
# ---------------------------------------------------------------------------


class TestSkyCover:
    def test_sct_parsed(self):
        from tradewinds.weather._ghcnh import parse_ghcnh_row

        obs = parse_ghcnh_row(_make_row(sky_cover_summation_1="SCT:04;"))
        assert obs is not None
        assert obs["sky_cover_1"] == "SCT"

    def test_bkn_parsed(self):
        from tradewinds.weather._ghcnh import parse_ghcnh_row

        obs = parse_ghcnh_row(_make_row(sky_cover_summation_2="BKN:07;"))
        assert obs is not None
        assert obs["sky_cover_2"] == "BKN"

    def test_ovc_parsed(self):
        from tradewinds.weather._ghcnh import parse_ghcnh_row

        obs = parse_ghcnh_row(_make_row(sky_cover_summation_3="OVC:08;"))
        assert obs is not None
        assert obs["sky_cover_3"] == "OVC"

    def test_clr_parsed(self):
        from tradewinds.weather._ghcnh import parse_ghcnh_row

        obs = parse_ghcnh_row(_make_row(sky_cover_summation_1="CLR:00;"))
        assert obs is not None
        assert obs["sky_cover_1"] == "CLR"

    def test_empty_sky_cover_is_none(self):
        from tradewinds.weather._ghcnh import parse_ghcnh_row

        obs = parse_ghcnh_row(_make_row(sky_cover_summation_1=""))
        assert obs is not None
        assert obs["sky_cover_1"] is None

    def test_baseht_meters_to_feet(self):
        from tradewinds.weather._ghcnh import parse_ghcnh_row

        obs = parse_ghcnh_row(
            _make_row(
                sky_cover_summation_1="SCT:04;",
                sky_cover_summation_baseht_1="1494",
            )
        )
        assert obs is not None
        assert obs["sky_base_1_ft"] == round(1494 * 3.28084)
        assert isinstance(obs["sky_base_1_ft"], int)

    def test_baseht_empty_is_none(self):
        from tradewinds.weather._ghcnh import parse_ghcnh_row

        obs = parse_ghcnh_row(_make_row(sky_cover_summation_baseht_1=""))
        assert obs is not None
        assert obs["sky_base_1_ft"] is None

    def test_all_four_layers(self):
        from tradewinds.weather._ghcnh import parse_ghcnh_row

        obs = parse_ghcnh_row(
            _make_row(
                sky_cover_summation_1="SCT:04;",
                sky_cover_summation_2="SCT:04;",
                sky_cover_summation_3="BKN:07;",
                sky_cover_summation_4="BKN:07;",
                sky_cover_summation_baseht_1="1494",
                sky_cover_summation_baseht_2="3048",
                sky_cover_summation_baseht_3="4572",
                sky_cover_summation_baseht_4="7620",
            )
        )
        assert obs is not None
        assert obs["sky_cover_1"] == "SCT"
        assert obs["sky_cover_2"] == "SCT"
        assert obs["sky_cover_3"] == "BKN"
        assert obs["sky_cover_4"] == "BKN"
        assert obs["sky_base_1_ft"] == round(1494 * 3.28084)
        assert obs["sky_base_2_ft"] == round(3048 * 3.28084)
        assert obs["sky_base_3_ft"] == round(4572 * 3.28084)
        assert obs["sky_base_4_ft"] == round(7620 * 3.28084)


# ---------------------------------------------------------------------------
# Weather codes
# ---------------------------------------------------------------------------


class TestWeatherCodes:
    def test_single_code_no_colon(self):
        from tradewinds.weather._ghcnh import parse_ghcnh_row

        obs = parse_ghcnh_row(_make_row(pres_wx_AW1="TS"))
        assert obs is not None
        assert obs["weather_codes"] == "TS"

    def test_code_with_colon_strips_number(self):
        from tradewinds.weather._ghcnh import parse_ghcnh_row

        obs = parse_ghcnh_row(_make_row(pres_wx_AW1="RA:62"))
        assert obs is not None
        assert obs["weather_codes"] == "RA"

    def test_multiple_codes_joined(self):
        from tradewinds.weather._ghcnh import parse_ghcnh_row

        obs = parse_ghcnh_row(
            _make_row(pres_wx_AW1="TS:90", pres_wx_AW2="RA:62", pres_wx_AW3="BR:10")
        )
        assert obs is not None
        assert obs["weather_codes"] == "TS RA BR"

    def test_intensity_prefix_preserved(self):
        from tradewinds.weather._ghcnh import parse_ghcnh_row

        obs = parse_ghcnh_row(_make_row(pres_wx_AW1="+RA:02"))
        assert obs is not None
        assert obs["weather_codes"] == "+RA"

    def test_light_prefix_preserved(self):
        from tradewinds.weather._ghcnh import parse_ghcnh_row

        obs = parse_ghcnh_row(_make_row(pres_wx_AW1="-RA:02"))
        assert obs is not None
        assert obs["weather_codes"] == "-RA"

    def test_empty_codes_is_none(self):
        from tradewinds.weather._ghcnh import parse_ghcnh_row

        obs = parse_ghcnh_row(_make_row(pres_wx_AW1="", pres_wx_AW2="", pres_wx_AW3=""))
        assert obs is not None
        assert obs["weather_codes"] is None


# ---------------------------------------------------------------------------
# Quality_Code filtering
# ---------------------------------------------------------------------------


class TestQualityCodeFiltering:
    def test_qc_0_accepted(self):
        from tradewinds.weather._ghcnh import parse_ghcnh_row

        obs = parse_ghcnh_row(_make_row(temperature_Quality_Code="0"))
        assert obs is not None
        assert obs["temp_c"] == 5.0

    def test_qc_1_accepted(self):
        from tradewinds.weather._ghcnh import parse_ghcnh_row

        obs = parse_ghcnh_row(_make_row(temperature_Quality_Code="1"))
        assert obs is not None
        assert obs["temp_c"] == 5.0

    def test_qc_4_accepted(self):
        from tradewinds.weather._ghcnh import parse_ghcnh_row

        obs = parse_ghcnh_row(_make_row(temperature_Quality_Code="4"))
        assert obs is not None
        assert obs["temp_c"] == 5.0

    def test_qc_5_accepted(self):
        from tradewinds.weather._ghcnh import parse_ghcnh_row

        obs = parse_ghcnh_row(_make_row(temperature_Quality_Code="5"))
        assert obs is not None
        assert obs["temp_c"] == 5.0

    def test_qc_2_rejected_sets_temp_none(self):
        from tradewinds.weather._ghcnh import parse_ghcnh_row

        obs = parse_ghcnh_row(_make_row(temperature_Quality_Code="2"))
        assert obs is not None
        assert obs["temp_c"] is None
        assert obs["temp_f"] is None

    def test_qc_3_rejected(self):
        from tradewinds.weather._ghcnh import parse_ghcnh_row

        obs = parse_ghcnh_row(_make_row(temperature_Quality_Code="3"))
        assert obs is not None
        assert obs["temp_c"] is None

    def test_qc_6_rejected(self):
        from tradewinds.weather._ghcnh import parse_ghcnh_row

        obs = parse_ghcnh_row(_make_row(temperature_Quality_Code="6"))
        assert obs is not None
        assert obs["temp_c"] is None

    def test_qc_7_rejected(self):
        from tradewinds.weather._ghcnh import parse_ghcnh_row

        obs = parse_ghcnh_row(_make_row(temperature_Quality_Code="7"))
        assert obs is not None
        assert obs["temp_c"] is None

    def test_qc_letter_I_rejected(self):
        from tradewinds.weather._ghcnh import parse_ghcnh_row

        obs = parse_ghcnh_row(_make_row(temperature_Quality_Code="I"))
        assert obs is not None
        assert obs["temp_c"] is None

    def test_qc_letter_P_rejected(self):
        from tradewinds.weather._ghcnh import parse_ghcnh_row

        obs = parse_ghcnh_row(_make_row(temperature_Quality_Code="P"))
        assert obs is not None
        assert obs["temp_c"] is None

    def test_qc_letter_R_rejected(self):
        from tradewinds.weather._ghcnh import parse_ghcnh_row

        obs = parse_ghcnh_row(_make_row(temperature_Quality_Code="R"))
        assert obs is not None
        assert obs["temp_c"] is None

    def test_qc_letter_U_rejected(self):
        from tradewinds.weather._ghcnh import parse_ghcnh_row

        obs = parse_ghcnh_row(_make_row(temperature_Quality_Code="U"))
        assert obs is not None
        assert obs["temp_c"] is None

    def test_qc_empty_accepted(self):
        from tradewinds.weather._ghcnh import parse_ghcnh_row

        obs = parse_ghcnh_row(_make_row(temperature_Quality_Code=""))
        assert obs is not None
        assert obs["temp_c"] == 5.0

    def test_qc_whitespace_accepted(self):
        from tradewinds.weather._ghcnh import parse_ghcnh_row

        obs = parse_ghcnh_row(_make_row(temperature_Quality_Code=" 1 "))
        assert obs is not None
        assert obs["temp_c"] == 5.0

    def test_all_key_vars_rejected_returns_none(self):
        from tradewinds.weather._ghcnh import parse_ghcnh_row

        obs = parse_ghcnh_row(
            _make_row(
                temperature_Quality_Code="2",
                dew_point_temperature_Quality_Code="2",
                wind_speed_Quality_Code="2",
                sea_level_pressure_Quality_Code="2",
            )
        )
        assert obs is None

    def test_partial_rejection_row_still_returned(self):
        from tradewinds.weather._ghcnh import parse_ghcnh_row

        obs = parse_ghcnh_row(
            _make_row(
                temperature_Quality_Code="2",
                dew_point_temperature_Quality_Code="1",
                wind_speed_Quality_Code="1",
                sea_level_pressure_Quality_Code="1",
            )
        )
        assert obs is not None
        assert obs["temp_c"] is None
        assert obs["dewpoint_c"] == 2.0
        assert obs["wind_speed_kt"] is not None
        assert obs["sea_level_pressure_mb"] == 1013.2

    def test_wind_qc_rejected_wind_none(self):
        from tradewinds.weather._ghcnh import parse_ghcnh_row

        obs = parse_ghcnh_row(
            _make_row(
                wind_speed_Quality_Code="3",
                wind_direction_Quality_Code="3",
            )
        )
        assert obs is not None
        assert obs["wind_speed_kt"] is None
        assert obs["wind_dir_degrees"] is None


# ---------------------------------------------------------------------------
# Station code extraction fallback
# ---------------------------------------------------------------------------


class TestStationCodeExtraction:
    def test_icao_in_temperature(self):
        from tradewinds.weather._ghcnh import parse_ghcnh_row

        obs = parse_ghcnh_row(_make_row(temperature_Source_Station_ID="ICAO-KJFK"))
        assert obs is not None
        assert obs["station_code"] == "JFK"

    def test_wmo_falls_back_to_other_fields(self):
        from tradewinds.weather._ghcnh import parse_ghcnh_row

        row = _make_row(
            temperature_Source_Station_ID="744860-94789",
            dew_point_temperature_Source_Station_ID="744860-94789",
        )
        row["sky_cover_summation_4_Source_Station_ID"] = "ICAO-KJFK"
        obs = parse_ghcnh_row(row)
        assert obs is not None
        assert obs["station_code"] == "JFK"


# ---------------------------------------------------------------------------
# Raw METAR
# ---------------------------------------------------------------------------


class TestRawMetar:
    def test_passthrough(self):
        from tradewinds.weather._ghcnh import parse_ghcnh_row

        metar = "METAR KJFK 010051Z 09014G25KT 10SM SCT049"
        obs = parse_ghcnh_row(_make_row(REM=metar))
        assert obs is not None
        assert obs["raw_metar"] == metar

    def test_truncated_at_2048(self):
        from tradewinds.weather._ghcnh import parse_ghcnh_row

        long_rem = "A" * 3000
        obs = parse_ghcnh_row(_make_row(REM=long_rem))
        assert obs is not None
        assert len(obs["raw_metar"]) == 2048

    def test_empty_rem_is_none(self):
        from tradewinds.weather._ghcnh import parse_ghcnh_row

        obs = parse_ghcnh_row(_make_row(REM=""))
        assert obs is not None
        assert obs["raw_metar"] is None


# ---------------------------------------------------------------------------
# parse_ghcnh_file — integration with real PSV fixture
# ---------------------------------------------------------------------------


class TestParseGhcnhFile:
    @pytest.fixture
    def fixture_path(self):
        path = FIXTURES / "ghcnh_jfk_2025_sample.psv"
        if not path.exists():
            pytest.skip("No GHCNh sample fixture")
        return path

    def test_returns_list_of_dicts(self, fixture_path):
        from tradewinds.weather._ghcnh import parse_ghcnh_file

        results = parse_ghcnh_file(fixture_path)
        assert isinstance(results, list)
        assert len(results) > 0

    def test_all_validate_against_schema(self, fixture_path):
        from tradewinds.weather._ghcnh import parse_ghcnh_file

        schema = _load_schema()
        results = parse_ghcnh_file(fixture_path)
        errors = []
        for i, obs in enumerate(results):
            try:
                validate(instance=obs, schema=schema)
            except Exception as e:
                errors.append(f"Row {i}: {e}")
        assert not errors, f"{len(errors)} validation errors:\n" + "\n".join(errors[:5])

    def test_all_have_source_ghcnh(self, fixture_path):
        from tradewinds.weather._ghcnh import parse_ghcnh_file

        results = parse_ghcnh_file(fixture_path)
        for obs in results:
            assert obs["source"] == "ghcnh"

    def test_station_codes_valid(self, fixture_path):
        import re

        from tradewinds.weather._ghcnh import parse_ghcnh_file

        results = parse_ghcnh_file(fixture_path)
        pattern = re.compile(r"^[A-Z]{3,4}$")
        for obs in results:
            assert pattern.match(obs["station_code"]), f"Invalid station: {obs['station_code']}"

    def test_no_rounding_on_temperatures(self, fixture_path):
        from tradewinds._internal._convert import celsius_to_fahrenheit
        from tradewinds.weather._ghcnh import parse_ghcnh_file

        results = parse_ghcnh_file(fixture_path)
        for obs in results:
            if obs["temp_c"] is not None:
                assert obs["temp_f"] == celsius_to_fahrenheit(obs["temp_c"])

    def test_exactly_30_fields_each(self, fixture_path):
        from tradewinds.weather._ghcnh import parse_ghcnh_file

        results = parse_ghcnh_file(fixture_path)
        for obs in results:
            assert len(obs) == 30

    def test_empty_file(self, tmp_path):
        from tradewinds.weather._ghcnh import parse_ghcnh_file

        empty = tmp_path / "empty.psv"
        empty.write_text("STATION|DATE|temperature\n")
        results = parse_ghcnh_file(empty)
        assert results == []


# ---------------------------------------------------------------------------
# _safe_float edge cases
# ---------------------------------------------------------------------------


class TestSafeFloat:
    def test_inf_returns_none(self):
        from tradewinds.weather._ghcnh import _safe_float

        assert _safe_float("inf") is None

    def test_nan_returns_none(self):
        from tradewinds.weather._ghcnh import _safe_float

        assert _safe_float("nan") is None

    def test_na_returns_none(self):
        from tradewinds.weather._ghcnh import _safe_float

        assert _safe_float("NA") is None

    def test_valid_number(self):
        from tradewinds.weather._ghcnh import _safe_float

        assert _safe_float("10.5") == 10.5


# ---------------------------------------------------------------------------
# Temperature bounds
# ---------------------------------------------------------------------------


class TestTempBounds:
    def test_extreme_hot_temp_is_none(self):
        """500°C is well above the 60°C max."""
        from tradewinds.weather._ghcnh import parse_ghcnh_row

        obs = parse_ghcnh_row(_make_row(temperature="500.0"))
        assert obs is not None
        assert obs["temp_c"] is None
        assert obs["temp_f"] is None

    def test_extreme_cold_temp_is_none(self):
        """-200°C is below the -90°C min."""
        from tradewinds.weather._ghcnh import parse_ghcnh_row

        obs = parse_ghcnh_row(_make_row(temperature="-200.0"))
        assert obs is not None
        assert obs["temp_c"] is None
        assert obs["temp_f"] is None

    def test_extreme_dewpoint_is_none(self):
        from tradewinds.weather._ghcnh import parse_ghcnh_row

        obs = parse_ghcnh_row(_make_row(dew_point_temperature="100.0"))
        assert obs is not None
        assert obs["dewpoint_c"] is None
        assert obs["dewpoint_f"] is None

    def test_valid_temp_within_bounds(self):
        from tradewinds.weather._ghcnh import parse_ghcnh_row

        obs = parse_ghcnh_row(_make_row(temperature="25.0"))
        assert obs is not None
        assert obs["temp_c"] == 25.0

    def test_boundary_min_passes(self):
        from tradewinds.weather._ghcnh import parse_ghcnh_row

        obs = parse_ghcnh_row(_make_row(temperature="-90.0"))
        assert obs is not None
        assert obs["temp_c"] == -90.0

    def test_boundary_max_passes(self):
        from tradewinds.weather._ghcnh import parse_ghcnh_row

        obs = parse_ghcnh_row(_make_row(temperature="60.0"))
        assert obs is not None
        assert obs["temp_c"] == 60.0

    def test_just_outside_min_is_none(self):
        from tradewinds.weather._ghcnh import parse_ghcnh_row

        obs = parse_ghcnh_row(_make_row(temperature="-90.1"))
        assert obs is not None
        assert obs["temp_c"] is None

    def test_just_outside_max_is_none(self):
        from tradewinds.weather._ghcnh import parse_ghcnh_row

        obs = parse_ghcnh_row(_make_row(temperature="60.1"))
        assert obs is not None
        assert obs["temp_c"] is None

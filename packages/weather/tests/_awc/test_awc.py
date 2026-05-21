"""Tests for tradewinds.weather._awc — AWC METAR transform."""

from __future__ import annotations


def _make_metar(**overrides: object) -> dict:
    """Build a minimal valid AWC METAR dict with sensible defaults."""
    base: dict = {
        "icaoId": "KJFK",
        "obsTime": 1705320000,  # 2024-01-15T12:00:00Z
        "metarType": "METAR",
        "temp": 15.6,
        "dewp": 12.8,
        "wdir": 270,
        "wspd": 10,
        "wgst": None,
        "altim": 1013.25,
        "slp": 1013.2,
        "visib": "10",
        "wxString": None,
        "clouds": [
            {"cover": "SCT", "base": 3500},
            {"cover": "BKN", "base": 8000},
        ],
        "precip": None,
        "rawOb": "METAR KJFK 151200Z 27010KT 10SM SCT035 BKN080 16/13 A2992 RMK AO2",
        "qcField": 6,
    }
    base.update(overrides)
    return base


class TestAwcValidMapping:
    """awc_to_observation produces a valid observation dict."""

    def test_basic_mapping(self) -> None:
        from tradewinds.weather._awc import awc_to_observation

        result = awc_to_observation(_make_metar())
        assert result is not None
        assert result["station_code"] == "JFK"
        assert result["observed_at"] == "2024-01-15T12:00:00Z"
        assert result["observation_type"] == "METAR"
        assert result["source"] == "awc"

    def test_temp_c_and_dewpoint_c_populated(self) -> None:
        from tradewinds.weather._awc import awc_to_observation

        result = awc_to_observation(_make_metar(temp=15.6, dewp=12.8))
        assert result is not None
        assert result["temp_c"] == 15.6
        assert result["dewpoint_c"] == 12.8

    def test_temp_f_from_celsius_no_rounding(self) -> None:
        """temp_f = celsius_to_fahrenheit(temp_c), no rounding."""
        from tradewinds.weather._awc import awc_to_observation

        result = awc_to_observation(_make_metar(temp=15.6))
        assert result is not None
        expected = 15.6 * 9 / 5 + 32
        assert result["temp_f"] == expected

    def test_dewpoint_f_from_celsius_no_rounding(self) -> None:
        from tradewinds.weather._awc import awc_to_observation

        result = awc_to_observation(_make_metar(dewp=12.8))
        assert result is not None
        expected = 12.8 * 9 / 5 + 32
        assert result["dewpoint_f"] == expected

    def test_altimeter_hpa_to_inhg_no_rounding(self) -> None:
        """AWC altim is hPa, converted to inHg without rounding."""
        from tradewinds.weather._awc import awc_to_observation

        result = awc_to_observation(_make_metar(altim=1013.25))
        assert result is not None
        expected = 1013.25 * 0.0295299875
        assert result["altimeter_inhg"] == expected

    def test_sea_level_pressure_passthrough(self) -> None:
        from tradewinds.weather._awc import awc_to_observation

        result = awc_to_observation(_make_metar(slp=1013.2))
        assert result is not None
        assert result["sea_level_pressure_mb"] == 1013.2

    def test_sky_layers(self) -> None:
        from tradewinds.weather._awc import awc_to_observation

        result = awc_to_observation(_make_metar())
        assert result is not None
        assert result["sky_cover_1"] == "SCT"
        assert result["sky_base_1_ft"] == 3500
        assert result["sky_cover_2"] == "BKN"
        assert result["sky_base_2_ft"] == 8000
        assert result["sky_cover_3"] is None
        assert result["sky_base_3_ft"] is None

    def test_speci_type(self) -> None:
        from tradewinds.weather._awc import awc_to_observation

        result = awc_to_observation(_make_metar(metarType="SPECI"))
        assert result is not None
        assert result["observation_type"] == "SPECI"

    def test_raw_metar_truncated(self) -> None:
        from tradewinds.weather._awc import awc_to_observation

        long_metar = "X" * 3000
        result = awc_to_observation(_make_metar(rawOb=long_metar))
        assert result is not None
        assert len(result["raw_metar"]) == 2048

    def test_four_letter_non_conus_kept(self) -> None:
        """Non-K-prefix 4-letter ICAO stays as-is."""
        from tradewinds.weather._awc import awc_to_observation

        result = awc_to_observation(_make_metar(icaoId="EGLL"))
        assert result is not None
        assert result["station_code"] == "EGLL"


class TestAwcWindHandling:
    """VRB wind → null, numeric wind preserved."""

    def test_vrb_wind_is_null(self) -> None:
        from tradewinds.weather._awc import awc_to_observation

        result = awc_to_observation(_make_metar(wdir="VRB"))
        assert result is not None
        assert result["wind_dir_degrees"] is None

    def test_numeric_wind_dir(self) -> None:
        from tradewinds.weather._awc import awc_to_observation

        result = awc_to_observation(_make_metar(wdir=180))
        assert result is not None
        assert result["wind_dir_degrees"] == 180

    def test_calm_wind(self) -> None:
        from tradewinds.weather._awc import awc_to_observation

        result = awc_to_observation(_make_metar(wdir=0, wspd=0))
        assert result is not None
        assert result["wind_dir_degrees"] == 0
        assert result["wind_speed_kt"] == 0


class TestAwcVisibility:
    """10+ → 10, fractions parsed, plain numbers preserved."""

    def test_ten_plus(self) -> None:
        from tradewinds.weather._awc import awc_to_observation

        result = awc_to_observation(_make_metar(visib="10+"))
        assert result is not None
        assert result["visibility_miles"] == 10.0

    def test_half_mile(self) -> None:
        from tradewinds.weather._awc import awc_to_observation

        result = awc_to_observation(_make_metar(visib="1/2"))
        assert result is not None
        assert result["visibility_miles"] == 0.5

    def test_mixed_number(self) -> None:
        from tradewinds.weather._awc import awc_to_observation

        result = awc_to_observation(_make_metar(visib="1 1/2"))
        assert result is not None
        assert result["visibility_miles"] == 1.5

    def test_null_visibility(self) -> None:
        from tradewinds.weather._awc import awc_to_observation

        result = awc_to_observation(_make_metar(visib=None))
        assert result is not None
        assert result["visibility_miles"] is None


class TestAwcPrecip:
    """Trace precip 'T' → 0.0, numeric passthrough, null → null."""

    def test_trace_precip(self) -> None:
        from tradewinds.weather._awc import awc_to_observation

        result = awc_to_observation(_make_metar(precip="T"))
        assert result is not None
        assert result["precip_1hr_inches"] == 0.0

    def test_numeric_precip(self) -> None:
        from tradewinds.weather._awc import awc_to_observation

        result = awc_to_observation(_make_metar(precip=0.05))
        assert result is not None
        assert result["precip_1hr_inches"] == 0.05

    def test_null_precip(self) -> None:
        from tradewinds.weather._awc import awc_to_observation

        result = awc_to_observation(_make_metar(precip=None))
        assert result is not None
        assert result["precip_1hr_inches"] is None


class TestAwcMissingFields:
    """Missing fields → null, NEVER zero."""

    def test_missing_temp(self) -> None:
        from tradewinds.weather._awc import awc_to_observation

        result = awc_to_observation(_make_metar(temp=None))
        assert result is not None
        assert result["temp_c"] is None
        assert result["temp_f"] is None

    def test_missing_slp(self) -> None:
        from tradewinds.weather._awc import awc_to_observation

        result = awc_to_observation(_make_metar(slp=None))
        assert result is not None
        assert result["sea_level_pressure_mb"] is None

    def test_slp_zero_becomes_none(self) -> None:
        """sea_level_pressure_mb must NEVER be zero (original bug)."""
        from tradewinds.weather._awc import awc_to_observation

        result = awc_to_observation(_make_metar(slp=0))
        assert result is not None
        assert result["sea_level_pressure_mb"] is None

    def test_slp_negative_sentinel_becomes_none(self) -> None:
        """Meteorological sentinel -999.0 must be filtered."""
        from tradewinds.weather._awc import awc_to_observation

        result = awc_to_observation(_make_metar(slp=-999.0))
        assert result is not None
        assert result["sea_level_pressure_mb"] is None

    def test_slp_out_of_bounds_high_becomes_none(self) -> None:
        from tradewinds.weather._awc import awc_to_observation

        result = awc_to_observation(_make_metar(slp=1200.0))
        assert result is not None
        assert result["sea_level_pressure_mb"] is None

    def test_missing_clouds(self) -> None:
        from tradewinds.weather._awc import awc_to_observation

        result = awc_to_observation(_make_metar(clouds=[]))
        assert result is not None
        assert result["sky_cover_1"] is None
        assert result["sky_base_1_ft"] is None

    def test_snow_depth_always_none_from_awc(self) -> None:
        from tradewinds.weather._awc import awc_to_observation

        result = awc_to_observation(_make_metar())
        assert result is not None
        assert result["snow_depth_inches"] is None


class TestAwcQcField:
    """qc_field bitmask extraction from AWC."""

    def test_qc_field_extracted(self) -> None:
        from tradewinds.weather._awc import awc_to_observation

        result = awc_to_observation(_make_metar(qcField=6))
        assert result is not None
        assert result["qc_field"] == 6

    def test_qc_field_none_when_missing(self) -> None:
        from tradewinds.weather._awc import awc_to_observation

        result = awc_to_observation(_make_metar(qcField=None))
        assert result is not None
        assert result["qc_field"] is None

    def test_qc_field_zero_preserved(self) -> None:
        from tradewinds.weather._awc import awc_to_observation

        result = awc_to_observation(_make_metar(qcField=0))
        assert result is not None
        assert result["qc_field"] == 0


class TestAwcPeakWind:
    """Peak wind parsed from METAR remarks."""

    def test_peak_wind_parsed(self) -> None:
        from tradewinds.weather._awc import awc_to_observation

        raw = "METAR KJFK 151200Z 27010KT PK WND 28035/1156 RMK AO2"
        result = awc_to_observation(_make_metar(rawOb=raw))
        assert result is not None
        assert result["peak_wind_dir"] == 280
        assert result["peak_wind_gust_kt"] == 35
        assert result["peak_wind_time"] == "1156"

    def test_no_peak_wind(self) -> None:
        from tradewinds.weather._awc import awc_to_observation

        raw = "METAR KJFK 151200Z 27010KT 10SM SCT035 RMK AO2"
        result = awc_to_observation(_make_metar(rawOb=raw))
        assert result is not None
        assert result["peak_wind_dir"] is None
        assert result["peak_wind_gust_kt"] is None
        assert result["peak_wind_time"] is None


class TestAwcInvalidInput:
    """Invalid inputs return None."""

    def test_missing_icao_returns_none(self) -> None:
        from tradewinds.weather._awc import awc_to_observation

        result = awc_to_observation(_make_metar(icaoId=None))
        assert result is None

    def test_empty_icao_returns_none(self) -> None:
        from tradewinds.weather._awc import awc_to_observation

        result = awc_to_observation(_make_metar(icaoId=""))
        assert result is None

    def test_missing_obs_time_returns_none(self) -> None:
        from tradewinds.weather._awc import awc_to_observation

        result = awc_to_observation(_make_metar(obsTime=None))
        assert result is None


class TestAwcOutputSchema:
    """Output dict must have exactly the fields from observation.json."""

    def test_output_has_all_schema_fields(self) -> None:
        from tradewinds.weather._awc import awc_to_observation

        result = awc_to_observation(_make_metar())
        assert result is not None

        expected_keys = {
            "station_code",
            "observed_at",
            "observation_type",
            "source",
            "temp_c",
            "dewpoint_c",
            "temp_f",
            "dewpoint_f",
            "wind_dir_degrees",
            "wind_speed_kt",
            "wind_gust_kt",
            "altimeter_inhg",
            "sea_level_pressure_mb",
            "sky_cover_1",
            "sky_base_1_ft",
            "sky_cover_2",
            "sky_base_2_ft",
            "sky_cover_3",
            "sky_base_3_ft",
            "sky_cover_4",
            "sky_base_4_ft",
            "visibility_miles",
            "weather_codes",
            "precip_1hr_inches",
            "peak_wind_gust_kt",
            "peak_wind_dir",
            "peak_wind_time",
            "snow_depth_inches",
            "qc_field",
            "raw_metar",
        }
        assert set(result.keys()) == expected_keys

    def test_no_extra_fields(self) -> None:
        """additionalProperties: false — no extra keys allowed."""
        from tradewinds.weather._awc import awc_to_observation

        result = awc_to_observation(_make_metar())
        assert result is not None
        # Should NOT have relative_humidity or feels_like_f (computed in SDK)
        assert "relative_humidity" not in result
        assert "feels_like_f" not in result


class TestIcaoToStationCode:
    """Direct unit tests for icao_to_station_code."""

    def test_conus_4letter_strips_k(self) -> None:
        from tradewinds.weather._awc import icao_to_station_code

        assert icao_to_station_code("KJFK") == "JFK"

    def test_non_conus_4letter_kept(self) -> None:
        from tradewinds.weather._awc import icao_to_station_code

        assert icao_to_station_code("EGLL") == "EGLL"

    def test_3letter_k_prefix_not_stripped(self) -> None:
        from tradewinds.weather._awc import icao_to_station_code

        assert icao_to_station_code("KJF") == "KJF"

    def test_lowercase_uppercased(self) -> None:
        from tradewinds.weather._awc import icao_to_station_code

        assert icao_to_station_code("kjfk") == "JFK"

    def test_whitespace_stripped(self) -> None:
        from tradewinds.weather._awc import icao_to_station_code

        assert icao_to_station_code(" KJFK ") == "JFK"


class TestMapCloudCover:
    """Direct unit tests for map_cloud_cover."""

    def test_valid_codes(self) -> None:
        from tradewinds.weather._awc import map_cloud_cover

        for code in ("CLR", "SKC", "FEW", "SCT", "BKN", "OVC", "VV"):
            assert map_cloud_cover(code) == code

    def test_cavok_maps_to_clr(self) -> None:
        from tradewinds.weather._awc import map_cloud_cover

        assert map_cloud_cover("CAVOK") == "CLR"

    def test_unknown_returns_none(self) -> None:
        from tradewinds.weather._awc import map_cloud_cover

        assert map_cloud_cover("JUNK") is None

    def test_none_returns_none(self) -> None:
        from tradewinds.weather._awc import map_cloud_cover

        assert map_cloud_cover(None) is None

    def test_lowercase_uppercased(self) -> None:
        from tradewinds.weather._awc import map_cloud_cover

        assert map_cloud_cover("sct") == "SCT"


class TestParseAwcVisibilityEdges:
    """Edge cases for parse_awc_visibility."""

    def test_empty_string_returns_none(self) -> None:
        from tradewinds.weather._awc import parse_awc_visibility

        assert parse_awc_visibility("") is None

    def test_null_string_returns_none(self) -> None:
        from tradewinds.weather._awc import parse_awc_visibility

        assert parse_awc_visibility("null") is None

    def test_three_quarter_mile(self) -> None:
        from tradewinds.weather._awc import parse_awc_visibility

        assert parse_awc_visibility("3/4") == 0.75

    def test_mixed_two_and_quarter(self) -> None:
        from tradewinds.weather._awc import parse_awc_visibility

        assert parse_awc_visibility("2 1/4") == 2.25

    def test_large_value_capped(self) -> None:
        from tradewinds.weather._awc import parse_awc_visibility

        assert parse_awc_visibility("100") == 99.99


class TestAwcLowercaseIcao:
    """Station code validation after uppercase fix."""

    def test_lowercase_icao_accepted(self) -> None:
        from tradewinds.weather._awc import awc_to_observation

        result = awc_to_observation(_make_metar(icaoId="kjfk"))
        assert result is not None
        assert result["station_code"] == "JFK"

    def test_invalid_station_code_returns_none(self) -> None:
        from tradewinds.weather._awc import awc_to_observation

        result = awc_to_observation(_make_metar(icaoId="12"))
        assert result is None


class TestAwcObsTimeSanity:
    """obsTime sanity checks."""

    def test_millisecond_timestamp_rejected(self) -> None:
        from tradewinds.weather._awc import awc_to_observation

        result = awc_to_observation(_make_metar(obsTime=1705320000000))
        assert result is None

    def test_negative_timestamp_rejected(self) -> None:
        from tradewinds.weather._awc import awc_to_observation

        result = awc_to_observation(_make_metar(obsTime=-1))
        assert result is None


class TestAwcBoundsValidation:
    """Schema bounds validation on numeric outputs."""

    def test_negative_wind_speed_is_none(self) -> None:
        from tradewinds.weather._awc import awc_to_observation

        result = awc_to_observation(_make_metar(wspd=-5))
        assert result is not None
        assert result["wind_speed_kt"] is None

    def test_excessive_wind_speed_is_none(self) -> None:
        from tradewinds.weather._awc import awc_to_observation

        result = awc_to_observation(_make_metar(wspd=999))
        assert result is not None
        assert result["wind_speed_kt"] is None

    def test_negative_wind_gust_is_none(self) -> None:
        from tradewinds.weather._awc import awc_to_observation

        result = awc_to_observation(_make_metar(wgst=-10))
        assert result is not None
        assert result["wind_gust_kt"] is None

    def test_negative_wind_dir_is_none(self) -> None:
        from tradewinds.weather._awc import awc_to_observation

        result = awc_to_observation(_make_metar(wdir=-10))
        assert result is not None
        assert result["wind_dir_degrees"] is None

    def test_wind_dir_over_360_is_none(self) -> None:
        from tradewinds.weather._awc import awc_to_observation

        result = awc_to_observation(_make_metar(wdir=999))
        assert result is not None
        assert result["wind_dir_degrees"] is None

    def test_negative_precip_is_none(self) -> None:
        from tradewinds.weather._awc import awc_to_observation

        result = awc_to_observation(_make_metar(precip=-0.5))
        assert result is not None
        assert result["precip_1hr_inches"] is None

    def test_valid_bounds_pass_through(self) -> None:
        from tradewinds.weather._awc import awc_to_observation

        result = awc_to_observation(_make_metar(wspd=15, wgst=25, wdir=270))
        assert result is not None
        assert result["wind_speed_kt"] == 15
        assert result["wind_gust_kt"] == 25
        assert result["wind_dir_degrees"] == 270


class TestParseTgroup:
    """Direct unit tests for _parse_tgroup."""

    def test_positive_temps(self) -> None:
        from tradewinds.weather._awc import _parse_tgroup

        # T02560167 → 25.6°C / 16.7°C
        t, d = _parse_tgroup("METAR KJFK RMK AO2 T02560167")
        assert t == 25.6
        assert d == 16.7

    def test_negative_temp_positive_dewpoint(self) -> None:
        from tradewinds.weather._awc import _parse_tgroup

        # T10390061 → -3.9°C / 6.1°C
        t, d = _parse_tgroup("METAR KJFK RMK AO2 T10390061")
        assert t == -3.9
        assert d == 6.1

    def test_both_negative(self) -> None:
        from tradewinds.weather._awc import _parse_tgroup

        # T11001089 → -10.0°C / -8.9°C
        t, d = _parse_tgroup("METAR KJFK RMK AO2 T11001089")
        assert t == -10.0
        assert d == -8.9

    def test_zero_temps(self) -> None:
        from tradewinds.weather._awc import _parse_tgroup

        # T00000000 → 0.0°C / 0.0°C
        t, d = _parse_tgroup("METAR KJFK RMK T00000000")
        assert t == 0.0
        assert d == 0.0

    def test_no_tgroup_returns_none(self) -> None:
        from tradewinds.weather._awc import _parse_tgroup

        t, d = _parse_tgroup("METAR KJFK RMK AO2 SLP049")
        assert t is None
        assert d is None

    def test_none_input(self) -> None:
        from tradewinds.weather._awc import _parse_tgroup

        t, d = _parse_tgroup(None)
        assert t is None
        assert d is None

    def test_empty_string(self) -> None:
        from tradewinds.weather._awc import _parse_tgroup

        t, d = _parse_tgroup("")
        assert t is None
        assert d is None

    def test_tgroup_at_end_of_string(self) -> None:
        from tradewinds.weather._awc import _parse_tgroup

        t, d = _parse_tgroup("RMK AO2 T01560100")
        assert t == 15.6
        assert d == 10.0

    def test_partial_tgroup_7digits_returns_none(self) -> None:
        """7 digits after T should not match (need exactly 8)."""
        from tradewinds.weather._awc import _parse_tgroup

        t, d = _parse_tgroup("RMK AO2 T0256016")
        assert t is None
        assert d is None

    def test_tgroup_9digits_no_match(self) -> None:
        """9 digits after T should not match either."""
        from tradewinds.weather._awc import _parse_tgroup

        t, d = _parse_tgroup("RMK AO2 T025601670")
        assert t is None
        assert d is None


class TestAwcTgroupIntegration:
    """T-group overrides body group temp in awc_to_observation."""

    def test_tgroup_overrides_body_temp(self) -> None:
        from tradewinds.weather._awc import awc_to_observation

        raw = "METAR KJFK 151200Z 27010KT 10SM SCT035 16/13 A2992 RMK AO2 T01560128"
        result = awc_to_observation(_make_metar(temp=16.0, dewp=13.0, rawOb=raw))
        assert result is not None
        # T-group gives 15.6°C / 12.8°C, body gives 16.0/13.0
        assert result["temp_c"] == 15.6
        assert result["dewpoint_c"] == 12.8

    def test_no_tgroup_uses_body(self) -> None:
        from tradewinds.weather._awc import awc_to_observation

        raw = "METAR KJFK 151200Z 27010KT 10SM SCT035 16/13 A2992 RMK AO2 SLP049"
        result = awc_to_observation(_make_metar(temp=16.0, dewp=13.0, rawOb=raw))
        assert result is not None
        assert result["temp_c"] == 16.0
        assert result["dewpoint_c"] == 13.0

    def test_tgroup_negative_temps(self) -> None:
        from tradewinds.weather._awc import awc_to_observation

        raw = "METAR KJFK 151200Z 27010KT RMK AO2 T10390061"
        result = awc_to_observation(_make_metar(temp=-4.0, dewp=6.0, rawOb=raw))
        assert result is not None
        assert result["temp_c"] == -3.9
        assert result["dewpoint_c"] == 6.1

    def test_tgroup_temp_f_derived_from_tgroup(self) -> None:
        """temp_f is derived from T-group °C, not from body group."""
        from tradewinds.weather._awc import awc_to_observation

        raw = "METAR KJFK 151200Z 27010KT RMK AO2 T02560167"
        result = awc_to_observation(_make_metar(temp=26.0, dewp=17.0, rawOb=raw))
        assert result is not None
        assert result["temp_c"] == 25.6
        # temp_f should match 25.6 * 9/5 + 32
        expected_f = 25.6 * 9 / 5 + 32
        assert result["temp_f"] == expected_f

    def test_tgroup_missing_rawob_uses_body(self) -> None:
        """If rawOb is None, body group temps pass through."""
        from tradewinds.weather._awc import awc_to_observation

        result = awc_to_observation(_make_metar(temp=15.6, dewp=12.8, rawOb=None))
        assert result is not None
        assert result["temp_c"] == 15.6
        assert result["dewpoint_c"] == 12.8


class TestAwcTempBounds:
    """Temperature bounds clamp extreme values to None."""

    def test_extreme_hot_temp_is_none(self) -> None:
        from tradewinds.weather._awc import awc_to_observation

        # 500°C well above world record 56.7°C
        result = awc_to_observation(_make_metar(temp=500.0))
        assert result is not None
        assert result["temp_c"] is None
        assert result["temp_f"] is None

    def test_extreme_cold_temp_is_none(self) -> None:
        from tradewinds.weather._awc import awc_to_observation

        # -200°C below world record -89.2°C
        result = awc_to_observation(_make_metar(temp=-200.0))
        assert result is not None
        assert result["temp_c"] is None
        assert result["temp_f"] is None

    def test_extreme_dewpoint_is_none(self) -> None:
        from tradewinds.weather._awc import awc_to_observation

        result = awc_to_observation(_make_metar(dewp=100.0))
        assert result is not None
        assert result["dewpoint_c"] is None
        assert result["dewpoint_f"] is None

    def test_valid_temp_passes_bounds(self) -> None:
        from tradewinds.weather._awc import awc_to_observation

        result = awc_to_observation(_make_metar(temp=25.0, dewp=15.0))
        assert result is not None
        assert result["temp_c"] == 25.0
        assert result["dewpoint_c"] == 15.0

    def test_boundary_min_passes(self) -> None:
        from tradewinds.weather._awc import awc_to_observation

        result = awc_to_observation(_make_metar(temp=-90.0))
        assert result is not None
        assert result["temp_c"] == -90.0

    def test_boundary_max_passes(self) -> None:
        from tradewinds.weather._awc import awc_to_observation

        result = awc_to_observation(_make_metar(temp=60.0))
        assert result is not None
        assert result["temp_c"] == 60.0

    def test_just_outside_min_is_none(self) -> None:
        from tradewinds.weather._awc import awc_to_observation

        result = awc_to_observation(_make_metar(temp=-90.1))
        assert result is not None
        assert result["temp_c"] is None

    def test_just_outside_max_is_none(self) -> None:
        from tradewinds.weather._awc import awc_to_observation

        result = awc_to_observation(_make_metar(temp=60.1))
        assert result is not None
        assert result["temp_c"] is None

    def test_tgroup_outside_bounds_is_none(self) -> None:
        """T-group value of 65.0°C gets bounded to None (max=60°C)."""
        from tradewinds.weather._awc import awc_to_observation

        # T06500000 → sign=0, val=650/10=65.0°C (above 60°C max)
        raw = "METAR KJFK RMK AO2 T06500000"
        result = awc_to_observation(_make_metar(temp=60.0, rawOb=raw))
        assert result is not None
        # T-group overrides body, but 65.0°C > 60°C max → None
        assert result["temp_c"] is None
        assert result["temp_f"] is None

    def test_extreme_dewpoint_preserves_none_f(self) -> None:
        """When dewpoint_c is bounded to None, dewpoint_f is also None."""
        from tradewinds.weather._awc import awc_to_observation

        result = awc_to_observation(_make_metar(dewp=100.0))
        assert result is not None
        assert result["dewpoint_c"] is None
        assert result["dewpoint_f"] is None

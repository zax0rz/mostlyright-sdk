"""Tests for mostlyright._internal._convert — unit conversions with NO rounding."""

from __future__ import annotations

import importlib.util
import math

import pytest


# Wave 2 lifted `mostlyright._internal.models`, so the previously-skipped
# TestConvertObservation class now runs. The skipif gate stays defensive so
# this file survives a hypothetical drop of the models package; if models is
# present (which it always should be now), the suite is active.
def _has_tw_models() -> bool:
    try:
        return importlib.util.find_spec("mostlyright._internal.models") is not None
    except ModuleNotFoundError:
        return False


_HAS_MOSTLYRIGHT_MODELS = _has_tw_models()


class TestCelsiusToFahrenheit:
    """celsius_to_fahrenheit: C * 9/5 + 32, float64 precision, no rounding."""

    def test_zero_celsius(self) -> None:
        from mostlyright._internal._convert import celsius_to_fahrenheit

        assert celsius_to_fahrenheit(0.0) == 32.0

    def test_hundred_celsius(self) -> None:
        from mostlyright._internal._convert import celsius_to_fahrenheit

        assert celsius_to_fahrenheit(100.0) == 212.0

    def test_negative(self) -> None:
        from mostlyright._internal._convert import celsius_to_fahrenheit

        assert celsius_to_fahrenheit(-40.0) == -40.0

    def test_preserves_float64_precision_no_rounding(self) -> None:
        """T-group 15.6C should produce 60.08, NOT 60.1 (old _go_round bug)."""
        from mostlyright._internal._convert import celsius_to_fahrenheit

        result = celsius_to_fahrenheit(15.6)
        # Must be the raw float64 result: 15.6 * 9/5 + 32
        expected = 15.6 * 9 / 5 + 32
        assert result == expected
        # Specifically: must NOT be 60.1 (the rounded value)
        assert result != 60.1

    def test_t_group_negative(self) -> None:
        """T-group -5.6C → raw float64 conversion."""
        from mostlyright._internal._convert import celsius_to_fahrenheit

        result = celsius_to_fahrenheit(-5.6)
        expected = -5.6 * 9 / 5 + 32
        assert result == expected

    def test_none_returns_none(self) -> None:
        from mostlyright._internal._convert import celsius_to_fahrenheit

        assert celsius_to_fahrenheit(None) is None

    def test_nan_returns_none(self) -> None:
        from mostlyright._internal._convert import celsius_to_fahrenheit

        assert celsius_to_fahrenheit(float("nan")) is None

    def test_inf_returns_none(self) -> None:
        from mostlyright._internal._convert import celsius_to_fahrenheit

        assert celsius_to_fahrenheit(float("inf")) is None


class TestHpaToInhg:
    """hpa_to_inhg: hPa * 0.0295299875, float64 precision, no rounding."""

    def test_standard_pressure(self) -> None:
        from mostlyright._internal._convert import hpa_to_inhg

        result = hpa_to_inhg(1013.25)
        expected = 1013.25 * 0.0295299875
        assert result == expected

    def test_preserves_float64_no_rounding(self) -> None:
        """Must NOT round to 2 decimal places like _safe_altim did."""
        from mostlyright._internal._convert import hpa_to_inhg

        result = hpa_to_inhg(1015.0)
        expected = 1015.0 * 0.0295299875
        assert result == expected
        # Must be pure multiplication, not rounded
        assert result == 1015.0 * 0.0295299875

    def test_none_returns_none(self) -> None:
        from mostlyright._internal._convert import hpa_to_inhg

        assert hpa_to_inhg(None) is None

    def test_nan_returns_none(self) -> None:
        from mostlyright._internal._convert import hpa_to_inhg

        assert hpa_to_inhg(float("nan")) is None


class TestComputeRelativeHumidity:
    """compute_relative_humidity: Magnus formula, no rounding, clamped [0,100]."""

    def test_equal_temp_dewpoint_gives_100(self) -> None:
        from mostlyright._internal._convert import compute_relative_humidity

        result = compute_relative_humidity(20.0, 20.0)
        assert result == 100.0

    def test_typical_values(self) -> None:
        """20C temp, 10C dewpoint → ~52% RH (Magnus approximation)."""
        from mostlyright._internal._convert import compute_relative_humidity

        result = compute_relative_humidity(20.0, 10.0)
        assert result is not None
        assert 50.0 < result < 55.0

    def test_no_rounding_artifacts(self) -> None:
        """Result must be raw float64, not rounded to 1 decimal."""
        from mostlyright._internal._convert import compute_relative_humidity

        result = compute_relative_humidity(25.0, 15.0)
        assert result is not None
        # Raw Magnus formula result — should have many decimal places
        a, b = 17.625, 243.04
        expected = 100.0 * math.exp((a * 15.0) / (b + 15.0)) / math.exp((a * 25.0) / (b + 25.0))
        assert result == expected

    def test_none_temp_returns_none(self) -> None:
        from mostlyright._internal._convert import compute_relative_humidity

        assert compute_relative_humidity(None, 10.0) is None

    def test_none_dewpoint_returns_none(self) -> None:
        from mostlyright._internal._convert import compute_relative_humidity

        assert compute_relative_humidity(20.0, None) is None

    def test_clamped_to_100(self) -> None:
        """Dewpoint > temp (physically impossible but handle gracefully)."""
        from mostlyright._internal._convert import compute_relative_humidity

        result = compute_relative_humidity(10.0, 20.0)
        assert result is not None
        assert result == 100.0


class TestComputeFeelsLike:
    """compute_feels_like: full NWS algorithm, no rounding."""

    def test_mild_temperature_returns_temp(self) -> None:
        """Between 50-80F with low wind → returns raw temp."""
        from mostlyright._internal._convert import compute_feels_like

        result = compute_feels_like(65.0, 5, 50.0)
        assert result == 65.0

    def test_wind_chill_below_50f(self) -> None:
        """30F with 15kt wind → wind chill applies."""
        from mostlyright._internal._convert import compute_feels_like

        result = compute_feels_like(30.0, 15, 50.0)
        assert result is not None
        assert result < 30.0  # Wind chill makes it feel colder

    def test_wind_chill_no_rounding(self) -> None:
        """Wind chill result must be raw float64."""
        from mostlyright._internal._convert import compute_feels_like

        result = compute_feels_like(30.0, 15, 50.0)
        assert result is not None
        # Manually compute expected
        w_mph = 15 * 1.15078
        expected = 35.74 + 0.6215 * 30.0 - 35.75 * (w_mph**0.16) + 0.4275 * 30.0 * (w_mph**0.16)
        assert result == expected

    def test_heat_index_above_80f(self) -> None:
        """95F with high humidity → heat index applies."""
        from mostlyright._internal._convert import compute_feels_like

        result = compute_feels_like(95.0, 5, 80.0)
        assert result is not None
        assert result > 95.0  # Heat index makes it feel hotter

    def test_none_temp_returns_none(self) -> None:
        from mostlyright._internal._convert import compute_feels_like

        assert compute_feels_like(None, 10, 50.0) is None

    def test_none_wind_uses_zero(self) -> None:
        """Null wind → treated as calm (0 mph)."""
        from mostlyright._internal._convert import compute_feels_like

        result = compute_feels_like(65.0, None, 50.0)
        assert result == 65.0

    def test_none_rh_skips_heat_index(self) -> None:
        """Above 80F but no RH → returns raw temp."""
        from mostlyright._internal._convert import compute_feels_like

        result = compute_feels_like(85.0, 5, None)
        assert result == 85.0


# ===================================================================
# Sprint 2f Session 3: New conversion functions
# ===================================================================


class TestKtToMs:
    """kt_to_ms: knots × (1852/3600) = m/s. No rounding."""  # noqa: RUF002

    def test_known_value(self) -> None:
        from mostlyright._internal._convert import kt_to_ms

        result = kt_to_ms(10)
        assert result == 10 * (1852.0 / 3600.0)

    def test_zero(self) -> None:
        from mostlyright._internal._convert import kt_to_ms

        assert kt_to_ms(0) == 0.0

    def test_none_returns_none(self) -> None:
        from mostlyright._internal._convert import kt_to_ms

        assert kt_to_ms(None) is None

    def test_float_input(self) -> None:
        from mostlyright._internal._convert import kt_to_ms

        result = kt_to_ms(8.5)
        assert result == 8.5 * (1852.0 / 3600.0)


class TestKtToMph:
    """kt_to_mph: knots × 1.15078 = mph. No rounding."""  # noqa: RUF002

    def test_known_value(self) -> None:
        from mostlyright._internal._convert import kt_to_mph

        result = kt_to_mph(10)
        assert result == 10 * 1.15078

    def test_zero(self) -> None:
        from mostlyright._internal._convert import kt_to_mph

        assert kt_to_mph(0) == 0.0

    def test_none_returns_none(self) -> None:
        from mostlyright._internal._convert import kt_to_mph

        assert kt_to_mph(None) is None


class TestMiToKm:
    """mi_to_km: statute miles × 1.609344 = km. No rounding."""  # noqa: RUF002

    def test_known_value(self) -> None:
        from mostlyright._internal._convert import mi_to_km

        result = mi_to_km(10.0)
        assert result == 10.0 * 1.609344

    def test_one_mile(self) -> None:
        from mostlyright._internal._convert import mi_to_km

        assert mi_to_km(1.0) == 1.609344

    def test_none_returns_none(self) -> None:
        from mostlyright._internal._convert import mi_to_km

        assert mi_to_km(None) is None


class TestInchesToMm:
    """inches_to_mm: inches × 25.4 = mm. Exact conversion. No rounding."""  # noqa: RUF002

    def test_one_inch(self) -> None:
        from mostlyright._internal._convert import inches_to_mm

        assert inches_to_mm(1.0) == 25.4

    def test_fractional(self) -> None:
        from mostlyright._internal._convert import inches_to_mm

        result = inches_to_mm(0.05)
        assert result == 0.05 * 25.4

    def test_none_returns_none(self) -> None:
        from mostlyright._internal._convert import inches_to_mm

        assert inches_to_mm(None) is None


@pytest.mark.skipif(
    not _HAS_MOSTLYRIGHT_MODELS,
    reason="mostlyright._internal.models not available — should never trigger "
    "after Wave 2 lifted the models package.",
)
class TestConvertObservation:
    """convert_observation: returns NEW Observation with converted fields."""

    def _make_obs(self):
        from mostlyright._internal.models import Observation

        return Observation(
            station_code="NYC",
            observed_at="2025-01-15T12:00:00Z",
            observation_type="METAR",
            source="awc",
            temp_c=15.0,
            dewpoint_c=5.0,
            temp_f=59.0,
            dewpoint_f=41.0,
            wind_dir_degrees=270,
            wind_speed_kt=10,
            wind_gust_kt=20,
            altimeter_inhg=29.92,
            sea_level_pressure_mb=1013.25,
            sky_cover_1="SCT",
            sky_base_1_ft=4500,
            sky_cover_2=None,
            sky_base_2_ft=None,
            sky_cover_3=None,
            sky_base_3_ft=None,
            sky_cover_4=None,
            sky_base_4_ft=None,
            visibility_miles=10.0,
            weather_codes=None,
            precip_1hr_inches=0.05,
            peak_wind_gust_kt=25,
            peak_wind_dir=290,
            peak_wind_time="1400",
            snow_depth_inches=4.0,
            qc_field=0,
            raw_metar="KNYC 151200Z 27010KT 10SM SCT045 15/05 A2992",
        )

    def test_raw_is_noop(self) -> None:
        from mostlyright._internal._convert import convert_observation

        obs = self._make_obs()
        result = convert_observation(obs, "raw")
        assert result is obs

    def test_metric_converts_wind_to_ms(self) -> None:
        from mostlyright._internal._convert import convert_observation

        obs = self._make_obs()
        result = convert_observation(obs, "metric")
        assert result.wind_speed_kt == 10 * (1852.0 / 3600.0)
        assert result.wind_gust_kt == 20 * (1852.0 / 3600.0)
        assert result.peak_wind_gust_kt == 25 * (1852.0 / 3600.0)

    def test_metric_converts_visibility_to_km(self) -> None:
        from mostlyright._internal._convert import convert_observation

        obs = self._make_obs()
        result = convert_observation(obs, "metric")
        assert result.visibility_miles == 10.0 * 1.609344

    def test_metric_converts_precip_to_mm(self) -> None:
        from mostlyright._internal._convert import convert_observation

        obs = self._make_obs()
        result = convert_observation(obs, "metric")
        assert result.precip_1hr_inches == 0.05 * 25.4
        assert result.snow_depth_inches == 4.0 * 25.4

    def test_metric_leaves_temp_untouched(self) -> None:
        from mostlyright._internal._convert import convert_observation

        obs = self._make_obs()
        result = convert_observation(obs, "metric")
        assert result.temp_c == 15.0
        assert result.temp_f == 59.0
        assert result.dewpoint_c == 5.0
        assert result.dewpoint_f == 41.0

    def test_metric_leaves_pressure_untouched(self) -> None:
        from mostlyright._internal._convert import convert_observation

        obs = self._make_obs()
        result = convert_observation(obs, "metric")
        assert result.altimeter_inhg == 29.92
        assert result.sea_level_pressure_mb == 1013.25

    def test_imperial_converts_wind_to_mph(self) -> None:
        from mostlyright._internal._convert import convert_observation

        obs = self._make_obs()
        result = convert_observation(obs, "imperial")
        assert result.wind_speed_kt == 10 * 1.15078
        assert result.wind_gust_kt == 20 * 1.15078
        assert result.peak_wind_gust_kt == 25 * 1.15078

    def test_imperial_leaves_visibility_as_miles(self) -> None:
        from mostlyright._internal._convert import convert_observation

        obs = self._make_obs()
        result = convert_observation(obs, "imperial")
        assert result.visibility_miles == 10.0

    def test_imperial_leaves_precip_as_inches(self) -> None:
        from mostlyright._internal._convert import convert_observation

        obs = self._make_obs()
        result = convert_observation(obs, "imperial")
        assert result.precip_1hr_inches == 0.05
        assert result.snow_depth_inches == 4.0

    def test_returns_new_observation(self) -> None:
        from mostlyright._internal._convert import convert_observation

        obs = self._make_obs()
        result = convert_observation(obs, "metric")
        assert result is not obs

    def test_unknown_units_raises_valueerror(self) -> None:
        from mostlyright._internal._convert import convert_observation

        obs = self._make_obs()
        with pytest.raises(ValueError, match="Unrecognized"):
            convert_observation(obs, "celsius")

    def test_none_fields_stay_none(self) -> None:
        from mostlyright._internal._convert import convert_observation
        from mostlyright._internal.models import Observation

        obs = Observation(
            station_code="NYC",
            observed_at="2025-01-15T12:00:00Z",
            observation_type="METAR",
            source="awc",
            temp_c=15.0,
            dewpoint_c=5.0,
            temp_f=59.0,
            dewpoint_f=41.0,
            wind_dir_degrees=270,
            wind_speed_kt=None,
            wind_gust_kt=None,
            altimeter_inhg=29.92,
            sea_level_pressure_mb=1013.25,
            sky_cover_1=None,
            sky_base_1_ft=None,
            sky_cover_2=None,
            sky_base_2_ft=None,
            sky_cover_3=None,
            sky_base_3_ft=None,
            sky_cover_4=None,
            sky_base_4_ft=None,
            visibility_miles=None,
            weather_codes=None,
            precip_1hr_inches=None,
            peak_wind_gust_kt=None,
            peak_wind_dir=None,
            peak_wind_time=None,
            snow_depth_inches=None,
            qc_field=0,
            raw_metar="KNYC 151200Z",
        )
        result = convert_observation(obs, "metric")
        assert result.wind_speed_kt is None
        assert result.visibility_miles is None
        assert result.precip_1hr_inches is None
        assert result.snow_depth_inches is None

"""Tests for mostlyright._internal.models.observation — frozen dataclass with computed fields."""

from __future__ import annotations

import pytest


class TestObservationFields:
    """Observation dataclass has all 30 storage fields + 2 computed."""

    def test_all_storage_fields_present(self) -> None:
        from mostlyright._internal.models.observation import Observation

        obs = Observation(
            station_code="JFK",
            observed_at="2025-01-15T12:00:00Z",
            observation_type="METAR",
            source="awc",
            temp_c=15.6,
            dewpoint_c=12.8,
            temp_f=60.08,
            dewpoint_f=55.04,
            wind_dir_degrees=270,
            wind_speed_kt=10,
            wind_gust_kt=None,
            altimeter_inhg=29.92,
            sea_level_pressure_mb=1013.2,
            sky_cover_1="SCT",
            sky_base_1_ft=3500,
            sky_cover_2="BKN",
            sky_base_2_ft=8000,
            sky_cover_3=None,
            sky_base_3_ft=None,
            sky_cover_4=None,
            sky_base_4_ft=None,
            visibility_miles=10.0,
            weather_codes=None,
            precip_1hr_inches=None,
            peak_wind_gust_kt=None,
            peak_wind_dir=None,
            peak_wind_time=None,
            snow_depth_inches=None,
            qc_field=None,
            raw_metar="METAR KJFK 151200Z 27010KT 10SM SCT035 BKN080 16/13 A2992",
        )
        assert obs.station_code == "JFK"
        assert obs.source == "awc"
        assert obs.temp_c == 15.6
        assert obs.dewpoint_c == 12.8
        assert obs.qc_field is None

    def test_new_fields_temp_c_dewpoint_c_qc_field(self) -> None:
        """The 3 new additive fields exist on the dataclass."""
        from mostlyright._internal.models.observation import Observation

        obs = Observation(
            station_code="JFK",
            observed_at="2025-01-15T12:00:00Z",
            observation_type="METAR",
            source="awc",
            temp_c=-5.6,
            dewpoint_c=-8.3,
            temp_f=21.92,
            dewpoint_f=17.06,
            wind_dir_degrees=None,
            wind_speed_kt=None,
            wind_gust_kt=None,
            altimeter_inhg=None,
            sea_level_pressure_mb=None,
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
            qc_field=6,
            raw_metar=None,
        )
        assert obs.temp_c == -5.6
        assert obs.dewpoint_c == -8.3
        assert obs.qc_field == 6


class TestObservationComputed:
    """Computed fields: relative_humidity and feels_like_f derived at load time."""

    def test_relative_humidity_computed(self) -> None:
        from mostlyright._internal.models.observation import Observation

        obs = Observation(
            station_code="JFK",
            observed_at="2025-01-15T12:00:00Z",
            observation_type="METAR",
            source="awc",
            temp_c=20.0,
            dewpoint_c=10.0,
            temp_f=68.0,
            dewpoint_f=50.0,
            wind_dir_degrees=None,
            wind_speed_kt=10,
            wind_gust_kt=None,
            altimeter_inhg=None,
            sea_level_pressure_mb=None,
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
            qc_field=None,
            raw_metar=None,
        )
        assert obs.relative_humidity is not None
        assert 50.0 < obs.relative_humidity < 55.0

    def test_feels_like_computed(self) -> None:
        from mostlyright._internal.models.observation import Observation

        obs = Observation(
            station_code="JFK",
            observed_at="2025-01-15T12:00:00Z",
            observation_type="METAR",
            source="awc",
            temp_c=-1.1,
            dewpoint_c=-5.0,
            temp_f=30.0,
            dewpoint_f=23.0,
            wind_dir_degrees=270,
            wind_speed_kt=15,
            wind_gust_kt=None,
            altimeter_inhg=None,
            sea_level_pressure_mb=None,
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
            qc_field=None,
            raw_metar=None,
        )
        assert obs.feels_like_f is not None
        assert obs.feels_like_f < 30.0  # Wind chill

    def test_computed_fields_none_when_inputs_missing(self) -> None:
        from mostlyright._internal.models.observation import Observation

        obs = Observation(
            station_code="JFK",
            observed_at="2025-01-15T12:00:00Z",
            observation_type="METAR",
            source="awc",
            temp_c=None,
            dewpoint_c=None,
            temp_f=None,
            dewpoint_f=None,
            wind_dir_degrees=None,
            wind_speed_kt=None,
            wind_gust_kt=None,
            altimeter_inhg=None,
            sea_level_pressure_mb=None,
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
            qc_field=None,
            raw_metar=None,
        )
        assert obs.relative_humidity is None
        assert obs.feels_like_f is None


class TestObservationImmutability:
    """Observation must be frozen (immutable)."""

    def test_frozen_cannot_set_field(self) -> None:
        from mostlyright._internal.models.observation import Observation

        obs = Observation(
            station_code="JFK",
            observed_at="2025-01-15T12:00:00Z",
            observation_type="METAR",
            source="awc",
            temp_c=20.0,
            dewpoint_c=10.0,
            temp_f=68.0,
            dewpoint_f=50.0,
            wind_dir_degrees=None,
            wind_speed_kt=None,
            wind_gust_kt=None,
            altimeter_inhg=None,
            sea_level_pressure_mb=None,
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
            qc_field=None,
            raw_metar=None,
        )
        with pytest.raises(AttributeError):
            obs.temp_f = 99.0  # type: ignore[misc]


class TestObservationDictAccess:
    """Observation supports dict-style access for backward compat."""

    def test_getitem(self) -> None:
        from mostlyright._internal.models.observation import Observation

        obs = Observation(
            station_code="JFK",
            observed_at="2025-01-15T12:00:00Z",
            observation_type="METAR",
            source="awc",
            temp_c=20.0,
            dewpoint_c=10.0,
            temp_f=68.0,
            dewpoint_f=50.0,
            wind_dir_degrees=None,
            wind_speed_kt=None,
            wind_gust_kt=None,
            altimeter_inhg=None,
            sea_level_pressure_mb=None,
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
            qc_field=None,
            raw_metar=None,
        )
        assert obs["station_code"] == "JFK"
        assert obs["temp_f"] == 68.0

    def test_to_dict(self) -> None:
        from mostlyright._internal.models.observation import Observation

        obs = Observation(
            station_code="JFK",
            observed_at="2025-01-15T12:00:00Z",
            observation_type="METAR",
            source="awc",
            temp_c=20.0,
            dewpoint_c=10.0,
            temp_f=68.0,
            dewpoint_f=50.0,
            wind_dir_degrees=None,
            wind_speed_kt=None,
            wind_gust_kt=None,
            altimeter_inhg=None,
            sea_level_pressure_mb=None,
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
            qc_field=None,
            raw_metar=None,
        )
        d = obs.to_dict()
        assert isinstance(d, dict)
        assert d["station_code"] == "JFK"
        # Computed fields should be in the dict too
        assert "relative_humidity" in d
        assert "feels_like_f" in d

    def test_to_storage_dict_excludes_computed(self) -> None:
        from mostlyright._internal.models.observation import Observation

        obs = Observation(
            station_code="JFK",
            observed_at="2025-01-15T12:00:00Z",
            observation_type="METAR",
            source="awc",
            temp_c=20.0,
            dewpoint_c=10.0,
            temp_f=68.0,
            dewpoint_f=50.0,
            wind_dir_degrees=None,
            wind_speed_kt=None,
            wind_gust_kt=None,
            altimeter_inhg=None,
            sea_level_pressure_mb=None,
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
            qc_field=None,
            raw_metar=None,
        )
        sd = obs.to_storage_dict()
        assert "relative_humidity" not in sd
        assert "feels_like_f" not in sd
        assert sd["station_code"] == "JFK"
        assert len(sd) == 30


class TestObservationFromDict:
    """from_dict validates required fields."""

    def test_from_dict_missing_required_raises(self) -> None:
        from mostlyright._internal.models.observation import Observation

        with pytest.raises(ValueError, match="missing required fields"):
            Observation.from_dict({"temp_c": 20.0})

    def test_from_dict_valid(self) -> None:
        from mostlyright._internal.models.observation import Observation

        d = {
            "station_code": "JFK",
            "observed_at": "2025-01-15T12:00:00Z",
            "observation_type": "METAR",
            "source": "awc",
            "temp_c": 20.0,
            "dewpoint_c": 10.0,
            "temp_f": 68.0,
            "dewpoint_f": 50.0,
        }
        obs = Observation.from_dict(d)
        assert obs.station_code == "JFK"
        assert obs.relative_humidity is not None

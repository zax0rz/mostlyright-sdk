"""Phase 20 OM-02: StationForecastSchema unification + ForecastSchema alias."""

from __future__ import annotations

from mostlyright.core.schema import Schema
from mostlyright.core.schemas import SCHEMA_REGISTRY
from mostlyright.core.schemas.forecast import ForecastSchema, StationForecastSchema


def test_station_forecast_schema_id() -> None:
    assert StationForecastSchema.schema_id == "schema.forecast.station.v1"


def test_station_forecast_schema_is_schema_subclass() -> None:
    assert issubclass(StationForecastSchema, Schema)


def test_station_forecast_schema_column_count() -> None:
    # 7 required (identity + retrieved_at) + 6 IEM MOS core nullable + 13 OM
    # extras nullable = 26. Plan brief said 25 with "12 OM extras" but the
    # expected_extras test below requires 13 distinct OM extras, so the
    # actual count reconciles to 26.
    assert len(StationForecastSchema.COLUMNS) == 26


def test_station_forecast_schema_required_columns() -> None:
    required = {c.name for c in StationForecastSchema.COLUMNS if not c.nullable}
    # issued_at is nullable per Phase 20 PLAN-11 review (Python Architect
    # HIGH #1): open_meteo.seamless rows carry null issued_at by design;
    # LeakageDetector + assert_issued_at_populated() are the runtime
    # gates.
    assert required == {
        "station",
        "valid_at",
        "forecast_hour",
        "model",
        "source",
        "retrieved_at",
    }


def test_station_forecast_schema_nullable_columns() -> None:
    nullable = {c.name for c in StationForecastSchema.COLUMNS if c.nullable}
    assert len(nullable) == 20
    # IEM MOS core (now nullable in unified schema):
    assert "temp_c" in nullable
    assert "dew_point_c" in nullable
    assert "wind_speed_ms" in nullable
    assert "wind_dir_deg" in nullable
    assert "precip_probability" in nullable
    assert "sky_cover_pct" in nullable


def test_station_forecast_schema_open_meteo_extras_present() -> None:
    names = {c.name for c in StationForecastSchema.COLUMNS}
    expected_extras = {
        "apparent_temp_c",
        "shortwave_radiation_wm2",
        "direct_radiation_wm2",
        "cape_jkg",
        "precipitation_mm",
        "cloud_cover_pct",
        "surface_pressure_hpa",
        "pressure_msl_hpa",
        "freezing_level_m",
        "snow_depth_m",
        "visibility_m",
        "wind_gusts_ms",
        "weather_code",
    }
    assert expected_extras.issubset(names)


def test_forecast_schema_is_alias_of_station_forecast_schema() -> None:
    assert issubclass(ForecastSchema, StationForecastSchema)
    assert ForecastSchema.schema_id == "schema.forecast.iem_mos.v1"


def test_forecast_schema_columns_are_same_as_station_forecast_schema() -> None:
    # Same column list — back-compat alias
    assert ForecastSchema.COLUMNS == StationForecastSchema.COLUMNS


def test_both_schema_ids_registered() -> None:
    assert "schema.forecast.station.v1" in SCHEMA_REGISTRY
    assert "schema.forecast.iem_mos.v1" in SCHEMA_REGISTRY
    station_cols = SCHEMA_REGISTRY["schema.forecast.station.v1"].COLUMNS
    iem_mos_cols = SCHEMA_REGISTRY["schema.forecast.iem_mos.v1"].COLUMNS
    assert station_cols == iem_mos_cols


def test_imperial_renames_includes_open_meteo_extras() -> None:
    renames = StationForecastSchema.IMPERIAL_RENAMES
    assert renames["temp_c"] == "temp_F"
    assert renames["dew_point_c"] == "dew_point_F"
    assert renames["apparent_temp_c"] == "apparent_temp_F"
    assert renames["wind_speed_ms"] == "wind_speed_kt"
    assert renames["wind_gusts_ms"] == "wind_gusts_kt"

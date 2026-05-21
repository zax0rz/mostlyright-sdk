"""Contract tests for ForecastSchema.

Expected column set is a fixture list transcribed directly from
``docs/design.md`` §A 'Forecasts schema' (the deliberate subset of
mostlyright's FORECAST_FIELDS documented in §X).
"""

from __future__ import annotations

import pytest
from tradewinds._v02.schemas import ForecastSchema

# (name, dtype, units, nullable, enum_values) per docs/design.md §A.
_EXPECTED: list[tuple[str, str, str | None, bool, tuple[str, ...] | None]] = [
    ("station", "string", None, False, None),
    ("issued_at", "timestamp_utc", None, False, None),
    ("valid_at", "timestamp_utc", None, False, None),
    ("forecast_hour", "int64", "hours", False, None),
    ("model", "string", None, False, None),
    ("temp_c", "float64", "celsius", True, None),
    ("dew_point_c", "float64", "celsius", True, None),
    ("wind_speed_ms", "float64", "m/s", True, None),
    ("wind_dir_deg", "int64", "degrees", True, None),
    ("precip_probability", "float64", "probability", True, None),
    ("sky_cover_pct", "int64", "percent", True, None),
]


class TestForecastSchemaContract:
    def test_schema_id(self) -> None:
        assert ForecastSchema.schema_id == "schema.forecast.iem_mos.v1"

    def test_column_count_matches_design_doc(self) -> None:
        assert len(ForecastSchema.COLUMNS) == len(_EXPECTED) == 11

    def test_column_names_in_order(self) -> None:
        assert ForecastSchema.column_names("metric") == [
            row[0] for row in _EXPECTED
        ]

    @pytest.mark.parametrize(
        ("name", "dtype", "units", "nullable", "enum_values"), _EXPECTED
    )
    def test_each_column_spec_exact(
        self,
        name: str,
        dtype: str,
        units: str | None,
        nullable: bool,
        enum_values: tuple[str, ...] | None,
    ) -> None:
        spec = ForecastSchema.column(name)
        assert spec.dtype == dtype, name
        assert spec.units == units, name
        assert spec.nullable == nullable, name
        assert spec.enum_values == enum_values, name

    def test_required_columns_are_non_nullable(self) -> None:
        # Temporal + identity columns are required; numeric forecast values
        # are nullable.
        for name in ("station", "issued_at", "valid_at", "forecast_hour", "model"):
            assert ForecastSchema.column(name).nullable is False

    def test_documented_subset_omits_full_mostlyright_columns(self) -> None:
        # Sanity check: the columns §X explicitly says are dropped MUST NOT
        # appear in the v0.1 contract.
        dropped = {
            "qpf_6hr_in",
            "pop_6hr_pct",
            "cloud_cover_code",
            "ceiling_cat",
            "visibility_cat",
            "precip_type",
            "thunder_prob_12hr",
        }
        names = {c.name for c in ForecastSchema.COLUMNS}
        assert names.isdisjoint(dropped)

    def test_imperial_renames_apply_to_temperature_and_wind_speed(self) -> None:
        # Forecast does not declare event_time (event_time = valid_at is
        # derived); the imperial-mode rename map only covers the convertible
        # numeric columns the schema actually carries.
        assert ForecastSchema.IMPERIAL_RENAMES == {
            "temp_c": "temp_F",
            "dew_point_c": "dew_point_F",
            "wind_speed_ms": "wind_speed_kt",
        }

    def test_imperial_mode_column_names(self) -> None:
        imperial = ForecastSchema.column_names("imperial")
        assert imperial == [
            "station",
            "issued_at",
            "valid_at",
            "forecast_hour",
            "model",
            "temp_F",
            "dew_point_F",
            "wind_speed_kt",
            "wind_dir_deg",
            "precip_probability",
            "sky_cover_pct",
        ]

    def test_no_unexpected_columns(self) -> None:
        names = {c.name for c in ForecastSchema.COLUMNS}
        expected_names = {row[0] for row in _EXPECTED}
        assert names == expected_names

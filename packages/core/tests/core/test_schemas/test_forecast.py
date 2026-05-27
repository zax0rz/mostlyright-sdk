"""Contract tests for ForecastSchema (back-compat alias).

Phase 20 OM-02 unified the schema: ``ForecastSchema`` is now a back-compat
alias subclass of :class:`StationForecastSchema` (``schema.forecast.station.v1``)
that overrides ``schema_id`` to ``schema.forecast.iem_mos.v1``. The legacy
11-column shape is preserved as a subset within the unified 26-column
COLUMNS list — IEM MOS rows simply leave the 13 Open-Meteo extras null and
the IEM MOS core columns are now nullable (Open-Meteo may not provide all
of them). See ``docs/design.md`` §A 'Forecasts schema' and
``20-CONTEXT.md`` §D-03 for the design rationale.
"""

from __future__ import annotations

import pytest
from mostlyright.core.schemas import ForecastSchema, StationForecastSchema

# IEM MOS columns that MUST remain present and identifiable in the unified
# schema. Dtype + units match the legacy contract because Phase 17 parity
# fixtures depend on these column-level invariants.
_IEM_MOS_COLUMNS: list[tuple[str, str, str | None, bool, tuple[str, ...] | None]] = [
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

    def test_is_alias_of_station_forecast_schema(self) -> None:
        # Phase 20 OM-02: alias preserves column-list identity.
        assert issubclass(ForecastSchema, StationForecastSchema)
        assert ForecastSchema.COLUMNS == StationForecastSchema.COLUMNS

    def test_unified_column_count(self) -> None:
        # Phase 20 OM-02: unified schema is 26 columns (7 required identity +
        # 6 IEM MOS core nullable + 13 Open-Meteo extras nullable).
        assert len(ForecastSchema.COLUMNS) == 26

    @pytest.mark.parametrize(
        ("name", "dtype", "units", "nullable", "enum_values"), _IEM_MOS_COLUMNS
    )
    def test_iem_mos_column_spec_preserved(
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
        # Temporal + identity columns are required. Phase 20 OM-02 adds
        # ``source`` and ``retrieved_at`` as required for source identity
        # and provenance.
        for name in (
            "station",
            "issued_at",
            "valid_at",
            "forecast_hour",
            "model",
            "source",
            "retrieved_at",
        ):
            assert ForecastSchema.column(name).nullable is False

    def test_documented_subset_omits_full_mostlyright_columns(self) -> None:
        # The columns §X explicitly says are dropped MUST NOT appear in the
        # v0.1 contract (still true under the unified schema — those drops
        # were intentional and Open-Meteo does not re-introduce them).
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

    def test_imperial_renames_include_open_meteo_extras(self) -> None:
        # Phase 20 OM-02 extends IMPERIAL_RENAMES with apparent_temp_c and
        # wind_gusts_ms (the Open-Meteo convertible numeric extras). All
        # legacy entries are preserved.
        assert ForecastSchema.IMPERIAL_RENAMES == {
            "temp_c": "temp_F",
            "dew_point_c": "dew_point_F",
            "apparent_temp_c": "apparent_temp_F",
            "wind_speed_ms": "wind_speed_kt",
            "wind_gusts_ms": "wind_gusts_kt",
        }

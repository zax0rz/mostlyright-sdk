"""Contract tests for SettlementSchema.

Expected column set is a fixture list transcribed directly from
``docs/design.md`` §BB.3 (which supersedes the §A settlement-schema
table). Verifies ``station_tz`` is present and required.
"""

from __future__ import annotations

import pytest

from tradewinds._v02.schemas import SettlementSchema


# (name, dtype, units, nullable, enum_values) per docs/design.md §BB.3.
_EXPECTED: list[tuple[str, str, str | None, bool, tuple[str, ...] | None]] = [
    ("station", "string", None, False, None),
    ("station_tz", "string", None, False, None),
    ("observation_date", "date", None, False, None),
    ("event_time", "timestamp_utc", None, False, None),
    ("product_release_time", "timestamp_utc", None, False, None),
    (
        "report_type",
        "enum",
        None,
        False,
        ("preliminary", "final", "correction"),
    ),
    ("temp_max_F", "float64", "fahrenheit", True, None),
    ("temp_min_F", "float64", "fahrenheit", True, None),
    ("precipitation_in", "float64", "inches", True, None),
    ("snowfall_in", "float64", "inches", True, None),
]


class TestSettlementSchemaContract:
    def test_schema_id(self) -> None:
        assert SettlementSchema.schema_id == "schema.settlement.cli.v1"

    def test_column_count_matches_design_doc(self) -> None:
        assert len(SettlementSchema.COLUMNS) == len(_EXPECTED) == 10

    def test_column_names_in_order(self) -> None:
        assert SettlementSchema.column_names("metric") == [
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
        spec = SettlementSchema.column(name)
        assert spec.dtype == dtype, name
        assert spec.units == units, name
        assert spec.nullable == nullable, name
        assert spec.enum_values == enum_values, name

    def test_station_tz_present_and_required(self) -> None:
        # §BB.3: station_tz is required for local-climate-day semantics.
        spec = SettlementSchema.column("station_tz")
        assert spec.dtype == "string"
        assert spec.nullable is False
        # Documentation notes reference §U so future readers can find context.
        assert "America/Chicago" in spec.notes or "IANA" in spec.notes

    def test_observation_date_is_date_not_timestamp(self) -> None:
        # §U/§BB.3: observation_date is a local-calendar date with no
        # timezone applied to the date itself; event_time carries the UTC
        # conversion.
        assert SettlementSchema.column("observation_date").dtype == "date"
        assert (
            SettlementSchema.column("event_time").dtype == "timestamp_utc"
        )

    def test_required_columns_are_non_nullable(self) -> None:
        # Everything except the numeric daily values is required (§BB.3).
        required = [
            "station",
            "station_tz",
            "observation_date",
            "event_time",
            "product_release_time",
            "report_type",
        ]
        for name in required:
            assert SettlementSchema.column(name).nullable is False, name

    def test_numeric_values_are_nullable(self) -> None:
        for name in (
            "temp_max_F",
            "temp_min_F",
            "precipitation_in",
            "snowfall_in",
        ):
            assert SettlementSchema.column(name).nullable is True, name

    def test_no_imperial_rename_map(self) -> None:
        # CLI settlement IS Fahrenheit/inches; no rename map applies.
        assert SettlementSchema.IMPERIAL_RENAMES == {}
        assert SettlementSchema.column_names(
            "imperial"
        ) == SettlementSchema.column_names("metric")

    def test_report_type_enum_priority_order(self) -> None:
        # §A: dedup priority is preliminary < final < correction; the
        # enum_values tuple preserves this order so the priority logic in
        # the eventual adapter can rely on declaration order.
        spec = SettlementSchema.column("report_type")
        assert spec.enum_values == ("preliminary", "final", "correction")

    def test_no_unexpected_columns(self) -> None:
        names = {c.name for c in SettlementSchema.COLUMNS}
        expected_names = {row[0] for row in _EXPECTED}
        assert names == expected_names

"""Contract tests for ObservationSchema.

Expected column set is a fixture list transcribed directly from
``docs/design.md`` §A 'Observations schema'. Any drift between the
implementation and the design doc must fail loudly here.
"""

from __future__ import annotations

import pytest
from tradewinds.core.schemas import ObservationSchema

# Each tuple: (column_name, dtype, units, nullable, enum_values_or_None)
# Transcribed from docs/design.md §A Observations schema table.
_EXPECTED: list[tuple[str, str, str | None, bool, tuple[str, ...] | None]] = [
    ("station", "string", None, False, None),
    ("event_time", "timestamp_utc", None, False, None),
    (
        "observation_type",
        "enum",
        None,
        False,
        ("METAR", "SPECI"),
    ),
    ("temp_c", "float64", "celsius", True, None),
    ("dew_point_c", "float64", "celsius", True, None),
    ("wind_speed_ms", "float64", "m/s", True, None),
    ("wind_dir_deg", "int64", "degrees", True, None),
    ("wind_gust_ms", "float64", "m/s", True, None),
    ("slp_hpa", "float64", "hPa", True, None),
    ("visibility_m", "float64", "meters", True, None),
    ("precip_mm_1h", "float64", "mm", True, None),
    (
        "sky_cover_1",
        "enum",
        None,
        True,
        ("CLR", "FEW", "SCT", "BKN", "OVC", "VV"),
    ),
    ("sky_base_1_m", "float64", "meters", True, None),
    (
        "sky_cover_2",
        "enum",
        None,
        True,
        ("CLR", "FEW", "SCT", "BKN", "OVC", "VV"),
    ),
    ("sky_base_2_m", "float64", "meters", True, None),
    (
        "sky_cover_3",
        "enum",
        None,
        True,
        ("CLR", "FEW", "SCT", "BKN", "OVC", "VV"),
    ),
    ("sky_base_3_m", "float64", "meters", True, None),
    (
        "sky_cover_4",
        "enum",
        None,
        True,
        ("CLR", "FEW", "SCT", "BKN", "OVC", "VV"),
    ),
    ("sky_base_4_m", "float64", "meters", True, None),
    ("metar_raw", "string", None, True, None),
]


# Imperial-mode rename map per docs/design.md §A imperial-mode table.
_EXPECTED_IMPERIAL_RENAMES = {
    "event_time": "utc_datetime",
    "temp_c": "temp_F",
    "dew_point_c": "dew_point_F",
    "wind_speed_ms": "wind_speed_kt",
    "wind_gust_ms": "gust_kt",
    "visibility_m": "vsby",
    "precip_mm_1h": "precip_in_1h",
    "sky_base_1_m": "sky_base_1_ft",
    "sky_base_2_m": "sky_base_2_ft",
    "sky_base_3_m": "sky_base_3_ft",
    "sky_base_4_m": "sky_base_4_ft",
}


# The 9-column mostly-light/metar_parser anti-duplication contract.
# Imperial-mode projection MUST include these names (in some order).
_KXHIGH_IMPERIAL_NINE = {
    "station",
    "utc_datetime",
    "temp_F",
    "dew_point_F",
    "slp_hpa",
    "wind_speed_kt",
    "wind_dir_deg",
    "gust_kt",
    "vsby",
}


class TestObservationSchemaContract:
    def test_schema_id(self) -> None:
        assert ObservationSchema.schema_id == "schema.observation.v1"

    def test_column_count_matches_design_doc(self) -> None:
        assert len(ObservationSchema.COLUMNS) == len(_EXPECTED) == 20

    def test_column_names_in_order(self) -> None:
        # Order is load-bearing for serialization stability.
        assert ObservationSchema.column_names("metric") == [row[0] for row in _EXPECTED]

    @pytest.mark.parametrize(("name", "dtype", "units", "nullable", "enum_values"), _EXPECTED)
    def test_each_column_spec_exact(
        self,
        name: str,
        dtype: str,
        units: str | None,
        nullable: bool,
        enum_values: tuple[str, ...] | None,
    ) -> None:
        spec = ObservationSchema.column(name)
        assert spec.dtype == dtype, name
        assert spec.units == units, name
        assert spec.nullable == nullable, name
        assert spec.enum_values == enum_values, name

    def test_required_columns_are_non_nullable(self) -> None:
        for name in ("station", "event_time", "observation_type"):
            assert ObservationSchema.column(name).nullable is False

    def test_imperial_renames_match_design_doc(self) -> None:
        assert ObservationSchema.IMPERIAL_RENAMES == _EXPECTED_IMPERIAL_RENAMES

    def test_imperial_mode_column_names(self) -> None:
        # station, observation_type, wind_dir_deg, slp_hpa, sky_cover_N,
        # metar_raw are unchanged across modes per §A.
        imperial = ObservationSchema.column_names("imperial")
        expected = [
            "station",
            "utc_datetime",
            "observation_type",
            "temp_F",
            "dew_point_F",
            "wind_speed_kt",
            "wind_dir_deg",
            "gust_kt",
            "slp_hpa",
            "vsby",
            "precip_in_1h",
            "sky_cover_1",
            "sky_base_1_ft",
            "sky_cover_2",
            "sky_base_2_ft",
            "sky_cover_3",
            "sky_base_3_ft",
            "sky_cover_4",
            "sky_base_4_ft",
            "metar_raw",
        ]
        assert imperial == expected

    def test_imperial_projection_covers_kxhigh_nine(self) -> None:
        # The 9-column anti-duplication contract from
        # mostly-light/metar_parser.py is a subset of the imperial-mode
        # projection of this schema (§A).
        imperial = set(ObservationSchema.column_names("imperial"))
        assert _KXHIGH_IMPERIAL_NINE.issubset(imperial)

    def test_no_unexpected_columns(self) -> None:
        # Guard against silent additions outside the design doc.
        names = {c.name for c in ObservationSchema.COLUMNS}
        expected_names = {row[0] for row in _EXPECTED}
        assert names == expected_names

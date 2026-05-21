"""Tests for tradewinds._internal._bounds.

Lifted from monorepo-v0.14.1 (where _bounds had no dedicated test file —
coverage came from parser tests in test_awc.py, test_iem.py, test_ghcnh.py).
This module unit-tests the three helpers (bounded_int, bounded_float,
bounded_float_min) and pins the constant values that downstream parsers
depend on. When the Wave 3 weather parsers land, they will inherit this
coverage transitively via their own parser-level tests.
"""

from __future__ import annotations

import logging

import pytest
from tradewinds._internal._bounds import (
    MAX_RAW_METAR_LEN,
    MAX_VISIBILITY_MILES,
    MAX_WX_CODES_LEN,
    MAX_YEAR,
    MIN_YEAR,
    SKY_BASE_MAX_FT,
    SLP_MAX_MB,
    SLP_MIN_MB,
    STATION_CODE_RE,
    TEMP_MAX_C,
    TEMP_MIN_C,
    WIND_DIR_BOUNDS,
    WIND_GUST_MAX,
    WIND_SPEED_MAX,
    bounded_float,
    bounded_float_min,
    bounded_int,
)

# -----------------------------------------------------------------------------
# bounded_int
# -----------------------------------------------------------------------------


class TestBoundedInt:
    def test_none_returns_none(self):
        assert bounded_int(None, 0, 100) is None

    def test_value_in_range(self):
        assert bounded_int(50, 0, 100) == 50

    def test_value_at_lower_bound(self):
        assert bounded_int(0, 0, 100) == 0

    def test_value_at_upper_bound(self):
        assert bounded_int(100, 0, 100) == 100

    def test_value_below_range(self):
        assert bounded_int(-1, 0, 100) is None

    def test_value_above_range(self):
        assert bounded_int(101, 0, 100) is None

    def test_negative_range(self):
        assert bounded_int(-50, -100, -10) == -50
        assert bounded_int(-5, -100, -10) is None

    def test_wind_dir_bounds(self):
        lo, hi = WIND_DIR_BOUNDS
        assert bounded_int(0, lo, hi) == 0
        assert bounded_int(360, lo, hi) == 360
        assert bounded_int(361, lo, hi) is None
        assert bounded_int(-1, lo, hi) is None


# -----------------------------------------------------------------------------
# bounded_float
# -----------------------------------------------------------------------------


class TestBoundedFloat:
    def test_none_returns_none(self):
        assert bounded_float(None, 0.0, 100.0) is None

    def test_value_in_range(self):
        assert bounded_float(50.5, 0.0, 100.0) == 50.5

    def test_value_at_lower_bound(self):
        assert bounded_float(0.0, 0.0, 100.0) == 0.0

    def test_value_at_upper_bound(self):
        assert bounded_float(100.0, 0.0, 100.0) == 100.0

    def test_value_below_range_returns_none(self):
        assert bounded_float(-0.001, 0.0, 100.0) is None

    def test_value_above_range_returns_none(self):
        assert bounded_float(100.001, 0.0, 100.0) is None

    def test_out_of_bounds_logs_warning(self, caplog):
        with caplog.at_level(logging.WARNING, logger="tradewinds._internal._bounds"):
            result = bounded_float(200.0, 0.0, 100.0)
        assert result is None
        assert any("bounded_float" in rec.message for rec in caplog.records)

    def test_out_of_bounds_field_context_in_log(self, caplog):
        with caplog.at_level(logging.WARNING, logger="tradewinds._internal._bounds"):
            bounded_float(-100.0, 0.0, 100.0, field="temp_c")
        # Field name should be included in the log message
        assert any("temp_c" in rec.message for rec in caplog.records)

    def test_in_bounds_does_not_log(self, caplog):
        with caplog.at_level(logging.WARNING, logger="tradewinds._internal._bounds"):
            bounded_float(50.0, 0.0, 100.0, field="temp_c")
        assert not caplog.records

    def test_temp_c_bounds(self):
        # World records: -89.2 Vostok / 56.7 Death Valley
        assert bounded_float(-89.2, TEMP_MIN_C, TEMP_MAX_C) == -89.2
        assert bounded_float(56.7, TEMP_MIN_C, TEMP_MAX_C) == 56.7
        assert bounded_float(-90.0, TEMP_MIN_C, TEMP_MAX_C) == -90.0  # exact bound
        assert bounded_float(60.0, TEMP_MIN_C, TEMP_MAX_C) == 60.0  # exact bound
        assert bounded_float(-90.1, TEMP_MIN_C, TEMP_MAX_C) is None
        assert bounded_float(60.1, TEMP_MIN_C, TEMP_MAX_C) is None

    def test_pressure_bounds(self):
        assert bounded_float(1013.25, SLP_MIN_MB, SLP_MAX_MB) == 1013.25
        assert bounded_float(SLP_MIN_MB, SLP_MIN_MB, SLP_MAX_MB) == SLP_MIN_MB
        assert bounded_float(SLP_MAX_MB, SLP_MIN_MB, SLP_MAX_MB) == SLP_MAX_MB
        assert bounded_float(0.0, SLP_MIN_MB, SLP_MAX_MB) is None


# -----------------------------------------------------------------------------
# bounded_float_min
# -----------------------------------------------------------------------------


class TestBoundedFloatMin:
    def test_none_returns_none(self):
        assert bounded_float_min(None, 0.0) is None

    def test_value_above_min(self):
        assert bounded_float_min(5.0, 0.0) == 5.0

    def test_value_at_min(self):
        assert bounded_float_min(0.0, 0.0) == 0.0

    def test_value_below_min(self):
        assert bounded_float_min(-0.001, 0.0) is None

    def test_negative_min(self):
        assert bounded_float_min(-5.0, -10.0) == -5.0
        assert bounded_float_min(-15.0, -10.0) is None

    def test_precip_non_negative(self):
        # Real use case: precipitation must be >= 0
        assert bounded_float_min(0.0, 0.0) == 0.0
        assert bounded_float_min(0.5, 0.0) == 0.5
        assert bounded_float_min(-0.01, 0.0) is None


# -----------------------------------------------------------------------------
# Constants — pin the values that downstream parsers depend on
# -----------------------------------------------------------------------------


class TestConstants:
    def test_pressure_bounds(self):
        assert SLP_MIN_MB == 870.0
        assert SLP_MAX_MB == 1084.0

    def test_temperature_bounds(self):
        assert TEMP_MIN_C == -90.0
        assert TEMP_MAX_C == 60.0

    def test_string_length_limits(self):
        assert MAX_RAW_METAR_LEN == 2048
        assert MAX_WX_CODES_LEN == 256

    def test_visibility_max(self):
        assert MAX_VISIBILITY_MILES == 99.99

    def test_wind_bounds(self):
        assert WIND_DIR_BOUNDS == (0, 360)
        assert WIND_SPEED_MAX == 200
        assert WIND_GUST_MAX == 250

    def test_sky_base_max(self):
        assert SKY_BASE_MAX_FT == 60000

    def test_year_range(self):
        assert MIN_YEAR == 1940
        assert MAX_YEAR == 2100


# -----------------------------------------------------------------------------
# STATION_CODE_RE — security boundary (codes flow into Hive partition paths)
# -----------------------------------------------------------------------------


class TestStationCodeRegex:
    @pytest.mark.parametrize(
        "code",
        ["KJFK", "KORD", "KDEN", "EGLL", "LFPG", "RJTT", "ABC", "ZZZZ"],
    )
    def test_valid_codes(self, code):
        assert STATION_CODE_RE.match(code) is not None

    @pytest.mark.parametrize(
        "code",
        [
            "",  # empty
            "AB",  # too short (2 chars)
            "ABCDE",  # too long (5 chars)
            "kjfk",  # lowercase
            "K1FK",  # contains digit
            "K-FK",  # contains hyphen
            "K FK",  # contains space
            "K/FK",  # contains slash (path separator!)
            "../",  # path traversal attempt
            "K\nFK",  # newline
        ],
    )
    def test_invalid_codes_rejected(self, code):
        assert STATION_CODE_RE.match(code) is None

    def test_no_path_traversal(self):
        # The regex is a security boundary: codes go into Hive partition paths.
        assert STATION_CODE_RE.match("../K") is None
        assert STATION_CODE_RE.match("..") is None
        assert STATION_CODE_RE.match("K/../") is None

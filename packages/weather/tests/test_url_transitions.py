"""Phase 17 FORECAST-06: ``_url_transitions.py`` date-constant catalog."""

from __future__ import annotations

from datetime import UTC, datetime

from mostlyright.weather._fetchers._url_transitions import (
    ECMWF_AIFS_EXPERIMENTAL_START,
    ECMWF_AIFS_OPERATIONAL_START,
    ECMWF_IFS_PATH_TRANSITION,
    ECMWF_IFS_RESOLUTION_TRANSITION,
    GEFS_FORMAT_2018,
    GEFS_FORMAT_2020,
    GFS_V16_CUTOVER,
    LEGACY_MODELS_RETIRE,
)


def test_gfs_v16_cutover() -> None:
    assert datetime(2021, 3, 23, tzinfo=UTC) == GFS_V16_CUTOVER


def test_gefs_format_transitions() -> None:
    assert datetime(2018, 7, 27, tzinfo=UTC) == GEFS_FORMAT_2018
    assert datetime(2020, 9, 23, tzinfo=UTC) == GEFS_FORMAT_2020


def test_ecmwf_ifs_transitions() -> None:
    assert datetime(2024, 2, 28, 6, tzinfo=UTC) == ECMWF_IFS_PATH_TRANSITION
    assert datetime(2024, 2, 29, tzinfo=UTC) == ECMWF_IFS_RESOLUTION_TRANSITION


def test_ecmwf_aifs_transitions() -> None:
    assert datetime(2025, 2, 9, 12, tzinfo=UTC) == ECMWF_AIFS_EXPERIMENTAL_START
    assert datetime(2025, 2, 25, 6, tzinfo=UTC) == ECMWF_AIFS_OPERATIONAL_START


def test_legacy_models_retire() -> None:
    assert datetime(2026, 8, 31, tzinfo=UTC) == LEGACY_MODELS_RETIRE


def test_all_constants_are_tz_aware_utc() -> None:
    for c in (
        ECMWF_AIFS_EXPERIMENTAL_START,
        ECMWF_AIFS_OPERATIONAL_START,
        ECMWF_IFS_PATH_TRANSITION,
        ECMWF_IFS_RESOLUTION_TRANSITION,
        GEFS_FORMAT_2018,
        GEFS_FORMAT_2020,
        GFS_V16_CUTOVER,
        LEGACY_MODELS_RETIRE,
    ):
        assert c.tzinfo is UTC, f"{c!r} is not UTC-aware"

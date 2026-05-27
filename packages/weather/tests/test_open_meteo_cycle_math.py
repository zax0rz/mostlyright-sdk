"""Phase 20 OM-03: cycle-math primitives — floor_to_cycle + issued_at derivation."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from mostlyright.weather._fetchers._open_meteo_models import (
    floor_to_cycle,
    issued_at_from_live_cycle_math,
    issued_at_from_previous_day,
)

GFS_CYCLES = (0, 6, 12, 18)
HRRR_CYCLES = tuple(range(24))  # hourly
ECMWF_IFS_CYCLES = (0, 12)


def test_floor_to_cycle_snaps_down_to_most_recent_cycle() -> None:
    result = floor_to_cycle(datetime(2024, 6, 1, 23, 0, tzinfo=UTC), GFS_CYCLES)
    assert result == datetime(2024, 6, 1, 18, 0, tzinfo=UTC)


def test_floor_to_cycle_floor_below_cycle_value() -> None:
    # 17:00 must floor to 12:00 (not 18:00)
    result = floor_to_cycle(datetime(2024, 6, 1, 17, 0, tzinfo=UTC), GFS_CYCLES)
    assert result == datetime(2024, 6, 1, 12, 0, tzinfo=UTC)


def test_floor_to_cycle_crosses_midnight_backwards() -> None:
    # 5:30 must floor to 0:00 same day
    result = floor_to_cycle(datetime(2024, 6, 1, 5, 30, tzinfo=UTC), GFS_CYCLES)
    assert result == datetime(2024, 6, 1, 0, 0, tzinfo=UTC)


def test_floor_to_cycle_value_exactly_on_cycle() -> None:
    result = floor_to_cycle(datetime(2024, 6, 1, 0, 0, tzinfo=UTC), GFS_CYCLES)
    assert result == datetime(2024, 6, 1, 0, 0, tzinfo=UTC)


def test_floor_to_cycle_hourly_cycles() -> None:
    result = floor_to_cycle(datetime(2024, 6, 1, 14, 30, tzinfo=UTC), HRRR_CYCLES)
    assert result == datetime(2024, 6, 1, 14, 0, tzinfo=UTC)


def test_floor_to_cycle_ecmwf_ifs_cycles() -> None:
    result = floor_to_cycle(datetime(2024, 6, 1, 11, 59, tzinfo=UTC), ECMWF_IFS_CYCLES)
    assert result == datetime(2024, 6, 1, 0, 0, tzinfo=UTC)


def test_floor_to_cycle_empty_cycles_raises() -> None:
    with pytest.raises(ValueError, match="cycle_hours"):
        floor_to_cycle(datetime(2024, 6, 1, 12, 0, tzinfo=UTC), ())


def test_floor_to_cycle_naive_datetime_raises() -> None:
    with pytest.raises(ValueError, match=r"tz-aware|UTC"):
        floor_to_cycle(datetime(2024, 6, 1, 12, 0), GFS_CYCLES)


def test_issued_at_from_previous_day_gfs_nyc_example() -> None:
    """NYC 2024-06-01T23:00Z, GFS previous_day1 → 2024-05-31T18:00Z."""
    valid_at = datetime(2024, 6, 1, 23, 0, tzinfo=UTC)
    result = issued_at_from_previous_day(valid_at, N=1, cycle_hours=GFS_CYCLES)
    assert result == datetime(2024, 5, 31, 18, 0, tzinfo=UTC)


def test_issued_at_from_previous_day_gfs_n2() -> None:
    """NYC 2024-06-01T23:00Z, GFS previous_day2 → 2024-05-30T18:00Z."""
    valid_at = datetime(2024, 6, 1, 23, 0, tzinfo=UTC)
    result = issued_at_from_previous_day(valid_at, N=2, cycle_hours=GFS_CYCLES)
    assert result == datetime(2024, 5, 30, 18, 0, tzinfo=UTC)


def test_issued_at_from_previous_day_hrrr_hourly() -> None:
    """HRRR has hourly cycles → previous_day1 just shifts back 24h."""
    valid_at = datetime(2024, 6, 1, 23, 0, tzinfo=UTC)
    result = issued_at_from_previous_day(valid_at, N=1, cycle_hours=HRRR_CYCLES)
    assert result == datetime(2024, 5, 31, 23, 0, tzinfo=UTC)


def test_issued_at_from_live_cycle_math_gfs_4h_lag() -> None:
    """Live GFS, now=2024-06-01T14:00Z, publish_lag=4h → 2024-06-01T06:00Z."""
    now = datetime(2024, 6, 1, 14, 0, tzinfo=UTC)
    result = issued_at_from_live_cycle_math(
        now_utc=now,
        publish_lag=timedelta(hours=4),
        cycle_hours=GFS_CYCLES,
    )
    assert result == datetime(2024, 6, 1, 6, 0, tzinfo=UTC)


def test_issued_at_from_live_cycle_math_hrrr_1h_lag() -> None:
    """Live HRRR, now=14:30Z, publish_lag=1h → 13:00Z."""
    now = datetime(2024, 6, 1, 14, 30, tzinfo=UTC)
    result = issued_at_from_live_cycle_math(
        now_utc=now,
        publish_lag=timedelta(hours=1),
        cycle_hours=HRRR_CYCLES,
    )
    assert result == datetime(2024, 6, 1, 13, 0, tzinfo=UTC)


def test_issued_at_from_previous_day_rejects_n_below_1() -> None:
    valid_at = datetime(2024, 6, 1, 23, 0, tzinfo=UTC)
    with pytest.raises(ValueError, match=r"N must be in 1\.\.7|N must be"):
        issued_at_from_previous_day(valid_at, N=0, cycle_hours=GFS_CYCLES)


def test_issued_at_from_previous_day_rejects_n_above_7() -> None:
    valid_at = datetime(2024, 6, 1, 23, 0, tzinfo=UTC)
    with pytest.raises(ValueError, match=r"N must be in 1\.\.7|N must be"):
        issued_at_from_previous_day(valid_at, N=8, cycle_hours=GFS_CYCLES)

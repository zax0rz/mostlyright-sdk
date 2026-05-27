"""Phase 20 PLAN-05 OM-06: forecast cache tier (per-source partitioned)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from mostlyright.weather.cache import (
    forecast_cache_path,
    invalidate_forecast,
    read_forecast_cache,
    write_forecast_cache,
)


def test_forecast_cache_path_layout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MOSTLYRIGHTMD_CACHE_DIR", str(tmp_path))
    path = forecast_cache_path(
        "KNYC", "open_meteo.previous_runs", "gfs_global", 2024, 6
    )
    parts = path.parts
    assert "forecasts" in parts
    assert "open_meteo.previous_runs" in parts
    assert "gfs_global" in parts
    assert "KNYC" in parts
    assert "2024" in parts
    assert path.name == "06.parquet"


def test_write_then_read_forecast_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MOSTLYRIGHTMD_CACHE_DIR", str(tmp_path))
    rows = [
        {
            "station": "KNYC",
            "issued_at": datetime(2024, 5, 31, 18, tzinfo=UTC),
            "valid_at": datetime(2024, 6, 1, 23, tzinfo=UTC),
            "model": "gfs_global",
            "source": "open_meteo.previous_runs",
            "temp_c": 22.5,
        }
    ]
    write_forecast_cache(
        "KNYC", "open_meteo.previous_runs", "gfs_global", 2024, 6, rows
    )
    got = read_forecast_cache(
        "KNYC", "open_meteo.previous_runs", "gfs_global", 2024, 6
    )
    assert got is not None
    assert len(got) == 1
    assert got[0]["station"] == "KNYC"


def test_live_source_never_cached(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MOSTLYRIGHTMD_CACHE_DIR", str(tmp_path))
    rows = [
        {
            "station": "KNYC",
            "issued_at": datetime(2024, 6, 1, 0, tzinfo=UTC),
            "valid_at": datetime(2024, 6, 1, 0, tzinfo=UTC),
            "model": "gfs_global",
            "source": "open_meteo.live",
            "temp_c": 22.5,
        }
    ]
    write_forecast_cache(
        "KNYC", "open_meteo.live", "gfs_global", 2024, 6, rows
    )
    path = forecast_cache_path(
        "KNYC", "open_meteo.live", "gfs_global", 2024, 6
    )
    assert not path.exists()


def test_seamless_source_never_cached(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MOSTLYRIGHTMD_CACHE_DIR", str(tmp_path))
    rows = [
        {
            "station": "KNYC",
            "issued_at": None,
            "valid_at": datetime(2024, 6, 1, 0, tzinfo=UTC),
            "model": "gfs_global",
            "source": "open_meteo.seamless",
            "temp_c": 22.5,
        }
    ]
    write_forecast_cache(
        "KNYC", "open_meteo.seamless", "gfs_global", 2024, 6, rows
    )
    path = forecast_cache_path(
        "KNYC", "open_meteo.seamless", "gfs_global", 2024, 6
    )
    assert not path.exists()


def test_current_utc_month_skipped(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MOSTLYRIGHTMD_CACHE_DIR", str(tmp_path))
    now = datetime.now(UTC)
    rows = [
        {
            "station": "KNYC",
            "issued_at": now,
            "valid_at": now,
            "model": "gfs_global",
            "source": "open_meteo.previous_runs",
            "temp_c": 22.5,
        }
    ]
    write_forecast_cache(
        "KNYC",
        "open_meteo.previous_runs",
        "gfs_global",
        now.year,
        now.month,
        rows,
    )
    path = forecast_cache_path(
        "KNYC",
        "open_meteo.previous_runs",
        "gfs_global",
        now.year,
        now.month,
    )
    assert not path.exists()


def test_invalidate_forecast_removes_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MOSTLYRIGHTMD_CACHE_DIR", str(tmp_path))
    rows = [
        {
            "station": "KNYC",
            "issued_at": datetime(2024, 5, 31, 18, tzinfo=UTC),
            "valid_at": datetime(2024, 6, 1, 23, tzinfo=UTC),
            "model": "gfs_global",
            "source": "open_meteo.previous_runs",
            "temp_c": 22.5,
        }
    ]
    write_forecast_cache(
        "KNYC", "open_meteo.previous_runs", "gfs_global", 2024, 6, rows
    )
    assert invalidate_forecast(
        "KNYC", "open_meteo.previous_runs", "gfs_global", 2024, 6
    )
    assert not invalidate_forecast(
        "KNYC", "open_meteo.previous_runs", "gfs_global", 2024, 6
    )


def test_read_forecast_cache_miss_returns_none(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MOSTLYRIGHTMD_CACHE_DIR", str(tmp_path))
    got = read_forecast_cache(
        "KNYC", "open_meteo.previous_runs", "gfs_global", 2020, 1
    )
    assert got is None

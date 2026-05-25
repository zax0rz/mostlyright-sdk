"""Phase 7 PLAN-01: exact_window kwarg on download_iem_asos.

Tests the day-granular IEM URL bypass that skips year-normalization (lines
204-209 of iem_asos.py). The exact_window=True path:
  - Uses caller's start/end directly (no date(start.year, 1, 1) clamp).
  - Sends day-granular day1=/day2= URL params (not year-aligned 01-01 bounds).
  - Lands CSVs in a separate dest_dir namespace (caller-controlled — typically
    `sources/iem_asos_exact/`), never in canonical `sources/iem_asos/`.

The default (exact_window=False) preserves all existing behavior — verified
by the existing test suite at packages/weather/tests/_fetchers/test_iem_asos.py.

HTTP is mocked at `download_with_retry`; no network.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path
from unittest.mock import patch

import pytest
from mostlyright._internal.models.station import StationInfo
from mostlyright.weather._fetchers.iem_asos import download_iem_asos


def _make_station(code: str = "NYC", icao: str = "KNYC") -> StationInfo:
    return StationInfo(
        code=code,
        name="Central Park, New York",
        icao=icao,
        timezone="America/New_York",
        utc_offset_standard=-5,
        latitude=40.78,
        longitude=-73.97,
        kalshi_traded=True,
    )


@pytest.fixture
def frozen_today_utc():
    """Frozen 'today' in the past so default-mode tests are fully historical."""
    fake_dt = datetime(2026, 5, 22, 12, 0, 0, tzinfo=UTC)

    class _FakeDatetime(datetime):
        @classmethod
        def now(cls, tz=None):  # type: ignore[override]
            return fake_dt if tz is UTC or tz is not None else fake_dt.replace(tzinfo=None)

    with patch("mostlyright.weather._fetchers.iem_asos.datetime", _FakeDatetime):
        yield date(2026, 5, 22)


def test_exact_window_url_uses_day_granular_params(tmp_path, frozen_today_utc):
    """exact_window=True: URL contains caller's day1/day2 (NOT year-aligned)."""
    station = _make_station()
    captured_urls: list[str] = []

    def _fake_download(url: str, dest: Path) -> None:
        captured_urls.append(url)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text("station,valid\n", encoding="utf-8")

    dest_dir = tmp_path / "iem_asos_exact"

    with (
        patch(
            "mostlyright.weather._fetchers.iem_asos.download_with_retry",
            side_effect=_fake_download,
        ),
        patch("mostlyright.weather._fetchers.iem_asos.time.sleep"),
    ):
        paths = download_iem_asos(
            station,
            date(2024, 3, 5),
            date(2024, 3, 25),
            dest_dir,
            exact_window=True,
        )

    assert len(captured_urls) >= 1
    url = captured_urls[0]
    # Day-granular: caller's start was 2024-03-05, NOT 2024-01-01.
    assert "year1=2024" in url
    assert "month1=3" in url
    assert "day1=5" in url
    # End is caller's end (or end+1 for IEM exclusive-day-2 — both acceptable
    # as long as it's NOT 2025-01-01 year-aligned).
    assert "year2=2024" in url
    assert "month2=3" in url
    # day2 should be one of {25, 26} depending on IEM exclusive-end adjustment.
    assert any(f"day2={d}" in url for d in (25, 26))
    assert all(isinstance(p, Path) and p.suffix == ".csv" for p in paths)


def test_exact_window_false_preserves_year_normalization(tmp_path, frozen_today_utc):
    """exact_window=False (default): URL is year-aligned (existing behavior)."""
    station = _make_station()
    captured_urls: list[str] = []

    def _fake_download(url: str, dest: Path) -> None:
        captured_urls.append(url)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text("station,valid\n", encoding="utf-8")

    dest_dir = tmp_path / "iem_asos"

    with (
        patch(
            "mostlyright.weather._fetchers.iem_asos.download_with_retry",
            side_effect=_fake_download,
        ),
        patch("mostlyright.weather._fetchers.iem_asos.time.sleep"),
    ):
        download_iem_asos(
            station,
            date(2024, 3, 5),
            date(2024, 3, 25),
            dest_dir,
            # exact_window omitted → defaults to False.
        )

    assert len(captured_urls) >= 1
    url = captured_urls[0]
    # Default mode normalizes start to 2024-01-01.
    assert "year1=2024" in url
    assert "month1=1" in url
    assert "day1=1" in url


def test_exact_window_paths_under_caller_dest_dir(tmp_path, frozen_today_utc):
    """Returned paths must live under the caller-supplied dest_dir."""
    station = _make_station()
    dest_dir = tmp_path / "iem_asos_exact"

    def _fake_download(url: str, dest: Path) -> None:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text("station,valid\n", encoding="utf-8")

    with (
        patch(
            "mostlyright.weather._fetchers.iem_asos.download_with_retry",
            side_effect=_fake_download,
        ),
        patch("mostlyright.weather._fetchers.iem_asos.time.sleep"),
    ):
        paths = download_iem_asos(
            station,
            date(2024, 3, 5),
            date(2024, 3, 25),
            dest_dir,
            exact_window=True,
        )

    assert len(paths) >= 1
    for p in paths:
        assert dest_dir in p.parents, f"{p} not under {dest_dir}"
        # No `_exact_` infix in the filename — B-5: directory-level separation.
        assert "_exact_" not in p.name


def test_exact_window_returns_list_of_csv_paths(tmp_path, frozen_today_utc):
    """Function returns list[Path] of `.csv` files (parser handles them)."""
    station = _make_station()

    def _fake_download(url: str, dest: Path) -> None:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text("station,valid\n", encoding="utf-8")

    with (
        patch(
            "mostlyright.weather._fetchers.iem_asos.download_with_retry",
            side_effect=_fake_download,
        ),
        patch("mostlyright.weather._fetchers.iem_asos.time.sleep"),
    ):
        paths = download_iem_asos(
            station,
            date(2024, 3, 5),
            date(2024, 3, 25),
            tmp_path / "iem_asos_exact",
            exact_window=True,
        )

    assert isinstance(paths, list)
    assert all(isinstance(p, Path) for p in paths)
    assert all(p.suffix == ".csv" for p in paths)

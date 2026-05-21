"""Tests for tradewinds.weather._fetchers.ghcnh.

Covers:
- URL + filename pattern (must match monorepo-v0.14.1/ingest/sources/ghcnh_backfill.py)
- Single-year download writes the PSV to <dest_dir>/<station_id>/<filename>
- 404 raises for single-year and is skipped (with warning) for range
- Cache: existing file returns without HTTP; ``skip_cache=True`` forces re-fetch
- Multi-year range produces contiguous files in order

Network is fully mocked via ``respx``. ``time.sleep`` is monkey-patched to a
no-op in every test that exercises the polite delay so the suite stays fast.
"""

from __future__ import annotations

import logging
from pathlib import Path

import httpx
import pytest
from tradewinds.weather._fetchers.ghcnh import (
    GHCNH_BASE_URL,
    NCEI_POLITE_DELAY,
    download_ghcnh,
    download_ghcnh_range,
)


def _patch_sleep(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    """Replace the polite delay sleep with a no-op recorder.

    Returns the list that recorded the requested delays so tests can
    assert "polite delay was honored" without actually waiting.
    """
    calls: list[float] = []

    def _record(delay: float) -> None:
        calls.append(delay)

    monkeypatch.setattr(
        "tradewinds.weather._fetchers.ghcnh.time.sleep",
        _record,
    )
    return calls


# ---------------------------------------------------------------------------
# Module constants — guard the v0.14.1 URL pattern from drift
# ---------------------------------------------------------------------------
class TestModuleConstants:
    def test_base_url_matches_v014(self) -> None:
        """Pinned to v0.14.1 ingest/sources/ghcnh_backfill.py:25 exactly."""
        assert GHCNH_BASE_URL == (
            "https://www.ncei.noaa.gov/oa/global-historical-climatology-network/hourly/access"
        )

    def test_polite_delay_one_second(self) -> None:
        """NCEI politeness: 1 s between requests, per v0.14.1."""
        assert NCEI_POLITE_DELAY == 1.0


# ---------------------------------------------------------------------------
# URL + filename pattern
# ---------------------------------------------------------------------------
class TestUrlPattern:
    """The URL and filename format must mirror v0.14.1 exactly."""

    def test_filename_format(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Filename: GHCNh_<station_id>_<year>.psv (v0.14.1 line 97)."""
        respx = pytest.importorskip("respx")
        _patch_sleep(monkeypatch)

        station = "744860-94789"
        year = 2024
        url = (
            "https://www.ncei.noaa.gov/oa/global-historical-climatology-network/"
            f"hourly/access/by-year/{year}/psv/GHCNh_{station}_{year}.psv"
        )

        with respx.mock(assert_all_called=True) as mock:
            mock.get(url).respond(200, content=b"col1|col2\n")
            path = download_ghcnh(station, year, tmp_path)

        assert path.name == f"GHCNh_{station}_{year}.psv"

    def test_url_format(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """URL: <base>/by-year/<year>/psv/<filename> (v0.14.1 line 101)."""
        respx = pytest.importorskip("respx")
        _patch_sleep(monkeypatch)

        station = "USW00094728"  # NCEI 11-char form
        year = 2023
        expected_url = f"{GHCNH_BASE_URL}/by-year/{year}/psv/GHCNh_{station}_{year}.psv"

        with respx.mock(assert_all_called=True) as mock:
            route = mock.get(expected_url).respond(200, content=b"data\n")
            download_ghcnh(station, year, tmp_path)
            assert route.called

    def test_dest_layout_per_station_subdir(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Files land under <dest_dir>/<station_id>/<filename> (v0.14.1 line 98)."""
        respx = pytest.importorskip("respx")
        _patch_sleep(monkeypatch)

        station = "744860-94789"
        year = 2024
        url = f"{GHCNH_BASE_URL}/by-year/{year}/psv/GHCNh_{station}_{year}.psv"

        with respx.mock() as mock:
            mock.get(url).respond(200, content=b"x")
            path = download_ghcnh(station, year, tmp_path)

        assert path == tmp_path / station / f"GHCNh_{station}_{year}.psv"
        assert path.exists()
        assert path.read_bytes() == b"x"

    def test_station_id_with_dash(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """USAF-WBAN dashed ids must round-trip into the URL unchanged."""
        respx = pytest.importorskip("respx")
        _patch_sleep(monkeypatch)

        station = "722030-12839"  # KMIA
        year = 2022
        url = f"{GHCNH_BASE_URL}/by-year/{year}/psv/GHCNh_{station}_{year}.psv"

        with respx.mock(assert_all_called=True) as mock:
            mock.get(url).respond(200, content=b"miami")
            path = download_ghcnh(station, year, tmp_path)

        assert path.read_bytes() == b"miami"


# ---------------------------------------------------------------------------
# Polite delay
# ---------------------------------------------------------------------------
class TestPoliteDelay:
    def test_sleeps_after_successful_download(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        respx = pytest.importorskip("respx")
        sleeps = _patch_sleep(monkeypatch)

        station = "744860-94789"
        year = 2024
        url = f"{GHCNH_BASE_URL}/by-year/{year}/psv/GHCNh_{station}_{year}.psv"
        with respx.mock() as mock:
            mock.get(url).respond(200, content=b"data")
            download_ghcnh(station, year, tmp_path)

        assert sleeps == [NCEI_POLITE_DELAY]

    def test_no_sleep_on_cache_hit(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        sleeps = _patch_sleep(monkeypatch)

        station = "744860-94789"
        year = 2024
        filename = f"GHCNh_{station}_{year}.psv"
        cached = tmp_path / station / filename
        cached.parent.mkdir(parents=True, exist_ok=True)
        cached.write_bytes(b"cached")

        path = download_ghcnh(station, year, tmp_path)

        assert path == cached
        assert path.read_bytes() == b"cached"
        # No HTTP round-trip → no polite-delay sleep.
        assert sleeps == []

    def test_no_sleep_on_404(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        respx = pytest.importorskip("respx")
        sleeps = _patch_sleep(monkeypatch)

        station = "744860-94789"
        year = 1820  # Way before GHCNh coverage
        url = f"{GHCNH_BASE_URL}/by-year/{year}/psv/GHCNh_{station}_{year}.psv"
        with respx.mock() as mock:
            mock.get(url).respond(404)
            with pytest.raises(httpx.HTTPStatusError):
                download_ghcnh(station, year, tmp_path)
        assert sleeps == []


# ---------------------------------------------------------------------------
# 404 handling
# ---------------------------------------------------------------------------
class Test404SingleYear:
    def test_404_raises(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Single-year fetch raises on 404. Range helper handles the skip."""
        respx = pytest.importorskip("respx")
        _patch_sleep(monkeypatch)

        station = "744860-94789"
        year = 1820
        url = f"{GHCNH_BASE_URL}/by-year/{year}/psv/GHCNh_{station}_{year}.psv"
        with respx.mock() as mock:
            mock.get(url).respond(404)
            with pytest.raises(httpx.HTTPStatusError) as exc_info:
                download_ghcnh(station, year, tmp_path)

        assert exc_info.value.response.status_code == 404
        # No file was written on 404.
        assert not (tmp_path / station / f"GHCNh_{station}_{year}.psv").exists()


class Test404Range:
    def test_404_year_skipped_warning(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Range helper logs WARNING and continues past 404 years."""
        respx = pytest.importorskip("respx")
        _patch_sleep(monkeypatch)

        station = "744860-94789"

        url_ok_2022 = f"{GHCNH_BASE_URL}/by-year/2022/psv/GHCNh_{station}_2022.psv"
        url_missing_2023 = f"{GHCNH_BASE_URL}/by-year/2023/psv/GHCNh_{station}_2023.psv"
        url_ok_2024 = f"{GHCNH_BASE_URL}/by-year/2024/psv/GHCNh_{station}_2024.psv"

        with respx.mock(assert_all_called=True) as mock:
            mock.get(url_ok_2022).respond(200, content=b"y2022")
            mock.get(url_missing_2023).respond(404)
            mock.get(url_ok_2024).respond(200, content=b"y2024")
            with caplog.at_level(logging.WARNING, logger="tradewinds.weather._fetchers.ghcnh"):
                paths = download_ghcnh_range(station, 2022, 2024, tmp_path)

        # Only the 2 successful years come back; 2023 is silently dropped.
        assert len(paths) == 2
        assert paths[0].name == f"GHCNh_{station}_2022.psv"
        assert paths[1].name == f"GHCNh_{station}_2024.psv"
        # WARNING logged for the 404 year.
        assert any("2023" in r.message and "404" in r.message for r in caplog.records)

    def test_5xx_still_raises_in_range(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Transient archive failures must NOT be silently swallowed."""
        respx = pytest.importorskip("respx")
        _patch_sleep(monkeypatch)
        # _http.download_with_retry will retry then raise; suppress its sleeps too.
        monkeypatch.setattr("tradewinds._internal._http.time.sleep", lambda _: None)

        station = "744860-94789"
        url_500 = f"{GHCNH_BASE_URL}/by-year/2022/psv/GHCNh_{station}_2022.psv"

        with respx.mock() as mock:
            mock.get(url_500).respond(500)
            with pytest.raises(httpx.HTTPStatusError) as exc_info:
                download_ghcnh_range(station, 2022, 2024, tmp_path)

        assert exc_info.value.response.status_code == 500

    def test_empty_range(self, tmp_path: Path) -> None:
        """end_year < start_year returns []. No HTTP attempted."""
        paths = download_ghcnh_range("744860-94789", 2024, 2022, tmp_path)
        assert paths == []

    def test_single_year_range(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """start_year == end_year fetches exactly one year (inclusive)."""
        respx = pytest.importorskip("respx")
        _patch_sleep(monkeypatch)

        station = "744860-94789"
        year = 2024
        url = f"{GHCNH_BASE_URL}/by-year/{year}/psv/GHCNh_{station}_{year}.psv"
        with respx.mock(assert_all_called=True) as mock:
            mock.get(url).respond(200, content=b"y2024")
            paths = download_ghcnh_range(station, year, year, tmp_path)

        assert len(paths) == 1
        assert paths[0].name == f"GHCNh_{station}_{year}.psv"


# ---------------------------------------------------------------------------
# Cache behavior
# ---------------------------------------------------------------------------
class TestCache:
    def test_existing_file_skipped(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """If the file already exists, no HTTP request is made."""
        respx = pytest.importorskip("respx")
        _patch_sleep(monkeypatch)

        station = "744860-94789"
        year = 2024
        cached = tmp_path / station / f"GHCNh_{station}_{year}.psv"
        cached.parent.mkdir(parents=True, exist_ok=True)
        cached.write_bytes(b"already-here")

        # respx.mock(assert_all_called=True) would catch any unexpected
        # HTTP — but we DON'T register routes, so the assertion is implicit:
        # an unhandled request would raise.
        with respx.mock(assert_all_mocked=True):
            path = download_ghcnh(station, year, tmp_path)

        assert path == cached
        assert path.read_bytes() == b"already-here"

    def test_skip_cache_forces_redownload(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """skip_cache=True ignores the existing file and refetches."""
        respx = pytest.importorskip("respx")
        _patch_sleep(monkeypatch)

        station = "744860-94789"
        year = 2024
        cached = tmp_path / station / f"GHCNh_{station}_{year}.psv"
        cached.parent.mkdir(parents=True, exist_ok=True)
        cached.write_bytes(b"old-content")

        url = f"{GHCNH_BASE_URL}/by-year/{year}/psv/GHCNh_{station}_{year}.psv"
        with respx.mock(assert_all_called=True) as mock:
            mock.get(url).respond(200, content=b"new-content")
            path = download_ghcnh(station, year, tmp_path, skip_cache=True)

        assert path.read_bytes() == b"new-content"

    def test_skip_cache_propagates_through_range(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """download_ghcnh_range forwards skip_cache to each per-year call."""
        respx = pytest.importorskip("respx")
        _patch_sleep(monkeypatch)

        station = "744860-94789"
        # Pre-seed two cached years
        for year in (2022, 2023):
            cached = tmp_path / station / f"GHCNh_{station}_{year}.psv"
            cached.parent.mkdir(parents=True, exist_ok=True)
            cached.write_bytes(b"stale")

        url_2022 = f"{GHCNH_BASE_URL}/by-year/2022/psv/GHCNh_{station}_2022.psv"
        url_2023 = f"{GHCNH_BASE_URL}/by-year/2023/psv/GHCNh_{station}_2023.psv"

        with respx.mock(assert_all_called=True) as mock:
            mock.get(url_2022).respond(200, content=b"fresh-2022")
            mock.get(url_2023).respond(200, content=b"fresh-2023")
            paths = download_ghcnh_range(
                station,
                2022,
                2023,
                tmp_path,
                skip_cache=True,
            )

        assert paths[0].read_bytes() == b"fresh-2022"
        assert paths[1].read_bytes() == b"fresh-2023"


# ---------------------------------------------------------------------------
# Contiguous range behavior
# ---------------------------------------------------------------------------
class TestContiguousRange:
    def test_multi_year_contiguous(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Five contiguous years all-succeed produce 5 files in order."""
        respx = pytest.importorskip("respx")
        _patch_sleep(monkeypatch)

        station = "744860-94789"
        years = range(2020, 2025)  # 2020-2024 inclusive

        with respx.mock(assert_all_called=True) as mock:
            for year in years:
                url = f"{GHCNH_BASE_URL}/by-year/{year}/psv/GHCNh_{station}_{year}.psv"
                mock.get(url).respond(200, content=f"y{year}".encode())
            paths = download_ghcnh_range(station, 2020, 2024, tmp_path)

        assert len(paths) == 5
        # Chronological order
        for path, year in zip(paths, years, strict=True):
            assert path.name == f"GHCNh_{station}_{year}.psv"
            assert path.read_bytes() == f"y{year}".encode()

    def test_mixed_cache_and_fetch(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Range: middle year cached, surrounding years fetched."""
        respx = pytest.importorskip("respx")
        _patch_sleep(monkeypatch)

        station = "744860-94789"

        # Pre-seed 2023 only
        cached = tmp_path / station / f"GHCNh_{station}_2023.psv"
        cached.parent.mkdir(parents=True, exist_ok=True)
        cached.write_bytes(b"cached-2023")

        url_2022 = f"{GHCNH_BASE_URL}/by-year/2022/psv/GHCNh_{station}_2022.psv"
        url_2024 = f"{GHCNH_BASE_URL}/by-year/2024/psv/GHCNh_{station}_2024.psv"

        with respx.mock(assert_all_called=True) as mock:
            mock.get(url_2022).respond(200, content=b"fetched-2022")
            mock.get(url_2024).respond(200, content=b"fetched-2024")
            paths = download_ghcnh_range(station, 2022, 2024, tmp_path)

        assert len(paths) == 3
        assert paths[0].read_bytes() == b"fetched-2022"
        assert paths[1].read_bytes() == b"cached-2023"
        assert paths[2].read_bytes() == b"fetched-2024"

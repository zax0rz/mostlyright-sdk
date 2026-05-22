"""Tests for tradewinds.weather._fetchers.iem_asos.

Sprint 0 Wave 3B (Lane F) — covers:
- ``_monthly_chunks``: single-month, multi-month, year-boundary, day-1 start,
  inverted ranges.
- ``_build_iem_url``: snapshot test for a known station+date+report_type.
- End-exclusive quirk: a chunk including 2025-01-31..2025-02-15 must use
  ``day2=2025-03-01`` for the second chunk and ``day2=2025-02-01`` for the
  first (i.e. the next-month boundary).
- Cache behaviour: existing file is reused; ``skip_cache=True`` re-downloads.
- 5xx retry path: mocked ``download_with_retry`` is invoked once per chunk.

The fetcher itself does not need network access; all HTTP is mocked.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from unittest.mock import patch

import pytest
from tradewinds._internal.models.station import StationInfo
from tradewinds.weather._fetchers.iem_asos import (
    IEM_BASE_URL,
    IEM_POLITE_DELAY,
    _build_iem_url,
    _monthly_chunks,
    download_iem_asos,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _make_station(code: str = "NYC", icao: str = "KNYC") -> StationInfo:
    """Construct a minimal StationInfo for tests. Only ``code`` is sent to IEM."""
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


# ---------------------------------------------------------------------------
# Module constants
# ---------------------------------------------------------------------------
class TestModuleConstants:
    def test_polite_delay_is_one_second(self) -> None:
        # University server — be courteous.
        assert IEM_POLITE_DELAY == 1.0

    def test_base_url_is_iem_asos(self) -> None:
        assert IEM_BASE_URL == "https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py"


# ---------------------------------------------------------------------------
# _monthly_chunks
# ---------------------------------------------------------------------------
class TestMonthlyChunks:
    """After Codex W3B P1 fix: chunks ALWAYS month-aligned at start.

    The fix prevents the cache-key bug where Jan 15-31 stored partial data
    under `iem_202501_metar.csv` and a subsequent Jan 1-31 request hit that
    cache returning incomplete data. Trade-off: minor over-fetch in the
    first month; documented in _monthly_chunks docstring.
    """

    def test_single_month_mid_month_range(self) -> None:
        chunks = _monthly_chunks(date(2025, 1, 5), date(2025, 1, 20))
        # Always month-aligned at start; over-fetch Jan 1-5 is fine.
        assert chunks == [(date(2025, 1, 1), date(2025, 2, 1))]

    def test_single_full_month(self) -> None:
        chunks = _monthly_chunks(date(2025, 6, 1), date(2025, 6, 30))
        assert chunks == [(date(2025, 6, 1), date(2025, 7, 1))]

    def test_multi_month_range(self) -> None:
        chunks = _monthly_chunks(date(2025, 1, 15), date(2025, 3, 10))
        assert chunks == [
            (date(2025, 1, 1), date(2025, 2, 1)),
            (date(2025, 2, 1), date(2025, 3, 1)),
            (date(2025, 3, 1), date(2025, 4, 1)),
        ]

    def test_year_boundary(self) -> None:
        """December chunk must roll into next year's January 1st."""
        chunks = _monthly_chunks(date(2024, 12, 28), date(2025, 1, 5))
        assert chunks == [
            (date(2024, 12, 1), date(2025, 1, 1)),
            (date(2025, 1, 1), date(2025, 2, 1)),
        ]

    def test_end_exclusive_quirk_spanning_jan_31(self) -> None:
        """Explicit coverage of the IEM end-exclusive quirk.

        For caller window 2025-01-31..2025-02-15:
        - First chunk covers Jan (always month-aligned), end=Feb 1 (exclusive).
        - Second chunk covers Feb, day2 must be 2025-03-01 (NOT 2025-02-16).
        """
        chunks = _monthly_chunks(date(2025, 1, 31), date(2025, 2, 15))
        assert chunks == [
            (date(2025, 1, 1), date(2025, 2, 1)),
            (date(2025, 2, 1), date(2025, 3, 1)),
        ]
        # The second chunk's exclusive end must be March 1st, not Feb 16th.
        assert chunks[1][1] == date(2025, 3, 1)

    def test_single_day_range(self) -> None:
        chunks = _monthly_chunks(date(2025, 6, 15), date(2025, 6, 15))
        # Single mid-month day still over-fetches to the full month.
        assert chunks == [(date(2025, 6, 1), date(2025, 7, 1))]

    def test_inverted_range_returns_empty(self) -> None:
        """end < start: caller error; return [] rather than crash."""
        assert _monthly_chunks(date(2025, 6, 15), date(2025, 6, 1)) == []

    def test_codex_w3b_p1_cache_key_idempotent(self) -> None:
        """Regression: two requests for overlapping ranges within the same month
        produce identical chunks (so cache key matches), preventing the partial-
        month-served-as-full bug Codex W3B P1 flagged."""
        chunks_a = _monthly_chunks(date(2025, 1, 15), date(2025, 1, 31))
        chunks_b = _monthly_chunks(date(2025, 1, 1), date(2025, 1, 31))
        assert chunks_a == chunks_b
        assert chunks_a == [(date(2025, 1, 1), date(2025, 2, 1))]


# ---------------------------------------------------------------------------
# _build_iem_url
# ---------------------------------------------------------------------------
class TestBuildIemUrl:
    def test_url_snapshot_metar(self) -> None:
        """Locked snapshot of the param shape — byte-for-byte v0.14.1 parity."""
        station = _make_station(code="NYC", icao="KNYC")
        url = _build_iem_url(station, date(2025, 4, 1), date(2025, 5, 1), report_type=3)
        assert url == (
            "https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py"
            "?station=NYC"
            "&data=all&tz=Etc/UTC&format=comma&latlon=no&elev=no"
            "&missing=M&trace=T&direct=no&report_type=3"
            "&year1=2025&month1=4&day1=1"
            "&year2=2025&month2=5&day2=1"
        )

    def test_url_snapshot_speci(self) -> None:
        station = _make_station(code="ORD", icao="KORD")
        url = _build_iem_url(station, date(2024, 12, 28), date(2025, 1, 1), report_type=4)
        # Year-boundary call uses next-year exclusive end.
        assert url == (
            "https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py"
            "?station=ORD"
            "&data=all&tz=Etc/UTC&format=comma&latlon=no&elev=no"
            "&missing=M&trace=T&direct=no&report_type=4"
            "&year1=2024&month1=12&day1=28"
            "&year2=2025&month2=1&day2=1"
        )

    def test_url_uses_station_code_not_icao(self) -> None:
        """IEM ASOS wants the 3-letter code; the leading K is NOT sent."""
        station = _make_station(code="NYC", icao="KNYC")
        url = _build_iem_url(station, date(2025, 1, 1), date(2025, 2, 1), report_type=3)
        assert "station=NYC" in url
        assert "station=KNYC" not in url


# ---------------------------------------------------------------------------
# download_iem_asos: cache + retry
# ---------------------------------------------------------------------------
class TestDownloadIemAsos:
    def test_writes_one_file_per_chunk(self, tmp_path: Path) -> None:
        station = _make_station()
        calls: list[tuple[str, Path]] = []

        def fake_download(url: str, dest: Path) -> None:
            calls.append((url, dest))
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(b"station,valid\nNYC,2025-01-01 00:51\n")

        with (
            patch(
                "tradewinds.weather._fetchers.iem_asos.download_with_retry",
                side_effect=fake_download,
            ),
            patch("tradewinds.weather._fetchers.iem_asos.time.sleep") as mock_sleep,
        ):
            paths = download_iem_asos(
                station,
                date(2025, 1, 15),
                date(2025, 2, 10),
                tmp_path,
                report_type=3,
            )

        # Two chunks → two downloads, two paths, two polite sleeps.
        assert len(calls) == 2
        assert len(paths) == 2
        assert mock_sleep.call_count == 2
        mock_sleep.assert_any_call(IEM_POLITE_DELAY)
        # Files land under dest_dir/<station.code>/
        for p in paths:
            assert p.parent == tmp_path / "NYC"
            assert p.exists()
        assert paths[0].name == "iem_202501_metar.csv"
        assert paths[1].name == "iem_202502_metar.csv"

    def test_speci_uses_speci_suffix(self, tmp_path: Path) -> None:
        station = _make_station()

        def fake_download(url: str, dest: Path) -> None:
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(b"x")

        with (
            patch(
                "tradewinds.weather._fetchers.iem_asos.download_with_retry",
                side_effect=fake_download,
            ),
            patch("tradewinds.weather._fetchers.iem_asos.time.sleep"),
        ):
            paths = download_iem_asos(
                station,
                date(2025, 1, 1),
                date(2025, 1, 31),
                tmp_path,
                report_type=4,
            )
        assert len(paths) == 1
        assert paths[0].name == "iem_202501_speci.csv"

    def test_invalid_report_type_raises(self, tmp_path: Path) -> None:
        station = _make_station()
        with pytest.raises(ValueError, match="report_type"):
            download_iem_asos(
                station,
                date(2025, 1, 1),
                date(2025, 1, 31),
                tmp_path,
                report_type=99,
            )

    def test_cache_hit_skips_download(self, tmp_path: Path) -> None:
        """An existing local file is returned without re-fetching."""
        station = _make_station()
        # Pre-create the cache file the fetcher would produce for Jan 2025.
        cache_dir = tmp_path / "NYC"
        cache_dir.mkdir(parents=True, exist_ok=True)
        cached = cache_dir / "iem_202501_metar.csv"
        cached.write_bytes(b"cached")

        with (
            patch("tradewinds.weather._fetchers.iem_asos.download_with_retry") as mock_dl,
            patch("tradewinds.weather._fetchers.iem_asos.time.sleep") as mock_sleep,
        ):
            paths = download_iem_asos(
                station,
                date(2025, 1, 1),
                date(2025, 1, 31),
                tmp_path,
                report_type=3,
            )

        assert paths == [cached]
        assert paths[0].read_bytes() == b"cached"
        mock_dl.assert_not_called()
        mock_sleep.assert_not_called()

    def test_skip_cache_re_downloads(self, tmp_path: Path) -> None:
        """skip_cache=True forces a re-fetch even when the file exists."""
        station = _make_station()
        cache_dir = tmp_path / "NYC"
        cache_dir.mkdir(parents=True, exist_ok=True)
        cached = cache_dir / "iem_202501_metar.csv"
        cached.write_bytes(b"stale")

        def fake_download(url: str, dest: Path) -> None:
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(b"fresh")

        with (
            patch(
                "tradewinds.weather._fetchers.iem_asos.download_with_retry",
                side_effect=fake_download,
            ) as mock_dl,
            patch("tradewinds.weather._fetchers.iem_asos.time.sleep"),
        ):
            paths = download_iem_asos(
                station,
                date(2025, 1, 1),
                date(2025, 1, 31),
                tmp_path,
                skip_cache=True,
                report_type=3,
            )

        assert mock_dl.call_count == 1
        assert paths[0].read_bytes() == b"fresh"

    def test_retry_path_via_mocked_helper(self, tmp_path: Path) -> None:
        """The fetcher delegates retries to ``download_with_retry`` unchanged.

        We assert one invocation per chunk with the exact URL we'd expect —
        proving the 5xx retry path is reachable via the helper. (The helper
        itself is tested in packages/core/tests/_internal/test_http.py.)
        """
        station = _make_station()
        captured_urls: list[str] = []

        def fake_download(url: str, dest: Path) -> None:
            captured_urls.append(url)
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(b"ok")

        with (
            patch(
                "tradewinds.weather._fetchers.iem_asos.download_with_retry",
                side_effect=fake_download,
            ),
            patch("tradewinds.weather._fetchers.iem_asos.time.sleep"),
        ):
            download_iem_asos(
                station,
                date(2025, 1, 31),
                date(2025, 2, 15),
                tmp_path,
                report_type=3,
            )

        # Two chunks, two URLs. After codex W3B P1 fix, both chunks start on
        # the 1st of their month (cache idempotence), with end-exclusive day2.
        assert len(captured_urls) == 2
        assert "day1=1" in captured_urls[0] and "month1=1" in captured_urls[0]
        assert "day2=1" in captured_urls[0] and "month2=2" in captured_urls[0]
        assert "month1=2" in captured_urls[1] and "day1=1" in captured_urls[1]
        assert "month2=3" in captured_urls[1] and "day2=1" in captured_urls[1]

    def test_download_helper_error_propagates(self, tmp_path: Path) -> None:
        """Persistent 5xx (or 404) inside the helper bubbles up to the caller."""
        station = _make_station()

        def boom(url: str, dest: Path) -> None:
            raise RuntimeError("simulated retry exhaustion")

        with (
            patch("tradewinds.weather._fetchers.iem_asos.download_with_retry", side_effect=boom),
            patch("tradewinds.weather._fetchers.iem_asos.time.sleep"),
            pytest.raises(RuntimeError, match="simulated retry exhaustion"),
        ):
            download_iem_asos(
                station,
                date(2025, 1, 1),
                date(2025, 1, 31),
                tmp_path,
                report_type=3,
            )


# ---------------------------------------------------------------------------
# Station-code boundary validation (Rob PR #2 C1/H8)
# ---------------------------------------------------------------------------
class TestStationBoundaryValidation:
    """``download_iem_asos`` rejects path-traversal via ``station.code``.

    ``StationInfo.code`` is supposed to be a curated ICAO from the registry,
    but defense-in-depth a check at the URL/path boundary catches any
    registry corruption or mis-instantiation. No HTTP mock - validation must
    fail BEFORE any request is built.
    """

    @pytest.mark.parametrize(
        "payload",
        [
            "../evil",
            "..",
            "../../../tmp/evil",
            "NYC/../etc",
            "NYC/etc",
            "NYC\\windows",
            "NYC\x00",
            "NYC\n",
            "N YC",
            "nyc",  # lowercase rejected
        ],
    )
    def test_download_iem_asos_rejects_traversal(self, tmp_path: Path, payload: str) -> None:
        from tradewinds.weather._fetchers.iem_asos import download_iem_asos

        bad = _make_station(code=payload, icao="KNYC")
        with pytest.raises(ValueError, match="STATION_CODE_RE"):
            download_iem_asos(
                bad,
                date(2025, 1, 1),
                date(2025, 1, 31),
                tmp_path,
                report_type=3,
            )

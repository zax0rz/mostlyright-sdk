"""Tests for mostlyright.weather._fetchers.iem_asos.

Phase 1.5 PERF-01/02 — yearly-chunked CSV downloads with PR #85 cache-filename
and ``_partial`` namespace semantics:

- Yearly chunker (PERF-01) via :mod:`~mostlyright.weather._fetchers._iem_chunks`,
  with the mostlyright-specific normalization that clamps caller ``start`` to
  ``date(start.year, 1, 1)`` for cache idempotence across per-month research.py
  callers.
- Cache filename encodes the full chunk window (PERF-02 pattern A).
- ``skip_cache=True`` OR ``chunk_end > today_utc`` routes to the ``_partial``
  namespace that backfill never reads (PERF-02 OR-not-AND / Pitfall 3).
- Cutoff uses UTC, not local (Pitfall 2): ``datetime.now(timezone.utc).date()``.

The fetcher itself does not need network access; all HTTP is mocked.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path
from unittest.mock import patch

import pytest
from mostlyright._internal.models.station import StationInfo
from mostlyright.weather._fetchers.iem_asos import (
    IEM_BASE_URL,
    IEM_POLITE_DELAY,
    _build_iem_url,
    _iem_cache_filename,
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


# A frozen "today" in the past so every test date range is fully historical.
# Tests that need the partial branch override this fixture explicitly.
_FROZEN_TODAY = date(2026, 5, 22)


@pytest.fixture
def frozen_today_utc():
    """Patch ``datetime.now(UTC).date()`` to a fixed historical date."""
    fake_dt = datetime(2026, 5, 22, 12, 0, 0, tzinfo=UTC)

    class _FakeDatetime(datetime):
        @classmethod
        def now(cls, tz=None):  # type: ignore[override]
            return fake_dt if tz is UTC or tz is not None else fake_dt.replace(tzinfo=None)

    with patch("mostlyright.weather._fetchers.iem_asos.datetime", _FakeDatetime):
        yield _FROZEN_TODAY


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
# _iem_cache_filename
# ---------------------------------------------------------------------------
class TestIemCacheFilename:
    """PERF-02 PR #85 cache-filename pattern."""

    def test_canonical_filename_metar(self) -> None:
        assert (
            _iem_cache_filename(date(2024, 1, 1), date(2025, 1, 1), "metar", partial=False)
            == "iem_2024-01-01_2025-01-01_metar.csv"
        )

    def test_partial_filename_metar(self) -> None:
        assert (
            _iem_cache_filename(date(2024, 1, 1), date(2025, 1, 1), "metar", partial=True)
            == "iem_2024-01-01_2025-01-01_partial_metar.csv"
        )

    def test_canonical_filename_speci(self) -> None:
        assert (
            _iem_cache_filename(date(2025, 1, 1), date(2026, 1, 1), "speci", partial=False)
            == "iem_2025-01-01_2026-01-01_speci.csv"
        )

    def test_partial_filename_speci(self) -> None:
        assert (
            _iem_cache_filename(date(2025, 1, 1), date(2026, 1, 1), "speci", partial=True)
            == "iem_2025-01-01_2026-01-01_partial_speci.csv"
        )


# ---------------------------------------------------------------------------
# _build_iem_url (unchanged from monthly chunker era — URL params are
# date-driven regardless of how the dates were produced)
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
# download_iem_asos — yearly chunks + PR #85 cache + partial namespace
# ---------------------------------------------------------------------------
class TestDownloadIemAsosYearlyChunks:
    """PERF-01 — one HTTP request per calendar year (was: one per calendar month).

    mostlyright-specific normalization: caller's ``start`` is normalized to
    ``date(start.year, 1, 1)`` so per-month callers share a yearly cache key.
    """

    def test_single_month_caller_emits_one_yearly_chunk(
        self, tmp_path: Path, frozen_today_utc: date
    ) -> None:
        """A month-window caller produces ONE yearly request (was: one per month)."""
        station = _make_station()
        calls: list[tuple[str, Path]] = []

        def fake_download(url: str, dest: Path) -> None:
            calls.append((url, dest))
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(b"station,valid\nNYC,2025-01-01 00:51\n")

        with (
            patch(
                "mostlyright.weather._fetchers.iem_asos.download_with_retry",
                side_effect=fake_download,
            ),
            patch("mostlyright.weather._fetchers.iem_asos.time.sleep"),
        ):
            paths = download_iem_asos(
                station,
                date(2025, 1, 15),
                date(2025, 2, 10),
                tmp_path,
                report_type=3,
            )

        # Caller spans Jan-Feb 2025 but both months are in the same calendar year,
        # so normalization produces ONE yearly chunk → ONE HTTP request.
        assert len(calls) == 1
        assert len(paths) == 1
        # Cache filename encodes the FULL chunk window (Jan 1 → Jan 1 next year).
        assert paths[0].name == "iem_2025-01-01_2026-01-01_metar.csv"

    def test_per_month_calls_share_yearly_cache_key(
        self, tmp_path: Path, frozen_today_utc: date
    ) -> None:
        """Two month-window calls in the same year produce the SAME cache filename.

        This is the mostlyright-specific normalization payoff: research.py's
        per-month fetch loop hits the cache after the first month, not 12 times.
        """
        station = _make_station()
        fetched_urls: list[str] = []

        def fake_download(url: str, dest: Path) -> None:
            fetched_urls.append(url)
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(b"ok")

        with (
            patch(
                "mostlyright.weather._fetchers.iem_asos.download_with_retry",
                side_effect=fake_download,
            ),
            patch("mostlyright.weather._fetchers.iem_asos.time.sleep"),
        ):
            paths_jan = download_iem_asos(
                station, date(2025, 1, 1), date(2025, 1, 31), tmp_path, report_type=3
            )
            paths_feb = download_iem_asos(
                station, date(2025, 2, 1), date(2025, 2, 28), tmp_path, report_type=3
            )

        # Both calls resolve to the same cache file.
        assert paths_jan == paths_feb
        # Only ONE network request fired (Jan's miss; Feb hit the cache).
        assert len(fetched_urls) == 1

    def test_cross_year_range_produces_one_chunk_per_year(
        self, tmp_path: Path, frozen_today_utc: date
    ) -> None:
        """A range spanning N calendar years → N yearly chunks → N HTTP requests."""
        station = _make_station()
        fetched: list[str] = []

        def fake_download(url: str, dest: Path) -> None:
            fetched.append(url)
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(b"ok")

        with (
            patch(
                "mostlyright.weather._fetchers.iem_asos.download_with_retry",
                side_effect=fake_download,
            ),
            patch("mostlyright.weather._fetchers.iem_asos.time.sleep"),
        ):
            paths = download_iem_asos(
                station,
                date(2023, 6, 1),
                date(2025, 6, 1),
                tmp_path,
                report_type=3,
            )

        # 3 yearly chunks: 2023, 2024, 2025.
        assert len(paths) == 3
        assert len(fetched) == 3
        assert paths[0].name == "iem_2023-01-01_2024-01-01_metar.csv"
        assert paths[1].name == "iem_2024-01-01_2025-01-01_metar.csv"
        assert paths[2].name == "iem_2025-01-01_2026-01-01_metar.csv"

    def test_speci_uses_speci_suffix(self, tmp_path: Path, frozen_today_utc: date) -> None:
        station = _make_station()

        def fake_download(url: str, dest: Path) -> None:
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(b"x")

        with (
            patch(
                "mostlyright.weather._fetchers.iem_asos.download_with_retry",
                side_effect=fake_download,
            ),
            patch("mostlyright.weather._fetchers.iem_asos.time.sleep"),
        ):
            paths = download_iem_asos(
                station,
                date(2025, 1, 1),
                date(2025, 1, 31),
                tmp_path,
                report_type=4,
            )
        assert len(paths) == 1
        assert paths[0].name == "iem_2025-01-01_2026-01-01_speci.csv"

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


# ---------------------------------------------------------------------------
# Partial-namespace semantics (PERF-02 OR-branch + Pitfalls 2/3)
# ---------------------------------------------------------------------------
class TestPartialNamespace:
    def test_canonical_cache_hit_skips_download(
        self, tmp_path: Path, frozen_today_utc: date
    ) -> None:
        """An existing canonical file is returned without re-fetching."""
        station = _make_station()
        cache_dir = tmp_path / "NYC"
        cache_dir.mkdir(parents=True, exist_ok=True)
        cached = cache_dir / "iem_2025-01-01_2026-01-01_metar.csv"
        cached.write_bytes(b"cached")

        with (
            patch("mostlyright.weather._fetchers.iem_asos.download_with_retry") as mock_dl,
            patch("mostlyright.weather._fetchers.iem_asos.time.sleep") as mock_sleep,
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

    def test_skip_cache_alone_writes_to_partial(
        self, tmp_path: Path, frozen_today_utc: date
    ) -> None:
        """PERF-02 OR-branch A: skip_cache=True alone routes to _partial namespace.

        Every chunk is historical (chunk_end <= today_utc), so without skip_cache
        the canonical namespace would be used. With skip_cache=True, all chunks
        get the _partial infix — preserving the canonical cache for backfill.
        """
        station = _make_station()
        captured_dests: list[Path] = []

        def fake_download(url: str, dest: Path) -> None:
            captured_dests.append(dest)
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(b"fresh")

        with (
            patch(
                "mostlyright.weather._fetchers.iem_asos.download_with_retry",
                side_effect=fake_download,
            ),
            patch("mostlyright.weather._fetchers.iem_asos.time.sleep"),
        ):
            paths = download_iem_asos(
                station,
                date(2020, 1, 1),
                date(2020, 12, 31),  # fully historical given frozen_today=2026-05-22
                tmp_path,
                skip_cache=True,
                report_type=3,
            )

        # All chunks routed to _partial namespace.
        assert all("_partial_" in p.name for p in paths), [p.name for p in paths]
        assert all("_partial_" in p.name for p in captured_dests), [p.name for p in captured_dests]
        assert paths[0].name == "iem_2020-01-01_2021-01-01_partial_metar.csv"

    def test_future_chunk_end_alone_writes_to_partial(self, tmp_path: Path) -> None:
        """PERF-02 OR-branch B: chunk_end > today_utc alone routes to _partial.

        Frozen ``today_utc = 2026-05-22``; caller's end is ``2027-01-15`` — well
        in the future. The 2027 chunk (end=2028-01-01 > today_utc) is partial.
        The 2026 chunk (end=2027-01-01 > today_utc) is ALSO partial. Earlier
        years' chunks would be canonical (their end <= today_utc) but we test
        the future-only case here.
        """
        station = _make_station()
        # Freeze today_utc inside the fetcher to a known past date.
        fake_dt = datetime(2026, 5, 22, 12, 0, 0, tzinfo=UTC)

        class _FakeDt(datetime):
            @classmethod
            def now(cls, tz=None):  # type: ignore[override]
                return fake_dt

        captured: list[Path] = []

        def fake_download(url: str, dest: Path) -> None:
            captured.append(dest)
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(b"x")

        with (
            patch("mostlyright.weather._fetchers.iem_asos.datetime", _FakeDt),
            patch(
                "mostlyright.weather._fetchers.iem_asos.download_with_retry",
                side_effect=fake_download,
            ),
            patch("mostlyright.weather._fetchers.iem_asos.time.sleep"),
        ):
            paths = download_iem_asos(
                station,
                date(2027, 1, 1),
                date(2027, 1, 15),
                tmp_path,
                report_type=3,
                # skip_cache=False — proves the future-end branch alone triggers _partial
            )

        # The 2027 chunk's end = date(2028,1,1) > today_utc (2026-05-22) → partial.
        assert len(paths) == 1
        assert "_partial_" in paths[0].name
        assert paths[0].name == "iem_2027-01-01_2028-01-01_partial_metar.csv"

    def test_chunk_end_equal_today_utc_is_canonical(self, tmp_path: Path) -> None:
        """Boundary: ``chunk_end == today_utc`` is NOT partial (strict >).

        IEM ``day2`` is exclusive, so chunk_end = today_utc means "covers up to
        today_utc - 1" — which is fully populated.
        """
        station = _make_station()
        # Freeze today_utc to the chunk's exclusive-end day.
        fake_dt = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)

        class _FakeDt(datetime):
            @classmethod
            def now(cls, tz=None):  # type: ignore[override]
                return fake_dt

        def fake_download(url: str, dest: Path) -> None:
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(b"x")

        with (
            patch("mostlyright.weather._fetchers.iem_asos.datetime", _FakeDt),
            patch(
                "mostlyright.weather._fetchers.iem_asos.download_with_retry",
                side_effect=fake_download,
            ),
            patch("mostlyright.weather._fetchers.iem_asos.time.sleep"),
        ):
            paths = download_iem_asos(
                station,
                date(2025, 1, 1),
                date(2025, 12, 31),
                tmp_path,
                report_type=3,
            )

        # chunk_end = date(2026,1,1) and today_utc = date(2026,1,1)
        # → NOT (chunk_end > today_utc) → canonical.
        assert len(paths) == 1
        assert "_partial_" not in paths[0].name
        assert paths[0].name == "iem_2025-01-01_2026-01-01_metar.csv"

    def test_cutoff_uses_utc_not_local(self, tmp_path: Path) -> None:
        """Pitfall 2: cutoff uses ``datetime.now(UTC).date()``, NOT
        ``date.today()`` (which truncates on non-UTC hosts at the day boundary).

        Assertion strategy: AST-walk the production module to look for any
        ``Name('date').Attribute('today').Call(...)`` pattern in actual code.
        A grep on the source text would false-positive on docstring narrative
        that mentions ``date.today()`` as the anti-pattern being avoided.
        """
        import ast
        import inspect

        from mostlyright.weather._fetchers import iem_asos as fetcher_mod

        tree = ast.parse(inspect.getsource(fetcher_mod))

        forbidden = []
        utc_now_calls = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                # date.today() pattern
                if (
                    isinstance(node.func, ast.Attribute)
                    and node.func.attr == "today"
                    and isinstance(node.func.value, ast.Name)
                    and node.func.value.id == "date"
                ):
                    forbidden.append(ast.dump(node))
                # datetime.now(...) pattern — we want at least one
                if (
                    isinstance(node.func, ast.Attribute)
                    and node.func.attr == "now"
                    and isinstance(node.func.value, ast.Name)
                    and node.func.value.id == "datetime"
                ):
                    utc_now_calls.append(node)

        assert not forbidden, (
            f"Pitfall 2: forbidden date.today() call in iem_asos.py code: {forbidden}"
        )
        assert utc_now_calls, "Expected at least one datetime.now(...) call for UTC cutoff"
        # At least one of those datetime.now() calls must be passing UTC (positionally
        # or as a keyword) to ensure timezone awareness.
        utc_aware = False
        for call in utc_now_calls:
            arg_names = [a.id for a in call.args if isinstance(a, ast.Name)]
            kwarg_names = [k.value.id for k in call.keywords if isinstance(k.value, ast.Name)]
            if "UTC" in arg_names or "UTC" in kwarg_names:
                utc_aware = True
                break
        assert utc_aware, "datetime.now(...) must be called with UTC for the cutoff"

    def test_partial_cache_never_hits(self, tmp_path: Path) -> None:
        """An existing _partial file MUST NOT short-circuit a canonical request.

        Setup: pre-create a canonical chunk (which is what a backfill would write).
        Then call with skip_cache=True — the request goes to the _partial namespace,
        misses (nothing there), and re-downloads. The canonical file is untouched.
        """
        station = _make_station()
        # Freeze today_utc so chunks for 2024 are fully historical.
        fake_dt = datetime(2026, 5, 22, 12, 0, 0, tzinfo=UTC)

        class _FakeDt(datetime):
            @classmethod
            def now(cls, tz=None):  # type: ignore[override]
                return fake_dt

        cache_dir = tmp_path / "NYC"
        cache_dir.mkdir(parents=True, exist_ok=True)
        canonical = cache_dir / "iem_2024-01-01_2025-01-01_metar.csv"
        canonical.write_bytes(b"canonical")

        fetched: list[str] = []

        def fake_download(url: str, dest: Path) -> None:
            fetched.append(url)
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(b"partial-fresh")

        with (
            patch("mostlyright.weather._fetchers.iem_asos.datetime", _FakeDt),
            patch(
                "mostlyright.weather._fetchers.iem_asos.download_with_retry",
                side_effect=fake_download,
            ),
            patch("mostlyright.weather._fetchers.iem_asos.time.sleep"),
        ):
            paths = download_iem_asos(
                station,
                date(2024, 6, 1),
                date(2024, 6, 30),
                tmp_path,
                skip_cache=True,  # forces _partial route
                report_type=3,
            )

        # Canonical file was NOT consumed: the call wrote a _partial file.
        assert canonical.read_bytes() == b"canonical"
        assert len(fetched) == 1
        assert "_partial_" in paths[0].name


# ---------------------------------------------------------------------------
# Retry path (helper delegation) — unchanged from monthly-era contract
# ---------------------------------------------------------------------------
class TestDownloadIemAsosRetry:
    def test_retry_path_via_mocked_helper(self, tmp_path: Path, frozen_today_utc: date) -> None:
        """The fetcher delegates retries to ``download_with_retry`` unchanged.

        One invocation per yearly chunk with the expected URL — proves the 5xx
        retry path is reachable via the helper. (The helper itself is tested in
        packages/core/tests/_internal/test_http.py.)
        """
        station = _make_station()
        captured_urls: list[str] = []

        def fake_download(url: str, dest: Path) -> None:
            captured_urls.append(url)
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(b"ok")

        with (
            patch(
                "mostlyright.weather._fetchers.iem_asos.download_with_retry",
                side_effect=fake_download,
            ),
            patch("mostlyright.weather._fetchers.iem_asos.time.sleep"),
        ):
            download_iem_asos(
                station,
                date(2024, 12, 1),
                date(2025, 2, 15),
                tmp_path,
                report_type=3,
            )

        # Two calendar years → two URL requests.
        assert len(captured_urls) == 2
        assert "year1=2024&month1=1&day1=1" in captured_urls[0]
        assert "year2=2025&month2=1&day2=1" in captured_urls[0]
        assert "year1=2025&month1=1&day1=1" in captured_urls[1]
        assert "year2=2026&month2=1&day2=1" in captured_urls[1]

    def test_download_helper_error_propagates(self, tmp_path: Path, frozen_today_utc: date) -> None:
        """Persistent 5xx (or 404) inside the helper bubbles up to the caller."""
        station = _make_station()

        def boom(url: str, dest: Path) -> None:
            raise RuntimeError("simulated retry exhaustion")

        with (
            patch("mostlyright.weather._fetchers.iem_asos.download_with_retry", side_effect=boom),
            patch("mostlyright.weather._fetchers.iem_asos.time.sleep"),
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
# Station-code boundary validation (Rob PR #2 C1/H8) — unchanged
# ---------------------------------------------------------------------------
class TestStationBoundaryValidation:
    """``download_iem_asos`` rejects path-traversal via ``station.code``.

    ``StationInfo.code`` is supposed to be a curated ICAO from the registry, but
    defense-in-depth a check at the URL/path boundary catches any registry
    corruption or mis-instantiation. No HTTP mock — validation must fail BEFORE
    any request is built.
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
        bad = _make_station(code=payload, icao="KNYC")
        with pytest.raises(ValueError, match="STATION_CODE_RE"):
            download_iem_asos(
                bad,
                date(2025, 1, 1),
                date(2025, 1, 31),
                tmp_path,
                report_type=3,
            )

"""Tests for tradewinds._internal._http.

Lifted from monorepo-v0.14.1/ingest/sources/_http.py — the public-API
retry helper used by historical fetchers (IEM, GHCNh, AWC, CLI).

v0.14.1 had no dedicated test_http.py for this module; coverage was
transitive via fetcher tests that mocked download_with_retry. We add
direct tests here so the helper is guarded before Wave 3 lifts the
fetchers.
"""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest
from tradewinds._internal._http import (
    BASE_DELAY,
    HTTP_TIMEOUT,
    MAX_RETRIES,
    TRANSIENT_CODES,
    download_with_retry,
)


class TestModuleConstants:
    def test_max_retries(self) -> None:
        assert MAX_RETRIES == 3

    def test_base_delay(self) -> None:
        assert BASE_DELAY == 1.0

    def test_http_timeout(self) -> None:
        assert HTTP_TIMEOUT == 30.0

    def test_transient_codes(self) -> None:
        assert frozenset({500, 502, 503, 504}) == TRANSIENT_CODES


class TestDownloadWithRetry:
    """download_with_retry covers happy path, 404 (permanent), and
    transient-error retry/exhaustion. Uses respx for httpx mocking."""

    def test_happy_path_writes_dest(self, tmp_path: Path) -> None:
        url = "https://example.test/data.csv"
        dest = tmp_path / "out" / "data.csv"
        try:
            import respx
        except ImportError:
            pytest.skip("respx not installed; skipping HTTP mock test")

        with respx.mock(assert_all_called=True) as mock:
            mock.get(url).respond(200, content=b"row1,row2\n")
            download_with_retry(url, dest)

        assert dest.exists()
        assert dest.read_bytes() == b"row1,row2\n"

    def test_404_raises_immediately(self, tmp_path: Path) -> None:
        url = "https://example.test/notfound.csv"
        dest = tmp_path / "x.csv"
        try:
            import respx
        except ImportError:
            pytest.skip("respx not installed")

        with respx.mock() as mock:
            mock.get(url).respond(404)
            with pytest.raises(httpx.HTTPStatusError):
                download_with_retry(url, dest)
        assert not dest.exists()

    def test_503_retried_then_succeeds(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        url = "https://example.test/flaky.csv"
        dest = tmp_path / "flaky.csv"
        try:
            import respx
        except ImportError:
            pytest.skip("respx not installed")

        # Don't actually sleep through retries
        monkeypatch.setattr("tradewinds._internal._http.time.sleep", lambda _: None)

        with respx.mock(assert_all_called=True) as mock:
            route = mock.get(url)
            route.side_effect = [
                httpx.Response(503),
                httpx.Response(503),
                httpx.Response(200, content=b"OK"),
            ]
            download_with_retry(url, dest)

        assert dest.read_bytes() == b"OK"

    def test_503_exhausts_retries(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        url = "https://example.test/always-503.csv"
        dest = tmp_path / "fail.csv"
        try:
            import respx
        except ImportError:
            pytest.skip("respx not installed")

        monkeypatch.setattr("tradewinds._internal._http.time.sleep", lambda _: None)

        with respx.mock() as mock:
            mock.get(url).respond(503)
            with pytest.raises(httpx.HTTPStatusError):
                download_with_retry(url, dest)
        assert not dest.exists()

    def test_atomic_write_via_tmp_file(self, tmp_path: Path) -> None:
        """The helper writes to dest.with_suffix(suffix + .tmp) first then renames."""
        url = "https://example.test/atomic.csv"
        dest = tmp_path / "atomic.csv"
        try:
            import respx
        except ImportError:
            pytest.skip("respx not installed")

        with respx.mock() as mock:
            mock.get(url).respond(200, content=b"final")
            download_with_retry(url, dest)

        # tmp file should NOT linger after successful rename
        assert dest.exists()
        assert dest.read_bytes() == b"final"
        assert not dest.with_suffix(".csv.tmp").exists()

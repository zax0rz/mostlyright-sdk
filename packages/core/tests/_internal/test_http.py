"""Tests for mostlyright._internal._http.

Lifted from monorepo-v0.14.1/ingest/sources/_http.py — the public-API
retry helper used by historical fetchers (IEM, GHCNh, AWC, CLI).

v0.14.1 had no dedicated test_http.py for this module; coverage was
transitive via fetcher tests that mocked download_with_retry. We add
direct tests here so the helper is guarded before Wave 3 lifts the
fetchers.
"""

from __future__ import annotations

import importlib
from pathlib import Path

import httpx
import pytest
from mostlyright._internal._http import (
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
        # Phase 1.5 PERF-03: bumped 30 -> 60 to match the ~12x payload increase
        # per IEM yearly chunk (PR #85 cf9eb85 round-2 HIGH-2 finding).
        assert HTTP_TIMEOUT == 60.0

    def test_transient_codes(self) -> None:
        # 429 (Too Many Requests) is retryable so IEM ASOS rate-limit bursts
        # during a fresh-cache parity run get backed-off + retried instead of
        # silently degrading research() output. Codex iter-2 wave-3 follow-up.
        assert frozenset({429, 500, 502, 503, 504}) == TRANSIENT_CODES


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

    def test_503_retried_then_succeeds(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        url = "https://example.test/flaky.csv"
        dest = tmp_path / "flaky.csv"
        try:
            import respx
        except ImportError:
            pytest.skip("respx not installed")

        # Don't actually sleep through retries
        monkeypatch.setattr("mostlyright._internal._http.time.sleep", lambda _: None)

        with respx.mock(assert_all_called=True) as mock:
            route = mock.get(url)
            route.side_effect = [
                httpx.Response(503),
                httpx.Response(503),
                httpx.Response(200, content=b"OK"),
            ]
            download_with_retry(url, dest)

        assert dest.read_bytes() == b"OK"

    def test_429_retried_then_succeeds(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """429 Too Many Requests is treated as transient (Codex iter-2 wave-3).

        Locks in the IEM ASOS rate-limit retry behaviour relied on by the
        Wave 3 parity gate: without retry on 429, fresh-cache fetches for
        long-range cases (e.g. case 4 KMIA, 12 months x 2 report_types)
        silently lose months when IEM rate-limits the burst.
        """
        url = "https://example.test/rate-limited.csv"
        dest = tmp_path / "rate-limited.csv"
        try:
            import respx
        except ImportError:
            pytest.skip("respx not installed")

        monkeypatch.setattr("mostlyright._internal._http.time.sleep", lambda _: None)

        with respx.mock(assert_all_called=True) as mock:
            route = mock.get(url)
            route.side_effect = [
                httpx.Response(429),
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

        monkeypatch.setattr("mostlyright._internal._http.time.sleep", lambda _: None)

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


class TestEnvOverrides:
    """GH #51: MOSTLYRIGHT_HTTP_MAX_RETRIES / MOSTLYRIGHT_HTTP_TIMEOUT env
    vars override the module-load defaults so batch callers can tune IEM
    429 behavior without monkey-patching site-packages."""

    @staticmethod
    def _reload(monkeypatch: pytest.MonkeyPatch, env: dict[str, str]) -> object:
        """Force re-evaluation of the module-load env reads."""
        for k, v in env.items():
            monkeypatch.setenv(k, v)
        import mostlyright._internal._http as http_mod

        return importlib.reload(http_mod)

    def test_max_retries_env_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        mod = self._reload(monkeypatch, {"MOSTLYRIGHT_HTTP_MAX_RETRIES": "1"})
        try:
            assert mod.MAX_RETRIES == 1
        finally:
            monkeypatch.delenv("MOSTLYRIGHT_HTTP_MAX_RETRIES", raising=False)
            importlib.reload(mod)

    def test_http_timeout_env_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        mod = self._reload(monkeypatch, {"MOSTLYRIGHT_HTTP_TIMEOUT": "5.5"})
        try:
            assert mod.HTTP_TIMEOUT == 5.5
        finally:
            monkeypatch.delenv("MOSTLYRIGHT_HTTP_TIMEOUT", raising=False)
            importlib.reload(mod)

    def test_defaults_when_env_unset(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("MOSTLYRIGHT_HTTP_MAX_RETRIES", raising=False)
        monkeypatch.delenv("MOSTLYRIGHT_HTTP_TIMEOUT", raising=False)
        import mostlyright._internal._http as http_mod

        mod = importlib.reload(http_mod)
        try:
            assert mod.MAX_RETRIES == 3
            assert mod.HTTP_TIMEOUT == 60.0
        finally:
            importlib.reload(mod)

    def test_invalid_max_retries_falls_back_to_default(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Non-integer / negative values must not crash module import — fall
        back to the default so a typo doesn't block legitimate fetches."""
        mod = self._reload(monkeypatch, {"MOSTLYRIGHT_HTTP_MAX_RETRIES": "not-a-number"})
        try:
            assert mod.MAX_RETRIES == 3
        finally:
            monkeypatch.delenv("MOSTLYRIGHT_HTTP_MAX_RETRIES", raising=False)
            importlib.reload(mod)

    def test_invalid_http_timeout_falls_back_to_default(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        mod = self._reload(monkeypatch, {"MOSTLYRIGHT_HTTP_TIMEOUT": "-1"})
        try:
            assert mod.HTTP_TIMEOUT == 60.0
        finally:
            monkeypatch.delenv("MOSTLYRIGHT_HTTP_TIMEOUT", raising=False)
            importlib.reload(mod)

    def test_zero_max_retries_falls_back_to_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """MAX_RETRIES drives ``range(MAX_RETRIES)`` in the retry loop, so 0
        would issue NO request and return without writing ``dest`` — a silent
        no-op download. Sub-1 values must fall back to the default, never 0."""
        mod = self._reload(monkeypatch, {"MOSTLYRIGHT_HTTP_MAX_RETRIES": "0"})
        try:
            assert mod.MAX_RETRIES == 3
        finally:
            monkeypatch.delenv("MOSTLYRIGHT_HTTP_MAX_RETRIES", raising=False)
            importlib.reload(mod)

    def test_max_retries_one_is_accepted(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """1 is the legitimate minimum (one attempt, no retry) and must be
        honored — the sub-1 guard rejects only values below 1."""
        mod = self._reload(monkeypatch, {"MOSTLYRIGHT_HTTP_MAX_RETRIES": "1"})
        try:
            assert mod.MAX_RETRIES == 1
        finally:
            monkeypatch.delenv("MOSTLYRIGHT_HTTP_MAX_RETRIES", raising=False)
            importlib.reload(mod)

    @pytest.mark.parametrize("bad", ["nan", "inf", "-inf"])
    def test_non_finite_http_timeout_falls_back_to_default(
        self, monkeypatch: pytest.MonkeyPatch, bad: str
    ) -> None:
        """float() accepts nan/inf; both must be rejected — an inf timeout
        means 'hang forever' and nan is undefined in httpx. Fall back to the
        finite default rather than silently disabling the timeout."""
        mod = self._reload(monkeypatch, {"MOSTLYRIGHT_HTTP_TIMEOUT": bad})
        try:
            assert mod.HTTP_TIMEOUT == 60.0
        finally:
            monkeypatch.delenv("MOSTLYRIGHT_HTTP_TIMEOUT", raising=False)
            importlib.reload(mod)

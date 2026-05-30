"""Phase 24-04: optional reusable client in ``download_with_retry``.

``download_with_retry`` opened a fresh ``httpx.Client`` per call — a new
TCP+TLS handshake for every file. The new optional ``client`` kwarg lets a
multi-file fetcher thread ONE pooled client through its loop. When a client
is provided the helper reuses it and does NOT close it (caller owns the
lifecycle); when omitted it creates + closes one exactly as before.

All other behavior (404-raises-immediately, transient retry/backoff,
atomic .tmp+os.replace) must be preserved on the injected-client path.
"""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest
from mostlyright._internal._http import HTTP_TIMEOUT, download_with_retry


def _respx_or_skip():  # type: ignore[no-untyped-def]
    try:
        import respx
    except ImportError:
        pytest.skip("respx not installed; skipping HTTP mock test")
    return respx


def test_passed_in_client_is_reused_and_not_closed(tmp_path: Path) -> None:
    respx = _respx_or_skip()
    url1 = "https://example.test/a.csv"
    url2 = "https://example.test/b.csv"
    dest1 = tmp_path / "a.csv"
    dest2 = tmp_path / "b.csv"
    client = httpx.Client(timeout=HTTP_TIMEOUT)
    try:
        with respx.mock(assert_all_called=True) as mock:
            mock.get(url1).respond(200, content=b"AAA")
            mock.get(url2).respond(200, content=b"BBB")
            download_with_retry(url1, dest1, client=client)
            download_with_retry(url2, dest2, client=client)
            # The helper must NOT close a caller-owned client.
            assert not client.is_closed
    finally:
        client.close()
    assert dest1.read_bytes() == b"AAA"
    assert dest2.read_bytes() == b"BBB"


def test_default_path_creates_and_closes_a_client(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    respx = _respx_or_skip()
    created: list[httpx.Client] = []
    real_client_cls = httpx.Client

    class _Tracked(real_client_cls):  # type: ignore[misc, valid-type]
        def __init__(self, *args: object, **kwargs: object) -> None:
            super().__init__(*args, **kwargs)
            created.append(self)

    monkeypatch.setattr("mostlyright._internal._http.httpx.Client", _Tracked)
    url = "https://example.test/default.csv"
    dest = tmp_path / "default.csv"
    with respx.mock() as mock:
        mock.get(url).respond(200, content=b"x")
        download_with_retry(url, dest)  # client=None -> create + close
    assert len(created) == 1, "default path should create exactly one client"
    assert created[0].is_closed, "default-path client must be closed"
    assert dest.read_bytes() == b"x"


def test_injected_client_404_raises_immediately_without_closing(tmp_path: Path) -> None:
    respx = _respx_or_skip()
    url = "https://example.test/missing.csv"
    dest = tmp_path / "missing.csv"
    client = httpx.Client(timeout=HTTP_TIMEOUT)
    try:
        with respx.mock() as mock:
            mock.get(url).respond(404)
            with pytest.raises(httpx.HTTPStatusError):
                download_with_retry(url, dest, client=client)
        assert not dest.exists()
        # Even on error the helper leaves the caller's client open.
        assert not client.is_closed
    finally:
        client.close()


def test_injected_client_503_then_200_retries_and_writes_atomically(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    respx = _respx_or_skip()
    monkeypatch.setattr("mostlyright._internal._http.time.sleep", lambda _: None)
    url = "https://example.test/flaky.csv"
    dest = tmp_path / "flaky.csv"
    client = httpx.Client(timeout=HTTP_TIMEOUT)
    try:
        with respx.mock(assert_all_called=True) as mock:
            route = mock.get(url)
            route.side_effect = [httpx.Response(503), httpx.Response(200, content=b"OK")]
            download_with_retry(url, dest, client=client)
        assert dest.read_bytes() == b"OK"
        # tmp staging file must not linger after the atomic rename.
        assert not dest.with_suffix(".csv.tmp").exists()
        assert not client.is_closed
    finally:
        client.close()

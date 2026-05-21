"""Tests for src/tradewinds/_internal/_http.py — HTTP session.

Lifted byte-faithful from monorepo-v0.14.1/tests/test_sdk_http.py with
namespace rewrites:
- mostlyright._http      -> tradewinds._internal._http
- mostlyright.config     -> tradewinds._internal.config
- mostlyright.exceptions -> tradewinds._internal.exceptions
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx
import pytest


def _mock_response(
    status_code: int = 200,
    json_data: object = None,
    content: bytes = b"",
    headers: dict | None = None,
) -> httpx.Response:
    """Build a mock httpx.Response."""
    resp = httpx.Response(
        status_code=status_code,
        json=json_data,
        content=content if json_data is None else None,
        headers=headers or {"content-type": "application/json"},
    )
    return resp


class TestHttpSessionGet:
    """GET requests and JSON parsing."""

    def test_get_returns_json(self) -> None:
        from tradewinds._internal._http import HttpSession
        from tradewinds._internal.config import TherminalConfig

        cfg = TherminalConfig(base_url="http://test")
        session = HttpSession(cfg)
        with patch.object(
            session._client,
            "get",
            return_value=_mock_response(json_data={"status": "ok"}),
        ):
            result = session.get("/health")
        assert result == {"status": "ok"}

    def test_get_strips_none_params(self) -> None:
        from tradewinds._internal._http import HttpSession
        from tradewinds._internal.config import TherminalConfig

        cfg = TherminalConfig(base_url="http://test")
        session = HttpSession(cfg)
        mock_get = MagicMock(return_value=_mock_response(json_data=[]))
        with patch.object(session._client, "get", mock_get):
            session.get("/obs", {"station": "ATL", "from": None})
        called_params = mock_get.call_args[1]["params"]
        assert "from" not in called_params
        assert called_params["station"] == "ATL"


class TestHttpSessionErrors:
    """HTTP error -> SDK exception mapping."""

    def test_404_raises_not_found(self) -> None:
        from tradewinds._internal._http import HttpSession
        from tradewinds._internal.config import TherminalConfig
        from tradewinds._internal.exceptions import NotFoundError

        cfg = TherminalConfig(base_url="http://test")
        session = HttpSession(cfg)
        resp = _mock_response(404, json_data={"error": "Station ZZZ not found"})
        with patch.object(session._client, "get", return_value=resp):  # noqa: SIM117 — byte-faithful lift from mostlyright==0.14.1
            with pytest.raises(NotFoundError, match="ZZZ"):
                session.get("/obs", {"station": "ZZZ"})

    def test_400_raises_validation(self) -> None:
        from tradewinds._internal._http import HttpSession
        from tradewinds._internal.config import TherminalConfig
        from tradewinds._internal.exceptions import ValidationError

        cfg = TherminalConfig(base_url="http://test")
        session = HttpSession(cfg)
        resp = _mock_response(400, json_data={"error": "bad date"})
        with patch.object(session._client, "get", return_value=resp):  # noqa: SIM117 — byte-faithful lift from mostlyright==0.14.1
            with pytest.raises(ValidationError):
                session.get("/obs")

    def test_401_raises_auth(self) -> None:
        from tradewinds._internal._http import HttpSession
        from tradewinds._internal.config import TherminalConfig
        from tradewinds._internal.exceptions import AuthenticationError

        cfg = TherminalConfig(base_url="http://test")
        session = HttpSession(cfg)
        resp = _mock_response(401, json_data={"error": "Invalid API key"})
        with patch.object(session._client, "get", return_value=resp):  # noqa: SIM117 — byte-faithful lift from mostlyright==0.14.1
            with pytest.raises(AuthenticationError):
                session.get("/obs")

    def test_429_raises_rate_limit(self) -> None:
        from tradewinds._internal._http import HttpSession
        from tradewinds._internal.config import TherminalConfig
        from tradewinds._internal.exceptions import RateLimitError

        cfg = TherminalConfig(base_url="http://test")
        session = HttpSession(cfg)
        resp = _mock_response(
            429,
            json_data={"error": "rate limited"},
            headers={"content-type": "application/json", "Retry-After": "30"},
        )
        with patch.object(session._client, "get", return_value=resp):
            with pytest.raises(RateLimitError) as exc_info:
                session.get("/obs")
            assert exc_info.value.retry_after == 30

    def test_500_raises_server_error(self) -> None:
        from tradewinds._internal._http import HttpSession
        from tradewinds._internal.config import TherminalConfig
        from tradewinds._internal.exceptions import ServerError

        cfg = TherminalConfig(base_url="http://test")
        session = HttpSession(cfg)
        resp = _mock_response(500, json_data={"error": "internal"})
        with patch.object(session._client, "get", return_value=resp):  # noqa: SIM117 — byte-faithful lift from mostlyright==0.14.1
            with pytest.raises(ServerError):
                session.get("/obs")


class TestHttpSessionGetAll:
    """Auto-pagination."""

    def test_single_page(self) -> None:
        from tradewinds._internal._http import HttpSession
        from tradewinds._internal.config import TherminalConfig

        cfg = TherminalConfig(base_url="http://test")
        session = HttpSession(cfg)
        page = [{"id": i} for i in range(5)]
        with patch.object(
            session._client, "get", return_value=_mock_response(json_data=page)
        ):
            result = session.get_all("/obs", {"station": "ATL"})
        assert len(result) == 5

    def test_multi_page(self) -> None:
        from tradewinds._internal._http import HttpSession
        from tradewinds._internal.config import TherminalConfig

        cfg = TherminalConfig(base_url="http://test")
        session = HttpSession(cfg)
        page1 = [{"id": i} for i in range(10)]
        page2 = [{"id": i} for i in range(10, 15)]
        responses = iter(
            [_mock_response(json_data=page1), _mock_response(json_data=page2)]
        )
        with patch.object(
            session._client, "get", side_effect=lambda *a, **kw: next(responses)
        ):
            result = session.get_all("/obs", {"station": "ATL"}, page_size=10)
        assert len(result) == 15


class TestHttpSessionGetBytes:
    def test_returns_bytes(self) -> None:
        from tradewinds._internal._http import HttpSession
        from tradewinds._internal.config import TherminalConfig

        cfg = TherminalConfig(base_url="http://test")
        session = HttpSession(cfg)
        resp = httpx.Response(
            200,
            content=b"binary-data",
            headers={"content-type": "application/octet-stream"},
        )
        with patch.object(session._client, "get", return_value=resp):
            result = session.get_bytes("/obs", {"format": "parquet"})
        assert result == b"binary-data"


class TestHttpSessionContextManager:
    def test_context_manager(self) -> None:
        from tradewinds._internal._http import HttpSession
        from tradewinds._internal.config import TherminalConfig

        cfg = TherminalConfig(base_url="http://test")
        with HttpSession(cfg) as session:
            assert session is not None

    def test_close(self) -> None:
        from tradewinds._internal._http import HttpSession
        from tradewinds._internal.config import TherminalConfig

        cfg = TherminalConfig(base_url="http://test")
        session = HttpSession(cfg)
        session.close()  # Should not raise


class TestUserAgent:
    def test_user_agent_header(self) -> None:
        from tradewinds._internal._http import HttpSession
        from tradewinds._internal.config import TherminalConfig

        cfg = TherminalConfig(base_url="http://test")
        session = HttpSession(cfg)
        ua = session._client.headers.get("user-agent", "")
        assert "mostlyright" in ua.lower()

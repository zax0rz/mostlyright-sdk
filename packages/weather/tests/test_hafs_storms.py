"""Phase 17 PLAN-06: HAFS Storms() resolver — TTL cache + 403 surface."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest
from mostlyright.core.exceptions import StormNotFoundError
from mostlyright.weather._fetchers import _hafs_storms
from mostlyright.weather._fetchers._hafs_storms import (
    _STORM_LIST_TTL,
    _STORM_LIST_URL,
    _clear_cache_for_tests,
    get_active_storms,
    resolve_storm,
)


@pytest.fixture(autouse=True)
def _reset_cache() -> None:
    _clear_cache_for_tests()


def _make_mock_client(
    listing_html: str,
    message_bodies: dict[str, str],
) -> MagicMock:
    """Return a MagicMock that mimics httpx.Client for the Storms() flow."""
    mock = MagicMock()

    def _get(url: str) -> MagicMock:
        resp = MagicMock()
        resp.status_code = 200
        if url == _STORM_LIST_URL:
            resp.text = listing_html
        else:
            # URL is _STORM_LIST_URL + "messageN"
            message_name = url.rsplit("/", 1)[-1]
            resp.text = message_bodies.get(message_name, "")
        resp.raise_for_status = MagicMock()
        return resp

    mock.get = MagicMock(side_effect=_get)
    return mock


def test_storm_list_ttl_is_one_hour() -> None:
    assert timedelta(hours=1) == _STORM_LIST_TTL


def test_storm_list_url_is_nomads_inphfsa() -> None:
    assert _STORM_LIST_URL == ("https://nomads.ncep.noaa.gov/pub/data/nccf/com/hafs/prod/inphfsa/")


def test_get_active_storms_parses_listing_and_messages() -> None:
    listing = "<a href='message1'>message1</a> <a href='message2'>message2</a>"
    bodies = {
        "message1": "NHC 09L LAURA other-stuff",
        "message2": "NHC 10L MARCO other-stuff",
    }
    client = _make_mock_client(listing, bodies)
    storms = get_active_storms(client=client, bust_cache=True)
    assert storms == {"09l": "laura", "10l": "marco"}


def test_resolve_storm_by_id_passthrough() -> None:
    listing = "message1"
    bodies = {"message1": "NHC 09L LAURA"}
    client = _make_mock_client(listing, bodies)
    assert resolve_storm("09l", client=client, bust_cache=True) == "09l"


def test_resolve_storm_by_name_lookup() -> None:
    listing = "message1"
    bodies = {"message1": "NHC 09L LAURA"}
    client = _make_mock_client(listing, bodies)
    assert resolve_storm("laura", client=client, bust_cache=True) == "09l"


def test_resolve_storm_unknown_query_raises_storm_not_found() -> None:
    listing = "message1 message2"
    bodies = {
        "message1": "NHC 09L LAURA",
        "message2": "NHC 10L MARCO",
    }
    client = _make_mock_client(listing, bodies)
    with pytest.raises(StormNotFoundError) as exc_info:
        resolve_storm("ian", client=client, bust_cache=True)
    assert exc_info.value.query == "ian"
    assert sorted(exc_info.value.active_storms) == ["09l", "10l"]


def test_get_active_storms_cache_hit_within_ttl(monkeypatch: pytest.MonkeyPatch) -> None:
    """Second call within TTL reuses cache — no second listing fetch."""
    listing = "message1"
    bodies = {"message1": "NHC 09L LAURA"}
    client = _make_mock_client(listing, bodies)

    # First call populates cache.
    get_active_storms(client=client, bust_cache=True)
    initial_call_count = client.get.call_count
    # Second call within TTL: should hit cache, not call client.get again.
    get_active_storms(client=client)
    assert client.get.call_count == initial_call_count


def test_get_active_storms_cache_expires_after_ttl(monkeypatch: pytest.MonkeyPatch) -> None:
    """Re-fetch occurs once the cached entry is older than TTL."""
    listing = "message1"
    bodies = {"message1": "NHC 09L LAURA"}
    client = _make_mock_client(listing, bodies)

    # Freeze "_now" so we can advance it past the TTL.
    fake_time = [datetime(2026, 5, 24, 12, 0, tzinfo=UTC)]
    monkeypatch.setattr(_hafs_storms, "_now", lambda: fake_time[0])

    get_active_storms(client=client, bust_cache=True)
    first_count = client.get.call_count

    # Advance past TTL.
    fake_time[0] = fake_time[0] + timedelta(hours=2)
    get_active_storms(client=client)
    assert client.get.call_count > first_count

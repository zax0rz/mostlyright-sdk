"""Real Phase 3.3 Polymarket discovery + settlement tests.

Uses ``httpx.MockTransport`` to inject Gamma API responses so we
exercise the production HTTP code path without hitting Polymarket
servers in CI. A separate ``@pytest.mark.live`` test hits the real
endpoint and is excluded from CI per the testing playbook.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import httpx
import pytest
from tradewinds.markets._polymarket_client import (
    GAMMA_API_BASE,
    fetch_event_by_id,
    fetch_events,
)
from tradewinds.markets.polymarket import (
    POLYMARKET_RESOLUTION_SOURCE_TYPES,
    RESOLUTION_SOURCE_ALLOWLIST,
    PolymarketEventError,
    PolymarketSettlementError,
    TooEarlyToSettleError,
    polymarket_discover,
    polymarket_settle,
)

_UUID4 = "01234567-89ab-4cde-8f01-23456789abcd"


# ---------------------------------------------------------------------------
# Gamma API client
# ---------------------------------------------------------------------------
class TestFetchEvents:
    def test_returns_event_list_from_one_page(self) -> None:
        events = [
            {"id": _UUID4, "slug": "a", "title": "A"},
            {"id": _UUID4, "slug": "b", "title": "B"},
        ]

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=events)

        client = httpx.Client(transport=httpx.MockTransport(handler))
        try:
            out = fetch_events(client=client, sleep_between=0)
            assert [e["slug"] for e in out] == ["a", "b"]
        finally:
            client.close()

    def test_dedupes_by_slug_across_pages(self) -> None:
        # Simulate dup `b` returned on adjacent pages (Gamma is known
        # to occasionally repeat between page boundaries).
        pages: list[list[dict[str, Any]]] = [
            [{"id": _UUID4, "slug": "a"}, {"id": _UUID4, "slug": "b"}] * 50,
            [{"id": _UUID4, "slug": "b"}, {"id": _UUID4, "slug": "c"}] * 50,
            [],
        ]
        call_count = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            page = pages[min(call_count, len(pages) - 1)]
            call_count += 1
            return httpx.Response(200, json=page)

        client = httpx.Client(transport=httpx.MockTransport(handler))
        try:
            out = fetch_events(client=client, sleep_between=0)
            slugs = [e["slug"] for e in out]
            # Each slug appears exactly once.
            assert sorted(set(slugs)) == ["a", "b", "c"]
            assert len(slugs) == len(set(slugs))
        finally:
            client.close()

    def test_short_page_signals_end_of_pagination(self) -> None:
        """When upstream returns fewer than the batch limit, stop paginating."""
        call_count = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            # First page only has 5 items (< _EVENTS_LIMIT=100).
            return httpx.Response(
                200,
                json=[{"id": _UUID4, "slug": f"s{i}"} for i in range(5)],
            )

        client = httpx.Client(transport=httpx.MockTransport(handler))
        try:
            fetch_events(client=client, sleep_between=0)
            assert call_count == 1
        finally:
            client.close()

    def test_non_list_payload_raises_loudly(self) -> None:
        """Defensive — if Gamma changes shape, fail loudly not silently."""

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"data": []})

        client = httpx.Client(transport=httpx.MockTransport(handler))
        try:
            with pytest.raises(ValueError, match="non-list payload"):
                fetch_events(client=client, sleep_between=0)
        finally:
            client.close()

    def test_http_error_propagates(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(503)

        client = httpx.Client(transport=httpx.MockTransport(handler))
        try:
            with pytest.raises(httpx.HTTPStatusError):
                fetch_events(client=client, sleep_between=0)
        finally:
            client.close()


class TestFetchEventById:
    def test_returns_dict_payload(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            assert _UUID4 in str(request.url)
            return httpx.Response(200, json={"id": _UUID4, "slug": "x"})

        client = httpx.Client(transport=httpx.MockTransport(handler))
        try:
            out = fetch_event_by_id(_UUID4, client=client)
            assert out["slug"] == "x"
        finally:
            client.close()

    def test_404_raises_http_error(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(404)

        client = httpx.Client(transport=httpx.MockTransport(handler))
        try:
            with pytest.raises(httpx.HTTPStatusError):
                fetch_event_by_id(_UUID4, client=client)
        finally:
            client.close()

    def test_non_dict_payload_raises_loudly(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=["not", "a", "dict"])

        client = httpx.Client(transport=httpx.MockTransport(handler))
        try:
            with pytest.raises(ValueError, match="non-dict payload"):
                fetch_event_by_id(_UUID4, client=client)
        finally:
            client.close()


# ---------------------------------------------------------------------------
# polymarket_discover end-to-end
# ---------------------------------------------------------------------------
class TestPolymarketDiscover:
    def test_returns_dataframe_with_expected_columns(self) -> None:
        events = [
            {
                "id": _UUID4,
                "slug": "highest-temp-london-2026-05-23",
                "title": "Will London's highest temperature on 2026-05-23 be...",
                "city": "london",
                "description": "Resolves via https://www.wunderground.com/...",
                "endDate": "2026-05-24T00:00:00Z",
            }
        ]

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=events)

        client = httpx.Client(transport=httpx.MockTransport(handler))
        try:
            df = polymarket_discover(client=client, sleep_between=0)
            assert list(df.columns) == [
                "event_id",
                "slug",
                "title",
                "city",
                "icao",
                "measure",
                "end_time",
                "resolution_source_type",
            ]
            assert df.iloc[0]["icao"] == "EGLL"
            assert df.iloc[0]["measure"] == "high"
            assert df.iloc[0]["resolution_source_type"] == "wunderground"
            # Validator-friendly provenance attrs.
            assert df.attrs.get("source") == "polymarket_gamma"
            assert df.attrs.get("retrieved_at") is not None
        finally:
            client.close()

    def test_unknown_city_event_skipped(self) -> None:
        events = [
            {"id": _UUID4, "slug": "no-city-mentioned", "city": "atlantis"},
            {"id": _UUID4, "slug": "highest-temp-london-2026-05-23", "city": "london"},
        ]

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=events)

        client = httpx.Client(transport=httpx.MockTransport(handler))
        try:
            df = polymarket_discover(client=client, sleep_between=0)
            assert len(df) == 1
            assert df.iloc[0]["city"] == "london"
        finally:
            client.close()

    def test_bad_description_does_not_poison_other_events(self) -> None:
        """A 17 KB description on one event must not stop discovery."""
        events = [
            {
                "id": _UUID4,
                "slug": "good-event-london-2026-05-23",
                "city": "london",
                "description": "https://www.wunderground.com/x",
            },
            {
                "id": _UUID4,
                "slug": "oversize-paris-2026-05-23",
                "city": "paris",
                "description": "x" * (16 * 1024 + 1),
            },
        ]

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=events)

        client = httpx.Client(transport=httpx.MockTransport(handler))
        try:
            df = polymarket_discover(client=client, sleep_between=0)
            # Both rows present; oversize-description event drops its
            # resolution_source_type to None instead of erroring out.
            assert len(df) == 2
            paris_row = df[df["slug"] == "oversize-paris-2026-05-23"].iloc[0]
            assert paris_row["resolution_source_type"] is None
        finally:
            client.close()


# ---------------------------------------------------------------------------
# polymarket_settle end-to-end (no daily_extremes call needed for failure modes)
# ---------------------------------------------------------------------------
class TestPolymarketSettleBoundaries:
    def test_invalid_event_id_raises(self) -> None:
        with pytest.raises(PolymarketEventError, match="UUID4"):
            polymarket_settle("not-a-uuid")

    def test_oversized_description_raises(self) -> None:
        with pytest.raises(PolymarketEventError, match="16 KB cap"):
            polymarket_settle(_UUID4, description="x" * (16 * 1024 + 1))

    def test_unknown_url_in_description_raises(self) -> None:
        with pytest.raises(PolymarketEventError, match="not in allowlist"):
            polymarket_settle(
                _UUID4,
                description="Resolves via https://malicious.example.com/data",
                event={"slug": "x-2026-05-23", "city": "london"},
            )

    def test_deferred_market_raises_deferred_error(self) -> None:
        from tradewinds.international import DeferredMarketError

        event = {
            "id": _UUID4,
            "slug": "taipei-low-2026-05-23",
            "title": "Will Taipei's low be below 20°C on 2026-05-23?",
            "city": "taipei",
            "description": "https://www.wunderground.com/x",
        }
        with pytest.raises(DeferredMarketError):
            polymarket_settle(_UUID4, event=event)

    def test_missing_slug_date_raises_settlement_error(self) -> None:
        with pytest.raises(PolymarketSettlementError, match="no resolution date"):
            polymarket_settle(
                _UUID4,
                event={
                    "id": _UUID4,
                    "slug": "highest-temp-london-no-date",
                    "city": "london",
                    "title": "highest temp in London",
                    "description": "https://www.wunderground.com/x",
                },
            )

    def test_too_early_to_settle_raises(self) -> None:
        # Set "now" to one minute after the settlement date; the source
        # finalization window (Wunderground = 6h) hasn't elapsed.
        event = {
            "id": _UUID4,
            "slug": "highest-temp-london-2026-05-23",
            "title": "Will London's highest temperature on 2026-05-23 be over 80F?",
            "city": "london",
            "description": "https://www.wunderground.com/x",
        }
        now = datetime(2026, 5, 24, 0, 1, tzinfo=UTC)  # 1 min after end-of-day UTC
        with pytest.raises(TooEarlyToSettleError) as exc_info:
            polymarket_settle(_UUID4, event=event, now=now)
        assert exc_info.value.resolution_source_type == "wunderground"
        assert exc_info.value.wait_hours > 0


class TestPolymarketSettleResolutionPath:
    def test_settles_against_daily_extremes(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """End-to-end happy path with daily_extremes mocked.

        Polymarket event resolves to EGLL high for 2026-05-22. We stub
        daily_extremes to return one row with tmax_c=22.5 and verify
        the settlement payload carries that value.
        """
        from tradewinds.markets import polymarket as pm_module

        def fake_daily_extremes(station: str, from_date, to_date):
            assert station == "EGLL"
            return [
                {
                    "station": "EGLL",
                    "local_date": from_date.isoformat(),
                    "n_obs": 24,
                    "tmin_c": 12.0,
                    "tmax_c": 22.5,
                    "tmean_c": 17.0,
                    "precip_inches": 0.0,
                    "source_tmin": "iem.archive",
                    "source_tmax": "iem.archive",
                    "country": "GB",
                }
            ]

        monkeypatch.setattr(pm_module, "daily_extremes", fake_daily_extremes)

        event = {
            "id": _UUID4,
            "slug": "highest-temp-london-2026-05-22",
            "title": "Will London's highest temperature on 2026-05-22 be over 20C?",
            "city": "london",
            "description": "Resolves via https://www.wunderground.com/x",
        }
        # 'now' is well past the 6h Wunderground delay.
        now = datetime(2026, 5, 25, 0, 0, tzinfo=UTC)
        result = polymarket_settle(_UUID4, event=event, now=now)
        assert result["icao"] == "EGLL"
        assert result["measure"] == "high"
        assert result["observed_value_c"] == 22.5
        assert result["observed_source"] == "iem.archive"
        assert result["resolution_source_type"] == "wunderground"
        assert result["settlement_date"] == "2026-05-22"
        assert result["n_obs"] == 24

    def test_low_market_picks_tmin(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from tradewinds.markets import polymarket as pm_module

        monkeypatch.setattr(
            pm_module,
            "daily_extremes",
            lambda s, f, t: [
                {
                    "local_date": f.isoformat(),
                    "n_obs": 24,
                    "tmin_c": 5.0,
                    "tmax_c": 15.0,
                    "source_tmin": "iem.archive",
                    "source_tmax": "iem.archive",
                    "country": "GB",
                }
            ],
        )
        event = {
            "id": _UUID4,
            "slug": "lowest-temp-london-2026-05-22",
            "title": "Will London's lowest temperature on 2026-05-22 be below 0C?",
            "city": "london",
            "description": "Resolves via https://www.wunderground.com/x",
        }
        result = polymarket_settle(_UUID4, event=event, now=datetime(2026, 5, 25, 0, 0, tzinfo=UTC))
        assert result["measure"] == "low"
        assert result["observed_value_c"] == 5.0

    def test_no_data_raises_settlement_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from tradewinds.markets import polymarket as pm_module

        monkeypatch.setattr(pm_module, "daily_extremes", lambda s, f, t: [])
        event = {
            "id": _UUID4,
            "slug": "highest-temp-london-2026-05-22",
            "title": "Will London's highest temperature on 2026-05-22 be over 20C?",
            "city": "london",
            "description": "https://www.wunderground.com/x",
        }
        with pytest.raises(PolymarketSettlementError, match="no rows"):
            polymarket_settle(_UUID4, event=event, now=datetime(2026, 5, 25, 0, 0, tzinfo=UTC))

    def test_to_dict_carries_wait_hours(self) -> None:
        err = TooEarlyToSettleError("msg", wait_hours=5.5, resolution_source_type="noaa_wrh")
        d = err.to_dict()
        assert d["wait_hours"] == 5.5
        assert d["resolution_source_type"] == "noaa_wrh"


class TestEnumsAndAllowlist:
    def test_resolution_source_types_predeclared(self) -> None:
        for t in ("wunderground", "noaa_wrh", "hko", "cwa", "other"):
            assert t in POLYMARKET_RESOLUTION_SOURCE_TYPES

    def test_allowlist_includes_both_www_and_root_netloc(self) -> None:
        assert "wunderground.com" in RESOLUTION_SOURCE_ALLOWLIST
        assert "www.wunderground.com" in RESOLUTION_SOURCE_ALLOWLIST
        assert "weather.gov" in RESOLUTION_SOURCE_ALLOWLIST
        assert "www.weather.gov" in RESOLUTION_SOURCE_ALLOWLIST

    def test_gamma_base_is_polymarket_official(self) -> None:
        assert GAMMA_API_BASE == "https://gamma-api.polymarket.com"

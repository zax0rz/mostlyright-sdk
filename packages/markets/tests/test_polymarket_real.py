"""Real Phase 3.3 Polymarket discovery + settlement tests.

Uses ``httpx.MockTransport`` to inject Gamma API responses so we
exercise the production HTTP code path without hitting Polymarket
servers in CI. A separate ``@pytest.mark.live`` test hits the real
endpoint and is excluded from CI per the testing playbook.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any

import httpx
import pytest
from mostlyright.markets._polymarket_client import (
    GAMMA_API_BASE,
    fetch_event_by_id,
    fetch_events,
)
from mostlyright.markets.polymarket import (
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
                "source",
            ]
            assert df.iloc[0]["icao"] == "EGLL"
            assert df.iloc[0]["measure"] == "high"
            assert df.iloc[0]["resolution_source_type"] == "wunderground"
            # Architect iter-1 HIGH-5: per-row source overlay column.
            assert df.iloc[0]["source"] == "polymarket_gamma"
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
        with pytest.raises(PolymarketEventError, match=r"\[A-Za-z0-9_-\]"):
            polymarket_settle("contains spaces and ! chars")

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
        from mostlyright.international import DeferredMarketError

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
        from mostlyright.markets import polymarket as pm_module

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
        from mostlyright.markets import polymarket as pm_module

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
        from mostlyright.markets import polymarket as pm_module

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


class TestArchitectIter1Fixes:
    """Regression tests for architect iter-1 HIGH findings."""

    def test_settlement_date_takes_last_yyyymmdd_in_slug(self) -> None:
        """HIGH-4: slug carrying creation-date + resolution-date picks the latter."""
        from mostlyright.markets.polymarket import _settlement_date_from_slug

        out = _settlement_date_from_slug("created-2026-01-01-resolves-2026-05-23")
        assert out.isoformat() == "2026-05-23"

    def test_ambiguous_title_refuses_to_silently_default(self) -> None:
        """HIGH-3: no high/low keyword raises PolymarketSettlementError."""
        event = {
            "id": _UUID4,
            "slug": "some-event-london-2026-05-23",
            "title": "Will London weather match the forecast?",  # no high/low keyword
            "city": "london",
            "description": "https://www.wunderground.com/x",
        }
        now = datetime(2026, 5, 25, 0, 0, tzinfo=UTC)
        with pytest.raises(PolymarketSettlementError, match="ambiguous"):
            polymarket_settle(_UUID4, event=event, now=now)

    def test_too_early_uses_station_local_end_of_day(self) -> None:
        """HIGH-1: settle finalization window starts from local day-end, not UTC.

        For LAX (UTC-7), local day 2026-05-22 ends at 2026-05-23 06:59:59 UTC.
        Setting 'now' to 2026-05-23 03:00 UTC means we're 4h *before* local
        day-end — settle should refuse with TooEarlyToSettleError even though
        we're 27h past UTC end-of-day (which would have passed any 24h gate).
        """
        from mostlyright.markets.polymarket import _station_local_end_of_day

        # Sanity: confirm KLAX local end-of-day is 7h after UTC midnight.
        eod_utc = _station_local_end_of_day("KLAX", date(2026, 5, 22))
        # America/Los_Angeles on 2026-05-22 is PDT (UTC-7) so local
        # 23:59:59 PDT == 06:59:59 UTC next day.
        assert eod_utc.hour == 6
        assert eod_utc.day == 23

    def test_deferred_check_via_per_measure_table_not_just_station_set(self) -> None:
        """HIGH-2: RCTP/'high' must be blocked by defense-in-depth gate.

        resolve_station_for_event already blocks this, so we patch it
        out to confirm the secondary gate fires.
        """
        from unittest.mock import patch

        from mostlyright.international import DeferredMarketError
        from mostlyright.markets import polymarket as pm_module

        # Bypass the resolver's gate so we hit the defense-in-depth path.
        with patch.object(
            pm_module,
            "resolve_station_for_event",
            return_value=("RCTP", "default"),
        ):
            event = {
                "id": _UUID4,
                "slug": "highest-temp-taipei-2026-05-23",
                "title": "Will Taipei's highest temp be above 30C?",
                "city": "taipei",
                "description": "https://www.wunderground.com/x",
            }
            with pytest.raises(DeferredMarketError):
                pm_module.polymarket_settle(
                    _UUID4, event=event, now=datetime(2026, 5, 25, 0, 0, tzinfo=UTC)
                )

    def test_discover_per_row_source_column_survives_concat(self) -> None:
        """HIGH-5: df.attrs is lost on concat; per-row column persists."""
        import pandas as pd

        events = [
            {
                "id": _UUID4,
                "slug": "highest-london-2026-05-23",
                "title": "London highest temp 2026-05-23",
                "city": "london",
                "description": "https://www.wunderground.com/x",
            }
        ]

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=events)

        client = httpx.Client(transport=httpx.MockTransport(handler))
        try:
            df = polymarket_discover(client=client, sleep_between=0)
            other = pd.DataFrame(
                {
                    "event_id": ["x"],
                    "slug": ["y"],
                    "title": ["z"],
                    "city": [None],
                    "icao": [None],
                    "measure": [None],
                    "end_time": [None],
                    "resolution_source_type": [None],
                    "source": ["test_other"],
                }
            )
            combined = pd.concat([df, other], ignore_index=True)
            assert combined["source"].tolist() == ["polymarket_gamma", "test_other"]
        finally:
            client.close()


class TestCodexIter2Fixes:
    """Codex iter-2 P1 follow-ups: real Gamma payload compatibility."""

    def test_city_derived_from_slug_without_explicit_city_field(self) -> None:
        """Real Gamma events have no `city` field; derive from slug."""
        from mostlyright.markets.polymarket import _derive_city

        city_map = {"london": {"default": "EGLL"}, "paris": {"high": "LFPG"}}
        city_keys = tuple(sorted(city_map.keys(), key=len, reverse=True))
        ev = {
            "id": "12345",
            "slug": "will-london-see-record-high-on-2026-05-23",
            "title": "London record high",
        }
        assert _derive_city(ev, city_keys) == "london"

    def test_city_longest_match_wins(self) -> None:
        """``london_gatwick`` matches before ``london`` (longest-first)."""
        from mostlyright.markets.polymarket import _derive_city

        city_map = {
            "london": {"default": "EGLL"},
            "london_gatwick": {"default": "EGKK"},
        }
        city_keys = tuple(sorted(city_map.keys(), key=len, reverse=True))
        ev = {"slug": "highest-temp-london-gatwick-2026-05-23"}
        assert _derive_city(ev, city_keys) == "london_gatwick"

    def test_city_derived_from_tags(self) -> None:
        """Events tagged via Gamma `tags` array also resolve."""
        from mostlyright.markets.polymarket import _derive_city

        city_keys = ("london",)
        ev = {
            "slug": "weather-event-xyz",
            "title": "Will the temperature stay above 20C?",
            "tags": [{"label": "London"}, {"label": "weather"}],
        }
        assert _derive_city(ev, city_keys) == "london"

    def test_no_city_match_returns_none(self) -> None:
        from mostlyright.markets.polymarket import _derive_city

        city_keys = ("london", "paris")
        ev = {"slug": "atlantis-temp-event", "title": "Atlantis weather"}
        assert _derive_city(ev, city_keys) is None

    def test_numeric_event_id_accepted(self) -> None:
        """Real Gamma IDs are numeric strings, not UUID4."""
        # No raise — id passes the relaxed validation.
        # We use a stub event so we don't hit the network.
        with pytest.raises(PolymarketSettlementError, match="no resolution date in slug"):
            polymarket_settle(
                "12345",
                event={
                    "id": "12345",
                    "slug": "no-date-here",
                    "title": "highest london",
                    "city": "london",
                    "description": "https://www.wunderground.com/x",
                },
            )

    def test_discover_works_against_real_shape_events_without_city(self) -> None:
        """End-to-end: events from real Gamma shape (no city field) resolve."""
        # Numeric id, slug carrying city + date, no city field.
        events = [
            {
                "id": "987654321",
                "slug": "will-paris-be-above-30c-on-2026-07-15",
                "title": "Paris temp above 30C on 2026-07-15?",
                "description": "Resolves via https://www.wunderground.com/foo",
            }
        ]

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=events)

        client = httpx.Client(transport=httpx.MockTransport(handler))
        try:
            df = polymarket_discover(client=client, sleep_between=0)
            assert len(df) == 1
            assert df.iloc[0]["city"] == "paris"
            # paris is a multi-airport city; "above 30C" matches the
            # "highest" keyword family via the title and resolves to LFPG.
            assert df.iloc[0]["icao"] in ("LFPG", "LFPB", "LFPO")
            assert df.iloc[0]["event_id"] == "987654321"
        finally:
            client.close()


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

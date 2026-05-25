"""Tests for the Phase 9 Kalshi trades surface (TRADES-01..03).

All HTTP calls are mocked via ``respx``; no test is marked
``@pytest.mark.live`` so the suite stays CI-safe.
"""

from __future__ import annotations

from datetime import UTC, datetime

import httpx
import pytest

respx = pytest.importorskip("respx")

from mostlyright.markets._kalshi_client import (  # noqa: E402
    KALSHI_API_BASE,
)
from mostlyright.markets.kalshi_trades import (  # noqa: E402
    INTERVALS,
    candles,
    fills,
    orderbook,
)

_TICKER = "KXHIGHNY-25MAY26-T79"
_SERIES = "KXHIGHNY"


# ---------------------------------------------------------------------------
# candles
# ---------------------------------------------------------------------------
class TestCandles:
    def test_returns_dataframe_with_expected_columns_real_kalshi_shape(self):
        """Real Kalshi response (March 2026 migration): FixedPointDollars
        strings for prices + `*_fp` integer strings for size fields."""
        with respx.mock(assert_all_called=False) as router:
            router.get(f"{KALSHI_API_BASE}/series/{_SERIES}/markets/{_TICKER}/candlesticks").mock(
                return_value=httpx.Response(
                    200,
                    json={
                        "candlesticks": [
                            {
                                "end_period_ts": 1717200000,
                                "price": {
                                    "open_dollars": "0.5000",
                                    "high_dollars": "0.5500",
                                    "low_dollars": "0.4800",
                                    "close_dollars": "0.5200",
                                },
                                "volume_fp": "100",
                                "open_interest_fp": "500",
                            },
                            {
                                "end_period_ts": 1717203600,
                                "price": {
                                    "open_dollars": "0.5200",
                                    "high_dollars": "0.6000",
                                    "low_dollars": "0.5100",
                                    "close_dollars": "0.5800",
                                },
                                "volume_fp": "200",
                                "open_interest_fp": "600",
                            },
                        ]
                    },
                )
            )
            df = candles(
                _TICKER,
                interval="1h",
                from_=datetime(2026, 6, 1, tzinfo=UTC),
                to=datetime(2026, 6, 2, tzinfo=UTC),
                sleep_between=0,
            )
        assert list(df.columns) == [
            "ts",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "open_interest",
            "source",
        ]
        assert len(df) == 2
        assert (df["source"] == "kalshi").all()
        # cents = float(dollars_string) * 100 (binary float roundoff —
        # 0.58 * 100 = 57.99999... — so use approx for prices).
        assert df["open"].iloc[0] == pytest.approx(50.0)
        assert df["close"].iloc[1] == pytest.approx(58.0)
        assert df["volume"].iloc[0] == 100
        assert df["open_interest"].iloc[1] == 600

    def test_legacy_unsuffixed_fields_still_parsed_as_fallback(self):
        """Legacy integer-cents shape accepted as a fallback (older
        endpoints / recorded fixtures)."""
        with respx.mock(assert_all_called=False) as router:
            router.get(f"{KALSHI_API_BASE}/series/{_SERIES}/markets/{_TICKER}/candlesticks").mock(
                return_value=httpx.Response(
                    200,
                    json={
                        "candlesticks": [
                            {
                                "end_period_ts": 1717200000,
                                "price": {"open": 50, "high": 55, "low": 48, "close": 52},
                                "volume": 100,
                                "open_interest": 500,
                            },
                        ]
                    },
                )
            )
            df = candles(
                _TICKER,
                interval="1h",
                from_=datetime(2026, 6, 1, tzinfo=UTC),
                to=datetime(2026, 6, 2, tzinfo=UTC),
                sleep_between=0,
            )
        assert df["open"].iloc[0] == 50.0
        assert df["volume"].iloc[0] == 100

    def test_subpenny_precision_preserved(self):
        with respx.mock(assert_all_called=False) as router:
            router.get(f"{KALSHI_API_BASE}/series/{_SERIES}/markets/{_TICKER}/candlesticks").mock(
                return_value=httpx.Response(
                    200,
                    json={
                        "candlesticks": [
                            {
                                "end_period_ts": 1717200000,
                                "price": {
                                    "open_dollars": "0.5670",
                                    "high_dollars": "0.5670",
                                    "low_dollars": "0.5670",
                                    "close_dollars": "0.5670",
                                },
                                "volume_fp": "0",
                                "open_interest_fp": "0",
                            },
                        ]
                    },
                )
            )
            df = candles(
                _TICKER,
                interval="1h",
                from_=datetime(2026, 6, 1, tzinfo=UTC),
                to=datetime(2026, 6, 2, tzinfo=UTC),
                sleep_between=0,
            )
        # 0.567 dollars = 56.7 cents — subpenny preserved.
        assert df["open"].iloc[0] == pytest.approx(56.7)

    def test_empty_candlesticks_returns_empty_dataframe(self):
        with respx.mock(assert_all_called=False) as router:
            router.get(f"{KALSHI_API_BASE}/series/{_SERIES}/markets/{_TICKER}/candlesticks").mock(
                return_value=httpx.Response(200, json={"candlesticks": []})
            )
            df = candles(
                _TICKER,
                interval="1h",
                from_=datetime(2026, 6, 1, tzinfo=UTC),
                to=datetime(2026, 6, 2, tzinfo=UTC),
                sleep_between=0,
            )
        assert len(df) == 0
        assert list(df.columns)[-1] == "source"

    def test_naive_datetime_raises(self):
        with pytest.raises(TypeError, match="tz-aware"):
            candles(
                _TICKER,
                interval="1h",
                from_=datetime(2026, 6, 1),  # naive
                to=datetime(2026, 6, 2, tzinfo=UTC),
                sleep_between=0,
            )

    def test_from_geq_to_raises(self):
        with pytest.raises(ValueError, match="must be <"):
            candles(
                _TICKER,
                interval="1h",
                from_=datetime(2026, 6, 2, tzinfo=UTC),
                to=datetime(2026, 6, 1, tzinfo=UTC),
                sleep_between=0,
            )

    def test_bad_interval_raises(self):
        with pytest.raises(ValueError, match="interval must be"):
            candles(
                _TICKER,
                interval="5m",  # not supported
                from_=datetime(2026, 6, 1, tzinfo=UTC),
                to=datetime(2026, 6, 2, tzinfo=UTC),
                sleep_between=0,
            )

    def test_intervals_table_shape(self):
        assert INTERVALS == {"1m": 60, "1h": 3600, "1d": 86400}

    def test_bad_ticker_without_series_raises(self):
        with pytest.raises(ValueError, match="series prefix"):
            candles(
                "NODASH",
                interval="1h",
                from_=datetime(2026, 6, 1, tzinfo=UTC),
                to=datetime(2026, 6, 2, tzinfo=UTC),
                sleep_between=0,
            )

    def test_429_retries_then_succeeds(self):
        with respx.mock(assert_all_called=False) as router:
            route = router.get(f"{KALSHI_API_BASE}/series/{_SERIES}/markets/{_TICKER}/candlesticks")
            route.side_effect = [
                httpx.Response(429, json={"error": "rate_limited"}),
                httpx.Response(200, json={"candlesticks": []}),
            ]
            # Patch out the backoff sleep so the test runs fast.
            import mostlyright.markets._kalshi_client as kc

            orig_sleep = kc.time.sleep
            kc.time.sleep = lambda _s: None
            try:
                df = candles(
                    _TICKER,
                    interval="1h",
                    from_=datetime(2026, 6, 1, tzinfo=UTC),
                    to=datetime(2026, 6, 2, tzinfo=UTC),
                    sleep_between=0,
                )
            finally:
                kc.time.sleep = orig_sleep
        assert len(df) == 0

    def test_429_honors_retry_after_header(self):
        """Architect iter-1 CRITICAL: 429 + Retry-After: <seconds> should
        sleep at least the documented interval before retrying."""
        import mostlyright.markets._kalshi_client as kc

        with respx.mock(assert_all_called=False) as router:
            route = router.get(f"{KALSHI_API_BASE}/series/{_SERIES}/markets/{_TICKER}/candlesticks")
            route.side_effect = [
                httpx.Response(429, json={"error": "rate_limited"}, headers={"Retry-After": "5"}),
                httpx.Response(200, json={"candlesticks": []}),
            ]
            captured_sleep: list[float] = []
            orig_sleep = kc.time.sleep
            kc.time.sleep = lambda s: captured_sleep.append(s)
            try:
                candles(
                    _TICKER,
                    interval="1h",
                    from_=datetime(2026, 6, 1, tzinfo=UTC),
                    to=datetime(2026, 6, 2, tzinfo=UTC),
                    sleep_between=0,
                )
            finally:
                kc.time.sleep = orig_sleep
        # The 429-backoff sleep must be ≥ 5 (the Retry-After hint).
        # _BASE_DELAY is 1.0; max(5, 1.0) == 5.
        assert any(s >= 5 for s in captured_sleep), captured_sleep

    def test_parse_retry_after_seconds_helper(self):
        from mostlyright.markets._kalshi_client import _parse_retry_after_seconds

        assert _parse_retry_after_seconds("5") == 5.0
        assert _parse_retry_after_seconds("  10.5  ") == 10.5
        assert _parse_retry_after_seconds(None) is None
        assert _parse_retry_after_seconds("") is None
        assert _parse_retry_after_seconds("Wed, 21 Oct 2026 07:28:00 GMT") is None
        assert _parse_retry_after_seconds("-3") is None
        assert _parse_retry_after_seconds("nan") is None
        assert _parse_retry_after_seconds("inf") is None

    def test_retry_after_capped_at_max(self):
        """Iter-2 python-architect HIGH: a hostile/buggy server returning
        Retry-After: 999999 must not hang the SDK for ~11 days. The
        _MAX_RETRY_AFTER_S cap (120s) bounds the sleep."""
        import mostlyright.markets._kalshi_client as kc

        with respx.mock(assert_all_called=False) as router:
            route = router.get(f"{KALSHI_API_BASE}/series/{_SERIES}/markets/{_TICKER}/candlesticks")
            route.side_effect = [
                httpx.Response(
                    429, json={"error": "rate_limited"}, headers={"Retry-After": "999999"}
                ),
                httpx.Response(200, json={"candlesticks": []}),
            ]
            captured_sleep: list[float] = []
            orig_sleep = kc.time.sleep
            kc.time.sleep = lambda s: captured_sleep.append(s)
            try:
                candles(
                    _TICKER,
                    interval="1h",
                    from_=datetime(2026, 6, 1, tzinfo=UTC),
                    to=datetime(2026, 6, 2, tzinfo=UTC),
                    sleep_between=0,
                )
            finally:
                kc.time.sleep = orig_sleep
        # The 429-backoff sleep must be ≤ _MAX_RETRY_AFTER_S (120s) even
        # though the server requested 999999.
        backoff_sleeps = [s for s in captured_sleep if s > 1.0]
        assert backoff_sleeps, captured_sleep
        assert all(s <= 120.0 for s in backoff_sleeps), captured_sleep


# ---------------------------------------------------------------------------
# fills
# ---------------------------------------------------------------------------
class TestFills:
    def test_pagination_loops_until_empty_cursor_real_shape(self):
        """Real Kalshi /markets/trades response (post-March-2026 migration):
        yes_price_dollars + no_price_dollars + count_fp + taker_outcome_side."""
        with respx.mock(assert_all_called=False) as router:
            route = router.get(f"{KALSHI_API_BASE}/markets/trades")
            route.side_effect = [
                httpx.Response(
                    200,
                    json={
                        "trades": [
                            {
                                "trade_id": "t1",
                                "created_time": 1717200000,
                                "yes_price_dollars": "0.5200",
                                "no_price_dollars": "0.4800",
                                "count_fp": "10",
                                "taker_outcome_side": "yes",
                            }
                        ],
                        "cursor": "PAGE2",
                    },
                ),
                httpx.Response(
                    200,
                    json={
                        "trades": [
                            {
                                "trade_id": "t2",
                                "created_time": 1717200100,
                                "yes_price_dollars": "0.5300",
                                "no_price_dollars": "0.4700",
                                "count_fp": "5",
                                "taker_outcome_side": "no",
                            }
                        ],
                        "cursor": "",
                    },
                ),
            ]
            df = fills(_TICKER, sleep_between=0)
        assert len(df) == 2
        assert (df["source"] == "kalshi").all()
        assert df["trade_id"].tolist() == ["t1", "t2"]
        # cents (0–100), converted from dollars strings
        assert df["yes_price"].tolist() == [52.0, 53.0]
        assert df["no_price"].tolist() == [48.0, 47.0]
        assert df["count"].tolist() == [10, 5]
        assert df["taker_side"].tolist() == ["yes", "no"]

    def test_legacy_unsuffixed_trade_fields_still_parsed(self):
        with respx.mock(assert_all_called=False) as router:
            router.get(f"{KALSHI_API_BASE}/markets/trades").mock(
                return_value=httpx.Response(
                    200,
                    json={
                        "trades": [
                            {
                                "trade_id": "t1",
                                "created_time": 1717200000,
                                "yes_price": 52,
                                "no_price": 48,
                                "count": 10,
                                "taker_side": "yes",
                            }
                        ],
                        "cursor": "",
                    },
                )
            )
            df = fills(_TICKER, sleep_between=0)
        assert df["yes_price"].iloc[0] == 52.0
        assert df["count"].iloc[0] == 10
        assert df["taker_side"].iloc[0] == "yes"

    def test_iso_string_timestamp_parsed(self):
        with respx.mock(assert_all_called=False) as router:
            router.get(f"{KALSHI_API_BASE}/markets/trades").mock(
                return_value=httpx.Response(
                    200,
                    json={
                        "trades": [
                            {
                                "trade_id": "t1",
                                "created_time": "2026-06-01T00:00:00Z",
                                "yes_price": 52,
                                "no_price": 48,
                                "count": 10,
                                "taker_side": "yes",
                            }
                        ],
                        "cursor": "",
                    },
                )
            )
            df = fills(_TICKER, sleep_between=0)
        assert df["ts"].iloc[0] == datetime(2026, 6, 1, tzinfo=UTC)

    def test_naive_since_raises(self):
        with pytest.raises(TypeError, match="tz-aware"):
            fills(_TICKER, since=datetime(2026, 6, 1), sleep_between=0)

    def test_since_geq_until_raises(self):
        with pytest.raises(ValueError, match="must be <"):
            fills(
                _TICKER,
                since=datetime(2026, 6, 2, tzinfo=UTC),
                until=datetime(2026, 6, 1, tzinfo=UTC),
                sleep_between=0,
            )

    def test_max_pages_exceeded_raises(self):
        with respx.mock(assert_all_called=False) as router:
            # Always return a cursor — would loop forever without max_pages cap.
            router.get(f"{KALSHI_API_BASE}/markets/trades").mock(
                return_value=httpx.Response(
                    200,
                    json={
                        "trades": [{"trade_id": "loop", "created_time": 1, "count": 1}],
                        "cursor": "FOREVER",
                    },
                )
            )
            with pytest.raises(RuntimeError, match="max_pages"):
                fills(_TICKER, max_pages=3, sleep_between=0)


# ---------------------------------------------------------------------------
# orderbook
# ---------------------------------------------------------------------------
class TestOrderbook:
    def test_yes_no_levels_real_kalshi_shape(self):
        """Real Kalshi /markets/{ticker}/orderbook response: orderbook_fp with
        yes_dollars / no_dollars arrays of [price_dollar_string, count_fp_string]."""
        with respx.mock(assert_all_called=False) as router:
            router.get(f"{KALSHI_API_BASE}/markets/{_TICKER}/orderbook").mock(
                return_value=httpx.Response(
                    200,
                    json={
                        "orderbook_fp": {
                            "yes_dollars": [["0.5200", "100"], ["0.5100", "200"]],
                            "no_dollars": [["0.4800", "150"]],
                        }
                    },
                )
            )
            df = orderbook(_TICKER, sleep_between=0)
        assert list(df.columns) == ["side", "price", "size", "source"]
        assert len(df) == 3
        assert (df["source"] == "kalshi").all()
        # cents = float(dollars_string) * 100
        assert df[df["side"] == "yes"]["price"].tolist() == [52.0, 51.0]
        assert df[df["side"] == "yes"]["size"].tolist() == [100, 200]
        assert df[df["side"] == "no"]["price"].tolist() == [48.0]

    def test_legacy_orderbook_shape_still_parsed(self):
        with respx.mock(assert_all_called=False) as router:
            router.get(f"{KALSHI_API_BASE}/markets/{_TICKER}/orderbook").mock(
                return_value=httpx.Response(
                    200,
                    json={
                        "orderbook": {
                            "yes": [[52, 100], [51, 200]],
                            "no": [[48, 150]],
                        }
                    },
                )
            )
            df = orderbook(_TICKER, sleep_between=0)
        assert len(df) == 3
        assert df[df["side"] == "yes"]["price"].tolist() == [52.0, 51.0]

    def test_dict_form_levels_tolerated(self):
        with respx.mock(assert_all_called=False) as router:
            router.get(f"{KALSHI_API_BASE}/markets/{_TICKER}/orderbook").mock(
                return_value=httpx.Response(
                    200,
                    json={
                        "orderbook": {
                            "yes": [{"price": 50, "size": 25}],
                            "no": [],
                        }
                    },
                )
            )
            df = orderbook(_TICKER, sleep_between=0)
        assert len(df) == 1
        assert df["price"].iloc[0] == 50.0
        assert df["size"].iloc[0] == 25

    def test_depth_out_of_range_raises(self):
        with pytest.raises(ValueError, match="depth out of range"):
            orderbook(_TICKER, depth=0, sleep_between=0)

    def test_snapshot_at_attr_present(self):
        with respx.mock(assert_all_called=False) as router:
            router.get(f"{KALSHI_API_BASE}/markets/{_TICKER}/orderbook").mock(
                return_value=httpx.Response(200, json={"orderbook": {"yes": [], "no": []}})
            )
            df = orderbook(_TICKER, sleep_between=0)
        assert "snapshot_at" in df.attrs
        assert isinstance(df.attrs["snapshot_at"], datetime)

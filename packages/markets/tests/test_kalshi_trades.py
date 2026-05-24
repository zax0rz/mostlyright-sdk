"""Tests for the Phase 9 Kalshi trades surface (TRADES-01..03).

All HTTP calls are mocked via ``respx``; no test is marked
``@pytest.mark.live`` so the suite stays CI-safe.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import httpx
import pytest

respx = pytest.importorskip("respx")

from tradewinds.markets._kalshi_client import (  # noqa: E402
    KALSHI_API_BASE,
)
from tradewinds.markets.kalshi_trades import (  # noqa: E402
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
    def test_returns_dataframe_with_expected_columns(self):
        with respx.mock(assert_all_called=False) as router:
            router.get(
                f"{KALSHI_API_BASE}/series/{_SERIES}/markets/{_TICKER}/candlesticks"
            ).mock(
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
                            {
                                "end_period_ts": 1717203600,
                                "price": {"open": 52, "high": 60, "low": 51, "close": 58},
                                "volume": 200,
                                "open_interest": 600,
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
        assert df["open"].iloc[0] == 50.0
        assert df["close"].iloc[1] == 58.0

    def test_empty_candlesticks_returns_empty_dataframe(self):
        with respx.mock(assert_all_called=False) as router:
            router.get(
                f"{KALSHI_API_BASE}/series/{_SERIES}/markets/{_TICKER}/candlesticks"
            ).mock(return_value=httpx.Response(200, json={"candlesticks": []}))
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
            route = router.get(
                f"{KALSHI_API_BASE}/series/{_SERIES}/markets/{_TICKER}/candlesticks"
            )
            route.side_effect = [
                httpx.Response(429, json={"error": "rate_limited"}),
                httpx.Response(200, json={"candlesticks": []}),
            ]
            # Patch out the backoff sleep so the test runs fast.
            import tradewinds.markets._kalshi_client as kc

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


# ---------------------------------------------------------------------------
# fills
# ---------------------------------------------------------------------------
class TestFills:
    def test_pagination_loops_until_empty_cursor(self):
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
                                "yes_price": 52,
                                "no_price": 48,
                                "count": 10,
                                "taker_side": "yes",
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
                                "yes_price": 53,
                                "no_price": 47,
                                "count": 5,
                                "taker_side": "no",
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
        assert df["count"].tolist() == [10, 5]

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
    def test_yes_no_levels_become_rows(self):
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
        assert list(df.columns) == ["side", "price", "size", "source"]
        assert len(df) == 3
        assert (df["source"] == "kalshi").all()
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
                return_value=httpx.Response(
                    200, json={"orderbook": {"yes": [], "no": []}}
                )
            )
            df = orderbook(_TICKER, sleep_between=0)
        assert "snapshot_at" in df.attrs
        assert isinstance(df.attrs["snapshot_at"], datetime)

"""Tests for the Phase 9 Polymarket trades surface (TRADES-04..05).

All HTTP calls mocked via ``respx``. CI-safe (no @pytest.mark.live).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

import httpx
import pytest

respx = pytest.importorskip("respx")

from tradewinds.markets._polymarket_client import GAMMA_API_BASE  # noqa: E402
from tradewinds.markets.polymarket_trades import history, snapshot  # noqa: E402


# ---------------------------------------------------------------------------
# history
# ---------------------------------------------------------------------------
class TestHistory:
    def test_returns_dataframe_with_expected_columns(self):
        with respx.mock(assert_all_called=False) as router:
            router.get(f"{GAMMA_API_BASE}/prices-history").mock(
                return_value=httpx.Response(
                    200,
                    json={
                        "history": [
                            {"t": 1717200000, "p": 0.42, "v": 100.0},
                            {"t": 1717203600, "p": 0.45, "v": 250.0},
                        ]
                    },
                )
            )
            df = history(
                "0xMARKETCONDITION",
                from_=datetime(2026, 6, 1, tzinfo=UTC),
                to=datetime(2026, 6, 2, tzinfo=UTC),
                sleep_between=0,
            )
        assert list(df.columns) == ["ts", "price", "volume", "source"]
        assert len(df) == 2
        assert (df["source"] == "polymarket.gamma").all()
        assert df["price"].tolist() == [0.42, 0.45]

    def test_bare_list_payload_tolerated(self):
        """Gamma occasionally returns a bare list instead of {history: ...}."""
        with respx.mock(assert_all_called=False) as router:
            router.get(f"{GAMMA_API_BASE}/prices-history").mock(
                return_value=httpx.Response(
                    200,
                    json=[
                        {"t": 1717200000, "p": 0.42, "v": 100.0},
                    ],
                )
            )
            df = history(
                "M1",
                from_=datetime(2026, 6, 1, tzinfo=UTC),
                to=datetime(2026, 6, 2, tzinfo=UTC),
                sleep_between=0,
            )
        assert len(df) == 1

    def test_empty_history_returns_empty_dataframe(self):
        with respx.mock(assert_all_called=False) as router:
            router.get(f"{GAMMA_API_BASE}/prices-history").mock(
                return_value=httpx.Response(200, json={"history": []})
            )
            df = history(
                "M1",
                from_=datetime(2026, 6, 1, tzinfo=UTC),
                to=datetime(2026, 6, 2, tzinfo=UTC),
                sleep_between=0,
            )
        assert len(df) == 0
        assert list(df.columns) == ["ts", "price", "volume", "source"]

    def test_naive_datetime_raises(self):
        with pytest.raises(TypeError, match="tz-aware"):
            history(
                "M1",
                from_=datetime(2026, 6, 1),
                to=datetime(2026, 6, 2, tzinfo=UTC),
                sleep_between=0,
            )

    def test_from_geq_to_raises(self):
        with pytest.raises(ValueError, match="must be <"):
            history(
                "M1",
                from_=datetime(2026, 6, 2, tzinfo=UTC),
                to=datetime(2026, 6, 1, tzinfo=UTC),
                sleep_between=0,
            )

    def test_empty_market_id_raises(self):
        with pytest.raises(ValueError, match="non-empty str"):
            history(
                "",
                from_=datetime(2026, 6, 1, tzinfo=UTC),
                to=datetime(2026, 6, 2, tzinfo=UTC),
                sleep_between=0,
            )

    def test_fidelity_zero_raises(self):
        with pytest.raises(ValueError, match="fidelity_minutes"):
            history(
                "M1",
                from_=datetime(2026, 6, 1, tzinfo=UTC),
                to=datetime(2026, 6, 2, tzinfo=UTC),
                fidelity_minutes=0,
                sleep_between=0,
            )


# ---------------------------------------------------------------------------
# snapshot
# ---------------------------------------------------------------------------
class TestSnapshot:
    def test_returns_row_per_outcome(self):
        # Polymarket commonly JSON-encodes outcomes / outcomePrices.
        event_payload = {
            "id": "E1",
            "slug": "highest-temp-in-nyc",
            "markets": [
                {
                    "id": "M1",
                    "outcomes": json.dumps(["Yes", "No"]),
                    "outcomePrices": json.dumps(["0.62", "0.38"]),
                    "volume": "12345.67",
                    "liquidity": "5000",
                },
            ],
        }
        with respx.mock(assert_all_called=False) as router:
            router.get(f"{GAMMA_API_BASE}/events/E1").mock(
                return_value=httpx.Response(200, json=event_payload)
            )
            df = snapshot("E1")
        assert list(df.columns) == [
            "market_id",
            "outcome",
            "last_price",
            "volume",
            "liquidity",
            "source",
        ]
        assert len(df) == 2
        assert df["outcome"].tolist() == ["Yes", "No"]
        assert df["last_price"].tolist() == [0.62, 0.38]
        assert (df["source"] == "polymarket.gamma").all()
        assert df["volume"].iloc[0] == pytest.approx(12345.67)

    def test_native_list_outcomes_also_supported(self):
        event_payload = {
            "id": "E1",
            "markets": [
                {
                    "id": "M1",
                    "outcomes": ["Yes", "No"],  # native list, not JSON-string
                    "outcomePrices": ["0.5", "0.5"],
                    "volume": 100,
                    "liquidity": 0,
                },
            ],
        }
        with respx.mock(assert_all_called=False) as router:
            router.get(f"{GAMMA_API_BASE}/events/E1").mock(
                return_value=httpx.Response(200, json=event_payload)
            )
            df = snapshot("E1")
        assert len(df) == 2
        assert df["last_price"].tolist() == [0.5, 0.5]

    def test_multi_market_event_flattens(self):
        event_payload = {
            "id": "E2",
            "markets": [
                {
                    "id": "M1",
                    "outcomes": ["Yes", "No"],
                    "outcomePrices": ["0.6", "0.4"],
                },
                {
                    "id": "M2",
                    "outcomes": ["Yes", "No"],
                    "outcomePrices": ["0.3", "0.7"],
                },
            ],
        }
        with respx.mock(assert_all_called=False) as router:
            router.get(f"{GAMMA_API_BASE}/events/E2").mock(
                return_value=httpx.Response(200, json=event_payload)
            )
            df = snapshot("E2")
        assert len(df) == 4
        assert df["market_id"].tolist() == ["M1", "M1", "M2", "M2"]

    def test_empty_markets_returns_empty(self):
        with respx.mock(assert_all_called=False) as router:
            router.get(f"{GAMMA_API_BASE}/events/E3").mock(
                return_value=httpx.Response(200, json={"id": "E3", "markets": []})
            )
            df = snapshot("E3")
        assert len(df) == 0
        assert list(df.columns) == [
            "market_id",
            "outcome",
            "last_price",
            "volume",
            "liquidity",
            "source",
        ]

    def test_snapshot_at_in_attrs(self):
        with respx.mock(assert_all_called=False) as router:
            router.get(f"{GAMMA_API_BASE}/events/E1").mock(
                return_value=httpx.Response(200, json={"id": "E1", "markets": []})
            )
            df = snapshot("E1")
        assert "snapshot_at" in df.attrs
        assert isinstance(df.attrs["snapshot_at"], datetime)

    def test_empty_event_id_raises(self):
        with pytest.raises(ValueError, match="non-empty str"):
            snapshot("")

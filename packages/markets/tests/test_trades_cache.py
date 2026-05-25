"""Tests for the Phase 9 trades cache (TRADES-06)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from mostlyright.markets._trades_cache import (
    invalidate_trades,
    read_trades_cache,
    trades_cache_path,
    write_trades_cache,
)


@pytest.fixture()
def cache_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("TRADEWINDS_CACHE_DIR", str(tmp_path))
    return tmp_path


# ---------------------------------------------------------------------------
# Path construction
# ---------------------------------------------------------------------------
class TestPath:
    def test_canonical_layout(self, cache_dir):
        path = trades_cache_path("kalshi", "KXHIGHNY-25MAY26-T79", 2026, 5)
        assert str(path).endswith("v1/trades/kalshi/KXHIGHNY-25MAY26-T79/2026-05.parquet")

    def test_uppercase_issuer_rejected(self, cache_dir):
        with pytest.raises(ValueError, match="invalid issuer"):
            trades_cache_path("Kalshi", "KX", 2026, 5)

    def test_empty_issuer_rejected(self, cache_dir):
        with pytest.raises(ValueError, match="invalid issuer"):
            trades_cache_path("", "KX", 2026, 5)

    def test_ticker_with_path_separator_rejected(self, cache_dir):
        with pytest.raises(ValueError, match="invalid ticker"):
            trades_cache_path("kalshi", "KX/EVIL", 2026, 5)

    def test_path_traversal_ticker_rejected(self, cache_dir):
        with pytest.raises(ValueError, match="invalid ticker"):
            trades_cache_path("kalshi", "../../etc/passwd", 2026, 5)

    def test_all_dot_ticker_rejected_dot(self, cache_dir):
        """Architect iter-1 HIGH: ``.`` ticker would silently misplace files."""
        with pytest.raises(ValueError, match="invalid ticker"):
            trades_cache_path("kalshi", ".", 2026, 5)

    def test_all_dot_ticker_rejected_dotdot(self, cache_dir):
        with pytest.raises(ValueError, match="invalid ticker"):
            trades_cache_path("kalshi", "..", 2026, 5)

    def test_all_dot_ticker_rejected_triple(self, cache_dir):
        with pytest.raises(ValueError, match="invalid ticker"):
            trades_cache_path("kalshi", "...", 2026, 5)

    def test_ticker_with_null_byte_rejected(self, cache_dir):
        with pytest.raises(ValueError, match="invalid ticker"):
            trades_cache_path("kalshi", "KX\x00EVIL", 2026, 5)

    def test_year_out_of_range_low(self, cache_dir):
        with pytest.raises(ValueError, match="year out of range"):
            trades_cache_path("kalshi", "KX", 1999, 5)

    def test_year_out_of_range_high(self, cache_dir):
        with pytest.raises(ValueError, match="year out of range"):
            trades_cache_path("kalshi", "KX", 2101, 5)

    def test_month_zero_rejected(self, cache_dir):
        with pytest.raises(ValueError, match="month out of range"):
            trades_cache_path("kalshi", "KX", 2026, 0)

    def test_month_13_rejected(self, cache_dir):
        with pytest.raises(ValueError, match="month out of range"):
            trades_cache_path("kalshi", "KX", 2026, 13)


# ---------------------------------------------------------------------------
# Current-UTC-month + future-month skip
# ---------------------------------------------------------------------------
class TestSkipRules:
    def test_current_utc_month_write_returns_false(self, cache_dir):
        now = datetime(2026, 6, 15, tzinfo=UTC)
        wrote = write_trades_cache(
            "kalshi",
            "KX",
            2026,
            6,
            [{"trade_id": "t1", "ts": 1, "price": 50}],
            now=now,
        )
        assert wrote is False
        # Nothing on disk.
        assert not trades_cache_path("kalshi", "KX", 2026, 6).exists()

    def test_current_utc_month_read_returns_None(self, cache_dir):
        now = datetime(2026, 6, 15, tzinfo=UTC)
        # Even if a stale file existed, the read returns None for current month.
        path = trades_cache_path("kalshi", "KX", 2026, 6)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"")  # stub
        result = read_trades_cache("kalshi", "KX", 2026, 6, now=now)
        assert result is None

    def test_future_month_write_returns_false(self, cache_dir):
        now = datetime(2026, 6, 15, tzinfo=UTC)
        wrote = write_trades_cache("kalshi", "KX", 2026, 7, [{"trade_id": "t1"}], now=now)
        assert wrote is False

    def test_future_year_write_returns_false(self, cache_dir):
        now = datetime(2026, 6, 15, tzinfo=UTC)
        wrote = write_trades_cache("kalshi", "KX", 2027, 1, [{"trade_id": "t1"}], now=now)
        assert wrote is False


# ---------------------------------------------------------------------------
# Past-month roundtrip
# ---------------------------------------------------------------------------
class TestRoundtrip:
    def test_write_then_read(self, cache_dir):
        now = datetime(2026, 6, 15, tzinfo=UTC)
        rows = [
            {"trade_id": "t1", "ts": 1717200000, "price": 50.0, "count": 10},
            {"trade_id": "t2", "ts": 1717200100, "price": 52.0, "count": 5},
        ]
        wrote = write_trades_cache("kalshi", "KX", 2026, 5, rows, now=now)
        assert wrote is True
        got = read_trades_cache("kalshi", "KX", 2026, 5, now=now)
        assert got == rows

    def test_write_empty_rows_returns_false(self, cache_dir):
        now = datetime(2026, 6, 15, tzinfo=UTC)
        wrote = write_trades_cache("kalshi", "KX", 2026, 5, [], now=now)
        assert wrote is False

    def test_read_missing_returns_None(self, cache_dir):
        now = datetime(2026, 6, 15, tzinfo=UTC)
        assert read_trades_cache("kalshi", "KX", 2026, 5, now=now) is None

    def test_corrupt_parquet_returns_None(self, cache_dir):
        """Cache miss on read failure — defensive against corrupted files."""
        now = datetime(2026, 6, 15, tzinfo=UTC)
        path = trades_cache_path("kalshi", "KX", 2026, 5)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"not parquet")
        assert read_trades_cache("kalshi", "KX", 2026, 5, now=now) is None


# ---------------------------------------------------------------------------
# invalidate
# ---------------------------------------------------------------------------
class TestInvalidate:
    def test_invalidate_existing_file(self, cache_dir):
        now = datetime(2026, 6, 15, tzinfo=UTC)
        rows = [{"trade_id": "t1"}]
        write_trades_cache("kalshi", "KX", 2026, 5, rows, now=now)
        path = trades_cache_path("kalshi", "KX", 2026, 5)
        assert path.exists()
        assert invalidate_trades("kalshi", "KX", 2026, 5) is True
        assert not path.exists()

    def test_invalidate_missing_file_returns_false(self, cache_dir):
        assert invalidate_trades("kalshi", "KX", 2026, 5) is False

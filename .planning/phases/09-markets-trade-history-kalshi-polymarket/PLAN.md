---
phase: 09
plan: 01
wave: 1
depends_on: [08]
files_modified:
  - packages/markets/src/tradewinds/markets/_kalshi_client.py
  - packages/markets/src/tradewinds/markets/_trades_cache.py
  - packages/markets/src/tradewinds/markets/kalshi/__init__.py
  - packages/markets/src/tradewinds/markets/kalshi/trades.py
  - packages/markets/src/tradewinds/markets/polymarket_trades.py
  - packages/markets/tests/test_kalshi_trades.py
  - packages/markets/tests/test_polymarket_trades.py
  - packages/markets/tests/test_trades_cache.py
  - packages-ts/markets/src/trades/index.ts
  - packages-ts/markets/src/trades/kalshi.ts
  - packages-ts/markets/src/trades/polymarket.ts
  - packages-ts/markets/src/trades/cache.ts
  - packages-ts/markets/src/trades/types.ts
  - packages-ts/markets/tests/trades/kalshi.test.ts
  - packages-ts/markets/tests/trades/polymarket.test.ts
  - packages-ts/markets/tests/trades/cache.test.ts
  - packages-ts/markets/tsup.config.ts
  - packages-ts/markets/package.json
  - .planning/research/MARKETS-RATE-LIMITS.md
requirements: [TRADES-01, TRADES-02, TRADES-03, TRADES-04, TRADES-05, TRADES-06, TRADES-07, TRADES-08]
autonomous: true
review_panel:
  - codex high
  - python-architect
  - typescript-architect
must_haves:
  truths:
    - kalshi candles/fills/orderbook return DataFrames with source="kalshi" per row
    - polymarket history/snapshot return DataFrames with source="polymarket.gamma" per row
    - cache layout ~/.tradewinds/cache/v1/trades/{issuer}/{ticker}/{YYYY-MM}.parquet with current-UTC-month rewriteable
    - TS port at @tradewinds/markets/trades subpath, row-equivalent shape to Python
    - rate-limit politeness floors documented per source
    - mock-tested (respx/pytest-httpx/msw) — no @pytest.mark.live in CI
  key_links:
    - .planning/ROADMAP.md#phase-9
    - .planning/REQUIREMENTS.md#phase-9-markets-trade-history--kalshi--polymarket-v02
    - .planning/REVIEW-DISCIPLINE.md
    - packages/markets/src/tradewinds/markets/_polymarket_client.py
    - packages/markets/src/tradewinds/markets/polymarket.py
---

# Plan 09-01: Markets Trade History (Kalshi + Polymarket)

## TS Parity

Phase 9 is **dual-SDK** (paired Python + TS in same merge per CROSS-SDK-SYNC.md §2). Every Python deliverable carries a TS counterpart:

| Python | TS counterpart |
|---|---|
| `tradewinds.markets.kalshi.trades.{candles, fills, orderbook}` | `@tradewinds/markets/trades` (`kalshiCandles`, `kalshiFills`, `kalshiOrderbook`) |
| `tradewinds.markets.polymarket.trades.{history, snapshot}` | `@tradewinds/markets/trades` (`polymarketHistory`, `polymarketSnapshot`) |
| `_trades_cache.py` (filesystem parquet) | `trades/cache.ts` (IndexedDB / FsStore via existing `@tradewinds/core` cache adapter) |
| `_kalshi_client.py` (rate-limited httpx wrapper) | `trades/kalshi-client.ts` (rate-limited fetch wrapper) |

**TS-only constraints:** trades cache uses the existing `CacheStore` interface from `@tradewinds/core` (MemoryStore / IndexedDBStore / FsStore). Bundle size impact ≤ ~3 KB on `@tradewinds/markets` subpath (well under 10 KB main-bundle gate; subpath bundled separately). No CORS posture change — Kalshi public-market endpoints don't require auth + return CORS headers (verified via TS-W5 wave research); Polymarket Gamma is server-side per `.planning/research/TS-CORS-MATRIX.md`.

## Objective

Add trade-history surface (candles, fills, orderbook, history, snapshot) for both Kalshi and Polymarket so quants can pair settlement data with trade timeseries. This phase unblocks `include_trades=True` in Phase 10's composable `research()`.

The implementation is dominated by HTTP-client work + DataFrame shaping + cache wiring. No new merge logic, no parity-fixture impact (trades data is not part of the v0.14.1 weather-parity contract).

## Tasks

### Task 1.1: Kalshi shared HTTP client (`_kalshi_client.py`)

<read_first>
- packages/markets/src/tradewinds/markets/_polymarket_client.py (the canonical rate-limited httpx pattern for this codebase)
- packages/core/src/tradewinds/_internal/_http.py (download_with_retry — TRANSIENT_CODES, retry backoff)
</read_first>

<action>
Create `packages/markets/src/tradewinds/markets/_kalshi_client.py`. Public-only Kalshi REST client (no auth) over `https://api.elections.kalshi.com/trade-api/v2/` (the public market data subset).

```python
from __future__ import annotations

import logging
import time
from typing import Any

import httpx

log = logging.getLogger(__name__)

KALSHI_API_BASE = "https://api.elections.kalshi.com/trade-api/v2"

#: Kalshi documented rate limit is 10 req/sec for public endpoints (see
#: .planning/research/MARKETS-RATE-LIMITS.md). 0.1s polite floor stays
#: well under that to avoid 429s in burst scenarios.
_REQUEST_DELAY_S: float = 0.1

#: Per-page batch size for paginated trade endpoints.
_TRADES_PAGE_LIMIT: int = 1000

_TRANSIENT_CODES = frozenset({429, 500, 502, 503, 504})
_MAX_RETRIES = 3
_BASE_DELAY = 1.0

_USER_AGENT = "tradewinds-markets/0.2 (+https://github.com/helloiamvu/tradewinds)"


def _request(
    path: str,
    *,
    params: dict[str, Any] | None = None,
    client: httpx.Client | None = None,
    sleep_between: float = _REQUEST_DELAY_S,
) -> dict[str, Any]:
    """GET ``path`` and return JSON. Retries 429/5xx with exponential backoff."""
    url = f"{KALSHI_API_BASE}{path}"
    headers = {"User-Agent": _USER_AGENT, "Accept": "application/json"}
    _owns_client = client is None
    if client is None:
        client = httpx.Client(timeout=30.0)
    try:
        delay = _BASE_DELAY
        for attempt in range(_MAX_RETRIES):
            response = client.get(url, params=params, headers=headers)
            if response.status_code in _TRANSIENT_CODES and attempt < _MAX_RETRIES - 1:
                log.warning(
                    "kalshi HTTP %d for %s, retry %d/%d in %.1fs",
                    response.status_code, url, attempt + 1, _MAX_RETRIES, delay,
                )
                time.sleep(delay)
                delay *= 2
                continue
            response.raise_for_status()
            if sleep_between > 0:
                time.sleep(sleep_between)
            return response.json()
        raise RuntimeError(f"kalshi {url}: exhausted retries")
    finally:
        if _owns_client:
            client.close()


def fetch_candlesticks(
    ticker: str,
    *,
    start_ts: int,
    end_ts: int,
    period_interval: int,
    client: httpx.Client | None = None,
) -> list[dict[str, Any]]:
    """GET /series/{series_ticker}/markets/{ticker}/candlesticks.

    Kalshi groups markets under series tickers. ``ticker`` here is the
    full market ticker (e.g. ``KXHIGHNY-25MAY26-T79``); the series is
    parsed as the prefix before the first hyphen.
    """
    series = ticker.split("-", 1)[0]
    path = f"/series/{series}/markets/{ticker}/candlesticks"
    params = {
        "start_ts": start_ts,
        "end_ts": end_ts,
        "period_interval": period_interval,
    }
    payload = _request(path, params=params, client=client)
    return payload.get("candlesticks", []) or []


def fetch_trades(
    ticker: str,
    *,
    min_ts: int | None = None,
    max_ts: int | None = None,
    client: httpx.Client | None = None,
) -> list[dict[str, Any]]:
    """GET /markets/trades?ticker=<ticker> with cursor pagination."""
    path = "/markets/trades"
    out: list[dict[str, Any]] = []
    cursor: str | None = None
    while True:
        params: dict[str, Any] = {"ticker": ticker, "limit": _TRADES_PAGE_LIMIT}
        if min_ts is not None:
            params["min_ts"] = min_ts
        if max_ts is not None:
            params["max_ts"] = max_ts
        if cursor:
            params["cursor"] = cursor
        payload = _request(path, params=params, client=client)
        trades = payload.get("trades", []) or []
        out.extend(trades)
        cursor = payload.get("cursor")
        if not cursor or not trades:
            break
    return out


def fetch_orderbook(
    ticker: str,
    *,
    depth: int = 50,
    client: httpx.Client | None = None,
) -> dict[str, Any]:
    """GET /markets/{ticker}/orderbook."""
    path = f"/markets/{ticker}/orderbook"
    return _request(path, params={"depth": depth}, client=client)
```
</action>

<acceptance_criteria>
- Module importable: `from tradewinds.markets._kalshi_client import fetch_candlesticks, fetch_trades, fetch_orderbook`.
- Functions raise on 4xx (other than 429), retry on 429/5xx with exponential backoff.
- Cursor pagination loops until empty cursor or empty page.
- Tests with respx/pytest-httpx mock the HTTP layer; unit tests are NOT marked `@pytest.mark.live`.
</acceptance_criteria>

### Task 1.2: Kalshi trades public surface (`kalshi/trades.py`)

<action>
Convert `packages/markets/src/tradewinds/markets/kalshi/` into a subpackage:
1. `packages/markets/src/tradewinds/markets/kalshi/__init__.py` — re-exports `trades` namespace.
2. `packages/markets/src/tradewinds/markets/kalshi/trades.py` — public surface.

```python
"""Kalshi trade-history surface (TRADES-01..03).

Public read-only Kalshi market data: candlestick OHLCV, historical fills,
orderbook snapshot. No auth required.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from tradewinds.markets._kalshi_client import (
    fetch_candlesticks,
    fetch_orderbook,
    fetch_trades,
)

if TYPE_CHECKING:
    import pandas as pd

__all__ = ["candles", "fills", "orderbook"]

_SOURCE = "kalshi"


def _require_pandas() -> Any:
    try:
        import pandas as _pandas
    except ImportError as exc:
        from tradewinds.core.exceptions import SourceUnavailableError

        raise SourceUnavailableError(
            "tradewinds.markets.kalshi.trades requires pandas. Install with: "
            "pip install tradewinds-markets[trades]",
            source="kalshi",
            retryable=False,
            underlying=str(exc),
        ) from None
    return _pandas


def candles(
    ticker: str,
    *,
    interval: str,
    from_: datetime,
    to: datetime,
    client: Any | None = None,
) -> "pd.DataFrame":
    """Return OHLCV candles for `ticker` between `from_` and `to`.

    Args:
        ticker: Kalshi market ticker (e.g. "KXHIGHNY-25MAY26-T79").
        interval: Granularity — one of "1m", "1h", "1d".
        from_, to: tz-aware UTC datetimes (TypeError if naive).
        client: Optional httpx.Client for connection reuse.

    Returns:
        DataFrame with columns: ts, open, high, low, close, volume,
        open_interest, source.
    """
    pd = _require_pandas()
    _validate_aware(from_, "from_")
    _validate_aware(to, "to")
    if from_ >= to:
        raise ValueError(f"from_ ({from_}) must be < to ({to})")
    interval_seconds = _interval_to_seconds(interval)
    raw = fetch_candlesticks(
        ticker,
        start_ts=int(from_.timestamp()),
        end_ts=int(to.timestamp()),
        period_interval=interval_seconds // 60,  # Kalshi takes minutes
        client=client,
    )
    rows = []
    for c in raw:
        rows.append(
            {
                "ts": datetime.fromtimestamp(c["end_period_ts"], tz=UTC),
                "open": _maybe_float(c.get("price", {}).get("open")),
                "high": _maybe_float(c.get("price", {}).get("high")),
                "low": _maybe_float(c.get("price", {}).get("low")),
                "close": _maybe_float(c.get("price", {}).get("close")),
                "volume": _maybe_int(c.get("volume")),
                "open_interest": _maybe_int(c.get("open_interest")),
                "source": _SOURCE,
            }
        )
    df = pd.DataFrame(
        rows,
        columns=["ts", "open", "high", "low", "close", "volume", "open_interest", "source"],
    )
    df.attrs["source"] = _SOURCE
    df.attrs["ticker"] = ticker
    df.attrs["interval"] = interval
    return df


def fills(
    ticker: str,
    *,
    since: datetime | None = None,
    until: datetime | None = None,
    client: Any | None = None,
) -> "pd.DataFrame":
    """Return historical fills for `ticker` (paginated)."""
    pd = _require_pandas()
    if since is not None:
        _validate_aware(since, "since")
    if until is not None:
        _validate_aware(until, "until")
    min_ts = int(since.timestamp()) if since is not None else None
    max_ts = int(until.timestamp()) if until is not None else None
    raw = fetch_trades(ticker, min_ts=min_ts, max_ts=max_ts, client=client)
    rows = []
    for t in raw:
        rows.append(
            {
                "trade_id": t.get("trade_id"),
                "ts": datetime.fromtimestamp(t["created_time"], tz=UTC)
                if isinstance(t.get("created_time"), (int, float))
                else None,
                "yes_price": _maybe_float(t.get("yes_price")),
                "no_price": _maybe_float(t.get("no_price")),
                "count": _maybe_int(t.get("count")),
                "taker_side": t.get("taker_side"),
                "source": _SOURCE,
            }
        )
    df = pd.DataFrame(
        rows,
        columns=["trade_id", "ts", "yes_price", "no_price", "count", "taker_side", "source"],
    )
    df.attrs["source"] = _SOURCE
    df.attrs["ticker"] = ticker
    return df


def orderbook(
    ticker: str,
    *,
    depth: int = 50,
    client: Any | None = None,
) -> "pd.DataFrame":
    """Return current orderbook snapshot for `ticker` as a flat DataFrame."""
    pd = _require_pandas()
    payload = fetch_orderbook(ticker, depth=depth, client=client)
    book = payload.get("orderbook") or {}
    rows = []
    for side, key in [("yes", "yes"), ("no", "no")]:
        for price, size in book.get(key) or []:
            rows.append(
                {
                    "side": side,
                    "price": _maybe_float(price),
                    "size": _maybe_int(size),
                    "source": _SOURCE,
                }
            )
    df = pd.DataFrame(rows, columns=["side", "price", "size", "source"])
    df.attrs["source"] = _SOURCE
    df.attrs["ticker"] = ticker
    df.attrs["snapshot_at"] = datetime.now(UTC)
    return df


# ---- helpers ---------------------------------------------------------------
def _validate_aware(dt: datetime, name: str) -> None:
    if not isinstance(dt, datetime):
        raise TypeError(f"{name} must be datetime, got {type(dt).__name__}")
    if dt.tzinfo is None:
        raise TypeError(f"{name} must be tz-aware UTC datetime")


_INTERVAL_MAP = {"1m": 60, "1h": 3600, "1d": 86400}


def _interval_to_seconds(interval: str) -> int:
    if interval not in _INTERVAL_MAP:
        raise ValueError(f"interval must be one of {sorted(_INTERVAL_MAP)}, got {interval!r}")
    return _INTERVAL_MAP[interval]


def _maybe_float(v: Any) -> float | None:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _maybe_int(v: Any) -> int | None:
    if v is None:
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None
```

Update `packages/markets/src/tradewinds/markets/kalshi/__init__.py` to re-export `trades` (if existing `kalshi/` is empty/missing, create it as a subpackage with `from . import trades` + the existing `catalog/` modules re-exported).
</action>

<acceptance_criteria>
- `from tradewinds.markets.kalshi.trades import candles, fills, orderbook` works.
- `candles("KXHIGHNY-25MAY26-T79", interval="1h", from_=utc_dt_a, to=utc_dt_b)` returns a DataFrame with the 8 expected columns + `source="kalshi"` on every row.
- Naive datetimes raise TypeError.
- `from_ >= to` raises ValueError.
- Tests use respx/pytest-httpx mocks; no `@pytest.mark.live` decorator (mock-only in CI).
</acceptance_criteria>

### Task 1.3: Polymarket trades public surface (`polymarket_trades.py`)

<action>
Create `packages/markets/src/tradewinds/markets/polymarket_trades.py`:

```python
"""Polymarket trade-history surface (TRADES-04..05).

Public read-only Polymarket Gamma API: market price timeseries +
event snapshot. No auth required.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from tradewinds.markets._polymarket_client import _request, fetch_event_by_id

if TYPE_CHECKING:
    import pandas as pd

__all__ = ["history", "snapshot"]

_SOURCE = "polymarket.gamma"


def _require_pandas() -> Any:
    try:
        import pandas as _pandas
    except ImportError as exc:
        from tradewinds.core.exceptions import SourceUnavailableError

        raise SourceUnavailableError(
            "tradewinds.markets.polymarket.trades requires pandas. Install with: "
            "pip install tradewinds-markets[trades]",
            source="polymarket.gamma",
            retryable=False,
            underlying=str(exc),
        ) from None
    return _pandas


def history(
    market_id: str,
    *,
    from_: datetime,
    to: datetime,
    fidelity: int = 60,  # minutes per bucket
    client: Any | None = None,
) -> "pd.DataFrame":
    """Return market price/volume timeseries from Gamma.

    Args:
        market_id: Polymarket market id (e.g. condition_id or numeric id).
        from_, to: tz-aware UTC datetimes.
        fidelity: Bucket size in minutes (default 60 = hourly).

    Returns:
        DataFrame with columns: ts, price, volume, source.
    """
    pd = _require_pandas()
    _validate_aware(from_, "from_")
    _validate_aware(to, "to")
    if from_ >= to:
        raise ValueError(f"from_ ({from_}) must be < to ({to})")

    payload = _request(
        "/prices-history",
        params={
            "market": market_id,
            "startTs": int(from_.timestamp()),
            "endTs": int(to.timestamp()),
            "fidelity": fidelity,
        },
        client=client,
    )
    raw = payload.get("history", []) if isinstance(payload, dict) else (payload or [])
    rows = []
    for p in raw:
        rows.append(
            {
                "ts": datetime.fromtimestamp(p["t"], tz=UTC)
                if isinstance(p.get("t"), (int, float))
                else None,
                "price": _maybe_float(p.get("p")),
                "volume": _maybe_float(p.get("v")),
                "source": _SOURCE,
            }
        )
    df = pd.DataFrame(rows, columns=["ts", "price", "volume", "source"])
    df.attrs["source"] = _SOURCE
    df.attrs["market_id"] = market_id
    df.attrs["fidelity_minutes"] = fidelity
    return df


def snapshot(
    event_id: str,
    *,
    client: Any | None = None,
) -> "pd.DataFrame":
    """Return current state for `event_id` from Gamma.

    Returns:
        DataFrame with one row per outcome: outcome, last_price, volume,
        liquidity, source.
    """
    pd = _require_pandas()
    event = fetch_event_by_id(event_id, client=client)
    if not isinstance(event, dict):
        raise ValueError(f"polymarket snapshot: bad event payload for {event_id!r}")
    markets = event.get("markets") or []
    rows = []
    for m in markets:
        outcomes = m.get("outcomes") or []
        prices = m.get("outcomePrices") or []
        for i, outcome in enumerate(outcomes):
            price = prices[i] if i < len(prices) else None
            rows.append(
                {
                    "market_id": m.get("id"),
                    "outcome": outcome,
                    "last_price": _maybe_float(price),
                    "volume": _maybe_float(m.get("volume")),
                    "liquidity": _maybe_float(m.get("liquidity")),
                    "source": _SOURCE,
                }
            )
    df = pd.DataFrame(
        rows,
        columns=["market_id", "outcome", "last_price", "volume", "liquidity", "source"],
    )
    df.attrs["source"] = _SOURCE
    df.attrs["event_id"] = event_id
    df.attrs["snapshot_at"] = datetime.now(UTC)
    return df


# ---- helpers --------------------------------------------------------------
def _validate_aware(dt: datetime, name: str) -> None:
    if not isinstance(dt, datetime):
        raise TypeError(f"{name} must be datetime, got {type(dt).__name__}")
    if dt.tzinfo is None:
        raise TypeError(f"{name} must be tz-aware UTC datetime")


def _maybe_float(v: Any) -> float | None:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None
```

Note: `_request` may need to be exported from `_polymarket_client.py` (currently internal). Add it to `__all__` there or use a thin wrapper here.
</action>

<acceptance_criteria>
- `from tradewinds.markets.polymarket_trades import history, snapshot` works.
- `history(market_id, from_=..., to=...)` returns DataFrame with `ts, price, volume, source`.
- `snapshot(event_id)` returns DataFrame with `market_id, outcome, last_price, volume, liquidity, source`.
- Naive datetimes raise TypeError.
- Mock-tested with respx.
</acceptance_criteria>

### Task 1.4: Trades cache layer (`_trades_cache.py`)

<action>
Create `packages/markets/src/tradewinds/markets/_trades_cache.py`:

```python
"""Trades cache — ~/.tradewinds/cache/v1/trades/{issuer}/{ticker}/{YYYY-MM}.parquet."""

from __future__ import annotations

import logging
import os
import re
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from filelock import FileLock

logger = logging.getLogger(__name__)

CACHE_VERSION = "v1"
DEFAULT_ROOT = Path.home() / ".tradewinds" / "cache"
LOCK_TIMEOUT_SECONDS = 30

#: Allowlist for issuer name segment in cache path.
_ISSUER_RE = re.compile(r"^[a-z][a-z0-9._-]{0,31}$")
#: Allowlist for ticker name segment (safer than letting issuer-specific
#: chars through unfiltered).
_TICKER_RE = re.compile(r"^[A-Za-z0-9._-]{1,128}$")


def _cache_root() -> Path:
    override = os.environ.get("TRADEWINDS_CACHE_DIR")
    return Path(override) if override else DEFAULT_ROOT


def trades_cache_path(issuer: str, ticker: str, year: int, month: int) -> Path:
    if not _ISSUER_RE.match(issuer):
        raise ValueError(f"invalid issuer name for cache path: {issuer!r}")
    if not _TICKER_RE.match(ticker):
        raise ValueError(f"invalid ticker name for cache path: {ticker!r}")
    if not (1 <= month <= 12):
        raise ValueError(f"month out of range: {month}")
    if not (2000 <= year <= 2100):
        raise ValueError(f"year out of range: {year}")
    root = _cache_root()
    path = root / CACHE_VERSION / "trades" / issuer / ticker / f"{year:04d}-{month:02d}.parquet"
    # Defense in depth — never escape the cache root via crafted ticker.
    resolved = path.resolve()
    root_resolved = root.resolve()
    if not str(resolved).startswith(str(root_resolved)):
        raise ValueError(f"computed cache path escapes root: {resolved}")
    return path


def _is_current_utc_month(year: int, month: int) -> bool:
    now = datetime.now(UTC)
    return year == now.year and month == now.month


def _is_future_utc_month(year: int, month: int) -> bool:
    now = datetime.now(UTC)
    return (year, month) > (now.year, now.month)


def read_trades_cache(issuer: str, ticker: str, year: int, month: int) -> list[dict] | None:
    """Read cached parquet rows; return None when unavailable or current-month."""
    if _is_current_utc_month(year, month) or _is_future_utc_month(year, month):
        return None
    path = trades_cache_path(issuer, ticker, year, month)
    if not path.exists():
        return None
    try:
        import pyarrow.parquet as pq

        table = pq.read_table(path)
        return table.to_pylist()
    except Exception:
        logger.warning("trades cache read failed for %s; ignoring", path, exc_info=True)
        return None


def write_trades_cache(
    issuer: str,
    ticker: str,
    year: int,
    month: int,
    rows: list[dict],
) -> bool:
    """Atomic write; no-op (returns False) when month is current UTC or future."""
    if _is_current_utc_month(year, month) or _is_future_utc_month(year, month):
        return False
    if not rows:
        return False
    path = trades_cache_path(issuer, ticker, year, month)
    path.parent.mkdir(parents=True, exist_ok=True)
    lock = FileLock(str(path) + ".lock", timeout=LOCK_TIMEOUT_SECONDS)
    with lock:
        import pyarrow as pa
        import pyarrow.parquet as pq

        table = pa.Table.from_pylist(rows)
        tmp = path.with_suffix(path.suffix + ".tmp")
        pq.write_table(table, tmp, version="2.6", coerce_timestamps="us")
        os.replace(tmp, path)
    return True


def invalidate_trades(issuer: str, ticker: str, year: int, month: int) -> bool:
    path = trades_cache_path(issuer, ticker, year, month)
    if path.exists():
        path.unlink()
        return True
    return False


__all__ = [
    "DEFAULT_ROOT",
    "CACHE_VERSION",
    "invalidate_trades",
    "read_trades_cache",
    "trades_cache_path",
    "write_trades_cache",
]
```
</action>

<acceptance_criteria>
- `trades_cache_path("kalshi", "KXHIGHNY-25MAY26-T79", 2026, 5)` returns a Path under `$HOME/.tradewinds/cache/v1/trades/kalshi/KXHIGHNY-25MAY26-T79/2026-05.parquet`.
- Bad issuer / bad ticker / out-of-range year/month raise ValueError.
- write_cache for current UTC month returns False without writing.
- write_cache for future month returns False.
- write_cache + read_cache roundtrip preserves row content.
- TRADEWINDS_CACHE_DIR env var override works.
</acceptance_criteria>

### Task 1.5: Tests (Python)

<action>
Three new test files using respx/pytest-httpx mocks (no `@pytest.mark.live`):

1. `packages/markets/tests/test_kalshi_trades.py` — covers `candles`, `fills`, `orderbook`:
   - Mock Kalshi `/series/{s}/markets/{t}/candlesticks` → assert DataFrame shape + `source="kalshi"`.
   - Mock `/markets/trades?ticker=...&cursor=...` → assert pagination loops to empty cursor.
   - Mock `/markets/{t}/orderbook` → assert DataFrame with yes/no rows.
   - Naive-datetime raises TypeError.
   - `from_ >= to` raises ValueError.
   - Bad interval raises ValueError.
   - Retry on 429 → success on 2nd attempt.

2. `packages/markets/tests/test_polymarket_trades.py` — covers `history`, `snapshot`:
   - Mock Gamma `/prices-history` → assert DataFrame columns + `source="polymarket.gamma"`.
   - Mock `/events/{id}` → assert snapshot row-per-outcome.
   - Naive-datetime raises TypeError.

3. `packages/markets/tests/test_trades_cache.py`:
   - Path construction valid + invalid cases.
   - Current UTC month is no-op on write + None on read.
   - Future month is no-op.
   - Past month write + read roundtrip.
   - Path-traversal attempt via crafted ticker raises ValueError.
</action>

<acceptance_criteria>
- All three test files green.
- Mocks via `respx` (preferred — already on httpx integration) or `pytest_httpx`.
- No `@pytest.mark.live` markers.
- Full markets suite: `uv run pytest packages/markets/tests/ -q` exits 0.
</acceptance_criteria>

### Task 1.6: TS port — `@tradewinds/markets/trades` subpath

<action>
Create the TS counterpart:

1. `packages-ts/markets/src/trades/types.ts` — shared types (KalshiCandle, KalshiFill, KalshiOrderbookEntry, PolymarketPricePoint, PolymarketOutcome).
2. `packages-ts/markets/src/trades/kalshi-client.ts` — rate-limited fetch wrapper for Kalshi.
3. `packages-ts/markets/src/trades/kalshi.ts` — public `kalshiCandles`, `kalshiFills`, `kalshiOrderbook` functions returning row arrays + envelope.
4. `packages-ts/markets/src/trades/polymarket.ts` — public `polymarketHistory`, `polymarketSnapshot`.
5. `packages-ts/markets/src/trades/cache.ts` — thin adapter over `@tradewinds/core` `CacheStore` for trades; key = `trades/{issuer}/{ticker}/{YYYY-MM}`.
6. `packages-ts/markets/src/trades/index.ts` — barrel exports.
7. Update `packages-ts/markets/tsup.config.ts` to add a third entry for `src/trades/index.ts` → `dist/trades/`.
8. Update `packages-ts/markets/package.json` exports map to add `./trades` subpath.
9. Three test files mirroring Python:
   - `packages-ts/markets/tests/trades/kalshi.test.ts`
   - `packages-ts/markets/tests/trades/polymarket.test.ts`
   - `packages-ts/markets/tests/trades/cache.test.ts`

Type signatures (TS):
```typescript
export interface KalshiCandleRow {
  ts: string; // ISO UTC
  open: number | null;
  high: number | null;
  low: number | null;
  close: number | null;
  volume: number | null;
  openInterest: number | null;
  source: "kalshi";
}

export interface KalshiCandlesArgs {
  interval: "1m" | "1h" | "1d";
  from: Date;
  to: Date;
  fetchFn?: typeof fetch;
}

export async function kalshiCandles(
  ticker: string,
  args: KalshiCandlesArgs,
): Promise<readonly KalshiCandleRow[]>;
```

Symmetric for fills / orderbook / polymarket. Use `vitest` + `msw` or hand-rolled `fetchFn` injection (matches TS-W5 polymarket pattern).
</action>

<acceptance_criteria>
- `pnpm --filter @tradewinds/markets exec vitest run` exits 0 — all new trades tests pass.
- `pnpm --filter @tradewinds/markets typecheck` exits 0 — strict TS.
- `pnpm --filter @tradewinds/markets build` produces `dist/trades/index.{mjs,cjs,d.ts}`.
- Exports map allows `import { kalshiCandles } from "@tradewinds/markets/trades"`.
- Row shape matches Python (`source: "kalshi"` literal, ts as ISO string, etc.).
</acceptance_criteria>

### Task 1.7: Rate-limit politeness floors doc (TRADES-08)

<action>
Create `.planning/research/MARKETS-RATE-LIMITS.md` with:
- Kalshi: documented limit 10 req/sec for public endpoints (per docs link). Conservative floor 0.1s between requests = 10 req/sec ceiling matched exactly.
- Polymarket Gamma: no documented hard limit. Conservative floor 0.2s (inherited from existing `_polymarket_client.py` — 300 req/min). Worked reliably in v0.1 discovery.
- Empirical spike notes: deferred (running real spikes against public endpoints in CI is a DoS concern; manual operator-led spike documented but not gated).
- Future expansion: when websocket / orderbook tape arrives in v0.3, revisit.
</action>

<acceptance_criteria>
- `.planning/research/MARKETS-RATE-LIMITS.md` exists with per-source sections, citations, and the deferred-spike note.
</acceptance_criteria>

### Task 1.8: Review loop + STATE.md + merge

<action>
1. Run `uv run pytest -m "not live" -q` + `pnpm -r exec vitest run` — confirm green.
2. Dispatch review (codex high + python-architect + ts-architect, mixed PR routing) in parallel. Max 5 iterations.
3. Fix iter-N findings; loop.
4. Update STATE.md with Phase 9 closeout.
5. Rebase against main (in case Phase 6/7 parallel work landed) + merge `--no-ff` to main.
</action>

<acceptance_criteria>
- All three reviewers final-iter PASS.
- `git merge --no-ff` clean.
- STATE.md updated.
</acceptance_criteria>

## Out of scope (explicit)

- Websocket / streaming trades — v0.3.
- Kalshi orderbook tape (historical book replay) — v0.3.
- Polymarket UMA on-chain settlement validation — out of scope per Phase 8 + 9 ROADMAP.
- Authenticated Kalshi endpoints (private orders, account state) — v0.3+.
- Composable `research(include_trades=True)` integration — Phase 10.

## Review panel

Per REVIEW-DISCIPLINE.md mixed routing (Python + TS in same PR): codex `high` + Python Architect + TS Architect in parallel. User override: 5-iteration cap. Rate-limit changes are security-adjacent (DoS surface) — review may add security if rate-limit spike reveals unexpected headroom.

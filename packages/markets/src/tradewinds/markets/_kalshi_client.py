"""Kalshi public REST client — Phase 9.

Public read-only Kalshi market-data API at
``https://api.elections.kalshi.com/trade-api/v2``. No auth required, no
API key, no key registration — the candlestick, trades, and orderbook
endpoints are documented as public.

Kalshi documents a 10 req/sec rate limit for public endpoints (see
``.planning/research/MARKETS-RATE-LIMITS.md``). The 0.1s per-request
polite floor matches that ceiling exactly without throttling normal
backtest runs.

The module is deliberately narrow — only what
:mod:`tradewinds.markets.kalshi_trades` needs for v0.2 candles + fills +
orderbook. Authenticated endpoints (orders, positions, account state)
are out of scope and intentionally not exposed.
"""

from __future__ import annotations

import logging
import time
from typing import Any

import httpx

log = logging.getLogger(__name__)


#: Kalshi public REST endpoint base URL.
KALSHI_API_BASE: str = "https://api.elections.kalshi.com/trade-api/v2"


#: Per-request polite floor. Kalshi documents 10 req/sec ceiling for
#: public endpoints; 0.1s spaces requests to exactly match without
#: tripping the 429 burst threshold. Tests pass ``sleep_between=0`` to
#: skip.
_REQUEST_DELAY_S: float = 0.1


#: Per-page batch size for paginated trade endpoints.
_TRADES_PAGE_LIMIT: int = 1000


#: HTTP status codes that warrant a retry (transient).
_TRANSIENT_CODES: frozenset[int] = frozenset({429, 500, 502, 503, 504})


#: Bounded retry budget per request.
_MAX_RETRIES: int = 3


#: Base exponential backoff delay (doubled each retry).
_BASE_DELAY: float = 1.0


#: Safety cap on total pages walked per `fetch_trades` call. 10k pages *
#: 1000 trades/page = 10M trades, well beyond any sane backtest scope.
_MAX_TRADES_PAGES: int = 10_000


#: User-Agent banner. Sites occasionally block blank UAs as bot traffic.
_USER_AGENT: str = "tradewinds-markets/0.2 (+https://github.com/helloiamvu/tradewinds)"


def _request(
    path: str,
    *,
    params: dict[str, Any] | None = None,
    client: httpx.Client | None = None,
    sleep_between: float | None = None,
    timeout: float = 30.0,
) -> Any:
    """GET ``path`` and return decoded JSON.

    Retries 429/5xx with exponential backoff. 4xx (other than 429)
    surfaces immediately so callers see permanent errors (bad ticker,
    bad params) rather than wasting the retry budget.

    Args:
        path: Path under ``KALSHI_API_BASE`` (must start with ``/``).
        params: Optional query parameters.
        client: Optional ``httpx.Client`` for connection reuse.
        sleep_between: Per-request polite sleep. ``None`` uses the
            default 0.1s floor; tests pass ``0``.
        timeout: Per-request httpx timeout in seconds.

    Returns:
        Parsed JSON payload (``dict`` or ``list``).
    """
    if sleep_between is None:
        sleep_between = _REQUEST_DELAY_S
    url = f"{KALSHI_API_BASE}{path}"
    headers = {"User-Agent": _USER_AGENT, "Accept": "application/json"}
    owns_client = client is None
    if client is None:
        client = httpx.Client(timeout=timeout)
    try:
        delay = _BASE_DELAY
        for attempt in range(_MAX_RETRIES):
            response = client.get(url, params=params, headers=headers)
            if response.status_code in _TRANSIENT_CODES and attempt < _MAX_RETRIES - 1:
                log.warning(
                    "kalshi HTTP %d for %s, retry %d/%d in %.1fs",
                    response.status_code,
                    url,
                    attempt + 1,
                    _MAX_RETRIES,
                    delay,
                )
                time.sleep(delay)
                delay *= 2
                continue
            response.raise_for_status()
            if sleep_between > 0:
                time.sleep(sleep_between)
            return response.json()
        # Loop only exits via `continue` (transient + budget remaining) or
        # `return`. Reaching here means the final attempt was transient and
        # raise_for_status didn't fire — defensive RuntimeError.
        raise RuntimeError(  # pragma: no cover — unreachable
            f"kalshi {url}: exhausted retries without raising"
        )
    finally:
        if owns_client:
            client.close()


def fetch_candlesticks(
    ticker: str,
    *,
    start_ts: int,
    end_ts: int,
    period_interval: int,
    client: httpx.Client | None = None,
    sleep_between: float | None = None,
) -> list[dict[str, Any]]:
    """Fetch OHLCV candlesticks for a Kalshi market.

    Args:
        ticker: Full market ticker (e.g. ``KXHIGHNY-25MAY26-T79``). The
            series ticker is parsed as the prefix before the first ``-``.
        start_ts, end_ts: UNIX timestamps (seconds) bounding the window.
        period_interval: Bucket size in MINUTES (Kalshi documents 1, 60, 1440).
        client: Optional ``httpx.Client``.
        sleep_between: Per-request polite sleep override.

    Returns:
        List of candle dicts as returned by Kalshi (shape:
        ``{"end_period_ts": int, "price": {"open": int, "high": int,
        "low": int, "close": int}, "volume": int, "open_interest": int}``).
        Empty list when no candles in the window.
    """
    if "-" not in ticker:
        raise ValueError(
            f"kalshi ticker must contain '-' to derive series prefix; got {ticker!r}"
        )
    series = ticker.split("-", 1)[0]
    path = f"/series/{series}/markets/{ticker}/candlesticks"
    params = {
        "start_ts": start_ts,
        "end_ts": end_ts,
        "period_interval": period_interval,
    }
    payload = _request(path, params=params, client=client, sleep_between=sleep_between)
    candles = payload.get("candlesticks") if isinstance(payload, dict) else None
    return list(candles) if candles else []


def fetch_trades(
    ticker: str,
    *,
    min_ts: int | None = None,
    max_ts: int | None = None,
    limit: int = _TRADES_PAGE_LIMIT,
    client: httpx.Client | None = None,
    sleep_between: float | None = None,
    max_pages: int = _MAX_TRADES_PAGES,
) -> list[dict[str, Any]]:
    """Fetch historical fills for ``ticker``, paginated via cursor.

    The cursor field is documented but its exact name varies — we
    forward whatever key the upstream returned. When the cursor is
    empty or missing, pagination terminates.

    Args:
        ticker: Full market ticker.
        min_ts, max_ts: Optional UNIX timestamp bounds.
        limit: Per-page count (default 1000, Kalshi's documented max).
        client: Optional ``httpx.Client``.
        sleep_between: Per-request polite sleep override.
        max_pages: Safety cap on total pages walked. Raises
            :class:`RuntimeError` if exceeded.

    Returns:
        List of trade dicts.
    """
    path = "/markets/trades"
    out: list[dict[str, Any]] = []
    cursor: str | None = None
    pages = 0
    while True:
        params: dict[str, Any] = {"ticker": ticker, "limit": limit}
        if min_ts is not None:
            params["min_ts"] = min_ts
        if max_ts is not None:
            params["max_ts"] = max_ts
        if cursor:
            params["cursor"] = cursor
        payload = _request(path, params=params, client=client, sleep_between=sleep_between)
        trades = payload.get("trades") if isinstance(payload, dict) else None
        if trades:
            out.extend(trades)
        cursor = (
            payload.get("cursor") if isinstance(payload, dict) else None  # type: ignore[arg-type]
        )
        pages += 1
        if not cursor or not trades:
            break
        if pages >= max_pages:
            raise RuntimeError(
                f"kalshi fetch_trades({ticker!r}) exceeded max_pages={max_pages}; "
                "narrow the window via min_ts/max_ts or raise the cap"
            )
    return out


def fetch_orderbook(
    ticker: str,
    *,
    depth: int = 50,
    client: httpx.Client | None = None,
    sleep_between: float | None = None,
) -> dict[str, Any]:
    """Fetch current orderbook snapshot for ``ticker``."""
    if depth < 1 or depth > 1000:
        raise ValueError(f"depth out of range [1, 1000]: {depth}")
    path = f"/markets/{ticker}/orderbook"
    payload = _request(
        path, params={"depth": depth}, client=client, sleep_between=sleep_between
    )
    if not isinstance(payload, dict):
        raise RuntimeError(
            f"kalshi orderbook for {ticker!r}: expected dict payload, got {type(payload).__name__}"
        )
    return payload


__all__ = [
    "KALSHI_API_BASE",
    "fetch_candlesticks",
    "fetch_orderbook",
    "fetch_trades",
]

"""Kalshi trade-history public surface — Phase 9 (TRADES-01..03).

Three read-only entry points over the public Kalshi REST API:

- :func:`candles` — OHLCV bars at a chosen interval.
- :func:`fills` — historical trade prints, paginated by cursor.
- :func:`orderbook` — current book snapshot.

All three return :class:`pandas.DataFrame` with a ``source="kalshi"``
column preserved per row so downstream `pd.concat` / `merge` keep
source-identity intact (the v0.1.0 invariant).

No authentication required; no Kalshi API key needed. Calls go to the
documented public endpoints under ``api.elections.kalshi.com``.

Lives at flat module name :mod:`tradewinds.markets.kalshi_trades`
(rather than a hypothetical ``tradewinds.markets.kalshi.trades``
subpackage) because the existing ``tradewinds.markets.catalog.kalshi_*``
modules already use the ``catalog/`` namespace for contract metadata;
trades data is a separate flat module to avoid restructuring the
catalog package layout. Phase 10 may revisit the namespace if a
top-level ``tradewinds.markets.kalshi`` aggregate becomes desirable.
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
    import httpx
    import pandas as pd


__all__ = ["INTERVALS", "candles", "fills", "orderbook"]


_SOURCE: str = "kalshi"


#: Supported candle intervals → seconds. Kalshi documents 1-minute,
#: 1-hour, and 1-day candles; the seconds → minutes conversion at the
#: call site reflects Kalshi's ``period_interval`` being in minutes.
INTERVALS: dict[str, int] = {"1m": 60, "1h": 3600, "1d": 86400}


def _require_pandas() -> Any:
    """Lazy-import pandas with an actionable install hint on miss."""
    try:
        import pandas as _pandas
    except ImportError as exc:
        from tradewinds.core.exceptions import SourceUnavailableError

        raise SourceUnavailableError(
            "tradewinds.markets.kalshi_trades requires pandas. Install with: "
            "pip install tradewinds-markets[trades]",
            source=_SOURCE,
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
    client: httpx.Client | None = None,
    sleep_between: float | None = None,
) -> pd.DataFrame:
    """OHLCV candles for ``ticker`` between ``from_`` and ``to``.

    Args:
        ticker: Full Kalshi market ticker (e.g. ``"KXHIGHNY-25MAY26-T79"``).
        interval: Candle granularity — one of :data:`INTERVALS` keys
            (``"1m"``, ``"1h"``, ``"1d"``).
        from_, to: tz-aware UTC datetimes bounding the window.
        client: Optional shared ``httpx.Client``.
        sleep_between: Per-request polite-sleep override (tests pass 0).

    Returns:
        ``pd.DataFrame`` with columns:

        - ``ts`` (datetime UTC): end-of-period timestamp.
        - ``open`` / ``high`` / ``low`` / ``close`` (float | None): OHLC cents.
        - ``volume`` (int | None): contracts traded in the bucket.
        - ``open_interest`` (int | None): contracts outstanding at bucket end.
        - ``source`` (str): always ``"kalshi"``.

    Raises:
        TypeError: ``from_``/``to`` not tz-aware datetimes.
        ValueError: ``from_ >= to`` OR ``interval`` not in :data:`INTERVALS`.
    """
    pd = _require_pandas()
    _validate_aware(from_, "from_")
    _validate_aware(to, "to")
    if from_ >= to:
        raise ValueError(f"from_ ({from_.isoformat()}) must be < to ({to.isoformat()})")
    if interval not in INTERVALS:
        raise ValueError(
            f"interval must be one of {sorted(INTERVALS)}; got {interval!r}"
        )
    period_interval_minutes = INTERVALS[interval] // 60
    raw = fetch_candlesticks(
        ticker,
        start_ts=int(from_.timestamp()),
        end_ts=int(to.timestamp()),
        period_interval=period_interval_minutes,
        client=client,
        sleep_between=sleep_between,
    )
    rows: list[dict[str, Any]] = []
    for c in raw:
        price = c.get("price") or {}
        ts_value = c.get("end_period_ts")
        ts = (
            datetime.fromtimestamp(int(ts_value), tz=UTC)
            if isinstance(ts_value, (int, float))
            else None
        )
        rows.append(
            {
                "ts": ts,
                "open": _maybe_float(price.get("open")),
                "high": _maybe_float(price.get("high")),
                "low": _maybe_float(price.get("low")),
                "close": _maybe_float(price.get("close")),
                "volume": _maybe_int(c.get("volume")),
                "open_interest": _maybe_int(c.get("open_interest")),
                "source": _SOURCE,
            }
        )
    df = pd.DataFrame(
        rows,
        columns=[
            "ts",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "open_interest",
            "source",
        ],
    )
    df.attrs["source"] = _SOURCE
    df.attrs["ticker"] = ticker
    df.attrs["interval"] = interval
    df.attrs["retrieved_at"] = datetime.now(UTC)
    return df


def fills(
    ticker: str,
    *,
    since: datetime | None = None,
    until: datetime | None = None,
    client: httpx.Client | None = None,
    sleep_between: float | None = None,
    max_pages: int = 10_000,
) -> pd.DataFrame:
    """Historical fills for ``ticker``, paginated until cursor exhausts.

    Args:
        ticker: Full Kalshi market ticker.
        since, until: Optional tz-aware UTC datetime bounds.
        client: Optional shared ``httpx.Client``.
        sleep_between: Per-request polite-sleep override.
        max_pages: Safety cap on cursor pagination (defaults to 10k pages
            = 10M trades). Raises ``RuntimeError`` if exceeded.

    Returns:
        DataFrame with columns:

        - ``trade_id`` (str | None)
        - ``ts`` (datetime UTC | None)
        - ``yes_price`` / ``no_price`` (float | None)
        - ``count`` (int | None): contracts in this fill.
        - ``taker_side`` (str | None): ``"yes"`` / ``"no"`` / None.
        - ``source`` (str): always ``"kalshi"``.

    Raises:
        TypeError: ``since`` / ``until`` not tz-aware datetimes when set.
        ValueError: ``since >= until`` when both set.
    """
    pd = _require_pandas()
    if since is not None:
        _validate_aware(since, "since")
    if until is not None:
        _validate_aware(until, "until")
    if since is not None and until is not None and since >= until:
        raise ValueError(
            f"since ({since.isoformat()}) must be < until ({until.isoformat()})"
        )
    min_ts = int(since.timestamp()) if since is not None else None
    max_ts = int(until.timestamp()) if until is not None else None
    raw = fetch_trades(
        ticker,
        min_ts=min_ts,
        max_ts=max_ts,
        client=client,
        sleep_between=sleep_between,
        max_pages=max_pages,
    )
    rows: list[dict[str, Any]] = []
    for t in raw:
        ts_value = t.get("created_time")
        ts: datetime | None = None
        if isinstance(ts_value, (int, float)):
            ts = datetime.fromtimestamp(int(ts_value), tz=UTC)
        elif isinstance(ts_value, str):
            try:
                ts = datetime.fromisoformat(ts_value.replace("Z", "+00:00"))
            except ValueError:
                ts = None
        rows.append(
            {
                "trade_id": t.get("trade_id"),
                "ts": ts,
                "yes_price": _maybe_float(t.get("yes_price")),
                "no_price": _maybe_float(t.get("no_price")),
                "count": _maybe_int(t.get("count")),
                "taker_side": t.get("taker_side"),
                "source": _SOURCE,
            }
        )
    df = pd.DataFrame(
        rows,
        columns=[
            "trade_id",
            "ts",
            "yes_price",
            "no_price",
            "count",
            "taker_side",
            "source",
        ],
    )
    df.attrs["source"] = _SOURCE
    df.attrs["ticker"] = ticker
    df.attrs["retrieved_at"] = datetime.now(UTC)
    return df


def orderbook(
    ticker: str,
    *,
    depth: int = 50,
    client: httpx.Client | None = None,
    sleep_between: float | None = None,
) -> pd.DataFrame:
    """Current orderbook snapshot for ``ticker``.

    Args:
        ticker: Full Kalshi market ticker.
        depth: Number of price levels per side (default 50; Kalshi
            documented max varies — capped at 1000 in the client).
        client: Optional shared ``httpx.Client``.
        sleep_between: Per-request polite-sleep override.

    Returns:
        DataFrame, one row per (side, price level):

        - ``side`` (str): ``"yes"`` or ``"no"``.
        - ``price`` (float | None): price in cents.
        - ``size`` (int | None): contracts at this level.
        - ``source`` (str): always ``"kalshi"``.

        Snapshot timestamp lives in ``df.attrs["snapshot_at"]`` (no
        per-row column because every row has the same wall-clock instant).
    """
    pd = _require_pandas()
    payload = fetch_orderbook(
        ticker, depth=depth, client=client, sleep_between=sleep_between
    )
    book = payload.get("orderbook") or {}
    rows: list[dict[str, Any]] = []
    for side in ("yes", "no"):
        levels = book.get(side) or []
        for level in levels:
            # Kalshi documents [price, size] tuples. Tolerate dict form too.
            if isinstance(level, (list, tuple)) and len(level) >= 2:
                price_v, size_v = level[0], level[1]
            elif isinstance(level, dict):
                price_v = level.get("price")
                size_v = level.get("size") or level.get("contracts")
            else:
                continue
            rows.append(
                {
                    "side": side,
                    "price": _maybe_float(price_v),
                    "size": _maybe_int(size_v),
                    "source": _SOURCE,
                }
            )
    df = pd.DataFrame(rows, columns=["side", "price", "size", "source"])
    df.attrs["source"] = _SOURCE
    df.attrs["ticker"] = ticker
    df.attrs["snapshot_at"] = datetime.now(UTC)
    return df


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------
def _validate_aware(dt: datetime, name: str) -> None:
    if not isinstance(dt, datetime):
        raise TypeError(
            f"{name} must be a datetime instance; got {type(dt).__name__}"
        )
    if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
        raise TypeError(
            f"{name} must be a tz-aware UTC datetime; got naive {dt!r}"
        )


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

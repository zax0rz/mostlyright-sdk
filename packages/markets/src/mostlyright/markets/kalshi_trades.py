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

Lives at flat module name :mod:`mostlyright.markets.kalshi_trades`
(rather than a hypothetical ``mostlyright.markets.kalshi.trades``
subpackage) because the existing ``mostlyright.markets.catalog.kalshi_*``
modules already use the ``catalog/`` namespace for contract metadata;
trades data is a separate flat module to avoid restructuring the
catalog package layout. Phase 10 may revisit the namespace if a
top-level ``mostlyright.markets.kalshi`` aggregate becomes desirable.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from mostlyright.markets._kalshi_client import (
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
        from mostlyright.core.exceptions import SourceUnavailableError

        raise SourceUnavailableError(
            "mostlyright.markets.kalshi_trades requires pandas. Install with: "
            "pip install mostlyright-markets[trades]",
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
        - ``open`` / ``high`` / ``low`` / ``close`` (float | None): OHLC in
          **cents** (0.0–100.0, subpenny precision preserved). Conversion
          from the Kalshi FixedPointDollars wire format (e.g. ``"0.5600"``)
          is ``cents = float(api_string) * 100`` per the canonical
          ``packages/core/.../specs/candle.json`` contract.
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
        raise ValueError(f"interval must be one of {sorted(INTERVALS)}; got {interval!r}")
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
        # Kalshi API (March 2026 migration) returns FixedPointDollars strings
        # (e.g. "0.5600") for prices and FixedPoint integer strings for
        # volume / open_interest (`*_fp` suffix). Canonical storage per
        # `packages/core/src/mostlyright/_internal/specs/candle.json` is cents
        # in [0, 100] (float — subpenny preserved). Conversion:
        #   cents = float(api_string) * 100
        # Legacy integer-cents fields (`open`/`high`/`low`/`close`/`volume`/
        # `open_interest` without suffix) are accepted as a fallback so a
        # future Kalshi rollback or alternate endpoint shape stays parseable.
        rows.append(
            {
                "ts": ts,
                "open": _pick_price(price, "open"),
                "high": _pick_price(price, "high"),
                "low": _pick_price(price, "low"),
                "close": _pick_price(price, "close"),
                "volume": _pick_fp(c, "volume"),
                "open_interest": _pick_fp(c, "open_interest"),
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
        - ``yes_price`` / ``no_price`` (float | None): cents (0.0–100.0,
          subpenny precision). Converted from Kalshi's
          ``yes_price_dollars``/``no_price_dollars`` FixedPointDollars
          strings via ``cents = float(s) * 100``.
        - ``count`` (int | None): contracts in this fill. Read from
          ``count_fp`` (Kalshi's FixedPoint integer string) and converted
          to int.
        - ``taker_side`` (str | None): ``"yes"`` / ``"no"`` / None. Read
          from Kalshi's ``taker_outcome_side``.
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
        raise ValueError(f"since ({since.isoformat()}) must be < until ({until.isoformat()})")
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
        # Real Kalshi /markets/trades returns FixedPointDollars strings:
        # yes_price_dollars / no_price_dollars / count_fp / taker_outcome_side.
        # Legacy unsuffixed names accepted as a fallback.
        taker_side = (
            t.get("taker_outcome_side") if "taker_outcome_side" in t else t.get("taker_side")
        )
        rows.append(
            {
                "trade_id": t.get("trade_id"),
                "ts": ts,
                "yes_price": _pick_price(t, "yes_price"),
                "no_price": _pick_price(t, "no_price"),
                "count": _pick_fp(t, "count"),
                "taker_side": taker_side,
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
        - ``price`` (float | None): price in cents (0.0–100.0). Converted
          from Kalshi's ``orderbook_fp.{yes_dollars,no_dollars}`` levels
          (each level is ``[price_dollar_string, count_fp_string]``) via
          ``cents = float(price_dollar_string) * 100``.
        - ``size`` (int | None): contracts at this level (parsed from
          ``count_fp_string``).
        - ``source`` (str): always ``"kalshi"``.

        Snapshot timestamp lives in ``df.attrs["snapshot_at"]`` (no
        per-row column because every row has the same wall-clock instant).
    """
    pd = _require_pandas()
    payload = fetch_orderbook(ticker, depth=depth, client=client, sleep_between=sleep_between)
    # Kalshi API (March 2026 migration) returns `orderbook_fp` with
    # `yes_dollars` / `no_dollars` arrays of [price_dollar_string,
    # count_fp_string]. Legacy `orderbook.yes` / `.no` accepted as fallback
    # for older endpoints or recorded fixtures with the prior shape.
    if "orderbook_fp" in payload:
        book = payload.get("orderbook_fp") or {}
        keys = {"yes": "yes_dollars", "no": "no_dollars"}
        fp_form = True
    else:
        book = payload.get("orderbook") or {}
        keys = {"yes": "yes", "no": "no"}
        fp_form = False
    rows: list[dict[str, Any]] = []
    for side, key in keys.items():
        levels = book.get(key) or []
        for level in levels:
            # [price, size] tuples (legacy: ints; new fp form: dollar
            # strings + fp integer strings). Dict form also tolerated for
            # backward compatibility with mock fixtures.
            if isinstance(level, (list, tuple)) and len(level) >= 2:
                price_v, size_v = level[0], level[1]
            elif isinstance(level, dict):
                price_v = level.get("price")
                size_v = level.get("size") or level.get("contracts")
            else:
                continue
            if fp_form:
                price_cents = _dollars_to_cents(price_v)
                size_int = _fp_string_to_int(size_v)
            else:
                price_cents = _maybe_float(price_v)
                size_int = _maybe_int(size_v)
            rows.append(
                {
                    "side": side,
                    "price": price_cents,
                    "size": size_int,
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
        raise TypeError(f"{name} must be a datetime instance; got {type(dt).__name__}")
    if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
        raise TypeError(f"{name} must be a tz-aware UTC datetime; got naive {dt!r}")


def _maybe_float(v: Any) -> float | None:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _dollars_to_cents(v: Any) -> float | None:
    """Parse a Kalshi FixedPointDollars string (e.g. ``"0.5600"``) → cents.

    Canonical conversion per
    ``packages/core/src/mostlyright/_internal/specs/candle.json``:
    ``cents = float(dollars_string) * 100``. Subpenny precision preserved
    (e.g. ``"0.567"`` → 56.7).
    """
    f = _maybe_float(v)
    if f is None:
        return None
    return f * 100.0


def _fp_string_to_int(v: Any) -> int | None:
    """Parse a Kalshi FixedPoint integer string (volume_fp / count_fp /
    open_interest_fp) to int. Tolerates trailing decimals like ``"100.00"``.
    """
    if v is None:
        return None
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return None


def _pick_price(d: dict[str, Any], base: str) -> float | None:
    """Read ``{base}_dollars`` and convert to cents; fall back to legacy ``base``."""
    dollars_key = f"{base}_dollars"
    if dollars_key in d:
        return _dollars_to_cents(d.get(dollars_key))
    return _maybe_float(d.get(base))


def _pick_fp(d: dict[str, Any], base: str) -> int | None:
    """Read ``{base}_fp`` and convert to int; fall back to legacy ``base``."""
    fp_key = f"{base}_fp"
    if fp_key in d:
        return _fp_string_to_int(d.get(fp_key))
    return _maybe_int(d.get(base))


def _maybe_int(v: Any) -> int | None:
    if v is None:
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None

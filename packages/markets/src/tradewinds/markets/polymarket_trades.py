"""Polymarket trade-history public surface — Phase 9 (TRADES-04..05).

Two read-only entry points over the public Polymarket Gamma API:

- :func:`history` — price + volume timeseries for a single market.
- :func:`snapshot` — current state for an event (one row per outcome).

Both return :class:`pandas.DataFrame` with ``source="polymarket.gamma"``
per row so downstream `pd.concat` / `merge` keep source-identity intact.

The trades surface intentionally lives at the flat module name
:mod:`tradewinds.markets.polymarket_trades` (rather than under a
hypothetical ``tradewinds.markets.polymarket.trades`` subpackage)
because converting the existing ``polymarket.py`` module into a package
would break the dozen-plus call sites (including ``test_polymarket_real.py``
and ``test_cross_issuer_station_identity.py``) that import private
names like ``_derive_city``. Flat module + namespaced sibling is the
minimum-invasive shape for Phase 9; Phase 10 can revisit if the
namespace becomes load-bearing.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from tradewinds.markets._polymarket_client import fetch_event_by_id, get_json

if TYPE_CHECKING:
    import httpx
    import pandas as pd


__all__ = ["history", "snapshot"]


_SOURCE: str = "polymarket.gamma"


def _require_pandas() -> Any:
    """Lazy-import pandas with an actionable install hint on miss."""
    try:
        import pandas as _pandas
    except ImportError as exc:
        from tradewinds.core.exceptions import SourceUnavailableError

        raise SourceUnavailableError(
            "tradewinds.markets.polymarket_trades requires pandas. Install with: "
            "pip install tradewinds-markets[trades]",
            source=_SOURCE,
            retryable=False,
            underlying=str(exc),
        ) from None
    return _pandas


def history(
    market_id: str,
    *,
    from_: datetime,
    to: datetime,
    fidelity_minutes: int = 60,
    client: httpx.Client | None = None,
    sleep_between: float | None = None,
) -> pd.DataFrame:
    """Market price/volume timeseries from Gamma ``/prices-history``.

    Polymarket reports time-bucketed last-price + volume; there is no
    separate H/L/C per bucket (the order book is too thin in many
    markets for OHLC to be meaningful at sub-day granularity).

    Args:
        market_id: Polymarket market id (numeric or condition-id form).
        from_, to: tz-aware UTC datetimes bounding the window.
        fidelity_minutes: Bucket size in minutes (default 60 = hourly).
            Polymarket documents minimum 1; values that don't divide
            the window cleanly are tolerated upstream.
        client: Optional shared ``httpx.Client``.
        sleep_between: Per-request polite-sleep override.

    Returns:
        DataFrame with columns:

        - ``ts`` (datetime UTC | None): bucket end timestamp.
        - ``price`` (float | None): last-traded price [0, 1] for YES.
        - ``volume`` (float | None): volume in the bucket.
        - ``source`` (str): always ``"polymarket.gamma"``.

    Raises:
        TypeError: ``from_``/``to`` not tz-aware datetimes.
        ValueError: ``from_ >= to`` or ``fidelity_minutes < 1``.
        ValueError: ``market_id`` not a non-empty str.
    """
    pd = _require_pandas()
    if not isinstance(market_id, str) or not market_id:
        raise ValueError(f"market_id must be a non-empty str; got {market_id!r}")
    _validate_aware(from_, "from_")
    _validate_aware(to, "to")
    if from_ >= to:
        raise ValueError(f"from_ ({from_.isoformat()}) must be < to ({to.isoformat()})")
    if fidelity_minutes < 1:
        raise ValueError(f"fidelity_minutes must be >= 1; got {fidelity_minutes}")

    raw = get_json(
        "/prices-history",
        params={
            "market": market_id,
            "startTs": int(from_.timestamp()),
            "endTs": int(to.timestamp()),
            "fidelity": fidelity_minutes,
        },
        client=client,
        sleep_between=0 if sleep_between is None else sleep_between,
    )

    # Gamma typically returns {"history": [{"t": int, "p": float}, ...]}.
    # Defensively unwrap a bare list too (some endpoints flip shapes).
    points: list[Any]
    if isinstance(raw, dict):
        points = raw.get("history") or []
    elif isinstance(raw, list):
        points = raw
    else:
        points = []

    rows: list[dict[str, Any]] = []
    for p in points:
        if not isinstance(p, dict):
            continue
        ts_value = p.get("t")
        ts = (
            datetime.fromtimestamp(int(ts_value), tz=UTC)
            if isinstance(ts_value, (int, float))
            else None
        )
        rows.append(
            {
                "ts": ts,
                "price": _maybe_float(p.get("p") if "p" in p else p.get("price")),
                "volume": _maybe_float(p.get("v") if "v" in p else p.get("volume")),
                "source": _SOURCE,
            }
        )
    df = pd.DataFrame(rows, columns=["ts", "price", "volume", "source"])
    df.attrs["source"] = _SOURCE
    df.attrs["market_id"] = market_id
    df.attrs["fidelity_minutes"] = fidelity_minutes
    df.attrs["retrieved_at"] = datetime.now(UTC)
    return df


def snapshot(
    event_id: str,
    *,
    client: httpx.Client | None = None,
) -> pd.DataFrame:
    """Current state for ``event_id`` from Gamma ``/events/{id}``.

    Args:
        event_id: Polymarket event id.
        client: Optional shared ``httpx.Client``.

    Returns:
        DataFrame, one row per outcome (across all markets in the event):

        - ``market_id`` (str | None)
        - ``outcome`` (str): e.g. ``"Yes"`` / ``"No"`` / candidate name.
        - ``last_price`` (float | None): in [0, 1].
        - ``volume`` (float | None): per-market lifetime volume.
        - ``liquidity`` (float | None): order-book liquidity proxy.
        - ``source`` (str): always ``"polymarket.gamma"``.

        ``snapshot_at`` lives in ``df.attrs``.

    Raises:
        ValueError: ``event_id`` not a non-empty str OR upstream payload
            is not a dict.
    """
    pd = _require_pandas()
    if not isinstance(event_id, str) or not event_id:
        raise ValueError(f"event_id must be a non-empty str; got {event_id!r}")
    event = fetch_event_by_id(event_id, client=client)
    if not isinstance(event, dict):
        raise ValueError(
            f"polymarket snapshot: bad event payload type for {event_id!r}; "
            f"expected dict, got {type(event).__name__}"
        )
    markets = event.get("markets") or []
    rows: list[dict[str, Any]] = []
    for m in markets:
        if not isinstance(m, dict):
            continue
        outcomes = _coerce_string_list(m.get("outcomes"))
        prices = _coerce_string_list(m.get("outcomePrices"))
        volume = _maybe_float(m.get("volume"))
        liquidity = _maybe_float(m.get("liquidity"))
        market_id_raw = m.get("id")
        market_id_str = str(market_id_raw) if market_id_raw is not None else None
        for i, outcome in enumerate(outcomes):
            price_str = prices[i] if i < len(prices) else None
            rows.append(
                {
                    "market_id": market_id_str,
                    "outcome": outcome,
                    "last_price": _maybe_float(price_str),
                    "volume": volume,
                    "liquidity": liquidity,
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


def _coerce_string_list(v: Any) -> list[str]:
    """Coerce Polymarket's polymorphic list field to a list of strings.

    Gamma sometimes returns ``outcomes`` / ``outcomePrices`` as JSON
    strings (`'["Yes", "No"]'`) and sometimes as native lists.
    Defensive parse covers both.
    """
    if v is None:
        return []
    if isinstance(v, list):
        return [str(x) for x in v]
    if isinstance(v, str):
        # JSON-encoded list
        try:
            import json as _json

            parsed = _json.loads(v)
        except (ValueError, TypeError):
            return []
        if isinstance(parsed, list):
            return [str(x) for x in parsed]
    return []

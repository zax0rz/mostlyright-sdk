"""Polymarket trade-history public surface — Phase 9 (TRADES-04..05).

Two read-only entry points over the public Polymarket Gamma API:

- :func:`history` — price + volume timeseries for a single market.
- :func:`snapshot` — current state for an event (one row per outcome).

Both return :class:`pandas.DataFrame` with ``source="polymarket.gamma"``
per row so downstream `pd.concat` / `merge` keep source-identity intact.

The trades surface intentionally lives at the flat module name
:mod:`mostlyright.markets.polymarket_trades` (rather than under a
hypothetical ``mostlyright.markets.polymarket.trades`` subpackage)
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

from mostlyright.markets._polymarket_client import (
    CLOB_API_BASE,
    get_json,
)

if TYPE_CHECKING:
    import httpx
    import pandas as pd


__all__ = ["history", "snapshot"]


#: Per-row source label for the snapshot endpoint (Gamma-hosted).
_SOURCE_SNAPSHOT: str = "polymarket.gamma"

#: Per-row source label for the history endpoint (CLOB-hosted; distinct
#: from snapshot because the two endpoints live on different hosts).
_SOURCE_HISTORY: str = "polymarket.clob"


def _require_pandas(source_label: str = "polymarket") -> Any:
    """Lazy-import pandas with an actionable install hint on miss."""
    try:
        import pandas as _pandas
    except ImportError as exc:
        from mostlyright.core.exceptions import SourceUnavailableError

        raise SourceUnavailableError(
            "mostlyright.markets.polymarket_trades requires pandas. Install with: "
            "pip install mostlyright-markets[trades]",
            source=source_label,
            retryable=False,
            underlying=str(exc),
        ) from None
    return _pandas


def history(
    token_id: str,
    *,
    from_: datetime,
    to: datetime,
    fidelity_minutes: int = 60,
    client: httpx.Client | None = None,
    sleep_between: float | None = None,
) -> pd.DataFrame:
    """Market price/volume timeseries from Polymarket CLOB ``/prices-history``.

    Architect iter-1 CRITICAL fix: ``/prices-history`` lives on the **CLOB**
    host (``clob.polymarket.com``), NOT Gamma. The ``market`` query
    parameter is the CLOB token id (ERC-1155 asset id, one per YES/NO
    outcome), retrievable from Gamma's ``/markets/slug/{slug}`` response as
    ``clobTokenIds``. It is NOT a Gamma market/condition/event id.

    Polymarket reports time-bucketed last-price + volume; there is no
    separate H/L/C per bucket (the order book is too thin in many
    markets for OHLC to be meaningful at sub-day granularity).

    Args:
        token_id: Polymarket CLOB token id (asset id for a single
            outcome — YES or NO; pick the side you want). NOT a Gamma
            market/condition/event id.
        from_, to: tz-aware UTC datetimes bounding the window.
        fidelity_minutes: Bucket size in minutes (default 60 = hourly).
            Polymarket documents minimum 1.
        client: Optional shared ``httpx.Client``.
        sleep_between: Per-request polite-sleep override.

    Returns:
        DataFrame with columns:

        - ``ts`` (datetime UTC | None): bucket end timestamp.
        - ``price`` (float | None): last-traded price in [0, 1] for the
          requested outcome token.
        - ``volume`` (float | None): volume in the bucket.
        - ``source`` (str): always ``"polymarket.clob"``.

        ``df.attrs["token_id"]`` echoes the input for downstream attribution.

    Raises:
        TypeError: ``from_``/``to`` not tz-aware datetimes.
        ValueError: ``from_ >= to`` or ``fidelity_minutes < 1``.
        ValueError: ``token_id`` not a non-empty str.
    """
    pd = _require_pandas(source_label=_SOURCE_HISTORY)
    if not isinstance(token_id, str) or not token_id:
        raise ValueError(f"token_id must be a non-empty str; got {token_id!r}")
    _validate_aware(from_, "from_")
    _validate_aware(to, "to")
    if from_ >= to:
        raise ValueError(f"from_ ({from_.isoformat()}) must be < to ({to.isoformat()})")
    if fidelity_minutes < 1:
        raise ValueError(f"fidelity_minutes must be >= 1; got {fidelity_minutes}")

    # Iter-3 codex HIGH: passing `sleep_between=0` whenever the caller
    # omits it would force CLOB calls to run unthrottled by default,
    # bypassing the 200ms polite floor documented in
    # `.planning/research/MARKETS-RATE-LIMITS.md`. Tests pass `0`
    # explicitly; production callers should inherit `get_json`'s default
    # by passing `None` through (when caller omitted) or the explicit
    # override (when caller passed `0` for tests).
    get_kwargs: dict[str, Any] = {
        "params": {
            "market": token_id,
            "startTs": int(from_.timestamp()),
            "endTs": int(to.timestamp()),
            "fidelity": fidelity_minutes,
        },
        "client": client,
        "base_url": CLOB_API_BASE,
    }
    if sleep_between is not None:
        get_kwargs["sleep_between"] = sleep_between
    raw = get_json("/prices-history", **get_kwargs)

    # Polymarket CLOB typically returns {"history": [{"t": int, "p": float}, ...]}.
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
                "source": _SOURCE_HISTORY,
            }
        )
    df = pd.DataFrame(rows, columns=["ts", "price", "volume", "source"])
    df.attrs["source"] = _SOURCE_HISTORY
    df.attrs["token_id"] = token_id
    df.attrs["fidelity_minutes"] = fidelity_minutes
    df.attrs["retrieved_at"] = datetime.now(UTC)
    return df


def snapshot(
    event_id: str,
    *,
    client: httpx.Client | None = None,
    sleep_between: float | None = None,
) -> pd.DataFrame:
    """Current state for ``event_id`` from Gamma ``/events/{id}``.

    Args:
        event_id: Polymarket event id.
        client: Optional shared ``httpx.Client``.
        sleep_between: Per-request polite-sleep override. Default applies
            ``get_json``'s 0.2s floor (the Gamma rate-limit-floor
            documented in ``.planning/research/MARKETS-RATE-LIMITS.md``).
            Iter-4 codex HIGH: the previous implementation routed through
            ``fetch_event_by_id`` which has no sleep path — snapshot in a
            loop bypassed the polite floor entirely. Now routes through
            ``get_json`` so the default sleep applies.

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
    get_kwargs: dict[str, Any] = {
        "params": None,
        "client": client,
        # base_url defaults to GAMMA_API_BASE in get_json.
    }
    if sleep_between is not None:
        get_kwargs["sleep_between"] = sleep_between
    event = get_json(f"/events/{event_id}", **get_kwargs)
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
                    "source": _SOURCE_SNAPSHOT,
                }
            )
    df = pd.DataFrame(
        rows,
        columns=["market_id", "outcome", "last_price", "volume", "liquidity", "source"],
    )
    df.attrs["source"] = _SOURCE_SNAPSHOT
    df.attrs["event_id"] = event_id
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

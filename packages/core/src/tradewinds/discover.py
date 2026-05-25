"""Phase 10 — ``discover()`` ergonomic surface.

Pre-research lookup that shows quants which station settles which
issuer's market for a given city. Use this BEFORE picking the right
selector for ``research()`` — especially for cross-issuer cities like
NYC where Kalshi settles against KNYC and Polymarket against KLGA.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import pandas as pd


def discover(*, city: str) -> "pd.DataFrame":
    """Return per-station discovery table for ``city``.

    Each row shows one settlement station + the list of ``"<issuer>:<ticker>"``
    markers that resolve against it. Stations in the per-city Polymarket
    denylist also appear (with empty ``settles_for``) so quants see the
    full station neighborhood before deciding whether to use
    ``station_override=``.

    Args:
        city: city slug (``"NYC"`` for Kalshi, ``"nyc"`` for Polymarket;
            both forms are normalized).

    Returns:
        ``pd.DataFrame`` with columns:

        - ``city`` (str): the input city, echoed.
        - ``station`` (str): 4-char K-prefix ICAO.
        - ``settles_for`` (list[str]): ``["kalshi:NYC"]`` / ``["polymarket:nyc"]``
          / ``[]`` (denylist backstop).

    Raises:
        ValueError: city not in either catalog.
        SourceUnavailableError: pandas not installed.
    """
    if not isinstance(city, str) or not city:
        raise ValueError(f"city must be a non-empty str; got {city!r}")
    try:
        import pandas as _pandas
    except ImportError as exc:
        from tradewinds.core.exceptions import SourceUnavailableError

        raise SourceUnavailableError(
            "tradewinds.discover requires pandas. Install with: "
            "pip install tradewinds[parquet]",
            source="discover",
            retryable=False,
            underlying=str(exc),
        ) from None

    # Iter-1 codex HIGH: discover() is exported from the `tradewinds`
    # (core) package but the resolver depends on `tradewinds.markets`,
    # which is shipped as a separate distribution (`tradewinds-markets`).
    # A clean install of `tradewinds` alone would fail at this point.
    # Surface a clear SourceUnavailableError pointing the operator at
    # the install hint rather than letting an ImportError bubble up.
    try:
        from tradewinds._compose import annotate_settles_for, resolve_city
    except ImportError as exc:
        from tradewinds.core.exceptions import SourceUnavailableError

        raise SourceUnavailableError(
            "tradewinds.discover requires the sibling `tradewinds-markets` "
            "distribution (for the Kalshi + Polymarket city catalogs). "
            "Install with: pip install tradewinds-markets",
            source="discover",
            retryable=False,
            underlying=str(exc),
        ) from None

    stations = resolve_city(city)
    rows: list[dict[str, Any]] = [
        {
            "city": city,
            "station": station,
            "settles_for": annotate_settles_for(station, city),
        }
        for station in stations
    ]
    df = _pandas.DataFrame(rows, columns=["city", "station", "settles_for"])
    df.attrs["city"] = city
    df.attrs["source"] = "discover"
    return df


__all__ = ["discover"]

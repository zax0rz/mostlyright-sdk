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

    # Iter-1 + iter-2 codex HIGH: discover() is exported from the
    # `tradewinds` (core) package but the resolver depends on
    # `tradewinds.markets`, which is shipped as a separate distribution
    # (`tradewinds-markets`). The `_compose` module itself imports
    # cleanly (the markets imports inside it are LAZY at call time), so
    # wrapping only the top-level `from tradewinds._compose import ...`
    # (the iter-1 fix) was not enough — the actual `ModuleNotFoundError`
    # fires inside `resolve_city()` / `annotate_settles_for()` when they
    # call `from tradewinds.markets... import ...`. The iter-2 fix
    # wraps the resolver calls below as well, converting the lazy
    # ImportError into a friendly SourceUnavailableError with the
    # canonical install hint.
    from tradewinds._compose import annotate_settles_for, resolve_city

    try:
        stations = resolve_city(city)
    except ModuleNotFoundError as exc:
        if "tradewinds.markets" in (exc.name or ""):
            from tradewinds.core.exceptions import SourceUnavailableError

            raise SourceUnavailableError(
                "tradewinds.discover requires the sibling `tradewinds-markets` "
                "distribution (for the Kalshi + Polymarket city catalogs). "
                "Install with: pip install tradewinds-markets",
                source="discover",
                retryable=False,
                underlying=str(exc),
            ) from None
        raise

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

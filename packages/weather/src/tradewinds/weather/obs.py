"""tradewinds.weather.obs — public surface for observation aggregates.

Smart-routes between three ingest strategies:

- **exact_window**: bypass year-normalization in IEM, day-granular URL params,
  ≤2 MB cold for 1mo KNYC. Best for one-off backtest replays.
- **warm_cache**: current ``research()`` orchestration with year-aligned cache
  hit-rate optimization. Best for repeated queries across overlapping windows.
- **hosted**: precomputed-API seam (gated by ``TW_HOSTED_URL``); deferred to v0.2.x.

The default ``strategy="auto"`` selects between these based on window size,
cache warmth, and env-var presence. PLAN-07-04 fills in the dispatch body.
The default ships as ``"auto"`` from PLAN-02 onward and never changes (B-6 —
no public-API churn between PRs).

See ``docs/ingest-strategies.md`` for the decision tree.
"""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    import pandas as pd

Source = Literal["iem", "ghcnh", "awc"]
Strategy = Literal["auto", "exact_window", "warm_cache", "hosted"]

_VALID_SOURCES: frozenset[str] = frozenset({"iem", "ghcnh", "awc"})
_VALID_STRATEGIES: frozenset[str] = frozenset(
    {"auto", "exact_window", "warm_cache", "hosted"}
)


def obs(
    station: str,
    start: str,
    end: str,
    *,
    source: Source | None = None,
    strategy: Strategy = "auto",
    as_dataframe: bool = True,
) -> "pd.DataFrame | list[dict]":
    """Return observation aggregates for ``station`` over ``[start, end]``.

    Parameters
    ----------
    station : str
        ICAO code (e.g. ``"KNYC"``) or 3-letter NWS code.
    start, end : str
        ISO date strings (YYYY-MM-DD), inclusive bounds.
    source : {"iem", "ghcnh", "awc"} | None, keyword-only
        If set, only that source is queried; the other two fetchers are skipped.
        If None, all three are queried and merged with the standard priority
        (AWC > IEM > GHCNh).
    strategy : {"auto", "exact_window", "warm_cache", "hosted"}, keyword-only
        Ingest strategy. Default is ``"auto"`` (resolved by PLAN-07-04). In
        PLAN-07-02 the ``"auto"`` branch is a stub that raises NotImplementedError
        pointing the caller at an explicit strategy. The public default does
        NOT churn between PRs — it ships as ``"auto"`` and stays ``"auto"``.
    as_dataframe : bool, keyword-only, default True
        If True (default), return ``pandas.DataFrame``. If False, return ``list[dict]``.

    Returns
    -------
    pd.DataFrame | list[dict]
        Observation rows merged via SOURCE_PRIORITY (AWC > IEM > GHCNh).

    Raises
    ------
    ValueError
        If ``source`` or ``strategy`` is not in the allowed Literal set.
    NotImplementedError
        If ``strategy="hosted"`` (deferred to v0.2.x), or if ``strategy="warm_cache"``
        / ``"auto"`` until PLAN-07-03 / PLAN-07-04 wire their dispatch bodies.

    Examples
    --------
    >>> from tradewinds.weather import obs
    >>> df = obs("KNYC", "2024-03-01", "2024-03-31", source="iem",
    ...          strategy="exact_window")  # doctest: +SKIP
    """
    if source is not None and source not in _VALID_SOURCES:
        raise ValueError(
            f"source must be one of {sorted(_VALID_SOURCES)} or None; got {source!r}"
        )
    if strategy not in _VALID_STRATEGIES:
        raise ValueError(
            f"strategy must be one of {sorted(_VALID_STRATEGIES)}; got {strategy!r}"
        )

    # Eager ISO validation — fail fast for malformed dates before any network.
    date.fromisoformat(start)
    date.fromisoformat(end)

    # Resolve station via the existing research.py helper (single source of truth).
    from tradewinds.research import _resolve_station
    info = _resolve_station(station)

    # Dispatch. PLAN-02 wires ONLY exact_window. PLAN-03 fills in warm_cache;
    # PLAN-04 fills in the "auto" branch body (signature stays "auto").
    if strategy == "exact_window":
        from tradewinds._exact_fetch import _exact_fetch_observations
        rows = _exact_fetch_observations(
            info,
            start,
            end,
            source=source,
        )
    elif strategy == "warm_cache":
        raise NotImplementedError(
            "strategy='warm_cache' wired in PLAN-07-03 — pass "
            "strategy='exact_window' explicitly until then."
        )
    elif strategy == "auto":
        raise NotImplementedError(
            "strategy='auto' dispatch wired in PLAN-07-04 — "
            "pass strategy='exact_window' or 'warm_cache' explicitly until then."
        )
    elif strategy == "hosted":
        raise NotImplementedError(
            "hosted strategy deferred to v0.2.x — "
            "set TW_HOSTED_URL to enable once client lands"
        )
    else:
        raise ValueError(f"Unknown strategy: {strategy!r}")

    if as_dataframe:
        import pandas as pd
        return pd.DataFrame(rows)
    return rows


__all__ = ["Source", "Strategy", "obs"]

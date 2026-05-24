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
        If ``source`` or ``strategy`` is not in the allowed Literal set, OR if
        ``strategy="warm_cache"`` is called with ``source != None`` (post-merge
        filtering would corrupt SOURCE_PRIORITY semantics; use
        ``strategy="exact_window"`` for single-source queries).
    NotImplementedError
        If ``strategy="hosted"`` (deferred to v0.2.x), or if ``strategy="auto"``
        until PLAN-07-04 wires the dispatch body.

    Notes
    -----
    - ``strategy="warm_cache"`` is byte-equivalent to ``research()`` Mode-1 obs
      aggregates for the columns: obs_high_f, obs_low_f, obs_high_at, obs_low_at,
      source. Verified against the 5 Phase 1 parity fixtures (see
      ``tests/weather/test_obs_warm_cache_parity.py``).

    - ``obs()`` does NOT return CLI climate columns (cli_high_f, cli_low_f,
      fcst_*). If you need joined obs + CLI + forecast, use ``research()`` directly.

    - ``strategy="exact_window"`` is NOT byte-equivalent to ``research()`` — it
      intentionally bypasses year-aligned caching to minimize cold-fetch bytes.
      Output values match research() at the row level, but cache footprint and
      fetch URLs differ.

    - ``strategy="hosted"`` is reserved for the v0.2.x precomputed-API client and
      raises NotImplementedError until that lands.

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
        rows = _warm_cache_fetch(
            info,
            start,
            end,
            source=source,
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


def _warm_cache_fetch(
    info,  # StationInfo from tradewinds._internal._stations
    from_date_iso: str,
    to_date_iso: str,
    *,
    source: Source | None,
) -> list[dict]:
    """Obs rows via research()-equivalent warm-cache orchestration.

    Re-uses the existing ``_fetch_observations_range`` from research.py — same
    per-month loop, same UNION skip predicate, same ``_is_writable_month`` gate,
    same ``_all_caches_warm`` zero-network short-circuit. Skips the climate
    (CLI) leg of ``research()`` since ``obs()`` does not return CLI columns.

    The output is byte-equivalent to the obs aggregates ``research()`` Mode-1
    produces for the same (station, from_date, to_date) inputs at the row level
    (post-aggregation columns are computed by ``research()``'s ``build_pairs``;
    ``obs()`` returns the merged raw rows pre-aggregation).

    ``source != None`` is structurally incompatible with merge-priority
    semantics (post-merge filtering silently drops rows where the named
    source lost the priority tie). Source-filtered callers must use
    ``strategy="exact_window"``, which can enforce source at the FETCHER
    boundary before the merge runs.
    """
    from datetime import timedelta

    from tradewinds.research import (
        _all_caches_warm,
        _fetch_observations_range,
        _prefetch_sources,
    )

    if source is not None:
        raise ValueError(
            f"warm_cache strategy requires source=None; got source={source!r}. "
            "Source filtering requires fetcher-boundary enforcement to preserve "
            "merge priority semantics. Use strategy='exact_window' with "
            "source=... instead."
        )

    # Mirror research.py:1167 — extend by 1 day for the LST-pre-midnight tail.
    extended_to_iso = (
        date.fromisoformat(to_date_iso) + timedelta(days=1)
    ).isoformat()

    # _all_caches_warm gate (preserves the zero-network invariant for fully
    # cached re-runs; see research.py:1183-1185).
    awc_rows = None
    if not _all_caches_warm(info, from_date_iso, to_date_iso, extended_to_iso):
        prefetch = _prefetch_sources(info, from_date_iso, to_date_iso, extended_to_iso)
        awc_rows = prefetch["awc_rows"]

    return _fetch_observations_range(
        info,
        from_date_iso,
        extended_to_iso,
        prefetched_awc_rows=awc_rows,
    )


__all__ = ["Source", "Strategy", "obs"]

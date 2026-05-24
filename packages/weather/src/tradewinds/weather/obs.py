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

    # Resolve "auto" to a concrete strategy first; never recurse (W-5).
    if strategy == "auto":
        import os

        resolved = _resolve_strategy(
            from_date=date.fromisoformat(start),
            to_date=date.fromisoformat(end),
            station=station,
            env=os.environ,
        )
    else:
        resolved = strategy

    rows = _dispatch_strategy(
        info,
        start,
        end,
        source=source,
        strategy=resolved,
    )

    if as_dataframe:
        import pandas as pd
        return pd.DataFrame(rows)
    return rows


def _dispatch_strategy(
    info,
    from_date_iso: str,
    to_date_iso: str,
    *,
    source: "Source | None",
    strategy: Literal["exact_window", "warm_cache", "hosted"],
) -> list[dict]:
    """Single dispatch path for the three concrete strategies. NEVER recurses (W-5).

    Future kwargs added to ``obs()`` need to be threaded ONCE through this
    helper, not re-marshalled into a recursive ``obs(...)`` call where every
    new param risks being forgotten.
    """
    if strategy == "exact_window":
        from tradewinds._exact_fetch import _exact_fetch_observations

        return _exact_fetch_observations(
            info, from_date_iso, to_date_iso, source=source
        )
    if strategy == "warm_cache":
        return _warm_cache_fetch(
            info, from_date_iso, to_date_iso, source=source
        )
    if strategy == "hosted":
        raise NotImplementedError(
            "hosted strategy deferred to v0.2.x — "
            "set TW_HOSTED_URL to enable once client lands"
        )
    raise ValueError(f"Unknown concrete strategy: {strategy!r}")


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


def _resolve_strategy(
    from_date: date,
    to_date: date,
    station: str,
    env,
    *,
    cache_root=None,
) -> Literal["exact_window", "warm_cache", "hosted"]:
    """Decide which ingest strategy ``auto`` should dispatch to.

    Decision rules (applied in order; first match wins):

    1. If ``env["TW_HOSTED_URL"]`` is set → ``"hosted"``.
    2. Else if window < 90 days AND no cached parquet for ANY year touching
       the window → ``"exact_window"``.
    3. Else if any cached parquet for ANY year touching the window exists →
       ``"warm_cache"``.
    4. Else (large window, no cache, no env) → ``"warm_cache"`` (fallback;
       long windows benefit from year-aligned caching even cold because
       multiple months hit the same yearly IEM CSV).

    W-2: cache-warmth check spans every year from ``from_date.year`` through
    ``to_date.year`` inclusive. A window crossing Dec→Jan would otherwise
    miss any warm cache in the second year.

    The 90-day threshold matches the empirical finding in
    ``.planning/research/INGEST-PLANNER-RESEARCH.md``: at 3 months a
    warm_cache query already pays the full ~13 MB year-aligned cost, so
    under that bucket exact_window wins decisively when the cache is cold.

    Parameters
    ----------
    from_date, to_date : date
        Window bounds (inclusive).
    station : str
        Station identifier (used to probe the cache).
    env : Mapping[str, str]
        Environment mapping. Pass ``os.environ`` in production; pass a dict
        for tests.
    cache_root : Path | None
        Override cache root for tests. Defaults to ``$TRADEWINDS_CACHE_DIR``
        or ``~/.tradewinds/cache`` via ``_cache_root()``.

    Returns
    -------
    {"exact_window", "warm_cache", "hosted"}
    """
    from tradewinds.weather.cache import _has_cached_year

    if env.get("TW_HOSTED_URL"):
        return "hosted"

    window_days = (to_date - from_date).days + 1
    has_cache = any(
        _has_cached_year(station, y, cache_root=cache_root)
        for y in range(from_date.year, to_date.year + 1)
    )

    if window_days < 90 and not has_cache:
        return "exact_window"

    return "warm_cache"


__all__ = ["Source", "Strategy", "obs"]

"""mostlyright.weather.obs — public surface for observation aggregates.

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
_VALID_STRATEGIES: frozenset[str] = frozenset({"auto", "exact_window", "warm_cache", "hosted"})


def obs(
    station: str,
    start: str,
    end: str,
    *,
    source: Source | None = None,
    strategy: Strategy = "auto",
    as_dataframe: bool = True,
) -> pd.DataFrame | list[dict]:
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
    >>> from mostlyright.weather import obs
    >>> df = obs("KNYC", "2024-03-01", "2024-03-31", source="iem",
    ...          strategy="exact_window")  # doctest: +SKIP
    """
    if source is not None and source not in _VALID_SOURCES:
        raise ValueError(f"source must be one of {sorted(_VALID_SOURCES)} or None; got {source!r}")
    if strategy not in _VALID_STRATEGIES:
        raise ValueError(f"strategy must be one of {sorted(_VALID_STRATEGIES)}; got {strategy!r}")

    # Eager ISO validation — fail fast for malformed dates before any network.
    date.fromisoformat(start)
    date.fromisoformat(end)

    # Resolve station via the existing research.py helper (single source of truth).
    from mostlyright.research import _resolve_station

    info = _resolve_station(station)

    # Resolve "auto" to a concrete strategy first; never recurse (W-5).
    if strategy == "auto":
        import os

        resolved = _resolve_strategy(
            from_date=date.fromisoformat(start),
            to_date=date.fromisoformat(end),
            station=info.icao,  # cache uses ICAO (e.g. KNYC), not raw user input
            env=os.environ,
            source=source,
        )
    else:
        resolved = strategy

    raw_rows = _dispatch_strategy(
        info,
        start,
        end,
        source=source,
        strategy=resolved,
    )

    # Aggregate raw observation rows to daily summary rows. The output schema is
    # the obs_* subset of research() Mode-1 columns (no CLI / no forecast). Both
    # exact_window and warm_cache funnel through this aggregation so the daily
    # rows are byte-equivalent across strategies.
    aggregated = _aggregate_daily_rows(raw_rows, info, start, end)

    if as_dataframe:
        import pandas as pd

        return pd.DataFrame(aggregated)
    return aggregated


def _dispatch_strategy(
    info,
    from_date_iso: str,
    to_date_iso: str,
    *,
    source: Source | None,
    strategy: Literal["exact_window", "warm_cache", "hosted"],
) -> list[dict]:
    """Single dispatch path for the three concrete strategies. NEVER recurses (W-5).

    Future kwargs added to ``obs()`` need to be threaded ONCE through this
    helper, not re-marshalled into a recursive ``obs(...)`` call where every
    new param risks being forgotten.
    """
    if strategy == "exact_window":
        from mostlyright._exact_fetch import _exact_fetch_observations

        return _exact_fetch_observations(info, from_date_iso, to_date_iso, source=source)
    if strategy == "warm_cache":
        return _warm_cache_fetch(info, from_date_iso, to_date_iso, source=source)
    if strategy == "hosted":
        # Phase 21 21-09: migrated from NotImplementedError to the structural
        # DataAvailabilityError so cross-SDK callers can branch on `e.reason`
        # rather than string-matching the message. Symmetric with TS
        # obs(strategy="hosted") per D-06.
        from mostlyright.core.exceptions import DataAvailabilityError

        raise DataAvailabilityError(
            reason="model_unavailable",
            hint="hosted strategy deferred to v0.2.x — set TW_HOSTED_URL to enable once client lands",
            source="obs.hosted",
        )
    raise ValueError(f"Unknown concrete strategy: {strategy!r}")


def _warm_cache_fetch(
    info,  # StationInfo from mostlyright._internal._stations
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

    from mostlyright.research import _fetch_observations_range

    if source is not None:
        raise ValueError(
            f"warm_cache strategy requires source=None; got source={source!r}. "
            "Source filtering requires fetcher-boundary enforcement to preserve "
            "merge priority semantics. Use strategy='exact_window' with "
            "source=... instead."
        )

    # Mirror research.py:1167 — extend by 1 day for the LST-pre-midnight tail.
    extended_to_iso = (date.fromisoformat(to_date_iso) + timedelta(days=1)).isoformat()

    # Skip _all_caches_warm + _prefetch_sources from research.py: those gate on
    # CLI climate cache + fire a CLI prefetch worker that obs() never consumes.
    # Calling _fetch_observations_range directly with prefetched_awc_rows=None
    # makes it perform its own per-month cache reads + lazy AWC fetch. Fully
    # cached re-runs still short-circuit at the per-month read_cache layer in
    # research.py:_fetch_observations_range (codex iter-2 HIGH #3).
    return _fetch_observations_range(
        info,
        from_date_iso,
        extended_to_iso,
        prefetched_awc_rows=None,
    )


def _aggregate_daily_rows(
    raw_rows: list[dict],
    info,
    from_date_iso: str,
    to_date_iso: str,
    *,
    tz_override: str | None = None,
) -> list[dict]:
    """Bucket raw obs rows by LST settlement date then aggregate per-day.

    Mirrors the obs-only subset of ``research()``'s pipeline at
    ``packages/core/src/mostlyright/research.py:1213-1238``: each raw row is
    routed to its LST settlement date via :func:`settlement_date_for`, then
    ``_obs_aggregates`` produces the daily summary columns (``obs_high_f``,
    ``obs_low_f``, ``obs_mean_f``, ``obs_mean_dewpoint_f``, ``obs_max_wind_kt``,
    ``obs_max_gust_kt``, ``obs_total_precip_in``, ``obs_count``).

    The bucketing fixes the per-row UTC-date filter that previously dropped
    legitimate observations belonging to the last LST settlement window's
    pre-midnight UTC tail (codex iter-1 CRITICAL #2): rows are now classified
    by SETTLEMENT date, not UTC date, so a US-station observation at
    ``2024-04-01T03:00:00Z`` correctly counts toward ``2024-03-31`` LST.

    Rows whose settlement date falls outside ``[from_date_iso, to_date_iso]``
    are dropped from the output (they were fetched only to capture the
    settlement-window tail).
    """
    from mostlyright._internal._pairs import _obs_aggregates, date_range
    from mostlyright.snapshot import settlement_date_for

    dates = date_range(from_date_iso, to_date_iso)
    buckets: dict[str, list[dict]] = {d: [] for d in dates}
    for r in raw_rows:
        observed_at = r.get("observed_at")
        if not observed_at:
            continue
        try:
            settle_date = settlement_date_for(observed_at, info.code, tz_override=tz_override)
        except ValueError:
            continue
        bucket = buckets.get(settle_date)
        if bucket is not None:
            bucket.append(r)

    out: list[dict] = []
    for d in dates:
        agg = _obs_aggregates(buckets[d])
        out.append({"date": d, "station": info.code, **agg})
    return out


def _resolve_strategy(
    from_date: date,
    to_date: date,
    station: str,
    env,
    *,
    cache_root=None,
    source: Source | None = None,
) -> Literal["exact_window", "warm_cache", "hosted"]:
    """Decide which ingest strategy ``auto`` should dispatch to.

    Decision rules (applied in order; first match wins):

    1. If ``source`` is not None → ``"exact_window"``. No other strategy
       honors source filtering today: warm_cache rejects source!=None
       (post-merge filtering would corrupt SOURCE_PRIORITY); hosted is a
       v0.2.x stub that raises NotImplementedError. This rule runs BEFORE
       the env-var check so source-filtered callers still succeed even
       with TW_HOSTED_URL set (codex iter-3 HIGH).
    2. Else if ``env["TW_HOSTED_URL"]`` is set → ``"hosted"``.
    3. Else if window < 90 days AND no cached parquet for ANY year touching
       the window → ``"exact_window"``.
    4. Else if any cached parquet for ANY year touching the window exists →
       ``"warm_cache"``.
    5. Else (large window, no cache, no env) → ``"warm_cache"`` (fallback;
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
        Override cache root for tests. Defaults to ``$MOSTLYRIGHT_CACHE_DIR``
        or ``~/.mostlyright/cache`` via ``_cache_root()``.
    source : {"iem", "ghcnh", "awc"} | None
        Source filter from the obs() caller. When set, forces exact_window
        regardless of window size or cache warmth — warm_cache cannot honor
        source filtering correctly.

    Returns
    -------
    {"exact_window", "warm_cache", "hosted"}
    """
    from mostlyright.weather.cache import _has_cached_year

    # Source-filtered queries always go through exact_window because no other
    # strategy honors source filtering today (warm_cache rejects source!=None;
    # hosted is a v0.2.x stub that raises NotImplementedError). Source check
    # runs BEFORE the env-var check so source-filtered callers can still use
    # exact_window even with TW_HOSTED_URL set in the environment — otherwise
    # `obs(source="iem")` would fail loudly for users who have the env var
    # set for other reasons (codex iter-3 HIGH).
    if source is not None:
        return "exact_window"

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

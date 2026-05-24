# Ingest strategies — `tw.weather.obs(...)`

`tw.weather.obs()` smart-routes between three ingest strategies depending on
your query shape and cache state. This page is the decision-tree reference and
the per-strategy cost table.

## Quick reference

```python
from tradewinds.weather import obs

# Default (strategy="auto") picks the right path for you.
df = obs("KNYC", "2024-03-01", "2024-03-31")

# Explicit strategies:
df = obs("KNYC", "2024-03-01", "2024-03-31", strategy="exact_window")
df = obs("KNYC", "2024-03-01", "2024-03-31", strategy="warm_cache")
df = obs("KNYC", "2024-03-01", "2024-03-31", strategy="hosted")  # v0.2.x
```

## Decision tree (`strategy="auto"`)

```
                  TW_HOSTED_URL env var set?
                          /         \
                       yes           no
                        |             |
                     hosted    window < 90 days?
                                  /         \
                                yes           no
                                 |             |
                          cache hit for     warm_cache
                          (station, year)?  (fallback)
                              /     \
                           yes       no
                            |         |
                       warm_cache  exact_window
```

Rules applied in order, first match wins:

1. `TW_HOSTED_URL` set → `hosted` (raises `NotImplementedError` until v0.2.x).
2. Window < 90 days AND no cached parquet for any year touching the window → `exact_window`.
3. Any cached parquet for any year touching the window exists → `warm_cache`.
4. Otherwise (large window, cold cache, no env) → `warm_cache` (fallback).

The 90-day threshold is empirically derived: at 3 months a `warm_cache` query
already pays the full ~13 MB year-aligned cost (because IEM serves yearly
CSVs), so under that bucket `exact_window` wins decisively when the cache is
cold.

The cache-warmth check scans every year from `from_date.year` through
`to_date.year` inclusive (W-2). Windows crossing Dec→Jan correctly see warm
cache in either year.

## Per-strategy cost table

Source: `.planning/research/INGEST-PLANNER-RESEARCH.md`. Numbers are for
KNYC, March 2024 (1 month), March-May 2024 (3 months), and full 2024 (12 months).

| Strategy       | Window | Cold (s) | Warm (s) | Bytes (MB) | Rows | Best for |
|----------------|--------|----------|----------|------------|------|----------|
| `exact_window` | 1 mo   | ~10–15   | ~0.5     | **≤ 2**    | 31   | one-off backtest replays, cold cache |
| `warm_cache`   | 1 mo   | ~69.7    | ~4.72    | 13.43      | 31   | repeated overlapping queries |
| `warm_cache`   | 3 mo   | ~10.17   | ~0.35    | 13.54      | 92   | quarter-window backtests with warm cache |
| `warm_cache`   | 12 mo  | ~23.69   | ~0.56    | 26.01      | 366  | full-year sweeps |
| `hosted`       | any    | TBD      | TBD      | minimal    | —    | v0.2.x precomputed-API path |

Notes:
- `exact_window` writes NO entries to the canonical
  `v1/observations/{STATION}/{YYYY}/{MM}.parquet` cache by design — repeated
  calls re-fetch. IEM CSVs for exact-window queries land under a SEPARATE
  directory namespace at `sources/iem_asos_exact/` (B-5: directory-level
  separation; no filename infix collisions).
- `warm_cache` populates the canonical cache; subsequent calls with overlapping
  windows benefit from the year-aligned read path. Byte-equivalent to
  `research()` Mode-1 obs aggregates for the 5 Phase 1 parity fixtures.
- `warm_cache` requires `source=None` — single-source warm_cache would corrupt
  the merge-priority semantics. For source-filtered queries use
  `exact_window` (fetcher-boundary enforcement preserves priority correctly).
- `hosted` is reserved for the precomputed-API client landing in v0.2.x. The
  seam (`TW_HOSTED_URL` env var) is wired today.

## Mutable-period semantics

All three strategies honor the same mutable-period invariants:

- The **current LST month** for a given station is never written to the
  canonical monthly parquet. It is re-fetched on every call.
- The **current LST year** influences the `_is_current_lst_year` cache
  predicate for yearly IEM CSVs — files spanning the current year use the
  `_partial` filename infix and are not trusted as final.
- The `_is_writable_month` gate is "strictly past UTC" — months whose final
  day has not yet passed in UTC time are excluded from canonical cache writes.

These invariants are enforced in the existing helpers
(`tradewinds.research._is_writable_month`,
`tradewinds.weather.cache._is_current_lst_month`,
`tradewinds.weather.cache._is_current_lst_year`) — see source for details.
The `tradewinds.weather.obs` surface reuses these helpers and adds no new
mutable-period logic.

## When to use which strategy

- **Default (`auto`)** is the right choice for almost all interactive use. It
  picks `exact_window` for cheap one-off queries and `warm_cache` when you've
  already paid the year-aligned cache cost (or when the window is too large
  for `exact_window` to make sense).
- **Force `exact_window`** if you know you're doing a single backtest replay
  on a cold cache and want minimal bytes (e.g. CI). Also use for single-source
  queries (`source="iem"`, etc.) — these are not supported by `warm_cache`.
- **Force `warm_cache`** if you're running batch backtests across many windows
  and want the year-aligned cache to pay off. This is what `research()` does
  internally — `obs(strategy="warm_cache")` is byte-equivalent to `research()`
  Mode-1 obs aggregates.
- **`hosted`** will become the default for v0.2.x users with `TW_HOSTED_URL`
  set, once the precomputed-API client lands.

## See also

- `tradewinds.research.research()` — the full obs + CLI + forecast join.
- `.planning/research/INGEST-PLANNER-RESEARCH.md` — the empirical research
  doc that informed this design.
- `.planning/ROADMAP.md` — Phase 7 entry.

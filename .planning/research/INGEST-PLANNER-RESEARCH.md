# Ingest Planner Research — empirical foundation for `tw.weather.obs(strategy="auto")`

Part 1 of a two-part task. Part 2 will use `/gsd-add-phase` +
`/gsd-plan-phase` to design `tw.weather.obs(..., strategy="auto")` and
consumes this doc as its empirical foundation. No code changes here —
this is research/documentation only.

- Date: 2026-05-24
- Machine: macOS aarch64-darwin
- tradewinds: 0.1.0rc1
- Station under test: KNYC
- Bench mode: live (real public APIs, AWC + IEM ASOS + GHCNh + NWS CLI)

----------------------------------------------------------------------

## §1 Executive summary

- **Headline finding:** the 1-month and 3-month cold downloads transfer
  essentially the same bytes (13.43 MB vs 13.54 MB) because the IEM ASOS
  fetcher year-normalizes the request window
  (`packages/weather/src/tradewinds/weather/_fetchers/iem_asos.py:204-209`).
  Small caller windows do NOT shrink the network footprint under current
  behavior — a 31-day query pays for a full canonical year.
- **The 12-month case doubles bytes** (26.01 MB) only because
  `research()`'s `extended_to=2025-01-01`
  (`packages/core/src/tradewinds/research.py:968`) forces a second IEM
  yearly chunk + a second GHCNh PSV for the spilled day.
- **Warm re-fetch is free** (`delta_bytes=0`) at every window size — the
  fully-cached zero-network path is honored
  (`research.py:626-647`, `_all_caches_warm`).
- **The 1mo cold-time anomaly (69.7s vs 3mo's 10.17s) is one-shot process
  startup**: Python interpreter + pandas import + pyarrow import + httpx
  connection-pool warmup baked into the first call of the process. NOT
  proportional to window size. Subsequent calls in the same process
  amortize it (3mo/12mo cold times sit at 10-24s).
- **Rows scale linearly** (31 → 92 → 366), **bytes do not** (13.43 →
  13.54 → 26.01). Bytes step only at the year boundary because of
  year-normalization.
- **Forward pointer (Part 2):** the auto-planner needs at minimum a
  `strategy="exact_window"` mode for one-off small queries to bypass
  year-normalization. Win envelope is up to ~12 MB per 1-month query if
  the caller will not also hit sibling per-month callers in the same
  year. `warm_cache` keeps current behavior; `hosted` is a reserved v0.2
  seam.

----------------------------------------------------------------------

## §2 Current architecture (file:line refs)

This is the live `research()` ingest path. Every bullet has a concrete
file:line citation that has been validated against the worktree.

- **Orchestrator entry:**
  `packages/core/src/tradewinds/research.py:876-1024` — top-level
  `research(station, from_date, to_date, ...)`. The function:
  1. Resolves the station via `_resolve_station`
     (`research.py:76-98`) against the 20-station Phase 1 registry.
  2. Validates the inclusive LST settlement-date range with
     `date_range(from_date, to_date)` (lifted helper).
  3. Computes `extended_to = (to_date + 1 day).isoformat()`
     (`research.py:968`) so the last LST settlement window's pre-midnight
     UTC tail observations are included.
  4. Calls `_all_caches_warm(...)` (`research.py:626-647`); if False,
     runs `_prefetch_sources(...)` and captures `awc_rows` for the
     downstream observation fetch.
  5. Calls `_fetch_observations_range(...)` then
     `_fetch_climate_range(...)` sequentially.
  6. Groups observations by `settlement_date_for(...)` (Pitfall-1 fix in
     `research.py:1004` — NOT `observed_at[:10]`) and joins via
     `build_pairs(...)`.

- **Prefetch (4-way parallel):**
  `packages/core/src/tradewinds/research.py:650-873` —
  `_prefetch_sources()` runs a
  `concurrent.futures.ThreadPoolExecutor(max_workers=4)` per Option C
  from `.planning/research/SOURCE-LIMITS.md`. The four workers are
  `iem.archive`, `cli.archive`, `ghcnh.archive`, `awc.live`. Two
  load-bearing contracts in this block:
  - **Pitfall-6 timing pattern**: `submitted_at[name]` is captured
    immediately after `ex.submit()` (`research.py:849-853`), NOT inside
    the `as_completed` loop, so per-source timings measure actual work
    rather than iteration-order accident.
  - **Narrow-except contract** in the `_warm_*` helpers: only
    `httpx.HTTPStatusError`, `httpx.RequestError`, `OSError` are
    swallowed (see `research.py:742, 762-776, 787-801, 829-831`).
    Programming bugs propagate via `f.result()` (`research.py:863`) per
    the orchestrator's degraded-graceful contract.
  - **Current-UTC-year skip**: `range(from_d.year, min(..., _now.year - 1) + 1)`
    (`research.py:729, 759, 784`) prevents prefetching the current UTC
    year, which would write to the `_partial` namespace and force the
    sequential lazy path to re-fetch into the canonical namespace
    (codex/architect iter-1 HIGH-3/4).
  - **AWC-window-relevance skip**: `_fetch_awc()` returns `None` (not
    `[]`) when no requested month overlaps the AWC 168h window
    (`research.py:809-812, 825-826`), preserving the lazy fallback
    contract so fully-cached re-runs touch zero network.

- **Observations range fetch:**
  `packages/core/src/tradewinds/research.py:362-516` —
  `_fetch_observations_range()`. Per-month loop:
  1. `read_cache(info.icao, year, month)` — on hit, extend result and
     skip network entirely (also skips GHCNh + AWC for this month).
  2. On miss, compute `month_is_writable_utc` via `_is_writable_month`
     and the union skip predicate
     `skip_iem_source = _is_current_lst_month(...) or not month_is_writable_utc`
     (`research.py:456-457`).
  3. Call `_fetch_iem_month` (METAR + SPECI, requires BOTH to succeed
     for `iem_ok=True` — `research.py:256-259`).
  4. Lazy-load GHCNh year via `_ensure_ghcnh_year` (`research.py:336-359`).
  5. Slice AWC rows for month via `_awc_for_month` (closes over
     `prefetched_awc_rows`).
  6. **Pre-sort** the combined list by `(observed_at, source)`
     (`research.py:493`) BEFORE `merge_observations` — the merge layer
     uses first-seen-wins at equal priority and dict-insertion-order
     `list(best.values())` output, so input order is load-bearing for
     both tie-break determinism AND survivor ordering.
  7. **Cache-write gate**: `if iem_ok and _is_writable_month(...)` —
     both gates must pass to call `write_cache` (`research.py:502-512`).

- **Climate range fetch:**
  `packages/core/src/tradewinds/research.py:519-623` —
  `_fetch_climate_range()`. Per-year loop:
  1. `read_climate_cache(info.icao, year)`; on hit, extend and continue.
  2. On miss, compute the union skip predicate
     `skip_cli_source = _is_current_lst_year(...) or year >= _now.year`
     (`research.py:566`).
  3. Call `download_cli(...)`, parse via `parse_cli_response`, merge via
     `merge_climate` (STRICT `>` tie-break, see `CLAUDE.md` Climate
     LIVE_V1 rules).
  4. Write gate: `if year < _now.year` — strict UTC past only
     (`research.py:612-620`).

- **Zero-network gate:**
  `packages/core/src/tradewinds/research.py:626-647` —
  `_all_caches_warm()` returns True iff every requested
  `(station, year, month)` parquet exists AND every requested
  `(station, year)` climate parquet exists. When True, `research()` does
  NOT call `_prefetch_sources` (`research.py:984`), so fully-cached
  re-runs touch zero network.

- **IEM ASOS fetcher:**
  `packages/weather/src/tradewinds/weather/_fetchers/iem_asos.py` —
  - **Year-normalization** lives at `iem_asos.py:204-209`. The caller's
    `start` is rewritten to `date(start.year, 1, 1)` before the chunker
    runs. Tradewinds-specific deviation from mostlyright PR #85 verbatim.
    See §4 for the full rationale + quoted comment.
  - **Cache filename**: `iem_{start_iso}_{end_iso}_{suffix}.csv` is the
    canonical form; `_partial` is injected before `_{suffix}` when
    `chunk_is_partial = skip_cache or chunk_end > today_utc`
    (`iem_asos.py:215-216`). The two predicates are joined by **OR not
    AND** (Pitfall-3) — each independently can poison the cache, so
    each independently must route to `_partial`.
  - **Polite delay**: `IEM_POLITE_DELAY = 1.0` (`iem_asos.py:68`) sleep
    between consecutive HTTP requests; IEM published a 1-sec/IP throttle
    on 2026-04-21 (see `.planning/research/SOURCE-LIMITS.md`).
  - **Reversed-range guard**: `if start > end: return []`
    (`iem_asos.py:201-202`) at the caller boundary mirrors the chunker
    invariant (codex iter-1 HIGH).

- **Other adapters (one-liners):**
  - **AWC** (`packages/weather/src/tradewinds/weather/_fetchers/awc.py`)
    — `fetch_awc_metars([icao], hours=168)`. 168-hour live fetch window;
    in-memory only; no disk cache. Largest single response observed in
    the spike: ~110 KB.
  - **GHCNh** (`packages/weather/src/tradewinds/weather/_fetchers/ghcnh.py`)
    — per-station-year PSV at NCEI. Largest single body observed in the
    spike: ~10.8 MB; load-bearing for the PERF-03 `HTTP_TIMEOUT=60s`
    bump.
  - **IEM CLI** (`packages/weather/src/tradewinds/weather/_fetchers/iem_cli.py`)
    — per-station-year JSON. ~460 KB per station-year in the spike.

- **Parquet cache:**
  `$HOME/.tradewinds/cache/v1/observations/{STATION}/{YYYY}/{MM}.parquet`
  for observations and
  `$HOME/.tradewinds/cache/v1/climate/{STATION}/{YYYY}.parquet` for
  climate. Cache root override: `TRADEWINDS_CACHE_DIR` env var
  (`packages/weather/src/tradewinds/weather/cache.py:135-144`).
  - **FileLock-guarded atomic write**:
    `packages/weather/src/tradewinds/weather/cache.py:230-253`. Writes to
    `path.with_suffix('.tmp')` under a `FileLock` with 30 s timeout,
    then `os.replace(tmp, path)` (atomic on POSIX and Windows). A crash
    mid-write never leaves a truncated parquet at the read path.
  - **Parquet options**: every write uses `version="2.6"` and
    `coerce_timestamps="us"` (`cache.py:250`) for cross-pyarrow-version
    byte stability + microsecond-resolution timestamps.

- **Mutable-period invariants (load-bearing):**
  - `_is_writable_month`: `packages/core/src/tradewinds/research.py:316-333`
    — orchestrator-layer gate; UTC-strict-past-only
    (`(year, month) < (now.year, now.month)`). The docstring rationale,
    quoted verbatim, is load-bearing context for any future strategy
    mode:

    ```python
    """True iff ``(year, month)`` is strictly in the past in UTC.

    ``write_cache`` already no-ops the station's current **LST** month, but
    that predicate lags UTC for negative-offset stations (the v0.1.0
    registry is all US, UTC-5 .. UTC-10). At month boundaries — when UTC
    has rolled into the next month but LST is still in the previous month
    — the LST-only gate lets the orchestrator write a parquet for the
    new UTC month with only the few hours of data IEM has so far. Once
    LST catches up, ``read_cache`` would treat that partial file as
    complete and return stale aggregates (codex iter-2 P2).

    This stricter UTC-based predicate gates writes at the orchestrator
    layer so the partial-month race cannot happen regardless of the
    station's timezone offset.
    """
    ```

  - `_is_current_lst_month` / `_is_current_lst_year` in
    `packages/weather/src/tradewinds/weather/cache.py:194-211` — LST-current
    skip inside the cache layer. Used by both `read_cache` /
    `read_climate_cache` (return `None`) and `write_cache` /
    `write_climate_cache` (no-op).
  - **Source-cache skip predicate is the UNION**: "current LST" OR
    "not strictly past UTC". Both predicates must clear before a row is
    allowed to enter the parquet cache. See `research.py:457`
    (observations) and `research.py:566` (climate). Skipping the union
    on either source forfeits the partial-month / partial-year safety
    guarantees.

----------------------------------------------------------------------

## §3 Empirical timing (the bench + interpretation)

### §3.1 Methodology

- Bench script lived at `/tmp/tw_ingest_bench.py` (NOT committed — this
  doc captures everything that matters).
- Each case ran cold then warm against `TRADEWINDS_CACHE_DIR=/tmp/tw_bench_cache_{label}`
  so cold = empty cache. Warm = immediately re-call `research()` with
  the same cache populated by the cold call.
- Bytes are dir-size delta on `$TRADEWINDS_CACHE_DIR` before/after the
  cold call (summing `f.stat().st_size` over every file under the cache
  root). Warm delta is measured the same way and confirms zero new
  bytes land on disk.
- Test station: KNYC. Three windows:
  - 1mo — 2024-03-01..2024-03-31 (31 settlement days)
  - 3mo — 2024-03-01..2024-05-31 (92 settlement days)
  - 12mo — 2024-01-01..2024-12-31 (366 settlement days; 2024 was a leap year)
- All windows are stable past UTC as of 2026-05-24 — nothing trips the
  `_is_writable_month` / `_is_current_lst_*` skip predicates.
- Machine: macOS aarch64-darwin, 2026-05-24 morning, live public APIs
  (AWC + IEM ASOS + GHCNh + NWS CLI).

### §3.2 Results

Raw bench output (inlined; the `/tmp/tw_bench_results.json` artifact is
NOT committed):

```
=== 1mo (KNYC, 2024-03-01..2024-03-31) ===
  cold: 69.7s, rows=31, delta=13.43 MB
  warm: 4.72s, delta=0.0 MB
  IEM CSV files:    ['iem_2024-01-01_2025-01-01_metar.csv', 'iem_2024-01-01_2025-01-01_speci.csv']
  GHCNh PSV files:  ['GHCNh_USW00094728_2024.psv']
  CLI JSON files:   ['cli_2024.json']
  obs_parquets (2): ['v1/observations/KNYC/2024/03.parquet',
                     'v1/observations/KNYC/2024/04.parquet']
  clim_parquets:    ['v1/climate/KNYC/2024.parquet']

=== 3mo (KNYC, 2024-03-01..2024-05-31) ===
  cold: 10.17s, rows=92, delta=13.54 MB
  warm: 0.35s, delta=0.0 MB
  IEM CSV files:    ['iem_2024-01-01_2025-01-01_metar.csv', 'iem_2024-01-01_2025-01-01_speci.csv']
  GHCNh PSV files:  ['GHCNh_USW00094728_2024.psv']
  CLI JSON files:   ['cli_2024.json']
  obs_parquets (4): ['v1/observations/KNYC/2024/03.parquet',
                     'v1/observations/KNYC/2024/04.parquet',
                     'v1/observations/KNYC/2024/05.parquet',
                     'v1/observations/KNYC/2024/06.parquet']
  clim_parquets:    ['v1/climate/KNYC/2024.parquet']

=== 12mo (KNYC, 2024-01-01..2024-12-31) ===
  cold: 23.69s, rows=366, delta=26.01 MB
  warm: 0.56s, delta=0.0 MB
  IEM CSV files (4):
    ['iem_2024-01-01_2025-01-01_metar.csv',
     'iem_2024-01-01_2025-01-01_speci.csv',
     'iem_2025-01-01_2026-01-01_metar.csv',
     'iem_2025-01-01_2026-01-01_speci.csv']
  GHCNh PSV files (2):
    ['GHCNh_USW00094728_2024.psv',
     'GHCNh_USW00094728_2025.psv']
  CLI JSON files: ['cli_2024.json']
  obs_parquets (13):
    ['v1/observations/KNYC/2024/01.parquet',
     'v1/observations/KNYC/2024/02.parquet',
     'v1/observations/KNYC/2024/03.parquet',
     'v1/observations/KNYC/2024/04.parquet',
     'v1/observations/KNYC/2024/05.parquet',
     'v1/observations/KNYC/2024/06.parquet',
     'v1/observations/KNYC/2024/07.parquet',
     'v1/observations/KNYC/2024/08.parquet',
     'v1/observations/KNYC/2024/09.parquet',
     'v1/observations/KNYC/2024/10.parquet',
     'v1/observations/KNYC/2024/11.parquet',
     'v1/observations/KNYC/2024/12.parquet',
     'v1/observations/KNYC/2025/01.parquet']
  clim_parquets: ['v1/climate/KNYC/2024.parquet']
```

Compact summary table for cross-reference:

| Case | Window | Cold (s) | Warm (s) | Cold ΔMB | Warm ΔMB | Rows | IEM CSVs | GHCNh PSVs | CLI JSONs | Obs parquets |
|------|--------|---------:|---------:|---------:|---------:|-----:|---------:|-----------:|----------:|-------------:|
| 1mo  | 2024-03-01..2024-03-31 | 69.70 | 4.72 | 13.43 | 0.0 | 31  | 2 | 1 | 1 | 2  |
| 3mo  | 2024-03-01..2024-05-31 | 10.17 | 0.35 | 13.54 | 0.0 | 92  | 2 | 1 | 1 | 4  |
| 12mo | 2024-01-01..2024-12-31 | 23.69 | 0.56 | 26.01 | 0.0 | 366 | 4 | 2 | 1 | 13 |

### §3.3 Interpretation (the empirical findings)

1. **1mo ≈ 3mo bytes (13.43 MB vs 13.54 MB).** Year-normalization
   (`iem_asos.py:204-209`) forces the full IEM 2024-01-01..2025-01-01
   window regardless of caller window size. The CSV filenames are
   identical between the two cases:
   `iem_2024-01-01_2025-01-01_metar.csv` +
   `iem_2024-01-01_2025-01-01_speci.csv`. GHCNh is per-station-year, so
   the same `GHCNh_USW00094728_2024.psv` lands either way. NWS CLI is
   per-station-year too (`cli_2024.json`). Net: a 1-month caller pays
   the same bytes as a 3-month caller. **This is the single fact that
   motivates `strategy="exact_window"` in Part 2.**

2. **12mo doubles bytes (26.01 MB).** `extended_to=2025-01-01`
   (`research.py:968` adds one day past `to_date` for the LST-tail
   capture) spills the observation fetch into year 2. The 12mo case
   therefore touches `_fetch_iem_month(..., year=2025, month=1)` once;
   that triggers `download_iem_asos` with `start = 2025-01-01` which
   year-normalizes to a full 2025 canonical chunk + its sibling SPECI.
   Same logic for GHCNh: `_ensure_ghcnh_year` populates 2025 on first
   miss, fetching `GHCNh_USW00094728_2025.psv`. The 13th obs parquet
   (`2025/01.parquet`) is the `extended_to` artifact. NWS CLI is
   per-LST-day so the climate year range is unchanged (`cli_2024.json`
   only) — see `research.py:552, 994` which uses the original
   `[from_date, to_date]` year range rather than `extended_to`.

3. **1mo cold-time anomaly (69.7s vs 3mo's 10.17s).** Not proportional
   to window. One-shot process startup: Python interpreter +
   `import pandas` + `import pyarrow` + `httpx` connection-pool warmup
   baked into the first call of the process. Subsequent calls in the
   same process amortize this — the 3mo and 12mo cold timings (10.17s
   and 23.69s) reflect the steady-state network + parse + merge work.
   Document this so the Part-2 planner doesn't over-weight 1mo cold
   timings when sizing the `exact_window` heuristic.

4. **Warm is always free (`delta=0.0 MB`).** `_all_caches_warm`
   (`research.py:626-647`) gates the no-network path. Warm wall-times
   of 0.35 s (3mo) / 0.56 s (12mo) reflect pyarrow parquet reads +
   `build_pairs` + DataFrame construction, NOT HTTP. The 1mo warm time
   of 4.72 s is dominated by the same first-call-of-process startup
   cost — a re-run in a fresh process measures the cache-only path
   accurately at sub-second.

5. **Rows scale linearly, bytes do not.** 31 → 92 → 366 rows; bytes
   13.43 → 13.54 → 26.01 MB. The bytes step only at the year boundary.
   Within a single year the network footprint is constant (same canonical
   yearly CSV + same annual PSV + same annual JSON); only the parquet
   layer grows by ~kB per month. This confirms the year-quantization
   story end to end and tells Part 2 that small-window cost-savings
   live on the network layer, not the parquet layer.

----------------------------------------------------------------------

## §4 Year-normalization deep dive

### §4.1 The code

Lifted PR #85 chunker logic — the verbatim caller-side modifications in
`packages/weather/src/tradewinds/weather/_fetchers/iem_asos.py`:

```python
    # Defense-in-depth: validate station.code at the URL/path boundary BEFORE it goes
    # into the IEM URL param or the per-station cache subdirectory. StationInfo.code
    # is supposed to be a curated 3-letter no-K-prefix ICAO from the registry, but
    # the check at the boundary catches any registry corruption or mis-call.
    validate_icao_for_path(station.code, field="station.code")
    # Reversed-range guard (codex iter-1 HIGH): the underlying chunker honors
    # ``start > end -> []``, but the tradewinds-specific year-normalization
    # below would mask an inverted same-year range and fire a full-year
    # download. Mirror the chunker invariant at the caller boundary.
    if start > end:
        return []
    suffix = _REPORT_TYPE_SUFFIX[report_type]
    # Tradewinds-specific: normalize start to Jan 1 of its year so per-month callers
    # share a yearly cache key. PR #85's chunker uses max(current, start), which
    # floats the chunk_start with the caller — fine for one-shot backfills, wasteful
    # for tradewinds' per-month research.py loop. See module docstring "Deviation".
    normalized_start = date(start.year, 1, 1)
    chunks = yearly_chunks_exclusive_end(normalized_start, end)
```

Lines `iem_asos.py:197-202` (the reversed-range guard) and
`iem_asos.py:204-209` (the year-normalization line) are siblings — both
were added during the PR #85 lift to defend the caller boundary against
inputs the upstream chunker would otherwise mishandle.

### §4.2 Why it exists (the mostlyright PR #85 lift note)

- PR #85's upstream chunker
  (`yearly_chunks_exclusive_end(start, end)`) uses
  `chunk_start = max(current, start)` to float the first chunk's start
  with the caller's actual start date. That's correct for PR #85's
  one-shot backfill caller pattern: the caller wants a single contiguous
  multi-year fetch starting on a specific day, and the cache filename
  reflects that exact range.
- Tradewinds calls IEM in a **per-month research.py loop**
  (`_fetch_observations_range`, `research.py:362-516`). Without
  year-normalization, each per-month caller would issue
  `download_iem_asos(info, first, last, ...)` with a different
  `start = first` for every month, producing a different cache filename
  `iem_{first_iso}_{end_iso}_{suffix}.csv` for every one of 12 sibling
  callers in the same year. Net effect: 12 full-year fetches per year
  instead of 1.
- The chosen fix: normalize `start` to `date(start.year, 1, 1)` at the
  caller boundary BEFORE invoking the chunker. The chunker module itself
  remains PR-#85 verbatim. Cache filename becomes year-stable:
  `iem_YYYY-01-01_YYYY+1-01-01_{suffix}.csv`. Twelve sibling per-month
  callers in the same year do exactly 1 round trip — the first — and
  every subsequent per-month caller is a cache hit on `dest.exists()`
  (`iem_asos.py:218-221`).
- The cost: a single one-off small-window caller pays a full-year IEM
  bill (~13 MB at KNYC for both METAR + SPECI combined) to retrieve
  rows for only the requested month.
- Cite `CLAUDE.md` "Data + parity rules" — the source-priority and
  byte-faithful merge guarantees depend on the canonical yearly cache
  being stable across sibling callers. Any small-window mode in Part 2
  must NOT pollute this canonical cache.

### §4.3 The cost on small one-off windows

- A 1mo caller pays ~13.43 MB to retrieve 31 settlement-date rows.
  The 13 MB is the full year of METAR + SPECI CSV (~12 MB combined for
  KNYC 2024) + the GHCNh annual PSV (~1 MB) + the NWS CLI annual JSON
  (~460 KB). The parquet layer adds only kBs (2 monthly parquets +
  1 climate parquet, all small).
- A 3mo caller pays ~13.54 MB for 92 rows. The marginal cost of months
  2 and 3 vs the 1-month caller is only the additional parquet bytes —
  100 kB — because the source-layer downloads were already paid in
  full by the first month's call.
- This is the cost basis for Part 2's `strategy="exact_window"`: use
  IEM's native day-granular URL params (`year1/month1/day1` +
  `year2/month2/day2` — already supported by `_build_iem_url`,
  `iem_asos.py:96-125`) + a SEPARATE cache namespace so exact-window
  queries do not pollute the canonical yearly cache.
- **Explicit caveat:** `exact_window` is NOT a free win in a per-month
  research.py loop — it would defeat the canonical year cache by
  re-downloading per-month exact ranges from IEM, undoing the entire
  PR #85 lift. The decision is per-call (per top-level `obs(...)`
  invocation), not a global toggle. Part 2 must define both the
  decision-tree heuristic and the cache-namespace separation.

### §4.4 Parity-safety note

- Year-normalization changes only the **fetch window** sent to IEM and
  the resulting cache filename. It does NOT change the **merge policy**
  or **filter**. Post-parse, `_fetch_iem_month` filters parsed rows
  back to `(year, month)` via the `_observed_at_month` check
  (`research.py:253-255`):

  ```python
  for row in parse_iem_file(p, observation_type_override=override):
      if _observed_at_month(row.get("observed_at", "")) == (year, month):
          rows.append(row)
  ```

  Without this filter, the per-month merge loop would see Jan-Dec IEM
  rows mixed with the month's AWC + GHCNh slice, which changes the merge
  composition (and therefore tie-break order on strict-`>` priority
  comparisons) at month boundaries. The filter restores the exact merge
  input set the pre-PR-#85 monthly-chunker era produced.
- The 5-fixture byte-equivalent parity gate held end-to-end after PR
  #85's lift. See Phase 1.5 closeout in `STATE.md`: KNYC 5-year backfill
  ran 50.3 s against a 720 s (12 min) gate, and `research()` parity
  fixtures dropped from 97 s → 49 s post-PERF-04.
- **Year-normalization is cache-shape-only, NOT semantic.** Any Part-2
  `exact_window` mode that bypasses year-normalization must therefore
  also continue to honor the same post-parse month-boundary filter — or
  prove via parity replay that the alternate fetch shape still
  reproduces byte-identical merge outputs.

----------------------------------------------------------------------

## §5 What auto-planner modes need (forward-looking design constraints)

Each sub-section is **design constraints for Part 2 only**, not
implementation guidance. Part 2 chooses the surface; Part 1 fixes the
invariants Part 2 must honor.

### §5.1 `exact_window`

- Bypass `normalized_start = date(start.year, 1, 1)`
  (`iem_asos.py:208`) — invoke the underlying IEM endpoint with the
  caller's actual `start`/`end`. The `_build_iem_url` helper
  (`iem_asos.py:96-125`) already supports arbitrary day-granular
  windows; the bypass is at the caller boundary, not the URL layer.
- **Separate cache namespace** from the canonical yearly cache.
  Suggested form:
  `$HOME/.tradewinds/cache/v1/observations_exact/{STATION}/{start_iso}_{end_iso}.parquet`
  (Part 2 decides the final path; this is a constraint, not a design).
  Constraint rationale: the canonical yearly cache is shared by every
  per-month research.py caller in the same year; an exact-window file
  with a non-yearly name in the same directory tree would either be
  invisible (no cache hit for siblings) or actively corrupt
  (different shape mistakenly read by sibling callers).
- **Heuristic for when to choose:** window < ~90 days AND single-shot
  (no sibling per-month callers in the same year planned in this
  process). The 90-day threshold is the empirical break-even where the
  marginal cost of a full-year canonical fetch starts to dominate the
  per-day-of-data byte cost. Part 2 should validate this heuristic.
- **Win envelope:** up to ~12 MB saved for a 1-month query vs current
  behavior (the IEM CSV layer is the dominant byte cost). Wall-time win
  is harder to characterize — see §5.4 below; AWC + GHCNh + CLI also
  contribute to the cold-call time, so the network-time win materializes
  fully only when `source="iem"` is also requested.

### §5.2 `warm_cache`

- Keep current behavior end to end: year-normalization, canonical
  yearly cache key, 4-source prefetch via `_prefetch_sources`,
  sequential `_fetch_observations_range` + `_fetch_climate_range`
  assembly.
- **Heuristic for when to choose:** multi-month windows AND/OR repeated
  queries against the same station-year (research notebooks, backtest
  loops, walk-forward training data prep). Anything where multiple
  sibling per-month callers are planned in the same process or against
  the same on-disk cache.
- This mode IS the current `research()` path. `strategy="warm_cache"`
  must be byte-equivalent to today's behavior — the 5-fixture parity
  gate applies to this mode unchanged. Any divergence would invalidate
  the v0.1.0 v0.14.1 parity contract.

### §5.3 `hosted` (v0.2 seam)

- Bypass IEM + GHCNh + CLI entirely. Hit a precomputed low-latency
  endpoint (e.g., set via `TW_HOSTED_URL` env var or a
  `~/.tradewinds/config.toml` key).
- **v0.2 reserved seam** — do NOT implement in v0.1.0. Document the
  contract surface only:
  - Same arguments as `warm_cache` / `exact_window` (`station`,
    `from_date`, `to_date`, optional `tz_override`).
  - Same return DataFrame columns (settle for byte-identity of the
    `date`/`station`/`obs_*`/`cli_*` columns).
  - Optional provenance fields if the hosted manifest can carry them:
    `source_url` (e.g. the hosted endpoint URL), `source_etag` (manifest
    ETag at the time of the call).
- **Decision-tree note:** presence of `TW_HOSTED_URL` short-circuits
  other strategies ONLY when both (a) the env var is set AND (b) the
  requested window is fully covered by the hosted manifest's stated
  coverage range. Partial coverage falls through to `warm_cache` /
  `exact_window` per the normal heuristic.

### §5.4 `source="iem"` single-source path

- **Orthogonal to strategy mode.** `source=` controls which sources
  fire; `strategy=` controls which cache namespace is consulted. The
  matrix is `strategy ∈ {exact_window, warm_cache, hosted} × source ∈
  {iem, awc, ghcnh, all, ...}`. Part 2 chooses the source-shape
  (string vs set — see §6 Q4).
- Currently `research()` always fetches all 4 (IEM + AWC + GHCNh + CLI)
  via `_prefetch_sources` (`research.py:842-847`). There is no public
  way to opt out of any single source today.
- **Opt-out cost envelope per call:**
  - No AWC: saves ~110 KB + ~0.5 s (AWC is bandwidth-light; the
    `awc.live` worker only fires when `months_overlap_awc` is True, so
    most historical queries already pay zero here).
  - No GHCNh: saves ~10 MB per relevant year + ~2 s p50 download +
    parse.
  - No CLI: saves ~460 KB per relevant year + ~2 s p50 download (CLI is
    bandwidth-bound on its larger annual JSON payload).
- **Constraint:** single-source paths forfeit cross-source dedup. The
  CLAUDE.md "Source priority (LIVE_V1 observations): AWC > IEM > GHCNh"
  contract is what makes LIVE_V1 settlement-safe; with `source="iem"`
  only the orchestrator never sees the higher-priority AWC rows for
  in-window months. Auto-planner must surface this trade-off explicitly
  to the caller (e.g., via a docstring contract + an emitted log line),
  not hide it. The settlement-correctness implications are real —
  `source="iem"` is for research-mode users who know they want a
  single-source pull, not for production settlement code.

### §5.5 Mutable-period invariants (DO NOT TOUCH)

These invariants are non-negotiable. Every strategy mode
(`exact_window`, `warm_cache`, `hosted`) MUST honor them; the planner
phase has no latitude to relax them.

- `_is_writable_month` (`research.py:316-333`): UTC-strict-past-only
  gate at orchestrator layer. Closes the LST-vs-UTC partial-month race
  for negative-offset stations.
- `_is_current_lst_month` / `_is_current_lst_year` (`cache.py:194-211`):
  LST-current skip inside cache layer. Reads return `None`; writes
  no-op silently.
- Source-cache skip predicate is the **UNION** of "current LST" OR
  "not strictly past UTC". Both must clear. This is the union joining
  `_is_current_lst_month` (cache layer) with the
  `not _is_writable_month(...)` (orchestrator layer). See
  `research.py:457` and `research.py:566`.
- **Auto-planner constraint:** mutable periods are NEVER cached
  regardless of strategy. The `exact_window` cache namespace must
  apply the same union predicate before writing — that includes the
  `_partial` infix routing the IEM fetcher already uses for
  `chunk_end > today_utc` (`iem_asos.py:215-216`). An exact-window
  mode that skipped this check would let one user's mid-month query
  poison another user's settlement-bound research.

----------------------------------------------------------------------

## §6 Open questions for Part 2

Five concrete decisions for `/gsd-add-phase` + `/gsd-plan-phase` in
Part 2.

1. **Where does `tw.weather.obs()` live?**
   Proposal: `packages/weather/src/tradewinds/weather/obs.py` with a
   re-export at the top-level `tradewinds.weather.obs` public surface.
   Confirm or refine. Bringing a new public symbol into the
   `tradewinds-weather` distribution requires bumping its
   `__version__` and updating `scripts/check_wheel_metadata.py` if the
   sentinel changes. Naming nit: `obs` vs `observations` — the former
   matches the parquet path layout (`v1/observations/...`) but is a
   shorter name; the latter is more searchable. Part 2 picks.

2. **How does `strategy="auto"` decide?**
   Proposed decision tree:
   - `TW_HOSTED_URL` set AND window covered by hosted manifest →
     `hosted`
   - else `(to_date - from_date).days < 90` AND `source == "iem"` AND
     no sibling per-month callers detected → `exact_window`
   - else → `warm_cache`

   Confirm / refine the 90-day threshold and the "sibling per-month
   callers detected" detection heuristic. Detection is non-trivial in
   pure-Python: process-local state could track recently-called
   stations + years and prefer `warm_cache` when a hit is plausible.
   Part 2 must decide whether this detection is per-process,
   per-cache-root, or absent (caller declares intent explicitly via
   a kwarg). Empirical input: §3.3 finding #1 means the per-month-loop
   discount is real and is the entire reason `warm_cache` exists.

3. **Mutable-period interaction with `exact_window`.**
   Confirm that `exact_window` writes to a separate parquet cache
   namespace AND honors the same `_is_writable_month` +
   `_is_current_lst_*` gates as `warm_cache`. The union skip
   predicate (`research.py:457, 566`) is non-negotiable — see §5.5.
   Open detail: how does an `exact_window` cache key handle a window
   that straddles the mutable-period boundary (e.g., a 30-day query
   that crosses the current UTC month)? Two options:
   1. Refuse the write entirely (matches today's `iem_ok and
      _is_writable_month` gate at month granularity).
   2. Split the parquet at the boundary and write only the strictly-past
      tail.

   Part 2 picks. The orchestrator-level partial-month race
   (`research.py:316-333` docstring) MUST stay closed regardless.

4. **`source=` keyword shape.**
   Should `source` be a string (`"iem"`, `"awc"`, `"all"`) or a set
   (`{"iem", "ghcnh"}`)? Trade-offs:
   - String: maps cleanly to a single provenance field on output rows;
     fewer cardinality edge cases; matches mostlyright's older
     `source_filter=` shape.
   - Set: gives compositional power — e.g., "IEM + GHCNh but skip AWC"
     for users who don't need live live observations. More test
     surface; provenance gets murkier (each row's `source` field still
     resolves to a single string, but the input filter is plural).

   The merge layer's source-priority logic (`AWC > IEM > GHCNh`) works
   either way; what changes is the public surface ergonomics. Part 2
   decides. Note: `source="all"` is the byte-equivalent shorthand for
   today's behavior.

5. **Migration path from `research()` → `tw.weather.obs()`.**
   Does `research()` become a thin wrapper that calls
   `obs(..., strategy="warm_cache")` + the climate join + `build_pairs`?
   Or do `research()` and `obs()` stay as independent surfaces?
   - Wrapper path: less code, single canonical implementation, but
     `obs()` must support every kwarg `research()` does
     (`tz_override`, `forecast_model`, `as_dataframe`). The climate
     fetch + `settlement_date_for` grouping + `build_pairs` logic
     stays in `research.py`, just consumes `obs()` rows.
   - Independent path: `research()` keeps its current shape; `obs()`
     is a new surface for users who want observations without the
     CLI climate join. Two implementations of the observation
     prefetch + assembly logic; risk of drift.

   Affects how much of `research.py`'s orchestration logic moves into
   `obs.py`. The wrapper path is the GSD-style "single source of
   truth" choice; the independent path is the lower-risk parity-safety
   choice (zero changes to the byte-equivalent `research()` parity
   gate). Part 2 picks.

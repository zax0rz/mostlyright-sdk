---
phase: 260524-ohu
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - .planning/research/INGEST-PLANNER-RESEARCH.md
autonomous: true
requirements:
  - QUICK-260524-ohu
---

<objective>
Write a single research/documentation markdown file at
`.planning/research/INGEST-PLANNER-RESEARCH.md` capturing the empirical
timing data + architectural map for the current `tradewinds.research()`
ingest path. This doc is Part 1 of a two-part task — Part 2 will use
`/gsd-add-phase` + `/gsd-plan-phase` to design
`tw.weather.obs(..., strategy="auto")`, and consumes this doc as its
empirical foundation.

Purpose: Give the planner phase (Part 2) a single source of truth for
file:line refs, measured cold/warm timings + bytes, year-normalization
rationale, mutable-period invariants, and the open design questions that
the auto-planner strategy modes (`exact_window` / `warm_cache` / `hosted`)
must answer.

Output: One markdown file (~400-600 lines). No code changes to
`research.py` or any fetcher. No script committed. No tests added.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
</execution_context>

<context>
@.planning/STATE.md
@./CLAUDE.md
@.planning/research/SOURCE-LIMITS.md
@packages/core/src/tradewinds/research.py
@packages/weather/src/tradewinds/weather/_fetchers/iem_asos.py
@packages/weather/src/tradewinds/weather/cache.py
</context>

<tasks>

<task type="auto">
  <name>Task 1: Write INGEST-PLANNER-RESEARCH.md (six sections)</name>
  <files>.planning/research/INGEST-PLANNER-RESEARCH.md</files>
  <action>
Create a single new markdown file at
`.planning/research/INGEST-PLANNER-RESEARCH.md` with exactly six top-level
sections in the order below. Target length ~400-600 lines.

Front-matter / title block:
- H1: `# Ingest Planner Research — empirical foundation for `tw.weather.obs(strategy="auto")``
- A 1-2 line preamble naming this as Part 1 of a two-part task (Part 2:
  `/gsd-add-phase` + `/gsd-plan-phase` to design the auto-planner).
- Date stamp: 2026-05-24. Machine: macOS aarch64-darwin.

----------------------------------------------------------------------
## §1 Executive summary (~10 lines)

One-liner finding + headline numbers. Must include:
- The single most important empirical finding: **the 1-month and 3-month
  cold downloads transfer essentially the same bytes (13.43 MB vs 13.54 MB)
  because the IEM ASOS fetcher year-normalizes the request window** —
  small windows do NOT shrink network footprint under current behavior.
- The 12-month case doubles bytes (26.01 MB) only because
  `extended_to=2025-01-01` forces a 2-year IEM + GHCNh fetch.
- Warm re-fetch is free (`delta_bytes=0`) for every window size — the
  full-cached path is honored.
- The 1-month cold-time anomaly (69.7s vs 3mo's 10.17s) is one-shot
  process startup (Python + pandas + pyarrow + httpx pool warmup), NOT
  proportional to window size.
- Single-line forward pointer: the auto-planner (Part 2) needs at minimum
  `strategy="exact_window"` for one-off small queries to bypass
  year-normalization and save up to ~12 MB.

----------------------------------------------------------------------
## §2 Current architecture (file:line refs)

Map the live `research()` ingest path with concrete file:line citations.
Every bullet must include a path + line range. Use this exact set of
refs (already validated against the worktree):

- **Orchestrator entry:** `packages/core/src/tradewinds/research.py:876-1024`
  — top-level `research(...)` function; computes `extended_to`, calls
  `_prefetch_sources`, then `_fetch_observations_range` +
  `_fetch_climate_range`, then merges.
- **Prefetch (4-way parallel):**
  `packages/core/src/tradewinds/research.py:650-873` — `_prefetch_sources()`
  uses a `ThreadPoolExecutor(max_workers=4)` to fire IEM, NWS CLI, GHCNh,
  AWC concurrently (Option-C per `.planning/research/SOURCE-LIMITS.md`).
  Note the Pitfall-6 timing pattern (capture `submitted_at` immediately
  after `ex.submit()`) and the narrow-except contract
  (`httpx.HTTPStatusError`, `httpx.RequestError`, `OSError` only).
- **Observations range fetch:**
  `packages/core/src/tradewinds/research.py:362-516` —
  `_fetch_observations_range()`. Iterates months; lazy per-year GHCNh
  load; FileLock-guarded parquet read/write.
- **Climate range fetch:**
  `packages/core/src/tradewinds/research.py:519-623` —
  `_fetch_climate_range()`. Per-station-year NWS CLI JSON.
- **Zero-network gate:**
  `packages/core/src/tradewinds/research.py:626-647` —
  `_all_caches_warm()` returns True when every requested
  (station, month) parquet is on disk AND every requested
  (station, year) climate parquet is on disk → fully cached re-runs touch
  zero network.
- **IEM ASOS fetcher:** `packages/weather/src/tradewinds/weather/_fetchers/iem_asos.py`
  - Year-normalization: `iem_asos.py:204-209` — caller's `start` is
    rewritten to `date(start.year, 1, 1)` BEFORE the chunker runs.
    Tradewinds-specific deviation from mostlyright PR #85 verbatim; the
    intent is per-month caller cache idempotence (a yearly canonical
    cache key shared across all per-month research.py callers in a
    given year). Quote the exact comment from lines 204-208 inline in
    a fenced block.
  - Cache filename: `iem_{start_iso}_{end_iso}_{suffix}.csv` is the
    canonical form; the `_partial` infix is injected when
    `chunk_end > today_utc` OR `skip_cache=True` (forward reference to
    iem_asos.py:215-216 `chunk_is_partial` OR-not-AND predicate;
    Pitfall-3 mention).
- **Other adapters (one-liners):**
  - **AWC:** 168h live fetch window; in-memory only; no disk cache.
  - **GHCNh:** per-station-year PSV (~1-10 MB each).
  - **IEM CLI (climate):** per-station-year JSON.
- **Parquet cache:**
  `$HOME/.tradewinds/cache/v1/observations/{STATION}/{YYYY}/{MM}.parquet`
  and `$HOME/.tradewinds/cache/v1/climate/{STATION}/{YYYY}.parquet`.
  FileLock-guarded atomic write at
  `packages/weather/src/tradewinds/weather/cache.py:230-253`.
- **Mutable-period invariants (load-bearing):**
  - `_is_writable_month`: `packages/core/src/tradewinds/research.py:316-333`
    — gate at the orchestrator layer; UTC-strict-past-only;
    closes the LST-vs-UTC race the codex iter-2 P2 review caught (quote
    the docstring rationale).
  - `_is_current_lst_month` / `_is_current_lst_year` in
    `packages/weather/src/tradewinds/weather/cache.py` — LST-current skip
    inside cache layer.
  - Source-cache skip predicate is the **UNION** of "current LST" OR
    "not strictly past UTC" — both predicates must clear before a row
    is allowed to enter the parquet cache.

----------------------------------------------------------------------
## §3 Empirical timing (the bench + interpretation)

Three sub-sections.

### §3.1 Methodology
- Bench script lived at `/tmp/tw_ingest_bench.py` (NOT committed; describe
  only). Methodology: clean `$HOME/.tradewinds/cache/` between cases;
  measure cold (empty cache) and warm (immediately-rerun) wall time +
  delta bytes on disk in `$HOME/.tradewinds/cache/`.
- Test station: KNYC. Three windows: 1mo (2024-03-01..2024-03-31), 3mo
  (2024-03-01..2024-05-31), 12mo (2024-01-01..2024-12-31).
- Raw bench JSON at `/tmp/tw_bench_results.json` (NOT committed; inline
  the relevant numbers below).
- Machine: macOS aarch64-darwin, 2026-05-24 morning, live APIs.

### §3.2 Results table

Inline a fenced block reproducing the three cases verbatim from the
benchmark output:

```
=== 1mo (KNYC, 2024-03-01..2024-03-31) ===
  cold: 69.7s, rows=31, delta=13.43 MB
  warm: 4.72s, delta=0.0 MB
  IEM CSV files: ['iem_2024-01-01_2025-01-01_metar.csv', 'iem_2024-01-01_2025-01-01_speci.csv']
  GHCNh PSV files: ['GHCNh_USW00094728_2024.psv']
  CLI JSON files: ['cli_2024.json']
  obs_parquets: 2 -> ['v1/observations/KNYC/2024/03.parquet', 'v1/observations/KNYC/2024/04.parquet']
  clim_parquets: ['v1/climate/KNYC/2024.parquet']
=== 3mo (KNYC, 2024-03-01..2024-05-31) ===
  cold: 10.17s, rows=92, delta=13.54 MB
  warm: 0.35s, delta=0.0 MB
  IEM CSV files: ['iem_2024-01-01_2025-01-01_metar.csv', 'iem_2024-01-01_2025-01-01_speci.csv']
  GHCNh PSV files: ['GHCNh_USW00094728_2024.psv']
  CLI JSON files: ['cli_2024.json']
  obs_parquets: 4 -> ['v1/observations/KNYC/2024/03.parquet', '...04', '...05', '...06']
  clim_parquets: ['v1/climate/KNYC/2024.parquet']
=== 12mo (KNYC, 2024-01-01..2024-12-31) ===
  cold: 23.69s, rows=366, delta=26.01 MB
  warm: 0.56s, delta=0.0 MB
  IEM CSV files: 2024 + 2025 full years (4 CSVs)
  GHCNh PSV files: 2024 + 2025 (2 PSVs)
  CLI JSON files: ['cli_2024.json']
  obs_parquets: 13 -> 2024-01..12 + 2025-01 (extended_to spill)
  clim_parquets: ['v1/climate/KNYC/2024.parquet']
```

### §3.3 Interpretation (the empirical findings)

Five interpretive bullets — each tied to a specific number from §3.2.

1. **1mo ≈ 3mo bytes (13.43 vs 13.54 MB).** Year-normalization
   (iem_asos.py:204-209) forces the full IEM 2024-01-01..2025-01-01 window
   regardless of caller window size. GHCNh is per-station-year, so the
   same `GHCNh_USW00094728_2024.psv` lands either way. Climate is
   per-station-year too (`cli_2024.json`). Net: 1mo callers pay the same
   bytes as a 3mo caller. **This is the single fact that motivates
   `strategy="exact_window"` in Part 2.**
2. **12mo doubles bytes (26.01 MB).** `extended_to=2025-01-01` spills into
   year 2: a second IEM yearly chunk + a second GHCNh PSV fire. The 13th
   obs parquet (`2025/01.parquet`) is the extended_to artifact.
3. **1mo cold-time anomaly (69.7s vs 3mo's 10.17s).** Not proportional to
   window. One-shot process startup: Python interpreter, pandas import,
   pyarrow import, httpx connection-pool warmup. Subsequent fetches in
   the same process amortize this. Document so the planner doesn't
   over-weight 1mo cold timings.
4. **Warm always free (`delta=0.0 MB`).** `_all_caches_warm`
   (research.py:626-647) gates the no-network path. Warm wall-times of
   0.35s/0.56s reflect pyarrow parquet reads + the merge, not HTTP.
5. **Rows scale linearly, bytes do not.** 31 → 92 → 366 rows. Bytes
   13.43 → 13.54 → 26.01 MB. Confirms the year-quantization story end to
   end.

----------------------------------------------------------------------
## §4 Year-normalization deep dive

Three sub-sections.

### §4.1 The code
- Quote `iem_asos.py:204-209` verbatim inside a fenced Python block (the
  comment + the `normalized_start = date(start.year, 1, 1)` line).
- Pair it with `iem_asos.py:197-202` (the reversed-range guard) since
  these two lift modifications are siblings.

### §4.2 Why it exists (the mostlyright PR #85 lift note)
- PR #85's upstream chunker uses `max(current, start)` to float the
  chunk_start with the caller — fine for one-shot backfills.
- Tradewinds calls IEM in a per-month research.py loop. Without
  year-normalization each month-call would touch a different
  `iem_{start_iso}_{end_iso}_{suffix}.csv` filename, defeating the cache
  for any subsequent call in the same year.
- The cost: every per-month caller fetches a full canonical year's worth
  of CSVs once, then shares them. The benefit: 12 sibling per-month
  callers in the same year do exactly 1 round trip (the first).
- Cite CLAUDE.md "Data + parity rules" section — the source-priority and
  byte-faithful merge guarantees depend on the canonical yearly cache
  being stable.

### §4.3 The cost on small one-off windows
- A 1mo caller pays a full-year IEM bill (~13 MB) to get 31 rows.
- This is the cost basis for Part 2's `strategy="exact_window"`: use
  IEM's native day-granular URL params + a separate cache namespace so
  these queries don't pollute the canonical yearly cache.
- Explicitly note: `exact_window` is NOT a free win in a per-month
  research.py loop — it would defeat the canonical year cache. Per-call
  decision, not a global toggle.

### §4.4 Parity-safety note
- Year-normalization changes only the **fetch window**, not the **merge
  policy** or **filter**. Post-parse, `_fetch_iem_month`
  (research.py side) filters back down to the requested month. The
  5-fixture byte-equivalent parity gate held end-to-end after PR #85's
  lift (cite Phase 1.5 closeout in STATE.md: KNYC 5-year 50.3s vs 720s
  gate; research() 97s → 49s post-PERF-04). Year-normalization is
  cache-shape-only, NOT semantic.

----------------------------------------------------------------------
## §5 What auto-planner modes need (forward-looking design constraints)

Four sub-sections — one per strategy mode + one for the
mutable-period invariant. Each sub-section is design constraints for
Part 2 ONLY (no implementation guidance).

### §5.1 `exact_window`
- Bypass `normalized_start = date(start.year, 1, 1)` (iem_asos.py:208) —
  call IEM with the caller's actual `start`/`end`.
- Separate cache namespace from canonical yearly cache. Suggested form:
  `$HOME/.tradewinds/cache/v1/observations_exact/{STATION}/{start_iso}_{end_iso}.parquet`
  (Part 2 plan decides final path; this is a constraint, not a design).
- Heuristic for when to choose: window < ~90 days AND single-shot (no
  sibling per-month calls in the same year planned).
- Win envelope: up to ~12 MB saved for a 1-month query vs current
  behavior; up to ~3-5s wall time when AWC/GHCNh/CLI are also skipped
  (see §5.4 single-source).

### §5.2 `warm_cache`
- Keep current behavior end to end: year-normalization, canonical yearly
  cache key, 4-source prefetch.
- Heuristic for when to choose: multi-month windows AND/OR repeated
  queries against the same station-year (research notebooks,
  backtest loops).
- This mode IS the current `research()` path — `strategy="warm_cache"`
  must be byte-equivalent to today's behavior.

### §5.3 `hosted` (v0.2 seam)
- Bypass IEM/GHCNh/CLI entirely. Hit a precomputed low-latency endpoint
  (e.g. set via `TW_HOSTED_URL` env var).
- v0.2 reserved seam — do NOT implement in v0.1.0. Document the
  contract surface only: same arguments, same return DataFrame columns,
  optional `source_url` / `source_etag` provenance fields.
- Decision tree note: presence of `TW_HOSTED_URL` short-circuits other
  strategies when it's set AND the requested window is fully covered by
  the hosted manifest.

### §5.4 `source="iem"` single-source path
- Orthogonal to strategy mode — controls which sources fire, not which
  cache namespace.
- Currently `research()` always fetches all 4 (IEM + AWC + GHCNh + CLI).
- Opting out of AWC + GHCNh + CLI saves ~1-2 MB + ~3-5s per call (no AWC
  168h HTTP, no GHCNh ~5 MB PSV download, no CLI JSON).
- Constraint: single-source path forfeits cross-source dedup
  (Pitfall: source-priority is what makes LIVE_V1 settlement-safe).
  Auto-planner must surface this trade-off to caller, not hide it.

### §5.5 Mutable-period invariants (DO NOT TOUCH)
- `_is_writable_month` (research.py:316-333): UTC-strict-past-only gate
  at orchestrator layer. Closes the LST-vs-UTC partial-month race.
- `_is_current_lst_month` / `_is_current_lst_year` (cache.py): LST-current
  skip inside cache layer.
- Source-cache skip predicate is **UNION** of "current LST" OR
  "not strictly past UTC". Both must clear.
- **Auto-planner constraint:** every strategy mode (`exact_window`,
  `warm_cache`, `hosted`) MUST honor these. Mutable periods are NEVER
  cached regardless of strategy. The `exact_window` cache namespace
  must apply the same predicate before writing.

----------------------------------------------------------------------
## §6 Open questions for Part 2

Five open questions — these are inputs to the
`/gsd-add-phase` + `/gsd-plan-phase` work in Part 2. Each phrased as a
concrete decision the planner must make.

1. **Where does `tw.weather.obs()` live?** Proposal:
   `packages/weather/src/tradewinds/weather/obs.py` with re-export at
   `tradewinds.weather.obs` (top-level public surface). Confirm or
   refine.
2. **How does `strategy="auto"` decide?** Proposed decision tree:
   - `TW_HOSTED_URL` set AND window covered by hosted manifest → `hosted`
   - else window < 90 days AND `source="iem"` AND no sibling per-month
     callers detected → `exact_window`
   - else → `warm_cache`
   Confirm/refine the thresholds and the per-month-caller detection
   heuristic.
3. **Mutable-period interaction with `exact_window`.** Confirm that
   `exact_window` writes to a separate parquet cache namespace AND
   honors the same `_is_writable_month` + LST-current gates as
   `warm_cache`. Invariants unchanged.
4. **`source=` keyword shape.** Should `source` be a string
   (`"iem"`, `"awc"`, `"all"`) or a set (`{"iem", "ghcnh"}`)? Single
   string maps cleanly to provenance; set gives compositional power.
   Part 2 decides.
5. **Migration path from `research()` → `tw.weather.obs()`.** Does
   `research()` become a thin wrapper that calls
   `obs(..., strategy="warm_cache")` + climate join? Or do they stay
   independent surfaces? Affects how much of research.py's
   orchestration logic moves into obs.py.

----------------------------------------------------------------------

Style + format rules:
- Use H1 for title, H2 for §1..§6, H3 for sub-sections.
- All file:line refs as backtick-quoted relative paths.
- Inline quoted code blocks for the year-normalization comment + the
  empirical results table.
- No tables unless cleaner than a list (results table OK; everything
  else as bulleted lists).
- Target 400-600 lines total. Density is fine — the planner phase
  will consume this end to end.
- Do NOT add a "Conclusion" or "Recommendations" section — §6
  is the handoff.
- Do NOT modify `research.py`, any fetcher, `cache.py`, or any test.
- Do NOT commit the bench script or `/tmp/tw_bench_results.json`.
- Do NOT add a `must_haves` block or any planning frontmatter to the
  research doc itself — it is a research artifact, not a plan.
  </action>
  <verify>
    <automated>test -f .planning/research/INGEST-PLANNER-RESEARCH.md && grep -c "^## §" .planning/research/INGEST-PLANNER-RESEARCH.md | grep -qx 6 && grep -q "iem_asos.py:204-209" .planning/research/INGEST-PLANNER-RESEARCH.md && grep -q "13.43 MB" .planning/research/INGEST-PLANNER-RESEARCH.md && grep -q "research.py:316-333" .planning/research/INGEST-PLANNER-RESEARCH.md && grep -q "strategy=\"exact_window\"\\|exact_window" .planning/research/INGEST-PLANNER-RESEARCH.md && wc -l .planning/research/INGEST-PLANNER-RESEARCH.md | awk '{ if ($1 < 300 || $1 > 800) { print "LENGTH OUT OF RANGE: " $1; exit 1 } else { print "OK: " $1 " lines" } }'</automated>
  </verify>
  <done>
    File `.planning/research/INGEST-PLANNER-RESEARCH.md` exists with:
    - Exactly 6 H2 sections (`## §1` .. `## §6`)
    - file:line references including `iem_asos.py:204-209` and
      `research.py:316-333`
    - The empirical results block including `13.43 MB`
    - At least one mention of `exact_window` (the Part-2 forward pointer)
    - Length between 300 and 800 lines
    No code files modified. No bench script committed.
  </done>
</task>

</tasks>

<verification>
- File exists at the exact path `.planning/research/INGEST-PLANNER-RESEARCH.md`.
- All six sections present in order (§1 Executive, §2 Architecture,
  §3 Empirical timing, §4 Year-normalization, §5 Auto-planner modes,
  §6 Open questions).
- Every file:line citation in §2 matches what the
  worktree contains (already validated during planning).
- No edits to `research.py`, fetchers, or `cache.py`.
- No new tests, no committed scripts, no other markdown files touched.
</verification>

<success_criteria>
- `.planning/research/INGEST-PLANNER-RESEARCH.md` is committed and reads
  as a self-contained empirical foundation for Part 2.
- A Part-2 planner reading this doc alone (no other context) can
  produce a `tw.weather.obs(strategy="auto")` plan with no ambiguity
  about: what the current path does, where it lives in code, what it
  costs over the wire, why year-normalization exists, what each
  strategy mode must do, and which invariants are non-negotiable.
</success_criteria>

<output>
After completion, the file `.planning/research/INGEST-PLANNER-RESEARCH.md`
is the deliverable. No SUMMARY.md required for this quick task.
</output>

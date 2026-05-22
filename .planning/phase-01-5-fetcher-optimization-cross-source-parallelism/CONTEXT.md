---
phase: 01-5-fetcher-optimization-cross-source-parallelism
type: context
gathered: 2026-05-22
status: ready-for-planning
source: orchestrator-brief + ROADMAP.md
---

# Phase 1.5: Fetcher Optimization + Cross-Source Parallelism — Context

**Gathered:** 2026-05-22
**Status:** Ready for planning
**Source:** Inline orchestrator brief (2026-05-22) + ROADMAP.md Phase 1.5 section (lines 37-53)

<domain>
## Phase Boundary

Make ingestion fast by default. Two work streams, strictly serial after Phase 1 (parity gate green, alpha1 published) and strictly before Phase 2.

**Stream A — Lift `mostlyright` PR #85 (commit `cf9eb85`, 2026-05-12):**
1. **PERF-01** IEM ASOS + MOS chunk size monthly → 365 days; calendar-aligned via shared `_iem_chunks()` helper (leap-year safe).
2. **PERF-02** Cache-poison fix: IEM CSV staging cache filename encodes full chunk window (`iem_{start_iso}_{end_iso}_{suffix}.csv`) inside `_fetchers/iem_asos.py`. `skip_cache=True` **OR** `chunk_end > today_utc` (where `today_utc = datetime.now(timezone.utc).date()`, NOT `date.today()`) routes to `_partial` namespace that backfill never reads. Distinct from `tradewinds.weather.cache`'s path-based parquet cache (untouched). *(Corrected 2026-05-22 per RESEARCH.md from PR #85 diff: condition is `OR` not `AND`; cutoff is UTC-aware to avoid Europe/Prague silent-data-loss bug.)*
3. **PERF-03** `HTTP_TIMEOUT` 30s → 60s in `_internal._http` to match the 12x payload increase per chunk.

**Stream B — New code:**
4. **PERF-04** `research.py` orchestrator fires AWC + IEM + GHCNh + NWS CLI concurrently for the same time window via `concurrent.futures.ThreadPoolExecutor` (max_workers=4, one per source).
5. **PERF-05** AWC + GHCNh rate-limit headroom verified via one-shot spike → `.planning/research/SOURCE-LIMITS.md` documenting max concurrent connections and actual response-size measurements (1-year, 5-year requested where API permits). Spike script kept under `spike/source_limits/` for v0.2 re-validation.

**Out of scope:** v0.2 async refactor of catalog adapters (CLAUDE.md: stay sync in v0.1, revisit async only if multi-station fetches bottleneck). Cache filename change applies only to the IEM CSV staging cache inside the fetcher; the user-facing parquet cache (`v1/observations/{station}/{YYYY}/{MM}.parquet`) is untouched.
</domain>

<decisions>
## Implementation Decisions (LOCKED)

### Concurrency primitive — threads, not asyncio
- **Locked:** `concurrent.futures.ThreadPoolExecutor` with `max_workers=4` (one per source) for cross-source parallelism in `research.py`.
- **Rationale:** CLAUDE.md technology-stack section explicitly defers asyncio to v0.2 ("Stay sync in v0.1. Revisit async in v0.2 if multi-station fetches become a bottleneck"). httpx supports both sync and async APIs; staying sync preserves byte-equivalence path and avoids restructuring the v0.14.1 lift surface. Threads are sufficient for 4-way I/O-bound parallelism.
- **Forbid:** any `asyncio`, `httpx.AsyncClient`, `async def` in Phase 1.5 deliverables.

### Sequencing — strictly serial, not co-executed with Phase 2 Wave 1
- **Locked:** Phase 1.5 runs strictly after Phase 1 (parity gate green, alpha1 published) and strictly before Phase 2. No co-execution with Phase 2 Wave 1.
- **Rationale:** Architect review rejected co-execution: both phases touch `_internal/_http.py` import graph (Wave 1 `_v02 → core` git-mv vs PERF-03 timeout bump). Concurrent edits on `merged-vision` guarantee rebase conflicts on parity-fixture test runs.

### Lift fidelity — from PR #85, NOT from monorepo head
- **Locked:** All PERF-01/02/03 changes lift from `mostlyright` PR #85 (commit `cf9eb85`, 2026-05-12). Diff must be reviewable against that exact commit.
- **Forbid:** any lift from monorepo HEAD (currently at v0.17.0 with diverged behavior — Open-Meteo removal, settlement_v1 intake, etc., per CLAUDE.md).
- **Rationale:** PR #85 patches were empirically validated on the same v0.14.1 codebase tradewinds is built on; HEAD has unrelated breaking changes.

### Parallelism check threshold
- **Locked:** `wall_time ≤ max(per_source_t_i) * 1.2` (proves no serial stall).
- **Rejected (architect):** earlier `≤ 45% of sum` threshold — mathematically invalid when per-source times are uneven (max-source dominates the sum).
- **How to apply:** assertion lives in a recorded-fixture integration test, not a unit test (real timings only meaningful against real-ish responses).

### Empirical performance gate
- **Locked:** KNYC 5-year ASOS backfill ≤ 12 min wall time at unchanged 1 req/sec politeness. (PR #85 measured 10 min; 20% headroom.)
- **Other-station regression:** pick one of {KMDW, KLAX, KMIA} from parity fixtures and confirm backfill within station-specific empirical wall time recorded during the Phase 1.5 spike. NO fixed cross-station threshold (per architect review).

### Cache scope — fetcher-internal CSV staging only
- **Locked:** PERF-02 cache-filename change applies ONLY to `_fetchers/iem_asos.py`'s raw-CSV staging cache. The user-facing parquet cache at `v1/observations/{station}/{YYYY}/{MM}.parquet` (under `tradewinds.weather.cache`) is UNTOUCHED by Phase 1.5.
- **Rationale:** Two different caches with different invariants. Parquet cache is path-based (filename = month) and already filelock-guarded. CSV staging cache is opaque-name (the bug PR #85 fixed).

### Parity gate handling — re-run all 5 fixtures pre-merge
- **Locked:** Before Phase 1.5 merges to `merged-vision`, re-run all 5 parity fixtures against 365-day-chunked `research()` output. Phase doesn't merge until parity green.
- **If parity drift:** decide post-spike between (a) revert chunk-size change, or (b) change `_internal/merge/observations.py` from strict `>` to `>=` with deterministic secondary key (`source` then `chunk_start`) and re-validate. Both paths acceptable; decision is empirical, not pre-committed.
- **Why this matters:** chunk size affects request pattern → row iteration order from fetcher → tie-resolution in merge (strict `>` is first-row-seen-wins on same-priority ties: SPECI-vs-METAR at same `(station, observed_at, observation_type)`, cross-source same-priority).

### Rate-limit spike documentation lives in `.planning/research/`
- **Locked:** SOURCE-LIMITS.md committed under `.planning/research/SOURCE-LIMITS.md`. Spike scripts under `spike/source_limits/` (project root, version controlled, NOT in tests/).
- **Rationale:** spike output is planning/research artifact (informs future v0.2 limits), not test code. Script kept so re-validation is one command.

### Review panel — temporarily 3 reviewers
- **Locked:** codex `high` + python-architect + security for Phase 1.5 PRs. Reason: chunk-size + cache-filename + timeout changes are parity-critical AND security-adjacent (HTTP timeout × payload-size attack surface).
- **Codex effort:** `high` (the only tier per REVIEW-DISCIPLINE.md — no second-pass at lower effort).
- **Reverts after Phase 1.5:** Phase 2 returns to standard 2-reviewer panel per REVIEW-DISCIPLINE.md.

### IEM rate-limit risk added 2026-05-22 (from RESEARCH.md)
- **NEW RISK:** IEM published a 1-sec per-IP throttle on 2026-04-21. Both ASOS (`asos.py`) and IEM-MOS (`cli.py`) hit `mesonet.agron.iastate.edu` — likely shared IP budget. The `max_workers=4` design includes TWO IEM threads, each `time.sleep(1.0)`-paced, totaling 2 req/sec to IEM — possibly 503-triggering.
- **Decision deferred to PERF-05 spike output:** three mitigation paths documented in RESEARCH.md (A: shared IEM lock; B: drop to max_workers=3 and serialize IEM ASOS+MOS; C: rely on spike empirical data to size the gap). Planner MUST sequence PERF-05 (spike) BEFORE PERF-04 (parallelism) so the spike informs the choice.

### Claude's Discretion
- Exact name of the shared `_iem_chunks()` helper and its module location (likely `tradewinds.weather._fetchers._iem_chunks` or `tradewinds.weather._fetchers.iem_asos`). Planner picks.
- Whether Phase 1.5 creates a `research.py` stub or postpones to Phase 3 — RESEARCH.md recommends Phase 1.5 stub with "Phase 3 will extend" docstring. Planner confirms.
- Granularity of plan files: planner decides 1 plan vs N (recommendation: separate plan per PERF requirement OR group lift-from-PR-85 into one + parallelism into one + spike into one).
- Whether the rate-limit spike (PERF-05) runs before or after PERF-04 within Phase 1.5. Both orderings work; planner picks based on dependency analysis.
- Exact assertion form for `wall_time ≤ max(per_source_t_i) * 1.2` (pytest fixture + timing helper, or inline `time.monotonic()` + assert). Planner picks.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase scope + sequencing
- `.planning/ROADMAP.md` (lines 17, 37-53) — Phase 1.5 section, success criteria, review-panel note, parity-gate handling
- `.planning/REQUIREMENTS.md` (PERF-01..05 rows + footer) — formal requirements text
- `.planning/REVIEW-DISCIPLINE.md` — review loop mechanics, severity gate, never-skip path list

### Source repo for lift
- `../monorepo-v0.14.1/` (NOT monorepo HEAD) — v0.14.1 codebase tradewinds was lifted from
- PR #85 (`mostlyright` repo, commit `cf9eb85`, 2026-05-12) — the empirically validated patches to lift. PERF-01/02/03 all originate here.

### Files that will be modified (forewarning to planner)
- `packages/weather/src/tradewinds/weather/_fetchers/iem_asos.py` — chunk size + cache filename (PERF-01, PERF-02)
- `packages/weather/src/tradewinds/weather/_fetchers/` (new helper module) — shared `_iem_chunks()` calendar-aligned chunker
- `packages/core/src/tradewinds/_internal/_http.py` — HTTP_TIMEOUT 30 → 60 (PERF-03)
- `packages/core/src/tradewinds/research.py` — ThreadPoolExecutor orchestration (PERF-04)
- `.planning/research/SOURCE-LIMITS.md` (new) — spike output (PERF-05)
- `spike/source_limits/` (new) — spike scripts (PERF-05)

### Reference implementation patterns (project-internal)
- `packages/weather/src/tradewinds/weather/cache.py` — existing parquet cache pattern (NOT to be modified; reference for "what good cache code looks like in this repo")
- Existing fetcher modules (`_fetchers/awc.py`, `_fetchers/ghcnh.py`, `_fetchers/cli.py`) — sync httpx pattern that ThreadPoolExecutor will parallelize

### Constraints from CLAUDE.md
- Tech stack section: `httpx>=0.28,<1.0`, `pandas>=2.2,<3.0`, "Stay sync in v0.1" — no asyncio in catalog adapters.
- TDD mandatory (RED → GREEN → REFACTOR). Pre-commit + pre-push hooks; no `--no-verify`.

</canonical_refs>

<specifics>
## Specific Ideas

- **Chunk helper API:** `_iem_chunks(start: date, end: date) -> Iterator[tuple[date, date]]`. Yields 365-day windows, leap-year-safe via calendar arithmetic (not `timedelta(days=365)`). Final chunk truncated to `end`.
- **Cache filename pattern:** `iem_{start_iso}_{end_iso}_{suffix}.csv` where `suffix` distinguishes ASOS vs MOS variants. The `_partial` namespace for in-progress chunks goes in a sibling subdirectory, NOT a prefix on the filename (cleaner separation).
- **ThreadPoolExecutor idiom (sketch — planner to verify):**
  ```python
  with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
      futures = {
          ex.submit(_fetch_observations, station, start, end): "observations",
          ex.submit(_fetch_iem_mos, station, start, end): "iem_mos",
          ex.submit(_fetch_ghcnh, station, start, end): "ghcnh",
          ex.submit(_fetch_cli, station, start, end): "cli",
      }
      results = {name: f.result() for f, name in futures.items()}
  ```
  Exceptions surface from `.result()` — no swallowing. Per-source timeouts handled by httpx's `HTTP_TIMEOUT` at the request level, not the executor level.
- **Spike scope:** `spike/source_limits/awc_concurrent.py` and `spike/source_limits/ghcnh_concurrent.py`. Each fires N parallel requests (N ∈ {2, 4, 8, 16}), measures p50/p95/p99 response time + any 429/5xx counts, writes results to stdout in a format SOURCE-LIMITS.md can paste.

</specifics>

<deferred>
## Deferred Ideas

- **Async refactor** — explicitly v0.2+ per CLAUDE.md. Phase 1.5 stays sync (threads).
- **Multi-station parallelism** — Phase 1.5 parallelizes across SOURCES for a single station. Cross-station parallelism (fetching KNYC + KMDW + KLAX simultaneously) is a separate concern; defer to v0.2 if cross-vertical batch workloads need it.
- **Adaptive rate limiting** — the spike captures empirical limits, but tradewinds v0.1 will NOT auto-throttle based on response headers. If a source 429s, log + retry with backoff is the only handling. Adaptive limits = v0.2.
- **Parity-gate fallback (revert vs merge-change)** — explicit decision deferred to post-spike. Both options are documented in ROADMAP; the choice depends on the actual parity-fixture results.

</deferred>

---

*Phase: 01-5-fetcher-optimization-cross-source-parallelism*
*Context gathered: 2026-05-22 from inline orchestrator brief + ROADMAP.md Phase 1.5 section*

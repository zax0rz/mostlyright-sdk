---
phase: 01-5-fetcher-optimization-cross-source-parallelism
plan: 01
type: execute
wave: 1
duration: Day 4.5 (~4-6h Claude execution; one calendar half-day with TDD)
waves: 1
depends_on: []      # Phase 1 complete on merged-vision (parity gate green, alpha1 published) — pre-condition, not an in-phase dependency
branch_strategy: per-wave; one sub-branch off `merged-vision` (`phase-1-5/wave-1/lift-pr85`); 3-reviewer panel (codex high + python-architect + security); merges to `merged-vision` ONLY after pre-flight parity check + full 5-fixture parity sweep are green
requirements:
  - PERF-01
  - PERF-02
  - PERF-03
autonomous: false   # Pre-merge requires manual `uv run pytest tests/test_parity.py` 5-fixture sweep + 3-reviewer panel; if parity drifts, post-spike human decision between revert vs merge `>` → `>=` (per CONTEXT.md locked decision)
files_modified:
  - packages/weather/src/tradewinds/weather/_fetchers/_iem_chunks.py            # NEW — shared calendar-year chunker
  - packages/weather/tests/_fetchers/test_iem_chunks.py                         # NEW — chunker unit tests (RED-first)
  - packages/weather/src/tradewinds/weather/_fetchers/iem_asos.py               # MODIFY — replace _monthly_chunks; add _iem_cache_filename with _partial; switch chunk-is-partial to UTC + OR
  - packages/weather/tests/_fetchers/test_iem_asos.py                           # MODIFY — add test_skip_cache_alone_writes_to_partial + test_future_chunk_end_alone_writes_to_partial + UTC-vs-local cutoff test
  - packages/core/src/tradewinds/_internal/_http.py                             # MODIFY — HTTP_TIMEOUT 30 → 60 + PR #85 docstring
  - packages/core/tests/_internal/test_http.py                                  # NEW (or MODIFY if exists) — assert HTTP_TIMEOUT == 60.0
  - CHANGELOG.md                                                                # MODIFY (or NEW) — note "old monthly cache files harmless; next backfill regenerates yearly files"
must_haves:
  truths:
    - "`from tradewinds.weather._fetchers._iem_chunks import yearly_chunks_exclusive_end` returns leap-year-safe calendar-aligned chunks (verified by test_iem_chunks::test_leap_year_2024_boundary)."
    - "`yearly_chunks_exclusive_end(date(2023,1,1), date(2025,1,1))` second chunk ends at `date(2025,1,1)` exactly (not `date(2024,12,31)` — that would be the timedelta-365 bug)."
    - "`yearly_chunks_exclusive_end(date(2025,12,31), date(2025,1,1))` returns `[]` (reversed-range guard, verbatim from PR #85)."
    - "`download_iem_asos(station, start, end, dest_dir)` issues ONE HTTP request per calendar year (was: one per calendar month) — verified by request-count assertion in test_iem_asos."
    - "`download_iem_asos(..., skip_cache=True)` writes ALL chunks to `_partial`-named files even when every chunk_end ≤ today_utc (PERF-02 OR-not-AND branch)."
    - "`download_iem_asos(...)` with chunk_end > today_utc writes that chunk to `_partial`-named file even when skip_cache=False (PERF-02 second OR branch)."
    - "Chunk-completeness cutoff uses `datetime.now(timezone.utc).date()`, NOT `date.today()` — verified by Pitfall-2 UTC-vs-local test that independently mocks both."
    - "Cache filename pattern is `iem_{chunk_start.isoformat()}_{chunk_end.isoformat()}_{suffix}.csv` for canonical chunks and `iem_{chunk_start.isoformat()}_{chunk_end.isoformat()}_partial_{suffix}.csv` for partial chunks."
    - "`tradewinds._internal._http.HTTP_TIMEOUT == 60.0` (was 30.0); docstring above the constant references PR #85 HIGH-2 12x-payload rationale."
    - "Pre-flight cheap parity check (single fixture, monthly-vs-yearly chunker) is byte-equal — if it drifts, surface to user BEFORE running full 5-fixture sweep."
    - "Full 5-fixture parity sweep passes `assert_frame_equal(check_dtype=True, check_exact=True)` after the chunker change."
    - "`uv run pytest -m \"not live\" -q` returns 0 failures across all packages."
    - "`uv run ruff check .` returns 0 errors and `uv run ruff format --check .` returns 0 diffs."
  artifacts:
    - path: packages/weather/src/tradewinds/weather/_fetchers/_iem_chunks.py
      provides: "yearly_chunks_inclusive(start, end) + yearly_chunks_exclusive_end(start, end) leap-year-safe calendar chunkers"
      contains: "def yearly_chunks_exclusive_end"
      min_lines: 30
    - path: packages/weather/tests/_fetchers/test_iem_chunks.py
      provides: "Chunker edge-case tests (leap year 2024, reversed range, single chunk, Jan 1 boundary)"
      contains: "def test_leap_year_2024_boundary"
      min_lines: 60
    - path: packages/weather/src/tradewinds/weather/_fetchers/iem_asos.py
      provides: "download_iem_asos using yearly_chunks_exclusive_end + _iem_cache_filename with partial kw-only + chunk_is_partial = skip_cache OR chunk_end > today_utc"
      contains: "def _iem_cache_filename"
    - path: packages/weather/tests/_fetchers/test_iem_asos.py
      provides: "test_skip_cache_alone_writes_to_partial + test_future_chunk_end_alone_writes_to_partial + UTC-vs-local cutoff test (mocks both datetime.now AND date.today)"
      contains: "def test_skip_cache_alone_writes_to_partial"
    - path: packages/core/src/tradewinds/_internal/_http.py
      provides: "HTTP_TIMEOUT = 60.0 with PR #85 HIGH-2 docstring"
      contains: "HTTP_TIMEOUT = 60.0"
    - path: packages/core/tests/_internal/test_http.py
      provides: "test_http_timeout_is_60s"
      contains: "assert HTTP_TIMEOUT == 60.0"
  key_links:
    - from: packages/weather/src/tradewinds/weather/_fetchers/iem_asos.py
      to: packages/weather/src/tradewinds/weather/_fetchers/_iem_chunks.py
      via: "import yearly_chunks_exclusive_end; replace local _monthly_chunks call"
      pattern: "from tradewinds.weather._fetchers._iem_chunks import yearly_chunks_exclusive_end"
    - from: packages/weather/src/tradewinds/weather/_fetchers/iem_asos.py
      to: datetime.now(timezone.utc).date()
      via: "chunk-completeness cutoff (NOT date.today())"
      pattern: "today_utc = datetime.now\\(timezone.utc\\)\\.date\\(\\)"
    - from: packages/weather/src/tradewinds/weather/_fetchers/iem_asos.py
      to: "chunk_is_partial = skip_cache or chunk_end > today_utc"
      via: "OR-not-AND partial-chunk decision (PR #85 verbatim)"
      pattern: "chunk_is_partial = skip_cache or chunk_end > today_utc"
    - from: tests/test_parity.py (5 fixtures, pre-existing)
      to: tradewinds.research(...)
      via: "full sweep MUST pass post-lift; pre-flight single-fixture check runs first as cheap detector"
      pattern: "assert_frame_equal\\(.*check_exact=True"
---

<objective>
Lift mostlyright PR #85 (commit `cf9eb85`, 2026-05-12) byte-faithfully into tradewinds: three coupled changes in a single coherent plan because they shipped as one PR upstream.

**Three lifts:**
1. **PERF-01** — Replace IEM ASOS monthly chunking with 365-day calendar-aligned chunking via a NEW shared helper `_iem_chunks.py` (extracted as a reusable module so future IEM-MOS work can consume it without re-deriving the algorithm).
2. **PERF-02** — Replace the opaque `iem_<YYYYMM>_<suffix>.csv` cache filename with the chunk-window-encoded `iem_{start_iso}_{end_iso}_{partial?}_{suffix}.csv` pattern. Route `skip_cache=True` OR `chunk_end > today_utc` to a `_partial` namespace that backfill never reads.
3. **PERF-03** — Bump `HTTP_TIMEOUT` 30s → 60s in `_internal/_http.py` to match the 12x payload increase per yearly chunk.

**The four landmines this plan defuses (RESEARCH.md Pitfalls 1-4):**
- `timedelta(days=365)` is wrong for leap years — use `date(year+1, 1, 1)` (Pitfall 1).
- `date.today()` is wrong for non-UTC hosts — use `datetime.now(timezone.utc).date()` (Pitfall 2, HIGH-severity PR #85 round-2 finding).
- The partial-chunk decision is `skip_cache OR chunk_end > today_utc`, NOT `AND` — CONTEXT.md previously had `AND` and was patched (Pitfall 3).
- Chunk size affects request pattern which affects merge tie-break order in `_internal/merge/observations.py` (strict `>` priority is first-row-seen wins). Mitigated by a cheap pre-flight single-fixture parity check before the full 5-fixture sweep (Pitfall 4).

**Purpose:** Phase 1 parity gate is green and alpha1 wheels are published. PR #85 is an empirically validated patch (PR #85 measured KNYC 5-year backfill at 10 min; we allow 20% headroom = 12 min). Without this lift, the IEM ASOS fetch path stays slow (~60-120 min for KNYC 5-year at monthly chunks) and has three known cache-poisoning paths. With this lift, the fetch path runs at upstream-measured 10 min and the cache poisoning paths close.

**Out of scope (deferred to Plan 03):** ThreadPoolExecutor orchestration in `research.py` (PERF-04). Out of scope (deferred to Plan 02): AWC/GHCNh rate-limit spike (PERF-05).

**Output:** Three file modifications + two new files + one CHANGELOG note. After this plan merges to `merged-vision`, downstream Plans 02 and 03 can run.
</objective>

<execution_context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/REQUIREMENTS.md
@.planning/STATE.md
@.planning/REVIEW-DISCIPLINE.md
@.planning/phase-01-5-fetcher-optimization-cross-source-parallelism/CONTEXT.md
@.planning/phase-01-5-fetcher-optimization-cross-source-parallelism/RESEARCH.md
@./CLAUDE.md
</execution_context>

<phase_summary>

**Goal:** Lift PR #85's three changes byte-faithfully into tradewinds, with TDD per change, and prove parity holds via pre-flight + full 5-fixture sweep before merging.

**Branch:** `phase-1-5/wave-1/lift-pr85` off `merged-vision`.

**TDD order (mandatory per CLAUDE.md):** RED → GREEN → REFACTOR per task. Each task writes failing tests FIRST, then implementation.

**Atomic commit boundaries:**
- Task 1 (chunker module) → 1-2 commits (RED test commit + GREEN impl commit, or single squash).
- Task 2 (iem_asos.py cache-filename + UTC cutoff + OR-partial decision) → 1 commit.
- Task 3 (HTTP_TIMEOUT bump) → 1 commit.
- Task 4 (parity pre-flight + full sweep) → 0-1 commit (only commits if a parity-related fixup is needed; otherwise just the pass).

**3-reviewer panel per CONTEXT.md locked decision:** codex `high` + python-architect + security. Security reviewer is included because HTTP timeout × payload-size is an attack surface (a slow-loris-style endpoint serving 60s of bytes per request can tie up worker threads).

**Pre-merge gate (mandatory, per ROADMAP.md Phase 1.5 parity-gate handling):**
1. Cheap pre-flight: ONE parity fixture re-run under monthly-chunker vs yearly-chunker — byte-equal must hold (Pitfall 4 detector, saves ~30 min if drift exists).
2. Full 5-fixture sweep: `uv run pytest tests/test_parity.py -x` MUST pass after the chunker change.
3. If parity drifts: surface to user with the empirical drift magnitude. Decision between (a) revert chunker, or (b) change merge `>` → `>=` with deterministic `(source, chunk_start)` secondary key is post-spike per CONTEXT.md — DO NOT silently pick.

</phase_summary>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1.1: Create shared `_iem_chunks.py` helper module (RED test FIRST)</name>
  <files>packages/weather/src/tradewinds/weather/_fetchers/_iem_chunks.py, packages/weather/tests/_fetchers/test_iem_chunks.py</files>
  <implements>PERF-01 (shared leap-year-safe calendar chunker)</implements>
  <read_first>
    - .planning/phase-01-5-fetcher-optimization-cross-source-parallelism/RESEARCH.md (lines 95-137 — verbatim PR #85 `_iem_chunks.py` source; lines 274-282 — Pitfall 1 leap-year landmine)
    - .planning/phase-01-5-fetcher-optimization-cross-source-parallelism/CONTEXT.md (Specifics section — chunk helper API contract)
    - packages/weather/src/tradewinds/weather/_fetchers/iem_asos.py (existing _monthly_chunks for reference of CURRENT pattern — will be replaced in Task 1.2, but read NOW to see the current docstring style)
    - packages/weather/src/tradewinds/weather/_fetchers/__init__.py (verify module exports pattern)
    - CLAUDE.md (TDD mandatory + 80% coverage minimum on new code)
  </read_first>
  <behavior>
    Tests to write FIRST (RED), all in `packages/weather/tests/_fetchers/test_iem_chunks.py`:

    1. `test_reversed_range_returns_empty`: `yearly_chunks_exclusive_end(date(2025,12,31), date(2025,1,1)) == []`
    2. `test_single_chunk_within_one_year`: `yearly_chunks_exclusive_end(date(2025,3,1), date(2025,9,30))` returns `[(date(2025,3,1), date(2026,1,1))]` (single chunk, exclusive end = next Jan 1)
    3. `test_two_year_range_produces_two_chunks`: `yearly_chunks_exclusive_end(date(2024,6,1), date(2025,6,1))` returns `[(date(2024,6,1), date(2025,1,1)), (date(2025,1,1), date(2026,1,1))]`
    4. `test_leap_year_2024_boundary` (CRITICAL — Pitfall 1): `yearly_chunks_exclusive_end(date(2023,1,1), date(2025,1,1))` second chunk's exclusive end is `date(2025,1,1)` exactly. If this returns `date(2024,12,31)`, the implementation used `timedelta(days=365)` and the leap year bit. MUST FAIL on naive `timedelta(days=365)` implementation.
    5. `test_jan_1_start_boundary`: `yearly_chunks_exclusive_end(date(2025,1,1), date(2025,1,1))` returns `[(date(2025,1,1), date(2026,1,1))]` (single chunk).
    6. `test_yearly_chunks_inclusive_basic`: `yearly_chunks_inclusive(date(2024,5,1), date(2025,3,15))` returns `[(date(2024,5,1), date(2024,12,31)), (date(2025,1,1), date(2025,3,15))]`.
    7. `test_yearly_chunks_inclusive_reversed_returns_empty`: `yearly_chunks_inclusive(date(2025,1,1), date(2024,12,31)) == []`.

    Run `uv run pytest packages/weather/tests/_fetchers/test_iem_chunks.py -x` — MUST fail (no impl yet). Commit: `test(phase-1-5): add failing tests for _iem_chunks calendar-year chunker (PERF-01 RED)`.
  </behavior>
  <action>
    Step 1 — Write tests FIRST in `packages/weather/tests/_fetchers/test_iem_chunks.py`. Use the exact test cases from `<behavior>`. Import path: `from tradewinds.weather._fetchers._iem_chunks import yearly_chunks_exclusive_end, yearly_chunks_inclusive`. Run `uv run pytest packages/weather/tests/_fetchers/test_iem_chunks.py -x` — MUST FAIL with `ImportError` or `ModuleNotFoundError`. Commit the RED tests.

    Step 2 — Implement `packages/weather/src/tradewinds/weather/_fetchers/_iem_chunks.py` VERBATIM from PR #85 (RESEARCH.md lines 102-137):

    ```python
    # Copy this verbatim from RESEARCH.md lines 102-137:
    from __future__ import annotations
    from datetime import date

    __all__ = ["yearly_chunks_inclusive", "yearly_chunks_exclusive_end"]


    def yearly_chunks_inclusive(start: date, end: date) -> list[tuple[date, date]]:
        """[start, end] split into per-calendar-year inclusive-end chunks."""
        if start > end:
            return []
        chunks: list[tuple[date, date]] = []
        current = start
        while current <= end:
            year_end = date(current.year, 12, 31)
            chunk_end = min(year_end, end)
            chunks.append((current, chunk_end))
            current = date(current.year + 1, 1, 1)  # leap-year safe
        return chunks


    def yearly_chunks_exclusive_end(start: date, end: date) -> list[tuple[date, date]]:
        """Range split into per-calendar-year EXCLUSIVE-end chunks (Jan 1 of next year)."""
        if start > end:
            return []
        chunks: list[tuple[date, date]] = []
        current = date(start.year, 1, 1)
        while current <= end:
            chunk_start = max(current, start)
            next_year_1st = date(current.year + 1, 1, 1)
            chunks.append((chunk_start, next_year_1st))
            current = next_year_1st
        return chunks
    ```

    Step 3 — Run `uv run pytest packages/weather/tests/_fetchers/test_iem_chunks.py -x` — MUST PASS all 7 tests. If `test_leap_year_2024_boundary` fails, you used `timedelta(days=365)` somewhere — fix to `date(year+1, 1, 1)`.

    Step 4 — Run `uv run ruff check --fix .` and `uv run ruff format .` on the new files. Commit: `feat(phase-1-5): add _iem_chunks calendar-year helper (PERF-01 GREEN — PR #85 cf9eb85)`.

    DO NOT modify `iem_asos.py` in this task — that's Task 1.2.
  </action>
  <verify>
    <automated>uv run pytest packages/weather/tests/_fetchers/test_iem_chunks.py -x -v</automated>
  </verify>
  <acceptance_criteria>
    - `test -f packages/weather/src/tradewinds/weather/_fetchers/_iem_chunks.py` returns 0 (file exists)
    - `grep -c "def yearly_chunks_exclusive_end" packages/weather/src/tradewinds/weather/_fetchers/_iem_chunks.py` returns 1
    - `grep -c "def yearly_chunks_inclusive" packages/weather/src/tradewinds/weather/_fetchers/_iem_chunks.py` returns 1
    - `grep "date(current.year + 1, 1, 1)" packages/weather/src/tradewinds/weather/_fetchers/_iem_chunks.py` returns non-empty (leap-year-safe pattern verbatim from PR #85)
    - `grep -c "timedelta(days=365)" packages/weather/src/tradewinds/weather/_fetchers/_iem_chunks.py` returns 0 (the WRONG pattern is NOT present)
    - `uv run pytest packages/weather/tests/_fetchers/test_iem_chunks.py -x -v` returns exit 0 with 7 passed
    - `grep -c "def test_leap_year_2024_boundary" packages/weather/tests/_fetchers/test_iem_chunks.py` returns 1
    - `uv run ruff check packages/weather/src/tradewinds/weather/_fetchers/_iem_chunks.py` returns 0 errors
    - Two commits exist on `phase-1-5/wave-1/lift-pr85`: the RED test commit and the GREEN implementation commit, both pre-commit-hook-validated (no `--no-verify`)
  </acceptance_criteria>
  <done>
    Shared `_iem_chunks.py` module exists with both helpers, leap-year safe, reversed-range-guarded. 7 unit tests pass under `pytest -x`. Module is ready for Task 1.2 to import.
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 1.2: Rewrite `iem_asos.py` chunker + cache-filename + UTC cutoff (RED tests FIRST)</name>
  <files>packages/weather/src/tradewinds/weather/_fetchers/iem_asos.py, packages/weather/tests/_fetchers/test_iem_asos.py</files>
  <implements>PERF-01 (chunker swap from _monthly_chunks → yearly_chunks_exclusive_end), PERF-02 (cache-filename + _partial + UTC + OR)</implements>
  <read_first>
    - .planning/phase-01-5-fetcher-optimization-cross-source-parallelism/RESEARCH.md (lines 141-188 — Pattern 2 cache-filename design; lines 152-188 — exact `_iem_cache_filename` + download_iem loop from PR #85; lines 285-301 — Pitfalls 2 (UTC) and 3 (OR-not-AND); lines 379-432 — full IEM ASOS fetcher diff shape)
    - .planning/phase-01-5-fetcher-optimization-cross-source-parallelism/CONTEXT.md (decisions section — "Cache scope — fetcher-internal CSV staging only"; "IEM rate-limit risk" — informational, not blocking this task)
    - packages/weather/src/tradewinds/weather/_fetchers/iem_asos.py (CURRENT FILE — read fully; you are replacing `_monthly_chunks` (lines 52-99) and the cache filename pattern at line 182. Keep the existing `report_type` keyword signature — RESEARCH.md note #1 at line 436 says do NOT change to multi-report-type-loop)
    - packages/weather/tests/_fetchers/test_iem_asos.py (CURRENT FILE — read to see existing test patterns and fixtures; do NOT regress them)
    - packages/weather/src/tradewinds/weather/_fetchers/_iem_chunks.py (Task 1.1 output — confirm the import path you will use)
  </read_first>
  <behavior>
    Tests to ADD FIRST to `packages/weather/tests/_fetchers/test_iem_asos.py` (in addition to existing tests which must keep passing):

    1. `test_chunk_filename_canonical`: With `partial=False`, `_iem_cache_filename(date(2024,1,1), date(2025,1,1), "metar", partial=False)` returns `"iem_2024-01-01_2025-01-01_metar.csv"`.
    2. `test_chunk_filename_partial`: With `partial=True`, `_iem_cache_filename(date(2024,1,1), date(2025,1,1), "metar", partial=True)` returns `"iem_2024-01-01_2025-01-01_partial_metar.csv"`.
    3. `test_yearly_chunks_replace_monthly` (request-count): Mock `download_with_retry` via `monkeypatch`/`respx`; call `download_iem_asos(station, date(2023,1,1), date(2024,12,31), tmp_path)` and assert exactly 2 HTTP requests are made (one per calendar year — was 24 monthly chunks pre-PERF-01).
    4. `test_skip_cache_alone_writes_to_partial` (PERF-02 OR-branch A): With `skip_cache=True` and ALL chunks fully historical (e.g. `start=date(2020,1,1), end=date(2021,1,1)`, frozen `today_utc = date(2026,5,22)`), every written file ends with `_partial_metar.csv`. NONE end with just `_metar.csv`.
    5. `test_future_chunk_end_alone_writes_to_partial` (PERF-02 OR-branch B): With `skip_cache=False` and `end > today_utc` (e.g. `end=date(2027,1,1)`, frozen `today_utc = date(2026,5,22)`), the chunk with `chunk_end > today_utc` writes to `_partial_metar.csv` while earlier chunks (`chunk_end <= today_utc`) write to canonical `_metar.csv`.
    6. `test_chunk_end_equals_today_utc_is_canonical` (boundary): `chunk_end == today_utc` is NOT partial (IEM `day2` exclusive means the chunk's last covered day is `today_utc - 1`, fully populated in UTC). The chunk writes to canonical `_metar.csv`. RESEARCH.md line 187 calls this out as a subtle correctness point.
    7. `test_cutoff_uses_utc_not_local` (Pitfall 2): Patch BOTH `datetime.now` (to return a UTC datetime fixed at `2026-05-22T03:00:00+00:00`) AND `date.today` (to return `date(2026, 5, 22)` — i.e. local-today = UTC-today + 1 because Europe/Prague is UTC+2 DST and local clock shows the next calendar day). Call with `end=date(2026,5,22)`. The implementation MUST treat `chunk_end == date(2026,5,22)` as NOT-greater-than `today_utc == date(2026,5,22)`, hence canonical. If `date.today()` is used, the assertion fails because local-today returns the same value here but the bug manifests with a different fixture — make the fixture: UTC = `2026-05-21T23:00:00+00:00` (UTC-today = `2026-05-21`), local-today (Prague +2) = `2026-05-22`. With `end=date(2026,5,22)`, the UTC code path classifies as `chunk_end > today_utc` (partial), the buggy local code path classifies as canonical. The test asserts `_partial_` is in the filename.
    8. `test_existing_canonical_cache_hit_skips_download`: If a canonical `.csv` file exists at the expected path and `chunk_is_partial=False`, no HTTP request is fired.
    9. `test_partial_cache_never_hits`: If a `_partial_*.csv` file exists at the expected path, the next call (with `chunk_is_partial=False` for that chunk) STILL fires a fresh request (because partial files are never read).

    Commit (RED): `test(phase-1-5): add failing tests for iem_asos yearly chunks + _partial cache + UTC cutoff (PERF-01/02 RED)`.
  </behavior>
  <action>
    Step 1 — Add the 9 new tests above to `packages/weather/tests/_fetchers/test_iem_asos.py`. Use `freezegun.freeze_time` if available; if not, use `unittest.mock.patch` to patch BOTH `tradewinds.weather._fetchers.iem_asos.datetime` and `tradewinds.weather._fetchers.iem_asos.date` separately (Pitfall 2: stubbing only one hides the bug). Use `respx` or `monkeypatch` against `download_with_retry` for the request-count test.

    Run `uv run pytest packages/weather/tests/_fetchers/test_iem_asos.py -x` — the 9 new tests MUST FAIL. Existing tests should continue to pass (they exercise current monthly-chunk behavior; some may break and that's expected — note which ones). Commit the RED tests.

    Step 2 — Modify `packages/weather/src/tradewinds/weather/_fetchers/iem_asos.py`:

    (a) Add imports at top (preserve existing imports):
    ```python
    from datetime import date, datetime, timezone
    from tradewinds.weather._fetchers._iem_chunks import yearly_chunks_exclusive_end
    ```

    (b) DELETE the entire `_monthly_chunks` function (current lines 52-99).

    (c) Add the `_iem_cache_filename` helper VERBATIM from RESEARCH.md lines 152-165:
    ```python
    def _iem_cache_filename(
        chunk_start: date,
        chunk_end: date,
        suffix: str,
        *,
        partial: bool,
    ) -> str:
        partial_infix = "_partial" if partial else ""
        return (
            f"iem_{chunk_start.isoformat()}_{chunk_end.isoformat()}"
            f"{partial_infix}_{suffix}.csv"
        )
    ```

    (d) Rewrite the download loop body (replacing `chunks = _monthly_chunks(start, end)` at line 179 + the for-loop that follows). The new structure (adapt from RESEARCH.md lines 170-186 — note tradewinds keeps ONE `report_type` per call, RESEARCH.md note #1 line 436):
    ```python
    chunks = yearly_chunks_exclusive_end(start, end)
    today_utc = datetime.now(timezone.utc).date()  # UTC, NOT date.today()
    paths: list[Path] = []
    for chunk_start, chunk_end in chunks:
        chunk_is_partial = skip_cache or chunk_end > today_utc  # OR, NOT AND
        filename = _iem_cache_filename(
            chunk_start, chunk_end, suffix, partial=chunk_is_partial
        )
        dest = dest_dir / station.code / filename
        if dest.exists() and not chunk_is_partial:
            log.info("IEM ASOS cache hit: %s", dest)
            paths.append(dest)
            continue
        url = _build_iem_url(station, chunk_start, chunk_end, report_type)
        download_with_retry(url, dest)
        time.sleep(IEM_POLITE_DELAY)
        paths.append(dest)
    return paths
    ```

    (e) Update the module docstring (lines 1-25) to reflect the new behavior: "yearly-chunked CSV downloads" (not monthly), cache key includes the full chunk window with `_partial` namespace, and reference PR #85 commit `cf9eb85`.

    (f) Update `_build_iem_url` if its signature reads `end-exclusive` from `_monthly_chunks` documentation — `yearly_chunks_exclusive_end` also emits exclusive ends, so this should be a no-op semantically.

    Step 3 — Run `uv run pytest packages/weather/tests/_fetchers/test_iem_asos.py -x -v`. All 9 new tests MUST pass. If existing tests reference `_monthly_chunks` directly or assert on monthly cache filenames, update those tests minimally to assert the new yearly behavior — this is a contract change documented in PR #85.

    Step 4 — Run `uv run pytest -m "not live" -q` (full fast suite) to catch any broader regressions.

    Step 5 — Run `uv run ruff check --fix .` + `uv run ruff format .`. Commit: `feat(phase-1-5): swap iem_asos to yearly chunks + _partial cache namespace + UTC cutoff (PERF-01/02 GREEN — PR #85 cf9eb85)`.
  </action>
  <verify>
    <automated>uv run pytest packages/weather/tests/_fetchers/test_iem_asos.py -x -v && uv run pytest -m "not live" -q</automated>
  </verify>
  <acceptance_criteria>
    - `grep -c "_monthly_chunks" packages/weather/src/tradewinds/weather/_fetchers/iem_asos.py` returns 0 (function removed; no straggler callers)
    - `grep -c "yearly_chunks_exclusive_end" packages/weather/src/tradewinds/weather/_fetchers/iem_asos.py` returns ≥1 (import + call site)
    - `grep -c "def _iem_cache_filename" packages/weather/src/tradewinds/weather/_fetchers/iem_asos.py` returns 1
    - `grep -E "today_utc = datetime\.now\(timezone\.utc\)\.date\(\)" packages/weather/src/tradewinds/weather/_fetchers/iem_asos.py` returns non-empty
    - `grep -c "date.today()" packages/weather/src/tradewinds/weather/_fetchers/iem_asos.py` returns 0 (Pitfall 2: local-date pattern is NOT present)
    - `grep "chunk_is_partial = skip_cache or chunk_end > today_utc" packages/weather/src/tradewinds/weather/_fetchers/iem_asos.py` returns non-empty (OR, not AND — verbatim PR #85)
    - `grep -c "skip_cache and chunk_end > today_utc" packages/weather/src/tradewinds/weather/_fetchers/iem_asos.py` returns 0 (Pitfall 3: AND pattern is NOT present)
    - `grep "iem_{chunk_start.isoformat()}_{chunk_end.isoformat()}" packages/weather/src/tradewinds/weather/_fetchers/iem_asos.py` returns non-empty (new filename pattern)
    - `uv run pytest packages/weather/tests/_fetchers/test_iem_asos.py -x -v` exits 0 with all 9 new tests passing
    - `uv run pytest -m "not live" -q` exits 0 (no regression in broader suite at the unit/integration level — parity sweep runs in Task 1.4)
    - `uv run ruff check packages/weather/src/tradewinds/weather/_fetchers/iem_asos.py` returns 0 errors
  </acceptance_criteria>
  <done>
    `iem_asos.py` issues one HTTP request per calendar year via the shared `yearly_chunks_exclusive_end` helper. Cache filenames encode the full chunk window. `_partial` namespace catches `skip_cache=True` OR `chunk_end > today_utc`. Cutoff uses UTC, not local. All 9 new tests pass. Broader fast-suite remains green.
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 1.3: Bump `HTTP_TIMEOUT` 30s → 60s in `_internal/_http.py` (RED test FIRST)</name>
  <files>packages/core/src/tradewinds/_internal/_http.py, packages/core/tests/_internal/test_http.py</files>
  <implements>PERF-03 (HTTP_TIMEOUT bump for 12x payload increase per yearly chunk)</implements>
  <read_first>
    - .planning/phase-01-5-fetcher-optimization-cross-source-parallelism/RESEARCH.md (lines 190-206 — Pattern 3 verbatim diff; lines 442-454 — exact before/after content for `_internal/_http.py`)
    - packages/core/src/tradewinds/_internal/_http.py (CURRENT FILE — read fully; line 18 has `HTTP_TIMEOUT = 30.0`; this is the only line to change. Line 19 has `TRANSIENT_CODES`, line 31 uses `httpx.Client(timeout=HTTP_TIMEOUT)` — verify no other constant needs touching)
    - packages/core/tests/_internal/ (check if `test_http.py` exists; if not, you'll create it)
    - .planning/REVIEW-DISCIPLINE.md (the never-skip list — `_internal/*` triggers the 3-reviewer panel automatically)
  </read_first>
  <behavior>
    Tests to write FIRST in `packages/core/tests/_internal/test_http.py` (CREATE the file if it doesn't exist):

    1. `test_http_timeout_is_60s`: `from tradewinds._internal._http import HTTP_TIMEOUT; assert HTTP_TIMEOUT == 60.0`.
    2. `test_max_retries_unchanged`: `from tradewinds._internal._http import MAX_RETRIES; assert MAX_RETRIES == 3` (Phase 1.5 explicitly does NOT touch retry policy — PR #85 only changed the timeout).
    3. `test_transient_codes_unchanged`: `from tradewinds._internal._http import TRANSIENT_CODES; assert TRANSIENT_CODES == frozenset({500, 502, 503, 504})`.

    Run `uv run pytest packages/core/tests/_internal/test_http.py -x` — `test_http_timeout_is_60s` MUST FAIL (current value is 30.0). Commit: `test(phase-1-5): add failing HTTP_TIMEOUT==60.0 assertion (PERF-03 RED)`.
  </behavior>
  <action>
    Step 1 — Create `packages/core/tests/_internal/test_http.py` if it doesn't exist (with appropriate `__init__.py` files if the test package init is missing). Add the 3 assertions from `<behavior>`. Run `uv run pytest packages/core/tests/_internal/test_http.py -x` — `test_http_timeout_is_60s` MUST FAIL with `AssertionError: assert 30.0 == 60.0`. Commit RED.

    Step 2 — Edit `packages/core/src/tradewinds/_internal/_http.py`. Replace line 18:

    Before:
    ```python
    HTTP_TIMEOUT = 30.0
    ```

    After (the docstring is mandatory — it's the PR #85 round-2 review HIGH-2 finding rationale, tradewinds-adapted; verbatim from RESEARCH.md lines 446-453):
    ```python
    # Round-2 review (PR #85) HIGH-2: 12x larger payload-per-request after the
    # IEM chunk bump (90d→year). Pre-bump ASOS was ~150 KB/month (30s plenty);
    # post-bump it's ~1.8 MB/year on the empirical KNYC sample. Tradewinds note:
    # AWC + GHCNh + CLI did not change payload size — the bump is conservative
    # overhead for those endpoints, not load-bearing.
    HTTP_TIMEOUT = 60.0
    ```

    Step 3 — Run `uv run pytest packages/core/tests/_internal/test_http.py -x -v` — all 3 tests MUST pass.

    Step 4 — Run `uv run pytest -m "not live" -q` — full fast suite MUST stay green. The timeout bump is conservative (longer wait, not shorter); no test should regress.

    Step 5 — `uv run ruff check --fix packages/core/src/tradewinds/_internal/_http.py` + `uv run ruff format .`. Commit: `feat(phase-1-5): bump HTTP_TIMEOUT 30→60s for 12x payload per yearly chunk (PERF-03 GREEN — PR #85 cf9eb85)`.

    DO NOT touch retry logic, backoff base, or transient-code set — PR #85 only changed the timeout constant, nothing else in `_http.py`.
  </action>
  <verify>
    <automated>uv run pytest packages/core/tests/_internal/test_http.py -x -v && uv run pytest -m "not live" -q</automated>
  </verify>
  <acceptance_criteria>
    - `grep "^HTTP_TIMEOUT = 60.0" packages/core/src/tradewinds/_internal/_http.py` returns non-empty (exact match, beginning of line)
    - `grep -c "^HTTP_TIMEOUT = 30.0" packages/core/src/tradewinds/_internal/_http.py` returns 0 (old value GONE)
    - `grep "12x larger payload-per-request" packages/core/src/tradewinds/_internal/_http.py` returns non-empty (PR #85 docstring present)
    - `grep "MAX_RETRIES = 3" packages/core/src/tradewinds/_internal/_http.py` returns non-empty (retry logic unchanged)
    - `grep "BASE_DELAY = 1.0" packages/core/src/tradewinds/_internal/_http.py` returns non-empty (backoff unchanged)
    - `test -f packages/core/tests/_internal/test_http.py` returns 0
    - `uv run pytest packages/core/tests/_internal/test_http.py::test_http_timeout_is_60s -x -v` exits 0
    - `uv run pytest -m "not live" -q` exits 0 (no regression)
    - `uv run ruff check packages/core/src/tradewinds/_internal/_http.py` returns 0 errors
  </acceptance_criteria>
  <done>
    `HTTP_TIMEOUT == 60.0` with PR #85 rationale docstring. Retry policy and transient-codes unchanged. Fast suite green.
  </done>
</task>

<task type="checkpoint:human-verify" gate="blocking">
  <name>Task 1.4: Pre-flight + full 5-fixture parity sweep (HARD gate — pre-merge)</name>
  <files>tests/test_parity.py (existing, no modification expected), CHANGELOG.md</files>
  <implements>ROADMAP.md Phase 1.5 parity-gate handling — mandatory pre-merge re-run; Pitfall 4 cheap pre-flight</implements>
  <read_first>
    - .planning/ROADMAP.md (lines 51-52 — parity gate handling: cheap pre-flight + full sweep mandatory pre-merge; revert vs `>` → `>=` decision is post-spike)
    - .planning/phase-01-5-fetcher-optimization-cross-source-parallelism/CONTEXT.md (decisions: "Parity gate handling — re-run all 5 fixtures pre-merge")
    - .planning/phase-01-5-fetcher-optimization-cross-source-parallelism/RESEARCH.md (lines 303-318 — Pitfall 4 chunk-iteration-order affects merge tie-break; lines 568-576 — pre-flight cheap parity-check methodology)
    - tests/test_parity.py (existing — Phase 1 Wave 3 deliverable; verify it parametrizes over all 5 fixtures and uses `assert_frame_equal(check_dtype=True, check_exact=True)`)
    - tests/fixtures/parity/ (existing — verify all 5 fixtures present)
    - packages/core/src/tradewinds/_internal/merge/observations.py (read to confirm the strict `>` priority comparison RESEARCH.md Pitfall 4 references — informs the post-flight fallback decision if needed)
  </read_first>
  <what-built>
    Tasks 1.1–1.3 are complete: yearly chunker module, `iem_asos.py` rewritten for yearly + `_partial` + UTC, `HTTP_TIMEOUT=60s`. Now we must prove parity holds before merging this plan to `merged-vision`.
  </what-built>
  <how-to-verify>
    **Step A — Pre-flight cheap check (Pitfall 4 detector, saves ~30 min if drift exists):**

    Run a single parity fixture, comparing the chunker-change output against the captured Phase 1 fixture:

    ```bash
    uv run pytest tests/test_parity.py -x -k "case_1" -v
    ```

    Expected: PASS. If FAIL: drift detected — DO NOT proceed to full sweep yet. Capture the diff (which columns drift, magnitude) and surface to user per ROADMAP.md decision tree before deciding revert vs `>` → `>=`.

    **Step B — Full 5-fixture sweep:**

    ```bash
    uv run pytest tests/test_parity.py -x -v
    ```

    Expected: 5 passed (KNYC, KMDW, KLAX, KMIA, KMSY). If any fail: capture the diff (column subset, value magnitude), classify as either (a) merge tie-break flip (likely `(observation_type, retrieved_at)` columns only — RESEARCH.md Pitfall 4 warning sign) or (b) real data-loss bug, and surface to user.

    **Step C — Verify ruff + pre-commit hooks pass:**

    ```bash
    uv run pre-commit run --all-files
    ```

    Expected: all hooks green (no `--no-verify`).

    **Step D — Add CHANGELOG note (RESEARCH.md Assumption A6):**

    Edit `CHANGELOG.md` (create at repo root if missing). Under an Unreleased / `[Phase 1.5]` heading, add:

    ```markdown
    ### Changed
    - IEM ASOS fetcher now uses 365-day calendar-aligned chunks (was: monthly). Cache filenames now encode the full chunk window (`iem_{start_iso}_{end_iso}_{suffix}.csv`). Old monthly cache files (`iem_<YYYYMM>_*.csv`) are harmless and will be re-generated by the next backfill into the new yearly-chunk format — no migration required. Lift target: mostlyright PR #85 commit `cf9eb85` (2026-05-12).
    - `tradewinds._internal._http.HTTP_TIMEOUT` raised 30s → 60s to match the 12x payload increase per yearly chunk.

    ### Added
    - `tradewinds.weather._fetchers._iem_chunks` module with `yearly_chunks_inclusive` and `yearly_chunks_exclusive_end` calendar-year helpers (leap-year safe).
    ```

    Commit: `docs(phase-1-5): CHANGELOG note for yearly chunks + HTTP_TIMEOUT bump (PERF-01/02/03)`.

    **Step E — Confirm to user:**

    Report to user with one of two messages:

    (1) **All green:** "Pre-flight + full 5-fixture parity sweep PASS. Ruff + pre-commit green. CHANGELOG updated. Plan 01 (PERF-01/02/03) ready for 3-reviewer panel (codex high + python-architect + security) and merge to `merged-vision`. Decision: type `approved` to proceed to the review panel."

    (2) **Drift detected:** "Parity drift detected on case_X. Drifting columns: [list]. Magnitude: [list]. Per ROADMAP.md decision tree, choose:
       - (a) **Revert the chunker change** — keep `_monthly_chunks`, drop PERF-01 from this plan. PERF-02 + PERF-03 can still ship if their tests pass independently of chunker change.
       - (b) **Change `_internal/merge/observations.py` from strict `>` to `>=` with deterministic secondary key `(source, chunk_start)`** — re-validate by re-running the full sweep. This adds a new wave-1 sub-task and re-triggers the 3-reviewer panel.
       Recommendation deferred to your inspection of the drift magnitude."
  </how-to-verify>
  <resume-signal>
    Type `approved` if parity is green and CHANGELOG committed (proceed to 3-reviewer panel + merge). Type `revert` to drop PERF-01 and keep PERF-02/03 only. Type `merge-relax` to take option (b) and re-run with `>=` + deterministic secondary key.
  </resume-signal>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| tradewinds → IEM ASOS endpoint (`mesonet.agron.iastate.edu`) | Outbound HTTP; tradewinds is the client. IEM controls payload size + response timing. |
| tradewinds local-disk cache | tradewinds writes CSV files to `~/.tradewinds/cache/iem_staging/<station>/`. Trust boundary if the cache dir is shared across users on a multi-tenant box (not the default, but possible). |
| tradewinds `_internal/_http.py` HTTP_TIMEOUT × concurrent thread count | Each outbound thread now holds an httpx connection open for up to 60s (was 30s). |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-1.5-01 | Tampering / Information Disclosure | `_partial` cache filenames in shared cache dir | mitigate | `_partial` infix is part of the filename, not a separate dir with permissions. On multi-tenant shared cache dirs, an attacker who can write to `~/.tradewinds/cache/iem_staging/<station>/` can already poison canonical files too. Accept residual: tradewinds is a local-first SDK; cache dir under `$HOME` by default; CACHE-01 honors `TRADEWINDS_CACHE_DIR` for per-user override. No new attack surface vs pre-PERF-02 baseline. |
| T-1.5-02 | Denial of Service | HTTP_TIMEOUT bump 30s→60s | accept | A slow-loris-style endpoint serving 60s of trickled bytes can now tie up an httpx worker thread for 2× as long. In v0.1 with `max_workers=4` (Plan 03) the worst case is 4 threads × 60s = 4 min of stuck workers per attack window. Mitigation by accept: IEM/AWC/GHCNh/NWS CLI are reputable .gov / .edu endpoints; no MITM in tradewinds threat model (HTTPS-only). Mark as residual; revisit in v0.2 if untrusted source endpoints are added. |
| T-1.5-03 | Information Disclosure | UTC-vs-local cutoff bug | mitigate | Pitfall 2 (Europe/Prague host with `date.today()` instead of `datetime.now(timezone.utc).date()`) causes silent data loss in canonical cache files — these are READ next backfill and the missing data propagates into parity DataFrames returned to user. The mitigation is the test `test_cutoff_uses_utc_not_local` that mocks BOTH `datetime.now` AND `date.today` independently to catch the bug. Implementation uses `datetime.now(timezone.utc).date()` verbatim from PR #85. |
| T-1.5-04 | Repudiation | Cache poisoning (3 paths PR #85 documented) | mitigate | Pre-PERF-02, `skip_cache=True` live-sweeps wrote partial-year data into canonical cache files (silent settlement-grade data corruption). PERF-02 routes `skip_cache=True` OR `chunk_end > today_utc` to `_partial` namespace that backfill NEVER reads. Two dedicated tests catch each OR-branch (`test_skip_cache_alone_writes_to_partial` and `test_future_chunk_end_alone_writes_to_partial`). Closes the 3 cache-poisoning paths. |
| T-1.5-05 | Elevation of Privilege | N/A | accept | No privilege boundaries in this plan (no auth, no secrets, no remote-write surface). |
</threat_model>

<verification>
## Plan-Level Checks (auto + manual)

| Check | Command | Expected |
|-------|---------|----------|
| `_iem_chunks` module unit tests | `uv run pytest packages/weather/tests/_fetchers/test_iem_chunks.py -x -v` | 7 passed |
| `iem_asos.py` unit + behavior tests (9 new) | `uv run pytest packages/weather/tests/_fetchers/test_iem_asos.py -x -v` | All passed (existing + 9 new) |
| `_http.py` constants | `uv run pytest packages/core/tests/_internal/test_http.py -x -v` | 3 passed |
| Full fast suite | `uv run pytest -m "not live" -q` | 0 failures |
| Pre-flight cheap parity | `uv run pytest tests/test_parity.py -x -k case_1 -v` | 1 passed |
| Full 5-fixture parity sweep | `uv run pytest tests/test_parity.py -x -v` | 5 passed |
| Ruff lint | `uv run ruff check .` | 0 errors |
| Ruff format | `uv run ruff format --check .` | 0 diffs |
| Pre-commit hooks all | `uv run pre-commit run --all-files` | All green |

## Static Regression Guards (grep-based)

```bash
# PERF-01: no straggler monthly chunker
grep -rn "_monthly_chunks" packages/weather/src/tradewinds/weather/_fetchers/ | grep -v "test_" && echo "FAIL: monthly chunker not fully removed" || echo "OK"

# PERF-02: UTC, not local
grep -n "date.today()" packages/weather/src/tradewinds/weather/_fetchers/iem_asos.py && echo "FAIL: date.today() present (Pitfall 2)" || echo "OK"

# PERF-02: OR, not AND
grep -n "skip_cache and chunk_end > today_utc" packages/weather/src/tradewinds/weather/_fetchers/iem_asos.py && echo "FAIL: AND pattern present (Pitfall 3)" || echo "OK"

# PERF-03: timeout value
grep "^HTTP_TIMEOUT = 60.0" packages/core/src/tradewinds/_internal/_http.py || echo "FAIL: HTTP_TIMEOUT != 60.0"

# PERF-01: leap-year-safe pattern
grep "date(current.year + 1, 1, 1)" packages/weather/src/tradewinds/weather/_fetchers/_iem_chunks.py || echo "FAIL: leap-year-safe pattern missing"

# PERF-01: timedelta-365 anti-pattern not present
grep -c "timedelta(days=365)" packages/weather/src/tradewinds/weather/_fetchers/_iem_chunks.py | grep -E "^0$" || echo "FAIL: timedelta(days=365) anti-pattern present"
```
</verification>

<success_criteria>
- [ ] PERF-01: `_iem_chunks.py` exists with `yearly_chunks_inclusive` + `yearly_chunks_exclusive_end`. 7 unit tests pass. `iem_asos.py` uses `yearly_chunks_exclusive_end`; `_monthly_chunks` is removed.
- [ ] PERF-02: `_iem_cache_filename(...)` defined with kw-only `partial`. `chunk_is_partial = skip_cache or chunk_end > today_utc` (OR, NOT AND). `today_utc = datetime.now(timezone.utc).date()` (NOT `date.today()`). 9 new unit tests pass, including the two OR-branches and the UTC-vs-local cutoff test.
- [ ] PERF-03: `HTTP_TIMEOUT == 60.0` with PR #85 docstring. `MAX_RETRIES`, `BASE_DELAY`, `TRANSIENT_CODES` unchanged.
- [ ] Pre-flight cheap parity check (single fixture, monthly-vs-yearly) is green.
- [ ] Full 5-fixture parity sweep is green via `uv run pytest tests/test_parity.py -x -v`.
- [ ] Fast suite green: `uv run pytest -m "not live" -q` exits 0.
- [ ] Pre-commit hooks green: `uv run pre-commit run --all-files` exits 0.
- [ ] `CHANGELOG.md` notes the old-cache-files-are-harmless story and lists PERF-01/02/03 changes.
- [ ] Branch `phase-1-5/wave-1/lift-pr85` is ready for 3-reviewer panel (codex `high` + python-architect + security). Reviewer prompt explicitly references PR #85 commit `cf9eb85` as the diff source-of-truth.
- [ ] No `--no-verify` used at any commit boundary.
</success_criteria>

<output>
After completion, create `.planning/phase-01-5-fetcher-optimization-cross-source-parallelism/01-5-01-SUMMARY.md` documenting:

- Three changes shipped (PERF-01/02/03) with PR #85 commit `cf9eb85` reference
- Parity-sweep result (5/5 green | drift detected + decision taken)
- Commit hashes on `phase-1-5/wave-1/lift-pr85` (RED + GREEN per task, then merge commit to `merged-vision`)
- 3-reviewer panel verdict (PASS | REVISE iterations)
- Any deviations from the verbatim PR #85 lift (none expected; document if unavoidable)
- Time spent (Claude execution wall time + human pre-merge verification time)
- Downstream signals for Plans 02 and 03: yearly chunker confirmed working, cache namespace partitioned, timeout sufficient. Plan 02 spike can now characterize AWC/GHCNh rate limits against the SAME timeout the production code uses.
</output>

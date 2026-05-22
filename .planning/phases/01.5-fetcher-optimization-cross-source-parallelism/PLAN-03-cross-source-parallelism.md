---
phase: 01-5-fetcher-optimization-cross-source-parallelism
plan: 03
type: execute
wave: 2
duration: Day 5–5.5 (~5-7h Claude execution + ~1h live KNYC 5-year backfill timing test)
waves: 1
depends_on:
  - PLAN-02-source-limits-spike.md   # Plan 03 reads SOURCE-LIMITS.md to choose IEM-sharing Option A/B/C
  - PLAN-01-lift-pr85.md             # Plan 03 imports from `_internal/_http.py` (post-PERF-03) and exercises yearly chunker (PERF-01) in the recorded-fixture test
branch_strategy: per-wave; one sub-branch off `merged-vision` (`phase-1-5/wave-2/research-py-fanout`); 3-reviewer panel (codex high + python-architect + security); merges to `merged-vision` ONLY after parallelism check + recorded-fixture integration test green AND (manual) live KNYC 5-year backfill timing test confirms ≤12 min
requirements:
  - PERF-04
autonomous: false   # Live KNYC 5-year backfill timing test is manual (`@pytest.mark.live`); requires user confirmation that observed wall time ≤12 min before merge
files_modified:
  - packages/core/src/tradewinds/research.py                                  # NEW — minimal Phase 1.5 stub with ThreadPoolExecutor fan-out
  - packages/core/tests/test_research_parallelism.py                          # NEW — recorded-fixture integration test for parallelism semantics
  - tests/test_live_perf.py                                                   # NEW — @pytest.mark.live KNYC 5-year backfill timing test
  - packages/core/src/tradewinds/__init__.py                                  # MODIFY — re-export `research` from `tradewinds.research`
  - CHANGELOG.md                                                              # MODIFY — note PERF-04 ships the ThreadPoolExecutor fan-out
must_haves:
  truths:
    - "`tradewinds.research(station, from_date, to_date)` exists as an importable callable from `packages/core/src/tradewinds/research.py` and is re-exported via `tradewinds.__init__.py`."
    - "`research()` uses `concurrent.futures.ThreadPoolExecutor(max_workers=N)` where N is chosen per SOURCE-LIMITS.md recommended Option (A: N=4 with IEM lock; B: N=3 with serialized IEM; C: N=4 with no IEM lock)."
    - "`research()` fires one future per source: `iem.archive` (IEM ASOS), `awc.live`, `ghcnh.archive`, `cli.archive` (IEM CLI). For Option B, IEM ASOS+CLI are combined into a single 'iem' worker function (so max_workers=3)."
    - "Per-source timing measurement uses `as_completed(futures)` + per-future `submitted_at` mapping — NOT `t0 = time.monotonic(); f.result()` inside the iteration (RESEARCH.md Pitfall 6). The submission timestamp is captured immediately after `ex.submit()` returns."
    - "`research()` propagates exceptions via `f.result()` — no try/except wrapping each future; the orchestrator catches at the top level only. Exceptions surface with the source name in the message."
    - "Parallelism check (recorded-fixture integration test): with all four cassettes deterministically replaying, `wall_time` is bounded by `max(per_source_t_i) * 1.2 + epsilon` where epsilon accounts for ThreadPoolExecutor + dict-iteration overhead. Test asserts `wall_time ≤ max(per_source_t_i) * 1.2`."
    - "Recorded-fixture integration test does NOT use a live network; it uses `pytest-recording` cassettes captured once at fixture-creation time and replayed deterministically in CI."
    - "`@pytest.mark.live` `test_knyc_5yr_backfill_under_12min` exists in `tests/test_live_perf.py` and is excluded from CI via `pytest -m \"not live\"`."
    - "Manual live run of `uv run pytest -m live tests/test_live_perf.py::test_knyc_5yr_backfill_under_12min -v` against real IEM produces wall_time ≤ 12 minutes for KNYC 5-year ASOS backfill (PR #85 measured 10 min; 20% headroom)."
    - "Other-station regression: pick one of {KMDW, KLAX, KMIA} from parity fixtures and confirm backfill completes within the per-station empirical wall time recorded during the Plan 02 spike (NO fixed cross-station threshold per CONTEXT.md)."
    - "`research.py` docstring explicitly states: 'Phase 1.5 scope: ThreadPoolExecutor parallelism only. Phase 3 will extend with Mode 1/Mode 2 source-explicit dispatch and the v0.14.1-parity DataFrame return shape.' (Addresses RESEARCH.md Open Question 2 / Assumption A4.)"
    - "If SOURCE-LIMITS.md recommends Option A: a module-level `threading.Lock` is acquired around `download_with_retry` calls inside IEM fetchers (or wrapped at the orchestrator level around IEM futures) — NOT around AWC/GHCNh."
    - "No asyncio, no httpx.AsyncClient, no `async def` anywhere in `research.py` (CONTEXT.md locked decision; verified by grep)."
  artifacts:
    - path: packages/core/src/tradewinds/research.py
      provides: "research(station, from_date, to_date) fan-out + join scaffold using ThreadPoolExecutor"
      contains: "def research"
      min_lines: 60
    - path: packages/core/tests/test_research_parallelism.py
      provides: "Recorded-fixture integration test: parallelism check + exception propagation + all-4-sources-returned"
      contains: "def test_wall_time_within_max_source_times"
      min_lines: 80
    - path: tests/test_live_perf.py
      provides: "@pytest.mark.live KNYC 5-year + other-station-regression backfill timing tests"
      contains: "@pytest.mark.live"
      min_lines: 40
    - path: packages/core/src/tradewinds/__init__.py
      provides: "Re-export of `research` from `tradewinds.research` so `import tradewinds; tradewinds.research(...)` works"
      contains: "from tradewinds.research import research"
  key_links:
    - from: packages/core/src/tradewinds/research.py
      to: packages/weather/src/tradewinds/weather/_fetchers/iem_asos.download_iem_asos (post-PERF-01)
      via: "lazy import inside research() to break cross-package circular dep (matches RESEARCH-05 pattern)"
      pattern: "from tradewinds.weather._fetchers.iem_asos import download_iem_asos"
    - from: packages/core/src/tradewinds/research.py
      to: concurrent.futures.ThreadPoolExecutor + as_completed
      via: "import; max_workers=N (Option A/B/C from SOURCE-LIMITS.md)"
      pattern: "concurrent.futures.ThreadPoolExecutor"
    - from: packages/core/tests/test_research_parallelism.py
      to: pytest-recording cassettes
      via: "@pytest.mark.vcr decorator; cassette under tests/cassettes/test_research_parallelism/"
      pattern: "@pytest.mark.vcr"
    - from: tests/test_live_perf.py
      to: tradewinds.research
      via: "@pytest.mark.live KNYC 5-year backfill — runs only under `uv run pytest -m live`"
      pattern: "@pytest.mark.live"
    - from: .planning/research/SOURCE-LIMITS.md (Plan 02 output)
      to: research.py max_workers + IEM-Lock wiring
      via: "MUST be cited in Task 3.1 read_first; chosen Option dictates the implementation shape"
---

<objective>
Implement PERF-04: a minimal `research.py` orchestrator at `packages/core/src/tradewinds/research.py` that fans out AWC + IEM-ASOS + GHCNh + IEM-CLI concurrently via `ThreadPoolExecutor`. The implementation shape (Option A vs B vs C — `max_workers=4` with IEM Lock, `max_workers=3` with merged IEM worker, or `max_workers=4` no Lock) is chosen based on the empirical evidence in `.planning/research/SOURCE-LIMITS.md` (Plan 02 deliverable).

**The two parallelism-correctness landmines this plan defuses (RESEARCH.md Pitfalls 5-6):**

- **Pitfall 5 — IEM shared-IP throttle:** Plan 02's spike answers whether `mesonet.agron.iastate.edu` enforces a shared per-IP budget across `asos.py` and `cli.py`. The answer dictates Option A/B/C. **Task 3.1 reads SOURCE-LIMITS.md as its first action** and forks the implementation accordingly.
- **Pitfall 6 — per-source timing measurement bug:** The CONTEXT.md sketched code measured per-source time as `t0 = time.monotonic(); f.result(); per_source_times[name] = time.monotonic() - t0` inside a dict iteration. This is wrong because `f.result()` blocks on the FIRST iterated future (which may not be the first to complete) → first source gets inflated time, later sources get ~0 time. The correct pattern: capture `submitted_at[name] = time.monotonic()` immediately after `ex.submit()`, then iterate `as_completed(futures)` and compute `per_source_times[name] = time.monotonic() - submitted_at[name]`. Plan 03 implements the correct pattern.

**Why this plan is in Wave 2 (depends on Plans 01 AND 02):**

- Depends on Plan 01: Plan 03 imports from `_internal/_http.py` (post-PERF-03 timeout=60s) and exercises the yearly chunker (PERF-01) via the recorded-fixture integration test against `iem_asos.download_iem_asos`. Plan 01 must merge first.
- Depends on Plan 02: Plan 03 reads SOURCE-LIMITS.md to choose the IEM-sharing Option. Plan 02 must merge first so SOURCE-LIMITS.md exists on `merged-vision` when Plan 03 forks.

**Phase 1.5 `research.py` ownership boundary with Phase 3 (RESEARCH.md Open Q2 / Assumption A4):** Phase 1.5 ships a MINIMAL `research.py` with the ThreadPoolExecutor fan-out as the only public surface. Phase 3 extends with Mode 1/Mode 2 dispatch + DataFrame return shape (RESEARCH-01..05). The Phase-1.5 stub docstring explicitly states "Phase 3 will replace the return type" so the executor-of-Phase-3 has unambiguous ownership.

**Out of scope:** Mode 1/Mode 2 dispatch (Phase 3). Adaptive rate-limiting (v0.2). Async (v0.2). Cross-station parallelism (v0.2). DataFrame return shape (Phase 3 — Plan 03's `research()` returns a dict, NOT a DataFrame).

**Output:** One new file (`research.py`) + one new test file + one live performance test + an `__init__.py` re-export. Wave 2 closes Phase 1.5 once this plan merges to `merged-vision`.
</objective>

<execution_context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/REQUIREMENTS.md
@.planning/STATE.md
@.planning/REVIEW-DISCIPLINE.md
@.planning/phase-01-5-fetcher-optimization-cross-source-parallelism/CONTEXT.md
@.planning/phase-01-5-fetcher-optimization-cross-source-parallelism/RESEARCH.md
@.planning/research/SOURCE-LIMITS.md
@./CLAUDE.md
</execution_context>

<phase_summary>

**Goal:** Ship `research.py` ThreadPoolExecutor fan-out with the Option (A/B/C) chosen by SOURCE-LIMITS.md, with the timing-measurement Pitfall 6 properly avoided, and prove the parallelism check holds via recorded-fixture integration test + live perf gate.

**Branch:** `phase-1-5/wave-2/research-py-fanout` off `merged-vision`. Strictly after Plans 01 + 02 merge (Wave 2 depends on Wave 1).

**Atomic commit boundaries:**
- Task 3.1 (`research.py` skeleton + Option-fork decision) → 1 commit (RED tests if applicable + GREEN impl)
- Task 3.2 (recorded-fixture integration test + parallelism assertion) → 1 commit
- Task 3.3 (live perf test for KNYC 5-year backfill) → 1 commit
- Task 3.4 (CHANGELOG + 5-fixture parity re-run + merge prep) → 1 commit

**3-reviewer panel per CONTEXT.md locked decision:** codex `high` + python-architect + security. Security reviewer focus: HTTP_TIMEOUT × concurrent-thread-count interaction (4 threads × 60s = 4 min max stuck-worker per attack window) + the IEM-Lock implementation correctness if Option A is chosen.

**Pre-merge gate (mandatory):**
1. Recorded-fixture integration test (`test_research_parallelism.py`) passes — proves correctness in CI without live network.
2. Live perf test (`test_knyc_5yr_backfill_under_12min`) passes manually — proves real-world performance gate.
3. Other-station regression: `KMDW` (or `KLAX` or `KMIA`) backfill completes within per-station baseline recorded in SOURCE-LIMITS.md.
4. Full 5-fixture parity sweep MUST continue to pass (Phase 1.5 changes must NOT regress the Day 3 HARD GATE).

</phase_summary>

<tasks>

<task type="auto" tdd="true">
  <name>Task 3.1: Implement `research.py` ThreadPoolExecutor fan-out (Option A/B/C per SOURCE-LIMITS.md)</name>
  <files>packages/core/src/tradewinds/research.py, packages/core/src/tradewinds/__init__.py</files>
  <implements>PERF-04 (ThreadPoolExecutor fan-out across 4 sources; IEM-sharing Option A/B/C per Plan 02 output)</implements>
  <read_first>
    - .planning/research/SOURCE-LIMITS.md (CRITICAL — read FIRST; the "Recommendation for Plan 03 PERF-04 design" section dictates Option A/B/C and therefore the implementation shape. If this file does not exist, STOP — Plan 02 must merge first.)
    - .planning/phase-01-5-fetcher-optimization-cross-source-parallelism/RESEARCH.md (lines 208-272 — Pattern 4 ThreadPoolExecutor + httpx thread-safety; lines 336-365 — Pitfall 6 timing measurement bug with correct pattern; lines 463-507 — code example for the minimal `research.py` stub; lines 319-335 — Pitfall 5 Option A/B/C descriptions)
    - .planning/phase-01-5-fetcher-optimization-cross-source-parallelism/CONTEXT.md (locked decisions — concurrency primitive: threads not asyncio; max_workers=4; "Claude's Discretion" — whether to create `research.py` in Phase 1.5: yes, minimal stub)
    - packages/weather/src/tradewinds/weather/_fetchers/iem_asos.py (post-Plan-01 — to know the signature of `download_iem_asos(station, start, end, dest_dir, *, skip_cache=False, report_type=3)`)
    - packages/weather/src/tradewinds/weather/_fetchers/awc.py (to know the AWC fetcher signature)
    - packages/weather/src/tradewinds/weather/_fetchers/ghcnh.py (to know the GHCNh fetcher signature)
    - packages/weather/src/tradewinds/weather/_fetchers/iem_cli.py (to know the IEM CLI fetcher signature; note for Option B this gets merged into a single iem worker)
    - packages/core/src/tradewinds/__init__.py (to see current top-level exports; you will ADD `research` to them)
    - packages/core/src/tradewinds/_internal/_http.py (post-Plan-01 — HTTP_TIMEOUT=60s; verify the constant is used by all fetchers)
    - CLAUDE.md (Stay sync in v0.1 — no asyncio; pre-commit + pre-push hooks)
  </read_first>
  <behavior>
    Tests to write FIRST (RED) in `packages/core/tests/test_research_parallelism.py` (the file is created here; Task 3.2 will expand it with the recorded-fixture integration tests):

    1. `test_research_is_callable_and_returns_dict`: `from tradewinds.research import research; result = research(station="KNYC", from_date=date(2024,1,1), to_date=date(2024,1,7))` — returns a dict with keys `{"results", "wall_time", "per_source_times"}`.
    2. `test_research_results_contains_four_sources` (Option A or C) or `test_research_results_contains_three_sources` (Option B): `set(result["results"].keys()) == {"iem.archive", "awc.live", "ghcnh.archive", "cli.archive"}` for A/C, or `{"iem", "awc.live", "ghcnh.archive"}` for B.
    3. `test_research_wall_time_is_float`: `assert isinstance(result["wall_time"], float)` and `result["wall_time"] > 0`.
    4. `test_research_per_source_times_keys_match_results`: `set(result["per_source_times"].keys()) == set(result["results"].keys())`.
    5. `test_research_propagates_fetcher_exceptions`: Monkeypatch one of the fetchers to raise a `RuntimeError("simulated source failure")`. Calling `research(...)` MUST raise that `RuntimeError` (or a wrapping `concurrent.futures.BrokenExecutor`). Exception MUST surface from `f.result()`, not be swallowed.
    6. `test_research_no_asyncio_used`: Source-level grep — `import asyncio` and `httpx.AsyncClient` and `async def` MUST NOT appear in `research.py` (Phase 1.5 sync-only constraint; this test uses `inspect.getsource(research)` + string search).
    7. `test_submitted_at_captured_immediately_after_submit` (Pitfall 6 sentinel): Either inspect via `monkeypatch` of `time.monotonic` to count calls and assert the call-order matches submit-then-as_completed, or use a more lightweight grep-based check: `inspect.getsource(research)` MUST contain both `submitted_at[` and `as_completed(` patterns and MUST NOT contain the anti-pattern `t0 = time.monotonic()` immediately followed by `f.result()` inside a `for f in futures` loop.

    Note: tests 1-7 are sufficient for Task 3.1's GREEN gate. Task 3.2 adds the timing-bound `wall_time ≤ max(per_source_t_i) * 1.2` test which requires cassettes.

    Commit (RED): `test(phase-1-5): add failing tests for research.py fan-out (PERF-04 RED)`.
  </behavior>
  <action>
    Step 1 — Read `.planning/research/SOURCE-LIMITS.md` to determine the chosen Option (A/B/C). If the file does not exist on `merged-vision`, halt and surface "Plan 02 has not merged yet; Plan 03 cannot proceed."

    Step 2 — Add 7 RED tests to `packages/core/tests/test_research_parallelism.py`. Per CLAUDE.md TDD discipline: run `uv run pytest packages/core/tests/test_research_parallelism.py -x` — MUST FAIL with `ModuleNotFoundError: No module named 'tradewinds.research'`. Commit RED.

    Step 3 — Create `packages/core/src/tradewinds/research.py`. Use the skeleton from RESEARCH.md lines 463-505 ADAPTED to the chosen Option. Three variants:

    **Option A (max_workers=4 + module-level IEM Lock):**
    ```python
    """research.py — Phase 1.5 PERF-04 ThreadPoolExecutor fan-out.

    Phase 1.5 scope: ThreadPoolExecutor parallelism only. The DataFrame
    return-shape contract (PARITY-01) is delivered by Phase 3.

    Per .planning/research/SOURCE-LIMITS.md PERF-05 spike output (IEM shared-IP
    test): Option A confirmed. IEM ASOS and IEM CLI workers share a per-IP
    throttle budget at mesonet.agron.iastate.edu; without a Lock, 2 concurrent
    1-req/sec threads emit 2 req/sec to the same IP and trigger 503s.

    No asyncio, no httpx.AsyncClient, no async def — CLAUDE.md locks sync in v0.1.
    """
    from __future__ import annotations

    import concurrent.futures
    import threading
    import time
    from datetime import date
    from pathlib import Path
    from typing import Any

    _IEM_LOCK = threading.Lock()


    def _iem_asos_with_lock(*args, **kwargs):
        # Lazy import to break cross-package circular dep (matches RESEARCH-05 pattern).
        from tradewinds.weather._fetchers.iem_asos import download_iem_asos
        with _IEM_LOCK:
            return download_iem_asos(*args, **kwargs)


    def _iem_cli_with_lock(*args, **kwargs):
        from tradewinds.weather._fetchers.iem_cli import download_iem_cli
        with _IEM_LOCK:
            return download_iem_cli(*args, **kwargs)


    def research(
        station: str,
        from_date: date,
        to_date: date,
        *,
        dest_dir: Path | None = None,
    ) -> dict[str, Any]:
        """Phase 1.5 fan-out + join across AWC, IEM-ASOS, GHCNh, IEM-CLI.

        Phase 1.5 scope: ThreadPoolExecutor parallelism only. Returns a dict;
        Phase 3 will replace the return type with the v0.14.1-parity DataFrame
        shape per RESEARCH-01..05.
        """
        # Lazy imports avoid the cross-package circular dependency.
        from tradewinds.weather._fetchers.awc import fetch_awc_metars
        from tradewinds.weather._fetchers.ghcnh import download_ghcnh_range
        # Station resolution + dest_dir defaulting (omitted; see Phase 3 for full surface)

        submitted_at: dict[str, float] = {}
        futures: dict[concurrent.futures.Future, str] = {}
        t_start = time.monotonic()
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
            # Submission order is the ONE place where the timing-measurement Pitfall 6
            # is defused: we capture submitted_at[name] = time.monotonic() IMMEDIATELY
            # after ex.submit() returns, so per-source timing measures actual work, not
            # iteration-order accident.
            for name, fetch_args in [
                ("iem.archive", (_iem_asos_with_lock, station_info, from_date, to_date, dest_dir)),
                ("awc.live", (fetch_awc_metars, [station], 168)),
                ("ghcnh.archive", (download_ghcnh_range, station, from_date.year, to_date.year, dest_dir)),
                ("cli.archive", (_iem_cli_with_lock, station, from_date.year, to_date.year, dest_dir)),
            ]:
                fn, *args = fetch_args
                f = ex.submit(fn, *args)
                submitted_at[name] = time.monotonic()
                futures[f] = name

            results: dict[str, Any] = {}
            per_source_times: dict[str, float] = {}
            for f in concurrent.futures.as_completed(futures):
                name = futures[f]
                per_source_times[name] = time.monotonic() - submitted_at[name]
                results[name] = f.result()  # propagates exceptions

        wall_time = time.monotonic() - t_start
        return {
            "results": results,
            "wall_time": wall_time,
            "per_source_times": per_source_times,
        }
    ```

    **Option B (max_workers=3, IEM ASOS+CLI merged into single worker):**
    Same scaffold but the futures dict is:
    ```python
    for name, fetch_args in [
        ("iem", (_iem_combined, station, from_date, to_date, dest_dir)),  # ASOS then CLI serially
        ("awc.live", (fetch_awc_metars, [station], 168)),
        ("ghcnh.archive", (download_ghcnh_range, station, from_date.year, to_date.year, dest_dir)),
    ]:
        ...
    # max_workers=3
    ```
    Where `_iem_combined` is:
    ```python
    def _iem_combined(station, from_date, to_date, dest_dir):
        from tradewinds.weather._fetchers.iem_asos import download_iem_asos
        from tradewinds.weather._fetchers.iem_cli import download_iem_cli
        asos = download_iem_asos(station, from_date, to_date, dest_dir)
        cli = download_iem_cli(station, from_date.year, to_date.year, dest_dir)
        return {"asos": asos, "cli": cli}
    ```

    **Option C (max_workers=4, no Lock):**
    Same as Option A but without `_IEM_LOCK` and without the `_with_lock` wrappers. Direct import of `download_iem_asos` and `download_iem_cli`.

    **Pick the variant per SOURCE-LIMITS.md recommendation; document the choice in `research.py`'s module docstring with a quote from the spike output.**

    Step 4 — Modify `packages/core/src/tradewinds/__init__.py`. Add (preserve existing exports):
    ```python
    from tradewinds.research import research

    __all__ = [*(__all__ if "__all__" in dir() else []), "research"]
    ```

    If `__all__` doesn't exist yet, add `__all__ = ["research", ...other exports...]`.

    Step 5 — Run `uv run pytest packages/core/tests/test_research_parallelism.py -x -v`. All 7 RED tests MUST now pass. If `test_research_propagates_fetcher_exceptions` fails, you swallowed an exception somewhere — fix to use bare `f.result()`. If `test_submitted_at_captured_immediately_after_submit` fails, you have the Pitfall 6 anti-pattern — fix to capture `submitted_at[name] = time.monotonic()` IMMEDIATELY after `ex.submit()`.

    Step 6 — Run `uv run pytest -m "not live" -q` — full fast suite stays green. The recorded-fixture integration test from Task 3.2 is not yet present so the parallelism timing bound is not yet asserted.

    Step 7 — `uv run ruff check --fix .` + `uv run ruff format .`. Commit: `feat(phase-1-5): research.py ThreadPoolExecutor fan-out (PERF-04 GREEN; Option [A|B|C] per SOURCE-LIMITS.md)`.
  </action>
  <verify>
    <automated>uv run pytest packages/core/tests/test_research_parallelism.py -x -v && uv run pytest -m "not live" -q</automated>
  </verify>
  <acceptance_criteria>
    - `test -f packages/core/src/tradewinds/research.py` returns 0
    - `grep -c "def research" packages/core/src/tradewinds/research.py` returns ≥1
    - `grep -c "concurrent.futures.ThreadPoolExecutor" packages/core/src/tradewinds/research.py` returns 1
    - `grep -c "as_completed" packages/core/src/tradewinds/research.py` returns 1
    - `grep -c "submitted_at\[" packages/core/src/tradewinds/research.py` returns ≥1 (Pitfall 6 correct pattern present)
    - `grep -c "import asyncio\|httpx.AsyncClient\|async def" packages/core/src/tradewinds/research.py` returns 0 (no asyncio per CONTEXT.md lock)
    - If Option A or C chosen: `grep "max_workers=4" packages/core/src/tradewinds/research.py` returns non-empty
    - If Option B chosen: `grep "max_workers=3" packages/core/src/tradewinds/research.py` returns non-empty
    - If Option A chosen: `grep "_IEM_LOCK\|threading.Lock" packages/core/src/tradewinds/research.py` returns non-empty
    - `grep "Phase 3 will" packages/core/src/tradewinds/research.py` returns non-empty (ownership-boundary docstring per Open Q2)
    - `grep "from tradewinds.research import research" packages/core/src/tradewinds/__init__.py` returns non-empty
    - `uv run pytest packages/core/tests/test_research_parallelism.py -x -v` exits 0 with 7 passed
    - `uv run pytest -m "not live" -q` exits 0 (no regression)
    - `uv run ruff check packages/core/src/tradewinds/research.py` returns 0 errors
  </acceptance_criteria>
  <done>
    `research.py` exists with ThreadPoolExecutor fan-out, the chosen Option from SOURCE-LIMITS.md, the Pitfall 6 timing pattern, exception propagation, and no asyncio. Top-level `tradewinds.research(...)` works. 7 unit tests pass.
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 3.2: Recorded-fixture integration test — parallelism check via cassettes</name>
  <files>packages/core/tests/test_research_parallelism.py, packages/core/tests/cassettes/test_research_parallelism/test_wall_time_within_max_source_times.yaml (auto-generated by pytest-recording on first run)</files>
  <implements>PERF-04 parallelism assertion (wall_time ≤ max(per_source_t_i) * 1.2)</implements>
  <read_first>
    - .planning/phase-01-5-fetcher-optimization-cross-source-parallelism/RESEARCH.md (lines 547-566 — Test strategy for PERF-04; lines 560-566 — Option A/B for assertion design; Option B recommended: live for the bound, recorded for the "all 4 sources returned" structural check)
    - .planning/phase-01-5-fetcher-optimization-cross-source-parallelism/CONTEXT.md ("Parallelism check threshold" locked decision — `wall_time ≤ max(per_source_t_i) * 1.2`)
    - packages/core/tests/test_research_parallelism.py (from Task 3.1 — 7 tests already present)
    - tests/conftest.py if it exists (for any pytest-recording configuration)
  </read_first>
  <behavior>
    Per RESEARCH.md recommendation (line 564: "Option B recommended"), the parallelism timing bound `wall_time ≤ max(per_source_t_i) * 1.2` is asserted in the LIVE test (Task 3.3), NOT here. Cassette replay is instantaneous and the wall-time bound becomes `0.01ms * 1.2 = 0.012ms` — within scheduling noise, so the test would be flaky.

    Tests to add HERE (in addition to Task 3.1's 7 tests):

    8. `test_wall_time_within_max_source_times_live_only_marker` (documentation test): assert that the live test exists at `tests/test_live_perf.py::test_knyc_5yr_backfill_under_12min` (file + test name presence check via `pathlib.Path` + simple text read). This ties the cassette test to the live test so reviewers see the relationship.
    9. `test_all_four_sources_return_under_cassette_replay` (the structural cassette test): `@pytest.mark.vcr` decorated. First run records cassettes from a 7-day KNYC window across all 4 sources (so cassettes are ~tens of KB, not megabytes). Subsequent runs replay. Asserts:
       - `result["results"]` has the expected source keys (Option A/C: 4 keys; Option B: 3 keys).
       - `result["per_source_times"]` has the same keys.
       - No source's future raised (i.e. the dict comprehension over `f.result()` did not raise).
       - `result["wall_time"] > 0` and `< 60` (cassette replay should be sub-second on any modern machine; 60s is loose upper bound just to catch infinite loops).
    10. `test_cassette_replay_does_not_invoke_real_network`: assert by patching `httpx.get` and `httpx.post` to raise — replay must NOT trigger them (proves the cassette is intercepting the requests). If patching is too invasive, replace with a `httpx.Transport`-level mock or rely on pytest-recording's `disable_recording` mode.

    Commit (RED): `test(phase-1-5): add recorded-fixture integration tests for research.py fan-out structure (PERF-04)`.
  </behavior>
  <action>
    Step 1 — Add the 3 new tests (8, 9, 10) to `packages/core/tests/test_research_parallelism.py`. Use `pytest-recording` (vcrpy) per CLAUDE.md canonical choice. The decorator:
    ```python
    import pytest
    from pathlib import Path
    from datetime import date


    @pytest.mark.vcr(
        match_on=("method", "scheme", "host", "port", "path", "query"),
        record_mode="once",  # record on first run, replay subsequently
    )
    def test_all_four_sources_return_under_cassette_replay(tmp_path):
        from tradewinds.research import research

        result = research(
            station="KNYC",
            from_date=date(2024, 1, 1),
            to_date=date(2024, 1, 7),
            dest_dir=tmp_path,  # avoid touching ~/.tradewinds/cache
        )
        # Adjust expected source set per chosen Option
        if "iem.archive" in result["results"]:
            expected_sources = {"iem.archive", "awc.live", "ghcnh.archive", "cli.archive"}
        else:
            expected_sources = {"iem", "awc.live", "ghcnh.archive"}
        assert set(result["results"].keys()) == expected_sources
        assert set(result["per_source_times"].keys()) == expected_sources
        assert 0 < result["wall_time"] < 60.0


    def test_wall_time_within_max_source_times_live_only_marker():
        """Documentation: the actual timing bound is asserted in the live test."""
        live_test = Path(__file__).parent.parent.parent.parent / "tests" / "test_live_perf.py"
        assert live_test.exists()
        content = live_test.read_text()
        assert "test_knyc_5yr_backfill_under_12min" in content
        assert "wall_time" in content
    ```

    Step 2 — Configure pytest-recording in `pyproject.toml` if not already present. Add under `[tool.pytest.ini_options]`:
    ```toml
    [tool.pytest.ini_options]
    markers = [
        "live: marks tests that hit real public APIs (excluded from CI; run manually pre-publish)",
        "vcr: marks tests using pytest-recording cassettes",
    ]
    ```

    Verify with `uv run pytest --markers | grep -E "live|vcr"`.

    Step 3 — Run `uv run pytest packages/core/tests/test_research_parallelism.py -x -v --record-mode=once`. On first run, pytest-recording will capture cassettes for the 4 sources (KNYC 7-day window). This is a ONE-TIME live network hit during cassette capture; subsequent CI runs replay.

    Step 4 — Sanity-check the captured cassette file size. KNYC 7-day across 4 sources should be ~50-500 KB total. If a cassette is >5MB, the window is too wide — narrow to a 3-day window and re-capture.

    Step 5 — Run cassette replay (no `--record-mode`): `uv run pytest packages/core/tests/test_research_parallelism.py -x -v` — all 10 tests MUST pass without network.

    Step 6 — Filter sensitive data in cassettes if applicable (per RESEARCH.md, CLAUDE.md mentions filtering). For tradewinds, there are no API keys in URLs or headers — all sources are public-by-design. Verify no `Authorization` header or `?token=` parameter appears in any cassette via `grep -r "Authorization\|token=" packages/core/tests/cassettes/`.

    Step 7 — Commit cassettes + test code. `uv run ruff check --fix .`. Commit: `test(phase-1-5): cassette-replay integration test for research.py fan-out (PERF-04)`.
  </action>
  <verify>
    <automated>uv run pytest packages/core/tests/test_research_parallelism.py -x -v && uv run pytest -m "not live" -q</automated>
  </verify>
  <acceptance_criteria>
    - `test -d packages/core/tests/cassettes/test_research_parallelism/` returns 0 (cassette dir created)
    - At least one cassette file (e.g. `test_all_four_sources_return_under_cassette_replay.yaml`) exists in the cassette dir
    - `grep -c "@pytest.mark.vcr" packages/core/tests/test_research_parallelism.py` returns ≥1
    - `grep -c "def test_all_four_sources_return_under_cassette_replay" packages/core/tests/test_research_parallelism.py` returns 1
    - `grep -c "def test_wall_time_within_max_source_times_live_only_marker" packages/core/tests/test_research_parallelism.py` returns 1
    - `grep -r "Authorization\|token=" packages/core/tests/cassettes/` returns empty (no sensitive data leaked)
    - `uv run pytest packages/core/tests/test_research_parallelism.py -x -v` (cassette replay mode) exits 0 with 10 passed
    - `uv run pytest -m "not live" -q` exits 0 (no regression)
  </acceptance_criteria>
  <done>
    Recorded-fixture integration test exists; cassettes capture 4 sources × 7-day KNYC; replay is deterministic in CI; 10 unit/integration tests pass. The live timing-bound assertion is delegated to Task 3.3 per RESEARCH.md Option B.
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 3.3: Live performance test — KNYC 5-year backfill + other-station regression</name>
  <files>tests/test_live_perf.py</files>
  <implements>PERF-04 wall-time gate (KNYC 5-year ≤ 12 min; other-station regression against SOURCE-LIMITS.md baseline)</implements>
  <read_first>
    - .planning/phase-01-5-fetcher-optimization-cross-source-parallelism/CONTEXT.md ("Empirical performance gate" locked decision — KNYC 5-year ≤ 12 min; other-station regression from {KMDW, KLAX, KMIA} against per-station baseline; "Parallelism check threshold" — `wall_time ≤ max(per_source_t_i) * 1.2`)
    - .planning/research/SOURCE-LIMITS.md (per-station response-size measurements + the IEM-shared-IP option chosen)
    - .planning/ROADMAP.md (lines 43-46 — PERF-01 KNYC 5-year ≤ 12 min; PERF-04 parallelism check)
    - tests/test_parity.py (existing — see the conftest/fixtures structure; `tests/` is the workspace-level test dir, not under any single package)
    - CLAUDE.md (`@pytest.mark.live` for tests that hit real public APIs; excluded from CI per testing playbook; run manually before each publish)
  </read_first>
  <behavior>
    Tests to add to `tests/test_live_perf.py` (NEW file at workspace tests/ root):

    1. `test_knyc_5yr_backfill_under_12min`: `@pytest.mark.live` decorated. Calls `research(station="KNYC", from_date=date(2020,1,1), to_date=date(2024,12,31))`. Asserts:
       - `result["wall_time"] <= 12 * 60` (12 minutes in seconds)
       - `set(result["results"].keys())` contains all expected source keys
       - `result["per_source_times"]` has the same keys
       - Parallelism check: `result["wall_time"] <= max(result["per_source_times"].values()) * 1.2`
    2. `test_other_station_regression_within_baseline`: `@pytest.mark.live` decorated. Pick `KMDW` (or `KLAX` or `KMIA`). Per CONTEXT.md "no fixed cross-station threshold", read the per-station baseline from SOURCE-LIMITS.md (or hard-code from the latest spike). Asserts `result["wall_time"] <= station_baseline * 1.2`.

    Commit: `test(phase-1-5): live KNYC 5-year backfill + other-station regression (PERF-04 live gate)`.
  </behavior>
  <action>
    Step 1 — Create `tests/test_live_perf.py` (workspace tests/ root). Skeleton:

    ```python
    """Live performance tests — @pytest.mark.live; excluded from CI.

    Run manually pre-merge to merged-vision per Phase 1.5 ROADMAP.md gate:
      uv run pytest -m live tests/test_live_perf.py -v
    """
    from __future__ import annotations

    from datetime import date
    from pathlib import Path

    import pytest


    # Per-station baselines from .planning/research/SOURCE-LIMITS.md
    # (Updated when the PERF-05 spike is re-run, typically v0.2 milestone.)
    STATION_BASELINES_SECONDS = {
        "KNYC": 12 * 60,   # PR #85 measured 10 min for KNYC; 20% headroom = 12 min
        # Other-station regression: pick one and confirm against the spike-recorded
        # per-station baseline. The values here are illustrative; update from
        # SOURCE-LIMITS.md before running the live test.
        "KMDW": 12 * 60,
        "KLAX": 12 * 60,
        "KMIA": 12 * 60,
    }


    @pytest.mark.live
    def test_knyc_5yr_backfill_under_12min(tmp_path):
        from tradewinds.research import research

        result = research(
            station="KNYC",
            from_date=date(2020, 1, 1),
            to_date=date(2024, 12, 31),
            dest_dir=tmp_path,
        )

        # PERF-01 + PERF-03 + PERF-04 combined wall-time gate
        assert result["wall_time"] <= STATION_BASELINES_SECONDS["KNYC"], (
            f"KNYC 5-year backfill took {result['wall_time']:.1f}s "
            f"(baseline {STATION_BASELINES_SECONDS['KNYC']}s). "
            f"Per-source times: {result['per_source_times']}"
        )

        # PERF-04 parallelism check: no serial stall
        max_source_time = max(result["per_source_times"].values())
        assert result["wall_time"] <= max_source_time * 1.2, (
            f"Serial stall detected: wall_time={result['wall_time']:.1f}s, "
            f"max(per_source_t_i)={max_source_time:.1f}s, "
            f"ratio={result['wall_time']/max_source_time:.2f} (allowed ≤1.2)"
        )

        # Source-set sanity
        sources = set(result["results"].keys())
        assert "awc.live" in sources
        assert "ghcnh.archive" in sources
        assert ("iem.archive" in sources) or ("iem" in sources)  # Option A/C uses iem.archive; B uses iem


    @pytest.mark.live
    @pytest.mark.parametrize("station", ["KMDW"])  # other-station regression
    def test_other_station_regression_within_baseline(tmp_path, station):
        from tradewinds.research import research

        result = research(
            station=station,
            from_date=date(2020, 1, 1),
            to_date=date(2024, 12, 31),
            dest_dir=tmp_path,
        )

        baseline = STATION_BASELINES_SECONDS[station]
        assert result["wall_time"] <= baseline * 1.2, (
            f"{station} 5-year backfill took {result['wall_time']:.1f}s "
            f"(baseline {baseline}s + 20% headroom = {baseline * 1.2:.1f}s). "
            f"Per-source times: {result['per_source_times']}"
        )
    ```

    Step 2 — Verify the test is properly excluded from default CI run:
    ```bash
    uv run pytest tests/test_live_perf.py -m "not live" -v
    # Expected: 2 deselected (the live tests are skipped by the marker filter)
    ```

    Step 3 — Run the live tests MANUALLY (the user will do this; document the command in CHANGELOG and in the test file's module docstring):
    ```bash
    uv run pytest -m live tests/test_live_perf.py -v
    ```

    DO NOT run this in CI. Per CLAUDE.md, live tests run pre-publish.

    Step 4 — `uv run ruff check --fix .`. Commit: `test(phase-1-5): live perf gate for KNYC 5-year + other-station regression (PERF-04)`.

    NOTE: Claude does NOT execute the live test as part of this task. The user runs it manually before Task 3.4's merge prep. This task only CREATES the test file. The live run + verification happens in Task 3.4's checkpoint.
  </action>
  <verify>
    <automated>uv run pytest tests/test_live_perf.py -m "not live" -v</automated>
  </verify>
  <acceptance_criteria>
    - `test -f tests/test_live_perf.py` returns 0
    - `grep -c "@pytest.mark.live" tests/test_live_perf.py` returns ≥2 (both tests decorated)
    - `grep -c "def test_knyc_5yr_backfill_under_12min" tests/test_live_perf.py` returns 1
    - `grep -c "def test_other_station_regression_within_baseline" tests/test_live_perf.py` returns 1
    - `grep -c "max_source_time \* 1.2\|max(.*per_source_times.*) \* 1.2" tests/test_live_perf.py` returns ≥1 (parallelism check encoded)
    - `grep "STATION_BASELINES_SECONDS" tests/test_live_perf.py` returns non-empty
    - `uv run pytest tests/test_live_perf.py -m "not live" -v` shows 2 tests deselected
    - `uv run pytest tests/test_live_perf.py --collect-only -m live` lists 2 tests collected (proves the marker is applied)
    - `uv run ruff check tests/test_live_perf.py` returns 0 errors
  </acceptance_criteria>
  <done>
    Live perf test file exists with KNYC 5-year wall-time gate + parallelism-check assertion + other-station regression. Excluded from default CI run. Documented manual invocation command. Task 3.4 runs the live test as the merge gate.
  </done>
</task>

<task type="checkpoint:human-verify" gate="blocking">
  <name>Task 3.4: Live perf gate run + 5-fixture parity re-run + CHANGELOG + merge prep</name>
  <files>CHANGELOG.md</files>
  <implements>Phase 1.5 PERF-04 final merge gate (live wall-time + parity re-run + CHANGELOG)</implements>
  <read_first>
    - tests/test_live_perf.py (Task 3.3 output)
    - tests/test_parity.py (Phase 1 Wave 3 — 5-fixture sweep; MUST still pass after PERF-04 wiring)
    - CHANGELOG.md (existing entries from Plan 01 Task 1.4)
    - .planning/ROADMAP.md (Phase 1.5 success criteria items 1, 4, 5)
  </read_first>
  <what-built>
    Tasks 3.1–3.3 are complete: `research.py` with the chosen Option from SOURCE-LIMITS.md, cassette-replay integration tests, and the live perf gate test file. Now the user runs the live tests, re-runs the 5-fixture parity sweep (must still pass after PERF-04 — fan-out is orthogonal to the per-source CSV content, but verify), and updates CHANGELOG.
  </what-built>
  <how-to-verify>
    **Step A — Run the live perf gate (~10-12 min wall time):**

    ```bash
    uv run pytest -m live tests/test_live_perf.py -v 2>&1 | tee /tmp/phase15_live_perf.log
    ```

    Expected: 2 passed (KNYC 5-year ≤ 12 min; KMDW within baseline + 20% headroom). If either fails:
    - **Wall time exceeds gate but parallelism check passes:** the upstream APIs are slower than the spike baseline. Re-run the PERF-05 spike to refresh baselines; do NOT merge until gates align.
    - **Parallelism check fails (`wall_time > max(per_source) * 1.2`):** a serial stall exists. Most likely cause: the IEM-sharing Option (A/B/C) was misapplied. Re-read SOURCE-LIMITS.md and re-check `research.py`'s ThreadPoolExecutor structure.

    **Step B — Re-run 5-fixture parity sweep (MUST still pass — Phase 1 HARD GATE invariant):**

    ```bash
    uv run pytest tests/test_parity.py -x -v
    ```

    Expected: 5 passed. PERF-04 changes the CALL pattern (concurrent vs serial) but does NOT change the per-source CSV content, so parity should be unaffected. If a fixture drifts here AND Plan 01's parity-sweep was green, suspect a race condition where one source's data depends on another's — surface to user immediately; this would be a critical bug in the fan-out ordering.

    **Step C — Run full fast suite:**

    ```bash
    uv run pytest -m "not live" -q
    ```

    Expected: 0 failures.

    **Step D — Update CHANGELOG.md (under the same Unreleased / [Phase 1.5] heading Plan 01 created):**

    ```markdown
    ### Added
    - `tradewinds.research(station, from_date, to_date)` Phase 1.5 stub: concurrent fan-out of AWC + IEM-ASOS + GHCNh + IEM-CLI via `concurrent.futures.ThreadPoolExecutor`. **Return shape will change in Phase 3** (currently returns `dict`; Phase 3 returns v0.14.1-parity `DataFrame`). Lift target: PR #85 informed the chunker + timeout changes that this fan-out depends on.
    - `.planning/research/SOURCE-LIMITS.md` from the PERF-05 spike (max concurrent connections per source; IEM shared-IP throttle test).

    ### Changed
    - IEM ASOS + IEM CLI worker scheduling: [if Option A: uses a shared `threading.Lock` to respect the 1-sec per-IP throttle at `mesonet.agron.iastate.edu`. If Option B: ASOS + CLI execute serially within a single 'iem' worker. If Option C: no shared synchronization needed per empirical spike data.]
    ```

    Commit: `docs(phase-1-5): CHANGELOG note for research.py fan-out + SOURCE-LIMITS.md (PERF-04)`.

    **Step E — Final pre-merge checklist:**

    ```bash
    # 1. All Phase 1.5 tests green
    uv run pytest -m "not live" -q
    # 2. Parity sweep green (Day 3 HARD GATE invariant)
    uv run pytest tests/test_parity.py -x -v
    # 3. Live perf gate green
    uv run pytest -m live tests/test_live_perf.py -v   # already run in Step A
    # 4. Ruff + format + pre-commit
    uv run pre-commit run --all-files
    # 5. No asyncio leaked into research.py
    grep -c "import asyncio\|httpx.AsyncClient\|async def" packages/core/src/tradewinds/research.py  # MUST be 0
    # 6. No --no-verify used (confirm by checking git log on the branch)
    git log phase-1-5/wave-2/research-py-fanout --oneline
    ```

    All must pass before triggering the 3-reviewer panel.

    **Step F — Confirm to user:**

    Report:
    - Live KNYC wall_time: `[X] s` (gate: 720 s = 12 min)
    - Live KMDW wall_time: `[X] s` vs baseline `[Y] s + 20%`
    - Parallelism ratio (KNYC): `wall_time / max(per_source) = [X]` (gate: ≤ 1.2)
    - Parity sweep: 5/5 green
    - Fast suite: 0 failures
    - Chosen Option: A/B/C (per SOURCE-LIMITS.md)

    Type `approved` to commit CHANGELOG + trigger 3-reviewer panel + merge `phase-1-5/wave-2/research-py-fanout` to `merged-vision`. Type `redo-spike` if the wall-time gate is missed and the cause is upstream API drift (re-run Plan 02 spike to refresh baselines).
  </how-to-verify>
  <resume-signal>
    Type `approved` after all gates green (live perf + parity sweep + fast suite) to trigger 3-reviewer panel + merge. Type `redo-spike` if upstream API drift caused a gate miss. Type `rollback` if a critical bug requires reverting PERF-04 from this phase (PERF-01/02/03 still ship via Plan 01).
  </resume-signal>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| tradewinds → 4 public weather endpoints concurrently | Outbound HTTPS from up to 4 (or 3 for Option B) threads at once. |
| ThreadPoolExecutor worker exception propagation | Exceptions from per-source futures must surface, not be silently swallowed. |
| `_IEM_LOCK` (Option A only) | Single module-level lock arbitrating IEM ASOS + IEM CLI workers. |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-1.5-09 | Repudiation | Per-source exception swallowing | mitigate | The `f.result()` pattern (RESEARCH.md Pitfall — known Python issue) propagates exceptions; `test_research_propagates_fetcher_exceptions` (Task 3.1) explicitly tests this. No try/except wrapping per worker. |
| T-1.5-10 | Denial of Service (to remote) | 4-way fan-out hits 4 distinct endpoints concurrently | mitigate | Each fetcher preserves its own politeness pause (`IEM_POLITE_DELAY = 1.0`, AWC/GHCNh have none — verified empirically by PERF-05 spike). For Option A, `_IEM_LOCK` ensures only ONE IEM thread is in flight at a time, preserving the 1-sec/IP throttle compliance at `mesonet.agron.iastate.edu`. |
| T-1.5-11 | Tampering | `_IEM_LOCK` is module-level mutable state | accept | A single process-level Lock is the standard idiom for cross-thread synchronization in Python. Multi-process tradewinds usage would defeat the Lock — but tradewinds is a local SDK, not a service, so multi-process usage is rare. If it becomes a concern (v0.2 / hosted), use `filelock` at the IP level. Document this in `research.py` docstring for Option A. |
| T-1.5-12 | Information Disclosure | Cassettes captured in Task 3.2 | mitigate | Cassettes include real HTTP responses from public endpoints. Per RESEARCH.md, no auth headers / tokens in tradewinds requests (all sources are public-by-design). Task 3.2 grep-verifies `Authorization` and `token=` are absent. The cassette files are committed to version control; this is policy per pytest-recording usage in CLAUDE.md. |
| T-1.5-13 | Denial of Service (to self) | HTTP_TIMEOUT=60s × max_workers=4 = 4 min max worker-pool-stuck time per attack window | accept | Same as T-1.5-02 (residual from Plan 01). Worst case: a slow-loris remote endpoint serving 60s of trickled bytes ties up 4 worker threads. Tradewinds is a local SDK; the user is also the operator; restart-and-retry is acceptable. Revisit in v0.2 if hosted. |
</threat_model>

<verification>
| Check | Command | Expected |
|-------|---------|----------|
| `research.py` exists | `test -f packages/core/src/tradewinds/research.py` | exit 0 |
| `research()` is importable | `uv run python -c "from tradewinds.research import research; print(research)"` | "function" printed |
| Top-level re-export | `uv run python -c "import tradewinds; print(tradewinds.research)"` | "function" printed |
| 7 unit + 3 integration tests | `uv run pytest packages/core/tests/test_research_parallelism.py -x -v` | 10 passed |
| Cassette replay deterministic | `uv run pytest packages/core/tests/test_research_parallelism.py::test_all_four_sources_return_under_cassette_replay -x -v` (no `--record-mode`) | passed |
| Full fast suite | `uv run pytest -m "not live" -q` | 0 failures |
| Live perf gate | `uv run pytest -m live tests/test_live_perf.py -v` | 2 passed |
| 5-fixture parity sweep STILL green | `uv run pytest tests/test_parity.py -x -v` | 5 passed |
| No asyncio leak | `grep -c "import asyncio\|httpx.AsyncClient\|async def" packages/core/src/tradewinds/research.py` | 0 |
| Pitfall 6 correct pattern | `grep -c "submitted_at\[" packages/core/src/tradewinds/research.py` | ≥1 |
| Pre-commit | `uv run pre-commit run --all-files` | all green |
</verification>

<success_criteria>
- [ ] PERF-04: `tradewinds.research(station, from_date, to_date)` exists and is concurrent (4 or 3 workers per chosen Option from SOURCE-LIMITS.md)
- [ ] Per-source timing measurement uses `submitted_at` + `as_completed` (Pitfall 6 defused)
- [ ] If Option A: `_IEM_LOCK` is a module-level `threading.Lock` wrapping IEM workers only
- [ ] If Option B: IEM ASOS + IEM CLI are merged into a single `_iem_combined` worker; `max_workers=3`
- [ ] If Option C: no Lock; `max_workers=4`; rationale documented from spike data
- [ ] No asyncio / AsyncClient / async-def anywhere in `research.py`
- [ ] 10 tests pass in `packages/core/tests/test_research_parallelism.py` (7 from Task 3.1 + 3 from Task 3.2)
- [ ] Cassette replay works without live network
- [ ] Live perf gate green: KNYC 5-year ≤ 12 min AND parallelism check `wall_time ≤ max(per_source) * 1.2`
- [ ] Other-station regression green: KMDW (or chosen station) wall_time ≤ baseline × 1.2
- [ ] 5-fixture parity sweep STILL green (Phase 1 HARD GATE invariant preserved)
- [ ] CHANGELOG updated under `[Phase 1.5]` heading with PERF-04 entry
- [ ] Pre-commit hooks green; no `--no-verify`
- [ ] Branch `phase-1-5/wave-2/research-py-fanout` ready for 3-reviewer panel + merge
</success_criteria>

<output>
After completion, create `.planning/phase-01-5-fetcher-optimization-cross-source-parallelism/01-5-03-SUMMARY.md` documenting:

- `research.py` chosen Option (A/B/C) with citation to SOURCE-LIMITS.md
- Live KNYC 5-year wall_time + parallelism ratio (target ≤ 12 min, ≤ 1.2)
- Live other-station regression result
- 5-fixture parity sweep result (must be 5/5 — Phase 1 HARD GATE invariant)
- Commit hashes on `phase-1-5/wave-2/research-py-fanout`
- 3-reviewer panel verdict (PASS / REVISE iterations)
- Phase 1.5 closing summary: all 5 PERF-XX requirements green; Phase 2 unblocked
- Downstream signal for Phase 2: `research.py` exists as Phase 1.5 stub; Phase 3 will replace return type (documented in research.py docstring); Phase 2 catalog adapters can compose on top without rebuild
- Time spent (Claude execution + live test wall time + human review)
</output>

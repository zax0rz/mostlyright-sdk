---
phase: quick
plan: 260522-miq
type: execute
wave: 1
depends_on: []
files_modified:
  - .planning/phases/02.1-sprint-2o-lineage-refactor-per-source-provenance/02.1-PLAN-03-cache-layer-refactor.md
  - .planning/phases/02.1-sprint-2o-lineage-refactor-per-source-provenance/02.1-PLAN-04-integration-parity-gate.md
autonomous: true
requirements: [LINEAGE-02, LINEAGE-04]
user_setup: []

must_haves:
  truths:
    - "PLAN-03 Task 1 write_cache action block describes migrate-if-legacy-exists-and-no-ledger INSIDE the per-file lock, BEFORE the live-write append (so a write_cache that wins the lock race against a still-extant legacy file preserves legacy rows instead of clobbering them)"
    - "PLAN-03 threat T-02.1.3-02 description explicitly covers the write_cache-wins-the-race scenario and references migrate-if-needed-inside-lock as the mitigation"
    - "PLAN-03 Task 2 Test 9 (`test_auto_upgrade_does_not_race_with_concurrent_write_cache`) describes BOTH thread orderings (read-then-write AND write-then-read) so the write-wins case is exercised, not just the read-wins case"
    - "PLAN-04 Task 1 `_hardcoded_silver_class_b_same_priority_later_ts` builder lists the later-timestamp sibling FIRST and baseline (earliest) SECOND, so a buggy first-seen-wins implementation would pick the +200 marker (wrong) while earliest-timestamp-wins picks baseline (right) — the two strategies are now distinguishable by the test"
    - "PLAN-04 Task 1 `test_pre_flight_class_b_same_priority_later_ts_earliest_wins` docstring/comment cites the iter-6 P2 mitigation and explains the row order is deliberate"
    - "PLAN-04 class C builder remains correct (null-sibling-after-baseline → first-seen-wins picks baseline, null→'' lex-MIN picks null-sibling — different answers, already distinguishable). If review of the class C builder reveals an ordering issue, fix it; otherwise leave it."
  artifacts:
    - path: ".planning/phases/02.1-sprint-2o-lineage-refactor-per-source-provenance/02.1-PLAN-03-cache-layer-refactor.md"
      provides: "Updated write_cache action with migrate-inside-lock + updated T-02.1.3-02 + updated Test 9 docstring"
      contains: "migrate-if-needed"
    - path: ".planning/phases/02.1-sprint-2o-lineage-refactor-per-source-provenance/02.1-PLAN-04-integration-parity-gate.md"
      provides: "Class B builder rewritten with later-ts row listed FIRST + test docstring updated"
      contains: "later_siblings"
  key_links:
    - from: ".planning/phases/02.1-sprint-2o-lineage-refactor-per-source-provenance/02.1-PLAN-03-cache-layer-refactor.md"
      to: "T-02.1.3-02 threat register entry"
      via: "single-lock + migrate-if-needed-inside-lock pattern"
      pattern: "migrate-if-needed-inside-lock"
    - from: ".planning/phases/02.1-sprint-2o-lineage-refactor-per-source-provenance/02.1-PLAN-04-integration-parity-gate.md"
      to: "test_pre_flight_class_b_same_priority_later_ts_earliest_wins"
      via: "later-ts row listed FIRST so first-seen-wins would pick it (wrong)"
      pattern: "later_siblings.*\\+.*baseline"
---

<objective>
Fix 2 HIGH-severity findings from codex iteration 6 review on the Phase 2.1 planning artifacts. Both findings concern test/spec design — they don't introduce bugs in source code (none exists yet), but they let a buggy implementation slip through the parity gate. This quick task patches the PLAN.md specs so the iter-6 issues never reach the executor.

**Finding 1 (codex P1, HIGH, PLAN-03):** F2's unification put `write_cache` and `read_cache` auto-upgrade on the same per-file `.lock` sibling. That serializes them but does NOT synchronize the order of operations. If `write_cache` acquires the lock FIRST while `legacy_p` still exists and `ledger_p` doesn't, it creates `ledger_p` with only the new live rows. The subsequent `read_cache` sees `ledger_p` exists → SKIPS migration → silent legacy data loss. Fix: extend write_cache's locked region to migrate-if-needed FIRST before appending live rows.

**Finding 2 (codex P2, HIGH, PLAN-04):** The class-B builder lists baseline (T0) FIRST, then later-ts sibling. A buggy first-seen-wins impl that ignores `source_received_at` would still pick baseline — same answer as the correct earliest-timestamp impl. The test passes for the WRONG reason. Fix: reverse the order so later-ts comes first and baseline (earliest) comes second — first-seen-wins now picks the +200 marker (test fails as intended), earliest-timestamp-wins still picks baseline (test passes for the right reason).

Purpose: Tighten the Phase 2.1 spec before execution so iter-6's two HIGH findings are eliminated at the source. No production code touched. No test code touched. Only `.planning/` artifacts.

Output: Two PLAN.md files edited. Two atomic commits (one per finding).
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@.planning/REVIEW-DISCIPLINE.md
@.planning/phases/02.1-sprint-2o-lineage-refactor-per-source-provenance/02.1-PLAN-03-cache-layer-refactor.md
@.planning/phases/02.1-sprint-2o-lineage-refactor-per-source-provenance/02.1-PLAN-04-integration-parity-gate.md
</context>

<tasks>

<task type="auto">
  <name>Task 1: Patch PLAN-03 to close the write_cache-wins-the-race silent-data-loss path (codex iter-6 P1)</name>
  <files>.planning/phases/02.1-sprint-2o-lineage-refactor-per-source-provenance/02.1-PLAN-03-cache-layer-refactor.md</files>
  <read_first>
    - .planning/phases/02.1-sprint-2o-lineage-refactor-per-source-provenance/02.1-PLAN-03-cache-layer-refactor.md in full (you need the line numbers post-F2 to land the edits cleanly: Task 1 action block ~144-186, threat T-02.1.3-02 ~411, Test 9 ~223)
  </read_first>
  <action>
    Three coordinated edits inside 02.1-PLAN-03-cache-layer-refactor.md. All edits land under `.planning/` only — NO source code touched.

    **Edit A — Task 1 action block (write_cache rewrite, lines ~144-186):**

    The current step 3 says (paraphrased): generate ingestion_id, enrich rows, append-or-create at ledger_p, all under FileLock. The fix is to RESTRUCTURE step 3 so the migrate-if-legacy-exists check runs INSIDE the lock, BEFORE the live-write append. Replace the current step 3 body with:

    ```
    3. Rewrite write_cache(station, year, month, rows):
       a. Acquire FileLock on `<ledger_p>.lock` sibling (same lock object used by read_cache auto-upgrade and explicit migrate_to_v2 — single lock pattern across all three paths).
       b. INSIDE the lock — migrate-if-needed FIRST (codex iter-6 P1 mitigation): if `ledger_p` does NOT exist AND `legacy_p` exists, call `_legacy_v014_to_v021_migration(legacy_p, ledger_p, station, year, month)` to produce `ledger_p` with provenance="legacy" rows, then rename `legacy_p` → `legacy_p.with_suffix(".parquet.legacy")` via `os.replace` (cross-platform atomic). This guarantees no write_cache can "win" the lock race and clobber legacy data — by the time the live-row append runs, legacy rows are already persisted in ledger_p.
       c. Generate ingestion_id (per-call UUID4) and source_received_at (per-call) as before.
       d. Enrich rows with 9 lineage fields (provenance=None for live writes; the existing legacy rows already in ledger_p from step b have provenance="legacy" — APPEND new rows, do not overwrite the migrated ones).
       e. Build pa.Table from enriched live rows; if ledger_p exists (from step b OR a prior write_cache call), read existing via pq.read_table, concat new table via pa.concat_tables([existing, new]), atomic write. Otherwise (neither ledger_p nor legacy_p existed at step b) atomic write directly.
       f. Release lock.
    ```

    Preserve the surrounding step numbering (step 4 "Do NOT delete the existing function signature", step 5 "no env-var reads", step 6 "climate untouched", step 7 "write tests/test_cache_silver_write.py") — only step 3 is being rewritten.

    Also update step 3h (the QC sidecar mkdir line) — keep it but move it AFTER step 3f (lock release) so the mkdir isn't inside the per-file lock (it's a separate concern; doing mkdir inside the lock just slows the hot path with no correctness benefit).

    **Edit B — Threat register T-02.1.3-02 (line ~411):**

    Locate the row in the STRIDE Threat Register table where `Threat ID == T-02.1.3-02`. Replace the Component description and Mitigation Plan with:

    - Component: `Auto-upgrade race scenarios: (a) two read_cache processes try to migrate same legacy file simultaneously; (b) a read_cache auto-upgrade races with a concurrent write_cache on the same (station, year, month); (c) NEW (codex iter-6 P1): a write_cache call wins the lock race against a still-extant legacy file — without migrate-if-needed-inside-lock, write_cache would create ledger_p with only live rows, the subsequent read_cache would see ledger_p exists and SKIP migration, and the 5 legacy rows would be lost silently with .parquet.legacy rename never happening.`
    - Mitigation Plan: `UNIFIED FileLock pattern + migrate-if-needed-inside-lock: both write_cache (Task 1 step 3a-b) AND read_cache auto-upgrade (Task 2 step 4e) acquire the per-file .lock sibling (same lock object) AND run migrate-if-legacy-exists FIRST inside the lock before any live-row append or read. This guarantees: (1) only one process performs the migration, (2) no race-related data loss regardless of which call wins the lock, (3) the .parquet.legacy rename always happens. Inside the lock, re-check ledger_p.exists() so a process that lost the race becomes a no-op. RESEARCH Risk 3 mitigation extended to cover the write-wins case (codex iter-6 P1 finding).`

    **Edit C — Task 2 Test 9 docstring (line ~223):**

    Locate the `behavior` block for Task 2, find `Test 9: test_auto_upgrade_does_not_race_with_concurrent_write_cache`. Replace its body with:

    ```
    - Test 9: `test_auto_upgrade_does_not_race_with_concurrent_write_cache` — Pre-populate `observations/KNYC/2024/01.parquet` (legacy file with 5 known rows; observed_at hours 0..4). Spawn two `threading.Thread` workers in BOTH orderings to explicitly exercise both lock-acquisition winners (codex iter-6 P1 mitigation):
      - **Order A (read wins lock first):** thread A calls `read_cache("KNYC", 2024, 1)` (triggers auto-upgrade migration), thread B calls `write_cache("KNYC", 2024, 1, new_rows)` where `new_rows` = 5 NEW silver rows (observed_at hours 5..9, disjoint from legacy).
      - **Order B (write wins lock first — THE iter-6 P1 case):** thread B starts FIRST and acquires the per-file lock before thread A. Without migrate-if-needed-inside-lock, write_cache would create ledger_p with only the 5 live rows, then thread A's read_cache would see ledger_p exists and SKIP migration, losing the 5 legacy rows silently. With the iter-6 fix, write_cache's locked region migrates legacy FIRST inside the lock, so the final state is identical regardless of which thread wins.
      For BOTH orderings assert: (a) `observations_ledger/KNYC/2024/01.parquet` exists, (b) it contains BOTH the 5 migrated legacy rows (with `provenance == "legacy"`) AND the 5 newly written live rows (with `provenance is None`), totalling 10 rows, (c) `observations/KNYC/2024/01.parquet.legacy` exists (legacy renamed via os.replace). The test must run BOTH orderings (parametrize or two separate test functions sharing a helper) so the write-wins case is genuinely exercised — without this, a regression that only breaks the write-wins ordering would slip through.
    ```

    Also bump Task 2's `acceptance_criteria` test count from "8 tests PASSED" to "9 tests PASSED" if Order A/B is implemented as one parametrized test (count stays at 9 = 8 original + Test 9 itself), OR to "10 tests PASSED" if Order A and Order B are two separate test functions. Use the parametrized form (count = 9; mention "9 tests PASSED (Test 9 parametrized over Order A and Order B)" in the acceptance criterion). Update the `done` line for Task 2 accordingly: "10 silver+gold tests pass" → "9 silver+gold tests pass (Test 9 parametrized over both lock-race orderings)". Actually verify the post-Edit-C test count carefully: Task 2 currently lists 8 tests + Test 9 = 9 tests in behavior; the acceptance line says "all 18 silver+gold tests pass (10 + 8)" which already counts 9 in Task 2 — keep the 19 total (10 + 9). The Order A/B parametrization keeps the COUNT at 9; only the docstring grows. Confirm the `pytest -v` output line still reads "all 19 tests PASSED (10 + 9)".

    **Commit:** Use a single atomic commit for all three edits in this task. Commit message:
    ```
    docs(02.1-plan-03): close write_cache-wins-race silent-data-loss path (codex iter-6 P1)

    - Restructure write_cache step 3 so migrate-if-legacy-exists runs INSIDE the
      per-file lock BEFORE the live-row append. Guarantees that even if
      write_cache wins the lock race against a still-extant legacy file, the
      5 migrated legacy rows land in ledger_p before live rows are appended,
      and .parquet.legacy rename happens. Without this, write_cache would
      create ledger_p with only live rows, the subsequent read_cache would
      see ledger_p exists and SKIP migration, silently losing legacy data.
    - Update T-02.1.3-02 mitigation to cite migrate-if-needed-inside-lock as
      the race-closure mechanism for the write-wins case.
    - Update Test 9 docstring to exercise BOTH thread orderings (Order A:
      read wins lock; Order B: write wins lock) so the write-wins case is
      explicitly tested. Without Order B, a regression that only breaks
      the write-wins path would slip through.

    Scope: planning artifact only; no source code change.
    Ref: codex iteration 6 P1 finding on PLAN-03 Task 1 action + T-02.1.3-02.
    ```
  </action>
  <verify>
    <automated>grep -c "migrate-if-needed FIRST" .planning/phases/02.1-sprint-2o-lineage-refactor-per-source-provenance/02.1-PLAN-03-cache-layer-refactor.md | awk '$1 >= 1 {exit 0} {exit 1}' && grep -c "codex iter-6 P1" .planning/phases/02.1-sprint-2o-lineage-refactor-per-source-provenance/02.1-PLAN-03-cache-layer-refactor.md | awk '$1 >= 2 {exit 0} {exit 1}' && grep -c "Order A\|Order B" .planning/phases/02.1-sprint-2o-lineage-refactor-per-source-provenance/02.1-PLAN-03-cache-layer-refactor.md | awk '$1 >= 2 {exit 0} {exit 1}' && grep -c "migrate-if-needed-inside-lock" .planning/phases/02.1-sprint-2o-lineage-refactor-per-source-provenance/02.1-PLAN-03-cache-layer-refactor.md | awk '$1 >= 1 {exit 0} {exit 1}'</automated>
  </verify>
  <done>
    PLAN-03 Task 1 action block restructured so migrate-if-needed runs inside the per-file lock BEFORE the live-row append. T-02.1.3-02 mitigation extended to cite the write-wins case explicitly. Test 9 docstring describes both thread orderings (Order A read-wins, Order B write-wins). Single atomic commit. No source code touched.
  </done>
</task>

<task type="auto">
  <name>Task 2: Patch PLAN-04 class-B builder so first-seen-wins and earliest-timestamp-wins give DIFFERENT answers (codex iter-6 P2)</name>
  <files>.planning/phases/02.1-sprint-2o-lineage-refactor-per-source-provenance/02.1-PLAN-04-integration-parity-gate.md</files>
  <read_first>
    - .planning/phases/02.1-sprint-2o-lineage-refactor-per-source-provenance/02.1-PLAN-04-integration-parity-gate.md in full. Confirm current line numbers: `_hardcoded_silver_class_b_same_priority_later_ts` builder ~252-272, `test_pre_flight_class_b_same_priority_later_ts_earliest_wins` ~348-370, `_hardcoded_silver_class_c_same_priority_null_ts` ~275-295.
  </read_first>
  <action>
    Three coordinated edits inside 02.1-PLAN-04-integration-parity-gate.md. All edits land under `.planning/` only — NO source code touched, NO test code touched (test code does not exist yet; PLAN-04 is the spec that generates it).

    **Edit A — `_hardcoded_silver_class_b_same_priority_later_ts` builder (lines ~252-272):**

    Replace the current builder body (which lists baseline FIRST, then appends later-iem siblings) with the corrected version that lists later-iem siblings FIRST and baseline (earliest) SECOND. Replace the entire function with:

    ```python
    def _hardcoded_silver_class_b_same_priority_later_ts(station: str) -> list[dict]:
        # Class (b) — SAME-PRIORITY + LATER source_received_at: iem baseline (ts=T0) +
        # iem sibling (ts=T0+later) per row. NO awc — so strict-> on source_priority is a TIE
        # and the secondary key `source_received_at ASCENDING` decides the winner.
        # `query_time_merge` picks the EARLIEST source_received_at (baseline).
        #
        # IMPORTANT (codex iter-6 P2 mitigation): the later-timestamp sibling is listed
        # FIRST in the synthetic list and baseline (earliest) is listed SECOND. This
        # ordering is deliberate so that a buggy first-seen-wins implementation (one that
        # IGNORES source_received_at entirely and just picks whichever row appears first
        # in the input iteration) would pick the +200 marker — WRONG — and the test
        # would fail loudly. The correct earliest-timestamp-wins implementation picks
        # baseline regardless of input order. Without this reversal, first-seen-wins
        # and earliest-timestamp-wins would happen to agree by coincidence of row order,
        # and the test would pass for the WRONG reason.
        # Total: 20 rows synthesized (10 later-iem + 10 baseline), must collapse to 10 winners.
        baseline = _hardcoded_silver_no_duplicates(station)
        later_siblings = [
            {
                **b,
                "source": "iem",
                "ingestion_id": f"synth:later_iem:{station}:{i:04d}",
                "source_received_at": "2099-12-31T23:59:59.999999+00:00",
                "temp_c": b["temp_c"] + 200.0,  # marker — if this wins, the impl is first-seen-wins (BUG)
            }
            for i, b in enumerate(baseline)
        ]
        synthetic = list(later_siblings) + list(baseline)
        return synthetic
    ```

    **Edit B — `test_pre_flight_class_b_same_priority_later_ts_earliest_wins` docstring (lines ~348-370):**

    Locate the test function. In its current docstring (the `#` comment block at the top of the function body), update the wording to cite the iter-6 P2 mitigation explicitly. Replace the existing comment block with:

    ```python
        # Class (b): iem(2) baseline + iem(2) later-ts sibling. strict-> on source_priority
        # is a tie; secondary key `source_received_at ASCENDING` picks the baseline (earlier
        # ts wins). Asserts ONLY `query_time_merge`'s behavior — does NOT compare to legacy
        # because legacy uses first-seen-at-equal-priority.
        #
        # CRITICAL (codex iter-6 P2 mitigation): the builder
        # `_hardcoded_silver_class_b_same_priority_later_ts` lists the later-timestamp
        # sibling FIRST and baseline (earliest) SECOND specifically to disambiguate the
        # two competing semantics:
        #   - first-seen-wins (BUG): picks the +200 marker → test fails (as intended)
        #   - earliest-timestamp-wins (CORRECT): picks baseline → test passes for the
        #     right reason
        # Without this row-order reversal, both strategies would coincidentally agree
        # on the baseline row (the first one in iteration order under the old ordering),
        # and the test would pass for a buggy impl. The deliberate ordering forces the
        # strategies to disagree on the wrong answer, so only the correct impl passes.
    ```

    Leave the assertion bodies (`for i, n in enumerate(new_sorted): ...`) UNCHANGED. The fix is the BUILDER row order + the test DOCSTRING; the assertions already test the right thing (baseline temp_c = 5.0 + i, NOT 5.0 + i + 200).

    **Edit C — Class C builder review (lines ~275-295):**

    Read the current `_hardcoded_silver_class_c_same_priority_null_ts` builder. In class C:
    - baseline has source_received_at = "2025-01-15T11:00:00.000000+00:00" (a real RFC3339 timestamp)
    - null-sibling has source_received_at = None

    The merge engine coerces `r.get("source_received_at") or ""` so None → "" which lex-sorts BEFORE any RFC3339 string. So:
    - first-seen-wins (buggy) → picks baseline (listed first)
    - null→"" lex-MIN (correct) → picks null-sibling

    These two strategies give DIFFERENT answers regardless of row order — the test already distinguishes them. **Conclusion: class C is fine as-is; do NOT reverse the row order for class C.** Add a comment to the class C builder confirming this analysis. Insert this comment block just before the `synthetic = list(baseline); for i, b in enumerate(baseline): synthetic.append(...)` lines:

    ```python
        # Note (codex iter-6 P2 review): class C builder lists baseline FIRST, null-sibling
        # SECOND. This is INTENTIONALLY DIFFERENT from class B (which lists later-ts FIRST).
        # Reason: class C's two competing semantics already give DIFFERENT answers regardless
        # of row order — first-seen-wins picks baseline (a real RFC3339 timestamp), while the
        # correct null→"" lex-MIN coercion picks the null-sibling. The test is already
        # disambiguating; no row-order reversal needed. Leaving the natural baseline-first
        # order keeps the builder readable.
    ```

    Leave the rest of the class C builder UNCHANGED. The assertion in `test_pre_flight_class_c_same_priority_null_ts_null_wins` already expects null-sibling to win (`expected_temp = 5.0 + i + 300.0`).

    **Commit:** Use a single atomic commit for all three edits in this task. Commit message:
    ```
    docs(02.1-plan-04): separate first-seen-wins from earliest-ts-wins in class B (codex iter-6 P2)

    - Reverse the row order in _hardcoded_silver_class_b_same_priority_later_ts:
      list later-timestamp sibling FIRST, baseline (earliest) SECOND. Now a buggy
      first-seen-wins impl would pick the +200 marker (test fails as intended),
      while the correct earliest-timestamp-wins impl picks baseline. Without
      this reversal the two strategies coincidentally agreed on baseline and
      the test passed for the wrong reason.
    - Update test_pre_flight_class_b_same_priority_later_ts_earliest_wins
      docstring to cite the iter-6 P2 mitigation and explain the deliberate
      row order.
    - Add review comment to _hardcoded_silver_class_c_same_priority_null_ts
      confirming class C does NOT need the same reversal — null→"" coercion
      already produces different answers from first-seen-wins regardless of
      row order, so the test already disambiguates correctly.

    Scope: planning artifact only; no test or source code change (PLAN-04 is
    the spec that will generate the test code in Wave 4 execution).
    Ref: codex iteration 6 P2 finding on PLAN-04 class-B builder ordering.
    ```
  </action>
  <verify>
    <automated>grep -c "list(later_siblings) + list(baseline)" .planning/phases/02.1-sprint-2o-lineage-refactor-per-source-provenance/02.1-PLAN-04-integration-parity-gate.md | awk '$1 >= 1 {exit 0} {exit 1}' && grep -c "codex iter-6 P2" .planning/phases/02.1-sprint-2o-lineage-refactor-per-source-provenance/02.1-PLAN-04-integration-parity-gate.md | awk '$1 >= 2 {exit 0} {exit 1}' && grep -c "INTENTIONALLY DIFFERENT from class B" .planning/phases/02.1-sprint-2o-lineage-refactor-per-source-provenance/02.1-PLAN-04-integration-parity-gate.md | awk '$1 >= 1 {exit 0} {exit 1}' && grep -c "later_siblings" .planning/phases/02.1-sprint-2o-lineage-refactor-per-source-provenance/02.1-PLAN-04-integration-parity-gate.md | awk '$1 >= 2 {exit 0} {exit 1}'</automated>
  </verify>
  <done>
    PLAN-04 class-B builder reordered (later-ts FIRST, baseline SECOND) so first-seen-wins and earliest-timestamp-wins give different answers. Test docstring cites iter-6 P2 mitigation. Class C builder annotated to document why it does NOT need the same reversal. Single atomic commit. No source code or test code touched.
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| planning artifacts → executor | PLAN.md is the prompt for Wave 3/Wave 4 execution. A wrong literal, formula, or row order propagates straight into implementation and can silently corrupt the parity gate. REVIEW-DISCIPLINE.md "never-skip" rule applies (planning artifacts with code-like fragments). |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-miq-01 | T (Tampering) | This quick task accidentally introduces a regression in PLAN-03's lock semantics (e.g. moves the FileLock acquisition outside the migrate-then-append region) | mitigate | Task 1 verify command greps for "migrate-if-needed FIRST" + "migrate-if-needed-inside-lock" — both phrases must be present, confirming the migrate-inside-lock invariant is documented. Diff review by user before merge. |
| T-miq-02 | T (Tampering) | This quick task accidentally breaks the class-B builder so the `+200` marker no longer flags first-seen-wins bugs (e.g. drops the +200 increment) | mitigate | Task 2 verify command greps for "list(later_siblings) + list(baseline)" — exact ordering literal. If absent, the reversal didn't land. |
| T-miq-03 | I (Information disclosure) | The two atomic commits leak the codex finding IDs in commit messages | accept | Codex findings are internal review artifacts; their IDs (P1, P2) are not sensitive. Commit messages cite "codex iter-6 P1/P2" intentionally for traceability. |
</threat_model>

<verification>
After both tasks complete:

1. **PLAN-03 invariants present:**
   - `grep -c "migrate-if-needed FIRST" .planning/phases/02.1-sprint-2o-lineage-refactor-per-source-provenance/02.1-PLAN-03-cache-layer-refactor.md` → ≥ 1
   - `grep -c "migrate-if-needed-inside-lock" .planning/phases/02.1-sprint-2o-lineage-refactor-per-source-provenance/02.1-PLAN-03-cache-layer-refactor.md` → ≥ 1
   - `grep -c "codex iter-6 P1" .planning/phases/02.1-sprint-2o-lineage-refactor-per-source-provenance/02.1-PLAN-03-cache-layer-refactor.md` → ≥ 2 (action block + threat register + Test 9)
   - `grep -c "Order A\|Order B" .planning/phases/02.1-sprint-2o-lineage-refactor-per-source-provenance/02.1-PLAN-03-cache-layer-refactor.md` → ≥ 2 (both orderings mentioned in Test 9)
   - `grep -c "write_cache can \"win\" the lock race\|write-wins" .planning/phases/02.1-sprint-2o-lineage-refactor-per-source-provenance/02.1-PLAN-03-cache-layer-refactor.md` → ≥ 1

2. **PLAN-04 invariants present:**
   - `grep -c "list(later_siblings) + list(baseline)" .planning/phases/02.1-sprint-2o-lineage-refactor-per-source-provenance/02.1-PLAN-04-integration-parity-gate.md` → ≥ 1
   - `grep -c "codex iter-6 P2" .planning/phases/02.1-sprint-2o-lineage-refactor-per-source-provenance/02.1-PLAN-04-integration-parity-gate.md` → ≥ 2 (builder docstring + test docstring)
   - `grep -c "INTENTIONALLY DIFFERENT from class B" .planning/phases/02.1-sprint-2o-lineage-refactor-per-source-provenance/02.1-PLAN-04-integration-parity-gate.md` → ≥ 1 (class C review comment)
   - `grep -c "later_siblings" .planning/phases/02.1-sprint-2o-lineage-refactor-per-source-provenance/02.1-PLAN-04-integration-parity-gate.md` → ≥ 2 (builder + comment)

3. **No collateral damage:**
   - `git diff --stat HEAD~2..HEAD` shows ONLY the two PLAN.md files changed. NO source code, NO tests, NO other planning artifacts.
   - `find . -name "*.py" -newer .planning/quick/260522-miq-fix-2-codex-iteration-6-findings-write-w/260522-miq-PLAN.md` returns empty (no Python files modified after this plan was written).

4. **Atomic commit discipline:**
   - `git log --oneline -2` shows two commits, one per task, each referencing the corresponding codex finding (P1, P2).

5. **REVIEW-DISCIPLINE.md compliance:** This quick task touches planning artifacts with code-like fragments (action block code blocks, threat-register Component/Mitigation text, builder function bodies). Per REVIEW-DISCIPLINE.md "never-skip — planning artifact whose diff contains code, schema fragments, priority constants, fixture rows, or success-criterion threshold numbers", the two-reviewer loop (Codex high + Python Architect) MUST run before merging to `merged-vision`. Do NOT use `[review-skip: trivial]`.
</verification>

<success_criteria>
- PLAN-03 write_cache action block restructured so migrate-if-needed-inside-lock runs BEFORE live-row append. ✓
- PLAN-03 T-02.1.3-02 mitigation cites the write-wins case explicitly. ✓
- PLAN-03 Test 9 docstring exercises BOTH thread orderings (Order A read-wins, Order B write-wins). ✓
- PLAN-04 class-B builder lists later-ts row FIRST, baseline SECOND, so first-seen-wins and earliest-timestamp-wins give DIFFERENT answers. ✓
- PLAN-04 class-B test docstring cites iter-6 P2 mitigation. ✓
- PLAN-04 class-C builder annotated to document why it does NOT need the same reversal. ✓
- Two atomic commits, one per finding, each referencing codex iter-6 P1/P2 in the commit message. ✓
- Only `.planning/` files touched — NO source code, NO tests, NO other planning artifacts.
</success_criteria>

<output>
After completion, no SUMMARY.md is required for this quick task (per /gsd-quick convention — STATE.md "Quick Tasks Completed" table gets a single-row entry instead). Update STATE.md as part of the second commit OR as a separate trailing edit: add row to "Quick Tasks Completed" table:

```
| 260522-miq | Fix 2 codex iteration 6 findings (write-wins race in PLAN-03 + class-B order in PLAN-04) | 2026-05-22 | <COMMIT_SHA> | [260522-miq-fix-2-codex-iteration-6-findings-write-w](./quick/260522-miq-fix-2-codex-iteration-6-findings-write-w/) |
```

(The COMMIT_SHA can be either of the two atomic commits — pick the second, since it's the most recent and the row represents the task as a whole.)
</output>

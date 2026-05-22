---
phase: quick
plan: 260522-miq
type: execute
wave: 1
completed: 2026-05-22
status: complete
requirements: [LINEAGE-02, LINEAGE-04]
commits:
  - cdae0fb: "docs(02.1-plan-03): close write_cache-wins-race silent-data-loss path (codex iter-6 P1)"
  - 6c3c282: "docs(02.1-plan-04): separate first-seen-wins from earliest-ts-wins in class B (codex iter-6 P2)"
files_modified:
  - .planning/phases/02.1-sprint-2o-lineage-refactor-per-source-provenance/02.1-PLAN-03-cache-layer-refactor.md
  - .planning/phases/02.1-sprint-2o-lineage-refactor-per-source-provenance/02.1-PLAN-04-integration-parity-gate.md
---

# Quick Task 260522-miq Summary: Fix 2 Codex Iteration 6 Findings

## One-liner

Patched PLAN-03 to close write_cache-wins-the-race silent-data-loss path (codex iter-6 P1) and patched PLAN-04 class-B builder so first-seen-wins and earliest-timestamp-wins give distinguishable answers (codex iter-6 P2). Two atomic commits to planning artifacts only; no source code touched.

## Objective

Fix 2 HIGH-severity findings from codex iteration 6 review on the Phase 2.1 planning artifacts (PLAN-03 cache layer refactor + PLAN-04 integration parity gate). Both findings concern test/spec design — they don't introduce bugs in source code (none exists yet), but they let a buggy implementation slip through the parity gate. This quick task patches the PLAN.md specs so the iter-6 issues never reach the executor.

## What Was Done

### Task 1: PLAN-03 — Close write_cache-wins-the-race silent-data-loss path (codex iter-6 P1)

Three coordinated edits inside `.planning/phases/02.1-sprint-2o-lineage-refactor-per-source-provenance/02.1-PLAN-03-cache-layer-refactor.md`:

**Edit A — Restructured write_cache step 3 (action block, ~lines 144-186):**

Replaced the old "generate ingestion_id → enrich rows → append-or-create" sequence with a 7-substep sequence that puts the migrate-if-needed-inside-lock invariant up front:

1. step 3a: Acquire FileLock on `<ledger_p>.lock` — SAME lock object used by read_cache auto-upgrade (Task 2 step 4e) and explicit migrate_to_v2.
2. step 3b: **INSIDE the lock — migrate-if-needed FIRST (codex iter-6 P1 mitigation):** if `ledger_p` doesn't exist AND `legacy_p` exists, call `_legacy_v014_to_v021_migration(...)` to produce `ledger_p` populated with `provenance="legacy"` rows AND rename `legacy_p` → `legacy_p.with_suffix(".parquet.legacy")` via `os.replace`.
3. step 3c-d: Generate ingestion_id + source_received_at + enrich rows.
4. step 3e: Build `pa.Table.from_pylist(...)`, APPEND semantics (read existing → concat → atomic write).
5. step 3f: Release FileLock.
6. step 3g: mkdir QC sidecar dir — explicitly moved OUTSIDE the lock (was step 3h).

This guarantees that even if write_cache wins the lock race against a still-extant legacy file, the migrated legacy rows land in ledger_p BEFORE live rows are appended, and `.parquet.legacy` rename always happens.

**Edit B — Updated T-02.1.3-02 threat register row:**

The Component now explicitly covers three race scenarios:
- (a) two read_cache processes migrate the same legacy file simultaneously (original)
- (b) read_cache auto-upgrade races with concurrent write_cache (original)
- (c) **NEW (codex iter-6 P1):** write_cache wins the lock race against a still-extant legacy file → without migrate-if-needed-inside-lock, write_cache creates ledger_p with only live rows, subsequent read_cache sees ledger_p exists and SKIPS migration → silent legacy data loss.

The Mitigation Plan now reads "UNIFIED FileLock pattern + **migrate-if-needed-inside-lock**" and explicitly cites this phrase as the closure mechanism for the write-wins case.

**Edit C — Rewrote Test 9 docstring to exercise BOTH orderings:**

Test 9 `test_auto_upgrade_does_not_race_with_concurrent_write_cache` now covers:
- **Order A (read wins lock first):** thread A read_cache starts first, thread B write_cache after.
- **Order B (write wins lock first — THE codex iter-6 P1 case):** thread B write_cache starts FIRST and acquires the lock. Without migrate-if-needed-inside-lock, write_cache would create ledger_p with only live rows, then thread A's read_cache would SKIP migration, losing 5 legacy rows silently.

For BOTH orderings the test asserts identical final state: 10 rows in ledger_p (5 legacy with `provenance="legacy"` + 5 live with `provenance is None`) AND legacy file renamed to `.parquet.legacy`. The test must use `pytest.mark.parametrize` over `("read_first", "write_first")` (or two test functions sharing a helper) so the write-wins case is genuinely exercised — without Order B, a regression that only breaks the write-wins path would slip through. Task 2 test count stays at 9 (Test 9 parametrized).

**Commit:** cdae0fb

**Verification:**
- `grep -c "migrate-if-needed FIRST"` → 2 ✓
- `grep -c "migrate-if-needed-inside-lock"` → 2 ✓
- `grep -c "codex iter-6 P1"` → 4 ✓
- `grep -c "Order A\|Order B"` → 3 ✓
- `grep -c "write-wins\|wins the lock race"` → 3 ✓

### Task 2: PLAN-04 — Separate first-seen-wins from earliest-ts-wins in class B (codex iter-6 P2)

Three coordinated edits inside `.planning/phases/02.1-sprint-2o-lineage-refactor-per-source-provenance/02.1-PLAN-04-integration-parity-gate.md`:

**Edit A — Reversed `_hardcoded_silver_class_b_same_priority_later_ts` builder:**

The builder previously listed baseline (T0) FIRST and appended later-iem siblings via `synthetic = list(baseline); for ... synthetic.append(...)`. The new builder builds `later_siblings` as a list comprehension FIRST and then returns `list(later_siblings) + list(baseline)`. Now:
- **first-seen-wins (BUG):** picks the +200 marker → test fails (as intended).
- **earliest-timestamp-wins (CORRECT):** picks baseline → test passes for the right reason.

Without this reversal the two strategies coincidentally agreed on baseline (which was the first row in iteration order under the old ordering) and the test passed for a buggy impl.

**Edit B — Updated `test_pre_flight_class_b_same_priority_later_ts_earliest_wins` docstring:**

The comment block at the top of the test function body now cites the codex iter-6 P2 mitigation explicitly and documents the deliberate row order with a two-bullet contrast:
- first-seen-wins (BUG): picks the +200 marker → test fails (as intended)
- earliest-timestamp-wins (CORRECT): picks baseline → test passes for the right reason

The existing assertion bodies (`for i, n in enumerate(new_sorted): ...`) were left UNCHANGED — they already test the right thing (baseline temp_c = 5.0 + i, NOT 5.0 + i + 200). The fix is the BUILDER row order plus the test DOCSTRING.

**Edit C — Added review comment to `_hardcoded_silver_class_c_same_priority_null_ts` builder:**

After reviewing the class C builder, confirmed that class C does NOT need the same row-order reversal because its two competing semantics already give DIFFERENT answers regardless of row order:
- first-seen-wins (BUG): picks baseline (a real RFC3339 timestamp)
- null→"" lex-MIN coercion (CORRECT): picks null-sibling

Added a comment block inside the builder citing the iter-6 P2 review and explaining that the baseline-FIRST ordering is INTENTIONALLY DIFFERENT from class B's later-ts-FIRST ordering to keep the builder readable.

**Commit:** 6c3c282

**Verification:**
- `grep -c "list(later_siblings) + list(baseline)"` → 1 ✓
- `grep -c "codex iter-6 P2"` → 3 ✓
- `grep -c "INTENTIONALLY DIFFERENT from class B"` → 1 ✓
- `grep -c "later_siblings"` → 2 ✓

## Deviations from Plan

None — plan executed exactly as written. Both tasks landed in single atomic commits with the prescribed commit messages and all verify-block grep counts met or exceeded the required thresholds.

## Files Modified

| File | Lines Changed |
|------|---------------|
| `.planning/phases/02.1-sprint-2o-lineage-refactor-per-source-provenance/02.1-PLAN-03-cache-layer-refactor.md` | +15/-13 |
| `.planning/phases/02.1-sprint-2o-lineage-refactor-per-source-provenance/02.1-PLAN-04-integration-parity-gate.md` | +40/-13 |

**Total:** 2 files, +55/-26.

## Commits

| SHA | Message |
|-----|---------|
| cdae0fb | docs(02.1-plan-03): close write_cache-wins-race silent-data-loss path (codex iter-6 P1) |
| 6c3c282 | docs(02.1-plan-04): separate first-seen-wins from earliest-ts-wins in class B (codex iter-6 P2) |

## No Collateral Damage

- `git diff --stat HEAD~2..HEAD` shows ONLY the two PLAN.md files changed
- No `packages/` source code touched
- No `tests/` test code touched
- No other planning artifacts touched
- Two atomic commits, one per finding, each referencing the corresponding codex iter-6 ID (P1, P2)

## Success Criteria

- [x] PLAN-03 write_cache action block restructured so migrate-if-needed-inside-lock runs BEFORE live-row append
- [x] PLAN-03 T-02.1.3-02 mitigation cites "migrate-if-needed-inside-lock" as the write-wins-case closure mechanism
- [x] PLAN-03 Test 9 docstring exercises BOTH thread orderings (Order A read-wins, Order B write-wins)
- [x] PLAN-04 class-B builder lists later-ts row FIRST, baseline SECOND so first-seen-wins and earliest-timestamp-wins give DIFFERENT answers
- [x] PLAN-04 class-B test docstring cites iter-6 P2 mitigation
- [x] PLAN-04 class-C builder annotated to document why it does NOT need the same reversal
- [x] Two atomic commits, one per finding, each referencing codex iter-6 P1/P2
- [x] Only `.planning/` files touched — NO source code, NO tests, NO other planning artifacts

## Self-Check: PASSED

- File `.planning/phases/02.1-sprint-2o-lineage-refactor-per-source-provenance/02.1-PLAN-03-cache-layer-refactor.md` exists ✓
- File `.planning/phases/02.1-sprint-2o-lineage-refactor-per-source-provenance/02.1-PLAN-04-integration-parity-gate.md` exists ✓
- Commit cdae0fb exists in git log ✓
- Commit 6c3c282 exists in git log ✓
- All grep verification thresholds met or exceeded (see Task 1 + Task 2 verification blocks above)
- No collateral file changes outside `.planning/`

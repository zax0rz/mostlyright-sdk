---
phase: quick
plan: 260522-msx
subsystem: planning/02.1-cache-refactor
tags: [planning, review-discipline, iter-7, cache, write_cache, read_cache, FileLock, race-test]
dependency_graph:
  requires: []
  provides:
    - "PLAN-03 reconciled against iter-7 HIGH findings; ready for iter-8 reviewer re-dispatch"
  affects:
    - ".planning/phases/02.1-sprint-2o-lineage-refactor-per-source-provenance/02.1-PLAN-03-cache-layer-refactor.md"
tech_stack:
  added: []
  patterns:
    - "Single-locking-layer pattern: outer per-file FileLock is the only locking layer; inner atomic-write helper (_atomic_write_locked) is lock-free"
    - "threading.Event synchronisation barrier for deterministic race-test ordering across .start()-order parametrize cases"
key_files:
  created: []
  modified:
    - ".planning/phases/02.1-sprint-2o-lineage-refactor-per-source-provenance/02.1-PLAN-03-cache-layer-refactor.md"
key_decisions:
  - "KEEP iter-6 P1's parametrize over ('read_first', 'write_first') for Test 9 — cleanest way to exercise both lock-winner orderings; the count drift is fixed by updating PLAN-03 numbers to match pytest's parametrize-aware -v output, not by removing the parametrize"
  - "Introduce _atomic_write_locked() as a separate lock-free inner helper rather than refactoring the existing _atomic_write() — preserves the original for unlocked callers (one-off scripts) while making the single-locking-layer pattern explicit on the production paths"
  - "Mandate threading.Event barrier in the test spec (not just allow it) — without the barrier, the parametrize over read_first/write_first is OS-scheduler-dependent and the write-wins case can pass intermittently in CI"
metrics:
  duration_minutes: 5
  tasks_completed: 3
  commits: 3
  files_modified: 1
completed_date: 2026-05-22
---

# Quick Task 260522-msx: Fix 3 iter-7 HIGH findings on PLAN-03 Summary

Localised 3 reviewer HIGH findings (architect iter-7 HIGH-1 + codex iter-7 P1/P2) to `02.1-PLAN-03-cache-layer-refactor.md` only — count drift, write_cache self-locking risk, and Test 9 race-test non-determinism — re-tightening PLAN-03 before Wave 3 execution.

## Tasks Completed

| Task | Name                                                                                | Commit  |
| ---- | ----------------------------------------------------------------------------------- | ------- |
| 1    | Reconcile Test 9 parametrize count drift (architect iter-7 HIGH-1)                  | d1280e9 |
| 2    | Specify single-locking-layer pattern in write_cache (codex iter-7 P1 HIGH)          | 8c76e4b |
| 3    | Mandate threading.Event barrier in Test 9 race spec (codex iter-7 P2 HIGH)          | 3d35cd2 |

## What Changed

### Task 1 — Count drift (architect iter-7 HIGH-1)

Task 2's Test 9 was parametrized over `("read_first", "write_first")` in iter-6 P1, but pytest counts each parametrize case as a separate test in `-v` output. PLAN-03 still claimed 9 tests for Task 2 (actually 10), so the acceptance string `"all 19 tests PASSED (10 + 9)"` would never match pytest's actual output (`20 passed`), the `<done>` line said "18 silver+gold tests pass" (actually 19), and phase verification said "10+9+8 = 27 tests" (actually 28).

Updated 4 sites:

- Test 9 spec last sentence: now states the parametrization raises the count from 9 to 10 and explains why pytest counts each parametrize case separately.
- Task 2 acceptance bullet: `all 20 tests PASSED (10 + 10)` (was `all 19 tests PASSED (10 + 9)`).
- Task 2 `<done>` line: 19 silver+gold tests pass (10 silver + 9 gold-spec items, with Test 9 parametrized into 2 pytest cases = 20 collected).
- Phase `<verification>` step 1: `10 + 10 + 8 = 28 tests PASSED` with a parenthetical explaining the parametrize count.

### Task 2 — Single-locking-layer pattern (codex iter-7 P1 HIGH)

Task 1 step 3 had `write_cache` acquire the per-file FileLock and then INSIDE the lock call `_atomic_write()` — which itself internally acquires `FileLock(str(path) + ".lock")` on the same file. `filelock>=3.x` IS reentrant on the same thread, so on current Linux/macOS this works via the reentrant counter, but the plan should NOT depend on platform/library-version-dependent reentrancy.

Updated 6 sites:

- Added step **2-prime** to Task 1 action: defines a new lock-free atomic-write helper `_atomic_write_locked(path, table)` with same tmp-file + cross-platform `os.replace` atomicity as `_atomic_write()` but NO FileLock acquisition. Includes the explicit invariant: "outer per-file FileLock is the ONLY locking layer; the inner atomic-write helper is lock-free."
- Task 1 step 3e: write_cache now calls `_atomic_write_locked(ledger_p, table)` (lock-free) for both the existing-ledger-append branch and the empty-ledger-direct-write branch.
- Task 1 step 3f preservation note: both helpers preserved — `_atomic_write_locked()` for locked callers (write_cache, migration, auto-upgrade), `_atomic_write()` for unlocked callers.
- Task 2 step 3e (migration adapter atomic write): now calls `_atomic_write_locked(ledger_path, table)` with explicit "MUST be called from inside a held lock" precondition.
- Task 2 step 4e (auto-upgrade-on-read lock acquisition): extended narrative to call out that the lock acquired here is the SINGLE locking layer for that code path — inner migration call uses lock-free helper.
- Task 1 acceptance criteria: added two grep bullets verifying `_atomic_write_locked` appears ≥3 times in cache.py and is defined exactly once.
- Threat T-02.1.3-02 mitigation cell: appended sentence naming the single-locking-layer pattern + iter-7 P1 + non-reentrant-FileLock-backend rationale.

### Task 3 — threading.Event barrier (codex iter-7 P2 HIGH)

Test 9 parametrizes over `("read_first", "write_first")` but `.start()` order does NOT determine which thread acquires the lock first — the OS scheduler does. Under typical scheduling, the read thread can win the lock even when the write thread `.start()`-ed first, so the `write_first` case could pass without actually exercising the write-wins race it names.

Updated 4 sites:

- Test 9 spec body: appended a substantial sentence mandating `threading.Event` barrier, describing the Order A and Order B implementations (which thread `.set()`s the event and which `.wait()`s on it), and explaining why `.start()` order alone is insufficient.
- Task 2 acceptance criteria: added grep bullet verifying `threading.Event|lock_acquired_event` appears in `tests/test_cache_gold_read.py` (catches a missing-barrier regression at CI time without needing to actually run the race test).
- Task 2 `<done>` line: extended to note each ordering is gated by the `threading.Event` barrier.
- Threat T-02.1.3-02 mitigation cell: appended final sentence noting Task 2 Test 9 parametrize-with-barrier verifies both orderings deterministically, with `threading.Event` + iter-7 P2 reference.

## Sequencing Note

Task 3 modifies content that Task 1 already wrote (the Task 2 `<done>` line in PLAN-03). The plan documented this sequencing risk. Tasks were executed in order 1 → 2 → 3, with the file re-read between tasks to obtain the current state before editing. Both intermediate edits succeeded with exact-string matching.

## Verification

All 10 checks in PLAN's `<verification>` block pass:

| # | Check                                          | Actual | Expected |
| - | ---------------------------------------------- | ------ | -------- |
| 1 | `all 20 tests PASSED (10 + 10)` in PLAN-03     | 2      | ≥ 1      |
| 2 | `10 + 10 + 8 = 28`                             | 1      | 1        |
| 3 | `_atomic_write_locked` references              | 8      | ≥ 6      |
| 4 | `Single-locking-layer` invariant statements    | 3      | ≥ 2      |
| 5 | `threading.Event` references                   | 4      | ≥ 3      |
| 6 | `lock_acquired_event` references               | 2      | ≥ 2      |
| 7 | `iter-7 (P1|P2|HIGH-1)` finding references     | 4      | ≥ 4      |
| 8 | `all 19 tests PASSED (10 + 9)` (old count gone)| 0      | 0        |
| 9 | 3 distinct commits in `git log -3`             | ✓      | ✓        |
| 10| Working tree clean                             | ✓      | ✓        |

## Deviations from Plan

None — plan executed exactly as written. 3 tasks, 3 atomic commits, 1 file modified.

## Self-Check: PASSED

- `02.1-PLAN-03-cache-layer-refactor.md`: FOUND (modified, 3 commits ahead of HEAD~3)
- Commit `d1280e9`: FOUND in `git log --oneline`
- Commit `8c76e4b`: FOUND in `git log --oneline`
- Commit `3d35cd2`: FOUND in `git log --oneline`

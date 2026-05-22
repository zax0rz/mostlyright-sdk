---
task: 260522-nbw
type: quick
title: "Fix iter-10 architect HIGH P1 bug — write/auto-upgrade paths have same fresh-cache FileNotFoundError"
plan_file: .planning/phases/02.1-sprint-2o-lineage-refactor-per-source-provenance/02.1-PLAN-03-cache-layer-refactor.md
review_iteration: 10
reviewer: architect (+ codex iter-10 P3)
findings_addressed: 3
severity: HIGH (P1 × 2) + P3 grep-window false-negative
---

# Summary: Fix iter-10 reviewer findings on PLAN-03

The iter-9 P1 fix (parent-dir mkdir before FileLock) addressed Task 3 (migrate_to_v2 CLI) only. Architect iter-10 review found that Tasks 1 (write_cache) and 2 (read_cache auto-upgrade) have the SAME bug: they also acquire `FileLock` on `<ledger_p>.lock`, and that lock sidecar cannot be created in a non-existent directory.

This PR applies the iter-9 mkdir pattern uniformly across ALL THREE FileLock acquisition sites and fixes the codex iter-10 P3 grep-window false negative for the Task 3 acceptance criterion.

## Findings Addressed

### 1. (HIGH, architect iter-10) — Task 1 write_cache same P1 bug
**Site:** Task 1 action block step 3a (FileLock acquisition).

**Problem:** First `write_cache` call for a fresh `(station, year)` → `observations_ledger/<station>/<year>/` doesn't exist → `FileLock` can't create `.lock` sidecar → `FileNotFoundError`.

**Fix:** Inserted new step `3a-mkdir` BEFORE step 3a's FileLock acquisition:
> Ensure `ledger_path.parent` exists: `ledger_path.parent.mkdir(parents=True, exist_ok=True)`. Required because `FileLock(<ledger_path>.lock)` would `FileNotFoundError` on first write to a fresh `(station, year)` directory…

Also added grep acceptance criterion (using `-B 10` per codex iter-10 P3):
```
grep -B 10 "FileLock(.*ledger" packages/weather/src/tradewinds/weather/cache.py \
  | grep -c "ledger_path.parent.mkdir(parents=True, exist_ok=True)" >= 1
```

Done line extended: `…10 tests pass; fresh-cache parent dir created before FileLock.`

### 2. (HIGH, architect iter-10) — Task 2 read_cache auto-upgrade same P1 bug
**Site:** Task 2 action block step 4e (FileLock acquisition in auto-upgrade-on-read).

**Problem:** First read on a station with legacy data → legacy exists at `observations/<station>/<year>/<month>.parquet`, but `observations_ledger/<station>/<year>/` doesn't exist yet → `FileLock` can't create `.lock` sidecar → `FileNotFoundError`. This is exactly Test 4's scenario (`test_read_cache_auto_upgrade_from_legacy_path`).

**Fix:** Inserted new bullet at the START of step 4e (before the FileLock acquisition bullet):
> Ensure `ledger_p.parent` exists: `ledger_p.parent.mkdir(parents=True, exist_ok=True)`. Required because `FileLock(<ledger_p>.lock)` would `FileNotFoundError` on first auto-upgrade for a fresh `(station, year)` ledger dir (architect iter-10 P1 mitigation; mirrors Task 3 migrate_to_v2 iter-9 P1 fix and the now-applied Task 1 write_cache fix).

Also added grep acceptance criterion:
```
grep -B 10 "FileLock(.*ledger" packages/weather/src/tradewinds/weather/cache.py \
  | grep -c "ledger_p.parent.mkdir(parents=True, exist_ok=True)" >= 1
```

Done line extended: `…No dtype drift; fresh-cache parent dir created before FileLock for auto-upgrade path.`

(Variable names match each task's existing convention: Task 1 uses `ledger_path`, Task 2 uses `ledger_p`. Both greps target the same `cache.py` file; both should find their respective patterns.)

### 3. (P3, codex iter-10) — Task 3 grep window too small
**Site:** Task 3 acceptance criteria.

**Problem:** Existing iter-9 mkdir grep used `grep -B 5 "with FileLock"`, but the actual code has mkdir 6 lines before `with FileLock` (intervening comments + import + `lock_path` assignment). The grep returns 0 → false negative.

**Fix:** Changed `-B 5` to `-B 10` in the existing acceptance criterion. Annotated rationale inline so future readers understand the window-size choice.

## Threat T-02.1.3-02 Update

Extended the mitigation phrase one more time to record that the parent-dir-mkdir pattern is now applied uniformly across ALL THREE FileLock acquisition sites (Task 1 write_cache, Task 2 read_cache auto-upgrade, Task 3 migrate_to_v2 CLI) — architect iter-10 P1 mitigation closes the fresh-cache `FileNotFoundError` class for write and auto-upgrade paths.

## Files Modified

| File | Change |
|---|---|
| `.planning/phases/02.1-sprint-2o-lineage-refactor-per-source-provenance/02.1-PLAN-03-cache-layer-refactor.md` | +8 lines, -4 lines: Task 1 step 3a-mkdir + acceptance grep + done line; Task 2 step 4e mkdir + acceptance grep + done line; Task 3 `-B 5` → `-B 10`; T-02.1.3-02 mitigation phrase extension |

## Verification

- `git diff --stat` confirms changes scoped to PLAN-03 only.
- All three FileLock acquisition sites in PLAN-03 (write_cache step 3a, read_cache step 4e, migrate_to_v2 CLI) now have a documented parent-dir-mkdir step immediately before lock acquisition.
- Threat T-02.1.3-02 mitigation column now lists architect iter-10 P1 closure alongside codex iter-9 P1/P2.
- No code changes (planning artifact only); no test runs required.

## Commit

Single atomic commit per task instructions:
```
docs(02.1-plan-03): apply iter-9 P1 mkdir pattern to all FileLock sites (iter-10 architect)
```

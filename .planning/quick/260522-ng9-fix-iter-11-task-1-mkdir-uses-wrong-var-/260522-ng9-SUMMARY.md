---
quick-task: 260522-ng9
title: Fix iter-11 Task 1 mkdir uses wrong variable name + ordering
date: 2026-05-22
branch: planning/v01-intl-nwp-polymarket
files-modified:
  - .planning/phases/02.1-sprint-2o-lineage-refactor-per-source-provenance/02.1-PLAN-03-cache-layer-refactor.md
---

# 260522-ng9: Fix iter-11 Task 1 mkdir uses wrong variable name + ordering

## Problem

Iteration-11 review surfaced a HIGH-severity finding from BOTH reviewers (codex P2 + python-architect HIGH) on Task 1 in `02.1-PLAN-03-cache-layer-refactor.md`:

1. **Wrong variable name:** The standalone step `3a-mkdir` (line ~164) referenced `ledger_path.parent.mkdir(...)`, but Task 1 actually defines and uses `ledger_p` (not `ledger_path`). An implementer following the plan literally would emit a `NameError` at runtime.

2. **Wrong ordering:** Even if the variable name were corrected, the standalone `3a-mkdir` step was placed BEFORE step `3a` (the path-resolve step that defines `ledger_p`). The mkdir referenced a variable that did not yet exist at that program point.

Both issues compound: the mkdir step was syntactically broken (undefined var) AND semantically misordered (before path resolution).

## Fix

Two textual edits to `.planning/phases/02.1-sprint-2o-lineage-refactor-per-source-provenance/02.1-PLAN-03-cache-layer-refactor.md`:

### 1. Removed standalone step `3a-mkdir`, folded mkdir into step `3a` (line ~163-164)

Before (two steps, mkdir first with wrong var):
```
3. Rewrite write_cache(...) to:
   a-mkdir. Ensure ledger_path.parent exists BEFORE FileLock acquisition: ledger_path.parent.mkdir(...)
   a. Resolve paths: ledger_p = _ledger_path(...), legacy_p = _legacy_path(...). Acquire FileLock on <ledger_p>.lock sibling...
```

After (single step, path resolve first, then mkdir with correct var, then FileLock):
```
3. Rewrite write_cache(...) to:
   a. Resolve paths: ledger_p = _ledger_path(...), legacy_p = _legacy_path(...). Ensure ledger_p.parent exists BEFORE FileLock acquisition: ledger_p.parent.mkdir(parents=True, exist_ok=True). Required because FileLock(<ledger_p>.lock) would FileNotFoundError on first write... (architect iter-10 P1 mitigation; mirrors Task 3 migrate_to_v2 iter-9 P1 fix and Task 2 read_cache auto-upgrade step 4e fix). This is the FIRST P1 site of three (Task 1 write_cache here, Task 2 read_cache auto-upgrade step 4e, Task 3 migrate_to_v2 CLI). Acquire FileLock on <ledger_p>.lock sibling — the SAME lock object used by read_cache auto-upgrade (Task 2 step 4e) and explicit migrate_to_v2...
```

The ordering is now: (resolve `ledger_p`) → (mkdir `ledger_p.parent`) → (FileLock). This is the only sequence that doesn't raise `NameError` or `FileNotFoundError`.

### 2. Updated acceptance grep on line ~204

Before:
```
grep -B 10 "FileLock(.*ledger" packages/weather/src/tradewinds/weather/cache.py | grep -c "ledger_path.parent.mkdir(parents=True, exist_ok=True)"
```

After:
```
grep -B 10 "FileLock(.*ledger" packages/weather/src/tradewinds/weather/cache.py | grep -c "ledger_p.parent.mkdir(parents=True, exist_ok=True)"
```

The `-B 10` window stays correct (`ledger_p.parent.mkdir(...)` is now in the same step paragraph as the FileLock, well within 10 lines back). Only the variable-name substring changes.

## Verification

- Both edits applied successfully via Edit tool.
- `git diff --stat` shows `1 file changed, 2 insertions(+), 3 deletions(-)` — the line collapse (delete `3a-mkdir`, edit `3a`) plus the grep variable rename.
- The "P1 site of three" cross-reference inside the folded step now correctly points at Task 2 step 4e (the read_cache auto-upgrade) instead of "fix below" (which was an artifact of the standalone step being above it).
- Step lettering remains stable: 3a, 3b, 3c, 3d, 3e, 3f, 3g — no downstream renumbering needed.

## Why this matters

Task 1 is the FIRST of three P1 mkdir sites in the lineage refactor (the other two are Task 2 step 4e read_cache auto-upgrade, and Task 3 migrate_to_v2 CLI). Both sibling sites use the correct variable name and ordering already (verified by reading their step text earlier in the iter-11 cycle). Leaving Task 1 broken would:

1. Cause the implementer to copy-paste a non-compiling step into `cache.py` (mismatch between `ledger_path` in the plan vs `ledger_p` elsewhere in the same task).
2. Break the acceptance grep — even if the implementer silently corrected the var name to `ledger_p` while writing code, the acceptance grep on line 204 would still search for `ledger_path.parent.mkdir(...)` and return 0, failing the gate.
3. Diverge Task 1 from Task 2 and Task 3, which are supposed to be the SAME pattern across all three lock-acquiring write paths.

The fix preserves the single-lock-pattern invariant (step 2-prime) and the three-P1-sites cross-reference chain.

## Commit

See commit SHA in EXECUTION COMPLETE return.

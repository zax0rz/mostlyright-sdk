---
phase: quick
plan: 260522-lz3
subsystem: planning-docs
tags: [review-discipline, iteration-5, doc-fix, surgical]
requires: []
provides:
  - "PLAN-04 pre-flight test exercises all 3 tiebreak classes genuinely (not trivially)"
  - "PLAN-03 unified FileLock pattern between write_cache and read_cache auto-upgrade"
  - "PLAN-04 test counts converge on a single source of truth (22 / 33 totals)"
  - "STATE.md total_plans accurate (15 of 15 on disk)"
  - "PLAN-01 lists `observation_quality` as the 9th lineage column"
affects:
  - .planning/phases/02.1-sprint-2o-lineage-refactor-per-source-provenance/02.1-PLAN-04-integration-parity-gate.md
  - .planning/phases/02.1-sprint-2o-lineage-refactor-per-source-provenance/02.1-PLAN-03-cache-layer-refactor.md
  - .planning/phases/02.1-sprint-2o-lineage-refactor-per-source-provenance/02.1-PLAN-01-schema-and-validator.md
  - .planning/STATE.md
tech-stack:
  added: []
  patterns:
    - "5 atomic commits per finding (REVIEW iter-5 F1..F5 trailer pattern from iteration-4 quick task 260522-lah)"
    - "Unified per-file `.lock` sibling FileLock pattern (write_cache + read_cache auto-upgrade share the same lock object)"
key-files:
  created: []
  modified:
    - .planning/phases/02.1-sprint-2o-lineage-refactor-per-source-provenance/02.1-PLAN-04-integration-parity-gate.md
    - .planning/phases/02.1-sprint-2o-lineage-refactor-per-source-provenance/02.1-PLAN-03-cache-layer-refactor.md
    - .planning/phases/02.1-sprint-2o-lineage-refactor-per-source-provenance/02.1-PLAN-01-schema-and-validator.md
    - .planning/STATE.md
decisions:
  - "Keep the historical `ledger_p.parent` mention inside Test 9's failure-mode docstring — it documents WHY the unified pattern is needed (not an assertion of current behavior). The plan's Sub-edit C `new_string` specified this text verbatim."
  - "Task 1's residual `test_pre_flight_strict_priority_with_synthetic_duplicates_per_fixture` reference at line 445 was left for Task 3 (Sub-edit B) to clean up via the per-class debug-bullet split. Sequencing intentional; no separate fix needed."
metrics:
  duration: "~12 minutes wall-clock from start to final commit"
  completed_date: "2026-05-22"
  tasks: 5
  commits: 5
  files_changed: 4
  lines_inserted: 123
  lines_deleted: 55
---

# Quick Task 260522-lz3: Fix 5 REVIEW-DISCIPLINE Iteration 5 Findings Summary

Five surgical text edits to `.planning/` documents close the five HIGH-severity findings from REVIEW-DISCIPLINE iteration 5, shipping as five atomic per-finding commits on `planning/v01-intl-nwp-polymarket`. No source code touched. Each fix carries the `(REVIEW iter-5 F<n>)` trailer for traceability with the iteration-5 review notes.

## Findings Fixed

### Finding 1 — PLAN-04 pre-flight test didn't exercise stated tiebreak classes (HIGH)

**Commit:** `f6aa4c1` — `docs(02.1-PLAN-04): split pre-flight builder into 3 single-class helpers (REVIEW iter-5 F1)`

**Bug:** `_hardcoded_silver_with_duplicates` always appended a class (a) awc (priority 3) sibling alongside the iem (priority 2) baseline. Strict-> on `source_priority` alone picked awc in EVERY group, so the secondary tiebreak rule (`source_received_at` ascending, then `ingestion_id` ascending) was never exercised. The per-column equality assertion between `_legacy_dedup_rows` and `query_time_merge` was trivially satisfied because both impls agree on the cross-priority winner. Worse: the two impls AGREE on class (a) but DISAGREE on (b) and (c) by design — so the equality assertion was wrong for (b)/(c). The test as written could not fail on (b)/(c) because (b)/(c) never determined a winner.

**Fix:**
- Replaced the single builder with three single-class builders: `_hardcoded_silver_class_a_cross_priority`, `_hardcoded_silver_class_b_same_priority_later_ts`, `_hardcoded_silver_class_c_same_priority_null_ts`.
- Replaced the single parametrized test with three single-class tests, each exercising exactly one ambiguity rule.
- Class (a) test asserts both impls agree (cross-priority is the one place legacy and new MUST match).
- Classes (b) and (c) tests assert ONLY the new `query_time_merge` behavior, with docstrings documenting the deliberate divergence from legacy.

### Finding 2 — PLAN-03 lock pattern mismatch (HIGH)

**Commit:** `453eb6b` — `docs(02.1-PLAN-03): unify auto-upgrade lock pattern with write_cache + add race test (REVIEW iter-5 F2)`

**Bug:** Auto-upgrade-on-read locked `ledger_p.parent`, but `write_cache` locked the per-file `.lock` sibling — different lock objects. A concurrent `write_cache` + auto-upgrade migration on the same `(station, year, month)` could lose migrated data: write_cache reads empty ledger pre-migration, auto-upgrade writes legacy rows, write_cache writes back without concat, clobbering.

**Fix (5 sub-edits A-E):**
- Sub-edit A: step 4e locks `ledger_p.with_suffix(ledger_p.suffix + ".lock")` (SAME lock as write_cache step 3).
- Sub-edit B: T-02.1.3-02 now covers BOTH (a) two-readers race AND (b) write_cache-vs-migrator race; mitigation cites the unified lock.
- Sub-edit C: new Test 9 `test_auto_upgrade_does_not_race_with_concurrent_write_cache` exercises the unified pattern via threading.
- Sub-edit D: Task 2 acceptance criteria 18 → 19 (10 + 9).
- Sub-edit E: plan-level verification 26 → 27 (10 + 9 + 8).

### Finding 3 — PLAN-04 test counts contradicted (HIGH)

**Commit:** `aaa0f6d` — `docs(02.1-PLAN-04): recompute test counts after F1 restructure (REVIEW iter-5 F3)`

**Bug:** Plan-level verification block claimed "7 + 5 + 3 + 2 + 1 = 18 tests" but the actual file defined 12 + 8 + 3 = 23 tests pre-F1. After F1 restructure, the count changes again (Task 1 grows from 12 → 22 tests because the single parametrized class-mix test splits into three parametrized single-class tests across 5 PARITY_STATIONS).

**Fix (3 sub-edits A-C):**
- Sub-edit A: Task 1 acceptance criteria cites 22 tests with explicit 5+5+5+5+2 breakdown.
- Sub-edit B: the single "If `..._with_synthetic_duplicates_per_fixture` fails" debug bullet (the F1 residual) is replaced with three per-class debug bullets so failures pinpoint the broken rule (class a / b / c).
- Sub-edit C: plan-level verification cites "22 + 5 + 3 + 2 + 1 = 33 tests" with per-file breakdown comment.

Single source of truth: all three sites converge on 22 (Task 1) and 33 (plan-level).

### Finding 4 — STATE.md `total_plans` off by 2 (HIGH)

**Commit:** `f0fb34e` — `docs(STATE): bump total_plans 13 -> 15 to match plans on disk (REVIEW iter-5 F4)`

**Bug:** YAML frontmatter said `total_plans: 13` but 15 plans exist on disk (the prior iteration-4 fix omitted Phase 1 PLAN.md and Phase 2 PLAN.md).

**Fix:** Frontmatter `total_plans: 13 -> 15`. No other fields changed (`total_phases: 12`, `completed_phases: 0`, `completed_plans: 0`, `percent: 6` all preserved). No new YAML keys introduced.

### Finding 5 — PLAN-01 said "9 new lineage columns" but only named 8 (HIGH)

**Commit:** `0feccec` — `docs(02.1-PLAN-01): add 9th lineage column observation_quality (REVIEW iter-5 F5)`

**Bug:** Objective line 55 cited "9 new lineage columns" then listed only 8: `parser_name, parser_version, ingestion_id, as_of_time, source_received_at, qc_status, observation_kind, provenance`. The 9th column per LINEAGE-01 in REQUIREMENTS.md is `observation_quality` — the lineage enum `{clean, flagged, suspect}`. The interfaces NEW-fields block had the same omission.

**Fix (2 sub-edits A-B):**
- Sub-edit A: objective sentence lists all 9 columns including `observation_quality`.
- Sub-edit B: interfaces block gains an `observation_quality` bullet with the lineage enum values and a parenthetical distinguishing it from (i) the `qc_status` enum slot (per-rule QC firing, not row-quality) and (ii) the `obs_qc_status` bitmask column per QC-05.

`observation_quality` is nullable/additive — NOT added to any JSON Schema `required` array.

## Commits (chronological)

| # | SHA       | Finding | Subject |
|---|-----------|---------|---------|
| 1 | `f6aa4c1` | F1 | docs(02.1-PLAN-04): split pre-flight builder into 3 single-class helpers (REVIEW iter-5 F1) |
| 2 | `453eb6b` | F2 | docs(02.1-PLAN-03): unify auto-upgrade lock pattern with write_cache + add race test (REVIEW iter-5 F2) |
| 3 | `aaa0f6d` | F3 | docs(02.1-PLAN-04): recompute test counts after F1 restructure (REVIEW iter-5 F3) |
| 4 | `f0fb34e` | F4 | docs(STATE): bump total_plans 13 -> 15 to match plans on disk (REVIEW iter-5 F4) |
| 5 | `0feccec` | F5 | docs(02.1-PLAN-01): add 9th lineage column observation_quality (REVIEW iter-5 F5) |

## Files Modified

```
.planning/STATE.md                                                                    |   2 +-
.planning/phases/02.1-.../02.1-PLAN-01-schema-and-validator.md                        |   3 +-
.planning/phases/02.1-.../02.1-PLAN-03-cache-layer-refactor.md                        |   9 +-
.planning/phases/02.1-.../02.1-PLAN-04-integration-parity-gate.md                     | 164 +++++++++++++++------
4 files changed, 123 insertions(+), 55 deletions(-)
```

Diff scope (HEAD~5..HEAD) is `.planning/` only. No `packages/` source code modified.

## Verification

Plan-level verification block from `260522-lz3-PLAN.md` — all greps pass:

```bash
# F1: three single-class helpers + three single-class tests in PLAN-04
grep -c "_hardcoded_silver_class_a_cross_priority\|..._b_..._later_ts\|..._c_..._null_ts" PLAN-04   # → 6 (>=6) ✓
grep -c "_hardcoded_silver_with_duplicates\|test_pre_flight_strict_priority_with_synthetic_duplicates" PLAN-04  # → 0 ✓
grep -cE "def test_pre_flight_class_[abc]_" PLAN-04                                                   # → 3 ✓

# F2: unified lock pattern in PLAN-03
grep -c "ledger_p.with_suffix\|per-file \`.lock\` sibling" PLAN-03                                    # → 3 (>=2) ✓
grep -c "test_auto_upgrade_does_not_race_with_concurrent_write_cache" PLAN-03                         # → 1 (>=1) ✓
grep -c "19 tests PASSED\|10 + 9 + 8 = 27" PLAN-03                                                    # → 2 (>=2) ✓
grep -c "ledger_p.parent" PLAN-03                                                                     # → 1 (see Deviations) ✓ (acceptable)

# F3: PLAN-04 test counts reconciled
grep -c "18 tests PASSED\|12 tests PASSED\|7 + 5 + 3 + 2 + 1 = 18" PLAN-04                            # → 0 ✓
grep -c "22 tests PASSED\|22 + 5 + 3 + 2 + 1 = 33" PLAN-04                                            # → 2 (>=2) ✓

# F4: STATE.md total_plans bumped
grep "^  total_plans:" .planning/STATE.md                                                             # → "total_plans: 15" ✓
grep -c "total_plans: 13" .planning/STATE.md                                                          # → 0 ✓

# F5: observation_quality in PLAN-01
grep -c "observation_quality" PLAN-01                                                                 # → 6 (>=2) ✓

# Source untouched (HEAD~5..HEAD scope)
git diff --stat HEAD~5..HEAD | grep -E "^ packages/" || echo "OK: no packages/ changes"               # → OK ✓

# Five separate commits with iter-5 trailer
git log --oneline -5 | grep -cE "REVIEW iter-5 F[1-5]"                                                # → 5 ✓
```

## Deviations from Plan

### Auto-tracked Notes (no rule-breaks)

**1. F2 verify-block expected `grep -c "ledger_p.parent" PLAN-03` to return 0; actual is 1.**
- **Found during:** Task 2 post-edit verification
- **Root cause:** Sub-edit C's `new_string` (specified verbatim in the plan) describes Test 9's failure mode with the phrase "migration locks `ledger_p.parent` — different objects -> race -> write_cache clobbers migration". This is documenting WHY the unified pattern is needed, not asserting the current pattern.
- **Resolution:** Kept verbatim per the plan's prescribed `new_string`. The verify-block strictness (expect 0) didn't account for this historical-context mention that lives inside the action block. Task 2's commit message documents this. No follow-up edit needed — the surrounding code in step 4e and T-02.1.3-02 both correctly reference the per-file `.lock` sibling as the current pattern.

**2. F1 left one residual `test_pre_flight_strict_priority_with_synthetic_duplicates_per_fixture` mention at line ~445 (debug-path bullet).**
- **Found during:** Task 1 post-edit verification
- **Root cause:** That bullet is in the acceptance criteria, NOT in the test body Task 1 replaces. The plan correctly sequences Task 3 (Sub-edit B) to replace this bullet with three per-class debug bullets.
- **Resolution:** Sequencing intentional. Task 3 cleaned this up; final verify shows `grep -c "test_pre_flight_strict_priority_with_synthetic_duplicates" PLAN-04` → 0. No deviation from plan — just a sequencing observation.

### CLAUDE.md Adherence

- No source code touched (CLAUDE.md "All API calls direct from SDK" / "No `--no-verify`" do not apply — doc-only diff).
- Pre-commit hooks ran clean on all 5 commits (no `--no-verify` used). Ruff + ruff-format skipped because no `.py` files in the diff; trim-trailing-whitespace + fix-end-of-files + check-yaml + check-toml + large-files-check all passed.
- TDD mandate doesn't apply (no test code or runtime code added — only doc text describing future test code).

## Self-Check: PASSED

**Created files verified:**
- `[FOUND] .planning/quick/260522-lz3-fix-5-review-discipline-iteration-5-find/260522-lz3-SUMMARY.md` (this file)

**Commits verified:**
- `[FOUND] f6aa4c1` — F1 commit on `planning/v01-intl-nwp-polymarket`
- `[FOUND] 453eb6b` — F2 commit
- `[FOUND] aaa0f6d` — F3 commit
- `[FOUND] f0fb34e` — F4 commit
- `[FOUND] 0feccec` — F5 commit

**Files modified verified:**
- `[FOUND] .planning/phases/02.1-.../02.1-PLAN-04-integration-parity-gate.md` (F1 + F3)
- `[FOUND] .planning/phases/02.1-.../02.1-PLAN-03-cache-layer-refactor.md` (F2)
- `[FOUND] .planning/STATE.md` (F4)
- `[FOUND] .planning/phases/02.1-.../02.1-PLAN-01-schema-and-validator.md` (F5)

All plan success-criteria met:
- [x] All 5 iteration-5 findings closed via surgical text edits to 4 planning files.
- [x] Five commits on `planning/v01-intl-nwp-polymarket`, one per finding, each with `(REVIEW iter-5 F<n>)` suffix.
- [x] No source code changes (diff is .planning/ only).
- [x] No new YAML keys introduced in STATE.md.
- [x] Three PLAN-04 test-count sites converge on the same numbers after Task 3 (22 / 33).
- [x] Two PLAN-03 lock-acquisition sites (action step 4e + threat register T-02.1.3-02) cite the same FileLock target.
- [x] PLAN-01 objective and interfaces block both name `observation_quality` as the 9th lineage column.
- [x] Pre-commit hooks passed without `--no-verify` on all 5 commits.

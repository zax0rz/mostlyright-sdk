---
phase: ts-w4-mode2-transforms-qc-alpha
plan: 05
subsystem: qc
tags: [qc, bitfield, codegen-parity, alpha-rules, observation-quality]

# Dependency graph
requires:
  - phase: ts-w4-mode2-transforms-qc-alpha
    provides: column-naming convention {col}_{op}_{param} (Wave 2/3/4); codegen QC_ALPHA_RULES table already materialized at packages-ts/core/src/data/generated/qc-alpha-rules.ts
provides:
  - "@tradewinds/core/qc subpath: QCEngine + 5 alpha rule evaluators + ALPHA_RULES + QC_ALPHA_RULES"
  - "QCEngine.apply(rows) → rows with obsQcStatus (32-bit signed bitfield) column added"
  - "Codegen-parity regression guard test asserting ALPHA_RULES === QC_ALPHA_RULES byte-for-byte (ruleId, bitPosition, field, description)"
  - "Module-load drift safety net: throws if codegen table grows past evaluator count"
  - "Per-rule evaluators exposed for downstream composability: evalTempOutOfRange, evalDewpointExceedsTemp, evalWindSpeedNegative, evalWindDirOutOfRange, evalSlpOutOfRange"
affects: [ts-w4-06, ts-w5, future qc sidecar parquet emission, future Phase 3.5+ QC rule additions]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Codegen-consumption pattern: runtime registry built from QC_ALPHA_RULES_BY_ID.get(ruleId); ZERO hand-coded bit positions"
    - "Module-load drift guard: throws if codegen table length !== evaluator count"
    - "Defensive bit-31 ceiling: RangeError at construction if rule.bitPosition outside [0, 31]"
    - "Vectorized rule contract: rule.evaluate(rows) called ONCE per rule, returns parallel boolean[]"
    - "Subpath bundle isolation: ./qc lives outside root barrel to preserve 25 KB size-limit gate"

key-files:
  created:
    - "packages-ts/core/src/qc/rules.ts"
    - "packages-ts/core/src/qc/engine.ts"
    - "packages-ts/core/src/qc/index.ts"
    - "packages-ts/core/tests/qc/rules.test.ts"
    - "packages-ts/core/tests/qc/engine.test.ts"
    - "packages-ts/core/tests/qc/codegen-parity.test.ts"
  modified:
    - "packages-ts/core/package.json (added ./qc subpath export)"
    - "packages-ts/core/tsup.config.ts (added src/qc/index.ts entry)"

key-decisions:
  - "Bit positions + rule IDs CONSUMED from QC_ALPHA_RULES_BY_ID; never hand-coded — enforces TS-W4 critical-rule #4"
  - "obsQcStatus column name in camelCase (TS-idiom); Python uses snake_case obs_qc_status; wire-format conversion at jsonDumps boundary"
  - "Module-load drift guard throws if QC_ALPHA_RULES.length !== ALPHA_RULES.length — catches Phase 3.5+ codegen additions loud"
  - "JS bitwise OR is 32-bit signed; defensive RangeError at QCEngine construction if any rule.bitPosition outside [0, 31]"
  - "QC lives at @tradewinds/core/qc subpath; root barrel UNCHANGED to preserve 25 KB gate (6.02 kB after)"
  - "Null/missing/non-finite fields → rule does NOT fire (Python pd.Series([False]*len) + notna() parity)"
  - "Strict > for dewpoint exceeds temp (NOT >=) — equality is physically possible at saturation"

patterns-established:
  - "Codegen-runtime parity guard test: byte-for-byte tuple equality check at every commit"
  - "QC rule registry built via makeRule(ruleId, evaluator) lookup-on-codegen pattern"

requirements-completed:
  - TS-QC-01

# Metrics
duration: 5min
completed: 2026-05-24
---

# Phase TS-W4 Plan 05: QCEngine + 5 Alpha QC Rules Summary

**QCEngine.apply emits obsQcStatus 32-bit bitfield column wired to codegen QC_ALPHA_RULES table; 5 alpha rules (temp/dewpoint/wind-speed/wind-dir/slp bounds) ported at @tradewinds/core/qc subpath with codegen-parity regression guard.**

## Performance

- **Duration:** 5 min
- **Started:** 2026-05-24T16:27:54Z
- **Completed:** 2026-05-24T16:33:40Z
- **Tasks:** 3
- **Files created:** 6
- **Files modified:** 2
- **Tests added:** 63 (36 rules + 18 engine + 9 codegen-parity)
- **Total core tests after Wave 5:** 662 (up from 599 baseline)

## Accomplishments

- Ported Python `qc.py:53-160` QCEngine + 5 alpha rule evaluators to TypeScript with byte-equivalent behaviour (inclusive bounds, strict `>` for dewpoint, null-skip semantics)
- All bit positions + rule IDs CONSUMED from `QC_ALPHA_RULES_BY_ID` codegen table; ZERO hand-coded bit literals (enforces TS-W4 critical-rule #4)
- Codegen-parity regression guard test asserts runtime ALPHA_RULES tuples match `QC_ALPHA_RULES` byte-for-byte (full ruleId + bitPosition + field + description parity); fires loud on any future codegen drift
- Module-load drift safety net: throws at import if `QC_ALPHA_RULES.length !== ALPHA_RULES.length` (catches Phase 3.5+ codegen additions before they silently drop rules)
- Defensive 32-bit ceiling: RangeError at `QCEngine` construction if any rule's `bitPosition` outside [0, 31] (JS bitwise OR is 32-bit signed)
- `@tradewinds/core/qc` subpath wired (package.json + tsup); root barrel UNCHANGED — `@tradewinds/core` bundle stays at 6.02 kB (≤ 25 kB gate)
- `obsQcStatus === 31` end-to-end verified for a row triggering all 5 rules (proves 5-bit aggregation)

## Task Commits

Each task was committed atomically:

1. **Task 1: 5 alpha rule evaluators wired to codegen** — `bc5c663` (feat) — `src/qc/rules.ts` + 36 tests in `tests/qc/rules.test.ts`
2. **Task 2: QCEngine.apply emitting obsQcStatus** — `be44f95` (feat) — `src/qc/engine.ts` + 18 tests in `tests/qc/engine.test.ts`
3. **Task 3: Barrel + subpath + codegen-parity test** — `9e13eda` (feat) — `src/qc/index.ts`, `package.json`, `tsup.config.ts`, 9 tests in `tests/qc/codegen-parity.test.ts`

## Files Created/Modified

### Created
- `packages-ts/core/src/qc/rules.ts` — 5 alpha rule evaluators (`evalTempOutOfRange`, `evalDewpointExceedsTemp`, `evalWindSpeedNegative`, `evalWindDirOutOfRange`, `evalSlpOutOfRange`) + `QCRule` interface + `ALPHA_RULES` registry built via `makeRule(ruleId, evaluator)` lookup on codegen `QC_ALPHA_RULES_BY_ID`
- `packages-ts/core/src/qc/engine.ts` — `QCEngine` class with `apply(rows)` performing vectorized rule evaluation + per-row OR-aggregation of `1 << rule.bitPosition`; defensive bit-31 ceiling RangeError
- `packages-ts/core/src/qc/index.ts` — barrel re-exporting `QCEngine`, `QCRule`, `ALPHA_RULES`, `QC_ALPHA_RULES`, and the 5 evaluators
- `packages-ts/core/tests/qc/rules.test.ts` — 36 tests covering per-rule semantics (inclusive bounds, null-skip, missing-column no-fire, strict-`>` dewpoint) + codegen-consumption regression guards
- `packages-ts/core/tests/qc/engine.test.ts` — 18 tests covering single-bit isolation (bits 0-4), multi-bit aggregation (3 bits → 7, all 5 → 31), immutability, vectorized call-count contract, custom rule injection, bit-31 ceiling enforcement
- `packages-ts/core/tests/qc/codegen-parity.test.ts` — 9 tests asserting full tuple equality between ALPHA_RULES and QC_ALPHA_RULES + canonical-order assertions against Python `qc.py:103-134`

### Modified
- `packages-ts/core/package.json` — added `"./qc"` subpath export (types/import/require) after `"./transforms"` entry; root `.` export UNCHANGED
- `packages-ts/core/tsup.config.ts` — added new build entry block for `src/qc/index.ts` emitting `dist/qc/{index.mjs,index.cjs,index.d.ts}`

## Decisions Made

- **Codegen consumption (TS-W4 critical-rule #4):** all rule IDs + bit positions imported from `../data/generated/qc-alpha-rules.js`; hand-coded literals strictly forbidden. The `makeRule(ruleId, evaluator)` helper performs `QC_ALPHA_RULES_BY_ID.get(ruleId)` lookup and throws if the rule is missing from the codegen table.
- **Module-load drift guard:** `if (QC_ALPHA_RULES.length !== ALPHA_RULES.length) throw` — Phase 3.5+ codegen additions won't be silently dropped; the developer is forced to add a matching evaluator.
- **camelCase column name:** `obsQcStatus` (TS-idiom departure from Python `obs_qc_status`); the JSON serializer (`jsonDumps`) handles snake_case wire conversion at the cross-language boundary.
- **Strict `>` for dewpoint > temp:** mirrors Python `df["dew_point_c"] > df["temp_c"]` (equality is physically possible at saturation).
- **Null-skip semantics:** `getNum()` returns `null` for non-finite/non-numeric/missing values; calling rule does NOT fire — matches Python `pd.Series([False]*len(df))` (missing column) + `notna()` (null-filter) parity.
- **Subpath isolation:** QC lives at `@tradewinds/core/qc`, not the root barrel; preserves the 25 kB size-limit gate (root bundle: 6.02 kB after Wave 5).
- **32-bit signed-integer ceiling:** JS bitwise OR is 32-bit signed; defensive RangeError at `QCEngine` construction for any rule with `bitPosition` outside [0, 31].

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Replaced TypeScript non-null assertions (`!`) with safe optional chaining**
- **Found during:** Task 2 (QCEngine commit) — pre-commit `biome-check` hook rejected 3 `lint/style/noNonNullAssertion` errors in `src/qc/engine.ts` and `tests/qc/engine.test.ts`
- **Issue:** `this.rules[r]!`, `rows[i]!`, `input[0]!` — biome's `noNonNullAssertion` rule (which the codebase enforces) forbids the `!` operator.
- **Fix:** Switched to safe access: `const rule = this.rules[r]; if (rule === undefined) continue;` pattern; in the test, `const inputRow = input[0]; expect(inputRow).toBeDefined(); if (inputRow !== undefined) {...}`. No behaviour change; all 18 engine tests still passing.
- **Files modified:** `packages-ts/core/src/qc/engine.ts`, `packages-ts/core/tests/qc/engine.test.ts`
- **Verification:** `pnpm vitest run tests/qc/engine.test.ts` → 18 tests passing; subsequent `git commit` cleared biome-check.
- **Committed in:** `be44f95` (Task 2 commit, after fix re-applied)

**2. [Linter-driven, no behavioural impact] Biome auto-formatted multiple files on pre-commit**
- **Found during:** All 3 task commits — `lefthook` runs `biome-check` which auto-applies safe fixes (line-length wrapping, `!` → `?.` in tests, comment reflow). Listed as "intentional, do not revert" via system reminders.
- **Issue:** Initially-written code used slightly different formatting / non-null assertions; biome normalized to project conventions.
- **Fix:** None required — biome's auto-fixes are stylistic and were committed alongside the work in each task commit.
- **Files affected:** `src/qc/rules.ts`, `src/qc/engine.ts`, `tests/qc/rules.test.ts`, `tests/qc/engine.test.ts`, `tests/qc/codegen-parity.test.ts`
- **Verification:** All 63 qc tests still pass post-format; typecheck clean across workspace; build emits expected `dist/qc/*` artifacts.
- **Committed in:** `bc5c663`, `be44f95`, `9e13eda` (within each task commit)

---

**Total deviations:** 1 auto-fix (Rule 3 - Blocking: biome lint conformance) + 1 linter-driven format pass
**Impact on plan:** Zero scope creep; both interventions enforce repo-mandated CLAUDE.md rule ("Pre-commit hooks mandatory. No `--no-verify`. Fix the underlying issue."). Functional behaviour and acceptance criteria unchanged.

## Issues Encountered

None during planned work. The two deviations above arose from project lint discipline (CLAUDE.md mandates pre-commit hooks; no `--no-verify`); both were resolved without architectural changes.

## User Setup Required

None — pure code addition at the `@tradewinds/core/qc` subpath. Downstream consumers will pick up the surface by adding `import { QCEngine, ALPHA_RULES } from "@tradewinds/core/qc"` once they need QC. No env vars, no external service config, no DB migrations.

## Verification Results

- **`pnpm --filter @tradewinds/core test -- qc`**: 63 tests passing (36 rules + 18 engine + 9 codegen-parity). All evaluators verified across in-range/out-of-range/null/missing-column/non-numeric/empty-input cases.
- **`pnpm --filter @tradewinds/core test`**: 662 tests passing (up from 599 Wave 4 baseline; +63 = the new qc tests; no regressions).
- **`pnpm --filter @tradewinds/core run typecheck`**: clean.
- **`pnpm -r run typecheck`**: clean across workspace (5 of 6 projects).
- **`pnpm --filter @tradewinds/core run build`**: success — `dist/qc/{index.mjs (4.8 kB), index.cjs (6.2 kB), index.d.ts (3.4 kB)}` all emitted.
- **`pnpm run size`**: `@tradewinds/core` 6.02 kB ≤ 25 kB gate. `@tradewinds/weather` 10.35 kB, `@tradewinds/markets` 1.59 kB, `tradewinds meta` 19.52 kB — all unchanged.
- **End-to-end runtime sanity** (`node -e "import('@tradewinds/core/qc')..."`): subpath resolves; ALPHA_RULES has 5 entries; row triggering all 5 rules yields `obsQcStatus === 31` (5-bit max).
- **Codegen-parity test**: `ALPHA_RULES[i]` tuples `(ruleId, bitPosition, field, description)` match `QC_ALPHA_RULES[i]` byte-for-byte; canonical IDs match Python `qc.py:103-134` exactly.

## Next Phase Readiness

- TS-QC-01 fully met — wave dependency unblocks Plan 06.
- QC engine surface ready for downstream sidecar parquet emission (out-of-scope this plan; Phase 3.4 Python parity at `build_sidecar_rows` deferred to a later TS plan).
- Phase 3.5+ Python rules (when added) will land in `schemas/qc-alpha-rules.json` → regenerated `QC_ALPHA_RULES` → the module-load drift guard fires until the TS evaluator is registered; no silent drift possible.

## Self-Check: PASSED

- **Files created exist:**
  - `packages-ts/core/src/qc/rules.ts` — FOUND
  - `packages-ts/core/src/qc/engine.ts` — FOUND
  - `packages-ts/core/src/qc/index.ts` — FOUND
  - `packages-ts/core/tests/qc/rules.test.ts` — FOUND
  - `packages-ts/core/tests/qc/engine.test.ts` — FOUND
  - `packages-ts/core/tests/qc/codegen-parity.test.ts` — FOUND
- **Commits exist:**
  - `bc5c663` (Task 1) — FOUND in `git log`
  - `be44f95` (Task 2) — FOUND in `git log`
  - `9e13eda` (Task 3) — FOUND in `git log`
- **Build artifacts emitted:** `dist/qc/{index.mjs, index.cjs, index.d.ts, index.d.cts}` all present.
- **No stubs introduced.** All 5 evaluators have full implementations; codegen-parity guard is a real runtime assertion, not a placeholder.

---
*Phase: ts-w4-mode2-transforms-qc-alpha*
*Completed: 2026-05-24*

---
phase: ts-w4-mode2-transforms-qc-alpha
plan: 06
subsystem: qc
tags: [qc, crosscheck, iem, ghcnh, observation-quality, tolerance, inner-join]

# Dependency graph
requires:
  - phase: ts-w4-mode2-transforms-qc-alpha
    provides: "@tradewinds/core/qc subpath (Wave 5 — barrel + tsup entry + package.json export)"
provides:
  - "crosscheckIemGhcnh(iemRows, ghcnhRows, opts?) — inner-joins IEM/GHCNh observation rows by (station, eventTime); emits disagreement rows where |tempCIem - tempCGhcnh| > tolC (default 2.0 °C, STRICT >)"
  - "CrosscheckDisagreement, CrosscheckOptions type exports at @tradewinds/core/qc subpath"
  - "Parity-Ticket: camelCase TS row keys (eventTime, tempCIem, tempCGhcnh, deltaC) vs Python snake_case (event_time, temp_c_iem, temp_c_ghcnh, delta_c) — wire-format conversion lives at JSON serializer boundary"
affects: [ts-w5 research-time QC sidecar emission, downstream IEM/GHCNh source-discrepancy audits]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Inner-join via Map<compositeKey, row>; deterministic last-wins on duplicate iem (station, eventTime) keys"
    - "Strict `>` tolerance boundary (NOT `>=`) — exact-tolerance values produce NO disagreement (Python qc.py:228 parity)"
    - "Null/NaN/Infinity temp_c silently skipped (no comparison emitted) — Python pandas NA-aware merge parity"
    - "Empty either-side input → [] (no throw) — Python qc.py:212-215 parity"
    - "Missing required columns throws Error /must carry/ — Python ValueError at qc.py:217-220 parity"

key-files:
  created:
    - "packages-ts/core/src/qc/crosscheck.ts"
    - "packages-ts/core/tests/qc/crosscheck.test.ts"
    - "packages-ts/core/tests/qc/crosscheck.barrel.test.ts"
  modified:
    - "packages-ts/core/src/qc/index.ts (appended crosscheckIemGhcnh barrel export — idempotent)"

key-decisions:
  - "Strict `>` boundary (NOT `>=`) — Python qc.py:228 uses `merged.loc[merged['delta_c'] > tol_c]`. Mismatch would emit false disagreements at the exact tolerance boundary (e.g., delta=2.0 with tolC=2.0 would silently fire a disagreement row that shouldn't exist). Tested explicitly with delta === tolC asserting empty output."
  - "deltaC is ABSOLUTE (positive number) — Math.abs(iemT - ghcnhT). Asymmetric inputs (iem=25, ghcnh=20 AND iem=20, ghcnh=25) both produce deltaC=5. Signed deltaC would silently break downstream worst-disagreement sort queries."
  - "Missing (station, eventTime) throws Error — silent empty output would mask data-shape bugs in upstream callers. Parity with Python ValueError at qc.py:217-220."
  - "Duplicate iem keys: deterministic last-wins (Map.set overwrite). Documented deviation from Python pd.merge which would cartesian-product duplicates. Last-wins is the deterministic choice for test reproducibility; same-row-pair-twice doesn't change the semantic answer at v0.1.0 cardinality (one observation per station per eventTime is the invariant)."
  - "camelCase output keys (eventTime, tempCIem, tempCGhcnh, deltaC) — Parity-Ticket documented. Matches obsQcStatus from Wave 5. Wire-format snake_case conversion happens at jsonDumps (TS-W3 Plan 07)."
  - "Subpath placement (NOT root barrel) — @tradewinds/core root bundle remains 6.02 KB; crosscheck adds ~1 KB to qc subpath only. Bundle gate (25 KB on root) unchanged."

patterns-established:
  - "Map<compositeKey, row> inner-join pattern for hash-based join semantics in TS (TS port of pandas .merge(on=cols, how='inner'))"
  - "Strict > vs >= tolerance boundary — flag CRITICAL in review-discipline rubric for any future tolerance-based QC rule"

requirements-completed:
  - TS-QC-02

# Metrics
duration: 7min
completed: 2026-05-24
---

# Phase TS-W4 Plan 06: crosscheckIemGhcnh Summary

**`crosscheckIemGhcnh` inner-joins IEM/GHCNh observation rows by `(station, eventTime)` and emits disagreement rows where `|tempCIem - tempCGhcnh| > tolC` (STRICT `>`, default 2.0 °C); shipped at `@tradewinds/core/qc` subpath alongside QCEngine + ALPHA_RULES from Wave 5.**

## Performance

- **Duration:** ~7 min
- **Started:** 2026-05-24T16:37:00Z
- **Completed:** 2026-05-24T16:44:00Z
- **Tasks:** 2 (both TDD: RED → GREEN)
- **Commits:** 4 (2× test/RED + 2× feat/GREEN)
- **Files created:** 3 (crosscheck.ts + 2 test files)
- **Files modified:** 1 (qc barrel — idempotent append)
- **Tests added:** 32 (30 unit + 2 barrel)
- **Total core tests after Wave 6:** 694 (up from 662 baseline)
- **Bundle delta:** `@tradewinds/core` unchanged at 6.02 KB / 25 KB (crosscheck lives at qc subpath, not root)

## Accomplishments

- Ported Python `tradewinds.qc.crosscheck_iem_ghcnh` (qc.py:191-228) to TypeScript with byte-equivalent semantics
- Strict `>` tolerance boundary (NOT `>=`) — Python qc.py:228 parity; tested explicitly with `delta === tolC → []`
- Default `tolC = 2.0` °C (matches Python `tol_c=2.0`)
- Inner-join on composite `(station, eventTime)` key — NO cross-product on station alone (cardinality-explosion guard)
- Empty either-side input → `[]` (no throw) — Python qc.py:212-215 parity
- Missing required columns (`station` or `eventTime`) throws `Error("…must carry 'station' (string) and 'eventTime' (string) keys")` — Python ValueError parity
- Null/NaN/Infinity temp_c silently skipped — Python pandas NA-aware merge parity
- `deltaC` is absolute (positive number) via `Math.abs` — protects downstream `.sort_by('deltaC').head()` worst-disagreement queries
- camelCase output keys `{station, eventTime, tempCIem, tempCGhcnh, deltaC}` — TS-idiom Parity-Ticket documented; Python snake_case lives at JSON serializer boundary
- Pure: input arrays not mutated (asserted via deep-equal snapshot)
- Duplicate iem keys: deterministic last-wins (`Map.set` overwrite) — documented deviation from `pd.merge` cartesian-product
- Output order = ghcnh-row iteration order (deterministic, independent of iem ordering)
- Idempotent barrel append at `packages-ts/core/src/qc/index.ts` — re-exports `crosscheckIemGhcnh`, `CrosscheckDisagreement`, `CrosscheckOptions` from `./crosscheck.js`

## Tests Added (32)

### `tests/qc/crosscheck.test.ts` (30 unit tests)

- **Empty inputs (3):** both empty → `[]`; empty iem only → `[]`; empty ghcnh only → `[]`
- **Inner-join (2):** no matching station → `[]`; matching station but different eventTime → `[]`
- **Tolerance threshold (5):** within tol → `[]`; above tol → 1 row; **strict `>` boundary** (delta === tolC → `[]`); just above tol → 1 row; custom tolC=0.5 → 1 row at delta=0.7
- **Default tolC=2.0 (3):** no opts arg with delta=2.0 → `[]`; with delta=2.5 → 1 row; `opts={}` with delta=2.0 → `[]`
- **Mixed match/no-match (1):** 3 iem + 3 ghcnh — only NYC matches AND disagrees
- **Null/non-finite handling (5):** iem null → skipped; ghcnh null → skipped; both null → skipped; iem NaN → skipped; iem Infinity → skipped
- **deltaC absolute (2):** iem=25/ghcnh=20 → deltaC=5; iem=20/ghcnh=25 → also deltaC=5
- **Missing-column throws (4):** iem missing station → throws /must carry/; iem missing eventTime → throws; ghcnh missing station → throws; ghcnh missing eventTime → throws
- **Purity (2):** does NOT mutate iem rows; does NOT mutate ghcnh rows
- **Output order (1):** disagreements emitted in ghcnh-row iteration order
- **Duplicate iem keys (1):** two iem rows same composite key — last temp_c wins (`tempCIem: 30` over 20)
- **Composite key correctness (1):** same station, different eventTime → separate entries (not collapsed)

### `tests/qc/crosscheck.barrel.test.ts` (2 barrel tests)

- `crosscheckIemGhcnh` is exported from `@tradewinds/core/qc` barrel (typeof === "function")
- Returns `CrosscheckDisagreement` shape with camelCase keys — explicit `Object.hasOwn` assertions confirm presence of `eventTime`, `tempCIem`, `tempCGhcnh`, `deltaC` AND absence of Python snake_case `event_time`, `temp_c_iem`, `temp_c_ghcnh`, `delta_c`

## Verification Commands

```bash
# Wave 6 unit + barrel tests (32 cases, all green)
CI=1 pnpm --filter @tradewinds/core test -- qc/crosscheck
# → 2 test files, 32 tests passed

# All qc tests (rules + engine + codegen-parity + crosscheck + barrel)
CI=1 pnpm --filter @tradewinds/core test -- qc
# → 5 test files, 95 tests passed

# Full workspace test suite
CI=1 pnpm -r run test
# → core 694 / weather 218 / markets 41 / meta 85+1skip / codegen 6 — all green

# Typecheck
pnpm -r run typecheck
# → core / codegen / weather / markets / meta — all clean

# Bundle size gate
pnpm run size
# → @tradewinds/core 6.02 KB / 25 KB (unchanged; crosscheck at subpath)
```

## Commits

```
0556d08 feat(ts-w4/06): re-export crosscheckIemGhcnh from @tradewinds/core/qc barrel
37eb119 test(ts-w4/06): add failing barrel re-export test for crosscheckIemGhcnh
b3d666c feat(ts-w4/06): implement crosscheckIemGhcnh inner-join + tolerance
1cfd543 test(ts-w4/06): add failing tests for crosscheckIemGhcnh
```

## Deviations from Plan

**None for the function semantics or contract.** Plan executed exactly as written.

**Minor formatting auto-fix (Rule 1 — toolchain hygiene, not a code change):**
- Biome pre-commit auto-collapsed two lines in `crosscheck.ts` (lines 128-129 collapsed into one line each for the `iT`/`gT` ternary assignments) — purely formatting; identical AST.
- Biome flagged non-null assertions (`out[0]!`) in `crosscheck.barrel.test.ts` per `lint/style/noNonNullAssertion`. Rewrote as explicit `const row = out[0]; if (row === undefined) throw …` guard. Same semantic check, no `--no-verify` bypass used. Conforms to CLAUDE.md "Pre-commit + pre-push hooks mandatory. No `--no-verify`. Fix the underlying issue."

## Parity Notes

Python `tradewinds.qc.crosscheck_iem_ghcnh` (qc.py:191-228):

| Concern | Python | TS | Status |
|---------|--------|-----|--------|
| Tolerance comparison | `merged.loc[merged["delta_c"] > tol_c]` (strict `>`) | `if (delta > tolC)` (strict `>`) | ✅ byte-equivalent |
| Default tolerance | `tol_c: float = 2.0` | `opts.tolC ?? 2.0` | ✅ byte-equivalent |
| Inner-join key | `key_cols = ["station", "event_time"]` | `${row.station}|${row.eventTime}` composite | ✅ semantically equivalent |
| Empty handling | empty df → empty result df with named columns | empty input → `[]` | ✅ semantically equivalent (TS doesn't have "empty DataFrame with columns" shape) |
| Missing columns | `raise ValueError("iem_df missing required columns")` | `throw new Error("…must carry 'station' …")` | ✅ semantically equivalent |
| Delta sign | `(temp_c_iem - temp_c_ghcnh).abs()` | `Math.abs(iT - gT)` | ✅ byte-equivalent |
| Row keys | snake_case (event_time, temp_c_iem, temp_c_ghcnh, delta_c) | camelCase (eventTime, tempCIem, tempCGhcnh, deltaC) | ⚠️ **Parity-Ticket** — documented deviation; wire-format snake_case at jsonDumps |
| Duplicate iem keys | pd.merge cartesian-product | Map last-wins | ⚠️ documented deviation; deterministic, low-impact at v0.1.0 cardinality |
| Output order | merge result order (pandas implementation-defined) | ghcnh-row iteration order | ⚠️ documented deviation; deterministic |

## Self-Check: PASSED

- `packages-ts/core/src/qc/crosscheck.ts` exists (commit b3d666c)
- `packages-ts/core/tests/qc/crosscheck.test.ts` exists (commit 1cfd543)
- `packages-ts/core/tests/qc/crosscheck.barrel.test.ts` exists (commit 37eb119)
- `packages-ts/core/src/qc/index.ts` modified to re-export (commit 0556d08)
- All 4 commits present in `git log` on branch `ts-w4/mode2-transforms-qc-alpha`
- All acceptance criteria grep checks pass (export function, strict `>`, Math.abs, default tolC, must-carry throws, camelCase keys)
- `@tradewinds/core` 694 tests green (up from 662 baseline = +32 new)
- `pnpm -r run typecheck` clean across workspace
- `pnpm run size`: `@tradewinds/core` 6.02 KB / 25 KB gate unchanged
- Strict `>` boundary test explicitly asserts `delta === tolC → []` (NOT a disagreement row)
- Zero tests assert `deltaC === negative_value` (deltaC is absolute by contract)

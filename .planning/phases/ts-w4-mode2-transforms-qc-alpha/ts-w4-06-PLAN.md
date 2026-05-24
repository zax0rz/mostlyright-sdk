---
phase: ts-w4-mode2-transforms-qc-alpha
plan: 06
type: execute
wave: 6
depends_on: []
files_modified:
  - packages-ts/core/src/qc/crosscheck.ts
  - packages-ts/core/src/qc/index.ts
  - packages-ts/core/tests/qc/crosscheck.test.ts
autonomous: true
requirements:
  - TS-QC-02
must_haves:
  truths:
    - "crosscheckIemGhcnh(iemRows, ghcnhRows, opts?) returns ReadonlyArray<{station, eventTime, tempCIem, tempCGhcnh, deltaC}>"
    - "Default tolerance opts.tolC = 2.0 (matches Python crosscheck_iem_ghcnh tol_c=2.0)"
    - "Inner-join semantics: only rows with matching (station, eventTime) in BOTH inputs are compared"
    - "Returned disagreement rows: |tempCIem - tempCGhcnh| > tolC (strict greater-than, NOT >=; matches Python qc.py:228)"
    - "deltaC value is the ABSOLUTE difference (positive number); never negative"
    - "Empty iem or empty ghcnh → returns empty array (NO throw, NO error rows)"
    - "Missing required columns in either input throws Error (parity with Python ValueError at qc.py:217-220)"
    - "Output row shape uses camelCase TS row keys (eventTime, tempCIem, tempCGhcnh, deltaC) — TS-idiom departure from Python's snake_case event_time/temp_c_iem documented per Parity-Ticket"
    - "Output is independent of input row order (stable inner-join)"
  artifacts:
    - path: packages-ts/core/src/qc/crosscheck.ts
      provides: "crosscheckIemGhcnh function — inner-joins IEM + GHCNh rows by (station, eventTime); returns disagreements above tolC"
    - path: packages-ts/core/src/qc/index.ts
      provides: "Barrel re-exports crosscheckIemGhcnh alongside QCEngine + ALPHA_RULES"
  key_links:
    - from: packages-ts/core/src/qc/crosscheck.ts
      to: "qc subpath (created in Wave 5)"
      via: "exported via the same @tradewinds/core/qc barrel"
      pattern: "from .\\./qc"
---

<objective>
Port Python `tradewinds.qc.crosscheck_iem_ghcnh` to TS at `@tradewinds/core/qc`. Returns disagreement rows where the same `(station, event_time)` pair has IEM-vs-GHCNh `temp_c` values that differ by more than the tolerance.

**Signature:**
```typescript
crosscheckIemGhcnh<
  IemRow extends { station: string; eventTime: string; temp_c: number | null },
  GhcnhRow extends { station: string; eventTime: string; temp_c: number | null }
>(
  iemRows: ReadonlyArray<IemRow>,
  ghcnhRows: ReadonlyArray<GhcnhRow>,
  opts?: { tolC?: number },
): ReadonlyArray<{
  station: string;
  eventTime: string;
  tempCIem: number;
  tempCGhcnh: number;
  deltaC: number;
}>
```

**Inner-join + tolerance logic:**
1. Build a `Map<string, IemRow>` keyed by `${station}|${eventTime}` from IEM rows (latest-wins on collisions — same as Python pandas `.merge(on=key_cols, how='inner')` which keeps the iemDF row order).
2. For each GHCNh row, look up the matching IEM row by composite key.
3. If both `temp_c` values are finite numbers and `|iem - ghcnh| > tolC` → emit a disagreement row.
4. `tolC` default = `2.0`.

**Column-shape Parity-Ticket:** Python returns `{station, event_time, temp_c_iem, temp_c_ghcnh, delta_c}` (snake_case). TS returns `{station, eventTime, tempCIem, tempCGhcnh, deltaC}` (camelCase). Documented as a Parity-Ticket because the TS row-key idiom is camelCase elsewhere in the codebase (see `obsQcStatus` from Wave 5). Wire-format conversion is the JSON serializer's job (TS-W3 Plan 07 `jsonDumps` snake_cases on serialize).

**Subpath placement:** lives in the `@tradewinds/core/qc` subpath established by Wave 5. Wave 6 only adds a file + barrel entry. No new subpath / tsup wiring needed (idempotent: if Wave 5 hasn't shipped, Wave 6 creates the scaffolding itself per Wave 5's spec — but the wave order intentionally puts Wave 5 first because the codegen-parity guard + QCEngine ship the qc surface).

**Independence:** Wave 6 has NO hard dependency on Waves 1-5. Sequenced after Wave 5 only because they share the `@tradewinds/core/qc` subpath; Wave 6 can run in parallel with Waves 2-5 if scheduling allows AND the qc subpath is created by whichever wave runs first (idempotent file additions).

**Note on input row shape:** The TS `crosscheckIemGhcnh` requires `eventTime: string` on input rows (not Python's flexible `event_time` / `observed_at` auto-derivation). Callers normalize before calling. This narrowing keeps the TS surface predictable; the equivalent Python flexibility (`preprocessing.iem_crosscheck` auto-deriving `event_time` from `observed_at`) is NOT ported in v0.1.0.
</objective>

<context_files>
- `.planning/REQUIREMENTS.md` TS-QC-02 (canonical text)
- `packages/core/src/tradewinds/qc.py` lines 191-228 (Python `crosscheck_iem_ghcnh` — port the inner-join + abs(delta) > tol logic)
- `packages-ts/core/src/qc/engine.ts` (Wave 5 — shares the same subpath; no import dependency)
- `package.json` root size-limit block.
- Wave 5 plan (ts-w4-05-PLAN.md) for the qc subpath + tsup + barrel scaffolding context.
</context_files>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: crosscheckIemGhcnh inner-join + tolerance + disagreement output</name>
  <files>packages-ts/core/src/qc/crosscheck.ts, packages-ts/core/tests/qc/crosscheck.test.ts</files>
  <read_first>
    - `packages/core/src/tradewinds/qc.py` lines 191-228 (Python source — note strict `>` at line 228, NOT `>=`)
    - `packages-ts/core/src/qc/engine.ts` (Wave 5 output — shared module style)
  </read_first>
  <behavior>
    - `CrosscheckOptions = { tolC?: number }`. Default `tolC = 2.0`.
    - `CrosscheckRowIn = { station: string; eventTime: string; temp_c: number | null }`. Input rows must carry these three keys; extra keys allowed (generic).
    - `CrosscheckDisagreement = { station: string; eventTime: string; tempCIem: number; tempCGhcnh: number; deltaC: number }`.
    - Algorithm:
      1. If `iemRows.length === 0 || ghcnhRows.length === 0` → return `[]` (matches Python qc.py:212-215).
      2. Build `iemMap: Map<string, IemRow>` keyed by `${row.station}|${row.eventTime}`. On duplicate keys (same station + eventTime), LAST iem row wins (Python `pd.merge` doesn't dedupe; if duplicates exist they cartesian-product, but we keep it deterministic with last-wins; document the deviation in JSDoc).
      3. For each GHCNh row, lookup `iemMap.get('${row.station}|${row.eventTime}')`. If missing → skip.
      4. If both `temp_c` are finite numbers, compute `delta = Math.abs(iemRow.temp_c - ghcnhRow.temp_c)`. If `delta > tolC` → emit disagreement row.
      5. Returned array order matches GHCNh row order (Python's merge has implementation-defined order; we pin to ghcnhRows.iteration order for determinism).
    - **Column missing throw:** if any iem row lacks `station` or `eventTime`, OR any ghcnh row lacks them, throw `Error("crosscheckIemGhcnh: rows must carry 'station' and 'eventTime' keys")`. Matches Python ValueError at `qc.py:217-220`.
    - Pure: input arrays NOT mutated.
    - Type narrowing: TS doesn't easily prove `eventTime` is present at runtime via the type signature alone (rows could be cast from `any`); runtime check guards the join.
  </behavior>
  <action>
    1. Create `packages-ts/core/src/qc/crosscheck.ts`:
       ```typescript
       /**
        * crosscheckIemGhcnh — disagreement detection between IEM + GHCNh
        * temperature readings. Mirrors Python `tradewinds.qc.crosscheck_iem_ghcnh`
        * at `packages/core/src/tradewinds/qc.py:191-228`.
        *
        * Inner-joins by composite key `(station, eventTime)`. For matched
        * pairs where both temp_c are finite numbers and the absolute
        * delta exceeds `opts.tolC` (default 2.0 °C), emits a disagreement
        * row. Threshold is strict `>` (NOT `>=`) per Python qc.py:228.
        *
        * Parity-Ticket: Python returns snake_case keys (event_time,
        * temp_c_iem, temp_c_ghcnh, delta_c); TS returns camelCase
        * (eventTime, tempCIem, tempCGhcnh, deltaC). Wire-format
        * conversion happens at the JSON serializer.
        */
       export interface CrosscheckOptions {
         tolC?: number;
       }

       export interface CrosscheckDisagreement {
         readonly station: string;
         readonly eventTime: string;
         readonly tempCIem: number;
         readonly tempCGhcnh: number;
         readonly deltaC: number;
       }

       interface CrosscheckRowIn {
         station?: unknown;
         eventTime?: unknown;
         temp_c?: unknown;
       }

       export function crosscheckIemGhcnh(
         iemRows: ReadonlyArray<CrosscheckRowIn>,
         ghcnhRows: ReadonlyArray<CrosscheckRowIn>,
         opts: CrosscheckOptions = {},
       ): ReadonlyArray<CrosscheckDisagreement> {
         const tolC = opts.tolC ?? 2.0;

         if (iemRows.length === 0 || ghcnhRows.length === 0) return [];

         // Validate column presence upfront (parity with Python ValueError).
         for (const r of iemRows) {
           if (typeof r?.station !== "string" || typeof r?.eventTime !== "string") {
             throw new Error(
               `crosscheckIemGhcnh: iem rows must carry 'station' (string) and 'eventTime' (string) keys`,
             );
           }
         }
         for (const r of ghcnhRows) {
           if (typeof r?.station !== "string" || typeof r?.eventTime !== "string") {
             throw new Error(
               `crosscheckIemGhcnh: ghcnh rows must carry 'station' (string) and 'eventTime' (string) keys`,
             );
           }
         }

         // Build iem lookup map. Last-wins on duplicate (station, eventTime).
         const iemMap = new Map<string, CrosscheckRowIn>();
         for (const r of iemRows) {
           const key = `${r.station as string}|${r.eventTime as string}`;
           iemMap.set(key, r);
         }

         const out: CrosscheckDisagreement[] = [];
         for (const g of ghcnhRows) {
           const key = `${g.station as string}|${g.eventTime as string}`;
           const i = iemMap.get(key);
           if (i === undefined) continue;
           const iT = typeof i.temp_c === "number" && Number.isFinite(i.temp_c) ? i.temp_c : null;
           const gT = typeof g.temp_c === "number" && Number.isFinite(g.temp_c) ? g.temp_c : null;
           if (iT === null || gT === null) continue;
           const delta = Math.abs(iT - gT);
           if (delta > tolC) {
             out.push({
               station: g.station as string,
               eventTime: g.eventTime as string,
               tempCIem: iT,
               tempCGhcnh: gT,
               deltaC: delta,
             });
           }
         }
         return out;
       }
       ```

    2. Write `packages-ts/core/tests/qc/crosscheck.test.ts`:
       - **Empty inputs:**
         - `crosscheckIemGhcnh([], [], )` → `[]`.
         - Empty iem only → `[]`.
         - Empty ghcnh only → `[]`.
       - **No matching keys:** iem has `(NYC, 2024-06-01T00:00:00Z)`, ghcnh has `(LAX, 2024-06-01T00:00:00Z)` → `[]`.
       - **Agreement within tolerance:**
         - iem: `[{station:'NYC', eventTime:'2024-06-01T00:00:00Z', temp_c:20.0}]`.
         - ghcnh: `[{station:'NYC', eventTime:'2024-06-01T00:00:00Z', temp_c:21.5}]`.
         - `crosscheckIemGhcnh(iem, ghcnh, {tolC: 2.0})` → `[]` (delta=1.5 ≤ tol).
       - **Disagreement above tolerance:**
         - iem: `[{station:'NYC', eventTime:'2024-06-01T00:00:00Z', temp_c:20.0}]`.
         - ghcnh: `[{station:'NYC', eventTime:'2024-06-01T00:00:00Z', temp_c:25.0}]`.
         - `crosscheckIemGhcnh(iem, ghcnh, {tolC: 2.0})` → 1 row: `{station:'NYC', eventTime:'2024-06-01T00:00:00Z', tempCIem:20.0, tempCGhcnh:25.0, deltaC:5.0}`.
       - **Strict `>` boundary:**
         - iem 20.0, ghcnh 22.0, tolC 2.0 → `[]` (delta === tol; STRICT greater-than).
         - iem 20.0, ghcnh 22.001, tolC 2.0 → 1 disagreement row.
       - **Default tolC = 2.0 (no opts arg):**
         - iem 20.0, ghcnh 22.0 (delta=2.0) → `[]`.
         - iem 20.0, ghcnh 22.5 (delta=2.5) → 1 disagreement.
       - **Mixed match/no-match:**
         - iem: 3 rows with stations NYC, LAX, BOS.
         - ghcnh: 3 rows with stations NYC (matches+disagrees), LAX (matches+agrees), CHI (no match).
         - Expected: 1 disagreement row (NYC only).
       - **Null temp_c skipped:**
         - iem: `[{station:'NYC', eventTime:'...', temp_c:null}]`.
         - ghcnh: `[{station:'NYC', eventTime:'...', temp_c:25.0}]`.
         - → `[]` (no comparison when either is null).
       - **deltaC is absolute (positive):**
         - iem 25, ghcnh 20, delta=5 → row with `deltaC: 5` (NOT -5).
         - iem 20, ghcnh 25 → also `deltaC: 5`.
       - **Missing column throws:**
         - iem row without `station` → throws Error containing 'must carry'.
         - ghcnh row without `eventTime` → throws Error.
       - **Custom tolC = 0.5:**
         - iem 20.0, ghcnh 20.7, tolC=0.5 → 1 disagreement (delta=0.7 > 0.5).
       - **Source rows unchanged** (deep-equal on input arrays).
       - **Output order matches ghcnhRows iteration order** (assert by checking which row appears first in output when both ghcnh[0] and ghcnh[1] disagree).
       - **Duplicate iem keys: last-wins:**
         - iem: 2 rows with same station+eventTime; first temp_c=20, second temp_c=30.
         - ghcnh: 1 row station+eventTime same; temp_c=25.
         - Expected: 1 disagreement with `tempCIem: 30` (last iem wins) and `deltaC: 5`.
  </action>
  <acceptance_criteria>
    - `grep -n "export function crosscheckIemGhcnh" packages-ts/core/src/qc/crosscheck.ts` matches.
    - `grep -n "delta > tolC\\|delta > opts.tolC" packages-ts/core/src/qc/crosscheck.ts` confirms strict greater-than.
    - `grep -n "Math.abs" packages-ts/core/src/qc/crosscheck.ts` confirms absolute delta.
    - `grep -n "tolC ?? 2.0\\|opts.tolC ?? 2.0" packages-ts/core/src/qc/crosscheck.ts` confirms default tolerance.
    - `grep -n "throw new Error.*must carry\\|station.*eventTime.*string" packages-ts/core/src/qc/crosscheck.ts` confirms column-presence validation.
    - `grep -n "tempCIem\\|tempCGhcnh\\|deltaC\\|eventTime" packages-ts/core/src/qc/crosscheck.ts` confirms camelCase output keys.
    - `pnpm --filter @tradewinds/core test -- qc/crosscheck` ≥ 14 cases all green.
    - Strict-`>` boundary test explicitly asserts delta === tolC produces NO disagreement.
  </acceptance_criteria>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Add crosscheckIemGhcnh to qc barrel</name>
  <files>packages-ts/core/src/qc/index.ts, packages-ts/core/tests/qc/crosscheck.barrel.test.ts</files>
  <read_first>
    - `packages-ts/core/src/qc/index.ts` (Wave 5 output)
    - Wave 5's barrel test for pattern.
  </read_first>
  <behavior>
    - Append `crosscheckIemGhcnh` + the two related types to the qc barrel.
    - Verify subpath + tsup entry exist (created in Wave 5 — idempotent if Wave 6 runs first).
    - Bundle gate: after Wave 6 builds, `pnpm run size` confirms `@tradewinds/core` ≤ 25 KB. Crosscheck adds ~1 KB to qc bundle; comfortably within limits.
  </behavior>
  <action>
    1. Append to `packages-ts/core/src/qc/index.ts`:
       ```typescript
       export {
         crosscheckIemGhcnh,
         type CrosscheckDisagreement,
         type CrosscheckOptions,
       } from "./crosscheck.js";
       ```

    2. Write `packages-ts/core/tests/qc/crosscheck.barrel.test.ts`:
       ```typescript
       import { describe, expect, it } from "vitest";
       import {
         crosscheckIemGhcnh,
         type CrosscheckDisagreement,
       } from "../../src/qc/index.js";

       describe("@tradewinds/core/qc — crosscheckIemGhcnh barrel re-export", () => {
         it("crosscheckIemGhcnh is exported from the barrel", () => {
           expect(typeof crosscheckIemGhcnh).toBe("function");
         });

         it("Returns CrosscheckDisagreement shape with camelCase keys", () => {
           const iem = [{ station: "NYC", eventTime: "2024-06-01T00:00:00Z", temp_c: 20 }];
           const ghcnh = [{ station: "NYC", eventTime: "2024-06-01T00:00:00Z", temp_c: 25 }];
           const out: ReadonlyArray<CrosscheckDisagreement> = crosscheckIemGhcnh(iem, ghcnh);
           expect(out.length).toBe(1);
           expect(out[0]).toEqual({
             station: "NYC",
             eventTime: "2024-06-01T00:00:00Z",
             tempCIem: 20,
             tempCGhcnh: 25,
             deltaC: 5,
           });
           // Explicit key-presence assertions for the camelCase contract.
           expect(Object.hasOwn(out[0]!, "eventTime")).toBe(true);
           expect(Object.hasOwn(out[0]!, "tempCIem")).toBe(true);
           expect(Object.hasOwn(out[0]!, "tempCGhcnh")).toBe(true);
           expect(Object.hasOwn(out[0]!, "deltaC")).toBe(true);
           // Should NOT have snake_case (the Python form).
           expect(Object.hasOwn(out[0]!, "event_time")).toBe(false);
           expect(Object.hasOwn(out[0]!, "temp_c_iem")).toBe(false);
         });
       });
       ```

    3. Run `pnpm --filter @tradewinds/core run build && pnpm run size`. Assert `@tradewinds/core` ≤ 25 KB.
  </action>
  <acceptance_criteria>
    - `grep -n "crosscheckIemGhcnh\\|CrosscheckDisagreement\\|CrosscheckOptions" packages-ts/core/src/qc/index.ts` confirms barrel export.
    - `pnpm --filter @tradewinds/core test -- qc/crosscheck.barrel` 2 cases green.
    - `pnpm --filter @tradewinds/core run build` emits the updated qc bundle.
    - `pnpm run size` reports `@tradewinds/core` ≤ 25 KB unchanged.
    - `pnpm -r run typecheck` clean.
  </acceptance_criteria>
</task>

</tasks>

<verification>
1. `pnpm --filter @tradewinds/core test -- qc/crosscheck` runs both crosscheck test files (unit + barrel); ≥ 16 cases all green.
2. `pnpm --filter @tradewinds/core test -- qc` runs ALL qc test files (Wave 5 rules + engine + codegen-parity + Wave 6 crosscheck); all green.
3. `pnpm --filter @tradewinds/core run typecheck` clean.
4. `pnpm --filter @tradewinds/core run build` emits `dist/qc/{index.mjs,index.cjs,index.d.ts}` with `crosscheckIemGhcnh` exported.
5. `pnpm -r run typecheck` clean across the workspace.
6. `pnpm run size` reports `@tradewinds/core` ≤ 25 KB.
7. Strict-`>` boundary test confirms delta === tolC produces NO disagreement.
8. Output row shape uses camelCase (eventTime, tempCIem, tempCGhcnh, deltaC) — wire-format conversion to snake_case is the JSON serializer's responsibility.
</verification>

<success_criteria>
- TS-QC-02 fully met — crosscheckIemGhcnh inner-joins on `(station, eventTime)`; emits disagreement rows where `|tempCIem - tempCGhcnh| > tolC`; default tolC=2.0; missing-column throws Error.
- Strict greater-than (NOT `>=`) for the tolerance threshold (Python parity at qc.py:228).
- Disagreement row shape: `{station, eventTime, tempCIem, tempCGhcnh, deltaC}` camelCase; Parity-Ticket documented re Python snake_case.
- Pure: input arrays not mutated; deterministic last-wins on duplicate iem keys.
- Bundle gate holds: `@tradewinds/core` ≤ 25 KB.
- ZERO test cases assert `deltaC === negative_value` (deltaC is absolute by contract).
</success_criteria>

<review_discipline>
TypeScript-only changes under `packages-ts/core/**`. Per `.planning/REVIEW-DISCIPLINE.md`:

- **Reviewers**: codex `high` + **TypeScript Architect** (parallel).
- **Severity gate**: CRITICAL or HIGH only.
- **Loop**: fix on branch, re-dispatch, cap at 3.
- **Rubric calibration**:
  - CRITICAL if the tolerance comparison uses `>=` instead of `>` (Python qc.py:228 uses strict `>`; mismatch would emit false disagreements at the exact boundary).
  - CRITICAL if `deltaC` is signed (not absolute) — a negative deltaC silently breaks downstream `.sort_by('deltaC').head(10)` queries that look for worst-disagreements.
  - CRITICAL if missing `(station, eventTime)` columns silently produces empty output instead of throwing (Python raises ValueError; silent empty would mask data-shape bugs).
  - HIGH if the inner-join key uses ONLY `station` (cross-joining every iem station to every ghcnh station at the same eventTime is a 1000x cardinality explosion).
  - HIGH if `tempCIem`/`tempCGhcnh` are emitted as strings instead of numbers (downstream `.mean()` or `Math.abs` operations need numeric).
  - HIGH if row shape uses snake_case (event_time, temp_c_iem) — the TS-idiom departure is documented; camelCase is the locked contract.
  - HIGH if the function mutates iemRows or ghcnhRows (row-immutability invariant).
  - HIGH if duplicate iem keys silently produce ARBITRARY winner instead of deterministic last-wins (test reproducibility break).
  - HIGH if `crosscheckIemGhcnh` ships in the root `@tradewinds/core` barrel (bundle bloat; qc lives at subpath).
</review_discipline>

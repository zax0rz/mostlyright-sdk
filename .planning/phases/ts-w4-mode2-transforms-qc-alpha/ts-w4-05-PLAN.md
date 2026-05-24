---
phase: ts-w4-mode2-transforms-qc-alpha
plan: 05
type: execute
wave: 5
depends_on:
  - ts-w4-02
  - ts-w4-03
  - ts-w4-04
files_modified:
  - packages-ts/core/src/qc/rules.ts
  - packages-ts/core/src/qc/engine.ts
  - packages-ts/core/src/qc/index.ts
  - packages-ts/core/package.json
  - packages-ts/core/tsup.config.ts
  - packages-ts/core/tests/qc/rules.test.ts
  - packages-ts/core/tests/qc/engine.test.ts
  - packages-ts/core/tests/qc/codegen-parity.test.ts
autonomous: true
requirements:
  - TS-QC-01
must_haves:
  truths:
    - "QCRule interface exposes ruleId (string), bitPosition (number), and evaluate(rows) → boolean[] (one entry per row, true=rule fired)"
    - "5 alpha rules ported with EXACT ruleId + bitPosition values consumed from packages-ts/core/src/data/generated/qc-alpha-rules.ts (NOT hand-coded)"
    - "Rule IDs: temp_c.out_of_range (bit 0), dew_point_c.exceeds_temp (bit 1), wind_speed_ms.negative (bit 2), wind_dir_deg.out_of_range (bit 3), slp_hpa.out_of_range (bit 4)"
    - "QCEngine.apply(rows) returns rows with new column obsQcStatus (number; 32-bit bitfield)"
    - "Each row's obsQcStatus value has bit N set iff rule N.evaluate(rows)[i] === true"
    - "Empty input → empty output (no throw); empty obsQcStatus column added"
    - "Rows missing the column a rule operates on → rule does NOT fire (returns false for all rows; matches Python qc.py:57-58)"
    - "Rules registry uses QC_ALPHA_RULES_BY_ID from codegen for lookup; bit positions NEVER hardcoded in engine.ts"
    - "Subpath @tradewinds/core/qc exports QCEngine, QCRule, ALPHA_RULES (the 5 ported rules), and the underlying QC_ALPHA_RULES data"
  artifacts:
    - path: packages-ts/core/src/qc/rules.ts
      provides: "5 alpha rule evaluators wired to codegen QC_ALPHA_RULES bit positions"
    - path: packages-ts/core/src/qc/engine.ts
      provides: "QCEngine class with apply() emitting obsQcStatus bitfield column"
    - path: packages-ts/core/src/qc/index.ts
      provides: "Barrel re-exports QCEngine, QCRule, ALPHA_RULES, QC_ALPHA_RULES"
  key_links:
    - from: packages-ts/core/src/qc/rules.ts
      to: "packages-ts/core/src/data/generated/qc-alpha-rules.ts"
      via: "import { QC_ALPHA_RULES, QC_ALPHA_RULES_BY_ID } from '../data/generated/qc-alpha-rules.js'"
      pattern: "from .\\.\\./data/generated/qc-alpha-rules"
    - from: packages-ts/core/src/qc/engine.ts
      to: "ALPHA_RULES list from rules.ts"
      via: "iterates rules to OR each rule's bit into obsQcStatus per row"
      pattern: "obsQcStatus.*\\|=\\|<< rule.bitPosition"
---

<objective>
Port Python Phase 3.4 QCEngine + 5 alpha rules to TS at `@tradewinds/core/qc`. The bit-positions and rule-IDs are NOT redefined — they're CONSUMED from the codegen-shipped table at `packages-ts/core/src/data/generated/qc-alpha-rules.ts` (already materialized; bit positions verified: temp_c.out_of_range=0, dew_point_c.exceeds_temp=1, wind_speed_ms.negative=2, wind_dir_deg.out_of_range=3, slp_hpa.out_of_range=4).

**The non-negotiable contract:** rule IDs and bit positions come from `QC_ALPHA_RULES` / `QC_ALPHA_RULES_BY_ID` (the codegen artifact). The Wave 5 implementation provides ONLY the per-rule `evaluate(rows): boolean[]` functions and the `QCEngine.apply(rows)` orchestration. If the codegen table changes (e.g. Python Phase 3.5 adds a 6th rule), the Wave 5 code picks up the new bit position automatically (assuming a matching evaluator exists in rules.ts).

**TS-W4 critical-rule #4 enforcement:** Wave 5 MUST import `QC_ALPHA_RULES` and `QC_ALPHA_RULES_BY_ID` from `../data/generated/qc-alpha-rules.js`. Bit positions and rule IDs come from there, NEVER hand-coded. A dedicated `codegen-parity.test.ts` asserts the runtime ruleId → bitPosition mapping matches the codegen table byte-for-byte; this is the regression guard against future drift.

**Output column naming:** `obsQcStatus` (camelCase TS-side; Python uses `obs_qc_status` snake_case). This is a deliberate TS-idiom departure documented per Parity-Ticket: TS row keys follow TS naming; Python row keys follow Python naming. The wire-format conversion happens at the JSON serializer boundary (TS-W3 Plan 07 `jsonDumps` handles this), so cross-language MCP shape stays compatible.

**Subpath placement:** `@tradewinds/core/qc` is a NEW subpath. Bundle-size discipline: keep QC out of the root barrel (same pattern as transforms / temporal / formats). Wave 5 ships the package.json + tsup wiring. The qc subpath bundle is allowed to grow up to ~5 KB; the existing 25 KB limit on `@tradewinds/core`'s root bundle is unaffected.

**Wave dependency:** Wave 5 depends on Waves 2 + 3 + 4 ONLY for the column-naming convention `{col}_{op}_{param}` they establish (QC rules don't consume transform output but the engine's `obsQcStatus` column should match the same camelCase row-key idiom). No hard import dependency on transforms.
</objective>

<context_files>
- `.planning/REQUIREMENTS.md` TS-QC-01 (canonical text — note the Python source line 103 reference + the "loaded from codegen" requirement)
- `packages/core/src/tradewinds/qc.py` lines 33-160 (Python source — `QCRule` Protocol, `_RuleSpec` dataclass, 5 evaluator functions, `ALPHA_RULES` tuple, `QCEngine.apply`)
- `packages-ts/core/src/data/generated/qc-alpha-rules.ts` (codegen output — ALREADY MATERIALIZED; do NOT modify; CONSUME this)
- `packages-ts/core/src/data/generated/index.ts` (existing barrel — confirm QC_ALPHA_RULES is re-exported, OR if not, the qc package imports directly)
- Wave 2 / 3 / 4 plans for the transforms subpath + tsup + size-gate scaffolding pattern (mirror it for the qc subpath).
- `packages-ts/core/tests/internal/cache/bundle-sanity.test.ts` (TS-W3 reference for how bundles are sanity-checked).
</context_files>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: 5 alpha rule evaluators wired to codegen QC_ALPHA_RULES</name>
  <files>packages-ts/core/src/qc/rules.ts, packages-ts/core/tests/qc/rules.test.ts</files>
  <read_first>
    - `packages/core/src/tradewinds/qc.py` lines 53-97 (the 5 `_rule_*` evaluator functions — port verbatim)
    - `packages-ts/core/src/data/generated/qc-alpha-rules.ts` (the 5-rule codegen table — verify bit positions + rule IDs match Python qc.py:103-134)
  </read_first>
  <behavior>
    - Define `QCRule` interface:
      ```typescript
      export interface QCRule {
        readonly ruleId: string;
        readonly bitPosition: number;
        readonly description: string;
        readonly field: string;
        evaluate<Row extends Record<string, unknown>>(rows: ReadonlyArray<Row>): boolean[];
      }
      ```
    - 5 evaluator functions matching Python `qc.py:53-97`:
      - `evalTempOutOfRange(rows)`: returns `boolean[]`; `true` where `row.temp_c < -89 || row.temp_c > 57`. Rows where `temp_c` is missing/null/non-finite → `false` (matches Python `if "temp_c" not in df.columns: return Series([False]*len(df))` AND silent NaN handling).
      - `evalDewpointExceedsTemp(rows)`: `true` where `row.dew_point_c > row.temp_c` (both must be present + finite numbers; else `false`).
      - `evalWindSpeedNegative(rows)`: `true` where `row.wind_speed_ms < 0` (must be finite number).
      - `evalWindDirOutOfRange(rows)`: `true` where `row.wind_dir_deg < 0 || row.wind_dir_deg > 360`. Null wind_dir_deg → `false` (Python uses `notna()` + `~valid` at lines 86-87).
      - `evalSlpOutOfRange(rows)`: `true` where `row.slp_hpa < 870 || row.slp_hpa > 1085`. Null slp → false.
    - Wire each evaluator to the corresponding codegen entry via `QC_ALPHA_RULES_BY_ID.get(ruleId)`:
      ```typescript
      function makeRule(
        ruleId: string,
        evaluate: (rows: ReadonlyArray<Record<string, unknown>>) => boolean[],
      ): QCRule {
        const spec = QC_ALPHA_RULES_BY_ID.get(ruleId);
        if (spec === undefined) {
          throw new Error(`QC rule '${ruleId}' missing from codegen table; regenerate with 'pnpm codegen'`);
        }
        return {
          ruleId: spec.rule_id,
          bitPosition: spec.bit_position,
          description: spec.description,
          field: spec.field,
          evaluate,
        };
      }
      ```
      Note the `_ID_BY_ID` field names are snake_case in the codegen output (`rule_id`, `bit_position`); the QCRule interface re-exposes camelCase to align with TS idiom.
    - Export `ALPHA_RULES: ReadonlyArray<QCRule>` — five rules in the order matching `QC_ALPHA_RULES` (which is bit-position order: 0, 1, 2, 3, 4).
    - **Critical safety net:** if `QC_ALPHA_RULES.length !== ALPHA_RULES.length`, throw at module load — protects against the codegen table growing (Python Phase 3.5 adding rules) without the TS evaluators catching up. The error message must tell the developer to regenerate or add the missing evaluator.
  </behavior>
  <action>
    1. Create `packages-ts/core/src/qc/rules.ts`:
       ```typescript
       /**
        * 5 alpha QC rule evaluators. Bit positions + rule IDs are
        * CONSUMED from the codegen table (NEVER hand-coded). Mirrors
        * Python `packages/core/src/tradewinds/qc.py:53-134`.
        */
       import {
         QC_ALPHA_RULES,
         QC_ALPHA_RULES_BY_ID,
         type QcAlphaRule,
       } from "../data/generated/qc-alpha-rules.js";

       export interface QCRule {
         readonly ruleId: string;
         readonly bitPosition: number;
         readonly description: string;
         readonly field: string;
         evaluate(rows: ReadonlyArray<Record<string, unknown>>): boolean[];
       }

       function getNum(row: Record<string, unknown>, col: string): number | null {
         const v = row[col];
         return typeof v === "number" && Number.isFinite(v) ? v : null;
       }

       export function evalTempOutOfRange(rows: ReadonlyArray<Record<string, unknown>>): boolean[] {
         return rows.map((r) => {
           const t = getNum(r, "temp_c");
           if (t === null) return false;
           return t < -89.0 || t > 57.0;
         });
       }

       export function evalDewpointExceedsTemp(rows: ReadonlyArray<Record<string, unknown>>): boolean[] {
         return rows.map((r) => {
           const t = getNum(r, "temp_c");
           const dp = getNum(r, "dew_point_c");
           if (t === null || dp === null) return false;
           return dp > t;
         });
       }

       export function evalWindSpeedNegative(rows: ReadonlyArray<Record<string, unknown>>): boolean[] {
         return rows.map((r) => {
           const v = getNum(r, "wind_speed_ms");
           if (v === null) return false;
           return v < 0;
         });
       }

       export function evalWindDirOutOfRange(rows: ReadonlyArray<Record<string, unknown>>): boolean[] {
         return rows.map((r) => {
           const v = getNum(r, "wind_dir_deg");
           if (v === null) return false;
           return v < 0 || v > 360;
         });
       }

       export function evalSlpOutOfRange(rows: ReadonlyArray<Record<string, unknown>>): boolean[] {
         return rows.map((r) => {
           const v = getNum(r, "slp_hpa");
           if (v === null) return false;
           return v < 870 || v > 1085;
         });
       }

       function makeRule(
         ruleId: string,
         evaluate: (rows: ReadonlyArray<Record<string, unknown>>) => boolean[],
       ): QCRule {
         const spec: QcAlphaRule | undefined = QC_ALPHA_RULES_BY_ID.get(ruleId);
         if (spec === undefined) {
           throw new Error(
             `QC rule '${ruleId}' missing from codegen QC_ALPHA_RULES_BY_ID; ` +
             `regenerate via 'pnpm codegen' or align rule IDs.`,
           );
         }
         return {
           ruleId: spec.rule_id,
           bitPosition: spec.bit_position,
           description: spec.description,
           field: spec.field,
           evaluate,
         };
       }

       /**
        * The 5 alpha rules, indexed by bit position (0..4). Order matches
        * codegen QC_ALPHA_RULES which is sorted by bit_position.
        */
       export const ALPHA_RULES: ReadonlyArray<QCRule> = [
         makeRule("temp_c.out_of_range", evalTempOutOfRange),
         makeRule("dew_point_c.exceeds_temp", evalDewpointExceedsTemp),
         makeRule("wind_speed_ms.negative", evalWindSpeedNegative),
         makeRule("wind_dir_deg.out_of_range", evalWindDirOutOfRange),
         makeRule("slp_hpa.out_of_range", evalSlpOutOfRange),
       ];

       // Module-load safety net: codegen table must match our evaluator count.
       if (QC_ALPHA_RULES.length !== ALPHA_RULES.length) {
         throw new Error(
           `QC codegen drift: QC_ALPHA_RULES has ${QC_ALPHA_RULES.length} entries ` +
           `but ALPHA_RULES has ${ALPHA_RULES.length}. ` +
           `Python Phase 3.5+ may have added rules; add the matching evaluator in qc/rules.ts.`,
         );
       }

       export { QC_ALPHA_RULES };
       ```

    2. Write `packages-ts/core/tests/qc/rules.test.ts`:
       - **Codegen consumption (critical regression guard):**
         - `ALPHA_RULES.length === 5`.
         - For each rule, `rule.bitPosition` matches the codegen `QC_ALPHA_RULES[i].bit_position`.
         - For each rule, `rule.ruleId` matches the codegen `QC_ALPHA_RULES[i].rule_id`.
       - **evalTempOutOfRange**:
         - `[{temp_c: 0}]` → `[false]`.
         - `[{temp_c: -90}]` → `[true]`.
         - `[{temp_c: 58}]` → `[true]`.
         - `[{temp_c: 57}, {temp_c: -89}]` → `[false, false]` (inclusive bounds).
         - `[{temp_c: null}]` → `[false]` (missing → no fire).
         - `[{}]` → `[false]` (missing column → no fire; Python parity).
         - `[{temp_c: 'invalid'}]` → `[false]` (non-numeric → no fire).
       - **evalDewpointExceedsTemp**:
         - `[{temp_c: 20, dew_point_c: 25}]` → `[true]`.
         - `[{temp_c: 20, dew_point_c: 15}]` → `[false]`.
         - `[{temp_c: 20, dew_point_c: 20}]` → `[false]` (equal → not "exceeds").
         - `[{temp_c: 20}]` → `[false]` (dp missing).
         - `[{dew_point_c: 25}]` → `[false]` (temp missing).
       - **evalWindSpeedNegative**:
         - `[{wind_speed_ms: -0.1}, {wind_speed_ms: 0}, {wind_speed_ms: 10}]` → `[true, false, false]`.
         - `[{}]` → `[false]`.
       - **evalWindDirOutOfRange**:
         - `[{wind_dir_deg: 0}, {wind_dir_deg: 360}, {wind_dir_deg: -1}, {wind_dir_deg: 361}, {wind_dir_deg: 180}]` → `[false, false, true, true, false]`.
         - `[{wind_dir_deg: null}]` → `[false]` (null skipped, matches Python `notna()` filter).
       - **evalSlpOutOfRange**:
         - `[{slp_hpa: 869}, {slp_hpa: 870}, {slp_hpa: 1085}, {slp_hpa: 1086}]` → `[true, false, false, true]`.
         - `[{}]` → `[false]`.
       - **Empty input** for each evaluator → empty array.
  </action>
  <acceptance_criteria>
    - `grep -n "from .\\./data/generated/qc-alpha-rules" packages-ts/core/src/qc/rules.ts` confirms codegen consumption.
    - `grep -nE "bitPosition\\s*=\\s*[0-9]|bit_position:\\s*[0-9]" packages-ts/core/src/qc/rules.ts` returns NO matches (no hand-coded bit positions).
    - `grep -n "QC_ALPHA_RULES_BY_ID.get" packages-ts/core/src/qc/rules.ts` confirms lookup-based wiring.
    - `grep -n "QC_ALPHA_RULES.length !== ALPHA_RULES.length" packages-ts/core/src/qc/rules.ts` confirms drift safety net.
    - `grep -n "temp_c.out_of_range\\|dew_point_c.exceeds_temp\\|wind_speed_ms.negative\\|wind_dir_deg.out_of_range\\|slp_hpa.out_of_range" packages-ts/core/src/qc/rules.ts` shows all 5 rule IDs.
    - `pnpm --filter @tradewinds/core test -- qc/rules` ≥ 30 cases all green.
  </acceptance_criteria>
</task>

<task type="auto" tdd="true">
  <name>Task 2: QCEngine.apply emitting obsQcStatus bitfield column</name>
  <files>packages-ts/core/src/qc/engine.ts, packages-ts/core/tests/qc/engine.test.ts</files>
  <read_first>
    - `packages/core/src/tradewinds/qc.py` lines 137-160 (the `QCEngine.apply` Python source — port the bit-OR-aggregation logic; note the `int64` use)
    - Wave 5 Task 1 output (rules.ts) for the ALPHA_RULES list.
    - JS bitwise operators: `|` operates on 32-bit signed integers; for our 5-bit field (max value 0b11111 = 31), this is safe. Document the 32-bit ceiling in JSDoc — the engine will accept up to 32 rules before bit-31 overflow.
  </read_first>
  <behavior>
    - `QCEngine` class with:
      - `readonly rules: ReadonlyArray<QCRule>` (defaults to ALPHA_RULES; constructor allows injection for testing OR future Phase 3.5+ rule additions).
      - `apply<Row extends Record<string, unknown>>(rows: ReadonlyArray<Row>): ReadonlyArray<Row & { obsQcStatus: number }>`.
    - `apply` semantics:
      - Empty input → returns empty array (NO throw).
      - For each rule, call `rule.evaluate(rows)` ONCE (not per-row — match Python's vectorized pattern). Result: a `boolean[]` parallel to rows.
      - For each row `i`, compute `obsQcStatus[i] = OR over rules of (rule.evaluate(rows)[i] ? (1 << rule.bitPosition) : 0)`.
      - Return new array of `{ ...rows[i], obsQcStatus: <number> }`.
    - Source rows NOT mutated; output rows are fresh objects.
    - Default obsQcStatus value when no rules fire = `0`.
    - When `rule.bitPosition >= 32` → throw an explicit error (defensive; we're far from this limit but document it).
  </behavior>
  <action>
    1. Create `packages-ts/core/src/qc/engine.ts`:
       ```typescript
       /**
        * QCEngine — apply alpha QC rules; emit obsQcStatus bitfield column.
        *
        * Mirrors Python `packages/core/src/tradewinds/qc.py:137-160`. The
        * bitfield is a 32-bit signed integer (JS `|` semantics); current
        * alpha rule set uses bits 0-4 of 32, leaving ample room. Phase 3.5+
        * additions to QC_ALPHA_RULES are picked up automatically as long
        * as a matching evaluator exists in qc/rules.ts.
        */
       import { ALPHA_RULES, type QCRule } from "./rules.js";

       export class QCEngine {
         readonly rules: ReadonlyArray<QCRule>;

         constructor(rules: ReadonlyArray<QCRule> = ALPHA_RULES) {
           // Defensive: bit-31 ceiling for JS 32-bit signed-integer OR.
           for (const rule of rules) {
             if (rule.bitPosition < 0 || rule.bitPosition >= 32) {
               throw new RangeError(
                 `QCEngine: rule '${rule.ruleId}' bitPosition=${rule.bitPosition} ` +
                 `out of 32-bit range; JS bitwise OR supports bits 0-31.`,
               );
             }
           }
           this.rules = rules;
         }

         /**
          * Apply all rules; return rows with obsQcStatus bitfield column.
          *
          * obsQcStatus[i] has bit N set iff this.rules[N].evaluate(rows)[i] === true.
          */
         apply<Row extends Record<string, unknown>>(
           rows: ReadonlyArray<Row>,
         ): ReadonlyArray<Row & { obsQcStatus: number }> {
           if (rows.length === 0) return [];

           // Step 1: evaluate each rule ONCE; collect parallel masks.
           const masks: boolean[][] = this.rules.map((rule) => rule.evaluate(rows));

           // Step 2: per-row OR-aggregation.
           const out: Array<Row & { obsQcStatus: number }> = [];
           for (let i = 0; i < rows.length; i++) {
             let status = 0;
             for (let r = 0; r < this.rules.length; r++) {
               const rule = this.rules[r]!;
               const fired = masks[r]?.[i] === true;
               if (fired) {
                 status |= 1 << rule.bitPosition;
               }
             }
             out.push({ ...rows[i]!, obsQcStatus: status });
           }
           return out;
         }
       }
       ```

    2. Write `packages-ts/core/tests/qc/engine.test.ts`:
       - **Empty input** → empty output (no throw).
       - **No rules fire**: `engine.apply([{temp_c: 20, dew_point_c: 15, wind_speed_ms: 5, wind_dir_deg: 90, slp_hpa: 1013}])` → `obsQcStatus === 0`.
       - **Single rule fires (bit 0 — temp_c.out_of_range)**: `[{temp_c: -100, dew_point_c: -110, wind_speed_ms: 0, wind_dir_deg: 0, slp_hpa: 1000}]` — dew_point_c < temp_c so rule 1 doesn't fire; only rule 0 fires → `obsQcStatus === 1` (binary `0b00001`).
         - Wait: dew_point_c=-110 < temp_c=-100, so dewpoint NOT exceeds temp. Confirms rule 1 doesn't fire. ✓
       - **Bit 1 — dew_point_c.exceeds_temp**: `[{temp_c: 10, dew_point_c: 15}]` → `obsQcStatus === 2` (binary `0b00010`).
       - **Bit 2 — wind_speed_ms.negative**: `[{wind_speed_ms: -1}]` → `obsQcStatus === 4` (binary `0b00100`).
       - **Bit 3 — wind_dir_deg.out_of_range**: `[{wind_dir_deg: 400}]` → `obsQcStatus === 8` (binary `0b01000`).
       - **Bit 4 — slp_hpa.out_of_range**: `[{slp_hpa: 500}]` → `obsQcStatus === 16` (binary `0b10000`).
       - **Multiple bits set**: `[{temp_c: -100, dew_point_c: 5, wind_speed_ms: -5}]` — temp_c < -89 (bit 0); dew_point > temp_c (bit 1); wind_speed negative (bit 2). `obsQcStatus === 7` (binary `0b00111`).
       - **All 5 bits set**: row triggering every rule → `obsQcStatus === 31` (binary `0b11111`).
       - **Source rows unchanged** (deep-equal on input).
       - **Original columns preserved** (output has all input keys + obsQcStatus).
       - **Custom rule injection**: `new QCEngine([])` (no rules) → every row gets `obsQcStatus: 0`.
       - **Defensive bit-31 ceiling**: construct a fake rule with `bitPosition: 32` → constructor throws RangeError.
  </action>
  <acceptance_criteria>
    - `grep -n "export class QCEngine" packages-ts/core/src/qc/engine.ts` confirms class export.
    - `grep -n "obsQcStatus" packages-ts/core/src/qc/engine.ts` confirms camelCase column name.
    - `grep -n "status |= 1 << rule.bitPosition" packages-ts/core/src/qc/engine.ts` confirms bit-OR aggregation referencing codegen-sourced bitPosition.
    - `grep -n "bitPosition >= 32" packages-ts/core/src/qc/engine.ts` confirms defensive bit-31 ceiling.
    - `pnpm --filter @tradewinds/core test -- qc/engine` ≥ 12 cases all green.
    - Test explicitly asserts `obsQcStatus === 31` for the all-rules-fire row (the 5-bit max).
  </acceptance_criteria>
</task>

<task type="auto" tdd="true">
  <name>Task 3: Codegen-parity test + qc barrel + subpath export + size gate</name>
  <files>packages-ts/core/src/qc/index.ts, packages-ts/core/package.json, packages-ts/core/tsup.config.ts, packages-ts/core/tests/qc/codegen-parity.test.ts</files>
  <read_first>
    - Wave 2 Task 3 (the transforms subpath + tsup + size-gate pattern — mirror it for qc)
    - `packages-ts/core/src/data/generated/qc-alpha-rules.ts` (full file — the codegen-parity test reads this directly)
    - `package.json` root size-limit block.
  </read_first>
  <behavior>
    - Create `src/qc/index.ts` barrel exporting QCEngine + QCRule + ALPHA_RULES + QC_ALPHA_RULES.
    - Add `"./qc"` subpath to `packages-ts/core/package.json` exports.
    - Add tsup entry: `{ entry: { index: 'src/qc/index.ts' }, outDir: 'dist/qc', ... }`.
    - **Codegen-parity test** is the regression guard: read `QC_ALPHA_RULES` from the generated file, read `ALPHA_RULES` from rules.ts, assert their `(ruleId, bitPosition)` tuples match exactly. If a future codegen run re-orders the rules or shifts a bit position, this test fires loud.
    - Size gate: after Wave 5 builds, `pnpm run size` confirms `@tradewinds/core` ≤ 25 KB (qc lives at subpath; root unchanged).
  </behavior>
  <action>
    1. Create `packages-ts/core/src/qc/index.ts`:
       ```typescript
       // Barrel for @tradewinds/core/qc — TS-W4 Plan 05.
       //
       // Public API: QCEngine, QCRule, ALPHA_RULES, QC_ALPHA_RULES.
       // Bit positions + rule IDs come from the codegen-shipped
       // QC_ALPHA_RULES table at src/data/generated/qc-alpha-rules.ts.

       export { QCEngine } from "./engine.js";
       export {
         ALPHA_RULES,
         QC_ALPHA_RULES,
         evalDewpointExceedsTemp,
         evalSlpOutOfRange,
         evalTempOutOfRange,
         evalWindDirOutOfRange,
         evalWindSpeedNegative,
         type QCRule,
       } from "./rules.js";
       ```

    2. Update `packages-ts/core/package.json` exports — add after the `./transforms` entry:
       ```json
       "./qc": {
         "types": "./dist/qc/index.d.ts",
         "import": "./dist/qc/index.mjs",
         "require": "./dist/qc/index.cjs"
       }
       ```

    3. Update `packages-ts/core/tsup.config.ts` — add a new entry block after the transforms entry:
       ```typescript
       {
         // TS-W4 Plan 05 — QC engine + 5 alpha rules.
         // Bit positions sourced from data/generated/qc-alpha-rules.ts.
         entry: { index: "src/qc/index.ts" },
         format: ["esm", "cjs"],
         dts: true,
         sourcemap: true,
         clean: false,
         target: "es2022",
         outDir: "dist/qc",
         outExtension({ format }) {
           if (format === "esm") return { js: ".mjs" };
           return { js: ".cjs" };
         },
       },
       ```

    4. Write `packages-ts/core/tests/qc/codegen-parity.test.ts`:
       ```typescript
       import { describe, expect, it } from "vitest";
       import { ALPHA_RULES, QC_ALPHA_RULES } from "../../src/qc/index.js";
       import { QC_ALPHA_RULES_BY_ID } from "../../src/data/generated/qc-alpha-rules.js";

       describe("@tradewinds/core/qc — codegen-parity guard", () => {
         it("ALPHA_RULES length === QC_ALPHA_RULES length (5)", () => {
           expect(ALPHA_RULES.length).toBe(5);
           expect(QC_ALPHA_RULES.length).toBe(5);
         });

         it("ALPHA_RULES[i].ruleId matches codegen QC_ALPHA_RULES[i].rule_id", () => {
           for (let i = 0; i < ALPHA_RULES.length; i++) {
             expect(ALPHA_RULES[i]!.ruleId).toBe(QC_ALPHA_RULES[i]!.rule_id);
           }
         });

         it("ALPHA_RULES[i].bitPosition matches codegen QC_ALPHA_RULES[i].bit_position", () => {
           for (let i = 0; i < ALPHA_RULES.length; i++) {
             expect(ALPHA_RULES[i]!.bitPosition).toBe(QC_ALPHA_RULES[i]!.bit_position);
           }
         });

         it("Canonical rule IDs match Python qc.py:103-134", () => {
           const ids = ALPHA_RULES.map((r) => r.ruleId);
           expect(ids).toEqual([
             "temp_c.out_of_range",
             "dew_point_c.exceeds_temp",
             "wind_speed_ms.negative",
             "wind_dir_deg.out_of_range",
             "slp_hpa.out_of_range",
           ]);
         });

         it("Canonical bit positions match Python qc.py:103-134", () => {
           const positions = ALPHA_RULES.map((r) => r.bitPosition);
           expect(positions).toEqual([0, 1, 2, 3, 4]);
         });

         it("QC_ALPHA_RULES_BY_ID lookup returns codegen entry", () => {
           expect(QC_ALPHA_RULES_BY_ID.get("temp_c.out_of_range")?.bit_position).toBe(0);
           expect(QC_ALPHA_RULES_BY_ID.get("slp_hpa.out_of_range")?.bit_position).toBe(4);
         });
       });
       ```

    5. Run `pnpm --filter @tradewinds/core run build && pnpm run size`. Assert `@tradewinds/core` ≤ 25 KB unchanged.
  </action>
  <acceptance_criteria>
    - `grep -n '"./qc"' packages-ts/core/package.json` confirms subpath export.
    - `grep -n "src/qc/index.ts" packages-ts/core/tsup.config.ts` confirms tsup entry.
    - `pnpm --filter @tradewinds/core run build` emits `dist/qc/{index.mjs,index.cjs,index.d.ts}`.
    - `pnpm --filter @tradewinds/core test -- qc/codegen-parity` 6 cases green; rule IDs + bit positions verified against codegen byte-for-byte.
    - `pnpm --filter @tradewinds/core test -- qc` runs all 3 qc test files (rules, engine, codegen-parity); all green.
    - `pnpm --filter @tradewinds/core run typecheck` clean.
    - `pnpm run size` reports `@tradewinds/core` ≤ 25 KB.
    - From a downstream consumer: `import { QCEngine, ALPHA_RULES } from "@tradewinds/core/qc"` resolves.
  </acceptance_criteria>
</task>

</tasks>

<verification>
1. `pnpm --filter @tradewinds/core test -- qc` runs all 3 qc test files (rules, engine, codegen-parity); ≥ 48 cases all green.
2. `pnpm --filter @tradewinds/core run typecheck` clean.
3. `pnpm --filter @tradewinds/core run build` emits `dist/qc/{index.mjs,index.cjs,index.d.ts}`.
4. `pnpm -r run typecheck` clean across the workspace.
5. `pnpm run size` reports `@tradewinds/core` ≤ 25 KB (qc lives at subpath; root unchanged).
6. The codegen-parity test PASSES → rule IDs + bit positions match codegen byte-for-byte. This is the regression guard against future codegen drift.
7. `obsQcStatus === 31` test passes when a row triggers all 5 alpha rules (proves 5-bit aggregation works correctly).
</verification>

<success_criteria>
- TS-QC-01 fully met — QCEngine + 5 alpha rules ported; rule IDs + bit positions sourced from codegen QC_ALPHA_RULES (NOT hand-coded); obsQcStatus 32-bit bitfield column added per row.
- Codegen-parity guard test in place — future drift caught loud.
- Bundle gate holds: `@tradewinds/core` ≤ 25 KB (qc at subpath).
- The 5 alpha rule IDs + bit positions match Python `qc.py:103-134` exactly: temp_c.out_of_range=0, dew_point_c.exceeds_temp=1, wind_speed_ms.negative=2, wind_dir_deg.out_of_range=3, slp_hpa.out_of_range=4.
- 32-bit JS bitwise-OR ceiling documented; defensive check throws if a future rule's bitPosition ≥ 32.
</success_criteria>

<review_discipline>
TypeScript-only changes under `packages-ts/core/**`. Per `.planning/REVIEW-DISCIPLINE.md`:

- **Reviewers**: codex `high` + **TypeScript Architect** (parallel).
- **Severity gate**: CRITICAL or HIGH only.
- **Loop**: fix on branch, re-dispatch, cap at 3.
- **Rubric calibration**:
  - CRITICAL if `qc/rules.ts` hand-codes any bit position (e.g. `bitPosition: 0` literal) instead of consuming from QC_ALPHA_RULES_BY_ID (the explicit TS-W4 critical-rule #4). Silent codegen drift → wrong bits set in stored QC parquets → corrupt sidecar.
  - CRITICAL if rule IDs diverge from Python qc.py:103-134 (e.g. `temp.out_of_range` instead of `temp_c.out_of_range`). Cross-language wire format break.
  - CRITICAL if obsQcStatus aggregation OR-s a rule's bit when the rule does NOT fire (off-by-one in mask application) — silent false-positive flagging that contaminates every model trained on flagged-out data.
  - CRITICAL if `dewpoint > temp` rule uses `>=` instead of `>` (Python uses `df["dew_point_c"] > df["temp_c"]` at qc.py:68; equality is physically possible at saturation).
  - HIGH if missing-column case throws instead of returning all-false (Python returns `pd.Series([False]*len(df))` at qc.py:57-58; throw would break QC-after-research pipelines for stations missing some columns).
  - HIGH if QCEngine mutates input rows (row-immutability invariant).
  - HIGH if codegen-parity test is absent or only checks length (the regression guard's whole purpose is per-rule ID + bit-position verification).
  - HIGH if `obsQcStatus` column name uses snake_case (Python parity is `obs_qc_status`; TS-side camelCase is the deliberate TS-idiom departure documented in the Parity-Ticket note; HIGH if neither shape is consistent).
  - HIGH if QCEngine ships in the root `@tradewinds/core` barrel instead of the subpath (would push the main bundle over 25 KB).
</review_discipline>

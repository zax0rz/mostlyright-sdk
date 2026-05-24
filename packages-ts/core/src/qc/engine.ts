// TS-W4 Plan 05 Task 2 — QCEngine: apply alpha rules; emit obsQcStatus bitfield.
//
// Mirrors Python `packages/core/src/tradewinds/qc.py:137-160`. The bitfield is a
// 32-bit signed integer (JS `|` semantics); the alpha rule set uses bits 0-4
// of 32, leaving ample headroom. Phase 3.5+ additions to QC_ALPHA_RULES are
// picked up automatically by qc/rules.ts (which registers the matching
// evaluator) and flow through this engine unchanged.

import { ALPHA_RULES, type QCRule } from "./rules.js";

/**
 * QCEngine — orchestrates per-rule evaluation and OR-aggregates each rule's
 * bit into the per-row `obsQcStatus` bitfield column.
 *
 * Defaults to ALPHA_RULES; custom rule sets can be injected via the
 * constructor (used for testing, future Phase 3.5+ rule additions, or
 * downstream-defined custom rules).
 *
 * The `obsQcStatus` column name is camelCase (TS-side convention) — Python
 * uses snake_case `obs_qc_status`. The wire-format conversion happens at the
 * JSON serializer boundary (TS-W3 jsonDumps handles snake_case for export).
 *
 * JS bitwise OR (`|`) operates on 32-bit signed integers, so this engine
 * accepts rules with bitPosition in [0, 31]. A defensive RangeError fires at
 * construction if any rule violates that ceiling.
 */
export class QCEngine {
  readonly rules: ReadonlyArray<QCRule>;

  constructor(rules: ReadonlyArray<QCRule> = ALPHA_RULES) {
    // Defensive: bit-31 ceiling for JS 32-bit signed-integer OR.
    for (const rule of rules) {
      if (rule.bitPosition < 0 || rule.bitPosition >= 32) {
        throw new RangeError(
          `QCEngine: rule '${rule.ruleId}' bitPosition=${rule.bitPosition} out of 32-bit range; JS bitwise OR supports bits 0-31.`,
        );
      }
    }
    this.rules = rules;
  }

  /**
   * Apply all registered rules to `rows`; return new rows with an
   * `obsQcStatus` bitfield column appended.
   *
   * `obsQcStatus[i]` has bit N set iff `this.rules[N].evaluate(rows)[i] === true`.
   * Source rows are NOT mutated; output rows are fresh objects.
   * Empty input → empty output (no throw).
   *
   * Each rule's `evaluate(rows)` is called ONCE (vectorized contract) — the
   * rule sees the full row array and returns a parallel `boolean[]`.
   */
  apply<Row extends Record<string, unknown>>(
    rows: ReadonlyArray<Row>,
  ): ReadonlyArray<Row & { obsQcStatus: number }> {
    if (rows.length === 0) return [];

    // Step 1: evaluate each rule ONCE; collect parallel boolean masks.
    const masks: boolean[][] = this.rules.map((rule) => rule.evaluate(rows));

    // Step 2: per-row OR-aggregation.
    const out: Array<Row & { obsQcStatus: number }> = [];
    for (let i = 0; i < rows.length; i++) {
      const row = rows[i];
      if (row === undefined) continue;
      let status = 0;
      for (let r = 0; r < this.rules.length; r++) {
        const rule = this.rules[r];
        if (rule === undefined) continue;
        const fired = masks[r]?.[i] === true;
        if (fired) {
          status |= 1 << rule.bitPosition;
        }
      }
      out.push({ ...row, obsQcStatus: status });
    }
    return out;
  }
}

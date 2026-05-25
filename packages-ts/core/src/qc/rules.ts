// TS-W4 Plan 05 Task 1 — 5 alpha QC rule evaluators.
//
// Bit positions + rule IDs are CONSUMED from the codegen table at
// src/data/generated/qc-alpha-rules.ts (NEVER hand-coded). Mirrors Python
// `packages/core/src/mostlyright/qc.py:53-134`.
//
// If a future codegen run adds a new rule, this file MUST be updated to
// register a matching evaluator — the module-load drift guard fires loud
// otherwise (see end of file).

import {
  QC_ALPHA_RULES,
  QC_ALPHA_RULES_BY_ID,
  type QcAlphaRule,
} from "../data/generated/qc-alpha-rules.js";

/**
 * A QC rule: ruleId + bit position (both consumed from the codegen table)
 * plus a per-row evaluator. `evaluate(rows)` returns a `boolean[]` of length
 * === rows.length where `true` means the rule fired for that row.
 */
export interface QCRule {
  readonly ruleId: string;
  readonly bitPosition: number;
  readonly description: string;
  readonly field: string;
  evaluate(rows: ReadonlyArray<Record<string, unknown>>): boolean[];
}

/**
 * Safely read a numeric field from a row. Returns the number only if it's
 * finite (rejects null/undefined/NaN/Infinity/non-numeric). Null/missing/
 * non-finite → null, so the calling rule does NOT fire (Python
 * qc.py:57-58 + notna() parity).
 */
function getNum(row: Record<string, unknown>, col: string): number | null {
  const v = row[col];
  return typeof v === "number" && Number.isFinite(v) ? v : null;
}

/** Bit 0 — Temperature outside [-89C, 57C] (world-record bounds). */
export function evalTempOutOfRange(rows: ReadonlyArray<Record<string, unknown>>): boolean[] {
  return rows.map((r) => {
    const t = getNum(r, "temp_c");
    if (t === null) return false;
    return t < -89.0 || t > 57.0;
  });
}

/** Bit 1 — Dewpoint > temperature (physically impossible; strict `>`). */
export function evalDewpointExceedsTemp(rows: ReadonlyArray<Record<string, unknown>>): boolean[] {
  return rows.map((r) => {
    const t = getNum(r, "temp_c");
    const dp = getNum(r, "dew_point_c");
    if (t === null || dp === null) return false;
    return dp > t;
  });
}

/** Bit 2 — Wind speed negative. */
export function evalWindSpeedNegative(rows: ReadonlyArray<Record<string, unknown>>): boolean[] {
  return rows.map((r) => {
    const v = getNum(r, "wind_speed_ms");
    if (v === null) return false;
    return v < 0;
  });
}

/** Bit 3 — Wind direction outside [0, 360] (inclusive). */
export function evalWindDirOutOfRange(rows: ReadonlyArray<Record<string, unknown>>): boolean[] {
  return rows.map((r) => {
    const v = getNum(r, "wind_dir_deg");
    if (v === null) return false;
    return v < 0 || v > 360;
  });
}

/** Bit 4 — Sea-level pressure outside [870, 1085] mb. */
export function evalSlpOutOfRange(rows: ReadonlyArray<Record<string, unknown>>): boolean[] {
  return rows.map((r) => {
    const v = getNum(r, "slp_hpa");
    if (v === null) return false;
    return v < 870 || v > 1085;
  });
}

/**
 * Build a QCRule by looking up the codegen spec (ruleId, bitPosition,
 * description, field) and binding the per-row evaluator. Throws at module
 * load if the codegen table is missing the rule — protects against the
 * codegen contract drifting out from under the TS implementation.
 */
function makeRule(
  ruleId: string,
  evaluate: (rows: ReadonlyArray<Record<string, unknown>>) => boolean[],
): QCRule {
  const spec: QcAlphaRule | undefined = QC_ALPHA_RULES_BY_ID.get(ruleId);
  if (spec === undefined) {
    throw new Error(
      `QC rule '${ruleId}' missing from codegen QC_ALPHA_RULES_BY_ID; regenerate via 'pnpm codegen' or align rule IDs.`,
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
 * The 5 alpha rules, indexed by bit position (0..4). Order matches the
 * codegen QC_ALPHA_RULES (which is sorted by bit_position). Phase 3.5+
 * additions in the codegen table MUST land a matching evaluator here or
 * the drift guard below throws at module load.
 */
export const ALPHA_RULES: ReadonlyArray<QCRule> = [
  makeRule("temp_c.out_of_range", evalTempOutOfRange),
  makeRule("dew_point_c.exceeds_temp", evalDewpointExceedsTemp),
  makeRule("wind_speed_ms.negative", evalWindSpeedNegative),
  makeRule("wind_dir_deg.out_of_range", evalWindDirOutOfRange),
  makeRule("slp_hpa.out_of_range", evalSlpOutOfRange),
];

// Module-load safety net: codegen table must match our evaluator count.
// If Python Phase 3.5+ adds a new rule (e.g. a 6th entry to
// schemas/qc-alpha-rules.json → regenerated QC_ALPHA_RULES), the
// developer must add the matching evaluator here. The drift guard fires
// loud rather than silently dropping rules.
if (QC_ALPHA_RULES.length !== ALPHA_RULES.length) {
  throw new Error(
    `QC codegen drift: QC_ALPHA_RULES has ${QC_ALPHA_RULES.length} entries but ALPHA_RULES has ${ALPHA_RULES.length}. Python Phase 3.5+ may have added rules; add the matching evaluator in qc/rules.ts.`,
  );
}

export { QC_ALPHA_RULES };

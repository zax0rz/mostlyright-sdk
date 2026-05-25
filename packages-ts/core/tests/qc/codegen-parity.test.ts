// TS-W4 Plan 05 Task 3 — codegen-parity regression guard.
//
// The non-negotiable invariant: every ALPHA_RULES[i] entry's runtime
// (ruleId, bitPosition) MUST exactly match QC_ALPHA_RULES[i] from the
// codegen-shipped table at src/data/generated/qc-alpha-rules.ts. If a
// future codegen run re-orders rules, renames a rule, or shifts a bit
// position, this test fires LOUD before any downstream sidecar parquet
// gets corrupted.
//
// Also asserts canonical rule IDs + bit positions match Python
// qc.py:103-134 byte-for-byte (cross-language wire-format integrity).

import { describe, expect, it } from "vitest";

import { QC_ALPHA_RULES, QC_ALPHA_RULES_BY_ID } from "../../src/data/generated/qc-alpha-rules.js";
import { ALPHA_RULES } from "../../src/qc/index.js";

describe("@mostlyright/core/qc — codegen-parity guard", () => {
  it("ALPHA_RULES length === QC_ALPHA_RULES length (5)", () => {
    expect(ALPHA_RULES.length).toBe(5);
    expect(QC_ALPHA_RULES.length).toBe(5);
  });

  it("ALPHA_RULES[i].ruleId matches codegen QC_ALPHA_RULES[i].rule_id", () => {
    for (let i = 0; i < ALPHA_RULES.length; i++) {
      expect(ALPHA_RULES[i]?.ruleId).toBe(QC_ALPHA_RULES[i]?.rule_id);
    }
  });

  it("ALPHA_RULES[i].bitPosition matches codegen QC_ALPHA_RULES[i].bit_position", () => {
    for (let i = 0; i < ALPHA_RULES.length; i++) {
      expect(ALPHA_RULES[i]?.bitPosition).toBe(QC_ALPHA_RULES[i]?.bit_position);
    }
  });

  it("ALPHA_RULES[i].field matches codegen QC_ALPHA_RULES[i].field", () => {
    for (let i = 0; i < ALPHA_RULES.length; i++) {
      expect(ALPHA_RULES[i]?.field).toBe(QC_ALPHA_RULES[i]?.field);
    }
  });

  it("ALPHA_RULES[i].description matches codegen QC_ALPHA_RULES[i].description", () => {
    for (let i = 0; i < ALPHA_RULES.length; i++) {
      expect(ALPHA_RULES[i]?.description).toBe(QC_ALPHA_RULES[i]?.description);
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
    expect(QC_ALPHA_RULES_BY_ID.get("dew_point_c.exceeds_temp")?.bit_position).toBe(1);
    expect(QC_ALPHA_RULES_BY_ID.get("wind_speed_ms.negative")?.bit_position).toBe(2);
    expect(QC_ALPHA_RULES_BY_ID.get("wind_dir_deg.out_of_range")?.bit_position).toBe(3);
    expect(QC_ALPHA_RULES_BY_ID.get("slp_hpa.out_of_range")?.bit_position).toBe(4);
  });

  it("ALPHA_RULES + QC_ALPHA_RULES tuple equality (full byte-for-byte parity)", () => {
    const alphaTuples = ALPHA_RULES.map((r) => [r.ruleId, r.bitPosition] as const);
    const codegenTuples = QC_ALPHA_RULES.map((r) => [r.rule_id, r.bit_position] as const);
    expect(alphaTuples).toEqual(codegenTuples);
  });
});

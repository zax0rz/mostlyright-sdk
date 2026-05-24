// TS-W4 Plan 05 Task 1 — 5 alpha rule evaluators wired to codegen.
//
// Tests assert per-rule behaviour (out-of-range / null-skip / missing-column
// no-fire semantics) AND the critical codegen-consumption regression guards:
// rule IDs and bit positions for every entry of ALPHA_RULES come from
// QC_ALPHA_RULES (the codegen table at src/data/generated/qc-alpha-rules.ts)
// and are NOT hand-coded anywhere in qc/rules.ts.

import { describe, expect, it } from "vitest";

import { QC_ALPHA_RULES } from "../../src/data/generated/qc-alpha-rules.js";
import {
  ALPHA_RULES,
  evalDewpointExceedsTemp,
  evalSlpOutOfRange,
  evalTempOutOfRange,
  evalWindDirOutOfRange,
  evalWindSpeedNegative,
} from "../../src/qc/rules.js";

describe("ALPHA_RULES — codegen consumption regression guard", () => {
  it("contains exactly 5 rules", () => {
    expect(ALPHA_RULES.length).toBe(5);
  });

  it("each rule.bitPosition matches codegen QC_ALPHA_RULES[i].bit_position", () => {
    for (let i = 0; i < ALPHA_RULES.length; i++) {
      expect(ALPHA_RULES[i]?.bitPosition).toBe(QC_ALPHA_RULES[i]?.bit_position);
    }
  });

  it("each rule.ruleId matches codegen QC_ALPHA_RULES[i].rule_id", () => {
    for (let i = 0; i < ALPHA_RULES.length; i++) {
      expect(ALPHA_RULES[i]?.ruleId).toBe(QC_ALPHA_RULES[i]?.rule_id);
    }
  });

  it("each rule.field matches codegen QC_ALPHA_RULES[i].field", () => {
    for (let i = 0; i < ALPHA_RULES.length; i++) {
      expect(ALPHA_RULES[i]?.field).toBe(QC_ALPHA_RULES[i]?.field);
    }
  });

  it("each rule.description matches codegen QC_ALPHA_RULES[i].description", () => {
    for (let i = 0; i < ALPHA_RULES.length; i++) {
      expect(ALPHA_RULES[i]?.description).toBe(QC_ALPHA_RULES[i]?.description);
    }
  });

  it("exposes evaluate as a function on every rule", () => {
    for (const rule of ALPHA_RULES) {
      expect(typeof rule.evaluate).toBe("function");
    }
  });
});

describe("evalTempOutOfRange", () => {
  it("in-range returns false", () => {
    expect(evalTempOutOfRange([{ temp_c: 0 }])).toEqual([false]);
  });

  it("below -89 fires", () => {
    expect(evalTempOutOfRange([{ temp_c: -90 }])).toEqual([true]);
  });

  it("above 57 fires", () => {
    expect(evalTempOutOfRange([{ temp_c: 58 }])).toEqual([true]);
  });

  it("inclusive bounds: 57 and -89 do not fire", () => {
    expect(evalTempOutOfRange([{ temp_c: 57 }, { temp_c: -89 }])).toEqual([false, false]);
  });

  it("null temp_c does not fire", () => {
    expect(evalTempOutOfRange([{ temp_c: null }])).toEqual([false]);
  });

  it("missing column does not fire (Python qc.py:57-58 parity)", () => {
    expect(evalTempOutOfRange([{}])).toEqual([false]);
  });

  it("non-numeric temp_c does not fire", () => {
    expect(evalTempOutOfRange([{ temp_c: "invalid" }])).toEqual([false]);
  });

  it("NaN temp_c does not fire", () => {
    expect(evalTempOutOfRange([{ temp_c: Number.NaN }])).toEqual([false]);
  });

  it("empty input returns empty array", () => {
    expect(evalTempOutOfRange([])).toEqual([]);
  });
});

describe("evalDewpointExceedsTemp", () => {
  it("dew_point > temp fires", () => {
    expect(evalDewpointExceedsTemp([{ temp_c: 20, dew_point_c: 25 }])).toEqual([true]);
  });

  it("dew_point < temp does not fire", () => {
    expect(evalDewpointExceedsTemp([{ temp_c: 20, dew_point_c: 15 }])).toEqual([false]);
  });

  it("dew_point == temp does not fire (strict >, not >=)", () => {
    expect(evalDewpointExceedsTemp([{ temp_c: 20, dew_point_c: 20 }])).toEqual([false]);
  });

  it("dew_point missing does not fire", () => {
    expect(evalDewpointExceedsTemp([{ temp_c: 20 }])).toEqual([false]);
  });

  it("temp missing does not fire", () => {
    expect(evalDewpointExceedsTemp([{ dew_point_c: 25 }])).toEqual([false]);
  });

  it("both missing does not fire", () => {
    expect(evalDewpointExceedsTemp([{}])).toEqual([false]);
  });

  it("empty input returns empty array", () => {
    expect(evalDewpointExceedsTemp([])).toEqual([]);
  });
});

describe("evalWindSpeedNegative", () => {
  it("negative speeds fire; zero/positive do not", () => {
    expect(
      evalWindSpeedNegative([{ wind_speed_ms: -0.1 }, { wind_speed_ms: 0 }, { wind_speed_ms: 10 }]),
    ).toEqual([true, false, false]);
  });

  it("missing column does not fire", () => {
    expect(evalWindSpeedNegative([{}])).toEqual([false]);
  });

  it("null wind_speed_ms does not fire", () => {
    expect(evalWindSpeedNegative([{ wind_speed_ms: null }])).toEqual([false]);
  });

  it("empty input returns empty array", () => {
    expect(evalWindSpeedNegative([])).toEqual([]);
  });
});

describe("evalWindDirOutOfRange", () => {
  it("0 and 360 are inclusive (do not fire); -1 and 361 fire", () => {
    expect(
      evalWindDirOutOfRange([
        { wind_dir_deg: 0 },
        { wind_dir_deg: 360 },
        { wind_dir_deg: -1 },
        { wind_dir_deg: 361 },
        { wind_dir_deg: 180 },
      ]),
    ).toEqual([false, false, true, true, false]);
  });

  it("null wind_dir_deg does not fire (Python notna() parity)", () => {
    expect(evalWindDirOutOfRange([{ wind_dir_deg: null }])).toEqual([false]);
  });

  it("missing column does not fire", () => {
    expect(evalWindDirOutOfRange([{}])).toEqual([false]);
  });

  it("empty input returns empty array", () => {
    expect(evalWindDirOutOfRange([])).toEqual([]);
  });
});

describe("evalSlpOutOfRange", () => {
  it("inclusive bounds [870, 1085]; out-of-range fires", () => {
    expect(
      evalSlpOutOfRange([{ slp_hpa: 869 }, { slp_hpa: 870 }, { slp_hpa: 1085 }, { slp_hpa: 1086 }]),
    ).toEqual([true, false, false, true]);
  });

  it("null slp_hpa does not fire (Python notna() parity)", () => {
    expect(evalSlpOutOfRange([{ slp_hpa: null }])).toEqual([false]);
  });

  it("missing column does not fire", () => {
    expect(evalSlpOutOfRange([{}])).toEqual([false]);
  });

  it("empty input returns empty array", () => {
    expect(evalSlpOutOfRange([])).toEqual([]);
  });
});

describe("ALPHA_RULES canonical ordering (mirrors Python qc.py:103-134)", () => {
  it("rule IDs in order: temp_c, dew_point_c, wind_speed_ms, wind_dir_deg, slp_hpa", () => {
    expect(ALPHA_RULES.map((r) => r.ruleId)).toEqual([
      "temp_c.out_of_range",
      "dew_point_c.exceeds_temp",
      "wind_speed_ms.negative",
      "wind_dir_deg.out_of_range",
      "slp_hpa.out_of_range",
    ]);
  });

  it("bit positions in order: 0, 1, 2, 3, 4", () => {
    expect(ALPHA_RULES.map((r) => r.bitPosition)).toEqual([0, 1, 2, 3, 4]);
  });
});

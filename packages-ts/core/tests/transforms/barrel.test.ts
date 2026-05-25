// TS-W4 Plan 02 Task 3 — barrel re-export tests.
//
// Asserts the @mostlyrightmd/core/transforms barrel surfaces lag, diff, diff2,
// rolling, ROLLING_FNS, and the RollingFn type. Column-naming convention
// `{col}_{op}_{param}` is verified end-to-end through the barrel.
//
// Extended in TS-W4 Plan 03 to also assert calendarFeatures is wired
// through the same barrel (Wave 3 appends to the transforms subpath).

import { describe, expect, it } from "vitest";

import {
  ROLLING_FNS,
  type RollingFn,
  calendarFeatures,
  diff,
  diff2,
  lag,
  rolling,
} from "../../src/transforms/index.js";

describe("@mostlyrightmd/core/transforms barrel", () => {
  it("re-exports five transform functions (lag/diff/diff2/rolling/calendarFeatures)", () => {
    expect(typeof lag).toBe("function");
    expect(typeof diff).toBe("function");
    expect(typeof diff2).toBe("function");
    expect(typeof rolling).toBe("function");
    expect(typeof calendarFeatures).toBe("function");
  });

  it("ROLLING_FNS contains exactly 6 reducers in canonical order", () => {
    expect(ROLLING_FNS).toEqual(["mean", "median", "min", "max", "std", "count"]);
  });

  it("RollingFn type is assignable from each ROLLING_FNS entry", () => {
    // Compile-time check: every ROLLING_FNS member must be assignable to RollingFn.
    const fns: RollingFn[] = [...ROLLING_FNS];
    expect(fns.length).toBe(6);
  });

  it("output column naming matches {col}_{op}_{param} convention", () => {
    const rows = [{ temp_c: 10 }, { temp_c: 12 }, { temp_c: 14 }];

    const lagged = lag(rows, "temp_c", 1);
    const laggedRow = lagged[1];
    expect(laggedRow).toBeDefined();
    expect(Object.hasOwn(laggedRow as object, "temp_c_lag_1")).toBe(true);

    const diffed = diff(rows, "temp_c", 1);
    const diffedRow = diffed[1];
    expect(diffedRow).toBeDefined();
    expect(Object.hasOwn(diffedRow as object, "temp_c_diff_1")).toBe(true);

    const diffed2 = diff2(rows, "temp_c");
    const diffed2Row = diffed2[2];
    expect(diffed2Row).toBeDefined();
    expect(Object.hasOwn(diffed2Row as object, "temp_c_diff2")).toBe(true);

    const rolled = rolling(rows, "temp_c", 2, "mean");
    const rolledRow = rolled[1];
    expect(rolledRow).toBeDefined();
    expect(Object.hasOwn(rolledRow as object, "temp_c_rolling_2_mean")).toBe(true);
  });
});

// TS-W4 Plan 03 Task 2 — calendarFeatures barrel re-export test.
//
// Asserts the @mostlyright/core/transforms barrel surfaces calendarFeatures
// alongside Wave 2's lag/diff/diff2/rolling. End-to-end smoke: import the
// function from the barrel path consumers use, then verify all 8 derived
// columns appear on the output row.

import { describe, expect, it } from "vitest";

import { calendarFeatures } from "../../src/transforms/index.js";

describe("@mostlyright/core/transforms — calendarFeatures barrel re-export", () => {
  it("calendarFeatures is exported from the barrel", () => {
    expect(typeof calendarFeatures).toBe("function");
  });

  it("calendarFeatures returns the 8 expected derived columns", () => {
    const rows = [{ d: "2024-06-15T00:00:00Z" }];
    const out = calendarFeatures(rows, "d");
    const r = out[0];
    expect(r).toBeDefined();
    if (r === undefined) {
      throw new Error("unreachable: r checked above");
    }
    expect(Object.hasOwn(r, "month_sin")).toBe(true);
    expect(Object.hasOwn(r, "month_cos")).toBe(true);
    expect(Object.hasOwn(r, "dow_sin")).toBe(true);
    expect(Object.hasOwn(r, "dow_cos")).toBe(true);
    expect(Object.hasOwn(r, "hour_sin")).toBe(true);
    expect(Object.hasOwn(r, "hour_cos")).toBe(true);
    expect(Object.hasOwn(r, "day_of_year_sin")).toBe(true);
    expect(Object.hasOwn(r, "day_of_year_cos")).toBe(true);
  });
});

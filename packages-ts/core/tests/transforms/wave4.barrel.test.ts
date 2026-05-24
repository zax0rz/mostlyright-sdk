// TS-W4 Plan 04 Task 3 — Wave 4 barrel re-export tests.
//
// Asserts the @tradewinds/core/transforms barrel surfaces Wave 4's
// spread / windChill / heatIndex / clipOutliers / PHYSICS_BOUNDS alongside
// Wave 2's lag/diff/diff2/rolling and Wave 3's calendarFeatures. End-to-end
// smoke: imports from the barrel path consumers use, then exercises each
// function once.

import { describe, expect, it } from "vitest";

import {
  type ClipOutliersOptions,
  PHYSICS_BOUNDS,
  clipOutliers,
  heatIndex,
  spread,
  windChill,
} from "../../src/transforms/index.js";

function num(v: number | null): number {
  if (v === null) throw new Error("expected number, got null");
  return v;
}

describe("@tradewinds/core/transforms — Wave 4 barrel exports", () => {
  it("spread / windChill / heatIndex / clipOutliers are exported", () => {
    expect(typeof spread).toBe("function");
    expect(typeof windChill).toBe("function");
    expect(typeof heatIndex).toBe("function");
    expect(typeof clipOutliers).toBe("function");
  });

  it("PHYSICS_BOUNDS exposed as a ReadonlyMap with the temp_c entry", () => {
    expect(PHYSICS_BOUNDS.get("temp_c")).toEqual([-89.0, 57.0]);
  });

  it("ClipOutliersOptions type compiles", () => {
    const opts: ClipOutliersOptions = { bounds: [0, 100] };
    const out = clipOutliers([{ x: 5 }], "x", opts);
    expect(out[0]?.x_clipped).toBe(5);
  });

  it("NWS reference: windChill(20, 15) ≈ 6 °F (within 1°F)", () => {
    const v = windChill(20, 15);
    expect(v).not.toBeNull();
    expect(Math.abs(num(v) - 6)).toBeLessThan(1);
  });

  it("NWS reference: heatIndex(90, 70) ≈ 106 °F (within 1°F)", () => {
    const v = heatIndex(90, 70);
    expect(v).not.toBeNull();
    expect(Math.abs(num(v) - 106)).toBeLessThan(1);
  });

  it("spread derived column is exactly `{colA}_minus_{colB}`", () => {
    const out = spread([{ a: 10, b: 7 }], "a", "b");
    expect(out[0]?.a_minus_b).toBe(3);
  });
});

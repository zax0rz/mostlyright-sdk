// TS-W4 Plan 04 Task 2 — clipOutliers tests (RED phase).
//
// Mirrors Python `tradewinds.preprocessing.clip_outliers` at packages/core/
// src/tradewinds/preprocessing.py:49-91. Decision tree:
//
//   1. opts.bounds set            → clip to explicit [lo, hi]
//   2. PHYSICS_BOUNDS.has(col)    → clip to physics defaults
//   3. else                       → sigma fallback (mu ± std*sigma)
//
// Phase 3.5 review-iter HIGH fixes:
//   - std <= 0 in sigma branch → throw RangeError (Python ValueError equivalent)
//   - sigma === 0 in sigma branch → pass values through UNCHANGED (NOT collapse
//     to mu, NOT NaN). The "all values identical" edge case.

import { describe, expect, it } from "vitest";

import { PHYSICS_BOUNDS, clipOutliers } from "../../src/transforms/clip.js";

describe("clipOutliers — explicit bounds", () => {
  it("clips numeric values to [lo, hi]", () => {
    const rows = [{ x: 5 }, { x: 50 }, { x: -10 }];
    const out = clipOutliers(rows, "x", { bounds: [0, 30] });
    expect(out.map((r) => r.x_clipped)).toEqual([5, 30, 0]);
  });

  it("derived column is `{col}_clipped`; source column preserved", () => {
    const rows = [{ x: 100 }];
    const out = clipOutliers(rows, "x", { bounds: [0, 50] });
    const r = out[0];
    expect(r).toBeDefined();
    expect(Object.hasOwn(r as object, "x_clipped")).toBe(true);
    expect((r as Record<string, unknown>).x).toBe(100);
    expect((r as Record<string, unknown>).x_clipped).toBe(50);
  });
});

describe("clipOutliers — PHYSICS_BOUNDS", () => {
  it("temp_c uses [-89, 57]", () => {
    const rows = [{ temp_c: -100 }, { temp_c: 0 }, { temp_c: 60 }];
    const out = clipOutliers(rows, "temp_c");
    expect(out.map((r) => r.temp_c_clipped)).toEqual([-89, 0, 57]);
  });

  it("wind_speed_ms uses [0, 100]", () => {
    const rows = [{ wind_speed_ms: -5 }, { wind_speed_ms: 50 }, { wind_speed_ms: 200 }];
    const out = clipOutliers(rows, "wind_speed_ms");
    expect(out.map((r) => r.wind_speed_ms_clipped)).toEqual([0, 50, 100]);
  });

  it("slp_hpa uses [870, 1085]", () => {
    const rows = [{ slp_hpa: 800 }, { slp_hpa: 1013 }, { slp_hpa: 1100 }];
    const out = clipOutliers(rows, "slp_hpa");
    expect(out.map((r) => r.slp_hpa_clipped)).toEqual([870, 1013, 1085]);
  });

  it("PHYSICS_BOUNDS has 11 canonical entries", () => {
    expect(PHYSICS_BOUNDS.size).toBe(11);
  });

  it("PHYSICS_BOUNDS.temp_c value is exactly [-89, 57]", () => {
    expect(PHYSICS_BOUNDS.get("temp_c")).toEqual([-89.0, 57.0]);
  });

  it("PHYSICS_BOUNDS.wind_dir_deg value is exactly [0, 360]", () => {
    expect(PHYSICS_BOUNDS.get("wind_dir_deg")).toEqual([0.0, 360.0]);
  });

  it("PHYSICS_BOUNDS.slp_hpa value is exactly [870, 1085]", () => {
    expect(PHYSICS_BOUNDS.get("slp_hpa")).toEqual([870.0, 1085.0]);
  });

  it("explicit bounds override PHYSICS_BOUNDS", () => {
    // temp_c has physics [-89, 57], but explicit bounds win.
    const rows = [{ temp_c: -100 }, { temp_c: 100 }];
    const out = clipOutliers(rows, "temp_c", { bounds: [-50, 50] });
    expect(out.map((r) => r.temp_c_clipped)).toEqual([-50, 50]);
  });
});

describe("clipOutliers — sigma fallback (default std=3)", () => {
  it("wide-distribution values stay unclipped under default std=3", () => {
    // mu ≈ 21.2, sigma ≈ 43.8, clamp [-110, 153] — all 5 values stay.
    const rows = [{ x: 0 }, { x: 1 }, { x: 2 }, { x: 3 }, { x: 100 }];
    const out = clipOutliers(rows, "x");
    expect(out.map((r) => r.x_clipped)).toEqual([0, 1, 2, 3, 100]);
  });

  it("tight std=0.5 forces a clip on the outlier", () => {
    // mu ≈ 21.2, sigma ≈ 43.8 — clamp [-0.7, 43.1] (approx).
    // Outlier at 100 gets clipped to ~43.1; the 0 stays (within [-0.7, 43.1]).
    const rows = [{ x: 0 }, { x: 1 }, { x: 2 }, { x: 3 }, { x: 100 }];
    const out = clipOutliers(rows, "x", { std: 0.5 });
    const clipped = out.map((r) => r.x_clipped);
    // The first four (0..3) are within range, but 100 must be clipped down.
    expect(clipped[4]).not.toBe(100);
    if (typeof clipped[4] !== "number") throw new Error("clipped[4] should be number");
    expect(clipped[4]).toBeLessThan(100);
  });
});

describe("clipOutliers — Phase 3.5 review-iter fixes", () => {
  it("std=0 in sigma fallback → throws RangeError", () => {
    expect(() => clipOutliers([{ x: 1 }, { x: 2 }], "x", { std: 0 })).toThrow(RangeError);
    expect(() => clipOutliers([{ x: 1 }, { x: 2 }], "x", { std: 0 })).toThrow(/std must be > 0/);
  });

  it("std=-1 in sigma fallback → throws RangeError", () => {
    expect(() => clipOutliers([{ x: 1 }, { x: 2 }], "x", { std: -1 })).toThrow(RangeError);
  });

  it("std=NaN in sigma fallback → throws RangeError", () => {
    expect(() => clipOutliers([{ x: 1 }, { x: 2 }], "x", { std: Number.NaN })).toThrow(RangeError);
  });

  it("std<=0 with explicit bounds does NOT throw (only sigma branch guards)", () => {
    const out = clipOutliers([{ x: 1 }, { x: 200 }], "x", { std: -1, bounds: [0, 100] });
    expect(out.map((r) => r.x_clipped)).toEqual([1, 100]);
  });

  it("std<=0 with PHYSICS_BOUNDS does NOT throw", () => {
    const out = clipOutliers([{ temp_c: -100 }], "temp_c", { std: 0 });
    expect(out[0]?.temp_c_clipped).toBe(-89);
  });

  it("sigma=0 (all values identical) → pass-through, NOT NaN/collapse", () => {
    const rows = [{ x: 5 }, { x: 5 }, { x: 5 }, { x: 5 }];
    const out = clipOutliers(rows, "x");
    expect(out.map((r) => r.x_clipped)).toEqual([5, 5, 5, 5]);
  });

  it("single-value input (n=1) → pass-through (cannot compute sample sigma)", () => {
    const rows = [{ x: 42 }];
    const out = clipOutliers(rows, "x", { std: 3 });
    expect(out[0]?.x_clipped).toBe(42);
  });

  it("empty input → empty output (no throw)", () => {
    const out = clipOutliers([], "x", { std: 3 });
    expect(out).toEqual([]);
  });
});

describe("clipOutliers — null + non-numeric source handling", () => {
  it("null source → null derived (pass-through nulls)", () => {
    const rows = [{ x: null }, { x: 5 }];
    const out = clipOutliers(rows, "x", { bounds: [0, 10] });
    expect(out.map((r) => r.x_clipped)).toEqual([null, 5]);
  });

  it("string source → null derived (no auto-coercion)", () => {
    const rows = [{ x: "5" }];
    const out = clipOutliers(rows, "x", { bounds: [0, 10] });
    expect(out[0]?.x_clipped).toBeNull();
  });

  it("NaN source → null derived", () => {
    const rows = [{ x: Number.NaN }];
    const out = clipOutliers(rows, "x", { bounds: [0, 10] });
    expect(out[0]?.x_clipped).toBeNull();
  });

  it("undefined source → null derived", () => {
    const rows = [{ x: undefined }];
    const out = clipOutliers(rows, "x", { bounds: [0, 10] });
    expect(out[0]?.x_clipped).toBeNull();
  });

  it("Infinity source → null derived", () => {
    const rows = [{ x: Number.POSITIVE_INFINITY }];
    const out = clipOutliers(rows, "x", { bounds: [0, 10] });
    expect(out[0]?.x_clipped).toBeNull();
  });
});

describe("clipOutliers — invariants", () => {
  it("does NOT mutate source rows", () => {
    const rows = [{ x: 100 }, { x: -50 }];
    const before = JSON.stringify(rows);
    clipOutliers(rows, "x", { bounds: [0, 50] });
    expect(JSON.stringify(rows)).toBe(before);
  });

  it("output length === input length", () => {
    const rows = [{ x: 1 }, { x: 2 }, { x: 3 }];
    const out = clipOutliers(rows, "x", { bounds: [0, 10] });
    expect(out.length).toBe(rows.length);
  });

  it("preserves all original columns", () => {
    const rows = [{ date: "2026-01-01", x: 5, label: "a" }];
    const out = clipOutliers(rows, "x", { bounds: [0, 10] });
    expect(out[0]).toMatchObject({ date: "2026-01-01", x: 5, label: "a", x_clipped: 5 });
  });
});

// TS-W4 Plan 02 Task 2 — rolling reduction tests (RED phase).
//
// Mirrors Python `tradewinds.transforms.rolling` (packages/core/src/
// tradewinds/transforms.py:58-68) which uses
// `df[col].rolling(window=window, min_periods=1)` and `getattr(rolling, fn)()`.
//
// Key invariants:
//   - min_periods=1: every row gets a value as long as window has ≥ 1 non-null.
//   - std uses Bessel's correction (n-1 denominator); needs ≥ 2 values.
//   - Derived column: `{col}_rolling_{window}_{fn}`.

import { describe, expect, it } from "vitest";

import { ROLLING_FNS, rolling } from "../../src/transforms/rolling.js";

const SEVEN_ROW_FIXTURE = [
  { temp_c: 10 },
  { temp_c: 12 },
  { temp_c: 14 },
  { temp_c: 16 },
  { temp_c: 18 },
  { temp_c: 20 },
  { temp_c: 22 },
] as const;

describe("rolling — mean (default fn)", () => {
  it("window=3 mean over 7-row arithmetic progression", () => {
    const out = rolling(SEVEN_ROW_FIXTURE, "temp_c", 3, "mean");
    // i=0: window=[10] → 10
    // i=1: window=[10,12] → 11
    // i=2: window=[10,12,14] → 12
    // i=3: window=[12,14,16] → 14
    // i=4: window=[14,16,18] → 16
    // i=5: window=[16,18,20] → 18
    // i=6: window=[18,20,22] → 20
    expect(out.map((r) => r.temp_c_rolling_3_mean)).toEqual([10, 11, 12, 14, 16, 18, 20]);
  });

  it("default fn is 'mean'", () => {
    const out = rolling(SEVEN_ROW_FIXTURE, "temp_c", 3);
    expect(out.map((r) => r.temp_c_rolling_3_mean)).toEqual([10, 11, 12, 14, 16, 18, 20]);
  });
});

describe("rolling — min / max / median / count", () => {
  it("window=3 min", () => {
    const out = rolling(SEVEN_ROW_FIXTURE, "temp_c", 3, "min");
    expect(out.map((r) => r.temp_c_rolling_3_min)).toEqual([10, 10, 10, 12, 14, 16, 18]);
  });

  it("window=3 max", () => {
    const out = rolling(SEVEN_ROW_FIXTURE, "temp_c", 3, "max");
    expect(out.map((r) => r.temp_c_rolling_3_max)).toEqual([10, 12, 14, 16, 18, 20, 22]);
  });

  it("window=3 median", () => {
    const out = rolling(SEVEN_ROW_FIXTURE, "temp_c", 3, "median");
    // i=0: [10] → 10
    // i=1: [10,12] → 11 (avg of two middles)
    // i=2: [10,12,14] → 12
    // i=3+: middle of 3-element window
    expect(out.map((r) => r.temp_c_rolling_3_median)).toEqual([10, 11, 12, 14, 16, 18, 20]);
  });

  it("window=3 count", () => {
    const out = rolling(SEVEN_ROW_FIXTURE, "temp_c", 3, "count");
    expect(out.map((r) => r.temp_c_rolling_3_count)).toEqual([1, 2, 3, 3, 3, 3, 3]);
  });
});

describe("rolling — std (Bessel's correction)", () => {
  it("std on 7-row arithmetic progression", () => {
    const out = rolling(SEVEN_ROW_FIXTURE, "temp_c", 3, "std");
    const stds = out.map((r) => r.temp_c_rolling_3_std);
    // i=0: n=1 → null (need ≥ 2)
    expect(stds[0]).toBeNull();
    // i=1: window=[10,12], n=2 → sample std = sqrt(((10-11)^2 + (12-11)^2)/(2-1)) = sqrt(2)
    expect(stds[1]).toBeCloseTo(Math.sqrt(2), 10);
    // i=2: window=[10,12,14], mean=12 → sample std = sqrt(((10-12)^2+0+(14-12)^2)/(3-1)) = sqrt(4) = 2
    expect(stds[2]).toBeCloseTo(2, 10);
  });
});

describe("rolling — null handling", () => {
  it("count over column with leading null", () => {
    const rows = [
      { temp_c: null },
      { temp_c: 10 },
      { temp_c: null },
      { temp_c: 12 },
      { temp_c: 14 },
    ];
    const out = rolling(rows, "temp_c", 3, "count");
    // i=0: window=[null] → 0
    // i=1: window=[null, 10] → 1
    // i=2: window=[null, 10, null] → 1
    // i=3: window=[10, null, 12] → 2
    // i=4: window=[null, 12, 14] → 2
    expect(out.map((r) => r.temp_c_rolling_3_count)).toEqual([0, 1, 1, 2, 2]);
  });

  it("all-null window → mean/median/min/max/std return null; count returns 0", () => {
    const rows = [{ temp_c: null }, { temp_c: null }];
    expect(rolling(rows, "temp_c", 2, "mean").map((r) => r.temp_c_rolling_2_mean)).toEqual([
      null,
      null,
    ]);
    expect(rolling(rows, "temp_c", 2, "median").map((r) => r.temp_c_rolling_2_median)).toEqual([
      null,
      null,
    ]);
    expect(rolling(rows, "temp_c", 2, "min").map((r) => r.temp_c_rolling_2_min)).toEqual([
      null,
      null,
    ]);
    expect(rolling(rows, "temp_c", 2, "max").map((r) => r.temp_c_rolling_2_max)).toEqual([
      null,
      null,
    ]);
    expect(rolling(rows, "temp_c", 2, "std").map((r) => r.temp_c_rolling_2_std)).toEqual([
      null,
      null,
    ]);
    expect(rolling(rows, "temp_c", 2, "count").map((r) => r.temp_c_rolling_2_count)).toEqual([
      0, 0,
    ]);
  });
});

describe("rolling — guards", () => {
  it("throws RangeError on window=0", () => {
    expect(() => rolling(SEVEN_ROW_FIXTURE, "temp_c", 0, "mean")).toThrow(RangeError);
  });

  it("throws RangeError on window=-1", () => {
    expect(() => rolling(SEVEN_ROW_FIXTURE, "temp_c", -1, "mean")).toThrow(RangeError);
  });

  it("throws RangeError on window=1.5 (non-integer)", () => {
    expect(() => rolling(SEVEN_ROW_FIXTURE, "temp_c", 1.5, "mean")).toThrow(RangeError);
  });

  it("throws RangeError on unsupported fn='sum'", () => {
    // biome-ignore lint/suspicious/noExplicitAny: testing invalid input
    expect(() => rolling(SEVEN_ROW_FIXTURE, "temp_c", 3, "sum" as any)).toThrow(RangeError);
  });
});

describe("rolling — invariants", () => {
  it("does NOT mutate source rows", () => {
    const before = JSON.stringify(SEVEN_ROW_FIXTURE);
    rolling(SEVEN_ROW_FIXTURE, "temp_c", 3, "mean");
    expect(JSON.stringify(SEVEN_ROW_FIXTURE)).toBe(before);
  });

  it("output length === input length", () => {
    const out = rolling(SEVEN_ROW_FIXTURE, "temp_c", 3, "mean");
    expect(out.length).toBe(SEVEN_ROW_FIXTURE.length);
  });

  it("output preserves all original columns + adds only the derived key", () => {
    const rows = [
      { date: "2026-01-01", temp_c: 10, station: "KAUS" },
      { date: "2026-01-02", temp_c: 12, station: "KAUS" },
    ];
    const out = rolling(rows, "temp_c", 2, "mean");
    expect(out[1]).toMatchObject({
      date: "2026-01-02",
      temp_c: 12,
      station: "KAUS",
      temp_c_rolling_2_mean: 11,
    });
  });

  it("ROLLING_FNS exports the canonical 6-element ordered list", () => {
    expect(ROLLING_FNS).toEqual(["mean", "median", "min", "max", "std", "count"]);
  });
});

// TS-W4 Plan 02 Task 1 — diff + diff2 tests (RED phase).
//
// Mirrors Python `tradewinds.transforms.diff` / `diff2` (packages/core/src/
// tradewinds/transforms.py:48-55). `diff(rows, col, n)` → derived column
// `{col}_diff_{n}`; `diff2(rows, col)` → derived column `{col}_diff2` and
// MUST drop the intermediate `{col}_diff_1` so the output carries only the
// second-difference column (Python returns a single Series).

import { describe, expect, it } from "vitest";

import { diff, diff2 } from "../../src/transforms/diff.js";

const FIVE_ROW_FIXTURE = [
  { date: "2026-01-01", temp_c: 10 },
  { date: "2026-01-02", temp_c: 12 },
  { date: "2026-01-03", temp_c: 14 },
  { date: "2026-01-04", temp_c: 16 },
  { date: "2026-01-05", temp_c: 18 },
] as const;

describe("diff — happy paths", () => {
  it("diff n=1 on constant rise produces constant diff", () => {
    const out = diff(FIVE_ROW_FIXTURE, "temp_c", 1);
    expect(out.map((r) => r.temp_c_diff_1)).toEqual([null, 2, 2, 2, 2]);
  });

  it("diff n=2 on constant rise produces constant 2*step", () => {
    const out = diff(FIVE_ROW_FIXTURE, "temp_c", 2);
    expect(out.map((r) => r.temp_c_diff_2)).toEqual([null, null, 4, 4, 4]);
  });

  it("default n=1", () => {
    const out = diff(FIVE_ROW_FIXTURE, "temp_c");
    expect(out.map((r) => r.temp_c_diff_1)).toEqual([null, 2, 2, 2, 2]);
  });

  it("derived column name follows {col}_diff_{n} exactly", () => {
    const out = diff(FIVE_ROW_FIXTURE, "temp_c", 2);
    const row = out[3];
    expect(row).toBeDefined();
    expect(Object.hasOwn(row as object, "temp_c_diff_2")).toBe(true);
  });

  it("output preserves all original columns", () => {
    const out = diff(FIVE_ROW_FIXTURE, "temp_c", 1);
    expect(out[1]).toMatchObject({ date: "2026-01-02", temp_c: 12, temp_c_diff_1: 2 });
  });
});

describe("diff — null + type handling", () => {
  it("null source propagates as null", () => {
    const rows = [{ temp_c: 10 }, { temp_c: null }, { temp_c: 14 }];
    const out = diff(rows, "temp_c", 1);
    expect(out.map((r) => r.temp_c_diff_1)).toEqual([null, null, null]);
  });

  it("string source (no auto-coercion) produces null", () => {
    const rows = [{ temp_c: 10 }, { temp_c: "12" }];
    const out = diff(rows, "temp_c", 1);
    expect(out[1]?.temp_c_diff_1).toBeNull();
  });

  it("NaN source produces null", () => {
    const rows = [{ temp_c: 10 }, { temp_c: Number.NaN }];
    const out = diff(rows, "temp_c", 1);
    expect(out[1]?.temp_c_diff_1).toBeNull();
  });
});

describe("diff — guards", () => {
  it("throws RangeError on n=0", () => {
    expect(() => diff(FIVE_ROW_FIXTURE, "temp_c", 0)).toThrow(RangeError);
  });

  it("throws RangeError on n=-1", () => {
    expect(() => diff(FIVE_ROW_FIXTURE, "temp_c", -1)).toThrow(RangeError);
  });

  it("throws RangeError on non-integer n", () => {
    expect(() => diff(FIVE_ROW_FIXTURE, "temp_c", 1.5)).toThrow(RangeError);
  });

  it("does NOT mutate source rows", () => {
    const before = JSON.stringify(FIVE_ROW_FIXTURE);
    diff(FIVE_ROW_FIXTURE, "temp_c", 1);
    expect(JSON.stringify(FIVE_ROW_FIXTURE)).toBe(before);
  });
});

describe("diff2 — second difference", () => {
  it("constant rise → zero acceleration", () => {
    const out = diff2(FIVE_ROW_FIXTURE, "temp_c");
    expect(out.map((r) => r.temp_c_diff2)).toEqual([null, null, 0, 0, 0]);
  });

  it("doubling sequence → accelerating diff2", () => {
    // values: [1, 2, 4, 8, 16]
    // first diffs: [_, 1, 2, 4, 8]
    // second diffs: [_, _, 1, 2, 4]
    const rows = [{ temp_c: 1 }, { temp_c: 2 }, { temp_c: 4 }, { temp_c: 8 }, { temp_c: 16 }];
    const out = diff2(rows, "temp_c");
    expect(out.map((r) => r.temp_c_diff2)).toEqual([null, null, 1, 2, 4]);
  });

  it("derived column is `{col}_diff2` (NOT the intermediate diff_1)", () => {
    const out = diff2(FIVE_ROW_FIXTURE, "temp_c");
    const row = out[2];
    expect(row).toBeDefined();
    expect(Object.hasOwn(row as object, "temp_c_diff2")).toBe(true);
    // Intermediate {col}_diff_1 MUST NOT leak into output.
    expect(Object.hasOwn(row as object, "temp_c_diff_1")).toBe(false);
  });

  it("null in middle propagates through both diffs", () => {
    const rows = [{ temp_c: 10 }, { temp_c: null }, { temp_c: 14 }, { temp_c: 16 }];
    const out = diff2(rows, "temp_c");
    // first diffs:    [_, null, null, 2]
    // second diffs:   [_, _, null, null]
    expect(out.map((r) => r.temp_c_diff2)).toEqual([null, null, null, null]);
  });

  it("does NOT mutate source rows", () => {
    const before = JSON.stringify(FIVE_ROW_FIXTURE);
    diff2(FIVE_ROW_FIXTURE, "temp_c");
    expect(JSON.stringify(FIVE_ROW_FIXTURE)).toBe(before);
  });

  it("output length === input length", () => {
    const out = diff2(FIVE_ROW_FIXTURE, "temp_c");
    expect(out.length).toBe(FIVE_ROW_FIXTURE.length);
  });
});

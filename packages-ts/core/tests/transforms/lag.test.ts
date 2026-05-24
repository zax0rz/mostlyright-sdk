// TS-W4 Plan 02 Task 1 — lag transform tests (RED phase).
//
// Mirrors Python `tradewinds.transforms.lag` (packages/core/src/tradewinds/
// transforms.py:43-45). The TS port operates on `ReadonlyArray<Row>` and
// adds a derived column `{col}_lag_{n}` to each output row; the input array
// MUST NOT be mutated.

import { describe, expect, it } from "vitest";

import { lag } from "../../src/transforms/lag.js";

const FIVE_ROW_FIXTURE = [
  { date: "2026-01-01", temp_c: 10 },
  { date: "2026-01-02", temp_c: 12 },
  { date: "2026-01-03", temp_c: 14 },
  { date: "2026-01-04", temp_c: 16 },
  { date: "2026-01-05", temp_c: 18 },
] as const;

describe("lag — happy paths", () => {
  it("lag n=1 shifts column by one row; leading null", () => {
    const out = lag(FIVE_ROW_FIXTURE, "temp_c", 1);
    expect(out.map((r) => r.temp_c_lag_1)).toEqual([null, 10, 12, 14, 16]);
  });

  it("lag n=3 shifts column by three rows; leading three nulls", () => {
    const out = lag(FIVE_ROW_FIXTURE, "temp_c", 3);
    expect(out.map((r) => r.temp_c_lag_3)).toEqual([null, null, null, 10, 12]);
  });

  it("default n=1", () => {
    const out = lag(FIVE_ROW_FIXTURE, "temp_c");
    expect(out.map((r) => r.temp_c_lag_1)).toEqual([null, 10, 12, 14, 16]);
  });

  it("derived column name follows {col}_lag_{n} exactly", () => {
    const out = lag(FIVE_ROW_FIXTURE, "temp_c", 2);
    const row = out[2];
    expect(row).toBeDefined();
    expect(Object.hasOwn(row as object, "temp_c_lag_2")).toBe(true);
  });

  it("output preserves all original columns", () => {
    const out = lag(FIVE_ROW_FIXTURE, "temp_c", 1);
    expect(out[1]).toMatchObject({ date: "2026-01-02", temp_c: 12, temp_c_lag_1: 10 });
  });
});

describe("lag — null and type handling", () => {
  it("null source value propagates to null in derived column (NOT NaN)", () => {
    const rows = [{ temp_c: null }, { temp_c: 12 }, { temp_c: 14 }];
    const out = lag(rows, "temp_c", 1);
    expect(out[1]?.temp_c_lag_1).toBeNull();
    expect(out[2]?.temp_c_lag_1).toBe(12);
  });

  it("string source value (no auto-coercion) produces null", () => {
    const rows = [{ temp_c: "3.5" }, { temp_c: 12 }];
    const out = lag(rows, "temp_c", 1);
    expect(out[1]?.temp_c_lag_1).toBeNull();
  });

  it("undefined source value produces null", () => {
    const rows = [{ temp_c: undefined }, { temp_c: 12 }];
    const out = lag(rows, "temp_c", 1);
    expect(out[1]?.temp_c_lag_1).toBeNull();
  });

  it("NaN source value produces null", () => {
    const rows = [{ temp_c: Number.NaN }, { temp_c: 12 }];
    const out = lag(rows, "temp_c", 1);
    expect(out[1]?.temp_c_lag_1).toBeNull();
  });
});

describe("lag — guards + invariants", () => {
  it("throws RangeError on n=0", () => {
    expect(() => lag(FIVE_ROW_FIXTURE, "temp_c", 0)).toThrow(RangeError);
  });

  it("throws RangeError on n=-1", () => {
    expect(() => lag(FIVE_ROW_FIXTURE, "temp_c", -1)).toThrow(RangeError);
  });

  it("throws RangeError on n=1.5 (non-integer)", () => {
    expect(() => lag(FIVE_ROW_FIXTURE, "temp_c", 1.5)).toThrow(RangeError);
  });

  it("empty input → empty output (no throw)", () => {
    const out = lag([], "temp_c", 1);
    expect(out).toEqual([]);
  });

  it("does NOT mutate source rows", () => {
    const before = JSON.stringify(FIVE_ROW_FIXTURE);
    lag(FIVE_ROW_FIXTURE, "temp_c", 1);
    expect(JSON.stringify(FIVE_ROW_FIXTURE)).toBe(before);
  });

  it("output length === input length", () => {
    const out = lag(FIVE_ROW_FIXTURE, "temp_c", 2);
    expect(out.length).toBe(FIVE_ROW_FIXTURE.length);
  });
});

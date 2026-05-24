// TS-W4 Plan 04 Task 1 — spread cross-feature tests (RED phase).
//
// Mirrors Python `tradewinds.transforms.spread` (packages/core/src/tradewinds/
// transforms.py:103-105). Pairwise difference between two numeric columns,
// emitting a derived `{colA}_minus_{colB}` column. Strict numeric coercion
// (matches Wave 2 lag/diff strictness): strings like '10' do NOT auto-parse.

import { describe, expect, it } from "vitest";

import { spread } from "../../src/transforms/cross.js";

describe("spread — happy paths", () => {
  it("computes a-b across multiple rows; derived column name uses _minus_", () => {
    const rows = [
      { a: 10, b: 7 },
      { a: 12, b: 9 },
      { a: 0, b: -5 },
    ];
    const out = spread(rows, "a", "b");
    expect(out.map((r) => r.a_minus_b)).toEqual([3, 3, 5]);
  });

  it("output preserves all original columns", () => {
    const rows = [{ date: "2026-01-01", a: 10, b: 7 }];
    const out = spread(rows, "a", "b");
    expect(out[0]).toMatchObject({ date: "2026-01-01", a: 10, b: 7, a_minus_b: 3 });
  });

  it("derived column name is exactly `{colA}_minus_{colB}`", () => {
    const rows = [{ obs_high_f: 75, cli_high_f: 73 }];
    const out = spread(rows, "obs_high_f", "cli_high_f");
    const r = out[0];
    expect(r).toBeDefined();
    expect(Object.hasOwn(r as object, "obs_high_f_minus_cli_high_f")).toBe(true);
    expect((r as Record<string, unknown>).obs_high_f_minus_cli_high_f).toBe(2);
  });
});

describe("spread — null and type handling", () => {
  it("null in either input → null in derived column", () => {
    const rows = [
      { a: null, b: 7 },
      { a: 10, b: null },
      { a: null, b: null },
      { a: 10, b: 7 },
    ];
    const out = spread(rows, "a", "b");
    expect(out.map((r) => r.a_minus_b)).toEqual([null, null, null, 3]);
  });

  it("string source value (no auto-coercion) produces null", () => {
    const rows = [{ a: "10", b: 7 }];
    const out = spread(rows, "a", "b");
    expect(out[0]?.a_minus_b).toBeNull();
  });

  it("undefined source value produces null", () => {
    const rows = [{ a: undefined, b: 7 }];
    const out = spread(rows, "a", "b");
    expect(out[0]?.a_minus_b).toBeNull();
  });

  it("NaN source value produces null", () => {
    const rows = [{ a: Number.NaN, b: 7 }];
    const out = spread(rows, "a", "b");
    expect(out[0]?.a_minus_b).toBeNull();
  });

  it("Infinity source value produces null", () => {
    const rows = [{ a: Number.POSITIVE_INFINITY, b: 7 }];
    const out = spread(rows, "a", "b");
    expect(out[0]?.a_minus_b).toBeNull();
  });

  it("missing column on the row produces null (no throw)", () => {
    // Cast through unknown to allow heterogeneous rows in the test fixture
    // without losing the spread() generic narrowing.
    const rows = [{ a: 10 } as Record<string, unknown>];
    const out = spread(rows, "a", "b");
    expect(out[0]?.a_minus_b).toBeNull();
  });
});

describe("spread — invariants", () => {
  it("empty input → empty output (no throw)", () => {
    const out = spread([], "a", "b");
    expect(out).toEqual([]);
  });

  it("does NOT mutate source rows", () => {
    const rows = [{ a: 10, b: 7 }];
    const before = JSON.stringify(rows);
    spread(rows, "a", "b");
    expect(JSON.stringify(rows)).toBe(before);
  });

  it("output length === input length", () => {
    const rows = [
      { a: 1, b: 2 },
      { a: 3, b: 4 },
      { a: 5, b: 6 },
    ];
    const out = spread(rows, "a", "b");
    expect(out.length).toBe(rows.length);
  });
});

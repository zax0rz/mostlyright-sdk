// TS-W3 Plan 07 Task 3 — toonDumps + toonLoads tests.
//
// Byte-equivalence check against Python `encode_tabular` output (captured
// in tests/formats/fixtures/toon-byte-equiv.txt) is the load-bearing
// assertion — silent cross-language drift here would mis-parse every
// Python TOON consumer.

import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

import { ToonTabularError, toonDumps, toonLoads } from "../../src/formats/toon.js";

const __dirname = dirname(fileURLToPath(import.meta.url));
const FIXTURE_PATH = join(__dirname, "fixtures", "toon-byte-equiv.txt");

describe("toonDumps + toonLoads", () => {
  it("byte-equivalent to Python encode_tabular on shared 3-row fixture", () => {
    const fixture = readFileSync(FIXTURE_PATH, "utf8");
    const rows = [
      { a: 1, b: "two,three", c: null },
      { a: 4, b: "five", c: true },
      { a: 6, b: "", c: false },
    ];
    const dumped = toonDumps(rows);
    expect(dumped).toBe(fixture);
  });

  it("3-row roundtrip preserves data", () => {
    const rows = [
      { a: 1, b: "two,three", c: null },
      { a: 4, b: "five", c: true },
      { a: 6, b: "", c: false },
    ];
    const dumped = toonDumps(rows);
    const { rows: loaded, columns } = toonLoads(dumped);
    expect(columns).toEqual(["a", "b", "c"]);
    expect(loaded).toEqual(rows);
  });

  it("empty rows → 'rows[0]:' (encoder bare form); roundtrip is empty", () => {
    expect(toonDumps([])).toBe("rows[0]:");
    const { rows, columns } = toonLoads("rows[0]:");
    expect(rows).toEqual([]);
    expect(columns).toEqual([]);
  });

  it("empty rows + columns → 'rows[0]{...}:' (DataFrame-wrapper-style); roundtrip preserves columns", () => {
    const cols = ["a", "b", "c"];
    const dumped = toonDumps([], cols);
    expect(dumped).toBe("rows[0]{a,b,c}:");
    const { rows, columns } = toonLoads(dumped);
    expect(rows).toEqual([]);
    expect(columns).toEqual(cols);
  });

  it("special chars: comma + quote + whitespace in cells roundtrip", () => {
    const rows = [{ note: 'hello "world", with spaces' }];
    const dumped = toonDumps(rows);
    const { rows: loaded } = toonLoads(dumped);
    expect(loaded[0]?.note).toBe('hello "world", with spaces');
  });

  it("null cells → bare null literal", () => {
    const rows = [{ x: null, y: 5 }];
    const dumped = toonDumps(rows);
    expect(dumped).toContain("null,5");
    const { rows: loaded } = toonLoads(dumped);
    expect(loaded[0]?.x).toBeNull();
    expect(loaded[0]?.y).toBe(5);
  });

  it("boolean cells → true/false bare", () => {
    const rows = [{ alive: true, frozen: false }];
    const dumped = toonDumps(rows);
    expect(dumped).toContain("true,false");
    const { rows: loaded } = toonLoads(dumped);
    expect(loaded[0]?.alive).toBe(true);
    expect(loaded[0]?.frozen).toBe(false);
  });

  it("malformed header (no `[N]`) → RangeError", () => {
    expect(() => toonLoads("rows{a,b}:\n  1,2")).toThrow(RangeError);
  });

  it("declared count != actual rows → RangeError", () => {
    expect(() => toonLoads("rows[3]{a}:\n  1\n  2")).toThrow(RangeError);
  });

  it("row column count mismatch → RangeError", () => {
    expect(() => toonLoads("rows[1]{a,b,c}:\n  1,2")).toThrow(RangeError);
  });

  it("empty payload → RangeError", () => {
    expect(() => toonLoads("")).toThrow(RangeError);
    expect(() => toonLoads("   \n\n")).toThrow(RangeError);
  });

  it("ISO timestamp string cells roundtrip as exact strings", () => {
    const rows = [{ event_time: "2025-01-01T12:00:00Z", value: 42 }];
    const dumped = toonDumps(rows);
    // ISO strings have `-`, `:`, digits — needsQuoting triggers on the `:`.
    expect(dumped).toContain('"2025-01-01T12:00:00Z"');
    const { rows: loaded } = toonLoads(dumped);
    expect(loaded[0]?.event_time).toBe("2025-01-01T12:00:00Z");
  });

  it("integer-valued floats serialize without fractional part", () => {
    const rows = [{ x: 1.0, y: 2.5 }];
    const dumped = toonDumps(rows);
    expect(dumped).toContain("1,2.5");
  });

  it("NaN/Infinity → null (per Python _format_number)", () => {
    const rows = [{ a: Number.NaN, b: Number.POSITIVE_INFINITY }];
    const dumped = toonDumps(rows);
    expect(dumped).toContain("null,null");
  });
});

describe("toonDumps — non-tabular input is REJECTED (iter-1 C3 — Python parity)", () => {
  // Python `encode_tabular` raises `ValueError` when rows aren't uniform or
  // contain non-primitive values. The TS port must match — silent column
  // drops or JSON-stringified objects are data corruption.

  it("differing key sets across rows → ToonTabularError (missing column)", () => {
    const rows = [
      { a: 1, b: 2 },
      { a: 3 }, // missing `b`
    ];
    expect(() => toonDumps(rows)).toThrow(ToonTabularError);
  });

  it("differing key sets across rows → ToonTabularError (extra column)", () => {
    const rows = [
      { a: 1, b: 2 },
      { a: 3, b: 4, c: 5 }, // extra `c`
    ];
    expect(() => toonDumps(rows)).toThrow(ToonTabularError);
  });

  it("renamed key (same length, different name) → ToonTabularError", () => {
    const rows = [
      { a: 1, b: 2 },
      { a: 3, c: 4 }, // `b` swapped for `c`
    ];
    expect(() => toonDumps(rows)).toThrow(ToonTabularError);
  });

  it("non-primitive cell value (object) → ToonTabularError", () => {
    const rows = [{ a: 1, b: { nested: true } }];
    expect(() => toonDumps(rows)).toThrow(ToonTabularError);
  });

  it("non-primitive cell value (array) → ToonTabularError", () => {
    const rows = [{ a: 1, b: [1, 2, 3] }];
    expect(() => toonDumps(rows)).toThrow(ToonTabularError);
  });

  it("non-primitive cell value (bigint) → ToonTabularError", () => {
    const rows = [{ a: 1, b: 99n }] as ReadonlyArray<Record<string, unknown>>;
    expect(() => toonDumps(rows)).toThrow(ToonTabularError);
  });

  it("non-primitive cell value appearing past row 0 → ToonTabularError", () => {
    const rows = [
      { a: 1, b: 2 },
      { a: 3, b: { hidden: true } }, // sneaks in late
    ];
    expect(() => toonDumps(rows)).toThrow(ToonTabularError);
  });

  it("first row with no keys → ToonTabularError", () => {
    const rows = [{}, { a: 1 }];
    expect(() => toonDumps(rows)).toThrow(ToonTabularError);
  });

  it("uniform primitive rows still encode successfully (regression)", () => {
    const rows = [
      { a: 1, b: "x", c: null, d: true },
      { a: 2, b: "y", c: 3.14, d: false },
    ];
    // Sanity: the new guard must not break valid input.
    expect(() => toonDumps(rows)).not.toThrow();
  });
});

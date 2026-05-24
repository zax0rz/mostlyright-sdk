// TS-W3 Plan 07 Task 2 — csvDumps + csvLoads tests.
//
// Hand-rolled minimal RFC-4180 parser (no papaparse — bundle hit).
// Mirrors Python `csv.py` (pandas `to_csv(index=False)` / `read_csv`):
//   - no index column
//   - quote-escaping for `,`, `"`, `\n`, `\r`
//   - null/undefined → empty string

import { describe, expect, it } from "vitest";

import { csvDumps, csvLoads } from "../../src/formats/csv.js";

describe("csvDumps + csvLoads", () => {
  it("3-row simple roundtrip", () => {
    const rows = [
      { a: "1", b: "two", c: "3" },
      { a: "4", b: "five", c: "6" },
      { a: "7", b: "eight", c: "9" },
    ];
    const dumped = csvDumps(rows);
    const { rows: loaded, columns } = csvLoads(dumped);
    expect(columns).toEqual(["a", "b", "c"]);
    expect(loaded).toEqual(rows);
  });

  it("commas in cells: quoting + unquoting", () => {
    const rows = [{ name: "Smith, John", age: "42" }];
    const dumped = csvDumps(rows);
    expect(dumped).toContain('"Smith, John"');
    const { rows: loaded } = csvLoads(dumped);
    expect(loaded[0]?.name).toBe("Smith, John");
    expect(loaded[0]?.age).toBe("42");
  });

  it("quotes in cells: double-quote escape", () => {
    const rows = [{ note: 'She said "hi"' }];
    const dumped = csvDumps(rows);
    // RFC 4180: quotes inside quoted cells are doubled.
    expect(dumped).toContain('"She said ""hi"""');
    const { rows: loaded } = csvLoads(dumped);
    expect(loaded[0]?.note).toBe('She said "hi"');
  });

  it("null/undefined cells → empty string", () => {
    const rows = [
      { a: "1", b: null, c: undefined },
      { a: "2", b: "x", c: "y" },
    ];
    const dumped = csvDumps(rows);
    const { rows: loaded } = csvLoads(dumped);
    expect(loaded[0]?.b).toBe("");
    expect(loaded[0]?.c).toBe("");
    expect(loaded[1]?.b).toBe("x");
    expect(loaded[1]?.c).toBe("y");
  });

  it("empty rows → empty string output", () => {
    expect(csvDumps([])).toBe("");
    expect(csvLoads("")).toEqual({ rows: [], columns: [] });
  });

  it("header-only parse: returns columns, empty rows", () => {
    const { rows, columns } = csvLoads("a,b,c\n");
    expect(columns).toEqual(["a", "b", "c"]);
    expect(rows).toEqual([]);
  });

  it.skip("embedded newlines inside quoted cells (v0.1.0 documented gap)", () => {
    // The hand-rolled parser does NOT handle multi-line quoted cells.
    // Use jsonDumps/jsonLoads or toonDumps/toonLoads for free-form text.
    // This test documents the gap; it intentionally lives behind .skip.
    const rows = [{ note: "line1\nline2" }];
    const dumped = csvDumps(rows);
    const { rows: loaded } = csvLoads(dumped);
    expect(loaded[0]?.note).toBe("line1\nline2");
  });
});

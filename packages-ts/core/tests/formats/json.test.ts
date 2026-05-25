// TS-W3 Plan 07 Task 1 — jsonDumps + jsonLoads tests.
//
// Mirrors `packages/core/src/mostlyright/core/formats/json.py`. The
// load-bearing requirement: empty-frame envelope `{columns, data}`
// preserves column names through roundtrip — Python downstream readers
// would break without it.

import { describe, expect, it } from "vitest";

import { jsonDumps, jsonLoads } from "../../src/formats/json.js";

describe("jsonDumps + jsonLoads", () => {
  it("3-row roundtrip preserves data", () => {
    const rows = [
      { a: 1, b: "two", c: null },
      { a: 4, b: "five", c: true },
      { a: 6, b: "", c: false },
    ];
    const dumped = jsonDumps(rows);
    const { rows: loaded, columns } = jsonLoads(dumped);
    expect(loaded).toEqual(rows);
    expect(columns).toEqual(["a", "b", "c"]);
  });

  it("empty + columns emits envelope; loads back with columns", () => {
    const cols = ["a", "b", "c"];
    const dumped = jsonDumps([], cols);
    expect(dumped).toBe('{"columns":["a","b","c"],"data":[]}');
    const { rows, columns } = jsonLoads(dumped);
    expect(rows).toEqual([]);
    expect(columns).toEqual(cols);
  });

  it("empty WITHOUT columns throws RangeError", () => {
    expect(() => jsonDumps([])).toThrow(RangeError);
  });

  it("envelope without data field throws RangeError", () => {
    expect(() => jsonLoads('{"columns":["a"]}')).toThrow(RangeError);
  });

  it("envelope without columns field throws RangeError", () => {
    expect(() => jsonLoads('{"data":[]}')).toThrow(RangeError);
  });

  it("records form with ISO timestamps roundtrips byte-equal", () => {
    const rows = [{ event_time: "2025-01-01T12:00:00Z", value: 42 }];
    const dumped = jsonDumps(rows);
    const { rows: loaded } = jsonLoads(dumped);
    expect(loaded[0]?.event_time).toBe("2025-01-01T12:00:00Z");
  });

  it("null values preserved through roundtrip", () => {
    const rows = [{ x: null, y: 5 }];
    const dumped = jsonDumps(rows);
    const { rows: loaded } = jsonLoads(dumped);
    expect(loaded[0]?.x).toBeNull();
    expect(loaded[0]?.y).toBe(5);
  });

  it("records form with non-array payload throws", () => {
    expect(() => jsonLoads('"just a string"')).toThrow(RangeError);
  });
});

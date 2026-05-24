// TS-W3 Plan 07 Task 3 — fast-check roundtrip property tests across all
// three formats (JSON / CSV / TOON).

import fc from "fast-check";
import { describe, expect, it } from "vitest";

import { csvDumps, csvLoads } from "../../src/formats/csv.js";
import { jsonDumps, jsonLoads } from "../../src/formats/json.js";
import { toonDumps, toonLoads } from "../../src/formats/toon.js";

// Constrained arbitrary — finite numbers, no NaN, single-line strings
// (CSV's hand-rolled parser does not support embedded newlines; that's a
// documented v0.1.0 gap, not something to test through random input).
const arbRow = fc.record({
  id: fc.integer({ min: -1000, max: 1000 }),
  name: fc
    .string({ minLength: 0, maxLength: 30 })
    .filter((s) => !s.includes("\n") && !s.includes("\r")),
  value: fc.option(
    fc.float({
      noNaN: true,
      noDefaultInfinity: true,
      min: -1_000_000,
      max: 1_000_000,
    }),
  ),
});

describe("roundtrip property: dump → load preserves rows for all 3 formats", () => {
  it("JSON roundtrip (100 runs)", () => {
    fc.assert(
      fc.property(fc.array(arbRow, { minLength: 1, maxLength: 20 }), (rows) => {
        const dumped = jsonDumps(rows);
        const { rows: loaded } = jsonLoads(dumped);
        return JSON.stringify(loaded) === JSON.stringify(rows);
      }),
      { numRuns: 100 },
    );
  });

  it("CSV roundtrip — string coercion (100 runs)", () => {
    // CSV loses dtypes: loaded rows are Record<string, string>. Compare
    // column-by-column after normalizing to string. Null becomes "".
    fc.assert(
      fc.property(fc.array(arbRow, { minLength: 1, maxLength: 20 }), (rows) => {
        const dumped = csvDumps(rows);
        const { rows: loaded } = csvLoads(dumped);
        if (loaded.length !== rows.length) return false;
        for (let i = 0; i < rows.length; i++) {
          const r = rows[i] as (typeof rows)[number];
          const l = loaded[i] as (typeof loaded)[number];
          if (l.id !== String(r.id)) return false;
          if (l.name !== (r.name ?? "")) return false;
          // value is number | null — null becomes ""
          if (r.value == null) {
            if (l.value !== "") return false;
          } else {
            if (l.value !== String(r.value)) return false;
          }
        }
        return true;
      }),
      { numRuns: 100 },
    );
  });

  it("TOON roundtrip (100 runs)", () => {
    fc.assert(
      fc.property(fc.array(arbRow, { minLength: 1, maxLength: 20 }), (rows) => {
        const dumped = toonDumps(rows);
        const { rows: loaded } = toonLoads(dumped);
        if (loaded.length !== rows.length) return false;
        for (let i = 0; i < rows.length; i++) {
          const r = rows[i] as (typeof rows)[number];
          const l = loaded[i] as (typeof loaded)[number];
          if (l.id !== r.id) return false;
          // Empty strings roundtrip via `""` quoted form, decode to "".
          const expectedName = r.name ?? "";
          if (l.name !== expectedName) return false;
          // null roundtrips as null
          if (r.value == null) {
            if (l.value !== null) return false;
          } else {
            // Numeric values: tolerate integer vs float identity (TOON
            // collapses integer-valued floats to int form).
            const lv = l.value as number;
            const rv = r.value as number;
            if (!Number.isFinite(lv) || Math.abs(lv - rv) > 1e-9) return false;
          }
        }
        return true;
      }),
      { numRuns: 100 },
    );
  });

  it("TOON roundtrip on empty rows (with columns)", () => {
    const cols = ["a", "b", "c"];
    const dumped = toonDumps([], cols);
    const { rows, columns } = toonLoads(dumped);
    expect(rows).toEqual([]);
    expect(columns).toEqual(cols);
  });
});

// TS-W4 Plan 03 Task 1 — calendarFeatures transform tests.
//
// Mirrors Python `mostlyright.transforms.calendar_features`
// (packages/core/src/mostlyright/transforms.py:71-100). The TS port operates
// on `ReadonlyArray<Row>` and appends 8 cyclical-pair columns
// (month_sin/cos, dow_sin/cos, hour_sin/cos, day_of_year_sin/cos) computed
// from `dateCol`. TZ-aware extraction via `Intl.DateTimeFormat`.
//
// Coverage targets (per ts-w4-03-PLAN.md acceptance criteria):
//   - 4-row UTC fixture with month/dow/hour/doy expectations
//   - sin²+cos² ≈ 1 wraparound invariant
//   - tz='America/New_York' shifts hour=20 (June 14 EDT, not June 15 UTC)
//   - tz DST transition (Nov 3 2024 fall-back)
//   - Invalid tz throws RangeError BEFORE iterating
//   - Null / non-parseable / undefined date → all 8 cols null
//   - Date input (not string) supported
//   - Source rows immutable
//   - Empty input → empty output

import { describe, expect, it } from "vitest";

import { calendarFeatures } from "../../src/transforms/calendar.js";

const UTC_FIXTURE = [
  { date_utc: "2024-01-15T00:00:00Z" }, // Mon Jan 15 → month=1, dow=0, hour=0, doy=15
  { date_utc: "2024-04-15T12:00:00Z" }, // Mon Apr 15 → month=4, dow=0, hour=12, doy=106
  { date_utc: "2024-07-15T06:00:00Z" }, // Mon Jul 15 → month=7, dow=0, hour=6, doy=197
  { date_utc: "2024-10-15T18:00:00Z" }, // Tue Oct 15 → month=10, dow=1, hour=18, doy=289
] as const;

const TAU = 2 * Math.PI;
const closeTo = (actual: number, expected: number, eps = 1e-10): boolean =>
  Math.abs(actual - expected) <= eps;

// Strict accessor: throws (test fails) if index is out of range — avoids
// non-null assertion (`!`) which biome forbids and substitutes a clearer
// failure mode for "fixture changed shape".
function row<T>(arr: ReadonlyArray<T>, i: number): T {
  const r = arr[i];
  if (r === undefined) {
    throw new Error(`row(${i}): out of range (length=${arr.length})`);
  }
  return r;
}

describe("calendarFeatures — UTC extraction (no tz)", () => {
  it("Row 0 (Jan 15 UTC, Mon, 00:00) → month=1 dow=0 hour=0 doy=15", () => {
    const out = calendarFeatures(UTC_FIXTURE, "date_utc");
    const r = row(out, 0);
    expect(closeTo(r.month_sin as number, Math.sin((TAU * 1) / 12))).toBe(true);
    expect(closeTo(r.month_cos as number, Math.cos((TAU * 1) / 12))).toBe(true);
    expect(closeTo(r.dow_sin as number, Math.sin((TAU * 0) / 7))).toBe(true);
    expect(closeTo(r.dow_cos as number, Math.cos((TAU * 0) / 7))).toBe(true);
    expect(closeTo(r.hour_sin as number, Math.sin((TAU * 0) / 24))).toBe(true);
    expect(closeTo(r.hour_cos as number, Math.cos((TAU * 0) / 24))).toBe(true);
    expect(closeTo(r.day_of_year_sin as number, Math.sin((TAU * 15) / 365.0))).toBe(true);
    expect(closeTo(r.day_of_year_cos as number, Math.cos((TAU * 15) / 365.0))).toBe(true);
  });

  it("Row 1 (Apr 15 UTC, Mon, 12:00) → month=4 dow=0 hour=12 doy=106", () => {
    const out = calendarFeatures(UTC_FIXTURE, "date_utc");
    const r = row(out, 1);
    expect(closeTo(r.month_sin as number, Math.sin((TAU * 4) / 12))).toBe(true);
    expect(closeTo(r.hour_sin as number, Math.sin((TAU * 12) / 24))).toBe(true);
    expect(closeTo(r.day_of_year_sin as number, Math.sin((TAU * 106) / 365.0))).toBe(true);
    expect(closeTo(r.day_of_year_cos as number, Math.cos((TAU * 106) / 365.0))).toBe(true);
  });

  it("Row 2 (Jul 15 UTC, Mon, 06:00) → month=7 dow=0 hour=6 doy=197", () => {
    const out = calendarFeatures(UTC_FIXTURE, "date_utc");
    const r = row(out, 2);
    expect(closeTo(r.month_sin as number, Math.sin((TAU * 7) / 12))).toBe(true);
    expect(closeTo(r.hour_sin as number, Math.sin((TAU * 6) / 24))).toBe(true);
    expect(closeTo(r.day_of_year_sin as number, Math.sin((TAU * 197) / 365.0))).toBe(true);
  });

  it("Row 3 (Oct 15 UTC, Tue, 18:00) → month=10 dow=1 hour=18 doy=289", () => {
    const out = calendarFeatures(UTC_FIXTURE, "date_utc");
    const r = row(out, 3);
    expect(closeTo(r.month_sin as number, Math.sin((TAU * 10) / 12))).toBe(true);
    expect(closeTo(r.dow_sin as number, Math.sin((TAU * 1) / 7))).toBe(true);
    expect(closeTo(r.dow_cos as number, Math.cos((TAU * 1) / 7))).toBe(true);
    expect(closeTo(r.hour_sin as number, Math.sin((TAU * 18) / 24))).toBe(true);
    expect(closeTo(r.day_of_year_sin as number, Math.sin((TAU * 289) / 365.0))).toBe(true);
  });
});

describe("calendarFeatures — cyclical pair invariant (sin² + cos² ≈ 1)", () => {
  it("every pair on every row satisfies sin² + cos² ≈ 1 within 1e-10", () => {
    const out = calendarFeatures(UTC_FIXTURE, "date_utc");
    const pairs: Array<[string, string]> = [
      ["month_sin", "month_cos"],
      ["dow_sin", "dow_cos"],
      ["hour_sin", "hour_cos"],
      ["day_of_year_sin", "day_of_year_cos"],
    ];
    let assertions = 0;
    for (const r of out) {
      for (const [s, c] of pairs) {
        const sv = r[s] as number;
        const cv = r[c] as number;
        expect(closeTo(sv * sv + cv * cv, 1)).toBe(true);
        assertions++;
      }
    }
    // 4 rows × 4 pairs = 16 sin²+cos² invariant checks (each invariant
    // exercises both members of the pair → all 32 derived values are
    // touched). This is the "model sees wraparound" success criterion
    // from `transforms.py:80-84`.
    expect(assertions).toBe(16);
  });
});

describe("calendarFeatures — tz-aware extraction (Intl.DateTimeFormat)", () => {
  it("tz='America/New_York' on '2024-06-15T00:00:00Z' → month=6 dow=4 (Fri) hour=20 doy=166", () => {
    // Jun 15 00:00 UTC = Jun 14 20:00 EDT (UTC-4). Jun 14 2024 was a Friday.
    const out = calendarFeatures([{ d: "2024-06-15T00:00:00Z" }], "d", "America/New_York");
    const r = row(out, 0);
    expect(closeTo(r.month_sin as number, Math.sin((TAU * 6) / 12))).toBe(true);
    expect(closeTo(r.month_cos as number, Math.cos((TAU * 6) / 12))).toBe(true);
    expect(closeTo(r.dow_sin as number, Math.sin((TAU * 4) / 7))).toBe(true);
    expect(closeTo(r.dow_cos as number, Math.cos((TAU * 4) / 7))).toBe(true);
    expect(closeTo(r.hour_sin as number, Math.sin((TAU * 20) / 24))).toBe(true);
    expect(closeTo(r.hour_cos as number, Math.cos((TAU * 20) / 24))).toBe(true);
    expect(closeTo(r.day_of_year_sin as number, Math.sin((TAU * 166) / 365.0))).toBe(true);
    expect(closeTo(r.day_of_year_cos as number, Math.cos((TAU * 166) / 365.0))).toBe(true);
  });

  it("UTC vs tz produce DIFFERENT hour features (silent-UTC regression guard)", () => {
    const utc = calendarFeatures([{ d: "2024-06-15T00:00:00Z" }], "d");
    const ny = calendarFeatures([{ d: "2024-06-15T00:00:00Z" }], "d", "America/New_York");
    // UTC: hour=0 → hour_sin = 0. NY: hour=20 → hour_sin = sin(2π·20/24) ≈ -0.866.
    expect(utc[0]?.hour_sin).not.toBe(ny[0]?.hour_sin);
  });

  it("tz='America/New_York' DST fall-back: '2024-11-03T06:00:00Z' → month=11 dow=6 (Sun) hour=1 doy=308", () => {
    // Nov 3 06:00 UTC. After fall-back (02:00 EDT → 01:00 EST), this is
    // Nov 3 01:00 EST (UTC-5). Nov 3 2024 was a Sunday.
    const out = calendarFeatures([{ d: "2024-11-03T06:00:00Z" }], "d", "America/New_York");
    const r = row(out, 0);
    expect(closeTo(r.month_sin as number, Math.sin((TAU * 11) / 12))).toBe(true);
    expect(closeTo(r.dow_sin as number, Math.sin((TAU * 6) / 7))).toBe(true);
    expect(closeTo(r.dow_cos as number, Math.cos((TAU * 6) / 7))).toBe(true);
    expect(closeTo(r.hour_sin as number, Math.sin((TAU * 1) / 24))).toBe(true);
    expect(closeTo(r.day_of_year_sin as number, Math.sin((TAU * 308) / 365.0))).toBe(true);
  });

  it("invalid tz throws RangeError BEFORE iterating any row", () => {
    // Probe via Proxy: if any property other than `length` is read, the
    // implementation reached row iteration → fail-fast invariant broken.
    const sentinel: Array<{ d: string }> = [];
    let touchedNonLength = false;
    const guard = new Proxy(sentinel, {
      get(target, prop) {
        if (prop !== "length") touchedNonLength = true;
        return Reflect.get(target, prop);
      },
    });
    expect(() => calendarFeatures(guard, "d", "Invalid/Zone")).toThrow(RangeError);
    expect(() => calendarFeatures(guard, "d", "Invalid/Zone")).toThrow(/Invalid\/Zone/);
    expect(touchedNonLength).toBe(false);
  });
});

describe("calendarFeatures — null / type handling", () => {
  it("non-parseable date string → all 8 derived columns are null", () => {
    const out = calendarFeatures([{ d: "not-a-date" }], "d");
    const r = row(out, 0);
    expect(r.month_sin).toBeNull();
    expect(r.month_cos).toBeNull();
    expect(r.dow_sin).toBeNull();
    expect(r.dow_cos).toBeNull();
    expect(r.hour_sin).toBeNull();
    expect(r.hour_cos).toBeNull();
    expect(r.day_of_year_sin).toBeNull();
    expect(r.day_of_year_cos).toBeNull();
  });

  it("null date → all 8 derived columns are null", () => {
    const out = calendarFeatures([{ d: null }], "d");
    const r = row(out, 0);
    expect(r.month_sin).toBeNull();
    expect(r.day_of_year_cos).toBeNull();
  });

  it("undefined date column → all 8 derived columns are null", () => {
    const out = calendarFeatures([{ other: 1 } as Record<string, unknown>], "d");
    const r = row(out, 0);
    expect(r.month_sin).toBeNull();
    expect(r.day_of_year_cos).toBeNull();
  });

  it("Date instance input (not string) works equivalently to string", () => {
    const dateInput = calendarFeatures([{ d: new Date("2024-06-15T00:00:00Z") }], "d");
    const stringInput = calendarFeatures([{ d: "2024-06-15T00:00:00Z" }], "d");
    const dRow = row(dateInput, 0);
    const sRow = row(stringInput, 0);
    expect(dRow.month_sin).toBeCloseTo(sRow.month_sin as number, 12);
    expect(dRow.day_of_year_sin).toBeCloseTo(sRow.day_of_year_sin as number, 12);
  });

  it("invalid Date instance (NaN getTime) → all nulls", () => {
    const out = calendarFeatures([{ d: new Date("not-a-date") }], "d");
    expect(row(out, 0).month_sin).toBeNull();
  });
});

describe("calendarFeatures — purity + structure", () => {
  it("empty input → empty output (no throw)", () => {
    const out = calendarFeatures([], "date_utc");
    expect(out).toEqual([]);
  });

  it("does NOT mutate source rows", () => {
    const before = JSON.stringify(UTC_FIXTURE);
    calendarFeatures(UTC_FIXTURE, "date_utc");
    expect(JSON.stringify(UTC_FIXTURE)).toBe(before);
  });

  it("output preserves all original columns + adds exactly 8 derived columns", () => {
    const rows = [{ date_utc: "2024-06-15T00:00:00Z", station: "KJFK", temp_f: 75 }];
    const out = calendarFeatures(rows, "date_utc");
    const r = row(out, 0);
    expect(r.date_utc).toBe("2024-06-15T00:00:00Z");
    expect(r.station).toBe("KJFK");
    expect(r.temp_f).toBe(75);
    expect(Object.hasOwn(r, "month_sin")).toBe(true);
    expect(Object.hasOwn(r, "month_cos")).toBe(true);
    expect(Object.hasOwn(r, "dow_sin")).toBe(true);
    expect(Object.hasOwn(r, "dow_cos")).toBe(true);
    expect(Object.hasOwn(r, "hour_sin")).toBe(true);
    expect(Object.hasOwn(r, "hour_cos")).toBe(true);
    expect(Object.hasOwn(r, "day_of_year_sin")).toBe(true);
    expect(Object.hasOwn(r, "day_of_year_cos")).toBe(true);
  });

  it("output length === input length", () => {
    const out = calendarFeatures(UTC_FIXTURE, "date_utc");
    expect(out.length).toBe(UTC_FIXTURE.length);
  });
});

describe("calendarFeatures — Dec→Jan wraparound sanity", () => {
  it("month_sin/cos for Dec 31 and Jan 1 are NEAR each other (wraparound)", () => {
    // Dec → month=12 → sin(2π·12/12) = sin(2π) = 0; cos = 1.
    // Jan → month=1 → sin(2π/12) ≈ 0.5; cos ≈ 0.866.
    // Dec→Jan distance on the unit circle should be << Dec→Jul distance,
    // which is the property that lets a model see Dec→Jan as a 1-month
    // step rather than an 11-month jump.
    const decArr = calendarFeatures([{ d: "2024-12-31T00:00:00Z" }], "d");
    const janArr = calendarFeatures([{ d: "2025-01-01T00:00:00Z" }], "d");
    const julArr = calendarFeatures([{ d: "2024-07-15T00:00:00Z" }], "d");
    const dec = row(decArr, 0);
    const jan = row(janArr, 0);
    const jul = row(julArr, 0);
    const dist = (a: typeof dec, b: typeof dec): number => {
      const ds = (a.month_sin as number) - (b.month_sin as number);
      const dc = (a.month_cos as number) - (b.month_cos as number);
      return Math.sqrt(ds * ds + dc * dc);
    };
    expect(dist(dec, jan)).toBeLessThan(dist(dec, jul));
  });

  it("day_of_year denominator is 365.0 (NOT 365.25 / 366) — Python parity", () => {
    // 2025 is not a leap year; doy(Dec 31 2025) = 365.
    // sin(2π·365/365.0) = sin(2π) ≈ 0; cos = 1. The Python `transforms.py:98`
    // uses 365.0 verbatim — drift here breaks parity.
    const out = calendarFeatures([{ d: "2025-12-31T00:00:00Z" }], "d");
    const r = row(out, 0);
    expect(closeTo(r.day_of_year_sin as number, 0, 1e-12)).toBe(true);
    expect(closeTo(r.day_of_year_cos as number, 1, 1e-12)).toBe(true);
  });
});

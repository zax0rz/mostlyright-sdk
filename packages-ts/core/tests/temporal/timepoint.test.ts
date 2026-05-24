// TS-W3 Plan 04 Task 1 — TimePoint unit tests (RED phase).
//
// Mirrors `packages/core/src/tradewinds/core/temporal/timepoint.py`. Asserts
// that the TS port rejects naive/date-only/NaN/Infinity inputs loudly at
// construction and exposes parity accessors (toUTCDate, toISOString, asZone,
// equals/before/after, TimePoint.now()).

import { describe, expect, it } from "vitest";

import { TimePoint } from "../../src/temporal/timepoint.js";

describe("TimePoint — accepts valid tz-aware inputs", () => {
  it("accepts ISO with Z suffix", () => {
    const tp = new TimePoint("2026-05-21T14:30:00Z");
    expect(tp.toISOString()).toMatch(/Z$/);
  });

  it("accepts ISO with fractional seconds + Z", () => {
    const tp = new TimePoint("2026-05-21T14:30:00.123Z");
    expect(tp.toISOString()).toMatch(/Z$/);
  });

  it("accepts ISO with +00:00 offset", () => {
    const tp = new TimePoint("2026-05-21T14:30:00+00:00");
    expect(tp.toISOString()).toMatch(/Z$/);
  });

  it("accepts ISO with -05:00 offset", () => {
    const tp = new TimePoint("2026-05-21T14:30:00-05:00");
    expect(tp.toISOString()).toMatch(/Z$/);
  });

  it("accepts a Date instance", () => {
    const d = new Date(Date.UTC(2026, 4, 21, 14, 30, 0));
    const tp = new TimePoint(d);
    expect(tp.toISOString()).toBe("2026-05-21T14:30:00.000Z");
  });

  it("toISOString always ends in Z (Date input)", () => {
    const tp = new TimePoint(new Date());
    expect(tp.toISOString().endsWith("Z")).toBe(true);
  });

  it("toISOString always ends in Z (ISO string input)", () => {
    const tp = new TimePoint("2026-05-21T14:30:00-05:00");
    expect(tp.toISOString().endsWith("Z")).toBe(true);
  });
});

describe("TimePoint — rejects naive / date-only / invalid inputs", () => {
  it("rejects date-only ISO string", () => {
    expect(() => new TimePoint("2026-05-21")).toThrow(RangeError);
  });

  it("rejects date-only ISO string with Z suffix (no T/space separator)", () => {
    // Regression for iter-1 C1: `Date.parse("2026-05-21Z")` silently
    // normalizes to midnight UTC. The previous TZ_SUFFIX-only check let
    // this through. Python `_from_iso_string` rejects it — the separator
    // guard must run BEFORE the tz-suffix check.
    expect(() => new TimePoint("2026-05-21Z")).toThrow(RangeError);
  });

  it("rejects date-only ISO string with +HH:MM offset (no T/space separator)", () => {
    // Same iter-1 C1 regression — every tz-suffix shape must be guarded,
    // not just `Z`.
    expect(() => new TimePoint("2026-05-21+00:00")).toThrow(RangeError);
  });

  it("rejects naive ISO string (no Z, no offset)", () => {
    expect(() => new TimePoint("2026-05-21T14:30:00")).toThrow(RangeError);
  });

  it("rejects empty string", () => {
    expect(() => new TimePoint("")).toThrow(RangeError);
  });

  it("rejects whitespace-only string", () => {
    expect(() => new TimePoint("   ")).toThrow(RangeError);
  });

  it("rejects Date(NaN)", () => {
    expect(() => new TimePoint(new Date(Number.NaN))).toThrow(RangeError);
  });

  it("rejects Date built from Infinity", () => {
    expect(() => new TimePoint(new Date(Number.POSITIVE_INFINITY))).toThrow(RangeError);
  });

  it("rejects number input", () => {
    // @ts-expect-error — runtime defensive check
    expect(() => new TimePoint(123)).toThrow(TypeError);
  });

  it("rejects null input", () => {
    // @ts-expect-error — runtime defensive check
    expect(() => new TimePoint(null)).toThrow();
  });

  it("rejects undefined input", () => {
    // @ts-expect-error — runtime defensive check
    expect(() => new TimePoint(undefined)).toThrow();
  });

  it("rejects unparseable ISO string", () => {
    // tz suffix present but body is gibberish
    expect(() => new TimePoint("not-a-date-at-allZ")).toThrow(RangeError);
  });
});

describe("TimePoint — accessors", () => {
  it("toUTCDate returns a Date with the same UTC ms", () => {
    const tp = new TimePoint("2026-05-21T14:30:00Z");
    const expected = Date.UTC(2026, 4, 21, 14, 30, 0);
    expect(tp.toUTCDate().getTime()).toBe(expected);
  });

  it("toUTCDate returns a defensive copy (callers can mutate without leak)", () => {
    const tp = new TimePoint("2026-05-21T14:30:00Z");
    const d1 = tp.toUTCDate();
    d1.setUTCFullYear(1999);
    expect(tp.toUTCDate().getUTCFullYear()).toBe(2026);
  });

  it("asZone(America/New_York) returns a string containing the local date", () => {
    // 2026-05-21T14:30:00Z is 10:30 in New York DST; we use loose contains
    // because Intl.DateTimeFormat output format varies by Node version.
    const tp = new TimePoint("2026-05-21T14:30:00Z");
    const formatted = tp.asZone("America/New_York");
    expect(formatted).toContain("2026");
    expect(formatted).toContain("05");
    expect(formatted).toContain("21");
  });

  it("equals — two TimePoints from the same instant are equal", () => {
    const a = new TimePoint("2026-05-21T14:30:00Z");
    const b = new TimePoint("2026-05-21T09:30:00-05:00");
    expect(a.equals(b)).toBe(true);
  });

  it("before/after — strict ordering", () => {
    const a = new TimePoint("2026-05-21T14:30:00Z");
    const b = new TimePoint("2026-05-21T15:00:00Z");
    expect(a.before(b)).toBe(true);
    expect(b.after(a)).toBe(true);
    expect(a.before(a)).toBe(false);
    expect(a.after(a)).toBe(false);
  });
});

describe("TimePoint.now()", () => {
  it("returns a TimePoint within 1 second of Date.now()", () => {
    const before = Date.now();
    const tp = TimePoint.now();
    const after = Date.now();
    const ms = tp.toUTCDate().getTime();
    expect(ms).toBeGreaterThanOrEqual(before);
    expect(ms).toBeLessThanOrEqual(after);
  });
});

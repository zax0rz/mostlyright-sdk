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

describe("TimePoint — calendar-validity (iter-3 C8)", () => {
  // `Date.parse` silently normalizes impossible dates ("2025-02-30T..." →
  // "2025-03-02T..."), but Python `datetime.fromisoformat` raises ValueError.
  // These tests pin the Python-equivalent contract.
  it("rejects Feb 30 (silent rollover bug)", () => {
    // Date.parse("2025-02-30T00:00:00Z") === Date.UTC(2025,2,2). Without the
    // calendar-validity check, the constructor would silently shift the
    // event/knowledge time forward 2 days — a parity-breaking corruption.
    expect(() => new TimePoint("2025-02-30T00:00:00Z")).toThrow(RangeError);
  });

  it("rejects month 13 (silent year rollover bug)", () => {
    expect(() => new TimePoint("2025-13-01T00:00:00Z")).toThrow(RangeError);
  });

  it("rejects day 32 (silent month rollover bug)", () => {
    expect(() => new TimePoint("2025-01-32T00:00:00Z")).toThrow(RangeError);
  });

  it("rejects month 00", () => {
    // Some browsers/engines roll "2025-00-15" back to "2024-12-15"; mirror
    // Python's ValueError.
    expect(() => new TimePoint("2025-00-15T00:00:00Z")).toThrow();
  });

  it("rejects day 00", () => {
    expect(() => new TimePoint("2025-01-00T00:00:00Z")).toThrow();
  });

  it("rejects Feb 29 on a non-leap year (2025)", () => {
    expect(() => new TimePoint("2025-02-29T00:00:00Z")).toThrow(RangeError);
  });

  it("accepts Feb 29 on a leap year (2024)", () => {
    expect(() => new TimePoint("2024-02-29T00:00:00Z")).not.toThrow();
    const tp = new TimePoint("2024-02-29T00:00:00Z");
    expect(tp.toISOString()).toBe("2024-02-29T00:00:00.000Z");
  });

  it("accepts a valid date with non-UTC tz that legitimately shifts the wall-clock day", () => {
    // "2025-01-01T23:00:00-05:00" → UTC midnight on 2025-01-02. The source
    // string asserts day=01; the calendar-validity check must compare
    // against the SOURCE side (after undoing the offset), not raw UTC,
    // otherwise legitimate tz inputs would be rejected.
    expect(() => new TimePoint("2025-01-01T23:00:00-05:00")).not.toThrow();
    const tp = new TimePoint("2025-01-01T23:00:00-05:00");
    expect(tp.toISOString()).toBe("2025-01-02T04:00:00.000Z");
  });

  it("rejects an impossible-date with a non-UTC tz (Feb 30 +05:30)", () => {
    expect(() => new TimePoint("2025-02-30T12:00:00+05:30")).toThrow(RangeError);
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

describe("TimePoint.toPythonIso (iter-1 H1)", () => {
  it("zero-millisecond instant: matches Python datetime.isoformat shape", () => {
    // Python: datetime(2025,1,2,12,0,0,tzinfo=UTC).isoformat()
    //         → "2025-01-02T12:00:00+00:00"
    const tp = new TimePoint("2025-01-02T12:00:00Z");
    expect(tp.toPythonIso()).toBe("2025-01-02T12:00:00+00:00");
  });

  it("non-zero millisecond instant: pads to 6-digit microseconds", () => {
    // JS only carries ms precision; pad with trailing zeros for parity
    // with Python `pd.Timestamp(...).isoformat()` against a
    // millisecond-resolution column.
    const tp = new TimePoint("2025-01-02T12:00:00.123Z");
    expect(tp.toPythonIso()).toBe("2025-01-02T12:00:00.123000+00:00");
  });

  it("differs from toISOString (the H1 divergence shape)", () => {
    const tp = new TimePoint("2025-01-02T12:00:00Z");
    // toISOString emits the JS-native shape; toPythonIso emits Python's.
    expect(tp.toISOString()).toBe("2025-01-02T12:00:00.000Z");
    expect(tp.toPythonIso()).toBe("2025-01-02T12:00:00+00:00");
    expect(tp.toISOString()).not.toBe(tp.toPythonIso());
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

describe("TimePoint — microsecond precision (iter-11 C13)", () => {
  // Codex iter-11 CRITICAL: `Date.parse` collapses microsecond-resolution
  // ISO strings to the same epoch-ms (e.g. ".123456Z" and ".123789Z" both
  // parse to ms=123). assertNoLeakage / KnowledgeView compared via
  // `.getTime()`, so a row "known" 333µs after `asOf` could silently
  // pass the leakage gate. The fix: carry an epoch-µs `bigint` alongside
  // the Date and route ALL comparisons through it.

  it("parses + preserves 6-digit fractional seconds (.123456Z) as distinct from .123789Z", () => {
    const a = new TimePoint("2025-01-02T12:00:00.123456Z");
    const b = new TimePoint("2025-01-02T12:00:00.123789Z");
    // Date.getTime() would say these are equal (both ms=123) — that's
    // the bug. equals() must use µs precision and report them as distinct.
    expect(a.toUTCDate().getTime()).toBe(b.toUTCDate().getTime()); // ms collision (the latent bug surface)
    expect(a.equals(b)).toBe(false); // µs precision distinguishes them (the fix)
    expect(a.before(b)).toBe(true);
    expect(b.after(a)).toBe(true);
  });

  it("epoch-µs accessor reflects the source string's microsecond field", () => {
    const tp = new TimePoint("2025-01-02T12:00:00.123456Z");
    // 2025-01-02T12:00:00Z whole-second epoch = 1735819200 sec
    // → ms = 1_735_819_200_000, µs base = 1_735_819_200_000_000
    // plus 123_456 µs → 1_735_819_200_123_456n
    expect(tp.toEpochMicros()).toBe(1_735_819_200_123_456n);
  });

  it("epoch-µs accessor for ms-precision input pads the µs field with zeros", () => {
    const tp = new TimePoint("2025-01-02T12:00:00.123Z");
    // ".123" pads to ".123000" µs → epoch ms × 1000.
    expect(tp.toEpochMicros()).toBe(BigInt(Date.UTC(2025, 0, 2, 12, 0, 0, 123)) * 1000n);
  });

  it("epoch-µs accessor for no-fractional input equals ms × 1000n", () => {
    const tp = new TimePoint("2025-01-02T12:00:00Z");
    expect(tp.toEpochMicros()).toBe(BigInt(Date.UTC(2025, 0, 2, 12, 0, 0)) * 1000n);
  });

  it("epoch-µs accessor for Date input equals ms × 1000n (Date is ms-only)", () => {
    const d = new Date(Date.UTC(2025, 0, 2, 12, 0, 0, 123));
    const tp = new TimePoint(d);
    expect(tp.toEpochMicros()).toBe(BigInt(d.getTime()) * 1000n);
  });

  it("truncates ≥7-digit fractional seconds to 6 digits (matches Python fromisoformat)", () => {
    // Python `datetime.fromisoformat` accepts arbitrary precision but
    // truncates to 6 (microseconds). ".1234567Z" → µs=123456; the 7th
    // digit is sub-µs and dropped (no rounding).
    const tp = new TimePoint("2025-01-02T12:00:00.1234567Z");
    expect(tp.toEpochMicros() % 1_000_000n).toBe(123_456n);
  });

  it("pads <6-digit fractional seconds (.1Z → 100000 µs)", () => {
    const tp = new TimePoint("2025-01-02T12:00:00.1Z");
    expect(tp.toEpochMicros() % 1_000_000n).toBe(100_000n);
  });

  it("equals — two strings with identical full µs are equal", () => {
    const a = new TimePoint("2025-01-02T12:00:00.123456Z");
    const b = new TimePoint("2025-01-02T12:00:00.123456Z");
    expect(a.equals(b)).toBe(true);
  });

  it("equals — same instant via different tz suffixes (with µs) is still equal", () => {
    // 12:00:00.123456 UTC == 07:00:00.123456 -05:00. The µs field must
    // ride along through the tz normalization.
    const a = new TimePoint("2025-01-02T12:00:00.123456Z");
    const b = new TimePoint("2025-01-02T07:00:00.123456-05:00");
    expect(a.equals(b)).toBe(true);
  });

  it("before — µs-resolution strict ordering across same ms", () => {
    const a = new TimePoint("2025-01-02T12:00:00.123456Z");
    const b = new TimePoint("2025-01-02T12:00:00.123457Z");
    expect(a.before(b)).toBe(true);
    expect(b.before(a)).toBe(false);
    expect(a.before(a)).toBe(false);
  });

  it("toPythonIso round-trips 6-digit microseconds exactly (iter-11 C13)", () => {
    // The H1 fix emitted `.123000` for a `.123Z` source; the C13 fix
    // extends that to emit the TRUE 6-digit fraction for sources that
    // carry full µs precision.
    const tp = new TimePoint("2025-01-02T12:00:00.123456Z");
    expect(tp.toPythonIso()).toBe("2025-01-02T12:00:00.123456+00:00");
  });

  it("toPythonIso — zero microseconds (no fractional) → no subsecond portion", () => {
    const tp = new TimePoint("2025-01-02T12:00:00Z");
    expect(tp.toPythonIso()).toBe("2025-01-02T12:00:00+00:00");
  });

  it("toPythonIso — ms-precision input still pads to 6 digits (back-compat with H1)", () => {
    const tp = new TimePoint("2025-01-02T12:00:00.123Z");
    expect(tp.toPythonIso()).toBe("2025-01-02T12:00:00.123000+00:00");
  });

  it("toPythonIso — preserves the lowest µs (.000001Z) without dropping to zero", () => {
    // The bug-bait case: a single µs above zero must NOT round down to
    // "+00:00" (no fractional). The µs accessor sees 1, the formatter
    // emits ".000001+00:00".
    const tp = new TimePoint("2025-01-02T12:00:00.000001Z");
    expect(tp.toPythonIso()).toBe("2025-01-02T12:00:00.000001+00:00");
  });
});

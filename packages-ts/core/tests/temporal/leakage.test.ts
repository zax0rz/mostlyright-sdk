// TS-W3 Plan 04 Task 3 — assertNoLeakage + LeakageDetector tests.
//
// Mirrors `packages/core/src/tradewinds/core/temporal/leakage.py`. The wire
// shape from `LeakageError.toDict()` MUST use snake_case keys (as_of,
// violating_count, sample_violations) for Python-parity in MCP wire format.

import { describe, expect, it } from "vitest";

import { LeakageError, SchemaValidationError } from "../../src/exceptions/index.js";
import { LeakageDetector, assertNoLeakage } from "../../src/temporal/leakage.js";
import { TimePoint } from "../../src/temporal/timepoint.js";

const asOf = new TimePoint("2025-01-02T12:00:00Z");

describe("assertNoLeakage", () => {
  it("leak-free input → returns void (no throw)", () => {
    const rows = [
      { knowledge_time: "2025-01-01T00:00:00Z" },
      { knowledge_time: "2025-01-02T12:00:00Z" }, // equals — NOT leakage
    ];
    expect(() => assertNoLeakage(rows, asOf)).not.toThrow();
  });

  it("1 leaking row → throws LeakageError with violatingCount=1", () => {
    const rows = [
      { knowledge_time: "2025-01-01T00:00:00Z" },
      { knowledge_time: "2025-01-03T00:00:00Z", id: "leak" },
    ];
    try {
      assertNoLeakage(rows, asOf);
      throw new Error("expected LeakageError");
    } catch (e) {
      expect(e).toBeInstanceOf(LeakageError);
      const err = e as LeakageError;
      expect(err.violatingCount).toBe(1);
      expect(err.sampleViolations[0]).toHaveProperty("row_idx", 1);
      // H1: knowledge_time is re-emitted in Python isoformat shape
      // (`+00:00` suffix, no `.000` ms padding) for cross-SDK parity.
      expect(err.sampleViolations[0]).toHaveProperty("knowledge_time", "2025-01-03T00:00:00+00:00");
    }
  });

  it("15 leaking rows → throws LeakageError with violatingCount=15 and sampleViolations capped at 10", () => {
    const rows: Array<{ knowledge_time: string }> = [];
    for (let i = 0; i < 15; i++) {
      const t = new Date(asOf.toUTCDate().getTime() + (i + 1) * 86_400_000).toISOString();
      rows.push({ knowledge_time: t });
    }
    try {
      assertNoLeakage(rows, asOf);
      throw new Error("expected LeakageError");
    } catch (e) {
      expect(e).toBeInstanceOf(LeakageError);
      const err = e as LeakageError;
      expect(err.violatingCount).toBe(15);
      expect(err.sampleViolations).toHaveLength(10);
    }
  });

  it("LeakageError.toDict() emits snake_case wire shape with Python isoformat (H1 parity)", () => {
    const rows = [{ knowledge_time: "2025-01-03T00:00:00Z" }];
    try {
      assertNoLeakage(rows, asOf);
      throw new Error("expected LeakageError");
    } catch (e) {
      const err = e as LeakageError;
      const dict = err.toDict();
      // snake_case keys present:
      expect(Object.hasOwn(dict, "as_of")).toBe(true);
      expect(Object.hasOwn(dict, "violating_count")).toBe(true);
      expect(Object.hasOwn(dict, "sample_violations")).toBe(true);
      // camelCase keys MUST NOT appear:
      expect(Object.hasOwn(dict, "asOf")).toBe(false);
      expect(Object.hasOwn(dict, "violatingCount")).toBe(false);
      expect(Object.hasOwn(dict, "sampleViolations")).toBe(false);
      // H1: as_of is the Python `datetime.isoformat()` shape, NOT
      // JS `Date.toISOString()`. Asserted as a LITERAL string so any
      // future drift (back to `Z` suffix, or `.000` ms padding) fails
      // loudly. Python emits `"2025-01-02T12:00:00+00:00"` for a UTC
      // tz-aware datetime with zero microseconds.
      expect(dict.as_of).toBe("2025-01-02T12:00:00+00:00");
      // The Date.toISOString() form (with Z suffix + ms padding) MUST
      // NOT appear in the wire payload — that was the H1 divergence.
      expect(dict.as_of).not.toBe(asOf.toISOString());
      expect(dict.violating_count).toBe(1);
      // sample_violations[].knowledge_time also uses Python isoformat.
      const sv = dict.sample_violations as Array<Record<string, unknown>>;
      expect(sv[0]).toMatchObject({
        row_idx: 0,
        knowledge_time: "2025-01-03T00:00:00+00:00",
      });
    }
  });

  it("non-TimePoint asOf → TypeError", () => {
    expect(() =>
      // @ts-expect-error — runtime defensive check
      assertNoLeakage([], "2025-01-02T12:00:00Z"),
    ).toThrow(TypeError);
  });

  it("rows with non-string knowledge_time → SchemaValidationError (iter-3 C9)", () => {
    // Iter-3 C9 fix: Python's `assert_no_leakage` raises
    // SchemaValidationError when the column isn't a datetime dtype. Skipping
    // those rows let malformed temporal data pass the leakage gate
    // silently. The TS port now raises with `rule="datetime_dtype"`.
    const rows = [
      { knowledge_time: "2025-01-01T00:00:00Z" },
      { knowledge_time: 12345 },
    ] as unknown as Array<{ knowledge_time: string }>;
    expect(() => assertNoLeakage(rows, asOf)).toThrow(SchemaValidationError);
    try {
      assertNoLeakage(rows, asOf);
    } catch (e) {
      const err = e as SchemaValidationError;
      expect(err.violations[0]).toMatchObject({
        column: "knowledge_time",
        rule: "datetime_dtype",
        row_idx: 1,
      });
    }
  });

  it("rows with unparseable knowledge_time string → SchemaValidationError (iter-3 C9)", () => {
    // Iter-3 C9 fix: an unparseable string is the per-row analog of
    // Python's `col.dt.tz is None` (i.e. not a tz-aware datetime). Surfaced
    // as `rule="tz_aware_utc"`.
    const rows = [{ knowledge_time: "2025-01-01T00:00:00Z" }, { knowledge_time: "not-a-date" }];
    expect(() => assertNoLeakage(rows, asOf)).toThrow(SchemaValidationError);
    try {
      assertNoLeakage(rows, asOf);
    } catch (e) {
      const err = e as SchemaValidationError;
      expect(err.violations[0]).toMatchObject({
        column: "knowledge_time",
        rule: "tz_aware_utc",
        row_idx: 1,
      });
    }
  });

  it("empty input → returns void", () => {
    expect(() => assertNoLeakage([], asOf)).not.toThrow();
  });
});

describe("assertNoLeakage — iter-3 C9 validation contract", () => {
  // Pin every branch of the Python `assert_no_leakage` validation
  // contract: missing field → `required`, non-string → `datetime_dtype`,
  // naive / date-only → `tz_aware_utc`, valid → no throw. Cross-SDK MCP
  // consumers see byte-equivalent rule strings.

  it("missing knowledge_time field → SchemaValidationError(rule='required')", () => {
    const rows = [{ knowledge_time: undefined }] as unknown as Array<{
      knowledge_time: string;
    }>;
    expect(() => assertNoLeakage(rows, asOf)).toThrow(SchemaValidationError);
    try {
      assertNoLeakage(rows, asOf);
    } catch (e) {
      const err = e as SchemaValidationError;
      expect(err.violations[0]).toMatchObject({
        column: "knowledge_time",
        rule: "required",
        row_idx: 0,
      });
    }
  });

  it("numeric knowledge_time → SchemaValidationError(rule='datetime_dtype')", () => {
    const rows = [{ knowledge_time: 12345 }] as unknown as Array<{
      knowledge_time: string;
    }>;
    expect(() => assertNoLeakage(rows, asOf)).toThrow(SchemaValidationError);
    try {
      assertNoLeakage(rows, asOf);
    } catch (e) {
      const err = e as SchemaValidationError;
      expect(err.violations[0]).toMatchObject({
        column: "knowledge_time",
        rule: "datetime_dtype",
        row_idx: 0,
      });
    }
  });

  it("date-only string (no tz) → SchemaValidationError(rule='tz_aware_utc')", () => {
    const rows = [{ knowledge_time: "2025-01-01" }];
    expect(() => assertNoLeakage(rows, asOf)).toThrow(SchemaValidationError);
    try {
      assertNoLeakage(rows, asOf);
    } catch (e) {
      const err = e as SchemaValidationError;
      expect(err.violations[0]).toMatchObject({
        column: "knowledge_time",
        rule: "tz_aware_utc",
        row_idx: 0,
      });
    }
  });

  it("naive datetime (no tz suffix) → SchemaValidationError(rule='tz_aware_utc')", () => {
    const rows = [{ knowledge_time: "2025-01-01T12:00:00" }];
    expect(() => assertNoLeakage(rows, asOf)).toThrow(SchemaValidationError);
    try {
      assertNoLeakage(rows, asOf);
    } catch (e) {
      const err = e as SchemaValidationError;
      expect(err.violations[0]).toMatchObject({
        column: "knowledge_time",
        rule: "tz_aware_utc",
        row_idx: 0,
      });
    }
  });

  it("valid tz-aware UTC datetime → does NOT throw", () => {
    const rows = [{ knowledge_time: "2025-01-01T12:00:00Z" }];
    expect(() => assertNoLeakage(rows, asOf)).not.toThrow();
  });

  it("valid tz-aware non-UTC datetime → does NOT throw (offset preserved)", () => {
    // "2025-01-01T07:00:00-05:00" → UTC 2025-01-01T12:00:00, equal to asOf
    // (NOT leakage). Confirms the offset path through TimePoint flows
    // correctly through the new validation pass.
    const rows = [{ knowledge_time: "2025-01-01T07:00:00-05:00" }];
    expect(() => assertNoLeakage(rows, asOf)).not.toThrow();
  });

  it("impossible calendar date (iter-3 C8 sibling) → SchemaValidationError", () => {
    // The C8 calendar-validity fix makes "2025-02-30T00:00:00Z" raise from
    // TimePoint; assertNoLeakage's re-wrap surfaces it as
    // `rule="tz_aware_utc"` (the per-row analog of Python's "not a valid
    // datetime"). Without C9, this would have been silently skipped.
    const rows = [{ knowledge_time: "2025-02-30T00:00:00Z" }];
    expect(() => assertNoLeakage(rows, asOf)).toThrow(SchemaValidationError);
  });

  it("null row → SchemaValidationError(rule='required')", () => {
    const rows = [null] as unknown as Array<{ knowledge_time: string }>;
    expect(() => assertNoLeakage(rows, asOf)).toThrow(SchemaValidationError);
  });
});

describe("LeakageDetector", () => {
  it(".check(rows) delegates to assertNoLeakage", () => {
    const detector = new LeakageDetector(asOf);
    const rows = [{ knowledge_time: "2025-01-03T00:00:00Z" }];
    expect(() => detector.check(rows)).toThrow(LeakageError);
  });

  it(".asOf getter returns the same TimePoint", () => {
    const detector = new LeakageDetector(asOf);
    expect(detector.asOf).toBe(asOf);
  });

  it("constructor rejects non-TimePoint asOf → TypeError", () => {
    expect(
      () =>
        // @ts-expect-error — runtime defensive check
        new LeakageDetector("2025-01-02T12:00:00Z"),
    ).toThrow(TypeError);
  });
});

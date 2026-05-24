// TS-W3 Plan 04 Task 3 — assertNoLeakage + LeakageDetector tests.
//
// Mirrors `packages/core/src/tradewinds/core/temporal/leakage.py`. The wire
// shape from `LeakageError.toDict()` MUST use snake_case keys (as_of,
// violating_count, sample_violations) for Python-parity in MCP wire format.

import { describe, expect, it } from "vitest";

import { LeakageError } from "../../src/exceptions/index.js";
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
      expect(err.sampleViolations[0]).toHaveProperty("knowledge_time", "2025-01-03T00:00:00Z");
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

  it("LeakageError.toDict() emits snake_case wire shape (Python parity)", () => {
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
      // Values match asOf
      expect(dict.as_of).toBe(asOf.toISOString());
      expect(dict.violating_count).toBe(1);
    }
  });

  it("non-TimePoint asOf → TypeError", () => {
    expect(() =>
      // @ts-expect-error — runtime defensive check
      assertNoLeakage([], "2025-01-02T12:00:00Z"),
    ).toThrow(TypeError);
  });

  it("rows with non-string knowledge_time are SKIPPED (not counted as leakage)", () => {
    // Matches Python: validation is KnowledgeView's job; leakage check is
    // the > comparison only. A non-string knowledge_time silently skips.
    const rows = [
      { knowledge_time: "2025-01-01T00:00:00Z" },
      { knowledge_time: 12345 }, // skip
    ] as unknown as Array<{ knowledge_time: string }>;
    expect(() => assertNoLeakage(rows, asOf)).not.toThrow();
  });

  it("rows with unparseable knowledge_time string are skipped (not counted)", () => {
    const rows = [{ knowledge_time: "2025-01-01T00:00:00Z" }, { knowledge_time: "not-a-date" }];
    expect(() => assertNoLeakage(rows, asOf)).not.toThrow();
  });

  it("empty input → returns void", () => {
    expect(() => assertNoLeakage([], asOf)).not.toThrow();
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

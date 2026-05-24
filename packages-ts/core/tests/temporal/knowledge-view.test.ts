// TS-W3 Plan 04 Task 2 — KnowledgeView unit tests (RED phase).
//
// Mirrors `packages/core/src/tradewinds/core/temporal/knowledge_view.py`.
// Asserts: filter invariant (<= asOf), defensive copy on .rows(), eager
// validation of knowledge_time presence/typing at construction.

import { describe, expect, it } from "vitest";

import { SchemaValidationError } from "../../src/exceptions/index.js";
import { KnowledgeView } from "../../src/temporal/knowledge-view.js";
import { TimePoint } from "../../src/temporal/timepoint.js";

describe("KnowledgeView", () => {
  const asOf = new TimePoint("2025-01-02T12:00:00Z");

  it("basic filter: returns rows where knowledge_time <= asOf (3-row span)", () => {
    const rows = [
      { knowledge_time: "2025-01-01T00:00:00Z", value: 10 },
      { knowledge_time: "2025-01-02T12:00:00Z", value: 20 }, // equals — included
      { knowledge_time: "2025-01-03T00:00:00Z", value: 30 }, // future — excluded
    ];
    const view = new KnowledgeView(rows, asOf);
    const filtered = view.rows();
    expect(filtered).toHaveLength(2);
    expect(filtered.map((r) => r.value)).toEqual([10, 20]);
  });

  it("empty input → empty output", () => {
    const view = new KnowledgeView([], asOf);
    expect(view.rows()).toEqual([]);
  });

  it("all-future rows → empty output", () => {
    const rows = [
      { knowledge_time: "2025-02-01T00:00:00Z" },
      { knowledge_time: "2025-03-01T00:00:00Z" },
    ];
    const view = new KnowledgeView(rows, asOf);
    expect(view.rows()).toEqual([]);
  });

  it("all-past rows → all returned", () => {
    const rows = [
      { knowledge_time: "2024-12-01T00:00:00Z" },
      { knowledge_time: "2024-12-31T00:00:00Z" },
    ];
    const view = new KnowledgeView(rows, asOf);
    expect(view.rows()).toHaveLength(2);
  });

  it("missing knowledge_time → SchemaValidationError with rule='required' (H2 parity)", () => {
    // Runtime defensive check — cast through unknown so TS allows the
    // structurally-invalid row to exercise the runtime guard.
    const rows = [{ knowledge_time: "2025-01-01T00:00:00Z" }, { value: 99 }] as unknown as Array<{
      knowledge_time: string;
    }>;
    try {
      new KnowledgeView(rows, asOf);
      throw new Error("expected SchemaValidationError");
    } catch (e) {
      expect(e).toBeInstanceOf(SchemaValidationError);
      const err = e as SchemaValidationError;
      // H2: literal rule string from Python `knowledge_view.py`.
      expect(err.violations[0]).toMatchObject({
        column: "knowledge_time",
        row_idx: 1,
        rule: "required",
      });
    }
  });

  it("non-string knowledge_time → SchemaValidationError with rule='required' (H2 parity)", () => {
    const rows = [
      { knowledge_time: "2025-01-01T00:00:00Z" },
      { knowledge_time: 123 },
    ] as unknown as Array<{ knowledge_time: string }>;
    try {
      new KnowledgeView(rows, asOf);
      throw new Error("expected SchemaValidationError");
    } catch (e) {
      expect(e).toBeInstanceOf(SchemaValidationError);
      const err = e as SchemaValidationError;
      // H2: non-string knowledge_time also fires the `required` rule —
      // matches Python's column-level "missing or wrong type" semantics.
      expect(err.violations[0]).toMatchObject({
        column: "knowledge_time",
        row_idx: 1,
        rule: "required",
      });
    }
  });

  it("naive knowledge_time string → SchemaValidationError with rule='tz_aware_utc' (H2 parity)", () => {
    const rows = [{ knowledge_time: "2025-01-01T00:00:00" }]; // no Z, no offset
    try {
      new KnowledgeView(rows, asOf);
      throw new Error("expected SchemaValidationError");
    } catch (e) {
      expect(e).toBeInstanceOf(SchemaValidationError);
      const err = e as SchemaValidationError;
      // H2: literal rule string `tz_aware_utc` from Python — naive /
      // invalid tz strings fail this check.
      expect(err.violations[0]).toMatchObject({
        column: "knowledge_time",
        row_idx: 0,
        rule: "tz_aware_utc",
      });
    }
  });

  it("non-TimePoint asOf → TypeError", () => {
    // @ts-expect-error — runtime defensive check
    expect(() => new KnowledgeView([], "2025-01-02T12:00:00Z")).toThrow(TypeError);
  });

  it(".asOf getter returns the same TimePoint instance", () => {
    const view = new KnowledgeView([], asOf);
    expect(view.asOf).toBe(asOf);
  });

  it(".rows() does NOT mutate the input array", () => {
    const rows = [
      { knowledge_time: "2025-01-01T00:00:00Z", value: 10 },
      { knowledge_time: "2025-01-03T00:00:00Z", value: 30 },
    ];
    const before = JSON.stringify(rows);
    const view = new KnowledgeView(rows, asOf);
    view.rows();
    expect(JSON.stringify(rows)).toBe(before);
  });

  it("multiple .rows() calls return distinct arrays with equal content", () => {
    const rows = [{ knowledge_time: "2025-01-01T00:00:00Z", value: 10 }];
    const view = new KnowledgeView(rows, asOf);
    const a = view.rows();
    const b = view.rows();
    expect(a).not.toBe(b); // different array references
    expect(a).toEqual(b); // equal content
  });
});

// KnowledgeView — temporal filtering by `knowledge_time`.
//
// Mirrors `packages/core/src/tradewinds/core/temporal/knowledge_view.py`.
// A plain class (not an iterator subclass, not a DataFrame accessor) that
// filters its `rows()` output to entries where `knowledge_time <= asOf`.
//
// Construction validates the shape of EVERY row up-front: each
// `knowledge_time` must be a string that TimePoint accepts (rejecting naive
// / date-only / NaN inputs). Any failure throws SchemaValidationError with
// the violating row indices in `violations`.
//
// Iter-1 H2: violation `rule` vocabulary matches Python EXACTLY for MCP
// cross-language serialization parity:
//
//   - "required"      — missing column / non-string knowledge_time
//   - "tz_aware_utc"  — naive or otherwise invalid tz-aware ISO string
//
// See docs/design.md §M for the leakage-free training-view semantics.

import { SchemaValidationError } from "../exceptions/index.js";
import { TimePoint } from "./timepoint.js";

/**
 * A filtered, knowledge-time-bounded view over an array of rows.
 *
 * @template Row — caller's row type. Must have a string `knowledge_time` field.
 */
export class KnowledgeView<Row extends { knowledge_time: string }> {
  readonly #rows: ReadonlyArray<Row>;
  readonly #asOf: TimePoint;
  readonly #asOfMs: number;

  constructor(rows: ReadonlyArray<Row>, asOf: TimePoint) {
    if (!(asOf instanceof TimePoint)) {
      throw new TypeError(`asOf must be a TimePoint; got ${typeof asOf}`);
    }
    // Eager per-row validation: every row's knowledge_time must parse as a
    // valid tz-aware ISO datetime. We piggyback on TimePoint's rejection
    // logic so the error vocabulary matches construction-time errors.
    const violations: Array<Record<string, unknown>> = [];
    for (let i = 0; i < rows.length; i++) {
      const r = rows[i];
      if (r == null || typeof r.knowledge_time !== "string") {
        // H2: Python `knowledge_view.py` uses `rule="required"` when the
        // knowledge_time column is missing or wrong-typed. Mirror the
        // vocabulary so MCP wire payloads match cross-language.
        violations.push({
          column: "knowledge_time",
          row_idx: i,
          rule: "required",
        });
        continue;
      }
      try {
        new TimePoint(r.knowledge_time);
      } catch (e) {
        // H2: Python uses `rule="tz_aware_utc"` for naive / invalid
        // datetime strings (the upstream Python check is on the column
        // dtype, not per-row, but the rule string is what the wire
        // payload pins). Preserve the parsed error message in `message`
        // for debugging.
        violations.push({
          column: "knowledge_time",
          row_idx: i,
          rule: "tz_aware_utc",
          message: String(e),
        });
      }
    }
    if (violations.length > 0) {
      throw new SchemaValidationError(
        `KnowledgeView received ${violations.length} row(s) with invalid knowledge_time`,
        { schemaId: "<runtime>", violations },
      );
    }
    this.#rows = rows;
    this.#asOf = asOf;
    this.#asOfMs = asOf.toUTCDate().getTime();
  }

  /**
   * Return a freshly filtered array — only rows where
   * `knowledge_time <= asOf`. The returned array is a NEW reference each
   * call (defensive copy semantics), so callers can mutate it without
   * affecting subsequent calls.
   */
  rows(): ReadonlyArray<Row> {
    return this.#rows.filter((r) => Date.parse(r.knowledge_time) <= this.#asOfMs);
  }

  /** The as-of cutoff supplied at construction. */
  get asOf(): TimePoint {
    return this.#asOf;
  }
}

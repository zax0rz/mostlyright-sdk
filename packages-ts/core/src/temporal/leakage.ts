// assertNoLeakage + LeakageDetector — loud assertion of as-of leakage absence.
//
// Mirrors `packages/core/src/tradewinds/core/temporal/leakage.py`. Where
// KnowledgeView silently filters, assertNoLeakage throws LeakageError if
// any row has knowledge_time > asOf. The error payload follows design.md
// §D: violatingCount + sampleViolations (capped at 10).
//
// Behavior parity with Python `leakage.py`:
//  - Rows with missing / non-string knowledge_time are SKIPPED (NOT counted
//    as violations). Validation is KnowledgeView's job; this module's job
//    is the `>` comparison only.
//  - Unparseable ISO strings are likewise skipped (Date.parse → NaN).
//  - Sample cap = 10.
//  - Wire format for `as_of` AND `sample_violations[].knowledge_time` uses
//    the Python `datetime.isoformat()` shape (`"...T12:00:00+00:00"`) via
//    `TimePoint.toPythonIso()` — iter-1 H1 fix. MCP clients comparing
//    these strings across Python and TS see byte-equivalent values.

import { LeakageError } from "../exceptions/index.js";
import { TimePoint } from "./timepoint.js";

const SAMPLE_CAP = 10;

/**
 * Throw {@link LeakageError} if any row's `knowledge_time` is strictly
 * greater than `asOf`. Leak-free input returns void.
 *
 * @template Row — caller's row type. Must have a string `knowledge_time` field.
 */
export function assertNoLeakage<Row extends { knowledge_time: string }>(
  rows: ReadonlyArray<Row>,
  asOf: TimePoint,
): void {
  if (!(asOf instanceof TimePoint)) {
    throw new TypeError(`asOf must be a TimePoint; got ${typeof asOf}`);
  }
  const asOfMs = asOf.toUTCDate().getTime();
  const violations: Array<{ row_idx: number; knowledge_time: string }> = [];
  for (let i = 0; i < rows.length; i++) {
    const r = rows[i];
    if (r == null || typeof r.knowledge_time !== "string") {
      continue; // matches Python: validation is KnowledgeView's job
    }
    const t = Date.parse(r.knowledge_time);
    if (Number.isFinite(t) && t > asOfMs) {
      // Re-emit knowledge_time in the Python isoformat shape so cross-
      // language MCP consumers see byte-equivalent strings. The input
      // could be `"...Z"` (JS toISOString output) or `"...+00:00"`
      // (Python output) — normalize both via TimePoint.
      let knowledgeTime = r.knowledge_time;
      try {
        knowledgeTime = new TimePoint(r.knowledge_time).toPythonIso();
      } catch {
        // The Date.parse succeeded above so TimePoint should accept it;
        // if it doesn't (e.g. trailing whitespace differences), fall
        // back to the original string rather than dropping the row.
      }
      violations.push({ row_idx: i, knowledge_time: knowledgeTime });
    }
  }
  if (violations.length === 0) return;
  throw new LeakageError(`Found ${violations.length} row(s) with knowledge_time > asOf`, {
    asOf: asOf.toPythonIso(),
    violatingCount: violations.length,
    sampleViolations: violations.slice(0, SAMPLE_CAP),
  });
}

/**
 * Convenience wrapper for repeated leakage checks against a fixed `asOf`.
 *
 * ```ts
 * const detector = new LeakageDetector(asOf);
 * detector.check(trainingRows);
 * detector.check(featureRows);
 * ```
 */
export class LeakageDetector {
  readonly #asOf: TimePoint;

  constructor(asOf: TimePoint) {
    if (!(asOf instanceof TimePoint)) {
      throw new TypeError(`asOf must be a TimePoint; got ${typeof asOf}`);
    }
    this.#asOf = asOf;
  }

  get asOf(): TimePoint {
    return this.#asOf;
  }

  check<Row extends { knowledge_time: string }>(rows: ReadonlyArray<Row>): void {
    assertNoLeakage(rows, this.#asOf);
  }
}

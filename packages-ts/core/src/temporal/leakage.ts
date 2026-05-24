// assertNoLeakage + LeakageDetector — loud assertion of as-of leakage absence.
//
// Mirrors `packages/core/src/tradewinds/core/temporal/leakage.py`. Where
// KnowledgeView silently filters, assertNoLeakage throws LeakageError if
// any row has knowledge_time > asOf. The error payload follows design.md
// §D: violatingCount + sampleViolations (capped at 10).
//
// Behavior parity with Python `leakage.py`:
//  - Missing `knowledge_time` field → SchemaValidationError with
//    `violations: [{ column: "knowledge_time", rule: "required" }]`.
//    Matches Python's `"knowledge_time" not in df.columns` branch.
//  - Non-string `knowledge_time` value → SchemaValidationError with
//    `rule: "datetime_dtype"`. Matches Python's
//    `is_datetime64_any_dtype(col)` check.
//  - Naive / tz-less / unparseable `knowledge_time` string →
//    SchemaValidationError with `rule: "tz_aware_utc"`. Matches Python's
//    `col.dt.tz is None` check.
//  - Iter-3 C9 fix: previously these three cases were SKIPPED silently
//    (rows quietly dropped from the `>` comparison), which let malformed
//    temporal data pass the leakage gate. The Python contract raises;
//    the TS port now matches.
//  - Sample cap = 10.
//  - Wire format for `as_of` AND `sample_violations[].knowledge_time` uses
//    the Python `datetime.isoformat()` shape (`"...T12:00:00+00:00"`) via
//    `TimePoint.toPythonIso()` — iter-1 H1 fix. MCP clients comparing
//    these strings across Python and TS see byte-equivalent values.

import { LeakageError, SchemaValidationError } from "../exceptions/index.js";
import { TimePoint } from "./timepoint.js";

const SAMPLE_CAP = 10;
const RUNTIME_SCHEMA_ID = "<runtime>";

/**
 * Throw {@link LeakageError} if any row's `knowledge_time` is strictly
 * greater than `asOf`. Leak-free input returns void.
 *
 * Loudly rejects rows whose `knowledge_time` is missing, not a string,
 * or not a tz-aware ISO 8601 datetime — these surface as
 * {@link SchemaValidationError} (rule: `required` /
 * `datetime_dtype` / `tz_aware_utc`), mirroring Python's
 * `assert_no_leakage` validation contract.
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
    // Reject missing rows / missing knowledge_time field (iter-3 C9).
    // Python: `"knowledge_time" not in df.columns` →
    //   SchemaValidationError(rule="required", column="knowledge_time")
    if (r == null) {
      throw new SchemaValidationError("assertNoLeakage requires 'knowledge_time' on every row", {
        schemaId: RUNTIME_SCHEMA_ID,
        violations: [{ column: "knowledge_time", rule: "required", row_idx: i }],
        quarantineCount: rows.length,
        sampleViolations: [{ column: "knowledge_time", rule: "required", row_idx: i }],
      });
    }
    const rec = r as unknown as Record<string, unknown>;
    if (!("knowledge_time" in rec) || rec.knowledge_time === undefined) {
      throw new SchemaValidationError("assertNoLeakage requires 'knowledge_time' on every row", {
        schemaId: RUNTIME_SCHEMA_ID,
        violations: [{ column: "knowledge_time", rule: "required", row_idx: i }],
        quarantineCount: rows.length,
        sampleViolations: [{ column: "knowledge_time", rule: "required", row_idx: i }],
      });
    }
    // Reject non-string knowledge_time (iter-3 C9). Python: a non-datetime
    // column raises with `rule="datetime_dtype"`. The TS analog is a
    // per-row value that isn't even a string.
    const raw = rec.knowledge_time;
    if (typeof raw !== "string") {
      throw new SchemaValidationError(
        `assertNoLeakage requires string knowledge_time; got ${typeof raw} at row ${i}`,
        {
          schemaId: RUNTIME_SCHEMA_ID,
          violations: [{ column: "knowledge_time", rule: "datetime_dtype", row_idx: i }],
          quarantineCount: rows.length,
          sampleViolations: [{ column: "knowledge_time", rule: "datetime_dtype", row_idx: i }],
        },
      );
    }
    // Reject naive / unparseable / non-tz-aware strings (iter-3 C9).
    // Python: `col.dt.tz is None` raises with `rule="tz_aware_utc"`.
    // The TS analog: TimePoint's constructor rejects anything that isn't
    // a tz-aware ISO 8601 datetime (date-only, naive, unparseable, etc.).
    // Re-wrap any TimePoint constructor failure as SchemaValidationError
    // with the Python vocab so cross-SDK MCP consumers see the same
    // rule strings.
    let kt: TimePoint;
    try {
      kt = new TimePoint(raw);
    } catch (_err) {
      throw new SchemaValidationError(
        `assertNoLeakage requires tz-aware UTC knowledge_time; got ${JSON.stringify(raw)} at row ${i}`,
        {
          schemaId: RUNTIME_SCHEMA_ID,
          violations: [{ column: "knowledge_time", rule: "tz_aware_utc", row_idx: i }],
          quarantineCount: rows.length,
          sampleViolations: [{ column: "knowledge_time", rule: "tz_aware_utc", row_idx: i }],
        },
      );
    }
    const t = kt.toUTCDate().getTime();
    if (t > asOfMs) {
      // Re-emit knowledge_time in the Python isoformat shape so cross-
      // language MCP consumers see byte-equivalent strings.
      violations.push({ row_idx: i, knowledge_time: kt.toPythonIso() });
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

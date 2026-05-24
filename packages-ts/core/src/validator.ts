// validateRows — public schema validation API with Python-vocabulary
// violations + source-identity invariant.
//
// Mirrors `packages/core/src/tradewinds/core/validator.py`. The wire-vocab
// `violations[].rule` strings MUST match Python EXACTLY for cross-language
// MCP serialization parity. Vocabulary:
//   - unknown_schema_id
//   - source_attr_required
//   - source_column_required
//   - retrieved_at_required
//   - required_column_missing
//   - non_nullable_has_nulls
//   - mixed_null_sentinels
//   - dtype_mismatch
//   - enum_value_violation
//
// Check order (matches Python):
//   1. Schema lookup (unknown_schema_id)
//   2. allowSourceDrift type guard (TypeError / RangeError; loud)
//   3. Source attribute resolution (source_attr_required)
//   4. Per-row source-column check (SourceMismatchError)
//   5. retrievedAt resolution (retrieved_at_required)
//   6. Per-row ajv validation + mixed_null_sentinels scan

import { SchemaValidationError, SourceMismatchError } from "./exceptions/index.js";
import type { AjvErrorObject } from "./schemas/validators/index.js";
import { getValidator } from "./schemas/validators/index.js";

const SAMPLE_CAP = 10;

/**
 * Per-schema canonical source — mirrors Python `_registered_source` on
 * each Schema subclass (truth lives in
 * `packages/core/src/tradewinds/core/schemas/*.py`).
 *
 * Drift in this map produces silent cross-language source-identity
 * violations: a TS producer stamped `cli.archive` would falsely fail
 * the validator under the previous `iem.cli` mapping. Every entry below
 * MUST equal the `_registered_source: ClassVar[str]` on its Python peer.
 *
 * Iter-1 C2 fix: corrected `schema.settlement.cli.v1` (was `iem.cli`),
 * corrected `schema.forecast.iem_mos.v1` (was `iem.mos`), and added the
 * two catalog-internal schemas (`observation_ledger.v1`,
 * `observation_qc.v1`) — Python registers `iem.archive` for both.
 */
const SCHEMA_REGISTERED_SOURCE: Readonly<Record<string, string>> = Object.freeze({
  "schema.observation.v1": "iem.archive",
  "schema.settlement.cli.v1": "cli.archive",
  "schema.forecast.iem_mos.v1": "iem.archive",
  "schema.observation_ledger.v1": "iem.archive",
  "schema.observation_qc.v1": "iem.archive",
});

export interface ValidateOptions {
  /** Producer-stamped source string. Falls back to `rows[0].source` if absent. */
  readonly source?: string;
  /** Producer-stamped retrieval timestamp. Falls back to `rows[i].retrieved_at`. */
  readonly retrievedAt?: string;
  /** Non-empty reason string. Presence skips the source-identity check. */
  readonly allowSourceDrift?: string;
}

export interface ValidateResult {
  readonly rowCount: number;
  readonly source: string;
  readonly retrievedAt: string;
}

interface Violation {
  readonly rule: string;
  readonly column?: string;
  readonly row_idx?: number;
  readonly count?: number;
  readonly value?: unknown;
}

function mapAjvErrorToViolation(err: AjvErrorObject, rowIdx: number): Violation {
  const keyword = err.keyword;
  // Required-column violations bubble up the missing property name.
  if (keyword === "required") {
    const missing = (err.params as { missingProperty?: string }).missingProperty;
    if (typeof missing === "string") {
      return { rule: "required_column_missing", column: missing, row_idx: rowIdx };
    }
    return { rule: "required_column_missing", row_idx: rowIdx };
  }
  if (keyword === "type") {
    // For non-nullable nulls, ajv emits `type` violations when the value is
    // null and `null` is not in the allowed types. Differentiate from a
    // generic dtype mismatch by inspecting the value.
    const column = err.instancePath.replace(/^\//, "").replace(/\//g, ".");
    return {
      rule: "dtype_mismatch",
      column,
      row_idx: rowIdx,
    };
  }
  if (keyword === "enum") {
    const column = err.instancePath.replace(/^\//, "").replace(/\//g, ".");
    return {
      rule: "enum_value_violation",
      column,
      row_idx: rowIdx,
    };
  }
  // Unknown keyword — surface as dtype_mismatch with the inferred column.
  const column = err.instancePath.replace(/^\//, "").replace(/\//g, ".");
  if (column.length > 0) {
    return { rule: "dtype_mismatch", column, row_idx: rowIdx };
  }
  return { rule: "dtype_mismatch", row_idx: rowIdx };
}

function detectMixedNullSentinels(rows: ReadonlyArray<Record<string, unknown>>): string[] {
  // TS analog of Python's _has_mixed_null_sentinels (np.nan + pd.NA mix).
  // In TS we flag columns containing BOTH `null` and `undefined` (the two
  // missing-value sentinels native to JS — distinguishable but ambiguous
  // when serializers normalize them).
  const cols = new Map<string, { hasNull: boolean; hasUndef: boolean }>();
  for (const row of rows) {
    for (const [k, v] of Object.entries(row)) {
      const entry = cols.get(k) ?? { hasNull: false, hasUndef: false };
      if (v === null) entry.hasNull = true;
      if (v === undefined) entry.hasUndef = true;
      cols.set(k, entry);
    }
  }
  const mixed: string[] = [];
  for (const [k, e] of cols) {
    if (e.hasNull && e.hasUndef) mixed.push(k);
  }
  return mixed;
}

/**
 * Validate `rows` against the named canonical schema.
 *
 * Returns `{ rowCount, source, retrievedAt }` on success.
 *
 * Throws `SchemaValidationError` (with Python-vocabulary `violations[]`) on
 * structural / dtype / enum / required-column failures, OR
 * `SourceMismatchError` when per-row source identity drifts.
 *
 * @throws SchemaValidationError — see violations vocabulary in the module header.
 * @throws SourceMismatchError — per-row `source` column doesn't match resolved source.
 * @throws TypeError — `allowSourceDrift` is non-string.
 * @throws RangeError — `allowSourceDrift` is empty after trim.
 */
export function validateRows<Row extends Record<string, unknown> = Record<string, unknown>>(
  rows: ReadonlyArray<Row>,
  schemaId: string,
  opts: ValidateOptions = {},
): ValidateResult {
  // 1. Schema lookup
  const validate = getValidator(schemaId);
  if (validate == null) {
    throw new SchemaValidationError(`Unknown schema_id ${JSON.stringify(schemaId)}`, {
      schemaId,
      violations: [{ rule: "unknown_schema_id" }],
      quarantineCount: rows.length,
      sampleViolations: [],
    });
  }

  // 2. allowSourceDrift type guard
  if (opts.allowSourceDrift !== undefined) {
    if (typeof opts.allowSourceDrift !== "string") {
      throw new TypeError(
        `allowSourceDrift must be a non-empty reason string; got ${typeof opts.allowSourceDrift}`,
      );
    }
    if (opts.allowSourceDrift.trim().length === 0) {
      throw new RangeError(
        "allowSourceDrift must be a non-empty reason string (stripped whitespace)",
      );
    }
  }

  // 3. Source attribute resolution
  const firstRow = rows.length > 0 ? (rows[0] as Record<string, unknown>) : undefined;
  const resolvedSource =
    opts.source ?? (firstRow !== undefined ? (firstRow.source as string | undefined) : undefined);
  if (resolvedSource === undefined || resolvedSource === null) {
    throw new SchemaValidationError(
      "DataFrame missing source attribute; cannot validate source-identity",
      {
        schemaId,
        violations: [{ rule: "source_attr_required" }],
        quarantineCount: rows.length,
        sampleViolations: [],
      },
    );
  }

  // 3b. Source-identity invariant — opts.source vs canonical registered.
  const registeredSource = SCHEMA_REGISTERED_SOURCE[schemaId];
  if (
    registeredSource !== undefined &&
    resolvedSource !== registeredSource &&
    opts.allowSourceDrift === undefined
  ) {
    throw new SourceMismatchError(
      `Source drift: data is ${JSON.stringify(resolvedSource)}, schema expects ${JSON.stringify(registeredSource)}`,
      {
        schemaSource: registeredSource,
        dataSource: resolvedSource,
      },
    );
  }

  // 4. Per-row source-column check (when rows non-empty)
  if (rows.length > 0) {
    const hasSourceColumn = rows.some((r) => "source" in (r as object));
    if (!hasSourceColumn) {
      throw new SchemaValidationError(
        "Rows are missing the per-row 'source' overlay column required by canonical-schema producers.",
        {
          schemaId,
          violations: [{ column: "source", rule: "source_column_required" }],
          quarantineCount: rows.length,
          sampleViolations: [],
        },
      );
    }
    // Per-row mismatch check
    const badRows: Array<{ row_idx: number; source: unknown }> = [];
    for (let i = 0; i < rows.length; i++) {
      const r = rows[i] as Record<string, unknown>;
      const v = r.source;
      if (v == null || v !== resolvedSource) {
        badRows.push({ row_idx: i, source: v ?? null });
      }
    }
    if (badRows.length > 0) {
      const distinctBad = Array.from(
        new Set(badRows.map(({ source }) => (source == null ? "<null>" : String(source)))),
      ).slice(0, SAMPLE_CAP);
      throw new SourceMismatchError(
        `Per-row 'source' column has ${badRows.length} row(s) not matching resolved source=${JSON.stringify(resolvedSource)}; distinct bad values: ${JSON.stringify(distinctBad)}`,
        {
          schemaSource: resolvedSource,
          dataSource: distinctBad[0] ?? "<null>",
        },
      );
    }
  }

  // 5. retrievedAt resolution
  let resolvedRetrievedAt: string | undefined = opts.retrievedAt;
  if (resolvedRetrievedAt === undefined) {
    // Fall back to first row's retrieved_at field.
    const v = firstRow?.retrieved_at;
    if (typeof v === "string" && v.length > 0) resolvedRetrievedAt = v;
  }
  if (resolvedRetrievedAt === undefined) {
    throw new SchemaValidationError("Missing retrieved_at; cannot register validation", {
      schemaId,
      violations: [{ rule: "retrieved_at_required" }],
      quarantineCount: rows.length,
      sampleViolations: [],
    });
  }

  // 6. Per-row ajv validation + mixed_null_sentinels scan
  const violations: Violation[] = [];
  for (let i = 0; i < rows.length; i++) {
    const r = rows[i];
    const ok = validate(r);
    if (!ok && validate.errors != null) {
      // Detect non-nullable-with-null: ajv emits `type` keyword when null
      // hits a non-nullable property.
      for (const err of validate.errors) {
        const value = r as Record<string, unknown>;
        const column = err.instancePath.replace(/^\//, "");
        if (
          err.keyword === "type" &&
          value !== undefined &&
          column.length > 0 &&
          value[column] === null
        ) {
          violations.push({
            rule: "non_nullable_has_nulls",
            column,
            row_idx: i,
          });
        } else {
          violations.push(mapAjvErrorToViolation(err, i));
        }
        if (violations.length >= SAMPLE_CAP * 2) break;
      }
    }
  }

  // mixed_null_sentinels detection (column-wise)
  const mixedColumns = detectMixedNullSentinels(rows as ReadonlyArray<Record<string, unknown>>);
  for (const col of mixedColumns) {
    violations.push({ rule: "mixed_null_sentinels", column: col });
  }

  if (violations.length > 0) {
    throw new SchemaValidationError(
      `Schema validation failed with ${violations.length} violation(s) under ${schemaId}`,
      {
        schemaId,
        violations: violations as unknown as Array<Record<string, unknown>>,
        quarantineCount: rows.length,
        sampleViolations: violations.slice(0, SAMPLE_CAP) as unknown as Array<
          Record<string, unknown>
        >,
      },
    );
  }

  return {
    rowCount: rows.length,
    source: resolvedSource,
    retrievedAt: resolvedRetrievedAt,
  };
}

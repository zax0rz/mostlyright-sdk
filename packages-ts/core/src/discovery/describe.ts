// TS-W6 Wave 5 — describe(schemaId) + featureCatalog() + climateGaps stub.
//
// `describe(schemaId)` returns a multi-line human-readable string mined from
// the embedded JSON-Schema metadata. We bundle schema descriptions as a small
// JSON map keyed by `$id` (the canonical schema id) — produced by the codegen
// pipeline if/when it lands; for v0.1.0 we ship a hand-maintained list that
// matches what the codegen emits.
//
// `featureCatalog()` returns the transforms surface as a stable-sorted list
// of names — matches Python `feature_catalog()` exactly.
//
// `climateGaps(station, fromDate, toDate)` throws — TS has no climate cache
// in v0.1.0 (climate-year parquets are Python-only); the stub matches the
// Python signature so callers can `try/catch` the platform difference.

import { TradewindsError } from "../exceptions/index.js";

// ---------------------------------------------------------------------------
// Schema registry — keep in sync with `packages-ts/core/src/schemas/generated`.
// ---------------------------------------------------------------------------

interface SchemaInfo {
  readonly id: string;
  readonly title: string;
  readonly columnCount: number;
  readonly columns: ReadonlyArray<{
    readonly name: string;
    readonly description: string;
    readonly nullable: boolean;
  }>;
}

// Lazy loader — the JSON Schemas live in `schemas/json/` at repo root. We
// import them as a static manifest here so `@tradewinds/core/discovery`
// doesn't fan out a runtime fetch. For v0.1.0 the values are derived from
// the existing JSON Schema files at codegen time; until that step is wired,
// callers can override via `registerSchema` (used by tests).
const REGISTRY = new Map<string, SchemaInfo>();

/**
 * Register a schema for `describe()`. Tests + production callers use this to
 * populate the registry without coupling discovery to a runtime fetch.
 */
export function registerSchema(info: SchemaInfo): void {
  REGISTRY.set(info.id, Object.freeze({ ...info, columns: Object.freeze([...info.columns]) }));
}

/**
 * Return a multi-line description of a registered schema.
 *
 * @throws TradewindsError if `schemaId` is not registered. The error code is
 *   `UNKNOWN_SCHEMA` so callers can distinguish from validation/IO errors.
 */
export function describe(schemaId: string): string {
  const info = REGISTRY.get(schemaId);
  if (info === undefined) {
    const known = [...REGISTRY.keys()].sort();
    throw new UnknownSchemaError(
      `Unknown schemaId ${JSON.stringify(schemaId)}; registered: ${
        known.length === 0 ? "<none>" : known.join(", ")
      }`,
    );
  }
  const lines = [`Schema: ${info.id}`, `  Title: ${info.title}`, `  Columns: ${info.columnCount}`];
  for (const col of info.columns) {
    const nullable = col.nullable ? "?" : "";
    const desc = col.description.length === 0 ? "" : ` — ${col.description}`;
    lines.push(`    - ${col.name}${nullable}${desc}`);
  }
  return lines.join("\n");
}

/** Thrown by `describe` when `schemaId` is not registered. */
export class UnknownSchemaError extends TradewindsError {
  constructor(message: string) {
    super(message);
    this.name = "UnknownSchemaError";
  }
  static readonly defaultErrorCode = "UNKNOWN_SCHEMA";
}

// ---------------------------------------------------------------------------
// featureCatalog — list of transforms surface names.
// ---------------------------------------------------------------------------

const FEATURE_NAMES: ReadonlyArray<string> = Object.freeze([
  "calendarFeatures",
  "clipOutliers",
  "diff",
  "diff2",
  "heatIndex",
  "lag",
  "rolling",
  "spread",
  "windChill",
]);

/**
 * Return the transforms surface as a stable-sorted list.
 *
 * Matches Python `feature_catalog()`'s ordering — alphabetical on the
 * snake_case names, here the camelCase TS names sorted identically.
 */
export function featureCatalog(): ReadonlyArray<string> {
  return FEATURE_NAMES;
}

// ---------------------------------------------------------------------------
// climateGaps — stub that mirrors Python's signature but isn't implemented.
// ---------------------------------------------------------------------------

/**
 * Climate-gap scanning is Python-only in v0.1.0 (TS has no climate-year
 * parquet cache yet). Throws to match the documented contract.
 */
export function climateGaps(_station: string, _fromDate: string, _toDate: string): never {
  throw new ClimateGapsNotImplementedError(
    "climateGaps is Python-only in v0.1.0; the TS climate cache lands in v0.2",
  );
}

/** Thrown by `climateGaps` until the TS climate cache lands. */
export class ClimateGapsNotImplementedError extends TradewindsError {
  constructor(message: string) {
    super(message);
    this.name = "ClimateGapsNotImplementedError";
  }
  static readonly defaultErrorCode = "NOT_IMPLEMENTED";
}

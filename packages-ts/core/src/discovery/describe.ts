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

// Static manifest of the v0.1.0 schemas. Derived from `schemas/json/*.json`
// at repo root; baked in here so `@tradewinds/core/discovery` works in
// browsers (no `node:fs`) without a runtime fetch. The codegen pipeline
// would replace this hand-maintained list once it covers schema docs.
//
// Codex iter-1 P2: prior version left REGISTRY empty until callers ran
// `registerSchema()`, so `describe('schema.observation.v1')` always threw
// UNKNOWN_SCHEMA on a fresh import.
const BUILT_IN_SCHEMAS: ReadonlyArray<SchemaInfo> = Object.freeze([
  {
    id: "schema.observation.v1",
    title: "schema.observation.v1",
    columnCount: 20,
    columns: [
      { name: "dew_point_c", description: "units: celsius — bounded", nullable: true },
      { name: "event_time", description: "observation valid time", nullable: false },
      {
        name: "metar_raw",
        description: "raw METAR text if source has it; null for AWC JSON (structured-only)",
        nullable: true,
      },
      {
        name: "observation_type",
        description: "METAR | SPECI; defaults METAR when source can't distinguish (e.g. AWC JSON)",
        nullable: false,
      },
      {
        name: "precip_mm_1h",
        description: "units: mm — hourly precip (METAR p01i, converted from inches)",
        nullable: true,
      },
      {
        name: "sky_base_1_m",
        description: "units: meters — first cloud layer base height (converted from feet)",
        nullable: true,
      },
      { name: "sky_base_2_m", description: "units: meters", nullable: true },
      { name: "sky_base_3_m", description: "units: meters", nullable: true },
      { name: "sky_base_4_m", description: "units: meters", nullable: true },
      { name: "sky_cover_1", description: "first cloud layer cover code", nullable: true },
      { name: "sky_cover_2", description: "second layer; null if not present", nullable: true },
      { name: "sky_cover_3", description: "third layer; null if not present", nullable: true },
      { name: "sky_cover_4", description: "fourth layer; null if not present", nullable: true },
      {
        name: "slp_hpa",
        description:
          "units: hPa — sea-level pressure (canonical aviation unit, not converted across modes)",
        nullable: true,
      },
      { name: "station", description: "ICAO/ASOS station ID (e.g. KORD)", nullable: false },
      {
        name: "temp_c",
        description: "units: celsius — bounded TEMP_MIN_C..TEMP_MAX_C",
        nullable: true,
      },
      {
        name: "visibility_m",
        description: "units: meters — converted from statute miles",
        nullable: true,
      },
      {
        name: "wind_dir_deg",
        description: "units: degrees — 0-360, bounded",
        nullable: true,
      },
      { name: "wind_gust_ms", description: "units: m/s — converted from kt", nullable: true },
      { name: "wind_speed_ms", description: "units: m/s — converted from kt", nullable: true },
    ],
  },
  {
    id: "schema.forecast.iem_mos.v1",
    title: "schema.forecast.iem_mos.v1",
    columnCount: 11,
    columns: [
      { name: "dew_point_c", description: "units: celsius", nullable: true },
      {
        name: "forecast_hour",
        description: "units: hours — (valid_at - issued_at).total_seconds() / 3600",
        nullable: false,
      },
      {
        name: "issued_at",
        description: "model run time (from source `runtime` field)",
        nullable: false,
      },
      { name: "model", description: "e.g. NBE, GFS, LAV, MET", nullable: false },
      {
        name: "precip_probability",
        description: "units: probability — bounded [0, 1]",
        nullable: true,
      },
      {
        name: "sky_cover_pct",
        description: "units: percent — bounded [0, 100]",
        nullable: true,
      },
      { name: "station", description: "", nullable: false },
      { name: "temp_c", description: "units: celsius", nullable: true },
      {
        name: "valid_at",
        description: "forecast target time (from source `ftime`)",
        nullable: false,
      },
      { name: "wind_dir_deg", description: "units: degrees", nullable: true },
      { name: "wind_speed_ms", description: "units: m/s", nullable: true },
    ],
  },
  {
    id: "schema.settlement.cli.v1",
    title: "schema.settlement.cli.v1",
    columnCount: 12,
    columns: [
      {
        name: "cli_data_quality",
        description:
          "NWS CLI data-quality marker (Pitfall 6/16). Allows downstream code to filter or weight settlement rows by issuer quality without re-parsing the product header.",
        nullable: false,
      },
      {
        name: "event_time",
        description: "00:00 local time on observation_date converted to UTC; for sort/join only",
        nullable: false,
      },
      {
        name: "observation_date",
        description:
          "local climate day per NWS convention (no timezone applied to the date itself)",
        nullable: false,
      },
      { name: "precipitation_in", description: "units: inches", nullable: true },
      {
        name: "product_release_time",
        description: "parsed from CLI product header (_climate.py::_parse_product_timestamp)",
        nullable: false,
      },
      {
        name: "report_type",
        description:
          "preliminary | final | correction; dedup priority preliminary < final < correction",
        nullable: false,
      },
      {
        name: "settlement_finality",
        description:
          "provisional | final | superseded. Kalshi NHIGH/NLOW settlement contractually requires 'final'; 'provisional' values are kept for early-look research only.",
        nullable: false,
      },
      { name: "snowfall_in", description: "units: inches", nullable: true },
      { name: "station", description: "ICAO/ASOS station ID", nullable: false },
      {
        name: "station_tz",
        description:
          "IANA timezone for the station (e.g. America/Chicago for KORD). Required for local-climate-day semantics; see §U.",
        nullable: false,
      },
      {
        name: "temp_max_F",
        description:
          "units: fahrenheit — daily high (uppercase F for consistency with obs imperial mode)",
        nullable: true,
      },
      { name: "temp_min_F", description: "units: fahrenheit — daily low", nullable: true },
    ],
  },
  {
    id: "schema.observation_ledger.v1",
    title: "schema.observation_ledger.v1",
    columnCount: 15,
    columns: [
      { name: "as_of_time", description: "", nullable: true },
      { name: "dewpoint_c", description: "units: celsius", nullable: true },
      { name: "ingestion_id", description: "", nullable: true },
      { name: "observation_kind", description: "", nullable: true },
      {
        name: "observation_quality",
        description:
          "Lineage row-quality flag per LINEAGE-01; distinct from qc_status enum slot AND distinct from the obs_qc_status bitmask column per QC-05.",
        nullable: true,
      },
      { name: "observation_type", description: "", nullable: false },
      { name: "observed_at", description: "", nullable: false },
      { name: "parser_name", description: "", nullable: true },
      { name: "parser_version", description: "", nullable: true },
      { name: "provenance", description: "", nullable: true },
      { name: "qc_status", description: "", nullable: true },
      {
        name: "source",
        description: "ncei reserved per D-2.1-09; never written in v0.1.0.",
        nullable: false,
      },
      { name: "source_received_at", description: "", nullable: true },
      { name: "station_code", description: "", nullable: false },
      { name: "temp_c", description: "units: celsius", nullable: true },
    ],
  },
  {
    id: "schema.observation_qc.v1",
    title: "schema.observation_qc.v1",
    columnCount: 13,
    columns: [
      { name: "as_of_time", description: "", nullable: true },
      {
        name: "detector_metadata",
        description: "JSON-serialized detector payload; shape per qc_system.",
        nullable: true,
      },
      {
        name: "field",
        description: "Observation column the rule evaluated (e.g. temp_c).",
        nullable: false,
      },
      { name: "flag", description: "", nullable: false },
      { name: "ingestion_id", description: "", nullable: true },
      { name: "observation_kind", description: "", nullable: true },
      { name: "observed_at", description: "", nullable: false },
      { name: "parser_name", description: "", nullable: true },
      { name: "qc_system", description: "", nullable: false },
      { name: "qc_version", description: "", nullable: false },
      { name: "rule_id", description: "", nullable: false },
      { name: "source", description: "", nullable: false },
      { name: "station_code", description: "", nullable: false },
    ],
  },
]);

function deepFreezeSchema(info: SchemaInfo): SchemaInfo {
  const frozenCols = Object.freeze(info.columns.map((c) => Object.freeze({ ...c })));
  return Object.freeze({ ...info, columns: frozenCols });
}

const REGISTRY = new Map<string, SchemaInfo>(
  BUILT_IN_SCHEMAS.map((info) => [info.id, deepFreezeSchema(info)] as const),
);

/**
 * Register or override a schema for `describe()`. Built-in v0.1.0 schemas
 * are registered at module load (BUILT_IN_SCHEMAS); callers may add custom
 * schemas or override built-ins (e.g. with richer descriptions).
 */
export function registerSchema(info: SchemaInfo): void {
  REGISTRY.set(info.id, deepFreezeSchema(info));
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

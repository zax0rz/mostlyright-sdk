// IEM CLI daily climate report parser.
//
// Ported from `packages/weather/src/mostlyright/weather/_climate.py` —
// THE Kalshi settlement source. Report-type priority determines dedup:
// `final` (3.0) overwrites `preliminary` (1.0), but a second `final`
// never overwrites the first (strict `>`, first-seen wins at equal
// priority). The overnight `final` IS the Kalshi settlement value.
//
// `CLIMATE_REPORT_TYPE_PRIORITY` is consumed from `@mostlyrightmd/core`'s
// codegen output — do not re-define here.

import { CLIMATE_REPORT_TYPE_PRIORITY } from "@mostlyrightmd/core";

import type { CliRawRecord } from "../_fetchers/iem-cli.js";

/** Climate temp bounds from `specs/climate.json`. Inclusive. */
export const HIGH_TEMP_MIN_F = -60;
export const HIGH_TEMP_MAX_F = 150;
export const LOW_TEMP_MIN_F = -80;
export const LOW_TEMP_MAX_F = 130;

export type ReportType = "final" | "ncei_final" | "correction" | "preliminary" | "estimated";

export interface ClimateObservation {
  /** Station code (3-letter NWS or 4-letter ICAO, caller's choice). */
  station_code: string;
  /** Local climate day, YYYY-MM-DD. */
  observation_date: string;
  /** Daily high °F, rounded to int. `null` when missing or out-of-bounds. */
  high_temp_f: number | null;
  /** Daily low °F, rounded to int. `null` when missing or out-of-bounds. */
  low_temp_f: number | null;
  /** Inferred report type. */
  report_type: ReportType;
  /**
   * Numeric priority for dedup (final=3, ncei_final=2.5, correction=2,
   * preliminary=1, estimated=0). Sourced from
   * `CLIMATE_REPORT_TYPE_PRIORITY` in `@mostlyrightmd/core` codegen.
   */
  report_type_priority: number;
  /** Always `"iem"` for CLI records. */
  source: "iem";
  /** Raw NWS product identifier when present. */
  product_id: string | null;
  /** ISO 8601 UTC issuance time parsed from `product[:12]`, else `null`. */
  issued_at: string | null;
}

// Pre-compiled regexes — mirror Python's module-level `re.compile`.
const PRODUCT_TS_RE = /^(\d{12})/;
const DATE_RE = /^\d{4}-\d{2}-\d{2}$/;

/**
 * Parse the first-12-character product timestamp to a UTC `Date`.
 *
 * Format: `"202501160620-KFFC-CDUS42-CLIATL"` → `2025-01-16T06:20:00Z`.
 * Returns `null` for empty, malformed, or invalid calendar timestamps.
 */
function parseProductTimestamp(product: string): Date | null {
  if (!product) return null;
  const m = PRODUCT_TS_RE.exec(product);
  if (m === null) return null;
  const ts = m[1];
  if (ts === undefined) return null;
  const year = Number.parseInt(ts.slice(0, 4), 10);
  const month = Number.parseInt(ts.slice(4, 6), 10);
  const day = Number.parseInt(ts.slice(6, 8), 10);
  const hour = Number.parseInt(ts.slice(8, 10), 10);
  const minute = Number.parseInt(ts.slice(10, 12), 10);
  if (
    !Number.isFinite(year) ||
    !Number.isFinite(month) ||
    !Number.isFinite(day) ||
    !Number.isFinite(hour) ||
    !Number.isFinite(minute)
  ) {
    return null;
  }
  // Reject hour/minute out of range — `Date.UTC` would silently roll forward.
  if (month < 1 || month > 12 || day < 1 || day > 31 || hour > 23 || minute > 59) {
    return null;
  }
  const millis = Date.UTC(year, month - 1, day, hour, minute, 0, 0);
  if (!Number.isFinite(millis)) return null;
  const d = new Date(millis);
  // Round-trip check rejects e.g. "20250230" (Feb 30) silently rolling to Mar 2.
  if (
    d.getUTCFullYear() !== year ||
    d.getUTCMonth() !== month - 1 ||
    d.getUTCDate() !== day ||
    d.getUTCHours() !== hour ||
    d.getUTCMinutes() !== minute
  ) {
    return null;
  }
  return d;
}

/**
 * Parse an ISO date-only string ("YYYY-MM-DD") as a UTC `Date`. Returns
 * `null` if the string is missing/malformed or if the calendar date does
 * not exist (e.g. "2025-02-30"). Mirrors Python `date.fromisoformat`.
 */
function parseObservationDate(observationDate: string): Date | null {
  if (!DATE_RE.test(observationDate)) return null;
  const year = Number.parseInt(observationDate.slice(0, 4), 10);
  const month = Number.parseInt(observationDate.slice(5, 7), 10);
  const day = Number.parseInt(observationDate.slice(8, 10), 10);
  if (month < 1 || month > 12 || day < 1 || day > 31) return null;
  const millis = Date.UTC(year, month - 1, day);
  const d = new Date(millis);
  if (d.getUTCFullYear() !== year || d.getUTCMonth() !== month - 1 || d.getUTCDate() !== day) {
    return null;
  }
  return d;
}

/**
 * Infer report type from product timestamp vs observation date.
 *
 * Rules (byte-faithful port of Python `_climate.infer_report_type`):
 *  - No product → `"preliminary"` (safe default).
 *  - Unparseable product or observation date → `"preliminary"`.
 *  - Issued same day as observation → `"preliminary"`.
 *  - Issued the next day, 04:00–10:00 UTC → `"final"` (overnight CLI window).
 *  - Issued the next day outside that window → `"correction"`.
 *  - Issued >1 day later → `"correction"`.
 */
export function inferReportType(
  product: string | null | undefined,
  observationDate: string,
): ReportType {
  if (!product) return "preliminary";

  const issued = parseProductTimestamp(product);
  if (issued === null) return "preliminary";

  const obs = parseObservationDate(observationDate);
  if (obs === null) return "preliminary";

  // Compare issued *date* vs observation date in UTC days.
  const issuedDayUtc = Date.UTC(issued.getUTCFullYear(), issued.getUTCMonth(), issued.getUTCDate());
  const obsDayUtc = obs.getTime(); // already a UTC midnight from parseObservationDate
  const deltaDays = Math.round((issuedDayUtc - obsDayUtc) / 86_400_000);

  if (deltaDays <= 0) return "preliminary";
  if (deltaDays === 1) {
    const hour = issued.getUTCHours();
    if (hour >= 4 && hour <= 10) return "final";
    return "correction";
  }
  return "correction";
}

/** Parse a temperature sentinel into an integer °F or `null`. */
function parseTemp(val: unknown): number | null {
  if (val === null || val === undefined || val === "M" || val === "") return null;
  const n = typeof val === "number" ? val : Number(val);
  if (!Number.isFinite(n)) return null;
  // Python `round(float(val))` uses banker's rounding (round-half-to-even).
  // CLI temps are int-valued in practice (e.g. 45, -3); the sub-degree edge
  // case is rare enough that `Math.round` (half-up) matches expectations.
  return Math.round(n);
}

/**
 * Parse one IEM CLI record into a {@link ClimateObservation}.
 *
 * Returns `null` if:
 *  - `valid` is missing, non-string, or not a real calendar date, OR
 *  - **both** high and low end up `null` after bounds checks.
 *
 * Mirrors Python `parse_cli_record`.
 */
export function parseCliRecord(
  record: CliRawRecord,
  stationCode: string,
): ClimateObservation | null {
  const observationDate = record.valid;
  if (typeof observationDate !== "string" || observationDate.length === 0) return null;
  if (parseObservationDate(observationDate) === null) return null;

  let high = parseTemp(record.high);
  let low = parseTemp(record.low);

  if (high !== null && (high < HIGH_TEMP_MIN_F || high > HIGH_TEMP_MAX_F)) {
    high = null;
  }
  if (low !== null && (low < LOW_TEMP_MIN_F || low > LOW_TEMP_MAX_F)) {
    low = null;
  }

  if (high === null && low === null) return null;

  const product =
    typeof record.product === "string" && record.product.length > 0 ? record.product : null;

  const reportType = inferReportType(product, observationDate);
  const priority = CLIMATE_REPORT_TYPE_PRIORITY[reportType];
  // `priority` should always resolve — every ReportType is keyed in
  // CLIMATE_REPORT_TYPE_PRIORITY by construction. Guard for codegen drift.
  if (priority === undefined) {
    throw new Error(
      `report type ${JSON.stringify(reportType)} missing from CLIMATE_REPORT_TYPE_PRIORITY (codegen drift)`,
    );
  }

  let issuedAt: string | null = null;
  if (product !== null) {
    const issuedDt = parseProductTimestamp(product);
    if (issuedDt !== null) {
      // Format `YYYY-MM-DDTHH:MM:SSZ` to match Python's strftime output.
      issuedAt = `${issuedDt.toISOString().slice(0, 19)}Z`;
    }
  }

  return {
    station_code: stationCode,
    observation_date: observationDate,
    high_temp_f: high,
    low_temp_f: low,
    report_type: reportType,
    report_type_priority: priority,
    source: "iem",
    product_id: product,
    issued_at: issuedAt,
  };
}

/**
 * Parse a full IEM CLI response (post-unwrap) into climate observations,
 * filtering out records where both temps are missing or the date is
 * invalid. Mirrors Python `parse_cli_response`.
 */
export function parseCliResponse(
  data: ReadonlyArray<CliRawRecord>,
  stationCode: string,
): ReadonlyArray<ClimateObservation> {
  const out: ClimateObservation[] = [];
  for (const record of data) {
    const parsed = parseCliRecord(record, stationCode);
    if (parsed !== null) out.push(parsed);
  }
  return out;
}

// Backward-compat re-export. mergeClimate canonically lives at
// @mostlyrightmd/core/internal/merge as of TS-W2 Plan 04. Existing imports
// from @mostlyrightmd/weather continue to work; new code should prefer
// `import { mergeClimate } from "@mostlyrightmd/core/internal/merge"`.
export { mergeClimate } from "@mostlyrightmd/core/internal/merge";

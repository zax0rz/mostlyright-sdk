// Schema-derived bounds and validation helpers.
//
// Ported from `packages/core/src/tradewinds/_internal/_bounds.py`.
// Constants from specs/observation.json. Shared by AWC, GHCNh, and IEM parsers.

// Pressure bounds (observation.json: sea_level_pressure_mb)
export const SLP_MIN_MB = 870.0;
export const SLP_MAX_MB = 1084.0;

// Temperature bounds (°C). World records: -89.2°C (Vostok) / 56.7°C (Death Valley).
export const TEMP_MIN_C = -90.0;
export const TEMP_MAX_C = 60.0;

// String length limits
export const MAX_RAW_METAR_LEN = 2048;
export const MAX_WX_CODES_LEN = 256;

// Visibility (observation.json: visibility_miles max)
export const MAX_VISIBILITY_MILES = 99.99;

// Wind bounds (observation.json: wind_dir_degrees, wind_speed_kt, wind_gust_kt)
export const WIND_DIR_BOUNDS: readonly [number, number] = [0, 360];
export const WIND_SPEED_MAX = 200;
export const WIND_GUST_MAX = 250;

// Sky (observation.json: sky_base max)
export const SKY_BASE_MAX_FT = 60000;

// Year range for timestamp validation
export const MIN_YEAR = 1940;
export const MAX_YEAR = 2100;

// Station code regex — security boundary: codes flow into URL params and
// cache paths. Use ^...$ in TS (no multiline flag) so the absolute string
// ends are matched (equivalent to Python's `\A...\Z` here since `re.match`
// is anchored at start; we want anchored at both ends and no embedded
// newlines).
export const STATION_CODE_RE = /^[A-Z]{3,4}$/;

// GHCNh station identifier regex. NCEI uses two id flavours:
//   - ICAO-derived joined USAF-WBAN form, e.g. "744860-94789"
//   - 11-character NCEI station ids, alphanumeric
// Either way: alphanumeric + hyphen, length-bounded, anchored.
export const GHCNH_STATION_ID_RE = /^[A-Z0-9][A-Z0-9-]{0,31}$/;

// ---------------------------------------------------------------------------
// Bounded numerics
// ---------------------------------------------------------------------------

export function boundedInt(val: number | null, lo: number, hi: number): number | null {
  if (val === null || val === undefined) return null;
  if (!Number.isFinite(val)) return null;
  return val >= lo && val <= hi ? val : null;
}

export interface BoundedFloatOptions {
  /** Field name used for diagnostic logging (optional). */
  field?: string;
}

export function boundedFloat(
  val: number | null,
  lo: number,
  hi: number,
  _opts: BoundedFloatOptions = {},
): number | null {
  if (val === null || val === undefined) return null;
  if (!Number.isFinite(val)) return null;
  if (val >= lo && val <= hi) return val;
  return null;
}

export function boundedFloatMin(val: number | null, lo: number): number | null {
  if (val === null || val === undefined) return null;
  if (!Number.isFinite(val)) return null;
  return val >= lo ? val : null;
}

// ---------------------------------------------------------------------------
// Path-boundary validators
// ---------------------------------------------------------------------------

/**
 * Validate that `value` is a 3-4 letter uppercase ICAO/IATA code safe for
 * use as a URL parameter or filesystem path component. Throws `Error` on
 * mismatch — codes flow into URL params and cache paths, so any
 * path-separator character, whitespace, or non-ASCII char is rejected.
 */
export function validateIcaoForPath(value: unknown, field = "station"): string {
  if (typeof value !== "string") {
    throw new Error(
      `${field} must be a string (got ${typeof value}); unsafe to use in URL or cache path`,
    );
  }
  if (!STATION_CODE_RE.test(value)) {
    throw new Error(
      `${field}=${JSON.stringify(value)} does not match STATION_CODE_RE (3-4 uppercase letters); refusing to use as URL or path component`,
    );
  }
  return value;
}

/**
 * Validate that `value` is a GHCNh station identifier safe for URL/path use.
 * Accepts alphanumeric + hyphen, 1-32 chars, first char alphanumeric.
 */
export function validateGhcnhIdForPath(value: unknown, field = "station_id"): string {
  if (typeof value !== "string") {
    throw new Error(
      `${field} must be a string (got ${typeof value}); unsafe to use in URL or cache path`,
    );
  }
  if (!GHCNH_STATION_ID_RE.test(value)) {
    throw new Error(
      `${field}=${JSON.stringify(value)} does not match GHCNH_STATION_ID_RE (alphanumeric + hyphen, 1-32 chars); refusing to use as URL or path component`,
    );
  }
  return value;
}

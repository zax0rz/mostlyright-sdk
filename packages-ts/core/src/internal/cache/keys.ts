// Cache-key generators — pure functions producing the canonical key strings
// `cacheKeyForObservations(station, year, month)` and
// `cacheKeyForClimate(station, year)`. Matches the Python file-path zero-
// padded month/year scheme (Python: `01.parquet`, TS: `:01`).
//
// Station is upper-cased but NOT validated here (validation is the
// orchestrator's job; this module stays pure).

const MIN_YEAR = 1900;
const MAX_YEAR = 2100;

/**
 * Build the canonical observations cache key.
 *
 * Example: `cacheKeyForObservations("KNYC", 2025, 1)` →
 * `"tradewinds:v1:observations:KNYC:2025:01"`.
 */
export function cacheKeyForObservations(station: string, year: number, month: number): string {
  if (!Number.isInteger(year) || year < MIN_YEAR || year > MAX_YEAR) {
    throw new RangeError(`year out of range: ${year}`);
  }
  if (!Number.isInteger(month) || month < 1 || month > 12) {
    throw new RangeError(`month out of range: ${month}`);
  }
  const yyyy = String(year).padStart(4, "0");
  const mm = String(month).padStart(2, "0");
  return `tradewinds:v1:observations:${station.toUpperCase()}:${yyyy}:${mm}`;
}

/**
 * Build the canonical climate cache key (annual).
 *
 * Example: `cacheKeyForClimate("KNYC", 2025)` →
 * `"tradewinds:v1:climate:KNYC:2025"`.
 */
export function cacheKeyForClimate(station: string, year: number): string {
  if (!Number.isInteger(year) || year < MIN_YEAR || year > MAX_YEAR) {
    throw new RangeError(`year out of range: ${year}`);
  }
  const yyyy = String(year).padStart(4, "0");
  return `tradewinds:v1:climate:${station.toUpperCase()}:${yyyy}`;
}

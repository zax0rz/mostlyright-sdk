// Cache-key generators — pure functions producing the canonical key strings
// `cacheKeyForObservations(station, year, month)` and
// `cacheKeyForClimate(station, year)`. Matches the Python file-path zero-
// padded month/year scheme (Python: `01.parquet`, TS: `:01`).
//
// Station is upper-cased but NOT validated here (validation is the
// orchestrator's job; this module stays pure).
//
// iter-7 H13 / H14: an optional `source` segment was added to
// `cacheKeyForObservations` so the multi-source observations cache
// (IEM ASOS + GHCNh) does not collide on the same `(station, year, month)`
// triplet. Python writes one parquet per month containing the merged
// observations from all sources; the TS orchestrator caches per-source
// chunks pre-merge (because the fetchers are independent paths) and
// disambiguates with the source segment. Omitting `source` preserves the
// legacy 3-arg key shape — useful for tests that don't care about source
// (sentinel preloads, fixture replays) and matches the canonical
// Python-parity contract for callers that have already pre-merged sources.

const MIN_YEAR = 1900;
const MAX_YEAR = 2100;
const SOURCE_RE = /^[a-z0-9_-]+$/;

/**
 * Build the canonical observations cache key.
 *
 * Examples:
 *   `cacheKeyForObservations("KNYC", 2025, 1)` →
 *     `"tradewinds:v1:observations:KNYC:2025:01"`.
 *   `cacheKeyForObservations("KNYC", 2025, 1, "iem")` →
 *     `"tradewinds:v1:observations:KNYC:2025:01:iem"`.
 *
 * The `source` segment (optional, lowercase alphanumeric / hyphen /
 * underscore) namespaces per-source pre-merge chunks so IEM ASOS and
 * GHCNh writes for the same `(station, year, month)` do not collide.
 * Omit for back-compat (sentinel preloads, fixture replays).
 */
export function cacheKeyForObservations(
  station: string,
  year: number,
  month: number,
  source?: string,
): string {
  if (!Number.isInteger(year) || year < MIN_YEAR || year > MAX_YEAR) {
    throw new RangeError(`year out of range: ${year}`);
  }
  if (!Number.isInteger(month) || month < 1 || month > 12) {
    throw new RangeError(`month out of range: ${month}`);
  }
  const yyyy = String(year).padStart(4, "0");
  const mm = String(month).padStart(2, "0");
  const base = `tradewinds:v1:observations:${station.toUpperCase()}:${yyyy}:${mm}`;
  if (source === undefined) return base;
  if (typeof source !== "string" || !SOURCE_RE.test(source)) {
    throw new RangeError(
      `source must match ${SOURCE_RE.source} (lowercase alnum / hyphen / underscore); got ${JSON.stringify(source)}`,
    );
  }
  return `${base}:${source}`;
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

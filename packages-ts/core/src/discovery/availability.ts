// TS-W6 Wave 1 — availability(station, cache) reading from CacheStore.
//
// Ports Python `tradewinds.discovery.availability` semantics. Python walks the
// on-disk parquet hierarchy; TS uses the same canonical cache-key shape so the
// CacheStore implementation (Memory / IndexedDB / Fs) is the persistence layer.
//
// The keys we scan match `cacheKeyForObservations(station, year, month, source?)`
// and `cacheKeyForClimate(station, year)` — the Python file-path equivalents are
// `v1/observations/STATION/YYYY/MM.parquet` and `v1/climate/STATION/YYYY.parquet`.

import type { CacheStore } from "../internal/cache/index.js";

/**
 * Cache-coverage summary for a station.
 *
 * Mirrors Python `availability()` return shape.
 */
export interface AvailabilityResult {
  station: string;
  /** Count of distinct (year, month) observation cache entries. */
  monthsCached: number;
  /** Earliest cached month as `"YYYY-MM"`, or null if none. */
  firstMonth: string | null;
  /** Latest cached month as `"YYYY-MM"`, or null if none. */
  lastMonth: string | null;
  /** Count of cached climate years. */
  climateYears: number;
  /** Earliest cached climate year as `"YYYY"`, or null if none. */
  firstClimateYear: string | null;
  /** Latest cached climate year as `"YYYY"`, or null if none. */
  lastClimateYear: string | null;
}

/**
 * Optional adapter that lets `availability()` enumerate keys from a store.
 *
 * CacheStore's mandatory contract is opaque key-value: get/set/delete/withLock.
 * Discovery needs to enumerate which keys exist for a station — this is
 * implementation-specific (Memory iterates its Map, IndexedDB uses
 * `getAllKeys`, Fs walks the directory tree). Stores that support enumeration
 * implement the optional `listKeys(prefix)` method and `availability()` uses
 * it; stores without it return zero-coverage but never throw.
 *
 * Listed keys may exceed the requested prefix in the result (callers filter);
 * `listKeys` is best-effort.
 */
export interface KeyEnumerableStore extends CacheStore {
  listKeys(prefix: string): Promise<ReadonlyArray<string>>;
}

function hasListKeys(store: CacheStore): store is KeyEnumerableStore {
  return typeof (store as KeyEnumerableStore).listKeys === "function";
}

const STATION_RE = /^[A-Z0-9]{3,5}$/;

function normalizeStation(station: string): string {
  const upper = station.toUpperCase();
  if (!STATION_RE.test(upper)) {
    throw new RangeError(
      `availability: station must be a 3-5 char alphanumeric code; got ${JSON.stringify(station)}`,
    );
  }
  return upper;
}

const OBS_KEY_RE = /^tradewinds:v1:observations:([A-Z0-9]+):(\d{4}):(\d{2})(?::[a-z0-9_-]+)?$/;
const CLIMATE_KEY_RE = /^tradewinds:v1:climate:([A-Z0-9]+):(\d{4})$/;

/**
 * Return a summary of cached coverage for `station`.
 *
 * Stores without enumeration support return a zero-coverage result with the
 * station name populated (counts all zero, dates null).
 */
export async function availability(
  station: string,
  cache: CacheStore,
): Promise<AvailabilityResult> {
  const stationCode = normalizeStation(station);
  const empty: AvailabilityResult = Object.freeze({
    station: stationCode,
    monthsCached: 0,
    firstMonth: null,
    lastMonth: null,
    climateYears: 0,
    firstClimateYear: null,
    lastClimateYear: null,
  });

  if (!hasListKeys(cache)) {
    return empty;
  }

  const obsPrefix = `tradewinds:v1:observations:${stationCode}:`;
  const climatePrefix = `tradewinds:v1:climate:${stationCode}:`;

  const [obsKeys, climateKeys] = await Promise.all([
    cache.listKeys(obsPrefix),
    cache.listKeys(climatePrefix),
  ]);

  const months = new Set<string>();
  for (const key of obsKeys) {
    const m = OBS_KEY_RE.exec(key);
    if (m && m[1] === stationCode) {
      months.add(`${m[2]}-${m[3]}`);
    }
  }
  const sortedMonths = [...months].sort();

  const years = new Set<string>();
  for (const key of climateKeys) {
    const m = CLIMATE_KEY_RE.exec(key);
    if (m && m[1] === stationCode) {
      years.add(m[2] as string);
    }
  }
  const sortedYears = [...years].sort();

  return Object.freeze({
    station: stationCode,
    monthsCached: sortedMonths.length,
    firstMonth: sortedMonths[0] ?? null,
    lastMonth: sortedMonths.at(-1) ?? null,
    climateYears: sortedYears.length,
    firstClimateYear: sortedYears[0] ?? null,
    lastClimateYear: sortedYears.at(-1) ?? null,
  });
}

// TS-W6 Wave 1 — availability(station, cache) reading from CacheStore.
//
// Ports Python `tradewinds.discovery.availability` semantics. Python walks the
// on-disk parquet hierarchy; TS uses the same canonical cache-key shape so the
// CacheStore implementation (Memory / IndexedDB / Fs) is the persistence layer.
//
// The keys we scan match `cacheKeyForObservations(station, year, month, source?)`
// and `cacheKeyForClimate(station, year)`. @tradewinds/meta's `research()` writes
// cache entries under the 3-letter NWS code (`resolved.code` from
// STATION_BY_ICAO / STATION_BY_CODE) for US stations — e.g. `KNYC` resolves to
// `NYC` and the cache key reads `...:observations:NYC:...`. Codex iter-2 P2:
// availability resolves the input the same way so `availability("KNYC", cache)`
// finds entries written by `research("KNYC", ...)`.

import { STATION_BY_CODE, STATION_BY_ICAO } from "../data/generated/stations.js";
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

/**
 * Resolve `station` to the canonical CACHE-KEY station code.
 *
 * - For known stations: returns the 3-letter NWS `code` (e.g. `KNYC` → `NYC`)
 *   if one exists, falling back to the 4-letter ICAO. This matches the cache
 *   key that `research()` writes for US stations via `resolved.code` and
 *   international stations via `resolved.icao` (no NWS code exists).
 * - For unknown inputs that still satisfy the 3-5 char alphanumeric format:
 *   returns the upper-cased input. This lets bespoke callers query custom
 *   keys without coupling availability to the station registry.
 */
function normalizeStation(station: string): string {
  const upper = station.toUpperCase();
  if (!STATION_RE.test(upper)) {
    throw new RangeError(
      `availability: station must be a 3-5 char alphanumeric code; got ${JSON.stringify(station)}`,
    );
  }
  const byIcao = STATION_BY_ICAO.get(upper);
  if (byIcao !== undefined) {
    // US stations: NWS code is the cache-key form. International stations:
    // no NWS code, ICAO is the cache-key form.
    return byIcao.code ?? byIcao.icao;
  }
  const byCode = STATION_BY_CODE.get(upper);
  if (byCode !== undefined) {
    return byCode.code ?? byCode.icao;
  }
  // Bespoke / unknown codes — pass through. availability() returns
  // zero-coverage if the cache doesn't have entries under this exact key.
  return upper;
}

const OBS_KEY_RE = /^tradewinds:v1:observations:([A-Z0-9]+):(\d{4}):(\d{2})(?::[a-z0-9_-]+)?$/;
const CLIMATE_KEY_RE = /^tradewinds:v1:climate:([A-Z0-9]+):(\d{4})$/;

/**
 * Options for `availability()`.
 */
export interface AvailabilityOptions {
  /**
   * If true, confirm each candidate key with `cache.get()` before counting.
   * Eliminates the small overcount possible on stores whose `listKeys()` can
   * return keys with already-expired TTL entries (FsStore and IndexedDBStore
   * lazy-evict on `get`, not on `listKeys` — codex iter-3 P2). Off by default
   * because the v0.1.0 `research()` flow never writes with `ttlMs`, so the
   * overcount window is empty; turn on only if you populate the cache with
   * explicit TTLs.
   *
   * Cost: one `get()` per matching key. On warm caches this is cheap
   * (MemoryStore + IndexedDBStore in-memory). On FsStore it reads each
   * candidate's file.
   */
  readonly validate?: boolean;
}

/**
 * Return a summary of cached coverage for `station`.
 *
 * Stores without enumeration support return a zero-coverage result with the
 * station name populated (counts all zero, dates null).
 *
 * Pass `{ validate: true }` to confirm each candidate key via `cache.get()`
 * — needed if your callers populate the cache with `ttlMs` and might query
 * after expiry. The v0.1.0 `research()` flow does not use `ttlMs`, so the
 * default (fast scan, no validation) is correct for the canonical path.
 */
export async function availability(
  station: string,
  cache: CacheStore,
  opts: AvailabilityOptions = {},
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

  // Collect the matching keys grouped by (year-month) / year so we can both
  // dedupe (e.g. per-source observation keys for the same month) and run a
  // single validation get() per group.
  const monthCandidates = new Map<string, string[]>();
  for (const key of obsKeys) {
    const m = OBS_KEY_RE.exec(key);
    if (m && m[1] === stationCode) {
      const ym = `${m[2]}-${m[3]}`;
      const arr = monthCandidates.get(ym) ?? [];
      arr.push(key);
      monthCandidates.set(ym, arr);
    }
  }

  const yearCandidates = new Map<string, string[]>();
  for (const key of climateKeys) {
    const m = CLIMATE_KEY_RE.exec(key);
    if (m && m[1] === stationCode) {
      const y = m[2] as string;
      const arr = yearCandidates.get(y) ?? [];
      arr.push(key);
      yearCandidates.set(y, arr);
    }
  }

  let months: string[];
  let years: string[];

  if (opts.validate === true) {
    // For each candidate group, confirm at least one key still resolves.
    // Stores lazy-evict expired entries inside get() — calling it discards
    // stale TTLs from the on-disk / on-IDB state and gives us a correct
    // overall count.
    const monthChecks = await Promise.all(
      [...monthCandidates.entries()].map(async ([ym, keys]) => {
        for (const k of keys) {
          if ((await cache.get(k)) !== null) return ym;
        }
        return null;
      }),
    );
    months = monthChecks.filter((v): v is string => v !== null).sort();
    const yearChecks = await Promise.all(
      [...yearCandidates.entries()].map(async ([y, keys]) => {
        for (const k of keys) {
          if ((await cache.get(k)) !== null) return y;
        }
        return null;
      }),
    );
    years = yearChecks.filter((v): v is string => v !== null).sort();
  } else {
    months = [...monthCandidates.keys()].sort();
    years = [...yearCandidates.keys()].sort();
  }

  return Object.freeze({
    station: stationCode,
    monthsCached: months.length,
    firstMonth: months[0] ?? null,
    lastMonth: months.at(-1) ?? null,
    climateYears: years.length,
    firstClimateYear: years[0] ?? null,
    lastClimateYear: years.at(-1) ?? null,
  });
}

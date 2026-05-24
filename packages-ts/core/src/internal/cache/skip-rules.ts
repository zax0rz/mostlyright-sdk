// Cache-skip rule predicates — pure functions over inputs.
//
// Mirrors `packages/weather/src/tradewinds/weather/cache.py`:
//   - `_is_current_lst_month` / `_is_current_lst_year`
//   - `_is_live_source`
//
// Plus one TS-NEW addition required by TS-CACHE-02:
//   - `isWithinVolatileWindow` (30-day volatile-window check for archive
//     endpoints). Python's `cache.py` predates this rule; back-porting to
//     Python is tracked as a CROSS-SDK-SYNC parity ticket.
//
// All functions accept an optional `now: Date` test seam — production
// callers pass `new Date()` once at the call site (plan 06).

import { STATION_BY_CODE, STATION_BY_ICAO } from "../../data/generated/stations.js";
import { _lstOffsetHours } from "../../snapshot.js";

/** Resolve a station identifier (3-letter code OR 4-letter ICAO) to LST offset hours. */
function _lstOffsetHoursFor(station: string): number {
  const upper = station.trim().toUpperCase();
  const byCode = STATION_BY_CODE.get(upper);
  if (byCode !== undefined) return _lstOffsetHours(byCode.tz);
  const byIcao = STATION_BY_ICAO.get(upper);
  if (byIcao !== undefined) return _lstOffsetHours(byIcao.tz);
  if (upper.length === 4 && upper.startsWith("K")) {
    const stripped = upper.slice(1);
    const retry = STATION_BY_CODE.get(stripped);
    if (retry !== undefined) return _lstOffsetHours(retry.tz);
  }
  throw new RangeError(`unknown station: ${JSON.stringify(station)}`);
}

/**
 * Compute the station's current LST wall-clock as a UTC Date offset by the
 * LST hour shift. Use `getUTC*` to read fields (we already shifted the epoch).
 */
function _nowLst(station: string, now: Date = new Date()): Date {
  const offsetHours = _lstOffsetHoursFor(station);
  return new Date(now.getTime() + offsetHours * 3_600_000);
}

/**
 * True iff `(year, month)` is the current LST month for `station`.
 *
 * Mirrors Python `_is_current_lst_month`. The current month is mutable
 * (observations still arriving) — caching it would serve stale data.
 */
export function shouldSkipCacheForCurrentLstMonth(
  station: string,
  year: number,
  month: number,
  now?: Date,
): boolean {
  const lst = _nowLst(station, now);
  return lst.getUTCFullYear() === year && lst.getUTCMonth() + 1 === month;
}

/**
 * True iff `year` is the current LST year for `station`. Annual analog of
 * the monthly variant — gates the climate cache.
 */
export function shouldSkipCacheForCurrentLstYear(
  station: string,
  year: number,
  now?: Date,
): boolean {
  const lst = _nowLst(station, now);
  return lst.getUTCFullYear() === year;
}

/**
 * True iff `(year, month)` is a **strictly past** UTC month relative to
 * `now` — i.e. cacheable on the strictest possible temporal axis.
 *
 * iter-12 C14: `shouldSkipCacheForCurrentLstMonth` and `isMonthVolatile`
 * (lives in `meta/src/research.ts`) only catch the *current* LST month
 * and the immediate post-month volatile tail. Both predicates return
 * false for months that lie in the FUTURE relative to `now`, or for the
 * current UTC month when the station's LST is still in the prior UTC
 * month (negative tz offsets near UTC midnight). An empty / partial
 * fetch for such a month would be persisted and later served as
 * "complete." `isWritableMonth` is a stricter additional gate: it
 * requires the (year, month) to be lexicographically less than the
 * UTC current month, so neither future months nor the partial current
 * UTC month are ever cacheable — regardless of any station's LST.
 *
 * Mirrors Python `cache.py:_is_current_lst_month`'s implicit invariant
 * (Python paths use parquet-on-disk which can't be written for future
 * dates because the cache root never spawns those years). TS callers
 * MUST gate cache reads AND writes on this predicate before applying
 * the LST / volatile-window gates.
 */
export function isWritableMonth(year: number, month: number, now: Date): boolean {
  const nowYear = now.getUTCFullYear();
  const nowMonth = now.getUTCMonth() + 1; // 1-12
  if (year < nowYear) return true;
  if (year > nowYear) return false;
  return month < nowMonth;
}

/**
 * True iff `year` is a **strictly past** UTC year relative to `now` —
 * the annual analog of `isWritableMonth`.
 *
 * iter-12 C15: `shouldSkipCacheForCurrentLstYear` only catches the
 * current LST year. It misses (a) future years, which would silently
 * cache empty/incomplete data, and (b) the UTC Jan-1 boundary window
 * where the station's LST is still in the prior calendar year (negative
 * tz offsets) but the UTC year has already rolled over — without this
 * gate the new UTC year, which is mutable, could be written. Stricter
 * additional gate: require `year < now.getUTCFullYear()`. TS callers
 * MUST gate cache reads AND writes on this predicate before applying
 * the LST / volatile-window gates.
 */
export function isWritableYear(year: number, now: Date): boolean {
  return year < now.getUTCFullYear();
}

/**
 * True iff `source` ends with `.live`.
 *
 * Mirrors Python `_is_live_source` byte-equivalently — accepts null /
 * undefined / empty (returns false in all three cases).
 */
export function isLiveSource(source: string | null | undefined): boolean {
  return typeof source === "string" && source.length > 0 && source.endsWith(".live");
}

/**
 * **TS-NEW** addition per TS-CACHE-02: archive endpoints within `days` days
 * of `archiveAsOf` are treated as volatile (some sources amend their
 * published data for ~30 days post-event). NOT a Python port today — file
 * a CROSS-SDK-SYNC parity ticket if Python adopts it.
 *
 * Returns true iff `eventDate` falls within `[archiveAsOf - days, archiveAsOf]`
 * (inclusive at both endpoints — an event exactly `days` days before
 * `archiveAsOf` is still volatile and MUST be re-fetched).
 *
 * Events AFTER `archiveAsOf` are never volatile by this rule (deltaDays < 0).
 */
export function isWithinVolatileWindow(eventDate: string, archiveAsOf: string, days = 30): boolean {
  const e = Date.parse(`${eventDate}T00:00:00Z`);
  const a = Date.parse(`${archiveAsOf}T00:00:00Z`);
  if (!Number.isFinite(e) || !Number.isFinite(a)) {
    throw new RangeError(
      `invalid YYYY-MM-DD: eventDate=${JSON.stringify(eventDate)} archiveAsOf=${JSON.stringify(archiveAsOf)}`,
    );
  }
  const deltaDays = (a - e) / 86_400_000;
  return deltaDays >= 0 && deltaDays <= days;
}

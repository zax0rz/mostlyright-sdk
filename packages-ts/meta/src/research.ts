// `research()` orchestrator — TS-W2 multi-source Mode 1 join.
//
// Wires all four observation sources (AWC live, IEM ASOS archive, GHCNh
// archive, IEM CLI climate) into the canonical `PairsRow` shape via
// mergeObservations + mergeClimate + buildPairs. Mode 1 only — all
// `fcst_*` columns are unconditionally null in this phase.
//
// Lives in `packages-ts/meta/` so `@tradewinds/core` stays dep-free; this
// orchestrator imports from both core (snapshot math + station table +
// merge + pairs) and weather (4 fetchers + 4 parsers).
//
// W2 scope: AWC + IEM ASOS + GHCNh + CLI; no cache (TS-W3), no Mode 2
// (TS-W4), no forecast (TS-W5+), no parallel prefetch (TS-W3+). Fetches
// are sequential — fine for the parity gate; performance work is later.

import { STATION_BY_CODE, STATION_BY_ICAO, settlementDateFor } from "@tradewinds/core";
import {
  type CacheStore,
  cacheKeyForClimate,
  cacheKeyForObservations,
  defaultCacheStore,
  isLiveSource,
  shouldSkipCacheForCurrentLstMonth,
  shouldSkipCacheForCurrentLstYear,
} from "@tradewinds/core/internal/cache";
import { mergeClimate, mergeObservations } from "@tradewinds/core/internal/merge";
import {
  type PairsClimateLike,
  type PairsObservationLike,
  type PairsRow,
  buildPairs,
} from "@tradewinds/core/internal/pairs";
import {
  type ClimateObservation,
  type Observation,
  awcToObservation,
  downloadCliRange,
  downloadGhcnhRange,
  downloadIemAsos,
  fetchAwcMetars,
  parseCliResponse,
  parseGhcnhPsv,
  parseIemCsv,
} from "@tradewinds/weather";

// Re-export PairsRow so callers can `import { research, type PairsRow } from "tradewinds"`.
export type { PairsRow } from "@tradewinds/core/internal/pairs";

const AWC_MAX_HOURS = 168;

// ---------------------------------------------------------------------------
// Public types
// ---------------------------------------------------------------------------

export interface ResearchOptions {
  /** Forward to all underlying fetchers; aborts the whole pipeline. */
  signal?: AbortSignal;
  /** AWC lookback window in hours. Default 168 (AWC max). Clamped by the fetcher. */
  awcHours?: number;
  /** Polite-delay (ms) between successive IEM ASOS year chunks. Default 1000. */
  iemPolitenessMs?: number;
  /** Polite-delay (ms) between successive GHCNh year requests. Default 1000. */
  ghcnhPolitenessMs?: number;
  /** Polite-delay (ms) between successive CLI year requests. Default 1000. */
  cliPolitenessMs?: number;
  /**
   * Reference clock for the AWC-window overlap check (test-only seam).
   * Defaults to `new Date()`. Pass an override to force-include AWC for
   * historical date ranges in unit tests.
   */
  now?: Date;
  /**
   * Pluggable cache backend (TS-W3). When omitted, uses
   * `defaultCacheStore()` (auto-detects IndexedDB → FsStore → MemoryStore).
   * Pass `null` to opt out of caching entirely.
   */
  cache?: CacheStore | null;
}

/** Resolve the cache from opts. `null` means opt-out (returns null). */
function resolveCache(opts: ResearchOptions): CacheStore | null {
  if (opts.cache === null) return null;
  return opts.cache ?? defaultCacheStore();
}

// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------

const DATE_RE = /^\d{4}-\d{2}-\d{2}$/;

interface ResolvedStation {
  readonly code: string;
  readonly icao: string;
  readonly tz: string;
  readonly country: string | null;
  readonly ghcnhId: string | null;
}

function normalizeStation(input: string): ResolvedStation {
  const raw = input.trim().toUpperCase();
  if (raw.length === 0) {
    throw new Error("station must be a non-empty string");
  }
  const byIcao = STATION_BY_ICAO.get(raw);
  if (byIcao !== undefined) {
    if (byIcao.code === null) {
      throw new Error(`station ${JSON.stringify(raw)} has no 3-letter NWS code`);
    }
    return {
      code: byIcao.code,
      icao: byIcao.icao,
      tz: byIcao.tz,
      country: byIcao.country,
      ghcnhId: byIcao.ghcnh_id,
    };
  }
  const byCode = STATION_BY_CODE.get(raw);
  if (byCode !== undefined) {
    if (byCode.code === null) {
      throw new Error(`station ${JSON.stringify(raw)} has no 3-letter NWS code`);
    }
    return {
      code: byCode.code,
      icao: byCode.icao,
      tz: byCode.tz,
      country: byCode.country,
      ghcnhId: byCode.ghcnh_id,
    };
  }
  if (raw.startsWith("K") && raw.length === 4) {
    const stripped = raw.slice(1);
    const retry = STATION_BY_CODE.get(stripped);
    if (retry !== undefined && retry.code !== null) {
      return {
        code: retry.code,
        icao: retry.icao,
        tz: retry.tz,
        country: retry.country,
        ghcnhId: retry.ghcnh_id,
      };
    }
  }
  throw new Error(
    `unknown station ${JSON.stringify(input)} — not found in STATION_BY_CODE or STATION_BY_ICAO`,
  );
}

function parseIsoDate(s: string): Date {
  if (!DATE_RE.test(s)) {
    throw new Error(`expected YYYY-MM-DD, got ${JSON.stringify(s)}`);
  }
  const [yStr, mStr, dStr] = s.split("-");
  const year = Number(yStr);
  const month = Number(mStr);
  const day = Number(dStr);
  const ms = Date.UTC(year, month - 1, day);
  const d = new Date(ms);
  if (d.getUTCFullYear() !== year || d.getUTCMonth() !== month - 1 || d.getUTCDate() !== day) {
    throw new Error(`invalid calendar date ${JSON.stringify(s)}`);
  }
  return d;
}

function formatDate(d: Date): string {
  const y = d.getUTCFullYear();
  const m = d.getUTCMonth() + 1;
  const day = d.getUTCDate();
  const mm = m < 10 ? `0${m}` : `${m}`;
  const dd = day < 10 ? `0${day}` : `${day}`;
  return `${y}-${mm}-${dd}`;
}

function buildDateList(fromDate: string, toDate: string): ReadonlyArray<string> {
  const from = parseIsoDate(fromDate);
  const to = parseIsoDate(toDate);
  if (from.getTime() > to.getTime()) {
    throw new Error(`fromDate (${fromDate}) must be <= toDate (${toDate})`);
  }
  const dates: string[] = [];
  for (let cursor = from.getTime(); cursor <= to.getTime(); cursor += 24 * 3_600_000) {
    dates.push(formatDate(new Date(cursor)));
  }
  return dates;
}

/** Plus-one-day in UTC. Used to extend the upper bound so the final LST
 *  settlement window's pre-midnight UTC tail observations are captured. */
function plusOneDay(isoDate: string): string {
  const d = parseIsoDate(isoDate);
  return formatDate(new Date(d.getTime() + 24 * 3_600_000));
}

/** US stations only — GHCNh PSV archive is US-only. International stations
 *  have `ghcnh_id: null` AND `country !== "US"` in the TS codegen. */
function isUsStation(station: ResolvedStation): boolean {
  return station.country === "US";
}

/** Returns true if any date in `[fromDate, toDate]` is within `hours` of `now`.
 *  Mirrors Python `_month_overlaps_awc_window` semantics — defensive
 *  short-circuit so we don't hit AWC for purely historical windows. */
function anyDateOverlapsAwc(toDate: string, hours: number, now: Date): boolean {
  const to = parseIsoDate(toDate);
  // Window includes the END of toDate (LST close), so add 24h to the upper bound.
  const toEndMs = to.getTime() + 24 * 3_600_000;
  const nowMs = now.getTime();
  const cutoffMs = nowMs - hours * 3_600_000;
  return toEndMs >= cutoffMs;
}

function observedSettlementDate(observedAt: string, station: string): string | null {
  const ms = Date.parse(observedAt);
  if (!Number.isFinite(ms)) return null;
  try {
    return settlementDateFor(new Date(ms), station);
  } catch {
    return null;
  }
}

/** Lexicographic-on-`observed_at` sort, stable in `source`. Ensures
 *  byte-equivalent float aggregation in `_obsAggregates` (mean is
 *  non-associative for floats). */
function sortByObservedAtThenSource(rows: ReadonlyArray<Observation>): Observation[] {
  return [...rows].sort((a, b) => {
    if (a.observed_at < b.observed_at) return -1;
    if (a.observed_at > b.observed_at) return 1;
    if (a.source < b.source) return -1;
    if (a.source > b.source) return 1;
    return 0;
  });
}

/**
 * Fetch CLI climate per-year with read-through cache. Yearly chunks are
 * cached at `cacheKeyForClimate(code, year)`. Skip rules:
 *   - Current LST year — mutable, never cached.
 *   - Live source (`.live`) — never cached (CLI is archive `iem.cli` →
 *     this never fires today; defensive for future).
 */
async function fetchCliWithCache(
  fetchIcao: string,
  cacheCode: string,
  fromYear: number,
  toYear: number,
  opts: ResearchOptions,
  cache: CacheStore | null,
  now: Date,
): Promise<ClimateObservation[]> {
  const acc: ClimateObservation[] = [];
  for (let year = fromYear; year <= toYear; year++) {
    const skip = shouldSkipCacheForCurrentLstYear(cacheCode, year, now);
    if (cache !== null && !skip) {
      const cached = await cache.get<ClimateObservation[]>(cacheKeyForClimate(cacheCode, year));
      if (cached !== null) {
        acc.push(...cached);
        continue;
      }
    }
    const cliOpts: { signal?: AbortSignal; politenessMs?: number } = {};
    if (opts.signal !== undefined) cliOpts.signal = opts.signal;
    if (opts.cliPolitenessMs !== undefined) cliOpts.politenessMs = opts.cliPolitenessMs;
    const cliRaw = await downloadCliRange(fetchIcao, year, year, cliOpts);
    const parsed = parseCliResponse(cliRaw, cacheCode);
    acc.push(...parsed);
    // Write-through: cache only when (1) backend present, (2) skip permits,
    // (3) source isn't `.live` (defensive — iem.cli is archive). All parsed
    // rows share the same `source`; sample the first.
    const sample = parsed[0]?.source;
    if (cache !== null && !skip && !isLiveSource(sample)) {
      await cache.set(cacheKeyForClimate(cacheCode, year), parsed);
    }
  }
  return acc;
}

/** Fetch IEM ASOS observations per-year with read-through cache. */
async function fetchIemAsosWithCache(
  stationCode: string,
  fromYear: number,
  extendedToYear: number,
  fromDate: string,
  extendedTo: string,
  opts: ResearchOptions,
  cache: CacheStore | null,
  now: Date,
): Promise<Observation[]> {
  const acc: Observation[] = [];
  for (let year = fromYear; year <= extendedToYear; year++) {
    for (const reportType of [3, 4] as const) {
      // Year-granularity cache key (we don't have a yearly key generator;
      // re-use the observations key with month=01 as the year-sentinel and
      // a report-type-specific suffix encoded into the station).
      const cacheKey = `${cacheKeyForObservations(stationCode, year, 1)}:rt=${reportType}`;
      // Skip when the year contains the current LST year (annual granularity
      // for the year-grained cache — conservative; the per-month rule fires
      // at the cache-key level where Python's per-month observations cache
      // lives).
      const skipCurrentMonth = shouldSkipCacheForCurrentLstYear(stationCode, year, now);

      let yearRows: Observation[] | null = null;
      if (cache !== null && !skipCurrentMonth) {
        const cached = await cache.get<Observation[]>(cacheKey);
        if (cached !== null) yearRows = cached;
      }
      if (yearRows === null) {
        const iemOpts: { reportType: 3 | 4; politenessMs: number; signal?: AbortSignal } = {
          reportType,
          politenessMs: opts.iemPolitenessMs ?? 1000,
        };
        if (opts.signal !== undefined) iemOpts.signal = opts.signal;
        const chunks = await downloadIemAsos(
          stationCode,
          `${year}-01-01`,
          `${year}-12-31`,
          iemOpts,
        );
        const fetched: Observation[] = [];
        for (const chunk of chunks) {
          const parsed = parseIemCsv(chunk.csv, {
            observationTypeOverride: reportType === 3 ? "METAR" : "SPECI",
          });
          fetched.push(...parsed);
        }
        yearRows = fetched;
        const sample = fetched[0]?.source;
        if (cache !== null && !skipCurrentMonth && !isLiveSource(sample)) {
          await cache.set(cacheKey, fetched);
        }
      }
      for (const obs of yearRows) {
        const obsDate = obs.observed_at.slice(0, 10);
        if (obsDate >= fromDate && obsDate <= extendedTo) acc.push(obs);
      }
    }
  }
  return acc;
}

// ---------------------------------------------------------------------------
// Public surface
// ---------------------------------------------------------------------------

/**
 * Build daily research rows for a station + date window.
 *
 * @param station NWS 3-letter code (e.g. "NYC") OR 4-letter ICAO (e.g. "KNYC").
 * @param fromDate Inclusive start date, ISO YYYY-MM-DD (LST).
 * @param toDate Inclusive end date, ISO YYYY-MM-DD (LST).
 * @param opts See {@link ResearchOptions}.
 *
 * Returns an immutable array of frozen {@link PairsRow}s — one per LST day
 * in `[fromDate, toDate]`. Each row carries:
 *  - `cli_*` populated from IEM CLI (final preferred per `mergeClimate`).
 *  - `obs_*` daily aggregates over the 3-source merged observations
 *    (AWC > IEM > GHCNh per `mergeObservations`).
 *  - `fcst_*` unconditionally null (Mode 1).
 *  - `market_close_utc` formatted `YYYY-MM-DDTHH:MM:SSZ`.
 *
 * Throws on unknown station, malformed dates, or fromDate > toDate.
 * AbortSignal propagates from underlying fetchers.
 */
export async function research(
  station: string,
  fromDate: string,
  toDate: string,
  opts: ResearchOptions = {},
): Promise<ReadonlyArray<PairsRow>> {
  const resolved = normalizeStation(station);
  const dates = buildDateList(fromDate, toDate);
  const extendedTo = plusOneDay(toDate);

  const fromYear = Number(fromDate.slice(0, 4));
  const toYear = Number(toDate.slice(0, 4));
  const extendedToYear = Number(extendedTo.slice(0, 4));

  const baseOpts: { signal?: AbortSignal } = {};
  if (opts.signal !== undefined) baseOpts.signal = opts.signal;

  const cache = resolveCache(opts);
  const cacheNow = opts.now ?? new Date();

  // --- IEM CLI climate (per-year) ---------------------------------------
  // Cache strategy: read-through per (station code, year). Skip the current
  // LST year (mutable) and never cache `.live` sources. `iem.cli` is
  // archive → cacheable for completed years. Fetcher takes the ICAO
  // (resolved.icao), cache key uses the 3-letter NWS code (resolved.code).
  let mergedClimate: ReadonlyArray<ClimateObservation> = [];
  try {
    const cliRows = await fetchCliWithCache(
      resolved.icao,
      resolved.code,
      fromYear,
      toYear,
      opts,
      cache,
      cacheNow,
    );
    mergedClimate = mergeClimate(cliRows);
  } catch (err) {
    if (err instanceof DOMException && (err.name === "AbortError" || err.name === "TimeoutError")) {
      throw err;
    }
    // Degrade to no CLI data — buildPairs emits null cli_* for affected dates.
  }

  // --- AWC live observations (short-circuit on stale windows) -----------
  const awcHours = opts.awcHours ?? AWC_MAX_HOURS;
  const awcRows: Observation[] = [];
  if (anyDateOverlapsAwc(toDate, awcHours, opts.now ?? new Date())) {
    const awcOpts: { hours: number; signal?: AbortSignal } = { hours: awcHours };
    if (opts.signal !== undefined) awcOpts.signal = opts.signal;
    const awcRaw = await fetchAwcMetars([resolved.icao], awcOpts);
    for (const m of awcRaw) {
      const obs = awcToObservation(m);
      if (obs !== null) awcRows.push(obs);
    }
  }

  // --- IEM ASOS archive observations (per-year × {METAR, SPECI}) --------
  // IEM ASOS expects the 3-letter NWS station code (`station=NYC`),
  // NOT the 4-letter ICAO. Python `_fetchers/iem_asos.py:119` uses
  // `station={station.code}`. Use resolved.code, NOT resolved.icao.
  const iemRows = await fetchIemAsosWithCache(
    resolved.code,
    fromYear,
    extendedToYear,
    fromDate,
    extendedTo,
    opts,
    cache,
    cacheNow,
  );

  // --- GHCNh archive observations (US stations only) --------------------
  const ghcnhRows: Observation[] = [];
  if (isUsStation(resolved) && resolved.ghcnhId !== null && resolved.ghcnhId.length > 0) {
    const ghcnhOpts: { politenessMs: number; signal?: AbortSignal } = {
      politenessMs: opts.ghcnhPolitenessMs ?? 1000,
    };
    if (opts.signal !== undefined) ghcnhOpts.signal = opts.signal;
    const years = await downloadGhcnhRange(resolved.ghcnhId, fromYear, extendedToYear, ghcnhOpts);
    for (const yr of years) {
      const parsed = parseGhcnhPsv(yr.psv);
      for (const obs of parsed) {
        const obsDate = obs.observed_at.slice(0, 10);
        if (obsDate >= fromDate && obsDate <= extendedTo) ghcnhRows.push(obs);
      }
    }
  }

  // --- Merge observations + bucket by settlement date -------------------
  const combinedRaw = [...awcRows, ...iemRows, ...ghcnhRows];
  const sorted = sortByObservedAtThenSource(combinedRaw);
  const merged = mergeObservations(sorted);

  const observationsByDate: Record<string, PairsObservationLike[]> = {};
  // dates is guaranteed non-empty by buildDateList contract (throws on
  // fromDate > toDate; both validated above).
  const dateLo = dates[0] ?? "";
  const dateHi = dates[dates.length - 1] ?? "";
  for (const obs of merged) {
    const settleDate = observedSettlementDate(obs.observed_at, resolved.code);
    if (settleDate === null) continue;
    if (settleDate < dateLo || settleDate > dateHi) continue;
    let bucket = observationsByDate[settleDate];
    if (bucket === undefined) {
      bucket = [];
      observationsByDate[settleDate] = bucket;
    }
    bucket.push(obs);
  }

  // --- Bucket climate by date (mergeClimate already deduped) ------------
  const climateByDate: Record<string, PairsClimateLike | null> = {};
  for (const cli of mergedClimate) {
    climateByDate[cli.observation_date] = cli;
  }

  // --- buildPairs join + return -----------------------------------------
  return buildPairs(resolved.code, dates, observationsByDate, climateByDate);
}

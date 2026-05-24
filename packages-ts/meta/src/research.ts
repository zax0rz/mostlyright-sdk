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

import {
  NotFoundError,
  STATION_BY_CODE,
  STATION_BY_ICAO,
  settlementDateFor,
} from "@tradewinds/core";
import {
  type CacheStore,
  cacheKeyForClimate,
  cacheKeyForObservations,
  defaultCacheStore,
  isLiveSource,
  isWithinVolatileWindow,
  isWritableMonth,
  isWritableYear,
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
  downloadGhcnh,
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

  // ── Phase 10: composable selectors (mutually exclusive with station). ──
  //
  // Per the Phase 10 v0.2 scope, the validation surface is shipped on
  // both Python and TS; the multi-station / multi-issuer JOIN +
  // trade-attachment is deferred to v0.3. Passing any of the three
  // selectors below currently throws a clear NotImplementedError-like
  // error pointing callers at `discover()` + the station= path until
  // v0.3 lands.

  /** Cross-issuer city selector. Returns rows for every station that any
   *  issuer settles against (Kalshi + Polymarket + denylist backstops). */
  city?: string;
  /** Single-contract selector. Format: `"<issuer>:<id>"` (e.g.
   *  `"kalshi:KXHIGHNYC-25MAY26-T79"`). Auto-resolves to the contract's
   *  canonical settlement station via the Phase 8 catalog. */
  contract?: string;
  /** Multi-contract selector for basis-trade research. */
  contracts?: ReadonlyArray<string>;
  /** Override the contract's canonical settlement station. Emits a
   *  StationOverrideWarning via `onWarning?`; output row carries
   *  `settlementMismatch: true`. Only valid with `contract` selector. */
  stationOverride?: string;
  /** Mode 1 source subset — dedupe within. Mutually exclusive with `source`. */
  sources?: ReadonlyArray<string>;
  /** Mode 2 single-source pin — error on mismatch. Mutually exclusive with `sources`. */
  source?: string;
  /** Attach per-issuer trade timeseries via @tradewinds/markets/trades.
   *  Requires `contract` or `contracts`. */
  includeTrades?: boolean;
  /** Callback receiving Phase 10 StationOverrideWarning (no `warnings.warn()`
   *  analogue in JS). */
  onWarning?: (w: import("./compose.js").StationOverrideWarning) => void;
}

/**
 * Resolve the cache from opts. `null` means opt-out (returns null).
 *
 * Iter-1 H3: `defaultCacheStore()` is now async (FsStore loaded via
 * dynamic import behind a Node feature-detect). Caller already runs
 * inside `research()`'s async path, so awaiting here is free.
 */
async function resolveCache(opts: ResearchOptions): Promise<CacheStore | null> {
  if (opts.cache === null) return null;
  if (opts.cache !== undefined) return opts.cache;
  return await defaultCacheStore();
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
 * True iff the end-of-year ISO date for `year` falls inside the 30-day
 * volatile amendment window relative to `now`. Used to gate archive
 * cache reads/writes for IEM ASOS yearly chunks AND IEM CLI yearly
 * chunks (iter-5 H9). Rationale: rows from a year whose 12-31 boundary
 * is within 30 days of "now" may still be amended upstream; caching
 * them would persist soon-to-be-stale values.
 *
 * For `year` strictly less than the current calendar year of `now`, the
 * 12-31 boundary is well past 30 days back → returns false (cacheable).
 * For `year` equal to the current LST year, the year-end is in the
 * future relative to `now` → predicate returns false (the per-year
 * current-LST-year gate handles that case first and is still required).
 * The window only fires for the immediate-post-year window — exactly
 * the case where freshly-archived rows are most likely to be revised.
 */
function isYearVolatile(year: number, now: Date): boolean {
  const yearEnd = `${String(year).padStart(4, "0")}-12-31`;
  return isWithinVolatileWindow(yearEnd, formatDate(now), 30);
}

/**
 * Last calendar day of `(year, month)`. Used as archive-as-of for the
 * per-month volatile-window gate (iter-7 H13). Returns YYYY-MM-DD.
 */
function lastDayOfMonth(year: number, month: number): string {
  // UTC math: day 0 of (month+1) === last day of (month).
  const d = new Date(Date.UTC(year, month, 0));
  return formatDate(d);
}

/**
 * True iff the end-of-month ISO date for `(year, month)` falls inside the
 * 30-day volatile amendment window relative to `now`. Per-month analog of
 * `isYearVolatile`, used to gate the per-month observations cache
 * (iter-7 H13). Rationale: rows from a month whose final day is within
 * 30 days of "now" may still be amended upstream; caching them would
 * persist soon-to-be-stale values. The window only fires for the
 * immediate-post-month window — exactly the case where freshly-archived
 * rows are most likely to be revised.
 */
function isMonthVolatile(year: number, month: number, now: Date): boolean {
  return isWithinVolatileWindow(lastDayOfMonth(year, month), formatDate(now), 30);
}

/**
 * Enumerate `[year, month]` pairs that overlap `[fromIsoDate, toIsoDate]`
 * (inclusive on both ends). Used by the per-month observations cache
 * (iter-7 H13). Returns pairs in chronological order. Validates the
 * range; throws on inverted input.
 */
function monthsInRange(
  fromIsoDate: string,
  toIsoDate: string,
): ReadonlyArray<readonly [number, number]> {
  const from = parseIsoDate(fromIsoDate);
  const to = parseIsoDate(toIsoDate);
  if (from.getTime() > to.getTime()) {
    throw new Error(`fromDate (${fromIsoDate}) must be <= toDate (${toIsoDate})`);
  }
  const pairs: Array<readonly [number, number]> = [];
  let y = from.getUTCFullYear();
  let m = from.getUTCMonth() + 1; // 1-12
  const endY = to.getUTCFullYear();
  const endM = to.getUTCMonth() + 1;
  while (y < endY || (y === endY && m <= endM)) {
    pairs.push([y, m]);
    m += 1;
    if (m > 12) {
      m = 1;
      y += 1;
    }
  }
  return pairs;
}

/**
 * Fetch CLI climate per-year with read-through cache. Yearly chunks are
 * cached at `cacheKeyForClimate(code, year)`. Skip rules:
 *   - Current LST year — mutable, never cached.
 *   - 30-day volatile amendment window (iter-5 H9) — chunks whose
 *     year-end is within 30 days of `now` MUST be re-fetched. The
 *     window only fires for the year immediately preceding "now"
 *     once the calendar rolls over.
 *   - Live source (`.live`) — never cached (CLI is archive `iem.cli` →
 *     this never fires today; defensive for future).
 *
 * iter-6 C12: cache failures must NEVER discard the in-memory rows.
 * `cache.get` failures degrade to a live fetch (the intent — read-through
 * is a perf optimization, not a correctness requirement). `cache.set`
 * failures AFTER a successful fetch+parse MUST log and continue —
 * persisting to the cache is a best-effort side effect, never a reason
 * to drop already-fetched climate data. The previous broad try/catch in
 * the caller swallowed cache.set throws as "no CLI data," silently
 * corrupting research rows with null cli_* fields.
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
    // iter-12 C15: `isWritableYear` is the strictest temporal gate.
    // Any year that isn't STRICTLY in the past UTC-wise (future years
    // or the current UTC year, including the UTC Jan-1 boundary window
    // where a negative-offset station's LST is still in the prior year)
    // is never cacheable — regardless of LST or volatile-window logic.
    // Force a live fetch and skip both reads AND writes for non-writable
    // years.
    const writable = isWritableYear(year, now);
    const skipCurrentYear = shouldSkipCacheForCurrentLstYear(cacheCode, year, now);
    // iter-5 H9: the 30-day volatile amendment window MUST also block
    // cache reads — a hit served from inside the window would re-serve
    // soon-to-be-amended rows. Always prefer a fresh fetch when the
    // window is active.
    const skipVolatile = isYearVolatile(year, now);
    const skip = !writable || skipCurrentYear || skipVolatile;

    // --- Cache read (best-effort) -------------------------------------
    // iter-6 C12: a `cache.get` failure must not abort the per-year
    // chunk — fall through to the live fetch. A transient backend hiccup
    // is no reason to refuse climate data we can still fetch fresh.
    if (cache !== null && !skip) {
      let cached: ClimateObservation[] | null = null;
      try {
        cached = await cache.get<ClimateObservation[]>(cacheKeyForClimate(cacheCode, year));
      } catch (cacheErr) {
        // eslint-disable-next-line no-console
        console.warn(
          `[tradewinds] CLI cache.get failed for code=${cacheCode} year=${year}; falling back to live fetch:`,
          cacheErr,
        );
      }
      if (cached !== null) {
        acc.push(...cached);
        continue;
      }
    }

    // --- Live fetch + parse (errors here ARE fatal to this chunk) -----
    // Abort propagates; other errors bubble to the caller's try/catch
    // which degrades to "no CLI data" for the affected years. This is
    // the existing behavior — DO NOT widen the catch to include cache
    // writes (see below).
    const cliOpts: { signal?: AbortSignal; politenessMs?: number } = {};
    if (opts.signal !== undefined) cliOpts.signal = opts.signal;
    if (opts.cliPolitenessMs !== undefined) cliOpts.politenessMs = opts.cliPolitenessMs;
    const cliRaw = await downloadCliRange(fetchIcao, year, year, cliOpts);
    const parsed = parseCliResponse(cliRaw, cacheCode);
    acc.push(...parsed);

    // --- Cache write (best-effort, AFTER rows are accumulated) --------
    // iter-6 C12: `cache.set` MUST be wrapped in its own try/catch so a
    // transient write failure cannot discard already-fetched rows. The
    // previous code put cache.set inside the caller's broad CLI try/catch,
    // which silently degraded write failures to "no climate data" —
    // returning research rows with null cli_* fields. That's silent data
    // corruption; this guard prevents it.
    const sample = parsed[0]?.source;
    if (cache !== null && !skip && !isLiveSource(sample)) {
      try {
        await cache.set(cacheKeyForClimate(cacheCode, year), parsed);
      } catch (cacheErr) {
        // eslint-disable-next-line no-console
        console.warn(
          `[tradewinds] CLI cache.set failed for code=${cacheCode} year=${year}; in-memory rows preserved:`,
          cacheErr,
        );
      }
    }
  }
  return acc;
}

/**
 * Fetch IEM ASOS observations per-month with read-through cache.
 *
 * iter-7 H13: this previously cached at YEAR granularity using a sentinel
 * `:01:rt=N` key, violating the Python TS-CACHE-02 per-month contract.
 * The Python `read_cache(station, year, month)` / `write_cache(...)`
 * surface uses `(station, year, month)` triplets — one parquet per month
 * containing the merged METAR+SPECI slice. This helper now matches that
 * contract:
 *
 *   1. Enumerate `(year, month)` pairs overlapping the queried range.
 *   2. For each pair, attempt a per-month cache read using the
 *      source-namespaced key `cacheKeyForObservations(station, year,
 *      month, "iem")`.
 *   3. On cache miss, fetch the full year (single IEM HTTP request for
 *      `report_type=3` + one for `=4`) — IEM ASOS is yearly-chunked at
 *      the source — then partition parsed rows by `(year, month)` and
 *      filter back to the requested month (mirrors Python research.py
 *      L267-269 month-boundary filter).
 *   4. Apply per-MONTH skip rules:
 *        - `shouldSkipCacheForCurrentLstMonth(station, year, month, now)` —
 *          mutable current month; never written.
 *        - `isMonthVolatile(year, month, now)` — 30-day amendment window
 *          gate (iter-5 H9 / iter-7 H13). Within the window, both read
 *          AND write are skipped (IEM may publish late-arriving METARs
 *          or corrections).
 *   5. Write-through fires only when neither skip rule trips; otherwise
 *      the month's rows are returned in-memory but never persisted.
 *
 * Per-year fetch results are cached in a local `yearCache` Map so multiple
 * months within the same year share one HTTP round-trip — this is the
 * critical perf invariant from the previous implementation, preserved
 * across the granularity change.
 *
 * iter-6 C12: mirrors `fetchCliWithCache`'s split-try pattern — cache
 * `get` / `set` failures are logged but never discard the in-memory
 * rows. A cache backend hiccup must not silently drop observations
 * that were successfully fetched + parsed.
 */
async function fetchIemAsosWithCache(
  stationCode: string,
  _fromYear: number,
  _extendedToYear: number,
  fromDate: string,
  extendedTo: string,
  opts: ResearchOptions,
  cache: CacheStore | null,
  now: Date,
): Promise<Observation[]> {
  void _fromYear;
  void _extendedToYear;
  const acc: Observation[] = [];

  // Per-call memoization: avoid re-fetching the same (year, reportType)
  // when multiple months in the same year miss the cache.
  const yearByReportType = new Map<string, Observation[]>();

  async function fetchYearOnce(year: number, reportType: 3 | 4): Promise<Observation[]> {
    const memoKey = `${year}:${reportType}`;
    const cached = yearByReportType.get(memoKey);
    if (cached !== undefined) return cached;
    const iemOpts: { reportType: 3 | 4; politenessMs: number; signal?: AbortSignal } = {
      reportType,
      politenessMs: opts.iemPolitenessMs ?? 1000,
    };
    if (opts.signal !== undefined) iemOpts.signal = opts.signal;
    const chunks = await downloadIemAsos(stationCode, `${year}-01-01`, `${year}-12-31`, iemOpts);
    const fetched: Observation[] = [];
    for (const chunk of chunks) {
      const parsed = parseIemCsv(chunk.csv, {
        observationTypeOverride: reportType === 3 ? "METAR" : "SPECI",
      });
      fetched.push(...parsed);
    }
    yearByReportType.set(memoKey, fetched);
    return fetched;
  }

  function filterMonth(
    rows: ReadonlyArray<Observation>,
    year: number,
    month: number,
  ): Observation[] {
    const yyyy = String(year).padStart(4, "0");
    const mm = String(month).padStart(2, "0");
    const prefix = `${yyyy}-${mm}-`;
    const out: Observation[] = [];
    for (const r of rows) {
      if (r.observed_at.startsWith(prefix)) out.push(r);
    }
    return out;
  }

  const pairs = monthsInRange(fromDate, extendedTo);
  for (const [year, month] of pairs) {
    const cacheKey = cacheKeyForObservations(stationCode, year, month, "iem");
    // iter-12 C14: `isWritableMonth` is the strictest temporal gate.
    // Any month that isn't STRICTLY in the past UTC-wise (future months
    // or the current UTC month, including the UTC-rollover tail where
    // LST is still in the prior UTC month) is never cacheable —
    // regardless of LST or volatile-window logic. Force a live fetch
    // and skip both reads AND writes for non-writable months.
    const writable = isWritableMonth(year, month, now);
    const skipCurrentMonth = shouldSkipCacheForCurrentLstMonth(stationCode, year, month, now);
    const skipVolatile = isMonthVolatile(year, month, now);
    const skipCache = !writable || skipCurrentMonth || skipVolatile;

    // --- Cache read (best-effort) -------------------------------------
    // iter-6 C12: a `cache.get` failure must not abort the month — fall
    // through to the live fetch. The cached value combines METAR+SPECI
    // (single per-month entry), so a hit yields both report types.
    let monthRows: Observation[] | null = null;
    if (cache !== null && !skipCache) {
      try {
        const cached = await cache.get<Observation[]>(cacheKey);
        if (cached !== null) monthRows = cached;
      } catch (cacheErr) {
        // eslint-disable-next-line no-console
        console.warn(
          `[tradewinds] IEM ASOS cache.get failed for key=${cacheKey}; falling back to live fetch:`,
          cacheErr,
        );
      }
    }

    if (monthRows === null) {
      // --- Live fetch + parse (errors here propagate to the caller) ---
      // Fetch both report types for the year (memoized) and partition
      // to this month. Combining METAR+SPECI matches the Python contract
      // (write_cache receives one merged list per month).
      const metar = await fetchYearOnce(year, 3);
      const speci = await fetchYearOnce(year, 4);
      const monthMetar = filterMonth(metar, year, month);
      const monthSpeci = filterMonth(speci, year, month);
      monthRows = [...monthMetar, ...monthSpeci];

      // --- Cache write (best-effort, AFTER rows are accumulated) ------
      // iter-6 C12: `cache.set` failures MUST NOT propagate — a
      // transient write failure cannot be allowed to discard rows that
      // were just successfully fetched + parsed. Log and continue; the
      // in-memory `monthRows` is appended to `acc` below regardless.
      const sample = monthRows[0]?.source;
      if (cache !== null && !skipCache && !isLiveSource(sample)) {
        try {
          await cache.set(cacheKey, monthRows);
        } catch (cacheErr) {
          // eslint-disable-next-line no-console
          console.warn(
            `[tradewinds] IEM ASOS cache.set failed for key=${cacheKey}; in-memory rows preserved:`,
            cacheErr,
          );
        }
      }
    }

    for (const obs of monthRows) {
      const obsDate = obs.observed_at.slice(0, 10);
      if (obsDate >= fromDate && obsDate <= extendedTo) acc.push(obs);
    }
  }
  return acc;
}

/**
 * Fetch GHCNh archive observations per-month with read-through cache.
 *
 * iter-7 H14: previously the GHCNh path called `downloadGhcnhRange` on
 * every `research()` invocation and never touched the cache. TS-W3
 * requires GHCNh chunks to be cacheable just like IEM ASOS — this helper
 * applies the same per-month contract as `fetchIemAsosWithCache`:
 *
 *   1. Enumerate `(year, month)` pairs overlapping the queried range.
 *   2. For each pair, attempt a per-month cache read using the source-
 *      namespaced key `cacheKeyForObservations(station, year, month,
 *      "ghcnh")`. The `"ghcnh"` source segment prevents collision with
 *      IEM ASOS writes for the same `(station, year, month)` triplet
 *      (iter-7 H13 introduced `"iem"` namespacing).
 *   3. On cache miss, fetch the full year via `downloadGhcnh` (single
 *      PSV per station-year — NCEI's archive is yearly-chunked at the
 *      source) — memoized within the helper so multiple months in the
 *      same year share one HTTP round-trip.
 *   4. Per-month skip rules: `shouldSkipCacheForCurrentLstMonth` +
 *      `isMonthVolatile` (30-day amendment window). NCEI republishes
 *      `GHCNh_<id>_<YEAR>.psv` as new months land, so the same skip
 *      logic the IEM helper uses applies here.
 *   5. 404-as-no-data: a `NotFoundError` from `downloadGhcnh` means NCEI
 *      has no archive for this station-year (typical for recent partial
 *      years or pre-1973 stations). We memoize an empty year and treat
 *      every month as cache-eligible-but-empty. The Python range fetcher
 *      silently swallows 404 too (research.py L160-166 logs + continues).
 *
 * iter-6 C12: mirrors the split-try pattern — cache `get` / `set`
 * failures are logged but never discard the in-memory rows.
 */
async function fetchGhcnhWithCache(
  stationCode: string,
  ghcnhId: string,
  fromDate: string,
  extendedTo: string,
  opts: ResearchOptions,
  cache: CacheStore | null,
  now: Date,
): Promise<Observation[]> {
  const acc: Observation[] = [];

  // Per-call memoization: avoid re-fetching the same year when multiple
  // months in the same year miss the cache. `null` sentinel records a 404
  // (no data) so subsequent months in that year skip the HTTP call too.
  const yearCache = new Map<number, ReadonlyArray<Observation>>();

  async function fetchYearOnce(year: number): Promise<ReadonlyArray<Observation>> {
    const cached = yearCache.get(year);
    if (cached !== undefined) return cached;
    const ghcnhOpts: { signal?: AbortSignal } = {};
    if (opts.signal !== undefined) ghcnhOpts.signal = opts.signal;
    let parsed: ReadonlyArray<Observation>;
    try {
      const yr = await downloadGhcnh(ghcnhId, year, ghcnhOpts);
      parsed = parseGhcnhPsv(yr.psv);
    } catch (err) {
      if (err instanceof NotFoundError) {
        // NCEI 404 → no data for this station-year. Mirrors the
        // `downloadGhcnhRange` swallow-404 behavior; memoize empty so
        // subsequent months in this year don't re-hit NCEI.
        parsed = [];
      } else {
        throw err;
      }
    }
    yearCache.set(year, parsed);
    return parsed;
  }

  function filterMonth(
    rows: ReadonlyArray<Observation>,
    year: number,
    month: number,
  ): Observation[] {
    const yyyy = String(year).padStart(4, "0");
    const mm = String(month).padStart(2, "0");
    const prefix = `${yyyy}-${mm}-`;
    const out: Observation[] = [];
    for (const r of rows) {
      if (r.observed_at.startsWith(prefix) && r.station_code === stationCode) out.push(r);
    }
    return out;
  }

  const pairs = monthsInRange(fromDate, extendedTo);
  for (const [year, month] of pairs) {
    const cacheKey = cacheKeyForObservations(stationCode, year, month, "ghcnh");
    // iter-12 C14: stricter additional temporal gate — see the matching
    // comment in `fetchIemAsosWithCache`. NCEI's archive can return
    // empty data for not-yet-published months; we must NEVER persist a
    // not-strictly-past UTC month as if it were complete.
    const writable = isWritableMonth(year, month, now);
    const skipCurrentMonth = shouldSkipCacheForCurrentLstMonth(stationCode, year, month, now);
    const skipVolatile = isMonthVolatile(year, month, now);
    const skipCache = !writable || skipCurrentMonth || skipVolatile;

    // --- Cache read (best-effort) -------------------------------------
    let monthRows: Observation[] | null = null;
    if (cache !== null && !skipCache) {
      try {
        const cached = await cache.get<Observation[]>(cacheKey);
        if (cached !== null) monthRows = cached;
      } catch (cacheErr) {
        // eslint-disable-next-line no-console
        console.warn(
          `[tradewinds] GHCNh cache.get failed for key=${cacheKey}; falling back to live fetch:`,
          cacheErr,
        );
      }
    }

    if (monthRows === null) {
      // --- Live fetch + parse (errors here propagate to the caller) ---
      const yearRows = await fetchYearOnce(year);
      monthRows = filterMonth(yearRows, year, month);

      // --- Cache write (best-effort, AFTER rows are accumulated) ------
      // iter-6 C12: `cache.set` failures MUST NOT propagate. Even an
      // empty month list is written when the year was successfully
      // fetched — it pins the "no observations for this month" fact so
      // the next call doesn't re-fetch the year just to discover nothing.
      const sample = monthRows[0]?.source;
      if (cache !== null && !skipCache && !isLiveSource(sample)) {
        try {
          await cache.set(cacheKey, monthRows);
        } catch (cacheErr) {
          // eslint-disable-next-line no-console
          console.warn(
            `[tradewinds] GHCNh cache.set failed for key=${cacheKey}; in-memory rows preserved:`,
            cacheErr,
          );
        }
      }
    }

    for (const obs of monthRows) {
      const obsDate = obs.observed_at.slice(0, 10);
      if (obsDate >= fromDate && obsDate <= extendedTo) acc.push(obs);
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
  // ── Phase 10 selector + cross-arg validation ─────────────────────────
  //
  // The TS signature pre-dates Phase 10's composable kwargs, so the
  // `station` positional is still always passed. The new selectors live
  // on `opts` (city / contract / contracts) and are validated here:
  // exactly one of station / city / contract / contracts is allowed.
  //
  // v0.2 ships only the validation surface; the multi-station JOIN +
  // trade-attachment lands in v0.3. Passing any non-station selector
  // surfaces a clear NotImplementedError-style error so callers can
  // route via discover() + the station-path until v0.3.
  const hasCity = typeof opts.city === "string" && opts.city.length > 0;
  const hasContract = typeof opts.contract === "string" && opts.contract.length > 0;
  const hasContracts = Array.isArray(opts.contracts) && opts.contracts.length > 0;
  const hasStation = typeof station === "string" && station.length > 0;
  const selectorCount =
    Number(hasStation) + Number(hasCity) + Number(hasContract) + Number(hasContracts);
  if (selectorCount === 0) {
    throw new Error(
      "research(): exactly one of station, opts.city, opts.contract, opts.contracts must be provided",
    );
  }
  if (selectorCount > 1) {
    const names: string[] = [];
    if (hasStation) names.push("station");
    if (hasCity) names.push("city");
    if (hasContract) names.push("contract");
    if (hasContracts) names.push("contracts");
    throw new Error(`research(): selectors are mutually exclusive; got ${JSON.stringify(names)}`);
  }
  if (opts.sources !== undefined && opts.source !== undefined) {
    throw new Error("research(): sources and source are mutually exclusive");
  }
  if (opts.stationOverride !== undefined && !hasContract) {
    throw new Error(
      "research(): stationOverride requires contract (not standalone station/city/contracts)",
    );
  }
  if (opts.includeTrades === true && !(hasContract || hasContracts)) {
    throw new Error(
      "research(): includeTrades requires contract or contracts (station/city selectors have no trade timeseries)",
    );
  }
  if (hasCity || hasContract || hasContracts) {
    throw new Error(
      "research(): city/contract/contracts selectors are validated in Phase 10 v0.2 " +
        "but the multi-station/multi-issuer JOIN + trade attachment lands in v0.3. " +
        "For now, use `discover({city})` to find the station then call " +
        "`research(station, fromDate, toDate)` directly.",
    );
  }
  // ── Backwards-compat station path (existing implementation) ─────────
  const resolved = normalizeStation(station);
  const dates = buildDateList(fromDate, toDate);
  const extendedTo = plusOneDay(toDate);

  const fromYear = Number(fromDate.slice(0, 4));
  const toYear = Number(toDate.slice(0, 4));
  const extendedToYear = Number(extendedTo.slice(0, 4));

  const baseOpts: { signal?: AbortSignal } = {};
  if (opts.signal !== undefined) baseOpts.signal = opts.signal;

  const cache = await resolveCache(opts);
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
  // iter-7 H14: now wraps `downloadGhcnh` in `fetchGhcnhWithCache` so
  // GHCNh chunks are persisted at the same per-month granularity as IEM
  // ASOS. Repeat `research()` calls for the same range skip NCEI
  // entirely on cache hit. Non-US stations short-circuit before reaching
  // the helper — GHCNh PSVs are US-only.
  let ghcnhRows: Observation[] = [];
  if (isUsStation(resolved) && resolved.ghcnhId !== null && resolved.ghcnhId.length > 0) {
    ghcnhRows = await fetchGhcnhWithCache(
      resolved.code,
      resolved.ghcnhId,
      fromDate,
      extendedTo,
      opts,
      cache,
      cacheNow,
    );
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

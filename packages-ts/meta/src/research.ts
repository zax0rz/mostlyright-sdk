// `research()` orchestrator — TS-W1 Wave 6 MVP.
//
// Joins AWC live observations (last 168h) + IEM CLI climate reports into
// daily rows, mirroring (a subset of) Python `tradewinds.research()` Mode 1.
//
// Lives in `packages-ts/meta/` (NOT in @tradewinds/core) so the core
// package can stay dep-free; this orchestrator depends on both
// @tradewinds/core (snapshot math + station table) and @tradewinds/weather
// (AWC + CLI fetchers/parsers). See TS-W1 PLAN §Wave 6.
//
// W1 scope: AWC + CLI only. NO IEM ASOS, GHCNh, forecast, or cache —
// those land in later waves. All `fcst_*` columns are unconditionally null.

import {
  STATION_BY_CODE,
  STATION_BY_ICAO,
  marketCloseUtc,
  settlementDateFor,
} from "@tradewinds/core";
import {
  type ClimateObservation,
  type Observation,
  awcToObservation,
  downloadCliRange,
  fetchAwcMetars,
  mergeClimate,
  parseCliResponse,
} from "@tradewinds/weather";

// ---------------------------------------------------------------------------
// Public types
// ---------------------------------------------------------------------------

export interface ResearchOptions {
  /** Forward to all underlying fetchers; aborts the whole pipeline. */
  signal?: AbortSignal;
  /** AWC lookback window in hours. Default 168 (AWC max). Clamped by the fetcher. */
  awcHours?: number;
}

/**
 * A single date-keyed research row — one per calendar day in the
 * requested range, in the station's local standard time.
 *
 * All `fcst_*` columns are unconditionally null in W1 (forecast support
 * is reserved for a later wave). The column names are present so the
 * shape is forward-compatible with the Python `pairs()` schema.
 */
export interface ResearchRow {
  readonly date: string;
  readonly station: string;
  readonly cli_high_f: number | null;
  readonly cli_low_f: number | null;
  readonly cli_report_type: string | null;
  readonly obs_high_f: number | null;
  readonly obs_low_f: number | null;
  readonly obs_mean_f: number | null;
  readonly obs_mean_dewpoint_f: number | null;
  readonly obs_max_wind_kt: number | null;
  readonly obs_max_gust_kt: number | null;
  readonly obs_total_precip_in: number | null;
  readonly obs_count: number;
  readonly fcst_high_f: null;
  readonly fcst_low_f: null;
  readonly fcst_model: null;
  readonly fcst_issued_at: null;
  readonly fcst_pop_6hr_pct: null;
  readonly fcst_qpf_6hr_in: null;
  readonly market_close_utc: string;
}

// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------

const DATE_RE = /^\d{4}-\d{2}-\d{2}$/;

function normalizeStation(input: string): { code: string; icao: string; tz: string } {
  const raw = input.trim().toUpperCase();
  if (raw.length === 0) {
    throw new Error("station must be a non-empty string");
  }
  // Try ICAO form first (4-letter, may match KNYC etc.), then 3-letter code.
  const byIcao = STATION_BY_ICAO.get(raw);
  if (byIcao !== undefined) {
    if (byIcao.code === null) {
      throw new Error(`station ${JSON.stringify(raw)} has no 3-letter NWS code`);
    }
    return { code: byIcao.code, icao: byIcao.icao, tz: byIcao.tz };
  }
  const byCode = STATION_BY_CODE.get(raw);
  if (byCode !== undefined) {
    if (byCode.code === null) {
      throw new Error(`station ${JSON.stringify(raw)} has no 3-letter NWS code`);
    }
    return { code: byCode.code, icao: byCode.icao, tz: byCode.tz };
  }
  // Strip leading K and retry (`KNYC` already handled above, but legacy
  // 5-letter inputs like `KKNYC` shouldn't sneak through).
  if (raw.startsWith("K") && raw.length === 4) {
    const stripped = raw.slice(1);
    const retry = STATION_BY_CODE.get(stripped);
    if (retry !== undefined && retry.code !== null) {
      return { code: retry.code, icao: retry.icao, tz: retry.tz };
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

/**
 * Given an ISO-UTC observed_at string ("YYYY-MM-DDTHH:MM:SSZ") and the
 * station code, return the LOCAL STANDARD TIME calendar date (YYYY-MM-DD)
 * that the observation belongs to.
 *
 * Uses `settlementDateFor()` from @tradewinds/core — which applies the
 * station's STANDARD UTC offset (DST-ignored). Kalshi NHIGH/NLOW
 * settlement windows are midnight–midnight LST year-round; observations
 * MUST group by LST date, not by wall-clock local date, otherwise the
 * spring/fall DST edges produce wrong daily aggregates.
 */
function observedSettlementDate(observedAt: string, station: string): string | null {
  const ms = Date.parse(observedAt);
  if (!Number.isFinite(ms)) return null;
  try {
    return settlementDateFor(new Date(ms), station);
  } catch {
    // settlementDateFor throws on unknown station tz; the caller has
    // already validated the station code, so this shouldn't fire in
    // practice. Defensive fallthrough to null preserves the bucket
    // skip the original implementation used on parse failure.
    return null;
  }
}

function average(values: ReadonlyArray<number>): number | null {
  if (values.length === 0) return null;
  let sum = 0;
  for (const v of values) sum += v;
  return sum / values.length;
}

function maxOf(values: ReadonlyArray<number>): number | null {
  if (values.length === 0) return null;
  let best = values[0] as number;
  for (let i = 1; i < values.length; i++) {
    const v = values[i] as number;
    if (v > best) best = v;
  }
  return best;
}

function minOf(values: ReadonlyArray<number>): number | null {
  if (values.length === 0) return null;
  let best = values[0] as number;
  for (let i = 1; i < values.length; i++) {
    const v = values[i] as number;
    if (v < best) best = v;
  }
  return best;
}

function sumOf(values: ReadonlyArray<number>): number {
  let s = 0;
  for (const v of values) s += v;
  return s;
}

function nonNullField<T extends keyof Observation>(
  obs: ReadonlyArray<Observation>,
  field: T,
): ReadonlyArray<number> {
  const out: number[] = [];
  for (const o of obs) {
    const v = o[field];
    if (typeof v === "number" && Number.isFinite(v)) {
      out.push(v);
    }
  }
  return out;
}

// ---------------------------------------------------------------------------
// Public surface
// ---------------------------------------------------------------------------

/**
 * Build daily research rows for a station + date window.
 *
 * @param station NWS 3-letter code (e.g. "NYC") OR 4-letter ICAO (e.g. "KNYC").
 * @param fromDate Inclusive start date, ISO YYYY-MM-DD.
 * @param toDate Inclusive end date, ISO YYYY-MM-DD.
 * @param opts See {@link ResearchOptions}.
 *
 * Returns an immutable array of frozen {@link ResearchRow}s — one per day
 * in `[fromDate, toDate]`. Each row carries:
 *  - `cli_*` fields populated from IEM CLI when available, null otherwise.
 *  - `obs_*` daily aggregates over AWC live METARs grouped by local date.
 *    Note: AWC only serves ~168 hours; dates older than that have null obs.
 *  - `fcst_*` fields unconditionally null (W1 reserves the columns).
 *  - `market_close_utc` from `marketCloseUtc(date, station)`.
 *
 * Throws:
 *  - When the station can't be resolved.
 *  - When dates are malformed or `fromDate > toDate`.
 *  - When AbortSignal is triggered (propagates from fetchers).
 */
export async function research(
  station: string,
  fromDate: string,
  toDate: string,
  opts: ResearchOptions = {},
): Promise<ReadonlyArray<ResearchRow>> {
  const resolved = normalizeStation(station);
  const dates = buildDateList(fromDate, toDate);

  // --- CLI fetch (year range) -------------------------------------------
  // IEM CLI is per-station-year — we ask for the inclusive year span and
  // filter to the date range below.
  const fromYear = Number(fromDate.slice(0, 4));
  const toYear = Number(toDate.slice(0, 4));
  // `exactOptionalPropertyTypes` rejects `signal: undefined`; build the opts
  // object conditionally so the key is omitted when no signal is provided.
  const baseOpts: { signal?: AbortSignal } = {};
  if (opts.signal !== undefined) baseOpts.signal = opts.signal;

  let cliMap: Map<string, ClimateObservation>;
  try {
    const cliRaw = await downloadCliRange(resolved.icao, fromYear, toYear, baseOpts);
    const cliParsed = parseCliResponse(cliRaw, resolved.code);
    // Use mergeClimate() (byte-faithful port of Python merge_climate /
    // _dedup_climate_rows): keep the row with highest
    // `report_type_priority` per `(station_code, observation_date)` with
    // strict `>`. This ensures a later `final` replaces an earlier
    // `preliminary`, but a second `final` never overwrites the first.
    const cliDeduped = mergeClimate(cliParsed);
    cliMap = new Map<string, ClimateObservation>();
    for (const row of cliDeduped) {
      cliMap.set(row.observation_date, row);
    }
  } catch (err) {
    // Surface aborts to the caller; on other errors degrade to no CLI data.
    if (err instanceof DOMException && (err.name === "AbortError" || err.name === "TimeoutError")) {
      throw err;
    }
    cliMap = new Map();
  }

  // --- AWC fetch (live window) ------------------------------------------
  const awcOpts: { hours: number; signal?: AbortSignal } = {
    hours: opts.awcHours ?? 168,
  };
  if (opts.signal !== undefined) awcOpts.signal = opts.signal;
  const awcRaw = await fetchAwcMetars([resolved.icao], awcOpts);
  const obsByDate = new Map<string, Observation[]>();
  for (const m of awcRaw) {
    const obs = awcToObservation(m);
    if (obs === null) continue;
    const localDate = observedSettlementDate(obs.observed_at, resolved.code);
    if (localDate === null) continue;
    let bucket = obsByDate.get(localDate);
    if (bucket === undefined) {
      bucket = [];
      obsByDate.set(localDate, bucket);
    }
    bucket.push(obs);
  }

  // --- Assemble rows ----------------------------------------------------
  const rows: ResearchRow[] = [];
  for (const date of dates) {
    const cli = cliMap.get(date) ?? null;
    const obs = obsByDate.get(date) ?? [];
    const tempsF = nonNullField(obs, "temp_f");
    const dewpsF = nonNullField(obs, "dewpoint_f");
    const winds = nonNullField(obs, "wind_speed_kt");
    const gusts = nonNullField(obs, "wind_gust_kt");
    const precips = nonNullField(obs, "precip_1hr_inches");

    const row: ResearchRow = Object.freeze({
      date,
      station: resolved.code,
      cli_high_f: cli ? cli.high_temp_f : null,
      cli_low_f: cli ? cli.low_temp_f : null,
      cli_report_type: cli ? cli.report_type : null,
      obs_high_f: maxOf(tempsF),
      obs_low_f: minOf(tempsF),
      obs_mean_f: average(tempsF),
      obs_mean_dewpoint_f: average(dewpsF),
      obs_max_wind_kt: maxOf(winds),
      obs_max_gust_kt: maxOf(gusts),
      obs_total_precip_in: precips.length === 0 ? null : sumOf(precips),
      obs_count: obs.length,
      fcst_high_f: null,
      fcst_low_f: null,
      fcst_model: null,
      fcst_issued_at: null,
      fcst_pop_6hr_pct: null,
      fcst_qpf_6hr_in: null,
      market_close_utc: marketCloseUtc(date, resolved.code).toISOString(),
    });
    rows.push(row);
  }
  return Object.freeze(rows);
}

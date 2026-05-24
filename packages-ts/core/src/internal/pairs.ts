// buildPairs + _obsAggregates + pairsToRows — settlement-day row builder.
//
// Byte-faithful TS port of Python
// `packages/core/src/tradewinds/_internal/_pairs.py::build_pairs` (Mode 1
// subset — no forecast wiring; all fcst_* columns unconditionally null).
//
// The full Python `_select_best_run` / `_aggregate_fcst_temps_*` paths
// (IEM MOS + Open-Meteo) are intentionally NOT ported here; forecast
// support lands in TS-W5+. Same scope cut TS-W1 made for `research()`.
//
// Type strategy: structural `PairsObservationLike` + `PairsClimateLike`
// interfaces. The full `Observation` (from weather/_parsers/awc.ts) and
// `ClimateObservation` (from weather/_parsers/cli.ts) structurally
// satisfy them — avoids a circular import + matches the Plan 04
// `ObservationKey` discipline.

import { marketCloseUtc } from "../snapshot.js";

/** Subset of fields `_obsAggregates` reads from each observation row. */
export interface PairsObservationLike {
  readonly temp_f?: number | null;
  readonly dewpoint_f?: number | null;
  readonly wind_speed_kt?: number | null;
  readonly wind_gust_kt?: number | null;
  readonly precip_1hr_inches?: number | null;
}

/** Subset of `ClimateObservation` fields buildPairs reads from each CLI row. */
export interface PairsClimateLike {
  readonly high_temp_f: number | null;
  readonly low_temp_f: number | null;
  readonly report_type: string;
}

/** Aggregated observation summary for one settlement day. */
export interface ObsAggregates {
  readonly obs_high_f: number | null;
  readonly obs_low_f: number | null;
  readonly obs_mean_f: number | null;
  readonly obs_mean_dewpoint_f: number | null;
  readonly obs_max_wind_kt: number | null;
  readonly obs_max_gust_kt: number | null;
  readonly obs_total_precip_in: number | null;
  readonly obs_count: number;
}

/**
 * One settlement-date row — 20 columns, byte-shape-equivalent to Python
 * `build_pairs_row` output. The `fcst_*` columns are unconditionally
 * `null` in TS-W2 (Mode 1 only — forecast wiring is TS-W5+).
 *
 * Object-key order is preserved verbatim so `JSON.stringify` produces
 * column ordering byte-stable across SDKs.
 */
export interface PairsRow {
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

export interface BuildPairsOptions {
  /** Forwarded to `marketCloseUtc` (rare — used for synthetic test stations). */
  readonly tzOverride?: string;
}

// ---------------------------------------------------------------------------
// Aggregation helpers
// ---------------------------------------------------------------------------

function collectNonNull(
  obs: ReadonlyArray<PairsObservationLike>,
  key: keyof PairsObservationLike,
): number[] {
  const out: number[] = [];
  for (const o of obs) {
    const v = o[key];
    if (typeof v === "number" && Number.isFinite(v)) out.push(v);
  }
  return out;
}

function meanOrNull(vs: number[]): number | null {
  if (vs.length === 0) return null;
  let s = 0;
  for (const v of vs) s += v;
  return s / vs.length;
}

function maxOrNull(vs: number[]): number | null {
  if (vs.length === 0) return null;
  let best = vs[0] as number;
  for (let i = 1; i < vs.length; i++) {
    const v = vs[i] as number;
    if (v > best) best = v;
  }
  return best;
}

function minOrNull(vs: number[]): number | null {
  if (vs.length === 0) return null;
  let best = vs[0] as number;
  for (let i = 1; i < vs.length; i++) {
    const v = vs[i] as number;
    if (v < best) best = v;
  }
  return best;
}

function sumOrNull(vs: number[]): number | null {
  if (vs.length === 0) return null;
  let s = 0;
  for (const v of vs) s += v;
  return s;
}

// ---------------------------------------------------------------------------
// Aggregator
// ---------------------------------------------------------------------------

/**
 * Aggregate one day's observation rows into the 8-field `obs_*` summary.
 *
 * Rules (byte-faithful with Python `_obs_aggregates` at `_pairs.py:97-150`):
 *  - obs_high_f / obs_low_f / obs_mean_f: max / min / arithmetic mean over
 *    non-null `temp_f`. Mean-of-null-only → null.
 *  - obs_mean_dewpoint_f: mean over non-null `dewpoint_f`.
 *  - obs_max_wind_kt / obs_max_gust_kt: max over non-null wind/gust.
 *  - obs_total_precip_in: sum over non-null precip; `null` if NO non-null
 *    precip rows (mirrors Python `sum(precips) if precips else None`).
 *  - obs_count: total row count, INCLUDING rows where every measure is null.
 *
 * Numeric-stability note: mean is non-associative for floats. Callers MUST
 * pass observations in a deterministic order to preserve byte-equivalent
 * float aggregation. Plan 06's research orchestrator sorts by
 * `(observed_at, source)` before calling this.
 *
 * Returns a `Object.freeze`-d aggregate with key order matching Python.
 */
export function _obsAggregates(observations: ReadonlyArray<PairsObservationLike>): ObsAggregates {
  if (observations.length === 0) {
    return Object.freeze({
      obs_high_f: null,
      obs_low_f: null,
      obs_mean_f: null,
      obs_mean_dewpoint_f: null,
      obs_max_wind_kt: null,
      obs_max_gust_kt: null,
      obs_total_precip_in: null,
      obs_count: 0,
    });
  }
  const temps = collectNonNull(observations, "temp_f");
  const dewps = collectNonNull(observations, "dewpoint_f");
  const winds = collectNonNull(observations, "wind_speed_kt");
  const gusts = collectNonNull(observations, "wind_gust_kt");
  const precips = collectNonNull(observations, "precip_1hr_inches");
  return Object.freeze({
    obs_high_f: maxOrNull(temps),
    obs_low_f: minOrNull(temps),
    obs_mean_f: meanOrNull(temps),
    obs_mean_dewpoint_f: meanOrNull(dewps),
    obs_max_wind_kt: maxOrNull(winds),
    obs_max_gust_kt: maxOrNull(gusts),
    obs_total_precip_in: sumOrNull(precips),
    obs_count: observations.length,
  });
}

// ---------------------------------------------------------------------------
// Row + batch builders
// ---------------------------------------------------------------------------

/**
 * Build one PairsRow for a given (station, date) from its observation +
 * climate inputs. Mode 1 only — fcst_* are unconditionally null.
 *
 * `market_close_utc` is formatted `YYYY-MM-DDTHH:MM:SSZ` (no milliseconds)
 * via `Date.toISOString().slice(0, 19) + "Z"` — mirrors Python strftime.
 */
export function buildPairsRow(
  dateStr: string,
  station: string,
  observations: ReadonlyArray<PairsObservationLike>,
  climate: PairsClimateLike | null,
  opts: BuildPairsOptions = {},
): PairsRow {
  const obsAgg = _obsAggregates(observations);
  const closeUtc = marketCloseUtc(dateStr, station, opts.tzOverride);
  const closeIso = `${closeUtc.toISOString().slice(0, 19)}Z`;
  return Object.freeze({
    date: dateStr,
    station,
    cli_high_f: climate ? climate.high_temp_f : null,
    cli_low_f: climate ? climate.low_temp_f : null,
    cli_report_type: climate ? climate.report_type : null,
    obs_high_f: obsAgg.obs_high_f,
    obs_low_f: obsAgg.obs_low_f,
    obs_mean_f: obsAgg.obs_mean_f,
    obs_mean_dewpoint_f: obsAgg.obs_mean_dewpoint_f,
    obs_max_wind_kt: obsAgg.obs_max_wind_kt,
    obs_max_gust_kt: obsAgg.obs_max_gust_kt,
    obs_total_precip_in: obsAgg.obs_total_precip_in,
    obs_count: obsAgg.obs_count,
    fcst_high_f: null,
    fcst_low_f: null,
    fcst_model: null,
    fcst_issued_at: null,
    fcst_pop_6hr_pct: null,
    fcst_qpf_6hr_in: null,
    market_close_utc: closeIso,
  });
}

/**
 * Build PairsRows for every date in `dates` (input-order preserved).
 *
 * `observationsByDate[date]` and `climateByDate[date]` are looked up
 * defensively — missing keys are treated as empty obs / null climate.
 *
 * Returns a `Object.freeze`-d array.
 */
export function buildPairs(
  station: string,
  dates: ReadonlyArray<string>,
  observationsByDate: Readonly<Record<string, ReadonlyArray<PairsObservationLike>>>,
  climateByDate: Readonly<Record<string, PairsClimateLike | null>>,
  opts: BuildPairsOptions = {},
): ReadonlyArray<PairsRow> {
  const out: PairsRow[] = [];
  for (const date of dates) {
    const obs = observationsByDate[date] ?? [];
    const climate = climateByDate[date] ?? null;
    out.push(buildPairsRow(date, station, obs, climate, opts));
  }
  return Object.freeze(out);
}

/**
 * Surface-parity alias of `buildPairs` output. Python's `pairs_to_dataframe`
 * converts the list[dict] into a pandas DataFrame indexed by date; TS has
 * no DataFrame, so this is identity. Exists for cross-SDK signature parity
 * per CROSS-SDK-SYNC.md.
 */
export function pairsToRows(rows: ReadonlyArray<PairsRow>): ReadonlyArray<PairsRow> {
  return rows;
}

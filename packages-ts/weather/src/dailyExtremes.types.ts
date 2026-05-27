// Phase 21 21-05 — dailyExtremes type contract.
//
// Mirrors Python `mostlyright.international.daily_extremes(station, from,
// to, merge='live_v1')` return shape. Composes the existing
// `internationalDailyExtremes` rollup with a fetch step keyed on the
// STATIONS-registry tz.

/**
 * Merge mode controlling which sources contribute observations.
 *
 *  - `live_v1` (default) — IEM ASOS for historical depth + AWC for the
 *    recent 168h window. Matches Python `merge="live_v1"`.
 *  - `awc_only` — AWC live METAR only. Window must be inside the 168h
 *    AWC retention or callers see a sparse return.
 *  - `iem_only` — IEM ASOS archive only. No live fallback.
 */
export type DailyExtremesMergeMode = "live_v1" | "awc_only" | "iem_only";

export interface DailyExtremesOptions {
  /** Source merge mode; default `"live_v1"`. */
  merge?: DailyExtremesMergeMode;
}

/**
 * One station-local day's rollup.
 *
 * Field names mirror Python `DailyExtreme` TypedDict exactly so
 * cross-language code reads the same way:
 *   - `date`, `station`, `tmin_f`, `tmax_f`, `tmean_f`, `precip_in`
 *   - `low_coverage` (boolean) and `n_obs` (int) for debug-friendly gating
 */
export interface DailyExtremeRow {
  /** Station-local calendar date as `YYYY-MM-DD`. */
  date: string;
  /** ICAO station code. */
  station: string;
  /** Minimum temperature in °F, or null on low coverage. */
  tmin_f: number | null;
  /** Maximum temperature in °F, or null on low coverage. */
  tmax_f: number | null;
  /** Mean temperature in °F, or null on low coverage. */
  tmean_f: number | null;
  /** Total 1-hour precipitation across the local day, in inches. */
  precip_in: number | null;
  /** True when n_obs < 12 (matches Python low-coverage gate). */
  low_coverage: boolean;
  /** Count of observation rows that contributed to the day. */
  n_obs: number;
}

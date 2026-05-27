// Phase 21 21-04 — obs(station, from, to, opts?) type contract.
//
// Mirrors Python `tw.weather.obs(station, start, end, source=None,
// strategy='auto')` so cross-language code reads the same way.
//
// Strategy enum matches Python `Literal["auto", "exact_window",
// "warm_cache", "hosted"]`. Per D-06 in 21-CONTEXT:
//   - `exact_window` works the same as Python.
//   - `warm_cache` writes IndexedDB (browser) / Node FS (server) instead
//     of parquet; behavior otherwise matches.
//   - `hosted` raises DataAvailabilityError(reason='model_unavailable',
//     hint='hosted ingest API ships in v0.2.x') — symmetric to Python.
//   - `auto` (default) routes based on window size: 7-day or smaller →
//     `exact_window`, else → `warm_cache`.

/** Strategy enum — matches Python verbatim. */
export type ObsStrategy = "auto" | "exact_window" | "warm_cache" | "hosted";

/**
 * Source filter — matches Python `tw.weather.obs(source=...)` `_VALID_SOURCES`
 * frozenset `{"awc", "iem", "ghcnh"}`. `null` (default) means all sources
 * merged.
 *
 * Phase 21 21-09 fix-iter-1: `ghcnh` validates as accepted but is not yet
 * wired in TS (no GHCNh fetcher path in `fetchByStrategy`); selecting it
 * raises `DataAvailabilityError(reason="model_unavailable")` rather than
 * silently returning `[]`. Tracking issue: TS-W4 GHCNh fetcher port. The
 * `cli` value was removed — it is not a valid Python source filter either.
 */
export type ObsSourceFilter = "awc" | "iem" | "ghcnh" | null;

export interface ObsOptions {
  /** Optional source filter. `null` (default) means all sources merged. */
  source?: ObsSourceFilter;
  /** Strategy mode; default `"auto"`. */
  strategy?: ObsStrategy;
}

/**
 * Single observation row. Field set mirrors the canonical Observation
 * schema (`@mostlyrightmd/weather` Observation interface) with the
 * METAR-derived fields (temp_f / dewpoint_f / wind_speed_kts / ...).
 */
export interface ObsRow {
  station: string;
  observed_at: string;
  source: string;
  temp_c: number | null;
  temp_f: number | null;
  dewpoint_c?: number | null;
  dewpoint_f?: number | null;
  wind_speed_kts?: number | null;
  wind_direction_deg?: number | null;
  pressure_inhg?: number | null;
  precip_mm_1h?: number | null;
  raw_metar?: string | null;
}

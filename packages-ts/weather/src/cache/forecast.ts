// Phase 20 OM-06 + OM-09 — Open-Meteo forecast cache (TS mirror of
// Python `packages/weather/src/mostlyright/weather/cache.py`
// forecast_cache_path / read_forecast_cache / write_forecast_cache).
//
// Layout per D-09:
//   forecasts:{source}:{model}:{station}:{YYYY}:{MM}
//
// Cache eligibility rules (mirror Python):
//   - source === "open_meteo.live"     → NEVER cache (rolling cycle)
//   - source === "open_meteo.seamless" → NEVER cache (banned)
//   - current UTC month                → SKIP (cycles may still publish)
//   - else                              → cacheable

import type { CacheStore } from "@mostlyrightmd/core/internal/cache";

import type { OpenMeteoRow, OpenMeteoSource } from "../forecasts/types.js";

/** Build the cache key for the partition tuple (D-09 layout). */
export function cacheKeyForForecast(
  station: string,
  source: OpenMeteoSource,
  model: string,
  year: number,
  month: number,
): string {
  const mm = String(month).padStart(2, "0");
  const yyyy = String(year).padStart(4, "0");
  return `forecasts:${source}:${model}:${station}:${yyyy}:${mm}`;
}

function isLiveSource(source: OpenMeteoSource): boolean {
  return source === "open_meteo.live";
}

function isSeamlessSource(source: OpenMeteoSource): boolean {
  return source === "open_meteo.seamless";
}

function isCurrentUtcMonth(year: number, month: number, nowMs?: number): boolean {
  const d = new Date(nowMs ?? Date.now());
  return d.getUTCFullYear() === year && d.getUTCMonth() + 1 === month;
}

/** Read a forecast cache partition, or `null` on miss / ineligible / current-month. */
export async function readForecastCache(
  store: CacheStore,
  station: string,
  source: OpenMeteoSource,
  model: string,
  year: number,
  month: number,
): Promise<OpenMeteoRow[] | null> {
  if (isLiveSource(source) || isSeamlessSource(source)) return null;
  if (isCurrentUtcMonth(year, month)) return null;
  const key = cacheKeyForForecast(station, source, model, year, month);
  const got = await store.get<OpenMeteoRow[]>(key);
  return got;
}

/** Atomically write a forecast cache partition.
 *
 * No-op on:
 *   - source = open_meteo.live (rolling)
 *   - source = open_meteo.seamless (banned)
 *   - (year, month) = current UTC month
 *   - empty rows
 */
export async function writeForecastCache(
  store: CacheStore,
  station: string,
  source: OpenMeteoSource,
  model: string,
  year: number,
  month: number,
  rows: ReadonlyArray<OpenMeteoRow>,
): Promise<void> {
  if (isLiveSource(source) || isSeamlessSource(source)) return;
  if (isCurrentUtcMonth(year, month)) return;
  if (rows.length === 0) return;
  const key = cacheKeyForForecast(station, source, model, year, month);
  await store.withLock(key, async () => {
    await store.set(key, [...rows]);
  });
}

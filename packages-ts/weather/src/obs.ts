// Phase 21 21-04 — obs(station, from, to, opts?) public function.
//
// Port of Python `tw.weather.obs(station, start, end, source=None,
// strategy='auto')` — the Phase 7 ingest-planner smart-router. Picks
// between three fetch strategies based on window size + caller intent:
//
//   - `exact_window` — one-off ≤7-day window; fetches the exact bytes
//     the caller asked for, no year-padding. Cheapest path.
//   - `warm_cache` — year-aligned cache layout; the same orchestration
//     research() uses. Best for callers that will hit overlapping
//     windows.
//   - `hosted` — precomputed-API seam; raises DataAvailabilityError
//     until v0.2.x ships the hosted ingest endpoint (D-06).
//   - `auto` (default) — routes to `exact_window` when (toDate-fromDate)
//     ≤ 7 days, else `warm_cache`. Threshold matches Python's heuristic.
//
// Per D-06, the TS adaptations differ from Python in storage (IndexedDB
// browser / Node FS server instead of parquet) but match Python in
// strategy semantics + raised exceptions.

import { DataAvailabilityError } from "@mostlyrightmd/core";

import { fetchAwcMetars } from "./_fetchers/awc.js";
import { downloadIemAsos } from "./_fetchers/iem-asos.js";
import { awcToObservation } from "./_parsers/awc.js";
import { parseIemCsv } from "./_parsers/iem.js";
import type { ObsOptions, ObsRow, ObsStrategy } from "./obs.types.js";

/** Day count between two ISO YYYY-MM-DD strings (inclusive). */
function daysBetween(fromDate: string, toDate: string): number {
  const from = Date.UTC(
    Number.parseInt(fromDate.slice(0, 4), 10),
    Number.parseInt(fromDate.slice(5, 7), 10) - 1,
    Number.parseInt(fromDate.slice(8, 10), 10),
  );
  const to = Date.UTC(
    Number.parseInt(toDate.slice(0, 4), 10),
    Number.parseInt(toDate.slice(5, 7), 10) - 1,
    Number.parseInt(toDate.slice(8, 10), 10),
  );
  return Math.round((to - from) / (24 * 60 * 60 * 1000)) + 1;
}

/** Resolve `auto` to the concrete strategy chosen by the smart-router. */
export function resolveAutoStrategy(fromDate: string, toDate: string): ObsStrategy {
  // Python heuristic: 7-day or smaller windows route to exact_window
  // (one-off cold fetch ≤ 2 MB estimated payload); larger windows route
  // to warm_cache (year-aligned cache layout, reusable across calls).
  return daysBetween(fromDate, toDate) <= 7 ? "exact_window" : "warm_cache";
}

// Field names mirror the canonical Observation interface from
// `_parsers/awc.ts`. ObsRow uses the same snake_case shape so cross-
// language code stays symmetric with Python. Precipitation is stored in
// inches at the source (`precip_1hr_inches`); we surface it as
// `precip_mm_1h` per the Python ObsRow contract, so the conversion
// (inches × 25.4 = mm) happens at the projection boundary.

function inchesToMm(inches: number | null | undefined): number | null {
  if (inches === null || inches === undefined) return null;
  return inches * 25.4;
}

function mbToInhg(mb: number | null | undefined): number | null {
  if (mb === null || mb === undefined) return null;
  return mb * 0.029529983071445;
}

function fromObservation(o: NonNullable<ReturnType<typeof awcToObservation>>): ObsRow {
  const tempC = o.temp_c ?? null;
  const dewC = o.dewpoint_c ?? null;
  return {
    station: o.station_code,
    observed_at: o.observed_at,
    source: o.source,
    temp_c: tempC,
    temp_f: tempC !== null ? tempC * (9 / 5) + 32 : null,
    dewpoint_c: dewC,
    dewpoint_f: dewC !== null ? dewC * (9 / 5) + 32 : null,
    wind_speed_kts: o.wind_speed_kt ?? null,
    wind_direction_deg: o.wind_dir_degrees ?? null,
    pressure_inhg: mbToInhg(o.sea_level_pressure_mb),
    precip_mm_1h: inchesToMm(o.precip_1hr_inches),
    raw_metar: o.raw_metar ?? null,
  };
}

/**
 * IEM fetch helper. Phase 21 21-04 fix-iter-3 (codex HIGH): the byte-range
 * URL the upstream IEM ASOS endpoint accepts is honored by `downloadIemAsos`
 * — passing date-bounded `start`/`end` produces a date-bounded payload.
 *
 *   - `exact_window` strategy: pass the caller's [fromDate, toDate] verbatim.
 *     A 1-day call pulls ~1 day of bytes, not a whole year. Matches Python
 *     `obs(strategy="exact_window")` semantics.
 *   - `warm_cache` strategy: pad to year-boundaries to maximize cache reuse
 *     for callers that hit overlapping windows. Matches Python
 *     `obs(strategy="warm_cache")` semantics.
 *
 * Post-fetch trim still runs in both cases — the upstream may include
 * boundary observations slightly outside [fromDate, toDate] depending on
 * METAR reporting cadence.
 */
async function fetchIemForWindow(
  station: string,
  fromDate: string,
  toDate: string,
  resolvedStrategy: Exclude<ObsStrategy, "auto" | "hosted">,
): Promise<ObsRow[]> {
  const out: ObsRow[] = [];

  if (resolvedStrategy === "exact_window") {
    // Date-bounded fetch — pull only the bytes the caller asked for.
    const chunks = await downloadIemAsos(station, fromDate, toDate, {
      reportType: 3,
      politenessMs: 1000,
    });
    for (const chunk of chunks) {
      const rows = parseIemCsv(chunk.csv, { observationTypeOverride: "METAR" });
      for (const r of rows) {
        const d = r.observed_at.slice(0, 10);
        if (d >= fromDate && d <= toDate) out.push(fromObservation(r));
      }
    }
    return out;
  }

  // warm_cache: span the [fromYear, toYear] calendar-year range so future
  // calls hitting overlapping windows can reuse cached year-chunks.
  const fromYear = Number.parseInt(fromDate.slice(0, 4), 10);
  const toYear = Number.parseInt(toDate.slice(0, 4), 10);
  for (let year = fromYear; year <= toYear; year++) {
    const chunks = await downloadIemAsos(station, `${year}-01-01`, `${year}-12-31`, {
      reportType: 3,
      politenessMs: 1000,
    });
    for (const chunk of chunks) {
      const rows = parseIemCsv(chunk.csv, { observationTypeOverride: "METAR" });
      for (const r of rows) {
        const d = r.observed_at.slice(0, 10);
        if (d >= fromDate && d <= toDate) out.push(fromObservation(r));
      }
    }
  }
  return out;
}

async function fetchAwcForWindow(
  station: string,
  fromDate: string,
  toDate: string,
): Promise<ObsRow[]> {
  const raw = await fetchAwcMetars([station]);
  const out: ObsRow[] = [];
  for (const r of raw) {
    const obs = awcToObservation(r);
    if (obs === null) continue;
    const d = obs.observed_at.slice(0, 10);
    if (d >= fromDate && d <= toDate) out.push(fromObservation(obs));
  }
  return out;
}

async function fetchByStrategy(
  station: string,
  fromDate: string,
  toDate: string,
  resolvedStrategy: Exclude<ObsStrategy, "auto" | "hosted">,
  source: ObsOptions["source"],
): Promise<ObsRow[]> {
  // Phase 21 21-04 fix-iter-3 (codex HIGH): `resolvedStrategy` now drives
  // the IEM fetch shape. `exact_window` issues a date-bounded request so
  // small calls pull small payloads (matches Python's Phase 7 ingest-
  // planner semantics); `warm_cache` pads to year-boundaries so
  // overlapping callers reuse cached chunks. AWC is always the live
  // 168-hour endpoint regardless of strategy — the request shape doesn't
  // change with strategy in either Python or TS.
  const wantsIem = source === null || source === undefined || source === "iem";
  const wantsAwc = source === null || source === undefined || source === "awc";

  const tasks: Promise<ObsRow[]>[] = [];
  if (wantsIem) tasks.push(fetchIemForWindow(station, fromDate, toDate, resolvedStrategy));
  if (wantsAwc) tasks.push(fetchAwcForWindow(station, fromDate, toDate).catch(() => []));

  const results = await Promise.all(tasks);
  return results.flat();
}

/**
 * Fetch raw observations for a station's window.
 *
 * Matches Python `tw.weather.obs(station, start, end, source=None,
 * strategy='auto')` signature. The strategy enum selects between the
 * smart-router's three concrete fetch paths.
 *
 * @param station    ICAO code (e.g. "KNYC")
 * @param fromDate   ISO date `YYYY-MM-DD` (inclusive)
 * @param toDate     ISO date `YYYY-MM-DD` (inclusive)
 * @param opts       optional source filter + strategy mode
 * @returns          flat array of ObsRow (each row is a single METAR observation)
 * @throws DataAvailabilityError when strategy='hosted' (v0.2.x deferral)
 * @throws TypeError when strategy is not in the accepted enum
 */
export async function obs(
  station: string,
  fromDate: string,
  toDate: string,
  opts: ObsOptions = {},
): Promise<ReadonlyArray<ObsRow>> {
  const strategy = opts.strategy ?? "auto";
  const source = opts.source ?? null;

  // Phase 21 21-09 fix-iter-1: reject source values that have no TS fetcher
  // wiring loudly rather than silently returning [] (codex+ts-architect
  // CRITICAL). `ghcnh` is a documented Python filter but the GHCNh fetcher
  // is not wired through `fetchByStrategy` in TS yet — surface the gap as
  // DataAvailabilityError(reason="model_unavailable") so consumers see the
  // missing wiring instead of empty rows.
  if (source === "ghcnh") {
    throw new DataAvailabilityError({
      reason: "model_unavailable",
      source: "obs.ghcnh",
      hint:
        "source='ghcnh' is a valid Python `obs()` filter but the GHCNh " +
        "fetcher path is not yet wired in the TypeScript SDK. Use " +
        "source='iem' or source='awc' (or omit `source` for merged) until " +
        "the TS GHCNh fetcher ships.",
    });
  }

  if (strategy === "hosted") {
    throw new DataAvailabilityError({
      reason: "model_unavailable",
      source: "obs-hosted-stub",
      hint:
        "hosted ingest API ships in v0.2.x — use strategy='exact_window' " +
        "or 'warm_cache' for v1.x. See " +
        "https://mostlyright.md/docs/sdk/typescript/ingest-strategies",
    });
  }

  let resolved: Exclude<ObsStrategy, "auto" | "hosted">;
  if (strategy === "auto") {
    resolved = resolveAutoStrategy(fromDate, toDate) as Exclude<ObsStrategy, "auto" | "hosted">;
  } else if (strategy === "exact_window" || strategy === "warm_cache") {
    resolved = strategy;
  } else {
    throw new TypeError(
      `obs: unknown strategy "${String(strategy)}" — expected one of: auto, exact_window, warm_cache, hosted`,
    );
  }

  return fetchByStrategy(station, fromDate, toDate, resolved, source);
}

export type {
  ObsOptions,
  ObsRow,
  ObsSourceFilter,
  ObsStrategy,
} from "./obs.types.js";

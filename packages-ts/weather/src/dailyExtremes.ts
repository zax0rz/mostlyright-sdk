// Phase 21 21-05 — dailyExtremes(station, from, to, opts?) fetch+rollup wrapper.
//
// Matches Python `mostlyright.international.daily_extremes(station, from,
// to, merge='live_v1')` signature so cross-language code stays symmetric.
// Composes:
//   1. STATIONS-registry lookup for the station's IANA timezone.
//   2. Source fetch per merge mode (IEM ASOS for historical depth +
//      optional AWC for the live window).
//   3. `internationalDailyExtremes(rows, {stationTz, precision})` rollup.
//   4. Projection of the existing `DailyExtreme` (TS) shape into the
//      Python-mirroring `DailyExtremeRow` (date/tmin_f/tmax_f/.../n_obs).
//
// US ASOS stations get integer-°F precision (Phase 18 invariant); other
// stations get 0.1-precision values. The integer-°F detection key is the
// `country === "US"` field on the STATIONS registry.
//
// Note: GHCNh has CORS issues in browser per `.planning/research/TS-CORS-MATRIX.md`
// — `merge="live_v1"` in this v1 wrapper only composes IEM + AWC. Adding
// GHCNh requires the Node-only path; documented for a follow-up.

import { STATIONS } from "@mostlyrightmd/core";

import {
  type DailyExtreme,
  type InternationalRow,
  internationalDailyExtremes,
} from "@mostlyrightmd/core/discovery";
import { fetchAwcMetars } from "./_fetchers/awc.js";
import { downloadIemAsos } from "./_fetchers/iem-asos.js";
import { awcToObservation } from "./_parsers/awc.js";
import { parseIemCsv } from "./_parsers/iem.js";
import type {
  DailyExtremeRow,
  DailyExtremesMergeMode,
  DailyExtremesOptions,
} from "./dailyExtremes.types.js";

const LOW_COVERAGE_THRESHOLD = 12;

/**
 * Phase 21 21-05 fix-iter-2 (codex CRITICAL): `fromDate`/`toDate` are
 * station-LOCAL dates, but `row.observed_at` is UTC. Filtering UTC date
 * prefix against local date prefix drops tz-edge observations that fall
 * on adjacent UTC days but the local target day (e.g. for a UTC+9
 * station, `2025-01-06 23:30 local` is `2025-01-06 14:30Z` which has UTC
 * prefix `2025-01-06` — OK — but `2025-01-06 02:00 local` is
 * `2025-01-05 17:00Z` which has UTC prefix `2025-01-05` and would be
 * dropped pre-fix).
 *
 * Mitigation: widen the pre-rollup window by ±1 UTC day so every
 * station-local observation in [fromDate, toDate] is captured regardless
 * of tz offset. The `internationalDailyExtremes()` rollup downstream
 * re-projects observations into station-local days; we then clip the
 * resulting rows back to the caller's [fromDate, toDate] using the
 * station-local `localDate` field on each rollup row.
 */
function addUtcDays(iso: string, days: number): string {
  const [yStr, mStr, dStr] = iso.split("-");
  const dt = new Date(Date.UTC(Number(yStr), Number(mStr) - 1, Number(dStr)));
  dt.setUTCDate(dt.getUTCDate() + days);
  const yyyy = dt.getUTCFullYear();
  const mm = String(dt.getUTCMonth() + 1).padStart(2, "0");
  const dd = String(dt.getUTCDate()).padStart(2, "0");
  return `${yyyy}-${mm}-${dd}`;
}

interface StationLookup {
  tz: string;
  isUs: boolean;
}

function lookupStation(icao: string): StationLookup {
  const upper = icao.toUpperCase();
  for (const s of STATIONS) {
    if (s.icao === upper) {
      return { tz: s.tz, isUs: s.country === "US" };
    }
  }
  throw new Error(`dailyExtremes: station "${icao}" not in registry — check STATIONS catalog`);
}

function cToF(c: number | null): number | null {
  if (c === null) return null;
  return c * (9 / 5) + 32;
}

function roundHalfUp(value: number, decimals: number): number {
  const m = 10 ** decimals;
  return Math.round(value * m) / m;
}

async function fetchIemAsosObservations(
  station: string,
  fromDate: string,
  toDate: string,
): Promise<InternationalRow[]> {
  // Lazy minimal port of the research() yearly-chunking loop. For the
  // window-bounded wrapper we just span the [from, to] year range.
  const fromYear = Number.parseInt(fromDate.slice(0, 4), 10);
  const toYear = Number.parseInt(toDate.slice(0, 4), 10);
  const out: InternationalRow[] = [];
  for (let year = fromYear; year <= toYear; year++) {
    const chunks = await downloadIemAsos(station, `${year}-01-01`, `${year}-12-31`, {
      reportType: 3,
      politenessMs: 1000,
    });
    for (const chunk of chunks) {
      const parsed = parseIemCsv(chunk.csv, { observationTypeOverride: "METAR" });
      for (const row of parsed) {
        // Filter to the requested window. The canonical Observation field
        // is `precip_1hr_inches` (inches); InternationalRow expects mm —
        // convert at the boundary so the per-day precip rollup is in mm.
        // Phase 21 21-05 fix-iter-2 (codex CRITICAL): pre-rollup filter uses
        // the UTC date prefix against the widened-by-±1-day UTC window.
        // The caller's [fromDate, toDate] is station-LOCAL; observations
        // that fall on the adjacent UTC day but the local target day must
        // be kept so internationalDailyExtremes() can bin them into the
        // correct station-local bucket. Output is clipped back to the
        // caller's [fromDate, toDate] post-rollup using `localDate`.
        const obsDate = row.observed_at.slice(0, 10);
        if (obsDate >= fromDate && obsDate <= toDate) {
          const precipInches = row.precip_1hr_inches ?? null;
          out.push({
            observed_at: row.observed_at,
            temp_c: row.temp_c ?? null,
            precip_mm_1h: precipInches !== null ? precipInches * 25.4 : null,
            source: row.source,
          });
        }
      }
    }
  }
  return out;
}

async function fetchAwcObservations(
  station: string,
  fromDate: string,
  toDate: string,
): Promise<InternationalRow[]> {
  // AWC serves the last 168h; the wrapper still queries even if the
  // requested window straddles that horizon — sparse responses are
  // surfaced via the low_coverage gate.
  const raw = await fetchAwcMetars([station]);
  const out: InternationalRow[] = [];
  for (const r of raw) {
    const obs = awcToObservation(r);
    if (obs === null) continue;
    // Phase 21 21-09 fix-iter-1 (ts-architect HIGH): symmetric date-prefix
    // comparison on both bounds (see fetchIemObservations comment above).
    const obsDate = obs.observed_at.slice(0, 10);
    if (obsDate >= fromDate && obsDate <= toDate) {
      const precipInches = obs.precip_1hr_inches ?? null;
      out.push({
        observed_at: obs.observed_at,
        temp_c: obs.temp_c ?? null,
        precip_mm_1h: precipInches !== null ? precipInches * 25.4 : null,
        source: obs.source,
      });
    }
  }
  return out;
}

async function fetchForMode(
  station: string,
  fromDate: string,
  toDate: string,
  mode: DailyExtremesMergeMode,
): Promise<InternationalRow[]> {
  switch (mode) {
    case "iem_only":
      return fetchIemAsosObservations(station, fromDate, toDate);
    case "awc_only":
      return fetchAwcObservations(station, fromDate, toDate);
    case "live_v1": {
      const [iem, awc] = await Promise.all([
        fetchIemAsosObservations(station, fromDate, toDate),
        fetchAwcObservations(station, fromDate, toDate).catch(() => []),
      ]);
      return [...iem, ...awc];
    }
    default: {
      const _exhaustive: never = mode;
      throw new TypeError(`dailyExtremes: unknown merge mode "${String(_exhaustive)}"`);
    }
  }
}

function projectRow(station: string, d: DailyExtreme, isUs: boolean): DailyExtremeRow {
  const lowCoverage = d.nObs < LOW_COVERAGE_THRESHOLD;
  const decimals = isUs ? 0 : 1;
  const precipIn =
    d.precipMm !== null && d.precipMm !== undefined ? roundHalfUp(d.precipMm / 25.4, 2) : null;
  if (lowCoverage) {
    return {
      date: d.localDate,
      station,
      tmin_f: null,
      tmax_f: null,
      tmean_f: null,
      precip_in: precipIn,
      low_coverage: true,
      n_obs: d.nObs,
    };
  }
  return {
    date: d.localDate,
    station,
    tmin_f: d.tempMinF !== null ? roundHalfUp(d.tempMinF, decimals) : null,
    tmax_f: d.tempMaxF !== null ? roundHalfUp(d.tempMaxF, decimals) : null,
    tmean_f: d.tempMeanC !== null ? roundHalfUp(cToF(d.tempMeanC) as number, decimals) : null,
    precip_in: precipIn,
    low_coverage: false,
    n_obs: d.nObs,
  };
}

/**
 * Compute per-day tmin/tmax/tmean/precip for a station's window.
 *
 * Matches Python `mostlyright.international.daily_extremes` signature.
 * Day-bucketing uses the station's IANA local tz from the STATIONS
 * registry; US ASOS stations get integer-°F precision (Phase 18
 * invariant); other stations get 0.1-precision values.
 *
 * @param station  ICAO code (e.g. "KNYC")
 * @param fromDate ISO date `YYYY-MM-DD` (inclusive, station-local)
 * @param toDate   ISO date `YYYY-MM-DD` (inclusive, station-local)
 * @param opts     optional merge mode (default `"live_v1"`)
 * @returns array of DailyExtremeRow, one per station-local day
 * @throws Error if station is not in the STATIONS registry
 */
export async function dailyExtremes(
  station: string,
  fromDate: string,
  toDate: string,
  opts: DailyExtremesOptions = {},
): Promise<ReadonlyArray<DailyExtremeRow>> {
  const { tz, isUs } = lookupStation(station);
  const merge = opts.merge ?? "live_v1";

  // Phase 21 21-05 fix-iter-2 (codex CRITICAL): widen the pre-rollup UTC
  // window by ±1 day so station-local-day observations at tz edges are
  // not silently dropped (e.g. UTC+14 stations have local 23:00 falling
  // on the previous UTC day). The rollup re-projects into the
  // station-local IANA day; we then clip the rollup output back to the
  // caller's [fromDate, toDate] via the station-local `localDate` field
  // so the public surface still returns exactly the requested days.
  const fetchFrom = addUtcDays(fromDate, -1);
  const fetchTo = addUtcDays(toDate, 1);
  const rows = await fetchForMode(station, fetchFrom, fetchTo, merge);

  const extremes = internationalDailyExtremes(rows, {
    stationTz: tz,
    precision: isUs ? 1 : 0,
  });

  return extremes
    .filter((d) => d.localDate >= fromDate && d.localDate <= toDate)
    .map((d) => projectRow(station.toUpperCase(), d, isUs));
}

export type {
  DailyExtremeRow,
  DailyExtremesMergeMode,
  DailyExtremesOptions,
} from "./dailyExtremes.types.js";

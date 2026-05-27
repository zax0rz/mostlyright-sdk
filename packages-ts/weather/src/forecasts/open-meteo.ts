// Phase 20 OM-07 + OM-08 — Open-Meteo TS fetcher (mirrors Python
// `packages/weather/src/mostlyright/weather/_fetchers/_open_meteo.py`).
//
// Endpoints (Phase 20 D-01):
//   - Previous Runs:    https://previous-runs-api.open-meteo.com/v1/forecast
//   - Single Runs:      https://single-runs-api.open-meteo.com/v1/forecast
//   - Live Forecast:    https://api.open-meteo.com/v1/forecast
//   - Historical (SEAMLESS):
//                       https://historical-forecast-api.open-meteo.com/v1/forecast
//     BANNED unless caller passes allowLeakage=true.
//
// Browser-safe: uses `fetch` + AbortController only (no Node-only APIs).

import { OpenMeteoSeamlessLeakageError } from "@mostlyrightmd/core";

import {
  CYCLE_HOURS,
  OPEN_METEO_MODELS,
  PUBLISH_LAG_HOURS,
  issuedAtFromLiveCycleMathMs,
  issuedAtFromPreviousDayMs,
} from "./open-meteo-models.js";
import type {
  OpenMeteoMode,
  OpenMeteoModel,
  OpenMeteoOptions,
  OpenMeteoRow,
  OpenMeteoSource,
} from "./types.js";

export const OPEN_METEO_PREVIOUS_RUNS_URL = "https://previous-runs-api.open-meteo.com/v1/forecast";
export const OPEN_METEO_SINGLE_RUNS_URL = "https://single-runs-api.open-meteo.com/v1/forecast";
export const OPEN_METEO_LIVE_URL = "https://api.open-meteo.com/v1/forecast";
export const OPEN_METEO_SEAMLESS_URL = "https://historical-forecast-api.open-meteo.com/v1/forecast";

const VALID_MODES: ReadonlySet<OpenMeteoMode> = new Set(["training", "live", "seamless"]);

const HOURLY_VARIABLES = [
  "temperature_2m",
  "dew_point_2m",
  "apparent_temperature",
  "wind_speed_10m",
  "wind_direction_10m",
  "wind_gusts_10m",
  "precipitation",
  "precipitation_probability",
  "cloud_cover",
  "surface_pressure",
  "pressure_msl",
  "shortwave_radiation",
  "direct_radiation",
  "cape",
  "freezing_level_height",
  "snow_depth",
  "visibility",
  "weather_code",
] as const;

// Built-in station coordinates for the Phase 20 regression fixtures.
const STATION_COORDS: ReadonlyMap<string, { lat: number; lon: number }> = new Map([
  ["KNYC", { lat: 40.78, lon: -73.97 }],
  ["KORD", { lat: 41.98, lon: -87.9 }],
  ["KDEN", { lat: 39.86, lon: -104.67 }],
  ["KMIA", { lat: 25.79, lon: -80.29 }],
  ["KSEA", { lat: 47.45, lon: -122.31 }],
]);

function resolveCoords(station: string): { lat: number; lon: number } {
  const coords = STATION_COORDS.get(station);
  if (coords) return coords;
  throw new Error(
    `openMeteoForecasts: station=${JSON.stringify(station)} not in built-in coords table; add to STATION_COORDS`,
  );
}

function buildHourlyParam(endpoint: string): string {
  if (endpoint === OPEN_METEO_PREVIOUS_RUNS_URL) {
    return HOURLY_VARIABLES.map((v) => `${v}_previous_day1`).join(",");
  }
  return HOURLY_VARIABLES.join(",");
}

function dispatchEndpoint(
  mode: OpenMeteoMode,
  opts: { allowLeakage: boolean; model: OpenMeteoModel; issuedAt: string | undefined },
): string {
  if (mode === "training") {
    return opts.issuedAt ? OPEN_METEO_SINGLE_RUNS_URL : OPEN_METEO_PREVIOUS_RUNS_URL;
  }
  if (mode === "live") {
    return OPEN_METEO_LIVE_URL;
  }
  if (mode === "seamless") {
    if (!opts.allowLeakage) {
      throw new OpenMeteoSeamlessLeakageError(
        "Open-Meteo seamless endpoint is banned for training data " +
          "(see Tarabcak/mostlyright#70). Pass allowLeakage: true to opt in; " +
          "LeakageDetector will still reject these rows when asOf is asserted.",
        {
          model: opts.model,
          endpointUrl: OPEN_METEO_SEAMLESS_URL,
        },
      );
    }
    return OPEN_METEO_SEAMLESS_URL;
  }
  throw new Error(`openMeteoForecasts: unknown mode ${JSON.stringify(mode)}`);
}

function isoIfNotNull(ms: number | null): string | null {
  return ms === null ? null : new Date(ms).toISOString();
}

function maybeNumber(value: unknown): number | null {
  if (value === null || value === undefined) return null;
  const n = typeof value === "number" ? value : Number(value);
  return Number.isFinite(n) ? n : null;
}

function pickHourlyValue(
  hourly: Record<string, unknown[]>,
  key: string,
  isPreviousRuns: boolean,
  idx: number,
): unknown {
  const arr = isPreviousRuns ? (hourly[`${key}_previous_day1`] ?? hourly[key]) : hourly[key];
  if (!Array.isArray(arr) || idx >= arr.length) return null;
  return arr[idx];
}

/**
 * Fetch Open-Meteo forecasts for `station` in `[fromDate, toDate]`.
 *
 * Phase 20 OM-07. Mirrors Python `fetch_open_meteo(...)`. Default
 * `mode: "training"` hits Previous Runs API; with `issuedAt: "..."`
 * dispatches to Single Runs API. `mode: "live"` hits Live Forecast API
 * with cycle-math fallback `issuedAt`. `mode: "seamless"` requires
 * `allowLeakage: true` (BANNED for training data).
 */
export async function openMeteoForecasts(
  station: string,
  fromDate: string,
  toDate: string,
  opts: OpenMeteoOptions = {},
): Promise<OpenMeteoRow[]> {
  const model = opts.model ?? "gfs_global";
  if (!OPEN_METEO_MODELS.has(model)) {
    throw new Error(
      `openMeteoForecasts: model must be one of OPEN_METEO_MODELS (36 keys); got ${JSON.stringify(model)}`,
    );
  }
  const mode = opts.mode ?? "training";
  if (!VALID_MODES.has(mode)) {
    throw new Error(
      `openMeteoForecasts: mode must be one of training,live,seamless; got ${JSON.stringify(mode)}`,
    );
  }
  const endpoint = dispatchEndpoint(mode, {
    allowLeakage: opts.allowLeakage ?? false,
    model,
    issuedAt: opts.issuedAt,
  });

  const { lat, lon } = resolveCoords(station);
  const params = new URLSearchParams();
  params.set("latitude", String(lat));
  params.set("longitude", String(lon));
  params.set("start_date", fromDate);
  params.set("end_date", toDate);
  params.set("hourly", buildHourlyParam(endpoint));
  params.set("models", model);
  params.set("timezone", "UTC");
  if (endpoint === OPEN_METEO_SINGLE_RUNS_URL && opts.issuedAt) {
    params.set("run", opts.issuedAt);
  }

  const fetchFn = opts.fetchFn ?? fetch;
  const url = `${endpoint}?${params.toString()}`;
  const resp = await fetchFn(url);
  if (resp.status === 404) return [];
  if (!resp.ok) {
    throw new Error(`openMeteoForecasts: HTTP ${resp.status} on ${url}`);
  }
  const payload = (await resp.json()) as {
    hourly?: { time?: string[]; [k: string]: unknown };
  };
  const hourly = payload.hourly ?? {};
  const times = hourly.time ?? [];
  if (times.length === 0) return [];

  let source: OpenMeteoSource;
  if (endpoint === OPEN_METEO_PREVIOUS_RUNS_URL) {
    source = "open_meteo.previous_runs";
  } else if (endpoint === OPEN_METEO_SINGLE_RUNS_URL) {
    source = "open_meteo.single_run";
  } else if (endpoint === OPEN_METEO_LIVE_URL) {
    source = "open_meteo.live";
  } else {
    source = "open_meteo.seamless";
  }

  const cycleHours = CYCLE_HOURS.get(model) ?? [0, 6, 12, 18];
  const publishLag = PUBLISH_LAG_HOURS.get(model) ?? 6;
  const retrievedAt = new Date().toISOString();
  const nowMs = Date.now();

  const rows: OpenMeteoRow[] = [];
  for (let i = 0; i < times.length; i++) {
    const tIso = times[i] ?? "";
    if (!tIso) continue;
    const validAtMs = Date.parse(tIso.endsWith("Z") || tIso.includes("+") ? tIso : `${tIso}Z`);
    let issuedAtMs: number | null;
    if (source === "open_meteo.previous_runs") {
      issuedAtMs = issuedAtFromPreviousDayMs(validAtMs, 1, cycleHours);
    } else if (source === "open_meteo.single_run") {
      issuedAtMs = opts.issuedAt
        ? Date.parse(
            opts.issuedAt.endsWith("Z") || opts.issuedAt.includes("+")
              ? opts.issuedAt
              : `${opts.issuedAt}Z`,
          )
        : null;
    } else if (source === "open_meteo.live") {
      issuedAtMs = issuedAtFromLiveCycleMathMs(nowMs, publishLag, cycleHours);
    } else {
      // seamless — null by design
      issuedAtMs = null;
    }
    const validAtIso = new Date(validAtMs).toISOString();
    const forecastHour =
      issuedAtMs === null ? null : Math.round((validAtMs - issuedAtMs) / 3_600_000);
    const isPrev = source === "open_meteo.previous_runs";
    const h = hourly as Record<string, unknown[]>;
    const popPct = maybeNumber(pickHourlyValue(h, "precipitation_probability", isPrev, i));
    rows.push({
      station,
      model,
      issuedAt: isoIfNotNull(issuedAtMs),
      validAt: validAtIso,
      forecastHour,
      tempC: maybeNumber(pickHourlyValue(h, "temperature_2m", isPrev, i)),
      dewPointC: maybeNumber(pickHourlyValue(h, "dew_point_2m", isPrev, i)),
      apparentTempC: maybeNumber(pickHourlyValue(h, "apparent_temperature", isPrev, i)),
      windSpeedMs: maybeNumber(pickHourlyValue(h, "wind_speed_10m", isPrev, i)),
      windDirDeg: maybeNumber(pickHourlyValue(h, "wind_direction_10m", isPrev, i)),
      windGustsMs: maybeNumber(pickHourlyValue(h, "wind_gusts_10m", isPrev, i)),
      precipProbability: popPct === null ? null : popPct / 100,
      precipitationMm: maybeNumber(pickHourlyValue(h, "precipitation", isPrev, i)),
      cloudCoverPct: maybeNumber(pickHourlyValue(h, "cloud_cover", isPrev, i)),
      surfacePressureHpa: maybeNumber(pickHourlyValue(h, "surface_pressure", isPrev, i)),
      pressureMslHpa: maybeNumber(pickHourlyValue(h, "pressure_msl", isPrev, i)),
      shortwaveRadiationWm2: maybeNumber(pickHourlyValue(h, "shortwave_radiation", isPrev, i)),
      directRadiationWm2: maybeNumber(pickHourlyValue(h, "direct_radiation", isPrev, i)),
      capeJkg: maybeNumber(pickHourlyValue(h, "cape", isPrev, i)),
      freezingLevelM: maybeNumber(pickHourlyValue(h, "freezing_level_height", isPrev, i)),
      snowDepthM: maybeNumber(pickHourlyValue(h, "snow_depth", isPrev, i)),
      visibilityM: maybeNumber(pickHourlyValue(h, "visibility", isPrev, i)),
      weatherCode: maybeNumber(pickHourlyValue(h, "weather_code", isPrev, i)),
      source,
      retrievedAt,
    });
  }
  return rows;
}

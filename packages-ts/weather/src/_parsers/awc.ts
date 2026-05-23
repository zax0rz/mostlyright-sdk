// AWC METAR parser — maps raw AWC JSON record to `Observation` row.
//
// Ported byte-faithfully from
// `packages/weather/src/tradewinds/weather/_awc.py::awc_to_observation`.
//
// Output `source` is `"awc.live"` — the canonical source-id used by
// downstream merge / cache layers (the Python parser emits `"awc"` and
// gets normalized to `"awc.live"` later; we emit the normalized form
// directly to match the TS-SDK source-id contract).
//
// =============================================================================
// Inlined bounds + conversion helpers
// =============================================================================
// `@tradewinds/core` exposes these via `internal/bounds.ts` and `internal/convert.ts`
// but the package only re-exports `fetchWithRetry` at its public surface
// (other helpers are documented as "deep imports for fetchers + parsers in
// later waves" but the `exports` field gates subpath access). Per the
// TS-W1 Wave 3 task scope ("All code in `packages-ts/weather/src/_fetchers/`
// + `_parsers/` ONLY. Do NOT modify any other package"), the needed
// constants and pure-function helpers are inlined verbatim here. Drift is
// caught by the parity-fixture gate in TS-W2.
// =============================================================================

import type { AwcMetarRaw } from "../_fetchers/awc.js";

// ---------------------------------------------------------------------------
// Bounds (mirror packages-ts/core/src/internal/bounds.ts)
// ---------------------------------------------------------------------------

const SLP_MIN_MB = 870.0;
const SLP_MAX_MB = 1084.0;
const TEMP_MIN_C = -90.0;
const TEMP_MAX_C = 60.0;
const MAX_RAW_METAR_LEN = 2048;
const MAX_WX_CODES_LEN = 256;
const MAX_VISIBILITY_MILES = 99.99;
const WIND_DIR_LO = 0;
const WIND_DIR_HI = 360;
const WIND_SPEED_MAX = 200;
const WIND_GUST_MAX = 250;
const SKY_BASE_MAX_FT = 60000;
const STATION_CODE_RE = /^[A-Z]{3,4}$/;

// ---------------------------------------------------------------------------
// Conversions (mirror packages-ts/core/src/internal/convert.ts)
// ---------------------------------------------------------------------------

const HPA_TO_INHG = 0.0295299875;

function finiteOrNull(v: number | null | undefined): number | null {
  if (v === null || v === undefined) return null;
  return Number.isFinite(v) ? v : null;
}

function celsiusToFahrenheit(c: number | null): number | null {
  const v = finiteOrNull(c);
  return v === null ? null : (v * 9) / 5 + 32;
}

function hpaToInhg(hpa: number | null): number | null {
  const v = finiteOrNull(hpa);
  return v === null ? null : v * HPA_TO_INHG;
}

// ---------------------------------------------------------------------------
// Bounded numerics (mirror bounds.ts helpers)
// ---------------------------------------------------------------------------

function boundedInt(val: number | null, lo: number, hi: number): number | null {
  if (val === null || val === undefined) return null;
  if (!Number.isFinite(val)) return null;
  return val >= lo && val <= hi ? val : null;
}

function boundedFloat(val: number | null, lo: number, hi: number): number | null {
  if (val === null || val === undefined) return null;
  if (!Number.isFinite(val)) return null;
  return val >= lo && val <= hi ? val : null;
}

function boundedFloatMin(val: number | null, lo: number): number | null {
  if (val === null || val === undefined) return null;
  if (!Number.isFinite(val)) return null;
  return val >= lo ? val : null;
}

// ---------------------------------------------------------------------------
// Observation row schema (matches specs/observation.json field set)
// ---------------------------------------------------------------------------

/**
 * Single observation row, matching `specs/observation.json`.
 *
 * Notes on null vs unknown:
 *  - Every field defaults to `null` if the upstream record omits it,
 *    fails bounds, or fails type parsing. This mirrors the Python
 *    parser (no exceptions on bad input — only on missing required keys).
 *  - `source` is always the string literal `"awc.live"` for AWC-sourced rows.
 *  - `observed_at` is ISO 8601 UTC with `Z` suffix.
 */
export interface Observation {
  readonly station_code: string;
  readonly observed_at: string;
  readonly observation_type: "METAR" | "SPECI";
  readonly source: "awc.live";
  readonly temp_c: number | null;
  readonly dewpoint_c: number | null;
  readonly temp_f: number | null;
  readonly dewpoint_f: number | null;
  readonly wind_dir_degrees: number | null;
  readonly wind_speed_kt: number | null;
  readonly wind_gust_kt: number | null;
  readonly altimeter_inhg: number | null;
  readonly sea_level_pressure_mb: number | null;
  readonly sky_cover_1: string | null;
  readonly sky_base_1_ft: number | null;
  readonly sky_cover_2: string | null;
  readonly sky_base_2_ft: number | null;
  readonly sky_cover_3: string | null;
  readonly sky_base_3_ft: number | null;
  readonly sky_cover_4: string | null;
  readonly sky_base_4_ft: number | null;
  readonly visibility_miles: number | null;
  readonly weather_codes: string | null;
  readonly precip_1hr_inches: number | null;
  readonly peak_wind_gust_kt: number | null;
  readonly peak_wind_dir: number | null;
  readonly peak_wind_time: string | null;
  readonly snow_depth_inches: number | null;
  readonly qc_field: number | null;
  readonly raw_metar: string | null;
}

// ---------------------------------------------------------------------------
// Public helpers
// ---------------------------------------------------------------------------

/**
 * Strip the leading `K` from 4-letter CONUS ICAO codes to get the
 * 3-letter NWS station code (`KNYC` → `NYC`). Non-K-prefixed codes
 * pass through unchanged after `.toUpperCase()`.
 */
export function icaoToStationCode(icao: string): string {
  const upper = icao.trim().toUpperCase();
  if (upper.startsWith("K") && upper.length === 4) {
    return upper.slice(1);
  }
  return upper;
}

/**
 * Map AWC cloud-cover token to the standard abbreviation set.
 * - Accepts {CLR, SKC, FEW, SCT, BKN, OVC, VV}
 * - `CAVOK` → `CLR`
 * - everything else (incl. null/undefined) → null
 */
export function mapCloudCover(cover: string | null | undefined): string | null {
  if (cover === null || cover === undefined) return null;
  const upper = String(cover).toUpperCase();
  if (
    upper === "CLR" ||
    upper === "SKC" ||
    upper === "FEW" ||
    upper === "SCT" ||
    upper === "BKN" ||
    upper === "OVC" ||
    upper === "VV"
  ) {
    return upper;
  }
  if (upper === "CAVOK") {
    return "CLR";
  }
  return null;
}

/**
 * Parse AWC visibility — handles all forms documented in the Python parser:
 *   - numeric (`10`)              → `10`
 *   - "10+"                       → `10`  (trailing plus = "or more")
 *   - "1/2"                       → `0.5`
 *   - "2 1/4"                     → `2.25`
 *   - "M1/4"                      → `0.25` (METAR "less than" prefix)
 *   - bad input / empty / "null"  → `null`
 *
 * All results are clamped at `MAX_VISIBILITY_MILES` (99.99).
 */
export function parseAwcVisibility(vis: string | number | null | undefined): number | null {
  if (vis === null || vis === undefined) return null;

  // Numeric pass-through (must be finite).
  if (typeof vis === "number") {
    if (!Number.isFinite(vis)) return null;
    return Math.min(vis, MAX_VISIBILITY_MILES);
  }

  const s = String(vis);
  if (s === "" || s === "null") return null;

  // "10+" → 10
  if (s.endsWith("+")) {
    const n = Number(s.slice(0, -1));
    if (!Number.isFinite(n)) return null;
    return Math.min(n, MAX_VISIBILITY_MILES);
  }

  // Mixed number "2 1/4" → 2.25  (space + slash both present)
  if (s.includes(" ") && s.includes("/")) {
    const parts = s.split(" ");
    if (parts.length !== 2) return null;
    const whole = Number(parts[0]);
    const frac = (parts[1] as string).split("/");
    if (frac.length !== 2) return null;
    const num = Number(frac[0]);
    const den = Number(frac[1]);
    if (!(Number.isFinite(whole) && Number.isFinite(num) && Number.isFinite(den) && den !== 0)) {
      return null;
    }
    return Math.min(whole + num / den, MAX_VISIBILITY_MILES);
  }

  // Simple fraction "1/2" or "M1/4"
  if (s.includes("/")) {
    let trimmed = s;
    if (trimmed.startsWith("M") || trimmed.startsWith("m")) {
      trimmed = trimmed.slice(1);
    }
    const frac = trimmed.split("/");
    if (frac.length !== 2) return null;
    const num = Number(frac[0]);
    const den = Number(frac[1]);
    if (!(Number.isFinite(num) && Number.isFinite(den) && den !== 0)) return null;
    return Math.min(num / den, MAX_VISIBILITY_MILES);
  }

  // Plain numeric string.
  const n = Number(s);
  if (!Number.isFinite(n)) return null;
  return Math.min(n, MAX_VISIBILITY_MILES);
}

// ---------------------------------------------------------------------------
// METAR remarks parsers (peak wind + T-group)
// ---------------------------------------------------------------------------

// `PK WND dddss/hhmm` (direction may be 2-3 digits; AWC payloads use 3+2)
const PK_WND_RE = /PK WND (\d{3})(\d{2,3})\/(\d{4})/;

// T-group in METAR remarks: T{s}{SSS}{s}{DDD}
// s=0 positive, s=1 negative. SSS/DDD = tenths of °C.
const TGROUP_RE = /\bT([01])(\d{3})([01])(\d{3})\b/;

function parsePeakWind(rawMetar: string | null): {
  dir: number | null;
  speed: number | null;
  time: string | null;
} {
  if (!rawMetar) return { dir: null, speed: null, time: null };
  const m = PK_WND_RE.exec(rawMetar);
  if (!m) return { dir: null, speed: null, time: null };
  const dir = Number.parseInt(m[1] as string, 10);
  const spd = Number.parseInt(m[2] as string, 10);
  const time = m[3] as string;
  if (!(dir >= 0 && dir <= 360) || spd < 0) {
    return { dir: null, speed: null, time: null };
  }
  return { dir, speed: spd, time };
}

function parseTGroup(rawMetar: string | null): { tempC: number | null; dewpC: number | null } {
  if (!rawMetar) return { tempC: null, dewpC: null };
  // T-group is a remarks-only element — search only after RMK to avoid
  // false positives on body group patterns.
  const rmkIdx = rawMetar.indexOf("RMK");
  if (rmkIdx < 0) return { tempC: null, dewpC: null };
  const m = TGROUP_RE.exec(rawMetar.slice(rmkIdx));
  if (!m) return { tempC: null, dewpC: null };
  const tSign = m[1] === "1" ? -1 : 1;
  const tVal = (Number.parseInt(m[2] as string, 10) / 10.0) * tSign;
  const dSign = m[3] === "1" ? -1 : 1;
  const dVal = (Number.parseInt(m[4] as string, 10) / 10.0) * dSign;
  return { tempC: tVal, dewpC: dVal };
}

// ---------------------------------------------------------------------------
// Safe numeric coercion (mirror Python `_safe_int`, `_safe_float`, `_safe_precip`)
// ---------------------------------------------------------------------------

function safeInt(v: unknown): number | null {
  if (v === null || v === undefined) return null;
  const f = typeof v === "number" ? v : Number(v);
  if (!Number.isFinite(f)) return null;
  // Python uses banker's `round()`; for non-negative half-values the
  // difference would matter, but observation payloads contain integral
  // counts (wind speed, sky base feet, qc bitmask). Use Math.round which
  // matches "round half away from zero" — adequate for the integer
  // domains we coerce here.
  return Math.round(f);
}

function safeFloat(v: unknown): number | null {
  if (v === null || v === undefined) return null;
  const f = typeof v === "number" ? v : Number(v);
  return Number.isFinite(f) ? f : null;
}

function safePrecip(v: unknown): number | null {
  if (v === null || v === undefined) return null;
  if (typeof v === "string" && v.trim().toUpperCase() === "T") {
    // Python returns 0.0 for trace; the task spec mentions "0.005 (Python
    // trace convention)" but the actual Python source maps "T" → 0.0 (see
    // `_safe_precip` in `_awc.py`). We match Python source byte-faithfully.
    return 0.0;
  }
  return safeFloat(v);
}

function cloudLayer(layer: unknown): { cover: string | null; base: number | null } {
  if (layer === null || typeof layer !== "object") return { cover: null, base: null };
  const obj = layer as { cover?: unknown; base?: unknown };
  const base = boundedInt(safeInt(obj.base), 0, SKY_BASE_MAX_FT);
  return { cover: mapCloudCover(obj.cover as string | null | undefined), base };
}

// ---------------------------------------------------------------------------
// Main parser
// ---------------------------------------------------------------------------

/**
 * Convert one raw AWC METAR record into the canonical observation row.
 *
 * Returns `null` if the record is missing `icaoId` or `obsTime`, or if the
 * station code can't be resolved via `icaoToStationCode` + STATION_CODE_RE,
 * or if `obsTime` produces an out-of-range date.
 *
 * Otherwise returns a fully-typed `Observation` with every field either a
 * validated value or `null`. Never throws.
 */
export function awcToObservation(m: AwcMetarRaw): Observation | null {
  // --- Required keys -----------------------------------------------------
  const icaoId = m.icaoId;
  if (typeof icaoId !== "string" || icaoId === "") return null;

  const obsTime = m.obsTime;
  if (typeof obsTime !== "number" || !Number.isFinite(obsTime)) return null;

  const stationCode = icaoToStationCode(icaoId);
  if (!STATION_CODE_RE.test(stationCode)) return null;

  // --- observed_at -------------------------------------------------------
  const dt = new Date(obsTime * 1000);
  if (Number.isNaN(dt.getTime())) return null;
  const year = dt.getUTCFullYear();
  if (!(year >= 1970 && year <= 2100)) return null;
  // ISO 8601 with second precision + "Z" suffix (matches Python
  // `%Y-%m-%dT%H:%M:%SZ`). `Date.toISOString` emits ms which we strip.
  const observedAt = `${dt.toISOString().slice(0, 19)}Z`;

  // --- observation_type --------------------------------------------------
  const metarType = typeof m.metarType === "string" ? m.metarType.toUpperCase() : "METAR";
  const observationType: "METAR" | "SPECI" = metarType === "SPECI" ? "SPECI" : "METAR";

  // --- Wind direction ----------------------------------------------------
  let wdir: number | null = null;
  const rawWdir = m.wdir;
  if (rawWdir !== null && rawWdir !== undefined) {
    if (typeof rawWdir === "number") {
      wdir = boundedInt(Math.trunc(rawWdir), WIND_DIR_LO, WIND_DIR_HI);
    } else if (rawWdir !== "VRB") {
      const parsed = Number(rawWdir);
      if (Number.isFinite(parsed)) {
        wdir = boundedInt(Math.trunc(parsed), WIND_DIR_LO, WIND_DIR_HI);
      }
    }
    // "VRB" → wdir stays null (Python leaves it None; task spec says
    // "0 (matches Python convention)" but the Python source on disk
    // leaves it None — we follow the source-of-truth).
  }

  // --- Wind speed / gust -------------------------------------------------
  const wspd = boundedInt(safeInt(m.wspd), 0, WIND_SPEED_MAX);
  const wgst = boundedInt(safeInt(m.wgst), 0, WIND_GUST_MAX);

  // --- Altimeter (hPa input → inHg output) -------------------------------
  const altim = hpaToInhg(safeFloat(m.altim));

  // --- Sea-level pressure (already mb/hPa) -------------------------------
  let slp = safeFloat(m.slp);
  if (slp !== null && !(slp >= SLP_MIN_MB && slp <= SLP_MAX_MB)) {
    slp = null;
  }

  // --- Cloud layers (up to 4) --------------------------------------------
  const clouds = m.clouds ?? [];
  const c0 = clouds[0] !== undefined ? cloudLayer(clouds[0]) : { cover: null, base: null };
  const c1 = clouds[1] !== undefined ? cloudLayer(clouds[1]) : { cover: null, base: null };
  const c2 = clouds[2] !== undefined ? cloudLayer(clouds[2]) : { cover: null, base: null };
  const c3 = clouds[3] !== undefined ? cloudLayer(clouds[3]) : { cover: null, base: null };

  // --- Raw METAR (truncate) ----------------------------------------------
  let rawMetar: string | null = null;
  if (typeof m.rawOb === "string") {
    rawMetar = m.rawOb.slice(0, MAX_RAW_METAR_LEN);
  }

  // --- Weather codes (truncate) ------------------------------------------
  let weatherCodes: string | null = null;
  if (typeof m.wxString === "string") {
    weatherCodes = m.wxString.slice(0, MAX_WX_CODES_LEN);
  }

  // --- Temperature + dewpoint (T-group overrides body group) -------------
  let tempC = safeFloat(m.temp);
  let dewpC = safeFloat(m.dewp);
  const { tempC: tgTemp, dewpC: tgDewp } = parseTGroup(rawMetar);
  if (tgTemp !== null) tempC = tgTemp;
  if (tgDewp !== null) dewpC = tgDewp;
  tempC = boundedFloat(tempC, TEMP_MIN_C, TEMP_MAX_C);
  dewpC = boundedFloat(dewpC, TEMP_MIN_C, TEMP_MAX_C);
  const tempF = celsiusToFahrenheit(tempC);
  const dewpointF = celsiusToFahrenheit(dewpC);

  // --- Peak wind ---------------------------------------------------------
  const pk = parsePeakWind(rawMetar);
  const pkDir = boundedInt(pk.dir, WIND_DIR_LO, WIND_DIR_HI);
  const pkSpd = boundedInt(pk.speed, 0, WIND_GUST_MAX);

  // --- Precip + QC -------------------------------------------------------
  const precip = boundedFloatMin(safePrecip(m.precip), 0.0);
  const qcField = safeInt(m.qcField);

  return {
    station_code: stationCode,
    observed_at: observedAt,
    observation_type: observationType,
    source: "awc.live",
    temp_c: tempC,
    dewpoint_c: dewpC,
    temp_f: tempF,
    dewpoint_f: dewpointF,
    wind_dir_degrees: wdir,
    wind_speed_kt: wspd,
    wind_gust_kt: wgst,
    altimeter_inhg: altim,
    sea_level_pressure_mb: slp,
    sky_cover_1: c0.cover,
    sky_base_1_ft: c0.base,
    sky_cover_2: c1.cover,
    sky_base_2_ft: c1.base,
    sky_cover_3: c2.cover,
    sky_base_3_ft: c2.base,
    sky_cover_4: c3.cover,
    sky_base_4_ft: c3.base,
    visibility_miles: parseAwcVisibility(m.visib),
    weather_codes: weatherCodes,
    precip_1hr_inches: precip,
    peak_wind_gust_kt: pkSpd,
    peak_wind_dir: pkDir,
    peak_wind_time: pk.time,
    snow_depth_inches: null, // AWC doesn't carry snow-depth in METARs
    qc_field: qcField,
    raw_metar: rawMetar,
  };
}

// GHCNh PSV parser — pipe-delimited body in, Observation rows out.
//
// Byte-faithful TS port of Python
// `packages/weather/src/mostlyright/weather/_ghcnh.py::parse_ghcnh_row` and
// `parse_ghcnh_file`. The TS port consumes the PSV body in-memory (a
// string returned by `downloadGhcnh`); the Python version walks a file
// handle but the semantics are identical.
//
// GHCNh ships pre-QC'd data with per-variable `*_Quality_Code` columns.
// We keep raw observations only (`{0, 1, 4, 5, ""}`) and drop QC-flagged
// variables (`{2, 3, 6, 7, I, P, R, U}`). The empty-string acceptance is
// load-bearing — many GHCNh rows omit Quality_Code entirely and would
// otherwise drop silently (parity case 5).
//
// Unit conversions: m/s → kt, km → mi, m → ft, mm → in, cm → in.
// Sky-cover layers 1-4 + per-layer baseht; present-weather codes from
// pres_wx_AW{1..3}; raw_metar extracted from REM column.
//
// CSV implementation: hand-rolled pipe-split + header-map. NO `csv` dep —
// the parser preserves bundle-size discipline (TS Architect rubric §2).

import {
  MAX_RAW_METAR_LEN,
  MAX_VISIBILITY_MILES,
  MAX_WX_CODES_LEN,
  MAX_YEAR,
  MIN_YEAR,
  SKY_BASE_MAX_FT,
  SLP_MAX_MB,
  SLP_MIN_MB,
  TEMP_MAX_C,
  TEMP_MIN_C,
  boundedFloat,
  boundedFloatMin,
  boundedInt,
} from "@mostlyright/core/internal/bounds";
import { celsiusToFahrenheit, hpaToInhg } from "@mostlyright/core/internal/convert";

import { extractStationCode } from "./_station_translator.js";
import { type Observation, mapCloudCover } from "./awc.js";

export {
  SSID_COLUMNS,
  extractStationCode,
  ghcnhStationToCode,
} from "./_station_translator.js";

// ---------------------------------------------------------------------------
// Constants (byte-faithful with Python `_ghcnh.py`)
// ---------------------------------------------------------------------------

const MS_TO_KT = 1 / 0.514444;
const KM_TO_MI = 1 / 1.60934;
const M_TO_FT = 3.28084;
const MM_TO_IN = 1 / 25.4;
const CM_TO_IN = 1 / 2.54;

/** ISO 8601 form GHCNh uses in its DATE column. Optional trailing `Z`. */
const DATE_RE = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z?$/;

/** Quality_Code values that pass the raw-only filter. Empty string also accepts. */
const ALLOWED_QC: ReadonlySet<string> = new Set(["0", "1", "4", "5"]);

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function safeFloat(val: string): number | null {
  if (!val || val === "NA") return null;
  const f = Number(val);
  return Number.isFinite(f) ? f : null;
}

function safeInt(val: string): number | null {
  const f = safeFloat(val);
  return f === null ? null : Math.round(f);
}

/**
 * Quality_Code acceptance gate. Accepts {0, 1, 4, 5} and empty string.
 * Rejects {2, 3, 6, 7} and letter flags {I, P, R, U}. Empty-string
 * acceptance is critical — without it, ungraded rows drop silently
 * (parity case 5 KMSY Hurricane Francine).
 */
function isQcAccepted(qc: string): boolean {
  const stripped = qc.trim();
  if (!stripped) return true;
  return ALLOWED_QC.has(stripped);
}

/** `"SCT:04;"` → `"SCT"` via {@link mapCloudCover}. */
function parseSkyCover(val: string): string | null {
  if (!val) return null;
  let code: string;
  if (val.includes(":")) {
    const colonIdx = val.indexOf(":");
    code = val.slice(0, colonIdx);
  } else {
    code = val.endsWith(";") ? val.slice(0, -1) : val;
  }
  return mapCloudCover(code);
}

/** sky_cover_summation_baseht_N (meters) → integer feet (rounded, bounded). */
function parseSkyBaseht(val: string): number | null {
  const meters = safeFloat(val);
  if (meters === null || meters < 0) return null;
  const feet = Math.round(meters * M_TO_FT);
  return feet <= SKY_BASE_MAX_FT ? feet : null;
}

/**
 * Parse `pres_wx_AW{1..3}` columns. GHCNh format is `"TS:90"` / `"+RA:02"`
 * (METAR text + WMO AW code) — extract the leading METAR token, filter
 * bare-numeric WMO codes, honor per-column Quality_Code (`{3, P}` reject).
 */
function parseWeatherCodes(row: Record<string, string>): string | null {
  const codes: string[] = [];
  for (let i = 1; i <= 3; i++) {
    const val = row[`pres_wx_AW${i}`] ?? "";
    if (!val) continue;
    const qc = (row[`pres_wx_AW${i}_Quality_Code`] ?? "").trim();
    if (qc === "3" || qc === "P") continue;
    const code = val.includes(":") ? val.slice(0, val.indexOf(":")) : val;
    if (!code) continue;
    // Skip bare-numeric WMO codes (`"02"`, `"+90"`, `"-10"`).
    const numericProbe = code.replace(/^[+-]/, "");
    if (numericProbe.length > 0 && /^\d+$/.test(numericProbe)) continue;
    codes.push(code);
  }
  if (codes.length === 0) return null;
  const result = codes.join(" ");
  return result.length > MAX_WX_CODES_LEN ? result.slice(0, MAX_WX_CODES_LEN) : result;
}

/**
 * Calendar-validity round-trip for `YYYY-MM-DDTHH:MM:SS[Z]`. Returns true if
 * the parts round-trip exactly through `Date.UTC` — rejects `2025-02-30`,
 * `2025-13-01`, etc. Mirrors Python's `datetime.fromisoformat` exception path.
 */
function isValidCalendarDate(iso: string): boolean {
  const stripped = iso.endsWith("Z") ? iso.slice(0, -1) : iso;
  // Format-guard already applied by DATE_RE — substring math is safe.
  const year = Number.parseInt(stripped.slice(0, 4), 10);
  const month = Number.parseInt(stripped.slice(5, 7), 10);
  const day = Number.parseInt(stripped.slice(8, 10), 10);
  const hour = Number.parseInt(stripped.slice(11, 13), 10);
  const minute = Number.parseInt(stripped.slice(14, 16), 10);
  const second = Number.parseInt(stripped.slice(17, 19), 10);
  if (month < 1 || month > 12) return false;
  if (day < 1 || day > 31) return false;
  if (hour > 23 || minute > 59 || second > 59) return false;
  const millis = Date.UTC(year, month - 1, day, hour, minute, second, 0);
  if (!Number.isFinite(millis)) return false;
  const d = new Date(millis);
  return (
    d.getUTCFullYear() === year &&
    d.getUTCMonth() === month - 1 &&
    d.getUTCDate() === day &&
    d.getUTCHours() === hour &&
    d.getUTCMinutes() === minute &&
    d.getUTCSeconds() === second
  );
}

// ---------------------------------------------------------------------------
// Row parser
// ---------------------------------------------------------------------------

/**
 * Parse one GHCNh PSV row (header→cell dict) into the canonical Observation
 * row. Returns `null` if the row should be skipped:
 *  - Station code unresolvable from any `Source_Station_ID` column
 *  - DATE missing / malformed / calendar-invalid / out-of-year-range
 *  - ALL four key vars (temperature, dew_point_temperature, wind_speed,
 *    sea_level_pressure) fail Quality_Code
 *
 * Output dict-key order is preserved verbatim to keep downstream
 * `JSON.stringify` byte-stable across SDKs.
 */
export function parseGhcnhRow(row: Readonly<Record<string, string>>): Observation | null {
  const stationCode = extractStationCode(row);
  if (stationCode === null) return null;

  const dateStr = row.DATE ?? "";
  if (!dateStr || !DATE_RE.test(dateStr)) return null;
  if (!isValidCalendarDate(dateStr)) return null;

  const year = Number.parseInt(dateStr.slice(0, 4), 10);
  if (year < MIN_YEAR || year > MAX_YEAR) return null;

  const observedAt = dateStr.endsWith("Z") ? dateStr : `${dateStr}Z`;

  const reportType = row.temperature_Report_Type ?? "";
  const observationType: "METAR" | "SPECI" = reportType === "FM16" ? "SPECI" : "METAR";

  // Per-variable Quality_Code gates.
  const tempOk = isQcAccepted(row.temperature_Quality_Code ?? "");
  const dewpOk = isQcAccepted(row.dew_point_temperature_Quality_Code ?? "");
  const wspdOk = isQcAccepted(row.wind_speed_Quality_Code ?? "");
  const wdirOk = isQcAccepted(row.wind_direction_Quality_Code ?? "");
  const wgustOk = isQcAccepted(row.wind_gust_Quality_Code ?? "");
  const slpOk = isQcAccepted(row.sea_level_pressure_Quality_Code ?? "");
  const altimOk = isQcAccepted(row.altimeter_Quality_Code ?? "");
  const visOk = isQcAccepted(row.visibility_Quality_Code ?? "");
  const precipOk = isQcAccepted(row.precipitation_Quality_Code ?? "");
  const snowOk = isQcAccepted(row.snow_depth_Quality_Code ?? "");

  // Skip-row gate (Python L200-201).
  if (!(tempOk || dewpOk || wspdOk || slpOk)) return null;

  // Temperature (no rounding, bounded; °C native).
  const tempC = tempOk
    ? boundedFloat(safeFloat(row.temperature ?? ""), TEMP_MIN_C, TEMP_MAX_C, { field: "temp_c" })
    : null;
  const dewpC = dewpOk
    ? boundedFloat(safeFloat(row.dew_point_temperature ?? ""), TEMP_MIN_C, TEMP_MAX_C, {
        field: "dewpoint_c",
      })
    : null;
  const tempF = celsiusToFahrenheit(tempC);
  const dewpF = celsiusToFahrenheit(dewpC);

  // Wind direction (degrees, bounded 0..360).
  const windDir = wdirOk ? boundedInt(safeInt(row.wind_direction ?? ""), 0, 360) : null;

  // Wind speed/gust (m/s → kt, rounded, bounded).
  const windSpeedMs = wspdOk ? safeFloat(row.wind_speed ?? "") : null;
  const windGustMs = wgustOk ? safeFloat(row.wind_gust ?? "") : null;
  const windSpeedKt = boundedInt(
    windSpeedMs !== null ? Math.round(windSpeedMs * MS_TO_KT) : null,
    0,
    200,
  );
  const windGustKt = boundedInt(
    windGustMs !== null ? Math.round(windGustMs * MS_TO_KT) : null,
    0,
    250,
  );

  // Pressure.
  let slp = slpOk ? safeFloat(row.sea_level_pressure ?? "") : null;
  if (slp !== null && (slp < SLP_MIN_MB || slp > SLP_MAX_MB)) {
    slp = null;
  }
  const altimHpa = altimOk ? safeFloat(row.altimeter ?? "") : null;
  const altimInhg = hpaToInhg(altimHpa);

  // Visibility (km → mi, non-negative, clamped at MAX_VISIBILITY_MILES).
  const visKm = visOk ? safeFloat(row.visibility ?? "") : null;
  let visMiles: number | null = null;
  if (visKm !== null && visKm >= 0) {
    visMiles = Math.min(visKm * KM_TO_MI, MAX_VISIBILITY_MILES);
  }

  // Precipitation (mm → in, non-negative).
  const precipMm = precipOk ? safeFloat(row.precipitation ?? "") : null;
  const precipInches = precipMm !== null ? boundedFloatMin(precipMm * MM_TO_IN, 0.0) : null;

  // Snow depth (cm → in, non-negative).
  const snowCm = snowOk ? safeFloat(row.snow_depth ?? "") : null;
  const snowInches = snowCm !== null ? boundedFloatMin(snowCm * CM_TO_IN, 0.0) : null;

  // Sky cover layers 1-4 with per-layer QC.
  const skyCovers: Array<string | null> = [];
  const skyBases: Array<number | null> = [];
  for (let i = 1; i <= 4; i++) {
    const covQc = isQcAccepted(row[`sky_cover_summation_${i}_Quality_Code`] ?? "");
    const baseQc = isQcAccepted(row[`sky_cover_summation_baseht_${i}_Quality_Code`] ?? "");
    skyCovers.push(covQc ? parseSkyCover(row[`sky_cover_summation_${i}`] ?? "") : null);
    skyBases.push(baseQc ? parseSkyBaseht(row[`sky_cover_summation_baseht_${i}`] ?? "") : null);
  }

  // Weather codes.
  const weatherCodes = parseWeatherCodes(row as Record<string, string>);

  // Raw METAR from REM column. GHCNh wraps the METAR/SPECI in a prefix
  // like "MET2025-09-10 14:51:00 METAR KMSY 101451Z ..." — slice from the
  // leading METAR/SPECI marker so raw_metar starts with the canonical form.
  const rem = row.REM ?? "";
  let rawMetar: string | null = null;
  if (rem) {
    const idxMetar = rem.indexOf("METAR ");
    const idxSpeci = rem.indexOf("SPECI ");
    let cleaned: string;
    if (idxMetar >= 0 && (idxSpeci < 0 || idxMetar < idxSpeci)) {
      cleaned = rem.slice(idxMetar);
    } else if (idxSpeci >= 0) {
      cleaned = rem.slice(idxSpeci);
    } else {
      cleaned = rem;
    }
    rawMetar = cleaned.length > MAX_RAW_METAR_LEN ? cleaned.slice(0, MAX_RAW_METAR_LEN) : cleaned;
  }

  return {
    station_code: stationCode,
    observed_at: observedAt,
    observation_type: observationType,
    source: "ghcnh",
    temp_c: tempC,
    dewpoint_c: dewpC,
    temp_f: tempF,
    dewpoint_f: dewpF,
    wind_dir_degrees: windDir,
    wind_speed_kt: windSpeedKt,
    wind_gust_kt: windGustKt,
    altimeter_inhg: altimInhg,
    sea_level_pressure_mb: slp,
    sky_cover_1: skyCovers[0] ?? null,
    sky_base_1_ft: skyBases[0] ?? null,
    sky_cover_2: skyCovers[1] ?? null,
    sky_base_2_ft: skyBases[1] ?? null,
    sky_cover_3: skyCovers[2] ?? null,
    sky_base_3_ft: skyBases[2] ?? null,
    sky_cover_4: skyCovers[3] ?? null,
    sky_base_4_ft: skyBases[3] ?? null,
    visibility_miles: visMiles,
    weather_codes: weatherCodes,
    precip_1hr_inches: precipInches,
    peak_wind_gust_kt: null,
    peak_wind_dir: null,
    peak_wind_time: null,
    snow_depth_inches: snowInches,
    qc_field: null,
    raw_metar: rawMetar,
  };
}

/**
 * Parse a GHCNh PSV body string into Observation rows.
 *
 * Hand-rolled pipe-split — no `csv` dep. Empty body / header-only → `[]`.
 * Rows that {@link parseGhcnhRow} skips are omitted (no null entries).
 */
export function parseGhcnhPsv(psvBody: string): ReadonlyArray<Observation> {
  if (!psvBody) return [];
  // Normalize CRLF → LF, then split. Skip blank lines.
  const lines = psvBody.replace(/\r/g, "").split("\n");
  let headerIdx = -1;
  for (let i = 0; i < lines.length; i++) {
    if ((lines[i] as string).length > 0) {
      headerIdx = i;
      break;
    }
  }
  if (headerIdx < 0) return [];
  const header = (lines[headerIdx] as string).split("|");

  const out: Observation[] = [];
  for (let i = headerIdx + 1; i < lines.length; i++) {
    const line = lines[i] as string;
    if (line.length === 0) continue;
    const cells = line.split("|");
    const row: Record<string, string> = {};
    for (let c = 0; c < header.length; c++) {
      const key = header[c] as string;
      row[key] = c < cells.length ? (cells[c] as string) : "";
    }
    const obs = parseGhcnhRow(row);
    if (obs !== null) out.push(obs);
  }
  return out;
}

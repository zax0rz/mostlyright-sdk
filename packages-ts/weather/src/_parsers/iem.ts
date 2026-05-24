// IEM METAR CSV parser — string-body in, Observation rows out.
//
// Byte-faithful TS port of Python
// `packages/weather/src/tradewinds/weather/_iem.py::iem_to_observation`
// + `parse_iem_file`. The TS port consumes the CSV body in-memory (a
// string returned by `downloadIemAsos`); the Python version walks a file
// handle but the semantics are identical.
//
// IEM provides pre-parsed METAR fields in US/METAR-native units (°F, kt,
// mi, inHg). We emit Observation dicts matching the canonical
// `schema.observation.v1` shape (30 fields, source="iem").
//
// Key port details:
//  - Comment lines starting with `#` are stripped BEFORE the CSV header
//    is consumed (mirrors Python's `filtered = (line for line in f if
//    not line.startswith("#"))`).
//  - `M` and empty string both parse as `null` for numeric fields.
//  - `T` (trace) parses as `0.0` for `p01i` only; on other numeric
//    fields, T is non-numeric and yields `null`.
//  - Out-of-bounds Celsius consistency rule: when derived `temp_c` is
//    nulled by bounds, the raw `temp_f` is ALSO nulled (Python L170-171).
//  - All 4 key vars (raw `tmpf`, raw `dwpf`, `wind_speed`, `slp`) missing
//    → row skipped (returns `null` from `iemToObservation`).
//  - Output dict-key order matches Python verbatim so `JSON.stringify`
//    produces byte-stable output across SDKs (downstream diff tooling).
//
// CSV implementation: hand-rolled split-on-comma. IEM's `format=comma`
// endpoint does NOT quote fields with embedded commas (the Python parser
// confirms this empirically — it uses csv.DictReader with default
// dialect and works). A hand-rolled split keeps the bundle-size gate
// happy (no papaparse dep) and matches the TS Architect rubric §2
// (bundle size) + the plan's "DO NOT add deps" note.

import {
  MAX_RAW_METAR_LEN,
  MAX_VISIBILITY_MILES,
  MAX_WX_CODES_LEN,
  MAX_YEAR,
  MIN_YEAR,
  SKY_BASE_MAX_FT,
  SLP_MAX_MB,
  SLP_MIN_MB,
  STATION_CODE_RE,
  TEMP_MAX_C,
  TEMP_MIN_C,
  WIND_DIR_BOUNDS,
  WIND_GUST_MAX,
  WIND_SPEED_MAX,
  boundedFloat,
  boundedFloatMin,
  boundedInt,
} from "@tradewinds/core/internal/bounds";
import { fahrenheitToCelsius } from "@tradewinds/core/internal/convert";

import { type Observation, icaoToStationCode, mapCloudCover } from "./awc.js";

const [WIND_DIR_LO, WIND_DIR_HI] = WIND_DIR_BOUNDS;

// Match Python `_TS_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2}) (\d{2}):(\d{2})$")`.
const TS_RE = /^(\d{4})-(\d{2})-(\d{2}) (\d{2}):(\d{2})$/;

const VALID_OBS_TYPES = new Set<string>(["METAR", "SPECI"]);

export type IemObservationTypeOverride = "METAR" | "SPECI";

export interface IemToObservationOptions {
  /**
   * Force `observation_type` to this value regardless of metar text.
   * Used by callers that issue separate report_type=3/4 fetches and
   * therefore know the type per-batch without inspecting the raw text.
   */
  observationTypeOverride?: IemObservationTypeOverride;
}

/** Raw IEM CSV row (header → cell value), all strings before parsing. */
export type IemCsvRow = Record<string, string>;

/**
 * Parse an IEM numeric cell into a finite float. `"M"` (IEM's missing
 * sentinel) and empty strings yield `null`; non-finite values yield `null`.
 *
 * Mirrors Python `_safe_float`.
 */
function safeFloat(val: string): number | null {
  if (val === "" || val === "M") return null;
  const f = Number(val);
  return Number.isFinite(f) ? f : null;
}

/**
 * Parse an IEM numeric cell into a rounded integer via `safeFloat`.
 * `null` propagates. Mirrors Python `_safe_int` (round → int).
 */
function safeInt(val: string): number | null {
  const f = safeFloat(val);
  return f === null ? null : Math.round(f);
}

/**
 * Parse the IEM precipitation cell. `M` / empty → `null`; `T` (trace) → `0.0`;
 * numeric values pass through `safeFloat`. Mirrors Python `_parse_precip`.
 */
function parsePrecip(val: string): number | null {
  if (val === "" || val === "M") return null;
  if (val.trim().toUpperCase() === "T") return 0.0;
  return safeFloat(val);
}

/**
 * Parse IEM timestamp (`YYYY-MM-DD HH:MM`) into RFC3339 / ISO 8601 UTC.
 * Returns `null` for missing (`""`/`M`), malformed, calendar-invalid, or
 * out-of-year-range inputs. Mirrors Python `_parse_timestamp`.
 */
function parseTimestamp(val: string): string | null {
  if (val === "" || val === "M") return null;
  const trimmed = val.trim();
  const m = TS_RE.exec(trimmed);
  if (m === null) return null;
  // RegExp matched — groups 1..5 are guaranteed defined.
  const year = Number.parseInt(m[1] as string, 10);
  const month = Number.parseInt(m[2] as string, 10);
  const day = Number.parseInt(m[3] as string, 10);
  const hour = Number.parseInt(m[4] as string, 10);
  const minute = Number.parseInt(m[5] as string, 10);
  // Range checks BEFORE Date.UTC round-trip (rejects Feb-30 / hour-25 inputs
  // that Date.UTC would otherwise silently roll forward).
  if (year < MIN_YEAR || year > MAX_YEAR) return null;
  if (month < 1 || month > 12) return null;
  if (day < 1 || day > 31) return null;
  if (hour > 23 || minute > 59) return null;
  // Calendar validity via UTC round-trip — rejects "2025-02-30 12:00" etc.
  const millis = Date.UTC(year, month - 1, day, hour, minute, 0, 0);
  if (!Number.isFinite(millis)) return null;
  const d = new Date(millis);
  if (
    d.getUTCFullYear() !== year ||
    d.getUTCMonth() !== month - 1 ||
    d.getUTCDate() !== day ||
    d.getUTCHours() !== hour ||
    d.getUTCMinutes() !== minute
  ) {
    return null;
  }
  // Format as `YYYY-MM-DDTHH:MM:00Z` byte-faithful with Python's f-string.
  return `${m[1]}-${m[2]}-${m[3]}T${m[4]}:${m[5]}:00Z`;
}

/**
 * Parse `YYYY-MM-DD HH:MM` peak-wind-time into the bare `HHMM` form Python
 * emits. Returns `null` on `""`/`M`/malformed. Mirrors Python
 * `_parse_peak_wind_time`.
 */
function parsePeakWindTime(val: string): string | null {
  if (val === "" || val === "M") return null;
  const trimmed = val.trim();
  const parts = trimmed.split(" ");
  if (parts.length !== 2) return null;
  const timeParts = (parts[1] as string).split(":");
  if (timeParts.length !== 2) return null;
  const h = Number.parseInt(timeParts[0] as string, 10);
  const min = Number.parseInt(timeParts[1] as string, 10);
  if (!Number.isFinite(h) || !Number.isFinite(min)) return null;
  if (h < 0 || h > 23 || min < 0 || min > 59) return null;
  const hh = h < 10 ? `0${h}` : String(h);
  const mm = min < 10 ? `0${min}` : String(min);
  return `${hh}${mm}`;
}

/**
 * Detect METAR vs SPECI from the raw METAR text first word. Empty / `M` →
 * `"METAR"` (safe default). Mirrors Python `_detect_obs_type`.
 */
function detectObsType(metar: string): "METAR" | "SPECI" {
  if (metar === "" || metar === "M") return "METAR";
  const words = metar.trim().split(/\s+/, 1);
  if (words.length > 0 && words[0] === "SPECI") return "SPECI";
  return "METAR";
}

/**
 * Convert one IEM CSV row (header→cell dict) into the canonical
 * Observation row. Returns `null` if the row should be skipped:
 *  - station missing/M, or doesn't match STATION_CODE_RE after K-strip
 *  - timestamp unparseable / out-of-range
 *  - ALL 4 key vars (raw tmpf, raw dwpf, wind_speed, slp) missing
 *
 * Throws on bad `observationTypeOverride` (Python L152-156 parity).
 *
 * Output dict-key order is preserved verbatim — matters for downstream
 * byte-stable JSON snapshot diffs.
 */
export function iemToObservation(
  row: IemCsvRow,
  opts: IemToObservationOptions = {},
): Observation | null {
  // --- Station code ------------------------------------------------------
  const stationRaw = row.station ?? "";
  if (stationRaw === "" || stationRaw === "M") return null;
  const stationCode = icaoToStationCode(stationRaw);
  if (!STATION_CODE_RE.test(stationCode)) return null;

  // --- Timestamp ---------------------------------------------------------
  const observedAt = parseTimestamp(row.valid ?? "");
  if (observedAt === null) return null;

  // --- Observation type (caller override or auto-detect) ----------------
  const override = opts.observationTypeOverride;
  if (override !== undefined && !VALID_OBS_TYPES.has(override)) {
    throw new Error(
      `Invalid observation_type_override: ${JSON.stringify(
        override,
      )}. Must be one of ${[...VALID_OBS_TYPES].join(", ")}`,
    );
  }
  const metarText = row.metar ?? "";
  const observationType: "METAR" | "SPECI" =
    override !== undefined ? override : detectObsType(metarText);

  // --- Temperature (IEM gives °F; derive °C; bounds-check on °C) ---------
  const rawTempF = safeFloat(row.tmpf ?? "");
  const rawDewpF = safeFloat(row.dwpf ?? "");
  const tempC = boundedFloat(fahrenheitToCelsius(rawTempF), TEMP_MIN_C, TEMP_MAX_C, {
    field: "temp_c",
  });
  const dewpC = boundedFloat(fahrenheitToCelsius(rawDewpF), TEMP_MIN_C, TEMP_MAX_C, {
    field: "dewpoint_c",
  });
  // Consistency rule (Python L170-171): if derived °C is out of bounds,
  // the raw °F is also bogus — null both sides.
  const tempF: number | null = tempC !== null ? rawTempF : null;
  const dewpF: number | null = dewpC !== null ? rawDewpF : null;

  // --- Wind (already in knots) ------------------------------------------
  const windDir = boundedInt(safeInt(row.drct ?? ""), WIND_DIR_LO, WIND_DIR_HI);
  const windSpeed = boundedInt(safeInt(row.sknt ?? ""), 0, WIND_SPEED_MAX);
  const windGust = boundedInt(safeInt(row.gust ?? ""), 0, WIND_GUST_MAX);

  // --- Pressure ----------------------------------------------------------
  const altim = safeFloat(row.alti ?? ""); // inHg (passthrough)
  let slp = safeFloat(row.mslp ?? ""); // mb / hPa
  if (slp !== null && !(slp >= SLP_MIN_MB && slp <= SLP_MAX_MB)) {
    slp = null;
  }

  // --- Visibility (statute miles; clamp at MAX_VISIBILITY_MILES) --------
  let vis = safeFloat(row.vsby ?? "");
  if (vis !== null) {
    if (vis < 0) vis = null;
    else if (vis > MAX_VISIBILITY_MILES) vis = MAX_VISIBILITY_MILES;
  }

  // --- Sky covers + base heights (4 columns; IEM gives feet) ------------
  const skyCovers: Array<string | null> = [];
  const skyBases: Array<number | null> = [];
  for (let i = 1; i <= 4; i += 1) {
    const coverRaw = row[`skyc${i}`] ?? "";
    const baseRaw = row[`skyl${i}`] ?? "";
    const cover = coverRaw !== "" && coverRaw !== "M" ? mapCloudCover(coverRaw) : null;
    const base = boundedInt(safeInt(baseRaw), 0, SKY_BASE_MAX_FT);
    skyCovers.push(cover);
    skyBases.push(base);
  }

  // --- Weather codes (truncate to MAX_WX_CODES_LEN) ---------------------
  const wxRaw = row.wxcodes ?? "";
  const weatherCodes: string | null =
    wxRaw !== "" && wxRaw !== "M" ? wxRaw.slice(0, MAX_WX_CODES_LEN) : null;

  // --- Precipitation ('T' = trace → 0.0; clamp at 0.0) ------------------
  const precip = boundedFloatMin(parsePrecip(row.p01i ?? ""), 0.0);

  // --- Snow depth (clamp at 0.0) ----------------------------------------
  const snow = boundedFloatMin(safeFloat(row.snowdepth ?? ""), 0.0);

  // --- Peak wind ---------------------------------------------------------
  const pkGust = boundedInt(safeInt(row.peak_wind_gust ?? ""), 0, WIND_GUST_MAX);
  const pkDir = boundedInt(safeInt(row.peak_wind_drct ?? ""), WIND_DIR_LO, WIND_DIR_HI);
  const pkTime = parsePeakWindTime(row.peak_wind_time ?? "");

  // --- Raw METAR (truncate) ---------------------------------------------
  const rawMetar: string | null =
    metarText !== "" && metarText !== "M" ? metarText.slice(0, MAX_RAW_METAR_LEN) : null;

  // --- Skip-row gate: ALL 4 key vars missing → drop the row -------------
  // Mirror Python L222-224: uses the RAW values (raw_temp_f, raw_dewp_f,
  // wind_speed bounded, slp bounded). Note slp uses post-bounds null so a
  // pressure outside [870, 1084] also counts as missing for skip purposes.
  if (rawTempF === null && rawDewpF === null && windSpeed === null && slp === null) {
    return null;
  }

  // Return literal preserves Python's iem_to_observation key order
  // exactly — 30 fields. JSON.stringify ordering matters for downstream
  // byte-stable diff tooling.
  return {
    station_code: stationCode,
    observed_at: observedAt,
    observation_type: observationType,
    source: "iem",
    temp_c: tempC,
    dewpoint_c: dewpC,
    temp_f: tempF,
    dewpoint_f: dewpF,
    wind_dir_degrees: windDir,
    wind_speed_kt: windSpeed,
    wind_gust_kt: windGust,
    altimeter_inhg: altim,
    sea_level_pressure_mb: slp,
    sky_cover_1: skyCovers[0] as string | null,
    sky_base_1_ft: skyBases[0] as number | null,
    sky_cover_2: skyCovers[1] as string | null,
    sky_base_2_ft: skyBases[1] as number | null,
    sky_cover_3: skyCovers[2] as string | null,
    sky_base_3_ft: skyBases[2] as number | null,
    sky_cover_4: skyCovers[3] as string | null,
    sky_base_4_ft: skyBases[3] as number | null,
    visibility_miles: vis,
    weather_codes: weatherCodes,
    precip_1hr_inches: precip,
    peak_wind_gust_kt: pkGust,
    peak_wind_dir: pkDir,
    peak_wind_time: pkTime,
    snow_depth_inches: snow,
    qc_field: null, // IEM CSV doesn't carry a QC field — schema-stable null
    raw_metar: rawMetar,
  };
}

/**
 * Parse a full IEM CSV body into Observation rows.
 *
 * - Lines beginning with `#` are dropped before the header is consumed
 *   (mirror Python `filtered = (line for line in f if not line.startswith("#"))`).
 * - The first non-comment line is the header; subsequent lines are data.
 * - Rows that `iemToObservation` rejects are silently dropped (parser
 *   never throws on bad data; only `observationTypeOverride` validation
 *   throws — that's a programmer-error path).
 *
 * Returns an empty array for empty / header-only / all-comments input.
 */
export function parseIemCsv(
  csvBody: string,
  opts: IemToObservationOptions = {},
): ReadonlyArray<Observation> {
  if (csvBody === "") return [];
  // Normalize line endings + split. Drop empty trailing lines so trailing
  // newlines don't yield phantom rows.
  const lines = csvBody.split(/\r?\n/).filter((line) => !line.startsWith("#"));
  // Skip empty lines (incl. the final newline tail).
  const nonEmpty = lines.filter((line) => line.length > 0);
  if (nonEmpty.length === 0) return [];
  const headerLine = nonEmpty[0] as string;
  const header = headerLine.split(",");
  const out: Observation[] = [];
  for (let i = 1; i < nonEmpty.length; i += 1) {
    const line = nonEmpty[i] as string;
    const cells = line.split(",");
    const row: IemCsvRow = {};
    for (let c = 0; c < header.length; c += 1) {
      const key = header[c] as string;
      row[key] = (cells[c] ?? "").trim();
    }
    const obs = iemToObservation(row, opts);
    if (obs !== null) out.push(obs);
  }
  return out;
}

// GHCNh Source_Station_ID → station_code translator.
//
// Byte-faithful TS port of Python
// `packages/weather/src/mostlyright/weather/_ghcnh.py::ghcnh_station_to_code`
// (L133-145) and `_extract_station_code` (L148-155) + the `_SSID_COLUMNS`
// tuple verbatim.
//
// GHCNh PSV rows carry up to 11 Source_Station_ID columns (per variable);
// we walk them in priority order and return the first ICAO-prefixed value
// that resolves to a valid station code.

import { STATION_CODE_RE } from "@mostlyrightmd/core/internal/bounds";

import { icaoToStationCode } from "./awc.js";

/**
 * Source_Station_ID column priority. Order matches Python `_SSID_COLUMNS`
 * tuple at `_ghcnh.py:45-57` EXACTLY (temperature first, then dew_point,
 * wind_speed, wind_direction, sea_level_pressure, altimeter, visibility,
 * then four sky_cover_summation layers).
 */
export const SSID_COLUMNS = [
  "temperature_Source_Station_ID",
  "dew_point_temperature_Source_Station_ID",
  "wind_speed_Source_Station_ID",
  "wind_direction_Source_Station_ID",
  "sea_level_pressure_Source_Station_ID",
  "altimeter_Source_Station_ID",
  "visibility_Source_Station_ID",
  "sky_cover_summation_1_Source_Station_ID",
  "sky_cover_summation_2_Source_Station_ID",
  "sky_cover_summation_3_Source_Station_ID",
  "sky_cover_summation_4_Source_Station_ID",
] as const;

/**
 * Extract the 3-letter station code from a GHCNh Source_Station_ID value.
 *
 *   `"ICAO-KJFK"`     → `"JFK"`  (strip prefix, apply ICAO→code conversion)
 *   `"744860-94789"`  → `null`   (WMO USAF-WBAN format, no ICAO prefix)
 *   `""` / `"ICAO-"`  → `null`
 *
 * Returns `null` for any input that does not resolve to a value matching
 * `STATION_CODE_RE` (3-4 uppercase letters).
 */
export function ghcnhStationToCode(sourceStationId: string): string | null {
  if (!sourceStationId || !sourceStationId.startsWith("ICAO-")) {
    return null;
  }
  const icao = sourceStationId.slice(5);
  if (!icao) {
    return null;
  }
  const code = icaoToStationCode(icao);
  if (STATION_CODE_RE.test(code)) {
    return code;
  }
  return null;
}

/**
 * Walk `SSID_COLUMNS` in priority order and return the first non-null
 * result from `ghcnhStationToCode`. Returns `null` if every column misses.
 */
export function extractStationCode(row: Readonly<Record<string, string>>): string | null {
  for (const col of SSID_COLUMNS) {
    const ssid = row[col] ?? "";
    const code = ghcnhStationToCode(ssid);
    if (code !== null) {
      return code;
    }
  }
  return null;
}

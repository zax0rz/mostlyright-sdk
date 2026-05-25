// TS-W4 Plan 04 Task 1 — NWS weather cross-features (wind chill + heat index).
//
// Pure scalar ports of Python `mostlyright.transforms.wind_chill` and
// `heat_index` at packages/core/src/mostlyright/transforms.py:108-147.
//
// **PARITY-NOTE (out-of-domain return value):**
// Python returns `temp_f` UNCHANGED when outside the valid domain
// (transforms.py:114 for wind_chill, transforms.py:126 for heat_index).
// The REQUIREMENTS.md text says "out-of-domain → null" but that is incorrect
// vs the canonical Python source. We honor Python source and return tempF
// unchanged in those branches. `null` is reserved for null / undefined /
// non-finite inputs only.

/**
 * NWS wind-chill formula (°F). Domain: `tempF ≤ 50 AND windMph > 3`.
 *
 * Mirrors Python `transforms.wind_chill` at transforms.py:108-116. The
 * formula is the 2001 NWS standard:
 *
 *   wc = 35.74 + 0.6215 * T - 35.75 * V^0.16 + 0.4275 * T * V^0.16
 *
 * where T is air temperature in °F and V is wind speed in mph.
 *
 * **Out-of-domain (NOT null — Python parity):** when the domain bounds are
 * not satisfied, returns `tempF` unchanged — physically "wind chill equals
 * air temperature when wind is calm or air is warm". Null is reserved for
 * null / undefined / non-finite inputs.
 *
 * Reference: https://www.weather.gov/safety/cold-wind-chill-chart
 * Sanity: `windChill(20, 15) ≈ 6 °F` matches the NWS chart.
 */
export function windChill(
  tempF: number | null | undefined,
  windMph: number | null | undefined,
): number | null {
  if (tempF === null || tempF === undefined || windMph === null || windMph === undefined) {
    return null;
  }
  if (typeof tempF !== "number" || !Number.isFinite(tempF)) return null;
  if (typeof windMph !== "number" || !Number.isFinite(windMph)) return null;
  if (tempF > 50.0 || windMph <= 3.0) return tempF; // out-of-domain → tempF (Python parity)
  const v016 = windMph ** 0.16;
  return 35.74 + 0.6215 * tempF - 35.75 * v016 + 0.4275 * tempF * v016;
}

/**
 * NWS heat index (°F) using the Rothfusz regression. Domain: `tempF ≥ 80`.
 *
 * Mirrors Python `transforms.heat_index` at transforms.py:119-147. Includes:
 *
 *  1. A simple approximation `simple = 0.5*(T + 61 + (T-68)*1.2 + RH*0.094)`
 *     used when `(simple + T)/2 < 80` (low-effective-temperature fast path).
 *  2. The Rothfusz 9-term polynomial:
 *     hi = -42.379 + 2.04901523*T + 10.14333127*RH - 0.22475541*T*RH
 *          - 0.00683783*T² - 0.05481717*RH² + 0.00122874*T²*RH
 *          + 0.00085282*T*RH² - 0.00000199*T²*RH²
 *  3. A dry-air adjustment when `RH < 13 && 80 ≤ T ≤ 112`:
 *     hi -= ((13 - RH) / 4) * sqrt((17 - |T - 95|) / 17)
 *  4. A humid-air adjustment when `RH > 85 && 80 ≤ T ≤ 87`:
 *     hi += ((RH - 85) / 10) * ((87 - T) / 5)
 *
 * **Out-of-domain (NOT null — Python parity):** when `tempF < 80`, returns
 * `tempF` unchanged. Null is reserved for null / undefined / non-finite
 * inputs.
 *
 * Reference: https://www.wpc.ncep.noaa.gov/html/heatindex.shtml
 * Sanity: `heatIndex(90, 70) ≈ 106 °F` matches the NWS Rothfusz table.
 */
export function heatIndex(
  tempF: number | null | undefined,
  rhPct: number | null | undefined,
): number | null {
  if (tempF === null || tempF === undefined || rhPct === null || rhPct === undefined) {
    return null;
  }
  if (typeof tempF !== "number" || !Number.isFinite(tempF)) return null;
  if (typeof rhPct !== "number" || !Number.isFinite(rhPct)) return null;
  if (tempF < 80.0) return tempF; // out-of-domain → tempF (Python parity)

  const t = tempF;
  const h = rhPct;
  const simple = 0.5 * (t + 61.0 + (t - 68.0) * 1.2 + h * 0.094);
  if ((simple + t) / 2.0 < 80.0) return simple;

  let hi =
    -42.379 +
    2.04901523 * t +
    10.14333127 * h -
    0.22475541 * t * h -
    0.00683783 * t * t -
    0.05481717 * h * h +
    0.00122874 * t * t * h +
    0.00085282 * t * h * h -
    0.00000199 * t * t * h * h;

  if (h < 13.0 && t >= 80.0 && t <= 112.0) {
    hi -= ((13.0 - h) / 4.0) * Math.sqrt((17.0 - Math.abs(t - 95.0)) / 17.0);
  } else if (h > 85.0 && t >= 80.0 && t <= 87.0) {
    hi += ((h - 85.0) / 10.0) * ((87.0 - t) / 5.0);
  }
  return hi;
}

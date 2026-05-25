// Unit conversions for the mostlyright SDK.
//
// Ported from `packages/core/src/mostlyright/_internal/_convert.py`.
//
// CRITICAL: No rounding anywhere. Store float64 as-is. The Python module's
// "no _go_round / no round / no math.floor(x + 0.5)" rule applies here too —
// every formula returns the raw float64 result.

// ---------------------------------------------------------------------------
// Constants (exact-by-definition where possible)
// ---------------------------------------------------------------------------

export const KT_TO_MPH = 1.15078;
/** Exact: 1 knot = 1852 m / 3600 s. */
export const KT_TO_MS = 1852.0 / 3600.0;
/** Exact by definition (mile → kilometre). */
export const MI_TO_KM = 1.609344;
/** Exact by definition (mile → metre). */
export const MI_TO_M = 1609.344;
/** Exact by definition (foot → metre). */
export const FT_TO_M = 0.3048;
/** Exact by definition (inch → millimetre). */
export const IN_TO_MM = 25.4;
/** WMO standard conversion factor (hectopascal → inHg). */
export const HPA_TO_INHG = 0.0295299875;

// August–Roche–Magnus approximation (Alduchov & Eskridge 1996)
export const MAGNUS_A = 17.625;
/** Celsius. */
export const MAGNUS_B = 243.04;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function finiteOrNull(v: number | null | undefined): number | null {
  if (v === null || v === undefined) return null;
  return Number.isFinite(v) ? v : null;
}

// ---------------------------------------------------------------------------
// Public conversions
// ---------------------------------------------------------------------------

export function ktToMs(kt: number | null): number | null {
  const v = finiteOrNull(kt);
  return v === null ? null : v * KT_TO_MS;
}

export function ktToMph(kt: number | null): number | null {
  const v = finiteOrNull(kt);
  return v === null ? null : v * KT_TO_MPH;
}

export function miToKm(mi: number | null): number | null {
  const v = finiteOrNull(mi);
  return v === null ? null : v * MI_TO_KM;
}

export function miToM(mi: number | null): number | null {
  const v = finiteOrNull(mi);
  return v === null ? null : v * MI_TO_M;
}

export function ftToM(ft: number | null): number | null {
  const v = finiteOrNull(ft);
  return v === null ? null : v * FT_TO_M;
}

export function inchesToMm(inches: number | null): number | null {
  const v = finiteOrNull(inches);
  return v === null ? null : v * IN_TO_MM;
}

export function celsiusToFahrenheit(c: number | null): number | null {
  const v = finiteOrNull(c);
  return v === null ? null : (v * 9) / 5 + 32;
}

export function fahrenheitToCelsius(f: number | null): number | null {
  const v = finiteOrNull(f);
  return v === null ? null : ((v - 32) * 5) / 9;
}

export function hpaToInhg(hpa: number | null): number | null {
  const v = finiteOrNull(hpa);
  return v === null ? null : v * HPA_TO_INHG;
}

/**
 * Compute relative humidity (%) from temperature and dewpoint (both Celsius)
 * via the August–Roche–Magnus approximation. Result is clamped to [0, 100];
 * non-finite or null inputs return null.
 */
export function computeRelativeHumidity(tempC: number | null, dewpC: number | null): number | null {
  const t = finiteOrNull(tempC);
  const td = finiteOrNull(dewpC);
  if (t === null || td === null) return null;
  // exp can overflow at extreme inputs; guard for safety.
  const numer = Math.exp((MAGNUS_A * td) / (MAGNUS_B + td));
  const denom = Math.exp((MAGNUS_A * t) / (MAGNUS_B + t));
  if (!Number.isFinite(numer) || !Number.isFinite(denom) || denom === 0) {
    return null;
  }
  const rh = (100.0 * numer) / denom;
  return Math.max(0.0, Math.min(rh, 100.0));
}

/**
 * Compute feels-like temperature in Fahrenheit (full NWS algorithm).
 *
 * - Wind chill at or below 50°F with wind > 3 mph.
 * - Heat index at or above 80°F with known RH.
 * - Plain temp otherwise. No rounding.
 *
 * `windKt` is in knots (matches Python signature); null is treated as zero.
 * `rh` is relative humidity in [0, 100]; null disables the heat-index branch.
 */
export function computeFeelsLike(
  tempF: number | null,
  windKt: number | null,
  rh: number | null,
): number | null {
  const t = finiteOrNull(tempF);
  if (t === null) return null;

  let wMph = 0.0;
  if (windKt !== null && windKt !== undefined) {
    const w = Number.isFinite(windKt) ? windKt * KT_TO_MPH : null;
    if (w === null || !Number.isFinite(w)) return null;
    wMph = w;
  }

  // Treat non-finite rh as missing (don't feed NaN into heat index).
  let rhSafe: number | null = rh;
  if (rhSafe !== null && rhSafe !== undefined && !Number.isFinite(rhSafe)) {
    rhSafe = null;
  }

  // Wind chill (NWS): valid for temp <= 50°F and wind > 3 mph
  if (t <= 50.0 && wMph > 3.0) {
    return 35.74 + 0.6215 * t - 35.75 * wMph ** 0.16 + 0.4275 * t * wMph ** 0.16;
  }

  // Heat index (NWS): requires known RH
  if (t >= 80.0 && rhSafe !== null) {
    const h = rhSafe;
    // Step 1: Steadman simplified
    const simple = 0.5 * (t + 61.0 + (t - 68.0) * 1.2 + h * 0.094);
    if ((simple + t) / 2.0 < 80.0) {
      return simple;
    }

    // Step 2: Rothfusz regression
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

    // Step 3: NWS adjustments
    if (h < 13.0 && t >= 80.0 && t <= 112.0) {
      hi -= ((13.0 - h) / 4.0) * Math.sqrt((17.0 - Math.abs(t - 95.0)) / 17.0);
    } else if (h > 85.0 && t >= 80.0 && t <= 87.0) {
      hi += ((h - 85.0) / 10.0) * ((87.0 - t) / 5.0);
    }

    return hi;
  }

  return t;
}

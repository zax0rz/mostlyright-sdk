// Phase 18 PREC-02: shared Tgroup parser for ASOS METAR remarks.
//
// TS parity port of packages/weather/src/mostlyright/weather/_internal/tgroup.py.
// Extracted so AWC and IEM (and any future consumer) parse Tgroup identically.
// The Tgroup is the canonical tenths-°C encoding of the integer-°F ASOS
// reading; recovering it from raw METAR remarks is the single source of truth
// for U.S. ASOS temperature precision. See
// .planning/phases/18-precision-fix-asos-integer-fahrenheit/18-CONTEXT.md.

/**
 * Regex matching the T-group in METAR remarks: T{s}{SSS}{s}{DDD}.
 *
 * - s=0 positive, s=1 negative.
 * - SSS/DDD = tenths of °C.
 *
 * Examples: `T02560167` → 25.6°C / 16.7°C. `T10390061` → -3.9°C / 6.1°C.
 */
export const TGROUP_RE = /\bT([01])(\d{3})([01])(\d{3})\b/;

/**
 * Parse T-group from METAR remarks for tenths-precision temperature.
 *
 * ASOS stations always include T-group in remarks. Format:
 * `T{s}{SSS}{s}{DDD}` where s=0 positive, s=1 negative, SSS=temp tenths °C,
 * DDD=dewpoint tenths °C. Searches only the remarks section (after `RMK`)
 * to avoid false positives on body group patterns.
 *
 * Returns `[temp_c, dewpoint_c]` as a 2-tuple, mirroring the Python helper
 * shape. Either element may be `null`:
 * - `[null, null]` when input is empty/null, has no `RMK` section, or no
 *   Tgroup match.
 *
 * @example
 *   parseTgroup("KLGA 281451Z 27008KT 10SM CLR 27/06 A3001 RMK T02670061")
 *   // → [26.7, 6.1]
 */
export function parseTgroup(rawMetar: string | null | undefined): [number | null, number | null] {
  if (!rawMetar) return [null, null];
  // T-group is a remarks-only element — search only after RMK.
  // No RMK section = no T-group. Do NOT fallback to full string to avoid
  // false positives on body group patterns.
  const rmkIdx = rawMetar.indexOf("RMK");
  if (rmkIdx < 0) return [null, null];
  const match = TGROUP_RE.exec(rawMetar.slice(rmkIdx));
  if (!match) return [null, null];
  const tSign = match[1] === "1" ? -1 : 1;
  const tVal = (Number.parseInt(match[2] as string, 10) / 10.0) * tSign;
  const dSign = match[3] === "1" ? -1 : 1;
  const dVal = (Number.parseInt(match[4] as string, 10) / 10.0) * dSign;
  return [tVal, dVal];
}

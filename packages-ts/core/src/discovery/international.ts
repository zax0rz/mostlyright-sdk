// TS-W6 Wave 2 — internationalDailyExtremes rollup.
//
// Ports Python `mostlyright.international.daily_extremes` semantics:
//
//   - For each row, parse `observed_at` as UTC, convert to the station's IANA
//     local calendar date via `Intl.DateTimeFormat` (the only universally-
//     available tz-aware extractor in JS), bucket per `(localDate)`.
//   - For each bucketed day:
//       * n_obs < 12 → tmin/tmax/tmean null (low coverage; matches Python
//         `_LOW_COVERAGE_THRESHOLD`).
//       * Otherwise: tmin = min(temp_c), tmax = max(temp_c), tmean = mean.
//         Round HALF_UP — to 1 decimal for US stations, whole °C for intl.
//   - precip_mm summed across rows that report it (mm — matches the
//     observation schema field name; Python uses `precip_inches` because its
//     historical units are inches, but the TS schema is mm).
//
// `stationTz` is required because the input rows are raw observations (no
// station registry lookup here); callers supply the IANA tz string for the
// station they're rolling up.

const LOW_COVERAGE_THRESHOLD = 12;

/** Minimal row shape consumed by `internationalDailyExtremes`. */
export interface InternationalRow {
  /** ISO 8601 UTC instant. Must end with `Z` or include an offset. */
  observed_at?: string | null;
  /** Air temperature in degrees Celsius. */
  temp_c?: number | null;
  /** 1-hour precipitation total in millimeters. */
  precip_mm_1h?: number | null;
  /** Source identifier (preserved on the tmin/tmax aggregate). */
  source?: string | null;
}

export interface DailyExtreme {
  /** Station-local calendar date as `YYYY-MM-DD`. */
  localDate: string;
  /** Count of rows with a parseable temp_c. */
  nObs: number;
  /** Min temperature in °C, or null on low coverage. */
  tempMinC: number | null;
  /** Max temperature in °C, or null on low coverage. */
  tempMaxC: number | null;
  /** Mean temperature in °C, or null on low coverage. */
  tempMeanC: number | null;
  /** Min temperature in °F, or null on low coverage. */
  tempMinF: number | null;
  /** Max temperature in °F, or null on low coverage. */
  tempMaxF: number | null;
  /** Total 1-hour precipitation across the local day, in mm. */
  precipMm: number;
  /** Source identifier of the row that produced tmin (or null on low coverage). */
  sourceTmin: string | null;
  /** Source identifier of the row that produced tmax (or null on low coverage). */
  sourceTmax: string | null;
}

export interface InternationalDailyExtremesOptions {
  /** IANA timezone identifier for the station, e.g. `"Asia/Tokyo"`. Required. */
  stationTz: string;
  /**
   * Decimal places for HALF_UP rounding. Defaults to 0 (whole °C) — the
   * international convention. Pass `1` for US-station tenths.
   */
  precision?: number;
  /**
   * Minimum number of observations required for tmin/tmax/tmean to be
   * populated. Defaults to 12 (the Python threshold). Tests can override.
   */
  minObs?: number;
}

const PARTS_CACHE = new Map<string, Intl.DateTimeFormat>();

function getDateFormatter(tz: string): Intl.DateTimeFormat {
  let f = PARTS_CACHE.get(tz);
  if (f === undefined) {
    // `formatToParts` with these options yields `{year, month, day}` parts
    // for the given UTC instant in the requested tz. The result is the
    // local calendar date even across DST and arbitrary UTC offsets.
    f = new Intl.DateTimeFormat("en-US", {
      timeZone: tz,
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
    });
    PARTS_CACHE.set(tz, f);
  }
  return f;
}

function localDateFor(instant: Date, tz: string): string {
  const parts = getDateFormatter(tz).formatToParts(instant);
  let y = "";
  let m = "";
  let d = "";
  for (const p of parts) {
    if (p.type === "year") y = p.value;
    else if (p.type === "month") m = p.value;
    else if (p.type === "day") d = p.value;
  }
  return `${y}-${m}-${d}`;
}

function parseInstant(observed: string | null | undefined): Date | null {
  if (observed === undefined || observed === null || observed.length === 0) {
    return null;
  }
  const ms = Date.parse(observed);
  if (Number.isNaN(ms)) return null;
  return new Date(ms);
}

function roundHalfUp(value: number, places: number): number {
  if (!Number.isFinite(value)) return value;
  // HALF_UP rounding: tie-breaks always round away from zero for positives,
  // toward +∞ for negatives. JS `Math.round` rounds half toward +∞, which
  // disagrees with HALF_UP on negative .5 boundaries; replicate the Python
  // Decimal behavior by adjusting positives only and mirroring negatives.
  const scale = 10 ** places;
  const sign = value < 0 ? -1 : 1;
  const abs = Math.abs(value);
  // Add a tiny epsilon scaled to the magnitude to defeat IEEE-754 errors that
  // make `2.675 * 100` come out as `267.49999...`. The epsilon is small
  // enough (relative-1e-12) not to affect legitimate non-tie values.
  const rounded = Math.floor(abs * scale + 0.5 + abs * 1e-12) / scale;
  return sign * rounded;
}

function cToF(c: number): number {
  return c * 1.8 + 32;
}

/**
 * Roll up observation rows to per-local-calendar-day temperature extremes.
 *
 * @param rows  raw observation rows (any source). Rows without a parseable
 *              `observed_at` are dropped.
 * @param opts  `stationTz` is required. Optional `precision` (default 0;
 *              pass 1 for US-station tenths) and `minObs` (default 12).
 *
 * @returns one entry per local calendar day with at least one row. Days
 *          with fewer than `minObs` rows have temps set to null.
 */
export function internationalDailyExtremes(
  rows: ReadonlyArray<InternationalRow>,
  opts: InternationalDailyExtremesOptions,
): DailyExtreme[] {
  const tz = opts.stationTz;
  if (typeof tz !== "string" || tz.length === 0) {
    throw new RangeError("internationalDailyExtremes: stationTz is required (non-empty string)");
  }
  const precision = opts.precision ?? 0;
  const minObs = opts.minObs ?? LOW_COVERAGE_THRESHOLD;

  // Validate tz up front so we get a clean error rather than per-row failures.
  try {
    getDateFormatter(tz);
  } catch (e) {
    throw new RangeError(
      `internationalDailyExtremes: invalid stationTz ${JSON.stringify(tz)}: ${(e as Error).message}`,
    );
  }

  type Bucket = {
    temps: { value: number; source: string | null }[];
    precipMm: number;
  };
  const byLocalDate = new Map<string, Bucket>();

  for (const row of rows) {
    const instant = parseInstant(row.observed_at);
    if (instant === null) continue;
    const localDate = localDateFor(instant, tz);
    let bucket = byLocalDate.get(localDate);
    if (bucket === undefined) {
      bucket = { temps: [], precipMm: 0 };
      byLocalDate.set(localDate, bucket);
    }
    const t = row.temp_c;
    if (typeof t === "number" && Number.isFinite(t)) {
      bucket.temps.push({ value: t, source: row.source ?? null });
    }
    const p = row.precip_mm_1h;
    if (typeof p === "number" && Number.isFinite(p)) {
      bucket.precipMm += p;
    }
  }

  const out: DailyExtreme[] = [];
  const sortedDates = [...byLocalDate.keys()].sort();
  for (const localDate of sortedDates) {
    const bucket = byLocalDate.get(localDate);
    if (bucket === undefined) continue;
    const nObs = bucket.temps.length;
    let tempMinC: number | null = null;
    let tempMaxC: number | null = null;
    let tempMeanC: number | null = null;
    let sourceTmin: string | null = null;
    let sourceTmax: string | null = null;

    // Codex iter-4 P2: `nObs >= minObs` alone is not enough when minObs=0,
    // because a day with a parseable timestamp but no finite temp_c reaches
    // this branch with nObs === 0 and then dereferences bucket.temps[0].
    // Always require at least one temperature row before computing extremes.
    if (nObs > 0 && nObs >= minObs) {
      let minIdx = 0;
      let maxIdx = 0;
      let sum = 0;
      for (let i = 0; i < bucket.temps.length; i += 1) {
        const v = bucket.temps[i] as { value: number; source: string | null };
        sum += v.value;
        const minRow = bucket.temps[minIdx] as { value: number };
        const maxRow = bucket.temps[maxIdx] as { value: number };
        if (v.value < minRow.value) minIdx = i;
        if (v.value > maxRow.value) maxIdx = i;
      }
      const mean = sum / nObs;
      const minRow = bucket.temps[minIdx] as { value: number; source: string | null };
      const maxRow = bucket.temps[maxIdx] as { value: number; source: string | null };
      tempMinC = roundHalfUp(minRow.value, precision);
      tempMaxC = roundHalfUp(maxRow.value, precision);
      tempMeanC = roundHalfUp(mean, precision);
      sourceTmin = minRow.source;
      sourceTmax = maxRow.source;
    }

    out.push(
      Object.freeze({
        localDate,
        nObs,
        tempMinC,
        tempMaxC,
        tempMeanC,
        tempMinF: tempMinC === null ? null : roundHalfUp(cToF(tempMinC), precision),
        tempMaxF: tempMaxC === null ? null : roundHalfUp(cToF(tempMaxC), precision),
        precipMm: roundHalfUp(bucket.precipMm, 4),
        sourceTmin,
        sourceTmax,
      }),
    );
  }

  return out;
}

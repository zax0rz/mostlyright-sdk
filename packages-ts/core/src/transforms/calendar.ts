// TS-W4 Plan 03 Task 1 — calendarFeatures transform.
//
// Pure row→row port of Python `tradewinds.transforms.calendar_features`
// (packages/core/src/tradewinds/transforms.py:71-100). Adds 8 cyclical-pair
// columns (month_sin/cos, dow_sin/cos, hour_sin/cos, day_of_year_sin/cos)
// to each output row; source rows NOT mutated.
//
// TZ awareness (the load-bearing detail): when the caller passes `tz` (an
// IANA name like 'America/New_York'), month/dow/hour/dayOfYear come from
// the LOCAL clock in that tz — extracted via `Intl.DateTimeFormat`
// (browser + Node built-in; NO luxon/date-fns dep, keeping the bundle
// under the TS-BUNDLE-01 25 KB gate).
//
// When `tz` is omitted, UTC parts of the parsed date are used
// (`getUTCMonth`, `getUTCDay`, etc.).
//
// Cyclical formulas (verbatim from Python `transforms.py:90-99`):
//   month_sin = sin(2π·month/12), month ∈ [1, 12]
//   dow_sin   = sin(2π·dow/7),    dow ∈ [0, 6] (Mon=0..Sun=6 ISO order)
//   hour_sin  = sin(2π·hour/24),  hour ∈ [0, 23]
//   day_of_year_sin = sin(2π·doy/365.0) — note 365.0 (NOT 365.25, NOT 366)
//
// Day-of-week ordering: ISO Monday-first (Mon=0..Sun=6), matching Python's
// `pd.Series.dt.dayofweek`. JS's native `Date.prototype.getDay()` uses
// Sunday=0..Saturday=6, so we convert with `(jsDay + 6) % 7`.
//
// Null handling: rows whose `dateCol` value is null/undefined/non-parseable
// produce `null` (NOT NaN) for all 8 derived columns. Matches Python's
// returning NaT/NaN without raising.

/**
 * Add 8 cyclical-pair calendar features to each row.
 *
 * Pairs (sin²+cos² ≈ 1, so a model sees wraparound — Dec→Jan is 1 month
 * apart, not 11):
 *
 * - `month_sin` / `month_cos`            (period 12)
 * - `dow_sin` / `dow_cos`                (period 7, ISO Mon=0..Sun=6)
 * - `hour_sin` / `hour_cos`              (period 24)
 * - `day_of_year_sin` / `day_of_year_cos` (period 365.0, NOT 365.25)
 *
 * TZ handling: when `tz` is an IANA zone name like 'America/New_York',
 * month/dow/hour/dayOfYear come from the LOCAL clock in that tz (via
 * `Intl.DateTimeFormat`). When `tz` is omitted, UTC parts are used.
 *
 * Invalid `tz` throws `RangeError` BEFORE any row processing (fail-fast).
 *
 * @param rows    input rows (NOT mutated)
 * @param dateCol column name containing a date — accepted as ISO string,
 *                `Date` instance, or finite epoch-ms number
 * @param tz      optional IANA timezone name (validated upfront)
 * @returns       new array of rows, each carrying 8 new derived columns
 *                (each value is a `number` from sin/cos, or `null` when
 *                the row's date is non-parseable)
 * @throws RangeError if `tz` is provided but not a valid IANA zone
 */
export function calendarFeatures<Row extends Record<string, unknown>>(
  rows: ReadonlyArray<Row>,
  dateCol: string,
  tz?: string,
): ReadonlyArray<Row & Record<string, number | null>> {
  // Fail-fast tz validation: construct a formatter once, before any row work.
  // Invalid IANA names throw RangeError from the Intl constructor; we
  // re-throw with a clearer message that includes the offending string.
  let formatter: Intl.DateTimeFormat | null = null;
  if (tz !== undefined) {
    try {
      formatter = new Intl.DateTimeFormat("en-US", {
        timeZone: tz,
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
        hour12: false,
        weekday: "short",
      });
    } catch (e) {
      throw new RangeError(`calendarFeatures: invalid IANA timezone '${tz}': ${String(e)}`);
    }
  }

  const TAU = 2 * Math.PI;
  // Sentinel object for the null-date case: all 8 derived columns are null
  // (NOT NaN; matches Python's None/NaT for unparseable dates).
  const NULLS = {
    month_sin: null,
    month_cos: null,
    dow_sin: null,
    dow_cos: null,
    hour_sin: null,
    hour_cos: null,
    day_of_year_sin: null,
    day_of_year_cos: null,
  } as const;

  // Map Intl's `weekday: 'short'` (en-US: Mon, Tue, ..., Sun) to the ISO
  // Monday-first ordering used by Python's `dt.dayofweek` (Mon=0..Sun=6).
  const WEEKDAY_INDEX: Readonly<Record<string, number>> = {
    Mon: 0,
    Tue: 1,
    Wed: 2,
    Thu: 3,
    Fri: 4,
    Sat: 5,
    Sun: 6,
  };

  const out: Array<Row & Record<string, number | null>> = [];
  for (const r of rows) {
    const raw = r[dateCol];

    // Parse `raw` into a valid Date, or `null` if the value isn't a usable date.
    let d: Date | null = null;
    if (raw instanceof Date) {
      d = Number.isFinite(raw.getTime()) ? raw : null;
    } else if (typeof raw === "string") {
      const parsed = new Date(raw);
      d = Number.isFinite(parsed.getTime()) ? parsed : null;
    } else if (typeof raw === "number" && Number.isFinite(raw)) {
      d = new Date(raw);
    }

    if (d === null) {
      out.push({ ...r, ...NULLS } as Row & Record<string, number | null>);
      continue;
    }

    let month: number; // 1..12
    let dow: number; //   0..6 (Mon=0..Sun=6 ISO)
    let hour: number; //  0..23
    let doy: number; //   1..366

    if (formatter !== null) {
      // TZ branch: use Intl.DateTimeFormat.formatToParts to pluck the
      // LOCAL-tz year/month/day/hour/weekday for `d`. This is the
      // browser+Node native pathway for tz-aware calendar extraction —
      // no luxon/date-fns dep required.
      const parts = formatter.formatToParts(d);
      const get = (t: string): string => parts.find((p) => p.type === t)?.value ?? "";
      const y = Number.parseInt(get("year"), 10);
      month = Number.parseInt(get("month"), 10);
      const dom = Number.parseInt(get("day"), 10);
      hour = Number.parseInt(get("hour"), 10);
      // `weekday: 'short'` returns 'Mon', 'Tue', ..., 'Sun' in en-US.
      // Map to ISO Mon=0..Sun=6. `?? 0` is unreachable in practice (formatter
      // always emits a weekday part), but kept defensive.
      dow = WEEKDAY_INDEX[get("weekday")] ?? 0;
      // Day-of-year from the tz-LOCAL (y, month, dom) tuple: number of full
      // days between Jan 1 of that year and the local date, +1. Computing
      // via `Date.UTC` differences sidesteps DST: both anchors share the
      // same UTC offset (they're treated as UTC for arithmetic only).
      doy = Math.floor((Date.UTC(y, month - 1, dom) - Date.UTC(y, 0, 1)) / 86400000) + 1;
    } else {
      // UTC branch: pull straight from the Date's UTC accessors.
      month = d.getUTCMonth() + 1;
      // JS getUTCDay: Sun=0..Sat=6. Convert to ISO Mon=0..Sun=6.
      dow = (d.getUTCDay() + 6) % 7;
      hour = d.getUTCHours();
      const yStart = Date.UTC(d.getUTCFullYear(), 0, 1);
      doy = Math.floor((d.getTime() - yStart) / 86400000) + 1;
    }

    const derived = {
      month_sin: Math.sin((TAU * month) / 12),
      month_cos: Math.cos((TAU * month) / 12),
      dow_sin: Math.sin((TAU * dow) / 7),
      dow_cos: Math.cos((TAU * dow) / 7),
      hour_sin: Math.sin((TAU * hour) / 24),
      hour_cos: Math.cos((TAU * hour) / 24),
      day_of_year_sin: Math.sin((TAU * doy) / 365.0),
      day_of_year_cos: Math.cos((TAU * doy) / 365.0),
    };

    out.push({ ...r, ...derived } as Row & Record<string, number | null>);
  }
  return out;
}

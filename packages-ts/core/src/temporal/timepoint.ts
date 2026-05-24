// UTC-aware timestamp wrapper for tradewinds.core (TS-W3 Plan 04 Task 1).
//
// Mirrors `packages/core/src/tradewinds/core/temporal/timepoint.py`.
// Every timestamp in tradewinds.core is UTC-aware. TimePoint rejects:
//  - naive ISO strings (no Z, no +HH:MM, no -HH:MM offset)
//  - date-only ISO strings (e.g. "2026-05-21" — no time component)
//  - date-only ISO strings with a timezone suffix (e.g. "2026-05-21Z" or
//    "2026-05-21+00:00") — Python `_from_iso_string` rejects these by
//    requiring a `T` (or space) separator BEFORE checking the tz suffix.
//  - NaN / Infinity / -Infinity (via Date(NaN), Date(Infinity), etc.)
//  - empty / whitespace-only strings
//  - non-Date, non-string inputs (TypeError; belt-and-suspenders runtime guard)
//
// Note on Date inputs: a JS `Date` is just epoch ms — no timezone metadata.
// "Naive" only applies to STRING inputs, where we can inspect the source
// text for a timezone indicator. For Date inputs we only reject NaN/Infinity.

const ISO_DATE_ONLY = /^\d{4}-\d{2}-\d{2}$/;
// ISO 8601 requires a `T` (or RFC 3339 space) separator between the date
// and time components. Without one, the string is a bare date — even if a
// timezone suffix is appended (`"2026-05-21Z"`). Mirrors the Python guard
// in `_from_iso_string` that checks `"T" not in s and " " not in s`.
const DATETIME_SEPARATOR = /[T ]/;
const TZ_SUFFIX = /(?:Z|[+-]\d{2}:?\d{2})$/;
// Calendar-validity check (iter-3 C8): extract the YYYY-MM-DD prefix so we
// can verify that the parsed UTC date matches the literal date the caller
// supplied. `Date.parse("2025-02-30T00:00:00Z")` silently normalizes to
// `2025-03-02T00:00:00.000Z`, while Python `datetime.fromisoformat(...)`
// raises ValueError. Mirror the Python contract by rejecting any string
// whose calendar fields don't survive the round-trip.
const ISO_DATE_PREFIX = /^(\d{4})-(\d{2})-(\d{2})/;

/**
 * UTC-aware timestamp wrapper.
 *
 * Equivalent to Python's `tradewinds.core.TimePoint`. Constructed from either
 * a `Date` (rejects NaN/Infinity) or a tz-aware ISO 8601 string (rejects
 * naive / date-only inputs). Internally stored as a single epoch-ms Date.
 *
 * Immutable: the underlying Date is hidden behind a private `#utc` field
 * and `toUTCDate()` returns a defensive copy so callers cannot mutate the
 * wrapped instant.
 */
export class TimePoint {
  // Private field — naive ISO strings cannot leak back through any accessor.
  readonly #utc: Date;

  constructor(value: Date | string) {
    if (value instanceof Date) {
      const t = value.getTime();
      if (!Number.isFinite(t)) {
        // RangeError for NaN/Infinity — see "date-only" / "naive" peers below.
        throw new RangeError("TimePoint does not accept NaN/Infinity Date");
      }
      this.#utc = new Date(t);
      return;
    }
    if (typeof value !== "string") {
      throw new TypeError(`TimePoint accepts Date or ISO 8601 string; got ${typeof value}`);
    }
    const trimmed = value.trim();
    if (trimmed.length === 0) {
      throw new RangeError("TimePoint requires non-empty ISO 8601 string");
    }
    // Date-only check: a bare "YYYY-MM-DD" has no time component.
    if (ISO_DATE_ONLY.test(trimmed)) {
      throw new RangeError(
        `TimePoint requires datetime, not date-only (got ${JSON.stringify(
          value,
        )}). Use an ISO 8601 datetime with a timezone, e.g. '2026-05-21T14:30:00Z'.`,
      );
    }
    // Separator check (MUST run BEFORE the tz-suffix check): a date-only
    // payload like "2026-05-21Z" or "2026-05-21+00:00" has no `T`/space
    // separator and is still a bare date — Date.parse silently normalizes
    // it to midnight UTC, but Python `_from_iso_string` rejects it. Reject
    // here so the constructor matches the Python contract exactly.
    if (!DATETIME_SEPARATOR.test(trimmed)) {
      throw new RangeError(
        `TimePoint requires datetime, not date-only (got ${JSON.stringify(
          value,
        )}). ISO 8601 requires a 'T' or space separator between the date and time, e.g. '2026-05-21T14:30:00Z'.`,
      );
    }
    // Naive check: must end in Z, +HH:MM, +HHMM, -HH:MM, or -HHMM.
    if (!TZ_SUFFIX.test(trimmed)) {
      throw new RangeError(
        `TimePoint requires tz-aware timestamp; got naive ISO string (${JSON.stringify(
          value,
        )}). Include a timezone offset (e.g. 'Z' or '+00:00').`,
      );
    }
    const parsed = Date.parse(trimmed);
    if (!Number.isFinite(parsed)) {
      throw new RangeError(`TimePoint could not parse ISO 8601 string ${JSON.stringify(value)}`);
    }
    // Calendar-validity check (iter-3 C8): `Date.parse` is forgiving — it
    // silently normalizes impossible dates (e.g. "2025-02-30T..." becomes
    // "2025-03-02T...", "2025-13-01T..." becomes "2026-01-01T..."). Python
    // `datetime.fromisoformat` raises ValueError for the same inputs. To
    // match the Python contract, extract the YYYY-MM-DD prefix from the
    // ORIGINAL trimmed input and require that the parsed Date's UTC
    // year/month/day match exactly. Any mismatch means Date.parse rolled
    // the date over — reject loudly. The parsed date's UTC fields are the
    // right basis for comparison because non-UTC tz-suffixes (e.g.
    // "...T23:00:00-05:00") legitimately shift the wall-clock date forward
    // when converted to UTC, but only by ±1 day; an off-by-one shift due
    // to a legitimate tz offset will still hit this check, so we ALSO
    // accept a match against the local fields the source string asserts.
    //
    // Strategy: compute what the source-side year/month/day would be after
    // applying the declared UTC offset, then compare those derived fields
    // against the literal YYYY-MM-DD in the string. If the source string
    // was an impossible calendar date, Date.parse's silent normalization
    // will have shifted the underlying ms beyond what the declared offset
    // alone could account for, so the derived fields won't match.
    const dateMatch = ISO_DATE_PREFIX.exec(trimmed);
    if (dateMatch !== null) {
      const litYear = Number(dateMatch[1]);
      const litMonth = Number(dateMatch[2]);
      const litDay = Number(dateMatch[3]);
      // Derive the source-side date by undoing the declared tz offset.
      // The trailing tz suffix is one of: "Z", "+HH:MM", "-HH:MM", "+HHMM",
      // "-HHMM". For "Z" the offset is 0. For the signed forms, the offset
      // is the source's distance ahead/behind UTC: a "-05:00" tz on
      // "10:00:00" means UTC is 15:00:00, so to recover the source's
      // wall-clock year/month/day we ADD the offset back to the UTC ms
      // before extracting Y/M/D. Equivalently: build a Date at the same
      // ms, then read its UTC fields after offsetting.
      let offsetMin = 0;
      const tzMatch = /(Z|[+-]\d{2}:?\d{2})$/.exec(trimmed);
      // Under `noUncheckedIndexedAccess: true`, `tzMatch[1]` is typed
      // `string | undefined` even after the `null` guard. Capture it once
      // and narrow with an explicit undefined check (unreachable when
      // tzMatch is non-null — the regex always populates group 1 — but
      // the type checker can't prove that on its own).
      const tz = tzMatch === null ? undefined : tzMatch[1];
      if (tz !== undefined && tz !== "Z") {
        // tz is like "+05:30", "-0500", "+0000".
        const sign = tz.startsWith("-") ? -1 : 1;
        const body = tz.slice(1).replace(":", "");
        const hh = Number(body.slice(0, 2));
        const mm = Number(body.slice(2, 4));
        offsetMin = sign * (hh * 60 + mm);
      }
      // The source's wall-clock instant in ms-since-epoch: take the UTC ms
      // and add the offset (positive offset means source is ahead of UTC).
      const sourceMs = parsed + offsetMin * 60_000;
      const sourceDate = new Date(sourceMs);
      const derivedYear = sourceDate.getUTCFullYear();
      const derivedMonth = sourceDate.getUTCMonth() + 1;
      const derivedDay = sourceDate.getUTCDate();
      if (derivedYear !== litYear || derivedMonth !== litMonth || derivedDay !== litDay) {
        throw new RangeError(
          `TimePoint rejects impossible calendar date in ${JSON.stringify(
            value,
          )}: literal date ${dateMatch[0]} does not survive round-trip (parser normalized to ${derivedYear}-${String(derivedMonth).padStart(2, "0")}-${String(derivedDay).padStart(2, "0")}). Python datetime.fromisoformat raises ValueError on this input.`,
        );
      }
    }
    this.#utc = new Date(parsed);
  }

  /** Return a defensive copy of the underlying UTC Date. */
  toUTCDate(): Date {
    return new Date(this.#utc.getTime());
  }

  /** Return the canonical ISO 8601 UTC string (always ends in 'Z'). */
  toISOString(): string {
    return this.#utc.toISOString();
  }

  /**
   * Return the Python-compatible ISO 8601 UTC string.
   *
   * Where {@link toISOString} emits the JS-native `"...Z"` suffix and
   * forces `.000` millisecond padding, this method matches Python's
   * `datetime.isoformat()` output for a UTC-tz-aware datetime:
   *
   *   - tz suffix is `+00:00`, never `Z`
   *   - subsecond portion is omitted when zero (`"...T12:00:00+00:00"`)
   *   - microsecond portion appears as 6 digits when non-zero
   *     (`"...T12:00:00.123456+00:00"`); JS Dates only carry millisecond
   *     precision so we 3-pad-then-zero-pad to 6 digits for parity with
   *     `pd.Timestamp(...).isoformat()` against a `datetime64[ms]`.
   *
   * Used by error payloads (LeakageError.toDict, sample violations) so
   * MCP clients comparing the on-wire string across the Python and TS
   * SDKs see byte-equivalent values. Iter-1 H1 fix.
   */
  toPythonIso(): string {
    const utcMs = this.#utc.getTime();
    const year = this.#utc.getUTCFullYear();
    const month = String(this.#utc.getUTCMonth() + 1).padStart(2, "0");
    const day = String(this.#utc.getUTCDate()).padStart(2, "0");
    const hour = String(this.#utc.getUTCHours()).padStart(2, "0");
    const minute = String(this.#utc.getUTCMinutes()).padStart(2, "0");
    const second = String(this.#utc.getUTCSeconds()).padStart(2, "0");
    const ms = this.#utc.getUTCMilliseconds();
    const head = `${year}-${month}-${day}T${hour}:${minute}:${second}`;
    if (ms === 0) {
      return `${head}+00:00`;
    }
    // JS only carries ms precision (3 digits); pad to 6 for parity with
    // Python's microsecond-precision isoformat.
    const micros = `${String(ms).padStart(3, "0")}000`;
    // Reference utcMs to keep the linter happy (we computed but didn't
    // need it once the breakdown is in hand).
    void utcMs;
    return `${head}.${micros}+00:00`;
  }

  /**
   * Format this instant in an IANA timezone via Intl.DateTimeFormat.
   * Display helper only — canonical storage stays UTC.
   *
   * Uses `en-CA` locale for a YYYY-MM-DD, HH:MM:SS shape that's easy to grep
   * in logs. The exact output format may vary slightly across Node releases;
   * callers writing tests should use loose contains-style assertions.
   */
  asZone(tz: string): string {
    return new Intl.DateTimeFormat("en-CA", {
      timeZone: tz,
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      hour12: false,
    }).format(this.#utc);
  }

  equals(other: TimePoint): boolean {
    return this.#utc.getTime() === other.#utc.getTime();
  }

  before(other: TimePoint): boolean {
    return this.#utc.getTime() < other.#utc.getTime();
  }

  after(other: TimePoint): boolean {
    return this.#utc.getTime() > other.#utc.getTime();
  }

  /** Return a TimePoint for the current UTC instant. */
  static now(): TimePoint {
    return new TimePoint(new Date());
  }
}

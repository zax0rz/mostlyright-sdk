// UTC-aware timestamp wrapper for tradewinds.core (TS-W3 Plan 04 Task 1).
//
// Mirrors `packages/core/src/tradewinds/core/temporal/timepoint.py`.
// Every timestamp in tradewinds.core is UTC-aware. TimePoint rejects:
//  - naive ISO strings (no Z, no +HH:MM, no -HH:MM offset)
//  - date-only ISO strings (e.g. "2026-05-21" — no time component)
//  - NaN / Infinity / -Infinity (via Date(NaN), Date(Infinity), etc.)
//  - empty / whitespace-only strings
//  - non-Date, non-string inputs (TypeError; belt-and-suspenders runtime guard)
//
// Note on Date inputs: a JS `Date` is just epoch ms — no timezone metadata.
// "Naive" only applies to STRING inputs, where we can inspect the source
// text for a timezone indicator. For Date inputs we only reject NaN/Infinity.

const ISO_DATE_ONLY = /^\d{4}-\d{2}-\d{2}$/;
const TZ_SUFFIX = /(?:Z|[+-]\d{2}:?\d{2})$/;

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

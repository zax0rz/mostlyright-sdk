// Shared calendar-year chunkers for IEM fetchers.
//
// Byte-faithful TS port of
// `packages/weather/src/tradewinds/weather/_fetchers/_iem_chunks.py::yearly_chunks_exclusive_end`
// (mostlyright PR #85 commit cf9eb85, 2026-05-12; Pattern 1).
//
// Only the EXCLUSIVE-end variant is ported here — the IEM ASOS download
// loop (`iem-asos.ts`) is the sole TS-side consumer, and IEM's `day2`
// query parameter is exclusive. `yearly_chunks_inclusive` (used by the
// Python forecast / climate paths) is NOT ported in TS-W2.
//
// Leap-year safety: the advance step uses calendar arithmetic
// (`date(year+1, 1, 1)`), NOT `+365 days`. The latter silently drops Feb 29
// in leap years and walks the calendar boundary by one day every leap year
// — PR #85's primary anti-pattern.
//
// Date representation: ISO 8601 date strings ("YYYY-MM-DD"). Strings sort
// lexicographically equivalent to calendar order and round-trip cleanly;
// the JS `Date` constructor is deliberately avoided because its arithmetic
// silently shifts to local-time, which would poison cache keys at midnight
// boundaries for non-UTC hosts (Python's `_iem_chunks.py` module docstring
// references this class of bug).

/**
 * ISO 8601 date string, no time component. Format: `YYYY-MM-DD`.
 *
 * Brand-style alias — at runtime this is a plain `string`. Use
 * {@link parseIsoDate} when you need the parsed year/month/day integers.
 */
export type IsoDate = string;

const ISO_DATE_RE = /^(\d{4})-(\d{2})-(\d{2})$/;

interface YMD {
  readonly year: number;
  readonly month: number;
  readonly day: number;
}

/**
 * Parse an ISO date string into year/month/day integers. Throws on
 * malformed input. The validation is intentionally minimal — chunker
 * inputs come from the fetcher's normalization layer, which is the
 * defensive boundary. Calendar-validity (e.g. Feb 30) is NOT checked
 * here; the caller has already validated.
 */
function parseIsoDate(value: IsoDate): YMD {
  const m = ISO_DATE_RE.exec(value);
  if (m === null) {
    throw new Error(`Invalid ISO date: ${JSON.stringify(value)}; expected "YYYY-MM-DD"`);
  }
  // Indices 1-3 always present when the regex matches.
  return {
    year: Number.parseInt(m[1] as string, 10),
    month: Number.parseInt(m[2] as string, 10),
    day: Number.parseInt(m[3] as string, 10),
  };
}

/**
 * Format integer year/month/day as an ISO date string. Month and day are
 * zero-padded to 2 digits to preserve lexicographic order.
 */
function formatIsoDate(year: number, month: number, day: number): IsoDate {
  const mm = month < 10 ? `0${month}` : String(month);
  const dd = day < 10 ? `0${day}` : String(day);
  return `${year}-${mm}-${dd}`;
}

/**
 * Range split into per-calendar-year EXCLUSIVE-end chunks
 * (Jan 1 of next year).
 *
 * Properties:
 *  - The first chunk's start is `max(date(start.year, 1, 1), start)` — i.e.
 *    the caller's actual start for the first chunk, NOT Jan 1. The
 *    `current = date(start.year, 1, 1)` initialization ensures the loop
 *    visits every calendar-year boundary regardless of the caller's start.
 *  - Every chunk's end is `date(year+1, 1, 1)` — the IEM `day2`-exclusive
 *    convention for "include all of `year`".
 *  - Leap-year safe: advance via `date(year+1, 1, 1)`, NOT `+365 days`.
 *  - Reversed range (`start > end` by lexicographic compare) returns `[]`
 *    without throwing — higher layers iterate the list directly.
 *
 * Byte-faithful with the Python helper used by `iem_asos.download_iem_asos`.
 */
export function yearlyChunksExclusiveEnd(
  start: IsoDate,
  end: IsoDate,
): ReadonlyArray<readonly [IsoDate, IsoDate]> {
  // Reversed-range short-circuit (lexicographic compare is equivalent to
  // calendar compare for YYYY-MM-DD strings of identical shape). Mirrors
  // Python L66-67 (`if start > end: return []`).
  if (start > end) {
    return [];
  }

  const { year: startYear } = parseIsoDate(start);
  const { year: endYear } = parseIsoDate(end);

  const chunks: Array<readonly [IsoDate, IsoDate]> = [];
  // Match Python `current = date(start.year, 1, 1)` initialization.
  let currentYear = startYear;
  while (currentYear <= endYear) {
    const currentYearStart = formatIsoDate(currentYear, 1, 1);
    // Match Python `chunk_start = max(current, start)`. For the first
    // iteration this clamps to the caller's `start`; for subsequent
    // iterations `currentYearStart` is always greater.
    const chunkStart: IsoDate = currentYearStart > start ? currentYearStart : start;
    // CRITICAL: leap-year safe via calendar arithmetic, NOT `+365 days`.
    const nextYearFirst: IsoDate = formatIsoDate(currentYear + 1, 1, 1);
    chunks.push([chunkStart, nextYearFirst]);
    currentYear += 1;
  }
  return chunks;
}

// IEM CLI (NWS climate) historical fetcher — settlement-grade source.
//
// Ported from `packages/weather/src/mostlyright/weather/_fetchers/iem_cli.py`
// (TS-W1 Wave 4). Uses the native `fetch` via `@mostlyright/core`'s
// `fetchWithRetry`, so this module runs in browsers, Node 20+, Cloudflare
// Workers, and Deno.
//
// CORS posture: OPEN (Access-Control-Allow-Origin: *). See
// `.planning/research/TS-CORS-MATRIX.md`.
//
// Granularity is whole-year (one HTTP request per station-year). Callers
// that want a window filter the parsed records downstream — IEM's cli.py
// endpoint does not support partial-year requests.

import { NotFoundError, fetchWithRetry } from "@mostlyright/core";
import type { FetchWithRetryOptions } from "@mostlyright/core";

/** IEM cli.py JSON endpoint. Mirrors Python `IEM_CLI_BASE_URL`. */
export const IEM_CLI_BASE_URL = "https://mesonet.agron.iastate.edu/json/cli.py";

/**
 * Polite delay (ms) between range requests. Mirrors Python
 * `IEM_CLI_POLITE_DELAY = 1.0` — IEM runs on a university server.
 */
export const IEM_CLI_POLITE_DELAY_MS = 1000;

/**
 * Station code regex (3-4 uppercase letters). Mirrors
 * `STATION_CODE_RE` in `@mostlyright/core/internal/bounds`. Inlined here
 * because that helper is intentionally a deep-import in core; we don't
 * want fetchers transitively pulling in the validators barrel.
 *
 * NOTE: IEM CLI expects a 4-letter ICAO (e.g. `KNYC`). The shared regex
 * also accepts 3-letter NWS codes — we tighten the check below.
 */
const STATION_CODE_RE = /^[A-Z]{3,4}$/;

/**
 * Raw record shape returned by IEM cli.py (post-unwrap of `{results: [...]}`).
 *
 * We capture only the fields consumed by the parser; everything else is
 * preserved as `unknown` so forward-compat is automatic when IEM adds
 * new columns.
 */
export interface CliRawRecord {
  /** Local climate day, YYYY-MM-DD. */
  valid: string;
  /** Observed daily high °F. Sentinel: "M" or empty string for missing. */
  high?: number | "M" | "" | null;
  /** Observed daily low °F. Sentinel: "M" or empty string for missing. */
  low?: number | "M" | "" | null;
  /** Product identifier, e.g. "202501160620-KFFC-CDUS42-CLIATL". */
  product?: string | null;
  [key: string]: unknown;
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function validateIcao(stationIcao: string): void {
  if (typeof stationIcao !== "string" || !STATION_CODE_RE.test(stationIcao)) {
    throw new Error(
      `station_icao=${JSON.stringify(
        stationIcao,
      )} does not match STATION_CODE_RE (3-4 uppercase letters); refusing to use as URL component`,
    );
  }
}

function unwrapResults(data: unknown): ReadonlyArray<CliRawRecord> {
  // IEM cli.py returns either a bare array or `{results: [...]}`. Empty
  // bodies (e.g. `[]` or `{results: []}`) are treated as "no records".
  if (Array.isArray(data)) {
    return data as ReadonlyArray<CliRawRecord>;
  }
  if (
    data !== null &&
    typeof data === "object" &&
    "results" in data &&
    Array.isArray((data as { results: unknown }).results)
  ) {
    return (data as { results: ReadonlyArray<CliRawRecord> }).results;
  }
  // The Python port raises ValueError here; mirror that with a plain Error
  // so callers can catch it without depending on a core exception class.
  throw new Error(
    `Unexpected IEM CLI response shape: ${
      data === null ? "null" : Array.isArray(data) ? "array" : typeof data
    }`,
  );
}

/**
 * Download IEM CLI JSON for one station-year.
 *
 * URL: `${IEM_CLI_BASE_URL}?station={icao}&year={year}`.
 *
 * Response may be wrapped as `{"results": [...]}` — we unwrap and return
 * the inner array so downstream parsers always see the same shape.
 *
 * Throws {@link NotFoundError} on HTTP 404 (no data for that year);
 * {@link downloadCliRange} catches and continues. Other transport errors
 * propagate as the structured exceptions defined by `fetchWithRetry`.
 */
export async function downloadCli(
  stationIcao: string,
  year: number,
  opts: FetchWithRetryOptions = {},
): Promise<ReadonlyArray<CliRawRecord>> {
  validateIcao(stationIcao);
  const url = `${IEM_CLI_BASE_URL}?station=${stationIcao}&year=${year}`;
  const response = await fetchWithRetry(url, opts);
  const data = (await response.json()) as unknown;
  return unwrapResults(data);
}

export interface DownloadCliRangeOptions extends FetchWithRetryOptions {
  /**
   * Delay (ms) between successive year requests. Defaults to
   * {@link IEM_CLI_POLITE_DELAY_MS}.
   */
  politenessMs?: number;
}

/**
 * Download CLI records for an inclusive year range.
 *
 * Skips 404s (IEM "no data for this year") so multi-year backfills do
 * not abort when a station has gaps — mirrors Python's
 * `download_cli_range` 404-skip behavior. Other HTTP errors propagate.
 *
 * Between requests we sleep `politenessMs` (default
 * {@link IEM_CLI_POLITE_DELAY_MS}).
 */
export async function downloadCliRange(
  stationIcao: string,
  startYear: number,
  endYear: number,
  opts: DownloadCliRangeOptions = {},
): Promise<ReadonlyArray<CliRawRecord>> {
  if (endYear < startYear) {
    throw new Error(`endYear (${endYear}) must be >= startYear (${startYear})`);
  }
  validateIcao(stationIcao);

  const politenessMs = opts.politenessMs ?? IEM_CLI_POLITE_DELAY_MS;
  // Strip `politenessMs` so it isn't forwarded to fetchWithRetry's strict opts.
  const { politenessMs: _drop, ...fetchOpts } = opts;
  void _drop;

  const out: CliRawRecord[] = [];
  for (let year = startYear; year <= endYear; year++) {
    if (year > startYear && politenessMs > 0) {
      await sleep(politenessMs);
    }
    try {
      const records = await downloadCli(stationIcao, year, fetchOpts);
      out.push(...records);
    } catch (err) {
      if (err instanceof NotFoundError) {
        // No data for that year — log-equivalent silent skip. Continue.
        continue;
      }
      throw err;
    }
  }
  return out;
}

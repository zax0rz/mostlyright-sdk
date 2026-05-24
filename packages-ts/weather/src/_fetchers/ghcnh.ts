// NCEI GHCNh per-year PSV fetcher — single station-year and inclusive range.
//
// Byte-faithful TS port of Python
// `packages/weather/src/tradewinds/weather/_fetchers/ghcnh.py::download_ghcnh`
// and `download_ghcnh_range`, with the following deliberate adaptations:
//
//  1. No disk cache. Python writes per-station PSVs under
//     `dest_dir/{station_id}/GHCNh_{station}_{year}.psv`; the TS port
//     returns the PSV body in-memory via `{ stationId, year, psv }`.
//     The disk-cache layer lands in TS-W3 — out of scope here.
//  2. Station-id validation at the URL boundary uses an inline regex
//     (`^[A-Z0-9-]{1,32}$`) matching the path-traversal guard from Python
//     `_internal/_bounds.py::validate_ghcnh_id_for_path`. There's no path
//     here in TS-W2, so the regex check is the defense-in-depth measure.
//
// 404-as-no-data behavior in `downloadGhcnhRange` is byte-faithful — NCEI
// returns 404 for station-years that have no published data (typical for
// recent partial years or pre-1973 stations), and the range function
// silently skips them. Other HTTP errors propagate.
//
// CORS posture: NCEI GHCNh emits `Access-Control-Allow-Origin: *` per
// `.planning/research/TS-CORS-MATRIX.md` §GHCNh — OPEN. Works in browsers,
// Node 20+, Cloudflare Workers, Deno.

import { NotFoundError, fetchWithRetry } from "@tradewinds/core";
import type { FetchWithRetryOptions } from "@tradewinds/core";

/** NCEI GHCNh public archive base URL (no trailing slash). Mirrors Python `GHCNH_BASE_URL`. */
export const GHCNH_BASE_URL =
  "https://www.ncei.noaa.gov/oa/global-historical-climatology-network/hourly/access";

/**
 * Polite delay (ms) between consecutive NCEI HTTP requests in range mode.
 * Mirrors Python `NCEI_POLITE_DELAY = 1.0` (s). The delay fires AFTER each
 * successful response; 404s and network errors do NOT pay the tax.
 */
export const NCEI_POLITE_DELAY_MS = 1000;

/**
 * GHCNh station-id boundary regex. Permits the USAF-WBAN form
 * (`744860-94789`), the 11-char NCEI id (`USW00094789`), and short ICAO-like
 * tokens. Rejects path separators, NUL, and any whitespace before the value
 * ever reaches a URL path segment.
 */
const GHCNH_STATION_ID_RE = /^[A-Z0-9-]{1,32}$/;

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function validateStationId(stationId: string): void {
  if (typeof stationId !== "string" || !GHCNH_STATION_ID_RE.test(stationId)) {
    throw new Error(
      `station_id=${JSON.stringify(
        stationId,
      )} does not match GHCNH_STATION_ID_RE (uppercase alphanumeric + hyphen, 1-32 chars); refusing to use as URL component`,
    );
  }
}

function buildGhcnhUrl(stationId: string, year: number): string {
  return `${GHCNH_BASE_URL}/by-year/${year}/psv/GHCNh_${stationId}_${year}.psv`;
}

/** One downloaded station-year PSV. */
export interface GhcnhYearResult {
  readonly stationId: string;
  readonly year: number;
  /** Raw PSV body returned by NCEI (text/plain, pipe-delimited). */
  readonly psv: string;
}

export interface DownloadGhcnhRangeOptions extends FetchWithRetryOptions {
  /**
   * Delay (ms) between successive year requests. Defaults to
   * {@link NCEI_POLITE_DELAY_MS}. Set to `0` in unit tests.
   */
  politenessMs?: number;
}

/**
 * Download a NOAA GHCNh PSV for one station-year.
 *
 * URL: `${GHCNH_BASE_URL}/by-year/{year}/psv/GHCNh_{stationId}_{year}.psv`.
 *
 * @throws {NotFoundError} when NCEI returns 404 (no data for this station-year).
 *         Callers that want 404-as-skip behavior should use {@link downloadGhcnhRange}.
 * @throws If `stationId` does not match `GHCNH_STATION_ID_RE`.
 * @throws Whatever `fetchWithRetry` propagates on persistent network/HTTP errors.
 */
export async function downloadGhcnh(
  stationId: string,
  year: number,
  opts: FetchWithRetryOptions = {},
): Promise<GhcnhYearResult> {
  validateStationId(stationId);
  const url = buildGhcnhUrl(stationId, year);
  const response = await fetchWithRetry(url, opts);
  const psv = await response.text();
  return { stationId, year, psv };
}

/**
 * Download GHCNh PSVs for an inclusive year range.
 *
 * Iterates `[startYear, endYear]`. Years that return 404 (no data for that
 * station-year) are silently skipped — they do NOT appear in the output
 * array. Other HTTP errors propagate.
 *
 * `endYear < startYear` returns `[]` with zero HTTP requests.
 *
 * Polite delay fires AFTER each successful response only.
 */
export async function downloadGhcnhRange(
  stationId: string,
  startYear: number,
  endYear: number,
  opts: DownloadGhcnhRangeOptions = {},
): Promise<ReadonlyArray<GhcnhYearResult>> {
  validateStationId(stationId);

  if (endYear < startYear) {
    return [];
  }

  const politenessMs = opts.politenessMs ?? NCEI_POLITE_DELAY_MS;
  const { politenessMs: _pmDrop, ...fetchOpts } = opts;
  void _pmDrop;

  const out: GhcnhYearResult[] = [];
  for (let year = startYear; year <= endYear; year++) {
    let result: GhcnhYearResult;
    try {
      result = await downloadGhcnh(stationId, year, fetchOpts);
    } catch (err) {
      if (err instanceof NotFoundError) {
        // 404 → silent skip. Mirrors Python L160-166 (log + continue).
        continue;
      }
      throw err;
    }
    out.push(result);
    if (politenessMs > 0) {
      await sleep(politenessMs);
    }
  }
  return out;
}

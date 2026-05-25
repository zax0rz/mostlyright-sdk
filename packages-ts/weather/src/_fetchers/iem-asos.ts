// IEM ASOS historical METAR fetcher — yearly-chunked CSV downloads.
//
// Byte-faithful TS port of Python
// `packages/weather/src/mostlyright/weather/_fetchers/iem_asos.py::download_iem_asos`,
// with the following deliberate adaptations:
//
//  1. No disk cache. Python writes per-station CSVs under
//     `dest_dir/{station}/iem_*.csv`; the TS port returns the CSV body
//     in-memory via `{ chunkStart, chunkEnd, csv }`. The disk-cache layer
//     (PERF-02 partial-namespace + cache-poisoning paths) lands in TS-W3 —
//     it's intentionally out of scope here. Drop ALL filename / `skip_cache`
//     / `today_utc` partial-namespace logic.
//  2. Station validation at the URL boundary uses an inline regex
//     (`^[A-Z]{3,4}$`) matching `iem-cli.ts`'s `validateIcao` pattern. The
//     Python `validate_icao_for_path` from `_internal/_bounds.py` is a
//     path-traversal guard — there's no path here in TS-W2, so the regex
//     check is the equivalent defense-in-depth measure.
//
// URL shape, start-normalization (caller's `start` clamped to
// `date(start.year, 1, 1)` for cache idempotence under per-month callers),
// reversed-range short-circuit (`start > end → []`), report_type guard
// ({3, 4}), and 1-sec polite delay are byte-faithful.
//
// CORS posture: OPEN — IEM emits `Access-Control-Allow-Origin: *` per
// `.planning/research/TS-CORS-MATRIX.md` §IEM-ASOS. Works in browsers,
// Node 20+, Cloudflare Workers, Deno.

import { fetchWithRetry } from "@mostlyrightmd/core";
import type { FetchWithRetryOptions } from "@mostlyrightmd/core";

import { type IsoDate, yearlyChunksExclusiveEnd } from "./_iem_chunks.js";

/** IEM ASOS request endpoint. Mirrors Python `IEM_BASE_URL`. */
export const IEM_BASE_URL = "https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py";

/**
 * Polite delay (ms) between consecutive IEM HTTP requests. Mirrors Python
 * `IEM_POLITE_DELAY = 1.0` (s) — IEM runs on a university server and
 * documents a 1-sec/IP throttle (see .planning/research/SOURCE-LIMITS.md).
 */
export const IEM_POLITE_DELAY_MS = 1000;

/**
 * Station code regex (3-4 uppercase letters). Mirrors the inline pattern
 * used by `iem-cli.ts::validateIcao` and the shared `STATION_CODE_RE` from
 * `@mostlyrightmd/core/internal/bounds`. Inlined here so the fetcher does not
 * transitively pull in the validators barrel — keeps the per-fetcher
 * dep graph narrow per the TS-W1 review pattern.
 */
const STATION_CODE_RE = /^[A-Z]{3,4}$/;

/** Permitted IEM report_type values: 3 = METAR, 4 = SPECI. */
const VALID_REPORT_TYPES = new Set<number>([3, 4]);

/**
 * One downloaded yearly chunk. The CSV body is forwarded verbatim from
 * the upstream response so the parser can run a downstream pass over it.
 */
export interface IemChunkResult {
  /** First day of this chunk's range (caller's start for chunk 0; Jan 1 for subsequent). */
  readonly chunkStart: IsoDate;
  /** EXCLUSIVE end of this chunk's range — Jan 1 of the following calendar year. */
  readonly chunkEnd: IsoDate;
  /** Raw CSV body returned by IEM (text/plain, comma-separated). */
  readonly csv: string;
}

export interface DownloadIemAsosOptions extends FetchWithRetryOptions {
  /** `3` (METAR, default) or `4` (SPECI). */
  reportType?: 3 | 4;
  /**
   * Delay (ms) between successive chunk requests. Defaults to
   * {@link IEM_POLITE_DELAY_MS}. Set to `0` in unit tests.
   */
  politenessMs?: number;
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function validateIcao(stationCode: string): void {
  if (typeof stationCode !== "string" || !STATION_CODE_RE.test(stationCode)) {
    throw new Error(
      `station_code=${JSON.stringify(
        stationCode,
      )} does not match STATION_CODE_RE (3-4 uppercase letters); refusing to use as URL component`,
    );
  }
}

/**
 * Build the IEM ASOS download URL for one (chunk, report_type) request.
 *
 * Param shape and ordering are byte-faithful to Python `_build_iem_url`:
 *   station, data, tz, format, latlon, elev, missing, trace, direct,
 *   report_type, year1, month1, day1, year2, month2, day2.
 *
 * Month/day are emitted WITHOUT zero-padding (Python uses bare `{start.month}`,
 * not `{start.month:02d}`) — preserve byte-equivalence on URL snapshots.
 *
 * `end` is the EXCLUSIVE end (already adjusted by the chunker to Jan 1 of
 * the following calendar year).
 */
export function buildIemUrl(
  stationCode: string,
  start: IsoDate,
  end: IsoDate,
  reportType: number,
): string {
  // Parse ISO strings into ints (no Date — avoids local-TZ silent shifts).
  const [sy, sm, sd] = splitIso(start);
  const [ey, em, ed] = splitIso(end);
  const params = `station=${stationCode}&data=all&tz=Etc/UTC&format=comma&latlon=no&elev=no&missing=M&trace=T&direct=no&report_type=${reportType}&year1=${sy}&month1=${sm}&day1=${sd}&year2=${ey}&month2=${em}&day2=${ed}`;
  return `${IEM_BASE_URL}?${params}`;
}

function splitIso(iso: IsoDate): [number, number, number] {
  // The chunker has already validated; we just split.
  const parts = iso.split("-");
  // Length-3 guaranteed if the chunker emitted this; defense in depth.
  if (parts.length !== 3) {
    throw new Error(`Invalid ISO date passed to buildIemUrl: ${JSON.stringify(iso)}`);
  }
  return [
    Number.parseInt(parts[0] as string, 10),
    Number.parseInt(parts[1] as string, 10),
    Number.parseInt(parts[2] as string, 10),
  ];
}

/**
 * Download yearly chunks of IEM ASOS data for one station, returning the
 * raw CSV bodies in chunker-natural order.
 *
 * The caller's inclusive `[start, end]` is normalized internally to
 * `[date(start.year, 1, 1), end]` and split into per-calendar-year
 * EXCLUSIVE-end chunks via {@link yearlyChunksExclusiveEnd}. Each chunk
 * fires one HTTP request to the IEM ASOS endpoint, with a polite delay
 * between successful responses (default {@link IEM_POLITE_DELAY_MS}).
 *
 * Errors propagate from `fetchWithRetry` — 4xx/5xx after retry exhaustion
 * are NOT swallowed (the IEM ASOS path is parity-critical; silent failure
 * would manifest as missing observation rows downstream).
 *
 * @throws If `reportType` is not `3` (METAR) or `4` (SPECI).
 * @throws If `stationCode` does not match `^[A-Z]{3,4}$` (path-traversal /
 *         URL-injection defense).
 * @throws Whatever `fetchWithRetry` propagates on persistent network/HTTP
 *         errors.
 */
export async function downloadIemAsos(
  stationCode: string,
  start: IsoDate,
  end: IsoDate,
  opts: DownloadIemAsosOptions = {},
): Promise<ReadonlyArray<IemChunkResult>> {
  const reportType = opts.reportType ?? 3;
  if (!VALID_REPORT_TYPES.has(reportType)) {
    throw new Error(`report_type must be 3 (METAR) or 4 (SPECI), got ${reportType}`);
  }
  // Defense-in-depth: validate at the URL boundary BEFORE any HTTP.
  validateIcao(stationCode);

  // Reversed-range guard. Mirror Python L201-202: the chunker honors
  // `start > end → []`, but defensive short-circuit here avoids ever
  // computing the normalized year boundary for a malformed call.
  if (start > end) {
    return [];
  }

  // Tradewinds-specific normalization: clamp caller's `start` to Jan 1 of
  // its year so per-month callers share a yearly cache key (parity-faithful
  // with Python's `normalized_start = date(start.year, 1, 1)`). Mirrored in
  // TS so the URL shape (and the future TS-W3 cache key) stays byte-stable
  // with Python on the same range.
  const normalizedStart: IsoDate = `${start.slice(0, 4)}-01-01`;
  const chunks = yearlyChunksExclusiveEnd(normalizedStart, end);

  const politenessMs = opts.politenessMs ?? IEM_POLITE_DELAY_MS;
  // Strip fetcher-specific opts from the bag forwarded to fetchWithRetry.
  const { reportType: _rtDrop, politenessMs: _pmDrop, ...fetchOpts } = opts;
  void _rtDrop;
  void _pmDrop;

  const out: IemChunkResult[] = [];
  for (const [chunkStart, chunkEnd] of chunks) {
    const url = buildIemUrl(stationCode, chunkStart, chunkEnd, reportType);
    const response = await fetchWithRetry(url, fetchOpts);
    const csv = await response.text();
    out.push({ chunkStart, chunkEnd, csv });
    // Polite delay AFTER each successful round-trip (mirror Python L224
    // which sleeps unconditionally). Skipping the trailing sleep on the
    // last chunk would be a micro-optimization not present in Python.
    if (politenessMs > 0) {
      await sleep(politenessMs);
    }
  }
  return out;
}

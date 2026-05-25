// AWC METAR HTTP fetcher — live observations from aviationweather.gov.
//
// Ported byte-faithfully from
// `packages/weather/src/mostlyright/weather/_fetchers/awc.py::fetch_awc_metars`.
//
// =============================================================================
// CORS posture: NONE (per .planning/research/TS-CORS-MATRIX.md)
// =============================================================================
// AWC's `aviationweather.gov` does NOT emit any `Access-Control-Allow-*` headers.
// This means a pure browser-app (no extension) cannot call this endpoint via
// `fetch()` directly — the browser blocks the response.
//
// Workarounds:
//   1. Chrome extension (MV3 service worker): declare host permissions in
//      manifest.json — `"host_permissions": ["https://aviationweather.gov/*"]`.
//      MV3 service workers bypass CORS for hosts they have permission for.
//   2. CORS proxy: deploy a thin Cloudflare Worker (or similar) that fronts
//      this endpoint and emits `Access-Control-Allow-Origin: *`. Then point
//      this fetcher at the proxy URL via the `urlOverride` option (TODO: when
//      added in a future wave).
//   3. Node.js / Deno / Bun / Cloudflare Worker runtime: no CORS — works
//      out of the box.
//
// See `.planning/research/TS-CORS-MATRIX.md` §AWC and `docs/chrome-extension-integration.md`
// for the canonical workaround guidance.
// =============================================================================
//
// The AWC live endpoint serves only recent observations — at most ~168 hours
// (7 days). For historical multi-day fetches use IEM ASOS (lands in TS-W4).
//
// Return contract: ReadonlyArray<AwcMetarRaw>. Empty array on 4xx, timeout, or
// exhausted retries — NEVER throws (matches Python `fetch_awc_metars` so the
// caller can degrade gracefully when AWC is down).

import { type FetchWithRetryOptions, TherminalError, fetchWithRetry } from "@mostlyrightmd/core";

/** Canonical AWC METAR endpoint. */
export const AWC_METAR_URL = "https://aviationweather.gov/api/data/metar";

/**
 * AWC live serves at most ~168 hours (7 days). Beyond that the endpoint
 * either silently truncates or returns an empty list — use IEM ASOS for
 * history.
 */
export const AWC_MAX_HOURS = 168;

/**
 * Raw AWC METAR record as returned by the public JSON endpoint.
 *
 * Fields are documented loosely — the upstream payload is not formally
 * schema-versioned. We pass-through optional fields to the parser
 * (`_parsers/awc.ts`) which validates them against bounds.
 */
export interface AwcMetarRaw {
  /** Four-letter ICAO identifier (e.g. "KNYC"). REQUIRED. */
  icaoId: string;
  /** Observation time as Unix epoch seconds. REQUIRED. */
  obsTime: number;
  metarType?: "METAR" | "SPECI" | string;
  /** Wind direction in degrees, or "VRB" for variable. */
  wdir?: number | "VRB" | string;
  wspd?: number | null;
  wgst?: number | null;
  /** Altimeter setting in hPa. */
  altim?: number | null;
  /** Sea-level pressure in mb/hPa. */
  slp?: number | null;
  /** Temperature in Celsius. */
  temp?: number | null;
  /** Dewpoint in Celsius. */
  dewp?: number | null;
  /** Visibility — may be number, "10+", "1/2", "2 1/4", "M1/4", etc. */
  visib?: string | number | null;
  clouds?: ReadonlyArray<{ cover?: string; base?: number | null }>;
  /** Raw METAR text — includes remarks. */
  rawOb?: string | null;
  /** Weather codes (e.g. "RA BR"). */
  wxString?: string | null;
  /** Precipitation past hour (inches). "T" = trace. */
  precip?: number | "T" | string | null;
  /** QC bitmask field. */
  qcField?: number | null;
}

export interface FetchAwcOptions extends FetchWithRetryOptions {
  /** Lookback window in hours. Default 168 (max). Values above `AWC_MAX_HOURS` are clamped. */
  hours?: number;
}

/**
 * Fetch recent METARs from AWC for one or more ICAO stations.
 *
 * Returns the raw JSON array as-is (typed as `AwcMetarRaw[]`); compose with
 * `awcToObservation` from `../_parsers/awc.ts` to map each entry to the
 * observation row schema.
 *
 * Behaviour mirrors Python `fetch_awc_metars`:
 *  - empty `stationIcaos` → return `[]` immediately, no HTTP issued
 *  - 4xx after retry exhaustion → `[]`
 *  - 5xx / network errors after retry budget → `[]`
 *  - non-array JSON body → `[]`
 *  - NEVER throws (callers want graceful degradation)
 */
export async function fetchAwcMetars(
  stationIcaos: ReadonlyArray<string>,
  opts: FetchAwcOptions = {},
): Promise<ReadonlyArray<AwcMetarRaw>> {
  if (stationIcaos.length === 0) {
    return [];
  }

  const hours = Math.min(opts.hours ?? AWC_MAX_HOURS, AWC_MAX_HOURS);
  // Encode each component (defensive — caller should already have validated
  // ICAOs via station registry, but the URL shape must be safe regardless).
  const idsCsv = stationIcaos.map((s) => encodeURIComponent(s)).join(",");
  const url = `${AWC_METAR_URL}?ids=${idsCsv}&format=json&taf=false&hours=${hours}`;

  // Strip `hours` from the options forwarded to fetchWithRetry so the type
  // is exactly `FetchWithRetryOptions`. Note: `hours` is consumed above.
  const { hours: _consumed, ...retryOpts } = opts;
  void _consumed;

  let response: Response;
  try {
    response = await fetchWithRetry(url, retryOpts);
  } catch (err) {
    // Any TherminalError (404, 400, 401, 403, 429-after-exhaustion, 5xx-after-
    // exhaustion) OR raw network error → return [] (mirror Python). This is
    // the "graceful degradation" contract; orchestration layer decides whether
    // to surface a SourceUnavailableError instead.
    if (err instanceof TherminalError) {
      return [];
    }
    // Re-raise abort errors so callers that pass AbortSignals can cancel.
    if (err instanceof DOMException && (err.name === "AbortError" || err.name === "TimeoutError")) {
      // For caller-initiated aborts we re-throw; otherwise the timeout was
      // composed in by fetchWithRetry and would already have been retried.
      if (opts.signal?.aborted) {
        throw err;
      }
      return [];
    }
    return [];
  }

  let data: unknown;
  try {
    data = await response.json();
  } catch {
    return [];
  }

  if (!Array.isArray(data)) {
    return [];
  }

  return data as ReadonlyArray<AwcMetarRaw>;
}

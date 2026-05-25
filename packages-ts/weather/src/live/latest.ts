// Phase 11 — one-shot `latest()` fetch.
//
// Mirrors Python `mostlyright.live.latest`. Single-source poll: hit AWC or
// IEM ONCE, parse the response, return the most-recent observation row
// with its live source identity tag. No fusion, no cache, no QC.

import { NoLiveDataError } from "@mostlyrightmd/core";

import { fetchLatest, normalizeStation, pickMostRecent } from "./_fetch.js";
import { type LiveSource, sourceTag, validateSource } from "./sources.js";
import type { LiveObservation } from "./types.js";

export interface LatestOptions {
  /**
   * Live source to poll. `"awc"` (default, fastest) or `"iem"` (~10-min
   * delay; useful when AWC is down). Case-insensitive.
   */
  readonly source?: LiveSource | string | null;
}

/**
 * Return the most-recent observation row for `station` from a SINGLE source.
 *
 * Same fetch path as {@link stream}, but returns once instead of looping.
 * Use this for cron-style polling where you want one fresh observation per
 * invocation.
 *
 * @param station - ICAO (`"KNYC"`) or 3-letter US ID (`"NYC"`). Case-insensitive.
 * @param opts - Optional `{ source }`.
 *
 * @throws `Error` when `opts.source` is unknown.
 * @throws {@link NoLiveDataError} when the upstream returned no observations
 *   for the station — payload carries the resolved `station` and live
 *   `source` tag for branching.
 */
export async function latest(station: string, opts: LatestOptions = {}): Promise<LiveObservation> {
  const src: LiveSource = validateSource(opts.source ?? undefined);
  const rows = await fetchLatest(station, src);
  const picked = pickMostRecent(rows);
  if (picked === null) {
    throw new NoLiveDataError(
      `no live data for station=${JSON.stringify(station)} source=${JSON.stringify(src)}`,
      {
        station: normalizeStation(station),
        source: sourceTag(src),
      },
    );
  }
  return picked;
}

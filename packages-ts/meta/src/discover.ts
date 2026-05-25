// Phase 10 — discover({city}) ergonomic surface (TS port of
// packages/core/src/tradewinds/discover.py).
//
// Pre-research lookup. Shows quants which station settles which issuer's
// market for a given city so they can pick the right selector before
// invoking research(). Especially useful for cross-issuer cities like NYC
// where Kalshi settles against KNYC and Polymarket against KLGA.

import { annotateSettlesFor, resolveCity } from "./compose.js";

/** One row per station in the resolved city neighborhood. */
export interface DiscoverRow {
  /** Echo of the input city. */
  readonly city: string;
  /** 4-char K-prefix ICAO. */
  readonly station: string;
  /**
   * `"<issuer>:<ticker>"` markers that resolve against this station.
   * Empty array = denylist backstop surfaced for explicit awareness.
   */
  readonly settlesFor: ReadonlyArray<string>;
}

/** Envelope mirrors the Python `df.attrs` pattern. */
export interface DiscoverResult {
  readonly rows: ReadonlyArray<DiscoverRow>;
  readonly city: string;
  readonly source: "discover";
}

/**
 * Return per-station discovery table for `city`.
 *
 * Each row shows one settlement station + the issuer:ticker markers that
 * resolve against it. Stations in the per-city Polymarket denylist also
 * appear with empty `settlesFor` so quants see the full neighborhood
 * before deciding whether to use `stationOverride`.
 *
 * @example
 *   const result = discover({ city: "NYC" });
 *   // rows include {station: "KNYC", settlesFor: ["kalshi:NYC"]},
 *   //              {station: "KLGA", settlesFor: ["polymarket:nyc"]},
 *   //              {station: "KJFK", settlesFor: []},  // denylist
 *   //              {station: "KEWR", settlesFor: []}.
 */
export function discover(args: { readonly city: string }): DiscoverResult {
  if (typeof args !== "object" || args === null) {
    throw new TypeError(`discover(): args must be an object; got ${typeof args}`);
  }
  const stations = resolveCity(args.city);
  const rows: DiscoverRow[] = stations.map((station) => ({
    city: args.city,
    station,
    settlesFor: annotateSettlesFor(station, args.city),
  }));
  return Object.freeze({
    rows: Object.freeze(rows),
    city: args.city,
    source: "discover" as const,
  });
}

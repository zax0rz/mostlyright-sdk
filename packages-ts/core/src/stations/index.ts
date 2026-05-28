// Venue-agnostic station catalog (Phase 22) — the TS mirror of Python's
// `mostlyright.stations`.
//
// A station is a physical fact; the prediction-market venue that settles on it
// is metadata. The `venues` tag follows each issuer's ACTUAL settlement map,
// not country — Kalshi and Polymarket settle several shared cities against
// different stations (NYC: KNYC vs KLGA; Chicago: KMDW vs KORD), so
// `filterByVenue("kalshi")` is the Kalshi settlement universe, NOT "every US
// station". Markets derives its settlement universe by filtering here; bare-data
// consumers ignore venues entirely.
//
// `venues` is `readonly string[]` (not a Set) on each record to keep the data
// tree-shakeable and the gzipped bundle small.

import {
  STATIONS,
  STATION_BY_CODE,
  STATION_BY_ICAO,
  type StationInfo,
} from "../data/generated/stations.js";

// The codegen record IS the public station shape — one source of truth,
// re-exported (not duplicated), mirroring Python's `Station = StationInfo`.
export type Station = StationInfo;

/**
 * Read-only view over the station registry with venue/country filters.
 *
 * Lookups accept either the registry code (3-letter NWS code for US stations,
 * ICAO for international) or the 4-letter ICAO directly, so `get("NYC")`,
 * `get("KNYC")`, and `get("EGLL")` all resolve.
 */
export class StationCatalog {
  private readonly stations: ReadonlyArray<Station>;
  private readonly byCode: ReadonlyMap<string, Station>;
  private readonly byIcao: ReadonlyMap<string, Station>;

  constructor(stations: ReadonlyArray<Station> = STATIONS) {
    this.stations = stations;
    if (stations === STATIONS) {
      // Reuse the codegen maps for the default catalog — no rebuild.
      this.byCode = STATION_BY_CODE;
      this.byIcao = STATION_BY_ICAO;
    } else {
      const byCode = new Map<string, Station>();
      const byIcao = new Map<string, Station>();
      for (const s of stations) {
        if (s.code !== null) byCode.set(s.code, s);
        byIcao.set(s.icao, s);
      }
      this.byCode = byCode;
      this.byIcao = byIcao;
    }
  }

  /**
   * Return the station for `code` (registry code or ICAO).
   * @throws if no station matches.
   */
  get(code: string): Station {
    const station = this.byCode.get(code) ?? this.byIcao.get(code);
    if (station === undefined) {
      throw new Error(
        `Unknown station ${JSON.stringify(code)}. Expected a registry code (e.g. "NYC", "EGLL") or a 4-letter ICAO (e.g. "KNYC").`,
      );
    }
    return station;
  }

  /** Stations tagged with `venue` (e.g. "kalshi"), sorted by ICAO. */
  filterByVenue(venue: string): Station[] {
    return this.stations
      .filter((s) => s.venues.includes(venue))
      .sort((a, b) => a.icao.localeCompare(b.icao));
  }

  /** Stations whose ISO 3166-1 alpha-2 `country` matches, sorted by ICAO. */
  filterByCountry(country: string): Station[] {
    return this.stations
      .filter((s) => s.country === country)
      .sort((a, b) => a.icao.localeCompare(b.icao));
  }

  /** Union of all venue tags present in the catalog. */
  venues(): ReadonlySet<string> {
    const out = new Set<string>();
    for (const s of this.stations) {
      for (const v of s.venues) out.add(v);
    }
    return out;
  }

  /** True iff `code` resolves to a station (by registry code or ICAO). */
  has(code: string): boolean {
    return this.byCode.has(code) || this.byIcao.has(code);
  }

  get size(): number {
    return this.stations.length;
  }

  [Symbol.iterator](): Iterator<Station> {
    return this.stations[Symbol.iterator]();
  }
}

/** Process-wide default catalog over the codegen station registry. */
export const CATALOG = new StationCatalog();

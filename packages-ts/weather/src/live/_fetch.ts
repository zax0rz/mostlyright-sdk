// Phase 11 — per-source live fetch dispatch (internal).
//
// Wraps the existing AWC + IEM fetchers and re-tags each parsed row with
// the live-channel source identity (`"awc.live"` / `"iem.live"`). Errors
// inside the fetcher are NOT caught here — callers (`stream`, `latest`)
// have different error semantics and handle their own try/catch.

import type { Observation } from "../_parsers/awc.js";
import { awcToObservation } from "../_parsers/awc.js";
import { fetchAwcMetars } from "../_fetchers/awc.js";

import { type LiveSource, sourceTag } from "./sources.js";
import type { LiveObservation } from "./types.js";

/**
 * Accept "KNYC" or "NYC" — emit the 4-letter ICAO form for fetchers.
 *
 * Defensive: trim + uppercase + add leading `K` for the 3-letter US ID
 * shortform. AWC accepts only ICAO; IEM accepts both, but normalizing here
 * keeps cache keys + log messages stable.
 */
export function normalizeStation(station: string): string {
  const s = station.trim().toUpperCase();
  if (s.length === 3) return `K${s}`;
  return s;
}

/** Re-tag a parsed `Observation` row with the live-channel source. */
function asLiveObservation(obs: Observation, tag: LiveObservation["source"]): LiveObservation {
  // Spread + override — the canonical Observation is `readonly`, so we
  // produce a new object rather than mutating.
  return { ...obs, source: tag };
}

/** Poll AWC once for the given station and return parsed observation rows. */
export async function fetchAwcLatest(station: string): Promise<LiveObservation[]> {
  const icao = normalizeStation(station);
  const raw = await fetchAwcMetars([icao], { hours: 1 });
  const tag = sourceTag("awc");
  const rows: LiveObservation[] = [];
  for (const m of raw) {
    const obs = awcToObservation(m);
    if (obs !== null) {
      rows.push(asLiveObservation(obs, tag));
    }
  }
  return rows;
}

/** Today's UTC midnight as an `YYYY-MM-DD` ISO date string. */
function todayUtcIso(): string {
  const d = new Date();
  const y = d.getUTCFullYear();
  const m = String(d.getUTCMonth() + 1).padStart(2, "0");
  const day = String(d.getUTCDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

/** Add one day to a `YYYY-MM-DD` UTC ISO string. */
function nextDayIso(iso: string): string {
  const [y, m, d] = iso.split("-").map(Number);
  // biome-ignore lint/style/noNonNullAssertion: split-by-`-` on a YYYY-MM-DD literal always yields 3 parts
  const dt = new Date(Date.UTC(y!, m! - 1, d!));
  dt.setUTCDate(dt.getUTCDate() + 1);
  const ny = dt.getUTCFullYear();
  const nm = String(dt.getUTCMonth() + 1).padStart(2, "0");
  const nd = String(dt.getUTCDate()).padStart(2, "0");
  return `${ny}-${nm}-${nd}`;
}

/**
 * Poll IEM once for the given station and return parsed observation rows.
 *
 * Uses a direct one-day URL via `buildIemUrl` + `fetchWithRetry` rather than
 * `downloadIemAsos` because the TS `downloadIemAsos` normalizes the caller's
 * `start` to `${start.slice(0, 4)}-01-01` for cache-key stability — that's
 * the right call for `research()` but wrong for a live tick (would download
 * the full calendar year on every poll). Module import is dynamic so the
 * browser AWC-only bundle doesn't pull the IEM parser tree.
 */
export async function fetchIemLatest(station: string): Promise<LiveObservation[]> {
  const [{ fetchWithRetry }, { buildIemUrl }, { parseIemCsv }] = await Promise.all([
    import("@tradewinds/core"),
    import("../_fetchers/iem-asos.js"),
    import("../_parsers/iem.js"),
  ]);
  const icao = normalizeStation(station);
  const stationCode = icao.length === 4 && icao.startsWith("K") ? icao.slice(1) : icao;
  const startIso = todayUtcIso();
  const endIso = nextDayIso(startIso);
  const url = buildIemUrl(stationCode, startIso, endIso, 3);
  const response = await fetchWithRetry(url);
  const csv = await response.text();
  const obs = parseIemCsv(csv, { observationTypeOverride: "METAR" });
  const tag = sourceTag("iem");
  return obs.map((row) => asLiveObservation(row, tag));
}

/** Dispatch to the per-source fetch. */
export async function fetchLatest(station: string, source: LiveSource): Promise<LiveObservation[]> {
  switch (source) {
    case "awc":
      return fetchAwcLatest(station);
    case "iem":
      return fetchIemLatest(station);
  }
}

/**
 * Pick the row with the largest `observed_at`; SPECI > METAR at ties.
 *
 * `observed_at` is ISO 8601 ending in `Z` — lexicographic sort matches
 * chronological. Ties on `observed_at` resolve to SPECI (special report)
 * over METAR (routine) since SPECI is issued for a significant change.
 */
export function pickMostRecent(rows: ReadonlyArray<LiveObservation>): LiveObservation | null {
  if (rows.length === 0) return null;
  let best = rows[0]!;
  for (let i = 1; i < rows.length; i++) {
    const cur = rows[i]!;
    if (cur.observed_at > best.observed_at) {
      best = cur;
    } else if (
      cur.observed_at === best.observed_at &&
      cur.observation_type === "SPECI" &&
      best.observation_type !== "SPECI"
    ) {
      best = cur;
    }
  }
  return best;
}

// TS-W5 Wave 2 — Tier 0/1/2/3 resolver chain + city catalog.
//
// Mirrors Python `_per_event_station.resolve_station_for_event` + the
// `_derive_city` helper. The resolver chain:
//
//   - Tier 0 (deferred check): if the resolved ICAO is in DEFERRED_STATIONS
//     (Taipei RCTP, Hong Kong VHHH) AND the market is low-extreme, raise
//     DeferredMarketError. The Python contract defers only HK-LOW + Taipei
//     because v0.2 will land CWA + HKO clients.
//   - Tier 1: explicit `event.city` field if a known city.
//   - Tier 2: derive city from slug + title + tags (lowercase substring
//     match against the catalog, longest-key-first so multi-token cities
//     like "london_gatwick" resolve before "london").
//   - Tier 3: bail with KeyError — discover() drops the row, settle()
//     surfaces PolymarketSettlementError.

import { DeferredMarketError } from "@tradewinds/core";

import { POLYMARKET_CITY_STATIONS } from "../data/generated/polymarket-city-stations.js";
import type { PolymarketEventRaw } from "./client.js";
import { PolymarketSettlementError } from "./errors.js";
import { DEFERRED_STATIONS } from "./types.js";

/**
 * Detect whether the market resolves on the daily HIGH or LOW from
 * keywords in the event title/slug/name. Distinct from the station-level
 * measure: many cities have one airport for both, but the market still
 * resolves on tmax XOR tmin.
 */
export function detectMarketMeasure(event: PolymarketEventRaw): "high" | "low" | "default" {
  const text = [event.title, event.slug, (event as { name?: string }).name]
    .filter((v): v is string => typeof v === "string")
    .join(" ")
    .toLowerCase();
  const hasHigh = /\b(highest|high|hottest|warmest|max(?:imum)?)\b/.test(text);
  const hasLow = /\b(lowest|low|coldest|coolest|min(?:imum)?)\b/.test(text);
  if (hasLow && !hasHigh) return "low";
  if (hasHigh && !hasLow) return "high";
  return "default";
}

const CITY_KEYS_SORTED: ReadonlyArray<string> = Object.freeze(
  Object.keys(POLYMARKET_CITY_STATIONS).sort((a, b) => b.length - a.length),
);

/**
 * Derive a city key from slug + title + tags. Lowercase substring match
 * against the catalog; longest-first so multi-token cities outrank prefixes.
 * Returns null when no match — caller decides whether to drop or surface.
 */
export function deriveCity(event: PolymarketEventRaw): string | null {
  const parts: string[] = [];
  const slug = typeof event.slug === "string" ? event.slug.toLowerCase() : "";
  const title = typeof event.title === "string" ? event.title.toLowerCase() : "";
  parts.push(slug, title);
  const tags = event.tags;
  if (Array.isArray(tags)) {
    for (const tag of tags) {
      if (typeof tag === "string") parts.push(tag.toLowerCase());
      else if (tag !== null && typeof tag === "object") {
        const label = tag.label ?? tag.slug;
        if (typeof label === "string") parts.push(label.toLowerCase());
      }
    }
  }
  // Codex iter-5 P2: require word-boundary matches so cities don't false-
  // positive inside ordinary words (e.g. "comparison" → "paris"). Build a
  // regex per needle with non-word-character boundaries on both sides.
  // Word characters are ASCII letters/digits + underscore; we treat "-",
  // " ", "/", "(", ")" etc. as boundaries (covers the slug/title/tag forms
  // we ingest).
  const haystack = ` ${parts.join(" ")} `;
  for (const key of CITY_KEYS_SORTED) {
    const needles = [key, key.replace(/_/g, "-"), key.replace(/_/g, " ")];
    for (const n of needles) {
      if (n.length === 0) continue;
      // Escape any regex metacharacters in `n` (city keys are alphanum +
      // underscore + hyphen + space; the latter two need no escaping but
      // be defensive).
      const escaped = n.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
      const re = new RegExp(`(^|[^A-Za-z0-9])${escaped}(?=[^A-Za-z0-9]|$)`);
      if (re.test(haystack)) return key;
    }
  }
  return null;
}

// Phase 8 — Tier 1.5 URL extraction (POLY-US-03).
// Wunderground PWS URL pattern; captures K-prefix ICAO. US-only by design —
// international Wunderground URLs use lat/lng or alternate IDs and fall back
// to Tier 2 city-derive.
const WUNDERGROUND_ICAO_RE = /https?:\/\/(?:www\.)?wunderground\.com\/[^\s<>"')]*?\b(K[A-Z]{3})\b/i;

/**
 * Extract the first ICAO from a Wunderground URL in `text`.
 *
 * Tier 1.5 of the resolver chain — runs between explicit `event.city`
 * and slug-derive. When a Polymarket event embeds a Wunderground URL
 * pointing at a specific PWS station, the URL IS the source of truth;
 * no catalog lookup needed.
 *
 * Returns uppercase ICAO (4 chars, leading K) if a Wunderground URL with
 * an ICAO is found; null otherwise. Tolerates null/undefined/empty/non-
 * string for caller convenience.
 */
export function extractIcaoFromResolutionSource(text: string | null | undefined): string | null {
  if (typeof text !== "string" || text.length === 0) return null;
  const m = text.match(WUNDERGROUND_ICAO_RE);
  if (m === null || m[1] === undefined) return null;
  return m[1].toUpperCase();
}

// Reverse-lookup the canonical city for a given ICAO. Linear scan over the
// small catalog (≤60 entries) — no perf concern. Returns null when the ICAO
// is not represented in any catalog entry (e.g. a private PWS).
function findCityForIcao(icao: string): string | null {
  for (const [city, entry] of Object.entries(POLYMARKET_CITY_STATIONS)) {
    if (entry === undefined) continue;
    if (entry.default === icao || entry.high === icao || entry.low === icao) {
      return city;
    }
  }
  return null;
}

/**
 * Resolve an event to `{icao, stationMeasure}` using the city catalog.
 *
 * Returns null when no city matches (caller drops the event).
 * Raises DeferredMarketError when the resolution would route to a v0.2
 * source (Taipei RCTP, Hong Kong VHHH for the low-extreme market).
 */
export function resolveStationForEvent(
  event: PolymarketEventRaw,
  marketMeasure: "high" | "low" | "default",
): { city: string; icao: string; stationMeasure: "high" | "low" | "default" } | null {
  // Tier 1: explicit city field — useful for tests / synthetic events.
  let cityKey: string | null = null;
  const explicit = (event as { city?: unknown }).city;
  if (typeof explicit === "string") {
    const low = explicit.toLowerCase();
    if (Object.prototype.hasOwnProperty.call(POLYMARKET_CITY_STATIONS, low)) {
      cityKey = low;
    }
  }

  // Tier 1.5: URL extraction from description / resolutionSource.
  // The Wunderground URL is the issuer's canonical proof — beats catalog
  // lookup. Defer gate still applies so a URL injection cannot silently
  // route an RCTP / HK-low market.
  const desc = typeof event.description === "string" ? event.description : "";
  const resSrc =
    typeof (event as { resolutionSource?: unknown }).resolutionSource === "string"
      ? (event as { resolutionSource: string }).resolutionSource
      : "";
  const urlText = `${desc} ${resSrc}`;
  const extractedIcao = extractIcaoFromResolutionSource(urlText);
  if (extractedIcao !== null) {
    if (extractedIcao === "RCTP") {
      throw new DeferredMarketError(
        `Polymarket market for station ${extractedIcao} is deferred until the v0.2 CWA client lands`,
      );
    }
    if (extractedIcao === "VHHH" && marketMeasure === "low") {
      throw new DeferredMarketError(
        `Polymarket low-extreme market for station ${extractedIcao} is deferred until the v0.2 HKO client lands`,
      );
    }
    if (DEFERRED_STATIONS.has(extractedIcao) && marketMeasure === "default") {
      throw new DeferredMarketError(
        `Polymarket market for deferred station ${extractedIcao} (measure=default) requires v0.2 client`,
      );
    }
    // Reverse-lookup the city for the extracted ICAO; fall back to explicit
    // city (if set) or empty string when neither resolves (the ICAO is the
    // authoritative resolution target — discovery can still attribute it).
    const fallbackCity = findCityForIcao(extractedIcao) ?? cityKey ?? "";
    return { city: fallbackCity, icao: extractedIcao, stationMeasure: "default" };
  }

  // Tier 2: scan slug + title + tags.
  if (cityKey === null) {
    cityKey = deriveCity(event);
  }
  if (cityKey === null) return null;

  const entry = POLYMARKET_CITY_STATIONS[cityKey];
  if (entry === undefined) return null;

  // Station-level measure: cities that split (paris high vs low) follow
  // the market measure; cities without a split use "default".
  let stationMeasure: "high" | "low" | "default" = "default";
  if (marketMeasure === "high" && typeof entry.high === "string") stationMeasure = "high";
  else if (marketMeasure === "low" && typeof entry.low === "string") stationMeasure = "low";

  const icao = entry[stationMeasure] ?? entry.default;
  if (typeof icao !== "string") return null;

  // Tier 0 deferred-station guard. Taipei (RCTP) defers all markets;
  // Hong Kong (VHHH) defers only the low market because HKO is the issuer
  // for the daily low. High markets at HK resolve via standard METAR.
  if (icao === "RCTP") {
    throw new DeferredMarketError(
      `Polymarket market for station ${icao} is deferred until the v0.2 CWA client lands`,
    );
  }
  if (icao === "VHHH" && marketMeasure === "low") {
    throw new DeferredMarketError(
      `Polymarket low-extreme market for station ${icao} is deferred until the v0.2 HKO client lands`,
    );
  }
  if (DEFERRED_STATIONS.has(icao) && marketMeasure === "default") {
    // Conservative default fallback for deferred stations.
    throw new DeferredMarketError(
      `Polymarket market for deferred station ${icao} (measure=default) requires v0.2 client`,
    );
  }

  return { city: cityKey, icao, stationMeasure };
}

/**
 * Parse the resolution date from a Polymarket weather slug. The LAST
 * YYYY-MM-DD match wins because slugs may carry both a creation date and
 * a resolution date (`created-2026-01-01-resolves-2026-05-23`) — the
 * resolution date is typically rightmost in Polymarket's convention.
 *
 * Mirrors Python `_settlement_date_from_slug` architect iter-1 HIGH-4.
 */
export function settlementDateFromSlug(slug: string): string {
  const matches = slug.matchAll(/(\d{4})-(\d{2})-(\d{2})/g);
  let last: RegExpMatchArray | null = null;
  for (const m of matches) last = m;
  if (last === null) {
    throw new PolymarketSettlementError(
      `no resolution date in slug ${JSON.stringify(slug)} (expected YYYY-MM-DD)`,
    );
  }
  const [_, y, m, d] = last;
  const year = Number(y);
  const month = Number(m);
  const day = Number(d);
  // Validate calendar date roundtrips (e.g. reject 2025-02-30).
  const ts = Date.UTC(year, month - 1, day);
  const back = new Date(ts);
  if (
    back.getUTCFullYear() !== year ||
    back.getUTCMonth() !== month - 1 ||
    back.getUTCDate() !== day
  ) {
    throw new PolymarketSettlementError(
      `slug ${JSON.stringify(slug)} carries malformed date ${y}-${m}-${d}`,
    );
  }
  return `${y}-${m}-${d}`;
}

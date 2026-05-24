// TS-W5 Wave 3 — polymarketDiscover().
//
// Calls Gamma `/events`, enriches each event with city + ICAO + market
// measure + resolution-source classification. Drops events that don't
// resolve to a known city (logged for the caller). Surfaces deferred
// markets (Taipei, HK-low) with `icao: null` so callers see they exist.

import { DeferredMarketError } from "@tradewinds/core";
import { type FetchEventsOptions, type PolymarketEventRaw, fetchEvents } from "./client.js";
import { extractResolutionSourceType, validateDescription } from "./description.js";
import { PayloadTooLargeError, PolymarketEventError } from "./errors.js";
import { detectMarketMeasure, resolveStationForEvent } from "./resolver.js";
import type { PolymarketDiscoveryRow, PolymarketResolutionSourceType } from "./types.js";

export interface PolymarketDiscoverOptions extends FetchEventsOptions {
  /**
   * Sink for dropped events. Tests pass a recorder; production can pass
   * console.info or omit. Receives `{slug, reason}` per skipped event.
   */
  onSkip?: (info: { slug: string | null; reason: string }) => void;
}

/**
 * Discover active Polymarket weather events.
 *
 * Returns one row per resolvable event. Events the resolver can't match
 * are dropped silently (with optional `onSkip` callback). Events that
 * route to a deferred station (Taipei, HK-low) appear in the result with
 * `icao: null` and `measure: null` so callers can SEE them.
 */
export async function polymarketDiscover(
  opts: PolymarketDiscoverOptions = {},
): Promise<PolymarketDiscoveryRow[]> {
  const raw = await fetchEvents(opts);
  const out: PolymarketDiscoveryRow[] = [];
  for (const ev of raw) {
    const slug = typeof ev.slug === "string" ? ev.slug : null;
    const title = typeof ev.title === "string" ? ev.title : null;
    const endTime = typeof ev.endDate === "string" ? ev.endDate : null;
    const eventId = typeof ev.id === "string" ? ev.id : null;

    const marketMeasure = detectMarketMeasure(ev);

    let icao: string | null = null;
    let cityKey: string | null = null;
    let measureOut: "high" | "low" | "default" | null = null;

    try {
      const resolved = resolveStationForEvent(ev, marketMeasure);
      if (resolved === null) {
        opts.onSkip?.({ slug, reason: "no city match in catalog" });
        continue;
      }
      icao = resolved.icao;
      cityKey = resolved.city;
      measureOut = marketMeasure;
    } catch (err) {
      if (err instanceof DeferredMarketError) {
        // Surface so callers see it exists but can't be settled in v0.1.
        cityKey = null;
        icao = null;
        measureOut = null;
      } else {
        throw err;
      }
    }

    const description = typeof ev.description === "string" ? ev.description : "";
    let resolutionSourceType: PolymarketResolutionSourceType | null = null;
    if (description.length > 0) {
      try {
        validateDescription(description);
        resolutionSourceType = extractResolutionSourceType(description);
      } catch (err) {
        // Bad description on a single event shouldn't poison the whole
        // discovery batch. Codex iter-1 P2: catch both validation paths
        // (PolymarketEventError AND PayloadTooLargeError, which is a
        // sibling TradewindsError after the static-field flatten).
        if (err instanceof PolymarketEventError || err instanceof PayloadTooLargeError) {
          opts.onSkip?.({ slug, reason: `description rejected: ${err.message}` });
          resolutionSourceType = null;
        } else {
          throw err;
        }
      }
    }

    out.push(
      Object.freeze({
        eventId,
        slug,
        title,
        city: cityKey,
        icao,
        measure: measureOut,
        endTime,
        resolutionSourceType,
      }),
    );
  }
  return out;
}

/** Re-export for callers who want the raw shape. */
export type { PolymarketEventRaw } from "./client.js";

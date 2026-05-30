import { CATALOG } from "@mostlyrightmd/core";
import { describe, expect, it } from "vitest";

import { KALSHI_SETTLEMENT_STATIONS } from "../src/data/generated/kalshi-stations.js";
import { POLYMARKET_CITY_STATIONS } from "../src/data/generated/polymarket-city-stations.js";

// Phase 22 — the core catalog is the venue-membership authority; the markets
// citation/city maps are venue-specific provenance. These tests close the loop
// (mirroring the Python test_kalshi_stations / test_polymarket_stations) so a
// drift between markets data and core venue tags fails loudly.

describe("Kalshi venue tag <-> settlement citations", () => {
  it("filterByVenue('kalshi') equals the citation ICAOs", () => {
    const citationIcaos = new Set(Object.values(KALSHI_SETTLEMENT_STATIONS).map((c) => c.station));
    const coreKalshi = new Set(CATALOG.filterByVenue("kalshi").map((s) => s.icao));
    expect(coreKalshi).toEqual(citationIcaos);
  });
});

describe("Polymarket venue tag <-> city-station map", () => {
  it("filterByVenue('polymarket') equals the in-catalog settlement ICAOs", () => {
    const settlementIcaos = new Set<string>();
    for (const stations of Object.values(POLYMARKET_CITY_STATIONS)) {
      for (const icao of Object.values(stations)) {
        if (typeof icao === "string") settlementIcaos.add(icao);
      }
    }
    const catalogIcaos = new Set([...CATALOG].map((s) => s.icao));

    // Phase 23: KLGA/KORD are now registry stations. HKO (Hong Kong
    // Observatory — no airport ICAO, v0.2-deferred) is the sole settlement
    // ICAO without a registry record / venue tag.
    const notInCatalog = [...settlementIcaos].filter((i) => !catalogIcaos.has(i)).sort();
    expect(notInCatalog).toEqual(["HKO"]);

    const expected = new Set([...settlementIcaos].filter((i) => catalogIcaos.has(i)));
    const tagged = new Set(CATALOG.filterByVenue("polymarket").map((s) => s.icao));
    expect(tagged).toEqual(expected);
  });

  it("Polymarket NYC/Chicago stations differ from Kalshi's", () => {
    expect(POLYMARKET_CITY_STATIONS.nyc?.default).toBe("KLGA");
    expect(POLYMARKET_CITY_STATIONS.chicago?.default).toBe("KORD");
    // Phase 23: KLGA/KORD are polymarket-only registry stations; KNYC/KMDW
    // stay kalshi-only — divergence preserved on both sides.
    expect([...CATALOG.get("KLGA").venues]).toEqual(["polymarket"]);
    expect([...CATALOG.get("KORD").venues]).toEqual(["polymarket"]);
    expect(CATALOG.get("KNYC").venues).not.toContain("polymarket");
    expect(CATALOG.get("KMDW").venues).not.toContain("polymarket");
  });
});

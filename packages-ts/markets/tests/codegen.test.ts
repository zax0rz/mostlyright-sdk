import { describe, expect, it } from "vitest";

import {
  KALSHI_SETTLEMENT_STATIONS,
  KNOWN_WRONG_STATIONS,
} from "../src/data/generated/kalshi-stations.js";
import { POLYMARKET_CITY_STATIONS } from "../src/data/generated/polymarket-city-stations.js";

describe("codegen: kalshi", () => {
  it("NYC resolves to KNYC (not KLGA / KJFK / KEWR)", () => {
    expect(KALSHI_SETTLEMENT_STATIONS.NYC?.station).toBe("KNYC");
  });

  it("KORD is in known-wrong (Chicago must use KMDW for Kalshi)", () => {
    expect(KNOWN_WRONG_STATIONS.has("KORD")).toBe(true);
  });

  it("CHI resolves to KMDW (Midway, NOT ORD)", () => {
    expect(KALSHI_SETTLEMENT_STATIONS.CHI?.station).toBe("KMDW");
  });
});

describe("codegen: polymarket measure-specific mappings (TS-W0 iter-1 CRITICAL 1)", () => {
  it("paris default is LFPG (Charles de Gaulle)", () => {
    expect(POLYMARKET_CITY_STATIONS.paris?.default).toBe("LFPG");
  });

  it("paris high is LFPG", () => {
    expect(POLYMARKET_CITY_STATIONS.paris?.high).toBe("LFPG");
  });

  it("paris low is LFPB (Le Bourget) — NOT LFPG", () => {
    // Silently routing paris-low to LFPG would corrupt every Polymarket
    // Paris settlement. This is the bug KNOWN_WRONG_STATIONS exists to prevent.
    expect(POLYMARKET_CITY_STATIONS.paris?.low).toBe("LFPB");
    expect(POLYMARKET_CITY_STATIONS.paris?.low).not.toBe("LFPG");
  });

  it("hong_kong carries high/low keys (same value as default)", () => {
    expect(POLYMARKET_CITY_STATIONS.hong_kong?.high).toBe("VHHH");
    expect(POLYMARKET_CITY_STATIONS.hong_kong?.low).toBe("VHHH");
  });

  it("tokyo carries high/low keys (same value as default)", () => {
    expect(POLYMARKET_CITY_STATIONS.tokyo?.high).toBe("RJTT");
    expect(POLYMARKET_CITY_STATIONS.tokyo?.low).toBe("RJTT");
  });

  it("cities without measure-specific overrides have only `default`", () => {
    const london = POLYMARKET_CITY_STATIONS.london;
    expect(london?.default).toBe("EGLL");
    expect(london?.high).toBeUndefined();
    expect(london?.low).toBeUndefined();
  });
});

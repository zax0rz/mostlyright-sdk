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
  it("paris collapsed to a single station LFPB (Phase 23, no high/low split)", () => {
    // Phase 23: the operator roster lists Paris as one station (LFPB). The old
    // LFPG/LFPB high/low split is gone; LFPG stays a bare registry record.
    expect(POLYMARKET_CITY_STATIONS.paris?.default).toBe("LFPB");
    expect(POLYMARKET_CITY_STATIONS.paris?.high).toBeUndefined();
    expect(POLYMARKET_CITY_STATIONS.paris?.low).toBeUndefined();
  });

  it("hong_kong carries high/low keys = HKO (Phase 23 — Observatory, deferred)", () => {
    expect(POLYMARKET_CITY_STATIONS.hong_kong?.high).toBe("HKO");
    expect(POLYMARKET_CITY_STATIONS.hong_kong?.low).toBe("HKO");
    expect(POLYMARKET_CITY_STATIONS.hong_kong?.default).toBe("HKO");
  });

  it("tokyo carries high/low keys (same value as default)", () => {
    expect(POLYMARKET_CITY_STATIONS.tokyo?.high).toBe("RJTT");
    expect(POLYMARKET_CITY_STATIONS.tokyo?.low).toBe("RJTT");
  });

  it("london is a single-airport entry — EGLC (Phase 23 move off EGLL)", () => {
    const london = POLYMARKET_CITY_STATIONS.london;
    expect(london?.default).toBe("EGLC");
    expect(london?.high).toBeUndefined();
    expect(london?.low).toBeUndefined();
  });
});

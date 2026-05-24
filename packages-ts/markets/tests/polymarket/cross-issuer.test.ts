import { describe, expect, it } from "vitest";

import { KALSHI_SETTLEMENT_STATIONS } from "../../src/data/generated/kalshi-stations.js";
import { POLYMARKET_CITY_STATIONS } from "../../src/data/generated/polymarket-city-stations.js";
import { POLYMARKET_KNOWN_WRONG_STATIONS } from "../../src/polymarket/known-wrong-stations.js";

describe("Cross-issuer station identity (Phase 8)", () => {
  it("NYC: Kalshi = KNYC, Polymarket = KLGA", () => {
    expect(KALSHI_SETTLEMENT_STATIONS.NYC?.station).toBe("KNYC");
    expect(POLYMARKET_CITY_STATIONS.nyc?.default).toBe("KLGA");
    expect(KALSHI_SETTLEMENT_STATIONS.NYC?.station).not.toBe(POLYMARKET_CITY_STATIONS.nyc?.default);
  });

  it("Chicago: Kalshi = KMDW, Polymarket = KORD", () => {
    expect(KALSHI_SETTLEMENT_STATIONS.CHI?.station).toBe("KMDW");
    expect(POLYMARKET_CITY_STATIONS.chicago?.default).toBe("KORD");
  });

  it("KLGA is in Polymarket NYC catalog but NOT in Polymarket NYC denylist", () => {
    expect(POLYMARKET_CITY_STATIONS.nyc?.default).toBe("KLGA");
    expect(POLYMARKET_KNOWN_WRONG_STATIONS.nyc?.has("KLGA")).toBe(false);
  });

  it("KNYC is Kalshi NYC station but Polymarket NYC denylist forbids it", () => {
    expect(KALSHI_SETTLEMENT_STATIONS.NYC?.station).toBe("KNYC");
    expect(POLYMARKET_KNOWN_WRONG_STATIONS.nyc?.has("KNYC")).toBe(true);
  });

  it("KMDW is Kalshi Chicago station but Polymarket Chicago denylist forbids it", () => {
    expect(KALSHI_SETTLEMENT_STATIONS.CHI?.station).toBe("KMDW");
    expect(POLYMARKET_KNOWN_WRONG_STATIONS.chicago?.has("KMDW")).toBe(true);
  });

  it("Every Polymarket city default is NOT in its own denylist", () => {
    for (const [city, denylist] of Object.entries(POLYMARKET_KNOWN_WRONG_STATIONS)) {
      const entry = POLYMARKET_CITY_STATIONS[city];
      if (entry === undefined) continue;
      expect(denylist.has(entry.default)).toBe(false);
    }
  });
});

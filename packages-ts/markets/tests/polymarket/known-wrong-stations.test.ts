import { describe, expect, it } from "vitest";

import { POLYMARKET_KNOWN_WRONG_STATIONS } from "../../src/polymarket/known-wrong-stations.js";

describe("POLYMARKET_KNOWN_WRONG_STATIONS", () => {
  it("denies KNYC/KJFK/KEWR for NYC", () => {
    const nyc = POLYMARKET_KNOWN_WRONG_STATIONS.nyc;
    expect(nyc).toBeDefined();
    expect(nyc?.has("KNYC")).toBe(true);
    expect(nyc?.has("KJFK")).toBe(true);
    expect(nyc?.has("KEWR")).toBe(true);
  });

  it("does NOT deny KLGA for NYC (KLGA is the correct Polymarket NYC station)", () => {
    expect(POLYMARKET_KNOWN_WRONG_STATIONS.nyc?.has("KLGA")).toBe(false);
  });

  it("denies KMDW for Chicago (Kalshi uses KMDW; Polymarket uses KORD)", () => {
    expect(POLYMARKET_KNOWN_WRONG_STATIONS.chicago?.has("KMDW")).toBe(true);
  });

  it("does NOT deny KORD for Chicago", () => {
    expect(POLYMARKET_KNOWN_WRONG_STATIONS.chicago?.has("KORD")).toBe(false);
  });

  it("denies KHOU for Houston", () => {
    expect(POLYMARKET_KNOWN_WRONG_STATIONS.houston?.has("KHOU")).toBe(true);
  });

  it("denies KIAD and KBWI for washington_dc", () => {
    expect(POLYMARKET_KNOWN_WRONG_STATIONS.washington_dc?.has("KIAD")).toBe(true);
    expect(POLYMARKET_KNOWN_WRONG_STATIONS.washington_dc?.has("KBWI")).toBe(true);
  });

  it("is shallow-frozen — top-level rebinding fails in strict mode", () => {
    expect(Object.isFrozen(POLYMARKET_KNOWN_WRONG_STATIONS)).toBe(true);
  });
});

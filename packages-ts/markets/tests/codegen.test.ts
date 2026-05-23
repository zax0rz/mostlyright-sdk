import { describe, expect, it } from "vitest";

import {
  KALSHI_SETTLEMENT_STATIONS,
  KNOWN_WRONG_STATIONS,
} from "../src/data/generated/kalshi-stations.js";

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

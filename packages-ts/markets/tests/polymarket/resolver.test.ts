import { DeferredMarketError } from "@tradewinds/core";
import { describe, expect, it } from "vitest";

import {
  PolymarketSettlementError,
  deriveCity,
  detectMarketMeasure,
  resolveStationForEvent,
  settlementDateFromSlug,
} from "../../src/polymarket/index.js";

describe("detectMarketMeasure", () => {
  it("returns 'high' when title carries a high keyword", () => {
    expect(detectMarketMeasure({ title: "Will NYC's daily HIGH exceed 80F?" })).toBe("high");
  });

  it("returns 'low' when title carries a low keyword", () => {
    expect(detectMarketMeasure({ title: "Tokyo daily lowest below 20C?" })).toBe("low");
  });

  it("returns 'default' when both / neither", () => {
    expect(detectMarketMeasure({ title: "London weather event" })).toBe("default");
    expect(detectMarketMeasure({ title: "high and low both" })).toBe("default");
  });

  it("scans slug and name fields too", () => {
    expect(detectMarketMeasure({ slug: "will-hottest-nyc-2025" })).toBe("high");
  });
});

describe("deriveCity", () => {
  it("matches city in the slug", () => {
    expect(deriveCity({ slug: "will-nyc-something-2025" })).toBeNull();
    // NYC is in the US registry, not Polymarket city catalog. Use london.
    expect(deriveCity({ slug: "will-london-be-above-25c-on-2025-07-04" })).toBe("london");
  });

  it("prefers longest-matching city (multi-token)", () => {
    expect(deriveCity({ slug: "will-london-gatwick-be-above-25c-on-2025-07-04" })).toBe(
      "london_gatwick",
    );
  });

  it("matches via tags too", () => {
    expect(deriveCity({ tags: [{ label: "Tokyo" }], slug: "some-other-slug" })).toBe("tokyo");
  });

  it("returns null on no match", () => {
    expect(deriveCity({ slug: "unknown-city-2025" })).toBeNull();
  });
});

describe("resolveStationForEvent", () => {
  it("resolves London → EGLL via slug derivation", () => {
    const r = resolveStationForEvent({ slug: "will-london-above-25c-2025" }, "high");
    expect(r?.icao).toBe("EGLL");
    expect(r?.city).toBe("london");
  });

  it("resolves Paris HIGH → LFPG, Paris LOW → LFPB (city-split aware)", () => {
    const high = resolveStationForEvent({ slug: "will-paris-hottest-2025" }, "high");
    expect(high?.icao).toBe("LFPG");
    const low = resolveStationForEvent({ slug: "will-paris-lowest-2025" }, "low");
    expect(low?.icao).toBe("LFPB");
  });

  it("raises DeferredMarketError for Taipei (always)", () => {
    expect(() => resolveStationForEvent({ slug: "will-taipei-be-above-30c-2025" }, "high")).toThrow(
      DeferredMarketError,
    );
  });

  it("raises DeferredMarketError for Hong Kong LOW (HKO deferred)", () => {
    expect(() => resolveStationForEvent({ slug: "will-hong-kong-coldest-2025" }, "low")).toThrow(
      DeferredMarketError,
    );
  });

  it("accepts Hong Kong HIGH (METAR resolves it)", () => {
    const r = resolveStationForEvent({ slug: "will-hong-kong-hottest-2025" }, "high");
    expect(r?.icao).toBe("VHHH");
  });

  it("returns null when no city matches", () => {
    expect(resolveStationForEvent({ slug: "no-known-city-2025" }, "default")).toBeNull();
  });

  it("honors explicit event.city field over slug derivation", () => {
    const r = resolveStationForEvent(
      { slug: "ambiguous", city: "london" } as { slug: string; city: string },
      "default",
    );
    expect(r?.icao).toBe("EGLL");
  });
});

describe("settlementDateFromSlug", () => {
  it("extracts a single YYYY-MM-DD", () => {
    expect(settlementDateFromSlug("will-nyc-be-above-80f-on-2026-05-23")).toBe("2026-05-23");
  });

  it("picks the LAST date when slug carries multiple", () => {
    expect(settlementDateFromSlug("created-2026-01-01-resolves-2026-05-23")).toBe("2026-05-23");
  });

  it("throws when no date is present", () => {
    expect(() => settlementDateFromSlug("no-date-here")).toThrow(PolymarketSettlementError);
  });

  it("rejects calendar-invalid dates (e.g. 2025-02-30)", () => {
    expect(() => settlementDateFromSlug("resolves-on-2025-02-30")).toThrow(
      PolymarketSettlementError,
    );
  });
});

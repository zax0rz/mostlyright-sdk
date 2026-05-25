import { DeferredMarketError } from "@mostlyright/core";
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
    // Phase 8 added nyc to the Polymarket city catalog (KLGA, not KNYC).
    // The slug-derive now correctly surfaces it.
    expect(deriveCity({ slug: "will-nyc-something-2025" })).toBe("nyc");
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

  it("requires token-delimited matches (codex iter-5 P2)", () => {
    // "comparison" contains "paris" as a substring but is NOT a Paris
    // weather event. Word-boundary match should reject this.
    expect(deriveCity({ title: "comparison of two events" })).toBeNull();
    // "milano" should NOT match "milan" — different city, substring
    // would have matched previously. (Real Polymarket slugs use the
    // city key form anyway: "milan".)
    expect(deriveCity({ title: "milano vs roma" })).toBeNull();
    // Hyphen/space separators still match as expected.
    expect(deriveCity({ slug: "weather-london-2025" })).toBe("london");
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

// Phase 8 — Tier 1.5 URL extraction (ts-architect iter-1 HIGH: zero coverage).
describe("resolveStationForEvent — Tier 1.5 URL extraction", () => {
  it("URL ICAO overrides catalog (city + URL disagree)", () => {
    // city=chicago → KORD in catalog; URL embeds KLAX → URL wins.
    const r = resolveStationForEvent(
      {
        slug: "chicago-high",
        title: "Chicago daily high",
        description: "Resolves via https://www.wunderground.com/dashboard/pws/KLAX",
        city: "chicago",
      } as { slug: string; title: string; description: string; city: string },
      "high",
    );
    expect(r?.icao).toBe("KLAX");
    // CRITICAL parity invariant: `city` is the slug/explicit value, NOT a
    // reverse-lookup from the URL ICAO. Mirrors Python `polymarket_discover`.
    expect(r?.city).toBe("chicago");
    // Iter-2 codex HIGH: stationMeasure mirrors the market measure (high
    // here, from "Chicago daily high" title), not a hardcoded "default".
    expect(r?.stationMeasure).toBe("high");
  });

  it("Tier 1.5 stationMeasure mirrors detected low marketMeasure", () => {
    const r = resolveStationForEvent(
      {
        slug: "la-low",
        title: "Will LA's lowest temp drop below 50?",
        description: "https://www.wunderground.com/dashboard/pws/KLAX",
      } as { slug: string; title: string; description: string },
      "low",
    );
    expect(r?.icao).toBe("KLAX");
    expect(r?.stationMeasure).toBe("low");
  });

  it("URL alone resolves an event with no city field", () => {
    const r = resolveStationForEvent(
      {
        slug: "ambiguous",
        title: "Daily high somewhere",
        description: "https://www.wunderground.com/dashboard/pws/KLAX",
      },
      "high",
    );
    expect(r?.icao).toBe("KLAX");
    expect(r?.city).toBe(""); // No explicit nor slug-derived city — empty by design.
  });

  it("URL extraction picks up resolutionSource field", () => {
    const r = resolveStationForEvent(
      {
        slug: "ambiguous",
        title: "high",
        resolutionSource: "https://wunderground.com/dashboard/pws/KLGA",
      } as { slug: string; title: string; resolutionSource: string },
      "high",
    );
    expect(r?.icao).toBe("KLGA");
  });

  it("multi-URL disagreement abstains (Tier 1.5 returns null path)", () => {
    // city=chicago (catalog→KORD) + two disagreeing URLs (KLAX + KSFO).
    // Tier 1.5 must abstain → resolver falls through to catalog → KORD.
    const r = resolveStationForEvent(
      {
        slug: "chi",
        city: "chicago",
        description:
          "See https://www.wunderground.com/dashboard/pws/KLAX " +
          "and historical https://www.wunderground.com/history/daily/KSFO/date/2026-01-01",
      } as { slug: string; city: string; description: string },
      "high",
    );
    expect(r?.icao).toBe("KORD");
    expect(r?.city).toBe("chicago");
  });

  it("multi-URL agreement passes", () => {
    const r = resolveStationForEvent(
      {
        slug: "chi",
        city: "chicago",
        description:
          "Primary https://www.wunderground.com/dashboard/pws/KLAX " +
          "or alternate https://www.wunderground.com/history/daily/KLAX/date/2026-05-23",
      } as { slug: string; city: string; description: string },
      "high",
    );
    expect(r?.icao).toBe("KLAX");
    expect(r?.city).toBe("chicago");
  });

  it("non-canonical Wunderground URL path falls through to catalog", () => {
    // Hostile-pattern guard: news URLs / arbitrary slugs MUST NOT trigger Tier 1.5.
    const r = resolveStationForEvent(
      {
        slug: "boston",
        city: "boston",
        description: "https://www.wunderground.com/news/2024-summer-KIDS-overview",
      } as { slug: string; city: string; description: string },
      "high",
    );
    expect(r?.icao).toBe("KBOS"); // boston catalog default
    expect(r?.city).toBe("boston");
  });

  it("no URL → falls through to Tier 2 city derive", () => {
    const r = resolveStationForEvent({ slug: "will-london-be-above-25c-2025" }, "high");
    expect(r?.icao).toBe("EGLL");
    expect(r?.city).toBe("london");
  });

  it("URL containing non-K-prefix ICAO (e.g. RCTP) is not extracted by the regex", () => {
    // The Wunderground regex is K-prefix only by design (US-only constraint).
    // Even if an issuer embeds a synthetic non-US ICAO in the URL, Tier 1.5
    // returns null and the resolver falls through to Tier 2 — which catches
    // the slug-derived "taipei" and routes through the catalog-side defer
    // gate (already covered by the Tier 2 deferred-market tests above).
    // The defer gate inside Tier 1.5 is defense-in-depth for any future
    // K-prefix deferred station and remains as visible source-side guards.
    expect(() =>
      resolveStationForEvent(
        {
          slug: "taipei",
          description: "https://www.wunderground.com/dashboard/pws/RCTP",
        } as { slug: string; description: string },
        "high",
      ),
    ).toThrow(DeferredMarketError);
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

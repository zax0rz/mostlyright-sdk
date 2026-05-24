import { describe, expect, it } from "vitest";

import { extractIcaoFromResolutionSource } from "../../src/polymarket/resolver.js";

describe("extractIcaoFromResolutionSource", () => {
  it("captures KLGA from dashboard/pws URL", () => {
    expect(extractIcaoFromResolutionSource("https://wunderground.com/dashboard/pws/KLGA")).toBe(
      "KLGA",
    );
  });

  it("captures KLGA from bare pws URL", () => {
    expect(extractIcaoFromResolutionSource("https://wunderground.com/pws/KLGA")).toBe("KLGA");
  });

  it("captures KORD from history/daily URL with date", () => {
    expect(
      extractIcaoFromResolutionSource(
        "https://www.wunderground.com/history/daily/KORD/date/2026-05-23",
      ),
    ).toBe("KORD");
  });

  it("captures KORD from history/airport URL", () => {
    expect(
      extractIcaoFromResolutionSource(
        "https://www.wunderground.com/history/airport/KORD/2026/5/23/DailyHistory.html",
      ),
    ).toBe("KORD");
  });

  it("captures KSFO from weather-station URL", () => {
    expect(extractIcaoFromResolutionSource("https://wunderground.com/weather-station/KSFO")).toBe(
      "KSFO",
    );
  });

  it("ignores non-canonical paths (news / arbitrary slugs)", () => {
    // Iter-1 TS-architect HIGH: incidental K-prefix tokens in non-canonical
    // Wunderground URL paths MUST NOT match.
    expect(
      extractIcaoFromResolutionSource(
        "https://www.wunderground.com/news/2024-summer-KIDS-overview",
      ),
    ).toBeNull();
  });

  it("ignores codex-flagged hostile URL pattern (wunderground.com/weather/.../VHHH)", () => {
    // Codex iter-1 CRITICAL: original loose regex extracted "KONG" from
    // "hong-kong" slug. Tightened pattern requires canonical path segment.
    expect(
      extractIcaoFromResolutionSource("https://www.wunderground.com/weather/hk/hong-kong/VHHH"),
    ).toBeNull();
  });

  it("ignores weather.gov URLs (not allowlisted for ICAO extraction)", () => {
    expect(extractIcaoFromResolutionSource("https://weather.gov/nyc")).toBeNull();
  });

  it("returns null for null/undefined/empty", () => {
    expect(extractIcaoFromResolutionSource(null)).toBeNull();
    expect(extractIcaoFromResolutionSource(undefined)).toBeNull();
    expect(extractIcaoFromResolutionSource("")).toBeNull();
  });

  it("returns null when no URL in text", () => {
    expect(extractIcaoFromResolutionSource("no urls in this description")).toBeNull();
  });

  it("does NOT match lowercase ICAO (iter-3 codex CRITICAL — dropped IGNORECASE)", () => {
    // Iter-3 dropped IGNORECASE so the intermediate-slug pattern can't
    // consume uppercase station segments. Synthetic lowercase ICAOs no
    // longer match — real Wunderground URLs use uppercase ICAOs.
    expect(
      extractIcaoFromResolutionSource("https://wunderground.com/dashboard/pws/klax"),
    ).toBeNull();
  });

  it("extracts from text containing prose plus URL", () => {
    const text =
      "Settles per Wunderground daily-high — see https://www.wunderground.com/dashboard/pws/KSFO";
    expect(extractIcaoFromResolutionSource(text)).toBe("KSFO");
  });

  it("returns null on disagreeing multi-URL (architect iter-1 HIGH)", () => {
    const text =
      "Primary https://www.wunderground.com/dashboard/pws/KLAX " +
      "or use https://www.wunderground.com/dashboard/pws/KSFO instead";
    expect(extractIcaoFromResolutionSource(text)).toBeNull();
  });

  it("returns the ICAO when multiple URLs agree", () => {
    const text =
      "Primary https://www.wunderground.com/dashboard/pws/KLAX " +
      "and mirror https://www.wunderground.com/history/daily/KLAX/date/2026-05-23";
    expect(extractIcaoFromResolutionSource(text)).toBe("KLAX");
  });

  // ---------------------------------------------------------------------
  // Iter-2 architect CRITICAL: real Polymarket URL shapes carry
  // country/state/city slugs between the anchor and the ICAO.
  // ---------------------------------------------------------------------
  it("captures KLGA from real Polymarket NYC URL with /us/ny/new-york-city/ slugs", () => {
    expect(
      extractIcaoFromResolutionSource(
        "https://www.wunderground.com/history/daily/us/ny/new-york-city/KLGA",
      ),
    ).toBe("KLGA");
  });

  it("captures KORD from real Polymarket Chicago URL with /us/il/chicago/ slugs", () => {
    expect(
      extractIcaoFromResolutionSource(
        "https://www.wunderground.com/history/daily/us/il/chicago/KORD",
      ),
    ).toBe("KORD");
  });

  it("captures KLAX from real Polymarket LA URL", () => {
    expect(
      extractIcaoFromResolutionSource(
        "https://www.wunderground.com/history/daily/us/ca/los-angeles/KLAX",
      ),
    ).toBe("KLAX");
  });

  it("captures KLGA from /cat/forecasts/ URL with state slugs", () => {
    expect(
      extractIcaoFromResolutionSource(
        "https://www.wunderground.com/cat/forecasts/us/ny/new-york/KLGA",
      ),
    ).toBe("KLGA");
  });

  // ---------------------------------------------------------------------
  // Iter-2 codex CRITICAL: URL terminators in Markdown / prose.
  // ---------------------------------------------------------------------
  it("captures URL with trailing Markdown paren", () => {
    expect(
      extractIcaoFromResolutionSource(
        "see [station](https://www.wunderground.com/dashboard/pws/KLGA)",
      ),
    ).toBe("KLGA");
  });

  it("captures URL followed by period", () => {
    expect(
      extractIcaoFromResolutionSource(
        "Settles via https://www.wunderground.com/dashboard/pws/KLGA.",
      ),
    ).toBe("KLGA");
  });

  it("captures URL followed by comma", () => {
    expect(
      extractIcaoFromResolutionSource(
        "Sources: https://www.wunderground.com/dashboard/pws/KLGA, plus others",
      ),
    ).toBe("KLGA");
  });

  // ---------------------------------------------------------------------
  // Regression guards — negative-lookahead rejects K-prefix continuations.
  // ---------------------------------------------------------------------
  it("does NOT extract from /pws/KIDS-summer-2024 (hyphen-continuation)", () => {
    expect(
      extractIcaoFromResolutionSource("https://wunderground.com/pws/KIDS-summer-2024"),
    ).toBeNull();
  });

  it("does NOT extract from /pws/KORDX (longer uppercase ID)", () => {
    expect(extractIcaoFromResolutionSource("https://wunderground.com/pws/KORDX")).toBeNull();
  });

  // ---------------------------------------------------------------------
  // Iter-3 codex CRITICAL: regex must NOT consume uppercase station slot
  // as an "intermediate slug" when IGNORECASE is dropped.
  // ---------------------------------------------------------------------
  it("extracts FIRST K-prefix segment from /history/daily/KORD/date/KLAX (canonical slot)", () => {
    expect(
      extractIcaoFromResolutionSource("https://www.wunderground.com/history/daily/KORD/date/KLAX"),
    ).toBe("KORD");
  });

  it("extracts canonical KORD from /pws/KORD/nearby/KLAX", () => {
    expect(extractIcaoFromResolutionSource("https://wunderground.com/pws/KORD/nearby/KLAX")).toBe(
      "KORD",
    );
  });

  it("extracts canonical KORD from /history/airport/KORD/2026/5/KLAX/DailyHistory.html", () => {
    expect(
      extractIcaoFromResolutionSource(
        "https://www.wunderground.com/history/airport/KORD/2026/5/KLAX/DailyHistory.html",
      ),
    ).toBe("KORD");
  });

  it("extracts canonical KORD from real-shape URL with trailing uppercase path components", () => {
    expect(
      extractIcaoFromResolutionSource(
        "https://www.wunderground.com/history/daily/us/il/chicago/KORD/date/KLAX",
      ),
    ).toBe("KORD");
  });
});

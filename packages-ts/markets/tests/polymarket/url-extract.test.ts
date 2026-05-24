import { describe, expect, it } from "vitest";

import { extractIcaoFromResolutionSource } from "../../src/polymarket/resolver.js";

describe("extractIcaoFromResolutionSource", () => {
  it("captures KLGA from pws URL", () => {
    expect(extractIcaoFromResolutionSource("https://wunderground.com/dashboard/pws/KLGA")).toBe(
      "KLGA",
    );
  });

  it("captures KORD from history URL with date", () => {
    expect(
      extractIcaoFromResolutionSource(
        "https://www.wunderground.com/history/daily/KORD/date/2026-05-23",
      ),
    ).toBe("KORD");
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

  it("uppercases the captured ICAO", () => {
    expect(extractIcaoFromResolutionSource("https://wunderground.com/dashboard/pws/klax")).toBe(
      "KLAX",
    );
  });

  it("extracts from text containing prose plus URL", () => {
    const text =
      "Settles per Wunderground daily-high — see https://www.wunderground.com/dashboard/pws/KSFO";
    expect(extractIcaoFromResolutionSource(text)).toBe("KSFO");
  });
});

import { describe, expect, it } from "vitest";

import {
  PayloadTooLargeError,
  PolymarketEventError,
  extractResolutionSourceType,
  validateDescription,
} from "../../src/polymarket/index.js";

describe("validateDescription — 16 KB cap", () => {
  it("accepts an empty description", () => {
    expect(() => validateDescription("")).not.toThrow();
  });

  it("accepts a typical short description", () => {
    expect(() =>
      validateDescription("Resolves on weather.gov for NYC daily high on 2025-01-06."),
    ).not.toThrow();
  });

  it("accepts a description right at the 16 KB boundary", () => {
    const at = "x".repeat(16 * 1024);
    expect(() => validateDescription(at)).not.toThrow();
  });

  it("rejects a description that exceeds the 16 KB cap", () => {
    const over = "x".repeat(16 * 1024 + 1);
    expect(() => validateDescription(over)).toThrow(PayloadTooLargeError);
  });

  it("counts UTF-8 bytes, not code units", () => {
    // 4-byte chars × 4097 = 16388 bytes (over) but only 4097 chars (under cu count).
    const fourByteChar = "𠮷"; // U+20BB7
    const over = fourByteChar.repeat(4097);
    expect(() => validateDescription(over)).toThrow(PayloadTooLargeError);
  });

  it("rejects non-string input with a clear TypeError-style message", () => {
    expect(() => validateDescription(null as unknown as string)).toThrow(PolymarketEventError);
    expect(() => validateDescription(undefined as unknown as string)).toThrow(PolymarketEventError);
    expect(() => validateDescription(123 as unknown as string)).toThrow(PolymarketEventError);
  });
});

describe("validateDescription — netloc allowlist", () => {
  it("accepts wunderground.com (with and without www.)", () => {
    expect(() => validateDescription("source: https://wunderground.com/x")).not.toThrow();
    expect(() => validateDescription("source: https://www.wunderground.com/x")).not.toThrow();
  });

  it("accepts weather.gov (with and without www.)", () => {
    expect(() => validateDescription("source: https://weather.gov/x")).not.toThrow();
    expect(() => validateDescription("source: https://www.weather.gov/x")).not.toThrow();
  });

  it("rejects unknown netlocs", () => {
    expect(() => validateDescription("source: https://evil.example.com/")).toThrow(
      PolymarketEventError,
    );
    expect(() => validateDescription("source: https://accuweather.com/")).toThrow(
      PolymarketEventError,
    );
  });

  it("rejects a description with multiple URLs if any is outside the allowlist", () => {
    expect(() =>
      validateDescription("primary https://weather.gov/ secondary https://evil.example.com/"),
    ).toThrow(PolymarketEventError);
  });

  it("rejects unparseable URLs", () => {
    // URL constructor will reject bare schemes or whitespace-broken hosts.
    expect(() => validateDescription("see http://[not-a-url")).toThrow(PolymarketEventError);
  });
});

describe("extractResolutionSourceType", () => {
  it("returns 'wunderground' when description carries a Wunderground URL", () => {
    expect(extractResolutionSourceType("see https://www.wunderground.com/x")).toBe("wunderground");
  });

  it("returns 'noaa_wrh' when description carries a weather.gov URL", () => {
    expect(extractResolutionSourceType("see https://www.weather.gov/x")).toBe("noaa_wrh");
  });

  it("returns 'other' when no allowlisted URL appears", () => {
    expect(extractResolutionSourceType("plain text with no URL")).toBe("other");
  });

  it("picks the FIRST allowlisted netloc when multiple appear", () => {
    expect(
      extractResolutionSourceType(
        "first https://weather.gov/x then https://www.wunderground.com/y",
      ),
    ).toBe("noaa_wrh");
  });
});

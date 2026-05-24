// TS-W3 Plan 03 Task 2 — cache-key generator tests.

import { describe, expect, it } from "vitest";

import { cacheKeyForClimate, cacheKeyForObservations } from "../../../src/internal/cache/keys.js";

describe("cacheKeyForObservations", () => {
  it("emits the canonical key shape", () => {
    expect(cacheKeyForObservations("KNYC", 2025, 1)).toBe(
      "tradewinds:v1:observations:KNYC:2025:01",
    );
    expect(cacheKeyForObservations("KNYC", 2025, 12)).toBe(
      "tradewinds:v1:observations:KNYC:2025:12",
    );
  });

  it("upper-cases station identifiers", () => {
    expect(cacheKeyForObservations("knyc", 2025, 12)).toBe(
      "tradewinds:v1:observations:KNYC:2025:12",
    );
  });

  it("zero-pads month to 2 digits", () => {
    expect(cacheKeyForObservations("KNYC", 2025, 1)).toContain(":2025:01");
    expect(cacheKeyForObservations("KNYC", 2025, 9)).toContain(":2025:09");
    expect(cacheKeyForObservations("KNYC", 2025, 10)).toContain(":2025:10");
  });

  it("rejects out-of-range months", () => {
    expect(() => cacheKeyForObservations("KNYC", 2025, 0)).toThrow(RangeError);
    expect(() => cacheKeyForObservations("KNYC", 2025, 13)).toThrow(RangeError);
    expect(() => cacheKeyForObservations("KNYC", 2025, -1)).toThrow(RangeError);
    expect(() => cacheKeyForObservations("KNYC", 2025, 1.5)).toThrow(RangeError);
  });

  it("rejects out-of-range years", () => {
    expect(() => cacheKeyForObservations("KNYC", 1899, 1)).toThrow(RangeError);
    expect(() => cacheKeyForObservations("KNYC", 2101, 1)).toThrow(RangeError);
    expect(() => cacheKeyForObservations("KNYC", Number.NaN, 1)).toThrow(RangeError);
    expect(() => cacheKeyForObservations("KNYC", 2025.5, 1)).toThrow(RangeError);
  });
});

describe("cacheKeyForClimate", () => {
  it("emits the canonical key shape (year-only)", () => {
    expect(cacheKeyForClimate("KNYC", 2025)).toBe("tradewinds:v1:climate:KNYC:2025");
  });

  it("upper-cases station identifiers", () => {
    expect(cacheKeyForClimate("knyc", 2025)).toBe("tradewinds:v1:climate:KNYC:2025");
  });

  it("rejects out-of-range years", () => {
    expect(() => cacheKeyForClimate("KNYC", 1899)).toThrow(RangeError);
    expect(() => cacheKeyForClimate("KNYC", 2101)).toThrow(RangeError);
  });
});

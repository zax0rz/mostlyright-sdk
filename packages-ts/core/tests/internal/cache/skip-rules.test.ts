// TS-W3 Plan 03 Task 1 + Task 3 — cache-skip predicate tests + 5-case
// behavior fixture replay.

import { describe, expect, it } from "vitest";

import {
  isLiveSource,
  isWithinVolatileWindow,
  shouldSkipCacheForCurrentLstMonth,
  shouldSkipCacheForCurrentLstYear,
} from "../../../src/internal/cache/skip-rules.js";

import fixtureData from "./fixtures/skip-rules-behavior.json" with { type: "json" };

describe("shouldSkipCacheForCurrentLstMonth", () => {
  it("KNYC (UTC-5 LST): now=2025-01-15T12:00:00Z falls in Jan 2025 LST", () => {
    const now = new Date("2025-01-15T12:00:00Z");
    expect(shouldSkipCacheForCurrentLstMonth("KNYC", 2025, 1, now)).toBe(true);
    expect(shouldSkipCacheForCurrentLstMonth("KNYC", 2024, 12, now)).toBe(false);
    expect(shouldSkipCacheForCurrentLstMonth("KNYC", 2025, 2, now)).toBe(false);
  });

  it("KNYC across UTC-day boundary: 2025-02-01T03:00Z is still 2025-01-31 LST", () => {
    const now = new Date("2025-02-01T03:00:00Z");
    expect(shouldSkipCacheForCurrentLstMonth("KNYC", 2025, 1, now)).toBe(true);
    expect(shouldSkipCacheForCurrentLstMonth("KNYC", 2025, 2, now)).toBe(false);
  });

  it("unknown station throws RangeError", () => {
    expect(() => shouldSkipCacheForCurrentLstMonth("XYZQ", 2025, 1, new Date())).toThrow(
      RangeError,
    );
  });
});

describe("shouldSkipCacheForCurrentLstYear", () => {
  it("RJTT (UTC+9): now=2025-12-31T20:00Z is 2026-01-01 in Tokyo", () => {
    const now = new Date("2025-12-31T20:00:00Z");
    expect(shouldSkipCacheForCurrentLstYear("RJTT", 2026, now)).toBe(true);
    expect(shouldSkipCacheForCurrentLstYear("RJTT", 2025, now)).toBe(false);
  });
});

describe("isLiveSource", () => {
  it("returns true for sources ending in .live", () => {
    expect(isLiveSource("awc.live")).toBe(true);
    expect(isLiveSource("iem.archive.live")).toBe(true);
  });

  it("returns false for non-live sources", () => {
    expect(isLiveSource("awc")).toBe(false);
    expect(isLiveSource("iem.archive")).toBe(false);
    expect(isLiveSource("live.fake")).toBe(false);
  });

  it("returns false for null / undefined / empty", () => {
    expect(isLiveSource(null)).toBe(false);
    expect(isLiveSource(undefined)).toBe(false);
    expect(isLiveSource("")).toBe(false);
  });
});

describe("isWithinVolatileWindow", () => {
  it("returns true for events within `days` of asOf", () => {
    expect(isWithinVolatileWindow("2025-01-01", "2025-01-15")).toBe(true); // 14 days
    expect(isWithinVolatileWindow("2025-01-15", "2025-01-15")).toBe(true); // 0 days
  });

  it("returns false for events outside the window", () => {
    expect(isWithinVolatileWindow("2024-12-01", "2025-01-15")).toBe(false); // 45 days
    expect(isWithinVolatileWindow("2025-01-16", "2025-01-15")).toBe(false); // future
  });

  it("treats the documented boundary (exactly `days` days back) as volatile", () => {
    // archiveAsOf - eventDate == 30 days; doc comment defines the window as
    // [archiveAsOf - days, archiveAsOf] inclusive at both endpoints, so an
    // event exactly 30 days old MUST still be skipped (off-by-one regression
    // closed in iter-5 H10).
    expect(isWithinVolatileWindow("2024-12-16", "2025-01-15")).toBe(true); // 30 days
    expect(isWithinVolatileWindow("2024-12-15", "2025-01-15")).toBe(false); // 31 days
    // Custom-window boundary: days=7 → 7 days back is inclusive.
    expect(isWithinVolatileWindow("2025-01-08", "2025-01-15", 7)).toBe(true);
    expect(isWithinVolatileWindow("2025-01-07", "2025-01-15", 7)).toBe(false);
  });

  it("custom `days` window", () => {
    expect(isWithinVolatileWindow("2025-01-01", "2025-01-15", 7)).toBe(false);
    expect(isWithinVolatileWindow("2025-01-12", "2025-01-15", 7)).toBe(true);
  });

  it("invalid dates throw RangeError", () => {
    expect(() => isWithinVolatileWindow("not-a-date", "2025-01-15")).toThrow(RangeError);
    expect(() => isWithinVolatileWindow("2025-01-15", "not-a-date")).toThrow(RangeError);
  });
});

describe("skip-rules behavior fixture (5 cases — TS-W3 SC#2)", () => {
  for (const c of fixtureData.cases) {
    it(`${c.id}`, () => {
      const now = new Date(c.now);
      expect(shouldSkipCacheForCurrentLstMonth(c.station, c.year, c.month, now)).toBe(
        c.expected.skipCurrentMonth,
      );
      expect(isLiveSource(c.source)).toBe(c.expected.skipLive);
      expect(isWithinVolatileWindow(c.eventDate, c.asOf, 30)).toBe(c.expected.skipVolatile);
    });
  }
});

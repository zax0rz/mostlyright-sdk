// TS-W2 Plan 01 — yearlyChunksExclusiveEnd unit tests.
//
// Byte-faithful port of
// `packages/weather/src/mostlyright/weather/_fetchers/_iem_chunks.py::yearly_chunks_exclusive_end`
// (PR #85 cf9eb85, 2026-05-12). Leap-year safety via `date(year+1, 1, 1)` —
// NEVER `+365 days` (drops Feb 29; PR #85's primary anti-pattern).

import { describe, expect, it } from "vitest";

import { yearlyChunksExclusiveEnd } from "../src/_fetchers/_iem_chunks.js";

describe("yearlyChunksExclusiveEnd — single-year ranges", () => {
  it("same-year mid-range produces one chunk ending at Jan 1 of next year", () => {
    // Caller asked for 2024-03-15..2024-08-20; chunk extends to 2025-01-01 (exclusive end).
    expect(yearlyChunksExclusiveEnd("2024-03-15", "2024-08-20")).toEqual([
      ["2024-03-15", "2025-01-01"],
    ]);
  });

  it("mid-year range 2024-06-01..2024-09-30 → single chunk (2024-06-01, 2025-01-01)", () => {
    expect(yearlyChunksExclusiveEnd("2024-06-01", "2024-09-30")).toEqual([
      ["2024-06-01", "2025-01-01"],
    ]);
  });

  it("start on Jan 1 → chunk_start equals input (no clamping needed)", () => {
    expect(yearlyChunksExclusiveEnd("2024-01-01", "2024-06-30")).toEqual([
      ["2024-01-01", "2025-01-01"],
    ]);
  });
});

describe("yearlyChunksExclusiveEnd — multi-year spans", () => {
  it("three-year span 2023-11-01..2025-02-15 → 3 chunks; intermediates start Jan 1", () => {
    // Mirrors the plan's behavior bullet exactly.
    expect(yearlyChunksExclusiveEnd("2023-11-01", "2025-02-15")).toEqual([
      ["2023-11-01", "2024-01-01"],
      ["2024-01-01", "2025-01-01"],
      ["2025-01-01", "2026-01-01"],
    ]);
  });

  it("three full calendar years 2022-01-01..2024-12-31 → 3 chunks all Jan-1-anchored", () => {
    const chunks = yearlyChunksExclusiveEnd("2022-01-01", "2024-12-31");
    expect(chunks).toHaveLength(3);
    expect(chunks).toEqual([
      ["2022-01-01", "2023-01-01"],
      ["2023-01-01", "2024-01-01"],
      ["2024-01-01", "2025-01-01"],
    ]);
    // All intermediate chunk_starts MUST be Jan 1.
    for (const chunk of chunks) {
      expect(chunk[0].endsWith("-01-01")).toBe(true);
    }
  });
});

describe("yearlyChunksExclusiveEnd — leap-year safety", () => {
  it("leap-day start 2024-02-29..2024-03-01 → (2024-02-29, 2025-01-01); no off-by-one", () => {
    // Python's `date(year+1, 1, 1)` advance is leap-safe; `+365 days` would
    // silently drop Feb 29 and walk the calendar boundary by one day every
    // leap year. The test asserts the calendar-safe form.
    expect(yearlyChunksExclusiveEnd("2024-02-29", "2024-03-01")).toEqual([
      ["2024-02-29", "2025-01-01"],
    ]);
  });

  it("leap-year-span 2023-12-31..2024-12-31 → (2023-12-31, 2024-01-01), (2024-01-01, 2025-01-01)", () => {
    expect(yearlyChunksExclusiveEnd("2023-12-31", "2024-12-31")).toEqual([
      ["2023-12-31", "2024-01-01"],
      ["2024-01-01", "2025-01-01"],
    ]);
  });
});

describe("yearlyChunksExclusiveEnd — reversed range guard", () => {
  it("start > end (lexicographic) → empty array, no throw", () => {
    expect(yearlyChunksExclusiveEnd("2025-01-01", "2024-12-31")).toEqual([]);
  });

  it("start > end same-year → empty array", () => {
    expect(yearlyChunksExclusiveEnd("2024-06-15", "2024-03-15")).toEqual([]);
  });
});

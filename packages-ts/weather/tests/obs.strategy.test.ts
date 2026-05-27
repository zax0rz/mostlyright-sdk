// Phase 21 21-04 — obs strategy 'auto' routing tests.
//
// The smart-router picks `exact_window` for ≤7-day windows (small one-off
// payloads), `warm_cache` for longer windows (year-aligned cache reuse).
// Boundary tests lock the 7-day threshold so it doesn't drift.

import { describe, expect, it } from "vitest";

import { resolveAutoStrategy } from "../src/obs.js";

describe("obs auto-routing — window-size heuristic", () => {
  it("7-day window routes to exact_window", () => {
    // 2025-01-06 .. 2025-01-12 inclusive = 7 days.
    expect(resolveAutoStrategy("2025-01-06", "2025-01-12")).toBe("exact_window");
  });

  it("1-day window routes to exact_window", () => {
    expect(resolveAutoStrategy("2025-01-06", "2025-01-06")).toBe("exact_window");
  });

  it("8-day window routes to warm_cache (above 7-day threshold)", () => {
    // 2025-01-06 .. 2025-01-13 inclusive = 8 days.
    expect(resolveAutoStrategy("2025-01-06", "2025-01-13")).toBe("warm_cache");
  });

  it("full-year window routes to warm_cache", () => {
    expect(resolveAutoStrategy("2025-01-01", "2025-12-31")).toBe("warm_cache");
  });

  it("multi-year window routes to warm_cache", () => {
    expect(resolveAutoStrategy("2024-01-01", "2025-12-31")).toBe("warm_cache");
  });
});

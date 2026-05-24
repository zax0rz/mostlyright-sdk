// Backward-compat smoke test: `mergeClimate` re-exported from
// @tradewinds/weather must point at the SAME function as the canonical
// one in @tradewinds/core/internal/merge (TS-W2 Plan 04 migration).

import { describe, expect, it } from "vitest";

import { mergeClimate as fromCore } from "@tradewinds/core/internal/merge";
import { mergeClimate as fromWeather } from "@tradewinds/weather";

describe("mergeClimate — backward-compat re-export", () => {
  it("@tradewinds/weather's mergeClimate is the same function as @tradewinds/core/internal/merge's", () => {
    expect(fromWeather).toBe(fromCore);
  });
});

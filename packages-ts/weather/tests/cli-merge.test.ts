// Backward-compat smoke test: `mergeClimate` re-exported from
// @tradewinds/weather must point at the SAME function as the canonical
// one in @tradewinds/core/internal/merge (TS-W2 Plan 04 migration).

import { describe, expect, it } from "vitest";

import { mergeClimate as fromCore } from "@tradewinds/core/internal/merge";
// Self-import via the package barrel. Vitest's `@tradewinds/weather` alias
// (vitest.config.ts) points at ./src/index.ts so this resolves at test time.
import { mergeClimate as fromWeather } from "../src/index.js";

describe("mergeClimate — backward-compat re-export", () => {
  it("@tradewinds/weather's mergeClimate is the same function as @tradewinds/core/internal/merge's", () => {
    expect(fromWeather).toBe(fromCore);
  });
});

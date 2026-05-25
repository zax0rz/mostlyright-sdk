// Backward-compat smoke test: `mergeClimate` re-exported from
// @mostlyrightmd/weather must point at the SAME function as the canonical
// one in @mostlyrightmd/core/internal/merge (TS-W2 Plan 04 migration).

import { describe, expect, it } from "vitest";

import { mergeClimate as fromCore } from "@mostlyrightmd/core/internal/merge";
// Self-import via the package barrel. Vitest's `@mostlyrightmd/weather` alias
// (vitest.config.ts) points at ./src/index.ts so this resolves at test time.
import { mergeClimate as fromWeather } from "../src/index.js";

describe("mergeClimate — backward-compat re-export", () => {
  it("@mostlyrightmd/weather's mergeClimate is the same function as @mostlyrightmd/core/internal/merge's", () => {
    expect(fromWeather).toBe(fromCore);
  });
});

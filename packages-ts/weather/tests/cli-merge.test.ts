// Backward-compat smoke test: `mergeClimate` re-exported from
// @mostlyright/weather must point at the SAME function as the canonical
// one in @mostlyright/core/internal/merge (TS-W2 Plan 04 migration).

import { describe, expect, it } from "vitest";

import { mergeClimate as fromCore } from "@mostlyright/core/internal/merge";
// Self-import via the package barrel. Vitest's `@mostlyright/weather` alias
// (vitest.config.ts) points at ./src/index.ts so this resolves at test time.
import { mergeClimate as fromWeather } from "../src/index.js";

describe("mergeClimate — backward-compat re-export", () => {
  it("@mostlyright/weather's mergeClimate is the same function as @mostlyright/core/internal/merge's", () => {
    expect(fromWeather).toBe(fromCore);
  });
});

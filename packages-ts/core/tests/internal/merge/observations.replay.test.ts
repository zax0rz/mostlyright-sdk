// Canonical-fetch-order replay test for mergeObservations.
//
// Synthetic mixed-source row sequence representing what a real fetch-order
// would produce (AWC live first, then IEM yearly chunk, then GHCNh yearly
// chunk). Mirrors the order in which `_fetch_observations_range` (Python)
// and `research()` (TS Plan 06) feed rows into the merge function.
//
// Two assertions:
//   1. Cross-run byte-equivalence: identical input → identical JSON output.
//   2. Priority cascade is observable in the survivor source field.
//
// Plan 08 layers an HTTP-recording replay on top (loads real msw recordings
// captured from the parity-fixture date ranges); this test is the unit-level
// determinism floor.

import { describe, expect, it } from "vitest";

import { mergeObservations } from "../../../src/internal/merge/observations.js";

const CANONICAL_ROWS = Object.freeze([
  // AWC chunk (highest priority, fetched first).
  {
    station_code: "NYC",
    observed_at: "2025-01-08T14:51:00Z",
    observation_type: "METAR" as const,
    source: "awc" as const,
  },
  {
    station_code: "NYC",
    observed_at: "2025-01-08T15:51:00Z",
    observation_type: "METAR" as const,
    source: "awc" as const,
  },
  // IEM chunk (priority 2).
  {
    station_code: "NYC",
    observed_at: "2025-01-08T14:51:00Z",
    observation_type: "METAR" as const,
    source: "iem" as const,
  },
  {
    station_code: "NYC",
    observed_at: "2025-01-08T15:51:00Z",
    observation_type: "METAR" as const,
    source: "iem" as const,
  },
  {
    station_code: "NYC",
    observed_at: "2025-01-08T16:51:00Z",
    observation_type: "METAR" as const,
    source: "iem" as const,
  },
  {
    station_code: "NYC",
    observed_at: "2025-01-08T16:55:00Z",
    observation_type: "SPECI" as const,
    source: "iem" as const,
  },
  // GHCNh chunk (priority 1, last in fetch order).
  {
    station_code: "NYC",
    observed_at: "2025-01-08T14:51:00Z",
    observation_type: "METAR" as const,
    source: "ghcnh" as const,
  },
  {
    station_code: "NYC",
    observed_at: "2025-01-08T15:51:00Z",
    observation_type: "METAR" as const,
    source: "ghcnh" as const,
  },
  {
    station_code: "NYC",
    observed_at: "2025-01-08T16:51:00Z",
    observation_type: "METAR" as const,
    source: "ghcnh" as const,
  },
  {
    station_code: "NYC",
    observed_at: "2025-01-08T17:51:00Z",
    observation_type: "METAR" as const,
    source: "ghcnh" as const,
  },
]);

describe("mergeObservations — canonical-fetch-order replay (TS-W2 SC#4)", () => {
  it("produces byte-identical JSON output across runs given identical input order", () => {
    const run1 = JSON.stringify(mergeObservations([...CANONICAL_ROWS]));
    const run2 = JSON.stringify(mergeObservations([...CANONICAL_ROWS]));
    expect(run1).toEqual(run2);
  });

  it("AWC wins over IEM and GHCNh at the same key", () => {
    const merged = mergeObservations([...CANONICAL_ROWS]);
    const at1451 = merged.find(
      (r) => r.observed_at === "2025-01-08T14:51:00Z" && r.observation_type === "METAR",
    );
    expect(at1451?.source).toBe("awc");
  });

  it("IEM wins over GHCNh when AWC is absent", () => {
    const merged = mergeObservations([...CANONICAL_ROWS]);
    const at1651 = merged.find(
      (r) => r.observed_at === "2025-01-08T16:51:00Z" && r.observation_type === "METAR",
    );
    expect(at1651?.source).toBe("iem");
  });

  it("GHCNh survives when neither AWC nor IEM has a row", () => {
    const merged = mergeObservations([...CANONICAL_ROWS]);
    const at1751 = merged.find((r) => r.observed_at === "2025-01-08T17:51:00Z");
    expect(at1751?.source).toBe("ghcnh");
  });

  it("SPECI from IEM is kept separately from METAR (different observation_type key)", () => {
    const merged = mergeObservations([...CANONICAL_ROWS]);
    const speci = merged.filter((r) => r.observation_type === "SPECI");
    expect(speci).toHaveLength(1);
    expect(speci[0]?.source).toBe("iem");
  });

  it("survivor count = 5 (one per unique (key, observation_type))", () => {
    const merged = mergeObservations([...CANONICAL_ROWS]);
    expect(merged).toHaveLength(5);
  });
});

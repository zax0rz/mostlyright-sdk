import { describe, expect, it } from "vitest";

import {
  type ObservationKey,
  SOURCE_PRIORITY,
  mergeObservations,
} from "../../../src/internal/merge/observations.js";

function row(
  station: string,
  observedAt: string,
  type: "METAR" | "SPECI",
  source: "awc" | "iem" | "ghcnh" | string,
  marker?: string,
): ObservationKey & { marker?: string } {
  return {
    station_code: station,
    observed_at: observedAt,
    observation_type: type,
    source,
    ...(marker !== undefined ? { marker } : {}),
  };
}

describe("SOURCE_PRIORITY", () => {
  it("matches Python verbatim {awc: 3, iem: 2, ghcnh: 1}", () => {
    expect(SOURCE_PRIORITY).toEqual({ awc: 3, iem: 2, ghcnh: 1 });
  });

  it("is frozen — consumers cannot mutate the policy at runtime", () => {
    expect(Object.isFrozen(SOURCE_PRIORITY)).toBe(true);
  });
});

describe("mergeObservations — cross-source priority", () => {
  it("AWC > IEM regardless of input order", () => {
    const a = row("NYC", "2025-01-08T14:51:00Z", "METAR", "iem", "iem-first");
    const b = row("NYC", "2025-01-08T14:51:00Z", "METAR", "awc", "awc-second");
    const r1 = mergeObservations([a, b]);
    const r2 = mergeObservations([b, a]);
    expect(r1).toHaveLength(1);
    expect(r2).toHaveLength(1);
    expect(r1[0]?.source).toBe("awc");
    expect(r2[0]?.source).toBe("awc");
  });

  it("IEM > GHCNh", () => {
    const ghcnh = row("NYC", "2025-01-08T14:51:00Z", "METAR", "ghcnh");
    const iem = row("NYC", "2025-01-08T14:51:00Z", "METAR", "iem");
    const merged = mergeObservations([ghcnh, iem]);
    expect(merged).toHaveLength(1);
    expect(merged[0]?.source).toBe("iem");
  });

  it("AWC > IEM > GHCNh end-to-end", () => {
    const all = [
      row("NYC", "2025-01-08T14:51:00Z", "METAR", "ghcnh", "ghcnh"),
      row("NYC", "2025-01-08T14:51:00Z", "METAR", "iem", "iem"),
      row("NYC", "2025-01-08T14:51:00Z", "METAR", "awc", "awc"),
    ];
    const merged = mergeObservations(all);
    expect(merged).toHaveLength(1);
    expect(merged[0]?.source).toBe("awc");
  });
});

describe("mergeObservations — equal-priority first-seen tiebreak", () => {
  it("two IEM rows at same key: first-seen wins", () => {
    const a = row("NYC", "2025-01-08T14:51:00Z", "METAR", "iem", "first");
    const b = row("NYC", "2025-01-08T14:51:00Z", "METAR", "iem", "second");
    const merged = mergeObservations([a, b]) as Array<{ marker?: string }>;
    expect(merged).toHaveLength(1);
    expect(merged[0]?.marker).toBe("first");
  });

  it("reversed input order produces DIFFERENT survivor (Python-faithful order-dependence)", () => {
    const a = row("NYC", "2025-01-08T14:51:00Z", "METAR", "iem", "first");
    const b = row("NYC", "2025-01-08T14:51:00Z", "METAR", "iem", "second");
    const merged = mergeObservations([b, a]) as Array<{ marker?: string }>;
    expect(merged[0]?.marker).toBe("second");
  });
});

describe("mergeObservations — unknown source priority", () => {
  it("unknown source string resolves to priority 0 and loses to any known", () => {
    const unknown = row("NYC", "2025-01-08T14:51:00Z", "METAR", "polymarket");
    const ghcnh = row("NYC", "2025-01-08T14:51:00Z", "METAR", "ghcnh");
    const merged = mergeObservations([unknown, ghcnh]);
    expect(merged[0]?.source).toBe("ghcnh");
  });

  it("two unknown sources at same key: first-seen wins (priority 0 tie)", () => {
    const a = row("NYC", "2025-01-08T14:51:00Z", "METAR", "foo", "first");
    const b = row("NYC", "2025-01-08T14:51:00Z", "METAR", "bar", "second");
    const merged = mergeObservations([a, b]) as Array<{ marker?: string }>;
    expect(merged[0]?.marker).toBe("first");
    expect(merged[0]?.source).toBe("foo");
  });
});

describe("mergeObservations — distinct-key preservation", () => {
  it("different stations: both rows kept", () => {
    const nyc = row("NYC", "2025-01-08T14:51:00Z", "METAR", "iem");
    const ord = row("ORD", "2025-01-08T14:51:00Z", "METAR", "iem");
    const merged = mergeObservations([nyc, ord]);
    expect(merged).toHaveLength(2);
  });

  it("different timestamps: both rows kept", () => {
    const t1 = row("NYC", "2025-01-08T14:51:00Z", "METAR", "iem");
    const t2 = row("NYC", "2025-01-08T15:51:00Z", "METAR", "iem");
    const merged = mergeObservations([t1, t2]);
    expect(merged).toHaveLength(2);
  });

  it("METAR + SPECI at same (station, observed_at): separate keys, both kept", () => {
    const metar = row("NYC", "2025-01-08T14:51:00Z", "METAR", "iem");
    const speci = row("NYC", "2025-01-08T14:51:00Z", "SPECI", "iem");
    const merged = mergeObservations([metar, speci]);
    expect(merged).toHaveLength(2);
  });
});

describe("mergeObservations — boundary cases", () => {
  it("empty input → []", () => {
    expect(mergeObservations([])).toEqual([]);
  });

  it("single row → returned as-is (single-element array)", () => {
    const only = row("NYC", "2025-01-08T14:51:00Z", "METAR", "awc");
    expect(mergeObservations([only])).toEqual([only]);
  });

  it("returns a freshly-allocated array (not the input array)", () => {
    const input = [row("NYC", "2025-01-08T14:51:00Z", "METAR", "awc")];
    const merged = mergeObservations(input);
    expect(merged).not.toBe(input);
  });

  it("output insertion order matches first-seen-key order", () => {
    const rows = [
      row("ORD", "2025-01-08T14:51:00Z", "METAR", "iem"),
      row("NYC", "2025-01-08T14:51:00Z", "METAR", "iem"),
      row("LAX", "2025-01-08T14:51:00Z", "METAR", "iem"),
    ];
    const merged = mergeObservations(rows);
    expect(merged.map((r) => r.station_code)).toEqual(["ORD", "NYC", "LAX"]);
  });
});

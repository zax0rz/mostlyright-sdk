import { beforeEach, describe, expect, it } from "vitest";

import { availability } from "../../src/discovery/availability.js";
import { cacheKeyForClimate, cacheKeyForObservations } from "../../src/internal/cache/keys.js";
import { MemoryStore } from "../../src/internal/cache/memory.js";
import type { CacheStore } from "../../src/internal/cache/types.js";

describe("availability", () => {
  let store: MemoryStore;

  beforeEach(() => {
    store = new MemoryStore();
  });

  // research() writes US-station cache keys under the 3-letter NWS code
  // (e.g. KNYC → NYC), so tests populate the cache that way and query with
  // the user-facing ICAO. The Codex iter-2 P2 fix resolves the ICAO before
  // scanning so the two forms agree.

  it("returns zero-coverage for an empty store", async () => {
    const r = await availability("KNYC", store);
    expect(r).toEqual({
      station: "NYC",
      monthsCached: 0,
      firstMonth: null,
      lastMonth: null,
      climateYears: 0,
      firstClimateYear: null,
      lastClimateYear: null,
    });
  });

  it("normalizes lowercase ICAOs to the canonical NWS code", async () => {
    const r = await availability("knyc", store);
    expect(r.station).toBe("NYC");
  });

  it("rejects invalid station codes", async () => {
    await expect(availability("", store)).rejects.toThrow(RangeError);
    await expect(availability("toolong-station", store)).rejects.toThrow(RangeError);
    await expect(availability("12", store)).rejects.toThrow(RangeError);
    await expect(availability("a b", store)).rejects.toThrow(RangeError);
  });

  it("counts unique observation months ignoring source segment", async () => {
    // Three sources, two months → 2 distinct months (not 6).
    await store.set(cacheKeyForObservations("NYC", 2025, 1, "iem"), { v: 1 });
    await store.set(cacheKeyForObservations("NYC", 2025, 1, "ghcnh"), { v: 1 });
    await store.set(cacheKeyForObservations("NYC", 2025, 1, "awc"), { v: 1 });
    await store.set(cacheKeyForObservations("NYC", 2025, 2, "iem"), { v: 1 });
    await store.set(cacheKeyForObservations("NYC", 2025, 2, "ghcnh"), { v: 1 });

    const r = await availability("KNYC", store);
    expect(r.monthsCached).toBe(2);
    expect(r.firstMonth).toBe("2025-01");
    expect(r.lastMonth).toBe("2025-02");
  });

  it("counts climate years separately from observation months", async () => {
    await store.set(cacheKeyForClimate("NYC", 2023), { v: 1 });
    await store.set(cacheKeyForClimate("NYC", 2024), { v: 1 });
    await store.set(cacheKeyForClimate("NYC", 2025), { v: 1 });
    await store.set(cacheKeyForObservations("NYC", 2025, 6), { v: 1 });

    const r = await availability("KNYC", store);
    expect(r.climateYears).toBe(3);
    expect(r.firstClimateYear).toBe("2023");
    expect(r.lastClimateYear).toBe("2025");
    expect(r.monthsCached).toBe(1);
    expect(r.firstMonth).toBe("2025-06");
  });

  it("scopes results to the requested station", async () => {
    await store.set(cacheKeyForObservations("NYC", 2025, 1), { v: 1 });
    await store.set(cacheKeyForObservations("LAX", 2025, 7), { v: 1 });
    await store.set(cacheKeyForObservations("ORD", 2024, 12), { v: 1 });

    const ny = await availability("KNYC", store);
    expect(ny.monthsCached).toBe(1);
    expect(ny.firstMonth).toBe("2025-01");

    const la = await availability("KLAX", store);
    expect(la.monthsCached).toBe(1);
    expect(la.firstMonth).toBe("2025-07");
  });

  it("returns zero-coverage when the store lacks listKeys", async () => {
    const opaque: CacheStore = {
      async get() {
        return null;
      },
      async set() {},
      async delete() {},
      async withLock<T>(_k: string, fn: () => Promise<T>) {
        return fn();
      },
    };
    const r = await availability("KNYC", opaque);
    expect(r.monthsCached).toBe(0);
    expect(r.climateYears).toBe(0);
    expect(r.firstMonth).toBeNull();
  });

  it("freezes the result so callers can't mutate", async () => {
    const r = await availability("KNYC", store);
    expect(Object.isFrozen(r)).toBe(true);
  });

  it("resolves the input ICAO to the cache-key code (codex iter-2 P2)", async () => {
    // research()'s US cache path writes under the 3-letter NWS code. Calling
    // availability with the user-facing ICAO must still find those entries.
    await store.set(cacheKeyForObservations("NYC", 2025, 3, "iem"), { v: 1 });
    await store.set(cacheKeyForClimate("NYC", 2024), { v: 1 });

    const fromIcao = await availability("KNYC", store);
    const fromCode = await availability("NYC", store);
    expect(fromIcao.monthsCached).toBe(1);
    expect(fromIcao.climateYears).toBe(1);
    expect(fromIcao.station).toBe("NYC");
    expect(fromCode).toEqual(fromIcao);
  });

  it("resolves international stations by ICAO (no NWS code → ICAO is the cache form)", async () => {
    // International stations have null `code`; research() uses ICAO as the
    // cache form. availability should return ICAO for those.
    await store.set(cacheKeyForObservations("EGLL", 2025, 5, "iem"), { v: 1 });
    const r = await availability("EGLL", store);
    expect(r.station).toBe("EGLL");
    expect(r.monthsCached).toBe(1);
  });

  it("passes through unknown codes that satisfy the format", async () => {
    // Bespoke or non-registry codes — pass through upper-cased. Caller
    // is responsible for matching the cache write key.
    await store.set(cacheKeyForObservations("X1Y2", 2025, 1), { v: 1 });
    const r = await availability("x1y2", store);
    expect(r.station).toBe("X1Y2");
    expect(r.monthsCached).toBe(1);
  });
});

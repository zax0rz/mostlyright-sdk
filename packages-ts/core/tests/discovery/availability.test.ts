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

  it("returns zero-coverage for an empty store", async () => {
    const r = await availability("KNYC", store);
    expect(r).toEqual({
      station: "KNYC",
      monthsCached: 0,
      firstMonth: null,
      lastMonth: null,
      climateYears: 0,
      firstClimateYear: null,
      lastClimateYear: null,
    });
  });

  it("normalizes lowercase station codes to upper-case", async () => {
    const r = await availability("knyc", store);
    expect(r.station).toBe("KNYC");
  });

  it("rejects invalid station codes", async () => {
    await expect(availability("", store)).rejects.toThrow(RangeError);
    await expect(availability("toolong-station", store)).rejects.toThrow(RangeError);
    await expect(availability("12", store)).rejects.toThrow(RangeError);
    await expect(availability("a b", store)).rejects.toThrow(RangeError);
  });

  it("counts unique observation months ignoring source segment", async () => {
    // Three sources, two months → 2 distinct months (not 6).
    await store.set(cacheKeyForObservations("KNYC", 2025, 1, "iem"), { v: 1 });
    await store.set(cacheKeyForObservations("KNYC", 2025, 1, "ghcnh"), { v: 1 });
    await store.set(cacheKeyForObservations("KNYC", 2025, 1, "awc"), { v: 1 });
    await store.set(cacheKeyForObservations("KNYC", 2025, 2, "iem"), { v: 1 });
    await store.set(cacheKeyForObservations("KNYC", 2025, 2, "ghcnh"), { v: 1 });

    const r = await availability("KNYC", store);
    expect(r.monthsCached).toBe(2);
    expect(r.firstMonth).toBe("2025-01");
    expect(r.lastMonth).toBe("2025-02");
  });

  it("counts climate years separately from observation months", async () => {
    await store.set(cacheKeyForClimate("KNYC", 2023), { v: 1 });
    await store.set(cacheKeyForClimate("KNYC", 2024), { v: 1 });
    await store.set(cacheKeyForClimate("KNYC", 2025), { v: 1 });
    await store.set(cacheKeyForObservations("KNYC", 2025, 6), { v: 1 });

    const r = await availability("KNYC", store);
    expect(r.climateYears).toBe(3);
    expect(r.firstClimateYear).toBe("2023");
    expect(r.lastClimateYear).toBe("2025");
    expect(r.monthsCached).toBe(1);
    expect(r.firstMonth).toBe("2025-06");
  });

  it("scopes results to the requested station", async () => {
    await store.set(cacheKeyForObservations("KNYC", 2025, 1), { v: 1 });
    await store.set(cacheKeyForObservations("KLAX", 2025, 7), { v: 1 });
    await store.set(cacheKeyForObservations("KORD", 2024, 12), { v: 1 });

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
});

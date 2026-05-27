// Tests for the Phase 21 21-03 versionedCacheStore adapter.

import { describe, expect, it } from "vitest";

import { MemoryStore } from "../../../src/internal/cache/memory.js";
import {
  CACHE_SCHEMA_VERSION,
  type VersionedEntry,
  versionedCacheStore,
  wrapForCache,
} from "../../../src/internal/cache/versionedCacheStore.js";

describe("versionedCacheStore — round-trip + invalidation", () => {
  it("round-trips a value when version matches", async () => {
    const inner = new MemoryStore();
    const wrapped = versionedCacheStore(inner, "v1");
    await wrapped.set("k", { temp_f: 42 });
    expect(await wrapped.get("k")).toEqual({ temp_f: 42 });
  });

  it("returns null on version mismatch (stale entry → cache miss)", async () => {
    const inner = new MemoryStore();
    // Pre-seed the inner store directly with an OLD-version envelope.
    await inner.set("k", wrapForCache({ x: 1 }, "v-old"));
    const reader = versionedCacheStore(inner, "v-new");
    expect(await reader.get("k")).toBeNull();
  });

  it("returns null on missing _cache_schema_version (pre-21-03 entry)", async () => {
    const inner = new MemoryStore();
    // Pre-21-03 cache: raw value, no wrapper.
    await inner.set("k", 42);
    const reader = versionedCacheStore(inner, "v1");
    expect(await reader.get("k")).toBeNull();
  });

  it("returns null on miss (inner returns null)", async () => {
    const inner = new MemoryStore();
    const wrapped = versionedCacheStore(inner, "v1");
    expect(await wrapped.get("never-set")).toBeNull();
  });

  it("set serializes as {value, _cache_schema_version} envelope", async () => {
    const inner = new MemoryStore();
    const wrapped = versionedCacheStore(inner, "v-test");
    await wrapped.set("k", { foo: "bar" });
    const raw = (await inner.get("k")) as VersionedEntry<{ foo: string }>;
    expect(raw).not.toBeNull();
    expect(raw._cache_schema_version).toBe("v-test");
    expect(raw.value).toEqual({ foo: "bar" });
  });

  it("delete passes through to inner", async () => {
    const inner = new MemoryStore();
    const wrapped = versionedCacheStore(inner, "v1");
    await wrapped.set("k", 1);
    expect(await wrapped.get("k")).toBe(1);
    await wrapped.delete("k");
    expect(await wrapped.get("k")).toBeNull();
  });

  it("withLock passes through to inner (serializes per-key)", async () => {
    const inner = new MemoryStore();
    const wrapped = versionedCacheStore(inner, "v1");
    let counter = 0;
    let maxInFlight = 0;
    let inFlight = 0;
    const runOne = () =>
      wrapped.withLock("k", async () => {
        inFlight++;
        maxInFlight = Math.max(maxInFlight, inFlight);
        await new Promise((r) => setTimeout(r, 5));
        counter++;
        inFlight--;
      });
    await Promise.all([runOne(), runOne(), runOne()]);
    expect(counter).toBe(3);
    expect(maxInFlight).toBe(1);
  });

  it("listKeys forwards to inner when supported", async () => {
    const inner = new MemoryStore();
    const wrapped = versionedCacheStore(inner, "v1");
    await wrapped.set("obs/KNYC/2025-01", []);
    await wrapped.set("obs/KLAX/2025-01", []);
    await wrapped.set("climate/KNYC/2024", []);
    const obs = await (
      wrapped as unknown as {
        listKeys(prefix: string): Promise<ReadonlyArray<string>>;
      }
    ).listKeys("obs/");
    expect([...obs].sort()).toEqual(["obs/KLAX/2025-01", "obs/KNYC/2025-01"]);
  });

  it("rejects empty version string at construction", () => {
    const inner = new MemoryStore();
    expect(() => versionedCacheStore(inner, "")).toThrow(TypeError);
  });

  it("CACHE_SCHEMA_VERSION matches Python Phase 18 18-08 exactly", () => {
    // Python: packages/weather/src/mostlyright/weather/cache.py
    //   _cache_schema_version = "v2-phase18-integer-f"
    // Drift here means perpetual cross-language mismatch.
    expect(CACHE_SCHEMA_VERSION).toBe("v2-phase18-integer-f");
  });
});

describe("versionedCacheStore — TTL passthrough", () => {
  it("honors ttlMs via the inner MemoryStore", async () => {
    const inner = new MemoryStore();
    const wrapped = versionedCacheStore(inner, "v1");
    await wrapped.set("k", "x", { ttlMs: 1 });
    await new Promise((r) => setTimeout(r, 10));
    expect(await wrapped.get("k")).toBeNull();
  });
});

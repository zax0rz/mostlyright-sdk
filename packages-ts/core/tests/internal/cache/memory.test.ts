// TS-W3 Plan 01 Task 2 — MemoryStore: contract suite + isolation tests.

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { MemoryStore } from "../../../src/internal/cache/memory.js";
import { runCacheStoreContract } from "./_contract.js";

describe("MemoryStore", () => {
  runCacheStoreContract(() => new MemoryStore());

  describe("instance isolation", () => {
    it("two stores do not share state", async () => {
      const a = new MemoryStore();
      const b = new MemoryStore();
      await a.set("k", 1);
      expect(await b.get("k")).toBeNull();
    });
  });

  describe("value isolation via structuredClone", () => {
    it("mutating an object after set does not change what get returns", async () => {
      const store = new MemoryStore();
      const obj = { count: 1, nested: { x: "hello" } };
      await store.set("k", obj);
      obj.count = 2;
      obj.nested.x = "mutated";
      const got = await store.get<{ count: number; nested: { x: string } }>("k");
      expect(got).toEqual({ count: 1, nested: { x: "hello" } });
    });

    it("mutating the returned value does not affect subsequent gets", async () => {
      const store = new MemoryStore();
      await store.set("k", { count: 1 });
      const first = await store.get<{ count: number }>("k");
      if (first == null) throw new Error("expected stored entry, got null");
      first.count = 999;
      const second = await store.get<{ count: number }>("k");
      expect(second?.count).toBe(1);
    });
  });

  describe("ttlMs", () => {
    beforeEach(() => {
      vi.useFakeTimers();
    });

    afterEach(() => {
      vi.useRealTimers();
    });

    it("non-expired entries return their value", async () => {
      const store = new MemoryStore();
      await store.set("k", "v", { ttlMs: 100 });
      expect(await store.get("k")).toBe("v");
    });

    it("expired entries return null", async () => {
      const store = new MemoryStore();
      await store.set("k", "v", { ttlMs: 100 });
      vi.advanceTimersByTime(200);
      expect(await store.get("k")).toBeNull();
    });
  });
});

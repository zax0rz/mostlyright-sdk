// Shared CacheStore contract suite. Imported by memory.test.ts, fs.test.ts
// (plan 01), and indexeddb.test.ts (plan 02). Lives as a NON-test file
// (`_contract.ts`, not `_contract.test.ts`) so vitest doesn't try to
// execute it standalone — and so biome's noExportsInTest rule doesn't fire.

import { describe, expect, it } from "vitest";

import type { CacheStore } from "../../../src/internal/cache/types.js";
import { lockKeyFor } from "../../../src/internal/cache/types.js";

export function runCacheStoreContract(makeStore: () => CacheStore | Promise<CacheStore>): void {
  describe("CacheStore contract", () => {
    it("round-trip set/get returns the same value", async () => {
      const store = await makeStore();
      await store.set("k", { a: 1, b: "two" });
      const got = await store.get<{ a: number; b: string }>("k");
      expect(got).toEqual({ a: 1, b: "two" });
    });

    it("get on missing key returns null (does NOT throw)", async () => {
      const store = await makeStore();
      const got = await store.get("missing");
      expect(got).toBeNull();
    });

    it("delete on missing key resolves (does NOT throw)", async () => {
      const store = await makeStore();
      await expect(store.delete("missing")).resolves.toBeUndefined();
    });

    it("delete after set causes subsequent get to return null", async () => {
      const store = await makeStore();
      await store.set("k", "hello");
      await store.delete("k");
      const got = await store.get("k");
      expect(got).toBeNull();
    });

    it("withLock serializes nested calls on the same key", async () => {
      const store = await makeStore();
      const events: string[] = [];
      const p1 = store.withLock("shared", async () => {
        events.push("p1-start");
        await new Promise((r) => setTimeout(r, 20));
        events.push("p1-end");
        return 1;
      });
      const p2 = store.withLock("shared", async () => {
        events.push("p2-start");
        events.push("p2-end");
        return 2;
      });
      const [r1, r2] = await Promise.all([p1, p2]);
      expect(r1).toBe(1);
      expect(r2).toBe(2);
      // p2 must start AFTER p1 ends — proves serialization.
      expect(events).toEqual(["p1-start", "p1-end", "p2-start", "p2-end"]);
    });

    it("withLock releases on fn throw (subsequent withLock with same key resolves)", async () => {
      const store = await makeStore();
      await expect(
        store.withLock("k", async () => {
          throw new Error("intentional");
        }),
      ).rejects.toThrow("intentional");
      // The lock must have been released — this second call must complete.
      const result = await store.withLock("k", async () => "ok");
      expect(result).toBe("ok");
    });

    it("set with ttlMs in the past, get returns null", async () => {
      const store = await makeStore();
      await store.set("k", "v", { ttlMs: -1 }); // already expired
      const got = await store.get("k");
      expect(got).toBeNull();
    });

    it("stored objects are isolated by value (post-set mutation does not leak)", async () => {
      const store = await makeStore();
      const obj = { count: 1 };
      await store.set("k", obj);
      obj.count = 999;
      const got = await store.get<{ count: number }>("k");
      expect(got?.count).toBe(1);
    });
  });

  describe("lockKeyFor (via contract suite)", () => {
    it("returns the canonical lock id", () => {
      expect(lockKeyFor("foo")).toBe("tradewinds:cache:lock:foo");
    });

    it("is pure (same input → same output)", () => {
      expect(lockKeyFor("x")).toBe(lockKeyFor("x"));
    });
  });
}

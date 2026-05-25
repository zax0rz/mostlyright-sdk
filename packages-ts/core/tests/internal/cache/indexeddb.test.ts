// TS-W3 Plan 02 Task 1 — IndexedDBStore: shared contract + IDB-specific tests.
//
// Routed through jsdom + fake-indexeddb (see vitest.config.ts
// environmentMatchGlobs + setup-fake-indexeddb.ts).

import { randomUUID } from "node:crypto";

import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { DB_NAME, IndexedDBStore } from "../../../src/internal/cache/indexeddb.js";
import { runCacheStoreContract } from "./_contract.js";

describe("IndexedDBStore", () => {
  runCacheStoreContract(() => new IndexedDBStore({ dbName: `tw-test-${randomUUID()}` }));

  it("DB_NAME constant matches the canonical wire value", () => {
    expect(DB_NAME).toBe("mostlyright-cache-v1");
  });

  describe("DB name isolation", () => {
    it("two instances with the SAME dbName share state", async () => {
      const dbName = `tw-test-${randomUUID()}`;
      const a = new IndexedDBStore({ dbName });
      await a.set("k", "value-from-a");
      const b = new IndexedDBStore({ dbName });
      expect(await b.get("k")).toBe("value-from-a");
    });

    it("two instances with DIFFERENT dbName are isolated", async () => {
      const a = new IndexedDBStore({ dbName: `tw-test-${randomUUID()}` });
      const b = new IndexedDBStore({ dbName: `tw-test-${randomUUID()}` });
      await a.set("k", 1);
      expect(await b.get("k")).toBeNull();
    });
  });

  describe("withLock fallback (no navigator.locks)", () => {
    let originalLocks: unknown;
    beforeEach(() => {
      // jsdom doesn't ship navigator.locks; ensure absence to exercise
      // the in-process promise-chain fallback.
      const nav = navigator as unknown as { locks?: unknown };
      originalLocks = nav.locks;
      nav.locks = undefined;
    });
    afterEach(() => {
      const nav = navigator as unknown as { locks?: unknown };
      if (originalLocks !== undefined) nav.locks = originalLocks;
    });

    it("nested withLock calls serialize via the promise chain", async () => {
      const store = new IndexedDBStore({ dbName: `tw-test-${randomUUID()}` });
      const events: string[] = [];
      const p1 = store.withLock("shared", async () => {
        events.push("p1-start");
        await new Promise((r) => setTimeout(r, 20));
        events.push("p1-end");
      });
      const p2 = store.withLock("shared", async () => {
        events.push("p2-start");
        events.push("p2-end");
      });
      await Promise.all([p1, p2]);
      expect(events).toEqual(["p1-start", "p1-end", "p2-start", "p2-end"]);
    });
  });

  describe("ttlMs lazy eviction", () => {
    it("expired entry returns null AND is removed from the store", async () => {
      // Use a real sleep instead of vi.useFakeTimers — fake-indexeddb's
      // internal scheduling depends on microtask/setTimeout being real,
      // and stubbing them stalls every db.get() call indefinitely.
      const store = new IndexedDBStore({ dbName: `tw-test-${randomUUID()}` });
      await store.set("k", "v", { ttlMs: 10 });
      await new Promise((r) => setTimeout(r, 50));
      expect(await store.get("k")).toBeNull();
      // Re-set fresh value to confirm the slot is reusable post-eviction.
      await store.set("k", "fresh");
      expect(await store.get("k")).toBe("fresh");
    });
  });
});

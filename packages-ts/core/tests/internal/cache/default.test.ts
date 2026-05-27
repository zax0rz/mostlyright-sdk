// TS-W3 Plan 02 Task 2 — defaultCacheStore() runtime auto-detection tests.
// Routed through jsdom so the IndexedDB branch is exercisable.
//
// Iter-1 H3: defaultCacheStore is now async — FsStore is loaded via
// dynamic `import('./fs.js')` behind a `process.versions?.node` guard to
// keep `node:fs/promises` & friends out of browser / MV3 bundles. Tests
// now `await` the call.

import { afterEach, beforeEach, describe, expect, it } from "vitest";

// Iter-2 H5: FsStore no longer re-exported from the cache barrel
// (the re-export pulled node:fs/promises etc. into the browser
// subbundle). Import directly from the fs module — production Node
// callers should use the dedicated subpath
// `@mostlyrightmd/core/internal/cache/fs`.
import { FsStore } from "../../../src/internal/cache/fs.js";
import {
  IndexedDBStore,
  MemoryStore,
  defaultCacheStore,
} from "../../../src/internal/cache/index.js";
import type { CacheStore } from "../../../src/internal/cache/types.js";

/**
 * Phase 21 21-03 fix-iter-1: `defaultCacheStore()` now returns a
 * `VersionedCacheStore` wrapper around the concrete backend so stale
 * pre-Phase-18 cache entries silently miss. To assert which concrete
 * backend was selected, peek through the wrapper via the
 * `__peekInner()` test seam (versionedCacheStore.ts).
 */
function innerOf(store: CacheStore): CacheStore {
  const maybe = store as CacheStore & { __peekInner?: () => CacheStore };
  if (typeof maybe.__peekInner === "function") {
    return maybe.__peekInner();
  }
  return store;
}

describe("defaultCacheStore()", () => {
  it("returns IndexedDBStore when indexedDB is present (jsdom + fake-indexeddb)", async () => {
    expect(innerOf(await defaultCacheStore())).toBeInstanceOf(IndexedDBStore);
  });

  describe("FsStore fallback (no indexedDB, Node process present)", () => {
    let originalIdb: unknown;
    beforeEach(() => {
      originalIdb = (globalThis as Record<string, unknown>).indexedDB;
      (globalThis as Record<string, unknown>).indexedDB = undefined as unknown;
      // Use `delete` semantics — assigning undefined keeps `typeof X !== "undefined"` true.
      (globalThis as Record<string, unknown>).indexedDB = undefined;
    });
    afterEach(() => {
      if (originalIdb !== undefined) {
        (globalThis as Record<string, unknown>).indexedDB = originalIdb;
      }
    });

    it("returns FsStore when indexedDB is absent and process.versions.node is present", async () => {
      expect(innerOf(await defaultCacheStore())).toBeInstanceOf(FsStore);
    });
  });

  describe("MemoryStore fallback (neither indexedDB nor Node)", () => {
    let originalIdb: unknown;
    let originalProcess: unknown;
    beforeEach(() => {
      originalIdb = (globalThis as Record<string, unknown>).indexedDB;
      originalProcess = (globalThis as Record<string, unknown>).process;
      (globalThis as Record<string, unknown>).indexedDB = undefined;
      (globalThis as Record<string, unknown>).process = undefined;
    });
    afterEach(() => {
      // Restore — vitest itself uses process; leaving it deleted breaks teardown.
      if (originalProcess !== undefined) {
        (globalThis as Record<string, unknown>).process = originalProcess;
      }
      if (originalIdb !== undefined) {
        (globalThis as Record<string, unknown>).indexedDB = originalIdb;
      }
    });

    it("returns MemoryStore when no runtime markers are present", async () => {
      expect(innerOf(await defaultCacheStore())).toBeInstanceOf(MemoryStore);
    });
  });

  it("each call returns a NEW instance (not a singleton)", async () => {
    const a = await defaultCacheStore();
    const b = await defaultCacheStore();
    expect(a).not.toBe(b);
  });

  // Phase 21 21-03 fix-iter-1: lock in that defaultCacheStore() returns a
  // version-wrapped store. If a future refactor strips the wrap, this test
  // catches it before stale-cache regressions ship.
  it("wraps the concrete store in a versioned cache adapter", async () => {
    const store = await defaultCacheStore();
    // The wrapper installs __peekInner; the unwrapped store does not.
    expect(typeof (store as { __peekInner?: unknown }).__peekInner).toBe("function");
    // Write/read round-trip via the wrapper still works.
    await store.set("phase21-21-03-smoke", { x: 1 });
    const back = await store.get<{ x: number }>("phase21-21-03-smoke");
    expect(back).toEqual({ x: 1 });
    await store.delete("phase21-21-03-smoke");
  });
});

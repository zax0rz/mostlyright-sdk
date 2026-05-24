// TS-W3 Plan 02 Task 2 — defaultCacheStore() runtime auto-detection tests.
// Routed through jsdom so the IndexedDB branch is exercisable.

import { afterEach, beforeEach, describe, expect, it } from "vitest";

import {
  FsStore,
  IndexedDBStore,
  MemoryStore,
  defaultCacheStore,
} from "../../../src/internal/cache/index.js";

describe("defaultCacheStore()", () => {
  it("returns IndexedDBStore when indexedDB is present (jsdom + fake-indexeddb)", () => {
    expect(defaultCacheStore()).toBeInstanceOf(IndexedDBStore);
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

    it("returns FsStore when indexedDB is absent and process.versions.node is present", () => {
      expect(defaultCacheStore()).toBeInstanceOf(FsStore);
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

    it("returns MemoryStore when no runtime markers are present", () => {
      expect(defaultCacheStore()).toBeInstanceOf(MemoryStore);
    });
  });

  it("each call returns a NEW instance (not a singleton)", () => {
    const a = defaultCacheStore();
    const b = defaultCacheStore();
    expect(a).not.toBe(b);
  });
});

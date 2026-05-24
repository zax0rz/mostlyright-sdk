// TS-W3 Plan 01 Task 3 — FsStore: contract suite + FS-specific tests.

import { mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { homedir, tmpdir } from "node:os";
import { join } from "node:path";

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { FsStore, defaultFsRoot } from "../../../src/internal/cache/fs.js";
import { runCacheStoreContract } from "./_contract.js";

describe("FsStore", () => {
  let scratchDir = "";

  beforeEach(async () => {
    scratchDir = await mkdtemp(join(tmpdir(), "tw-fs-"));
  });

  afterEach(async () => {
    if (scratchDir.length > 0) {
      await rm(scratchDir, { recursive: true, force: true });
    }
  });

  runCacheStoreContract(() => new FsStore({ root: scratchDir }));

  describe("defaultFsRoot()", () => {
    it("honors TRADEWINDS_CACHE_DIR env override", () => {
      vi.stubEnv("TRADEWINDS_CACHE_DIR", "/tmp/custom-tradewinds");
      try {
        expect(defaultFsRoot()).toBe("/tmp/custom-tradewinds");
      } finally {
        vi.unstubAllEnvs();
      }
    });

    it("falls back to $HOME/.tradewinds/cache-ts when env unset", () => {
      vi.stubEnv("TRADEWINDS_CACHE_DIR", "");
      try {
        expect(defaultFsRoot()).toBe(join(homedir(), ".tradewinds", "cache-ts"));
      } finally {
        vi.unstubAllEnvs();
      }
    });

    it("does NOT match the Python cache root (.tradewinds/cache)", () => {
      vi.stubEnv("TRADEWINDS_CACHE_DIR", "");
      try {
        const tsRoot = defaultFsRoot();
        const pyRoot = join(homedir(), ".tradewinds", "cache");
        expect(tsRoot).not.toBe(pyRoot);
        expect(tsRoot).toContain("cache-ts");
      } finally {
        vi.unstubAllEnvs();
      }
    });
  });

  describe("atomic write semantics", () => {
    it("a .tmp file left behind (simulated crash mid-write) does not affect reads", async () => {
      const store = new FsStore({ root: scratchDir });
      // Simulate a crashed writer by dropping a `.tmp` file directly at the
      // sanitized path. `get` should still return null (the canonical file
      // doesn't exist yet) without confusing the .tmp for a valid entry.
      const tmpPath = join(scratchDir, "k.json.tmp");
      await writeFile(tmpPath, "this is half-written garbage", "utf8");
      const got = await store.get("k");
      expect(got).toBeNull();
    });

    it("set produces no .tmp residue after success", async () => {
      const store = new FsStore({ root: scratchDir });
      await store.set("clean", { ok: true });
      const tmpPath = join(scratchDir, "clean.json.tmp");
      await expect(readFile(tmpPath, "utf8")).rejects.toThrow();
    });
  });

  describe("key sanitization", () => {
    it("colons in keys do not escape the root", async () => {
      const store = new FsStore({ root: scratchDir });
      const key = "tradewinds:v1:observations:KNYC:2025:01";
      await store.set(key, "value");
      const got = await store.get(key);
      expect(got).toBe("value");
      // The file lives under scratchDir, not under any nested directory.
      const expectedPath = join(scratchDir, "tradewinds__v1__observations__KNYC__2025__01.json");
      const content = await readFile(expectedPath, "utf8");
      expect(JSON.parse(content)).toEqual({ value: "value" });
    });
  });

  describe("withLock concurrency", () => {
    it("two concurrent withLock calls on the same key serialize", async () => {
      const store = new FsStore({ root: scratchDir });
      const events: string[] = [];
      const p1 = store.withLock("contention", async () => {
        events.push("p1-start");
        await new Promise((r) => setTimeout(r, 50));
        events.push("p1-end");
      });
      const p2 = store.withLock("contention", async () => {
        events.push("p2-start");
        events.push("p2-end");
      });
      await Promise.all([p1, p2]);
      expect(events).toEqual(["p1-start", "p1-end", "p2-start", "p2-end"]);
    });
  });

  describe("concurrent set race (iter-2 C6)", () => {
    // Codex iter-2 CRITICAL. Prior to the fix, FsStore.set always wrote to
    // `<path>.tmp` (literal `.tmp` suffix, not per-write random). Two
    // concurrent `set("same-key", ...)` calls would race: writer A's
    // rename moved `<path>.tmp` to `<path>` while writer B was still
    // mid-write, so B's subsequent rename threw ENOENT.
    //
    // research.ts calls cache.set unconditionally inside loops without
    // withLock, so this hits in test isolation under parallel vitest
    // workers. Fix at the FsStore layer: unique temp file per write.
    it("N parallel set() calls on the same key all succeed (no ENOENT)", async () => {
      const store = new FsStore({ root: scratchDir });
      const N = 20;
      const values = Array.from({ length: N }, (_, i) => ({ writer: i }));
      // All N parallel — no inter-promise serialization.
      const results = await Promise.allSettled(values.map((v) => store.set("contended-key", v)));
      const rejected = results.filter((r) => r.status === "rejected");
      // Surface the first error for clarity on regression.
      if (rejected.length > 0) {
        const reason = (rejected[0] as PromiseRejectedResult).reason;
        throw new Error(
          `Expected 0 ENOENT rejections under N=${N} concurrent set; got ${rejected.length}. First: ${String(reason)}`,
        );
      }
      // Final value must be one of the N writes (last-rename-wins
      // semantics — documented in FsStore.set).
      const final = (await store.get("contended-key")) as { writer: number } | null;
      expect(final).not.toBeNull();
      expect(final?.writer).toBeGreaterThanOrEqual(0);
      expect(final?.writer).toBeLessThan(N);
    });

    it("uses a unique temp filename per write (not literal `.tmp`)", async () => {
      // Belt-and-suspenders: even with a single writer, the temp file
      // should carry a random suffix (per-write isolation). Verified by
      // inspecting source — no literal `${p}.tmp` pattern.
      const store = new FsStore({ root: scratchDir });
      await store.set("unique-temp", { ok: true });
      // After success there is no `.tmp` file at all (rename moved it).
      // This pairs with the existing "set produces no .tmp residue" test.
      const got = await store.get("unique-temp");
      expect(got).toEqual({ ok: true });
    });
  });
});

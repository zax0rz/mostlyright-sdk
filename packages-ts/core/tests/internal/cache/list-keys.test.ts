import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";

import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { FsStore } from "../../../src/internal/cache/fs.js";
import { MemoryStore } from "../../../src/internal/cache/memory.js";

describe("MemoryStore.listKeys", () => {
  it("returns only keys with the requested prefix", async () => {
    const store = new MemoryStore();
    await store.set("a:1", { v: 1 });
    await store.set("a:2", { v: 2 });
    await store.set("b:1", { v: 3 });

    const aKeys = await store.listKeys("a:");
    expect([...aKeys].sort()).toEqual(["a:1", "a:2"]);
    const bKeys = await store.listKeys("b:");
    expect(bKeys).toEqual(["b:1"]);
  });

  it("omits expired entries (and evicts them)", async () => {
    const store = new MemoryStore();
    await store.set("a:1", { v: 1 }, { ttlMs: 1 });
    await store.set("a:2", { v: 2 });
    // Wait past the TTL window so eviction triggers.
    await new Promise((r) => setTimeout(r, 5));
    const keys = await store.listKeys("a:");
    expect(keys).toEqual(["a:2"]);
    // The expired key is gone from the underlying map as well — a fresh
    // `get` returns null without resurrection.
    expect(await store.get("a:1")).toBeNull();
  });

  it("returns empty for an empty store", async () => {
    const store = new MemoryStore();
    expect(await store.listKeys("anything:")).toEqual([]);
  });
});

describe("FsStore.listKeys", () => {
  let root: string;
  let store: FsStore;

  beforeEach(async () => {
    root = await mkdtemp(join(tmpdir(), "tw-fs-list-"));
    store = new FsStore({ root });
  });

  afterEach(async () => {
    await rm(root, { recursive: true, force: true });
  });

  it("returns empty when the root directory does not exist", async () => {
    const fresh = new FsStore({ root: join(root, "nonexistent") });
    expect(await fresh.listKeys("a:")).toEqual([]);
  });

  it("returns decoded keys with the requested prefix", async () => {
    await store.set("mostlyright:v1:observations:KNYC:2025:01", { v: 1 });
    await store.set("mostlyright:v1:observations:KNYC:2025:02", { v: 2 });
    await store.set("mostlyright:v1:climate:KNYC:2024", { v: 3 });
    await store.set("mostlyright:v1:observations:KLAX:2025:01", { v: 4 });

    const obs = await store.listKeys("mostlyright:v1:observations:KNYC:");
    expect([...obs].sort()).toEqual([
      "mostlyright:v1:observations:KNYC:2025:01",
      "mostlyright:v1:observations:KNYC:2025:02",
    ]);
  });

  it("survives URI-decode failures by skipping malformed names", async () => {
    // Place a file the SDK didn't write — should be skipped silently.
    const { writeFile } = await import("node:fs/promises");
    await writeFile(join(root, "%E0%A4%A.json"), '{"value":null}', "utf8");
    await store.set("mostlyright:v1:observations:KNYC:2025:01", { v: 1 });
    const out = await store.listKeys("mostlyright:");
    expect(out).toEqual(["mostlyright:v1:observations:KNYC:2025:01"]);
  });
});

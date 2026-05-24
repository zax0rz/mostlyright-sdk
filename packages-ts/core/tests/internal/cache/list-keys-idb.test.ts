// TS-W6 — IndexedDBStore.listKeys (jsdom + fake-indexeddb).
// Lives in a separate file from the Node-only list-keys.test.ts so vitest's
// `environmentMatchGlobs` keeps the IDB tests on jsdom.

import { randomUUID } from "node:crypto";

import { describe, expect, it } from "vitest";

import { IndexedDBStore } from "../../../src/internal/cache/indexeddb.js";

describe("IndexedDBStore.listKeys", () => {
  it("returns only keys with the requested prefix", async () => {
    const store = new IndexedDBStore({ dbName: `tw-test-list-${randomUUID()}` });
    await store.set("tradewinds:v1:observations:KNYC:2025:01", { v: 1 });
    await store.set("tradewinds:v1:observations:KNYC:2025:02", { v: 2 });
    await store.set("tradewinds:v1:observations:KLAX:2025:01", { v: 3 });
    await store.set("tradewinds:v1:climate:KNYC:2024", { v: 4 });

    const obs = await store.listKeys("tradewinds:v1:observations:KNYC:");
    expect([...obs].sort()).toEqual([
      "tradewinds:v1:observations:KNYC:2025:01",
      "tradewinds:v1:observations:KNYC:2025:02",
    ]);
  });

  it("returns empty when nothing matches the prefix", async () => {
    const store = new IndexedDBStore({ dbName: `tw-test-list-${randomUUID()}` });
    expect(await store.listKeys("nothing:")).toEqual([]);
  });
});

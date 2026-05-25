// TS-W3 Plan 01 Task 1 — standalone tests for the CacheStore type module.
// Per-implementation contract suites live in memory.test.ts, fs.test.ts,
// and indexeddb.test.ts (plan 02). They consume `runCacheStoreContract`
// from `./_contract.ts`.

import { describe, expect, it } from "vitest";

import { lockKeyFor } from "../../../src/internal/cache/types.js";

describe("lockKeyFor (standalone)", () => {
  it("returns the canonical lock id with the mostlyright:cache:lock: prefix", () => {
    expect(lockKeyFor("foo")).toBe("mostlyright:cache:lock:foo");
  });

  it("preserves the full key (no truncation, no normalization)", () => {
    const longKey = "mostlyright:v1:observations:KNYC:2025:01";
    expect(lockKeyFor(longKey)).toBe(`mostlyright:cache:lock:${longKey}`);
  });

  it("is pure (deterministic)", () => {
    expect(lockKeyFor("x")).toBe(lockKeyFor("x"));
    expect(lockKeyFor("y")).not.toBe(lockKeyFor("z"));
  });

  it("accepts the empty string", () => {
    expect(lockKeyFor("")).toBe("mostlyright:cache:lock:");
  });
});

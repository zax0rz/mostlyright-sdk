import { MemoryStore } from "@mostlyright/core/internal/cache";
import { describe, expect, it } from "vitest";

import {
  invalidateTradesCache,
  isCurrentUtcMonth,
  isFutureUtcMonth,
  readTradesCache,
  tradesCacheKey,
  writeTradesCache,
} from "../../src/trades/index.js";

describe("tradesCacheKey", () => {
  it("builds canonical key", () => {
    expect(
      tradesCacheKey({
        issuer: "kalshi",
        ticker: "KXHIGHNY-25MAY26-T79",
        year: 2026,
        month: 5,
      }),
    ).toBe("trades/kalshi/KXHIGHNY-25MAY26-T79/2026-05");
  });

  it("rejects uppercase issuer", () => {
    expect(() => tradesCacheKey({ issuer: "Kalshi", ticker: "KX", year: 2026, month: 5 })).toThrow(
      RangeError,
    );
  });

  it("rejects path-traversal ticker", () => {
    expect(() =>
      tradesCacheKey({ issuer: "kalshi", ticker: "../../etc/passwd", year: 2026, month: 5 }),
    ).toThrow(RangeError);
  });

  // Iter-2 codex + python-architect HIGH: TS regex parity with Python.
  it("rejects all-dot ticker `.`", () => {
    expect(() => tradesCacheKey({ issuer: "kalshi", ticker: ".", year: 2026, month: 5 })).toThrow(
      RangeError,
    );
  });

  it("rejects all-dot ticker `..`", () => {
    expect(() => tradesCacheKey({ issuer: "kalshi", ticker: "..", year: 2026, month: 5 })).toThrow(
      RangeError,
    );
  });

  it("rejects all-dot ticker `...`", () => {
    expect(() => tradesCacheKey({ issuer: "kalshi", ticker: "...", year: 2026, month: 5 })).toThrow(
      RangeError,
    );
  });

  it("rejects ticker with slash", () => {
    expect(() =>
      tradesCacheKey({ issuer: "kalshi", ticker: "KX/EVIL", year: 2026, month: 5 }),
    ).toThrow(RangeError);
  });

  it("rejects year out of range", () => {
    expect(() => tradesCacheKey({ issuer: "kalshi", ticker: "KX", year: 1999, month: 5 })).toThrow(
      RangeError,
    );
  });

  it("rejects month out of range", () => {
    expect(() => tradesCacheKey({ issuer: "kalshi", ticker: "KX", year: 2026, month: 13 })).toThrow(
      RangeError,
    );
  });
});

describe("month predicates", () => {
  it("isCurrentUtcMonth detects current UTC month", () => {
    const now = new Date("2026-06-15T00:00:00Z");
    expect(isCurrentUtcMonth(2026, 6, now)).toBe(true);
    expect(isCurrentUtcMonth(2026, 5, now)).toBe(false);
    expect(isCurrentUtcMonth(2026, 7, now)).toBe(false);
  });

  it("isFutureUtcMonth detects future months/years", () => {
    const now = new Date("2026-06-15T00:00:00Z");
    expect(isFutureUtcMonth(2026, 7, now)).toBe(true);
    expect(isFutureUtcMonth(2027, 1, now)).toBe(true);
    expect(isFutureUtcMonth(2026, 6, now)).toBe(false);
    expect(isFutureUtcMonth(2026, 5, now)).toBe(false);
  });
});

describe("readTradesCache / writeTradesCache", () => {
  it("current UTC month: write returns false, read returns null", async () => {
    const cache = new MemoryStore();
    const now = new Date("2026-06-15T00:00:00Z");
    const key = { issuer: "kalshi", ticker: "KX", year: 2026, month: 6 };
    const wrote = await writeTradesCache(cache, key, [{ a: 1 }], { now });
    expect(wrote).toBe(false);
    const got = await readTradesCache(cache, key, { now });
    expect(got).toBeNull();
  });

  it("future month: write returns false", async () => {
    const cache = new MemoryStore();
    const now = new Date("2026-06-15T00:00:00Z");
    const wrote = await writeTradesCache(
      cache,
      { issuer: "kalshi", ticker: "KX", year: 2026, month: 7 },
      [{ a: 1 }],
      { now },
    );
    expect(wrote).toBe(false);
  });

  it("past month: roundtrip", async () => {
    const cache = new MemoryStore();
    const now = new Date("2026-06-15T00:00:00Z");
    const key = { issuer: "kalshi", ticker: "KX", year: 2026, month: 5 };
    const rows = [
      { tradeId: "t1", price: 50 },
      { tradeId: "t2", price: 52 },
    ];
    const wrote = await writeTradesCache(cache, key, rows, { now });
    expect(wrote).toBe(true);
    const got = await readTradesCache(cache, key, { now });
    expect(got).toEqual(rows);
  });

  it("empty rows: write returns false", async () => {
    const cache = new MemoryStore();
    const now = new Date("2026-06-15T00:00:00Z");
    const wrote = await writeTradesCache(
      cache,
      { issuer: "kalshi", ticker: "KX", year: 2026, month: 5 },
      [],
      { now },
    );
    expect(wrote).toBe(false);
  });

  it("missing key: read returns null", async () => {
    const cache = new MemoryStore();
    const now = new Date("2026-06-15T00:00:00Z");
    const got = await readTradesCache(
      cache,
      { issuer: "kalshi", ticker: "KX", year: 2026, month: 5 },
      { now },
    );
    expect(got).toBeNull();
  });
});

describe("invalidateTradesCache", () => {
  it("returns true when an entry was deleted", async () => {
    const cache = new MemoryStore();
    const now = new Date("2026-06-15T00:00:00Z");
    const key = { issuer: "kalshi", ticker: "KX", year: 2026, month: 5 };
    await writeTradesCache(cache, key, [{ a: 1 }], { now });
    const removed = await invalidateTradesCache(cache, key);
    expect(removed).toBe(true);
    const after = await readTradesCache(cache, key, { now });
    expect(after).toBeNull();
  });

  it("returns false when no entry existed", async () => {
    const cache = new MemoryStore();
    const removed = await invalidateTradesCache(cache, {
      issuer: "kalshi",
      ticker: "KX",
      year: 2026,
      month: 5,
    });
    expect(removed).toBe(false);
  });
});

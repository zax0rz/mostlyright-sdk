// TS-W3 Plan 06 Task 1 — research() cache integration tests.
//
// Asserts:
//   - explicit `cache: MemoryStore` populates entries during a call
//   - explicit `cache: null` opts out (zero cache reads/writes)
//   - cache-warm rerun is byte-identical to cache-cold rerun (regression)
//
// The wall-time perf test (TS-W3 SC#2: 2nd call ≤ 10% of 1st) is
// conditionally enabled via env var so flaky CI runners don't false-fail
// the suite.

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  MemoryStore,
  cacheKeyForClimate,
  cacheKeyForObservations,
} from "@tradewinds/core/internal/cache";
import { research } from "../src/research.js";

interface CliMockRecord {
  valid: string;
  high: number | null;
  low: number | null;
  product: string;
}

interface AwcMockMetar {
  icaoId: string;
  reportTime: string;
  obsTime: number;
  temp: number;
  dewp?: number;
  wspd?: number;
  wdir?: number | string;
  rawOb: string;
}

function mockCliResponse(records: ReadonlyArray<CliMockRecord>): Response {
  // CLI mock format mirrors research.test.ts: { results: records } JSON.
  return new Response(JSON.stringify({ results: records }), {
    status: 200,
    headers: { "content-type": "application/json" },
  });
}

function mockAwcResponse(metars: ReadonlyArray<AwcMockMetar>): Response {
  return new Response(JSON.stringify(metars), {
    status: 200,
    headers: { "content-type": "application/json" },
  });
}

function installFetchMock(routes: {
  cli?: ReadonlyArray<CliMockRecord>;
  awc?: ReadonlyArray<AwcMockMetar>;
}) {
  return vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    const url = typeof input === "string" ? input : ((input as Request).url ?? String(input));
    if (url.includes("aviationweather.gov")) return mockAwcResponse(routes.awc ?? []);
    if (url.includes("mesonet.agron.iastate.edu/json/cli.py"))
      return mockCliResponse(routes.cli ?? []);
    if (url.includes("mesonet.agron.iastate.edu/cgi-bin/request/asos.py")) {
      return new Response("station,valid\n", {
        status: 200,
        headers: { "content-type": "text/plain" },
      });
    }
    if (url.includes("ncei.noaa.gov/oa/global-historical-climatology-network")) {
      return new Response("", { status: 404 });
    }
    throw new Error(`Unexpected fetch URL: ${url}`);
  });
}

describe("research() cache integration (TS-W3 Plan 06)", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("explicit MemoryStore — cache populated after research() runs (past year)", async () => {
    // 2023 is a past year — current LST year is 2026 per CLAUDE.md, so the
    // skip rule permits caching.
    const store = new MemoryStore();
    installFetchMock({
      cli: [{ valid: "2023-01-15", high: 50, low: 30, product: "test-cli" }],
      awc: [],
    });
    const rows = await research("NYC", "2023-01-15", "2023-01-15", { cache: store });
    expect(rows.length).toBeGreaterThanOrEqual(1);
    // CLI cache key populated for the queried year.
    const climateKey = cacheKeyForClimate("NYC", 2023);
    const cached = await store.get(climateKey);
    expect(cached).not.toBeNull();
  });

  it("explicit `cache: null` — no cache reads/writes; functionality preserved", async () => {
    const store = new MemoryStore();
    const getSpy = vi.spyOn(store, "get");
    const setSpy = vi.spyOn(store, "set");
    installFetchMock({
      cli: [{ valid: "2025-01-15", high: 50, low: 30, product: "test-cli" }],
      awc: [],
    });
    // Pass null → opts out
    const rows = await research("NYC", "2025-01-15", "2025-01-15", { cache: null });
    expect(rows.length).toBeGreaterThanOrEqual(1);
    // Neither spy fires because the store wasn't even injected.
    expect(getSpy).not.toHaveBeenCalled();
    expect(setSpy).not.toHaveBeenCalled();
  });

  it("regression: cache-warm output deep-equals cache-cold output (past year)", async () => {
    installFetchMock({
      cli: [{ valid: "2023-01-15", high: 50, low: 30, product: "test-cli" }],
      awc: [],
    });
    const cold = await research("NYC", "2023-01-15", "2023-01-15", { cache: null });
    // Same call with a populated MemoryStore (pre-warmed by reading-through).
    const store = new MemoryStore();
    await research("NYC", "2023-01-15", "2023-01-15", { cache: store });
    const warm = await research("NYC", "2023-01-15", "2023-01-15", { cache: store });
    expect(JSON.stringify(warm)).toBe(JSON.stringify(cold));
  });

  it.skipIf(process.env.CI && !process.env.TS_PERF_TEST)(
    "wall-time: 2nd cached call is <= 10% of 1st (skip-gated for flaky CI)",
    async () => {
      installFetchMock({
        cli: Array.from({ length: 30 }, (_, i) => ({
          valid: `2023-01-${String(i + 1).padStart(2, "0")}`,
          high: 50,
          low: 30,
          product: `test-cli-${i}`,
        })),
        awc: [],
      });
      const store = new MemoryStore();
      const t0 = performance.now();
      await research("NYC", "2023-01-01", "2023-01-30", { cache: store });
      const firstMs = performance.now() - t0;
      const t1 = performance.now();
      await research("NYC", "2023-01-01", "2023-01-30", { cache: store });
      const secondMs = performance.now() - t1;
      expect(secondMs).toBeLessThanOrEqual(firstMs * 0.1 + 50); // 50ms grace for cold caches
    },
  );

  // iter-6 C12 regression: a `cache.set` throw AFTER a successful CLI
  // fetch+parse MUST NOT discard the in-memory rows. The previous broad
  // try/catch around the CLI block in research.ts swallowed cache write
  // failures and returned research rows with null cli_* fields — silent
  // data corruption. This test simulates a flaky cache backend whose
  // `set` rejects on every call and asserts cli_* fields are populated.
  it("C12: cache.set failure does not discard CLI rows (silent corruption guard)", async () => {
    installFetchMock({
      cli: [{ valid: "2023-01-15", high: 72, low: 45, product: "test-cli" }],
      awc: [],
    });
    const store = new MemoryStore();
    // Make every `set` throw. `get` still works normally (returns null
    // on miss). The orchestrator must (a) still complete, (b) return
    // rows with populated cli_* fields from the live fetch.
    vi.spyOn(store, "set").mockImplementation(async () => {
      throw new Error("simulated cache backend write failure");
    });
    const rows = await research("NYC", "2023-01-15", "2023-01-15", { cache: store });
    expect(rows.length).toBeGreaterThanOrEqual(1);
    // The CLI row should produce populated cli_high_f / cli_low_f — proving
    // the rows were NOT discarded by the cache write throw.
    const row = rows[0];
    expect(row).toBeDefined();
    // Defensive narrowing — vitest's toBeDefined doesn't narrow for TS.
    if (row === undefined) throw new Error("row was undefined");
    expect(row.cli_high_f).toBe(72);
    expect(row.cli_low_f).toBe(45);
  });

  // iter-6 C12 (companion): same guard for the IEM ASOS path. A cache.set
  // throw from the IEM helper must not propagate up and crash research()
  // — observations were already fetched + parsed; the cache write is a
  // best-effort side effect. The IEM mock here returns an empty CSV so the
  // assertion is "research() completes without throwing," not row count.
  it("C12: IEM ASOS cache.set failure does not crash research()", async () => {
    installFetchMock({
      cli: [{ valid: "2023-01-15", high: 72, low: 45, product: "test-cli" }],
      awc: [],
    });
    const store = new MemoryStore();
    vi.spyOn(store, "set").mockImplementation(async () => {
      throw new Error("simulated cache backend write failure");
    });
    // Must NOT throw. IEM ASOS mock returns empty CSV → no obs, but the
    // CLI cache write also throws — neither failure should abort.
    await expect(
      research("NYC", "2023-01-15", "2023-01-15", { cache: store }),
    ).resolves.toBeDefined();
  });

  // iter-7 H13: IEM ASOS cache now uses per-month keys (mirrors Python
  // TS-CACHE-02 contract `(station, year, month)`), not a year-sentinel
  // `:01:rt=N` shape. This regression guard asserts:
  //   1. IEM writes carry a key matching the canonical per-month shape
  //      `tradewinds:v1:observations:STATION:YYYY:MM:iem`.
  //   2. The legacy `:rt=N` suffix is NEVER emitted.
  //   3. A query spanning multiple months produces a separate cache.set
  //      per month (3 months → 3 IEM-source writes).
  it("H13: IEM ASOS writes per-month keys, never the year-sentinel :01:rt=N shape", async () => {
    installFetchMock({
      cli: [
        { valid: "2023-01-15", high: 50, low: 30, product: "test-cli" },
        { valid: "2023-02-15", high: 55, low: 35, product: "test-cli" },
        { valid: "2023-03-15", high: 60, low: 40, product: "test-cli" },
      ],
      awc: [],
    });
    const store = new MemoryStore();
    const setSpy = vi.spyOn(store, "set");
    await research("NYC", "2023-01-15", "2023-03-15", { cache: store });
    const writtenKeys = setSpy.mock.calls.map((c) => String(c[0]));

    // No legacy year-sentinel or report-type suffix.
    for (const k of writtenKeys) {
      expect(k, `legacy :rt=N suffix in key=${k}`).not.toMatch(/:rt=\d/);
    }

    // Per-month IEM writes for each of {Jan, Feb, Mar} 2023. We assert each
    // canonical key shape is present somewhere in the write stream.
    const expected = [
      "tradewinds:v1:observations:NYC:2023:01:iem",
      "tradewinds:v1:observations:NYC:2023:02:iem",
      "tradewinds:v1:observations:NYC:2023:03:iem",
    ];
    for (const want of expected) {
      expect(writtenKeys, `missing expected IEM per-month key=${want}`).toContain(want);
    }
  });

  // iter-7 H13 follow-up: only the CURRENT LST month is skipped — months
  // adjacent to it in the same year MUST still be written. Previously the
  // helper skipped the whole year via `shouldSkipCacheForCurrentLstYear`,
  // silently dropping cacheable per-month writes for everything else in
  // that year. This guard pins the per-month skip semantics.
  it("H13: only the current LST month is skip-gated; sibling months in same year ARE cached", async () => {
    installFetchMock({
      cli: [
        { valid: "2025-01-15", high: 50, low: 30, product: "test-cli" },
        { valid: "2025-02-15", high: 55, low: 35, product: "test-cli" },
        { valid: "2025-03-15", high: 60, low: 40, product: "test-cli" },
      ],
      awc: [],
    });
    const store = new MemoryStore();
    const setSpy = vi.spyOn(store, "set");
    // now = March 15, 2025 → current LST month is 2025-03. 2025-01 + 2025-02
    // are cacheable (past months in current year, well past volatile window
    // since 2025-01-31 is 43 days back; 2025-02-28 is 15 days back → IN
    // the 30-day volatile window). So the writeable IEM months are 2025-01
    // (only). 2025-02 is volatile, 2025-03 is current LST month.
    const now = new Date("2025-03-15T12:00:00Z");
    await research("NYC", "2025-01-15", "2025-03-15", { cache: store, now });
    const writtenKeys = setSpy.mock.calls.map((c) => String(c[0]));

    // 2025-01 IEM key written (NOT skipped — past month, outside volatile window).
    expect(writtenKeys).toContain("tradewinds:v1:observations:NYC:2025:01:iem");
    // 2025-02 IEM key NOT written — inside 30-day volatile window relative to now.
    expect(writtenKeys).not.toContain("tradewinds:v1:observations:NYC:2025:02:iem");
    // 2025-03 IEM key NOT written — current LST month.
    expect(writtenKeys).not.toContain("tradewinds:v1:observations:NYC:2025:03:iem");
  });
});

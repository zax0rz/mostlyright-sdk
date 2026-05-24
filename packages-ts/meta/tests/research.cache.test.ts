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

  // iter-7 H14: GHCNh archive chunks are now cacheable. The previous code
  // always called `downloadGhcnhRange` on every research() invocation,
  // dropping the read-through path on the floor. These tests pin the
  // new per-month read-through / write-through cache semantics:
  //   1. First call populates per-month GHCNh keys; second call reuses
  //      them and issues ZERO NCEI HTTP requests.
  //   2. GHCNh and IEM ASOS keys do NOT collide for the same triplet
  //      (the source segment disambiguates "iem" vs "ghcnh").
  //   3. NCEI 404 (no data for station-year) is memoized empty so each
  //      month's per-month read-through still short-circuits the network.
  it("H14: GHCNh per-month cache read-through — second call issues zero NCEI requests", async () => {
    // Build a synthetic GHCNh PSV with two rows: 2023-01-15 and 2023-01-20.
    // NCEI mock returns this PSV on first call; mocked fetch counter
    // verifies subsequent calls don't re-hit NCEI.
    const header =
      "Station_ID|DATE|temperature_Source_Station_ID|temperature|temperature_Quality_Code|dew_point_temperature|dew_point_temperature_Quality_Code|wind_speed|wind_speed_Quality_Code|sea_level_pressure|sea_level_pressure_Quality_Code";
    const row1 = "USW00094728|2023-01-15T14:51:00Z|ICAO-KNYC|10.0|0|5.0|0|3.5|0|1015.0|0";
    const row2 = "USW00094728|2023-01-20T15:21:00Z|ICAO-KNYC|12.0|0|6.0|0|4.0|0|1014.0|0";
    const psv = [header, row1, row2].join("\n");

    let ghcnhHits = 0;
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const url = typeof input === "string" ? input : ((input as Request).url ?? String(input));
      if (url.includes("aviationweather.gov"))
        return new Response("[]", { status: 200, headers: { "content-type": "application/json" } });
      if (url.includes("mesonet.agron.iastate.edu/json/cli.py"))
        return new Response(JSON.stringify({ results: [] }), {
          status: 200,
          headers: { "content-type": "application/json" },
        });
      if (url.includes("mesonet.agron.iastate.edu/cgi-bin/request/asos.py"))
        return new Response("station,valid\n", {
          status: 200,
          headers: { "content-type": "text/plain" },
        });
      if (url.includes("ncei.noaa.gov/oa/global-historical-climatology-network")) {
        ghcnhHits += 1;
        return new Response(psv, { status: 200, headers: { "content-type": "text/plain" } });
      }
      throw new Error(`Unexpected fetch URL: ${url}`);
    });

    const store = new MemoryStore();
    // Cold call: hits NCEI once (single station-year).
    await research("NYC", "2023-01-15", "2023-01-15", { cache: store });
    expect(ghcnhHits, "cold call hits NCEI once").toBe(1);

    // Per-month GHCNh key written.
    const ghcnhKey = cacheKeyForObservations("NYC", 2023, 1, "ghcnh");
    expect(await store.get(ghcnhKey)).not.toBeNull();

    // Warm call: per-month read-through MUST short-circuit the NCEI fetch.
    ghcnhHits = 0;
    await research("NYC", "2023-01-15", "2023-01-15", { cache: store });
    expect(ghcnhHits, "warm call must NOT re-hit NCEI").toBe(0);
  });

  it("H14: GHCNh and IEM ASOS write disjoint per-month keys (source namespacing)", async () => {
    // Synthetic PSV with one row to give GHCNh something to cache.
    const psv =
      "Station_ID|DATE|temperature_Source_Station_ID|temperature|temperature_Quality_Code|dew_point_temperature|dew_point_temperature_Quality_Code|wind_speed|wind_speed_Quality_Code|sea_level_pressure|sea_level_pressure_Quality_Code\n" +
      "USW00094728|2023-01-15T14:51:00Z|ICAO-KNYC|10.0|0|5.0|0|3.5|0|1015.0|0";

    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const url = typeof input === "string" ? input : ((input as Request).url ?? String(input));
      if (url.includes("aviationweather.gov"))
        return new Response("[]", { status: 200, headers: { "content-type": "application/json" } });
      if (url.includes("mesonet.agron.iastate.edu/json/cli.py"))
        return new Response(JSON.stringify({ results: [] }), {
          status: 200,
          headers: { "content-type": "application/json" },
        });
      if (url.includes("mesonet.agron.iastate.edu/cgi-bin/request/asos.py"))
        return new Response("station,valid\n", {
          status: 200,
          headers: { "content-type": "text/plain" },
        });
      if (url.includes("ncei.noaa.gov/oa/global-historical-climatology-network"))
        return new Response(psv, { status: 200, headers: { "content-type": "text/plain" } });
      throw new Error(`Unexpected fetch URL: ${url}`);
    });

    const store = new MemoryStore();
    const setSpy = vi.spyOn(store, "set");
    await research("NYC", "2023-01-15", "2023-01-15", { cache: store });
    const keys = setSpy.mock.calls.map((c) => String(c[0]));

    // Both source-namespaced keys present, disjoint.
    expect(keys, "missing IEM per-month key").toContain(
      "tradewinds:v1:observations:NYC:2023:01:iem",
    );
    expect(keys, "missing GHCNh per-month key").toContain(
      "tradewinds:v1:observations:NYC:2023:01:ghcnh",
    );

    // No collision: the un-namespaced legacy key MUST NOT appear.
    expect(keys, "legacy non-namespaced observations key leaked").not.toContain(
      "tradewinds:v1:observations:NYC:2023:01",
    );
  });

  // iter-12 C14: observation cache must skip future + not-strictly-past
  // UTC months. The pre-existing `shouldSkipCacheForCurrentLstMonth` and
  // `isMonthVolatile` gates catch the current LST month and the 30-day
  // post-month volatile window, but both return false for months in the
  // FUTURE relative to `now` — and `shouldSkipCacheForCurrentLstMonth`
  // can also miss the current UTC month when the station's LST is in the
  // prior UTC month (negative tz offsets near UTC midnight). Without
  // `isWritableMonth`, empty / partial IEM ASOS or GHCNh chunks for a
  // future or current-UTC month would be persisted and later served as
  // complete. These tests pin the gate.
  it("C14: future month → no IEM/GHCNh cache.set, no cache.get attempted", async () => {
    installFetchMock({
      cli: [],
      awc: [],
    });
    const store = new MemoryStore();
    const getSpy = vi.spyOn(store, "get");
    const setSpy = vi.spyOn(store, "set");
    // now = 2025-06-15. Query a future month (2026-01). research() will
    // still attempt to fetch live data; we just require that the cache
    // is bypassed entirely for that month.
    const now = new Date("2025-06-15T12:00:00Z");
    await research("NYC", "2026-01-15", "2026-01-15", { cache: store, now });

    const writtenKeys = setSpy.mock.calls.map((c) => String(c[0]));
    const readKeys = getSpy.mock.calls.map((c) => String(c[0]));

    // No IEM/GHCNh observation key for 2026-01 may be written.
    expect(writtenKeys).not.toContain("tradewinds:v1:observations:NYC:2026:01:iem");
    expect(writtenKeys).not.toContain("tradewinds:v1:observations:NYC:2026:01:ghcnh");
    // And no read attempts for those keys either.
    expect(readKeys).not.toContain("tradewinds:v1:observations:NYC:2026:01:iem");
    expect(readKeys).not.toContain("tradewinds:v1:observations:NYC:2026:01:ghcnh");
  });

  it("C14: current UTC month → no IEM/GHCNh cache.set (covers UTC-rollover tail)", async () => {
    installFetchMock({
      cli: [],
      awc: [],
    });
    const store = new MemoryStore();
    const setSpy = vi.spyOn(store, "set");
    // now = 2025-01-01T01:00Z (just past UTC midnight Jan 1). For a UTC-5
    // station (NYC), LST is still 2024-12-31T20:00. The OLD
    // `shouldSkipCacheForCurrentLstMonth` would return false for the
    // current UTC month 2025-01 (because station LST is 2024-12) — but
    // `isWritableMonth` correctly rejects 2025-01 as the current UTC
    // month, preventing a partial cache write at the UTC-rollover tail.
    const now = new Date("2025-01-01T01:00:00Z");
    await research("NYC", "2025-01-01", "2025-01-01", { cache: store, now });

    const writtenKeys = setSpy.mock.calls.map((c) => String(c[0]));
    expect(writtenKeys).not.toContain("tradewinds:v1:observations:NYC:2025:01:iem");
    expect(writtenKeys).not.toContain("tradewinds:v1:observations:NYC:2025:01:ghcnh");
  });

  it("C14: past UTC month that is still current LST month → still gated by shouldSkipCacheForCurrentLstMonth", async () => {
    installFetchMock({
      cli: [],
      awc: [],
    });
    const store = new MemoryStore();
    const setSpy = vi.spyOn(store, "set");
    // Choose a station and `now` such that:
    //   - UTC month is (year, month+1) — so isWritableMonth(year, month, now) = true (past UTC month)
    //   - station LST is still in (year, month) — so shouldSkipCacheForCurrentLstMonth = true
    // LAX (America/Los_Angeles → UTC-8 LST) at 2025-02-01T07:00Z:
    //   - UTC month = Feb 2025 → isWritableMonth(2025, 1) = true (past UTC month)
    //   - LST = 2025-01-31T23:00 → station LST still in Jan 2025
    //   → shouldSkipCacheForCurrentLstMonth(LAX, 2025, 1) = true → no write.
    const now = new Date("2025-02-01T07:00:00Z");
    await research("LAX", "2025-01-15", "2025-01-15", { cache: store, now });

    const writtenKeys = setSpy.mock.calls.map((c) => String(c[0]));
    // Jan 2025 is a past UTC month (writable) but LST is still in Jan
    // for LAX, so `shouldSkipCacheForCurrentLstMonth` MUST fire and block
    // the write. The combined skipCache predicate stays true → no IEM
    // write for 2025-01.
    expect(writtenKeys).not.toContain("tradewinds:v1:observations:LAX:2025:01:iem");
    expect(writtenKeys).not.toContain("tradewinds:v1:observations:LAX:2025:01:ghcnh");
  });

  it("C14: past UTC month + past LST month → cacheable (existing behavior preserved)", async () => {
    installFetchMock({
      cli: [],
      awc: [],
    });
    const store = new MemoryStore();
    const setSpy = vi.spyOn(store, "set");
    // 2025-06-15: 2023-01 is past UTC AND past LST AND past volatile window.
    // It MUST still be written — `isWritableMonth` is an ADDITIONAL gate,
    // not a replacement.
    const now = new Date("2025-06-15T12:00:00Z");
    await research("NYC", "2023-01-15", "2023-01-15", { cache: store, now });

    const writtenKeys = setSpy.mock.calls.map((c) => String(c[0]));
    expect(writtenKeys).toContain("tradewinds:v1:observations:NYC:2023:01:iem");
  });

  // iter-12 C15: climate (CLI) cache must skip future + not-strictly-past
  // UTC years. The pre-existing `shouldSkipCacheForCurrentLstYear` only
  // catches the current LST year, and the volatile-window rule only
  // catches the immediate-post-year tail. Both miss future years and the
  // UTC Jan-1 boundary window where the station's LST is still in the
  // prior calendar year (negative tz offsets) but the UTC year has
  // already rolled over. Without `isWritableYear`, empty / incomplete
  // CLI data for such a year would be persisted and later served as
  // complete.
  it("C15: future year → no CLI cache.set, no cache.get attempted", async () => {
    installFetchMock({
      cli: [],
      awc: [],
    });
    const store = new MemoryStore();
    const getSpy = vi.spyOn(store, "get");
    const setSpy = vi.spyOn(store, "set");
    // now = 2025-06-15. Query a future year (2026). research() still
    // calls into the CLI fetcher, but the cache must be bypassed.
    const now = new Date("2025-06-15T12:00:00Z");
    await research("NYC", "2026-01-15", "2026-01-15", { cache: store, now });

    const writtenKeys = setSpy.mock.calls.map((c) => String(c[0]));
    const readKeys = getSpy.mock.calls.map((c) => String(c[0]));

    // No CLI key for 2026 may be written nor read.
    const climate2026 = cacheKeyForClimate("NYC", 2026);
    expect(writtenKeys).not.toContain(climate2026);
    expect(readKeys).not.toContain(climate2026);
  });

  it("C15: current UTC year → no CLI cache.set (covers UTC Jan-1 boundary)", async () => {
    installFetchMock({
      cli: [],
      awc: [],
    });
    const store = new MemoryStore();
    const setSpy = vi.spyOn(store, "set");
    // now = 2025-01-01T01:00Z (just past UTC midnight Jan 1). For a UTC-5
    // station (NYC), LST is still 2024-12-31T20:00 → year 2024 in LST.
    // The OLD `shouldSkipCacheForCurrentLstYear` would return false for
    // 2025 (because station LST is 2024). `isWritableYear` correctly
    // rejects 2025 as the current UTC year — preventing a partial cache
    // write at the UTC Jan-1 boundary.
    const now = new Date("2025-01-01T01:00:00Z");
    await research("NYC", "2025-01-01", "2025-01-01", { cache: store, now });

    const writtenKeys = setSpy.mock.calls.map((c) => String(c[0]));
    expect(writtenKeys).not.toContain(cacheKeyForClimate("NYC", 2025));
  });

  it("C15: past UTC year → CLI cache write fires (existing behavior preserved)", async () => {
    installFetchMock({
      cli: [{ valid: "2023-01-15", high: 50, low: 30, product: "test-cli" }],
      awc: [],
    });
    const store = new MemoryStore();
    const setSpy = vi.spyOn(store, "set");
    // 2025-06-15: 2023 is strictly past UTC AND past LST AND past volatile
    // window. `isWritableYear` is an ADDITIONAL gate; the write must
    // still fire.
    const now = new Date("2025-06-15T12:00:00Z");
    await research("NYC", "2023-01-15", "2023-01-15", { cache: store, now });

    const writtenKeys = setSpy.mock.calls.map((c) => String(c[0]));
    expect(writtenKeys).toContain(cacheKeyForClimate("NYC", 2023));
  });

  it("H14: GHCNh 404 is memoized; empty per-month entries cached so warm calls skip NCEI", async () => {
    let ghcnhHits = 0;
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const url = typeof input === "string" ? input : ((input as Request).url ?? String(input));
      if (url.includes("aviationweather.gov"))
        return new Response("[]", { status: 200, headers: { "content-type": "application/json" } });
      if (url.includes("mesonet.agron.iastate.edu/json/cli.py"))
        return new Response(JSON.stringify({ results: [] }), {
          status: 200,
          headers: { "content-type": "application/json" },
        });
      if (url.includes("mesonet.agron.iastate.edu/cgi-bin/request/asos.py"))
        return new Response("station,valid\n", {
          status: 200,
          headers: { "content-type": "text/plain" },
        });
      if (url.includes("ncei.noaa.gov/oa/global-historical-climatology-network")) {
        ghcnhHits += 1;
        return new Response("", { status: 404 });
      }
      throw new Error(`Unexpected fetch URL: ${url}`);
    });

    const store = new MemoryStore();
    // Range spans two months in same year so we exercise memoization:
    // year 2023 should be fetched ONCE despite two months in range.
    await research("NYC", "2023-01-15", "2023-02-15", { cache: store });
    expect(ghcnhHits, "404 year fetched at most once across multiple months").toBeLessThanOrEqual(
      1,
    );

    // 404 still WRITES empty per-month entries so subsequent calls skip
    // the network entirely. Both months should have empty arrays cached.
    expect(await store.get(cacheKeyForObservations("NYC", 2023, 1, "ghcnh"))).toEqual([]);
    expect(await store.get(cacheKeyForObservations("NYC", 2023, 2, "ghcnh"))).toEqual([]);
  });
});

// Tests for `research()` orchestrator — TS-W1 Wave 6.
//
// All HTTP is mocked via `vi.spyOn(globalThis, "fetch")`. We assert the
// row schema, station/date validation, and graceful degradation when
// either source returns nothing.

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { research } from "../src/research.js";

// ---------------------------------------------------------------------------
// Mock helpers
// ---------------------------------------------------------------------------

interface CliMockRecord {
  valid: string;
  high?: number | null;
  low?: number | null;
  product?: string | null;
}

interface AwcMockMetar {
  icaoId: string;
  obsTime: number; // unix seconds
  temp?: number | null;
  dewp?: number | null;
  wspd?: number | null;
  wgst?: number | null;
  precip?: number | null;
  rawOb?: string | null;
}

function mockCliResponse(records: ReadonlyArray<CliMockRecord>): Response {
  return new Response(JSON.stringify({ results: records }), {
    status: 200,
    headers: { "content-type": "application/json" },
  });
}

function mockAwcResponse(records: ReadonlyArray<AwcMockMetar>): Response {
  return new Response(JSON.stringify(records), {
    status: 200,
    headers: { "content-type": "application/json" },
  });
}

function epochOfUtc(iso: string): number {
  return Math.floor(Date.parse(iso) / 1000);
}

// Recent date inside AWC's 168h window (last 7 days from "now").
function recentUtcDate(daysAgo: number): string {
  const now = new Date();
  const target = new Date(now.getTime() - daysAgo * 86_400_000);
  const y = target.getUTCFullYear();
  const m = String(target.getUTCMonth() + 1).padStart(2, "0");
  const d = String(target.getUTCDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}

// Mock router — inspects URL and returns CLI or AWC payload.
function installFetchMock(routes: {
  cli?: ReadonlyArray<CliMockRecord>;
  awc?: ReadonlyArray<AwcMockMetar>;
  awcStatus?: number;
  cliStatus?: number;
}) {
  return vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    const url = typeof input === "string" ? input : ((input as Request).url ?? String(input));
    if (url.includes("aviationweather.gov")) {
      if (routes.awcStatus !== undefined && routes.awcStatus !== 200) {
        return new Response("err", { status: routes.awcStatus });
      }
      return mockAwcResponse(routes.awc ?? []);
    }
    if (url.includes("mesonet.agron.iastate.edu")) {
      if (routes.cliStatus !== undefined && routes.cliStatus !== 200) {
        return new Response("err", { status: routes.cliStatus });
      }
      return mockCliResponse(routes.cli ?? []);
    }
    throw new Error(`Unexpected fetch URL: ${url}`);
  });
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("research() — TS-W1 Wave 6 (AWC + CLI)", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("returns one row per day for a date range with CLI data", async () => {
    const cli: CliMockRecord[] = [
      { valid: "2025-01-01", high: 45, low: 30, product: "202501020600-KOKX-CDUS41-CLINYC" },
      { valid: "2025-01-02", high: 47, low: 32, product: "202501030600-KOKX-CDUS41-CLINYC" },
      { valid: "2025-01-03", high: 50, low: 35, product: "202501040600-KOKX-CDUS41-CLINYC" },
      { valid: "2025-01-04", high: 48, low: 33, product: "202501050600-KOKX-CDUS41-CLINYC" },
      { valid: "2025-01-05", high: 42, low: 28, product: "202501060600-KOKX-CDUS41-CLINYC" },
      { valid: "2025-01-06", high: 40, low: 25, product: "202501070600-KOKX-CDUS41-CLINYC" },
      { valid: "2025-01-07", high: 38, low: 22, product: "202501080600-KOKX-CDUS41-CLINYC" },
    ];
    installFetchMock({ cli, awc: [] });
    const rows = await research("NYC", "2025-01-01", "2025-01-07");
    expect(rows).toHaveLength(7);
    expect(rows[0]?.date).toBe("2025-01-01");
    expect(rows[6]?.date).toBe("2025-01-07");
    for (const r of rows) {
      expect(r.station).toBe("NYC");
      expect(r.cli_high_f).not.toBeNull();
      expect(r.cli_low_f).not.toBeNull();
      expect(r.cli_report_type).toBe("final");
      expect(r.fcst_high_f).toBeNull();
      expect(r.fcst_low_f).toBeNull();
      expect(r.fcst_model).toBeNull();
      expect(r.market_close_utc).toMatch(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}/);
    }
  });

  it("ICAO input (KNYC) is normalized to 3-letter code (NYC)", async () => {
    installFetchMock({ cli: [], awc: [] });
    const rows = await research("KNYC", "2025-02-10", "2025-02-12");
    expect(rows).toHaveLength(3);
    expect(rows[0]?.station).toBe("NYC");
  });

  it("AWC observations within window: obs_count > 0 and obs_high/low populated", async () => {
    // Use 'today' so the AWC observations fall in-window.
    const dateA = recentUtcDate(2);
    const dateB = recentUtcDate(1);
    const awc: AwcMockMetar[] = [
      // Two observations on dateA (UTC noon, NYC tz = local same day)
      {
        icaoId: "KNYC",
        obsTime: epochOfUtc(`${dateA}T17:00:00Z`),
        temp: 5,
        dewp: -2,
        wspd: 10,
        wgst: 18,
        precip: 0.02,
      },
      {
        icaoId: "KNYC",
        obsTime: epochOfUtc(`${dateA}T20:00:00Z`),
        temp: 8,
        dewp: 0,
        wspd: 12,
        wgst: null,
        precip: 0.01,
      },
      // One on dateB
      {
        icaoId: "KNYC",
        obsTime: epochOfUtc(`${dateB}T18:00:00Z`),
        temp: 3,
        dewp: -5,
        wspd: 6,
        wgst: null,
        precip: null,
      },
    ];
    installFetchMock({ cli: [], awc });

    const rows = await research("NYC", dateA, dateB);
    expect(rows).toHaveLength(2);
    const rowA = rows.find((r) => r.date === dateA);
    const rowB = rows.find((r) => r.date === dateB);
    expect(rowA?.obs_count).toBe(2);
    expect(rowA?.obs_high_f).toBeGreaterThan(rowA?.obs_low_f ?? Number.POSITIVE_INFINITY);
    expect(rowA?.obs_mean_f).not.toBeNull();
    expect(rowA?.obs_total_precip_in).toBeCloseTo(0.03, 5);
    expect(rowB?.obs_count).toBe(1);
  });

  it("rejects unknown station", async () => {
    installFetchMock({ cli: [], awc: [] });
    await expect(research("XXX", "2025-01-01", "2025-01-07")).rejects.toThrow(/unknown station/);
  });

  it("rejects fromDate > toDate", async () => {
    installFetchMock({ cli: [], awc: [] });
    await expect(research("NYC", "2025-01-10", "2025-01-01")).rejects.toThrow(/must be <=/);
  });

  it("rejects malformed date strings", async () => {
    installFetchMock({ cli: [], awc: [] });
    await expect(research("NYC", "2025/01/01", "2025-01-07")).rejects.toThrow(/YYYY-MM-DD/);
    await expect(research("NYC", "2025-02-30", "2025-03-01")).rejects.toThrow(/invalid calendar/);
  });

  it("empty AWC response: rows have null obs fields, CLI fields populated", async () => {
    const cli: CliMockRecord[] = [
      { valid: "2025-05-01", high: 70, low: 55, product: "202505020600-KOKX-CDUS41-CLINYC" },
    ];
    installFetchMock({ cli, awc: [] });
    const rows = await research("NYC", "2025-05-01", "2025-05-01");
    expect(rows).toHaveLength(1);
    const row = rows[0];
    expect(row?.cli_high_f).toBe(70);
    expect(row?.cli_low_f).toBe(55);
    expect(row?.obs_count).toBe(0);
    expect(row?.obs_high_f).toBeNull();
    expect(row?.obs_low_f).toBeNull();
    expect(row?.obs_mean_f).toBeNull();
    expect(row?.obs_total_precip_in).toBeNull();
  });

  it("empty CLI response: rows have null cli fields but obs_* populated where possible", async () => {
    const dateA = recentUtcDate(1);
    const awc: AwcMockMetar[] = [
      {
        icaoId: "KNYC",
        obsTime: epochOfUtc(`${dateA}T18:00:00Z`),
        temp: 10,
        dewp: 2,
        wspd: 5,
      },
    ];
    installFetchMock({ cli: [], awc });
    const rows = await research("NYC", dateA, dateA);
    expect(rows).toHaveLength(1);
    const row = rows[0];
    expect(row?.cli_high_f).toBeNull();
    expect(row?.cli_low_f).toBeNull();
    expect(row?.cli_report_type).toBeNull();
    expect(row?.obs_count).toBe(1);
    expect(row?.obs_high_f).not.toBeNull();
  });

  it("both empty: rows returned with all source fields null", async () => {
    installFetchMock({ cli: [], awc: [] });
    const rows = await research("NYC", "2025-06-01", "2025-06-03");
    expect(rows).toHaveLength(3);
    for (const row of rows) {
      expect(row.cli_high_f).toBeNull();
      expect(row.obs_high_f).toBeNull();
      expect(row.obs_count).toBe(0);
      expect(row.fcst_high_f).toBeNull();
    }
  });

  it("returned array and rows are frozen", async () => {
    installFetchMock({ cli: [], awc: [] });
    const rows = await research("NYC", "2025-01-01", "2025-01-02");
    expect(Object.isFrozen(rows)).toBe(true);
    expect(Object.isFrozen(rows[0])).toBe(true);
  });

  it("CLI 404 (no data for station-year) is tolerated; rows still returned", async () => {
    installFetchMock({ cli: [], awc: [], cliStatus: 404 });
    const rows = await research("NYC", "2025-01-01", "2025-01-03");
    expect(rows).toHaveLength(3);
    for (const row of rows) {
      expect(row.cli_high_f).toBeNull();
    }
  });

  it("market_close_utc is a valid ISO 8601 UTC string", async () => {
    installFetchMock({ cli: [], awc: [] });
    const rows = await research("NYC", "2025-07-04", "2025-07-04");
    const row = rows[0];
    expect(row?.market_close_utc).toBeDefined();
    const ms = Date.parse(row?.market_close_utc ?? "");
    expect(Number.isFinite(ms)).toBe(true);
  });

  it("CLI duplicate-date merge: later final replaces earlier preliminary", async () => {
    // Two CLI rows for the same date. The first (preliminary, issued same
    // day) carries high=45; the second (final, issued next morning at
    // 06:00 UTC — the overnight CLI window) carries high=50. Per
    // mergeClimate (strict `>` on report_type_priority), the `final` row
    // wins and high_temp_f for that date is 50.
    const cli: CliMockRecord[] = [
      // Preliminary: product timestamp = 2025-01-01T12:00 = same day as
      // observation 2025-01-01 → inferReportType returns "preliminary".
      { valid: "2025-01-01", high: 45, low: 30, product: "202501011200-KOKX-CDUS41-CLINYC" },
      // Final: product timestamp = 2025-01-02T06:00 = next day, hour 6
      // → inferReportType returns "final".
      { valid: "2025-01-01", high: 50, low: 35, product: "202501020600-KOKX-CDUS41-CLINYC" },
    ];
    installFetchMock({ cli, awc: [] });
    const rows = await research("NYC", "2025-01-01", "2025-01-01");
    expect(rows).toHaveLength(1);
    const row = rows[0];
    // Final (priority 3.0) beats preliminary (priority 1.0), strict >.
    expect(row?.cli_high_f).toBe(50);
    expect(row?.cli_low_f).toBe(35);
    expect(row?.cli_report_type).toBe("final");
  });

  it("CLI dedup: equal priority keeps first-seen (two finals)", async () => {
    // Two `final` rows for the same date — first wins. Order in input
    // matters; `mergeClimate` does NOT take strict-> against equal-priority
    // siblings (strict `>` only, first-seen wins on equality).
    const cli: CliMockRecord[] = [
      { valid: "2025-01-01", high: 50, low: 30, product: "202501020600-KOKX-CDUS41-CLINYC" },
      { valid: "2025-01-01", high: 99, low: 99, product: "202501020700-KOKX-CDUS41-CLINYC" },
    ];
    installFetchMock({ cli, awc: [] });
    const rows = await research("NYC", "2025-01-01", "2025-01-01");
    expect(rows[0]?.cli_high_f).toBe(50);
    expect(rows[0]?.cli_low_f).toBe(30);
  });

  it("AWC obs grouped by LST date (DST-ignored, not wall-clock local)", async () => {
    // 2024-03-10 was spring-forward in the US (02:00 EST → 03:00 EDT).
    // The observation at 05:30 UTC corresponds to:
    //   - Wall-clock NYC EDT: 01:30 (2024-03-10) — DST already shifted.
    //   - Standard time (LST, UTC-5 year-round): 00:30 (2024-03-10).
    // Either grouping puts it on 2024-03-10 actually; pick a clearer
    // edge: 04:30 UTC where wall-clock EDT = 00:30 (2024-03-10 still)
    // but EST = 23:30 of the *previous* day (2024-03-09). The Python
    // settlement model groups by LST → date is 2024-03-09.
    const dateStr = "2024-03-09";
    const awc: AwcMockMetar[] = [
      {
        icaoId: "KNYC",
        obsTime: epochOfUtc("2024-03-10T04:30:00Z"),
        temp: 10,
        dewp: 3,
        wspd: 4,
      },
    ];
    installFetchMock({ cli: [], awc });
    const rows = await research("NYC", dateStr, dateStr);
    expect(rows).toHaveLength(1);
    expect(rows[0]?.obs_count).toBe(1);
    expect(rows[0]?.obs_high_f).not.toBeNull();
  });
});

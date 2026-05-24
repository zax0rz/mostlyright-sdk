// Tests for `researchBySource` — TS-W4 Wave 1 Mode 2 dispatch.
//
// All HTTP is mocked via `vi.spyOn(globalThis, "fetch")`. We assert:
//   - Unknown source rejected synchronously, BEFORE any fetch call.
//   - 'iem.live' rejected with the v0.1.0 parity-gap message.
//   - 'iem.archive' / 'awc.live' / 'ghcnh.archive' dispatch + return rows.
//   - Per-row `source` field is NEVER rewritten — bare parser tag survives.
//   - Empty results return `[]` (NOT throw).
//   - GHCNh non-US station throws NotFoundError before any HTTP.
//   - assertSourceIdentity internal call passes for correctly-tagged rows.
//
// Mirrors `tests/research.test.ts` mocking patterns.

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { NotFoundError } from "@tradewinds/core";

import { type Mode2Source, researchBySource } from "../src/mode2.js";

// ---------------------------------------------------------------------------
// Mock helpers
// ---------------------------------------------------------------------------

const IEM_HEADER =
  "station,valid,tmpf,dwpf,drct,sknt,gust,alti,mslp,vsby,skyc1,skyl1,skyc2,skyl2,skyc3,skyl3,skyc4,skyl4,wxcodes,p01i,snowdepth,peak_wind_gust,peak_wind_drct,peak_wind_time,metar";

function makeIemRow(overrides: Record<string, string> = {}): string {
  const defaults: Record<string, string> = {
    station: "NYC",
    valid: "2024-06-01 12:51",
    tmpf: "75",
    dwpf: "55",
    drct: "180",
    sknt: "8",
    gust: "",
    alti: "29.92",
    mslp: "1013.2",
    vsby: "10",
    skyc1: "FEW",
    skyl1: "2500",
    skyc2: "",
    skyl2: "",
    skyc3: "",
    skyl3: "",
    skyc4: "",
    skyl4: "",
    wxcodes: "",
    p01i: "",
    snowdepth: "",
    peak_wind_gust: "",
    peak_wind_drct: "",
    peak_wind_time: "",
    metar: "KNYC 011251Z 18008KT 10SM FEW025 24/13 A2992 RMK AO2",
    ...overrides,
  };
  const cols = IEM_HEADER.split(",");
  return cols.map((c) => defaults[c] ?? "").join(",");
}

function iemCsv(rows: string[]): string {
  return `${[IEM_HEADER, ...rows].join("\n")}\n`;
}

// Minimal GHCNh PSV with one valid temperature row.
const GHCNH_HEADER =
  "temperature_Source_Station_ID|DATE|temperature|temperature_Quality_Code|dew_point_temperature|dew_point_temperature_Quality_Code";

function ghcnhPsv(date: string, tempC: string): string {
  return `${GHCNH_HEADER}\nICAO-KNYC|${date}|${tempC}|0|20.0|0\n`;
}

interface AwcMockMetar {
  icaoId: string;
  obsTime: number;
  temp?: number | null;
  dewp?: number | null;
  wspd?: number | null;
  precip?: number | null;
  rawOb?: string | null;
}

function mockAwcResponse(records: ReadonlyArray<AwcMockMetar>): Response {
  return new Response(JSON.stringify(records), {
    status: 200,
    headers: { "content-type": "application/json" },
  });
}

interface FetchMockRoutes {
  iemAsosCsv?: string;
  ghcnhPsv?: string;
  ghcnhStatus?: number;
  awc?: ReadonlyArray<AwcMockMetar>;
  awcStatus?: number;
}

function installFetchMock(routes: FetchMockRoutes) {
  return vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    const url = typeof input === "string" ? input : ((input as Request).url ?? String(input));
    if (url.includes("aviationweather.gov")) {
      if (routes.awcStatus !== undefined && routes.awcStatus !== 200) {
        return new Response("err", { status: routes.awcStatus });
      }
      return mockAwcResponse(routes.awc ?? []);
    }
    if (url.includes("mesonet.agron.iastate.edu/cgi-bin/request/asos.py")) {
      const body = routes.iemAsosCsv ?? `${IEM_HEADER}\n`;
      return new Response(body, { status: 200, headers: { "content-type": "text/plain" } });
    }
    if (url.includes("ncei.noaa.gov/oa/global-historical-climatology-network")) {
      const status = routes.ghcnhStatus ?? 404;
      if (status === 200) {
        return new Response(routes.ghcnhPsv ?? "", {
          status,
          headers: { "content-type": "text/plain" },
        });
      }
      return new Response("", { status, headers: { "content-type": "text/plain" } });
    }
    throw new Error(`Unexpected fetch URL: ${url}`);
  });
}

// Recent date inside AWC's 168h window (last 7 days from "now").
function recentUtcDate(daysAgo: number): string {
  const target = new Date(Date.now() - daysAgo * 86_400_000);
  const y = target.getUTCFullYear();
  const m = String(target.getUTCMonth() + 1).padStart(2, "0");
  const d = String(target.getUTCDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}

function epochOfUtc(iso: string): number {
  return Math.floor(Date.parse(iso) / 1000);
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("researchBySource — unknown source rejection", () => {
  beforeEach(() => vi.restoreAllMocks());
  afterEach(() => vi.restoreAllMocks());

  it("throws synchronously-on-await for an unknown source string (no fetch call)", async () => {
    const fetchSpy = installFetchMock({});
    // Cast through unknown to bypass the Mode2Source type at the boundary
    // (consumers in plain JS / loose TS can pass any string).
    const bad = "iem" as unknown as Mode2Source;
    await expect(researchBySource("NYC", bad, "2024-06-01", "2024-06-30")).rejects.toThrow(
      /Mode 2 source must be one of/,
    );
    // No HTTP call should have fired — guard runs before any fetcher.
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("rejection message includes the canonical four-value list", async () => {
    installFetchMock({});
    const bad = "nws" as unknown as Mode2Source;
    let err: unknown = null;
    try {
      await researchBySource("NYC", bad, "2024-06-01", "2024-06-30");
    } catch (e) {
      err = e;
    }
    expect(err).toBeInstanceOf(Error);
    const msg = (err as Error).message;
    expect(msg).toContain("iem.archive");
    expect(msg).toContain("iem.live");
    expect(msg).toContain("awc.live");
    expect(msg).toContain("ghcnh.archive");
  });
});

describe("researchBySource — iem.live v0.1.0 parity gap", () => {
  beforeEach(() => vi.restoreAllMocks());
  afterEach(() => vi.restoreAllMocks());

  it("rejects 'iem.live' with the not-yet-implemented message (no fetch call)", async () => {
    const fetchSpy = installFetchMock({});
    await expect(researchBySource("NYC", "iem.live", "2024-06-01", "2024-06-30")).rejects.toThrow(
      /iem.live.*not yet implemented/,
    );
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("message points users to 'iem.archive' as the workaround", async () => {
    installFetchMock({});
    let err: unknown = null;
    try {
      await researchBySource("NYC", "iem.live", "2024-06-01", "2024-06-30");
    } catch (e) {
      err = e;
    }
    expect((err as Error).message).toContain("iem.archive");
    expect((err as Error).message).toMatch(/v0\.1\.0/);
  });
});

describe("researchBySource — iem.archive dispatch", () => {
  beforeEach(() => vi.restoreAllMocks());
  afterEach(() => vi.restoreAllMocks());

  it("returns rows with bare parser tag 'iem' (NOT rewritten to 'iem.archive')", async () => {
    const csv = iemCsv([makeIemRow({ valid: "2024-06-15 12:51" })]);
    installFetchMock({ iemAsosCsv: csv });
    const rows = await researchBySource("NYC", "iem.archive", "2024-06-01", "2024-06-30", {
      iemPolitenessMs: 0,
    });
    expect(rows.length).toBeGreaterThan(0);
    // CRITICAL invariant (Python mode2.py:161-166): per-row source MUST
    // be the parser-emitted bare tag, NOT silently rewritten to the
    // dotted canonical form. Downstream Validator depends on this.
    expect(rows[0]?.source).toBe("iem");
    for (const r of rows) {
      expect(r.source).toBe("iem");
    }
  });

  it("filters rows to the queried date window", async () => {
    const csv = iemCsv([
      makeIemRow({ valid: "2024-05-15 12:51" }), // outside window (before)
      makeIemRow({ valid: "2024-06-15 12:51" }), // in window
      makeIemRow({ valid: "2024-07-15 12:51" }), // outside window (after)
    ]);
    installFetchMock({ iemAsosCsv: csv });
    const rows = await researchBySource("NYC", "iem.archive", "2024-06-01", "2024-06-30", {
      iemPolitenessMs: 0,
    });
    // The CSV fetcher returns the same body for both report_type=3 and =4,
    // so the in-window row is counted twice. Just assert all returned rows
    // fall inside the window.
    expect(rows.length).toBeGreaterThan(0);
    for (const r of rows) {
      const day = r.observed_at.slice(0, 10);
      expect(day >= "2024-06-01").toBe(true);
      expect(day <= "2024-06-30").toBe(true);
    }
  });

  it("empty data → returns [] (NOT throws)", async () => {
    // Empty IEM CSV (header-only).
    installFetchMock({ iemAsosCsv: `${IEM_HEADER}\n` });
    const rows = await researchBySource("NYC", "iem.archive", "2024-06-01", "2024-06-30", {
      iemPolitenessMs: 0,
    });
    expect(rows).toEqual([]);
  });
});

describe("researchBySource — awc.live dispatch", () => {
  beforeEach(() => vi.restoreAllMocks());
  afterEach(() => vi.restoreAllMocks());

  it("returns rows tagged with bare 'awc' (NOT 'awc.live')", async () => {
    const today = recentUtcDate(1);
    const awc: AwcMockMetar[] = [
      {
        icaoId: "KNYC",
        obsTime: epochOfUtc(`${today}T12:00:00Z`),
        temp: 25.0,
        dewp: 15.0,
        wspd: 5,
        rawOb: "KNYC 011200Z 18005KT 10SM CLR 25/15 A2992 RMK AO2",
      },
    ];
    installFetchMock({ awc });
    const rows = await researchBySource("NYC", "awc.live", today, today);
    expect(rows.length).toBeGreaterThan(0);
    for (const r of rows) {
      // Bare parser-emitted tag — NEVER rewritten to 'awc.live'.
      expect(r.source).toBe("awc");
    }
  });

  it("AWC returning [] → returns [] (NOT throws)", async () => {
    const today = recentUtcDate(1);
    installFetchMock({ awc: [] });
    const rows = await researchBySource("NYC", "awc.live", today, today);
    expect(rows).toEqual([]);
  });

  it("filters AWC rows outside [fromDate, toDate] (codex iter-1 P2 fix)", async () => {
    // AWC lookback can return METARs spanning ~168h. Mode 2 must drop rows
    // outside the caller's window — same contract IEM/GHCNh honor.
    const today = recentUtcDate(1);
    const inWindow = today;
    const outOfWindowFuture = recentUtcDate(0); // tomorrow vs `today`-window
    const awc: AwcMockMetar[] = [
      {
        icaoId: "KNYC",
        obsTime: epochOfUtc(`${inWindow}T12:00:00Z`),
        temp: 25.0,
        dewp: 15.0,
        wspd: 5,
        rawOb: "KNYC 011200Z 18005KT 10SM CLR 25/15 A2992 RMK AO2",
      },
      {
        icaoId: "KNYC",
        obsTime: epochOfUtc(`${outOfWindowFuture}T12:00:00Z`),
        temp: 26.0,
        dewp: 16.0,
        wspd: 5,
        rawOb: "KNYC 021200Z 18005KT 10SM CLR 26/16 A2992 RMK AO2",
      },
    ];
    installFetchMock({ awc });
    const rows = await researchBySource("NYC", "awc.live", today, today);
    // Only the in-window METAR survives.
    for (const r of rows) {
      const d = r.observed_at.slice(0, 10);
      expect(d >= today && d <= today).toBe(true);
    }
    // The out-of-window METAR must NOT appear.
    const outDates = rows.map((r) => r.observed_at.slice(0, 10));
    expect(outDates).not.toContain(outOfWindowFuture);
  });
});

describe("researchBySource — ghcnh.archive dispatch", () => {
  beforeEach(() => vi.restoreAllMocks());
  afterEach(() => vi.restoreAllMocks());

  it("returns rows tagged with bare 'ghcnh' (NOT 'ghcnh.archive')", async () => {
    const psv = ghcnhPsv("2024-06-15T14:51:00Z", "25.0");
    installFetchMock({ ghcnhPsv: psv, ghcnhStatus: 200 });
    const rows = await researchBySource("NYC", "ghcnh.archive", "2024-06-01", "2024-06-30");
    expect(rows.length).toBeGreaterThan(0);
    for (const r of rows) {
      expect(r.source).toBe("ghcnh");
    }
  });

  it("NCEI 404 (no data) → returns [] (NOT throws)", async () => {
    installFetchMock({ ghcnhStatus: 404 });
    const rows = await researchBySource("NYC", "ghcnh.archive", "2024-06-01", "2024-06-30");
    expect(rows).toEqual([]);
  });

  it("non-US station throws NotFoundError BEFORE any HTTP call", async () => {
    const fetchSpy = installFetchMock({});
    // NZAA is in the station table (NZ — non-US). country !== "US" → throw.
    await expect(
      researchBySource("NZAA", "ghcnh.archive", "2024-06-01", "2024-06-30"),
    ).rejects.toBeInstanceOf(NotFoundError);
    expect(fetchSpy).not.toHaveBeenCalled();
  });
});

describe("researchBySource — input validation", () => {
  beforeEach(() => vi.restoreAllMocks());
  afterEach(() => vi.restoreAllMocks());

  it("rejects unknown station", async () => {
    installFetchMock({});
    await expect(
      researchBySource("XXX", "iem.archive", "2024-06-01", "2024-06-30"),
    ).rejects.toThrow(/unknown station/);
  });

  it("rejects malformed fromDate", async () => {
    installFetchMock({});
    await expect(
      researchBySource("NYC", "iem.archive", "2024/06/01", "2024-06-30"),
    ).rejects.toThrow(/fromDate must be YYYY-MM-DD/);
  });

  it("rejects fromDate > toDate", async () => {
    installFetchMock({});
    await expect(
      researchBySource("NYC", "iem.archive", "2024-06-30", "2024-06-01"),
    ).rejects.toThrow(/must be <=/);
  });
});

describe("researchBySource — ICAO input normalization", () => {
  beforeEach(() => vi.restoreAllMocks());
  afterEach(() => vi.restoreAllMocks());

  it("accepts 4-letter ICAO (KNYC) and resolves to 3-letter NWS code", async () => {
    const csv = iemCsv([makeIemRow({ valid: "2024-06-15 12:51" })]);
    installFetchMock({ iemAsosCsv: csv });
    const rows = await researchBySource("KNYC", "iem.archive", "2024-06-01", "2024-06-30", {
      iemPolitenessMs: 0,
    });
    expect(rows.length).toBeGreaterThan(0);
    // station_code should be the 3-letter NWS code.
    expect(rows[0]?.station_code).toBe("NYC");
  });
});

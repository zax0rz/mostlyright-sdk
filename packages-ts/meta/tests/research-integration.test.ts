// Integration tests for research() TS-W2 multi-source orchestrator.
//
// Asserts the 20-column PairsRow shape + source-priority observability
// + short-circuit guards (AWC + GHCNh).

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { research } from "../src/research.js";

const FAST_OPTS = {
  iemPolitenessMs: 0,
  ghcnhPolitenessMs: 0,
  cliPolitenessMs: 0,
};

interface RouteCounts {
  awc: number;
  iem: number;
  ghcnh: number;
  cli: number;
}

function installRouter(opts: {
  awcBody?: string;
  cliBody?: string;
  iemBody?: string;
  ghcnhStatus?: number;
  ghcnhBody?: string;
}) {
  const counts: RouteCounts = { awc: 0, iem: 0, ghcnh: 0, cli: 0 };
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    const url = typeof input === "string" ? input : ((input as Request).url ?? String(input));
    if (url.includes("aviationweather.gov")) {
      counts.awc++;
      return new Response(opts.awcBody ?? "[]", {
        status: 200,
        headers: { "content-type": "application/json" },
      });
    }
    if (url.includes("mesonet.agron.iastate.edu/json/cli.py")) {
      counts.cli++;
      return new Response(opts.cliBody ?? '{"results":[]}', {
        status: 200,
        headers: { "content-type": "application/json" },
      });
    }
    if (url.includes("mesonet.agron.iastate.edu/cgi-bin/request/asos.py")) {
      counts.iem++;
      return new Response(opts.iemBody ?? "#empty\nstation,valid\n", {
        status: 200,
        headers: { "content-type": "text/plain" },
      });
    }
    if (url.includes("ncei.noaa.gov/oa/global-historical-climatology-network")) {
      counts.ghcnh++;
      const status = opts.ghcnhStatus ?? 404;
      return new Response(status === 200 ? (opts.ghcnhBody ?? "") : "", {
        status,
        headers: { "content-type": "text/plain" },
      });
    }
    throw new Error(`Unexpected fetch URL: ${url}`);
  });
  return counts;
}

beforeEach(() => {
  vi.restoreAllMocks();
});
afterEach(() => {
  vi.restoreAllMocks();
});

describe("research() — PairsRow shape (TS-W2 Wave 4)", () => {
  it("returns one PairsRow per day with 20 fields in canonical order", async () => {
    installRouter({});
    const rows = await research("NYC", "2025-01-06", "2025-01-08", FAST_OPTS);
    expect(rows).toHaveLength(3);
    expect(Object.keys(rows[0]!)).toEqual([
      "date",
      "station",
      "cli_high_f",
      "cli_low_f",
      "cli_report_type",
      "obs_high_f",
      "obs_low_f",
      "obs_mean_f",
      "obs_mean_dewpoint_f",
      "obs_max_wind_kt",
      "obs_max_gust_kt",
      "obs_total_precip_in",
      "obs_count",
      "fcst_high_f",
      "fcst_low_f",
      "fcst_model",
      "fcst_issued_at",
      "fcst_pop_6hr_pct",
      "fcst_qpf_6hr_in",
      "market_close_utc",
    ]);
  });

  it("all fcst_* fields are unconditionally null (Mode 1)", async () => {
    installRouter({});
    const rows = await research("NYC", "2025-01-06", "2025-01-06", FAST_OPTS);
    expect(rows[0]?.fcst_high_f).toBeNull();
    expect(rows[0]?.fcst_low_f).toBeNull();
    expect(rows[0]?.fcst_model).toBeNull();
    expect(rows[0]?.fcst_issued_at).toBeNull();
    expect(rows[0]?.fcst_pop_6hr_pct).toBeNull();
    expect(rows[0]?.fcst_qpf_6hr_in).toBeNull();
  });

  it("PairsRow is frozen", async () => {
    installRouter({});
    const rows = await research("NYC", "2025-01-06", "2025-01-06", FAST_OPTS);
    expect(Object.isFrozen(rows[0])).toBe(true);
  });
});

describe("research() — short-circuit guards", () => {
  it("stale historical window → AWC fetcher is NOT called", async () => {
    const counts = installRouter({});
    await research("NYC", "2020-01-01", "2020-01-03", FAST_OPTS);
    // 2020 is ~5 years older than May 2026; AWC short-circuit kicks in.
    expect(counts.awc).toBe(0);
    // IEM ASOS still fires per-year (2020 + 2021 from extendedTo) × 2 report_types.
    expect(counts.iem).toBeGreaterThan(0);
  });

  it("recent window (within AWC 168h) → AWC fetcher IS called", async () => {
    const counts = installRouter({});
    const recent = new Date(Date.now() - 24 * 3_600_000); // 1 day ago
    const dateStr = `${recent.getUTCFullYear()}-${String(recent.getUTCMonth() + 1).padStart(2, "0")}-${String(recent.getUTCDate()).padStart(2, "0")}`;
    await research("NYC", dateStr, dateStr, FAST_OPTS);
    expect(counts.awc).toBe(1);
  });

  it("GHCNh fetcher fires for US stations (NYC has ghcnh_id USW00094728)", async () => {
    const counts = installRouter({});
    await research("NYC", "2025-01-06", "2025-01-06", FAST_OPTS);
    expect(counts.ghcnh).toBeGreaterThan(0);
  });

  it.todo(
    "GHCNh fetcher does NOT fire for international stations (no ghcnh_id) — blocked on TS-W6 intl tz coverage (EGLL not in _STATION_TZ)",
  );
});

describe("research() — source-priority observable in aggregates", () => {
  it("when AWC has data for a date, AWC observations dominate the aggregate", async () => {
    // AWC: 1 metar with temp_f=40 on 2025-01-06 12:00 UTC (= 2025-01-06 LST in NYC).
    // IEM ASOS: 1 row at SAME timestamp with temp=10 (lower priority).
    // Survivor after mergeObservations should be AWC (temp=40), so obs_high_f=40.
    const awcMetar = [
      {
        icaoId: "KNYC",
        obsTime: Math.floor(Date.parse("2025-01-06T12:00:00Z") / 1000),
        temp: 40 / 1.8 - 40 / 9, // Reverse F→C conversion. Actually awc passes °C; let's set °C directly.
        rawOb: "KNYC 061200Z AUTO 00000KT CLR 04/M01 A3000 RMK AO2",
      },
    ];
    // Simpler — just set temp to °C value that yields temp_f=40: (40-32)*5/9 = 4.444
    awcMetar[0]!.temp = ((40 - 32) * 5) / 9;

    const iemCsv = `#empty
station,valid,tmpf,dwpf,sknt,gust,p01i,vsby,gust_mph,skyc1,skyl1,skyc2,skyl2,skyc3,skyl3,skyc4,skyl4,wxcodes,ice_accretion_1hr,ice_accretion_3hr,ice_accretion_6hr,peak_wind_gust,peak_wind_drct,peak_wind_time,feel,metar,snowdepth,relh,alti,mslp,drct
KNYC,2025-01-06 12:00,10,5,0,0,M,10.00,M,CLR,M,M,M,M,M,M,M,M,M,M,M,M,M,M,M,KNYC 061200Z AUTO 00000KT CLR M12/M14 A3000 RMK AO2,M,M,30.00,M,M
`;

    installRouter({
      awcBody: JSON.stringify(awcMetar),
      iemBody: iemCsv,
    });

    const rows = await research("NYC", "2025-01-06", "2025-01-06", {
      ...FAST_OPTS,
      now: new Date("2025-01-07T00:00:00Z"), // force AWC to be considered fresh
    });
    expect(rows).toHaveLength(1);
    // AWC should win the tie; obs_high_f should be ~40 (not 10).
    const high = rows[0]?.obs_high_f;
    expect(high).not.toBeNull();
    if (high !== null && high !== undefined) {
      expect(high).toBeGreaterThan(30); // safely above the IEM value
    }
  });
});

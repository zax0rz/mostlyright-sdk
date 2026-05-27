// Phase 20 OM-07 + OM-08 — Open-Meteo TS fetcher unit tests.

import { OpenMeteoSeamlessLeakageError } from "@mostlyrightmd/core";
import { describe, expect, it, vi } from "vitest";

import {
  CYCLE_HOURS,
  OPEN_METEO_MODELS,
  PUBLISH_LAG_HOURS,
  floorToCycleMs,
  issuedAtFromLiveCycleMathMs,
  issuedAtFromPreviousDayMs,
} from "../src/forecasts/open-meteo-models.js";
import {
  OPEN_METEO_LIVE_URL,
  OPEN_METEO_PREVIOUS_RUNS_URL,
  OPEN_METEO_SEAMLESS_URL,
  OPEN_METEO_SINGLE_RUNS_URL,
  openMeteoForecasts,
} from "../src/forecasts/open-meteo.js";

function mockFetch(payload: unknown, status = 200): typeof fetch {
  return vi.fn(
    async () =>
      new Response(JSON.stringify(payload), {
        status,
        headers: { "content-type": "application/json" },
      }),
  ) as unknown as typeof fetch;
}

const SAMPLE_PREVIOUS_RUNS = {
  latitude: 40.78,
  longitude: -73.97,
  hourly: {
    time: ["2024-06-01T00:00", "2024-06-01T12:00", "2024-06-01T23:00"],
    temperature_2m_previous_day1: [18.5, 22.0, 19.0],
  },
};

describe("Phase 20 OM-08 — 36-model registry", () => {
  it("OPEN_METEO_MODELS has exactly 36 entries", () => {
    expect(OPEN_METEO_MODELS.size).toBe(36);
  });

  it("includes the canonical 36 keys", () => {
    const expected = [
      "gfs_seamless",
      "gfs_global",
      "ecmwf_ifs_hres",
      "dwd_icon_global",
      "meteofrance_arpege_world025",
      "jma_gsm",
      "ukmo_global_deterministic_10km",
      "cmc_gem_gdps",
    ];
    for (const k of expected) {
      expect(OPEN_METEO_MODELS.has(k as never)).toBe(true);
    }
  });
});

describe("Phase 20 OM-03 — cycle math primitives", () => {
  it("floorToCycleMs snaps down to most recent cycle hour", () => {
    const valid = Date.UTC(2024, 5, 1, 23);
    const result = floorToCycleMs(valid, [0, 6, 12, 18]);
    expect(new Date(result).toISOString()).toBe("2024-06-01T18:00:00.000Z");
  });

  it("issuedAtFromPreviousDayMs NYC GFS reproduces #70 worked example", () => {
    const validAt = Date.UTC(2024, 5, 1, 23);
    const result = issuedAtFromPreviousDayMs(validAt, 1, [0, 6, 12, 18]);
    expect(new Date(result).toISOString()).toBe("2024-05-31T18:00:00.000Z");
  });

  it("issuedAtFromLiveCycleMathMs follows floor(now - lag) formula", () => {
    const now = Date.UTC(2024, 5, 1, 14);
    const result = issuedAtFromLiveCycleMathMs(now, 4, [0, 6, 12, 18]);
    expect(new Date(result).toISOString()).toBe("2024-06-01T06:00:00.000Z");
  });
});

describe("Phase 20 OM-07 — openMeteoForecasts dispatch", () => {
  it("training mode default hits Previous Runs API", async () => {
    const fetchFn = mockFetch(SAMPLE_PREVIOUS_RUNS);
    await openMeteoForecasts("KNYC", "2024-06-01", "2024-06-01", {
      model: "gfs_global",
      mode: "training",
      fetchFn,
    });
    const url = (fetchFn as ReturnType<typeof vi.fn>).mock.calls[0][0] as string;
    expect(url.startsWith(OPEN_METEO_PREVIOUS_RUNS_URL)).toBe(true);
  });

  it("training mode + issuedAt hits Single Runs API", async () => {
    const fetchFn = mockFetch(SAMPLE_PREVIOUS_RUNS);
    await openMeteoForecasts("KNYC", "2024-06-01", "2024-06-01", {
      model: "gfs_global",
      mode: "training",
      issuedAt: "2024-06-01T12:00",
      fetchFn,
    });
    const url = (fetchFn as ReturnType<typeof vi.fn>).mock.calls[0][0] as string;
    expect(url.startsWith(OPEN_METEO_SINGLE_RUNS_URL)).toBe(true);
  });

  it("live mode hits Live Forecast API", async () => {
    const fetchFn = mockFetch(SAMPLE_PREVIOUS_RUNS);
    await openMeteoForecasts("KNYC", "2024-06-01", "2024-06-01", {
      model: "gfs_global",
      mode: "live",
      fetchFn,
    });
    const url = (fetchFn as ReturnType<typeof vi.fn>).mock.calls[0][0] as string;
    expect(url.startsWith(OPEN_METEO_LIVE_URL)).toBe(true);
  });

  it("seamless without allowLeakage throws OpenMeteoSeamlessLeakageError", async () => {
    await expect(
      openMeteoForecasts("KNYC", "2024-06-01", "2024-06-01", {
        model: "gfs_global",
        mode: "seamless",
      }),
    ).rejects.toBeInstanceOf(OpenMeteoSeamlessLeakageError);
  });

  it("seamless with allowLeakage hits Historical Forecast API", async () => {
    const fetchFn = mockFetch(SAMPLE_PREVIOUS_RUNS);
    const rows = await openMeteoForecasts("KNYC", "2024-06-01", "2024-06-01", {
      model: "gfs_global",
      mode: "seamless",
      allowLeakage: true,
      fetchFn,
    });
    const url = (fetchFn as ReturnType<typeof vi.fn>).mock.calls[0][0] as string;
    expect(url.startsWith(OPEN_METEO_SEAMLESS_URL)).toBe(true);
    for (const r of rows) {
      expect(r.source).toBe("open_meteo.seamless");
      expect(r.issuedAt).toBeNull();
    }
  });

  it("previous_runs rows tagged source=open_meteo.previous_runs with derived issuedAt", async () => {
    const fetchFn = mockFetch(SAMPLE_PREVIOUS_RUNS);
    const rows = await openMeteoForecasts("KNYC", "2024-06-01", "2024-06-01", {
      model: "gfs_global",
      mode: "training",
      fetchFn,
    });
    expect(rows.length).toBe(3);
    for (const r of rows) {
      expect(r.source).toBe("open_meteo.previous_runs");
      expect(r.issuedAt).not.toBeNull();
    }
  });

  it("unknown model rejects", async () => {
    await expect(
      openMeteoForecasts("KNYC", "2024-06-01", "2024-06-01", {
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        model: "bogus_model" as any,
      }),
    ).rejects.toThrow(/OPEN_METEO_MODELS/);
  });

  it("404 returns empty array", async () => {
    const fetchFn = mockFetch({}, 404);
    const rows = await openMeteoForecasts("KNYC", "2024-06-01", "2024-06-01", {
      model: "gfs_global",
      mode: "training",
      fetchFn,
    });
    expect(rows).toEqual([]);
  });

  it("case_1 NYC 2024-06-01 23:00Z previous_day1 → issuedAt = 2024-05-31T18:00:00.000Z", async () => {
    const fetchFn = mockFetch(SAMPLE_PREVIOUS_RUNS);
    const rows = await openMeteoForecasts("KNYC", "2024-06-01", "2024-06-01", {
      model: "gfs_global",
      mode: "training",
      fetchFn,
    });
    const h23 = rows.find((r) => r.validAt === "2024-06-01T23:00:00.000Z");
    expect(h23).toBeDefined();
    expect(h23?.issuedAt).toBe("2024-05-31T18:00:00.000Z");
  });
});

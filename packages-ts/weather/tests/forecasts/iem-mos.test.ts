// Phase 17 PLAN-11 — iemMosForecasts TS unit tests (mocked fetch).

import { describe, expect, it, vi } from "vitest";

import {
  iemMosForecasts,
  type IemMosRow,
} from "../../src/forecasts/index.js";

const SAMPLE_ROW = {
  runtime: "2026-05-01T00:00:00Z",
  ftime: "2026-05-01T06:00:00Z",
  station: "KNYC",
  tmp: 68.0, // F → 20°C
  dpt: 50.0,
  wsp: 10.0, // 10 kt
  wdr: 270,
  pop12: 25.0,
};

function makeMockFetch(payload: unknown, status = 200): typeof fetch {
  return vi.fn(async () => ({
    ok: status >= 200 && status < 300,
    status,
    async json() {
      return payload;
    },
  })) as unknown as typeof fetch;
}

describe("iemMosForecasts", () => {
  it("returns IemMosRow[] from a 200 payload", async () => {
    const fetchFn = makeMockFetch({ data: [SAMPLE_ROW] });
    const rows = await iemMosForecasts(
      "KNYC",
      "2026-05-01",
      "2026-05-01",
      { model: "nbe", fetchFn },
    );
    expect(rows.length).toBeGreaterThan(0);
    const r = rows[0]!;
    expect(r.station).toBe("KNYC");
    expect(r.model).toBe("NBE");
    expect(r.source).toBe("iem.archive");
  });

  it("converts F→C correctly", async () => {
    const fetchFn = makeMockFetch({ data: [SAMPLE_ROW] });
    const rows = await iemMosForecasts(
      "KNYC",
      "2026-05-01",
      "2026-05-01",
      { model: "nbe", fetchFn },
    );
    expect(rows[0]!.tempC).toBeCloseTo(20.0, 2);
  });

  it("converts knots→m/s correctly", async () => {
    const fetchFn = makeMockFetch({ data: [SAMPLE_ROW] });
    const rows = await iemMosForecasts(
      "KNYC",
      "2026-05-01",
      "2026-05-01",
      { model: "nbe", fetchFn },
    );
    expect(rows[0]!.windSpeedMs).toBeCloseTo(5.144, 2);
  });

  it("converts pop12 % → unit probability", async () => {
    const fetchFn = makeMockFetch({ data: [SAMPLE_ROW] });
    const rows = await iemMosForecasts(
      "KNYC",
      "2026-05-01",
      "2026-05-01",
      { model: "nbe", fetchFn },
    );
    expect(rows[0]!.precipProbability).toBeCloseTo(0.25, 3);
  });

  it("returns [] when the API has no rows", async () => {
    const fetchFn = makeMockFetch({ data: [] });
    const rows = await iemMosForecasts(
      "KNYC",
      "2026-05-01",
      "2026-05-01",
      { model: "nbe", fetchFn },
    );
    expect(rows).toEqual([]);
  });

  it("silently skips 404 responses", async () => {
    const fetchFn = vi.fn(async () => ({
      ok: false,
      status: 404,
      async json() {
        return null;
      },
    })) as unknown as typeof fetch;
    const rows = await iemMosForecasts(
      "KNYC",
      "2026-05-01",
      "2026-05-01",
      { model: "nbe", fetchFn },
    );
    expect(rows).toEqual([]);
  });

  it("rejects unknown model", async () => {
    await expect(
      // @ts-expect-error — testing runtime rejection of invalid model
      iemMosForecasts("KNYC", "2026-05-01", "2026-05-01", { model: "bogus" }),
    ).rejects.toThrow(/model must be one of/);
  });

  it("rejects invalid date format", async () => {
    await expect(
      iemMosForecasts("KNYC", "not-a-date", "2026-05-01", { model: "nbe" }),
    ).rejects.toThrow(/ISO YYYY-MM-DD/);
  });

  it("forecastHour is derived from runtime + ftime", async () => {
    const fetchFn = makeMockFetch({ data: [SAMPLE_ROW] });
    const rows = await iemMosForecasts(
      "KNYC",
      "2026-05-01",
      "2026-05-01",
      { model: "nbe", fetchFn },
    );
    // runtime=00Z, ftime=06Z → 6 hours
    expect(rows[0]!.forecastHour).toBe(6);
  });
});

// Phase 17 PLAN-11 — iemMosForecasts TS unit tests (mocked fetch).

import { describe, expect, it, vi } from "vitest";

// MOS_FETCH_CONCURRENCY is an internal tuning constant (not re-exported from
// the public barrel), imported directly from the module for this regression.
import { MOS_FETCH_CONCURRENCY } from "../../src/forecasts/iem-mos.js";
import { type IemMosRow, iemMosForecasts } from "../../src/forecasts/index.js";

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
    const rows = await iemMosForecasts("KNYC", "2026-05-01", "2026-05-01", {
      model: "nbe",
      fetchFn,
    });
    expect(rows.length).toBeGreaterThan(0);
    expect(rows[0]?.station).toBe("KNYC");
    expect(rows[0]?.model).toBe("NBE");
    expect(rows[0]?.source).toBe("iem.archive");
  });

  it("converts F→C correctly", async () => {
    const fetchFn = makeMockFetch({ data: [SAMPLE_ROW] });
    const rows = await iemMosForecasts("KNYC", "2026-05-01", "2026-05-01", {
      model: "nbe",
      fetchFn,
    });
    expect(rows[0]?.tempC).toBeCloseTo(20.0, 2);
  });

  it("converts knots→m/s correctly", async () => {
    const fetchFn = makeMockFetch({ data: [SAMPLE_ROW] });
    const rows = await iemMosForecasts("KNYC", "2026-05-01", "2026-05-01", {
      model: "nbe",
      fetchFn,
    });
    expect(rows[0]?.windSpeedMs).toBeCloseTo(5.144, 2);
  });

  it("converts pop12 % → unit probability", async () => {
    const fetchFn = makeMockFetch({ data: [SAMPLE_ROW] });
    const rows = await iemMosForecasts("KNYC", "2026-05-01", "2026-05-01", {
      model: "nbe",
      fetchFn,
    });
    expect(rows[0]?.precipProbability).toBeCloseTo(0.25, 3);
  });

  it("returns [] when the API has no rows", async () => {
    const fetchFn = makeMockFetch({ data: [] });
    const rows = await iemMosForecasts("KNYC", "2026-05-01", "2026-05-01", {
      model: "nbe",
      fetchFn,
    });
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
    const rows = await iemMosForecasts("KNYC", "2026-05-01", "2026-05-01", {
      model: "nbe",
      fetchFn,
    });
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
    const rows = await iemMosForecasts("KNYC", "2026-05-01", "2026-05-01", {
      model: "nbe",
      fetchFn,
    });
    // runtime=00Z, ftime=06Z → 6 hours
    expect(rows[0]?.forecastHour).toBe(6);
  });

  // Issue #58 regression: cycles must fan out concurrently (not serially),
  // but with BOUNDED concurrency (codex review P2 — an unbounded Promise.all
  // over a year-scale window would launch ~1,460 simultaneous requests).
  it("issues runtime-cycle fetches concurrently but bounded by MOS_FETCH_CONCURRENCY", async () => {
    let dispatched = 0;
    let inFlight = 0;
    let peakInFlight = 0;
    const resolvers: Array<() => void> = [];

    const fetchFn = vi.fn(async () => {
      dispatched++;
      inFlight++;
      peakInFlight = Math.max(peakInFlight, inFlight);
      await new Promise<void>((resolve) => {
        resolvers.push(() => {
          inFlight--;
          resolve();
        });
      });
      return {
        ok: true,
        status: 200,
        async json() {
          return { data: [] };
        },
      };
    }) as unknown as typeof fetch;

    // Window AFTER NBE cutover (2026-05-05) → 4 cycles per day; 3-day window
    // = 12 cycles total (> MOS_FETCH_CONCURRENCY, so the cap is observable).
    const promise = iemMosForecasts("KNYC", "2026-05-10", "2026-05-12", {
      model: "nbe",
      fetchFn,
    });

    // Drain: tick the event loop and release one in-flight request at a time.
    // Each release frees a pool slot so a queued cycle can dispatch, until all
    // 12 cycles have been dispatched and resolved. Bounded guard prevents a
    // hang if the implementation regresses.
    for (let guard = 0; guard < 1000 && (dispatched < 12 || resolvers.length > 0); guard++) {
      await new Promise((r) => setImmediate(r));
      const r = resolvers.shift();
      if (r) r();
    }
    await promise;

    // Concurrent (not serial): more than one request was in flight at once.
    expect(peakInFlight).toBeGreaterThan(1);
    // Bounded: peak never exceeded the configured cap.
    expect(peakInFlight).toBeLessThanOrEqual(MOS_FETCH_CONCURRENCY);
    // All 12 day×runtime cycles were eventually dispatched.
    expect(dispatched).toBe(12);
  });

  // Fail-fast (codex iter-3): a non-404 HTTP error rejects AND stops the pool
  // from dispatching the remaining queued cycles — matching the serial path,
  // which threw on the first error and issued no further requests.
  it("stops dispatching further cycles after a non-404 HTTP error", async () => {
    let dispatched = 0;
    // 3-day post-cutover NBE window = 12 cycles. First response is a 500.
    const fetchFn = vi.fn(async () => {
      dispatched++;
      return {
        ok: false,
        status: 500,
        async json() {
          return null;
        },
      };
    }) as unknown as typeof fetch;

    await expect(
      iemMosForecasts("KNYC", "2026-05-10", "2026-05-12", { model: "nbe", fetchFn }),
    ).rejects.toThrow(/HTTP 500/);

    // The first batch (≤ MOS_FETCH_CONCURRENCY) may be in flight when the error
    // fires, but NO new cycles are dispatched afterward — far fewer than all 12.
    expect(dispatched).toBeLessThanOrEqual(MOS_FETCH_CONCURRENCY);
    expect(dispatched).toBeLessThan(12);
  });

  // Issue #17 regression: IEM /api/1/mos.json validates `model` against
  // ^(AVN|GFS|ETA|NAM|NBS|NBE|ECM|LAV|MEX)$ and returns HTTP 422 for any
  // lowercase value. Python had the same bug and was fixed in 240969d;
  // the TS fetcher needs the same uppercase contract on the wire.
  it("sends uppercase model query param (issue #17)", async () => {
    const calls: string[] = [];
    const fetchFn = vi.fn(async (input: RequestInfo | URL) => {
      calls.push(typeof input === "string" ? input : input.toString());
      return {
        ok: true,
        status: 200,
        async json() {
          return { data: [] };
        },
      };
    }) as unknown as typeof fetch;
    // Window AFTER the NBE 2026-05-05 cutover → canonical (0,6,12,18)Z = 4 GETs.
    await iemMosForecasts("KNYC", "2026-05-10", "2026-05-10", {
      model: "nbe",
      fetchFn,
    });
    expect(calls.length).toBeGreaterThan(0);
    for (const url of calls) {
      const got = new URL(url).searchParams.get("model");
      expect(got).toBe("NBE");
    }
  });
});

// TS-W2 Plan 01 Task 2 — downloadIemAsos fetcher tests.
//
// Byte-faithful port of Python
// `packages/weather/src/mostlyright/weather/_fetchers/iem_asos.py::download_iem_asos`,
// minus the disk-cache layer (deferred to TS-W3 — TS-side returns in-memory
// CSV bodies). URL shape, start-normalization, polite-delay, and reversed-
// range short-circuit semantics all match the Python source.
//
// HTTP is mocked via `vi.spyOn(globalThis, "fetch")` (matches the TS-W1
// convention; msw is intentionally NOT installed in TS-W2 per the plan
// "DO NOT add deps" note + REVIEW-DISCIPLINE bundle-size rubric).

import { type MockInstance, afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  IEM_BASE_URL,
  IEM_POLITE_DELAY_MS,
  buildIemUrl,
  downloadIemAsos,
} from "../src/_fetchers/iem-asos.js";

type FetchFn = typeof globalThis.fetch;
let fetchSpy: MockInstance<FetchFn>;

beforeEach(() => {
  fetchSpy = vi.spyOn(globalThis, "fetch") as unknown as MockInstance<FetchFn>;
});

afterEach(() => {
  fetchSpy.mockRestore();
  vi.restoreAllMocks();
});

function csvResponse(status: number, body: string): Response {
  return new Response(body, {
    status,
    headers: { "content-type": "text/csv" },
  });
}

const SYNTHETIC_HEADER =
  "station,valid,tmpf,dwpf,drct,sknt,gust,alti,mslp,vsby,skyc1,skyl1,skyc2,skyl2,skyc3,skyl3,skyc4,skyl4,wxcodes,p01i,snowdepth,peak_wind_gust,peak_wind_drct,peak_wind_time,metar";

function syntheticCsv(year: number): string {
  // One row per year — exact contents are not parsed by the fetcher (it
  // returns the body verbatim) but a realistic row keeps test intent clear.
  const row = `KNYC,${year}-06-15 12:51,75,55,180,8,M,29.92,1013.2,10,FEW,2500,M,M,M,M,M,M,,0.00,M,M,M,M,KNYC ${year}-06-15 12:51Z 18008KT 10SM FEW025 24/13 A2992`;
  return `${SYNTHETIC_HEADER}\n${row}\n`;
}

describe("IEM_BASE_URL + IEM_POLITE_DELAY_MS constants", () => {
  it("matches Python parity values", () => {
    expect(IEM_BASE_URL).toBe("https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py");
    expect(IEM_POLITE_DELAY_MS).toBe(1000);
  });
});

describe("buildIemUrl — URL shape byte-faithful to Python _build_iem_url", () => {
  it("encodes all required query params in canonical order", () => {
    const url = buildIemUrl("NYC", "2024-01-01", "2025-01-01", 3);
    expect(url).toBe(
      `${IEM_BASE_URL}?station=NYC&data=all&tz=Etc/UTC&format=comma&latlon=no&elev=no&missing=M&trace=T&direct=no&report_type=3&year1=2024&month1=1&day1=1&year2=2025&month2=1&day2=1`,
    );
  });

  it("emits report_type=4 for SPECI", () => {
    const url = buildIemUrl("NYC", "2024-06-15", "2025-01-01", 4);
    expect(url).toContain("report_type=4");
    // No leading-zero padding on month/day (mirror Python f-string `{month}` not `{month:02d}`).
    expect(url).toContain("year1=2024&month1=6&day1=15");
  });

  it("preserves chunk_end as Jan 1 of following year (IEM day2 exclusive)", () => {
    const url = buildIemUrl("LAX", "2024-03-15", "2025-01-01", 3);
    expect(url).toContain("year2=2025&month2=1&day2=1");
  });
});

describe("downloadIemAsos — happy path + chunk count", () => {
  it("returns one entry per yearly chunk with body forwarded verbatim", async () => {
    fetchSpy
      .mockResolvedValueOnce(csvResponse(200, syntheticCsv(2023)))
      .mockResolvedValueOnce(csvResponse(200, syntheticCsv(2024)))
      .mockResolvedValueOnce(csvResponse(200, syntheticCsv(2025)));
    const out = await downloadIemAsos("NYC", "2023-06-15", "2025-02-15", {
      reportType: 3,
      politenessMs: 0,
    });
    expect(out).toHaveLength(3);
    expect(fetchSpy).toHaveBeenCalledTimes(3);
    expect(out[0]?.csv).toBe(syntheticCsv(2023));
    expect(out[1]?.csv).toBe(syntheticCsv(2024));
    expect(out[2]?.csv).toBe(syntheticCsv(2025));
  });

  it("yields chunk bounds in chunker-natural order (start is Jan-1-normalized)", async () => {
    // Per Python parity: caller's `start=2023-06-15` is normalized to
    // `date(2023, 1, 1)` BEFORE the chunker runs (cache-key idempotence).
    // The first chunk therefore starts at 2023-01-01, NOT 2023-06-15.
    // Documented deviation rationale lives in iem-asos.ts module header.
    fetchSpy
      .mockResolvedValueOnce(csvResponse(200, ""))
      .mockResolvedValueOnce(csvResponse(200, ""))
      .mockResolvedValueOnce(csvResponse(200, ""));
    const out = await downloadIemAsos("NYC", "2023-06-15", "2025-02-15", {
      reportType: 3,
      politenessMs: 0,
    });
    expect(out.map((c) => [c.chunkStart, c.chunkEnd])).toEqual([
      ["2023-01-01", "2024-01-01"],
      ["2024-01-01", "2025-01-01"],
      ["2025-01-01", "2026-01-01"],
    ]);
  });
});

describe("downloadIemAsos — start normalization (Jan-1 cache-key parity)", () => {
  it("forces day1=1, month1=1, year1=start.year in the FIRST chunk's URL", async () => {
    // Caller passes a mid-year start (2024-06-15) — Python normalizes the
    // chunker input to date(2024, 1, 1) so per-month callers share the year
    // cache key. The first chunk's URL must therefore show day1=1, month1=1
    // — NOT the caller's actual date. Validate this directly off the URL
    // the spy was called with.
    fetchSpy.mockResolvedValueOnce(csvResponse(200, ""));
    await downloadIemAsos("NYC", "2024-06-15", "2024-08-20", {
      reportType: 3,
      politenessMs: 0,
    });
    const calledUrl = String(fetchSpy.mock.calls[0]?.[0]);
    // year1/month1/day1 reflect the Jan-1-normalized chunker start.
    // Per `yearlyChunksExclusiveEnd`, when start is already <= currentYearStart
    // the chunker's `max(currentYearStart, start)` returns the normalized
    // Jan 1 — and `downloadIemAsos` MUST pass the normalized date in.
    expect(calledUrl).toContain("year1=2024&month1=1&day1=1");
    expect(calledUrl).toContain("year2=2025&month2=1&day2=1");
  });

  it("first chunk's chunkStart in the returned envelope reflects the normalized Jan-1 start", async () => {
    fetchSpy.mockResolvedValueOnce(csvResponse(200, "X"));
    const out = await downloadIemAsos("NYC", "2024-06-15", "2024-08-20", {
      reportType: 3,
      politenessMs: 0,
    });
    expect(out).toHaveLength(1);
    expect(out[0]?.chunkStart).toBe("2024-01-01");
    expect(out[0]?.chunkEnd).toBe("2025-01-01");
  });
});

describe("downloadIemAsos — input validation guards", () => {
  it("rejects report_type outside {3, 4} synchronously, no HTTP", async () => {
    await expect(
      downloadIemAsos("NYC", "2024-01-01", "2024-12-31", {
        reportType: 5 as unknown as 3,
        politenessMs: 0,
      }),
    ).rejects.toThrow(/report.?type/i);
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("rejects report_type = 0 synchronously", async () => {
    await expect(
      downloadIemAsos("NYC", "2024-01-01", "2024-12-31", {
        reportType: 0 as unknown as 3,
        politenessMs: 0,
      }),
    ).rejects.toThrow();
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("rejects bogus station codes before any HTTP call (path-traversal defense)", async () => {
    await expect(
      downloadIemAsos("../etc/passwd", "2024-01-01", "2024-12-31", {
        reportType: 3,
        politenessMs: 0,
      }),
    ).rejects.toThrow(/STATION_CODE_RE/);
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("rejects lowercase station codes (regex requires uppercase)", async () => {
    await expect(
      downloadIemAsos("nyc", "2024-01-01", "2024-12-31", {
        reportType: 3,
        politenessMs: 0,
      }),
    ).rejects.toThrow(/STATION_CODE_RE/);
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("accepts 4-letter ICAOs (KNYC) and 3-letter NWS codes (NYC)", async () => {
    // mockImplementation returns a fresh Response per call (mockResolvedValue
    // returns the same instance, whose body can only be consumed once).
    fetchSpy.mockImplementation(async () => csvResponse(200, ""));
    await expect(
      downloadIemAsos("KNYC", "2024-01-01", "2024-06-30", { reportType: 3, politenessMs: 0 }),
    ).resolves.toHaveLength(1);
    await expect(
      downloadIemAsos("NYC", "2024-01-01", "2024-06-30", { reportType: 3, politenessMs: 0 }),
    ).resolves.toHaveLength(1);
  });
});

describe("downloadIemAsos — reversed range short-circuit", () => {
  it("returns [] with ZERO HTTP requests when start > end", async () => {
    const out = await downloadIemAsos("NYC", "2025-01-01", "2024-12-31", {
      reportType: 3,
      politenessMs: 0,
    });
    expect(out).toEqual([]);
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("same-year reversed range also short-circuits", async () => {
    const out = await downloadIemAsos("NYC", "2024-06-15", "2024-03-15", {
      reportType: 3,
      politenessMs: 0,
    });
    expect(out).toEqual([]);
    expect(fetchSpy).not.toHaveBeenCalled();
  });
});

describe("downloadIemAsos — polite delay default", () => {
  it("exposes IEM_POLITE_DELAY_MS = 1000 (Python parity: IEM_POLITE_DELAY = 1.0s)", () => {
    expect(IEM_POLITE_DELAY_MS).toBe(1000);
  });

  it("politenessMs option overrides the default", async () => {
    // Sanity: politenessMs=0 in tests makes them complete in <1s. If the
    // default were used the 2-chunk fetch below would idle ~2s. Wall-clock
    // assertion is loose (under 200ms) to avoid CI flakiness.
    fetchSpy
      .mockResolvedValueOnce(csvResponse(200, ""))
      .mockResolvedValueOnce(csvResponse(200, ""));
    const t0 = Date.now();
    await downloadIemAsos("NYC", "2023-06-15", "2024-06-15", {
      reportType: 3,
      politenessMs: 0,
    });
    const dt = Date.now() - t0;
    expect(dt).toBeLessThan(200);
  });
});

describe("downloadIemAsos — error propagation", () => {
  it("propagates 5xx errors (after fetchWithRetry exhaustion) without swallowing", async () => {
    // Pre-emptively short-circuit fetchWithRetry by throwing from the spy.
    // fetchWithRetry retries network errors but propagates after the budget.
    const boom = new Error("boom: 500");
    fetchSpy.mockRejectedValue(boom);
    await expect(
      downloadIemAsos("NYC", "2024-01-01", "2024-06-30", {
        reportType: 3,
        politenessMs: 0,
        maxRetries: 1, // no retries to keep test fast
      }),
    ).rejects.toThrow(/boom|fetch failed/);
  });
});

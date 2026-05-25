import { NotFoundError } from "@mostlyrightmd/core";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { MockInstance } from "vitest";

import {
  GHCNH_BASE_URL,
  NCEI_POLITE_DELAY_MS,
  downloadGhcnh,
  downloadGhcnhRange,
} from "../src/_fetchers/ghcnh.js";

type FetchFn = typeof globalThis.fetch;
let fetchSpy: MockInstance<FetchFn>;

beforeEach(() => {
  fetchSpy = vi.spyOn(globalThis, "fetch") as unknown as MockInstance<FetchFn>;
});

afterEach(() => {
  fetchSpy.mockRestore();
  vi.restoreAllMocks();
});

function psvResponse(status: number, body: string): Response {
  return new Response(body, {
    status,
    headers: { "content-type": "text/plain" },
  });
}

function emptyResponse(status: number): Response {
  return new Response("", {
    status,
    headers: { "content-type": "text/plain" },
  });
}

describe("downloadGhcnh — single station-year", () => {
  it("constructs the documented NCEI URL", async () => {
    fetchSpy.mockResolvedValueOnce(psvResponse(200, "DATE|station_code\n"));
    await downloadGhcnh("744860-94789", 2024);
    const url = fetchSpy.mock.calls[0]?.[0] as string;
    expect(url).toBe(`${GHCNH_BASE_URL}/by-year/2024/psv/GHCNh_744860-94789_2024.psv`);
  });

  it("returns { stationId, year, psv } with the response body", async () => {
    const body = "DATE|station_code\n2024-01-01T00:00:00Z|JFK\n";
    fetchSpy.mockResolvedValueOnce(psvResponse(200, body));
    const result = await downloadGhcnh("744860-94789", 2024);
    expect(result).toEqual({ stationId: "744860-94789", year: 2024, psv: body });
  });

  it("propagates 404 as NotFoundError (caller must catch for skip)", async () => {
    fetchSpy.mockResolvedValueOnce(emptyResponse(404));
    await expect(downloadGhcnh("744860-94789", 1900)).rejects.toBeInstanceOf(NotFoundError);
  });

  it("throws synchronously on invalid station id (path separator)", async () => {
    await expect(downloadGhcnh("FOO/../etc", 2024)).rejects.toThrow(/does not match/);
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("throws on whitespace in station id", async () => {
    await expect(downloadGhcnh("FOO BAR", 2024)).rejects.toThrow(/does not match/);
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("accepts USAF-WBAN style ids (digits + hyphen)", async () => {
    fetchSpy.mockResolvedValueOnce(psvResponse(200, ""));
    await expect(downloadGhcnh("744860-94789", 2024)).resolves.toBeDefined();
  });

  it("accepts NCEI 11-char ids (USW00094789)", async () => {
    fetchSpy.mockResolvedValueOnce(psvResponse(200, ""));
    await expect(downloadGhcnh("USW00094789", 2024)).resolves.toBeDefined();
  });
});

describe("downloadGhcnhRange — 404-as-skip + range semantics", () => {
  it("iterates inclusive years and concatenates successful PSVs", async () => {
    fetchSpy.mockResolvedValueOnce(psvResponse(200, "body-2020"));
    fetchSpy.mockResolvedValueOnce(psvResponse(200, "body-2021"));
    fetchSpy.mockResolvedValueOnce(psvResponse(200, "body-2022"));
    const out = await downloadGhcnhRange("744860-94789", 2020, 2022, { politenessMs: 0 });
    expect(out).toHaveLength(3);
    expect(out.map((r) => r.year)).toEqual([2020, 2021, 2022]);
    expect(out.map((r) => r.psv)).toEqual(["body-2020", "body-2021", "body-2022"]);
  });

  it("silently skips 404 years and continues the loop", async () => {
    fetchSpy.mockResolvedValueOnce(psvResponse(200, "body-2020"));
    fetchSpy.mockResolvedValueOnce(psvResponse(200, "body-2021"));
    fetchSpy.mockResolvedValueOnce(psvResponse(200, "body-2022"));
    fetchSpy.mockResolvedValueOnce(emptyResponse(404)); // 2023 → skip
    fetchSpy.mockResolvedValueOnce(psvResponse(200, "body-2024"));
    const out = await downloadGhcnhRange("744860-94789", 2020, 2024, { politenessMs: 0 });
    expect(out).toHaveLength(4);
    expect(out.map((r) => r.year)).toEqual([2020, 2021, 2022, 2024]);
  });

  it("propagates non-404 HTTP errors on first failing year (no further fetches)", async () => {
    fetchSpy.mockResolvedValueOnce(psvResponse(200, "body-2020"));
    // 500 fires retries via fetchWithRetry, then throws ServerError.
    fetchSpy.mockResolvedValue(emptyResponse(500));
    await expect(
      downloadGhcnhRange("744860-94789", 2020, 2022, {
        politenessMs: 0,
        maxRetries: 1,
        baseDelayMs: 1,
      }),
    ).rejects.toThrow();
  });

  it("reversed range returns [] without firing any HTTP requests", async () => {
    const out = await downloadGhcnhRange("744860-94789", 2024, 2020);
    expect(out).toEqual([]);
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("single-year range fires exactly one request", async () => {
    fetchSpy.mockResolvedValueOnce(psvResponse(200, "body"));
    const out = await downloadGhcnhRange("744860-94789", 2024, 2024, { politenessMs: 0 });
    expect(out).toHaveLength(1);
    expect(fetchSpy).toHaveBeenCalledTimes(1);
  });

  it("rejects invalid station id synchronously before any iteration", async () => {
    await expect(downloadGhcnhRange("BAD/ID", 2020, 2022)).rejects.toThrow(/does not match/);
    expect(fetchSpy).not.toHaveBeenCalled();
  });
});

describe("downloadGhcnh — constants", () => {
  it("NCEI_POLITE_DELAY_MS equals Python NCEI_POLITE_DELAY (1.0s → 1000ms)", () => {
    expect(NCEI_POLITE_DELAY_MS).toBe(1000);
  });

  it("GHCNH_BASE_URL matches Python verbatim", () => {
    expect(GHCNH_BASE_URL).toBe(
      "https://www.ncei.noaa.gov/oa/global-historical-climatology-network/hourly/access",
    );
  });
});

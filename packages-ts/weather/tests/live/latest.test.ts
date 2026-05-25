// Phase 11 — `latest()` unit tests (8 tests).
//
// Mirrors `packages/core/tests/test_live_latest.py`. `fetch` is mocked via
// `vi.spyOn(globalThis, "fetch")`. No msw / recordings.

import { type MockInstance, afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { NoLiveDataError } from "@tradewinds/core";

import { latest } from "../../src/live/latest.js";
import * as fetchModule from "../../src/live/_fetch.js";

// ---------------------------------------------------------------------------
// Test helpers
// ---------------------------------------------------------------------------

function awcMetar(obsTime: number): unknown {
  return {
    icaoId: "KNYC",
    obsTime,
    metarType: "METAR",
    temp: 20.0,
    dewp: 10.0,
    rawOb: "KNYC 251200Z 18010KT 10SM CLR 20/10 A3010",
  };
}

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

let fetchSpy: MockInstance<typeof globalThis.fetch>;

beforeEach(() => {
  fetchSpy = vi.spyOn(globalThis, "fetch");
});
afterEach(() => {
  vi.restoreAllMocks();
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("latest()", () => {
  it("AWC poll returns one parsed observation tagged source=awc.live", async () => {
    fetchSpy.mockResolvedValueOnce(jsonResponse([awcMetar(1748174400)]));
    const row = await latest("KNYC");
    expect(row.station_code).toBe("NYC");
    expect(row.source).toBe("awc.live");
    expect(row.observed_at).toMatch(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$/);
  });

  it("default source is AWC (no source= option)", async () => {
    fetchSpy.mockResolvedValueOnce(jsonResponse([awcMetar(1748174400)]));
    const row = await latest("KNYC"); // no opts
    expect(row.source).toBe("awc.live");
    expect(fetchSpy).toHaveBeenCalledTimes(1);
    const url = (fetchSpy.mock.calls[0]?.[0] as string) ?? "";
    expect(url).toContain("aviationweather.gov");
  });

  it("source='iem' routes to IEM dispatch (not AWC)", async () => {
    const iemSpy = vi
      // Spy on `fetchLatest` (the dispatch entrypoint) rather than
      // `fetchIemLatest` directly — module-internal calls don't go through
      // the export binding so spying the dispatch is the only stable hook.
      .spyOn(fetchModule, "fetchLatest")
      .mockResolvedValueOnce([
        {
          station_code: "NYC",
          observed_at: "2026-05-25T12:00:00Z",
          observation_type: "METAR",
          source: "iem.live",
          temp_c: 20,
          dewpoint_c: 10,
          temp_f: 68,
          dewpoint_f: 50,
          wind_dir_degrees: null,
          wind_speed_kt: null,
          wind_gust_kt: null,
          altimeter_inhg: null,
          sea_level_pressure_mb: null,
          sky_cover_1: null,
          sky_base_1_ft: null,
          sky_cover_2: null,
          sky_base_2_ft: null,
          sky_cover_3: null,
          sky_base_3_ft: null,
          sky_cover_4: null,
          sky_base_4_ft: null,
          visibility_miles: null,
          weather_codes: null,
          raw_metar: null,
          precip_in: null,
          qc_field: null,
        },
      ]);
    const row = await latest("KNYC", { source: "iem" });
    expect(iemSpy).toHaveBeenCalledTimes(1);
    expect(fetchSpy).not.toHaveBeenCalled();
    expect(row.source).toBe("iem.live");
  });

  it("unknown source raises Error", async () => {
    await expect(
      latest("KNYC", { source: "ghcnh" as never }),
    ).rejects.toThrow(/unknown live source/);
  });

  it("empty response → NoLiveDataError", async () => {
    fetchSpy.mockResolvedValueOnce(jsonResponse([]));
    await expect(latest("KNYC")).rejects.toBeInstanceOf(NoLiveDataError);
  });

  it("NoLiveDataError carries station + source on payload", async () => {
    fetchSpy.mockResolvedValueOnce(jsonResponse([]));
    try {
      await latest("knyc"); // lowercase to verify normalization
      throw new Error("expected throw");
    } catch (e) {
      expect(e).toBeInstanceOf(NoLiveDataError);
      const err = e as NoLiveDataError;
      const dict = err.toDict();
      expect(dict.station).toBe("KNYC");
      expect(dict.source).toBe("awc.live");
      expect(dict.error_code).toBe("NO_LIVE_DATA");
    }
  });

  it("returns the most-recent observation when multiple are served", async () => {
    fetchSpy.mockResolvedValueOnce(
      jsonResponse([
        awcMetar(1748170800), // earlier
        awcMetar(1748174400), // latest
        awcMetar(1748171800), // middle
      ]),
    );
    const row = await latest("KNYC");
    // Verify the chosen row matches the 1748174400 metar's observed_at —
    // ISO-8601-Z sorts lexicographically == chronologically.
    const expected = `${new Date(1748174400 * 1000).toISOString().slice(0, 19)}Z`;
    expect(row.observed_at).toBe(expected);
  });

  it("skips unparseable metars and returns the valid one", async () => {
    const bad = { icaoId: "", obsTime: 0 }; // awcToObservation returns null
    fetchSpy.mockResolvedValueOnce(jsonResponse([bad, awcMetar(1748174400)]));
    const row = await latest("KNYC");
    expect(row.station_code).toBe("NYC");
    expect(row.source).toBe("awc.live");
  });

  it("IEM path rejects malformed station codes (URL injection guard)", async () => {
    // Regression for iter-2 codex finding: `fetchIemLatest` interpolates
    // the station code into `buildIemUrl` directly (bypassing
    // `downloadIemAsos`'s year-normalize). The `validateIcao` guard from
    // `downloadIemAsos` was skipped — without an explicit STATION_CODE_RE
    // check, a station like `KNYC&data=foo` would alter the IEM request URL.
    // After the fix, `STATION_CODE_RE` is checked before `buildIemUrl`.
    await expect(latest("KN&data=foo", { source: "iem" })).rejects.toThrow(
      /STATION_CODE_RE/,
    );
    // Verify no HTTP request was issued (validation happens before fetch).
    expect(fetchSpy).not.toHaveBeenCalled();
  });
});

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

  it("IEM path uses exclusive day2 (one-day window per poll)", async () => {
    // Regression for iter-3 codex finding: `fetchIemLatest` previously passed
    // day1==day2 to `buildIemUrl`, but the IEM endpoint treats day2 as
    // EXCLUSIVE — that produced a zero-day request returning no data. Fix
    // passes `nextDayIso(today)` so we get `[today, today+1)` inclusive-start
    // exclusive-end, the expected one-day window.
    const captured: string[] = [];
    fetchSpy.mockImplementation(async (input) => {
      const url = typeof input === "string" ? input : (input as URL).toString();
      captured.push(url);
      return new Response("", { status: 200 });
    });
    // Empty CSV → NoLiveDataError, but we only care that the URL got built
    // with day1 < day2.
    await expect(latest("KNYC", { source: "iem" })).rejects.toThrow();
    expect(captured.length).toBeGreaterThan(0);
    const u = new URL(captured[0]!);
    const y1 = Number(u.searchParams.get("year1"));
    const m1 = Number(u.searchParams.get("month1"));
    const d1 = Number(u.searchParams.get("day1"));
    const y2 = Number(u.searchParams.get("year2"));
    const m2 = Number(u.searchParams.get("month2"));
    const d2 = Number(u.searchParams.get("day2"));
    // After iter-4 codex P2 (previous-day fallback), the window is
    // (yesterday, tomorrow) → a TWO-day span that includes both prev-UTC
    // and current-UTC observations. Iter-3 used a ONE-day window which
    // returned empty right after the 00:00Z rollover. Both invariants
    // still hold: day2 > day1 (no zero-day request) AND the window covers
    // the current UTC date.
    const start = new Date(Date.UTC(y1, m1 - 1, d1));
    const end = new Date(Date.UTC(y2, m2 - 1, d2));
    expect(end.getTime()).toBeGreaterThan(start.getTime());
    const spanDays = (end.getTime() - start.getTime()) / 86_400_000;
    expect(spanDays).toBe(2);
  });

  it("IEM path includes the previous UTC day in the lookup window", async () => {
    // Regression for iter-4 codex P2: a today-only window returns no rows
    // shortly after 00:00 UTC because IEM hasn't ingested the new day's
    // METARs yet. The fix prefixes the window with the previous UTC day so
    // a minutes-old prior-day METAR still surfaces as "latest".
    const captured: string[] = [];
    fetchSpy.mockImplementation(async (input) => {
      const url = typeof input === "string" ? input : (input as URL).toString();
      captured.push(url);
      return new Response("", { status: 200 });
    });
    await expect(latest("KNYC", { source: "iem" })).rejects.toThrow();
    const u = new URL(captured[0]!);
    const start = new Date(
      Date.UTC(
        Number(u.searchParams.get("year1")),
        Number(u.searchParams.get("month1")) - 1,
        Number(u.searchParams.get("day1")),
      ),
    );
    const today = new Date();
    const todayUtc = new Date(
      Date.UTC(today.getUTCFullYear(), today.getUTCMonth(), today.getUTCDate()),
    );
    // start must be < todayUtc (i.e., it's the previous UTC day).
    expect(start.getTime()).toBeLessThan(todayUtc.getTime());
    expect(todayUtc.getTime() - start.getTime()).toBe(86_400_000);
  });

  it("IEM path issues report_type=3 AND report_type=4 (METAR + SPECI)", async () => {
    // Regression for iter-3 codex finding: IEM strips the SPECI keyword
    // from raw METAR text and serves SPECIs only via report_type=4.
    // Routine-only (report_type=3) fetches miss intra-hour specials and
    // `latest()` could return an older METAR when a fresher SPECI exists.
    // Fix issues BOTH requests per poll.
    const reportTypes: number[] = [];
    fetchSpy.mockImplementation(async (input) => {
      const url = typeof input === "string" ? input : (input as URL).toString();
      const rt = Number(new URL(url).searchParams.get("report_type"));
      reportTypes.push(rt);
      return new Response("", { status: 200 });
    });
    await expect(latest("KNYC", { source: "iem" })).rejects.toThrow();
    expect(reportTypes).toContain(3);
    expect(reportTypes).toContain(4);
  });

  it("`live/index` barrel re-exports the documented surface", async () => {
    // Regression for iter-3 codex finding: the `live/` barrel was reachable
    // only via the main `@tradewinds/weather` import; the documented
    // `@tradewinds/weather/live` subpath was NOT in `package.json` exports
    // and was NOT a tsup entry. Phase 11 iter-3 added both.
    //
    // We use a SOURCE-RELATIVE import here (not the bare subpath) because
    // self-imports through the package's own `exports` map resolve to
    // `dist/live/...` during `tsc --noEmit`, which doesn't exist until
    // after build (iter-4 codex P1). The barrel surface itself is the
    // thing we're asserting — its consumability via the subpath is
    // validated separately by the dist-output existence check in the
    // package build step (`tsup` emits `dist/live/index.{mjs,cjs,d.ts}`).
    const mod = await import("../../src/live/index.js");
    expect(typeof mod.stream).toBe("function");
    expect(typeof mod.latest).toBe("function");
    expect(mod.SUPPORTED_SOURCES).toEqual(["awc", "iem"]);
    expect(mod.POLITE_FLOORS_S).toEqual({ awc: 30, iem: 60 });
  });
});

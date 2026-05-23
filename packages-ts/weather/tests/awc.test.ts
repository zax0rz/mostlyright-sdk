// TS-W1 Wave 3 — AWC live-METAR fetcher + parser tests.
//
// Mirrors the parity surface of:
//   - packages/weather/src/tradewinds/weather/_fetchers/awc.py::fetch_awc_metars
//   - packages/weather/src/tradewinds/weather/_awc.py::awc_to_observation
//
// `fetch` is mocked via `vi.spyOn(globalThis, "fetch")`. No msw / no recorded
// fixtures (those land in TS-W2 once the parity gate ports VCR cassettes).

import { type MockInstance, afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  AWC_MAX_HOURS,
  AWC_METAR_URL,
  type AwcMetarRaw,
  fetchAwcMetars,
} from "../src/_fetchers/awc.js";
import {
  awcToObservation,
  icaoToStationCode,
  mapCloudCover,
  parseAwcVisibility,
} from "../src/_parsers/awc.js";

// ---------------------------------------------------------------------------
// Test helpers
// ---------------------------------------------------------------------------

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

function errorResponse(status: number, body = ""): Response {
  return new Response(body, { status });
}

const VALID_AWC_METAR: AwcMetarRaw = {
  icaoId: "KNYC",
  // 2024-01-01T00:00:00Z
  obsTime: 1704067200,
  metarType: "METAR",
  temp: 5.0,
  dewp: -2.0,
  wdir: 270,
  wspd: 8,
  wgst: 12,
  altim: 1013.25,
  slp: 1015.0,
  visib: 10,
  clouds: [{ cover: "FEW", base: 2500 }],
  rawOb: "KNYC 010000Z 27008G12KT 10SM FEW025 05/M02 A2992 RMK AO2",
  wxString: null,
  precip: null,
  qcField: 0,
};

// ---------------------------------------------------------------------------
// Fetcher tests
// ---------------------------------------------------------------------------

describe("fetchAwcMetars — happy path", () => {
  let fetchSpy: MockInstance<typeof fetch>;

  beforeEach(() => {
    fetchSpy = vi.spyOn(globalThis, "fetch");
  });
  afterEach(() => {
    fetchSpy.mockRestore();
  });

  it("returns parsed JSON array on 200", async () => {
    fetchSpy.mockResolvedValueOnce(jsonResponse([VALID_AWC_METAR]));
    const rows = await fetchAwcMetars(["KNYC"]);
    expect(rows).toHaveLength(1);
    expect(rows[0]?.icaoId).toBe("KNYC");
  });

  it("issues GET to the canonical AWC URL with the expected query string", async () => {
    fetchSpy.mockResolvedValueOnce(jsonResponse([]));
    await fetchAwcMetars(["KNYC", "KLAX"]);
    expect(fetchSpy).toHaveBeenCalledTimes(1);
    const calledUrl = String(fetchSpy.mock.calls[0]?.[0]);
    expect(calledUrl.startsWith(AWC_METAR_URL)).toBe(true);
    expect(calledUrl).toContain("ids=KNYC,KLAX");
    expect(calledUrl).toContain("format=json");
    expect(calledUrl).toContain("taf=false");
    expect(calledUrl).toContain(`hours=${AWC_MAX_HOURS}`);
  });

  it("clamps hours above AWC_MAX_HOURS", async () => {
    fetchSpy.mockResolvedValueOnce(jsonResponse([]));
    await fetchAwcMetars(["KNYC"], { hours: 9999 });
    const calledUrl = String(fetchSpy.mock.calls[0]?.[0]);
    expect(calledUrl).toContain(`hours=${AWC_MAX_HOURS}`);
  });

  it("honors hours below the cap", async () => {
    fetchSpy.mockResolvedValueOnce(jsonResponse([]));
    await fetchAwcMetars(["KNYC"], { hours: 6 });
    const calledUrl = String(fetchSpy.mock.calls[0]?.[0]);
    expect(calledUrl).toContain("hours=6");
  });
});

describe("fetchAwcMetars — short-circuits", () => {
  let fetchSpy: MockInstance<typeof fetch>;

  beforeEach(() => {
    fetchSpy = vi.spyOn(globalThis, "fetch");
  });
  afterEach(() => {
    fetchSpy.mockRestore();
  });

  it("returns [] without fetching when station list is empty", async () => {
    const rows = await fetchAwcMetars([]);
    expect(rows).toEqual([]);
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("returns [] when the JSON body is not an array", async () => {
    fetchSpy.mockResolvedValueOnce(jsonResponse({ error: "nope" }));
    const rows = await fetchAwcMetars(["KNYC"]);
    expect(rows).toEqual([]);
  });

  it("returns [] when the body is not valid JSON", async () => {
    fetchSpy.mockResolvedValueOnce(
      new Response("not-json", { status: 200, headers: { "content-type": "text/plain" } }),
    );
    const rows = await fetchAwcMetars(["KNYC"]);
    expect(rows).toEqual([]);
  });
});

describe("fetchAwcMetars — retry + error handling", () => {
  let fetchSpy: MockInstance<typeof fetch>;

  beforeEach(() => {
    fetchSpy = vi.spyOn(globalThis, "fetch");
  });
  afterEach(() => {
    fetchSpy.mockRestore();
  });

  it("retries on 503 then succeeds on 200", async () => {
    fetchSpy
      .mockResolvedValueOnce(errorResponse(503))
      .mockResolvedValueOnce(jsonResponse([VALID_AWC_METAR]));
    const rows = await fetchAwcMetars(["KNYC"], { baseDelayMs: 1, maxRetries: 3 });
    expect(rows).toHaveLength(1);
    expect(fetchSpy).toHaveBeenCalledTimes(2);
  }, 10_000);

  it("returns [] on 404 (never throws)", async () => {
    fetchSpy.mockResolvedValueOnce(errorResponse(404));
    const rows = await fetchAwcMetars(["KNYC"], { baseDelayMs: 1, maxRetries: 1 });
    expect(rows).toEqual([]);
  });

  it("returns [] on 400 (never throws)", async () => {
    fetchSpy.mockResolvedValueOnce(errorResponse(400));
    const rows = await fetchAwcMetars(["KNYC"], { baseDelayMs: 1, maxRetries: 1 });
    expect(rows).toEqual([]);
  });

  it("returns [] when 5xx persists past retry budget", async () => {
    fetchSpy.mockResolvedValue(errorResponse(502));
    const rows = await fetchAwcMetars(["KNYC"], { baseDelayMs: 1, maxRetries: 2 });
    expect(rows).toEqual([]);
  }, 10_000);

  it("returns [] on network failure after retries exhausted", async () => {
    fetchSpy.mockRejectedValue(new TypeError("network down"));
    const rows = await fetchAwcMetars(["KNYC"], { baseDelayMs: 1, maxRetries: 2 });
    expect(rows).toEqual([]);
  }, 10_000);
});

// ---------------------------------------------------------------------------
// Parser unit tests — visibility
// ---------------------------------------------------------------------------

describe("parseAwcVisibility", () => {
  it("handles plain numbers", () => {
    expect(parseAwcVisibility(10)).toBe(10);
    expect(parseAwcVisibility("3")).toBe(3);
  });

  it('handles "10+" → 10', () => {
    expect(parseAwcVisibility("10+")).toBe(10);
  });

  it('handles simple fraction "1/2" → 0.5', () => {
    expect(parseAwcVisibility("1/2")).toBe(0.5);
  });

  it('handles mixed number "2 1/4" → 2.25', () => {
    expect(parseAwcVisibility("2 1/4")).toBe(2.25);
  });

  it('handles METAR less-than prefix "M1/4" → 0.25', () => {
    expect(parseAwcVisibility("M1/4")).toBe(0.25);
  });

  it("returns null on unparseable input", () => {
    expect(parseAwcVisibility("not-a-number")).toBeNull();
  });

  it("returns null on empty + null inputs", () => {
    expect(parseAwcVisibility("")).toBeNull();
    expect(parseAwcVisibility("null")).toBeNull();
    expect(parseAwcVisibility(null)).toBeNull();
    expect(parseAwcVisibility(undefined)).toBeNull();
  });

  it("clamps at MAX_VISIBILITY_MILES = 99.99", () => {
    expect(parseAwcVisibility(1000)).toBe(99.99);
    expect(parseAwcVisibility("1000+")).toBe(99.99);
  });

  it("returns null on division by zero (e.g. '1/0')", () => {
    expect(parseAwcVisibility("1/0")).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// Parser unit tests — cloud cover
// ---------------------------------------------------------------------------

describe("mapCloudCover", () => {
  it("maps known codes", () => {
    expect(mapCloudCover("CLR")).toBe("CLR");
    expect(mapCloudCover("FEW")).toBe("FEW");
    expect(mapCloudCover("SCT")).toBe("SCT");
    expect(mapCloudCover("BKN")).toBe("BKN");
    expect(mapCloudCover("OVC")).toBe("OVC");
    expect(mapCloudCover("VV")).toBe("VV");
    expect(mapCloudCover("SKC")).toBe("SKC");
  });

  it("normalizes CAVOK → CLR", () => {
    expect(mapCloudCover("CAVOK")).toBe("CLR");
  });

  it("returns null for unknown codes", () => {
    expect(mapCloudCover("WXYZ")).toBeNull();
    expect(mapCloudCover("")).toBeNull();
    expect(mapCloudCover(null)).toBeNull();
    expect(mapCloudCover(undefined)).toBeNull();
  });

  it("is case-insensitive on input", () => {
    expect(mapCloudCover("clr")).toBe("CLR");
    expect(mapCloudCover("Few")).toBe("FEW");
  });
});

// ---------------------------------------------------------------------------
// Parser unit tests — icaoToStationCode
// ---------------------------------------------------------------------------

describe("icaoToStationCode", () => {
  it("strips leading K from 4-letter CONUS ICAO", () => {
    expect(icaoToStationCode("KNYC")).toBe("NYC");
    expect(icaoToStationCode("KLAX")).toBe("LAX");
  });

  it("passes non-K 4-letter codes through unchanged", () => {
    expect(icaoToStationCode("EGLL")).toBe("EGLL");
    expect(icaoToStationCode("EDDB")).toBe("EDDB");
  });

  it("uppercases lowercase input", () => {
    expect(icaoToStationCode("knyc")).toBe("NYC");
  });

  it("trims whitespace", () => {
    expect(icaoToStationCode("  KNYC  ")).toBe("NYC");
  });

  it("leaves short codes alone (used for downstream regex filter)", () => {
    expect(icaoToStationCode("NYC")).toBe("NYC");
  });
});

// ---------------------------------------------------------------------------
// Parser unit tests — awcToObservation
// ---------------------------------------------------------------------------

describe("awcToObservation — happy path", () => {
  it("produces a fully populated row for a valid METAR", () => {
    const row = awcToObservation({
      icaoId: "KNYC",
      obsTime: 1704067200,
      temp: 5.0,
      dewp: -2.0,
      // No RMK so no T-group override → body-group values persist.
      rawOb: "KNYC 010000Z 27008KT 10SM CLR 05/M02 A2992",
    });

    expect(row).not.toBeNull();
    if (!row) throw new Error("row is null");
    expect(row.station_code).toBe("NYC");
    expect(row.observed_at).toBe("2024-01-01T00:00:00Z");
    expect(row.observation_type).toBe("METAR");
    expect(row.source).toBe("awc.live");
    expect(row.temp_c).toBe(5.0);
    expect(row.dewpoint_c).toBe(-2.0);
    // temp_f = 5 * 9/5 + 32 = 41
    expect(row.temp_f).toBe(41);
    // dewpoint_f = -2 * 9/5 + 32 = 28.4
    expect(row.dewpoint_f).toBeCloseTo(28.4, 5);
    expect(row.raw_metar).toBe("KNYC 010000Z 27008KT 10SM CLR 05/M02 A2992");
    expect(row.snow_depth_inches).toBeNull();
  });

  it("normalizes metarType=SPECI to observation_type=SPECI", () => {
    const row = awcToObservation({
      icaoId: "KNYC",
      obsTime: 1704067200,
      metarType: "SPECI",
    });
    expect(row?.observation_type).toBe("SPECI");
  });

  it("defaults missing metarType to METAR", () => {
    const row = awcToObservation({ icaoId: "KNYC", obsTime: 1704067200 });
    expect(row?.observation_type).toBe("METAR");
  });

  it("converts altimeter hPa → inHg", () => {
    const row = awcToObservation({ icaoId: "KNYC", obsTime: 1704067200, altim: 1000 });
    // 1000 hPa * 0.0295299875 = 29.5299875
    expect(row?.altimeter_inhg).toBeCloseTo(29.5299875, 6);
  });

  it("parses up to 4 cloud layers + drops 5th", () => {
    const row = awcToObservation({
      icaoId: "KNYC",
      obsTime: 1704067200,
      clouds: [
        { cover: "FEW", base: 1000 },
        { cover: "SCT", base: 3000 },
        { cover: "BKN", base: 6000 },
        { cover: "OVC", base: 12000 },
        { cover: "BKN", base: 25000 },
      ],
    });
    expect(row?.sky_cover_1).toBe("FEW");
    expect(row?.sky_base_1_ft).toBe(1000);
    expect(row?.sky_cover_4).toBe("OVC");
    expect(row?.sky_base_4_ft).toBe(12000);
  });

  it("populates peak wind from RMK PK WND", () => {
    const row = awcToObservation({
      icaoId: "KNYC",
      obsTime: 1704067200,
      rawOb: "KNYC 010000Z 27015G25KT 10SM CLR 05/M02 A2992 RMK AO2 PK WND 28032/2355",
    });
    expect(row?.peak_wind_dir).toBe(280);
    expect(row?.peak_wind_gust_kt).toBe(32);
    expect(row?.peak_wind_time).toBe("2355");
  });

  it("uses RMK T-group for tenths-precision temperature override", () => {
    // T02560167 → temp 25.6 °C / dewp 16.7 °C
    const row = awcToObservation({
      icaoId: "KNYC",
      obsTime: 1704067200,
      temp: 26, // body group whole-degree
      dewp: 17,
      rawOb: "KNYC 010000Z 27015KT 10SM CLR 26/17 A2992 RMK AO2 T02560167",
    });
    expect(row?.temp_c).toBeCloseTo(25.6, 5);
    expect(row?.dewpoint_c).toBeCloseTo(16.7, 5);
  });
});

describe("awcToObservation — rejections", () => {
  it("returns null when icaoId is missing", () => {
    expect(awcToObservation({ obsTime: 1704067200 } as unknown as AwcMetarRaw)).toBeNull();
  });

  it("returns null when icaoId is empty string", () => {
    expect(awcToObservation({ icaoId: "", obsTime: 1704067200 } as AwcMetarRaw)).toBeNull();
  });

  it("returns null when obsTime is missing", () => {
    expect(awcToObservation({ icaoId: "KNYC" } as unknown as AwcMetarRaw)).toBeNull();
  });

  it("returns null when station code fails STATION_CODE_RE (e.g. ICAO with digits)", () => {
    expect(awcToObservation({ icaoId: "12AB", obsTime: 1704067200 } as AwcMetarRaw)).toBeNull();
  });

  it("returns null when obsTime produces a year outside 1970..2100", () => {
    // 4102444800 = 2100-01-01 → OK; 8000000000 → 2223 → reject
    expect(awcToObservation({ icaoId: "KNYC", obsTime: 8000000000 } as AwcMetarRaw)).toBeNull();
  });
});

describe("awcToObservation — bounds enforcement", () => {
  it("drops out-of-range temperature to null", () => {
    const row = awcToObservation({
      icaoId: "KNYC",
      obsTime: 1704067200,
      temp: 999, // > TEMP_MAX_C (60)
    });
    expect(row?.temp_c).toBeNull();
    expect(row?.temp_f).toBeNull();
  });

  it("drops out-of-range SLP to null", () => {
    const row = awcToObservation({
      icaoId: "KNYC",
      obsTime: 1704067200,
      slp: 99999,
    });
    expect(row?.sea_level_pressure_mb).toBeNull();
  });

  it('treats wdir "VRB" as null (variable wind)', () => {
    const row = awcToObservation({
      icaoId: "KNYC",
      obsTime: 1704067200,
      wdir: "VRB",
    });
    expect(row?.wind_dir_degrees).toBeNull();
  });

  it("normalizes precip 'T' (trace) to 0.0", () => {
    const row = awcToObservation({
      icaoId: "KNYC",
      obsTime: 1704067200,
      precip: "T",
    });
    expect(row?.precip_1hr_inches).toBe(0);
  });
});

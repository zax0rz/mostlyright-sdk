import { NotFoundError } from "@mostlyright/core";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { MockInstance } from "vitest";

import {
  IEM_CLI_BASE_URL,
  IEM_CLI_POLITE_DELAY_MS,
  downloadCli,
  downloadCliRange,
} from "../src/_fetchers/iem-cli.js";
import type { CliRawRecord } from "../src/_fetchers/iem-cli.js";
import {
  HIGH_TEMP_MAX_F,
  inferReportType,
  parseCliRecord,
  parseCliResponse,
} from "../src/_parsers/cli.js";

type FetchFn = typeof globalThis.fetch;
let fetchSpy: MockInstance<FetchFn>;

beforeEach(() => {
  fetchSpy = vi.spyOn(globalThis, "fetch") as unknown as MockInstance<FetchFn>;
});

afterEach(() => {
  fetchSpy.mockRestore();
  vi.restoreAllMocks();
});

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

function emptyJsonResponse(status: number): Response {
  // 404s carry no body in the IEM contract, but Response needs a string.
  return new Response("", {
    status,
    headers: { "content-type": "text/plain" },
  });
}

describe("downloadCli — URL + happy path", () => {
  it("hits the documented endpoint with station + year query params", async () => {
    fetchSpy.mockResolvedValueOnce(jsonResponse(200, []));
    await downloadCli("KNYC", 2025);
    const url = fetchSpy.mock.calls[0]?.[0] as string;
    expect(url).toBe(`${IEM_CLI_BASE_URL}?station=KNYC&year=2025`);
  });

  it("returns the bare array body when IEM returns a list", async () => {
    const records: CliRawRecord[] = [
      { valid: "2025-01-15", high: 45, low: 30, product: "202501160620-KFFC-CDUS42-CLIATL" },
      { valid: "2025-01-16", high: 50, low: 32, product: "202501170620-KFFC-CDUS42-CLIATL" },
    ];
    fetchSpy.mockResolvedValueOnce(jsonResponse(200, records));
    const out = await downloadCli("KNYC", 2025);
    expect(out).toEqual(records);
  });

  it("unwraps {results: [...]}-wrapped responses transparently", async () => {
    const records: CliRawRecord[] = [{ valid: "2025-01-15", high: 45, low: 30 }];
    fetchSpy.mockResolvedValueOnce(jsonResponse(200, { results: records }));
    const out = await downloadCli("KNYC", 2025);
    expect(out).toEqual(records);
  });

  it("returns [] for empty payloads", async () => {
    fetchSpy.mockResolvedValueOnce(jsonResponse(200, []));
    const out = await downloadCli("KNYC", 2025);
    expect(out).toEqual([]);

    fetchSpy.mockResolvedValueOnce(jsonResponse(200, { results: [] }));
    const out2 = await downloadCli("KNYC", 2025);
    expect(out2).toEqual([]);
  });

  it("throws when IEM returns an unexpected shape", async () => {
    fetchSpy.mockResolvedValueOnce(jsonResponse(200, { something: "else" }));
    await expect(downloadCli("KNYC", 2025)).rejects.toThrow(/Unexpected IEM CLI response shape/);
  });
});

describe("downloadCli — input validation", () => {
  it("rejects bogus station codes before any HTTP call", async () => {
    await expect(downloadCli("../etc/passwd", 2025)).rejects.toThrow(/STATION_CODE_RE/);
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("rejects 5-letter codes (must be 3-4 uppercase letters)", async () => {
    await expect(downloadCli("KNYCS", 2025)).rejects.toThrow(/STATION_CODE_RE/);
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("accepts 3-letter NWS codes (e.g. NYC)", async () => {
    fetchSpy.mockResolvedValueOnce(jsonResponse(200, []));
    await expect(downloadCli("NYC", 2025)).resolves.toEqual([]);
  });
});

describe("downloadCli — 404 surfaces NotFoundError", () => {
  it("propagates NotFoundError from fetchWithRetry on HTTP 404", async () => {
    fetchSpy.mockResolvedValueOnce(emptyJsonResponse(404));
    await expect(downloadCli("KNYC", 1850)).rejects.toBeInstanceOf(NotFoundError);
  });
});

describe("downloadCliRange — multi-year + 404 skip", () => {
  it("concatenates records across an inclusive year range", async () => {
    fetchSpy
      .mockResolvedValueOnce(jsonResponse(200, [{ valid: "2023-01-01", high: 40, low: 20 }]))
      .mockResolvedValueOnce(jsonResponse(200, [{ valid: "2024-01-01", high: 41, low: 21 }]))
      .mockResolvedValueOnce(jsonResponse(200, [{ valid: "2025-01-01", high: 42, low: 22 }]));
    const out = await downloadCliRange("KNYC", 2023, 2025, { politenessMs: 0 });
    expect(out).toHaveLength(3);
    expect(out.map((r) => r.valid)).toEqual(["2023-01-01", "2024-01-01", "2025-01-01"]);
    expect(fetchSpy).toHaveBeenCalledTimes(3);
  });

  it("skips the year that returns 404 and continues with later years", async () => {
    fetchSpy
      .mockResolvedValueOnce(jsonResponse(200, [{ valid: "2023-01-01", high: 40, low: 20 }]))
      .mockResolvedValueOnce(emptyJsonResponse(404))
      .mockResolvedValueOnce(jsonResponse(200, [{ valid: "2025-01-01", high: 42, low: 22 }]));
    const out = await downloadCliRange("KNYC", 2023, 2025, { politenessMs: 0 });
    expect(out).toHaveLength(2);
    expect(out.map((r) => r.valid)).toEqual(["2023-01-01", "2025-01-01"]);
    expect(fetchSpy).toHaveBeenCalledTimes(3);
  });

  it("rejects when endYear < startYear", async () => {
    await expect(downloadCliRange("KNYC", 2025, 2024)).rejects.toThrow(/must be >= startYear/);
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("exposes IEM_CLI_POLITE_DELAY_MS = 1000 (matches Python parity)", () => {
    expect(IEM_CLI_POLITE_DELAY_MS).toBe(1000);
  });
});

// ---------------------------------------------------------------------------
// Parser unit tests
// ---------------------------------------------------------------------------

describe("inferReportType — Python-parity rules", () => {
  it("no product → preliminary (safe default)", () => {
    expect(inferReportType(null, "2025-01-15")).toBe("preliminary");
    expect(inferReportType(undefined, "2025-01-15")).toBe("preliminary");
    expect(inferReportType("", "2025-01-15")).toBe("preliminary");
  });

  it("unparseable product → preliminary", () => {
    expect(inferReportType("not-a-timestamp", "2025-01-15")).toBe("preliminary");
  });

  it("issued same day as observation → preliminary", () => {
    // Observation 2025-01-15, issued 2025-01-15 21:00 UTC
    expect(inferReportType("202501152100-KFFC-CDUS42-CLIATL", "2025-01-15")).toBe("preliminary");
  });

  it("issued next day 04:00-10:00 UTC → final (overnight CLI window)", () => {
    // Observation 2025-01-15, issued 2025-01-16 06:20 UTC
    expect(inferReportType("202501160620-KFFC-CDUS42-CLIATL", "2025-01-15")).toBe("final");
    // Boundary: 04:00 → final
    expect(inferReportType("202501160400-KFFC-CDUS42-CLIATL", "2025-01-15")).toBe("final");
    // Boundary: 10:59 → final (Python uses 4 <= hour <= 10, hour=10 inclusive)
    expect(inferReportType("202501161059-KFFC-CDUS42-CLIATL", "2025-01-15")).toBe("final");
  });

  it("issued next day outside overnight window → correction", () => {
    // 11:00 UTC → outside [4,10]
    expect(inferReportType("202501161100-KFFC-CDUS42-CLIATL", "2025-01-15")).toBe("correction");
    // 03:59 UTC → outside [4,10] on the low side
    expect(inferReportType("202501160359-KFFC-CDUS42-CLIATL", "2025-01-15")).toBe("correction");
  });

  it("issued >1 day later → correction", () => {
    // Observation 2025-01-15, issued 2025-01-17 06:20 UTC
    expect(inferReportType("202501170620-KFFC-CDUS42-CLIATL", "2025-01-15")).toBe("correction");
  });

  it("invalid observation date string → preliminary", () => {
    expect(inferReportType("202501160620-KFFC-CDUS42-CLIATL", "not-a-date")).toBe("preliminary");
    // Calendar-invalid (Feb 30) → preliminary
    expect(inferReportType("202501160620-KFFC-CDUS42-CLIATL", "2025-02-30")).toBe("preliminary");
  });
});

describe("parseCliRecord — happy path", () => {
  it("populates all fields for a typical overnight-final record", () => {
    const rec: CliRawRecord = {
      valid: "2025-01-15",
      high: 45,
      low: 30,
      product: "202501160620-KFFC-CDUS42-CLIATL",
    };
    const out = parseCliRecord(rec, "NYC");
    expect(out).not.toBeNull();
    expect(out).toEqual({
      station_code: "NYC",
      observation_date: "2025-01-15",
      high_temp_f: 45,
      low_temp_f: 30,
      report_type: "final",
      report_type_priority: 3,
      source: "iem",
      product_id: "202501160620-KFFC-CDUS42-CLIATL",
      issued_at: "2025-01-16T06:20:00Z",
    });
  });

  it("returns null when valid is missing", () => {
    expect(parseCliRecord({ valid: "" } as CliRawRecord, "NYC")).toBeNull();
  });

  it("returns null when valid is calendar-invalid", () => {
    expect(parseCliRecord({ valid: "2025-02-30", high: 45 } as CliRawRecord, "NYC")).toBeNull();
  });

  it("returns null when BOTH high and low are missing", () => {
    expect(
      parseCliRecord({ valid: "2025-01-15", high: "M", low: "" } as CliRawRecord, "NYC"),
    ).toBeNull();
    expect(
      parseCliRecord({ valid: "2025-01-15", high: null, low: null } as CliRawRecord, "NYC"),
    ).toBeNull();
  });

  it("treats 'M' and empty string as missing sentinels for individual temps", () => {
    const out = parseCliRecord({ valid: "2025-01-15", high: "M", low: 30 } as CliRawRecord, "NYC");
    expect(out?.high_temp_f).toBeNull();
    expect(out?.low_temp_f).toBe(30);
  });

  it("drops high above HIGH_TEMP_MAX_F (200 > 150)", () => {
    const out = parseCliRecord({ valid: "2025-01-15", high: 200, low: 30 } as CliRawRecord, "NYC");
    expect(out?.high_temp_f).toBeNull();
    expect(out?.low_temp_f).toBe(30);
    expect(HIGH_TEMP_MAX_F).toBe(150);
  });

  it("drops high below HIGH_TEMP_MIN_F (-100 < -60)", () => {
    const out = parseCliRecord({ valid: "2025-01-15", high: -100, low: 30 } as CliRawRecord, "NYC");
    expect(out?.high_temp_f).toBeNull();
    expect(out?.low_temp_f).toBe(30);
  });

  it("drops low out-of-bounds independently", () => {
    const out = parseCliRecord({ valid: "2025-01-15", high: 45, low: -100 } as CliRawRecord, "NYC");
    expect(out?.high_temp_f).toBe(45);
    expect(out?.low_temp_f).toBeNull();
  });

  it("rounds non-integer temps (round-half-up) to match expected CLI integer semantics", () => {
    const out = parseCliRecord(
      { valid: "2025-01-15", high: 45.6, low: 29.4 } as CliRawRecord,
      "NYC",
    );
    expect(out?.high_temp_f).toBe(46);
    expect(out?.low_temp_f).toBe(29);
  });

  it("issued_at parses correctly from product first-12 chars", () => {
    const out = parseCliRecord(
      {
        valid: "2025-01-15",
        high: 45,
        low: 30,
        product: "202501160620-KFFC-CDUS42-CLIATL",
      } as CliRawRecord,
      "NYC",
    );
    expect(out?.issued_at).toBe("2025-01-16T06:20:00Z");
  });

  it("issued_at is null when product is missing", () => {
    const out = parseCliRecord({ valid: "2025-01-15", high: 45 } as CliRawRecord, "NYC");
    expect(out?.product_id).toBeNull();
    expect(out?.issued_at).toBeNull();
    expect(out?.report_type).toBe("preliminary");
  });

  it("issued_at is null when product timestamp is unparseable", () => {
    const out = parseCliRecord(
      { valid: "2025-01-15", high: 45, product: "bogus" } as CliRawRecord,
      "NYC",
    );
    expect(out?.product_id).toBe("bogus");
    expect(out?.issued_at).toBeNull();
    expect(out?.report_type).toBe("preliminary");
  });

  it("preserves source='iem' constant and report_type_priority from codegen", () => {
    const out = parseCliRecord(
      {
        valid: "2025-01-15",
        high: 45,
        low: 30,
        product: "202501160620-KFFC-CDUS42-CLIATL",
      } as CliRawRecord,
      "NYC",
    );
    expect(out?.source).toBe("iem");
    expect(out?.report_type_priority).toBe(3); // final
  });
});

describe("parseCliResponse — end-to-end through fetcher", () => {
  it("threads downloadCli → parseCliResponse with station_code=NYC and source=iem", async () => {
    const records: CliRawRecord[] = [
      { valid: "2025-01-15", high: 45, low: 30, product: "202501160620-KFFC-CDUS42-CLIATL" },
      { valid: "2025-01-16", high: 50, low: 32, product: "202501170620-KFFC-CDUS42-CLIATL" },
      // This one drops — both temps missing.
      { valid: "2025-01-17", high: "M", low: "M", product: "" },
    ];
    fetchSpy.mockResolvedValueOnce(jsonResponse(200, records));
    const raw = await downloadCli("KNYC", 2025);
    const parsed = parseCliResponse(raw, "NYC");
    expect(parsed).toHaveLength(2);
    for (const row of parsed) {
      expect(row.station_code).toBe("NYC");
      expect(row.source).toBe("iem");
    }
  });

  it("filters out unparseable-date records without throwing", () => {
    const records: CliRawRecord[] = [
      { valid: "2025-01-15", high: 45, low: 30 },
      { valid: "not-a-date", high: 45, low: 30 } as unknown as CliRawRecord,
      { valid: "2025-02-30", high: 45, low: 30 } as CliRawRecord,
    ];
    const parsed = parseCliResponse(records, "NYC");
    expect(parsed).toHaveLength(1);
    expect(parsed[0]?.observation_date).toBe("2025-01-15");
  });
});

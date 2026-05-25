// TS-W2 Plan 01 Task 3 — IEM CSV parser tests.
//
// Byte-faithful port of Python
// `packages/weather/src/mostlyright/weather/_iem.py::iem_to_observation`
// + `parse_iem_file`. CSV bodies are passed as strings (the TS fetcher
// returns in-memory bodies — no Path/file I/O).
//
// Coverage targets the plan's 9 behavioral assertions:
//   1. `#`-prefix comment stripping (header still parsed correctly)
//   2. `M` / empty → null for numeric fields
//   3. `T` → 0.0 for precip; T → null for other numeric fields
//   4. Timestamp `YYYY-MM-DD HH:MM` → ISO 8601 UTC `…T…:00Z`
//   5. SPECI auto-detect from leading `SPECI ` in metar text
//   6. observationTypeOverride forces type regardless of metar text
//   7. Skip-row: all 4 key vars (tmpf/dwpf/sknt/mslp) missing → null
//   8. Out-of-bounds consistency: bad raw → both °C AND °F nulled
//   9. Bad override value throws synchronously

import { describe, expect, it } from "vitest";

import type { Observation } from "../src/_parsers/awc.js";
import { iemToObservation, parseIemCsv } from "../src/_parsers/iem.js";

const HEADER =
  "station,valid,tmpf,dwpf,drct,sknt,gust,alti,mslp,vsby,skyc1,skyl1,skyc2,skyl2,skyc3,skyl3,skyc4,skyl4,wxcodes,p01i,snowdepth,peak_wind_gust,peak_wind_drct,peak_wind_time,metar";

function makeRow(overrides: Record<string, string> = {}): string {
  const defaults: Record<string, string> = {
    station: "KNYC",
    valid: "2025-01-01 00:51",
    tmpf: "32",
    dwpf: "28",
    drct: "180",
    sknt: "8",
    gust: "",
    alti: "29.92",
    mslp: "1013.2",
    vsby: "10",
    skyc1: "FEW",
    skyl1: "2500",
    skyc2: "",
    skyl2: "",
    skyc3: "",
    skyl3: "",
    skyc4: "",
    skyl4: "",
    wxcodes: "",
    p01i: "",
    snowdepth: "",
    peak_wind_gust: "",
    peak_wind_drct: "",
    peak_wind_time: "",
    metar: "KNYC 010051Z 18008KT 10SM FEW025 00/M02 A2992 RMK AO2",
    ...overrides,
  };
  const cols = HEADER.split(",");
  return cols.map((c) => defaults[c] ?? "").join(",");
}

function csvBody(rows: string[], commentLines: string[] = []): string {
  const parts: string[] = [];
  for (const c of commentLines) parts.push(`# ${c}`);
  parts.push(HEADER);
  for (const r of rows) parts.push(r);
  return `${parts.join("\n")}\n`;
}

describe("parseIemCsv — comment-line stripping", () => {
  it("strips three # header lines and still parses the data header correctly", () => {
    const body = csvBody(
      [makeRow()],
      [
        "Data Source: Iowa Environmental Mesonet",
        "Generated: 2026-01-01",
        "Disclaimer: see https://mesonet.agron.iastate.edu/",
      ],
    );
    const out = parseIemCsv(body);
    expect(out).toHaveLength(1);
    expect(out[0]?.station_code).toBe("NYC");
  });

  it("returns empty array when CSV body has only comments + header (no data rows)", () => {
    const body = csvBody([], ["only comments"]);
    expect(parseIemCsv(body)).toEqual([]);
  });

  it("returns empty array on empty input", () => {
    expect(parseIemCsv("")).toEqual([]);
  });
});

describe("iemToObservation — M sentinel handling", () => {
  it("parses M as null for tmpf, dwpf, drct, sknt", () => {
    const out = parseIemCsv(
      csvBody([makeRow({ tmpf: "M", dwpf: "M", drct: "M", sknt: "8", mslp: "M" })]),
    );
    // sknt=8 keeps the row alive (one of the 4 key vars present).
    expect(out).toHaveLength(1);
    const row = out[0] as Observation;
    expect(row.temp_c).toBeNull();
    expect(row.temp_f).toBeNull();
    expect(row.dewpoint_c).toBeNull();
    expect(row.dewpoint_f).toBeNull();
    expect(row.wind_dir_degrees).toBeNull();
    expect(row.wind_speed_kt).toBe(8);
    expect(row.sea_level_pressure_mb).toBeNull();
  });

  it("parses empty-string as null", () => {
    const out = parseIemCsv(csvBody([makeRow({ alti: "", mslp: "1013.0" })]));
    expect(out).toHaveLength(1);
    expect(out[0]?.altimeter_inhg).toBeNull();
    expect(out[0]?.sea_level_pressure_mb).toBe(1013);
  });
});

describe("iemToObservation — T (trace) sentinel handling", () => {
  it("p01i='T' → precip_1hr_inches: 0.0", () => {
    const out = parseIemCsv(csvBody([makeRow({ p01i: "T" })]));
    expect(out).toHaveLength(1);
    expect(out[0]?.precip_1hr_inches).toBe(0);
  });

  it("p01i='0.25' → precip_1hr_inches: 0.25 (numeric passthrough)", () => {
    const out = parseIemCsv(csvBody([makeRow({ p01i: "0.25" })]));
    expect(out[0]?.precip_1hr_inches).toBe(0.25);
  });

  it("T only valid for precip — tmpf='T' is non-numeric → temp_c null", () => {
    const out = parseIemCsv(csvBody([makeRow({ tmpf: "T", mslp: "1013.0" })]));
    // mslp keeps row alive
    expect(out).toHaveLength(1);
    expect(out[0]?.temp_c).toBeNull();
    expect(out[0]?.temp_f).toBeNull();
  });
});

describe("iemToObservation — timestamp roundtrip", () => {
  it("'2025-01-01 00:51' → '2025-01-01T00:51:00Z'", () => {
    const out = parseIemCsv(csvBody([makeRow({ valid: "2025-01-01 00:51" })]));
    expect(out[0]?.observed_at).toBe("2025-01-01T00:51:00Z");
  });

  it("rejects malformed timestamps → row dropped", () => {
    const out = parseIemCsv(csvBody([makeRow({ valid: "not-a-timestamp" })]));
    expect(out).toEqual([]);
  });

  it("rejects calendar-invalid timestamps (Feb 30) → row dropped", () => {
    const out = parseIemCsv(csvBody([makeRow({ valid: "2025-02-30 12:00" })]));
    expect(out).toEqual([]);
  });

  it("rejects year out of [MIN_YEAR, MAX_YEAR] → row dropped", () => {
    const out = parseIemCsv(csvBody([makeRow({ valid: "1900-01-01 12:00" })]));
    expect(out).toEqual([]);
  });
});

describe("iemToObservation — observation type detection", () => {
  it("metar starts with 'SPECI ' → observation_type: SPECI when override unset", () => {
    const out = parseIemCsv(
      csvBody([makeRow({ metar: "SPECI KJFK 010051Z 18008KT 10SM FEW025 00/M02 A2992" })]),
    );
    expect(out[0]?.observation_type).toBe("SPECI");
  });

  it("plain METAR text → observation_type: METAR (default)", () => {
    const out = parseIemCsv(csvBody([makeRow()]));
    expect(out[0]?.observation_type).toBe("METAR");
  });

  it("observationTypeOverride='METAR' forces METAR even on SPECI-text row", () => {
    const out = parseIemCsv(
      csvBody([makeRow({ metar: "SPECI KJFK 010051Z 18008KT 10SM FEW025 00/M02 A2992" })]),
      { observationTypeOverride: "METAR" },
    );
    expect(out[0]?.observation_type).toBe("METAR");
  });

  it("observationTypeOverride='SPECI' forces SPECI on plain-METAR text", () => {
    const out = parseIemCsv(csvBody([makeRow()]), {
      observationTypeOverride: "SPECI",
    });
    expect(out[0]?.observation_type).toBe("SPECI");
  });

  it("throws on bad observationTypeOverride", () => {
    expect(() =>
      iemToObservation(
        {
          station: "KNYC",
          valid: "2025-01-01 00:51",
          tmpf: "32",
          dwpf: "28",
          drct: "180",
          sknt: "8",
          mslp: "1013.0",
          metar: "KNYC ...",
        },
        // biome-ignore lint/suspicious/noExplicitAny: testing runtime validation
        { observationTypeOverride: "foo" as any },
      ),
    ).toThrow(/observation.?type/i);
  });
});

describe("iemToObservation — row-skip semantics", () => {
  it("skips row when station is empty", () => {
    expect(parseIemCsv(csvBody([makeRow({ station: "" })]))).toEqual([]);
  });

  it("skips row when station is M", () => {
    expect(parseIemCsv(csvBody([makeRow({ station: "M" })]))).toEqual([]);
  });

  it("skips row when ALL 4 key vars (tmpf/dwpf/sknt/mslp) are empty", () => {
    expect(
      parseIemCsv(
        csvBody([makeRow({ tmpf: "", dwpf: "", sknt: "", mslp: "", gust: "", alti: "" })]),
      ),
    ).toEqual([]);
  });

  it("skips row when ALL 4 key vars are M", () => {
    expect(
      parseIemCsv(
        csvBody([makeRow({ tmpf: "M", dwpf: "M", sknt: "M", mslp: "M", gust: "M", alti: "M" })]),
      ),
    ).toEqual([]);
  });

  it("keeps row when at least one key var (sknt) is present", () => {
    const out = parseIemCsv(csvBody([makeRow({ tmpf: "", dwpf: "", sknt: "5", mslp: "" })]));
    expect(out).toHaveLength(1);
  });
});

describe("iemToObservation — out-of-bounds consistency", () => {
  it("tmpf=2000 (out of bounds) → both temp_c AND temp_f null", () => {
    const out = parseIemCsv(csvBody([makeRow({ tmpf: "2000" })]));
    // mslp=1013.2 in defaults keeps row alive.
    expect(out).toHaveLength(1);
    expect(out[0]?.temp_c).toBeNull();
    expect(out[0]?.temp_f).toBeNull();
    // dwpf=28 → ~-2.2°C still in bounds, so dewpoint stays populated.
    expect(out[0]?.dewpoint_f).toBe(28);
  });

  it("dwpf=-999 (out of bounds) → both dewpoint_c AND dewpoint_f null", () => {
    const out = parseIemCsv(csvBody([makeRow({ dwpf: "-999" })]));
    expect(out).toHaveLength(1);
    expect(out[0]?.dewpoint_c).toBeNull();
    expect(out[0]?.dewpoint_f).toBeNull();
    expect(out[0]?.temp_f).toBe(32);
  });
});

describe("iemToObservation — multi-column sky expansion", () => {
  it("expands 4 sky cover/base pairs from skyc{1..4}/skyl{1..4}", () => {
    const out = parseIemCsv(
      csvBody([
        makeRow({
          skyc1: "FEW",
          skyl1: "2500",
          skyc2: "SCT",
          skyl2: "5000",
          skyc3: "BKN",
          skyl3: "10000",
          skyc4: "OVC",
          skyl4: "25000",
        }),
      ]),
    );
    const row = out[0] as Observation;
    expect(row.sky_cover_1).toBe("FEW");
    expect(row.sky_base_1_ft).toBe(2500);
    expect(row.sky_cover_2).toBe("SCT");
    expect(row.sky_base_2_ft).toBe(5000);
    expect(row.sky_cover_3).toBe("BKN");
    expect(row.sky_base_3_ft).toBe(10000);
    expect(row.sky_cover_4).toBe("OVC");
    expect(row.sky_base_4_ft).toBe(25000);
  });

  it("missing higher sky cols default to null", () => {
    const out = parseIemCsv(csvBody([makeRow()]));
    const row = out[0] as Observation;
    expect(row.sky_cover_1).toBe("FEW");
    expect(row.sky_base_1_ft).toBe(2500);
    expect(row.sky_cover_2).toBeNull();
    expect(row.sky_base_2_ft).toBeNull();
    expect(row.sky_cover_3).toBeNull();
    expect(row.sky_base_3_ft).toBeNull();
    expect(row.sky_cover_4).toBeNull();
    expect(row.sky_base_4_ft).toBeNull();
  });
});

describe("iemToObservation — output shape", () => {
  it("produces 30 fields in the canonical Python key order", () => {
    const out = parseIemCsv(csvBody([makeRow()]));
    expect(out).toHaveLength(1);
    const row = out[0] as Observation;
    const keys = Object.keys(row);
    // 30 fields per Python iem_to_observation return dict.
    expect(keys).toHaveLength(30);
    // Order must match Python's return-dict literal — downstream diff
    // tooling relies on JSON.stringify producing identical byte output.
    expect(keys).toEqual([
      "station_code",
      "observed_at",
      "observation_type",
      "source",
      "temp_c",
      "dewpoint_c",
      "temp_f",
      "dewpoint_f",
      "wind_dir_degrees",
      "wind_speed_kt",
      "wind_gust_kt",
      "altimeter_inhg",
      "sea_level_pressure_mb",
      "sky_cover_1",
      "sky_base_1_ft",
      "sky_cover_2",
      "sky_base_2_ft",
      "sky_cover_3",
      "sky_base_3_ft",
      "sky_cover_4",
      "sky_base_4_ft",
      "visibility_miles",
      "weather_codes",
      "precip_1hr_inches",
      "peak_wind_gust_kt",
      "peak_wind_dir",
      "peak_wind_time",
      "snow_depth_inches",
      "qc_field",
      "raw_metar",
    ]);
  });

  it("always emits source='iem'", () => {
    const out = parseIemCsv(csvBody([makeRow()]));
    expect(out[0]?.source).toBe("iem");
  });

  it("strips leading 'K' from 4-letter ICAOs (KNYC → NYC)", () => {
    const out = parseIemCsv(csvBody([makeRow({ station: "KNYC" })]));
    expect(out[0]?.station_code).toBe("NYC");
  });

  it("preserves raw_metar passthrough (truncated at MAX_RAW_METAR_LEN)", () => {
    const longMetar = `KNYC 010051Z 18008KT 10SM FEW025 00/M02 A2992 RMK ${"X".repeat(3000)}`;
    const out = parseIemCsv(csvBody([makeRow({ metar: longMetar })]));
    const row = out[0] as Observation;
    expect(row.raw_metar).not.toBeNull();
    // MAX_RAW_METAR_LEN = 2048 per @mostlyrightmd/core/internal/bounds
    expect((row.raw_metar as string).length).toBe(2048);
  });
});

describe("iemToObservation — peak wind parsing", () => {
  it("'2025-01-01 01:31' → peak_wind_time: '0131'", () => {
    const out = parseIemCsv(
      csvBody([
        makeRow({
          peak_wind_gust: "35",
          peak_wind_drct: "210",
          peak_wind_time: "2025-01-01 01:31",
        }),
      ]),
    );
    const row = out[0] as Observation;
    expect(row.peak_wind_gust_kt).toBe(35);
    expect(row.peak_wind_dir).toBe(210);
    expect(row.peak_wind_time).toBe("0131");
  });

  it("missing peak wind fields → null", () => {
    const out = parseIemCsv(csvBody([makeRow()]));
    expect(out[0]?.peak_wind_gust_kt).toBeNull();
    expect(out[0]?.peak_wind_dir).toBeNull();
    expect(out[0]?.peak_wind_time).toBeNull();
  });
});

describe("parseIemCsv — multi-row mixed validity", () => {
  it("yields only valid rows; drops malformed ones without throwing", () => {
    const body = csvBody([
      makeRow({ valid: "2025-01-01 00:51", tmpf: "32" }),
      makeRow({ valid: "not-a-timestamp", tmpf: "33" }), // dropped: bad ts
      makeRow({ valid: "2025-01-01 01:51", tmpf: "34" }),
      makeRow({ station: "", tmpf: "35" }), // dropped: empty station
      makeRow({ valid: "2025-01-01 02:51", tmpf: "36" }),
    ]);
    const out = parseIemCsv(body);
    expect(out).toHaveLength(3);
    expect(out.map((r) => r.temp_f)).toEqual([32, 34, 36]);
  });
});

describe("Observation.source widening (TS-W2 Plan 01 cross-package contract)", () => {
  it("AWC and IEM parsers share the same Observation type at the type level", () => {
    // This test is type-level (compilation enforces); runtime check is a
    // belt-and-suspenders sanity sweep.
    const out = parseIemCsv(csvBody([makeRow()]));
    const obs: Observation = out[0] as Observation;
    expect(obs.source).toBe("iem");
    // The widened type accepts all three source literals.
    const allowed: ReadonlyArray<Observation["source"]> = ["awc", "iem", "ghcnh"];
    expect(allowed).toContain(obs.source);
  });
});

import { describe, expect, it } from "vitest";

import { parseGhcnhPsv, parseGhcnhRow } from "../src/_parsers/ghcnh.js";

/**
 * Build a PSV row dict mirroring how `parseGhcnhPsv` would feed a row
 * to `parseGhcnhRow`. Provides sensible defaults for required keys.
 */
function makeRow(overrides: Record<string, string> = {}): Record<string, string> {
  return {
    temperature_Source_Station_ID: "ICAO-KMSY",
    DATE: "2024-09-10T14:51:00Z",
    temperature: "25.0",
    temperature_Quality_Code: "0",
    dew_point_temperature: "20.0",
    dew_point_temperature_Quality_Code: "0",
    wind_speed: "5.0",
    wind_speed_Quality_Code: "0",
    sea_level_pressure: "1013.2",
    sea_level_pressure_Quality_Code: "0",
    ...overrides,
  };
}

describe("parseGhcnhRow — happy path", () => {
  it("emits source='ghcnh' + 30 fields", () => {
    const obs = parseGhcnhRow(makeRow());
    expect(obs).not.toBeNull();
    if (obs === null) return;
    expect(obs.source).toBe("ghcnh");
    expect(obs.station_code).toBe("MSY");
    expect(obs.observed_at).toBe("2024-09-10T14:51:00Z");
    expect(obs.observation_type).toBe("METAR");
    expect(obs.temp_c).toBe(25.0);
    expect(obs.dewpoint_c).toBe(20.0);
    // Field count = 30 per Observation schema.
    expect(Object.keys(obs)).toHaveLength(30);
  });

  it("appends 'Z' suffix when DATE missing it", () => {
    const obs = parseGhcnhRow(makeRow({ DATE: "2024-09-10T14:51:00" }));
    expect(obs?.observed_at).toBe("2024-09-10T14:51:00Z");
  });

  it("temperature_Report_Type='FM16' → observation_type='SPECI'", () => {
    const obs = parseGhcnhRow(makeRow({ temperature_Report_Type: "FM16" }));
    expect(obs?.observation_type).toBe("SPECI");
  });
});

describe("parseGhcnhRow — Quality_Code filtering", () => {
  it("temperature_Quality_Code='3' → temp_c nulled (but row kept via dewpoint)", () => {
    const obs = parseGhcnhRow(makeRow({ temperature_Quality_Code: "3" }));
    expect(obs).not.toBeNull();
    expect(obs?.temp_c).toBeNull();
    expect(obs?.temp_f).toBeNull();
    expect(obs?.dewpoint_c).toBe(20.0);
  });

  it("empty Quality_Code is ACCEPTED (load-bearing for parity case 5)", () => {
    const obs = parseGhcnhRow(makeRow({ temperature_Quality_Code: "" }));
    expect(obs?.temp_c).toBe(25.0);
  });

  it("letter QC flag 'I' rejects the variable", () => {
    const obs = parseGhcnhRow(makeRow({ temperature_Quality_Code: "I" }));
    expect(obs?.temp_c).toBeNull();
  });

  it("letter QC flag 'P' rejects the variable", () => {
    const obs = parseGhcnhRow(makeRow({ wind_speed_Quality_Code: "P" }));
    expect(obs?.wind_speed_kt).toBeNull();
  });

  it("QC codes {0,1,4,5} all accept", () => {
    for (const qc of ["0", "1", "4", "5"]) {
      const obs = parseGhcnhRow(makeRow({ temperature_Quality_Code: qc }));
      expect(obs?.temp_c, `qc=${qc}`).toBe(25.0);
    }
  });

  it("QC codes {2,3,6,7} all reject", () => {
    for (const qc of ["2", "3", "6", "7"]) {
      const obs = parseGhcnhRow(makeRow({ temperature_Quality_Code: qc }));
      expect(obs?.temp_c, `qc=${qc}`).toBeNull();
    }
  });

  it("drops row when ALL 4 key vars (temp, dewp, wspd, slp) QC-rejected", () => {
    const obs = parseGhcnhRow(
      makeRow({
        temperature_Quality_Code: "3",
        dew_point_temperature_Quality_Code: "3",
        wind_speed_Quality_Code: "3",
        sea_level_pressure_Quality_Code: "3",
      }),
    );
    expect(obs).toBeNull();
  });
});

describe("parseGhcnhRow — unit conversions", () => {
  it("wind_speed=10 m/s → 19 kt (10/0.514444 ≈ 19.438 → round → 19)", () => {
    const obs = parseGhcnhRow(makeRow({ wind_speed: "10" }));
    expect(obs?.wind_speed_kt).toBe(19);
  });

  it("wind_gust m/s → kt with rounding + bound", () => {
    const obs = parseGhcnhRow(makeRow({ wind_gust: "15", wind_gust_Quality_Code: "0" }));
    // 15 / 0.514444 ≈ 29.158 → 29
    expect(obs?.wind_gust_kt).toBe(29);
  });

  it("visibility km → miles (16.0934 km → ≈10 mi)", () => {
    const obs = parseGhcnhRow(makeRow({ visibility: "16.0934", visibility_Quality_Code: "0" }));
    expect(obs?.visibility_miles).toBeCloseTo(10, 3);
  });

  it("visibility clamped at MAX_VISIBILITY_MILES (99.99)", () => {
    const obs = parseGhcnhRow(makeRow({ visibility: "999", visibility_Quality_Code: "0" }));
    expect(obs?.visibility_miles).toBe(99.99);
  });

  it("precipitation mm → inches (25.4 mm → 1.0 in)", () => {
    const obs = parseGhcnhRow(makeRow({ precipitation: "25.4", precipitation_Quality_Code: "0" }));
    expect(obs?.precip_1hr_inches).toBeCloseTo(1.0, 5);
  });

  it("snow_depth cm → inches (5.08 cm → 2 in)", () => {
    const obs = parseGhcnhRow(makeRow({ snow_depth: "5.08", snow_depth_Quality_Code: "0" }));
    expect(obs?.snow_depth_inches).toBeCloseTo(2, 3);
  });
});

describe("parseGhcnhRow — sky cover", () => {
  it("sky_cover_summation_1='SCT:04;' → sky_cover_1='SCT'", () => {
    const obs = parseGhcnhRow(
      makeRow({
        sky_cover_summation_1: "SCT:04;",
        sky_cover_summation_1_Quality_Code: "0",
      }),
    );
    expect(obs?.sky_cover_1).toBe("SCT");
  });

  it("sky_cover_summation_baseht (meters) → feet (rounded)", () => {
    // 1000 m * 3.28084 → 3280.84 → round → 3281
    const obs = parseGhcnhRow(
      makeRow({
        sky_cover_summation_baseht_1: "1000",
        sky_cover_summation_baseht_1_Quality_Code: "0",
      }),
    );
    expect(obs?.sky_base_1_ft).toBe(3281);
  });

  it("rejects per-layer QC-flagged sky cover", () => {
    const obs = parseGhcnhRow(
      makeRow({
        sky_cover_summation_1: "SCT:04;",
        sky_cover_summation_1_Quality_Code: "3",
      }),
    );
    expect(obs?.sky_cover_1).toBeNull();
  });

  it("walks all 4 sky-cover layers", () => {
    const obs = parseGhcnhRow(
      makeRow({
        sky_cover_summation_1: "FEW:01;",
        sky_cover_summation_1_Quality_Code: "0",
        sky_cover_summation_2: "SCT:03;",
        sky_cover_summation_2_Quality_Code: "0",
        sky_cover_summation_3: "BKN:06;",
        sky_cover_summation_3_Quality_Code: "0",
        sky_cover_summation_4: "OVC:08;",
        sky_cover_summation_4_Quality_Code: "0",
      }),
    );
    expect(obs?.sky_cover_1).toBe("FEW");
    expect(obs?.sky_cover_2).toBe("SCT");
    expect(obs?.sky_cover_3).toBe("BKN");
    expect(obs?.sky_cover_4).toBe("OVC");
  });
});

describe("parseGhcnhRow — date validation", () => {
  it("calendar-invalid DATE (2025-02-30) → row dropped", () => {
    const obs = parseGhcnhRow(makeRow({ DATE: "2025-02-30T00:00:00Z" }));
    expect(obs).toBeNull();
  });

  it("malformed DATE (no time component) → row dropped", () => {
    const obs = parseGhcnhRow(makeRow({ DATE: "2024-09-10" }));
    expect(obs).toBeNull();
  });

  it("year out of range (1800) → row dropped", () => {
    const obs = parseGhcnhRow(makeRow({ DATE: "1800-01-01T00:00:00Z" }));
    expect(obs).toBeNull();
  });

  it("year at MAX_YEAR (2100) accepted", () => {
    const obs = parseGhcnhRow(makeRow({ DATE: "2100-01-01T00:00:00Z" }));
    expect(obs).not.toBeNull();
  });
});

describe("parseGhcnhRow — station resolution", () => {
  it("all SSID columns empty → row dropped", () => {
    const obs = parseGhcnhRow(makeRow({ temperature_Source_Station_ID: "" }));
    expect(obs).toBeNull();
  });

  it("falls back to lower-priority SSID column", () => {
    const obs = parseGhcnhRow(
      makeRow({
        temperature_Source_Station_ID: "",
        dew_point_temperature_Source_Station_ID: "ICAO-KJFK",
      }),
    );
    expect(obs?.station_code).toBe("JFK");
  });
});

describe("parseGhcnhRow — raw_metar from REM", () => {
  it("extracts METAR substring from prefixed REM", () => {
    const obs = parseGhcnhRow(
      makeRow({
        REM: "MET2024-09-10 14:51:00 METAR KMSY 101451Z 18012KT 10SM CLR",
      }),
    );
    expect(obs?.raw_metar).toBe("METAR KMSY 101451Z 18012KT 10SM CLR");
  });

  it("prefers earlier of METAR / SPECI markers", () => {
    const obs = parseGhcnhRow(
      makeRow({
        REM: "PREFIX METAR FIRST then SPECI LATER",
      }),
    );
    expect(obs?.raw_metar?.startsWith("METAR")).toBe(true);
  });

  it("uses SPECI when only SPECI marker present", () => {
    const obs = parseGhcnhRow(makeRow({ REM: "PREFIX SPECI KMSY 101451Z" }));
    expect(obs?.raw_metar?.startsWith("SPECI")).toBe(true);
  });

  it("falls back to raw REM when neither marker found", () => {
    const obs = parseGhcnhRow(makeRow({ REM: "no markers here" }));
    expect(obs?.raw_metar).toBe("no markers here");
  });

  it("empty REM → raw_metar null", () => {
    const obs = parseGhcnhRow(makeRow({ REM: "" }));
    expect(obs?.raw_metar).toBeNull();
  });
});

describe("parseGhcnhRow — weather codes", () => {
  it("extracts METAR text before colon, drops bare-numeric WMO codes", () => {
    const obs = parseGhcnhRow(
      makeRow({
        pres_wx_AW1: "TS:90",
        pres_wx_AW2: "BR:10",
        pres_wx_AW3: "02", // bare numeric → dropped
      }),
    );
    expect(obs?.weather_codes).toBe("TS BR");
  });

  it("pres_wx_AW1_Quality_Code='3' → that code dropped", () => {
    const obs = parseGhcnhRow(
      makeRow({
        pres_wx_AW1: "TS:90",
        pres_wx_AW1_Quality_Code: "3",
        pres_wx_AW2: "BR:10",
      }),
    );
    expect(obs?.weather_codes).toBe("BR");
  });

  it("pres_wx_AW1_Quality_Code='P' → that code dropped", () => {
    const obs = parseGhcnhRow(
      makeRow({
        pres_wx_AW1: "TS:90",
        pres_wx_AW1_Quality_Code: "P",
        pres_wx_AW2: "BR:10",
      }),
    );
    expect(obs?.weather_codes).toBe("BR");
  });

  it("no wx codes → null", () => {
    const obs = parseGhcnhRow(makeRow());
    expect(obs?.weather_codes).toBeNull();
  });

  it("empty QC accepts the wx code", () => {
    const obs = parseGhcnhRow(
      makeRow({
        pres_wx_AW1: "TS:90",
        pres_wx_AW1_Quality_Code: "",
      }),
    );
    expect(obs?.weather_codes).toBe("TS");
  });
});

describe("parseGhcnhPsv — PSV body integration", () => {
  it("empty body → []", () => {
    expect(parseGhcnhPsv("")).toEqual([]);
  });

  it("header only → []", () => {
    expect(parseGhcnhPsv("DATE|station_code\n")).toEqual([]);
  });

  it("parses a 2-row PSV with header + data", () => {
    const psv = `${[
      "DATE|temperature|temperature_Quality_Code|temperature_Source_Station_ID|dew_point_temperature|dew_point_temperature_Quality_Code|wind_speed|wind_speed_Quality_Code|sea_level_pressure|sea_level_pressure_Quality_Code",
      "2024-09-10T14:51:00Z|25.0|0|ICAO-KMSY|20.0|0|5.0|0|1013.2|0",
      "2024-09-10T15:51:00Z|26.0|0|ICAO-KMSY|21.0|0|6.0|0|1013.5|0",
    ].join("\n")}\n`;
    const out = parseGhcnhPsv(psv);
    expect(out).toHaveLength(2);
    expect(out[0]?.station_code).toBe("MSY");
    expect(out[1]?.temp_c).toBe(26.0);
  });

  it("normalizes CRLF line endings", () => {
    const psv = `${[
      "DATE|temperature|temperature_Quality_Code|temperature_Source_Station_ID|dew_point_temperature|dew_point_temperature_Quality_Code|wind_speed|wind_speed_Quality_Code|sea_level_pressure|sea_level_pressure_Quality_Code",
      "2024-09-10T14:51:00Z|25.0|0|ICAO-KMSY|20.0|0|5.0|0|1013.2|0",
    ].join("\r\n")}\r\n`;
    const out = parseGhcnhPsv(psv);
    expect(out).toHaveLength(1);
  });

  it("skips blank lines between header and data", () => {
    const psv =
      "\n\nDATE|temperature|temperature_Quality_Code|temperature_Source_Station_ID|dew_point_temperature|dew_point_temperature_Quality_Code|wind_speed|wind_speed_Quality_Code|sea_level_pressure|sea_level_pressure_Quality_Code\n\n2024-09-10T14:51:00Z|25.0|0|ICAO-KMSY|20.0|0|5.0|0|1013.2|0\n\n";
    const out = parseGhcnhPsv(psv);
    expect(out).toHaveLength(1);
  });

  it("drops rows that parseGhcnhRow returns null for (no nulls in output)", () => {
    const psv = `${[
      "DATE|temperature|temperature_Quality_Code|temperature_Source_Station_ID|dew_point_temperature|dew_point_temperature_Quality_Code|wind_speed|wind_speed_Quality_Code|sea_level_pressure|sea_level_pressure_Quality_Code",
      // Valid row
      "2024-09-10T14:51:00Z|25.0|0|ICAO-KMSY|20.0|0|5.0|0|1013.2|0",
      // No station id
      "2024-09-10T15:51:00Z|25.0|0||20.0|0|5.0|0|1013.2|0",
      // Calendar-invalid date
      "2025-02-30T00:00:00Z|25.0|0|ICAO-KMSY|20.0|0|5.0|0|1013.2|0",
    ].join("\n")}\n`;
    const out = parseGhcnhPsv(psv);
    expect(out).toHaveLength(1);
    expect(out.every((o) => o !== null)).toBe(true);
  });

  it("missing cells (short rows) parse as empty strings", () => {
    const psv = `${[
      "DATE|temperature|temperature_Quality_Code|temperature_Source_Station_ID|dew_point_temperature|dew_point_temperature_Quality_Code|wind_speed|wind_speed_Quality_Code|sea_level_pressure|sea_level_pressure_Quality_Code",
      // Short row — sea_level_pressure missing entirely
      "2024-09-10T14:51:00Z|25.0|0|ICAO-KMSY|20.0|0|5.0|0",
    ].join("\n")}\n`;
    const out = parseGhcnhPsv(psv);
    expect(out).toHaveLength(1);
    expect(out[0]?.sea_level_pressure_mb).toBeNull();
  });
});

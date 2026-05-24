import { describe, expect, it } from "vitest";

import {
  SSID_COLUMNS,
  extractStationCode,
  ghcnhStationToCode,
} from "../src/_parsers/_station_translator.js";

describe("ghcnhStationToCode", () => {
  it("strips ICAO- prefix and applies K-removal: ICAO-KJFK → JFK", () => {
    expect(ghcnhStationToCode("ICAO-KJFK")).toBe("JFK");
  });

  it("returns null for WMO USAF-WBAN format", () => {
    expect(ghcnhStationToCode("744860-94789")).toBeNull();
  });

  it("returns null for empty string", () => {
    expect(ghcnhStationToCode("")).toBeNull();
  });

  it("returns null for ICAO- prefix with empty ICAO", () => {
    expect(ghcnhStationToCode("ICAO-")).toBeNull();
  });

  it("returns null for ICAO- prefix with non-station value", () => {
    expect(ghcnhStationToCode("ICAO-12")).toBeNull();
    expect(ghcnhStationToCode("ICAO-toolong")).toBeNull();
  });

  it("handles non-K ICAO codes (international): ICAO-EGLL → EGLL", () => {
    // icaoToStationCode only strips K from 4-letter codes; international stays as-is.
    expect(ghcnhStationToCode("ICAO-EGLL")).toBe("EGLL");
  });

  it("ICAO-ORD (3-letter station already) → ORD", () => {
    expect(ghcnhStationToCode("ICAO-ORD")).toBe("ORD");
  });
});

describe("extractStationCode — column priority", () => {
  it("first column hit (temperature_Source_Station_ID = ICAO-KORD) → ORD", () => {
    const row: Record<string, string> = {
      temperature_Source_Station_ID: "ICAO-KORD",
      // Lower-priority columns have unparseable WMO IDs — should be ignored.
      dew_point_temperature_Source_Station_ID: "744860-94789",
      wind_speed_Source_Station_ID: "999999-99999",
    };
    expect(extractStationCode(row)).toBe("ORD");
  });

  it("cascades to dew_point when temperature column is empty", () => {
    const row: Record<string, string> = {
      temperature_Source_Station_ID: "",
      dew_point_temperature_Source_Station_ID: "ICAO-KJFK",
    };
    expect(extractStationCode(row)).toBe("JFK");
  });

  it("cascades through all 11 columns: only sky_cover_summation_4 has ICAO", () => {
    const row: Record<string, string> = {
      sky_cover_summation_4_Source_Station_ID: "ICAO-KMSY",
    };
    expect(extractStationCode(row)).toBe("MSY");
  });

  it("returns null when no column carries a valid ICAO id", () => {
    const row: Record<string, string> = {
      temperature_Source_Station_ID: "",
      dew_point_temperature_Source_Station_ID: "744860-94789",
      wind_speed_Source_Station_ID: "",
    };
    expect(extractStationCode(row)).toBeNull();
  });

  it("returns null for completely empty row", () => {
    expect(extractStationCode({})).toBeNull();
  });

  it("ignores ICAO- prefix in non-SSID columns (only walks SSID_COLUMNS)", () => {
    const row: Record<string, string> = {
      some_other_column: "ICAO-KJFK",
    };
    expect(extractStationCode(row)).toBeNull();
  });
});

describe("SSID_COLUMNS — ordering byte-faithful with Python tuple", () => {
  it("has exactly 11 columns", () => {
    expect(SSID_COLUMNS).toHaveLength(11);
  });

  it("matches Python _SSID_COLUMNS order at _ghcnh.py:45-57", () => {
    expect(SSID_COLUMNS).toEqual([
      "temperature_Source_Station_ID",
      "dew_point_temperature_Source_Station_ID",
      "wind_speed_Source_Station_ID",
      "wind_direction_Source_Station_ID",
      "sea_level_pressure_Source_Station_ID",
      "altimeter_Source_Station_ID",
      "visibility_Source_Station_ID",
      "sky_cover_summation_1_Source_Station_ID",
      "sky_cover_summation_2_Source_Station_ID",
      "sky_cover_summation_3_Source_Station_ID",
      "sky_cover_summation_4_Source_Station_ID",
    ]);
  });
});

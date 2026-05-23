import { describe, expect, it } from "vitest";

import {
  GHCNH_STATION_ID_RE,
  MAX_RAW_METAR_LEN,
  MAX_VISIBILITY_MILES,
  MIN_YEAR,
  SKY_BASE_MAX_FT,
  SLP_MAX_MB,
  SLP_MIN_MB,
  STATION_CODE_RE,
  TEMP_MAX_C,
  TEMP_MIN_C,
  WIND_DIR_BOUNDS,
  WIND_GUST_MAX,
  WIND_SPEED_MAX,
  boundedFloat,
  boundedFloatMin,
  boundedInt,
  validateGhcnhIdForPath,
  validateIcaoForPath,
} from "../src/internal/bounds.js";

describe("constants", () => {
  it("pressure bounds 870..1084 mb", () => {
    expect(SLP_MIN_MB).toBe(870);
    expect(SLP_MAX_MB).toBe(1084);
  });
  it("temperature bounds -90..60 °C", () => {
    expect(TEMP_MIN_C).toBe(-90);
    expect(TEMP_MAX_C).toBe(60);
  });
  it("wind bounds", () => {
    expect(WIND_DIR_BOUNDS).toEqual([0, 360]);
    expect(WIND_SPEED_MAX).toBe(200);
    expect(WIND_GUST_MAX).toBe(250);
  });
  it("sky/year/visibility/raw bounds", () => {
    expect(SKY_BASE_MAX_FT).toBe(60000);
    expect(MIN_YEAR).toBe(1940);
    expect(MAX_VISIBILITY_MILES).toBe(99.99);
    expect(MAX_RAW_METAR_LEN).toBe(2048);
  });
});

describe("boundedInt", () => {
  it("returns value within range", () => {
    expect(boundedInt(5, 0, 10)).toBe(5);
    expect(boundedInt(0, 0, 10)).toBe(0);
    expect(boundedInt(10, 0, 10)).toBe(10);
  });
  it("returns null when out of range", () => {
    expect(boundedInt(-1, 0, 10)).toBeNull();
    expect(boundedInt(11, 0, 10)).toBeNull();
  });
  it("null passthrough", () => {
    expect(boundedInt(null, 0, 10)).toBeNull();
  });
  it("non-finite → null", () => {
    expect(boundedInt(Number.NaN, 0, 10)).toBeNull();
  });
});

describe("boundedFloat", () => {
  it("returns value within range", () => {
    expect(boundedFloat(50.5, 0, 100)).toBe(50.5);
  });
  it("returns null when out of range", () => {
    expect(boundedFloat(-0.1, 0, 100)).toBeNull();
    expect(boundedFloat(100.1, 0, 100)).toBeNull();
  });
  it("null + non-finite passthrough", () => {
    expect(boundedFloat(null, 0, 100)).toBeNull();
    expect(boundedFloat(Number.POSITIVE_INFINITY, 0, 100)).toBeNull();
  });
});

describe("boundedFloatMin", () => {
  it("passes through when >= lo", () => {
    expect(boundedFloatMin(5, 0)).toBe(5);
    expect(boundedFloatMin(0, 0)).toBe(0);
  });
  it("returns null when < lo", () => {
    expect(boundedFloatMin(-1, 0)).toBeNull();
  });
  it("null/non-finite passthrough", () => {
    expect(boundedFloatMin(null, 0)).toBeNull();
    expect(boundedFloatMin(Number.NaN, 0)).toBeNull();
  });
});

describe("STATION_CODE_RE", () => {
  it("accepts 3-4 uppercase letters", () => {
    expect(STATION_CODE_RE.test("NYC")).toBe(true);
    expect(STATION_CODE_RE.test("KORD")).toBe(true);
  });
  it("rejects lowercase / numeric / path traversal / newline", () => {
    expect(STATION_CODE_RE.test("nyc")).toBe(false);
    expect(STATION_CODE_RE.test("NY1")).toBe(false);
    expect(STATION_CODE_RE.test("../etc")).toBe(false);
    expect(STATION_CODE_RE.test("NYC\n")).toBe(false);
    expect(STATION_CODE_RE.test("")).toBe(false);
  });
});

describe("validateIcaoForPath", () => {
  it("returns value when valid", () => {
    expect(validateIcaoForPath("KORD")).toBe("KORD");
    expect(validateIcaoForPath("NYC")).toBe("NYC");
  });
  it("throws on non-string", () => {
    expect(() => validateIcaoForPath(123)).toThrow();
    expect(() => validateIcaoForPath(null)).toThrow();
  });
  it("throws on path traversal", () => {
    expect(() => validateIcaoForPath("../../etc/passwd")).toThrow();
    expect(() => validateIcaoForPath("nyc")).toThrow();
  });
});

describe("GHCNH_STATION_ID_RE + validateGhcnhIdForPath", () => {
  it("accepts ICAO-derived ids", () => {
    expect(GHCNH_STATION_ID_RE.test("744860-94789")).toBe(true);
    expect(validateGhcnhIdForPath("USW00094728")).toBe("USW00094728");
  });
  it("rejects path separators and lowercase", () => {
    expect(GHCNH_STATION_ID_RE.test("../../tmp")).toBe(false);
    expect(GHCNH_STATION_ID_RE.test("usw00094728")).toBe(false);
    expect(() => validateGhcnhIdForPath("foo/bar")).toThrow();
  });
});

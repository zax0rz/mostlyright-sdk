import { describe, expect, it } from "vitest";

import {
  KT_TO_MPH,
  KT_TO_MS,
  MI_TO_KM,
  celsiusToFahrenheit,
  computeFeelsLike,
  computeRelativeHumidity,
  fahrenheitToCelsius,
  ftToM,
  hpaToInhg,
  inchesToMm,
  ktToMph,
  ktToMs,
  miToKm,
  miToM,
} from "../src/internal/convert.js";

const APPROX = 1e-9;

describe("constants", () => {
  it("KT_TO_MS is the exact 1852/3600 ratio", () => {
    expect(KT_TO_MS).toBeCloseTo(0.5144444444444445, 12);
  });
  it("KT_TO_MPH = 1.15078", () => {
    expect(KT_TO_MPH).toBe(1.15078);
  });
  it("MI_TO_KM = 1.609344", () => {
    expect(MI_TO_KM).toBe(1.609344);
  });
});

describe("ktToMs / ktToMph", () => {
  it("converts 10 kt → ~5.1444 m/s", () => {
    expect(ktToMs(10)).toBeCloseTo(5.144444444, 6);
  });
  it("converts 10 kt → 11.5078 mph", () => {
    expect(ktToMph(10)).toBeCloseTo(11.5078, 6);
  });
  it("null passthrough", () => {
    expect(ktToMs(null)).toBeNull();
    expect(ktToMph(null)).toBeNull();
  });
  it("non-finite → null", () => {
    expect(ktToMs(Number.NaN)).toBeNull();
    expect(ktToMs(Number.POSITIVE_INFINITY)).toBeNull();
  });
});

describe("miToKm / miToM / ftToM / inchesToMm", () => {
  it("1 mi = 1.609344 km", () => {
    expect(miToKm(1)).toBe(1.609344);
  });
  it("1 mi = 1609.344 m", () => {
    expect(miToM(1)).toBe(1609.344);
  });
  it("100 ft = 30.48 m", () => {
    expect(ftToM(100)).toBeCloseTo(30.48, 8);
  });
  it("1 in = 25.4 mm", () => {
    expect(inchesToMm(1)).toBe(25.4);
  });
  it("null + non-finite passthrough", () => {
    expect(miToKm(null)).toBeNull();
    expect(ftToM(Number.NaN)).toBeNull();
  });
});

describe("celsius/fahrenheit + hPa/inHg", () => {
  it("0°C = 32°F, 100°C = 212°F", () => {
    expect(celsiusToFahrenheit(0)).toBe(32);
    expect(celsiusToFahrenheit(100)).toBe(212);
  });
  it("32°F = 0°C, 212°F = 100°C", () => {
    expect(fahrenheitToCelsius(32)).toBe(0);
    expect(fahrenheitToCelsius(212)).toBeCloseTo(100, 9);
  });
  it("hPa to inHg conversion", () => {
    expect(hpaToInhg(1013.25)).toBeCloseTo(1013.25 * 0.0295299875, 9);
  });
  it("null passthrough", () => {
    expect(celsiusToFahrenheit(null)).toBeNull();
    expect(fahrenheitToCelsius(null)).toBeNull();
    expect(hpaToInhg(null)).toBeNull();
  });
});

describe("computeRelativeHumidity (Magnus formula)", () => {
  it("25°C / 15°C dewpoint → ~53.83 % (matches Python exactly)", () => {
    // Python: 100 * exp((17.625*15)/(243.04+15)) / exp((17.625*25)/(243.04+25))
    //       ≈ 53.830642
    const rh = computeRelativeHumidity(25, 15);
    expect(rh).not.toBeNull();
    expect(rh as number).toBeCloseTo(53.830642, 4);
  });

  it("equal temp/dewpoint → 100 %", () => {
    expect(computeRelativeHumidity(20, 20)).toBeCloseTo(100, 6);
  });

  it("dewpoint > temp clamps to 100 %", () => {
    expect(computeRelativeHumidity(10, 20)).toBeCloseTo(100, 0);
  });

  it("returns null for null inputs", () => {
    expect(computeRelativeHumidity(null, 10)).toBeNull();
    expect(computeRelativeHumidity(10, null)).toBeNull();
    expect(computeRelativeHumidity(Number.NaN, 10)).toBeNull();
  });
});

describe("computeFeelsLike", () => {
  it("mild temp + no wind → identity (20°F isn't either wind-chill or heat-index)", () => {
    // Per Python: wind chill requires <=50°F AND wind > 3 mph; heat index
    // requires >=80°F. 20°F + 0 mph wind hits neither, so returns t.
    expect(computeFeelsLike(20, 0, 50)).toBe(20);
  });

  it("wind chill branch active (10°F, 20 kt)", () => {
    // 20 kt ≈ 23.0156 mph > 3, so wind chill formula is applied.
    // 35.74 + 0.6215*10 - 35.75*23.0156^0.16 + 0.4275*10*23.0156^0.16
    const out = computeFeelsLike(10, 20, null);
    expect(out).not.toBeNull();
    expect(out as number).toBeLessThan(10);
  });

  it("heat index branch active (95°F, no wind, 70% RH)", () => {
    const out = computeFeelsLike(95, 0, 70);
    expect(out).not.toBeNull();
    // NWS Rothfusz says feels like is well above the raw temp here.
    expect(out as number).toBeGreaterThan(100);
  });

  it("null temp → null result", () => {
    expect(computeFeelsLike(null, 5, 50)).toBeNull();
  });

  it("non-finite wind → null", () => {
    expect(computeFeelsLike(60, Number.POSITIVE_INFINITY, 50)).toBeNull();
  });

  it("null rh disables heat-index branch (returns identity)", () => {
    // 90°F with no rh and no wind → returns t.
    expect(computeFeelsLike(90, 0, null)).toBe(90);
  });

  // Sanity check the Magnus approximation more precisely.
  it("approx matches Python output for (25, 15)", () => {
    const py =
      (100 * Math.exp((17.625 * 15) / (243.04 + 15))) / Math.exp((17.625 * 25) / (243.04 + 25));
    const rh = computeRelativeHumidity(25, 15) as number;
    expect(rh).toBeCloseTo(py, 9);
  });

  it("APPROX tolerance check (suppresses unused-var warning)", () => {
    expect(APPROX).toBeLessThan(1);
  });
});

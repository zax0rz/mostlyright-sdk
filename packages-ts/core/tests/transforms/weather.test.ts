// TS-W4 Plan 04 Task 1 — windChill + heatIndex tests (RED phase).
//
// Mirrors Python `tradewinds.transforms.wind_chill` and `heat_index` at
// `packages/core/src/tradewinds/transforms.py:108-147`. The NWS reference-
// table assertions are LOAD-BEARING acceptance criteria for TS-TRANSFORM-02:
//
//   - windChill(20°F, 15 mph) → 6 °F   (NWS chart)
//   - heatIndex(90°F, 70% RH) → 106 °F (NWS Rothfusz table)
//
// **PARITY-NOTE (out-of-domain):** Python returns `temp_f` UNCHANGED when
// outside the valid domain (transforms.py:114 for windChill, transforms.py:126
// for heatIndex). The REQUIREMENTS.md text says "→ null" but that is incorrect
// vs the canonical Python source. These tests honor Python source.

import { describe, expect, it } from "vitest";

import { heatIndex, windChill } from "../../src/transforms/weather.js";

// Strict number-narrowing helper: throws if `v` is null (test fails) rather
// than using a `v!` non-null assertion (biome lint forbids those).
function num(v: number | null): number {
  if (v === null) throw new Error("expected number, got null");
  return v;
}

const closeTo = (actual: number, expected: number, eps = 1): boolean =>
  Math.abs(actual - expected) <= eps;

describe("windChill — NWS reference table (load-bearing, ≤1°F tolerance)", () => {
  it("windChill(20, 15) ≈ 6 °F", () => {
    const v = windChill(20, 15);
    expect(v).not.toBeNull();
    expect(closeTo(num(v), 6)).toBe(true);
  });

  it("windChill(0, 25) ≈ -24 °F", () => {
    const v = windChill(0, 25);
    expect(v).not.toBeNull();
    expect(closeTo(num(v), -24)).toBe(true);
  });

  it("windChill(40, 10) ≈ 34 °F", () => {
    const v = windChill(40, 10);
    expect(v).not.toBeNull();
    expect(closeTo(num(v), 34)).toBe(true);
  });
});

describe("windChill — out-of-domain returns tempF unchanged (Python parity)", () => {
  it("tempF > 50 → returns tempF (not null)", () => {
    expect(windChill(60, 10)).toBe(60);
  });

  it("windMph ≤ 3 → returns tempF (not null) [boundary at 3]", () => {
    expect(windChill(20, 3)).toBe(20);
    expect(windChill(20, 2)).toBe(20);
    expect(windChill(20, 0)).toBe(20);
  });

  it("tempF exactly at 50 boundary uses NWS formula (50 is in-domain)", () => {
    // Domain check is `tempF > 50.0`, so 50 itself stays in-domain.
    const v = windChill(50, 15);
    expect(v).not.toBeNull();
    // Sanity: returned value should differ from tempF (NWS formula applied).
    expect(v).not.toBe(50);
  });
});

describe("windChill — null / undefined / non-finite → null", () => {
  it("null tempF → null", () => {
    expect(windChill(null, 15)).toBeNull();
  });

  it("undefined tempF → null", () => {
    expect(windChill(undefined, 15)).toBeNull();
  });

  it("null windMph → null", () => {
    expect(windChill(20, null)).toBeNull();
  });

  it("undefined windMph → null", () => {
    expect(windChill(20, undefined)).toBeNull();
  });

  it("NaN tempF → null", () => {
    expect(windChill(Number.NaN, 15)).toBeNull();
  });

  it("Infinity windMph → null", () => {
    expect(windChill(20, Number.POSITIVE_INFINITY)).toBeNull();
  });
});

describe("heatIndex — NWS reference table (load-bearing, ≤1°F tolerance)", () => {
  it("heatIndex(90, 70) ≈ 106 °F", () => {
    const v = heatIndex(90, 70);
    expect(v).not.toBeNull();
    expect(closeTo(num(v), 106)).toBe(true);
  });

  it("heatIndex(80, 50) ≈ 82 °F", () => {
    const v = heatIndex(80, 50);
    expect(v).not.toBeNull();
    expect(closeTo(num(v), 82)).toBe(true);
  });

  it("heatIndex(100, 60) ≈ 129 °F", () => {
    const v = heatIndex(100, 60);
    expect(v).not.toBeNull();
    expect(closeTo(num(v), 129)).toBe(true);
  });
});

describe("heatIndex — out-of-domain returns tempF unchanged (Python parity)", () => {
  it("tempF < 80 → returns tempF (not null)", () => {
    expect(heatIndex(70, 50)).toBe(70);
  });

  it("tempF = 79 (just below threshold) → returns tempF", () => {
    expect(heatIndex(79, 50)).toBe(79);
  });
});

describe("heatIndex — null / undefined / non-finite → null", () => {
  it("null tempF → null", () => {
    expect(heatIndex(null, 70)).toBeNull();
  });

  it("undefined tempF → null", () => {
    expect(heatIndex(undefined, 70)).toBeNull();
  });

  it("null rhPct → null", () => {
    expect(heatIndex(90, null)).toBeNull();
  });

  it("undefined rhPct → null", () => {
    expect(heatIndex(90, undefined)).toBeNull();
  });

  it("NaN rhPct → null", () => {
    expect(heatIndex(90, Number.NaN)).toBeNull();
  });

  it("Infinity tempF → null", () => {
    expect(heatIndex(Number.POSITIVE_INFINITY, 70)).toBeNull();
  });
});

describe("heatIndex — adjustment branches (Rothfusz dry + wet)", () => {
  it("low-humidity dry adjustment: heatIndex(95, 10) lowers vs unadjusted", () => {
    // For h<13 and 80≤t≤112, Rothfusz subtracts ((13-h)/4) * sqrt((17-|t-95|)/17).
    // At t=95, h=10: adj = ((13-10)/4) * sqrt(17/17) = 0.75 * 1.0 = 0.75
    const t = 95;
    const h = 10;
    const unadjusted =
      -42.379 +
      2.04901523 * t +
      10.14333127 * h -
      0.22475541 * t * h -
      0.00683783 * t * t -
      0.05481717 * h * h +
      0.00122874 * t * t * h +
      0.00085282 * t * h * h -
      0.00000199 * t * t * h * h;
    const expected = unadjusted - 0.75;
    const actual = heatIndex(t, h);
    expect(actual).not.toBeNull();
    expect(closeTo(num(actual), expected, 1e-9)).toBe(true);
  });

  it("high-humidity wet adjustment: heatIndex(85, 90) raises by 0.2", () => {
    // For h>85 and 80≤t≤87, Rothfusz adds ((h-85)/10) * ((87-t)/5).
    // At t=85, h=90: adj = ((90-85)/10) * ((87-85)/5) = 0.5 * 0.4 = 0.2
    const t = 85;
    const h = 90;
    const unadjusted =
      -42.379 +
      2.04901523 * t +
      10.14333127 * h -
      0.22475541 * t * h -
      0.00683783 * t * t -
      0.05481717 * h * h +
      0.00122874 * t * t * h +
      0.00085282 * t * h * h -
      0.00000199 * t * t * h * h;
    const expected = unadjusted + 0.2;
    const actual = heatIndex(t, h);
    expect(actual).not.toBeNull();
    expect(closeTo(num(actual), expected, 1e-9)).toBe(true);
  });

  it("simple approximation branch: low (simple+t)/2 returns simple", () => {
    // For tempF=80, rhPct=10: simple = 0.5*(80 + 61 + 14.4 + 0.94) = 78.17
    // (simple+t)/2 = (78.17+80)/2 = 79.085 < 80 → return simple (not Rothfusz)
    const v = heatIndex(80, 10);
    expect(v).not.toBeNull();
    const simple = 0.5 * (80 + 61.0 + (80 - 68.0) * 1.2 + 10 * 0.094);
    expect(closeTo(num(v), simple, 1e-9)).toBe(true);
  });
});

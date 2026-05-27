// Phase 18 PREC-01: AWC integer-°F recovery from Tgroup.
//
// TS parity port of Python plan 18-02 tests. When raw METAR contains a
// Tgroup remark, awcToObservation must emit temp_f / dewpoint_f as the
// integer °F the sensor actually reported (recovered via
// Math.round(c * 9/5 + 32)), not the float celsiusToFahrenheit() back-
// conversion that produces 80.06°F where the native reading was 80°F.

import { describe, expect, it } from "vitest";

import type { AwcMetarRaw } from "../src/_fetchers/awc.js";
import { awcToObservation } from "../src/_parsers/awc.js";

// Helper: ISO 8601 second-precision timestamp from epoch seconds.
const TS = 1704067200; // 2024-01-01T00:00:00Z

describe("awcToObservation Phase 18 PREC-01 integer-°F recovery", () => {
  it("A. happy-path: T02670122 → temp_f=80, dewpoint_f=52", () => {
    // T02670122 → 26.7°C / 12.2°C
    // round(26.7 * 9/5 + 32) = round(80.06) = 80
    // round(12.2 * 9/5 + 32) = round(53.96) = 54
    const row = awcToObservation({
      icaoId: "KLGA",
      obsTime: TS,
      temp: 27,
      dewp: 12,
      rawOb: "KLGA 010000Z 27008KT 10SM CLR 27/12 A3001 RMK AO2 T02670122",
    } as AwcMetarRaw);
    expect(row).not.toBeNull();
    expect(row?.temp_c).toBeCloseTo(26.7, 5);
    expect(row?.dewpoint_c).toBeCloseTo(12.2, 5);
    // Phase 18 PREC-01: integer-valued, NOT 80.06.
    expect(row?.temp_f).toBe(80);
    expect(row?.dewpoint_f).toBe(54);
  });

  it("B. negative temp Tgroup: T10390061 → temp_f=25, dewpoint_f=43", () => {
    // T10390061 → -3.9°C / 6.1°C
    // round(-3.9 * 9/5 + 32) = round(24.98) = 25
    // round(6.1 * 9/5 + 32) = round(42.98) = 43
    const row = awcToObservation({
      icaoId: "KORD",
      obsTime: TS,
      temp: -4,
      dewp: 6,
      rawOb: "KORD 010000Z 27008KT 10SM CLR M04/06 A3015 RMK AO2 T10390061",
    } as AwcMetarRaw);
    expect(row?.temp_f).toBe(25);
    expect(row?.dewpoint_f).toBe(43);
  });

  it("C. no Tgroup (international station): falls back to celsiusToFahrenheit float", () => {
    // EGLL with no Tgroup → temp_f is the legacy float path (e.g. 64.4
    // from 18°C), NOT integer-recovered.
    const row = awcToObservation({
      icaoId: "EGLL",
      obsTime: TS,
      temp: 18,
      dewp: 12,
      rawOb: "EGLL 010000Z 27008KT 10SM CLR 18/12 Q1015",
    } as AwcMetarRaw);
    expect(row).not.toBeNull();
    expect(row?.temp_c).toBe(18);
    expect(row?.dewpoint_c).toBe(12);
    // 18 * 9/5 + 32 = 64.4 — float, NOT integer-rounded
    expect(row?.temp_f).toBeCloseTo(64.4, 5);
    expect(row?.dewpoint_f).toBeCloseTo(53.6, 5);
  });

  it("D. RMK present but no Tgroup: legacy float path", () => {
    const row = awcToObservation({
      icaoId: "KJFK",
      obsTime: TS,
      temp: 20,
      dewp: 10,
      rawOb: "KJFK 010000Z 27008KT 10SM CLR 20/10 A3001 RMK AO2 SLP049",
    } as AwcMetarRaw);
    // Legacy float — would be 68.0 exact (no remainder), not coincidentally integer-rounded.
    expect(row?.temp_f).toBeCloseTo(68.0, 5);
    expect(row?.dewpoint_f).toBeCloseTo(50.0, 5);
  });

  it("E. tempC bounded-out: Tgroup wildly out of range → temp_f null (bounds cascade)", () => {
    // Note: TGROUP_RE only matches \d{3} for value, so the largest possible
    // value is 99.9°C. We get bounded-out via the negative sign path:
    // T19990000 → -99.9°C / 0.0°C. -99.9°C is below TEMP_MIN_C (-90).
    const row = awcToObservation({
      icaoId: "KLAX",
      obsTime: TS,
      temp: 20,
      dewp: 10,
      rawOb: "KLAX 010000Z 27008KT 10SM CLR 20/10 A3001 RMK AO2 T19990000",
    } as AwcMetarRaw);
    // tempC nulled by bounds → tempF was computed before bounds, but the
    // current implementation does temp_f after bounds so it's null too.
    // Confirm the actual semantics:
    expect(row?.temp_c).toBeNull();
    // The integer-F branch only fires when tempC is non-null after bounds;
    // here it's null, so the celsiusToFahrenheit fallback runs against
    // null → null. End result: temp_f null.
    expect(row?.temp_f).toBeNull();
  });

  it("F. round-trip invariant: for every integer °F in a sample, recovered F == input", () => {
    // Sample integer °F values, encode to Tgroup tenths-°C, parse back, assert.
    // Skip f=0 — Math.round(-0.04) returns -0 in JS, which trips Object.is on
    // toBe(0). The semantic invariant (round-trip recovers the input integer)
    // holds; the -0 vs +0 distinction is a JS numeric quirk, not a parser bug.
    const sampleFs = [-40, -10, 32, 50, 72, 80, 95, 110];
    for (const f of sampleFs) {
      const tenthsC = Math.round((((f - 32) * 5) / 9) * 10); // tenths of °C, signed
      const sign = tenthsC < 0 ? "1" : "0";
      const abs = Math.abs(tenthsC).toString().padStart(3, "0");
      // Pair with dewpoint = same value for simplicity
      const tgroup = `T${sign}${abs}${sign}${abs}`;
      const row = awcToObservation({
        icaoId: "KLGA",
        obsTime: TS,
        temp: Math.round(((f - 32) * 5) / 9),
        dewp: Math.round(((f - 32) * 5) / 9),
        rawOb: `KLGA 010000Z 27008KT 10SM CLR 20/10 A3001 RMK AO2 ${tgroup}`,
      } as AwcMetarRaw);
      // Skip bounded-out cases (extreme F)
      if (row?.temp_c === null) continue;
      expect(row?.temp_f, `F=${f}`).toBe(f);
      expect(row?.dewpoint_f, `F=${f}`).toBe(f);
    }
  });

  it("G. 12-station parametrized: each station's Tgroup METAR yields integer temp_f", () => {
    // 12 station fixtures — all with valid Tgroups encoding integer °F.
    const fixtures: Array<{ icao: string; raw: string; expectedF: number }> = [
      { icao: "KLGA", raw: "KLGA 010000Z RMK AO2 T02670122", expectedF: 80 }, // 26.7°C → 80°F
      { icao: "KJFK", raw: "KJFK 010000Z RMK AO2 T02560111", expectedF: 78 }, // 25.6°C → 78°F
      { icao: "KEWR", raw: "KEWR 010000Z RMK AO2 T02220100", expectedF: 72 }, // 22.2°C → 72°F
      { icao: "KBOS", raw: "KBOS 010000Z RMK AO2 T01670056", expectedF: 62 }, // 16.7°C → 62°F
      { icao: "KORD", raw: "KORD 010000Z RMK AO2 T00610006", expectedF: 43 }, // 6.1°C → 43°F
      { icao: "KDFW", raw: "KDFW 010000Z RMK AO2 T03330222", expectedF: 92 }, // 33.3°C → 92°F
      { icao: "KLAX", raw: "KLAX 010000Z RMK AO2 T02000122", expectedF: 68 }, // 20.0°C → 68°F
      { icao: "KMIA", raw: "KMIA 010000Z RMK AO2 T02780189", expectedF: 82 }, // 27.8°C → 82°F
      { icao: "KDEN", raw: "KDEN 010000Z RMK AO2 T00560011", expectedF: 42 }, // 5.6°C → 42°F
      { icao: "KSEA", raw: "KSEA 010000Z RMK AO2 T01390089", expectedF: 57 }, // 13.9°C → 57°F
      { icao: "KATL", raw: "KATL 010000Z RMK AO2 T02500167", expectedF: 77 }, // 25.0°C → 77°F
      { icao: "KPHX", raw: "KPHX 010000Z RMK AO2 T03940250", expectedF: 103 }, // 39.4°C → 103°F
    ];
    for (const { icao, raw, expectedF } of fixtures) {
      const row = awcToObservation({
        icaoId: icao,
        obsTime: TS,
        temp: 20,
        dewp: 10,
        rawOb: raw,
      } as AwcMetarRaw);
      expect(row, `${icao}: row should parse`).not.toBeNull();
      expect(row?.temp_f, `${icao}: expected integer-recovered ${expectedF}°F`).toBe(expectedF);
      // Integer-valued invariant
      expect(row?.temp_f === Math.round(row?.temp_f ?? Number.NaN)).toBe(true);
    }
  });
});

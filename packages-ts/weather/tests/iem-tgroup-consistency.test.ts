// Phase 18 PREC-02: IEM Tgroup-override + AWC↔IEM cross-source consistency.
//
// TS parity port of Python plans 18-03 (IEM Tgroup-override) + 18-06 Task 2
// (cross-source consistency). When raw METAR contains a Tgroup remark,
// iemToObservation must:
// 1. Override temp_c / dewpoint_c with the Tgroup tenths-°C value (matching
//    AWC's emitted temp_c for the same raw METAR — closes cross-source
//    drift).
// 2. CRITICAL: keep temp_f = raw rawTempF; do NOT derive temp_f from
//    temp_c. tempC (tenths-°C) and tempF (integer-°F) are different coded
//    views of the same integer-°F sensor reading.

import { describe, expect, it } from "vitest";

import type { AwcMetarRaw } from "../src/_fetchers/awc.js";
import { awcToObservation } from "../src/_parsers/awc.js";
import { type IemCsvRow, iemToObservation } from "../src/_parsers/iem.js";

// IEM CSV row helper. IEM emits METAR text in `metar` column; we use the
// Tgroup remark to test override.
function makeIemRow(station: string, tmpf: number, dwpf: number, metar: string): IemCsvRow {
  return {
    station,
    valid: "2025-01-15 12:00",
    tmpf: tmpf.toString(),
    dwpf: dwpf.toString(),
    drct: "270",
    sknt: "10",
    gust: "",
    p01i: "",
    alti: "30.00",
    mslp: "1015",
    vsby: "10",
    skyc1: "CLR",
    skyl1: "",
    skyc2: "",
    skyl2: "",
    skyc3: "",
    skyl3: "",
    skyc4: "",
    skyl4: "",
    wxcodes: "",
    peak_wind_gust: "",
    peak_wind_drct: "",
    peak_wind_time: "",
    snowdepth: "",
    metar,
  };
}

describe("iemToObservation Phase 18 PREC-02 Tgroup-override", () => {
  it("A. happy path: Tgroup tenths-°C override matches AWC value, temp_f stays = rawTempF", () => {
    // T02670122 → 26.7°C / 12.2°C. tmpf=80 (integer °F). tmp_c WOULD be
    // (80-32)*5/9 = 26.666... if back-derived from tmpf; Phase 18 fix
    // overrides with Tgroup 26.7.
    const row = iemToObservation(makeIemRow("LGA", 80, 54, "KLGA 010000Z RMK AO2 T02670122"));
    expect(row).not.toBeNull();
    expect(row?.temp_c).toBeCloseTo(26.7, 5); // Tgroup, NOT 26.666...
    expect(row?.dewpoint_c).toBeCloseTo(12.2, 5); // Tgroup
    // CRITICAL invariant: tempF stays = rawTmpf (80), NOT derived from
    // temp_c.
    expect(row?.temp_f).toBe(80);
    expect(row?.dewpoint_f).toBe(54);
  });

  it("B. no Tgroup (international): legacy F→C derivation kicks in", () => {
    // EGLL has no Tgroup. temp_c falls back to fahrenheitToCelsius(tmpf).
    const row = iemToObservation(
      makeIemRow("EGLL", 65, 50, "EGLL 010000Z 27015KT 10SM CLR 18/10 Q1015"),
    );
    expect(row).not.toBeNull();
    expect(row?.temp_c).toBeCloseTo(((65 - 32) * 5) / 9, 5);
    expect(row?.dewpoint_c).toBeCloseTo(((50 - 32) * 5) / 9, 5);
    // tempF preserved
    expect(row?.temp_f).toBe(65);
    expect(row?.dewpoint_f).toBe(50);
  });

  it("C. no Tgroup + empty metar string: legacy derivation still works", () => {
    const row = iemToObservation(makeIemRow("LGA", 72, 50, ""));
    expect(row?.temp_c).toBeCloseTo(((72 - 32) * 5) / 9, 5);
    expect(row?.temp_f).toBe(72);
  });

  it("D. negative Tgroup: T10390061 → temp_c=-3.9, dewpoint_c=6.1", () => {
    const row = iemToObservation(makeIemRow("ORD", 25, 43, "KORD 010000Z RMK AO2 T10390061"));
    expect(row?.temp_c).toBeCloseTo(-3.9, 5);
    expect(row?.dewpoint_c).toBeCloseTo(6.1, 5);
    expect(row?.temp_f).toBe(25); // preserved
  });

  it("E. cross-source: AWC + IEM produce identical temp_c for the same raw METAR", () => {
    // Same raw METAR with Tgroup. AWC sees it via raw_metar field; IEM
    // sees it via the metar column. Both should override temp_c with the
    // Tgroup tenths-°C.
    const rawMetar = "KLGA 010000Z 27008KT 10SM CLR 27/12 A3001 RMK AO2 T02670122";
    const awc = awcToObservation({
      icaoId: "KLGA",
      obsTime: 1704067200,
      temp: 27,
      dewp: 12,
      rawOb: rawMetar,
    } as AwcMetarRaw);
    const iem = iemToObservation(makeIemRow("LGA", 80, 54, rawMetar));
    expect(awc?.temp_c).toBeCloseTo(iem?.temp_c ?? Number.NaN, 5);
    expect(awc?.dewpoint_c).toBeCloseTo(iem?.dewpoint_c ?? Number.NaN, 5);
    // Note: AWC.temp_f is integer-recovered (80); IEM.temp_f is raw (80).
    // Both should be 80.
    expect(awc?.temp_f).toBe(80);
    expect(iem?.temp_f).toBe(80);
  });

  it("F. Tgroup bounded-out: temp_c null AND temp_f null (consistency rule)", () => {
    // T19990000 → -99.9°C / 0°C. -99.9 is below TEMP_MIN_C → temp_c null.
    // Consistency rule from Python L170-171 also nulls temp_f when temp_c
    // is bounded out.
    const row = iemToObservation(makeIemRow("LAX", 50, 50, "KLAX 010000Z RMK AO2 T19990000"));
    expect(row?.temp_c).toBeNull();
    expect(row?.temp_f).toBeNull();
    // Dewpoint with Tgroup 0.0°C is fine → 32°F preserved
    expect(row?.dewpoint_c).toBe(0);
    expect(row?.dewpoint_f).toBe(50);
  });

  it("G. Tgroup with whole-°F-lattice values: 12-station cross-source consistency", () => {
    // For 12 US ASOS stations, encode known integer-°F values to Tgroup,
    // pass same raw METAR through both parsers, assert temp_c matches and
    // temp_f stays integer.
    const fixtures: Array<{ icao: string; tmpf: number; tgroup: string }> = [
      { icao: "KLGA", tmpf: 80, tgroup: "T02670122" }, // 26.7°C
      { icao: "KJFK", tmpf: 78, tgroup: "T02560111" }, // 25.6°C
      { icao: "KEWR", tmpf: 72, tgroup: "T02220100" }, // 22.2°C
      { icao: "KBOS", tmpf: 62, tgroup: "T01670056" }, // 16.7°C
      { icao: "KORD", tmpf: 43, tgroup: "T00610006" }, // 6.1°C
      { icao: "KDFW", tmpf: 92, tgroup: "T03330222" }, // 33.3°C
      { icao: "KLAX", tmpf: 68, tgroup: "T02000122" }, // 20.0°C
      { icao: "KMIA", tmpf: 82, tgroup: "T02780189" }, // 27.8°C
      { icao: "KDEN", tmpf: 42, tgroup: "T00560011" }, // 5.6°C
      { icao: "KSEA", tmpf: 57, tgroup: "T01390089" }, // 13.9°C
      { icao: "KATL", tmpf: 77, tgroup: "T02500167" }, // 25.0°C
      { icao: "KPHX", tmpf: 103, tgroup: "T03940250" }, // 39.4°C → 103°F
    ];
    for (const { icao, tmpf, tgroup } of fixtures) {
      const raw = `${icao} 010000Z RMK AO2 ${tgroup}`;
      const awc = awcToObservation({
        icaoId: icao,
        obsTime: 1704067200,
        temp: Math.round(((tmpf - 32) * 5) / 9),
        dewp: Math.round(((tmpf - 32) * 5) / 9),
        rawOb: raw,
      } as AwcMetarRaw);
      const iem = iemToObservation(makeIemRow(icao.replace(/^K/, ""), tmpf, tmpf, raw));
      expect(awc?.temp_c, `${icao}: AWC.temp_c`).toBeCloseTo(iem?.temp_c ?? Number.NaN, 5);
      expect(awc?.temp_f, `${icao}: AWC.temp_f integer`).toBe(tmpf);
      expect(iem?.temp_f, `${icao}: IEM.temp_f preserved`).toBe(tmpf);
    }
  });
});

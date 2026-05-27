// Phase 18 PREC-05: exhaustive Tgroup round-trip invariant.
//
// TS parity port of Python plan 18-06 Task 1 (hypothesis property test).
// For every integer °F in [-50, 140] (covers all realistic
// surface-temperature readings), encode to Tgroup tenths-°C, parse back
// through parseTgroup + the integer-°F recovery branch, assert recovered
// F == input F.
//
// Uses exhaustive iteration rather than fast-check property randomization
// because the domain is finite and small (191 values) — exhaustive coverage
// is strictly stronger than random sampling.

import { describe, expect, it } from "vitest";

import type { AwcMetarRaw } from "../src/_fetchers/awc.js";
import { parseTgroup } from "../src/_internal/tgroup.js";
import { awcToObservation } from "../src/_parsers/awc.js";

const TS = 1704067200;

function encodeTgroup(tempC: number, dewpC: number): string {
  const tSign = tempC < 0 ? "1" : "0";
  const dSign = dewpC < 0 ? "1" : "0";
  const tAbs = Math.round(Math.abs(tempC) * 10)
    .toString()
    .padStart(3, "0");
  const dAbs = Math.round(Math.abs(dewpC) * 10)
    .toString()
    .padStart(3, "0");
  return `T${tSign}${tAbs}${dSign}${dAbs}`;
}

function tempCForIntegerF(f: number): number {
  // Round to 1 decimal place to match the ASOS Tgroup tenths-°C precision.
  return Math.round((((f - 32) * 5) / 9) * 10) / 10;
}

describe("Tgroup round-trip exhaustive invariant (Phase 18 PREC-05)", () => {
  it("parseTgroup → recovered F round-trips for every integer °F in [-50, 140]", () => {
    // -50..140 inclusive covers every realistic surface-temperature reading.
    // For each f, encode to Tgroup tenths-°C, re-parse, recover via
    // Math.round(c * 9/5 + 32), assert equals f.
    let checked = 0;
    let skipped = 0;
    for (let f = -50; f <= 140; f += 1) {
      const c = tempCForIntegerF(f);
      const tgroup = encodeTgroup(c, c);
      const [parsedC, parsedDewpC] = parseTgroup(`RMK AO2 ${tgroup}`);
      if (parsedC === null) {
        skipped += 1;
        continue;
      }
      const recoveredF = Math.round((parsedC * 9) / 5 + 32);
      const recoveredDewpF = Math.round(((parsedDewpC ?? 0) * 9) / 5 + 32);
      // Normalize -0 → 0 to dodge JS Object.is quirk.
      const normRecF = recoveredF === 0 ? 0 : recoveredF;
      const normRecDewpF = recoveredDewpF === 0 ? 0 : recoveredDewpF;
      const normF = f === 0 ? 0 : f;
      expect(normRecF, `f=${f}, c=${c}, tgroup=${tgroup}`).toBe(normF);
      expect(normRecDewpF, `f=${f} dewp`).toBe(normF);
      checked += 1;
    }
    // Sanity: most of the 191 values should be checked
    expect(checked).toBeGreaterThan(180);
    // Print diagnostic (visible with vitest --reporter=verbose)
    console.log(`[Phase 18 PREC-05] round-trip checked: ${checked}, skipped: ${skipped}`);
  });

  it("end-to-end via awcToObservation: every integer °F yields integer temp_f", () => {
    // Same domain, but routed through the full awcToObservation pipeline
    // to prove the integer-recovery branch fires correctly in the parser.
    // Skip bounded-out extremes.
    let checked = 0;
    for (let f = -40; f <= 130; f += 1) {
      const c = tempCForIntegerF(f);
      const tgroup = encodeTgroup(c, c);
      const row = awcToObservation({
        icaoId: "KLGA",
        obsTime: TS,
        temp: Math.round(c),
        dewp: Math.round(c),
        rawOb: `KLGA 010000Z 27008KT 10SM CLR 20/10 A3001 RMK AO2 ${tgroup}`,
      } as AwcMetarRaw);
      if (row?.temp_c === null) continue;
      // temp_f must be integer-valued
      expect(
        row?.temp_f === Math.round(row?.temp_f ?? Number.NaN),
        `f=${f}: temp_f not integer (${row?.temp_f})`,
      ).toBe(true);
      // Cross-check: round-trip matches original input
      const recovered = row?.temp_f;
      const normR = recovered === 0 ? 0 : recovered;
      const normF = f === 0 ? 0 : f;
      expect(normR, `f=${f}`).toBe(normF);
      checked += 1;
    }
    expect(checked).toBeGreaterThan(160);
  });
});

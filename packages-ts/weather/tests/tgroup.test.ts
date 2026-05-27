// Phase 18 PREC-02: shared parseTgroup unit tests.
//
// TS parity of Python plan 18-01 Task 1. The Tgroup helper is the single
// source of truth for parsing ASOS Tgroup tenths-°C remarks; the shared
// helper at packages-ts/weather/src/_internal/tgroup.ts is consumed by
// both _parsers/awc.ts and _parsers/iem.ts.

import { describe, expect, it } from "vitest";

import { TGROUP_RE, parseTgroup } from "../src/_internal/tgroup.js";

describe("parseTgroup (Phase 18 PREC-02 shared helper)", () => {
  it("parses happy-path positive temp + positive dewpoint", () => {
    // T02560167 → temp 25.6°C / dewp 16.7°C
    const [t, d] = parseTgroup("KNYC 010000Z 27015KT 10SM CLR 26/17 A2992 RMK AO2 T02560167");
    expect(t).toBeCloseTo(25.6, 5);
    expect(d).toBeCloseTo(16.7, 5);
  });

  it("parses negative temp + positive dewpoint", () => {
    // T10390061 → temp -3.9°C / dewp 6.1°C (cross-check: dewpoint > temp
    // is meteorologically invalid but TGROUP_RE is pure syntactic, so the
    // parser does not enforce the bound — bounds-clamping is the caller's
    // job).
    const [t, d] = parseTgroup("KORD 050300Z 27008KT 10SM CLR M04/M01 A3015 RMK AO2 T10390061");
    expect(t).toBeCloseTo(-3.9, 5);
    expect(d).toBeCloseTo(6.1, 5);
  });

  it("parses both temp + dewp negative", () => {
    // T10101021 → temp -1.0°C / dewp -2.1°C (both signs = 1 → negative)
    const [t, d] = parseTgroup("KDEN 100600Z 36003KT 10SM CLR M01/M02 A3020 RMK AO2 T10101021");
    expect(t).toBeCloseTo(-1.0, 5);
    expect(d).toBeCloseTo(-2.1, 5);
  });

  it("returns [null, null] when METAR has no RMK section", () => {
    const [t, d] = parseTgroup("KNYC 010000Z 27015KT 10SM CLR 26/17 A2992");
    expect(t).toBeNull();
    expect(d).toBeNull();
  });

  it("returns [null, null] for Tgroup pattern in body group (not in RMK)", () => {
    // T02560167 outside RMK — must NOT match (contract: remarks-only).
    const [t, d] = parseTgroup("FOO T02560167 KNYC 010000Z 27015KT 10SM CLR 26/17 A2992");
    expect(t).toBeNull();
    expect(d).toBeNull();
  });

  it("returns [null, null] when RMK present but no Tgroup", () => {
    const [t, d] = parseTgroup("KNYC 010000Z 27015KT 10SM CLR 26/17 A2992 RMK AO2 SLP049");
    expect(t).toBeNull();
    expect(d).toBeNull();
  });

  it("returns [null, null] for empty string input", () => {
    const [t, d] = parseTgroup("");
    expect(t).toBeNull();
    expect(d).toBeNull();
  });

  it("returns [null, null] for null/undefined input", () => {
    expect(parseTgroup(null)).toEqual([null, null]);
    expect(parseTgroup(undefined)).toEqual([null, null]);
  });

  it("TGROUP_RE matches a clean T-group exactly", () => {
    const m = TGROUP_RE.exec("RMK AO2 T02560167");
    expect(m).not.toBeNull();
    // Capture groups: tSign, tAbs, dSign, dAbs
    expect(m?.[1]).toBe("0");
    expect(m?.[2]).toBe("256");
    expect(m?.[3]).toBe("0");
    expect(m?.[4]).toBe("167");
  });
});

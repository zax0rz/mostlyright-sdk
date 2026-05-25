// TS-W1 Wave 2 — Kalshi NHIGH/NLOW resolver tests.
//
// Ports the parity surface of:
//   - packages/markets/src/mostlyright/markets/catalog/kalshi_nhigh.py
//   - packages/markets/src/mostlyright/markets/catalog/kalshi_nlow.py
//   - the KNOWN_WRONG_STATIONS contract test from kalshi_stations.py.
//
// The contract test is the load-bearing one: any drift in
// KALSHI_SETTLEMENT_STATIONS that resolves a city to a known-wrong
// airport silently corrupts every backtest for that city.

import { describe, expect, it } from "vitest";

import {
  KALSHI_SETTLEMENT_STATIONS,
  KNOWN_WRONG_STATIONS,
} from "../src/data/generated/kalshi-stations.js";
import { ContractIdError, kalshiNhighResolve, kalshiNlowResolve } from "../src/resolvers/index.js";

describe("kalshiNhighResolve — happy path", () => {
  it("KHIGHNYC + Date → KNYC (NOT KLGA / KJFK)", () => {
    const r = kalshiNhighResolve("KHIGHNYC", new Date("2025-01-06T00:00:00Z"));
    expect(r).toEqual({
      settlementSource: "cli.archive",
      settlementStation: "KNYC",
      cityTicker: "NYC",
      contractDate: "2025-01-06",
    });
  });

  it("KHIGHCHI → KMDW (Midway, NOT KORD)", () => {
    const r = kalshiNhighResolve("KHIGHCHI", "2025-01-06");
    expect(r.settlementStation).toBe("KMDW");
    expect(r.settlementStation).not.toBe("KORD");
    expect(r.cityTicker).toBe("CHI");
  });

  it("KHIGHDCA → KDCA (Reagan, NOT KIAD / KBWI)", () => {
    const r = kalshiNhighResolve("KHIGHDCA", "2025-01-06");
    expect(r.settlementStation).toBe("KDCA");
  });

  it("KHIGHHOU → KIAH (Intercontinental, NOT KHOU)", () => {
    const r = kalshiNhighResolve("KHIGHHOU", "2025-01-06");
    expect(r.settlementStation).toBe("KIAH");
  });

  it("KHIGHDAL → KDFW (NOT KDAL)", () => {
    const r = kalshiNhighResolve("KHIGHDAL", "2025-01-06");
    expect(r.settlementStation).toBe("KDFW");
  });

  it("is case-insensitive for the contract id", () => {
    const r = kalshiNhighResolve("khighNyc", "2025-01-06");
    expect(r.settlementStation).toBe("KNYC");
    expect(r.cityTicker).toBe("NYC");
  });

  it("settlementSource is the literal 'cli.archive'", () => {
    const r = kalshiNhighResolve("KHIGHNYC", "2025-01-06");
    expect(r.settlementSource).toBe("cli.archive");
  });

  it("returned object is frozen", () => {
    const r = kalshiNhighResolve("KHIGHNYC", "2025-01-06");
    expect(Object.isFrozen(r)).toBe(true);
  });
});

describe("kalshiNhighResolve — error path", () => {
  it("rejects a contract id missing the KHIGH prefix", () => {
    expect(() => kalshiNhighResolve("INVALID", "2025-01-06")).toThrow(ContractIdError);
  });

  it("rejects a contract id with KHIGH prefix but no city ticker", () => {
    expect(() => kalshiNhighResolve("KHIGH", "2025-01-06")).toThrow(ContractIdError);
  });

  it("rejects an unknown city ticker (KHIGHXXX)", () => {
    expect(() => kalshiNhighResolve("KHIGHXXX", "2025-01-06")).toThrow(/unknown city/);
  });

  it("rejects a non-string contractId", () => {
    expect(() => kalshiNhighResolve(123 as unknown as string, "2025-01-06")).toThrow(
      ContractIdError,
    );
  });

  it("rejects a Date with non-zero UTC time component (mirrors Python date vs datetime)", () => {
    expect(() => kalshiNhighResolve("KHIGHNYC", new Date("2025-01-06T12:00:00Z"))).toThrow(
      ContractIdError,
    );
  });

  it("rejects a Date with non-zero UTC minutes", () => {
    expect(() => kalshiNhighResolve("KHIGHNYC", new Date("2025-01-06T00:30:00Z"))).toThrow(
      ContractIdError,
    );
  });

  it("rejects a malformed date string (not YYYY-MM-DD)", () => {
    expect(() => kalshiNhighResolve("KHIGHNYC", "01/06/2025")).toThrow(ContractIdError);
  });

  it("rejects an impossible calendar date (2025-02-30)", () => {
    expect(() => kalshiNhighResolve("KHIGHNYC", "2025-02-30")).toThrow(ContractIdError);
  });

  it("rejects an invalid Date instance", () => {
    expect(() => kalshiNhighResolve("KHIGHNYC", new Date("not-a-date"))).toThrow(ContractIdError);
  });
});

describe("kalshiNlowResolve — happy path", () => {
  it("KLOWCHI + string → KMDW (Chicago = Midway, NOT KORD)", () => {
    const r = kalshiNlowResolve("KLOWCHI", "2025-01-06");
    expect(r).toEqual({
      settlementSource: "cli.archive",
      settlementStation: "KMDW",
      cityTicker: "CHI",
      contractDate: "2025-01-06",
    });
  });

  it("KLOWNYC → KNYC (Central Park, NOT LGA/JFK)", () => {
    const r = kalshiNlowResolve("KLOWNYC", "2025-01-06");
    expect(r.settlementStation).toBe("KNYC");
  });

  it("is case-insensitive for the contract id", () => {
    const r = kalshiNlowResolve("klowChi", "2025-01-06");
    expect(r.settlementStation).toBe("KMDW");
    expect(r.cityTicker).toBe("CHI");
  });

  it("accepts a UTC date-only Date", () => {
    const r = kalshiNlowResolve("KLOWNYC", new Date("2025-01-06T00:00:00Z"));
    expect(r.contractDate).toBe("2025-01-06");
  });

  it("returned object is frozen", () => {
    const r = kalshiNlowResolve("KLOWNYC", "2025-01-06");
    expect(Object.isFrozen(r)).toBe(true);
  });
});

describe("kalshiNlowResolve — error path", () => {
  it("rejects a contract id missing the KLOW prefix", () => {
    expect(() => kalshiNlowResolve("INVALID", "2025-01-06")).toThrow(ContractIdError);
  });

  it("rejects a contract id with KLOW prefix but no city ticker", () => {
    expect(() => kalshiNlowResolve("KLOW", "2025-01-06")).toThrow(ContractIdError);
  });

  it("rejects an unknown city ticker (KLOWXXX)", () => {
    expect(() => kalshiNlowResolve("KLOWXXX", "2025-01-06")).toThrow(/unknown city/);
  });

  it("rejects a Date with non-zero UTC time component", () => {
    expect(() => kalshiNlowResolve("KLOWNYC", new Date("2025-01-06T12:00:00Z"))).toThrow(
      ContractIdError,
    );
  });

  it("rejects a malformed date string", () => {
    expect(() => kalshiNlowResolve("KLOWNYC", "2025/01/06")).toThrow(ContractIdError);
  });
});

describe("KNOWN_WRONG_STATIONS contract test (parity-critical)", () => {
  // This is the load-bearing test from
  // packages/markets/.../kalshi_stations.py — any drift here silently
  // corrupts backtests for the affected city. If a known-wrong station
  // ever appears as a settlement station, every historical NHIGH/NLOW
  // pair for that city resolves against the wrong CLI report.
  it("no value in KALSHI_SETTLEMENT_STATIONS appears in KNOWN_WRONG_STATIONS", () => {
    const offenders: Array<{ city: string; station: string }> = [];
    for (const [city, entry] of Object.entries(KALSHI_SETTLEMENT_STATIONS)) {
      if (KNOWN_WRONG_STATIONS.has(entry.station)) {
        offenders.push({ city, station: entry.station });
      }
    }
    expect(offenders).toEqual([]);
  });

  it("KNOWN_WRONG_STATIONS contains the documented bad stations", () => {
    // Sanity: if codegen regresses and produces an empty set, the
    // contract test above would trivially pass. Pin the set membership.
    const required = ["KLGA", "KJFK", "KEWR", "KORD", "KIAD", "KBWI", "KOAK", "KHOU", "KDAL"];
    for (const s of required) {
      expect(KNOWN_WRONG_STATIONS.has(s)).toBe(true);
    }
  });

  it("every settlement station is a 4-letter K-prefixed ICAO", () => {
    for (const entry of Object.values(KALSHI_SETTLEMENT_STATIONS)) {
      expect(entry.station).toMatch(/^K[A-Z]{3}$/);
    }
  });
});

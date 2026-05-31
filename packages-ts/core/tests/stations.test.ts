import { describe, expect, it } from "vitest";

import { STATIONS } from "../src/data/generated/stations.js";
import { CATALOG, type Station, StationCatalog } from "../src/index.js";

// The 21 Kalshi NHIGH/NLOW settlement ICAOs (mirrors the markets citations).
const KALSHI_ICAOS = new Set([
  "KATL",
  "KAUS",
  "KBOS",
  "KDCA",
  "KDEN",
  "KDFW",
  "KLAX",
  "KMDW",
  "KMIA",
  "KMSP",
  "KNYC",
  "KPHL",
  "KPHX",
  "KSEA",
  "KSFO",
  "KIAH",
  "KDTW",
  "KCVG",
  "KBNA",
  "KSLC",
  "KLAS",
]);

// Registry stations no prediction-market venue settles against. Phase 23 grew
// this from 4 to 29: 3 US bare (KHOU moved TO polymarket) + 26 intl (roster
// drops + the London/Moscow/Taipei/HK/Paris move-sources).
const NO_VENUE_ICAOS = new Set([
  "KMSY",
  "KOKC",
  "KSAT",
  "EDDB",
  "EDDF",
  "EGKK",
  "EKCH",
  "ESSA",
  "LEBL",
  "LFPO",
  "LIRF",
  "LOWW",
  "LSZH",
  "NZAA",
  "OERK",
  "OMDB",
  "OTHH",
  "RJAA",
  "VABB",
  "VIDP",
  "VTBS",
  "YBBN",
  "YMML",
  "YSSY",
  "EGLL",
  "UUEE",
  "RCTP",
  "VHHH",
  "LFPG",
]);

const icaosOf = (stations: ReadonlyArray<Station>) => new Set(stations.map((s) => s.icao));

describe("StationCatalog", () => {
  it("covers the full 94-station registry", () => {
    expect(CATALOG.size).toBe(94);
    expect(CATALOG.size).toBe(STATIONS.length);
  });

  it("resolves by code, ICAO, and intl, including the 5 added stations", () => {
    expect(CATALOG.get("NYC").icao).toBe("KNYC");
    expect(CATALOG.get("KNYC").code).toBe("NYC");
    expect(CATALOG.get("EGLL").country).toBe("GB");
    expect(CATALOG.get("IAH").icao).toBe("KIAH");
    expect(CATALOG.get("KDTW").code).toBe("DTW");
  });

  it("throws on an unknown station", () => {
    expect(() => CATALOG.get("ZZZZ")).toThrow(/Unknown station/);
  });

  it("has() accepts code and ICAO", () => {
    expect(CATALOG.has("NYC")).toBe(true);
    expect(CATALOG.has("KNYC")).toBe(true);
    expect(CATALOG.has("ZZZZ")).toBe(false);
  });

  it("venue union is exactly {kalshi, polymarket}", () => {
    expect(CATALOG.venues()).toEqual(new Set(["kalshi", "polymarket"]));
  });

  it("kalshi venue equals the settlement universe, NOT every US station", () => {
    expect(icaosOf(CATALOG.filterByVenue("kalshi"))).toEqual(KALSHI_ICAOS);
    expect(CATALOG.filterByVenue("kalshi").length).toBe(21);
  });

  it("polymarket venue is the explicit 50-station roster, NOT every intl", () => {
    const poly = icaosOf(CATALOG.filterByVenue("polymarket"));
    expect(CATALOG.filterByVenue("polymarket").length).toBe(50);
    // NYC→KLGA / Chicago→KORD are now registry stations and ARE tagged.
    expect(poly.has("KLGA")).toBe(true);
    expect(poly.has("KORD")).toBe(true);
    // Roster drops + move-sources are NOT polymarket.
    for (const icao of ["EGLL", "LFPG", "VHHH", "RJAA", "YSSY", "OMDB"]) {
      expect(poly.has(icao)).toBe(false);
    }
  });

  it("Kalshi and Polymarket diverge on NYC, Chicago, and Houston", () => {
    // KNYC/KMDW are Kalshi-only — Polymarket settles NYC/Chicago against KLGA/KORD.
    expect(CATALOG.get("KNYC").venues).toContain("kalshi");
    expect(CATALOG.get("KNYC").venues).not.toContain("polymarket");
    expect(CATALOG.get("KMDW").venues).not.toContain("polymarket");
    // KLGA/KORD are Polymarket-only (the divergence partners).
    expect([...CATALOG.get("KLGA").venues]).toEqual(["polymarket"]);
    expect([...CATALOG.get("KORD").venues]).toEqual(["polymarket"]);
    // Houston (Phase 23): Kalshi=KIAH, Polymarket moved to KHOU — now divergent.
    expect([...CATALOG.get("KIAH").venues]).toEqual(["kalshi"]);
    expect([...CATALOG.get("KHOU").venues]).toEqual(["polymarket"]);
  });

  it("international stations are never tagged kalshi", () => {
    const intlKalshi = [...CATALOG].filter(
      (s) => s.country !== "US" && s.venues.includes("kalshi"),
    );
    expect(intlKalshi).toEqual([]);
  });

  it("bare weather stations carry no venue tag", () => {
    const untagged = new Set([...CATALOG].filter((s) => s.venues.length === 0).map((s) => s.icao));
    expect(untagged).toEqual(NO_VENUE_ICAOS);
  });

  it("filterByCountry works", () => {
    expect(CATALOG.filterByCountry("US").length).toBe(29);
    expect([...CATALOG].filter((s) => s.country !== "US").length).toBe(65);
    expect(CATALOG.filterByCountry("GB")[0]?.icao).toBe("EGKK");
  });

  it("filter results are sorted by ICAO", () => {
    const icaos = CATALOG.filterByVenue("polymarket").map((s) => s.icao);
    expect(icaos).toEqual([...icaos].sort((a, b) => a.localeCompare(b)));
  });

  it("supports an explicit subset catalog", () => {
    const subset = new StationCatalog(STATIONS.filter((s) => s.icao === "KNYC"));
    expect(subset.size).toBe(1);
    expect(subset.get("KNYC").code).toBe("NYC");
  });
});

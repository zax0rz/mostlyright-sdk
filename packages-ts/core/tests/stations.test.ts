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

// US registry stations no prediction-market venue settles against. Houston
// trades on both venues but settles against KIAH, not KHOU.
const NO_VENUE_ICAOS = new Set(["KHOU", "KMSY", "KOKC", "KSAT"]);

const icaosOf = (stations: ReadonlyArray<Station>) => new Set(stations.map((s) => s.icao));

describe("StationCatalog", () => {
  it("covers the full 66-station registry", () => {
    expect(CATALOG.size).toBe(66);
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

  it("polymarket venue is intl + the shared-US cities (41 + 15 = 56)", () => {
    const poly = icaosOf(CATALOG.filterByVenue("polymarket"));
    const intl = [...CATALOG].filter((s) => s.country !== "US").map((s) => s.icao);
    for (const icao of intl) expect(poly.has(icao)).toBe(true);
    expect(CATALOG.filterByVenue("polymarket").length).toBe(56);
  });

  it("Kalshi and Polymarket diverge on NYC and Chicago", () => {
    // KNYC/KMDW are Kalshi-only — Polymarket settles NYC/Chicago against
    // KLGA/KORD, which are not registry stations.
    expect(CATALOG.get("KNYC").venues).toContain("kalshi");
    expect(CATALOG.get("KNYC").venues).not.toContain("polymarket");
    expect(CATALOG.get("KMDW").venues).not.toContain("polymarket");
    // Houston settles against KIAH on both venues; KHOU carries no tag.
    expect([...CATALOG.get("KIAH").venues].sort()).toEqual(["kalshi", "polymarket"]);
    expect(CATALOG.get("KHOU").venues).toEqual([]);
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
    expect(CATALOG.filterByCountry("US").length).toBe(25);
    expect([...CATALOG].filter((s) => s.country !== "US").length).toBe(41);
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

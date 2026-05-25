// Phase 10 — tests for the TS composable research() dispatcher.

import { describe, expect, it } from "vitest";

import {
  annotateSettlesFor,
  buildOverrideWarning,
  discover,
  resolveCity,
  resolveContract,
  validateSelectors,
} from "../src/index.js";
import { research } from "../src/research.js";

describe("validateSelectors", () => {
  it("station only returns 'station'", () => {
    expect(validateSelectors({ station: "KNYC" })).toBe("station");
  });

  it("city only returns 'city'", () => {
    expect(validateSelectors({ city: "NYC" })).toBe("city");
  });

  it("contract only returns 'contract'", () => {
    expect(validateSelectors({ contract: "kalshi:KHIGHNYC" })).toBe("contract");
  });

  it("contracts only returns 'contracts'", () => {
    expect(validateSelectors({ contracts: ["kalshi:KHIGHNYC"] })).toBe("contracts");
  });

  it("no selector throws", () => {
    expect(() => validateSelectors({})).toThrow(/exactly one of/);
  });

  it("empty string selector treated as missing", () => {
    expect(() => validateSelectors({ station: "", city: "" })).toThrow(/exactly one of/);
  });

  it("empty contracts array treated as missing", () => {
    expect(() => validateSelectors({ contracts: [] })).toThrow(/exactly one of/);
  });

  it("two selectors throws", () => {
    expect(() => validateSelectors({ station: "KNYC", city: "NYC" })).toThrow(/mutually exclusive/);
  });
});

describe("resolveContract", () => {
  it("kalshi:KHIGHNYC → KNYC", () => {
    expect(resolveContract("kalshi:KHIGHNYC")).toEqual(["KNYC", "kalshi"]);
  });

  it("kalshi:KXHIGHNYC → KNYC", () => {
    expect(resolveContract("kalshi:KXHIGHNYC")).toEqual(["KNYC", "kalshi"]);
  });

  it("kalshi:KLOWNYC → KNYC", () => {
    expect(resolveContract("kalshi:KLOWNYC")).toEqual(["KNYC", "kalshi"]);
  });

  it("full ticker with date suffix → KNYC", () => {
    expect(resolveContract("kalshi:KXHIGHNYC-25MAY26-T79")).toEqual(["KNYC", "kalshi"]);
  });

  it("low ticker with date suffix → KMDW", () => {
    expect(resolveContract("kalshi:KXLOWCHI-25MAY26-T50")).toEqual(["KMDW", "kalshi"]);
  });

  it("kalshi:KXHIGHNY-25MAY26-T79 → KNYC (iter-1 codex HIGH alias)", () => {
    expect(resolveContract("kalshi:KXHIGHNY-25MAY26-T79")).toEqual(["KNYC", "kalshi"]);
  });

  it("kalshi:KXLOWNY-25MAY26-T50 → KNYC (iter-1 codex HIGH alias)", () => {
    expect(resolveContract("kalshi:KXLOWNY-25MAY26-T50")).toEqual(["KNYC", "kalshi"]);
  });

  it("kalshi:KHIGHCHI → KMDW (Kalshi uses Midway)", () => {
    expect(resolveContract("kalshi:KHIGHCHI")).toEqual(["KMDW", "kalshi"]);
  });

  it("polymarket throws NotImplementedError-style message", () => {
    expect(() => resolveContract("polymarket:0xabc")).toThrow(/v0.3/);
  });

  it("unknown issuer throws", () => {
    expect(() => resolveContract("predictit:abc")).toThrow(/unknown issuer/);
  });

  it("missing colon throws TypeError", () => {
    expect(() => resolveContract("KHIGHNYC")).toThrow(TypeError);
  });
});

describe("resolveCity", () => {
  it("NYC includes KNYC and KLGA", () => {
    const stations = resolveCity("NYC");
    expect(stations).toContain("KNYC");
    expect(stations).toContain("KLGA");
  });

  it("NYC includes denylist backstops KJFK + KEWR", () => {
    const stations = resolveCity("NYC");
    expect(stations).toContain("KJFK");
    expect(stations).toContain("KEWR");
  });

  it("chicago (polymarket slug) includes KORD and denylist KMDW", () => {
    const stations = resolveCity("chicago");
    expect(stations).toContain("KORD");
    expect(stations).toContain("KMDW"); // denylist surfaces it
  });

  it("CHI (Kalshi slug) includes KMDW", () => {
    const stations = resolveCity("CHI");
    expect(stations).toContain("KMDW");
  });

  it("unknown city throws", () => {
    expect(() => resolveCity("atlantis")).toThrow(/unknown city/);
  });

  it("empty city throws", () => {
    expect(() => resolveCity("")).toThrow(/non-empty/);
  });

  it("dedupes overlapping stations", () => {
    const stations = resolveCity("NYC");
    expect(stations.filter((s) => s === "KNYC").length).toBe(1);
    expect(stations.filter((s) => s === "KLGA").length).toBe(1);
  });

  it("LAX (Kalshi short) surfaces Polymarket los_angeles entry", () => {
    const stations = resolveCity("LAX");
    expect(stations).toContain("KLAX");
    const annotations = annotateSettlesFor("KLAX", "LAX");
    expect(annotations).toContain("kalshi:LAX");
    expect(annotations).toContain("polymarket:los_angeles");
  });

  it("los_angeles (Polymarket long) surfaces Kalshi LAX entry", () => {
    const stations = resolveCity("los_angeles");
    expect(stations).toContain("KLAX");
    const annotations = annotateSettlesFor("KLAX", "los_angeles");
    expect(annotations).toContain("kalshi:LAX");
    expect(annotations).toContain("polymarket:los_angeles");
  });

  it("chicago and CHI return overlapping cross-issuer neighborhoods", () => {
    const chicagoLong = resolveCity("chicago");
    const chiShort = resolveCity("CHI");
    // Both forms surface KMDW (Kalshi) AND KORD (Polymarket).
    expect(chicagoLong).toContain("KMDW");
    expect(chicagoLong).toContain("KORD");
    expect(chiShort).toContain("KMDW");
    expect(chiShort).toContain("KORD");
  });
});

describe("annotateSettlesFor", () => {
  it("KNYC for NYC returns kalshi:NYC", () => {
    expect(annotateSettlesFor("KNYC", "NYC")).toContain("kalshi:NYC");
  });

  it("KLGA for NYC returns polymarket:nyc", () => {
    expect(annotateSettlesFor("KLGA", "NYC")).toContain("polymarket:nyc");
  });

  it("KJFK for NYC is empty (denylist backstop)", () => {
    expect(annotateSettlesFor("KJFK", "NYC")).toEqual([]);
  });

  it("null city returns empty", () => {
    expect(annotateSettlesFor("KNYC", null)).toEqual([]);
  });

  it("KORD for chicago returns polymarket:chicago", () => {
    expect(annotateSettlesFor("KORD", "chicago")).toContain("polymarket:chicago");
  });
});

describe("buildOverrideWarning", () => {
  it("returns a structured warning payload", () => {
    const w = buildOverrideWarning("KNYC", "KJFK");
    expect(w.kind).toBe("StationOverrideWarning");
    expect(w.contractStation).toBe("KNYC");
    expect(w.overrideStation).toBe("KJFK");
    expect(w.message).toContain("KNYC");
    expect(w.message).toContain("KJFK");
  });
});

describe("discover({city})", () => {
  it("NYC returns rows with city + station + settlesFor", () => {
    const r = discover({ city: "NYC" });
    expect(r.source).toBe("discover");
    expect(r.city).toBe("NYC");
    expect(r.rows.length).toBeGreaterThan(0);
    const knyc = r.rows.find((row) => row.station === "KNYC");
    expect(knyc?.settlesFor).toContain("kalshi:NYC");
    const klga = r.rows.find((row) => row.station === "KLGA");
    expect(klga?.settlesFor).toContain("polymarket:nyc");
  });

  it("NYC denylist backstops appear with empty settlesFor", () => {
    const r = discover({ city: "NYC" });
    const kjfk = r.rows.find((row) => row.station === "KJFK");
    expect(kjfk?.settlesFor).toEqual([]);
  });

  it("unknown city throws", () => {
    expect(() => discover({ city: "atlantis" })).toThrow(/unknown city/);
  });
});

describe("research() Phase 10 signature validation", () => {
  it("no selector throws", async () => {
    await expect(research("", "2025-01-06", "2025-01-12")).rejects.toThrow(/exactly one of/);
  });

  it("two selectors throws", async () => {
    await expect(research("KNYC", "2025-01-06", "2025-01-12", { city: "NYC" })).rejects.toThrow(
      /mutually exclusive/,
    );
  });

  it("sources + source mutually exclusive", async () => {
    await expect(
      research("KNYC", "2025-01-06", "2025-01-12", {
        sources: ["iem.archive"],
        source: "iem.archive",
      }),
    ).rejects.toThrow(/mutually exclusive/);
  });

  it("sources alone raises v0.3 deferred (iter-1 codex HIGH)", async () => {
    await expect(
      research("KNYC", "2025-01-06", "2025-01-12", { sources: ["iem.archive"] }),
    ).rejects.toThrow(/v0.3/);
  });

  it("source alone raises v0.3 deferred (iter-1 codex HIGH)", async () => {
    await expect(
      research("KNYC", "2025-01-06", "2025-01-12", { source: "iem.archive" }),
    ).rejects.toThrow(/researchBySource/);
  });

  it("stationOverride requires contract", async () => {
    await expect(
      research("KNYC", "2025-01-06", "2025-01-12", { stationOverride: "KJFK" }),
    ).rejects.toThrow(/stationOverride requires contract/);
  });

  it("includeTrades requires contract/contracts", async () => {
    await expect(
      research("KNYC", "2025-01-06", "2025-01-12", { includeTrades: true }),
    ).rejects.toThrow(/includeTrades requires/);
  });

  it("city selector raises v0.3 deferred", async () => {
    await expect(research("", "2025-01-06", "2025-01-12", { city: "NYC" })).rejects.toThrow(/v0.3/);
  });

  it("contract selector raises v0.3 deferred", async () => {
    await expect(
      research("", "2025-01-06", "2025-01-12", { contract: "kalshi:KHIGHNYC" }),
    ).rejects.toThrow(/v0.3/);
  });

  it("contracts selector raises v0.3 deferred", async () => {
    await expect(
      research("", "2025-01-06", "2025-01-12", {
        contracts: ["kalshi:KHIGHNYC"],
        includeTrades: true,
      }),
    ).rejects.toThrow(/v0.3/);
  });
});

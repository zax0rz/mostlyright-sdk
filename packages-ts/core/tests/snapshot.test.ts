import { describe, expect, it } from "vitest";

import {
  _CLI_PUBLICATION_DELAY_HOURS,
  _MARKET_CLOSE_HOUR_LST,
  _MARKET_CLOSE_MINUTE_LST,
  _STATION_TZ,
  _lstOffsetHours,
  _resolveStationTz,
  cliAvailableAt,
  marketCloseUtc,
  settlementDateFor,
  settlementWindowUtc,
} from "../src/snapshot.js";

describe("_STATION_TZ coverage", () => {
  it("includes all 20 primary Kalshi cities", () => {
    const kalshi = [
      "NYC",
      "LAX",
      "ORD",
      "DFW",
      "MIA",
      "ATL",
      "BOS",
      "DEN",
      "SEA",
      "PHX",
      "PHL",
      "DCA",
      "MSP",
      "DTW",
      "HOU",
      "SLC",
      "LAS",
      "SAN",
      "SFO",
      "PDX",
    ];
    for (const code of kalshi) {
      expect(_STATION_TZ).toHaveProperty(code);
    }
  });

  it("constants match Python: 10h CLI delay, 16:30 LST market close", () => {
    expect(_CLI_PUBLICATION_DELAY_HOURS).toBe(10);
    expect(_MARKET_CLOSE_HOUR_LST).toBe(16);
    expect(_MARKET_CLOSE_MINUTE_LST).toBe(30);
  });
});

describe("_lstOffsetHours", () => {
  it("America/New_York → -5", () => {
    expect(_lstOffsetHours("America/New_York")).toBe(-5);
  });
  it("America/Chicago → -6", () => {
    expect(_lstOffsetHours("America/Chicago")).toBe(-6);
  });
  it("America/Denver → -7", () => {
    expect(_lstOffsetHours("America/Denver")).toBe(-7);
  });
  it("America/Los_Angeles → -8", () => {
    expect(_lstOffsetHours("America/Los_Angeles")).toBe(-8);
  });
  it("Pacific/Honolulu → -10", () => {
    expect(_lstOffsetHours("Pacific/Honolulu")).toBe(-10);
  });
  it("America/Phoenix → -7 (no DST)", () => {
    expect(_lstOffsetHours("America/Phoenix")).toBe(-7);
  });
});

describe("_resolveStationTz", () => {
  it("resolves NWS 3-letter code", () => {
    expect(_resolveStationTz("NYC")).toBe("America/New_York");
  });
  it("strips leading K from 4-letter ICAO", () => {
    expect(_resolveStationTz("KORD")).toBe("America/Chicago");
  });
  it("honors tzOverride", () => {
    expect(_resolveStationTz("XYZ", "Pacific/Auckland")).toBe("Pacific/Auckland");
  });
  it("throws for unknown station with no override", () => {
    expect(() => _resolveStationTz("ZZZ")).toThrow(/Unknown station timezone/);
  });
});

describe("settlementDateFor", () => {
  it("NYC early-morning UTC → previous local date", () => {
    // 03:00 UTC on July 4 = 22:00 LST (UTC-5) on July 3
    expect(settlementDateFor("2024-07-04T03:00:00Z", "NYC")).toBe("2024-07-03");
  });

  it("NYC mid-day UTC → same local date", () => {
    // 17:00 UTC = 12:00 LST
    expect(settlementDateFor("2024-07-04T17:00:00Z", "NYC")).toBe("2024-07-04");
  });

  it("LAX vs NYC at same UTC moment", () => {
    // 06:00 UTC: NYC = 01:00 (Jul 4), LAX = 22:00 prev day (Jul 3, UTC-8)
    expect(settlementDateFor("2024-07-04T06:00:00Z", "NYC")).toBe("2024-07-04");
    expect(settlementDateFor("2024-07-04T06:00:00Z", "LAX")).toBe("2024-07-03");
  });

  it("DST is ignored — March 10 boundary uses standard offset", () => {
    // US DST starts 2024-03-10 02:00 EST. Python ignores DST entirely
    // (always uses LST = UTC-5 for NYC), so we should match.
    // 05:00 UTC = 00:00 LST (right at midnight LST) → settlement date = "2024-03-10"
    expect(settlementDateFor("2024-03-10T05:00:00Z", "NYC")).toBe("2024-03-10");
    // 04:59 UTC = 23:59 LST prev day
    expect(settlementDateFor("2024-03-10T04:59:00Z", "NYC")).toBe("2024-03-09");
  });

  it("accepts Date object", () => {
    const d = new Date(Date.UTC(2024, 6, 4, 3, 0, 0));
    expect(settlementDateFor(d, "NYC")).toBe("2024-07-03");
  });
});

describe("settlementWindowUtc", () => {
  it("NYC window spans exactly 24h", () => {
    const [start, end] = settlementWindowUtc("2024-07-04", "NYC");
    expect(end.getTime() - start.getTime()).toBe(24 * 3_600_000);
  });

  it("NYC midnight LST = 05:00 UTC", () => {
    const [start, end] = settlementWindowUtc("2024-07-04", "NYC");
    expect(start.toISOString()).toBe("2024-07-04T05:00:00.000Z");
    expect(end.toISOString()).toBe("2024-07-05T05:00:00.000Z");
  });

  it("LAX midnight LST = 08:00 UTC", () => {
    const [start] = settlementWindowUtc("2024-07-04", "LAX");
    expect(start.toISOString()).toBe("2024-07-04T08:00:00.000Z");
  });

  it("throws on malformed date string", () => {
    expect(() => settlementWindowUtc("not-a-date", "NYC")).toThrow();
  });
});

describe("cliAvailableAt", () => {
  it("default delay = 10h after window end (= 10h after midnight LST D+1)", () => {
    // NYC: window end for 2024-07-04 is 2024-07-05T05:00:00Z → +10h = 15:00Z
    const t = cliAvailableAt("2024-07-04", "NYC");
    expect(t.toISOString()).toBe("2024-07-05T15:00:00.000Z");
  });

  it("custom delay honored", () => {
    const t = cliAvailableAt("2024-07-04", "NYC", 12);
    expect(t.toISOString()).toBe("2024-07-05T17:00:00.000Z");
  });
});

describe("marketCloseUtc", () => {
  it("NYC 4:30 PM LST → 21:30 UTC (UTC-5)", () => {
    const t = marketCloseUtc("2024-07-04", "NYC");
    expect(t.toISOString()).toBe("2024-07-04T21:30:00.000Z");
  });

  it("LAX 4:30 PM LST → 00:30 UTC next day", () => {
    // 16:30 LST (UTC-8) → 00:30 UTC next day
    const t = marketCloseUtc("2024-07-04", "LAX");
    expect(t.toISOString()).toBe("2024-07-05T00:30:00.000Z");
  });

  it("honors tzOverride for unknown station", () => {
    const t = marketCloseUtc("2024-07-04", "ZZZ", "America/Chicago");
    // 16:30 LST CST (UTC-6) → 22:30 UTC
    expect(t.toISOString()).toBe("2024-07-04T22:30:00.000Z");
  });
});

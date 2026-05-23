import { describe, expect, it } from "vitest";

import { STATIONS, STATION_BY_CODE, STATION_BY_ICAO } from "../src/data/generated/stations.js";

describe("codegen: stations", () => {
  it("has at least 60 entries (20 US + 40 intl)", () => {
    expect(STATIONS.length).toBeGreaterThanOrEqual(60);
  });

  it("includes KNYC via STATION_BY_ICAO", () => {
    const knyc = STATION_BY_ICAO.get("KNYC");
    expect(knyc?.icao).toBe("KNYC");
  });

  it("resolves the 3-letter US code 'NYC' to the same row as 'KNYC'", () => {
    const byCode = STATION_BY_CODE.get("NYC");
    const byIcao = STATION_BY_ICAO.get("KNYC");
    expect(byCode).toBeDefined();
    expect(byCode).toBe(byIcao);
  });

  it("preserves the `country` field for US stations (TS-W0 iter-1 HIGH 2)", () => {
    expect(STATION_BY_ICAO.get("KNYC")?.country).toBe("US");
  });

  it("preserves the `country` field for intl stations", () => {
    expect(STATION_BY_ICAO.get("EDDB")?.country).toBe("DE");
  });
});

// Phase 20 OM-06 / OM-09 — TS forecast cache tests.

import { describe, expect, it } from "vitest";

import {
  cacheKeyForForecast,
  readForecastCache,
  writeForecastCache,
} from "../src/cache/forecast.js";
import type { OpenMeteoRow } from "../src/forecasts/types.js";

interface InMemoryStore {
  data: Map<string, unknown>;
  get<T>(key: string): Promise<T | null>;
  set<T>(key: string, value: T): Promise<void>;
  delete(key: string): Promise<void>;
  withLock<T>(_key: string, fn: () => Promise<T>): Promise<T>;
}

function makeStore(): InMemoryStore {
  const data = new Map<string, unknown>();
  return {
    data,
    async get<T>(key: string): Promise<T | null> {
      return (data.get(key) as T | undefined) ?? null;
    },
    async set<T>(key: string, value: T): Promise<void> {
      data.set(key, value);
    },
    async delete(key: string): Promise<void> {
      data.delete(key);
    },
    async withLock<T>(_key: string, fn: () => Promise<T>): Promise<T> {
      return fn();
    },
  };
}

const SAMPLE_ROW: OpenMeteoRow = {
  station: "KNYC",
  model: "gfs_global",
  issuedAt: "2024-05-31T18:00:00.000Z",
  validAt: "2024-06-01T23:00:00.000Z",
  forecastHour: 29,
  tempC: 22.5,
  dewPointC: null,
  apparentTempC: null,
  windSpeedMs: null,
  windDirDeg: null,
  windGustsMs: null,
  precipProbability: null,
  precipitationMm: null,
  cloudCoverPct: null,
  surfacePressureHpa: null,
  pressureMslHpa: null,
  shortwaveRadiationWm2: null,
  directRadiationWm2: null,
  capeJkg: null,
  freezingLevelM: null,
  snowDepthM: null,
  visibilityM: null,
  weatherCode: null,
  source: "open_meteo.previous_runs",
  retrievedAt: "2026-05-28T00:00:00.000Z",
};

describe("Phase 20 OM-06 — TS forecast cache key", () => {
  it("cacheKeyForForecast emits canonical D-09 layout", () => {
    const key = cacheKeyForForecast("KNYC", "open_meteo.previous_runs", "gfs_global", 2024, 6);
    expect(key).toBe("forecasts:open_meteo.previous_runs:gfs_global:KNYC:2024:06");
  });
});

describe("Phase 20 OM-09 — TS forecast cache eligibility", () => {
  it("write + read previous_runs round-trips", async () => {
    const store = makeStore();
    await writeForecastCache(
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      store as any,
      "KNYC",
      "open_meteo.previous_runs",
      "gfs_global",
      2024,
      6,
      [SAMPLE_ROW],
    );
    const got = await readForecastCache(
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      store as any,
      "KNYC",
      "open_meteo.previous_runs",
      "gfs_global",
      2024,
      6,
    );
    expect(got).not.toBeNull();
    expect(got).toHaveLength(1);
    expect(got?.[0]?.station).toBe("KNYC");
  });

  it("live source is never cached", async () => {
    const store = makeStore();
    await writeForecastCache(
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      store as any,
      "KNYC",
      "open_meteo.live",
      "gfs_global",
      2024,
      6,
      [{ ...SAMPLE_ROW, source: "open_meteo.live" }],
    );
    expect(store.data.size).toBe(0);
  });

  it("seamless source is never cached", async () => {
    const store = makeStore();
    await writeForecastCache(
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      store as any,
      "KNYC",
      "open_meteo.seamless",
      "gfs_global",
      2024,
      6,
      [
        {
          ...SAMPLE_ROW,
          source: "open_meteo.seamless",
          issuedAt: null,
        },
      ],
    );
    expect(store.data.size).toBe(0);
  });

  it("readForecastCache returns null for live source", async () => {
    const store = makeStore();
    store.data.set(cacheKeyForForecast("KNYC", "open_meteo.live", "gfs_global", 2024, 6), [
      SAMPLE_ROW,
    ]);
    const got = await readForecastCache(
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      store as any,
      "KNYC",
      "open_meteo.live",
      "gfs_global",
      2024,
      6,
    );
    expect(got).toBeNull();
  });

  it("readForecastCache miss returns null", async () => {
    const store = makeStore();
    const got = await readForecastCache(
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      store as any,
      "KNYC",
      "open_meteo.previous_runs",
      "gfs_global",
      2020,
      1,
    );
    expect(got).toBeNull();
  });

  it("empty rows is no-op", async () => {
    const store = makeStore();
    await writeForecastCache(
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      store as any,
      "KNYC",
      "open_meteo.previous_runs",
      "gfs_global",
      2024,
      6,
      [],
    );
    expect(store.data.size).toBe(0);
  });
});

// Phase 20 OM-08 OM-07: TS leakage regression for the #70 reproduction.
//
// Mirrors `tests/test_open_meteo_leakage_regression.py::test_case_1_exact_70_reproduction`.

import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it, vi } from "vitest";

import { assertIssuedAtPopulated } from "@mostlyrightmd/core/temporal";

import { openMeteoForecasts } from "../src/forecasts/open-meteo.js";

const FIXTURE_PATH = resolve(
  __dirname,
  "..",
  "..",
  "tests",
  "fixtures",
  "openmeteo",
  "case_1_KNYC_2024-06-01_h13.json",
);

function mockFetchWithPayload(payload: unknown): typeof fetch {
  return vi.fn(
    async () =>
      new Response(JSON.stringify(payload), {
        status: 200,
        headers: { "content-type": "application/json" },
      }),
  ) as unknown as typeof fetch;
}

describe("OM-08 leakage regression — case_1 (NYC 2024-06-01 #70 reproduction)", () => {
  it("the 23:00 UTC validAt row has issuedAt = 2024-05-31T18:00:00.000Z", async () => {
    const payload = JSON.parse(readFileSync(FIXTURE_PATH, "utf-8"));
    const fetchFn = mockFetchWithPayload(payload);
    const rows = await openMeteoForecasts(
      "KNYC",
      "2024-06-01",
      "2024-06-01",
      { model: "gfs_global", mode: "training", fetchFn },
    );
    const h23 = rows.find(
      (r) => r.validAt === "2024-06-01T23:00:00.000Z",
    );
    expect(h23).toBeDefined();
    expect(h23!.issuedAt).toBe("2024-05-31T18:00:00.000Z");
  });

  it("every row has issuedAt <= asOf (h13 EDT = 17:00 UTC)", async () => {
    const payload = JSON.parse(readFileSync(FIXTURE_PATH, "utf-8"));
    const fetchFn = mockFetchWithPayload(payload);
    const rows = await openMeteoForecasts(
      "KNYC",
      "2024-06-01",
      "2024-06-01",
      { model: "gfs_global", mode: "training", fetchFn },
    );
    const asOf = new Date("2024-06-01T17:00:00Z").getTime();
    for (const row of rows) {
      if (row.issuedAt) {
        const issued = new Date(row.issuedAt).getTime();
        expect(issued).toBeLessThanOrEqual(asOf);
      }
    }
  });

  it("assertIssuedAtPopulated passes on all rows", async () => {
    const payload = JSON.parse(readFileSync(FIXTURE_PATH, "utf-8"));
    const fetchFn = mockFetchWithPayload(payload);
    const rows = await openMeteoForecasts(
      "KNYC",
      "2024-06-01",
      "2024-06-01",
      { model: "gfs_global", mode: "training", fetchFn },
    );
    expect(() => assertIssuedAtPopulated(rows)).not.toThrow();
  });

  it("no rows have source='open_meteo.seamless'", async () => {
    const payload = JSON.parse(readFileSync(FIXTURE_PATH, "utf-8"));
    const fetchFn = mockFetchWithPayload(payload);
    const rows = await openMeteoForecasts(
      "KNYC",
      "2024-06-01",
      "2024-06-01",
      { model: "gfs_global", mode: "training", fetchFn },
    );
    const sources = new Set(rows.map((r) => r.source));
    expect(sources.has("open_meteo.seamless")).toBe(false);
  });
});

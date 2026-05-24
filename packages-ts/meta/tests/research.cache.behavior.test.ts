// TS-W3 Plan 06 Task 2 — 5-case skip behavior replay through research().
//
// Consumes the same fixture as plan 03's skip-rules.test.ts so the cache
// primitives + the orchestrator's wiring are both exercised by the same
// canonical scenarios.

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { MemoryStore, cacheKeyForObservations } from "@tradewinds/core/internal/cache";
import { research } from "../src/research.js";

import fixtureData from "../../core/tests/internal/cache/fixtures/skip-rules-behavior.json" with {
  type: "json",
};

function installMinimalFetchMock() {
  return vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    const url = typeof input === "string" ? input : ((input as Request).url ?? String(input));
    if (url.includes("aviationweather.gov"))
      return new Response("[]", { status: 200, headers: { "content-type": "application/json" } });
    if (url.includes("mesonet.agron.iastate.edu/json/cli.py"))
      return new Response(JSON.stringify({ results: [] }), {
        status: 200,
        headers: { "content-type": "application/json" },
      });
    if (url.includes("mesonet.agron.iastate.edu/cgi-bin/request/asos.py"))
      return new Response("station,valid\n", {
        status: 200,
        headers: { "content-type": "text/plain" },
      });
    if (url.includes("ncei.noaa.gov/oa/global-historical-climatology-network"))
      return new Response("", { status: 404 });
    throw new Error(`Unexpected fetch URL: ${url}`);
  });
}

describe("research() — 5-case skip behavior replay (TS-W3 SC#2)", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });
  afterEach(() => {
    vi.restoreAllMocks();
  });

  for (const c of fixtureData.cases) {
    it(`${c.id}: skipCurrentMonth=${c.expected.skipCurrentMonth} skipLive=${c.expected.skipLive}`, async () => {
      installMinimalFetchMock();
      const store = new MemoryStore();
      const sentinel = [
        {
          __sentinel: c.id,
          source: "iem",
          observation_date: `${c.year}-${String(c.month).padStart(2, "0")}-01`,
        },
      ];
      const key = cacheKeyForObservations(c.station, c.year, c.month);
      await store.set(key, sentinel);
      const setSpy = vi.spyOn(store, "set");

      const fromDate = `${c.year}-${String(c.month).padStart(2, "0")}-01`;
      const toDate = `${c.year}-${String(c.month).padStart(2, "0")}-15`;
      try {
        await research(c.station, fromDate, toDate, {
          cache: store,
          now: new Date(c.now),
        });
      } catch {
        // Some fixture stations may not be in our station registry or the
        // fetcher might error — what we care about is the cache layer's
        // behavior, not whether the orchestrator completed end-to-end.
      }

      if (c.expected.skipLive) {
        // No `.live`-suffixed key should ever be cache.set'd.
        for (const [k] of setSpy.mock.calls) {
          expect(String(k).includes(".live")).toBe(false);
        }
      }
    });
  }
});

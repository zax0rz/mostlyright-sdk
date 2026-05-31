import { describe, expect, it } from "vitest";

import { polymarketDiscover } from "../../src/polymarket/index.js";

function jsonResponse(body: unknown, init: ResponseInit = {}): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" },
    ...init,
  });
}

describe("polymarketDiscover", () => {
  it("paginates by 100, dedups by slug, terminates on a short page", async () => {
    let calls = 0;
    const fetchFn = async (url: RequestInfo | URL) => {
      calls += 1;
      const u = url.toString();
      if (u.includes("offset=0")) {
        return jsonResponse([
          {
            id: "1",
            slug: "will-london-hottest-on-2026-05-23",
            title: "Will London be hottest?",
            description: "https://www.weather.gov/",
            endDate: "2026-05-23T23:59:59Z",
          },
          {
            id: "2",
            slug: "will-paris-coldest-on-2026-05-23",
            title: "Will Paris be coldest?",
            description: "https://www.wunderground.com/",
            endDate: "2026-05-23T23:59:59Z",
          },
        ]);
      }
      // Empty page → terminates.
      return jsonResponse([]);
    };
    const rows = await polymarketDiscover({ fetchFn, sleepBetweenMs: 0 });
    expect(rows).toHaveLength(2);
    expect(rows.map((r) => r.icao)).toEqual(["EGLC", "LFPB"]); // London EGLC (Phase 23), Paris → LFPB
    expect(rows.map((r) => r.measure)).toEqual(["high", "low"]);
    // We should not have looped forever — at most 2 page fetches (page 1 + terminating empty page).
    expect(calls).toBeLessThanOrEqual(2);
  });

  it("surfaces deferred markets with icao: null but PRESERVES the matched city (codex iter-4 P2)", async () => {
    const fetchFn = async () =>
      jsonResponse([
        {
          id: "10",
          slug: "will-taipei-be-hot-2026-05-23",
          title: "Will Taipei be hot?",
          description: "",
          endDate: "2026-05-23T23:59:59Z",
        },
      ]);
    const rows = await polymarketDiscover({ fetchFn, sleepBetweenMs: 0 });
    expect(rows).toHaveLength(1);
    expect(rows[0]?.icao).toBeNull();
    expect(rows[0]?.measure).toBeNull();
    expect(rows[0]?.city).toBe("taipei"); // preserved across the deferred path
    expect(rows[0]?.slug).toBe("will-taipei-be-hot-2026-05-23");
  });

  it("classifies empty descriptions as 'other' (codex iter-4 P2)", async () => {
    const fetchFn = async () =>
      jsonResponse([
        {
          id: "50",
          slug: "will-london-hottest-on-2026-07-04",
          title: "London July 4",
          description: "",
        },
      ]);
    const rows = await polymarketDiscover({ fetchFn, sleepBetweenMs: 0 });
    expect(rows).toHaveLength(1);
    expect(rows[0]?.resolutionSourceType).toBe("other");
  });

  it("drops unresolvable events via the onSkip callback", async () => {
    const skipped: Array<{ slug: string | null; reason: string }> = [];
    const fetchFn = async () =>
      jsonResponse([
        {
          id: "20",
          slug: "will-pluto-be-cold-2099-01-01",
          title: "Unknown city",
          description: "",
        },
      ]);
    const rows = await polymarketDiscover({
      fetchFn,
      sleepBetweenMs: 0,
      onSkip: (info) => skipped.push(info),
    });
    expect(rows).toEqual([]);
    expect(skipped).toHaveLength(1);
    expect(skipped[0]?.reason).toMatch(/no city match/);
  });

  it("unwraps the documented {data: [...]} envelope (codex iter-2 P2)", async () => {
    let page = 0;
    const fetchFn = async () => {
      page += 1;
      if (page === 1) {
        return jsonResponse({
          data: [
            {
              id: "40",
              slug: "will-london-hottest-on-2026-06-01",
              title: "London June 1",
              description: "https://www.weather.gov/",
            },
          ],
        });
      }
      return jsonResponse({ data: [] });
    };
    const rows = await polymarketDiscover({ fetchFn, sleepBetweenMs: 0 });
    expect(rows).toHaveLength(1);
    expect(rows[0]?.icao).toBe("EGLC");
  });

  it("throws on unexpected page shape (codex iter-2 P2)", async () => {
    const fetchFn = async () => jsonResponse({ unexpected: "wrapper" });
    await expect(polymarketDiscover({ fetchFn, sleepBetweenMs: 0 })).rejects.toThrow(
      /unexpected page shape/,
    );
  });

  it("dedups events that appear in multiple pages with the same slug", async () => {
    let page = 0;
    const fetchFn = async () => {
      page += 1;
      if (page > 2) return jsonResponse([]);
      return jsonResponse([
        {
          id: "30",
          slug: "will-london-hottest-on-2026-05-23",
          title: "Dup",
          description: "https://www.weather.gov/",
        },
      ]);
    };
    const rows = await polymarketDiscover({ fetchFn, sleepBetweenMs: 0 });
    expect(rows).toHaveLength(1);
  });
});

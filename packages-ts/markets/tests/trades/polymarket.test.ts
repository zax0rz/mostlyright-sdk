import { describe, expect, it } from "vitest";

import { polymarketHistory, polymarketSnapshot } from "../../src/trades/index.js";

function mockOnce(payload: unknown, status = 200): typeof fetch {
  return (async () =>
    new Response(JSON.stringify(payload), {
      status,
      headers: { "Content-Type": "application/json" },
    })) as typeof fetch;
}

describe("polymarketHistory", () => {
  it("returns rows with the expected columns + source", async () => {
    const result = await polymarketHistory(
      "0xMARKETCONDITION",
      {
        from: new Date("2026-06-01T00:00:00Z"),
        to: new Date("2026-06-02T00:00:00Z"),
      },
      {
        fetchFn: mockOnce({
          history: [
            { t: 1717200000, p: 0.42, v: 100 },
            { t: 1717203600, p: 0.45, v: 250 },
          ],
        }),
        sleepBetweenMs: 0,
      },
    );
    expect(result.rows.length).toBe(2);
    expect(result.rows[0]?.price).toBe(0.42);
    expect(result.rows.every((r) => r.source === "polymarket.gamma")).toBe(true);
    expect(result.source).toBe("polymarket.gamma");
    expect(result.marketId).toBe("0xMARKETCONDITION");
    expect(result.fidelityMinutes).toBe(60);
  });

  it("tolerates a bare-list payload", async () => {
    const result = await polymarketHistory(
      "M1",
      {
        from: new Date("2026-06-01T00:00:00Z"),
        to: new Date("2026-06-02T00:00:00Z"),
      },
      {
        fetchFn: mockOnce([{ t: 1717200000, p: 0.42, v: 100 }]),
        sleepBetweenMs: 0,
      },
    );
    expect(result.rows.length).toBe(1);
  });

  it("rejects empty marketId", async () => {
    await expect(
      polymarketHistory(
        "",
        {
          from: new Date("2026-06-01T00:00:00Z"),
          to: new Date("2026-06-02T00:00:00Z"),
        },
        { fetchFn: mockOnce({}), sleepBetweenMs: 0 },
      ),
    ).rejects.toThrow(TypeError);
  });

  it("rejects fidelityMinutes < 1", async () => {
    await expect(
      polymarketHistory(
        "M1",
        {
          from: new Date("2026-06-01T00:00:00Z"),
          to: new Date("2026-06-02T00:00:00Z"),
          fidelityMinutes: 0,
        },
        { fetchFn: mockOnce({ history: [] }), sleepBetweenMs: 0 },
      ),
    ).rejects.toThrow(RangeError);
  });

  it("rejects from >= to", async () => {
    await expect(
      polymarketHistory(
        "M1",
        {
          from: new Date("2026-06-02T00:00:00Z"),
          to: new Date("2026-06-01T00:00:00Z"),
        },
        { fetchFn: mockOnce({}), sleepBetweenMs: 0 },
      ),
    ).rejects.toThrow(RangeError);
  });

  it("empty history returns empty rows", async () => {
    const result = await polymarketHistory(
      "M1",
      {
        from: new Date("2026-06-01T00:00:00Z"),
        to: new Date("2026-06-02T00:00:00Z"),
      },
      { fetchFn: mockOnce({ history: [] }), sleepBetweenMs: 0 },
    );
    expect(result.rows.length).toBe(0);
    expect(result.source).toBe("polymarket.gamma");
  });
});

describe("polymarketSnapshot", () => {
  it("returns one row per outcome (JSON-encoded form)", async () => {
    const result = await polymarketSnapshot("E1", {
      fetchFn: mockOnce({
        id: "E1",
        markets: [
          {
            id: "M1",
            outcomes: JSON.stringify(["Yes", "No"]),
            outcomePrices: JSON.stringify(["0.62", "0.38"]),
            volume: "12345.67",
            liquidity: "5000",
          },
        ],
      }),
      sleepBetweenMs: 0,
    });
    expect(result.rows.length).toBe(2);
    expect(result.rows[0]?.outcome).toBe("Yes");
    expect(result.rows[0]?.lastPrice).toBe(0.62);
    expect(result.rows[0]?.volume).toBeCloseTo(12345.67);
    expect(result.rows.every((r) => r.source === "polymarket.gamma")).toBe(true);
    expect(result.eventId).toBe("E1");
  });

  it("supports native-list outcomes", async () => {
    const result = await polymarketSnapshot("E1", {
      fetchFn: mockOnce({
        id: "E1",
        markets: [
          {
            id: "M1",
            outcomes: ["Yes", "No"],
            outcomePrices: ["0.5", "0.5"],
            volume: 100,
            liquidity: 0,
          },
        ],
      }),
      sleepBetweenMs: 0,
    });
    expect(result.rows.length).toBe(2);
    expect(result.rows[0]?.lastPrice).toBe(0.5);
  });

  it("flattens multi-market events", async () => {
    const result = await polymarketSnapshot("E2", {
      fetchFn: mockOnce({
        id: "E2",
        markets: [
          {
            id: "M1",
            outcomes: ["Yes", "No"],
            outcomePrices: ["0.6", "0.4"],
          },
          {
            id: "M2",
            outcomes: ["Yes", "No"],
            outcomePrices: ["0.3", "0.7"],
          },
        ],
      }),
      sleepBetweenMs: 0,
    });
    expect(result.rows.length).toBe(4);
    expect(result.rows.map((r) => r.marketId)).toEqual(["M1", "M1", "M2", "M2"]);
  });

  it("rejects empty eventId", async () => {
    await expect(
      polymarketSnapshot("", { fetchFn: mockOnce({}), sleepBetweenMs: 0 }),
    ).rejects.toThrow(TypeError);
  });

  it("carries snapshotAt", async () => {
    const result = await polymarketSnapshot("E1", {
      fetchFn: mockOnce({ id: "E1", markets: [] }),
      sleepBetweenMs: 0,
    });
    expect(typeof result.snapshotAt).toBe("string");
  });
});

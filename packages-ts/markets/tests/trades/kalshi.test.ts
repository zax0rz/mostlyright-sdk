import { describe, expect, it } from "vitest";

import {
  KALSHI_API_BASE,
  KALSHI_INTERVALS,
  kalshiCandles,
  kalshiFills,
  kalshiOrderbook,
} from "../../src/trades/index.js";

const TICKER = "KXHIGHNY-25MAY26-T79";

function mockOnce(payload: unknown, status = 200): typeof fetch {
  return (async (_url: RequestInfo | URL, _init?: RequestInit) =>
    new Response(JSON.stringify(payload), {
      status,
      headers: { "Content-Type": "application/json" },
    })) as typeof fetch;
}

function mockSequence(
  payloads: ReadonlyArray<unknown | { status: number; body: unknown }>,
): typeof fetch {
  let i = 0;
  return (async (_url: RequestInfo | URL, _init?: RequestInit) => {
    const entry = payloads[i++];
    if (entry === undefined) {
      throw new Error(`mockSequence: ran out of payloads at call ${i}`);
    }
    let status = 200;
    let body: unknown = entry;
    if (typeof entry === "object" && entry !== null && "status" in entry && "body" in entry) {
      const wrapped = entry as { status: number; body: unknown };
      status = wrapped.status;
      body = wrapped.body;
    }
    return new Response(JSON.stringify(body), {
      status,
      headers: { "Content-Type": "application/json" },
    });
  }) as typeof fetch;
}

describe("kalshiCandles", () => {
  it("returns rows with the expected columns + source", async () => {
    const result = await kalshiCandles(
      TICKER,
      {
        interval: "1h",
        from: new Date("2026-06-01T00:00:00Z"),
        to: new Date("2026-06-02T00:00:00Z"),
      },
      {
        fetchFn: mockOnce({
          candlesticks: [
            {
              end_period_ts: 1717200000,
              price: { open: 50, high: 55, low: 48, close: 52 },
              volume: 100,
              open_interest: 500,
            },
            {
              end_period_ts: 1717203600,
              price: { open: 52, high: 60, low: 51, close: 58 },
              volume: 200,
              open_interest: 600,
            },
          ],
        }),
        sleepBetweenMs: 0,
      },
    );
    expect(result.rows.length).toBe(2);
    expect(result.rows[0]?.open).toBe(50);
    expect(result.rows[0]?.close).toBe(52);
    expect(result.rows[1]?.high).toBe(60);
    expect(result.rows.every((r) => r.source === "kalshi")).toBe(true);
    expect(result.source).toBe("kalshi");
    expect(result.ticker).toBe(TICKER);
    expect(result.interval).toBe("1h");
  });

  it("rejects invalid Date", async () => {
    await expect(
      kalshiCandles(
        TICKER,
        {
          interval: "1h",
          from: new Date("invalid"),
          to: new Date("2026-06-02T00:00:00Z"),
        },
        { fetchFn: mockOnce({}), sleepBetweenMs: 0 },
      ),
    ).rejects.toThrow(TypeError);
  });

  it("rejects from >= to", async () => {
    await expect(
      kalshiCandles(
        TICKER,
        {
          interval: "1h",
          from: new Date("2026-06-02T00:00:00Z"),
          to: new Date("2026-06-01T00:00:00Z"),
        },
        { fetchFn: mockOnce({}), sleepBetweenMs: 0 },
      ),
    ).rejects.toThrow(RangeError);
  });

  it("rejects unknown interval", async () => {
    await expect(
      kalshiCandles(
        TICKER,
        {
          // @ts-expect-error — verifying runtime guard
          interval: "5m",
          from: new Date("2026-06-01T00:00:00Z"),
          to: new Date("2026-06-02T00:00:00Z"),
        },
        { fetchFn: mockOnce({}), sleepBetweenMs: 0 },
      ),
    ).rejects.toThrow(RangeError);
  });

  it("interval table is exactly 1m/1h/1d", () => {
    expect(KALSHI_INTERVALS).toEqual(["1m", "1h", "1d"]);
  });

  it("builds correct URL with series prefix", async () => {
    let captured: string | URL | undefined;
    const fetchFn: typeof fetch = async (url, _init) => {
      captured = url as string | URL;
      return new Response(JSON.stringify({ candlesticks: [] }), { status: 200 });
    };
    await kalshiCandles(
      TICKER,
      {
        interval: "1h",
        from: new Date("2026-06-01T00:00:00Z"),
        to: new Date("2026-06-02T00:00:00Z"),
      },
      { fetchFn, sleepBetweenMs: 0 },
    );
    const urlStr = String(captured);
    expect(urlStr).toContain(`${KALSHI_API_BASE}/series/KXHIGHNY/markets/${TICKER}/candlesticks`);
    expect(urlStr).toContain("period_interval=60");
  });
});

describe("kalshiFills", () => {
  it("walks cursor pagination", async () => {
    const result = await kalshiFills(
      TICKER,
      {},
      {
        fetchFn: mockSequence([
          {
            trades: [
              {
                trade_id: "t1",
                created_time: 1717200000,
                yes_price: 52,
                no_price: 48,
                count: 10,
                taker_side: "yes",
              },
            ],
            cursor: "P2",
          },
          {
            trades: [
              {
                trade_id: "t2",
                created_time: "2026-06-01T00:01:00Z",
                yes_price: 53,
                no_price: 47,
                count: 5,
                taker_side: "no",
              },
            ],
            cursor: "",
          },
        ]),
        sleepBetweenMs: 0,
      },
    );
    expect(result.rows.length).toBe(2);
    expect(result.rows[0]?.tradeId).toBe("t1");
    expect(result.rows[1]?.takerSide).toBe("no");
    expect(result.rows[1]?.ts).toBe(new Date("2026-06-01T00:01:00Z").toISOString());
    expect(result.rows.every((r) => r.source === "kalshi")).toBe(true);
  });

  it("respects maxPages safety cap", async () => {
    const fetchFn: typeof fetch = async () =>
      new Response(
        JSON.stringify({
          trades: [{ trade_id: "loop", created_time: 1, count: 1 }],
          cursor: "FOREVER",
        }),
        { status: 200 },
      );
    await expect(
      kalshiFills(TICKER, { maxPages: 3 }, { fetchFn, sleepBetweenMs: 0 }),
    ).rejects.toThrow(/maxPages/);
  });

  it("rejects since >= until", async () => {
    await expect(
      kalshiFills(
        TICKER,
        {
          since: new Date("2026-06-02T00:00:00Z"),
          until: new Date("2026-06-01T00:00:00Z"),
        },
        { fetchFn: mockOnce({}), sleepBetweenMs: 0 },
      ),
    ).rejects.toThrow(RangeError);
  });
});

describe("kalshiOrderbook", () => {
  it("flattens yes/no levels into rows", async () => {
    const result = await kalshiOrderbook(
      TICKER,
      {},
      {
        fetchFn: mockOnce({
          orderbook: {
            yes: [
              [52, 100],
              [51, 200],
            ],
            no: [[48, 150]],
          },
        }),
        sleepBetweenMs: 0,
      },
    );
    expect(result.rows.length).toBe(3);
    expect(result.rows.filter((r) => r.side === "yes").length).toBe(2);
    expect(result.rows[0]?.price).toBe(52);
    expect(result.rows.every((r) => r.source === "kalshi")).toBe(true);
    expect(typeof result.snapshotAt).toBe("string");
  });

  it("supports dict-form levels", async () => {
    const result = await kalshiOrderbook(
      TICKER,
      {},
      {
        fetchFn: mockOnce({
          orderbook: {
            yes: [{ price: 50, size: 25 }],
            no: [],
          },
        }),
        sleepBetweenMs: 0,
      },
    );
    expect(result.rows.length).toBe(1);
    expect(result.rows[0]?.price).toBe(50);
    expect(result.rows[0]?.size).toBe(25);
  });

  it("rejects depth out of range", async () => {
    await expect(
      kalshiOrderbook(TICKER, { depth: 0 }, { fetchFn: mockOnce({}), sleepBetweenMs: 0 }),
    ).rejects.toThrow(/depth out of range/);
  });
});

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
  it("real Kalshi shape: FixedPointDollars strings → cents [0–100]", async () => {
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
              price: {
                open_dollars: "0.5000",
                high_dollars: "0.5500",
                low_dollars: "0.4800",
                close_dollars: "0.5200",
              },
              volume_fp: "100",
              open_interest_fp: "500",
            },
            {
              end_period_ts: 1717203600,
              price: {
                open_dollars: "0.5200",
                high_dollars: "0.6000",
                low_dollars: "0.5100",
                close_dollars: "0.5800",
              },
              volume_fp: "200",
              open_interest_fp: "600",
            },
          ],
        }),
        sleepBetweenMs: 0,
      },
    );
    expect(result.rows.length).toBe(2);
    // cents = float(dollars_string) * 100 (binary roundoff acceptable).
    expect(result.rows[0]?.open).toBeCloseTo(50);
    expect(result.rows[0]?.close).toBeCloseTo(52);
    expect(result.rows[1]?.high).toBeCloseTo(60);
    expect(result.rows[0]?.volume).toBe(100);
    expect(result.rows[1]?.openInterest).toBe(600);
    expect(result.rows.every((r) => r.source === "kalshi")).toBe(true);
    expect(result.source).toBe("kalshi");
    expect(result.ticker).toBe(TICKER);
    expect(result.interval).toBe("1h");
  });

  it("legacy unsuffixed candle fields still parsed", async () => {
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
          ],
        }),
        sleepBetweenMs: 0,
      },
    );
    expect(result.rows[0]?.open).toBe(50);
    expect(result.rows[0]?.volume).toBe(100);
  });

  it("subpenny precision preserved (0.567 → 56.7)", async () => {
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
              price: {
                open_dollars: "0.5670",
                high_dollars: "0.5670",
                low_dollars: "0.5670",
                close_dollars: "0.5670",
              },
              volume_fp: "0",
              open_interest_fp: "0",
            },
          ],
        }),
        sleepBetweenMs: 0,
      },
    );
    expect(result.rows[0]?.open).toBeCloseTo(56.7);
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
  it("real Kalshi shape: yes_price_dollars / count_fp / taker_outcome_side", async () => {
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
                yes_price_dollars: "0.5200",
                no_price_dollars: "0.4800",
                count_fp: "10",
                taker_outcome_side: "yes",
              },
            ],
            cursor: "P2",
          },
          {
            trades: [
              {
                trade_id: "t2",
                created_time: "2026-06-01T00:01:00Z",
                yes_price_dollars: "0.5300",
                no_price_dollars: "0.4700",
                count_fp: "5",
                taker_outcome_side: "no",
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
    // cents
    expect(result.rows[0]?.yesPrice).toBeCloseTo(52);
    expect(result.rows[1]?.noPrice).toBeCloseTo(47);
    expect(result.rows[0]?.count).toBe(10);
    expect(result.rows[1]?.count).toBe(5);
  });

  it("legacy unsuffixed trade fields still parsed", async () => {
    const result = await kalshiFills(
      TICKER,
      {},
      {
        fetchFn: mockOnce({
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
          cursor: "",
        }),
        sleepBetweenMs: 0,
      },
    );
    expect(result.rows[0]?.yesPrice).toBe(52);
    expect(result.rows[0]?.count).toBe(10);
    expect(result.rows[0]?.takerSide).toBe("yes");
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
  it("real Kalshi shape: orderbook_fp with yes_dollars / no_dollars", async () => {
    const result = await kalshiOrderbook(
      TICKER,
      {},
      {
        fetchFn: mockOnce({
          orderbook_fp: {
            yes_dollars: [
              ["0.5200", "100"],
              ["0.5100", "200"],
            ],
            no_dollars: [["0.4800", "150"]],
          },
        }),
        sleepBetweenMs: 0,
      },
    );
    expect(result.rows.length).toBe(3);
    expect(result.rows.filter((r) => r.side === "yes").length).toBe(2);
    // cents = float(dollars_string) * 100
    expect(result.rows[0]?.price).toBeCloseTo(52);
    expect(result.rows[0]?.size).toBe(100);
    expect(result.rows.every((r) => r.source === "kalshi")).toBe(true);
    expect(typeof result.snapshotAt).toBe("string");
  });

  it("legacy orderbook shape still parsed", async () => {
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
    expect(result.rows[0]?.price).toBe(52);
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

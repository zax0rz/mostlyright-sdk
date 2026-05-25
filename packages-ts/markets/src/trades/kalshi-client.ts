// Phase 9 — Kalshi public REST client (TS port of `_kalshi_client.py`).
//
// Read-only public Kalshi market data at
// https://api.elections.kalshi.com/trade-api/v2. No auth. 0.1s polite
// floor matches Kalshi's documented 10 req/sec ceiling. Reuses the
// fetchFn-injection pattern from packages-ts/markets/src/polymarket/
// client.ts so vitest can mock the HTTP layer.

import { fetchWithRetry } from "@mostlyrightmd/core";

export const KALSHI_API_BASE = "https://api.elections.kalshi.com/trade-api/v2";

const DEFAULT_SLEEP_BETWEEN_MS = 100; // 0.1 s
const DEFAULT_USER_AGENT = "mostlyright-ts/0.2.0 (+https://github.com/helloiamvu/tradewinds)";
const DEFAULT_TIMEOUT_MS = 30_000;
const DEFAULT_TRADES_PAGE_LIMIT = 1000;
const DEFAULT_MAX_TRADES_PAGES = 10_000;

export interface KalshiClientOptions {
  /** Politeness sleep between requests in ms. Default 100 (0.1 s). 0 to skip. */
  readonly sleepBetweenMs?: number;
  /** AbortSignal for the whole call. */
  readonly signal?: AbortSignal;
  /** Override fetch for tests. Defaults to global fetch. */
  readonly fetchFn?: typeof fetch;
  /** Per-attempt timeout. Default 30 000 ms. */
  readonly timeoutMs?: number;
}

async function sleep(ms: number, signal?: AbortSignal): Promise<void> {
  if (ms <= 0) return;
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => {
      cleanup();
      resolve();
    }, ms);
    const onAbort = () => {
      cleanup();
      reject(signal?.reason ?? new DOMException("Aborted", "AbortError"));
    };
    function cleanup() {
      clearTimeout(timer);
      signal?.removeEventListener("abort", onAbort);
    }
    if (signal) {
      if (signal.aborted) {
        cleanup();
        reject(signal.reason ?? new DOMException("Aborted", "AbortError"));
        return;
      }
      signal.addEventListener("abort", onAbort);
    }
  });
}

function buildUrl(
  path: string,
  params?: Record<string, string | number | boolean | null | undefined>,
): string {
  const url = new URL(`${KALSHI_API_BASE}${path}`);
  if (params) {
    for (const [key, value] of Object.entries(params)) {
      if (value === undefined || value === null) continue;
      url.searchParams.set(key, String(value));
    }
  }
  return url.toString();
}

async function getJson(
  path: string,
  params: Record<string, string | number | boolean | null | undefined> | undefined,
  opts: KalshiClientOptions,
): Promise<unknown> {
  const url = buildUrl(path, params);
  const headers: Record<string, string> = {
    "User-Agent": DEFAULT_USER_AGENT,
    Accept: "application/json",
  };
  const timeoutMs = opts.timeoutMs ?? DEFAULT_TIMEOUT_MS;
  let resp: Response;
  if (opts.fetchFn !== undefined) {
    // Tests inject `fetchFn` — bypass fetchWithRetry to keep mocks simple.
    // The injected fn is responsible for any retry / timeout behavior the
    // test wants to exercise.
    const init: RequestInit = { method: "GET", headers };
    if (opts.signal) init.signal = opts.signal;
    resp = await opts.fetchFn(url, init);
    if (!resp.ok) {
      throw new Error(`kalshi GET ${url} failed: HTTP ${resp.status}`);
    }
  } else {
    const retryOpts: Parameters<typeof fetchWithRetry>[1] = {
      method: "GET",
      headers,
      timeoutMs,
    };
    if (opts.signal) retryOpts.signal = opts.signal;
    resp = await fetchWithRetry(url, retryOpts);
  }
  const json = await resp.json();
  const sleepMs = opts.sleepBetweenMs ?? DEFAULT_SLEEP_BETWEEN_MS;
  if (sleepMs > 0) {
    await sleep(sleepMs, opts.signal);
  }
  return json;
}

// Real Kalshi API (post-March-2026 migration) returns FixedPointDollars
// strings (`_dollars` suffix) for prices and FixedPoint integer strings
// (`_fp` suffix) for sizes. Legacy unsuffixed fields accepted as a
// fallback for older endpoints / recorded fixtures. Field types are
// `string | number` to cover both wire shapes.
export interface RawKalshiCandle {
  readonly end_period_ts?: number;
  readonly price?: {
    // New wire format: dollar strings like "0.5600".
    readonly open_dollars?: string;
    readonly high_dollars?: string;
    readonly low_dollars?: string;
    readonly close_dollars?: string;
    // Legacy integer cents.
    readonly open?: number | string;
    readonly high?: number | string;
    readonly low?: number | string;
    readonly close?: number | string;
  };
  // New wire format: FixedPoint integer strings.
  readonly volume_fp?: string;
  readonly open_interest_fp?: string;
  // Legacy ints.
  readonly volume?: number | string;
  readonly open_interest?: number | string;
}

export interface RawKalshiTrade {
  readonly trade_id?: string;
  readonly created_time?: number | string;
  // New wire format: dollar strings + integer strings.
  readonly yes_price_dollars?: string;
  readonly no_price_dollars?: string;
  readonly count_fp?: string;
  readonly taker_outcome_side?: "yes" | "no";
  // Legacy unsuffixed.
  readonly yes_price?: number | string;
  readonly no_price?: number | string;
  readonly count?: number | string;
  readonly taker_side?: "yes" | "no";
}

// Orderbook level: real wire format is [price_dollar_string, count_fp_string];
// legacy is [price_int, count_int]. Dict form tolerated for backward compat
// with hand-authored fixtures.
type KalshiOrderLevel =
  | readonly [string | number, string | number]
  | {
      readonly price?: string | number;
      readonly size?: string | number;
      readonly contracts?: string | number;
    };

export interface RawKalshiOrderbook {
  // New wire format: orderbook_fp with yes_dollars / no_dollars arrays.
  readonly orderbook_fp?: {
    readonly yes_dollars?: ReadonlyArray<KalshiOrderLevel>;
    readonly no_dollars?: ReadonlyArray<KalshiOrderLevel>;
  };
  // Legacy: orderbook with yes / no arrays.
  readonly orderbook?: {
    readonly yes?: ReadonlyArray<KalshiOrderLevel>;
    readonly no?: ReadonlyArray<KalshiOrderLevel>;
  };
}

export async function fetchCandlesticks(
  ticker: string,
  args: {
    startTs: number;
    endTs: number;
    periodIntervalMinutes: number;
  },
  opts: KalshiClientOptions = {},
): Promise<ReadonlyArray<RawKalshiCandle>> {
  if (!ticker.includes("-")) {
    throw new Error(
      `kalshi ticker must contain '-' to derive series prefix; got ${JSON.stringify(ticker)}`,
    );
  }
  const series = ticker.split("-", 1)[0];
  const path = `/series/${series}/markets/${ticker}/candlesticks`;
  const payload = (await getJson(
    path,
    {
      start_ts: args.startTs,
      end_ts: args.endTs,
      period_interval: args.periodIntervalMinutes,
    },
    opts,
  )) as { candlesticks?: ReadonlyArray<RawKalshiCandle> } | null;
  return payload?.candlesticks ?? [];
}

export interface FetchTradesArgs {
  readonly minTs?: number;
  readonly maxTs?: number;
  readonly limit?: number;
  readonly maxPages?: number;
}

export async function fetchTrades(
  ticker: string,
  args: FetchTradesArgs = {},
  opts: KalshiClientOptions = {},
): Promise<ReadonlyArray<RawKalshiTrade>> {
  const limit = args.limit ?? DEFAULT_TRADES_PAGE_LIMIT;
  const maxPages = args.maxPages ?? DEFAULT_MAX_TRADES_PAGES;
  const out: RawKalshiTrade[] = [];
  let cursor: string | undefined;
  let pages = 0;
  while (true) {
    const params: Record<string, string | number | boolean | null | undefined> = {
      ticker,
      limit,
    };
    if (args.minTs !== undefined) params.min_ts = args.minTs;
    if (args.maxTs !== undefined) params.max_ts = args.maxTs;
    if (cursor) params.cursor = cursor;
    const payload = (await getJson("/markets/trades", params, opts)) as {
      trades?: ReadonlyArray<RawKalshiTrade>;
      cursor?: string;
    } | null;
    const trades = payload?.trades ?? [];
    if (trades.length > 0) out.push(...trades);
    cursor = payload?.cursor && payload.cursor.length > 0 ? payload.cursor : undefined;
    pages += 1;
    if (!cursor || trades.length === 0) break;
    if (pages >= maxPages) {
      throw new Error(
        `kalshi fetchTrades(${ticker}) exceeded maxPages=${maxPages}; narrow the window or raise the cap`,
      );
    }
  }
  return out;
}

export async function fetchOrderbook(
  ticker: string,
  args: { depth?: number } = {},
  opts: KalshiClientOptions = {},
): Promise<RawKalshiOrderbook> {
  const depth = args.depth ?? 50;
  if (depth < 1 || depth > 1000) {
    throw new Error(`depth out of range [1, 1000]: ${depth}`);
  }
  const path = `/markets/${ticker}/orderbook`;
  const payload = (await getJson(path, { depth }, opts)) as RawKalshiOrderbook | null;
  if (!payload || typeof payload !== "object") {
    throw new Error(`kalshi orderbook for ${ticker}: bad payload`);
  }
  return payload;
}

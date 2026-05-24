// Phase 9 — Kalshi trades public surface (TRADES-01..03, TS port of
// packages/markets/src/tradewinds/markets/kalshi_trades.py).
//
// Row shapes mirror the Python DataFrames column-for-column. Every row
// carries `source: "kalshi"` so cross-frame joins preserve source
// identity (the v0.1.0 load-bearing invariant).

import {
  type KalshiClientOptions,
  type RawKalshiCandle,
  type RawKalshiOrderbook,
  type RawKalshiTrade,
  fetchCandlesticks,
  fetchOrderbook,
  fetchTrades,
} from "./kalshi-client.js";
import {
  KALSHI_INTERVALS,
  type KalshiCandleRow,
  type KalshiFillRow,
  type KalshiInterval,
  type KalshiOrderbookRow,
  type TradesResult,
} from "./types.js";

const SOURCE = "kalshi" as const;

const INTERVAL_TO_MINUTES: Record<KalshiInterval, number> = {
  "1m": 1,
  "1h": 60,
  "1d": 1440,
};

export interface KalshiCandlesArgs {
  readonly interval: KalshiInterval;
  readonly from: Date;
  readonly to: Date;
}

export interface KalshiFillsArgs {
  readonly since?: Date;
  readonly until?: Date;
  readonly maxPages?: number;
}

export interface KalshiOrderbookArgs {
  readonly depth?: number;
}

function validateDate(d: Date, name: string): void {
  if (!(d instanceof Date) || Number.isNaN(d.getTime())) {
    throw new TypeError(`${name} must be a valid Date; got ${String(d)}`);
  }
}

function toIsoOrNull(epochSeconds: unknown): string | null {
  if (typeof epochSeconds === "number" && Number.isFinite(epochSeconds)) {
    return new Date(epochSeconds * 1000).toISOString();
  }
  return null;
}

function stringTsToIso(value: unknown): string | null {
  if (typeof value === "number" && Number.isFinite(value)) {
    return toIsoOrNull(value);
  }
  if (typeof value === "string") {
    const parsed = Date.parse(value);
    if (!Number.isNaN(parsed)) {
      return new Date(parsed).toISOString();
    }
  }
  return null;
}

function maybeNumber(v: unknown): number | null {
  if (v === null || v === undefined) return null;
  const n = typeof v === "string" ? Number(v) : (v as number);
  return typeof n === "number" && Number.isFinite(n) ? n : null;
}

function maybeInt(v: unknown): number | null {
  const n = maybeNumber(v);
  if (n === null) return null;
  return Math.trunc(n);
}

export async function kalshiCandles(
  ticker: string,
  args: KalshiCandlesArgs,
  opts: KalshiClientOptions = {},
): Promise<TradesResult<KalshiCandleRow>> {
  validateDate(args.from, "from");
  validateDate(args.to, "to");
  if (args.from.getTime() >= args.to.getTime()) {
    throw new RangeError(
      `from (${args.from.toISOString()}) must be < to (${args.to.toISOString()})`,
    );
  }
  if (!KALSHI_INTERVALS.includes(args.interval)) {
    throw new RangeError(
      `interval must be one of ${JSON.stringify([...KALSHI_INTERVALS])}; got ${JSON.stringify(args.interval)}`,
    );
  }
  const raw = await fetchCandlesticks(
    ticker,
    {
      startTs: Math.trunc(args.from.getTime() / 1000),
      endTs: Math.trunc(args.to.getTime() / 1000),
      periodIntervalMinutes: INTERVAL_TO_MINUTES[args.interval],
    },
    opts,
  );
  const rows: KalshiCandleRow[] = raw.map((c: RawKalshiCandle) => ({
    ts: toIsoOrNull(c.end_period_ts),
    open: maybeNumber(c.price?.open),
    high: maybeNumber(c.price?.high),
    low: maybeNumber(c.price?.low),
    close: maybeNumber(c.price?.close),
    volume: maybeInt(c.volume),
    openInterest: maybeInt(c.open_interest),
    source: SOURCE,
  }));
  return Object.freeze({
    rows: Object.freeze(rows),
    source: SOURCE,
    retrievedAt: new Date().toISOString(),
    ticker,
    interval: args.interval,
  });
}

export async function kalshiFills(
  ticker: string,
  args: KalshiFillsArgs = {},
  opts: KalshiClientOptions = {},
): Promise<TradesResult<KalshiFillRow>> {
  if (args.since !== undefined) validateDate(args.since, "since");
  if (args.until !== undefined) validateDate(args.until, "until");
  if (
    args.since !== undefined &&
    args.until !== undefined &&
    args.since.getTime() >= args.until.getTime()
  ) {
    throw new RangeError(
      `since (${args.since.toISOString()}) must be < until (${args.until.toISOString()})`,
    );
  }
  // exactOptionalPropertyTypes: omit undefined keys rather than passing them.
  const fetchArgs: { minTs?: number; maxTs?: number; maxPages?: number } = {};
  if (args.since) fetchArgs.minTs = Math.trunc(args.since.getTime() / 1000);
  if (args.until) fetchArgs.maxTs = Math.trunc(args.until.getTime() / 1000);
  if (args.maxPages !== undefined) fetchArgs.maxPages = args.maxPages;
  const raw = await fetchTrades(ticker, fetchArgs, opts);
  const rows: KalshiFillRow[] = raw.map((t: RawKalshiTrade) => ({
    tradeId: t.trade_id ?? null,
    ts: stringTsToIso(t.created_time),
    yesPrice: maybeNumber(t.yes_price),
    noPrice: maybeNumber(t.no_price),
    count: maybeInt(t.count),
    takerSide: t.taker_side === "yes" || t.taker_side === "no" ? t.taker_side : null,
    source: SOURCE,
  }));
  return Object.freeze({
    rows: Object.freeze(rows),
    source: SOURCE,
    retrievedAt: new Date().toISOString(),
    ticker,
  });
}

export async function kalshiOrderbook(
  ticker: string,
  args: KalshiOrderbookArgs = {},
  opts: KalshiClientOptions = {},
): Promise<TradesResult<KalshiOrderbookRow>> {
  const payload: RawKalshiOrderbook = await fetchOrderbook(ticker, args, opts);
  const book = payload.orderbook ?? {};
  const rows: KalshiOrderbookRow[] = [];
  for (const side of ["yes", "no"] as const) {
    const levels = book[side] ?? [];
    for (const level of levels) {
      if (Array.isArray(level) && level.length >= 2) {
        rows.push({
          side,
          price: maybeNumber(level[0]),
          size: maybeInt(level[1]),
          source: SOURCE,
        });
      } else if (level !== null && typeof level === "object") {
        // Dict form — access via Record<string, unknown> to satisfy TS strict
        // narrowing without losing the runtime tolerance for `contracts` alias.
        const obj = level as Record<string, unknown>;
        rows.push({
          side,
          price: maybeNumber(obj.price),
          size: maybeInt(obj.size ?? obj.contracts),
          source: SOURCE,
        });
      }
    }
  }
  const snapshotAt = new Date().toISOString();
  return Object.freeze({
    rows: Object.freeze(rows),
    source: SOURCE,
    retrievedAt: snapshotAt,
    snapshotAt,
    ticker,
  });
}

// Phase 9 — Kalshi trades public surface (TRADES-01..03, TS port of
// packages/markets/src/mostlyright/markets/kalshi_trades.py).
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

/**
 * Convert a Kalshi FixedPointDollars string (e.g. ``"0.5600"``) to cents
 * [0.0–100.0]. Subpenny precision is preserved (`"0.567"` → 56.7).
 * Canonical conversion per `packages/core/.../specs/candle.json`:
 * `cents = float(api_string) * 100`. Returns null on unparseable input.
 */
function dollarsToCents(v: unknown): number | null {
  const n = maybeNumber(v);
  if (n === null) return null;
  return n * 100;
}

/**
 * Parse a Kalshi FixedPoint integer string (e.g. ``"100"`` or ``"100.00"``)
 * to int. Tolerates trailing-decimal forms; returns null on unparseable.
 */
function fpStringToInt(v: unknown): number | null {
  const n = maybeNumber(v);
  if (n === null) return null;
  return Math.trunc(n);
}

/**
 * Read either `{base}_dollars` (new wire format, FixedPointDollars string)
 * or legacy unsuffixed `{base}` (integer cents) from a Kalshi payload
 * field and return a value in cents [0.0–100.0].
 */
function pickPrice(d: Record<string, unknown> | undefined, base: string): number | null {
  if (d === undefined) return null;
  const dollarsKey = `${base}_dollars`;
  if (Object.prototype.hasOwnProperty.call(d, dollarsKey)) {
    return dollarsToCents(d[dollarsKey]);
  }
  return maybeNumber(d[base]);
}

/**
 * Read either `{base}_fp` (new wire format, FixedPoint integer string) or
 * legacy unsuffixed `{base}` (integer) from a Kalshi payload field.
 */
function pickFp(d: Record<string, unknown> | undefined, base: string): number | null {
  if (d === undefined) return null;
  const fpKey = `${base}_fp`;
  if (Object.prototype.hasOwnProperty.call(d, fpKey)) {
    return fpStringToInt(d[fpKey]);
  }
  return maybeInt(d[base]);
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
  // Kalshi API (post-March-2026): FixedPointDollars strings for prices,
  // FixedPoint integer strings for sizes (`_fp` suffix). Legacy unsuffixed
  // names accepted as a fallback. pickPrice converts dollars → cents
  // [0.0, 100.0] per canonical specs/candle.json.
  const rows: KalshiCandleRow[] = raw.map((c: RawKalshiCandle) => {
    const priceObj = c.price as Record<string, unknown> | undefined;
    const top = c as unknown as Record<string, unknown>;
    return {
      ts: toIsoOrNull(c.end_period_ts),
      open: pickPrice(priceObj, "open"),
      high: pickPrice(priceObj, "high"),
      low: pickPrice(priceObj, "low"),
      close: pickPrice(priceObj, "close"),
      volume: pickFp(top, "volume"),
      openInterest: pickFp(top, "open_interest"),
      source: SOURCE,
    };
  });
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
  // Real Kalshi /markets/trades returns yes_price_dollars / no_price_dollars
  // / count_fp / taker_outcome_side. Legacy unsuffixed accepted as fallback.
  const rows: KalshiFillRow[] = raw.map((t: RawKalshiTrade) => {
    const obj = t as unknown as Record<string, unknown>;
    const takerRaw = (t.taker_outcome_side ?? t.taker_side) as unknown;
    const takerSide: "yes" | "no" | null =
      takerRaw === "yes" || takerRaw === "no" ? takerRaw : null;
    return {
      tradeId: t.trade_id ?? null,
      ts: stringTsToIso(t.created_time),
      yesPrice: pickPrice(obj, "yes_price"),
      noPrice: pickPrice(obj, "no_price"),
      count: pickFp(obj, "count"),
      takerSide,
      source: SOURCE,
    };
  });
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
  // Real Kalshi orderbook (post-March-2026): `orderbook_fp` with
  // `yes_dollars` / `no_dollars` arrays of [price_dollar_string,
  // count_fp_string]. Legacy `orderbook.yes` / `.no` accepted as fallback.
  let useFp: boolean;
  let levelsBySide: { yes: ReadonlyArray<unknown>; no: ReadonlyArray<unknown> };
  if (payload.orderbook_fp !== undefined) {
    useFp = true;
    levelsBySide = {
      yes: payload.orderbook_fp.yes_dollars ?? [],
      no: payload.orderbook_fp.no_dollars ?? [],
    };
  } else {
    useFp = false;
    levelsBySide = {
      yes: payload.orderbook?.yes ?? [],
      no: payload.orderbook?.no ?? [],
    };
  }
  const rows: KalshiOrderbookRow[] = [];
  for (const side of ["yes", "no"] as const) {
    const levels = levelsBySide[side];
    for (const level of levels) {
      if (Array.isArray(level) && level.length >= 2) {
        rows.push({
          side,
          price: useFp ? dollarsToCents(level[0]) : maybeNumber(level[0]),
          size: useFp ? fpStringToInt(level[1]) : maybeInt(level[1]),
          source: SOURCE,
        });
      } else if (level !== null && typeof level === "object") {
        // Dict form — access via Record<string, unknown> to satisfy TS strict
        // narrowing without losing the runtime tolerance for `contracts` alias.
        const obj = level as Record<string, unknown>;
        rows.push({
          side,
          price: useFp ? dollarsToCents(obj.price) : maybeNumber(obj.price),
          size: useFp
            ? fpStringToInt(obj.size ?? obj.contracts)
            : maybeInt(obj.size ?? obj.contracts),
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

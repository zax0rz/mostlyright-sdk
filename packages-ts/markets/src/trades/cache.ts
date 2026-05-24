// Phase 9 — trades cache adapter (TRADES-06, TS counterpart to
// packages/markets/src/tradewinds/markets/_trades_cache.py).
//
// Thin wrapper over the existing `@tradewinds/core` CacheStore interface
// (MemoryStore / IndexedDBStore / FsStore). Key shape mirrors the Python
// path layout: trades/{issuer}/{ticker}/{YYYY-MM}.
//
// Volatile-window rules: current UTC month and future months are not
// cacheable (write no-op + read miss) — trades may still arrive for the
// active month.

import type { CacheStore } from "@tradewinds/core/internal/cache";

const ISSUER_RE = /^[a-z][a-z0-9._-]{0,31}$/;
const TICKER_RE = /^[A-Za-z0-9._-]{1,128}$/;

export interface TradesCacheKey {
  readonly issuer: string;
  readonly ticker: string;
  readonly year: number;
  readonly month: number;
}

/** Build the canonical key string for a (issuer, ticker, year, month). */
export function tradesCacheKey(args: TradesCacheKey): string {
  if (typeof args.issuer !== "string" || !ISSUER_RE.test(args.issuer)) {
    throw new RangeError(
      `invalid issuer for cache key: ${JSON.stringify(args.issuer)}; must match ${ISSUER_RE}`,
    );
  }
  if (typeof args.ticker !== "string" || !TICKER_RE.test(args.ticker)) {
    throw new RangeError(
      `invalid ticker for cache key: ${JSON.stringify(args.ticker)}; must match ${TICKER_RE}`,
    );
  }
  if (!Number.isInteger(args.year) || args.year < 2000 || args.year > 2100) {
    throw new RangeError(`year out of range [2000, 2100]: ${args.year}`);
  }
  if (!Number.isInteger(args.month) || args.month < 1 || args.month > 12) {
    throw new RangeError(`month out of range [1, 12]: ${args.month}`);
  }
  const mm = args.month.toString().padStart(2, "0");
  return `trades/${args.issuer}/${args.ticker}/${args.year}-${mm}`;
}

export function isCurrentUtcMonth(year: number, month: number, now: Date = new Date()): boolean {
  return year === now.getUTCFullYear() && month === now.getUTCMonth() + 1;
}

export function isFutureUtcMonth(year: number, month: number, now: Date = new Date()): boolean {
  const yNow = now.getUTCFullYear();
  const mNow = now.getUTCMonth() + 1;
  return year > yNow || (year === yNow && month > mNow);
}

export interface TradesCacheReadOpts {
  readonly now?: Date;
}

export interface TradesCacheWriteOpts {
  readonly now?: Date;
}

/** Read cached trades rows. Returns `null` on miss / current-or-future month. */
export async function readTradesCache<Row>(
  cache: CacheStore,
  args: TradesCacheKey,
  opts: TradesCacheReadOpts = {},
): Promise<ReadonlyArray<Row> | null> {
  if (
    isCurrentUtcMonth(args.year, args.month, opts.now) ||
    isFutureUtcMonth(args.year, args.month, opts.now)
  ) {
    return null;
  }
  const key = tradesCacheKey(args);
  const value = await cache.get<ReadonlyArray<Row>>(key);
  return value ?? null;
}

/**
 * Write rows to the cache. Returns `false` (no-op) when:
 *   - the (year, month) is the current UTC month (still mutable),
 *   - the (year, month) is in the future, OR
 *   - rows is empty.
 */
export async function writeTradesCache<Row>(
  cache: CacheStore,
  args: TradesCacheKey,
  rows: ReadonlyArray<Row>,
  opts: TradesCacheWriteOpts = {},
): Promise<boolean> {
  if (
    isCurrentUtcMonth(args.year, args.month, opts.now) ||
    isFutureUtcMonth(args.year, args.month, opts.now)
  ) {
    return false;
  }
  if (rows.length === 0) return false;
  const key = tradesCacheKey(args);
  await cache.set(key, rows);
  return true;
}

/** Delete cached entry; returns true when a value existed before. */
export async function invalidateTradesCache(
  cache: CacheStore,
  args: TradesCacheKey,
): Promise<boolean> {
  const key = tradesCacheKey(args);
  const before = await cache.get(key);
  if (before === null) return false;
  await cache.delete(key);
  return true;
}

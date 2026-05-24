// Phase 9 — shared row + result types for the trades surface.
//
// Mirrors the Python DataFrames in `tradewinds.markets.{kalshi_trades,
// polymarket_trades}` row-for-row. The TS surface returns plain JS
// objects (frozen `readonly` arrays) since `@tradewinds/markets` does
// not depend on a DataFrame library.

/** Source string carried per row — load-bearing invariant for cross-frame joins. */
export type TradesSource = "kalshi" | "polymarket.gamma";

export interface KalshiCandleRow {
  /** Bucket-end timestamp as ISO 8601 UTC string. */
  readonly ts: string | null;
  readonly open: number | null;
  readonly high: number | null;
  readonly low: number | null;
  readonly close: number | null;
  readonly volume: number | null;
  readonly openInterest: number | null;
  readonly source: "kalshi";
}

export interface KalshiFillRow {
  readonly tradeId: string | null;
  readonly ts: string | null;
  readonly yesPrice: number | null;
  readonly noPrice: number | null;
  readonly count: number | null;
  readonly takerSide: "yes" | "no" | null;
  readonly source: "kalshi";
}

export interface KalshiOrderbookRow {
  readonly side: "yes" | "no";
  readonly price: number | null;
  readonly size: number | null;
  readonly source: "kalshi";
}

export interface PolymarketHistoryRow {
  readonly ts: string | null;
  readonly price: number | null;
  readonly volume: number | null;
  readonly source: "polymarket.gamma";
}

export interface PolymarketSnapshotRow {
  readonly marketId: string | null;
  readonly outcome: string;
  readonly lastPrice: number | null;
  readonly volume: number | null;
  readonly liquidity: number | null;
  readonly source: "polymarket.gamma";
}

/** Envelope returned by every trades function — rows + metadata. */
export interface TradesResult<Row> {
  readonly rows: ReadonlyArray<Row>;
  readonly source: TradesSource;
  readonly retrievedAt: string; // ISO UTC
  /** Snapshot-style results may carry a snapshotAt distinct from retrievedAt. */
  readonly snapshotAt?: string;
  /** Echo of the input ticker / market-id for downstream attribution. */
  readonly ticker?: string;
  readonly marketId?: string;
  readonly eventId?: string;
  readonly interval?: string;
  readonly fidelityMinutes?: number;
}

/** Supported candle intervals — exact union mirrors Python `INTERVALS`. */
export const KALSHI_INTERVALS = ["1m", "1h", "1d"] as const;
export type KalshiInterval = (typeof KALSHI_INTERVALS)[number];

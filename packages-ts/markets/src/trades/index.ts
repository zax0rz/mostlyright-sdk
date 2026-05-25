// Phase 9 — barrel for @mostlyrightmd/markets/trades subpath.

export {
  KALSHI_API_BASE,
  fetchCandlesticks,
  fetchOrderbook,
  fetchTrades,
  type KalshiClientOptions,
  type RawKalshiCandle,
  type RawKalshiOrderbook,
  type RawKalshiTrade,
} from "./kalshi-client.js";

export {
  kalshiCandles,
  kalshiFills,
  kalshiOrderbook,
  type KalshiCandlesArgs,
  type KalshiFillsArgs,
  type KalshiOrderbookArgs,
} from "./kalshi.js";

export {
  polymarketHistory,
  polymarketSnapshot,
  type PolymarketClientOptions,
  type PolymarketHistoryArgs,
} from "./polymarket.js";

export {
  invalidateTradesCache,
  isCurrentUtcMonth,
  isFutureUtcMonth,
  readTradesCache,
  tradesCacheKey,
  writeTradesCache,
  type TradesCacheKey,
  type TradesCacheReadOpts,
  type TradesCacheWriteOpts,
} from "./cache.js";

export {
  KALSHI_INTERVALS,
  type KalshiCandleRow,
  type KalshiFillRow,
  type KalshiInterval,
  type KalshiOrderbookRow,
  type PolymarketHistoryRow,
  type PolymarketSnapshotRow,
  type TradesResult,
  type TradesSource,
} from "./types.js";

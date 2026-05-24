// Barrel for the Polymarket surface — exposed as @tradewinds/markets/polymarket.

export { fetchEventById, fetchEvents } from "./client.js";
export type { FetchEventsOptions, PolymarketEventRaw } from "./client.js";

export { extractResolutionSourceType, validateDescription } from "./description.js";

export {
  PayloadTooLargeError,
  PolymarketEventError,
  PolymarketSettlementError,
  TooEarlyToSettleError,
} from "./errors.js";

export { polymarketDiscover } from "./discover.js";
export type { PolymarketDiscoverOptions } from "./discover.js";

export {
  detectMarketMeasure,
  deriveCity,
  resolveStationForEvent,
  settlementDateFromSlug,
} from "./resolver.js";

export { polymarketSettle, polymarketSettleById } from "./settle.js";
export type { ObservationLoader, PolymarketSettleArgs } from "./settle.js";

export {
  DEFERRED_STATIONS,
  EVENT_ID_RE,
  MAX_DESCRIPTION_BYTES,
  NETLOC_TO_RESOLUTION_TYPE,
  POLYMARKET_RESOLUTION_SOURCE_TYPES,
  RESOLUTION_SOURCE_ALLOWLIST,
  SETTLE_DELAY_HOURS,
  SLUG_DATE_RE,
} from "./types.js";
export type {
  PolymarketDiscoveryRow,
  PolymarketResolutionSourceType,
  PolymarketSettleOptions,
  PolymarketSettlementResult,
  SettlementUnit,
} from "./types.js";

// Phase 11 — `@tradewinds/weather/live` public re-exports.
//
// Three surfaces:
//  - `stream()`     — AsyncGenerator yielding fresh observations on a polite-floor cadence
//  - `latest()`     — one-shot fetch (same path as one `stream()` tick)
//  - `sources`/`POLITE_FLOORS_S` — registry constants
//
// LiveStreamError + NoLiveDataError live on `@tradewinds/core` (already
// exported via the core exceptions barrel); re-export here for ergonomic
// `import { LiveStreamError } from "@tradewinds/weather/live"`.

export { LiveStreamError, NoLiveDataError } from "@tradewinds/core";

export { latest, type LatestOptions } from "./latest.js";
export {
  POLITE_FLOORS_S,
  SOURCE_IDENTITY_TAGS,
  SUPPORTED_SOURCES,
  isLiveSource,
  sourceTag,
  validatePollSeconds,
  validateSource,
  type LiveSource,
  type LiveSourceTag,
} from "./sources.js";
export { stream, type StreamOptions } from "./stream.js";
export type { LiveObservation } from "./types.js";

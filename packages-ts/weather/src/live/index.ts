// Phase 11 — internal `live/*` barrel.
//
// This file is the in-package barrel; the public entry point is the main
// `@tradewinds/weather` barrel (`src/index.ts`), which re-exports
// everything below. There is intentionally NO `@tradewinds/weather/live`
// subpath export in the published package today — adding one needs both
// a `package.json` `exports` map entry and a separate tsup entry, which
// is deferred to a v0.2.x ergonomics pass.
//
// Three surfaces:
//  - `stream()`     — AsyncGenerator yielding fresh observations on a polite-floor cadence
//  - `latest()`     — one-shot fetch (same path as one `stream()` tick)
//  - `sources`/`POLITE_FLOORS_S` — registry constants
//
// LiveStreamError + NoLiveDataError live on `@tradewinds/core`
// (re-exported here so the weather barrel picks them up).

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

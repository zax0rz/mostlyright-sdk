// Phase 11 — `@mostlyright/weather/live` subpath barrel.
//
// This file is BOTH the in-package barrel AND the published subpath entry
// point — `package.json` declares `"./live"` in its `exports` map and
// `tsup.config.ts` emits `src/live/index.ts` as a separate dist bundle
// (`dist/live/index.{mjs,cjs,d.ts}`). The main `@mostlyright/weather`
// barrel re-exports the same surface, so both of these work:
//
//   import { stream } from "@mostlyright/weather/live"  // narrow subpath
//   import { stream } from "@mostlyright/weather"       // main barrel
//
// Three surfaces:
//  - `stream()`     — AsyncGenerator yielding fresh observations on a polite-floor cadence
//  - `latest()`     — one-shot fetch (same path as one `stream()` tick)
//  - `sources`/`POLITE_FLOORS_S` — registry constants
//
// LiveStreamError + NoLiveDataError live on `@mostlyright/core`
// (re-exported here so the weather barrel picks them up).

export { LiveStreamError, NoLiveDataError } from "@mostlyright/core";

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

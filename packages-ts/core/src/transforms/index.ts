// Barrel for @tradewinds/core/transforms — TS-W4 Plan 02.
//
// Pure functions porting Python `tradewinds.transforms` (lag/diff/diff2/
// rolling). Lives at the subpath, NOT the root barrel, to keep the
// @tradewinds/core main bundle under its 25 KB size-limit gate
// (TS-BUNDLE-01). Same pattern as temporal / formats / validator —
// see iter-4 H8 lesson in `packages-ts/core/src/index.ts`.
//
// Consumers import with:
//
//   import { lag, diff, diff2, rolling } from "@tradewinds/core/transforms";
//   import type { RollingFn } from "@tradewinds/core/transforms";
//
// Wave 3 (calendar features) and Wave 4 (cross-features: spread, wind_chill,
// heat_index, clip_outliers) APPEND to this barrel in subsequent commits.

export { lag } from "./lag.js";
export { diff, diff2 } from "./diff.js";
export { ROLLING_FNS, type RollingFn, rolling } from "./rolling.js";

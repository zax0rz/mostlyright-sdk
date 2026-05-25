// Barrel for @mostlyrightmd/core/transforms — TS-W4 Plan 02 + 03 + 04.
//
// Pure functions porting Python `mostlyright.transforms` (lag/diff/diff2/
// rolling/calendar_features/spread/wind_chill/heat_index) plus
// `mostlyright.preprocessing.clip_outliers`. Lives at the subpath, NOT the
// root barrel, to keep the @mostlyrightmd/core main bundle under its 25 KB
// size-limit gate (TS-BUNDLE-01). Same pattern as temporal / formats /
// validator — see iter-4 H8 lesson in `packages-ts/core/src/index.ts`.
//
// Consumers import with:
//
//   import {
//     lag, diff, diff2, rolling, calendarFeatures,
//     spread, windChill, heatIndex, clipOutliers, PHYSICS_BOUNDS,
//   } from "@mostlyrightmd/core/transforms";
//   import type { RollingFn, ClipOutliersOptions } from "@mostlyrightmd/core/transforms";

export { lag } from "./lag.js";
export { diff, diff2 } from "./diff.js";
export { ROLLING_FNS, type RollingFn, rolling } from "./rolling.js";
export { calendarFeatures } from "./calendar.js";
export { spread } from "./cross.js";
export { windChill, heatIndex } from "./weather.js";
export { clipOutliers, PHYSICS_BOUNDS, type ClipOutliersOptions } from "./clip.js";

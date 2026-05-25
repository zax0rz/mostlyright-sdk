// Barrel for @mostlyright/core/discovery — TS-W6.
//
// Five waves shipped at this subpath:
//
//   Wave 1: availability(station, cache) reading from CacheStore.
//   Wave 2: internationalDailyExtremes(rows, opts) UTC→local rollup.
//   Wave 3: buildSnapshot(...) + DataSnapshot.toDict / .toToon.
//   Wave 4: dataVersionFromComponents / dataVersionForResearch via Web Crypto.
//   Wave 5: describe(schemaId) + featureCatalog() + climateGaps stub.
//
// Discovery lives at the subpath (NOT the root barrel) to keep the
// @mostlyright/core main bundle under its 25 KB size-limit gate
// (TS-BUNDLE-01). Same pattern as transforms / temporal / formats / qc /
// validator — see iter-4 H8 lesson in `packages-ts/core/src/index.ts`.
//
// Consumers import with:
//
//   import {
//     availability,
//     internationalDailyExtremes,
//     buildSnapshot,
//     dataVersionFromComponents,
//     dataVersionForResearch,
//     describe,
//     featureCatalog,
//     climateGaps,
//   } from "@mostlyright/core/discovery";
//   import type {
//     AvailabilityResult,
//     KeyEnumerableStore,
//     DailyExtreme,
//     InternationalDailyExtremesOptions,
//     InternationalRow,
//     DataSnapshot,
//     BuildSnapshotOptions,
//     DataVersion,
//     DataVersionComponents,
//   } from "@mostlyright/core/discovery";

export { availability } from "./availability.js";
export type {
  AvailabilityOptions,
  AvailabilityResult,
  KeyEnumerableStore,
} from "./availability.js";

export { internationalDailyExtremes } from "./international.js";
export type {
  DailyExtreme,
  InternationalDailyExtremesOptions,
  InternationalRow,
} from "./international.js";

export { buildSnapshot } from "./snapshot.js";
export type { BuildSnapshotOptions, DataSnapshot } from "./snapshot.js";

export {
  dataVersionForResearch,
  dataVersionFromComponents,
} from "./data-version.js";
export type { DataVersion, DataVersionComponents } from "./data-version.js";

export {
  ClimateGapsNotImplementedError,
  UnknownSchemaError,
  climateGaps,
  describe,
  featureCatalog,
  registerSchema,
} from "./describe.js";

// @mostlyright/core/internal/merge — multi-source dedup policies.
//
// Subpath export consumed by:
//  - @mostlyright/meta/research orchestrator (calls both at the join step).
//  - @mostlyright/weather barrel (re-exports mergeClimate for backward compat).
//
// Same import discipline as `@mostlyright/core/internal/{bounds,convert}` —
// deep subpath keeps the main `@mostlyright/core` browser bundle thin.

export { SOURCE_PRIORITY, mergeObservations, type ObservationKey } from "./observations.js";
export { mergeClimate, type ClimateKey } from "./climate.js";

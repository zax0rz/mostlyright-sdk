// @mostlyrightmd/core/internal/merge — multi-source dedup policies.
//
// Subpath export consumed by:
//  - @mostlyrightmd/meta/research orchestrator (calls both at the join step).
//  - @mostlyrightmd/weather barrel (re-exports mergeClimate for backward compat).
//
// Same import discipline as `@mostlyrightmd/core/internal/{bounds,convert}` —
// deep subpath keeps the main `@mostlyrightmd/core` browser bundle thin.

export { SOURCE_PRIORITY, mergeObservations, type ObservationKey } from "./observations.js";
export { mergeClimate, type ClimateKey } from "./climate.js";

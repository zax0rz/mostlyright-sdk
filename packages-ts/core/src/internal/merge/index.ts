// @tradewinds/core/internal/merge — multi-source dedup policies.
//
// Subpath export consumed by:
//  - @tradewinds/meta/research orchestrator (calls both at the join step).
//  - @tradewinds/weather barrel (re-exports mergeClimate for backward compat).
//
// Same import discipline as `@tradewinds/core/internal/{bounds,convert}` —
// deep subpath keeps the main `@tradewinds/core` browser bundle thin.

export { SOURCE_PRIORITY, mergeObservations, type ObservationKey } from "./observations.js";
export { mergeClimate, type ClimateKey } from "./climate.js";

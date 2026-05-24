// Barrel for @tradewinds/core/formats — TS-W3 Plan 07.
//
// Three serializer pairs ported from Python:
//   - jsonDumps / jsonLoads (records form + empty-frame envelope)
//   - csvDumps / csvLoads   (hand-rolled minimal RFC-4180, no papaparse)
//   - toonDumps / toonLoads (TOON v3.0 tabular block, byte-equivalent
//     to Python `encode_tabular` on shared fixture).
//
// Out of scope per TS-FORMAT-01:
//   - parquet → deferred to v0.2 via parquet-wasm (no stub).
//   - dataframe → TS has no DataFrames (no stub).

export { jsonDumps, jsonLoads } from "./json.js";
export { csvDumps, csvLoads } from "./csv.js";
export { toonDumps, toonLoads } from "./toon.js";

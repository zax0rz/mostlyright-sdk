// Barrel for @tradewinds/core/qc — TS-W4 Plan 05.
//
// Public API: QCEngine, QCRule, ALPHA_RULES, QC_ALPHA_RULES + the 5
// per-rule evaluator functions (exposed for unit-testing + downstream
// composability).
//
// Bit positions + rule IDs come from the codegen-shipped QC_ALPHA_RULES
// table at src/data/generated/qc-alpha-rules.ts; this barrel exposes
// them so downstream consumers can introspect the rule registry without
// reaching into internal paths.
//
// Lives at the subpath (NOT root barrel) to keep the @tradewinds/core
// main bundle under its 25 KB size-limit gate (TS-BUNDLE-01); same
// pattern as temporal / formats / transforms / validator.

export { QCEngine } from "./engine.js";
export {
  ALPHA_RULES,
  QC_ALPHA_RULES,
  evalDewpointExceedsTemp,
  evalSlpOutOfRange,
  evalTempOutOfRange,
  evalWindDirOutOfRange,
  evalWindSpeedNegative,
  type QCRule,
} from "./rules.js";

// TS-W4 Plan 06 — crosscheckIemGhcnh: IEM/GHCNh disagreement detection.
// Inner-joins by (station, eventTime); emits rows where
// |tempCIem - tempCGhcnh| > tolC (default 2.0 °C; STRICT `>`).
// Mirrors Python `tradewinds.qc.crosscheck_iem_ghcnh` at qc.py:191-228.
export {
  crosscheckIemGhcnh,
  type CrosscheckDisagreement,
  type CrosscheckOptions,
} from "./crosscheck.js";

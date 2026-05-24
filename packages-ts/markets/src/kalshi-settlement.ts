// TS-W5 Wave 5 — kalshiSettlementFor higher-level helper.
//
// Dispatch by Kalshi contract-id prefix (KHIGH* vs KLOW*) to the right
// resolver. Returns the same shape both NHIGH and NLOW resolvers use so
// downstream consumers don't need to know about the city-suffix split.

import { type NHighResolution, kalshiNhighResolve } from "./resolvers/kalshi-nhigh.js";
import { ContractIdError } from "./resolvers/kalshi-nhigh.js";
import { type NLowResolution, kalshiNlowResolve } from "./resolvers/kalshi-nlow.js";

export type KalshiSettlement = NHighResolution | NLowResolution;

/**
 * Resolve a Kalshi NHIGH or NLOW contract id to its settlement metadata.
 *
 * `KHIGH*` prefixes dispatch to the NHIGH resolver; `KLOW*` prefixes
 * dispatch to NLOW. Anything else raises `ContractIdError`.
 *
 * @example
 *   kalshiSettlementFor("KHIGHNYC", "2025-01-06")
 *   // → { settlementSource: "cli.archive", settlementStation: "KNYC",
 *   //     cityTicker: "NYC", contractDate: "2025-01-06" }
 */
export function kalshiSettlementFor(contractId: string, date: string): KalshiSettlement {
  if (typeof contractId !== "string" || contractId.length === 0) {
    throw new ContractIdError("contractId must be a non-empty string");
  }
  const upper = contractId.toUpperCase();
  if (upper.startsWith("KHIGH")) return kalshiNhighResolve(upper, date);
  if (upper.startsWith("KLOW")) return kalshiNlowResolve(upper, date);
  throw new ContractIdError(
    `contractId ${JSON.stringify(contractId)} does not start with KHIGH or KLOW`,
  );
}

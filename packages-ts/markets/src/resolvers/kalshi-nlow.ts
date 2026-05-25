// Kalshi NLOW (daily LOW temperature) contract resolver.
//
// Mirror of kalshi-nhigh — same station whitelist + same source
// (cli.archive); only the metric differs. NLOW markets resolve against
// the NWS CLI `min_temp_f` value for a specific station on a specific
// date.
//
// Ported byte-faithful from packages/markets/src/mostlyright/markets/catalog/kalshi_nlow.py.

import { KALSHI_SETTLEMENT_STATIONS } from "../data/generated/kalshi-stations.js";
import { ContractIdError } from "./kalshi-nhigh.js";

export interface NLowResolution {
  readonly settlementSource: "cli.archive";
  readonly settlementStation: string; // 4-letter ICAO
  readonly cityTicker: string;
  readonly contractDate: string; // YYYY-MM-DD
}

/**
 * Coerce a Date or YYYY-MM-DD string into an ISO date-only string.
 *
 * Rejects Date instances whose UTC hours/minutes/seconds/ms are non-zero —
 * those would silently corrupt downstream settlement-date matching.
 *
 * Mirrors the Python `isinstance(settlement_date, datetime)` guard.
 *
 * Note: duplicated here (rather than imported) so kalshi-nlow stays a
 * standalone file matching the Python module split. The two functions
 * are byte-identical by design.
 */
function coerceContractDate(value: Date | string): string {
  if (typeof value === "string") {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) {
      throw new ContractIdError(
        `settlementDate string must be YYYY-MM-DD; got ${JSON.stringify(value)}`,
      );
    }
    const parsed = new Date(`${value}T00:00:00Z`);
    if (Number.isNaN(parsed.getTime())) {
      throw new ContractIdError(
        `settlementDate string is not a valid calendar date; got ${JSON.stringify(value)}`,
      );
    }
    const iso = parsed.toISOString().slice(0, 10);
    if (iso !== value) {
      throw new ContractIdError(
        `settlementDate string is not a valid calendar date; got ${JSON.stringify(value)}`,
      );
    }
    return value;
  }
  if (value instanceof Date) {
    if (Number.isNaN(value.getTime())) {
      throw new ContractIdError("settlementDate is an invalid Date instance");
    }
    if (
      value.getUTCHours() !== 0 ||
      value.getUTCMinutes() !== 0 ||
      value.getUTCSeconds() !== 0 ||
      value.getUTCMilliseconds() !== 0
    ) {
      throw new ContractIdError(
        `settlementDate must be a UTC date-only Date (H/M/S/ms = 0); got ${value.toISOString()}. Use new Date('YYYY-MM-DDT00:00:00Z') or pass a 'YYYY-MM-DD' string.`,
      );
    }
    return value.toISOString().slice(0, 10);
  }
  throw new ContractIdError("settlementDate must be a Date instance or YYYY-MM-DD string");
}

/**
 * Resolve a Kalshi NLOW contract to its settlement source + station.
 *
 * The contract id format is `KLOW<CITY>` (case-insensitive), where
 * `<CITY>` is a city ticker present in
 * {@link KALSHI_SETTLEMENT_STATIONS}.
 *
 * @param contractId Kalshi market identifier. Case-insensitive.
 * @param settlementDate Calendar date the market settles for. Either a
 *   UTC date-only `Date` (H/M/S/ms == 0) or a `YYYY-MM-DD` string.
 * @returns A frozen {@link NLowResolution}.
 * @throws {ContractIdError} The contract id doesn't follow
 *   `KLOW<CITY>`, the city is unknown, or the settlement date is
 *   invalid.
 */
export function kalshiNlowResolve(
  contractId: string,
  settlementDate: Date | string,
): NLowResolution {
  if (typeof contractId !== "string") {
    throw new ContractIdError(`contractId must be a string; got ${typeof contractId}`);
  }

  const contractDate = coerceContractDate(settlementDate);

  const cid = contractId.toUpperCase();
  if (!cid.startsWith("KLOW") || cid.length <= 4) {
    throw new ContractIdError(
      `NLOW contractId must follow 'KLOW<CITY>' format; got ${JSON.stringify(contractId)}`,
    );
  }
  const cityTicker = cid.slice(4);
  const station = KALSHI_SETTLEMENT_STATIONS[cityTicker];
  if (station === undefined) {
    const known = Object.keys(KALSHI_SETTLEMENT_STATIONS).sort();
    throw new ContractIdError(
      `unknown city ${JSON.stringify(cityTicker)} (known: ${known.join(", ")})`,
    );
  }

  return Object.freeze({
    settlementSource: "cli.archive" as const,
    settlementStation: station.station,
    cityTicker,
    contractDate,
  });
}

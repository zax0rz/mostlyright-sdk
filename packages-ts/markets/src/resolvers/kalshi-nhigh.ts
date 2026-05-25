// Kalshi NHIGH (daily HIGH temperature) contract resolver.
//
// NHIGH markets resolve against the NWS CLI `max_temp_f` value for a
// specific station on a specific date. `kalshiNhighResolve` is the
// deterministic mapping from a Kalshi market identifier to the
// (settlement_source, settlement_station) tuple downstream code uses
// to pull the right settlement row from the CLI catalog.
//
// Ported byte-faithful from packages/markets/src/mostlyright/markets/catalog/kalshi_nhigh.py.

import { KALSHI_SETTLEMENT_STATIONS } from "../data/generated/kalshi-stations.js";

export interface NHighResolution {
  readonly settlementSource: "cli.archive";
  readonly settlementStation: string; // 4-letter ICAO
  readonly cityTicker: string;
  readonly contractDate: string; // YYYY-MM-DD
}

/**
 * Custom error type for contract-id parsing / validation failures.
 *
 * Mirrors the Python `ValueError`/`TypeError` distinction: in TS we use a
 * named subclass so callers can `instanceof`-check rather than parse
 * error messages.
 */
export class ContractIdError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "ContractIdError";
  }
}

/**
 * Coerce a Date or YYYY-MM-DD string into an ISO date-only string.
 *
 * Rejects Date instances whose UTC hours/minutes/seconds/ms are non-zero —
 * those would silently corrupt downstream settlement-date matching
 * (date-equality is strict).
 *
 * Mirrors the Python `isinstance(settlement_date, datetime)` guard in
 * `kalshi_nhigh.resolve`.
 */
function coerceContractDate(value: Date | string): string {
  if (typeof value === "string") {
    // YYYY-MM-DD strict format check.
    if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) {
      throw new ContractIdError(
        `settlementDate string must be YYYY-MM-DD; got ${JSON.stringify(value)}`,
      );
    }
    // Validate it parses to a real calendar date.
    const parsed = new Date(`${value}T00:00:00Z`);
    if (Number.isNaN(parsed.getTime())) {
      throw new ContractIdError(
        `settlementDate string is not a valid calendar date; got ${JSON.stringify(value)}`,
      );
    }
    // Round-trip check — guards against e.g. "2025-02-30" silently
    // rolling forward.
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
    // Reject any Date with a non-zero UTC time component — mirrors
    // Python's `isinstance(settlement_date, datetime)` guard. A Date
    // carries a time component which would break downstream
    // date-equality matching.
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
 * Resolve a Kalshi NHIGH contract to its settlement source + station.
 *
 * The contract id format is `KHIGH<CITY>` (case-insensitive), where
 * `<CITY>` is a city ticker present in
 * {@link KALSHI_SETTLEMENT_STATIONS}.
 *
 * @param contractId Kalshi market identifier. Case-insensitive.
 * @param settlementDate Calendar date the market settles for. Either a
 *   UTC date-only `Date` (H/M/S/ms == 0) or a `YYYY-MM-DD` string.
 * @returns A frozen {@link NHighResolution}.
 * @throws {ContractIdError} The contract id doesn't follow
 *   `KHIGH<CITY>`, the city is unknown, or the settlement date is
 *   invalid.
 */
export function kalshiNhighResolve(
  contractId: string,
  settlementDate: Date | string,
): NHighResolution {
  if (typeof contractId !== "string") {
    throw new ContractIdError(`contractId must be a string; got ${typeof contractId}`);
  }

  const contractDate = coerceContractDate(settlementDate);

  const cid = contractId.toUpperCase();
  if (!cid.startsWith("KHIGH") || cid.length <= 5) {
    throw new ContractIdError(
      `NHIGH contractId must follow 'KHIGH<CITY>' format; got ${JSON.stringify(contractId)}`,
    );
  }
  const cityTicker = cid.slice(5);
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

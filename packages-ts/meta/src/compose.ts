// Phase 10 — composable research() dispatcher (TS port of
// packages/core/src/tradewinds/_compose.py).
//
// Translates the new selectors (`city`, `contract`, `contracts`) into
// resolution metadata + station lists. Pure logic, no I/O.

import {
  KALSHI_SETTLEMENT_STATIONS,
  type KalshiStation,
  POLYMARKET_CITY_STATIONS,
} from "@tradewinds/markets";
import { POLYMARKET_KNOWN_WRONG_STATIONS } from "@tradewinds/markets/polymarket";

/** The four mutually-exclusive selector names. */
export const SELECTOR_NAMES = ["station", "city", "contract", "contracts"] as const;
export type SelectorName = (typeof SELECTOR_NAMES)[number];

/**
 * Structured warning emitted when `stationOverride` deliberately
 * mismatches the contract's canonical settlement station. The output
 * row carries `settlementMismatch: true`.
 *
 * JS has no `warnings.warn()` analogue; callers receive these via the
 * `onWarning?` callback in ResearchOptions.
 */
export interface StationOverrideWarning {
  readonly kind: "StationOverrideWarning";
  readonly contractStation: string;
  readonly overrideStation: string;
  readonly message: string;
}

/** Selector kwargs accepted by research(). Exactly one MUST be provided. */
export interface SelectorArgs {
  readonly station?: string;
  readonly city?: string;
  readonly contract?: string;
  readonly contracts?: ReadonlyArray<string>;
}

/**
 * Validate selector arity. Returns the active selector name; throws when
 * zero or >1 selectors are provided.
 */
export function validateSelectors(args: SelectorArgs): SelectorName {
  const provided: SelectorName[] = [];
  if (typeof args.station === "string" && args.station.length > 0) provided.push("station");
  if (typeof args.city === "string" && args.city.length > 0) provided.push("city");
  if (typeof args.contract === "string" && args.contract.length > 0) provided.push("contract");
  if (Array.isArray(args.contracts) && args.contracts.length > 0) provided.push("contracts");

  if (provided.length === 0) {
    throw new Error(
      "research(): exactly one of station, city, contract, contracts must be provided",
    );
  }
  if (provided.length > 1) {
    throw new Error(
      `research(): selectors are mutually exclusive; got ${JSON.stringify(provided)}`,
    );
  }
  return provided[0] as SelectorName;
}

/**
 * Resolve a `"<issuer>:<id>"` contract id to `[station, issuer]`.
 *
 * Supported: `kalshi:KHIGH<CITY>` / `kalshi:KXHIGH<CITY>-<DATE>-<STRIKE>`
 * and `kalshi:KLOW<CITY>` / `kalshi:KXLOW<CITY>-<DATE>-<STRIKE>`.
 *
 * Polymarket contract resolution requires an event_id → station lookup
 * (via polymarket-discover); Phase 10 v0.2 defers to v0.3 and throws.
 */
export function resolveContract(contractId: string): readonly [string, string] {
  if (typeof contractId !== "string" || !contractId.includes(":")) {
    throw new TypeError(`contract id must be \`<issuer>:<id>\`; got ${JSON.stringify(contractId)}`);
  }
  const colonIdx = contractId.indexOf(":");
  const issuer = contractId.slice(0, colonIdx).toLowerCase();
  const raw = contractId.slice(colonIdx + 1);
  const rawUpper = raw.toUpperCase();

  if (issuer === "kalshi") {
    // Strip KX exchange prefix (KXHIGHNYC → KHIGHNYC) and trailing
    // -DATE-STRIKE suffix to recover the legacy KHIGH<CITY> / KLOW<CITY>
    // shape the KALSHI_SETTLEMENT_STATIONS map keys are derived from.
    let normalized = rawUpper;
    if (normalized.startsWith("KX")) {
      normalized = `K${normalized.slice(2)}`;
    }
    const cityOnly = normalized.split("-", 1)[0] ?? "";
    let cityTicker: string | null = null;
    if (cityOnly.startsWith("KHIGH") && cityOnly.length > 5) {
      cityTicker = cityOnly.slice(5);
    } else if (cityOnly.startsWith("KLOW") && cityOnly.length > 4) {
      cityTicker = cityOnly.slice(4);
    } else {
      throw new Error(
        `unsupported kalshi contract format: ${JSON.stringify(raw)}; expected KHIGH<CITY>* / KXHIGH<CITY>* / KLOW<CITY>* / KXLOW<CITY>* prefix`,
      );
    }
    const entry: KalshiStation | undefined = KALSHI_SETTLEMENT_STATIONS[cityTicker];
    if (entry === undefined) {
      throw new Error(`unknown Kalshi city ticker: ${JSON.stringify(cityTicker)}`);
    }
    return [entry.station, "kalshi"] as const;
  }
  if (issuer === "polymarket") {
    throw new Error(
      "polymarket contract resolution requires event_id → station lookup via " +
        "polymarketDiscover()/polymarketSettle(); Phase 10 v0.2 defers this to " +
        "v0.3. Use `city: 'nyc'` or pass `stationOverride` until then.",
    );
  }
  throw new Error(
    `unknown issuer prefix: ${JSON.stringify(issuer)}; expected kalshi or polymarket`,
  );
}

/**
 * Resolve a city slug to all stations any issuer settles against.
 * Returns deduplicated array in stable order: Kalshi → Polymarket default/high/low
 * → Polymarket denylist backstops.
 */
export function resolveCity(city: string): readonly string[] {
  if (typeof city !== "string" || !city) {
    throw new Error(`city must be a non-empty string; got ${JSON.stringify(city)}`);
  }
  const out: string[] = [];
  const cityUpper = city.toUpperCase();
  const cityLower = city.toLowerCase();

  const kalshi = KALSHI_SETTLEMENT_STATIONS[cityUpper];
  if (kalshi !== undefined && !out.includes(kalshi.station)) {
    out.push(kalshi.station);
  }
  const poly = POLYMARKET_CITY_STATIONS[cityLower];
  if (poly !== undefined) {
    for (const measure of ["default", "high", "low"] as const) {
      const st = poly[measure];
      if (typeof st === "string" && !out.includes(st)) out.push(st);
    }
  }
  const wrong = POLYMARKET_KNOWN_WRONG_STATIONS[cityLower];
  if (wrong !== undefined) {
    const sortedWrong = [...wrong].sort();
    for (const st of sortedWrong) {
      if (!out.includes(st)) out.push(st);
    }
  }
  if (out.length === 0) {
    throw new Error(`unknown city ${JSON.stringify(city)}; not in kalshi or polymarket catalogs`);
  }
  return out;
}

/**
 * Return the list of `"<issuer>:<ticker>"` markers that settle against
 * `station` for `city`. Empty array when no issuer settles against this
 * station (typically a denylist backstop).
 */
export function annotateSettlesFor(station: string, city: string | null): readonly string[] {
  if (city === null) return [];
  const out: string[] = [];
  const cityUpper = city.toUpperCase();
  const cityLower = city.toLowerCase();
  const kalshi = KALSHI_SETTLEMENT_STATIONS[cityUpper];
  if (kalshi !== undefined && kalshi.station === station) {
    out.push(`kalshi:${cityUpper}`);
  }
  const poly = POLYMARKET_CITY_STATIONS[cityLower];
  if (poly !== undefined) {
    for (const measure of ["default", "high", "low"] as const) {
      if (poly[measure] === station) {
        out.push(`polymarket:${cityLower}`);
        break;
      }
    }
  }
  return out.sort();
}

/**
 * Build a structured `StationOverrideWarning` payload. Callers receive
 * these via the optional `onWarning?` callback on research options.
 */
export function buildOverrideWarning(
  contractStation: string,
  overrideStation: string,
): StationOverrideWarning {
  return {
    kind: "StationOverrideWarning",
    contractStation,
    overrideStation,
    message: `stationOverride=${JSON.stringify(overrideStation)} differs from contract's canonical settlement station ${JSON.stringify(contractStation)}; output row will carry settlementMismatch=true`,
  };
}

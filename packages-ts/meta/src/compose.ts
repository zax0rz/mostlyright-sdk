// Phase 10 — composable research() dispatcher (TS port of
// packages/core/src/mostlyright/_compose.py).
//
// Translates the new selectors (`city`, `contract`, `contracts`) into
// resolution metadata + station lists. Pure logic, no I/O.

import {
  KALSHI_SETTLEMENT_STATIONS,
  type KalshiStation,
  POLYMARKET_CITY_STATIONS,
} from "@mostlyright/markets";
import { POLYMARKET_KNOWN_WRONG_STATIONS } from "@mostlyright/markets/polymarket";

/** The four mutually-exclusive selector names. */
export const SELECTOR_NAMES = ["station", "city", "contract", "contracts"] as const;
export type SelectorName = (typeof SELECTOR_NAMES)[number];

/**
 * Kalshi short-ticker → canonical city slug. Real Kalshi tickers use
 * variable-length city suffixes: `KXHIGHNY-...` (NY → NYC),
 * `KXHIGHCHI-...` (CHI → CHI). The `KALSHI_SETTLEMENT_STATIONS` catalog
 * is keyed by the canonical 3-letter slug; this alias normalizes the
 * variable-length Kalshi suffix to the catalog key before lookup.
 */
const KALSHI_TICKER_ALIASES: Record<string, string> = {
  NY: "NYC",
};

/**
 * Kalshi-short ↔ Polymarket-long city slug alias. Iter-1 python-architect
 * HIGH: without this, `resolveCity("LAX")` would miss Polymarket's KLAX
 * (keyed as `los_angeles`); `resolveCity("chicago")` would miss Kalshi's
 * KMDW (keyed as `CHI`). Bi-directional probe surfaces the full
 * cross-issuer settlement neighborhood regardless of which slug form
 * the caller passed.
 */
const CITY_SLUG_ALIASES: Record<string, readonly [string, string]> = {
  // short_kalshi (lower) → [polymarket_long, kalshi_upper]
  nyc: ["nyc", "NYC"],
  chi: ["chicago", "CHI"],
  lax: ["los_angeles", "LAX"],
  mia: ["miami", "MIA"],
  den: ["denver", "DEN"],
  bos: ["boston", "BOS"],
  aus: ["austin", "AUS"],
  dca: ["washington_dc", "DCA"],
  phl: ["philadelphia", "PHL"],
  sfo: ["san_francisco", "SFO"],
  sea: ["seattle", "SEA"],
  atl: ["atlanta", "ATL"],
  hou: ["houston", "HOU"],
  dal: ["dallas", "DAL"],
  phx: ["phoenix", "PHX"],
  msp: ["minneapolis", "MSP"],
  dtw: ["detroit", "DTW"],
};

const CITY_SLUG_ALIASES_REVERSE: Record<string, readonly [string, string]> = (() => {
  const out: Record<string, readonly [string, string]> = {};
  for (const [shortLower, [longPoly, kalshiUpper]] of Object.entries(CITY_SLUG_ALIASES)) {
    out[longPoly] = [shortLower, kalshiUpper];
  }
  return out;
})();

/** Return `[polymarket_slug_lower, kalshi_slug_upper]` for `city`. */
function normalizeCitySlugs(city: string): readonly [string, string] {
  const lower = city.toLowerCase();
  const upper = city.toUpperCase();
  const direct = CITY_SLUG_ALIASES[lower];
  if (direct !== undefined) return direct;
  const reverse = CITY_SLUG_ALIASES_REVERSE[lower];
  if (reverse !== undefined) return [lower, reverse[1]];
  return [lower, upper];
}

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
    let cityTickerRaw: string | null = null;
    if (cityOnly.startsWith("KHIGH") && cityOnly.length > 5) {
      cityTickerRaw = cityOnly.slice(5);
    } else if (cityOnly.startsWith("KLOW") && cityOnly.length > 4) {
      cityTickerRaw = cityOnly.slice(4);
    } else {
      throw new Error(
        `unsupported kalshi contract format: ${JSON.stringify(raw)}; expected KHIGH<CITY>* / KXHIGH<CITY>* / KLOW<CITY>* / KXLOW<CITY>* prefix`,
      );
    }
    // Iter-1 codex HIGH: normalize variable-length Kalshi ticker suffix
    // (NY → NYC, etc.) via the alias table before the catalog lookup.
    const cityTicker = KALSHI_TICKER_ALIASES[cityTickerRaw] ?? cityTickerRaw;
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
  // Iter-1 python-architect HIGH: cross-issuer slug alias surfaces the
  // full settlement neighborhood for either input form.
  const [polySlug, kalshiSlug] = normalizeCitySlugs(city);
  const out: string[] = [];

  const kalshi = KALSHI_SETTLEMENT_STATIONS[kalshiSlug];
  if (kalshi !== undefined && !out.includes(kalshi.station)) {
    out.push(kalshi.station);
  }
  const poly = POLYMARKET_CITY_STATIONS[polySlug];
  if (poly !== undefined) {
    for (const measure of ["default", "high", "low"] as const) {
      const st = poly[measure];
      if (typeof st === "string" && !out.includes(st)) out.push(st);
    }
  }
  const wrong = POLYMARKET_KNOWN_WRONG_STATIONS[polySlug];
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
  // Iter-1 python-architect HIGH: cross-issuer slug alias annotates both
  // issuers regardless of slug form.
  const [polySlug, kalshiSlug] = normalizeCitySlugs(city);
  const out: string[] = [];
  const kalshi = KALSHI_SETTLEMENT_STATIONS[kalshiSlug];
  if (kalshi !== undefined && kalshi.station === station) {
    out.push(`kalshi:${kalshiSlug}`);
  }
  const poly = POLYMARKET_CITY_STATIONS[polySlug];
  if (poly !== undefined) {
    for (const measure of ["default", "high", "low"] as const) {
      if (poly[measure] === station) {
        out.push(`polymarket:${polySlug}`);
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

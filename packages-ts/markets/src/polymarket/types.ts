// TS-W5 — Polymarket types + security constants.
//
// Ports the v0.14.1 + Phase 3.3 Python contract verbatim. Anything that
// crosses the trust boundary (event description, resolution URL) is
// validated against the constants here before reaching the HTTP fetch
// or settlement engine.

/**
 * Resolution-source netlocs we trust. Anything else throws
 * PolymarketEventError. Mirrors Python `RESOLUTION_SOURCE_ALLOWLIST`.
 */
export const RESOLUTION_SOURCE_ALLOWLIST: ReadonlySet<string> = new Set([
  "wunderground.com",
  "www.wunderground.com",
  "weather.gov",
  "www.weather.gov",
]);

/**
 * Per-netloc → enum value for the `resolutionSourceType` field on settlement
 * records. `hko` / `cwa` are predeclared for v0.2 (HKO/CWA clients).
 */
export const NETLOC_TO_RESOLUTION_TYPE: Readonly<Record<string, string>> = Object.freeze({
  "wunderground.com": "wunderground",
  "www.wunderground.com": "wunderground",
  "weather.gov": "noaa_wrh",
  "www.weather.gov": "noaa_wrh",
});

/** Enum values for the `resolutionSourceType` column. */
export const POLYMARKET_RESOLUTION_SOURCE_TYPES = Object.freeze([
  "wunderground",
  "noaa_wrh",
  "hko",
  "cwa",
  "other",
] as const);
export type PolymarketResolutionSourceType = (typeof POLYMARKET_RESOLUTION_SOURCE_TYPES)[number];

/**
 * Event id pattern. Python widened this in codex iter-2 P1: real Gamma IDs
 * are numeric strings (`"12345"`), but condition-tag UUIDs + slugs also
 * appear in the wild. Wide enough to accept real Gamma payloads but narrow
 * enough to defend against URL-path injection.
 *
 * The plan called this "UUID4 regex" but follows Python's actual behavior:
 * the strict UUID4 form rejected every real Gamma event, breaking the
 * discover → settle round-trip.
 */
export const EVENT_ID_RE = /^[A-Za-z0-9_-]{1,128}$/;

/**
 * Max bytes of a Polymarket event description we'll parse. Polymarket
 * descriptions are concise; oversized payloads indicate hostile input
 * (ReDoS defense).
 */
export const MAX_DESCRIPTION_BYTES = 16 * 1024;

/**
 * Per-resolution-source publication delay. Settlement refuses to settle
 * until `now - settlementDate >= delay` to avoid settling on values the
 * issuer hasn't published yet.
 *
 * Wunderground typically posts daily extremes ~6h after local midnight;
 * NOAA WRH ~4h. "other" gets a conservative 24h fallback.
 */
export const SETTLE_DELAY_HOURS: Readonly<Record<string, number>> = Object.freeze({
  wunderground: 6,
  noaa_wrh: 4,
  other: 24,
});

/**
 * Slug date extractor. Polymarket weather slugs embed the resolution date
 * (e.g. `will-nyc-be-above-80f-on-2026-05-23`). Used by `polymarketSettle`
 * to derive the resolution date from the slug instead of `event.endDate`.
 */
export const SLUG_DATE_RE = /(\d{4})-(\d{2})-(\d{2})/g;

/** Markets routed to v0.2 sources (CWA/HKO clients). */
export const DEFERRED_STATIONS: ReadonlySet<string> = new Set(["VHHH", "RCTP"]);

/** Discovery row shape — one per active weather event. */
export interface PolymarketDiscoveryRow {
  readonly eventId: string | null;
  readonly slug: string | null;
  readonly title: string | null;
  readonly city: string | null;
  readonly icao: string | null;
  readonly measure: "high" | "low" | "default" | null;
  readonly endTime: string | null;
  readonly resolutionSourceType: PolymarketResolutionSourceType | null;
}

/** Settlement result shape. */
export interface PolymarketSettlementResult {
  readonly eventId: string;
  readonly settlementDate: string; // YYYY-MM-DD
  readonly icao: string;
  readonly measure: "high" | "low" | "default";
  readonly resolvedValue: number;
  readonly resolutionSourceType: PolymarketResolutionSourceType;
  readonly dataQualityAlert: string | null;
}

/** Settlement options. */
export interface PolymarketSettleOptions {
  /** Optional description override (live discovery normally supplies this). */
  readonly description?: string;
  /** Reference "now" for the finalization-delay check. Defaults to `new Date()`. */
  readonly now?: Date;
  /** Polymarket's published settlement value, if known. ±1°F/0.6°C diff emits an alert. */
  readonly polymarketPublishedValue?: number;
}

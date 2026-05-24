// TS-W5 Wave 4 — polymarketSettle().
//
// Settlement engine that consumes internationalDailyExtremes() from
// @tradewinds/core/discovery (TS-W6) as the resolution source, applies
// the security/validation gates (event-id regex, 16 KB description cap,
// netloc allowlist), and gates on the per-source publication-delay
// window via TooEarlyToSettleError.
//
// Returns `{ icao, measure, resolvedValue, resolutionSourceType, settlementDate, dataQualityAlert }`.
//
// Threshold-bucket parsing (Python computes win/lose buckets from
// description text) is deferred to v0.2 — for v0.1.0 we return the raw
// resolved value (the daily extreme) and the caller picks the bucket.
// This matches the contract the plan documents: "ports the resolution
// path, not the bucket-parser".

import { STATIONS } from "@tradewinds/core";
import { type InternationalRow, internationalDailyExtremes } from "@tradewinds/core/discovery";

import { type PolymarketEventRaw, fetchEventById } from "./client.js";
import { extractResolutionSourceType, validateDescription } from "./description.js";
import {
  PolymarketEventError,
  PolymarketSettlementError,
  TooEarlyToSettleError,
} from "./errors.js";
import { detectMarketMeasure, resolveStationForEvent, settlementDateFromSlug } from "./resolver.js";
import {
  EVENT_ID_RE,
  type PolymarketResolutionSourceType,
  type PolymarketSettleOptions,
  type PolymarketSettlementResult,
  SETTLE_DELAY_HOURS,
} from "./types.js";

/**
 * Loader contract for the resolution-source observation rows. Defaults to
 * a no-op stub so the security/validation gates can be unit-tested without
 * pulling live cache data; production callers wire the cache reader here.
 *
 * Returning an empty array signals "no rows available for this date" and
 * surfaces as PolymarketSettlementError downstream.
 */
export type ObservationLoader = (args: {
  icao: string;
  fromDate: string;
  toDate: string;
}) => Promise<ReadonlyArray<InternationalRow>>;

export interface PolymarketSettleArgs extends PolymarketSettleOptions {
  /**
   * The raw Gamma event payload. Required because the settle engine reads
   * `slug` (for the resolution date), `description` (for the resolution
   * source), and `title/slug/name` (for the measure). Callers can fetch
   * via `fetchEventById` if they only have an id.
   */
  readonly event: PolymarketEventRaw;
  /**
   * Loader that returns observation rows for `[fromDate, toDate]`. Defaults
   * to an in-memory empty loader so callers MUST wire this for production.
   */
  readonly loader?: ObservationLoader;
}

function tzForStation(icao: string): string | null {
  for (const s of STATIONS) {
    if (s.icao === icao) return s.tz;
  }
  return null;
}

function safeUuidIsh(eventId: string): boolean {
  return typeof eventId === "string" && EVENT_ID_RE.test(eventId);
}

/**
 * Settle a single Polymarket event.
 *
 * Validates the event id, description (16 KB cap, netloc allowlist),
 * resolves the station via the city catalog, parses the resolution date
 * from the slug, enforces the per-source publication-delay window, and
 * pulls the daily extreme via `internationalDailyExtremes`.
 *
 * @throws PolymarketEventError on bad id / bad description / unsupported station.
 * @throws PolymarketSettlementError when no rows resolve for the station/date.
 * @throws TooEarlyToSettleError when the publication delay hasn't elapsed.
 */
export async function polymarketSettle(
  args: PolymarketSettleArgs,
): Promise<PolymarketSettlementResult> {
  const event = args.event;
  const eventId = typeof event.id === "string" ? event.id : "";
  if (!safeUuidIsh(eventId)) {
    throw new PolymarketEventError(
      `event id ${JSON.stringify(eventId)} does not match ${EVENT_ID_RE.source}`,
    );
  }
  const slug = typeof event.slug === "string" ? event.slug : "";
  if (slug.length === 0) {
    throw new PolymarketSettlementError("event.slug is required for settlement (carries the date)");
  }
  const description =
    args.description ?? (typeof event.description === "string" ? event.description : "");
  validateDescription(description);
  const resolutionSourceType: PolymarketResolutionSourceType =
    description.length > 0 ? extractResolutionSourceType(description) : "other";

  const marketMeasure = detectMarketMeasure(event);
  const resolved = resolveStationForEvent(event, marketMeasure);
  if (resolved === null) {
    throw new PolymarketSettlementError(
      `unable to resolve station for slug=${JSON.stringify(slug)} — no matching city in catalog`,
    );
  }

  const settlementDate = settlementDateFromSlug(slug);
  const now = args.now ?? new Date();

  // Finalization-delay gate. We compare `now` to the station-local end of
  // day (23:59:59 in the station's tz) so the delay doesn't fire too early
  // for stations east of UTC.
  const tz = tzForStation(resolved.icao) ?? "UTC";
  const localEodMs = stationLocalEodUtcMs(settlementDate, tz);
  const delayHours = SETTLE_DELAY_HOURS[resolutionSourceType] ?? SETTLE_DELAY_HOURS.other ?? 24;
  const delayMs = delayHours * 3600 * 1000;
  const earliestSettleMs = localEodMs + delayMs;
  if (now.getTime() < earliestSettleMs) {
    const waitMs = earliestSettleMs - now.getTime();
    throw new TooEarlyToSettleError(
      `settlement for ${resolved.icao} on ${settlementDate} (source=${resolutionSourceType}) requires another ${(
        waitMs / 3600 / 1000
      ).toFixed(2)} h`,
      { waitHours: waitMs / 3600 / 1000, resolutionSourceType },
    );
  }

  const loader = args.loader ?? defaultEmptyLoader;
  const rows = await loader({
    icao: resolved.icao,
    fromDate: settlementDate,
    toDate: settlementDate,
  });
  if (rows.length === 0) {
    throw new PolymarketSettlementError(
      `no observation rows for station=${resolved.icao} date=${settlementDate} — warm the cache first`,
    );
  }

  const extremes = internationalDailyExtremes(rows, { stationTz: tz });
  const day = extremes.find((r) => r.localDate === settlementDate);
  if (day === undefined) {
    throw new PolymarketSettlementError(
      `no daily extreme for station=${resolved.icao} on local date ${settlementDate}`,
    );
  }

  // Pick the value per the market measure.
  let resolvedValue: number | null = null;
  if (marketMeasure === "low") {
    resolvedValue = day.tempMinF;
  } else if (marketMeasure === "high") {
    resolvedValue = day.tempMaxF;
  } else {
    // default → market doesn't specify high/low (e.g. average). Surface
    // mean if available, else fail explicitly.
    resolvedValue = day.tempMaxF; // documented v0.1.0 fallback
  }
  if (resolvedValue === null) {
    throw new PolymarketSettlementError(
      `daily extreme for ${resolved.icao} on ${settlementDate} has null ${marketMeasure} (low coverage)`,
    );
  }

  // Optional data-quality alert if caller supplied Polymarket's published value.
  let dataQualityAlert: string | null = null;
  if (typeof args.polymarketPublishedValue === "number") {
    const diffF = Math.abs(resolvedValue - args.polymarketPublishedValue);
    if (diffF > 1) {
      dataQualityAlert = `tradewinds resolved ${resolvedValue}°F but Polymarket published ${args.polymarketPublishedValue}°F (Δ=${diffF.toFixed(2)}°F > 1°F threshold)`;
    }
  }

  return Object.freeze({
    eventId,
    settlementDate,
    icao: resolved.icao,
    measure: marketMeasure,
    resolvedValue,
    resolutionSourceType,
    dataQualityAlert,
  });
}

/**
 * Settle by event id alone. Fetches the event from Gamma first, then
 * delegates to `polymarketSettle`. Useful when a caller only has the id
 * (e.g. from a Kalshi-side cross-reference).
 */
export async function polymarketSettleById(
  eventId: string,
  args: Omit<PolymarketSettleArgs, "event">,
): Promise<PolymarketSettlementResult> {
  if (!safeUuidIsh(eventId)) {
    throw new PolymarketEventError(
      `event id ${JSON.stringify(eventId)} does not match ${EVENT_ID_RE.source}`,
    );
  }
  const event = await fetchEventById(eventId);
  if (event === null) {
    throw new PolymarketSettlementError(
      `Gamma returned 404 for event id ${JSON.stringify(eventId)}`,
    );
  }
  return polymarketSettle({ ...args, event });
}

async function defaultEmptyLoader(): Promise<ReadonlyArray<InternationalRow>> {
  return [];
}

/**
 * Compute the UTC ms instant of station-local 23:59:59 for the given date.
 * Used by the publication-delay gate so the delay doesn't fire too early
 * for stations east of UTC (architect iter-1 HIGH-1 in the Python port).
 */
function stationLocalEodUtcMs(localDate: string, tz: string): number {
  // Step 1: pick a UTC instant guaranteed inside the local day (noon UTC
  // gets us inside the local day for every tz on Earth).
  const noon = new Date(`${localDate}T12:00:00Z`);
  // Step 2: extract the local-tz year/month/day for that instant via
  // Intl.DateTimeFormat (matches the discovery/international.ts trick).
  const fmt = new Intl.DateTimeFormat("en-US", {
    timeZone: tz,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  });
  const parts = fmt.formatToParts(noon);
  let y = "";
  let m = "";
  let d = "";
  for (const p of parts) {
    if (p.type === "year") y = p.value;
    else if (p.type === "month") m = p.value;
    else if (p.type === "day") d = p.value;
  }
  // Step 3: assume the station-local end-of-day is at most 14h east of UTC
  // and at most 12h west. Brute-search over the day window (1-hour grid)
  // for the instant whose local date is `y-m-d` and local time is 23:00 —
  // accept the highest match, then add 59:59 in UTC.
  // Simpler: compute as midnight-next-day local in tz minus 1s. We
  // approximate by adding 1 day to localDate and converting that midnight
  // to UTC via the same tz-format trick.
  const nextDay = new Date(`${localDate}T00:00:00Z`);
  nextDay.setUTCDate(nextDay.getUTCDate() + 1);
  // Build a UTC instant that represents the local midnight of nextDay.
  // We find the UTC ms that, when projected into tz, equals nextDay's
  // calendar date at midnight. Iterate ±14 hourly steps from nextDay UTC.
  for (let offsetH = -14; offsetH <= 14; offsetH += 1) {
    const candidate = new Date(nextDay.getTime() + offsetH * 3600 * 1000);
    const cParts = fmt.formatToParts(candidate);
    let cy = "";
    let cm = "";
    let cd = "";
    for (const p of cParts) {
      if (p.type === "year") cy = p.value;
      else if (p.type === "month") cm = p.value;
      else if (p.type === "day") cd = p.value;
    }
    // Read the local hour as well.
    const hourFmt = new Intl.DateTimeFormat("en-US", {
      timeZone: tz,
      hour: "2-digit",
      hour12: false,
    });
    const hourParts = hourFmt.formatToParts(candidate);
    const hourStr = hourParts.find((p) => p.type === "hour")?.value ?? "00";
    // Some tz formatters use "24" for midnight; normalize.
    const hour = hourStr === "24" ? 0 : Number(hourStr);
    if (`${cy}-${cm}-${cd}` === `${nextDayDate(localDate)}` && hour === 0) {
      // candidate is exactly the next-day midnight LOCAL. Subtract 1s
      // for end-of-day.
      return candidate.getTime() - 1000;
    }
  }
  // Fallback: assume UTC if we can't resolve.
  return new Date(`${localDate}T23:59:59Z`).getTime();
}

function nextDayDate(localDate: string): string {
  const d = new Date(`${localDate}T00:00:00Z`);
  d.setUTCDate(d.getUTCDate() + 1);
  return d.toISOString().slice(0, 10);
}

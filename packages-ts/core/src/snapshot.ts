// Snapshot math — settlement-window and market-close arithmetic.
//
// Ported from `packages/core/src/tradewinds/snapshot.py` and
// `packages/core/src/tradewinds/_internal/_pairs.py:market_close_utc`.
//
// Key concepts:
//  - LOCAL STANDARD TIME (LST): station's standard UTC offset, DST ignored.
//    Kalshi NHIGH/NLOW contracts define the settlement window in LST.
//  - Settlement window: midnight-midnight LST for a given date.
//    During US daylight saving the clock window is 1:00 AM–1:00 AM next day
//    (EDT), but the UTC bounds are the same year-round.
//  - CLI publication delay: NWS issues the overnight final CLI ~04:00–10:00
//    UTC the day after observation. Default: 10 h after midnight LST.

// ---------------------------------------------------------------------------
// Station → IANA timezone database
// ---------------------------------------------------------------------------
//
// Used to extract the LOCAL STANDARD TIME UTC offset via a January reference
// moment. Ported from `tradewinds.snapshot._STATION_TZ`.

export const _STATION_TZ: Readonly<Record<string, string>> = Object.freeze({
  // Eastern (UTC-5 standard / UTC-4 DST)
  NYC: "America/New_York",
  JFK: "America/New_York",
  LGA: "America/New_York",
  EWR: "America/New_York",
  ATL: "America/New_York",
  BOS: "America/New_York",
  PHL: "America/New_York",
  DCA: "America/New_York",
  IAD: "America/New_York",
  BWI: "America/New_York",
  MIA: "America/New_York",
  MCO: "America/New_York",
  TPA: "America/New_York",
  CLT: "America/New_York",
  RDU: "America/New_York",
  CLE: "America/New_York",
  PIT: "America/New_York",
  BUF: "America/New_York",
  DTW: "America/Detroit",
  IND: "America/Indiana/Indianapolis",
  CVG: "America/New_York",
  CMH: "America/New_York",
  SYR: "America/New_York",
  ALB: "America/New_York",
  BTV: "America/New_York",
  ORF: "America/New_York",
  RIC: "America/New_York",
  GSO: "America/New_York",
  CHS: "America/New_York",
  SAV: "America/New_York",
  JAX: "America/New_York",
  RSW: "America/New_York",
  PBI: "America/New_York",
  FLL: "America/New_York",
  // Central (UTC-6 standard / UTC-5 DST)
  ORD: "America/Chicago",
  MDW: "America/Chicago",
  DFW: "America/Chicago",
  DAL: "America/Chicago",
  IAH: "America/Chicago",
  HOU: "America/Chicago",
  MSP: "America/Chicago",
  STL: "America/Chicago",
  MCI: "America/Chicago",
  OMA: "America/Chicago",
  MKE: "America/Chicago",
  MSY: "America/Chicago",
  MEM: "America/Chicago",
  BNA: "America/Chicago",
  OKC: "America/Chicago",
  SAT: "America/Chicago",
  AUS: "America/Chicago",
  DSM: "America/Chicago",
  TUL: "America/Chicago",
  LIT: "America/Chicago",
  BIR: "America/Chicago",
  SDF: "America/Chicago",
  HSV: "America/Chicago",
  BHM: "America/Chicago",
  MOB: "America/Chicago",
  BTR: "America/Chicago",
  SHV: "America/Chicago",
  // Mountain (UTC-7 standard / UTC-6 DST)
  DEN: "America/Denver",
  SLC: "America/Denver",
  ABQ: "America/Denver",
  BOI: "America/Boise",
  BZN: "America/Denver",
  GJT: "America/Denver",
  // Arizona: no DST (UTC-7 always)
  PHX: "America/Phoenix",
  TUS: "America/Phoenix",
  // Pacific (UTC-8 standard / UTC-7 DST)
  LAX: "America/Los_Angeles",
  SFO: "America/Los_Angeles",
  SEA: "America/Los_Angeles",
  PDX: "America/Los_Angeles",
  LAS: "America/Los_Angeles",
  SAN: "America/Los_Angeles",
  OAK: "America/Los_Angeles",
  SJC: "America/Los_Angeles",
  SMF: "America/Los_Angeles",
  RNO: "America/Los_Angeles",
  FAT: "America/Los_Angeles",
  SNA: "America/Los_Angeles",
  ONT: "America/Los_Angeles",
  BUR: "America/Los_Angeles",
  // Alaska (UTC-9 standard / UTC-8 DST)
  ANC: "America/Anchorage",
  FAI: "America/Anchorage",
  JNU: "America/Juneau",
  // Hawaii (UTC-10, no DST)
  HNL: "Pacific/Honolulu",
  OGG: "Pacific/Honolulu",
  KOA: "Pacific/Honolulu",
  // International (iter-6 H12): minimal set required to un-skip the
  // case-5 RJTT year-wrap cache behavior test. Python's
  // `tradewinds.snapshot._resolve_tz` falls back to the broader STATIONS
  // registry for intl ICAOs; the TS port hasn't ported that fallback
  // yet (tracked as TS-W6 — exhaustive intl-station tz coverage). This
  // entry closes H12 cleanly without pulling the whole STATIONS map in.
  // ICAO key (RJTT) — international stations have no 3-letter NWS code.
  // Tokyo Haneda — UTC+9 LST, no DST.
  RJTT: "Asia/Tokyo",
});

/** Reference UTC moment in January (no DST in Northern Hemisphere US). */
export const _JAN_REF = new Date(Date.UTC(2024, 0, 15, 12, 0, 0));

/** NWS CLI typical publication delay: 10 h after midnight LST. */
export const _CLI_PUBLICATION_DELAY_HOURS = 10.0;

/** Kalshi market typical close time (LST). */
export const _MARKET_CLOSE_HOUR_LST = 16;
export const _MARKET_CLOSE_MINUTE_LST = 30;

// ---------------------------------------------------------------------------
// LST offset extraction
// ---------------------------------------------------------------------------

const _OFFSET_CACHE = new Map<string, number>();

/**
 * Return the LOCAL STANDARD TIME UTC offset (in hours) for an IANA tz,
 * sampled from January 15 2024 12:00 UTC so the result is never affected
 * by DST in the Northern Hemisphere.
 *
 * Implementation: format `_JAN_REF` in the target tz via Intl.DateTimeFormat
 * and diff against the UTC formatted view to recover the offset.
 */
export function _lstOffsetHours(stationTz: string): number {
  const cached = _OFFSET_CACHE.get(stationTz);
  if (cached !== undefined) return cached;

  // We compute: localComponents(stationTz, _JAN_REF) − utcComponents(_JAN_REF).
  // The difference gives the tz offset in (hours). Negative for west of UTC.
  const fmt = new Intl.DateTimeFormat("en-US", {
    timeZone: stationTz,
    hour12: false,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
  const parts = fmt.formatToParts(_JAN_REF);
  const get = (type: string): number => {
    const part = parts.find((p) => p.type === type);
    if (!part) {
      throw new Error(`Intl.DateTimeFormat missing ${type} for tz=${stationTz}`);
    }
    return Number(part.value);
  };

  const year = get("year");
  const month = get("month");
  const day = get("day");
  let hour = get("hour");
  const minute = get("minute");
  const second = get("second");
  // Some locales return hour "24" instead of "00" for midnight; normalize.
  if (hour === 24) hour = 0;

  // Compute the timezone's wall-clock for _JAN_REF treated as UTC.
  const localAsUtc = Date.UTC(year, month - 1, day, hour, minute, second);
  const offsetMs = localAsUtc - _JAN_REF.getTime();
  const offsetHours = offsetMs / 3_600_000;
  _OFFSET_CACHE.set(stationTz, offsetHours);
  return offsetHours;
}

// ---------------------------------------------------------------------------
// Station code normalization + tz lookup
// ---------------------------------------------------------------------------

function _stationCodeNormalized(station: string): string {
  const s = station.trim().toUpperCase();
  if (s.length === 4 && s.startsWith("K")) {
    return s.substring(1);
  }
  return s;
}

/**
 * Resolve a station code (NWS 3-letter, ICAO 4-letter) to an IANA tz string.
 * Honors `tzOverride` first, then the built-in `_STATION_TZ` map.
 * Throws if no tz can be resolved.
 */
export function _resolveStationTz(station: string, tzOverride?: string): string {
  if (tzOverride) return tzOverride;
  const code = _stationCodeNormalized(station);
  const tz = _STATION_TZ[code];
  if (tz) return tz;
  throw new Error(
    `Unknown station timezone: ${JSON.stringify(code)}. Add it to _STATION_TZ or pass tzOverride="America/...".`,
  );
}

// ---------------------------------------------------------------------------
// as_of parsing
// ---------------------------------------------------------------------------

function _parseAsOf(asOf: Date | string): Date {
  if (asOf instanceof Date) {
    if (Number.isNaN(asOf.getTime())) {
      throw new Error("Invalid Date passed as asOf");
    }
    return asOf;
  }
  let s = asOf.trim();
  // Python: bare ISO without tz → assume UTC.
  if (s.endsWith("Z")) {
    // Date.parse handles "Z" natively.
  } else if (!/[+-]\d{2}:?\d{2}$/.test(s)) {
    // No timezone suffix — treat as UTC.
    s = `${s}Z`;
  }
  const ms = Date.parse(s);
  if (!Number.isFinite(ms)) {
    throw new Error(`Invalid as_of string: ${JSON.stringify(asOf)}`);
  }
  return new Date(ms);
}

// ---------------------------------------------------------------------------
// Public surface
// ---------------------------------------------------------------------------

function _pad2(n: number): string {
  return n < 10 ? `0${n}` : `${n}`;
}

function _isoDate(year: number, month: number, day: number): string {
  return `${year}-${_pad2(month)}-${_pad2(day)}`;
}

/**
 * Return the Kalshi settlement date (YYYY-MM-DD LST) for a UTC moment.
 *
 * Kalshi NHIGH/NLOW contracts cover midnight–midnight LOCAL STANDARD TIME.
 * DST is ignored: the window is always fixed to the standard UTC offset.
 */
export function settlementDateFor(
  asOf: Date | string,
  station: string,
  tzOverride?: string,
): string {
  const utcDt = _parseAsOf(asOf);
  const tz = _resolveStationTz(station, tzOverride);
  const offsetHours = _lstOffsetHours(tz);
  // offsetHours is negative for US stations → lstMs < utcMs.
  const lstMs = utcDt.getTime() + offsetHours * 3_600_000;
  const lst = new Date(lstMs);
  // Use getUTC* because we already shifted the epoch by the LST offset.
  return _isoDate(lst.getUTCFullYear(), lst.getUTCMonth() + 1, lst.getUTCDate());
}

/**
 * Return UTC start/end of the Kalshi settlement window for a date.
 * The window is midnight-midnight LST, expressed in UTC.
 */
export function settlementWindowUtc(
  dateStr: string,
  station: string,
  tzOverride?: string,
): [Date, Date] {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(dateStr);
  if (!match) {
    throw new Error(`Invalid ISO date for settlement window: ${JSON.stringify(dateStr)}`);
  }
  const [, yStr, mStr, dStr] = match;
  const year = Number(yStr);
  const month = Number(mStr);
  const day = Number(dStr);
  const tz = _resolveStationTz(station, tzOverride);
  const offsetHours = _lstOffsetHours(tz);

  // midnight LST = 00:00 LST = (00:00 UTC) − offset (offset is negative)
  // Example: UTC-5 → midnight LST = 05:00 UTC.
  const midnightLstAsUtcMs = Date.UTC(year, month - 1, day, 0, 0, 0);
  const startMs = midnightLstAsUtcMs - offsetHours * 3_600_000;
  const start = new Date(startMs);
  const end = new Date(startMs + 24 * 3_600_000);
  return [start, end];
}

/**
 * Return the UTC time at which the NWS CLI for a date is expected to be
 * available. Default delay is 10 h after midnight LST on the next day.
 */
export function cliAvailableAt(
  dateStr: string,
  station: string,
  delayHours: number = _CLI_PUBLICATION_DELAY_HOURS,
  tzOverride?: string,
): Date {
  const [, windowEnd] = settlementWindowUtc(dateStr, station, tzOverride);
  return new Date(windowEnd.getTime() + delayHours * 3_600_000);
}

/**
 * Return the UTC time of the Kalshi market close for a settlement date.
 * Kalshi NHIGH/NLOW markets close at 4:30 PM LST on the day of settlement.
 */
export function marketCloseUtc(dateStr: string, station: string, tzOverride?: string): Date {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(dateStr);
  if (!match) {
    throw new Error(`Invalid ISO date for market close: ${JSON.stringify(dateStr)}`);
  }
  const [, yStr, mStr, dStr] = match;
  const year = Number(yStr);
  const month = Number(mStr);
  const day = Number(dStr);
  const tz = _resolveStationTz(station, tzOverride);
  const offsetHours = _lstOffsetHours(tz);

  const marketCloseAsUtcMs = Date.UTC(
    year,
    month - 1,
    day,
    _MARKET_CLOSE_HOUR_LST,
    _MARKET_CLOSE_MINUTE_LST,
    0,
  );
  return new Date(marketCloseAsUtcMs - offsetHours * 3_600_000);
}

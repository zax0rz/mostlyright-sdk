// TS-W5 Wave 1 — Polymarket Gamma API client.
//
// Port of `packages/markets/src/tradewinds/markets/_polymarket_client.py`.
// HTTP fetch + 0.2s politeness sleep + retry on 429/5xx + offset-paginated
// discovery up to 10000 events. Gamma's Cloudfront edge 403s on blank
// User-Agent, so we always set a tradewinds UA.

import { fetchWithRetry } from "@tradewinds/core";

const GAMMA_BASE = "https://gamma-api.polymarket.com";
const PAGE_SIZE = 100;
const MAX_EVENTS = 10_000;
const DEFAULT_USER_AGENT = "tradewinds-ts/0.1.0 (+https://github.com/Tarabcak/tradewinds)";
const DEFAULT_SLEEP_BETWEEN_MS = 200; // 0.2 s
const RETRY_STATUSES: ReadonlySet<number> = new Set([429, 500, 502, 503, 504]);

/** Raw Gamma event payload — narrow shape we depend on. */
export interface PolymarketEventRaw {
  id?: string;
  slug?: string;
  title?: string;
  description?: string;
  endDate?: string;
  active?: boolean;
  closed?: boolean;
  archived?: boolean;
  tags?: Array<string | { label?: string; slug?: string }>;
  [key: string]: unknown;
}

export interface FetchEventsOptions {
  /** Politeness sleep between requests, in ms. Default 200 (0.2 s). Pass 0 to skip. */
  readonly sleepBetweenMs?: number;
  /** AbortSignal for the whole paginator. */
  readonly signal?: AbortSignal;
  /** Override fetch (for tests). Defaults to global fetch. */
  readonly fetchFn?: typeof fetch;
}

async function sleep(ms: number, signal?: AbortSignal): Promise<void> {
  if (ms <= 0) return;
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => {
      cleanup();
      resolve();
    }, ms);
    const onAbort = () => {
      cleanup();
      reject(signal?.reason ?? new DOMException("Aborted", "AbortError"));
    };
    function cleanup() {
      clearTimeout(timer);
      if (signal !== undefined) signal.removeEventListener("abort", onAbort);
    }
    if (signal !== undefined) {
      if (signal.aborted) {
        cleanup();
        reject(signal.reason ?? new DOMException("Aborted", "AbortError"));
        return;
      }
      signal.addEventListener("abort", onAbort, { once: true });
    }
  });
}

/**
 * Fetch every active weather event from Gamma, paginated by `offset` in
 * `PAGE_SIZE` increments until either an empty page is returned or
 * `MAX_EVENTS` is reached. Dedup by slug to defend against the rare case
 * where pagination overlaps under concurrent edits on Gamma's side.
 */
export async function fetchEvents(opts: FetchEventsOptions = {}): Promise<PolymarketEventRaw[]> {
  const sleepMs = opts.sleepBetweenMs ?? DEFAULT_SLEEP_BETWEEN_MS;
  const seen = new Set<string>();
  const out: PolymarketEventRaw[] = [];
  for (let offset = 0; offset < MAX_EVENTS; offset += PAGE_SIZE) {
    const url = `${GAMMA_BASE}/events?limit=${PAGE_SIZE}&offset=${offset}&active=true&closed=false`;
    const fetchOpts: Parameters<typeof fetchWithRetry>[1] = {
      headers: { Accept: "application/json" },
      userAgent: DEFAULT_USER_AGENT,
      retryStatuses: RETRY_STATUSES,
    };
    if (opts.signal !== undefined) fetchOpts.signal = opts.signal;
    const resp = await (opts.fetchFn !== undefined
      ? // Custom fetch override (tests). Bypass retry — caller mock-controls statuses.
        opts.fetchFn(url, { headers: { ...fetchOpts.headers, "User-Agent": DEFAULT_USER_AGENT } })
      : fetchWithRetry(url, fetchOpts));
    if (!resp.ok) {
      throw new Error(`Gamma API returned ${resp.status} ${resp.statusText} for offset=${offset}`);
    }
    const page = (await resp.json()) as PolymarketEventRaw[];
    if (!Array.isArray(page) || page.length === 0) break;
    for (const ev of page) {
      const slug = typeof ev.slug === "string" ? ev.slug : null;
      if (slug === null || seen.has(slug)) continue;
      seen.add(slug);
      out.push(ev);
    }
    if (page.length < PAGE_SIZE) break;
    if (sleepMs > 0 && offset + PAGE_SIZE < MAX_EVENTS) {
      await sleep(sleepMs, opts.signal);
    }
  }
  return out;
}

/** Fetch a single event by id. Useful for the settle() flow when only an id is known. */
export async function fetchEventById(
  eventId: string,
  opts: FetchEventsOptions = {},
): Promise<PolymarketEventRaw | null> {
  const url = `${GAMMA_BASE}/events/${encodeURIComponent(eventId)}`;
  const fetchOpts: Parameters<typeof fetchWithRetry>[1] = {
    headers: { Accept: "application/json" },
    userAgent: DEFAULT_USER_AGENT,
    retryStatuses: RETRY_STATUSES,
  };
  if (opts.signal !== undefined) fetchOpts.signal = opts.signal;
  const resp = await (opts.fetchFn !== undefined
    ? opts.fetchFn(url, { headers: { ...fetchOpts.headers, "User-Agent": DEFAULT_USER_AGENT } })
    : fetchWithRetry(url, fetchOpts));
  if (resp.status === 404) return null;
  if (!resp.ok) {
    throw new Error(`Gamma API returned ${resp.status} ${resp.statusText} for event=${eventId}`);
  }
  return (await resp.json()) as PolymarketEventRaw;
}

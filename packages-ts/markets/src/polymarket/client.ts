// TS-W5 Wave 1 — Polymarket Gamma API client.
//
// Port of `packages/markets/src/mostlyright/markets/_polymarket_client.py`.
// HTTP fetch + 0.2s politeness sleep + retry on 429/5xx + offset-paginated
// discovery up to 10000 events. Gamma's Cloudfront edge 403s on blank
// User-Agent, so we always set a mostlyright UA.

import { NotFoundError, fetchWithRetry } from "@mostlyright/core";

const GAMMA_BASE = "https://gamma-api.polymarket.com";
const PAGE_SIZE = 100;
const MAX_EVENTS = 10_000;
const DEFAULT_USER_AGENT = "mostlyright-ts/0.1.0 (+https://github.com/Tarabcak/mostlyright)";
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
    // Codex iter-5 P3: forward `signal` to the custom fetchFn override too
    // so callers can abort in-flight requests, not just inter-page sleeps.
    const customInit: RequestInit = {
      headers: { ...fetchOpts.headers, "User-Agent": DEFAULT_USER_AGENT },
    };
    if (opts.signal !== undefined) customInit.signal = opts.signal;
    const resp = await (opts.fetchFn !== undefined
      ? // Custom fetch override (tests). Bypass retry — caller mock-controls statuses.
        opts.fetchFn(url, customInit)
      : fetchWithRetry(url, fetchOpts));
    if (!resp.ok) {
      throw new Error(`Gamma API returned ${resp.status} ${resp.statusText} for offset=${offset}`);
    }
    const raw = (await resp.json()) as unknown;
    // Codex iter-2 P2: distinguish "Gamma changed shape" from "empty page".
    // Empty list → natural pagination terminator. Non-list → upstream
    // contract changed; surface loudly instead of returning {} as nothing.
    let page: PolymarketEventRaw[];
    if (Array.isArray(raw)) {
      page = raw as PolymarketEventRaw[];
    } else if (
      raw !== null &&
      typeof raw === "object" &&
      Array.isArray((raw as { data?: unknown }).data)
    ) {
      // Tolerate the documented `{data: [...]}` envelope shape.
      page = (raw as { data: PolymarketEventRaw[] }).data;
    } else {
      throw new Error(
        `Gamma API returned an unexpected page shape at offset=${offset} (expected array or {data: array}, got ${
          raw === null ? "null" : typeof raw
        }). The upstream contract may have changed; check https://docs.polymarket.com/.`,
      );
    }
    if (page.length === 0) break;
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
  // Codex iter-2 P2: fetchWithRetry THROWS NotFoundError on 404 (it does
  // not return a Response); the resp.status check below is unreachable
  // through the default path. Catch + convert to the documented null
  // return so polymarketSettleById can surface PolymarketSettlementError.
  // Codex iter-5 P3: forward `signal` to custom fetchFn override too.
  const customInit: RequestInit = {
    headers: { ...fetchOpts.headers, "User-Agent": DEFAULT_USER_AGENT },
  };
  if (opts.signal !== undefined) customInit.signal = opts.signal;
  let resp: Response;
  try {
    resp =
      opts.fetchFn !== undefined
        ? await opts.fetchFn(url, customInit)
        : await fetchWithRetry(url, fetchOpts);
  } catch (err) {
    if (err instanceof NotFoundError) return null;
    throw err;
  }
  if (resp.status === 404) return null;
  if (!resp.ok) {
    throw new Error(`Gamma API returned ${resp.status} ${resp.statusText} for event=${eventId}`);
  }
  return (await resp.json()) as PolymarketEventRaw;
}

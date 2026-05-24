// Phase 9 — Polymarket trades public surface (TRADES-04..05, TS port of
// packages/markets/src/tradewinds/markets/polymarket_trades.py).
//
// Uses the existing Gamma client pattern (fetchFn injection, 0.2 s polite
// floor). Row shapes mirror Python column-for-column.

import { fetchWithRetry } from "@tradewinds/core";

import type { PolymarketHistoryRow, PolymarketSnapshotRow, TradesResult } from "./types.js";

const GAMMA_BASE = "https://gamma-api.polymarket.com";
const DEFAULT_USER_AGENT = "tradewinds-ts/0.2.0 (+https://github.com/helloiamvu/tradewinds)";
const DEFAULT_SLEEP_BETWEEN_MS = 200;
const SOURCE = "polymarket.gamma" as const;

export interface PolymarketClientOptions {
  /** Politeness sleep between requests in ms. Default 200. 0 to skip. */
  readonly sleepBetweenMs?: number;
  /** AbortSignal for the whole call. */
  readonly signal?: AbortSignal;
  /** Override fetch for tests. */
  readonly fetchFn?: typeof fetch;
  /** Per-attempt timeout. Default 30_000 ms. */
  readonly timeoutMs?: number;
}

export interface PolymarketHistoryArgs {
  readonly from: Date;
  readonly to: Date;
  /** Bucket size in minutes (default 60). */
  readonly fidelityMinutes?: number;
}

function validateDate(d: Date, name: string): void {
  if (!(d instanceof Date) || Number.isNaN(d.getTime())) {
    throw new TypeError(`${name} must be a valid Date; got ${String(d)}`);
  }
}

function maybeNumber(v: unknown): number | null {
  if (v === null || v === undefined) return null;
  const n = typeof v === "string" ? Number(v) : (v as number);
  return typeof n === "number" && Number.isFinite(n) ? n : null;
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
      signal?.removeEventListener("abort", onAbort);
    }
    if (signal) {
      if (signal.aborted) {
        cleanup();
        reject(signal.reason ?? new DOMException("Aborted", "AbortError"));
        return;
      }
      signal.addEventListener("abort", onAbort);
    }
  });
}

function buildUrl(
  path: string,
  params?: Record<string, string | number | boolean | null | undefined>,
): string {
  const url = new URL(`${GAMMA_BASE}${path}`);
  if (params) {
    for (const [key, value] of Object.entries(params)) {
      if (value === undefined || value === null) continue;
      url.searchParams.set(key, String(value));
    }
  }
  return url.toString();
}

async function getJson(
  path: string,
  params: Record<string, string | number | boolean | null | undefined> | undefined,
  opts: PolymarketClientOptions,
): Promise<unknown> {
  const url = buildUrl(path, params);
  const headers: Record<string, string> = {
    "User-Agent": DEFAULT_USER_AGENT,
    Accept: "application/json",
  };
  const timeoutMs = opts.timeoutMs ?? 30_000;
  let resp: Response;
  if (opts.fetchFn !== undefined) {
    const init: RequestInit = { method: "GET", headers };
    if (opts.signal) init.signal = opts.signal;
    resp = await opts.fetchFn(url, init);
    if (!resp.ok) {
      throw new Error(`polymarket GET ${url} failed: HTTP ${resp.status}`);
    }
  } else {
    const retryOpts: Parameters<typeof fetchWithRetry>[1] = {
      method: "GET",
      headers,
      timeoutMs,
    };
    if (opts.signal) retryOpts.signal = opts.signal;
    resp = await fetchWithRetry(url, retryOpts);
  }
  const json = await resp.json();
  const sleepMs = opts.sleepBetweenMs ?? DEFAULT_SLEEP_BETWEEN_MS;
  if (sleepMs > 0) {
    await sleep(sleepMs, opts.signal);
  }
  return json;
}

interface RawPricePoint {
  readonly t?: number;
  readonly p?: number | string;
  readonly v?: number | string;
  readonly price?: number | string;
  readonly volume?: number | string;
}

interface RawMarket {
  readonly id?: string | number;
  readonly outcomes?: string | ReadonlyArray<unknown>;
  readonly outcomePrices?: string | ReadonlyArray<unknown>;
  readonly volume?: number | string;
  readonly liquidity?: number | string;
}

interface RawEvent {
  readonly id?: string;
  readonly markets?: ReadonlyArray<RawMarket>;
}

function coerceStringList(v: unknown): string[] {
  if (v === null || v === undefined) return [];
  if (Array.isArray(v)) return v.map((x) => String(x));
  if (typeof v === "string") {
    try {
      const parsed: unknown = JSON.parse(v);
      if (Array.isArray(parsed)) return parsed.map((x) => String(x));
    } catch {
      return [];
    }
  }
  return [];
}

export async function polymarketHistory(
  marketId: string,
  args: PolymarketHistoryArgs,
  opts: PolymarketClientOptions = {},
): Promise<TradesResult<PolymarketHistoryRow>> {
  if (typeof marketId !== "string" || marketId.length === 0) {
    throw new TypeError(`marketId must be a non-empty string; got ${JSON.stringify(marketId)}`);
  }
  validateDate(args.from, "from");
  validateDate(args.to, "to");
  if (args.from.getTime() >= args.to.getTime()) {
    throw new RangeError(
      `from (${args.from.toISOString()}) must be < to (${args.to.toISOString()})`,
    );
  }
  const fidelity = args.fidelityMinutes ?? 60;
  if (fidelity < 1 || !Number.isInteger(fidelity)) {
    throw new RangeError(`fidelityMinutes must be a positive integer; got ${fidelity}`);
  }
  const payload = await getJson(
    "/prices-history",
    {
      market: marketId,
      startTs: Math.trunc(args.from.getTime() / 1000),
      endTs: Math.trunc(args.to.getTime() / 1000),
      fidelity,
    },
    opts,
  );
  let points: ReadonlyArray<RawPricePoint>;
  if (Array.isArray(payload)) {
    points = payload as ReadonlyArray<RawPricePoint>;
  } else if (payload !== null && typeof payload === "object") {
    points = (payload as { history?: ReadonlyArray<RawPricePoint> }).history ?? [];
  } else {
    points = [];
  }
  const rows: PolymarketHistoryRow[] = [];
  for (const p of points) {
    if (p === null || typeof p !== "object") continue;
    const tsEpoch = p.t;
    const ts =
      typeof tsEpoch === "number" && Number.isFinite(tsEpoch)
        ? new Date(tsEpoch * 1000).toISOString()
        : null;
    rows.push({
      ts,
      price: maybeNumber(p.p ?? p.price),
      volume: maybeNumber(p.v ?? p.volume),
      source: SOURCE,
    });
  }
  return Object.freeze({
    rows: Object.freeze(rows),
    source: SOURCE,
    retrievedAt: new Date().toISOString(),
    marketId,
    fidelityMinutes: fidelity,
  });
}

export async function polymarketSnapshot(
  eventId: string,
  opts: PolymarketClientOptions = {},
): Promise<TradesResult<PolymarketSnapshotRow>> {
  if (typeof eventId !== "string" || eventId.length === 0) {
    throw new TypeError(`eventId must be a non-empty string; got ${JSON.stringify(eventId)}`);
  }
  const payload = await getJson(`/events/${encodeURIComponent(eventId)}`, undefined, opts);
  if (payload === null || typeof payload !== "object" || Array.isArray(payload)) {
    throw new Error(
      `polymarket snapshot: bad event payload for ${JSON.stringify(eventId)}; expected object`,
    );
  }
  const event = payload as RawEvent;
  const markets = event.markets ?? [];
  const rows: PolymarketSnapshotRow[] = [];
  for (const m of markets) {
    if (m === null || typeof m !== "object") continue;
    const outcomes = coerceStringList(m.outcomes);
    const prices = coerceStringList(m.outcomePrices);
    const volume = maybeNumber(m.volume);
    const liquidity = maybeNumber(m.liquidity);
    const marketIdStr = m.id !== undefined && m.id !== null ? String(m.id) : null;
    for (let i = 0; i < outcomes.length; i++) {
      const priceStr = i < prices.length ? prices[i] : null;
      rows.push({
        marketId: marketIdStr,
        outcome: outcomes[i] ?? "",
        lastPrice: maybeNumber(priceStr),
        volume,
        liquidity,
        source: SOURCE,
      });
    }
  }
  const snapshotAt = new Date().toISOString();
  return Object.freeze({
    rows: Object.freeze(rows),
    source: SOURCE,
    retrievedAt: snapshotAt,
    snapshotAt,
    eventId,
  });
}

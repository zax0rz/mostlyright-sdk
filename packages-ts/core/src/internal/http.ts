// Shared HTTP download helper with retry logic.
//
// Ported from `packages/core/src/tradewinds/_internal/_http.py`.
// Uses the native `fetch` API so this module works in browsers, Node 20+,
// Cloudflare Workers, and Deno. Returns the `Response` on success — callers
// decide whether to consume JSON, text, or bytes.

import {
  AuthenticationError,
  ForbiddenError,
  NotFoundError,
  RateLimitError,
  ServerError,
  TherminalError,
  ValidationError,
} from "../exceptions/index.js";

/** Default base backoff delay (ms). Mirrors Python `BASE_DELAY = 1.0`. */
const DEFAULT_BASE_DELAY_MS = 1000;
/** Default retry budget. Mirrors Python `MAX_RETRIES = 3` (total attempts). */
const DEFAULT_MAX_RETRIES = 3;
/** Default per-attempt timeout. Mirrors Python `HTTP_TIMEOUT = 60.0`. */
const DEFAULT_TIMEOUT_MS = 60_000;
/** Retryable statuses. Mirrors Python `TRANSIENT_CODES`. */
const DEFAULT_RETRY_STATUSES: ReadonlySet<number> = new Set([429, 500, 502, 503, 504]);

export interface FetchWithRetryOptions {
  /** Base backoff delay in milliseconds (default 1000). */
  baseDelayMs?: number;
  /** Total attempts (default 3). */
  maxRetries?: number;
  /** Per-attempt timeout in milliseconds (default 60_000). */
  timeoutMs?: number;
  /** Statuses that trigger a retry. Default {429, 500, 502, 503, 504}. */
  retryStatuses?: ReadonlySet<number>;
  /** Caller-supplied abort signal (composed with per-attempt timeout). */
  signal?: AbortSignal;
  /** Request headers. */
  headers?: Record<string, string>;
  /** Convenience: set the User-Agent header. */
  userAgent?: string;
  /** HTTP method (default GET). */
  method?: string;
  /** Optional request body (forwarded to `fetch`). */
  body?: BodyInit | null;
}

function sleep(ms: number, signal?: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    if (signal?.aborted) {
      reject(new DOMException("Aborted", "AbortError"));
      return;
    }
    const timer = setTimeout(() => {
      cleanup();
      resolve();
    }, ms);
    const onAbort = () => {
      cleanup();
      reject(new DOMException("Aborted", "AbortError"));
    };
    const cleanup = () => {
      clearTimeout(timer);
      signal?.removeEventListener("abort", onAbort);
    };
    signal?.addEventListener("abort", onAbort, { once: true });
  });
}

function parseRetryAfter(header: string | null): number | null {
  if (!header) return null;
  const asInt = Number(header);
  if (Number.isFinite(asInt) && asInt >= 0) return asInt;
  // HTTP-date form — convert to seconds-from-now.
  const dateMs = Date.parse(header);
  if (Number.isFinite(dateMs)) {
    return Math.max(0, Math.round((dateMs - Date.now()) / 1000));
  }
  return null;
}

function throwForNonRetryableStatus(status: number, url: string, retryAfter: number | null): never {
  if (status === 404) {
    throw new NotFoundError(`HTTP 404 for ${url}`);
  }
  if (status === 400) {
    throw new ValidationError(`HTTP 400 for ${url}`);
  }
  if (status === 401) {
    throw new AuthenticationError(`HTTP 401 for ${url}`);
  }
  if (status === 403) {
    throw new ForbiddenError(`HTTP 403 for ${url}`);
  }
  if (status === 429) {
    throw new RateLimitError(retryAfter, { source: url });
  }
  if (status >= 500 && status < 600) {
    throw new ServerError(`HTTP ${status} for ${url}`, { statusCode: status });
  }
  throw new TherminalError(`HTTP ${status} for ${url}`, { statusCode: status });
}

/**
 * GET (or other) a URL with exponential-backoff retry semantics.
 *
 * Behaviour:
 *  - `signal` is composed with a per-attempt timeout via `AbortController`.
 *  - On retryable status (default: 429/500/502/503/504), wait
 *    `baseDelayMs * 2^attempt` (with ≤25% jitter) and retry, up to
 *    `maxRetries` total attempts.
 *  - On 404 → `NotFoundError`. On 400/401/403 → `ValidationError` /
 *    `AuthenticationError` / `ForbiddenError`. After retry exhaustion on
 *    429 → `RateLimitError` (with `retryAfter` honoured). After retry
 *    exhaustion on 5xx → `ServerError`.
 *  - On network/transport failure: retried under the same budget, last
 *    error rethrown as a `TherminalError` if it isn't one already.
 */
export async function fetchWithRetry(
  url: string,
  opts: FetchWithRetryOptions = {},
): Promise<Response> {
  const baseDelay = opts.baseDelayMs ?? DEFAULT_BASE_DELAY_MS;
  const maxRetries = opts.maxRetries ?? DEFAULT_MAX_RETRIES;
  const timeoutMs = opts.timeoutMs ?? DEFAULT_TIMEOUT_MS;
  const retryStatuses = opts.retryStatuses ?? DEFAULT_RETRY_STATUSES;

  const headers: Record<string, string> = { ...(opts.headers ?? {}) };
  if (opts.userAgent && !("user-agent" in lowercaseKeys(headers))) {
    headers["User-Agent"] = opts.userAgent;
  }

  let lastError: unknown = null;

  for (let attempt = 0; attempt < maxRetries; attempt++) {
    const attemptController = new AbortController();
    const timeoutHandle = setTimeout(() => attemptController.abort(), timeoutMs);
    const onParentAbort = () => attemptController.abort();
    if (opts.signal) {
      if (opts.signal.aborted) {
        clearTimeout(timeoutHandle);
        throw new DOMException("Aborted", "AbortError");
      }
      opts.signal.addEventListener("abort", onParentAbort, { once: true });
    }

    try {
      const init: RequestInit = {
        method: opts.method ?? "GET",
        headers,
        signal: attemptController.signal,
      };
      if (opts.body !== undefined && opts.body !== null) {
        init.body = opts.body;
      }
      const response = await fetch(url, init);

      if (response.status === 404) {
        throw new NotFoundError(`HTTP 404 for ${url}`);
      }

      if (retryStatuses.has(response.status)) {
        const retryAfterHeader = parseRetryAfter(response.headers.get("retry-after"));
        if (attempt < maxRetries - 1) {
          const jitter = baseDelay * 2 ** attempt * Math.random() * 0.25;
          const delayMs = baseDelay * 2 ** attempt + jitter;
          // RFC 7231 §7.1.3: prefer caller's Retry-After when present.
          const sleepMs = retryAfterHeader !== null ? retryAfterHeader * 1000 : delayMs;
          await sleep(sleepMs, opts.signal);
          continue;
        }
        throwForNonRetryableStatus(response.status, url, retryAfterHeader);
      }

      if (response.status >= 400) {
        const retryAfterHeader = parseRetryAfter(response.headers.get("retry-after"));
        throwForNonRetryableStatus(response.status, url, retryAfterHeader);
      }

      return response;
    } catch (err) {
      // Preserve TherminalError subclasses unchanged (don't retry permanent
      // 4xx errors). Retry network/transport errors and AbortError from the
      // per-attempt timeout only — caller-provided signal abort is fatal.
      if (
        err instanceof TherminalError &&
        !(err instanceof ServerError) &&
        !(err instanceof RateLimitError)
      ) {
        throw err;
      }
      if (opts.signal?.aborted) {
        throw err;
      }
      lastError = err;
      if (attempt < maxRetries - 1) {
        const jitter = baseDelay * 2 ** attempt * Math.random() * 0.25;
        const delayMs = baseDelay * 2 ** attempt + jitter;
        await sleep(delayMs, opts.signal);
        continue;
      }
      // Retry budget exhausted — propagate.
      if (err instanceof TherminalError) throw err;
      throw new TherminalError(`fetch failed after ${maxRetries} attempts: ${describeError(err)}`, {
        source: url,
      });
    } finally {
      clearTimeout(timeoutHandle);
      opts.signal?.removeEventListener("abort", onParentAbort);
    }
  }

  // Unreachable in practice — the loop either returns or throws each
  // iteration, but TS can't prove it.
  /* istanbul ignore next */
  if (lastError instanceof Error) throw lastError;
  /* istanbul ignore next */
  throw new TherminalError(`fetch failed: ${describeError(lastError)}`, { source: url });
}

function describeError(err: unknown): string {
  if (err instanceof Error) return err.message;
  return String(err);
}

function lowercaseKeys(obj: Record<string, string>): Record<string, string> {
  const out: Record<string, string> = {};
  for (const k of Object.keys(obj)) {
    out[k.toLowerCase()] = obj[k] as string;
  }
  return out;
}

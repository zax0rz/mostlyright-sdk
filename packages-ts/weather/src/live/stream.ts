// Phase 11 — `stream()` async generator.
//
// Mirrors Python `tradewinds.live.stream`. Continuous poll loop over a
// single source. Yields each fresh observation exactly once (dedup by
// `observed_at`), then sleeps for the polite-floor cadence.
//
// Cancellation: callers can `break` out of `for await` or call `.return()`
// on the iterator. The polite-floor sleep uses an abortable Promise so the
// loop terminates promptly rather than waiting out the full cadence.

import { fetchLatest, pickMostRecent } from "./_fetch.js";
import {
  type LiveSource,
  validatePollSeconds,
  validateSource,
} from "./sources.js";
import type { LiveObservation } from "./types.js";

export interface StreamOptions {
  /**
   * Live source to poll. `"awc"` (default) or `"iem"`. Case-insensitive.
   */
  readonly source?: LiveSource | string | null;

  /**
   * Override the polite-floor cadence. Must be `>=` the per-source floor
   * (AWC=30, IEM=60). When omitted, uses the floor for the active source.
   */
  readonly pollSeconds?: number | null;

  /**
   * Optional `AbortSignal` for clean cancellation. When fired, the current
   * polite-floor sleep is interrupted and the generator returns. The current
   * in-flight fetch (if any) is allowed to complete — `AbortSignal` is not
   * threaded into the underlying fetchers (yet) since the v0.14.1 fetchers
   * are synchronous and wrapped via the platform fetch.
   */
  readonly signal?: AbortSignal;
}

/** Abortable sleep helper — rejects-as-return on `signal`. */
async function sleep(ms: number, signal: AbortSignal | undefined): Promise<void> {
  if (signal?.aborted) return;
  await new Promise<void>((resolve) => {
    const t = setTimeout(resolve, ms);
    signal?.addEventListener(
      "abort",
      () => {
        clearTimeout(t);
        resolve();
      },
      { once: true },
    );
  });
}

/**
 * Yield fresh observations for `station` from a SINGLE source on a
 * polite-floor cadence.
 *
 * The loop:
 *  1. Validate `source` + `pollSeconds` (throws BEFORE first poll).
 *  2. Poll once.
 *  3. If the most-recent observation's `observed_at` differs from the last
 *     one yielded, yield it. Otherwise skip (dedup).
 *  4. `await sleep(pollSeconds)`.
 *  5. Loop.
 *
 * Empty responses (network error, fetcher returned `[]`) DO NOT abort the
 * stream — they're treated as "nothing fresh yet" and the loop continues
 * after the polite-floor sleep. To get a single-shot failure path, use
 * {@link latest}.
 *
 * @throws `Error` BEFORE the first poll when `opts.source` is unsupported
 *   or `opts.pollSeconds` is below the polite floor.
 */
export async function* stream(
  station: string,
  opts: StreamOptions = {},
): AsyncGenerator<LiveObservation> {
  const src: LiveSource = validateSource(opts.source ?? undefined);
  const cadenceS = validatePollSeconds(opts.pollSeconds ?? undefined, src);
  const cadenceMs = cadenceS * 1000;
  let lastObservedAt: string | null = null;

  while (true) {
    if (opts.signal?.aborted) return;
    let rows: LiveObservation[] = [];
    try {
      rows = await fetchLatest(station, src);
    } catch {
      // Fetcher errors must NOT abort the stream — wait for the next tick.
      // (We deliberately don't log here; the underlying fetchers already
      // log their own failures and a `console.error` from the SDK would
      // spam browser consoles.)
      rows = [];
    }
    const picked = pickMostRecent(rows);
    if (picked !== null) {
      const current = picked.observed_at;
      if (current && current !== lastObservedAt) {
        lastObservedAt = current;
        yield picked;
      }
    }
    if (opts.signal?.aborted) return;
    await sleep(cadenceMs, opts.signal);
  }
}

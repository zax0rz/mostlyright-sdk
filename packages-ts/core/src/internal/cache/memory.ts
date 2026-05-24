// MemoryStore — Map-backed CacheStore for ephemeral runtimes (Cloudflare
// Workers, jsdom test envs without persistence). NOT shared across
// processes — per-instance state.
//
// Value isolation via `structuredClone`: callers can mutate stored objects
// after `.set()` without leaking changes back. Honors ttlMs with lazy
// eviction at `.get()` time.
//
// withLock uses a per-key promise chain — pending lock-acquisitions queue
// behind the current holder and run in FIFO order on settle.

import type { CacheEntry, CacheSetOptions, CacheStore } from "./types.js";

/**
 * In-memory cache. Per-instance state; two MemoryStore instances do NOT
 * share state.
 *
 * - Values cloned via `structuredClone` so post-`set` mutation can't leak.
 * - ttlMs honored with lazy eviction on `get`.
 * - withLock serializes nested calls via a per-key promise chain.
 */
export class MemoryStore implements CacheStore {
  readonly #entries = new Map<string, CacheEntry<unknown>>();
  readonly #chain = new Map<string, Promise<unknown>>();

  async get<T = unknown>(key: string): Promise<T | null> {
    const e = this.#entries.get(key);
    if (e === undefined) return null;
    if (e.expiresAt !== undefined && Date.now() >= e.expiresAt) {
      this.#entries.delete(key);
      return null;
    }
    // Defensive clone on read too — callers can't mutate stored value via
    // the returned reference either.
    return structuredClone(e.value) as T;
  }

  async set<T = unknown>(key: string, value: T, opts?: CacheSetOptions): Promise<void> {
    const cloned = structuredClone(value);
    const entry: CacheEntry<unknown> =
      opts?.ttlMs !== undefined
        ? { value: cloned, expiresAt: Date.now() + opts.ttlMs }
        : { value: cloned };
    this.#entries.set(key, entry);
  }

  async delete(key: string): Promise<void> {
    this.#entries.delete(key);
  }

  async withLock<T>(key: string, fn: () => Promise<T>): Promise<T> {
    const prev = this.#chain.get(key) ?? Promise.resolve();
    // Chain `fn` after `prev` regardless of whether `prev` resolved or
    // rejected — the lock holder's failure shouldn't poison the queue.
    const next = prev.then(
      () => fn(),
      () => fn(),
    );
    // Store an absorber as the new tail so a later prev.then() handles
    // both branches without producing an unhandled-rejection warning. The
    // caller still receives the original `next` promise (including any
    // rejection from `fn`).
    const absorbed = next.then(
      () => undefined,
      () => undefined,
    );
    this.#chain.set(key, absorbed);
    absorbed.finally(() => {
      if (this.#chain.get(key) === absorbed) {
        this.#chain.delete(key);
      }
    });
    return next;
  }
}

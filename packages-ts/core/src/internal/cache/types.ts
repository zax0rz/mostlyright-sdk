// CacheStore — pluggable key/value contract for the @tradewinds/core cache
// layer. Three concrete implementations land in TS-W3:
//   - MemoryStore — Map-backed, no persistence (Cloudflare Workers default).
//   - FsStore — node:fs/promises + proper-lockfile (Node default).
//   - IndexedDBStore — idb + Web Locks API (browser; plan 02).
//
// `defaultCacheStore()` (plan 02) auto-detects at runtime per
// TS-SDK-DESIGN §5.4.

/** Cache entry envelope with optional TTL. */
export interface CacheEntry<T = unknown> {
  readonly value: T;
  /** Epoch ms when the entry expires. Absence = no expiry. */
  readonly expiresAt?: number;
}

/** Optional setters for cache writes. */
export interface CacheSetOptions {
  /** Time-to-live in milliseconds. Implementations may honor or ignore. */
  readonly ttlMs?: number;
}

/**
 * Pluggable key/value cache contract used throughout the SDK.
 *
 * All methods are async — concrete implementations may resolve immediately
 * (MemoryStore) or do I/O (FsStore / IndexedDBStore).
 *
 * Semantic contract:
 *   - `get<T>(key)` returns the stored value or `null` on miss. NEVER throws
 *     on miss.
 *   - `set<T>(key, value, opts?)` overwrites. ttlMs is implementation-honored
 *     (MemoryStore + IndexedDBStore honor it; FsStore ignores in v0.1).
 *   - `delete(key)` is a no-op on miss; returns void.
 *   - `withLock<T>(key, fn)` runs `fn` under a key-scoped exclusive lock and
 *     releases on settle (resolve OR throw). Nested calls to the same key
 *     serialize; calls to different keys MAY run in parallel.
 */
export interface CacheStore {
  get<T = unknown>(key: string): Promise<T | null>;
  set<T = unknown>(key: string, value: T, opts?: CacheSetOptions): Promise<void>;
  delete(key: string): Promise<void>;
  withLock<T>(key: string, fn: () => Promise<T>): Promise<T>;
}

/**
 * Canonical lock identifier for a given cache key.
 *
 * Pure — same key → same lock id. Used by FsStore (proper-lockfile sidecar)
 * and IndexedDBStore (`navigator.locks.request(...)` name).
 */
export function lockKeyFor(key: string): string {
  return `tradewinds:cache:lock:${key}`;
}

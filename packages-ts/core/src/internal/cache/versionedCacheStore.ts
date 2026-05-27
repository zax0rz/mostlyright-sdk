// versionedCacheStore — Phase 21 21-03.
//
// Schema-version invariant for the TS cache, matching Python's Phase 18
// 18-08 invariant. Wraps any underlying CacheStore so reads with a stale
// `_cache_schema_version` field return null (cache miss → re-fetch),
// matching the parquet-metadata-based invariant on the Python side.
//
// Before: TS cache was generic key/value with no version stamping. After
// Phase 18 lifted the ASOS integer-°F precision fix, pre-Phase-18 user
// caches (with 0.06°F float values) would silently return stale values
// on next call instead of re-fetching. Python embeds the version into
// parquet metadata (pyarrow `kv_metadata`); TS embeds it as a sidecar
// field in the stored JSON value.
//
// Wire-up: `defaultCacheStore()` wraps each concrete store
// (IndexedDBStore / FsStore / MemoryStore) via this adapter so consumers
// see the same `CacheStore` interface. The version wrap/unwrap is
// invisible from the caller's perspective.
//
// Bump `CACHE_SCHEMA_VERSION` in `./types.ts` when the next cache-shape
// change ships; existing cached values silently invalidate.

import type { CacheEntry, CacheSetOptions, CacheStore } from "./types.js";

/** Sentinel field name embedded in every cached value. */
const VERSION_FIELD = "_cache_schema_version" as const;

/** Wrapper shape stored under each key. */
export interface VersionedEntry<T = unknown> {
  readonly value: T;
  readonly _cache_schema_version: string;
}

function isVersionedEntry(v: unknown): v is VersionedEntry<unknown> {
  if (v === null || typeof v !== "object") return false;
  if (!(VERSION_FIELD in (v as Record<string, unknown>))) return false;
  return typeof (v as Record<string, unknown>)[VERSION_FIELD] === "string";
}

// Optional extension surface — some concrete stores (MemoryStore,
// IndexedDBStore) expose `listKeys(prefix)` beyond the CacheStore
// contract. The adapter forwards it transparently when present so
// `availability()` and friends keep working.
interface ListKeysCapable {
  listKeys(prefix: string): Promise<ReadonlyArray<string>>;
}

function hasListKeys(s: CacheStore): s is CacheStore & ListKeysCapable {
  return typeof (s as Partial<ListKeysCapable>).listKeys === "function";
}

class VersionedCacheStore implements CacheStore, ListKeysCapable {
  readonly #inner: CacheStore;
  readonly #version: string;

  constructor(inner: CacheStore, version: string) {
    if (typeof version !== "string" || version.length === 0) {
      throw new TypeError("versionedCacheStore: version must be a non-empty string");
    }
    this.#inner = inner;
    this.#version = version;
  }

  /**
   * Test/diagnostics seam: return the underlying store so tests can assert
   * which concrete backend `defaultCacheStore()` selected. NOT a production
   * API — production code MUST use the wrapped store so version
   * invalidation fires on stale reads.
   *
   * @internal
   */
  __peekInner(): CacheStore {
    return this.#inner;
  }

  async get<T = unknown>(key: string): Promise<T | null> {
    const raw = await this.#inner.get<unknown>(key);
    if (raw === null) return null;
    if (!isVersionedEntry(raw)) {
      // Pre-21-03 cache entry (no version wrapper). Treat as miss; caller
      // will re-fetch with the new wrapper on the next set.
      return null;
    }
    if (raw._cache_schema_version !== this.#version) {
      // Mismatched schema version — stale. Treat as miss.
      return null;
    }
    return raw.value as T;
  }

  async set<T = unknown>(key: string, value: T, opts?: CacheSetOptions): Promise<void> {
    const wrapped: VersionedEntry<T> = {
      value,
      [VERSION_FIELD]: this.#version,
    } as VersionedEntry<T>;
    await this.#inner.set(key, wrapped, opts);
  }

  async delete(key: string): Promise<void> {
    await this.#inner.delete(key);
  }

  async withLock<T>(key: string, fn: () => Promise<T>): Promise<T> {
    return this.#inner.withLock(key, fn);
  }

  async listKeys(prefix: string): Promise<ReadonlyArray<string>> {
    if (hasListKeys(this.#inner)) {
      return this.#inner.listKeys(prefix);
    }
    return Object.freeze([]);
  }
}

/**
 * Wrap any CacheStore so reads validate `_cache_schema_version` and
 * writes embed it. The wrapper is transparent — callers continue to use
 * the same `CacheStore` interface.
 *
 * @param inner   underlying store (MemoryStore / IndexedDBStore / FsStore)
 * @param version the schema version to embed; non-matching reads miss
 */
export function versionedCacheStore(inner: CacheStore, version: string): CacheStore {
  return new VersionedCacheStore(inner, version);
}

// Re-export the canonical version constant alongside the adapter — the
// constant lives in `./types.ts` (single source of truth) but is
// surfaced here too so callers writing
// `versionedCacheStore(inner, CACHE_SCHEMA_VERSION)` import both from
// the same module.
export { CACHE_SCHEMA_VERSION } from "./types.js";

/**
 * Internal helper for tests + diagnostics: expose the raw envelope shape
 * so callers can pre-seed an underlying store with the wrapped shape
 * without round-tripping through this adapter.
 */
export function wrapForCache<T>(value: T, version: string): VersionedEntry<T> {
  return { value, [VERSION_FIELD]: version } as VersionedEntry<T>;
}

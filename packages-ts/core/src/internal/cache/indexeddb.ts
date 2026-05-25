// IndexedDBStore — idb + Web Locks API CacheStore for browsers.
//
// Per TS-CACHE-02, the canonical IndexedDB DB name is `mostlyright-cache-v1`.
// Object store: `entries`. Schema: key = string, value = CacheEntry<T>.
//
// withLock prefers `navigator.locks.request(name, ...)` (Web Locks API,
// Chrome 69+, Firefox 96+, Safari 15.4+; all production-browser baselines).
// When `navigator.locks` is unavailable (jsdom default), falls back to the
// same per-key in-process promise chain used by MemoryStore / FsStore —
// edge runtimes (Workers without web-locks polyfills) get the in-process
// guarantee at least.
//
// ttlMs is honored via lazy eviction at `get` time (matches FsStore).

import { type IDBPDatabase, openDB } from "idb";

import type { CacheEntry, CacheSetOptions, CacheStore } from "./types.js";
import { lockKeyFor } from "./types.js";

/** Canonical DB name. Re-exported via the cache barrel. */
export const DB_NAME = "mostlyright-cache-v1";

const STORE_NAME = "entries";
const SCHEMA_VERSION = 1;

export interface IndexedDBStoreOptions {
  /** Override the DB name. Tests pass unique values per case so they don't pollute each other. */
  readonly dbName?: string;
}

interface WebLocksApi {
  request: <T>(
    name: string,
    options: { mode: "exclusive" },
    fn: () => Promise<T> | T,
  ) => Promise<T>;
}

function getWebLocks(): WebLocksApi | null {
  if (typeof navigator === "undefined") return null;
  const nav = navigator as unknown as { locks?: WebLocksApi };
  return nav.locks ?? null;
}

/**
 * Browser CacheStore backed by IndexedDB (via idb) + Web Locks API.
 *
 * When `navigator.locks` is unavailable (jsdom, edge runtimes without
 * Web Locks), falls back to a per-key in-process promise chain.
 */
export class IndexedDBStore implements CacheStore {
  readonly #dbName: string;
  readonly #dbPromise: Promise<IDBPDatabase>;
  readonly #chain = new Map<string, Promise<unknown>>();

  constructor(opts: IndexedDBStoreOptions = {}) {
    this.#dbName = opts.dbName ?? DB_NAME;
    this.#dbPromise = openDB(this.#dbName, SCHEMA_VERSION, {
      upgrade(db) {
        if (!db.objectStoreNames.contains(STORE_NAME)) {
          db.createObjectStore(STORE_NAME);
        }
      },
    });
  }

  async get<T = unknown>(key: string): Promise<T | null> {
    const db = await this.#dbPromise;
    const entry = (await db.get(STORE_NAME, key)) as CacheEntry<T> | undefined;
    if (entry === undefined) return null;
    if (entry.expiresAt !== undefined && Date.now() >= entry.expiresAt) {
      // Lazy-evict — best-effort; ignore failures.
      try {
        await db.delete(STORE_NAME, key);
      } catch {
        // ignore
      }
      return null;
    }
    return entry.value as T;
  }

  async set<T = unknown>(key: string, value: T, opts?: CacheSetOptions): Promise<void> {
    const db = await this.#dbPromise;
    const entry: CacheEntry<T> =
      opts?.ttlMs !== undefined ? { value, expiresAt: Date.now() + opts.ttlMs } : { value };
    await db.put(STORE_NAME, entry, key);
  }

  async delete(key: string): Promise<void> {
    const db = await this.#dbPromise;
    await db.delete(STORE_NAME, key);
  }

  /**
   * Enumerate keys with the given prefix using IndexedDB's bounded range
   * query. Live keys only — expired entries are lazy-evicted on read by
   * `get()`, so a stale-but-not-yet-evicted entry can appear here; callers
   * who care about expiration should `get()` to confirm.
   *
   * TS-W6 Wave 1: `availability()` uses this to count observation months and
   * climate years for a station.
   */
  async listKeys(prefix: string): Promise<ReadonlyArray<string>> {
    const db = await this.#dbPromise;
    // Build an inclusive lower bound and an exclusive upper bound using the
    // next-codepoint trick. IndexedDB's IDBKeyRange handles string ordering
    // by UTF-16 code units, which matches JS string comparison; we use the
    // Unicode max-codepoint as the upper sentinel so any key starting with
    // `prefix` lands inside the range.
    const range = IDBKeyRange.bound(prefix, `${prefix}￿`, false, false);
    const keys = (await db.getAllKeys(STORE_NAME, range)) as IDBValidKey[];
    const out: string[] = [];
    for (const k of keys) {
      if (typeof k === "string" && k.startsWith(prefix)) {
        out.push(k);
      }
    }
    return Object.freeze(out);
  }

  async withLock<T>(key: string, fn: () => Promise<T>): Promise<T> {
    const locks = getWebLocks();
    if (locks !== null) {
      // Web Locks API — production-browser path. Cross-tab safe.
      return locks.request<T>(lockKeyFor(key), { mode: "exclusive" }, () => fn());
    }
    // Fallback for jsdom / edge runtimes without navigator.locks: in-process
    // per-key promise chain (FIFO; matches MemoryStore semantics).
    const prev = this.#chain.get(key) ?? Promise.resolve();
    const next = prev.then(
      () => fn(),
      () => fn(),
    );
    const absorbed = next.then(
      () => undefined,
      () => undefined,
    );
    this.#chain.set(key, absorbed);
    absorbed.finally(() => {
      if (this.#chain.get(key) === absorbed) this.#chain.delete(key);
    });
    return next;
  }
}

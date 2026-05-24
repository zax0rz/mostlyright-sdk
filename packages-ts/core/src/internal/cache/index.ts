// Barrel for @tradewinds/core/internal/cache.
//
// Plan 01: types + MemoryStore + FsStore.
// Plan 02: IndexedDBStore + defaultCacheStore (runtime auto-detect).
// Plan 03: skip-rule predicates + key generators.

export type { CacheStore, CacheSetOptions, CacheEntry } from "./types.js";
export { lockKeyFor } from "./types.js";
export { MemoryStore } from "./memory.js";
export { FsStore, defaultFsRoot } from "./fs.js";
export type { FsStoreOptions } from "./fs.js";
export { IndexedDBStore, DB_NAME as INDEXEDDB_DB_NAME } from "./indexeddb.js";
export type { IndexedDBStoreOptions } from "./indexeddb.js";
export { defaultCacheStore } from "./default.js";
export {
  shouldSkipCacheForCurrentLstMonth,
  shouldSkipCacheForCurrentLstYear,
  isLiveSource,
  isWithinVolatileWindow,
} from "./skip-rules.js";
export { cacheKeyForObservations, cacheKeyForClimate } from "./keys.js";

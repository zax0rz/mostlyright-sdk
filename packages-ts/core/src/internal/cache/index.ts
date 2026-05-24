// Barrel for @tradewinds/core/internal/cache.
//
// Plan 01: types + MemoryStore + FsStore.
// Plan 02: IndexedDBStore + defaultCacheStore (runtime auto-detect).
// Plan 03: skip-rule predicates + key generators.
//
// Iter-2 H5: `FsStore` / `defaultFsRoot` / `FsStoreOptions` are NOT
// re-exported here. tsup hoisted them into a sibling chunk that the
// subbundle top-level-imported (transitively pulling `node:fs/promises`,
// `node:os`, `node:path`, `proper-lockfile`, `node:crypto` into MV3
// service-worker bundles), even though `defaultCacheStore` itself uses
// a dynamic `import('./fs.js')` per iter-1 H3. Node-only consumers
// (FsStore unit tests + downstream Node users) MUST import from the
// dedicated subpath `@tradewinds/core/internal/cache/fs`.

export type { CacheStore, CacheSetOptions, CacheEntry } from "./types.js";
export { lockKeyFor } from "./types.js";
export { MemoryStore } from "./memory.js";
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

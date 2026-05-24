// Barrel for @tradewinds/core/internal/cache — TS-W3 Plan 01 baseline.
//
// Plan 02 extends with IndexedDBStore + defaultCacheStore.
// Plan 03 extends with skip-rule predicates + key generators.

export type { CacheStore, CacheSetOptions, CacheEntry } from "./types.js";
export { lockKeyFor } from "./types.js";
export { MemoryStore } from "./memory.js";
export { FsStore, defaultFsRoot } from "./fs.js";
export type { FsStoreOptions } from "./fs.js";

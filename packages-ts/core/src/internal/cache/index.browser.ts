// Browser/MV3 entry for @tradewinds/core/internal/cache.
//
// Iter-8 H15: the iter-1/iter-2 fixes (dynamic `await import('./fs.js')`
// behind a runtime feature-detect + dropping the FsStore re-export from
// the barrel) eliminated STATIC references to FsStore from the cache
// subbundle but NOT dynamic ones. esbuild, when bundling for browser/MV3
// targets, still follows `await import("./fs.js")` from `default.ts`
// into the FsStore chunk and pulls `node:crypto`, `node:fs/promises`,
// `node:os`, `node:path`, and `proper-lockfile` into the bundle —
// breaking `pnpm size` for `packages-ts/meta/dist/index.mjs`.
//
// The architectural fix: package.json conditional exports route Node
// consumers to `./index.ts` (this file's sibling — keeps FsStore via
// dynamic import) and browser/MV3 consumers to THIS file. This file has
// NO reference to `./fs.js` via ANY mechanism — static import, dynamic
// import, or re-export. esbuild cannot follow what isn't there.
//
// Exports MUST mirror `index.ts` exactly, MINUS anything that references
// FsStore. The runtime priority for `defaultCacheStore` here is:
//   1. `typeof indexedDB !== "undefined"` → IndexedDBStore.
//   2. else → MemoryStore.
// (The FsStore branch is unreachable in browser/MV3 bundles by
// construction — there's no `process.versions?.node` in a service
// worker anyway, but more importantly the source code is absent so
// esbuild's static analysis cannot drag the Node-only chunk in.)

import { IndexedDBStore } from "./indexeddb.js";
import { MemoryStore } from "./memory.js";
import type { CacheStore } from "./types.js";

export type { CacheStore, CacheSetOptions, CacheEntry } from "./types.js";
export { lockKeyFor } from "./types.js";
export { MemoryStore } from "./memory.js";
export { IndexedDBStore, DB_NAME as INDEXEDDB_DB_NAME } from "./indexeddb.js";
export type { IndexedDBStoreOptions } from "./indexeddb.js";
export {
  shouldSkipCacheForCurrentLstMonth,
  shouldSkipCacheForCurrentLstYear,
  isLiveSource,
  isWithinVolatileWindow,
  isWritableMonth,
  isWritableYear,
} from "./skip-rules.js";
export { cacheKeyForObservations, cacheKeyForClimate } from "./keys.js";

/**
 * Browser/MV3 variant of {@link defaultCacheStore}. Auto-detects the best
 * available CacheStore in a browser/edge environment:
 *
 *   1. IndexedDB present → {@link IndexedDBStore}
 *   2. else → {@link MemoryStore}
 *
 * Returns a NEW instance per call.
 *
 * Iter-8 H15: kept async so the signature matches the Node entry's
 * `defaultCacheStore` (which awaits a dynamic import). Callers that
 * `await defaultCacheStore()` work unchanged when the package.json
 * conditional exports flip them between entries.
 */
export async function defaultCacheStore(): Promise<CacheStore> {
  if (typeof indexedDB !== "undefined") return new IndexedDBStore();
  return new MemoryStore();
}

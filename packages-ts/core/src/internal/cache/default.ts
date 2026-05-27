// defaultCacheStore — runtime auto-detection per TS-SDK-DESIGN §5.4.
//
// Priority order (fixed, deterministic):
//   1. `typeof indexedDB !== "undefined"` → IndexedDBStore (browser)
//   2. `typeof process !== "undefined" && process.versions?.node` → FsStore
//      (Node, loaded via `await import('./fs.js')`)
//   3. else → MemoryStore (Workers / edge / unknown)
//
// Iter-1 H3: `FsStore` is NO longer statically imported here. It
// top-level-imports `node:fs/promises`, `node:os`, `node:path`, and
// `proper-lockfile`, which would pull all four into any MV3 / browser /
// edge bundle that touches `@mostlyrightmd/core/internal/cache` — even via
// the IndexedDB code path. The dynamic `await import('./fs.js')` behind
// a `process.versions?.node` runtime feature-detect ensures bundlers
// can statically prove the FsStore subgraph is unreachable from the
// browser entry, eliminating the Node-only-deps edge.
//
// Function is async because dynamic import returns a Promise. Callers
// (research() and friends) already operate inside async code paths.

import { IndexedDBStore } from "./indexeddb.js";
import { MemoryStore } from "./memory.js";
import { CACHE_SCHEMA_VERSION, type CacheStore } from "./types.js";
import { versionedCacheStore } from "./versionedCacheStore.js";

/**
 * Auto-detect the best CacheStore for the current runtime.
 *
 * Returns a NEW instance per call.
 *
 * Phase 21 21-03 (iter-1 fix per codex + ts-architect CRITICAL): the
 * concrete store is wrapped in `versionedCacheStore(CACHE_SCHEMA_VERSION)`
 * so pre-Phase-18 cache entries (no version sidecar, or wrong version)
 * silently miss instead of returning stale `0.06°F`-precision rows. The
 * wrap is transparent — callers see the same `CacheStore` interface.
 *
 * @returns a Promise resolving to a fresh CacheStore (wrapped). The
 *   Node-only `FsStore` is loaded via dynamic import behind a runtime
 *   feature detect, so browser / MV3 / edge bundles never pull
 *   `node:fs/promises` et al. (iter-1 H3 fix).
 */
export async function defaultCacheStore(): Promise<CacheStore> {
  const inner = await pickConcreteStore();
  return versionedCacheStore(inner, CACHE_SCHEMA_VERSION);
}

async function pickConcreteStore(): Promise<CacheStore> {
  if (typeof indexedDB !== "undefined") return new IndexedDBStore();
  if (
    typeof process !== "undefined" &&
    typeof process.versions === "object" &&
    process.versions !== null &&
    typeof process.versions.node === "string"
  ) {
    // Dynamic import keeps `./fs.js` (and its `node:fs/promises`,
    // `node:os`, `node:path`, `proper-lockfile` chain) out of the
    // browser bundle. Bundlers that support code-splitting will emit
    // a separate chunk; bundlers targeting `browser` resolution skip
    // the chunk entirely when the feature-detect short-circuits.
    const { FsStore } = await import("./fs.js");
    return new FsStore();
  }
  return new MemoryStore();
}

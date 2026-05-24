// defaultCacheStore — runtime auto-detection per TS-SDK-DESIGN §5.4.
//
// Priority order (fixed, deterministic):
//   1. `typeof indexedDB !== "undefined"` → IndexedDBStore (browser)
//   2. `typeof process !== "undefined" && process.versions?.node` → FsStore
//      (Node)
//   3. else → MemoryStore (Workers / edge / unknown)
//
// Pure function — no caching, no module-level state. Each call returns a
// NEW instance. Callers wanting a singleton wrap the result themselves.
//
// NO top-level imports of side-effect modules. All three constructors are
// imported statically (no dynamic imports) — bundlers tree-shake unused
// implementations away if the consumer ships only one runtime.

import { FsStore } from "./fs.js";
import { IndexedDBStore } from "./indexeddb.js";
import { MemoryStore } from "./memory.js";
import type { CacheStore } from "./types.js";

/**
 * Auto-detect the best CacheStore for the current runtime.
 *
 * Returns a NEW instance per call.
 */
export function defaultCacheStore(): CacheStore {
  if (typeof indexedDB !== "undefined") return new IndexedDBStore();
  if (
    typeof process !== "undefined" &&
    typeof process.versions === "object" &&
    process.versions !== null &&
    typeof process.versions.node === "string"
  ) {
    return new FsStore();
  }
  return new MemoryStore();
}

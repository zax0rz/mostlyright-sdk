// Node-only subpath entry for @tradewinds/core/internal/cache/fs.
//
// Iter-2 H5: FsStore + defaultFsRoot were removed from the cache
// barrel (`./internal/cache/index.ts`) because the re-export pulled
// `node:fs/promises`, `node:os`, `node:path`, `node:crypto`,
// `proper-lockfile` into the browser-facing cache subbundle (even
// though `defaultCacheStore` uses dynamic `import('./fs.js')`).
// This dedicated subpath exists so Node-side consumers (FsStore unit
// tests + downstream callers who explicitly want a filesystem store)
// can import FsStore without dragging the whole cache barrel into a
// browser bundle.
//
// Package.json maps `@tradewinds/core/internal/cache/fs` → this file.
// tsup config emits it as a sibling dist entry (`dist/internal/cache/
// fs.{mjs,cjs}`); the cache subbundle has no static import to this
// file, so tree-shaking keeps Node imports out of MV3 bundles.

export { FsStore, defaultFsRoot } from "./fs.js";
export type { FsStoreOptions } from "./fs.js";

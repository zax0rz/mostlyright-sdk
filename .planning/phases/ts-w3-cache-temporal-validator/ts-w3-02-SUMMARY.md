---
phase: ts-w3-cache-temporal-validator
plan: 02
subsystem: internal/cache
tags: [indexeddb, web-locks, jsdom, fake-indexeddb, default-cache-store]
status: complete
commits:
  - 7aa687f feat(ts-w3/02): IndexedDBStore + defaultCacheStore + jsdom routing
test_delta: +19 (15 indexeddb + 4 default)
---

# TS-W3 Plan 02: Browser Cache + Auto-Detect Summary

Adds the browser-side CacheStore + runtime auto-detection.

## What shipped
- `indexeddb.ts` — IndexedDBStore (`idb`-wrapped, DB name
  `tradewinds-cache-v1`, exclusive Web Locks API for cross-tab safety,
  per-key promise-chain fallback for jsdom/edge runtimes without
  navigator.locks).
- `default.ts` — `defaultCacheStore()` priority: indexedDB → process →
  Memory.
- Barrel updated to export IndexedDBStore, INDEXEDDB_DB_NAME,
  defaultCacheStore.
- Vitest config: environmentMatchGlobs routes indexeddb.test.ts +
  default.test.ts through jsdom; setupFiles polyfills IndexedDB via
  fake-indexeddb/auto.

## Key decisions
- **Real setTimeout for IDB ttlMs test:** fake-indexeddb's microtask
  scheduling stalls under `vi.useFakeTimers()`. Tests use real sleep
  (10ms ttl + 50ms wait).
- **Unique dbName per test:** randomUUID-derived names prevent
  cross-test pollution within a worker.
- **No top-level side effects in default.ts:** static imports of all
  three Store classes; tree-shakers prune unused branches.

## Test delta
Core: 295 → 314 (+19).

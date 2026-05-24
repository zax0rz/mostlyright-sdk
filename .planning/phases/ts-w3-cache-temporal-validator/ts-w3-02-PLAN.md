---
phase: ts-w3-cache-temporal-validator
plan: 02
type: execute
wave: 2
depends_on:
  - ts-w3-01
files_modified:
  - packages-ts/core/src/internal/cache/indexeddb.ts
  - packages-ts/core/src/internal/cache/default.ts
  - packages-ts/core/src/internal/cache/index.ts
  - packages-ts/core/package.json
  - packages-ts/core/vitest.config.ts
  - packages-ts/core/tests/internal/cache/indexeddb.test.ts
  - packages-ts/core/tests/internal/cache/default.test.ts
autonomous: true
requirements:
  - TS-CACHE-01
must_haves:
  truths:
    - "IndexedDBStore implementation passes the shared CacheStore contract test suite under jsdom"
    - "IndexedDBStore.withLock uses navigator.locks.request (Web Locks API), with a serialized-microtask fallback when navigator.locks is unavailable (jsdom)"
    - "defaultCacheStore() returns IndexedDBStore when typeof indexedDB !== 'undefined'"
    - "defaultCacheStore() returns FsStore when typeof process !== 'undefined' && process.versions?.node and indexedDB is undefined"
    - "defaultCacheStore() returns MemoryStore otherwise (Workers/edge runtimes)"
  artifacts:
    - path: packages-ts/core/src/internal/cache/indexeddb.ts
      provides: "IndexedDBStore — idb + Web Locks API CacheStore for browsers"
    - path: packages-ts/core/src/internal/cache/default.ts
      provides: "defaultCacheStore() — runtime auto-detection"
    - path: packages-ts/core/src/internal/cache/index.ts
      provides: "Barrel re-exports — now includes IndexedDBStore + defaultCacheStore"
  key_links:
    - from: packages-ts/core/vitest.config.ts
      to: "jsdom environment"
      via: "environmentMatchGlobs (jsdom for *.dom.test.ts; node default)"
      pattern: "environmentMatchGlobs|environment.*jsdom"
---

<objective>
Add the browser-side `IndexedDBStore` (via `idb`) + Web Locks API integration, then wire `defaultCacheStore()` to auto-detect the right backend at runtime. After this wave: `pnpm test -- cache` is fully green under both Node (FsStore + MemoryStore) AND jsdom (IndexedDBStore + MemoryStore).

The runtime detection logic matches the spec in TS-SDK-DESIGN.md §5.4 exactly. No bundler magic, no top-level await — just the three `typeof` checks in deterministic priority order.
</objective>

<context_files>
- `.planning/research/TS-SDK-DESIGN.md` §5.4 lines 252-264 (auto-detection algorithm)
- `.planning/REQUIREMENTS.md` TS-CACHE-01 (IndexedDB DB name `tradewinds-cache-v1`; Web Locks API for withLock)
- `packages-ts/core/src/internal/cache/types.ts` (plan 01 — CacheStore contract)
- `packages-ts/core/tests/internal/cache/types.contract.test.ts` (plan 01 — `runCacheStoreContract`)
- `packages-ts/core/src/internal/cache/fs.ts` + `memory.ts` (plan 01 — style reference)
- [`idb` docs](https://github.com/jakearchibald/idb) — Jake Archibald's IndexedDB wrapper (~3 KB minified)
- [Web Locks API spec](https://developer.mozilla.org/docs/Web/API/Web_Locks_API) — `navigator.locks.request(name, callback)` returns whatever the callback returns; lock released on settle
</context_files>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: IndexedDBStore implementation + jsdom-aware vitest config</name>
  <files>packages-ts/core/src/internal/cache/indexeddb.ts, packages-ts/core/package.json, packages-ts/core/vitest.config.ts, packages-ts/core/tests/internal/cache/indexeddb.test.ts</files>
  <read_first>
    - `packages-ts/core/src/internal/cache/types.ts` (Task 1 of plan 01 — interface)
    - `packages-ts/core/src/internal/cache/memory.ts` + `fs.ts` (plan 01 — withLock chain pattern, ttlMs handling, structuredClone)
    - `packages-ts/core/tests/internal/cache/types.contract.test.ts` (plan 01 — `runCacheStoreContract`)
    - `packages-ts/core/vitest.config.ts` (current config — add `environmentMatchGlobs` without breaking existing Node tests)
  </read_first>
  <behavior>
    - DB name: `tradewinds-cache-v1` (frozen constant `DB_NAME`); object store: `entries`.
    - Schema: key = string (the cache key), value = `CacheEntry&lt;T&gt;` (the same envelope as MemoryStore/FsStore so cross-backend assertions hold).
    - withLock: prefer `navigator.locks.request(lockKeyFor(key), { mode: 'exclusive' }, fn)`. When `navigator.locks` is undefined (jsdom default), fall back to the per-key promise chain pattern from `MemoryStore` — documented as "test/edge fallback; production browsers have Web Locks since 2022 (Chrome 69, Firefox 96, Safari 15.4)".
    - get: lazy-evicts expired entries (same as FsStore).
    - The IDB upgrade callback ONLY runs on first DB open; subsequent opens hit the existing store. Use `idb`'s `openDB` `upgrade` hook.
    - Constructor accepts `{ dbName?: string }` override for tests (so concurrent tests don't share a real DB by default — each test creates a unique name).
  </behavior>
  <action>
    1. Add `idb` to `packages-ts/core/package.json` dependencies:
       ```json
       "dependencies": { "idb": "^8.0.0", "proper-lockfile": "^4.1.2" }
       ```
       Add `fake-indexeddb` + `jsdom` to devDependencies (for vitest under jsdom):
       ```json
       "devDependencies": { "fake-indexeddb": "^6.0.0", "jsdom": "^25.0.1", ... }
       ```
    2. Update `packages-ts/core/vitest.config.ts` to route DOM tests through jsdom while keeping Node default:
       ```typescript
       export default defineConfig({
         test: {
           include: ["tests/**/*.test.ts"],
           exclude: ["**/*.live.test.ts", "**/node_modules/**", "**/dist/**"],
           environmentMatchGlobs: [
             ["tests/internal/cache/indexeddb.test.ts", "jsdom"],
             ["tests/internal/cache/default.test.ts", "jsdom"],
           ],
           setupFiles: ["./tests/setup-fake-indexeddb.ts"],
           coverage: { /* existing block */ },
         },
       });
       ```
       Create `packages-ts/core/tests/setup-fake-indexeddb.ts`:
       ```typescript
       // Polyfill IndexedDB for jsdom. The polyfill is a no-op when run under
       // Node-only tests (typeof indexedDB stays undefined there).
       import "fake-indexeddb/auto";
       ```
    3. Implement `IndexedDBStore` in `packages-ts/core/src/internal/cache/indexeddb.ts`:
       - Module-level `DB_NAME = "tradewinds-cache-v1"` (constant; per TS-CACHE-02).
       - Module-level `STORE_NAME = "entries"`.
       - `openDB(dbName, 1, { upgrade(db) { if (!db.objectStoreNames.contains(STORE_NAME)) db.createObjectStore(STORE_NAME); } })`.
       - Constructor: `{ dbName = DB_NAME }: { dbName?: string } = {}`. Tests pass unique names per case to avoid cross-test pollution.
       - `get`: read entry; if `expiresAt && expiresAt <= Date.now()` return null and `delete(key)` (await but don't propagate delete errors — log-only).
       - `set`: store the `CacheEntry` envelope.
       - `delete`: `tx.objectStore(STORE_NAME).delete(key)`.
       - `withLock`: branch on `typeof navigator !== "undefined" && navigator.locks?.request`. If present, use the Web Locks API. Otherwise use the same per-key promise chain from `MemoryStore`. Document this fallback explicitly in the class JSDoc.
       - Document idb tree-shaking: only the `openDB` symbol is imported, keeping bundle delta minimal (~3 KB gzipped).
    4. Write `tests/internal/cache/indexeddb.test.ts`:
       - Uses `runCacheStoreContract(() =&gt; new IndexedDBStore({ dbName: \`tw-test-\${randomUUID()}\` }))`.
       - IndexedDBStore-specific tests:
         - `DB_NAME` constant equals `"tradewinds-cache-v1"`.
         - Two IndexedDBStore instances with the SAME `dbName` share state (cross-instance get sees set).
         - Two IndexedDBStore instances with DIFFERENT `dbName` are isolated.
         - withLock fallback path: when `navigator.locks` is deleted (simulated edge runtime), nested withLock still serializes via the promise chain — assert via timestamps.
         - `expiresAt` lazy eviction: set with ttlMs=1, advance time (vi.useFakeTimers), get returns null, then asserting the entry was actually deleted (next get with the same key after re-setting fresh value works).
  </action>
  <acceptance_criteria>
    - `pnpm --filter @tradewinds/core test -- indexeddb` runs and passes (contract suite + 4-5 IndexedDB-specific).
    - `grep -n 'DB_NAME = "tradewinds-cache-v1"' packages-ts/core/src/internal/cache/indexeddb.ts` confirms canonical name.
    - `grep -n "navigator.locks" packages-ts/core/src/internal/cache/indexeddb.ts` confirms Web Locks API integration.
    - `grep -n "environmentMatchGlobs" packages-ts/core/vitest.config.ts` confirms jsdom routing.
    - `pnpm --filter @tradewinds/core run typecheck` clean (jsdom + fake-indexeddb types resolved).
    - Existing tests (memory.test, fs.test, codegen, hello, bounds, snapshot, convert, exceptions, internal/http, internal/pairs, internal/merge/*) still pass under Node — i.e. the jsdom routing didn't accidentally globalize.
  </acceptance_criteria>
</task>

<task type="auto" tdd="true">
  <name>Task 2: defaultCacheStore() runtime detection + barrel re-export + tests</name>
  <files>packages-ts/core/src/internal/cache/default.ts, packages-ts/core/src/internal/cache/index.ts, packages-ts/core/tests/internal/cache/default.test.ts</files>
  <read_first>
    - `.planning/research/TS-SDK-DESIGN.md` lines 257-262 (auto-detection algorithm canonical text)
    - `packages-ts/core/src/internal/cache/indexeddb.ts` (Task 1 output)
    - `packages-ts/core/src/internal/cache/index.ts` (plan 01 barrel)
  </read_first>
  <behavior>
    - Priority order is fixed and deterministic:
      1. `typeof indexedDB !== "undefined"` → `new IndexedDBStore()`
      2. `typeof process !== "undefined" && process.versions?.node` → `new FsStore()`
      3. else → `new MemoryStore()`
    - Pure function — no caching, no module-level state. Each call returns a NEW instance (consumers wanting a singleton wrap it).
    - NO top-level imports of side-effect modules. Lazy imports OK if needed for tree-shaking but the spec doesn't require it.
  </behavior>
  <action>
    1. Implement `packages-ts/core/src/internal/cache/default.ts`:
       ```typescript
       import { FsStore } from "./fs.js";
       import { IndexedDBStore } from "./indexeddb.js";
       import { MemoryStore } from "./memory.js";
       import type { CacheStore } from "./types.js";

       /**
        * Auto-detect the best CacheStore for the current runtime.
        *
        * Priority (matches TS-SDK-DESIGN.md §5.4):
        * 1. IndexedDBStore — when `typeof indexedDB !== "undefined"` (browser).
        * 2. FsStore — when running under Node (`process.versions.node` present).
        * 3. MemoryStore — fallback for Workers / edge / unknown runtimes.
        *
        * Returns a NEW instance per call. Callers wanting a singleton must
        * cache the result themselves.
        */
       export function defaultCacheStore(): CacheStore {
         if (typeof indexedDB !== "undefined") return new IndexedDBStore();
         if (typeof process !== "undefined" && process.versions?.node) return new FsStore();
         return new MemoryStore();
       }
       ```
    2. Update `packages-ts/core/src/internal/cache/index.ts` barrel to include `IndexedDBStore` + `defaultCacheStore`:
       ```typescript
       export type { CacheStore, CacheSetOptions, CacheEntry } from "./types.js";
       export { lockKeyFor } from "./types.js";
       export { MemoryStore } from "./memory.js";
       export { FsStore, defaultFsRoot } from "./fs.js";
       export { IndexedDBStore, DB_NAME as INDEXEDDB_DB_NAME } from "./indexeddb.js";
       export { defaultCacheStore } from "./default.js";
       ```
    3. Write `tests/internal/cache/default.test.ts` (jsdom-routed — covers IndexedDB branch and the fallback branches by deleting globals):
       ```typescript
       import { describe, expect, it } from "vitest";
       import { defaultCacheStore, IndexedDBStore, FsStore, MemoryStore } from "../../../src/internal/cache/index.js";

       describe("defaultCacheStore()", () =&gt; {
         it("returns IndexedDBStore when indexedDB is present (jsdom + fake-indexeddb)", () =&gt; {
           expect(defaultCacheStore()).toBeInstanceOf(IndexedDBStore);
         });
         it("returns FsStore when indexedDB is absent and Node process is present", () =&gt; {
           const original = globalThis.indexedDB;
           // @ts-expect-error — runtime detach
           delete globalThis.indexedDB;
           try {
             expect(defaultCacheStore()).toBeInstanceOf(FsStore);
           } finally {
             globalThis.indexedDB = original;
           }
         });
         it("returns MemoryStore when neither indexedDB nor Node process is present", () =&gt; {
           const idb = globalThis.indexedDB;
           const proc = (globalThis as any).process;
           // @ts-expect-error — runtime detach
           delete globalThis.indexedDB;
           // @ts-expect-error
           delete (globalThis as any).process;
           try {
             expect(defaultCacheStore()).toBeInstanceOf(MemoryStore);
           } finally {
             globalThis.indexedDB = idb;
             (globalThis as any).process = proc;
           }
         });
         it("each call returns a NEW instance", () =&gt; {
           expect(defaultCacheStore()).not.toBe(defaultCacheStore());
         });
       });
       ```
       Note: deleting `globalThis.process` inside vitest is risky (vitest needs it). Wrap the "MemoryStore branch" assertion in a separate try/restore, or use `vi.stubGlobal`. Prefer `vi.stubGlobal` if it cleans up reliably.
  </action>
  <acceptance_criteria>
    - `pnpm --filter @tradewinds/core test -- default` runs and passes all four cases (IndexedDB, Fs, Memory, distinct-instances).
    - `grep -n "defaultCacheStore" packages-ts/core/src/internal/cache/index.ts` confirms barrel export.
    - `grep -n "IndexedDBStore" packages-ts/core/src/internal/cache/index.ts` confirms barrel export.
    - `pnpm --filter @tradewinds/core run build` emits all 5 cache modules under `dist/internal/cache/`.
    - `pnpm --filter @tradewinds/core run typecheck` clean.
    - Bundle delta check (`pnpm --filter @tradewinds/core run size-limit` if configured): cache subsystem add ≤ 6 KB (idb ~3 KB gzipped + our wrappers ~1-2 KB; proper-lockfile only loaded by fs.ts in Node).
  </acceptance_criteria>
</task>

</tasks>

<verification>
1. `pnpm --filter @tradewinds/core test -- cache` runs all 4 cache test files (memory + fs + indexeddb + default), all green.
2. `pnpm --filter @tradewinds/core run typecheck` clean.
3. `pnpm --filter @tradewinds/core run build` produces `dist/internal/cache/{types,memory,fs,indexeddb,default,index}.{mjs,cjs,d.ts}`.
4. `pnpm -r run typecheck` clean (meta + weather + markets can import `@tradewinds/core/internal/cache` without complaint).
5. Bundle-size check: confirm `idb` and `proper-lockfile` are imported only from their respective files (not from `index.ts`) so tree-shaking is clean.
</verification>

<success_criteria>
- TS-CACHE-01 fully met — all 3 concrete impls + `defaultCacheStore()` ship.
- TS-CACHE-02 partial — IndexedDB DB name `tradewinds-cache-v1` verified; FsStore root verified in plan 01; cache-skip rules land in plan 03.
- Bundle-size: `@tradewinds/core` total stays under 25 KB target (TS-BUNDLE-01) — flag in plan 03 if at risk after skip rules + key generator are layered on.
- Web Locks API used in production browsers; promise-chain fallback covers jsdom and edge runtimes.
</success_criteria>

<review_discipline>
This plan ships TypeScript-only changes under `packages-ts/core/**`. Per `.planning/REVIEW-DISCIPLINE.md`:

- **Reviewers**: codex `high` + **TypeScript Architect** (parallel dispatch).
- **Severity gate**: CRITICAL or HIGH only.
- **Loop**: fix on this branch, re-dispatch both. Cap at 3 iterations; escalate at 3.
- **Rubric calibration for this plan**:
  - CRITICAL if `IndexedDBStore` writes the raw `value` instead of the `CacheEntry` envelope (breaks ttlMs eviction and cross-backend test cassettes).
  - CRITICAL if `defaultCacheStore()` instantiation has side effects at import time (top-level `new IndexedDBStore()` would crash in Node without polyfill).
  - HIGH if `navigator.locks` branch is missing and the promise-chain fallback is the only path — production browsers deserve real Web Locks for cross-tab safety.
  - HIGH if `idb` is pulled into the meta-bundle when consumers don't use IndexedDB (verify by reading `dist/internal/cache/index.mjs` — `idb` should appear only in `indexeddb.mjs`).
  - HIGH if `vi.stubGlobal` is misused such that `process` is permanently deleted (breaks downstream test suite).
</review_discipline>

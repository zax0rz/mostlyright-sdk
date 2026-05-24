---
phase: ts-w3-cache-temporal-validator
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - packages-ts/core/src/internal/cache/types.ts
  - packages-ts/core/src/internal/cache/memory.ts
  - packages-ts/core/src/internal/cache/fs.ts
  - packages-ts/core/src/internal/cache/index.ts
  - packages-ts/core/package.json
  - packages-ts/core/tests/internal/cache/memory.test.ts
  - packages-ts/core/tests/internal/cache/fs.test.ts
  - packages-ts/core/tests/internal/cache/types.contract.test.ts
autonomous: true
requirements:
  - TS-CACHE-01
  - TS-CACHE-02
must_haves:
  truths:
    - "CacheStore interface defines get/set/delete/withLock contract"
    - "MemoryStore implementation passes the shared CacheStore contract test suite"
    - "FsStore implementation passes the shared CacheStore contract test suite under Node"
    - "FsStore root is process.env.TRADEWINDS_CACHE_DIR ?? path.join(os.homedir(), '.tradewinds', 'cache-ts')"
    - "FsStore withLock uses proper-lockfile (NOT lockfile, NOT custom .lock files)"
  artifacts:
    - path: packages-ts/core/src/internal/cache/types.ts
      provides: "CacheStore interface, CacheEntry shape, lockKeyFor() helper"
    - path: packages-ts/core/src/internal/cache/memory.ts
      provides: "MemoryStore — Map-backed CacheStore for Workers/ephemeral runtimes"
    - path: packages-ts/core/src/internal/cache/fs.ts
      provides: "FsStore — Node fs/promises + proper-lockfile CacheStore"
    - path: packages-ts/core/src/internal/cache/index.ts
      provides: "Barrel exports CacheStore + MemoryStore + FsStore (IndexedDBStore added in plan 02; defaultCacheStore in plan 02)"
  key_links:
    - from: packages-ts/core/package.json
      to: "exports['./internal/cache']"
      via: "tsup subpath build target dist/internal/cache/index.{mjs,cjs,d.ts}"
      pattern: "internal/cache"
---

<objective>
Define the `CacheStore` interface and ship two concrete implementations (`MemoryStore` + `FsStore`) at the canonical `@tradewinds/core/internal/cache` subpath. This wave is Node-first and browser-free — `IndexedDBStore` + `defaultCacheStore()` land in plan 02 once jsdom plumbing is in place. The shared contract test runs against both implementations so plan 02 can drop in `IndexedDBStore` without re-deriving acceptance criteria.

Mirror the Python cache (`packages/weather/src/tradewinds/weather/cache.py`) shape where possible — but cache scope here is generic key/value, NOT parquet/station/year/month. The station-level skip rules land in plan 03; this wave is plumbing only.
</objective>

<context_files>
- `.planning/research/TS-SDK-DESIGN.md` §5.4 (Cache topology — interface + FsStore root + auto-detection)
- `.planning/REQUIREMENTS.md` TS-CACHE-01, TS-CACHE-02 (canonical text)
- `.planning/REVIEW-DISCIPLINE.md` (TS Architect rubric — bundle size + Python parity + readonly contracts)
- `packages/weather/src/tradewinds/weather/cache.py` (Python source: `DEFAULT_ROOT`, `_atomic_write`, `FileLock` patterns — Python writes parquet under `.tradewinds/cache`, TS writes JSON under `.tradewinds/cache-ts`; the layout differs but the safety invariants don't)
- `packages-ts/core/src/internal/merge/observations.ts` (TS-W2 style guide — JSDoc voice, frozen exports, structural interface pattern, dep direction)
- `packages-ts/core/src/internal/merge/index.ts` (barrel export pattern under `internal/`)
- `packages-ts/core/package.json` (current subpath exports — add `./internal/cache` mirroring `./internal/merge`)
- `packages-ts/core/vitest.config.ts` (test include pattern)
</context_files>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Define CacheStore interface + lockKeyFor helper</name>
  <files>packages-ts/core/src/internal/cache/types.ts, packages-ts/core/tests/internal/cache/types.contract.test.ts</files>
  <read_first>
    - `packages-ts/core/src/internal/merge/observations.ts` (JSDoc + frozen-export style)
    - `.planning/research/TS-SDK-DESIGN.md` lines 244-264 (CacheStore interface canonical text)
    - `packages-ts/core/src/exceptions/index.ts` lines 100-170 (TradewindsError + payload contract for any cache errors)
  </read_first>
  <behavior>
    - CacheStore is a readonly interface (no mutator method bodies; type-only contract).
    - get&lt;T&gt;(key): returns parsed JSON value or null on miss; never throws on miss.
    - set&lt;T&gt;(key, value, opts?): persists; opts.ttlMs optional and OPTIONAL — implementations may ignore it (MemoryStore honors, FsStore ignores in v0.1 — documented).
    - delete(key): no-op on miss; returns void.
    - withLock&lt;T&gt;(key, fn): runs fn under a key-scoped lock; releases lock on fn throw; nested calls to same key must serialize.
    - lockKeyFor(key): pure function returning the lock identifier; same input → same output.
  </behavior>
  <action>
    Create `packages-ts/core/src/internal/cache/types.ts` exporting:

    ```typescript
    /** Cache entry envelope with optional TTL. */
    export interface CacheEntry&lt;T = unknown&gt; {
      readonly value: T;
      /** Epoch ms when the entry expires. Optional; absence = no expiry. */
      readonly expiresAt?: number;
    }

    /** Optional setters for cache writes. */
    export interface CacheSetOptions {
      /** Time-to-live in milliseconds. Implementations may honor or ignore. */
      readonly ttlMs?: number;
    }

    /**
     * Pluggable key/value cache contract.
     *
     * Three concrete implementations:
     * - {@link MemoryStore} — Map-backed, no persistence (Cloudflare Workers default).
     * - {@link FsStore} — node:fs/promises + proper-lockfile (Node default).
     * - IndexedDBStore — idb + Web Locks API (browser; lands in plan 02).
     *
     * `defaultCacheStore()` auto-detects (plan 02).
     */
    export interface CacheStore {
      get&lt;T = unknown&gt;(key: string): Promise&lt;T | null&gt;;
      set&lt;T = unknown&gt;(key: string, value: T, opts?: CacheSetOptions): Promise&lt;void&gt;;
      delete(key: string): Promise&lt;void&gt;;
      withLock&lt;T&gt;(key: string, fn: () =&gt; Promise&lt;T&gt;): Promise&lt;T&gt;;
    }

    /**
     * Canonical lock identifier for a given cache key.
     * Pure: same key always returns the same lock id. Used by FsStore + IndexedDBStore.
     */
    export function lockKeyFor(key: string): string {
      return `tradewinds:cache:lock:${key}`;
    }
    ```

    Write a `tests/internal/cache/types.contract.test.ts` that exports a `runCacheStoreContract(makeStore: () =&gt; CacheStore)` helper used by both `memory.test.ts` and `fs.test.ts` (plan 02 reuses for jsdom IndexedDBStore). Contract assertions:
    1. round-trip set/get returns the same value
    2. get on missing key returns null (does NOT throw)
    3. delete on missing key resolves (does NOT throw)
    4. delete after set causes subsequent get to return null
    5. withLock serializes nested calls on the same key (interleaved calls await each other)
    6. withLock releases on fn throw (subsequent withLock with same key resolves)
    7. set with ttlMs in the past, get returns null
    8. JSON-incompatible values (Date, Map, undefined fields) round-trip per the implementation contract — MemoryStore should preserve via JSON.stringify/parse semantics, NOT by-reference.

    Also include a smoke test `expect(lockKeyFor("foo")).toBe("tradewinds:cache:lock:foo")` (deterministic).
  </action>
  <acceptance_criteria>
    - `grep -n "interface CacheStore" packages-ts/core/src/internal/cache/types.ts` shows the interface.
    - `grep -n "lockKeyFor" packages-ts/core/src/internal/cache/types.ts` shows the pure function.
    - `grep -n "runCacheStoreContract" packages-ts/core/tests/internal/cache/types.contract.test.ts` shows the exported helper.
    - `pnpm --filter @tradewinds/core run typecheck` passes.
  </acceptance_criteria>
</task>

<task type="auto" tdd="true">
  <name>Task 2: MemoryStore implementation + tests</name>
  <files>packages-ts/core/src/internal/cache/memory.ts, packages-ts/core/tests/internal/cache/memory.test.ts</files>
  <read_first>
    - `packages-ts/core/src/internal/cache/types.ts` (Task 1 output)
    - `packages-ts/core/tests/internal/cache/types.contract.test.ts` (Task 1 contract runner)
  </read_first>
  <behavior>
    - MemoryStore backed by `Map<string, CacheEntry>`.
    - Serializes via `structuredClone` (default) so callers can't mutate stored values by reference. NaN/Infinity stay as numbers (structuredClone supports them).
    - withLock implemented via a per-key promise chain: `this._chain.set(key, prev.finally(() =&gt; fn()))`. Releases by removing from chain when promise settles.
    - Honors ttlMs: if `Date.now() &gt;= expiresAt`, get returns null AND deletes the entry (lazy eviction).
    - Per-instance state — two MemoryStore instances do NOT share state (test that).
  </behavior>
  <action>
    Implement `MemoryStore` in `packages-ts/core/src/internal/cache/memory.ts`. Key points:

    - Use `structuredClone` for value isolation (Node 17+ has it natively; works in jsdom and browsers).
    - Per-key promise chain for `withLock` — track `Map<string, Promise<unknown>>`, build `next = prev.then(fn, fn)`, store with `.finally(() =&gt; { if (this._chain.get(key) === next) this._chain.delete(key); })`.
    - Document the structuredClone semantics in the class JSDoc (NaN/Infinity preserved; functions/symbols rejected; circular refs work).

    Write `tests/internal/cache/memory.test.ts`:

    ```typescript
    import { describe, expect, it } from "vitest";
    import { MemoryStore } from "../../../src/internal/cache/memory.js";
    import { runCacheStoreContract } from "./types.contract.test.js";

    describe("MemoryStore", () =&gt; {
      runCacheStoreContract(() =&gt; new MemoryStore());

      it("instance isolation: two stores do not share state", async () =&gt; { /* ... */ });
      it("structuredClone: stored value mutations do not leak back", async () =&gt; {
        const store = new MemoryStore();
        const obj = { count: 1 };
        await store.set("k", obj);
        obj.count = 2;
        const got = await store.get&lt;{ count: number }&gt;("k");
        expect(got?.count).toBe(1);
      });
      it("ttlMs honored — expired entries return null", async () =&gt; { /* fake timers ok */ });
    });
    ```
  </action>
  <acceptance_criteria>
    - `pnpm --filter @tradewinds/core test -- memory` runs &gt;= 12 tests (contract suite + 3 MemoryStore-specific) all green.
    - `grep -n "structuredClone" packages-ts/core/src/internal/cache/memory.ts` confirms isolation strategy.
    - `grep -n "withLock" packages-ts/core/src/internal/cache/memory.ts` shows per-key promise chain.
    - Mutating a value object after `set` does NOT change what `get` returns (asserted in test).
  </acceptance_criteria>
</task>

<task type="auto" tdd="true">
  <name>Task 3: FsStore implementation + subpath export + tests</name>
  <files>packages-ts/core/src/internal/cache/fs.ts, packages-ts/core/src/internal/cache/index.ts, packages-ts/core/package.json, packages-ts/core/tests/internal/cache/fs.test.ts</files>
  <read_first>
    - `packages-ts/core/src/internal/cache/types.ts` + `memory.ts` (Tasks 1-2)
    - `packages/weather/src/tradewinds/weather/cache.py` lines 60-66 (`DEFAULT_ROOT`), lines 230-253 (`_atomic_write` pattern — write tmp + os.replace under FileLock; TS port: writeFile to `.tmp` then `rename` under proper-lockfile)
    - `packages-ts/core/src/internal/merge/index.ts` (barrel pattern)
    - `packages-ts/core/package.json` exports map (subpath layout)
  </read_first>
  <behavior>
    - Cache root: `process.env.TRADEWINDS_CACHE_DIR ?? path.join(os.homedir(), '.tradewinds', 'cache-ts')`. DISTINCT from Python (`.tradewinds/cache`). Per TS-CACHE-02.
    - Key → path: sanitize key (replace `:` `/` with `__`) so `tradewinds:v1:observations:KNYC:2025:01` becomes `tradewinds__v1__observations__KNYC__2025__01.json` under the root.
    - Atomic write: write `${path}.tmp` then `fs.rename(tmp, path)` — POSIX atomic, Windows-safe via `fs.rename` (Node ≥10).
    - withLock: use `proper-lockfile.lock(filepath, { retries: { retries: 5, minTimeout: 50 } })` against `${path}.lock` sidecar. Release on fn throw.
    - ttlMs: stored in the JSON envelope; `get` checks `expiresAt &lt;= Date.now()` and returns null + deletes file.
    - mkdir -p the parent dir before any write (matches Python's `path.parent.mkdir(parents=True, exist_ok=True)`).
  </behavior>
  <action>
    1. Add `proper-lockfile` to `packages-ts/core/package.json` dependencies (NOT devDependencies — it ships to consumers):
       ```json
       "dependencies": { "proper-lockfile": "^4.1.2" },
       "devDependencies": { "@types/proper-lockfile": "^4.1.4", ... }
       ```
    2. Implement `FsStore` in `packages-ts/core/src/internal/cache/fs.ts`:
       - Default root resolution as a function `defaultFsRoot()` (NOT a module-level constant — env var must be re-readable per test).
       - `_pathFor(key: string): string` sanitizes `key` to a filename under the root.
       - `_atomicWrite(path, json)`: mkdir parents, write `${path}.tmp`, then `rename`. Errors propagate.
       - `withLock` wraps `proper-lockfile.lock` with `realpath: false` so the lock can be acquired on a path whose target may not yet exist.
       - Document the divergence from Python: Python uses parquet + per-month files keyed by station; TS uses JSON + per-key files keyed by the caller's opaque string. The station-aware key generation lives in `weather/cache-keys.ts` (plan 06).
    3. Create `packages-ts/core/src/internal/cache/index.ts` barrel:
       ```typescript
       export type { CacheStore, CacheSetOptions, CacheEntry } from "./types.js";
       export { lockKeyFor } from "./types.js";
       export { MemoryStore } from "./memory.js";
       export { FsStore, defaultFsRoot } from "./fs.js";
       // defaultCacheStore + IndexedDBStore exported by plan 02.
       ```
    4. Update `packages-ts/core/package.json` to add the subpath export:
       ```json
       "./internal/cache": {
         "types": "./dist/internal/cache/index.d.ts",
         "import": "./dist/internal/cache/index.mjs",
         "require": "./dist/internal/cache/index.cjs"
       }
       ```
       Also add the entry to `tsup.config.ts` if entry points are enumerated (check first; current `internal/merge` pattern is the model).
    5. Write `tests/internal/cache/fs.test.ts`:
       - Uses `runCacheStoreContract` against `new FsStore({ root: tmpdir })` where `tmpdir = await fs.mkdtemp(path.join(os.tmpdir(), "tw-fs-"))`.
       - `afterEach`: `fs.rm(tmpdir, { recursive: true, force: true })`.
       - FsStore-specific tests:
         - `defaultFsRoot()` honors `TRADEWINDS_CACHE_DIR` env (use `vi.stubEnv`).
         - `defaultFsRoot()` falls back to `path.join(os.homedir(), ".tradewinds", "cache-ts")` when env unset.
         - `defaultFsRoot()` does NOT match the Python root (`.tradewinds/cache`) — assert by string comparison.
         - Atomic write: simulated crash mid-write (write a `.tmp` file directly then verify `get` doesn't see it) returns null.
         - withLock under proper-lockfile: two concurrent `withLock(key, ...)` calls serialize (use timestamps; second's start &gt;= first's end).
  </action>
  <acceptance_criteria>
    - `pnpm --filter @tradewinds/core test -- cache` runs MemoryStore + FsStore contract suites all green.
    - `grep -n "proper-lockfile" packages-ts/core/package.json` confirms dep added.
    - `grep -n "cache-ts" packages-ts/core/src/internal/cache/fs.ts` confirms TS-specific cache root.
    - `grep -n '"./internal/cache"' packages-ts/core/package.json` confirms subpath export added.
    - `pnpm --filter @tradewinds/core run build` produces `dist/internal/cache/index.{mjs,cjs,d.ts}`.
    - `pnpm --filter @tradewinds/core run typecheck` passes.
    - From a sibling package: `import { FsStore, MemoryStore, type CacheStore } from "@tradewinds/core/internal/cache"` resolves (typecheck the meta package as smoke).
  </acceptance_criteria>
</task>

</tasks>

<verification>
1. `pnpm --filter @tradewinds/core run typecheck` clean.
2. `pnpm --filter @tradewinds/core test -- cache` all green; both contract suites (Memory + Fs) run.
3. `pnpm --filter @tradewinds/core run build` emits `dist/internal/cache/index.{mjs,cjs,d.ts}` AND `dist/internal/cache/types.d.ts` etc.
4. `pnpm -r run typecheck` clean (meta package can import the new subpath).
5. `pnpm --filter @tradewinds/core run size-limit` (if configured) — no regression beyond ~3 KB (proper-lockfile is tree-shaken on browser since it's only inside `fs.ts` which has no browser code).
</verification>

<success_criteria>
- TS-CACHE-01 partial — interface + 2/3 concrete impls land. IndexedDBStore + defaultCacheStore complete in plan 02.
- TS-CACHE-02 partial — FsStore root + Python-distinct root verified. Cache-skip rules (LST/`.live`/30-day) land in plan 03.
- All cache code lives under `@tradewinds/core/internal/cache` — never `@tradewinds/weather` (matches Python `_internal/merge/` placement rationale).
- Bundle size: `proper-lockfile` only imported from `fs.ts`. The browser bundle path (used by plan 02's IndexedDBStore) does NOT pull it. Verify with size-limit AFTER plan 02 lands.
</success_criteria>

<review_discipline>
This plan ships TypeScript-only changes under `packages-ts/core/**`. Per `.planning/REVIEW-DISCIPLINE.md`:

- **Reviewers**: codex `high` + **TypeScript Architect** (parallel dispatch).
- **Severity gate**: CRITICAL or HIGH only — no MEDIUM/LOW/style nits.
- **Loop**: fix any CRITICAL/HIGH on this branch (NOT on `merged-vision`), then re-dispatch both. Stop when both PASS clean, or escalate at iteration 3.
- **Rubric calibration for this plan**:
  - CRITICAL if `FsStore` root accidentally collides with the Python cache root (would let Python parquet files leak into TS reads as JSON — silent corruption).
  - CRITICAL if `withLock` doesn't release on fn throw (deadlocks every subsequent caller).
  - HIGH if `MemoryStore` stores by reference (caller mutation leaks back — TS-W1 iter-1 caught a similar contract drift).
  - HIGH if the new `./internal/cache` subpath export is missing from `tsup.config.ts` entries (build emits dist but typecheck breaks for consumers — TS-W2 iter-1 P1 pattern).
  - HIGH if `proper-lockfile` is in devDependencies (consumers can't run `FsStore` after install).
</review_discipline>

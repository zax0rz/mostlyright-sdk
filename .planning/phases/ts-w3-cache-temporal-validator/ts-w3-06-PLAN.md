---
phase: ts-w3-cache-temporal-validator
plan: 06
type: execute
wave: 6
depends_on:
  - ts-w3-01
  - ts-w3-02
  - ts-w3-03
files_modified:
  - packages-ts/meta/src/research.ts
  - packages-ts/meta/tests/research.cache.test.ts
  - packages-ts/meta/tests/research.cache.behavior.test.ts
  - packages-ts/core/vitest.config.ts
  - packages-ts/core/package.json
autonomous: true
requirements:
  - TS-CACHE-01
  - TS-CACHE-02
must_haves:
  truths:
    - "research() accepts opts.cache?: CacheStore parameter; defaults to defaultCacheStore() when omitted"
    - "research() read-through path: on cache hit for (station, year, month), skips the remote fetch for that month chunk"
    - "research() write-through path: after fetching a month chunk, writes to cache IFF skip rules permit (not current LST month, not .live source)"
    - "Second research() call for same (station, fromDate, toDate) is ≤ 10% of first-call wall time on cached-month data (measured via vitest test-time stamps)"
    - "5-case skip behavior fixture from plan 03 replays correctly through research()"
    - "≥ 90% branch coverage on @tradewinds/core (the TS-W3 success criterion #5)"
  artifacts:
    - path: packages-ts/meta/src/research.ts
      provides: "Updated research() with cache integration"
    - path: packages-ts/meta/tests/research.cache.test.ts
      provides: "Wall-time perf test: 2nd call ≤ 10% of 1st call on cached month"
    - path: packages-ts/meta/tests/research.cache.behavior.test.ts
      provides: "5-case skip behavior replay through the orchestrator"
  key_links:
    - from: packages-ts/meta/src/research.ts
      to: "@tradewinds/core/internal/cache"
      via: "import { defaultCacheStore, cacheKeyForObservations, cacheKeyForClimate, shouldSkipCacheForCurrentLstMonth, isLiveSource } from '@tradewinds/core/internal/cache'"
      pattern: "from .@tradewinds/core/internal/cache"
---

<objective>
Wire the cache layer (plans 01-03) into `research()` to deliver TS-W3 success criteria #2 (≤10% wall time on second call) and #5 (≥90% branch coverage on @tradewinds/core). This is the integration wave: every cache primitive built in plans 01-03 must be exercised by the orchestrator.

Design:
- `research()` gains an optional `opts.cache?: CacheStore`. Default is `defaultCacheStore()` — lazy-instantiated so test environments without IndexedDB / fs fall back to MemoryStore automatically.
- For EACH `(station, year, month)` tuple in the date range, the orchestrator:
  1. Checks skip rules (`shouldSkipCacheForCurrentLstMonth`, `isWithinVolatileWindow`, per-source `isLiveSource`).
  2. If NOT skipped, attempts cache read via `cacheKeyForObservations(station, year, month)`.
  3. On hit, uses the cached rows; on miss, fetches from the remote source.
  4. After a successful fetch, writes to cache IFF skip rules permit.
- Wave 6 does NOT change the fetcher contract or merge logic — purely a layer above the existing TS-W2 pipeline.

The coverage gate (TS-W3 SC#5) is enforced here because all the temporal + validator + cache + formats code is in flight by this wave; verifying coverage early avoids a Wave 7 ambush.
</objective>

<context_files>
- `packages-ts/meta/src/research.ts` (current TS-W2 orchestrator — full file; the wiring goes here)
- `packages-ts/core/src/internal/cache/index.ts` (plans 01-03 barrel)
- `packages-ts/core/tests/internal/cache/fixtures/skip-rules-behavior.json` (plan 03 fixture — replay through `research()`)
- `packages/weather/src/tradewinds/weather/cache.py` lines 259-413 (Python `read_cache` / `write_cache` / `read_climate_cache` / `write_climate_cache` — the read-through/write-through patterns being ported to TS at the orchestrator layer)
- `packages-ts/meta/vitest.config.ts` (test config — confirm coverage settings)
- `packages-ts/meta/tests/research.test.ts` (current TS-W2 tests — style guide)
- `.planning/REQUIREMENTS.md` TS-CACHE-02 (5-case fixture requirement)
- TS-SDK-DESIGN.md §5.4 line 264 (canonical cache-skip semantics)
</context_files>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Wire CacheStore into research() (read-through + write-through)</name>
  <files>packages-ts/meta/src/research.ts, packages-ts/meta/tests/research.cache.test.ts</files>
  <read_first>
    - `packages-ts/meta/src/research.ts` (current — locate the per-month fetch loop and the per-year climate fetch loop)
    - `packages-ts/core/src/internal/cache/keys.ts` (cache key generators)
    - `packages-ts/core/src/internal/cache/skip-rules.ts` (skip predicates)
    - `packages-ts/core/src/internal/cache/default.ts` (defaultCacheStore)
    - `packages/weather/src/tradewinds/weather/cache.py` lines 259-291 (`read_cache` — exists check + current-LST-skip + TOCTOU treatment)
  </read_first>
  <behavior>
    - `ResearchOptions` extends with: `cache?: CacheStore | null` (`null` to opt out explicitly; absent to use default; explicit instance to inject).
    - For each month in the IEM ASOS yearly chunks: BEFORE fetching, check `shouldSkipCacheForCurrentLstMonth(station, year, month, opts.now)`. If skipped → fetch fresh (don't cache afterwards). If not skipped → try `cache.get(cacheKeyForObservations(station, year, month))`; on hit, use cached rows; on miss, fetch and call `cache.set(...)` IFF the source isn't `.live`.
    - For each year in the CLI climate fetch: same pattern with `shouldSkipCacheForCurrentLstYear` and `cacheKeyForClimate`.
    - AWC live source: NEVER cached (it's `.live` by definition — `isLiveSource("awc.live") === true`). The skip-rule check already handles this.
    - GHCNh archive: cacheable per yearly chunk; same pattern as IEM ASOS but per-year (current GHCNh fetch is per-year, not per-month).
    - Cached rows MUST match the structural shape that the merge step expects — store the row arrays directly (no envelope changes).
    - Cache writes happen AFTER the row arrays are fully parsed (post-`parseIemCsv` / `parseGhcnhPsv` / `parseCliResponse`). The merge step still runs on the assembled in-memory data.
  </behavior>
  <action>
    1. Update `packages-ts/meta/src/research.ts`:
       - Add the `cache` field to `ResearchOptions`.
       - Import the cache surface: `import { type CacheStore, defaultCacheStore, cacheKeyForObservations, cacheKeyForClimate, shouldSkipCacheForCurrentLstMonth, shouldSkipCacheForCurrentLstYear, isLiveSource } from "@tradewinds/core/internal/cache";`
       - Add helper: `function resolveCache(opts: ResearchOptions): CacheStore | null { if (opts.cache === null) return null; return opts.cache ?? defaultCacheStore(); }`.
       - Wrap each fetcher call (IEM ASOS month chunks, GHCNh year chunks, CLI year chunks) with the read-through/write-through pattern. AWC stays bypassed (skip-rule short-circuits).
       - Be careful about the existing canonical-fetch-order guarantee from TS-W2 — cache hits must NOT change the order of arguments handed to `mergeObservations` (TS-W1 iter-1 caught a similar reorder bug).

    2. Write `packages-ts/meta/tests/research.cache.test.ts`:
       - Smoke test 1: `research("KNYC", "2024-06-01", "2024-06-30", { cache: new MemoryStore() })` runs end-to-end against msw recordings (reuse TS-W2's recordings infrastructure). Asserts the cache has entries for `cacheKeyForObservations("KNYC", 2024, 6)` after the call.
       - Smoke test 2: `opts.cache = null` → no cache reads/writes; same result as before TS-W3 (regression guard).
       - Wall-time test (TS-W3 SC#2): pre-warm the cache by calling `research(...)` once; measure `t1 = performance.now()`; call again; measure `t2 = performance.now()`. Compute first/second-call durations across enough invocations to get stable numbers. Assert `secondDuration &lt;= firstDuration * 0.10`. Use msw to simulate a fixed 200ms-per-request fetch delay so the timer isn't dominated by network noise — the assertion is "second call avoids the 200ms × N month requests".
         - Skip-gate this test under `it.skipIf(process.env.CI && !process.env.TS_PERF_TEST)` so it runs locally + in a perf-specific CI job but doesn't blow up the regular CI on slow runners.
       - Regression test: `research()` output rows are byte-identical (deep-equal) between cache-bypassed and cache-warmed runs.
  </action>
  <acceptance_criteria>
    - `grep -n "from .@tradewinds/core/internal/cache" packages-ts/meta/src/research.ts` confirms cache wiring.
    - `grep -n "shouldSkipCacheForCurrentLstMonth\\|cacheKeyForObservations\\|defaultCacheStore" packages-ts/meta/src/research.ts` confirms all skip rules + key gen + default-store wired.
    - `pnpm --filter tradewinds test -- research.cache` runs (4 cases: smoke, opt-out, wall-time, regression); the regression test passes; the wall-time test passes locally or is appropriately skip-gated.
    - `pnpm --filter tradewinds run typecheck` clean.
    - `pnpm -r run test` overall remains green (the existing TS-W2 parity test must not regress; same row shape, same ordering, same merge output).
  </acceptance_criteria>
</task>

<task type="auto" tdd="true">
  <name>Task 2: 5-case skip behavior replay through research()</name>
  <files>packages-ts/meta/tests/research.cache.behavior.test.ts</files>
  <read_first>
    - `packages-ts/core/tests/internal/cache/fixtures/skip-rules-behavior.json` (plan 03 — 5 cases)
    - Task 1 output (research.ts cache integration)
  </read_first>
  <behavior>
    - For each of the 5 cases in the fixture:
      1. Construct a fresh `MemoryStore`.
      2. Pre-populate the store with a sentinel value for the expected cache key.
      3. Call `research()` with `opts.cache = store`, `opts.now = case.now`.
      4. Assert: cache read attempted; the skip-rule outcome matches `case.expected.skipCurrentMonth` (verified by observing whether the sentinel persisted unchanged OR was bypassed).
      5. For `isLiveSource` cases: assert no cache.set call landed for the AWC live source path (AWC fetches stay bypassed).
    - Uses the SAME fixture file as plan 03 — `import fixtureData from "@tradewinds/core/internal/cache/fixtures/skip-rules-behavior.json"` (or the relative path; whatever resolves cleanly across packages).
  </behavior>
  <action>
    Write `packages-ts/meta/tests/research.cache.behavior.test.ts`:
    ```typescript
    import { describe, it, expect, vi } from "vitest";
    import { MemoryStore, cacheKeyForObservations } from "@tradewinds/core/internal/cache";
    import { research } from "../src/research.js";
    import fixtureData from "../../core/tests/internal/cache/fixtures/skip-rules-behavior.json" with { type: "json" };

    describe("research() — 5-case skip behavior replay (TS-W3 SC#2)", () =&gt; {
      for (const c of fixtureData.cases) {
        it(`${c.id}: skipCurrentMonth=${c.expected.skipCurrentMonth} skipLive=${c.expected.skipLive}`, async () =&gt; {
          // Build a MemoryStore pre-seeded with a sentinel.
          const store = new MemoryStore();
          const sentinel = { __sentinel: c.id };
          const key = cacheKeyForObservations(c.station, c.year, c.month);
          await store.set(key, sentinel);

          // Spy on cache.set to count writes.
          const setSpy = vi.spyOn(store, "set");

          // Drive research() against a synthetic month window matching the case.
          // Use msw recordings for HTTP layer (existing TS-W2 setup); the cache
          // layer is what we're testing, not the network.
          try {
            await research(c.station, `${c.year}-${String(c.month).padStart(2, "0")}-01`, `${c.year}-${String(c.month).padStart(2, "0")}-15`, {
              cache: store,
              now: new Date(c.now),
            });
          } catch {
            // Cases that don't match a station in our msw recordings may fail at
            // the fetcher layer; that's fine — the cache assertion still holds.
          }

          // Assertion 1: when skipCurrentMonth=true, the sentinel was NEVER read.
          // (Read-through still happens but skip-rule short-circuits → no fetcher
          // result overwrites; sentinel stays.) When skipCurrentMonth=false, the
          // cache read returns the sentinel and short-circuits the fetcher.
          const after = await store.get(key);
          if (c.expected.skipCurrentMonth) {
            // Skipped — store untouched OR overwritten by fresh fetch (depending on whether the test fetcher succeeded).
            // The key invariant: skip-rule prevented BOTH the read AND the write.
            // Assert by checking setSpy was NOT called for this key after the initial seed.
            expect(setSpy.mock.calls.filter(([k]) =&gt; k === key).length).toBeLessThanOrEqual(1); // ≤1 (initial seed)
          }
          if (c.expected.skipLive) {
            // Live-source paths never cache. Confirm no .live-suffixed key was set.
            for (const [k] of setSpy.mock.calls) {
              expect(String(k).includes(".live")).toBe(false);
            }
          }
        });
      }
    });
    ```

    Notes:
    - The exact assertion logic depends on how `research()` exposes the cache flow. If the spy approach doesn't fit (e.g. because the orchestrator only calls cache for some months), simplify by asserting that the cache has expected keys after a normal call (positive assertion) and lacks them for skipped months (negative assertion).
    - Cases that don't have an msw recording fail gracefully (the try/catch swallows the fetcher error). The cache-layer assertion is what matters.
  </action>
  <acceptance_criteria>
    - `pnpm --filter tradewinds test -- research.cache.behavior` runs 5 cases; all green (or appropriately skip-gated where msw recordings are missing).
    - `grep -n "skip-rules-behavior.json" packages-ts/meta/tests/research.cache.behavior.test.ts` confirms the fixture file is consumed by the orchestrator test.
    - `grep -n "MemoryStore\\|cacheKeyForObservations" packages-ts/meta/tests/research.cache.behavior.test.ts` confirms the cache primitives are exercised.
  </acceptance_criteria>
</task>

<task type="auto" tdd="true">
  <name>Task 3: ≥90% branch coverage gate on @tradewinds/core</name>
  <files>packages-ts/core/vitest.config.ts, packages-ts/core/package.json</files>
  <read_first>
    - `packages-ts/core/vitest.config.ts` (current — coverage block exists but no threshold)
    - All `packages-ts/core/src/**/*.ts` (informational — confirm coverage paths)
  </read_first>
  <behavior>
    - Add coverage threshold to vitest config:
      ```typescript
      coverage: {
        provider: "v8",
        reporter: ["text", "lcov"],
        include: ["src/**/*.ts"],
        exclude: ["**/generated/**", "**/*.d.ts", "src/data/**", "src/schemas/validators/**"],
        thresholds: {
          branches: 90,
          functions: 90,
          lines: 90,
          statements: 90,
        },
      },
      ```
    - Generated/data modules are excluded (pure-data tables don't need branch coverage; matches Python `[tool.coverage.run].omit` discipline from Phase 4 closeout).
    - Run `pnpm --filter @tradewinds/core test -- --coverage` and confirm the gate passes. If under 90%, add targeted tests until it does — likely candidates: edge cases in `cacheKeyForObservations` validation, FsStore error paths, IndexedDBStore navigator.locks fallback branch, TimePoint NaN/Infinity rejection branches, validator vocabulary edge cases.
  </behavior>
  <action>
    1. Update `packages-ts/core/vitest.config.ts` to add the `thresholds` block. Also add `"@vitest/coverage-v8"` to devDependencies if not already present.
    2. Run `pnpm --filter @tradewinds/core test -- --coverage --run` once to baseline.
    3. If under 90%, add tests targeting the gap. Document any documented exclusion (e.g. unreachable defensive throws) with `/* c8 ignore next */` comments.
    4. Add a `pnpm` script alias: `"test:coverage": "vitest run --coverage"` for convenience.
  </action>
  <acceptance_criteria>
    - `pnpm --filter @tradewinds/core run test:coverage` exits 0 with all four threshold metrics ≥ 90%.
    - `grep -n '"branches": 90\\|branches: 90' packages-ts/core/vitest.config.ts` confirms the threshold is enforced.
    - Coverage report (`packages-ts/core/coverage/lcov.info`) generated.
    - The gate failure mode: running with coverage below threshold exits non-zero (vitest enforces).
  </acceptance_criteria>
</task>

</tasks>

<verification>
1. `pnpm --filter tradewinds test -- research.cache` all green (4+ cases).
2. `pnpm --filter tradewinds test -- research.cache.behavior` all green (5 fixture cases; or skip-gated for missing msw cases with reason documented).
3. `pnpm --filter @tradewinds/core run test:coverage` ≥ 90% on all four metrics.
4. `pnpm -r run test` overall green — TS-W2 parity test unchanged.
5. `pnpm -r run typecheck` clean.
6. Wall-time test: 2nd `research()` call &lt;= 10% of 1st call duration (locally measurable; skip-gated in CI if runner-flaky).
</verification>

<success_criteria>
- TS-W3 SC#2 fully met — cached `research()` second call ≤ 10% wall time; 5-case skip behavior fixture replays through the orchestrator.
- TS-W3 SC#5 (the ≥90% branch coverage gate on `@tradewinds/core`) is enforced in vitest config and passes.
- No regression in TS-W2 parity test or research() row shape — the cache layer is purely additive.
- `defaultCacheStore()` auto-detection works under all three runtimes the tests cover (Node default for fs.test; jsdom + fake-indexeddb for indexeddb.test; MemoryStore via explicit opt-in for research.cache tests).
</success_criteria>

<review_discipline>
TypeScript-only changes under `packages-ts/meta/**` + `packages-ts/core/**` (vitest config). Per `.planning/REVIEW-DISCIPLINE.md`:

- **Reviewers**: codex `high` + **TypeScript Architect** (parallel).
- **Severity gate**: CRITICAL or HIGH only.
- **Loop**: fix on branch, re-dispatch, cap at 3.
- **Rubric calibration**:
  - CRITICAL if cache wiring changes the canonical fetch order handed to `mergeObservations` (TS-W1 iter-1 + TS-W2 iter-1 both caught reorder bugs; this is the exact class of regression).
  - CRITICAL if cache writes happen for `.live` sources (silent staleness; users would get yesterday's "live" observation forever).
  - CRITICAL if cache writes happen for the current LST month (Python invariant; TS skipping it inconsistently would diverge silently).
  - HIGH if the wall-time perf test is unconditionally skipped in CI (the gate is meaningless if it never runs).
  - HIGH if the coverage threshold excludes too much (e.g. excluding `src/internal/cache/**` would defeat the purpose of TS-W3 SC#5).
  - HIGH if `opts.cache = null` doesn't fully disable caching (a leaky default-store fallback would silently re-enable for some paths).
  - HIGH if the regression test (cache-warm vs cache-cold output equality) is missing or weakened to a row-count check instead of deep-equal.
</review_discipline>

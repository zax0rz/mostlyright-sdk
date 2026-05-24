---
phase: ts-w3-cache-temporal-validator
plan: 03
type: execute
wave: 3
depends_on:
  - ts-w3-01
  - ts-w3-02
files_modified:
  - packages-ts/core/src/internal/cache/skip-rules.ts
  - packages-ts/core/src/internal/cache/keys.ts
  - packages-ts/core/src/internal/cache/index.ts
  - packages-ts/core/tests/internal/cache/skip-rules.test.ts
  - packages-ts/core/tests/internal/cache/keys.test.ts
  - packages-ts/core/tests/internal/cache/fixtures/skip-rules-behavior.json
autonomous: true
requirements:
  - TS-CACHE-02
must_haves:
  truths:
    - "shouldSkipCacheForCurrentLstMonth(station, year, month, now) returns true iff (year, month) equals the current LST month for station"
    - "isLiveSource(source) returns true iff source ends with '.live' (matches Python _is_live_source)"
    - "isWithinVolatileWindow(eventDate, archiveAsOf, days=30) returns true iff eventDate is within `days` days of archiveAsOf"
    - "cacheKeyForObservations(station, year, month) returns 'tradewinds:v1:observations:{STATION}:{YYYY}:{MM}' (zero-padded month)"
    - "cacheKeyForClimate(station, year) returns 'tradewinds:v1:climate:{STATION}:{YYYY}'"
    - "5-case behavior fixture pins skip behavior byte-by-byte for shared cross-language regression"
  artifacts:
    - path: packages-ts/core/src/internal/cache/skip-rules.ts
      provides: "Pure skip predicates: shouldSkipCacheForCurrentLstMonth, shouldSkipCacheForCurrentLstYear, isLiveSource, isWithinVolatileWindow"
    - path: packages-ts/core/src/internal/cache/keys.ts
      provides: "Key generators: cacheKeyForObservations, cacheKeyForClimate"
    - path: packages-ts/core/tests/internal/cache/fixtures/skip-rules-behavior.json
      provides: "5-case behavior fixture (per TS-W3 success criterion #2)"
  key_links:
    - from: packages-ts/core/src/internal/cache/skip-rules.ts
      to: "settlementDateFor / LST math from @tradewinds/core snapshot"
      via: "import { _lstOffsetHours, settlementDateFor } from '../../snapshot.js'"
      pattern: "lstOffset|settlementDate"
---

<objective>
Land the cache-skip rule engine that gates writes/reads against three independent conditions matching Python `packages/weather/src/tradewinds/weather/cache.py`:

1. **Current LST month skip** — `(year, month)` equals the station's current Local Standard Time month → no cache read/write (current month is mutable; obs still arriving).
2. **`.live` source skip** — any source string ending in `.live` is never cached (next call wants the next live observation, not the cached one).
3. **30-day volatile-window skip** — archive endpoints within 30 days of a moving asOf cursor are treated as volatile (some archive sources amend their published data for ~30 days).

Plus the deterministic cache-key generators (`tradewinds:v1:observations:KNYC:2025:01` shape) that the `research()` consumer in plan 06 needs.

This wave is pure functions over inputs — NO CacheStore I/O, NO network, NO timezone library beyond what `@tradewinds/core/snapshot` already provides (lifted in TS-W1). The 5-case behavior fixture (TS-W3 success criterion #2) is captured here as a JSON file so plan 06's wiring test can replay it.
</objective>

<context_files>
- `.planning/REQUIREMENTS.md` TS-CACHE-02 (canonical text — three skip conditions + cache root + Python distinct-root)
- `packages/weather/src/tradewinds/weather/cache.py` lines 187-224 (Python skip predicates `_is_current_lst_month`, `_is_current_lst_year`, `_is_live_source`)
- `packages-ts/core/src/snapshot.ts` (TS-W1 — settlementDateFor + LST offset math; reuse, do NOT re-derive tz tables)
- `packages-ts/core/src/data/generated/stations.ts` (codegen — for the 5-case fixture; pick KNYC + 1 intl station for tz coverage)
- TS-SDK-DESIGN.md §5.4 line 264 ("Cache-skip same as Python: current LST month and any `.live` source. 30-day volatile-window exclusion for archive endpoints.")
</context_files>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Cache-skip rule predicates + tests</name>
  <files>packages-ts/core/src/internal/cache/skip-rules.ts, packages-ts/core/tests/internal/cache/skip-rules.test.ts</files>
  <read_first>
    - `packages/weather/src/tradewinds/weather/cache.py` lines 87-224 (`_lst_offset` + `_now_lst` + `_is_current_lst_month` + `_is_current_lst_year` + `_is_live_source`)
    - `packages-ts/core/src/snapshot.ts` (existing LST math — find the exported helpers; reuse for now-LST computation)
    - `packages-ts/core/src/data/generated/stations.ts` (station record shape; for tz lookups)
  </read_first>
  <behavior>
    - `shouldSkipCacheForCurrentLstMonth(station: string, year: number, month: number, now?: Date): boolean` — returns true iff `(year, month)` matches the LST-current month for the station. The `now` parameter is a test seam defaulting to `new Date()`. Mirrors Python `_is_current_lst_month`.
    - `shouldSkipCacheForCurrentLstYear(station: string, year: number, now?: Date): boolean` — same idea, annual granularity (for the climate cache). Mirrors Python `_is_current_lst_year`.
    - `isLiveSource(source: string | null | undefined): boolean` — returns true iff `source` is truthy AND `source.endsWith(".live")`. Mirrors Python `_is_live_source` BYTE-EQUIVALENTLY (Python uses `bool(source) and source.endswith(".live")`).
    - `isWithinVolatileWindow(eventDate: string, archiveAsOf: string, days = 30): boolean` — returns true iff `eventDate` (YYYY-MM-DD) falls within the last `days` days of `archiveAsOf` (YYYY-MM-DD). Note: Python's weather cache does NOT ship this predicate today (cache.py predates the 30-day rule). The TS-CACHE-02 requirement text adds it for TS. Document this as a TS-NEW addition (not a Python port) with a CROSS-SDK-SYNC ticket reference for back-porting to Python in a later milestone.
    - All four functions are PURE — no module-level state, no Date.now() except via the optional `now` param.
  </behavior>
  <action>
    1. Implement `packages-ts/core/src/internal/cache/skip-rules.ts`:
       ```typescript
       import { STATION_BY_CODE, STATION_BY_ICAO } from "../../data/generated/stations.js";
       // Import the LST helpers from @tradewinds/core/snapshot — TS-W1 already
       // shipped this; do NOT re-implement the tz table.

       /** Resolve a station identifier (3-letter code OR 4-letter ICAO) to the LST hour offset. */
       function _lstOffsetHoursFor(station: string): number { /* normalize via STATION_BY_CODE / STATION_BY_ICAO; throw on unknown */ }

       /** Current LST datetime for `station`, expressed as a plain Date (no zone — read year/month/year fields). */
       function _nowLst(station: string, now: Date = new Date()): Date {
         const offsetHours = _lstOffsetHoursFor(station);
         return new Date(now.getTime() + offsetHours * 3600 * 1000);
       }

       export function shouldSkipCacheForCurrentLstMonth(station: string, year: number, month: number, now?: Date): boolean {
         const lst = _nowLst(station, now);
         return lst.getUTCFullYear() === year && lst.getUTCMonth() + 1 === month;
       }

       export function shouldSkipCacheForCurrentLstYear(station: string, year: number, now?: Date): boolean {
         const lst = _nowLst(station, now);
         return lst.getUTCFullYear() === year;
       }

       export function isLiveSource(source: string | null | undefined): boolean {
         return Boolean(source) && (source as string).endsWith(".live");
       }

       /**
        * TS-NEW addition per TS-CACHE-02: 30-day volatile window for archive endpoints.
        * NOT a Python port today — file a CROSS-SDK-SYNC parity ticket if Python adopts it.
        */
       export function isWithinVolatileWindow(eventDate: string, archiveAsOf: string, days = 30): boolean {
         const e = Date.parse(`${eventDate}T00:00:00Z`);
         const a = Date.parse(`${archiveAsOf}T00:00:00Z`);
         if (Number.isNaN(e) || Number.isNaN(a)) throw new RangeError(`invalid YYYY-MM-DD: eventDate=${eventDate} archiveAsOf=${archiveAsOf}`);
         const deltaDays = (a - e) / 86_400_000;
         return deltaDays &gt;= 0 && deltaDays &lt; days;
       }
       ```
       Document in the module docstring: "Pure predicates — no I/O. Each maps 1:1 to a Python `cache.py` helper EXCEPT `isWithinVolatileWindow` which is TS-NEW (Python adds in a later milestone via CROSS-SDK-SYNC)."

    2. Write `tests/internal/cache/skip-rules.test.ts` covering:
       - KNYC (UTC-5 LST): `now = 2025-01-15T12:00:00Z` → LST clock reads `2025-01-15T07:00:00`; `shouldSkipCacheForCurrentLstMonth("KNYC", 2025, 1, now)` is true.
       - KNYC across UTC-day-boundary: `now = 2025-02-01T03:00:00Z` (UTC Feb 1 03:00) → LST reads `2025-01-31T22:00:00`; `shouldSkipCacheForCurrentLstMonth("KNYC", 2025, 1, now)` is true; (2025, 2) is false.
       - RJTT (UTC+9, intl station from the codegen registry — confirm it's in the W1 station table): `now = 2025-12-31T20:00:00Z` (Dec 31 20:00 UTC) → LST reads `2026-01-01T05:00:00`; `shouldSkipCacheForCurrentLstYear("RJTT", 2026, now)` is true.
       - `isLiveSource("awc.live")` true; `isLiveSource("awc")` false; `isLiveSource(null)` false; `isLiveSource("")` false; `isLiveSource("iem.archive.live")` true (endsWith is the rule).
       - `isWithinVolatileWindow("2025-01-01", "2025-01-15")` true (14 days &lt; 30); `isWithinVolatileWindow("2024-12-01", "2025-01-15")` false (45 days); `isWithinVolatileWindow("2025-01-15", "2025-01-15")` true (0 days &lt; 30); `isWithinVolatileWindow("2025-01-16", "2025-01-15")` false (negative — eventDate AFTER archiveAsOf is never volatile by this definition).
       - Unknown station → throws RangeError (matches Python ValueError-on-unknown contract from `_lst_offset`).
  </action>
  <acceptance_criteria>
    - `pnpm --filter @tradewinds/core test -- skip-rules` ≥ 10 cases all green.
    - `grep -n "shouldSkipCacheForCurrentLstMonth" packages-ts/core/src/internal/cache/skip-rules.ts` shows export.
    - `grep -n "endsWith.*live" packages-ts/core/src/internal/cache/skip-rules.ts` confirms `.live` suffix check matches Python.
    - `grep -n "TS-NEW" packages-ts/core/src/internal/cache/skip-rules.ts` confirms divergence is documented for `isWithinVolatileWindow`.
    - All four predicates are pure (no `new Date()` outside the optional `now` parameter — grep-verify: `grep -c "new Date()" packages-ts/core/src/internal/cache/skip-rules.ts` returns 0 OUTSIDE function-default-parameter positions).
  </acceptance_criteria>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Cache-key generators + tests</name>
  <files>packages-ts/core/src/internal/cache/keys.ts, packages-ts/core/tests/internal/cache/keys.test.ts</files>
  <read_first>
    - `.planning/research/TS-SDK-DESIGN.md` line 264 (key scheme: `tradewinds:v1:observations:&lt;STATION&gt;:&lt;YYYY&gt;:&lt;MM&gt;`)
    - `packages/weather/src/tradewinds/weather/cache.py` lines 147-183 (`cache_path` + `climate_cache_path` — Python pads month to 2 digits)
  </read_first>
  <behavior>
    - `cacheKeyForObservations("KNYC", 2025, 1)` returns `"tradewinds:v1:observations:KNYC:2025:01"` (zero-padded month; matches Python file-path month padding for cross-language audit).
    - `cacheKeyForClimate("KNYC", 2025)` returns `"tradewinds:v1:climate:KNYC:2025"`.
    - Year is always 4 digits; month is always 2 digits (zero-pad single-digit months).
    - Station is upper-cased BUT NOT validated here (validation happens in the orchestrator before the cache layer — keeps this module pure).
    - Reject month outside `[1, 12]` (RangeError) and year outside `[1900, 2100]` (RangeError) — sanity guards mirroring Python's implicit ranges.
  </behavior>
  <action>
    Implement `packages-ts/core/src/internal/cache/keys.ts`:
    ```typescript
    /** Build the canonical cache key for monthly observations. */
    export function cacheKeyForObservations(station: string, year: number, month: number): string {
      if (!Number.isInteger(year) || year < 1900 || year > 2100) throw new RangeError(`year out of range: ${year}`);
      if (!Number.isInteger(month) || month < 1 || month > 12) throw new RangeError(`month out of range: ${month}`);
      const yyyy = String(year).padStart(4, "0");
      const mm = String(month).padStart(2, "0");
      return `tradewinds:v1:observations:${station.toUpperCase()}:${yyyy}:${mm}`;
    }

    /** Build the canonical cache key for annual climate data. */
    export function cacheKeyForClimate(station: string, year: number): string {
      if (!Number.isInteger(year) || year < 1900 || year > 2100) throw new RangeError(`year out of range: ${year}`);
      const yyyy = String(year).padStart(4, "0");
      return `tradewinds:v1:climate:${station.toUpperCase()}:${yyyy}`;
    }
    ```

    Update `packages-ts/core/src/internal/cache/index.ts` barrel to re-export:
    ```typescript
    export {
      shouldSkipCacheForCurrentLstMonth,
      shouldSkipCacheForCurrentLstYear,
      isLiveSource,
      isWithinVolatileWindow,
    } from "./skip-rules.js";
    export { cacheKeyForObservations, cacheKeyForClimate } from "./keys.js";
    ```

    Write `tests/internal/cache/keys.test.ts`:
    - `cacheKeyForObservations("KNYC", 2025, 1)` → `"tradewinds:v1:observations:KNYC:2025:01"`.
    - `cacheKeyForObservations("knyc", 2025, 12)` → `"tradewinds:v1:observations:KNYC:2025:12"` (uppercase).
    - `cacheKeyForClimate("KNYC", 2025)` → `"tradewinds:v1:climate:KNYC:2025"`.
    - `cacheKeyForObservations("KNYC", 2025, 0)` throws RangeError; same for 13, -1, 1.5.
    - `cacheKeyForObservations("KNYC", 1899, 1)` throws RangeError; same for 2101, NaN, 2025.5.
  </action>
  <acceptance_criteria>
    - `pnpm --filter @tradewinds/core test -- keys` ≥ 8 cases all green.
    - `grep -n "padStart" packages-ts/core/src/internal/cache/keys.ts` confirms zero-padding.
    - `grep -n "cacheKeyForObservations\|cacheKeyForClimate" packages-ts/core/src/internal/cache/index.ts` confirms barrel exports.
  </acceptance_criteria>
</task>

<task type="auto" tdd="true">
  <name>Task 3: 5-case behavior fixture pinning cross-language skip behavior</name>
  <files>packages-ts/core/tests/internal/cache/fixtures/skip-rules-behavior.json, packages-ts/core/tests/internal/cache/skip-rules.test.ts</files>
  <read_first>
    - Task 1 + Task 2 outputs
    - `packages-ts/core/src/data/generated/stations.ts` (pick KNYC + one intl station, e.g. RJTT, with known LST offsets)
  </read_first>
  <behavior>
    - The fixture is JSON, captured by hand from the predicate definitions (NOT from a live Python run — the goal is to pin TS behavior for plan 06 wiring; Python parity is a CROSS-SDK-SYNC tracker, not a hard gate in this wave).
    - 5 cases minimum, covering the three skip rules:
      1. KNYC current LST month → skip true
      2. KNYC last month → skip false (cacheable)
      3. KNYC `.live` source → skip true (regardless of month)
      4. KNYC archive 10 days ago → volatile window true
      5. RJTT (UTC+9) UTC-Dec-31-late, LST = Jan 1 next year → skip current month=Jan
    - Each case has `{ id, station, year, month, source, eventDate, asOf, now, expected: { skipCurrentMonth, skipLive, skipVolatile } }`.
  </behavior>
  <action>
    1. Create `packages-ts/core/tests/internal/cache/fixtures/skip-rules-behavior.json`:
       ```json
       {
         "version": 1,
         "description": "TS-CACHE-02 5-case behavior fixture (per TS-W3 SC#2). Pins cache-skip semantics for cross-language regression. Python equivalent fixture: TODO (CROSS-SDK-SYNC parity ticket — back-port to packages/weather/tests/cache/fixtures/ when Python adopts the 30-day volatile rule).",
         "cases": [
           {
             "id": "case-1-knyc-current-lst-month",
             "station": "KNYC",
             "year": 2025,
             "month": 1,
             "source": "iem.archive",
             "eventDate": "2025-01-15",
             "asOf": "2025-01-15",
             "now": "2025-01-15T12:00:00Z",
             "expected": { "skipCurrentMonth": true, "skipLive": false, "skipVolatile": true }
           },
           {
             "id": "case-2-knyc-last-month-cacheable",
             "station": "KNYC",
             "year": 2024,
             "month": 12,
             "source": "iem.archive",
             "eventDate": "2024-11-15",
             "asOf": "2025-01-15",
             "now": "2025-01-15T12:00:00Z",
             "expected": { "skipCurrentMonth": false, "skipLive": false, "skipVolatile": false }
           },
           {
             "id": "case-3-live-source-never-cached",
             "station": "KNYC",
             "year": 2024,
             "month": 11,
             "source": "awc.live",
             "eventDate": "2024-11-15",
             "asOf": "2025-01-15",
             "now": "2025-01-15T12:00:00Z",
             "expected": { "skipCurrentMonth": false, "skipLive": true, "skipVolatile": false }
           },
           {
             "id": "case-4-volatile-window-10-days-ago",
             "station": "KNYC",
             "year": 2024,
             "month": 12,
             "source": "iem.archive",
             "eventDate": "2025-01-05",
             "asOf": "2025-01-15",
             "now": "2025-01-15T12:00:00Z",
             "expected": { "skipCurrentMonth": false, "skipLive": false, "skipVolatile": true }
           },
           {
             "id": "case-5-rjtt-utc-plus-9-year-wrap",
             "station": "RJTT",
             "year": 2026,
             "month": 1,
             "source": "iem.archive",
             "eventDate": "2026-01-01",
             "asOf": "2026-01-01",
             "now": "2025-12-31T20:00:00Z",
             "expected": { "skipCurrentMonth": true, "skipLive": false, "skipVolatile": true }
           }
         ]
       }
       ```

    2. Add a fixture-driven test block to `tests/internal/cache/skip-rules.test.ts`:
       ```typescript
       import fixtureData from "./fixtures/skip-rules-behavior.json" with { type: "json" };

       describe("skip-rules behavior fixture (5 cases — TS-W3 SC#2)", () =&gt; {
         for (const c of fixtureData.cases) {
           it(`${c.id}`, () =&gt; {
             const now = new Date(c.now);
             expect(shouldSkipCacheForCurrentLstMonth(c.station, c.year, c.month, now)).toBe(c.expected.skipCurrentMonth);
             expect(isLiveSource(c.source)).toBe(c.expected.skipLive);
             expect(isWithinVolatileWindow(c.eventDate, c.asOf, 30)).toBe(c.expected.skipVolatile);
           });
         }
       });
       ```

    3. Verify `RJTT` is actually in the codegen station table (TS-W1 added 60 intl stations). If not present, swap to an intl station that IS in the table — re-derive the expected LST offset from the registry to keep case-5 honest. Document the substitution in the fixture's `description` field.
  </action>
  <acceptance_criteria>
    - `pnpm --filter @tradewinds/core test -- skip-rules` runs the 5 fixture cases plus the unit tests; all green.
    - `grep -n '"version": 1' packages-ts/core/tests/internal/cache/fixtures/skip-rules-behavior.json` confirms versioning (future bumps document evolution).
    - All 5 expected fields match the implementation output (no test is x.it.skip or x.it.todo).
    - `grep -n "RJTT" packages-ts/core/src/data/generated/stations.ts` confirms the case-5 station is in the registry (else fixture documents a substitution).
  </acceptance_criteria>
</task>

</tasks>

<verification>
1. `pnpm --filter @tradewinds/core test -- cache` runs all cache test files (plan 01 + plan 02 + plan 03 — memory, fs, indexeddb, default, skip-rules, keys) and the 5-case fixture; all green.
2. `pnpm --filter @tradewinds/core run typecheck` clean.
3. `pnpm --filter @tradewinds/core run build` emits `dist/internal/cache/{skip-rules,keys}.{mjs,cjs,d.ts}` plus the existing files.
4. `grep -rn "@tradewinds/core/internal/cache" packages-ts/` (from the meta + weather packages) — no consumers wired yet; plan 06 adds them.
</verification>

<success_criteria>
- TS-CACHE-02 fully met — three skip rules ship as pure predicates; key generators emit the canonical string scheme; 5-case fixture pins behavior.
- All predicate functions have a `now` test seam — production code passes `new Date()` once at the call site (plan 06), keeping the cache module itself pure.
- The `isWithinVolatileWindow` divergence from Python is explicitly documented (TS-NEW; CROSS-SDK-SYNC ticket).
</success_criteria>

<review_discipline>
TypeScript-only changes under `packages-ts/core/**`. Per `.planning/REVIEW-DISCIPLINE.md`:

- **Reviewers**: codex `high` + **TypeScript Architect** (parallel).
- **Severity gate**: CRITICAL or HIGH only.
- **Loop**: fix on branch, re-dispatch both, cap at 3.
- **Rubric calibration**:
  - CRITICAL if `isLiveSource` regex differs from Python's `endswith(".live")` (e.g. `.includes(".live")` would match `awc.live.archive` and silently disable cache for non-live sources).
  - CRITICAL if `cacheKeyForObservations` produces a different string than the spec (`tradewinds:v1:observations:KNYC:2025:01`) — any change here breaks the cache root reading layer in plan 06.
  - HIGH if `shouldSkipCacheForCurrentLstMonth` reads `new Date()` directly instead of accepting an optional `now` (breaks fixture-based regression tests).
  - HIGH if `isWithinVolatileWindow` divergence from Python is NOT documented (silent cross-SDK drift — TS-W0 iter-1 caught this exact pattern in the Polymarket measure-mapping deletion).
  - HIGH if the fixture has fewer than 5 cases or doesn't exercise all three skip rules across at least 2 stations.
</review_discipline>

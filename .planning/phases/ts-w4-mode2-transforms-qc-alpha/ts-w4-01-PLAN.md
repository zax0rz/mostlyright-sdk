---
phase: ts-w4-mode2-transforms-qc-alpha
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - packages-ts/meta/src/research.ts
  - packages-ts/meta/src/mode2.ts
  - packages-ts/meta/src/index.ts
  - packages-ts/core/src/temporal/index.ts
  - packages-ts/meta/tests/mode2.test.ts
  - packages-ts/meta/tests/assert-source-identity.test.ts
autonomous: true
requirements:
  - TS-RESEARCH-02
  - TS-MODE2-01
must_haves:
  truths:
    - "researchBySource(station, source, fromDate, toDate) dispatches per source value and returns ReadonlyArray<Observation> tagged with the requested source"
    - "Unknown source string throws an Error (TradewindsError subclass or built-in ValidationError) before any network call"
    - "Empty result for a valid source returns [] (NOT throws)"
    - "assertSourceIdentity(rows, expectedSource, role) throws SourceMismatchError when at least one row's source !== expectedSource"
    - "assertSourceIdentity passes silently when every row's source === expectedSource (or rows is empty)"
    - "SourceMismatchError carries role: 'observations' | 'forecasts' | 'settlement' and toDict() emits snake_case { schema_source, data_source, role, catalog_warning }"
    - "researchBySource calls assertSourceIdentity internally as defense-in-depth before returning"
    - "Source enum is a const-union of EXACTLY ['iem.archive', 'iem.live', 'awc.live', 'ghcnh.archive'] (no enum keyword, tree-shake-safe)"
  artifacts:
    - path: packages-ts/meta/src/mode2.ts
      provides: "researchBySource + Mode2Source enum + SOURCE_ALIASES table"
    - path: packages-ts/meta/src/index.ts
      provides: "Barrel re-exports research + researchBySource + assertSourceIdentity + Mode2Source"
    - path: packages-ts/core/src/temporal/index.ts
      provides: "(unchanged) — re-confirms assertSourceIdentity is NOT moved here; lives in meta"
  key_links:
    - from: packages-ts/meta/src/mode2.ts
      to: "@tradewinds/weather"
      via: "imports the same fetchers research() uses (downloadIemAsos, downloadGhcnh, fetchAwcMetars) + their parsers"
      pattern: "from .@tradewinds/weather."
    - from: packages-ts/meta/src/mode2.ts
      to: "@tradewinds/core SourceMismatchError"
      via: "import { SourceMismatchError } from '@tradewinds/core'"
      pattern: "SourceMismatchError"
---

<objective>
Port Python Phase 3 Mode 2 dispatch to TS at the canonical location alongside `research()`. Three deliverables:

1. **`Mode2Source`** — `const`-union (NOT `enum`) of exactly the four source values: `'iem.archive' | 'iem.live' | 'awc.live' | 'ghcnh.archive'`. Mirrors Python `tradewinds.mode2._VALID_OBSERVATION_SOURCES` frozenset at the TS narrowed-to-canonical input vocabulary. TS does NOT accept bare `iem`/`awc`/`ghcnh` at the input boundary (the prompt's contract — TS narrows what Python widens, simpler is better; bare forms are only what parsers emit per-row).
2. **`researchBySource(station, source, fromDate, toDate, opts?)`** — Mode 2 entry point. Lives in `packages-ts/meta/src/mode2.ts` alongside `research()`. Calls the per-source fetcher directly (single source only — no merge), tags every row's `source` field, returns `ReadonlyArray<Observation>` with `source === expectedSource`. Invokes `assertSourceIdentity` internally before returning (defense-in-depth, matches Python `mode2.py:173-193`).
3. **`assertSourceIdentity(rows, expectedSource, role?)`** — throws `SourceMismatchError` if any row's `source !== expectedSource`. Lives in `packages-ts/meta/src/mode2.ts` (NOT in `@tradewinds/core` — it consumes the `Observation` shape from `@tradewinds/weather`, which `@tradewinds/core` must not depend on). `role` defaults to `'observations'` (the only role exercised in v0.1.0; `'forecasts'`/`'settlement'` reserved for v0.2).

`SourceMismatchError` already exists in `packages-ts/core/src/exceptions/index.ts` (lines 247-288, verified) with role + schemaSource + dataSource + catalogWarning. NO changes needed to exceptions — just consume the existing class.

Bundle-size discipline (TS-BUNDLE-01): Mode 2 ships at the **meta** package, not in `@tradewinds/core`. `@tradewinds/core` already sits ≤25 KB and must stay there. The meta package limit is 30 KB; Mode 2 should fit within ~2 KB headroom because it's thin orchestration over existing fetchers. A `pnpm size` check is part of the verification gate.
</objective>

<context_files>
- `.planning/REQUIREMENTS.md` TS-RESEARCH-02 + TS-MODE2-01 (canonical text — search for the IDs)
- `packages/core/src/tradewinds/mode2.py` lines 50-194 (Python source — port `_VALID_OBSERVATION_SOURCES`, `research_by_source`, `assert_source_identity`)
- `packages-ts/meta/src/research.ts` lines 1-100 + 740-870 (existing `research()` orchestrator; reuse the same fetcher imports, station resolution, date handling)
- `packages-ts/core/src/exceptions/index.ts` lines 247-288 (SourceMismatchError — already exists with role; toDict() emits snake_case `{ schema_source, data_source, role, catalog_warning }` from `payload()`)
- `packages-ts/weather/src/index.ts` (the fetcher + parser surface researchBySource consumes — note `Observation` type signature)
- `packages-ts/core/src/index.ts` (current root barrel — confirm SourceMismatchError is re-exported via `./exceptions/index.js`)
- `packages-ts/meta/src/index.ts` (current — likely just re-exports research; add researchBySource + Mode2Source + assertSourceIdentity)
- `packages-ts/meta/package.json` (no subpath change needed — researchBySource sits at the root `tradewinds` export)
- `package.json` root size-limit block (meta limit: 30 KB ESM gzipped)
</context_files>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Mode2Source enum + SOURCE_ALIASES + assertSourceIdentity</name>
  <files>packages-ts/meta/src/mode2.ts, packages-ts/meta/tests/assert-source-identity.test.ts</files>
  <read_first>
    - `packages/core/src/tradewinds/mode2.py` lines 50-63 (`_VALID_OBSERVATION_SOURCES` + `_SOURCE_ALIASES` — port the alias table to map canonical dotted forms to the bare parser-emitted tags)
    - `packages/core/src/tradewinds/mode2.py` lines 173-193 (`assert_source_identity` — raises SourceMismatchError with `role="observations"`, `schema_source=expected_source`, `data_source=distinct[0]`, `catalog_warning=None`)
    - `packages-ts/core/src/exceptions/index.ts` lines 247-288 (SourceMismatchError constructor signature: `new SourceMismatchError(message, { schemaSource, dataSource, role?, catalogWarning? })`)
    - `packages-ts/weather/src/index.ts` (Observation type — note its `source` is `'awc' | 'iem' | 'ghcnh'` bare form, NOT the dotted canonical form)
  </read_first>
  <behavior>
    - `Mode2Source` is a TypeScript `const`-union derived from `as const` array: `export const MODE2_SOURCES = ['iem.archive', 'iem.live', 'awc.live', 'ghcnh.archive'] as const; export type Mode2Source = typeof MODE2_SOURCES[number];`. NEVER use the `enum` keyword (defeats tree-shaking; per TS Architect rubric §5).
    - `SOURCE_ALIASES: ReadonlyMap<Mode2Source, ReadonlySet<string>>` maps each canonical dotted source to the bare parser-emitted tags that satisfy it. Per `packages/core/src/tradewinds/mode2.py:55-63`:
      - `'iem.archive'` → `{'iem', 'iem.archive'}`
      - `'iem.live'` → `{'iem', 'iem.live'}`
      - `'awc.live'` → `{'awc', 'awc.live'}`
      - `'ghcnh.archive'` → `{'ghcnh', 'ghcnh.archive'}`
    - `assertSourceIdentity<Row extends { source?: string | null }>(rows, expectedSource, role?)` — throws `SourceMismatchError` if any row's `source` field exists AND is not `expectedSource`. Rows with `source === undefined` or `source === null` are skipped (matches Python `assert_source_identity` `if "source" not in df.columns: return`).
    - `role` parameter defaults to `'observations'`. Type-narrowed to `SourceMismatchRole` (`'observations' | 'forecasts' | 'settlement'`) — re-export this type from `@tradewinds/core` so callers can refer to it.
    - The thrown SourceMismatchError carries: `schemaSource=expectedSource`, `dataSource=<first distinct mismatched source>`, `role=<role>`, `catalogWarning=null`. The message follows Python's pattern: `Mode 2 dispatch requested 'iem.archive' but received N row(s) with other sources: ['awc', 'ghcnh']`.
    - Public types: `export type { SourceMismatchRole } from '@tradewinds/core';`. Re-export so consumers don't need a `@tradewinds/core` deep import.
  </behavior>
  <action>
    1. Create `packages-ts/meta/src/mode2.ts`:
       ```typescript
       // Mode 2 — source-explicit research() variant.
       //
       // Mirrors packages/core/src/tradewinds/mode2.py. Mode 1 (the existing
       // `research()`) merges AWC > IEM > GHCNh; Mode 2 lets the caller pin
       // observations to a single named source for source-identified
       // training pairs (the workflow Vojtech wanted for backtests that
       // need source-identity invariants).
       //
       // Lives in @tradewinds/meta (alongside `research()`), NOT in
       // @tradewinds/core — `assertSourceIdentity` consumes the
       // @tradewinds/weather `Observation` type, which @tradewinds/core
       // must not depend on (would create a cycle).

       import { SourceMismatchError, type SourceMismatchRole } from "@tradewinds/core";
       import type { Observation } from "@tradewinds/weather";

       export type { SourceMismatchRole };

       /** Mode 2 canonical source vocabulary. */
       export const MODE2_SOURCES = [
         "iem.archive",
         "iem.live",
         "awc.live",
         "ghcnh.archive",
       ] as const;

       export type Mode2Source = (typeof MODE2_SOURCES)[number];

       /**
        * Map each canonical dotted source to the bare parser-emitted tags
        * that satisfy it. Parsers emit bare `iem`/`awc`/`ghcnh` per
        * packages-ts/weather; tradewinds' canonical vocab is dotted. The
        * alias table bridges both at the boundary without rewriting the
        * per-row source — downstream consumers see the truthful
        * parser-emitted tag.
        *
        * Mirrors packages/core/src/tradewinds/mode2.py:55-63.
        */
       export const SOURCE_ALIASES: ReadonlyMap<Mode2Source, ReadonlySet<string>> =
         new Map<Mode2Source, ReadonlySet<string>>([
           ["iem.archive", new Set(["iem", "iem.archive"])],
           ["iem.live", new Set(["iem", "iem.live"])],
           ["awc.live", new Set(["awc", "awc.live"])],
           ["ghcnh.archive", new Set(["ghcnh", "ghcnh.archive"])],
         ]);

       /** Type-guard: narrow an unknown string to Mode2Source. */
       export function isMode2Source(value: unknown): value is Mode2Source {
         return typeof value === "string"
           && (MODE2_SOURCES as readonly string[]).includes(value);
       }

       /**
        * Throw SourceMismatchError if any row's `source` field disagrees
        * with `expectedSource`. Empty rows / rows with no `source` field
        * pass silently (matches Python mode2.py:181-182).
        *
        * @param rows  rows to check (any shape with optional `source: string`)
        * @param expectedSource  the source the caller asked for
        * @param role  role-name vocabulary; defaults to 'observations'
        */
       export function assertSourceIdentity<Row extends { source?: string | null }>(
         rows: ReadonlyArray<Row>,
         expectedSource: string,
         role: SourceMismatchRole = "observations",
       ): void {
         const distinct = new Set<string>();
         let bad = 0;
         for (const r of rows) {
           const src = r?.source;
           if (typeof src !== "string") continue;
           if (src !== expectedSource) {
             distinct.add(src);
             bad += 1;
           }
         }
         if (bad === 0) return;
         const others = [...distinct].sort();
         const first = others[0] ?? "<unknown>";
         throw new SourceMismatchError(
           `Mode 2 dispatch requested '${expectedSource}' but received ${bad} row(s) with other sources: [${others.map(s => `'${s}'`).join(", ")}]`,
           {
             schemaSource: expectedSource,
             dataSource: first,
             role,
             catalogWarning: null,
           },
         );
       }
       ```

    2. Write `packages-ts/meta/tests/assert-source-identity.test.ts`:
       - Empty rows → no throw.
       - Rows without `source` field → no throw.
       - All rows have `source === 'iem.archive'` and `expectedSource === 'iem.archive'` → no throw.
       - 1 row with `source === 'awc'`, expected `'iem.archive'` → throws SourceMismatchError; `err.role === 'observations'`; `err.schemaSource === 'iem.archive'`; `err.dataSource === 'awc'`.
       - Mixed: 2 awc + 1 ghcnh, expected `'iem.archive'` → throws; `err.dataSource` is first sorted distinct (`'awc'`); error message contains both `'awc'` and `'ghcnh'`.
       - `err.toDict()` emits snake_case keys: `schema_source`, `data_source`, `role`, `catalog_warning` (use `Object.hasOwn` assertions; explicit NOT `schemaSource` etc.).
       - role parameter override: pass `role: 'forecasts'` → `err.role === 'forecasts'`.
       - `isMode2Source('iem.archive') === true`; `isMode2Source('iem') === false` (bare form rejected at input boundary).
       - `MODE2_SOURCES.length === 4` and contains exactly the four canonical strings.
  </behavior>
  <action>
    Use Write tool to create both files exactly as specified in `<behavior>`.
  </action>
  <acceptance_criteria>
    - `grep -n "export const MODE2_SOURCES" packages-ts/meta/src/mode2.ts` matches.
    - `grep -n "as const" packages-ts/meta/src/mode2.ts` confirms tuple-literal pattern (NOT `enum`).
    - `grep -nE "\\benum\\s" packages-ts/meta/src/mode2.ts` returns NO matches (zero `enum` keyword anywhere).
    - `grep -n "SourceMismatchError" packages-ts/meta/src/mode2.ts` confirms the existing class is consumed (NOT redefined).
    - `grep -n "role: 'observations'\\|role: \"observations\"" packages-ts/meta/src/mode2.ts` confirms default role.
    - `grep -n "schema_source\\|data_source\\|catalog_warning" packages-ts/meta/tests/assert-source-identity.test.ts` confirms snake_case assertions on toDict().
    - `pnpm --filter tradewinds test -- assert-source-identity` ≥ 9 cases all green.
  </acceptance_criteria>
</task>

<task type="auto" tdd="true">
  <name>Task 2: researchBySource + Mode 2 dispatch table</name>
  <files>packages-ts/meta/src/mode2.ts, packages-ts/meta/tests/mode2.test.ts</files>
  <read_first>
    - `packages/core/src/tradewinds/mode2.py` lines 66-170 (`research_by_source` — port the dispatch behavior)
    - `packages-ts/meta/src/research.ts` lines 740-870 (existing `research()` — same station resolution, date handling, fetcher invocation patterns)
    - `packages-ts/weather/src/index.ts` (the four fetcher exports: `fetchAwcMetars`, `downloadIemAsos`, `downloadGhcnh`, `downloadCliRange`; their parsers; the `Observation` type)
    - `packages-ts/meta/src/mode2.ts` (Task 1 output — Mode2Source + SOURCE_ALIASES + assertSourceIdentity)
  </read_first>
  <behavior>
    - Signature: `researchBySource(station: string, source: Mode2Source, fromDate: string, toDate: string, opts?: ResearchBySourceOptions): Promise<ReadonlyArray<Observation>>`.
    - `ResearchBySourceOptions` extends a subset of ResearchOptions: `{ signal?: AbortSignal; awcHours?: number; iemPolitenessMs?: number; ghcnhPolitenessMs?: number; now?: Date; cache?: CacheStore | null }`. (Forecast + climate opts are NOT included — Mode 2 returns observations only.)
    - **Unknown source rejection:** if `!isMode2Source(source)`, throw `new Error("Mode 2 source must be one of ['iem.archive', 'iem.live', 'awc.live', 'ghcnh.archive']; got '${source}'")`. Throw BEFORE any network call. Tests assert the throw is synchronous-ish (rejects the returned promise immediately without invoking fetchers).
    - **Dispatch table** (mirrors `_SOURCE_ALIASES`):
      - `'iem.archive'` → call `downloadIemAsos` (same code path as Mode 1's IEM ASOS branch, but isolated — no merge).
      - `'iem.live'` → reject in v0.1.0 with `new Error("Mode 2 source 'iem.live' not yet implemented in v0.1.0 (Python parity: requires per-month live IEM endpoint not yet ported). Use 'iem.archive' for historical IEM rows.")`. Documented as a known Parity-Ticket gap; v0.2 will add.
      - `'awc.live'` → call `fetchAwcMetars` + `awcToObservation`.
      - `'ghcnh.archive'` → call `downloadGhcnh` (US stations only — non-US throws `NotFoundError`).
    - Returns the rows filtered through `SOURCE_ALIASES.get(source)` — keep only rows whose bare `source` is in the alias set. Per-row `source` is NOT rewritten (Python mode2.py:161-166 — silent rewrite would break downstream Validator).
    - Calls `assertSourceIdentity(filtered, source, 'observations')` before returning (defense-in-depth — catches a fetcher mis-tagging bug).
    - Empty array (no rows match) is a valid return — NO throw on empty. The empty-result case still passes assertSourceIdentity (no rows → no mismatch).
    - Station resolution: reuse `normalizeStation` or equivalent from `research.ts`. If not exported, copy the resolution snippet — keep it tiny.
  </behavior>
  <action>
    1. Open `packages-ts/meta/src/research.ts` and confirm whether `normalizeStation` is exported or internal. If internal, extract a tiny `resolveStation(station: string): { code: string; icao: string; ghcnhId: string | null }` helper into a shared module (`packages-ts/meta/src/_station.ts`) OR copy the relevant lookup into `mode2.ts` (preferred to keep mode2 self-contained; the duplication is ~10 lines).

    2. Append to `packages-ts/meta/src/mode2.ts` (after assertSourceIdentity):
       ```typescript
       import { NotFoundError, STATION_BY_CODE, STATION_BY_ICAO } from "@tradewinds/core";
       import type { CacheStore } from "@tradewinds/core/internal/cache";
       import {
         awcToObservation,
         downloadGhcnh,
         downloadIemAsos,
         fetchAwcMetars,
         parseGhcnhPsv,
         parseIemCsv,
       } from "@tradewinds/weather";

       export interface ResearchBySourceOptions {
         signal?: AbortSignal;
         awcHours?: number;
         iemPolitenessMs?: number;
         ghcnhPolitenessMs?: number;
         now?: Date;
         cache?: CacheStore | null;
       }

       /**
        * Mode 2 source-explicit observation fetch.
        *
        * Dispatches to a single source's fetcher (no merge) and returns
        * raw Observations tagged with that source. Mirrors Python
        * tradewinds.mode2.research_by_source.
        *
        * @throws Error  if `source` is not one of MODE2_SOURCES
        * @throws Error  if `source === 'iem.live'` (v0.1.0 parity gap; use 'iem.archive')
        * @throws SourceMismatchError  if a row's source disagrees with `source`
        *                              (defense-in-depth; assertSourceIdentity)
        * @throws NotFoundError  if `source === 'ghcnh.archive'` and the station
        *                       is non-US (GHCNh PSV files are US-only)
        */
       export async function researchBySource(
         station: string,
         source: Mode2Source,
         fromDate: string,
         toDate: string,
         opts: ResearchBySourceOptions = {},
       ): Promise<ReadonlyArray<Observation>> {
         if (!isMode2Source(source)) {
           throw new Error(
             `Mode 2 source must be one of ${JSON.stringify(MODE2_SOURCES)}; got '${String(source)}'`,
           );
         }
         if (source === "iem.live") {
           throw new Error(
             "Mode 2 source 'iem.live' not yet implemented in v0.1.0 " +
             "(Parity-Ticket: requires per-month live IEM endpoint not yet ported). " +
             "Use 'iem.archive' for historical IEM rows.",
           );
         }
         // ... station resolution (copy or reuse from research.ts) ...
         // ... per-source dispatch:
         //     'awc.live'     → fetchAwcMetars + awcToObservation
         //     'iem.archive'  → downloadIemAsos + parseIemCsv
         //     'ghcnh.archive'→ downloadGhcnh + parseGhcnhPsv (US only — else NotFoundError)
         // ... filter through SOURCE_ALIASES.get(source)!
         // ... call assertSourceIdentity(filtered, source, 'observations')
         // ... return filtered;
       }
       ```

    3. Write `packages-ts/meta/tests/mode2.test.ts`:
       - Unknown source → throws Error synchronously (reject the promise; assert message contains the canonical list).
       - `source === 'iem.live'` → throws Error mentioning v0.1.0 parity gap.
       - Valid call: `researchBySource('NYC', 'iem.archive', '2024-06-01', '2024-06-30')` against msw recordings → returns ≥1 row; every row has `source === 'iem'` (bare parser tag — see SOURCE_ALIASES) OR `source === 'iem.archive'` (the alias accepts both).
       - All returned rows pass `assertSourceIdentity(rows, 'iem.archive')` — but wait: the bare tag `'iem'` is NOT equal to `'iem.archive'`, so this WILL throw. Resolution: per Python `mode2.py:147` the filter retains rows whose `source` is in the alias set; the per-row tag stays as parser-emitted; `assertSourceIdentity` then compares against `expectedSource` and fails. The Python code calls `assert_source_identity` on the OUTPUT — the test for that comparison uses the canonical expected, but the rows still carry the bare form, so the check would always fire on bare-form rows. Read Python carefully: `assert_source_identity` is defense-in-depth checking the per-row attr against the requested source. Python tolerates the parser-emitted bare tag because the WIDENED Python `_VALID_OBSERVATION_SOURCES` accepts both. In TS we narrowed to canonical-only. To preserve the invariant "all returned rows carry `source === expectedSource`" without rewriting per-row sources (CRITICAL per Python comment), our test must use bare-form-aware comparison: assertSourceIdentity in TS must compare against the alias set, NOT the bare string. Update assertSourceIdentity API: accept either a string OR a `ReadonlySet<string>` of acceptable values. Researcher passes `SOURCE_ALIASES.get(source)!`; downstream callers passing a bare string still work for the simple case. Document this in mode2.ts JSDoc.
       - **Updated test:** `researchBySource(...)` returns rows whose `source` is in `SOURCE_ALIASES.get('iem.archive')` (i.e. `'iem'` or `'iem.archive'`). NO SourceMismatchError thrown.
       - Empty result (date range with no data) → returns `[]`; no throw.
       - GHCNh non-US station → throws `NotFoundError`.
       - AWC: `researchBySource('NYC', 'awc.live', toDateStr, toDateStr)` returns rows with `source === 'awc'`.
       - Per-row source NEVER rewritten: input rows from `parseIemCsv` emit `source: 'iem'`; output rows still have `source: 'iem'` (NOT rewritten to `'iem.archive'`). Verify with `expect(rows[0].source).toBe('iem')` for the iem.archive call.

    4. Revise `assertSourceIdentity` signature in Task 1's `mode2.ts` to accept the alias-set form:
       ```typescript
       export function assertSourceIdentity<Row extends { source?: string | null }>(
         rows: ReadonlyArray<Row>,
         expected: string | ReadonlySet<string>,
         role: SourceMismatchRole = "observations",
       ): void {
         const accept = typeof expected === "string"
           ? new Set<string>([expected])
           : expected;
         // ... rest checks `if (!accept.has(src)) { bad += 1; distinct.add(src); }`
         // message uses [...accept].sort().join() as the "expected" label
       }
       ```
       Update Task 1's tests accordingly — the string-form test stays valid; add a new case asserting Set-form acceptance.
  </action>
  <acceptance_criteria>
    - `grep -n "export async function researchBySource" packages-ts/meta/src/mode2.ts` matches.
    - `grep -n "isMode2Source(source)" packages-ts/meta/src/mode2.ts` confirms the unknown-source guard runs BEFORE any fetcher import/call.
    - `grep -n "iem.live.*not yet implemented\\|iem.live'.*v0.1.0" packages-ts/meta/src/mode2.ts` confirms the v0.1.0 parity-gap throw.
    - `grep -n "SOURCE_ALIASES.get(source)" packages-ts/meta/src/mode2.ts` confirms filtering via alias table.
    - `grep -n "assertSourceIdentity.*source" packages-ts/meta/src/mode2.ts` confirms the defense-in-depth assertion runs before return.
    - `pnpm --filter tradewinds test -- mode2` ≥ 7 cases all green.
    - Per-row source NOT rewritten: test explicitly checks parser-emitted `'iem'` survives, NOT rewritten to `'iem.archive'`.
  </acceptance_criteria>
</task>

<task type="auto" tdd="true">
  <name>Task 3: Wire researchBySource into meta barrel + size-limit gate</name>
  <files>packages-ts/meta/src/index.ts, packages-ts/meta/tests/mode2.barrel.test.ts</files>
  <read_first>
    - `packages-ts/meta/src/index.ts` (current — minimal; mostly re-exports research)
    - `package.json` root size-limit block (meta limit: 30 KB ESM gzipped; @tradewinds/core limit: 25 KB)
    - `packages-ts/meta/tsup.config.ts` (entry config — confirm `src/mode2.ts` does NOT need a new entry; it's imported transitively via index.ts)
  </read_first>
  <behavior>
    - `packages-ts/meta/src/index.ts` adds re-exports for:
      - `researchBySource`
      - `Mode2Source` (type)
      - `MODE2_SOURCES` (const value — useful for caller validation)
      - `assertSourceIdentity`
      - `isMode2Source`
      - `SourceMismatchRole` (type — passthrough from @tradewinds/core)
    - These join the existing `research`, `PairsRow`, `ResearchOptions` exports.
    - Tree-shake check: a barrel test imports ONLY `research` and confirms the bundle does NOT pull in `researchBySource`'s code path when not used. Use vitest + a simple "imports compile" test, not bundle analysis (analysis is the size-limit gate's job).
    - **Size gate (TS-BUNDLE-01):** after build, `pnpm size` must show:
      - `@tradewinds/core` ESM ≤ 25 KB (UNCHANGED — Mode 2 lives in meta).
      - `tradewinds meta` ESM ≤ 30 KB (the gate; was ~28 KB pre-Mode-2; budget ~2 KB headroom for Mode 2's thin orchestration).
    - If `pnpm size` reports the meta bundle over 30 KB, the implementation MUST be slimmed before declaring this task done. Possible mitigations:
      - Inline tiny helpers instead of importing from `@tradewinds/weather` (probably not — fetchers are already imported by research()).
      - Lazy-import the iem.live throw branch (it's a one-line throw — negligible).
      - Push Mode 2 to a subpath export `tradewinds/mode2` so the root tradewinds bundle stays slim. This is the recommended fallback.
  </behavior>
  <action>
    1. Update `packages-ts/meta/src/index.ts` to re-export Mode 2:
       ```typescript
       // ... existing research re-exports unchanged ...
       export {
         assertSourceIdentity,
         isMode2Source,
         MODE2_SOURCES,
         researchBySource,
         SOURCE_ALIASES,
         type Mode2Source,
         type ResearchBySourceOptions,
         type SourceMismatchRole,
       } from "./mode2.js";
       ```

    2. Write `packages-ts/meta/tests/mode2.barrel.test.ts`:
       ```typescript
       import { describe, expect, it } from "vitest";
       import {
         assertSourceIdentity,
         isMode2Source,
         MODE2_SOURCES,
         researchBySource,
         type Mode2Source,
       } from "../src/index.js";

       describe("meta barrel — Mode 2 surface", () => {
         it("exports researchBySource", () => {
           expect(typeof researchBySource).toBe("function");
         });
         it("exports MODE2_SOURCES with exactly 4 canonical values", () => {
           expect(MODE2_SOURCES).toEqual([
             "iem.archive", "iem.live", "awc.live", "ghcnh.archive",
           ]);
         });
         it("exports isMode2Source + assertSourceIdentity", () => {
           expect(typeof isMode2Source).toBe("function");
           expect(typeof assertSourceIdentity).toBe("function");
         });
         it("Mode2Source type is the canonical union", () => {
           const _check: Mode2Source = "iem.archive"; // type-level check
           expect(isMode2Source(_check)).toBe(true);
         });
       });
       ```

    3. Run `pnpm --filter tradewinds run build && pnpm size` from the repo root. Assert both gates pass:
       - `@tradewinds/core` ≤ 25 KB.
       - `tradewinds meta` ≤ 30 KB.
       If meta is over 30 KB, switch Mode 2 to a subpath export pattern:
       - Add `"./mode2"` to `packages-ts/meta/package.json` exports (mirror the `@tradewinds/core/temporal` pattern from TS-W3 plan 04).
       - Add `entry: { mode2: 'src/mode2.ts' }` to `packages-ts/meta/tsup.config.ts`.
       - Keep root barrel re-exports for backward compat BUT document the subpath in the test (`import { researchBySource } from 'tradewinds/mode2'`).
       - Update root size-limit entries in `package.json` accordingly.

    4. Add a script entry `"size": "size-limit"` reference in the root if missing (already present per investigation), and run `pnpm run size` to capture the report.
  </action>
  <acceptance_criteria>
    - `grep -n "researchBySource\\|MODE2_SOURCES\\|assertSourceIdentity" packages-ts/meta/src/index.ts` confirms 3+ matches in the barrel.
    - `pnpm --filter tradewinds test -- mode2.barrel` 4+ cases green.
    - `pnpm -r run build` clean across all 5 TS packages.
    - `pnpm -r run typecheck` clean.
    - `pnpm run size` reports `@tradewinds/core` ≤ 25 KB AND `tradewinds meta` ≤ 30 KB (both gates).
    - If subpath fallback used: `grep -n '"./mode2"' packages-ts/meta/package.json` confirms the subpath export.
  </acceptance_criteria>
</task>

</tasks>

<verification>
1. `pnpm --filter tradewinds test -- mode2` runs all 3 test files (assert-source-identity, mode2, mode2.barrel); all green.
2. `pnpm --filter tradewinds run typecheck` clean.
3. `pnpm -r run build` clean across the 5 TS packages.
4. `pnpm run size` reports the meta bundle ≤ 30 KB AND core ≤ 25 KB.
5. From a downstream consumer: `import { researchBySource, type Mode2Source } from "tradewinds"` resolves. The thrown `SourceMismatchError` is `instanceof TradewindsError`.
6. Per-row `source` field assertion: a test runs `researchBySource('NYC', 'iem.archive', ...)` against msw and asserts `rows[0].source === 'iem'` (parser-emitted bare tag preserved, NOT rewritten to `'iem.archive'`). This is the silent-rewrite check called out in Python mode2.py:161-166.
</verification>

<success_criteria>
- TS-RESEARCH-02 fully met — `researchBySource` dispatches per source; rejects unknown source synchronously; `assertSourceIdentity` throws `SourceMismatchError` with `role` field set correctly.
- TS-MODE2-01 fully met — `MODE2_SOURCES` const-union (NOT enum), exactly 4 canonical values; `iem.live` documented v0.1.0 gap; per-row source identity invariant enforced via internal `assertSourceIdentity` call.
- Bundle gates hold: `@tradewinds/core` ≤ 25 KB (unchanged, Mode 2 in meta), `tradewinds meta` ≤ 30 KB.
- Empty-result returns `[]` (NOT throws).
- Per-row sources are NEVER rewritten by Mode 2 (Python parity — silent rewrite would break downstream Validator).
</success_criteria>

<review_discipline>
TypeScript-only changes under `packages-ts/meta/**` + light `packages-ts/core/**` re-export note. Per `.planning/REVIEW-DISCIPLINE.md`:

- **Reviewers**: codex `high` + **TypeScript Architect** (parallel).
- **Severity gate**: CRITICAL or HIGH only.
- **Loop**: fix on branch, re-dispatch, cap at 3.
- **Rubric calibration**:
  - CRITICAL if `researchBySource` silently rewrites the per-row `source` field from bare (`'iem'`) to dotted canonical (`'iem.archive'`) — the iter-1 finding documented in Python mode2.py:161-166. Downstream Validator + future MCP wire format depend on the parser-emitted tag being truthful.
  - CRITICAL if `MODE2_SOURCES` is an `enum` instead of a `const` array (defeats tree-shaking; per TS Architect rubric §5).
  - CRITICAL if unknown source is rejected AFTER a fetcher network call (would burn API quota for invalid input).
  - HIGH if `SourceMismatchError.toDict()` is asserted via camelCase (`schemaSource`) instead of snake_case (`schema_source`) — wire-format parity break vs Python.
  - HIGH if `iem.live` silently falls through to `iem.archive` (no throw) — silent v0.1.0 parity hole.
  - HIGH if `assertSourceIdentity` is moved into `@tradewinds/core` (would create core→weather dep cycle via `Observation` type).
  - HIGH if `pnpm run size` is not part of the verification gate (TS-BUNDLE-01 enforcement skipped).
  - HIGH if the per-row source-preserved test is absent (the CRITICAL above wouldn't be caught).
</review_discipline>

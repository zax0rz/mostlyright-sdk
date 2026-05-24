---
phase: ts-w2-parity-gate
plan: 04
type: execute
wave: 2
depends_on:
  - ts-w2-01
  - ts-w2-02
files_modified:
  - packages-ts/core/src/internal/merge/observations.ts
  - packages-ts/core/src/internal/merge/index.ts
  - packages-ts/core/src/index.ts
  - packages-ts/core/package.json
  - packages-ts/core/tests/internal/merge/observations.test.ts
  - packages-ts/core/tests/internal/merge/observations.property.test.ts
  - packages-ts/core/tests/internal/merge/observations.replay.test.ts
  - packages-ts/weather/src/_parsers/cli.ts
  - packages-ts/weather/src/index.ts
  - packages-ts/weather/tests/cli-merge.test.ts
autonomous: true
requirements:
  - TS-MERGE-01

must_haves:
  truths:
    - "mergeObservations(rows) dedups by (station_code, observed_at, observation_type), keeping the row with highest SOURCE_PRIORITY (awc=3 > iem=2 > ghcnh=1)."
    - "Tie behavior is STRICT > (not >=): on equal priority, the FIRST row seen wins (input-order dependent — byte-faithful to Python v0.14.1)."
    - "Unknown source string gets priority 0 and loses to any known source."
    - "mergeObservations relocates from packages-ts/weather/src/_parsers/cli.ts::mergeClimate's sibling concept into a dedicated module under @tradewinds/core (NOT @tradewinds/weather) — both observations + climate merge live under @tradewinds/core/internal/merge/."
    - "mergeClimate is migrated from packages-ts/weather/src/_parsers/cli.ts to packages-ts/core/src/internal/merge/climate.ts; the cli.ts re-export remains for backward compat OR is removed and the consumer (meta/research.ts) updated."
    - "Property test (fast-check): mergeObservations is permutation-stable on the restricted input class where no two rows share (station_code, observed_at, observation_type, source) — i.e. no same-key-same-priority duplicates. An arbitrary-shuffle stability test would FALSELY require divergence from Python's order-dependent same-priority tiebreak."
    - "Canonical-fetch-order replay test asserts that loading rows in their captured order (per the Plan 03 JSON fixtures' implied per-source ordering) and running mergeObservations produces byte-equivalent output across runs."
    - "Property test uses fast-check arbitraries to generate the restricted input class, NOT arbitrary shuffles."
  artifacts:
    - path: "packages-ts/core/src/internal/merge/observations.ts"
      provides: "mergeObservations + SOURCE_PRIORITY constant"
      exports: ["mergeObservations", "SOURCE_PRIORITY"]
    - path: "packages-ts/core/src/internal/merge/climate.ts"
      provides: "mergeClimate (migrated from weather/_parsers/cli.ts) + CLIMATE_REPORT_TYPE_PRIORITY re-export"
      exports: ["mergeClimate"]
    - path: "packages-ts/core/src/internal/merge/index.ts"
      provides: "barrel re-export for mergeObservations + mergeClimate"
      exports: ["mergeObservations", "mergeClimate", "SOURCE_PRIORITY"]
  key_links:
    - from: "packages-ts/core/src/internal/merge/observations.ts"
      to: "packages-ts/weather/src/_parsers/awc.ts (Observation type)"
      via: "shared Observation interface — IMPORTANT: this creates a core→weather type-only dep; choose a clean direction"
      pattern: "import.*Observation"
    - from: "packages-ts/core/src/index.ts"
      to: "internal/merge barrel"
      via: "re-export via subpath export @tradewinds/core/internal/merge"
      pattern: "internal/merge"
---

<objective>
Port Python's `_internal.merge.observations.merge_observations` (the AWC > IEM > GHCNh source-priority dedup) to TypeScript, and migrate the existing `mergeClimate` from `packages-ts/weather/src/_parsers/cli.ts` to its canonical home under `@tradewinds/core/internal/merge/`. Add fast-check property tests for the restricted-input permutation-stability invariant and a canonical-fetch-order replay test.

**Why this matters:** mergeObservations is THE policy that makes the parity gate work. Without it, the orchestrator (Plan 06) would emit all 3 source rows per timestamp instead of the priority-1 survivor, and `_obs_aggregates` (Plan 05) would compute high/low/mean over 3× the row count → parity off by a deterministic factor. Strict-> + first-seen-wins is byte-faithful semantics: Python preserved input order through `dict.values()` (insertion order); TS uses `Map.values()` with the same guarantee.

**Why restricted-input property tests:** an arbitrary-shuffle property test would FALSELY require TS to diverge from Python's order-dependent same-priority tiebreak. The restricted input class (no two rows share (key, source)) is the class where permutation IS stable — anything broader is the wrong test.

**Output:** New merge module under @tradewinds/core, climate-merge migration, 3 test files (unit + property + replay).
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@.planning/REVIEW-DISCIPLINE.md
@.planning/research/TS-SDK-DESIGN.md
@.planning/phases/ts-w2-parity-gate/PLAN.md
@.planning/phases/ts-w2-parity-gate/ts-w2-01-PLAN.md
@.planning/phases/ts-w2-parity-gate/ts-w2-02-PLAN.md
@packages/core/src/tradewinds/_internal/merge/observations.py
@packages/core/src/tradewinds/_internal/merge/climate.py
@packages-ts/weather/src/_parsers/cli.ts
@packages-ts/weather/src/_parsers/awc.ts
@packages-ts/core/src/index.ts
@packages-ts/core/package.json

<interfaces>
From Plans 01+02 (Wave 1 outputs):
```typescript
// packages-ts/weather/src/_parsers/awc.ts (widened in Plan 01)
export interface Observation {
  readonly station_code: string;
  readonly observed_at: string;
  readonly observation_type: "METAR" | "SPECI";
  readonly source: "awc" | "iem" | "ghcnh";
  // ... 26 more fields
}
```

Python source-of-truth for SOURCE_PRIORITY (verbatim from `packages/core/src/tradewinds/_internal/merge/observations.py:18`):
```python
SOURCE_PRIORITY: dict[str, int] = {"awc": 3, "iem": 2, "ghcnh": 1}
```

Python merge_observations (L21-43):
```python
def merge_observations(rows):
    best = {}
    for row in rows:
        key = (row["station_code"], row["observed_at"], row["observation_type"])
        priority = SOURCE_PRIORITY.get(row.get("source", ""), 0)
        if key not in best:
            best[key] = row  # first-seen
        else:
            existing_priority = SOURCE_PRIORITY.get(best[key].get("source", ""), 0)
            if priority > existing_priority:  # STRICT >, not >=
                best[key] = row
    return list(best.values())
```
</interfaces>

**Type-dep direction decision:** putting `mergeObservations` in `@tradewinds/core` while the `Observation` type lives in `@tradewinds/weather` creates a core→weather coupling. Two acceptable resolutions:
1. **Move Observation to core** (under `@tradewinds/core/internal/observation.ts`); weather imports it. CLEANER. Recommended.
2. **mergeObservations uses a generic `interface ObservationRow { station_code; observed_at; observation_type; source }`** — only the 4 fields it actually keys/priority-checks. The Observation type satisfies the constraint.

Choose option (2): keep `Observation` in weather, define a structural `ObservationKey`-like interface in core. This avoids the type migration AND respects the rubric §4 (function signatures shouldn't grow upstream when the use is structural).
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Port mergeObservations to @tradewinds/core/internal/merge with unit tests</name>
  <files>packages-ts/core/src/internal/merge/observations.ts, packages-ts/core/src/internal/merge/index.ts, packages-ts/core/src/index.ts, packages-ts/core/package.json, packages-ts/core/tests/internal/merge/observations.test.ts</files>
  <behavior>
    - `mergeObservations([rowA, rowB])` where rowA.source="iem", rowB.source="awc", same key → returns `[rowB]` (AWC wins on priority).
    - Same input reversed `[rowB, rowA]` → returns `[rowB]` (still AWC wins — order doesn't matter when priority differs).
    - `mergeObservations([rowA, rowB])` where both `source="iem"`, same key → returns `[rowA]` (first-seen wins on equal priority).
    - Same input reversed `[rowB, rowA]` → returns `[rowB]` (first-seen — DIFFERENT survivor — this is Python-faithful behavior).
    - Unknown source `"foo"` → priority 0; loses to any of {awc, iem, ghcnh}.
    - Different keys → both rows kept (no dedup).
    - Empty input → empty array.
    - Output order: `Array.from(map.values())` — insertion order, mirrors Python `dict.values()`.
    - Returned array is a fresh `readonly Observation[]` (not the original input array; not a `ReadonlyArray<...>` cast of an existing array).
  </behavior>
  <action>
    1. Create directory + module: `packages-ts/core/src/internal/merge/observations.ts`.

    2. **Define the structural input shape** (avoid circular import on `Observation`):
       ```typescript
       /** Subset of Observation fields mergeObservations needs to dedup + priority-rank. */
       export interface ObservationKey {
         readonly station_code: string;
         readonly observed_at: string;
         readonly observation_type: string; // METAR | SPECI in practice
         readonly source: string; // awc | iem | ghcnh in practice; unknowns get priority 0
       }
       ```

       `mergeObservations<T extends ObservationKey>(rows: ReadonlyArray<T>): ReadonlyArray<T>` — generic so the consumer (Plan 06) can pass the full `Observation` type without losing fields.

    3. **Port the constant verbatim** (matches `packages/core/src/tradewinds/_internal/merge/observations.py:18`):
       ```typescript
       export const SOURCE_PRIORITY: Readonly<Record<string, number>> = Object.freeze({
         awc: 3,
         iem: 2,
         ghcnh: 1,
       });
       ```

    4. **Port the function byte-faithfully**:
       ```typescript
       export function mergeObservations<T extends ObservationKey>(
         rows: ReadonlyArray<T>,
       ): ReadonlyArray<T> {
         const best = new Map<string, T>();
         for (const row of rows) {
           // Tuple key as a single string. SAFE: station_code, observed_at, observation_type all controlled by parsers; no embedded separator collisions.
           const key = `${row.station_code}\x00${row.observed_at}\x00${row.observation_type}`;
           const priority = SOURCE_PRIORITY[row.source] ?? 0;
           const existing = best.get(key);
           if (existing === undefined) {
             best.set(key, row);
             continue;
           }
           const existingPriority = SOURCE_PRIORITY[existing.source] ?? 0;
           if (priority > existingPriority) {
             // STRICT >: on equal priority, first-seen stays (do NOT overwrite).
             best.set(key, row);
           }
         }
         return Array.from(best.values());
       }
       ```

       **Why `\x00` separator:** null byte. station_code is `[A-Z]{3,4}`, observed_at is `\d{4}-...Z`, observation_type is `METAR|SPECI` — none of these can contain a literal `\x00`. Defense against unrelated bugs in upstream parsers leaking weird chars.

    5. Create barrel `packages-ts/core/src/internal/merge/index.ts`:
       ```typescript
       export { mergeObservations, SOURCE_PRIORITY, type ObservationKey } from "./observations.js";
       export { mergeClimate } from "./climate.js"; // populated in Task 2
       ```

    6. **Add the subpath export** in `packages-ts/core/package.json`:
       ```jsonc
       "exports": {
         ".": { ... existing ... },
         "./internal/bounds": { ... existing ... },
         "./internal/convert": { ... existing ... },
         "./internal/merge": {
           "types": "./dist/internal/merge/index.d.ts",
           "import": "./dist/internal/merge/index.mjs",
           "require": "./dist/internal/merge/index.cjs"
         }
       }
       ```
       Mirror the bounds/convert subpath pattern (TS-W1 iter-1 HIGH 4).

    7. Update `packages-ts/core/src/index.ts` — do NOT add a wildcard export of merge from the main entry (keep it as a deep import for tree-shaking, matching the bounds/convert pattern).

    8. Update `tsup.config.ts` for core: ensure `internal/merge/index.ts` is in the entry list (mirror bounds/convert config).

    9. **Tests** (`packages-ts/core/tests/internal/merge/observations.test.ts`):
       - Cross-source priority wins regardless of input order.
       - Equal-source equal-priority: first-seen wins; reversed order produces different survivor.
       - Unknown source string ("polymarket", "foo") → priority 0; loses to awc/iem/ghcnh.
       - Different (station, observed_at, observation_type) combinations: all kept.
       - METAR vs SPECI at same (station, observed_at) are SEPARATE keys → both kept.
       - Empty input → `[]`.
       - SOURCE_PRIORITY frozen check (`Object.isFrozen(SOURCE_PRIORITY)` is true).
       - Type-level: `mergeObservations([{...full Observation...}])` returns `ReadonlyArray<Observation>` (compile-time check via dtslint-style assertion or just `const _: ReadonlyArray<Observation> = mergeObservations([...])`).

    10. Verify `pnpm --filter @tradewinds/core build` produces the `dist/internal/merge/index.{mjs,cjs,d.ts}` artifacts.
  </action>
  <verify>
    <automated>pnpm --filter @tradewinds/core test -- --run merge/observations.test &amp;&amp; pnpm --filter @tradewinds/core build</automated>
  </verify>
  <done>
    Unit tests pass; `mergeObservations` is callable from `@tradewinds/core/internal/merge`; the subpath export resolves under `pnpm typecheck`; SOURCE_PRIORITY is frozen + matches Python verbatim; strict-> + first-seen-wins behavior is observable from tests.
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Migrate mergeClimate from weather to core/internal/merge</name>
  <files>packages-ts/core/src/internal/merge/climate.ts, packages-ts/weather/src/_parsers/cli.ts, packages-ts/weather/src/index.ts, packages-ts/meta/src/research.ts, packages-ts/weather/tests/cli-merge.test.ts, packages-ts/core/tests/internal/merge/climate.test.ts</files>
  <behavior>
    - `mergeClimate(rows)` lives at `@tradewinds/core/internal/merge` (NOT `@tradewinds/weather`).
    - `@tradewinds/weather` re-exports `mergeClimate` for backward compatibility BUT prefer fixing consumers to import from core directly.
    - Existing TS-W1 tests for `mergeClimate` continue to pass (the function semantics don't change — only its home moves).
    - `meta/src/research.ts` imports `mergeClimate` from `@tradewinds/core/internal/merge` (or via the convenience barrel) instead of `@tradewinds/weather`.
  </behavior>
  <action>
    1. Create `packages-ts/core/src/internal/merge/climate.ts`:
       - Copy the `mergeClimate` function body from `packages-ts/weather/src/_parsers/cli.ts:261-278`.
       - Define a structural `ClimateKey` interface (mirror Task 1's `ObservationKey` pattern):
         ```typescript
         export interface ClimateKey {
           readonly station_code: string;
           readonly observation_date: string;
           readonly report_type_priority: number;
         }
         ```
       - Generic signature: `mergeClimate<T extends ClimateKey>(rows: ReadonlyArray<T>): ReadonlyArray<T>`.
       - Use `\x00` separator pattern from Task 1.
       - Comment block citing the Python source (`packages/core/src/tradewinds/_internal/merge/climate.py:45-68`) and PR commit info same way Task 1 does for observations.

    2. **Remove** the `mergeClimate` function body from `packages-ts/weather/src/_parsers/cli.ts`. Replace with a re-export:
       ```typescript
       // Backward-compat re-export. mergeClimate canonically lives at
       // @tradewinds/core/internal/merge (TS-W2 Plan 04). Imports from
       // @tradewinds/weather continue to work.
       export { mergeClimate } from "@tradewinds/core/internal/merge";
       ```

       Keep the existing `ClimateObservation` type in cli.ts — it has more fields than `ClimateKey` (it's the full row shape) and is the parser's product.

    3. Update `packages-ts/weather/src/index.ts`: the existing `mergeClimate` export line still resolves (now via the re-export). No-op IF the existing export line uses `export { mergeClimate } from "./_parsers/cli.js"` — verify it does.

    4. Update `packages-ts/meta/src/research.ts`: change the import to come from `@tradewinds/core/internal/merge`:
       ```typescript
       import { mergeClimate } from "@tradewinds/core/internal/merge";
       ```
       (currently imports from `@tradewinds/weather`). DO NOT remove the function call usage.

    5. **Create `packages-ts/core/tests/internal/merge/climate.test.ts`**: port the relevant tests from `packages-ts/weather/tests/iem-cli.test.ts` (whichever ones test mergeClimate directly). Tests should cover:
       - Strict-> tiebreak: two `final` rows for same (station, date) — first-seen wins.
       - `preliminary` (priority 1.0) → `final` (priority 3.0) replaces.
       - `final` → `preliminary` does NOT replace.
       - Empty input → `[]`.
       - Missing `report_type_priority` on a row → treated as 0.0.

    6. **Create `packages-ts/weather/tests/cli-merge.test.ts`**: a smaller test that asserts the backward-compat re-export from `@tradewinds/weather` still works:
       ```typescript
       import { mergeClimate as fromWeather } from "@tradewinds/weather";
       import { mergeClimate as fromCore } from "@tradewinds/core/internal/merge";
       it("re-exports point at the same function", () => {
         expect(fromWeather).toBe(fromCore);
       });
       ```

    7. Run full test suite for both packages: `pnpm -r test --run` should still be green (existing TS-W1 tests rely on `mergeClimate` from @tradewinds/weather).
  </action>
  <verify>
    <automated>pnpm --filter @tradewinds/core test -- --run merge/climate.test &amp;&amp; pnpm --filter @tradewinds/weather test -- --run cli-merge</automated>
  </verify>
  <done>
    `mergeClimate` is canonically in core; the weather barrel re-export still works for backward-compat; meta/research.ts imports from core; all TS-W1 mergeClimate tests still pass; new unit tests in core cover the strict-> + first-seen-wins invariant.
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 3: Add fast-check property test + canonical-fetch-order replay test</name>
  <files>packages-ts/core/tests/internal/merge/observations.property.test.ts, packages-ts/core/tests/internal/merge/observations.replay.test.ts, packages-ts/core/package.json</files>
  <behavior>
    - Property test (restricted-input permutation stability): for any input where no two rows share `(station_code, observed_at, observation_type, source)`, `mergeObservations(shuffleRows(rows))` produces the SAME set of survivors as `mergeObservations(rows)` (Set equality, not list equality — survivors are stable even if output order differs across permutations).
    - Property test runs ≥ 100 fast-check examples (default `numRuns`).
    - **DOES NOT** assert arbitrary-shuffle stability of LIST equality OR shuffle stability on inputs with same-key-same-priority duplicates — both would falsely fail because Python's first-seen tiebreak is input-order dependent.
    - Canonical-fetch-order replay test: load a synthetic mixed-source row sequence representing what a real fetch-order would produce (AWC first, then IEM yearly chunk, then GHCNh yearly chunk), call mergeObservations TWICE, assert identical output bytes (via JSON.stringify equality).
  </behavior>
  <action>
    1. **Add fast-check dep:** `pnpm --filter @tradewinds/core add -D fast-check@^3` (latest fast-check 3.x supports ESM + TS).
       Verify with `pnpm --filter @tradewinds/core list fast-check`.

    2. **Property test** (`packages-ts/core/tests/internal/merge/observations.property.test.ts`):
       ```typescript
       import { describe, it, expect } from "vitest";
       import fc from "fast-check";
       import { mergeObservations, type ObservationKey } from "../../../src/internal/merge/observations.js";

       // Restricted arbitrary: no two rows share (station_code, observed_at, observation_type, source).
       // Generate by building a Set<keyString> and rejecting duplicates.
       const sourceArb = fc.constantFrom("awc", "iem", "ghcnh");
       const stationArb = fc.constantFrom("NYC", "ORD", "LAX", "MIA", "MSY");
       const observedAtArb = fc.integer({ min: 1700000000, max: 1800000000 }).map(
         (ts) => new Date(ts * 1000).toISOString().replace(/\.\d+Z$/, "Z"),
       );
       const obsTypeArb = fc.constantFrom("METAR", "SPECI");

       function rowArb() {
         return fc.record({
           station_code: stationArb,
           observed_at: observedAtArb,
           observation_type: obsTypeArb,
           source: sourceArb,
         });
       }

       function uniquePerSourceArb() {
         return fc.array(rowArb(), { minLength: 0, maxLength: 50 }).map((rows) => {
           // Reject rows that collide on (station, observed_at, observation_type, source).
           const seen = new Set<string>();
           const out: ObservationKey[] = [];
           for (const r of rows) {
             const k = `${r.station_code}|${r.observed_at}|${r.observation_type}|${r.source}`;
             if (seen.has(k)) continue;
             seen.add(k);
             out.push(r);
           }
           return out;
         });
       }

       function shuffleRows<T>(rows: ReadonlyArray<T>, seed: number): ReadonlyArray<T> {
         // Deterministic shuffle using xorshift from seed.
         const arr = [...rows];
         let s = seed | 0;
         for (let i = arr.length - 1; i > 0; i--) {
           s ^= s << 13;
           s ^= s >>> 17;
           s ^= s << 5;
           const j = Math.abs(s) % (i + 1);
           [arr[i], arr[j]] = [arr[j]!, arr[i]!];
         }
         return arr;
       }

       function survivorSet(rows: ReadonlyArray<ObservationKey>): Set<string> {
         // Identify each survivor by the same priority-distinguishing key fields:
         // (station_code, observed_at, observation_type, source).
         const merged = mergeObservations(rows);
         return new Set(
           merged.map((r) => `${r.station_code}|${r.observed_at}|${r.observation_type}|${r.source}`),
         );
       }

       describe("mergeObservations — restricted-input permutation stability (TS-W2 SC#4)", () => {
         it("survivor SET equals across permutations when no same-(key, source) duplicates exist", () => {
           fc.assert(
             fc.property(
               uniquePerSourceArb(),
               fc.integer({ min: -(2 ** 31), max: 2 ** 31 - 1 }),
               (rows, seed) => {
                 const baseline = survivorSet(rows);
                 const shuffled = survivorSet(shuffleRows(rows, seed));
                 expect(shuffled).toEqual(baseline);
               },
             ),
             { numRuns: 200 },
           );
         });
       });
       ```

       **Critical:** the test asserts SET equality on the (station, observed_at, observation_type, source) tuples — NOT list-order equality. Within an equal-priority bucket the restricted arbitrary guarantees there is no tiebreak to lose: each (key, source) is unique, so the survivor for each key is deterministic.

       Add comment explaining WHY this restriction matters (cite stub PLAN SC#4 text verbatim — "an arbitrary-shuffle stability test would FALSELY require TS to diverge from Python's order-dependent same-priority-tiebreak behavior").

    3. **Canonical-fetch-order replay test** (`packages-ts/core/tests/internal/merge/observations.replay.test.ts`):
       ```typescript
       import { describe, it, expect } from "vitest";
       import { mergeObservations } from "../../../src/internal/merge/observations.js";

       // Synthetic fetch-order: AWC live first (recent timestamps), then IEM yearly chunk
       // (broader, historical), then GHCNh yearly chunk (broader, includes same-key
       // overlaps with IEM at lower priority). Mirrors what `_fetch_observations_range`
       // sees in production.
       const CANONICAL_ROWS = Object.freeze([
         // AWC chunk
         { station_code: "NYC", observed_at: "2025-01-08T14:51:00Z", observation_type: "METAR", source: "awc" },
         { station_code: "NYC", observed_at: "2025-01-08T15:51:00Z", observation_type: "METAR", source: "awc" },
         // IEM chunk
         { station_code: "NYC", observed_at: "2025-01-08T14:51:00Z", observation_type: "METAR", source: "iem" },
         { station_code: "NYC", observed_at: "2025-01-08T15:51:00Z", observation_type: "METAR", source: "iem" },
         { station_code: "NYC", observed_at: "2025-01-08T16:51:00Z", observation_type: "METAR", source: "iem" },
         { station_code: "NYC", observed_at: "2025-01-08T16:55:00Z", observation_type: "SPECI", source: "iem" },
         // GHCNh chunk
         { station_code: "NYC", observed_at: "2025-01-08T14:51:00Z", observation_type: "METAR", source: "ghcnh" },
         { station_code: "NYC", observed_at: "2025-01-08T15:51:00Z", observation_type: "METAR", source: "ghcnh" },
         { station_code: "NYC", observed_at: "2025-01-08T16:51:00Z", observation_type: "METAR", source: "ghcnh" },
         { station_code: "NYC", observed_at: "2025-01-08T17:51:00Z", observation_type: "METAR", source: "ghcnh" },
       ] as const);

       describe("mergeObservations — canonical-fetch-order replay (TS-W2 SC#4)", () => {
         it("produces byte-identical output across runs given identical input order", () => {
           const run1 = JSON.stringify(mergeObservations([...CANONICAL_ROWS]));
           const run2 = JSON.stringify(mergeObservations([...CANONICAL_ROWS]));
           expect(run1).toEqual(run2);
         });

         it("AWC wins over IEM and GHCNh at same key", () => {
           const merged = mergeObservations([...CANONICAL_ROWS]);
           const at1451 = merged.find((r) => r.observed_at === "2025-01-08T14:51:00Z" && r.observation_type === "METAR");
           expect(at1451?.source).toEqual("awc");
         });

         it("IEM wins over GHCNh when AWC absent", () => {
           const merged = mergeObservations([...CANONICAL_ROWS]);
           const at1651 = merged.find((r) => r.observed_at === "2025-01-08T16:51:00Z" && r.observation_type === "METAR");
           expect(at1651?.source).toEqual("iem");
         });

         it("GHCNh survives when neither AWC nor IEM has a row", () => {
           const merged = mergeObservations([...CANONICAL_ROWS]);
           const at1751 = merged.find((r) => r.observed_at === "2025-01-08T17:51:00Z");
           expect(at1751?.source).toEqual("ghcnh");
         });

         it("SPECI from IEM is kept separately from METAR (different observation_type key)", () => {
           const merged = mergeObservations([...CANONICAL_ROWS]);
           const speci = merged.filter((r) => r.observation_type === "SPECI");
           expect(speci).toHaveLength(1);
           expect(speci[0]?.source).toEqual("iem");
         });

         it("survivor count = 5 (one per unique (key, observation_type))", () => {
           const merged = mergeObservations([...CANONICAL_ROWS]);
           expect(merged).toHaveLength(5);
         });
       });
       ```

    4. Run both new tests: `pnpm --filter @tradewinds/core test -- --run merge`.
  </action>
  <verify>
    <automated>pnpm --filter @tradewinds/core test -- --run merge</automated>
  </verify>
  <done>
    Property test passes 200 fast-check runs without shrinking to a failing case; replay test confirms cross-run determinism + the AWC/IEM/GHCNh priority cascade is observable in the survivor source field; fast-check dep recorded in core/package.json `devDependencies`; `pnpm typecheck` clean.
  </done>
</task>

</tasks>

<verification>
- 4 test files green: `observations.test.ts`, `climate.test.ts`, `observations.property.test.ts`, `observations.replay.test.ts`, `cli-merge.test.ts`.
- `mergeObservations` lives at `@tradewinds/core/internal/merge`; `mergeClimate` migrated to the same module.
- `@tradewinds/weather` still re-exports `mergeClimate` (backward compat).
- `@tradewinds/meta/src/research.ts` imports `mergeClimate` from `@tradewinds/core`.
- SOURCE_PRIORITY frozen + matches Python verbatim `{awc: 3, iem: 2, ghcnh: 1}`.
- Property test asserts RESTRICTED-input permutation stability (NOT arbitrary-shuffle); comment explicitly cites the SC#4 rationale.
- `pnpm -r test --run` green for all 5 packages (no regression).
- `pnpm -r build` green (subpath export resolves).
- `pnpm -r biome check` clean.
</verification>

<success_criteria>
Maps to TS-W2 stub SC#4: "mergeObservations(rows) reproduces Python source priority {awc:3, iem:2, ghcnh:1} + strict-> + first-seen tiebreak. mergeClimate(rows) dedups by (stationCode, observationDate) with REPORT_TYPE_PRIORITY from codegen. Property test (fast-check) asserts merge produces row-equivalent output across shuffleRows(rows) for the restricted input class where no two rows share the same (stationCode, observedAt, observationType) AND sourcePriority — i.e. permutation-stable on inputs WITHOUT same-priority duplicate-key conflicts. A separate canonical-fetch-order replay test asserts the parity-fixture HTTP recordings, replayed in their captured order, produce byte-equivalent merged output across runs."

- mergeObservations: verified in Task 1 + Task 3.
- mergeClimate: migrated + verified in Task 2.
- Restricted-input property test: Task 3.
- Canonical-fetch-order replay: Task 3 (synthetic data version; full HTTP-recording replay is Plan 08's job).
</success_criteria>

<output>
After completion, create `.planning/phases/ts-w2-parity-gate/ts-w2-04-SUMMARY.md` documenting:
- Final API at `@tradewinds/core/internal/merge` (mergeObservations, mergeClimate, SOURCE_PRIORITY).
- mergeClimate migration path (where it moved from / where the backward-compat re-export lives).
- Property test design rationale (restricted input class) — IMPORTANT for reviewers who might suggest "why not arbitrary shuffle".
- fast-check dep version added.
- Test count delta.
</output>

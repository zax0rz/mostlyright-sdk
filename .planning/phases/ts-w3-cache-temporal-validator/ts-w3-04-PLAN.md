---
phase: ts-w3-cache-temporal-validator
plan: 04
type: execute
wave: 4
depends_on: []
files_modified:
  - packages-ts/core/src/temporal/timepoint.ts
  - packages-ts/core/src/temporal/knowledge-view.ts
  - packages-ts/core/src/temporal/leakage.ts
  - packages-ts/core/src/temporal/index.ts
  - packages-ts/core/src/index.ts
  - packages-ts/core/package.json
  - packages-ts/core/tests/temporal/timepoint.test.ts
  - packages-ts/core/tests/temporal/knowledge-view.test.ts
  - packages-ts/core/tests/temporal/leakage.test.ts
  - packages-ts/core/tests/temporal/knowledge-view.property.test.ts
autonomous: true
requirements:
  - TS-TEMPORAL-01
  - TS-TEMPORAL-02
must_haves:
  truths:
    - "TimePoint(value) rejects naive datetimes (Date with no tz info from ISO string parse)"
    - "TimePoint(value) rejects date-only ISO strings (e.g. '2026-05-21')"
    - "TimePoint(value) rejects NaN, Infinity, -Infinity"
    - "TimePoint.now() returns a TimePoint for current UTC time"
    - "TimePoint exposes toUTCDate(), toISOString() (always ends in 'Z'), asZone(tz), equals/before/after"
    - "KnowledgeView&lt;Row&gt;(rows, asOf).rows() returns only rows where knowledge_time &lt;= asOf"
    - "KnowledgeView.asOf getter returns the asOf TimePoint"
    - "assertNoLeakage(rows, asOf) throws LeakageError with toDict() shape { as_of, violating_count, sample_violations } (snake_case matching Python wire shape)"
    - "LeakageDetector(asOf).check(rows) is a thin wrapper over assertNoLeakage"
    - "fast-check property test asserts the filter invariant over [2018-01-01, 2027-12-31] UTC date range"
  artifacts:
    - path: packages-ts/core/src/temporal/timepoint.ts
      provides: "TimePoint class — UTC-aware timestamp wrapper with naive-input rejection"
    - path: packages-ts/core/src/temporal/knowledge-view.ts
      provides: "KnowledgeView&lt;Row extends { knowledge_time: string }&gt; — temporal filter"
    - path: packages-ts/core/src/temporal/leakage.ts
      provides: "assertNoLeakage + LeakageDetector — loud leakage assertion"
    - path: packages-ts/core/src/temporal/index.ts
      provides: "Barrel re-exports TimePoint, KnowledgeView, LeakageDetector, assertNoLeakage"
  key_links:
    - from: packages-ts/core/src/index.ts
      to: "temporal/index.ts re-export"
      via: "export * from './temporal/index.js'"
      pattern: "from.*temporal"
---

<objective>
Port the three temporal-safety primitives from Python at the canonical `@tradewinds/core/temporal` subpath:

1. **`TimePoint`** — UTC-aware timestamp wrapper that rejects naive datetimes, date-only ISO strings, and NaN/Infinity loudly at construction. Mirrors `packages/core/src/tradewinds/core/temporal/timepoint.py`.
2. **`KnowledgeView&lt;Row&gt;`** — temporal filter returning `rows()` where `knowledge_time <= asOf`. Mirrors Python `KnowledgeView`.
3. **`LeakageDetector` + `assertNoLeakage`** — loud assertion variant that throws `LeakageError` (already defined in `@tradewinds/core/exceptions` with `{ asOf, violatingCount, sampleViolations }` properties and `toDict()` emitting snake_case `{ as_of, violating_count, sample_violations }`).

Independent of plan 01-03 (no cache dependency) — runs in Wave 4 in parallel with plan 03 if scheduled there, but listed as a separate wave here for sequencing clarity in execution.

The fast-check property test (TS-W3 SC#3) is THE acceptance criterion — generate arbitrary `(rows, asOf)` over the constrained `[2018-01-01, 2027-12-31]` UTC range and assert KnowledgeView's filter invariant for every generated case.
</objective>

<context_files>
- `.planning/REQUIREMENTS.md` TS-TEMPORAL-01 + TS-TEMPORAL-02 (canonical text)
- `.planning/research/TS-SDK-DESIGN.md` §6.3 lines 332-356 (TS API canonical signatures)
- `packages/core/src/tradewinds/core/temporal/timepoint.py` (Python source — 254 lines; the naive/date-only/NaN rejection logic)
- `packages/core/src/tradewinds/core/temporal/knowledge_view.py` (Python source — column required, tz-aware UTC required, defensive copy on `.dataframe()`)
- `packages/core/src/tradewinds/core/temporal/leakage.py` (Python source — `_SAMPLE_CAP = 10`, the `sample_violations` shape, the LeakageError raise)
- `packages-ts/core/src/exceptions/index.ts` lines 290-322 (TS LeakageError — already defined with `toDict()` emitting `as_of`/`violating_count`/`sample_violations`; just consume it)
- `packages-ts/core/src/snapshot.ts` (TS-W1 — for reference on testing Date math)
- `packages-ts/core/package.json` (add `./temporal` subpath export)
</context_files>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: TimePoint implementation + tests</name>
  <files>packages-ts/core/src/temporal/timepoint.ts, packages-ts/core/tests/temporal/timepoint.test.ts</files>
  <read_first>
    - `packages/core/src/tradewinds/core/temporal/timepoint.py` (full file — port the rejection branches exactly)
    - `.planning/research/TS-SDK-DESIGN.md` lines 334-344 (TS API surface)
  </read_first>
  <behavior>
    - Constructor accepts `Date | string`. Rejects:
      - `Date` constructed from a naive ISO string (e.g. `new Date("2026-05-21T10:00:00")` — note Date stores epoch ms, so "naive" here means the SOURCE string had no zone; we detect this from STRING inputs, not from `Date` objects).
      - ISO strings with no time component (e.g. `"2026-05-21"`).
      - ISO strings with no timezone offset (e.g. `"2026-05-21T10:00:00"` — no `Z`, no `+HH:MM`, no `-HH:MM`).
      - `NaN`, `Infinity`, `-Infinity` (passed via `new Date(NaN)` or via numeric string).
      - Empty / whitespace strings.
    - For `Date` input: the Date itself is timezone-agnostic (just epoch ms). Reject only `NaN`/`Infinity` underlying value (`isNaN(date.getTime())`). Accept any other Date.
    - For `string` input: parse and assert presence of timezone indicator BEFORE handing to `Date.parse` (which silently localizes naive strings on some engines).
    - Methods: `toUTCDate(): Date` (returns the underlying Date); `toISOString(): string` (always ends in `'Z'` — use `Date.prototype.toISOString()`); `asZone(tz: string): string` (ISO-like in IANA tz via `Intl.DateTimeFormat`); `equals(other)`, `before(other)`, `after(other)`.
    - Class method: `TimePoint.now()` → `new TimePoint(new Date())`.
    - Immutable (no setters; private `_utc` field via `#utc` or `readonly`).
  </behavior>
  <action>
    Implement `packages-ts/core/src/temporal/timepoint.ts`:
    ```typescript
    /**
     * UTC-aware timestamp wrapper.
     *
     * Mirrors `packages/core/src/tradewinds/core/temporal/timepoint.py`. Rejects
     * naive ISO strings, date-only ISO strings, NaN/Infinity at construction.
     *
     * Note on Date inputs: a JS Date is just epoch ms with no zone metadata.
     * "Naive" only applies to STRING inputs (where we can inspect the source
     * for a timezone indicator). For Date inputs we only reject NaN-valued.
     */
    export class TimePoint {
      readonly #utc: Date;

      constructor(value: Date | string) {
        if (value instanceof Date) {
          const t = value.getTime();
          if (!Number.isFinite(t)) {
            throw new RangeError("TimePoint does not accept NaN/Infinity Date");
          }
          this.#utc = new Date(t);
          return;
        }
        if (typeof value !== "string") {
          throw new TypeError(`TimePoint accepts Date or ISO string; got ${typeof value}`);
        }
        const s = value.trim();
        if (s.length === 0) {
          throw new RangeError("TimePoint requires non-empty ISO 8601 string");
        }
        // Date-only check: ISO datetime requires a T (or interior space) separator.
        if (!s.includes("T") && !/\\d \\d/.test(s)) {
          throw new RangeError(
            `TimePoint requires datetime, not date (got ${JSON.stringify(value)}). Use an ISO 8601 datetime with a timezone, e.g. '2026-05-21T14:30:00Z'.`,
          );
        }
        // Naive check: must include 'Z', '+HH:MM' or '-HH:MM' offset.
        const hasZone = /Z$|[+-]\\d{2}:?\\d{2}$/.test(s);
        if (!hasZone) {
          throw new RangeError(
            `TimePoint requires tz-aware timestamp; got naive ISO string (${JSON.stringify(value)}). Include a timezone offset (e.g. 'Z' or '+00:00').`,
          );
        }
        const parsed = Date.parse(s);
        if (!Number.isFinite(parsed)) {
          throw new RangeError(`TimePoint could not parse ISO 8601 string ${JSON.stringify(value)}`);
        }
        this.#utc = new Date(parsed);
      }

      toUTCDate(): Date { return new Date(this.#utc.getTime()); }
      toISOString(): string { return this.#utc.toISOString(); }
      asZone(tz: string): string {
        return new Intl.DateTimeFormat("en-CA", {
          timeZone: tz,
          year: "numeric", month: "2-digit", day: "2-digit",
          hour: "2-digit", minute: "2-digit", second: "2-digit",
          hour12: false,
        }).format(this.#utc);
      }
      equals(other: TimePoint): boolean { return this.#utc.getTime() === other.#utc.getTime(); }
      before(other: TimePoint): boolean { return this.#utc.getTime() < other.#utc.getTime(); }
      after(other: TimePoint): boolean { return this.#utc.getTime() > other.#utc.getTime(); }

      static now(): TimePoint { return new TimePoint(new Date()); }
    }
    ```

    Write `tests/temporal/timepoint.test.ts`:
    - Accepts valid: `"2026-05-21T14:30:00Z"`, `"2026-05-21T14:30:00.123Z"`, `"2026-05-21T14:30:00+00:00"`, `"2026-05-21T14:30:00-05:00"`, `new Date()`.
    - Rejects: `"2026-05-21"` (date-only) → RangeError.
    - Rejects: `"2026-05-21T14:30:00"` (naive) → RangeError.
    - Rejects: `""`, `"   "` → RangeError.
    - Rejects: `new Date(NaN)` → RangeError.
    - Rejects: `new Date(Infinity)` → RangeError.
    - Rejects: `123` (number), `null`, `undefined` → TypeError (defensive — type system blocks but runtime check is belt+suspenders).
    - `toISOString()` always ends in `'Z'` (asserted for both ISO-string-input and Date-input cases).
    - `asZone("America/New_York")` returns a string containing the New York wall-clock time for the UTC instant (loose contains check, not exact string match — locale formatting varies by Node version).
    - `equals` / `before` / `after` work as expected.
    - `TimePoint.now()` returns a TimePoint whose `toUTCDate().getTime()` is within 100ms of `Date.now()`.
  </action>
  <acceptance_criteria>
    - `pnpm --filter @tradewinds/core test -- timepoint` ≥ 18 cases all green.
    - `grep -n "class TimePoint" packages-ts/core/src/temporal/timepoint.ts` shows the class.
    - `grep -n "RangeError.*naive\\|RangeError.*date-only\\|RangeError.*Infinity" packages-ts/core/src/temporal/timepoint.ts` confirms three rejection branches (or equivalents).
    - `grep -n "#utc\\|readonly _utc" packages-ts/core/src/temporal/timepoint.ts` confirms private/readonly state.
  </acceptance_criteria>
</task>

<task type="auto" tdd="true">
  <name>Task 2: KnowledgeView + property test (fast-check)</name>
  <files>packages-ts/core/src/temporal/knowledge-view.ts, packages-ts/core/tests/temporal/knowledge-view.test.ts, packages-ts/core/tests/temporal/knowledge-view.property.test.ts</files>
  <read_first>
    - `packages/core/src/tradewinds/core/temporal/knowledge_view.py` (full file)
    - `packages-ts/core/src/temporal/timepoint.ts` (Task 1 output)
    - `packages-ts/core/src/exceptions/index.ts` (`SchemaValidationError` shape for missing-column errors)
    - `packages-ts/core/package.json` — confirm `fast-check` is in devDependencies (TS-W1 added it for the property tests there)
  </read_first>
  <behavior>
    - `KnowledgeView&lt;Row extends { knowledge_time: string }&gt;` — generic over row shape; the `knowledge_time` field MUST be present at the type level.
    - Constructor: `constructor(rows: ReadonlyArray&lt;Row&gt;, asOf: TimePoint)`. Validates that EVERY row's `knowledge_time` parses as a valid ISO datetime (use TimePoint constructor to validate); on any invalid row, throws `SchemaValidationError` with the row index in `violations`.
    - `.rows()` returns `ReadonlyArray&lt;Row&gt;` — only rows where `knowledge_time <= asOf`. Comparison is via epoch ms (`Date.parse(row.knowledge_time)` ≤ `asOf.toUTCDate().getTime()`).
    - `.asOf` getter returns the `TimePoint`.
    - Immutable — frozen-row input pattern: returned array is freshly built each call (NOT shared reference).
  </behavior>
  <action>
    1. Implement `packages-ts/core/src/temporal/knowledge-view.ts`:
       ```typescript
       import { SchemaValidationError } from "../exceptions/index.js";
       import { TimePoint } from "./timepoint.js";

       export class KnowledgeView&lt;Row extends { knowledge_time: string }&gt; {
         readonly #rows: ReadonlyArray&lt;Row&gt;;
         readonly #asOfMs: number;
         readonly #asOf: TimePoint;

         constructor(rows: ReadonlyArray&lt;Row&gt;, asOf: TimePoint) {
           if (!(asOf instanceof TimePoint)) {
             throw new TypeError(`asOf must be a TimePoint; got ${typeof asOf}`);
           }
           // Validate each row's knowledge_time parses as a valid tz-aware datetime.
           const violations: Array&lt;Record&lt;string, unknown&gt;&gt; = [];
           for (let i = 0; i &lt; rows.length; i++) {
             const r = rows[i];
             if (r == null || typeof r.knowledge_time !== "string") {
               violations.push({ row_idx: i, rule: "knowledge_time_missing_or_wrong_type" });
               continue;
             }
             try {
               new TimePoint(r.knowledge_time);
             } catch (e) {
               violations.push({ row_idx: i, rule: "knowledge_time_invalid", message: String(e) });
             }
           }
           if (violations.length &gt; 0) {
             throw new SchemaValidationError(
               `KnowledgeView received ${violations.length} row(s) with invalid knowledge_time`,
               { schemaId: "&lt;runtime&gt;", violations },
             );
           }
           this.#rows = rows;
           this.#asOf = asOf;
           this.#asOfMs = asOf.toUTCDate().getTime();
         }

         rows(): ReadonlyArray&lt;Row&gt; {
           return this.#rows.filter((r) =&gt; Date.parse(r.knowledge_time) &lt;= this.#asOfMs);
         }

         get asOf(): TimePoint { return this.#asOf; }
       }
       ```
       Verify the `SchemaValidationError` constructor signature in `packages-ts/core/src/exceptions/index.ts` matches the call site — if it expects `{ schemaId, violations }` adjust accordingly.

    2. Write `tests/temporal/knowledge-view.test.ts`:
       - Basic filter: 3 rows with knowledge_time spanning before/equal/after asOf — `.rows()` returns 2 (≤ asOf includes equals).
       - Empty input → empty output.
       - All-future rows → empty output.
       - All-past rows → all returned.
       - Invalid row (missing `knowledge_time`) → SchemaValidationError at construction.
       - `.asOf` returns the same TimePoint instance.
       - `.rows()` does NOT mutate the input array (input unchanged after call).
       - Multiple `.rows()` calls return new arrays (not shared reference) but with equal content.

    3. Write `tests/temporal/knowledge-view.property.test.ts` — the TS-W3 SC#3 fast-check property:
       ```typescript
       import { describe, expect, it } from "vitest";
       import fc from "fast-check";
       import { KnowledgeView } from "../../src/temporal/knowledge-view.js";
       import { TimePoint } from "../../src/temporal/timepoint.js";

       const DATE_RANGE_START = Date.parse("2018-01-01T00:00:00Z");
       const DATE_RANGE_END = Date.parse("2027-12-31T23:59:59Z");

       const arbDateMs = fc.integer({ min: DATE_RANGE_START, max: DATE_RANGE_END });
       const arbRow = arbDateMs.map((ms) =&gt; ({ knowledge_time: new Date(ms).toISOString() }));

       describe("KnowledgeView property: filter retains only knowledge_time &lt;= asOf", () =&gt; {
         it("invariant holds over the [2018-01-01, 2027-12-31] UTC range (200 runs)", () =&gt; {
           fc.assert(
             fc.property(
               fc.array(arbRow, { minLength: 0, maxLength: 100 }),
               arbDateMs,
               (rows, asOfMs) =&gt; {
                 const asOf = new TimePoint(new Date(asOfMs));
                 const view = new KnowledgeView(rows, asOf);
                 const filtered = view.rows();
                 // 1. Every row in `filtered` is &lt;= asOf.
                 for (const r of filtered) {
                   if (Date.parse(r.knowledge_time) &gt; asOfMs) return false;
                 }
                 // 2. Every row in `rows` &lt;= asOf is in `filtered` (no spurious drops).
                 for (const r of rows) {
                   if (Date.parse(r.knowledge_time) &lt;= asOfMs && !filtered.includes(r)) return false;
                 }
                 return true;
               },
             ),
             { numRuns: 200 },
           );
         });
       });
       ```
  </action>
  <acceptance_criteria>
    - `pnpm --filter @tradewinds/core test -- knowledge-view` runs unit + property suites; ≥ 9 unit cases + 200 property runs all green.
    - `grep -n "class KnowledgeView" packages-ts/core/src/temporal/knowledge-view.ts` shows the class.
    - `grep -n "fast-check\\|fc.assert\\|fc.property" packages-ts/core/tests/temporal/knowledge-view.property.test.ts` confirms property-test pattern.
    - `grep -n "DATE_RANGE_START\\|2018-01-01" packages-ts/core/tests/temporal/knowledge-view.property.test.ts` confirms the constrained range matches TS-W3 SC#3.
  </acceptance_criteria>
</task>

<task type="auto" tdd="true">
  <name>Task 3: assertNoLeakage + LeakageDetector + barrel + subpath export</name>
  <files>packages-ts/core/src/temporal/leakage.ts, packages-ts/core/src/temporal/index.ts, packages-ts/core/src/index.ts, packages-ts/core/package.json, packages-ts/core/tests/temporal/leakage.test.ts</files>
  <read_first>
    - `packages/core/src/tradewinds/core/temporal/leakage.py` (Python source — `_SAMPLE_CAP = 10`, the violation sample shape, the LeakageError raise)
    - `packages-ts/core/src/exceptions/index.ts` lines 290-322 (LeakageError — `asOf`, `violatingCount`, `sampleViolations` constructor; `payload()` emits snake_case)
    - `packages-ts/core/src/temporal/knowledge-view.ts` + `timepoint.ts` (Tasks 1-2)
  </read_first>
  <behavior>
    - `assertNoLeakage&lt;Row extends { knowledge_time: string }&gt;(rows, asOf: TimePoint): void` — throws `LeakageError` iff ≥ 1 row has `knowledge_time > asOf`.
    - LeakageError payload: `asOf` (TimePoint.toISOString()), `violatingCount` (number), `sampleViolations` (up to 10 entries, each `{ row_idx, knowledge_time }`).
    - `LeakageDetector` is the convenience class: `new LeakageDetector(asOf).check(rows)` → delegates to `assertNoLeakage`.
    - The `toDict()` shape on the thrown LeakageError emits snake_case `{ as_of, violating_count, sample_violations }` — verified by reading the existing `LeakageError.payload()` in `packages-ts/core/src/exceptions/index.ts`. NO changes needed to exceptions/index.ts; just consume it.
  </behavior>
  <action>
    1. Implement `packages-ts/core/src/temporal/leakage.ts`:
       ```typescript
       import { LeakageError } from "../exceptions/index.js";
       import { TimePoint } from "./timepoint.js";

       const SAMPLE_CAP = 10;

       export function assertNoLeakage&lt;Row extends { knowledge_time: string }&gt;(
         rows: ReadonlyArray&lt;Row&gt;,
         asOf: TimePoint,
       ): void {
         if (!(asOf instanceof TimePoint)) {
           throw new TypeError(`asOf must be a TimePoint; got ${typeof asOf}`);
         }
         const asOfMs = asOf.toUTCDate().getTime();
         const violations: Array&lt;{ row_idx: number; knowledge_time: string }&gt; = [];
         for (let i = 0; i &lt; rows.length; i++) {
           const r = rows[i];
           if (r == null || typeof r.knowledge_time !== "string") continue;
           const t = Date.parse(r.knowledge_time);
           if (Number.isFinite(t) && t &gt; asOfMs) {
             violations.push({ row_idx: i, knowledge_time: r.knowledge_time });
           }
         }
         if (violations.length === 0) return;
         throw new LeakageError(
           `Found ${violations.length} row(s) with knowledge_time &gt; asOf`,
           {
             asOf: asOf.toISOString(),
             violatingCount: violations.length,
             sampleViolations: violations.slice(0, SAMPLE_CAP),
           },
         );
       }

       export class LeakageDetector {
         readonly #asOf: TimePoint;
         constructor(asOf: TimePoint) {
           if (!(asOf instanceof TimePoint)) throw new TypeError(`asOf must be a TimePoint; got ${typeof asOf}`);
           this.#asOf = asOf;
         }
         get asOf(): TimePoint { return this.#asOf; }
         check&lt;Row extends { knowledge_time: string }&gt;(rows: ReadonlyArray&lt;Row&gt;): void {
           assertNoLeakage(rows, this.#asOf);
         }
       }
       ```

    2. Create `packages-ts/core/src/temporal/index.ts` barrel:
       ```typescript
       export { TimePoint } from "./timepoint.js";
       export { KnowledgeView } from "./knowledge-view.js";
       export { LeakageDetector, assertNoLeakage } from "./leakage.js";
       ```

    3. Update `packages-ts/core/package.json` to add the subpath export:
       ```json
       "./temporal": {
         "types": "./dist/temporal/index.d.ts",
         "import": "./dist/temporal/index.mjs",
         "require": "./dist/temporal/index.cjs"
       }
       ```
       Add `src/temporal/index.ts` to the tsup entries (matching the `internal/cache` pattern from plan 01).

    4. Update `packages-ts/core/src/index.ts` to re-export from temporal (so `import { TimePoint } from "@tradewinds/core"` works alongside the subpath import):
       ```typescript
       export * from "./temporal/index.js";
       ```

    5. Write `tests/temporal/leakage.test.ts`:
       - Leak-free input → returns void.
       - 1 leaking row → LeakageError; `err.violatingCount === 1`; `err.sampleViolations[0]` has `row_idx` and `knowledge_time`.
       - 15 leaking rows → LeakageError; `err.violatingCount === 15`; `err.sampleViolations.length === 10` (SAMPLE_CAP).
       - `err.toDict()` returns an object with snake_case keys: `as_of`, `violating_count`, `sample_violations`. Assert `Object.hasOwn(dict, 'as_of')` etc. (NOT `asOf`).
       - `err.toDict().as_of === asOf.toISOString()`.
       - LeakageDetector(asOf).check(rows) delegates correctly.
       - Non-TimePoint asOf → TypeError.
       - Row with non-string `knowledge_time` is skipped (does NOT throw, does NOT count as violation — matches Python "validation is KnowledgeView's job; leakage check is just the &gt; comparison").
  </action>
  <acceptance_criteria>
    - `pnpm --filter @tradewinds/core test -- leakage` ≥ 10 cases all green.
    - `grep -n "as_of:\\|violating_count:\\|sample_violations:" packages-ts/core/tests/temporal/leakage.test.ts` confirms snake_case assertions on `toDict()` output.
    - `grep -n '"./temporal"' packages-ts/core/package.json` confirms subpath export.
    - `pnpm --filter @tradewinds/core run build` emits `dist/temporal/{timepoint,knowledge-view,leakage,index}.{mjs,cjs,d.ts}`.
    - `pnpm --filter @tradewinds/core run typecheck` clean.
    - From meta package: `import { TimePoint, KnowledgeView, LeakageDetector, assertNoLeakage } from "@tradewinds/core/temporal"` resolves AND `import { TimePoint } from "@tradewinds/core"` resolves (both paths work).
    - `grep -n "SAMPLE_CAP\\s*=\\s*10" packages-ts/core/src/temporal/leakage.ts` confirms Python parity on cap.
  </acceptance_criteria>
</task>

</tasks>

<verification>
1. `pnpm --filter @tradewinds/core test -- temporal` runs all 4 test files (timepoint, knowledge-view unit, knowledge-view property, leakage); all green.
2. `pnpm --filter @tradewinds/core run typecheck` clean.
3. `pnpm --filter @tradewinds/core run build` emits `dist/temporal/{timepoint,knowledge-view,leakage,index}.{mjs,cjs,d.ts}`.
4. `pnpm -r run typecheck` clean — meta + weather + markets can consume `@tradewinds/core/temporal`.
5. `pnpm --filter @tradewinds/core run size-limit` — `@tradewinds/core` total bundle ≤ 25 KB (TS-BUNDLE-01); temporal layer adds ~2 KB.
</verification>

<success_criteria>
- TS-TEMPORAL-01 fully met — TimePoint with all rejection branches + accessors + `now()`.
- TS-TEMPORAL-02 fully met — KnowledgeView property-tested over the constrained range; assertNoLeakage throws LeakageError whose toDict() emits snake_case shape matching Python wire format.
- Both subpath (`@tradewinds/core/temporal`) AND root-export (`@tradewinds/core`) import paths work for the temporal trio.
- fast-check property test runs 200 iterations and passes deterministically (no flaky time-of-day dependencies).
</success_criteria>

<review_discipline>
TypeScript-only changes under `packages-ts/core/**`. Per `.planning/REVIEW-DISCIPLINE.md`:

- **Reviewers**: codex `high` + **TypeScript Architect** (parallel).
- **Severity gate**: CRITICAL or HIGH only.
- **Loop**: fix on branch, re-dispatch, cap at 3.
- **Rubric calibration**:
  - CRITICAL if `TimePoint` accepts naive ISO strings (silently localizes via `Date.parse` engine-dependent behavior → silent timezone corruption on cross-machine training pipelines).
  - CRITICAL if `LeakageError.toDict()` emits camelCase `asOf` / `violatingCount` / `sampleViolations` instead of snake_case (breaks Python-parity wire shape; Python emits snake_case; cross-language MCP wire format depends on parity).
  - HIGH if `KnowledgeView` returns a non-defensive reference (callers mutating the returned array would silently corrupt subsequent `.rows()` calls).
  - HIGH if the fast-check property test runs &lt; 100 iterations (defeats the purpose of property testing).
  - HIGH if `assertNoLeakage` silently accepts non-string `knowledge_time` AND counts it as leakage (silent type confusion — Python skips it cleanly).
  - HIGH if the subpath export `./temporal` is missing from `tsup.config.ts` entries (build emits dist but typecheck breaks for consumers — TS-W2 iter-1 P1 repeat).
</review_discipline>

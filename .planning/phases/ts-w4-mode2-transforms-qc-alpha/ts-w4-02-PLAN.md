---
phase: ts-w4-mode2-transforms-qc-alpha
plan: 02
type: execute
wave: 2
depends_on: []
files_modified:
  - packages-ts/core/src/transforms/lag.ts
  - packages-ts/core/src/transforms/diff.ts
  - packages-ts/core/src/transforms/rolling.ts
  - packages-ts/core/src/transforms/index.ts
  - packages-ts/core/package.json
  - packages-ts/core/tsup.config.ts
  - packages-ts/core/tests/transforms/lag.test.ts
  - packages-ts/core/tests/transforms/diff.test.ts
  - packages-ts/core/tests/transforms/rolling.test.ts
autonomous: true
requirements:
  - TS-TRANSFORM-01
must_haves:
  truths:
    - "lag(rows, col, n) returns a new array with each row carrying a derived column named `{col}_lag_{n}` whose value at row i is rows[i-n][col] (null for i<n)"
    - "diff(rows, col, n=1) returns rows with `{col}_diff_{n}` whose value at i is rows[i][col] - rows[i-n][col] (null for i<n)"
    - "diff2(rows, col) returns rows with `{col}_diff2` (second difference; nulls at i=0 and i=1)"
    - "rolling(rows, col, window, fn='mean') returns rows with `{col}_rolling_{window}_{fn}`; fn ∈ {'mean','median','min','max','std','count'}"
    - "rolling uses min_periods=1 semantics (Python parity: getattr(rolling, fn)() with min_periods=1)"
    - "All four functions are pure: input rows array is NOT mutated; returned rows are fresh objects"
    - "Null/undefined values in source column propagate as null (NOT NaN); arithmetic on nulls produces null"
    - "Subpath @tradewinds/core/transforms exports lag, diff, diff2, rolling, RollingFn type"
  artifacts:
    - path: packages-ts/core/src/transforms/lag.ts
      provides: "lag function; pure row→row transform with `{col}_lag_{n}` naming"
    - path: packages-ts/core/src/transforms/diff.ts
      provides: "diff + diff2 functions; pure row→row transform with `{col}_diff_{n}` / `{col}_diff2` naming"
    - path: packages-ts/core/src/transforms/rolling.ts
      provides: "rolling function with 6 reducers; pure row→row transform with `{col}_rolling_{window}_{fn}` naming"
    - path: packages-ts/core/src/transforms/index.ts
      provides: "Barrel re-export of lag, diff, diff2, rolling"
  key_links:
    - from: packages-ts/core/package.json
      to: "@tradewinds/core/transforms subpath"
      via: "exports['./transforms'] = { types/import/require pointing to dist/transforms/index.*}"
      pattern: "./transforms"
    - from: packages-ts/core/tsup.config.ts
      to: "tsup transforms entry"
      via: "entry: { index: 'src/transforms/index.ts' } emitted to dist/transforms/"
      pattern: "src/transforms/index.ts"
---

<objective>
Port the four temporal transforms from Python `tradewinds.transforms` — `lag`, `diff`, `diff2`, `rolling` — into TS at `@tradewinds/core/transforms`. Pure functions: take a `ReadonlyArray<Row>`, return a new array of rows each carrying a derived column.

**Column-naming convention (load-bearing):** `{col}_{op}_{param}` — matches Python's implicit pandas convention so a quant can compose transforms across both SDKs without renaming.
- `lag(rows, 'temp_c', 3)` → derived col `temp_c_lag_3`
- `diff(rows, 'temp_c', 1)` → `temp_c_diff_1`
- `diff(rows, 'temp_c', 2)` → `temp_c_diff_2`
- `diff2(rows, 'temp_c')` → `temp_c_diff2`
- `rolling(rows, 'temp_c', 7, 'mean')` → `temp_c_rolling_7_mean`

**Subpath placement:** these live at `@tradewinds/core/transforms` (NOT the root barrel) per the same bundle discipline that pushed validator + temporal + formats to subpaths in TS-W3 iter-4 H8. The `@tradewinds/core` root bundle (`dist/index.mjs`) must stay ≤ 25 KB.

**Parity scope:** TS does NOT have pandas Series; we operate on `ReadonlyArray<Row>` where `Row` is `Record<string, unknown>` constrained at the type level to `{ [key: string]: number | string | null | undefined | Date }`. Numeric ops on `null`/`undefined` produce `null` (NOT NaN — JSON-safe wire shape; matches Python `pd.NA`/`None` behavior on serialization).

**Independence:** Wave 2 has NO dependencies on Waves 1, 3, 4, 5, 6. Can run in parallel with Wave 3 + Wave 4 if scheduling allows.
</objective>

<context_files>
- `.planning/REQUIREMENTS.md` TS-TRANSFORM-01 (canonical text — `{col}_{op}_{param}` convention)
- `packages/core/src/tradewinds/transforms.py` lines 43-69 (Python source — `lag`, `diff`, `diff2`, `rolling`)
- `packages-ts/core/src/temporal/index.ts` (canonical TS-W3 barrel pattern to mirror)
- `packages-ts/core/tsup.config.ts` (subpath entry pattern — see lines 39-67 for temporal + formats entries)
- `packages-ts/core/package.json` (exports block — temporal/formats subpath pattern lines 37-51)
- `package.json` root size-limit block (core ≤ 25 KB enforces the subpath choice)
</context_files>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: lag + diff + diff2 (numeric column transforms)</name>
  <files>packages-ts/core/src/transforms/lag.ts, packages-ts/core/src/transforms/diff.ts, packages-ts/core/tests/transforms/lag.test.ts, packages-ts/core/tests/transforms/diff.test.ts</files>
  <read_first>
    - `packages/core/src/tradewinds/transforms.py` lines 43-56 (`lag`, `diff`, `diff2` — Python uses `pd.Series.shift(periods)` for lag and `.diff(periods)` for diff)
    - TS row-array convention: each row is `Record<string, unknown>` with numeric columns possibly `null`. NO mutation of source rows.
  </read_first>
  <behavior>
    - `lag<Row extends Record<string, unknown>>(rows: ReadonlyArray<Row>, col: string, n: number = 1): ReadonlyArray<Row & Record<string, number | null>>`:
      - `n` must be a positive integer (≥ 1); throws `RangeError` if `n < 1` or `!Number.isInteger(n)`.
      - For each row at index `i`, derived column name is `${col}_lag_${n}`. Value:
        - If `i < n` → `null` (no prior row to lag from).
        - Else → `rows[i-n][col]` coerced to `number` (use Number(value)) if numeric; if non-numeric or null/undefined, derived value is `null`.
      - Returns a freshly-built array; source rows are NOT mutated; each output row is `{ ...row, [`${col}_lag_${n}`]: value }`.
    - `diff<Row>(rows, col, n: number = 1): ReadonlyArray<Row & Record<string, number | null>>`:
      - Same `n` validation as `lag`.
      - Derived column: `${col}_diff_${n}`. Value at `i`:
        - If `i < n` → `null`.
        - Else if either `rows[i][col]` or `rows[i-n][col]` is null/undefined/non-finite → `null`.
        - Else → `Number(rows[i][col]) - Number(rows[i-n][col])`.
    - `diff2<Row>(rows, col): ReadonlyArray<Row & Record<string, number | null>>`:
      - Derived column: `${col}_diff2`.
      - Equivalent to applying `diff` twice; explicit implementation: compute first-differences in pass 1, then second-differences in pass 2. Nulls at `i=0` and `i=1`.
      - Implementation: chain `diff(rows, col, 1)` → grab the first-diff series → compute differences of THAT series → write `${col}_diff2` into output rows. Be careful to drop the intermediate `${col}_diff_1` column so the final output has ONLY `${col}_diff2` (not both — matches Python which returns a single Series).
    - All three functions: numeric coercion uses `typeof v === 'number' && Number.isFinite(v) ? v : null` — strings like `'3.5'` are NOT auto-parsed (be strict; the parsers upstream already coerce). Document this in JSDoc.
    - Output array length === input array length. Output array order matches input order (no sorting).
  </behavior>
  <action>
    1. Create `packages-ts/core/src/transforms/lag.ts`:
       ```typescript
       /**
        * lag — shift a column by N rows. Mirrors Python
        * `packages/core/src/tradewinds/transforms.py:43-45`.
        *
        * @param rows  input rows (NOT mutated)
        * @param col   column name to lag
        * @param n     positive integer; rows < n produce null in the derived column
        * @returns     new array of rows each carrying `{col}_lag_{n}` derived column
        */
       export function lag<Row extends Record<string, unknown>>(
         rows: ReadonlyArray<Row>,
         col: string,
         n: number = 1,
       ): ReadonlyArray<Row & Record<string, number | null>> {
         if (!Number.isInteger(n) || n < 1) {
           throw new RangeError(`lag: n must be a positive integer; got ${n}`);
         }
         const out: Array<Row & Record<string, number | null>> = [];
         const key = `${col}_lag_${n}`;
         for (let i = 0; i < rows.length; i++) {
           const src = i >= n ? rows[i - n]?.[col] : null;
           const v = typeof src === "number" && Number.isFinite(src) ? src : null;
           out.push({ ...rows[i]!, [key]: v } as Row & Record<string, number | null>);
         }
         return out;
       }
       ```

    2. Create `packages-ts/core/src/transforms/diff.ts`:
       ```typescript
       export function diff<Row extends Record<string, unknown>>(
         rows: ReadonlyArray<Row>,
         col: string,
         n: number = 1,
       ): ReadonlyArray<Row & Record<string, number | null>> {
         if (!Number.isInteger(n) || n < 1) {
           throw new RangeError(`diff: n must be a positive integer; got ${n}`);
         }
         const out: Array<Row & Record<string, number | null>> = [];
         const key = `${col}_diff_${n}`;
         for (let i = 0; i < rows.length; i++) {
           let v: number | null = null;
           if (i >= n) {
             const a = rows[i]?.[col];
             const b = rows[i - n]?.[col];
             if (typeof a === "number" && Number.isFinite(a)
                 && typeof b === "number" && Number.isFinite(b)) {
               v = a - b;
             }
           }
           out.push({ ...rows[i]!, [key]: v } as Row & Record<string, number | null>);
         }
         return out;
       }

       /**
        * diff2 — second difference. Mirrors Python `transforms.py:53-55`
        * which is `df[column].diff().diff()`.
        */
       export function diff2<Row extends Record<string, unknown>>(
         rows: ReadonlyArray<Row>,
         col: string,
       ): ReadonlyArray<Row & Record<string, number | null>> {
         // Step 1: first differences into a numeric array (parallel to rows).
         const first: Array<number | null> = new Array(rows.length).fill(null);
         for (let i = 1; i < rows.length; i++) {
           const a = rows[i]?.[col];
           const b = rows[i - 1]?.[col];
           if (typeof a === "number" && Number.isFinite(a)
               && typeof b === "number" && Number.isFinite(b)) {
             first[i] = a - b;
           }
         }
         // Step 2: second differences from `first`.
         const out: Array<Row & Record<string, number | null>> = [];
         const key = `${col}_diff2`;
         for (let i = 0; i < rows.length; i++) {
           let v: number | null = null;
           if (i >= 2) {
             const a = first[i];
             const b = first[i - 1];
             if (a !== null && b !== null) v = a - b;
           }
           out.push({ ...rows[i]!, [key]: v } as Row & Record<string, number | null>);
         }
         return out;
       }
       ```

    3. Write `packages-ts/core/tests/transforms/lag.test.ts`:
       - 5-row fixture with `temp_c: [10, 12, 14, 16, 18]`; `lag(rows, 'temp_c', 1)` → derived `temp_c_lag_1: [null, 10, 12, 14, 16]`.
       - `lag(rows, 'temp_c', 3)` → `temp_c_lag_3: [null, null, null, 10, 12]`.
       - `n=0` → throws RangeError; `n=-1` → throws; `n=1.5` → throws.
       - Source rows unchanged after call (deep-equal check via `JSON.stringify`).
       - Output rows preserve all original keys + add only the derived key.
       - Row with `temp_c: null` → lag value at the next row is `null` (NOT NaN, NOT undefined).
       - Row with `temp_c: 'invalid'` (string) → lag value is `null` (no coercion).
       - Empty input → empty output (no throw).
    4. Write `packages-ts/core/tests/transforms/diff.test.ts`:
       - 5-row fixture `temp_c: [10, 12, 14, 16, 18]`; `diff(rows, 'temp_c', 1)` → `temp_c_diff_1: [null, 2, 2, 2, 2]`.
       - `diff(rows, 'temp_c', 2)` → `temp_c_diff_2: [null, null, 4, 4, 4]`.
       - `diff2(rows, 'temp_c')` on `[10, 12, 14, 16, 18]` → `temp_c_diff2: [null, null, 0, 0, 0]` (constant rise → zero acceleration).
       - `diff2` on `[1, 2, 4, 8, 16]` → `temp_c_diff2: [null, null, 1, 2, 4]` (differences of [1,2,4,8] = [1,2,4]).
       - Null propagation: a `null` source value cascades through both diffs.
       - Output `temp_c_diff2` is the ONLY derived column (NOT `temp_c_diff_1` + `temp_c_diff2`).
       - Source rows unchanged after call.
       - `n=0` and `n=-1` throw RangeError on `diff`.
  </action>
  <acceptance_criteria>
    - `grep -n "export function lag\\|export function diff\\|export function diff2" packages-ts/core/src/transforms/lag.ts packages-ts/core/src/transforms/diff.ts` confirms three named exports.
    - `grep -n "_lag_\\|_diff_\\|_diff2" packages-ts/core/src/transforms/lag.ts packages-ts/core/src/transforms/diff.ts` confirms exact naming-convention template literals.
    - `grep -n "RangeError" packages-ts/core/src/transforms/lag.ts packages-ts/core/src/transforms/diff.ts` confirms guard throws.
    - `pnpm --filter @tradewinds/core test -- transforms/lag transforms/diff` ≥ 14 cases all green.
    - No mutation: explicit deep-equal-on-input test passes.
  </acceptance_criteria>
</task>

<task type="auto" tdd="true">
  <name>Task 2: rolling reduction (mean/median/min/max/std/count)</name>
  <files>packages-ts/core/src/transforms/rolling.ts, packages-ts/core/tests/transforms/rolling.test.ts</files>
  <read_first>
    - `packages/core/src/tradewinds/transforms.py` lines 58-68 (Python `rolling` — uses `df[column].rolling(window=window, min_periods=1)` and `getattr(rolling, fn)()`)
    - Python pandas `min_periods=1` semantics: at position `i` with window `w`, the window covers `[max(0, i-w+1), i+1)` and produces a value as long as ≥ 1 non-null exists in that window.
  </read_first>
  <behavior>
    - `RollingFn = 'mean' | 'median' | 'min' | 'max' | 'std' | 'count'` (const-union, not enum).
    - `rolling<Row>(rows: ReadonlyArray<Row>, col: string, window: number, fn: RollingFn = 'mean'): ReadonlyArray<Row & Record<string, number | null>>`:
      - `window` must be positive integer ≥ 1; else `RangeError`.
      - `fn` must be a `RollingFn` member; else `RangeError`.
      - Derived column name: `${col}_rolling_${window}_${fn}` (e.g. `temp_c_rolling_7_mean`).
      - At each row `i`, the window covers `rows[max(0, i-window+1) .. i]` (inclusive, both ends; `min_periods=1` semantics → all positions get a value if ≥ 1 non-null in window).
      - Aggregator semantics:
        - `mean`: average of non-null finite numbers in window; null if window is all-null.
        - `median`: middle of sorted non-null values; for even count, average of the two middles.
        - `min`: min of non-null finite numbers.
        - `max`: max of non-null finite numbers.
        - `std`: sample standard deviation (Bessel's correction, divide by `n-1`); requires ≥ 2 non-null values, else null.
        - `count`: count of non-null finite numbers in window (an integer; returned as number).
    - Pure: source rows NOT mutated.
  </behavior>
  <action>
    1. Create `packages-ts/core/src/transforms/rolling.ts`:
       ```typescript
       /**
        * rolling — windowed reduction over a numeric column. Mirrors
        * Python `transforms.rolling(df, col, window, fn)` with
        * `min_periods=1` semantics (every row gets a value as long as
        * the window contains ≥ 1 non-null value).
        */

       export const ROLLING_FNS = ["mean", "median", "min", "max", "std", "count"] as const;
       export type RollingFn = (typeof ROLLING_FNS)[number];

       function isRollingFn(v: unknown): v is RollingFn {
         return typeof v === "string"
           && (ROLLING_FNS as readonly string[]).includes(v);
       }

       function aggregate(vals: number[], fn: RollingFn): number | null {
         if (vals.length === 0) return fn === "count" ? 0 : null;
         if (fn === "count") return vals.length;
         if (fn === "mean") return vals.reduce((a, b) => a + b, 0) / vals.length;
         if (fn === "min") return Math.min(...vals);
         if (fn === "max") return Math.max(...vals);
         if (fn === "median") {
           const sorted = [...vals].sort((a, b) => a - b);
           const mid = Math.floor(sorted.length / 2);
           if (sorted.length % 2 === 0) {
             return ((sorted[mid - 1] ?? 0) + (sorted[mid] ?? 0)) / 2;
           }
           return sorted[mid] ?? null;
         }
         // std — sample stdev with Bessel's correction (n-1 denominator).
         if (vals.length < 2) return null;
         const mean = vals.reduce((a, b) => a + b, 0) / vals.length;
         const sumSq = vals.reduce((a, b) => a + (b - mean) ** 2, 0);
         return Math.sqrt(sumSq / (vals.length - 1));
       }

       export function rolling<Row extends Record<string, unknown>>(
         rows: ReadonlyArray<Row>,
         col: string,
         window: number,
         fn: RollingFn = "mean",
       ): ReadonlyArray<Row & Record<string, number | null>> {
         if (!Number.isInteger(window) || window < 1) {
           throw new RangeError(`rolling: window must be a positive integer; got ${window}`);
         }
         if (!isRollingFn(fn)) {
           throw new RangeError(
             `rolling: fn must be one of ${JSON.stringify(ROLLING_FNS)}; got '${String(fn)}'`,
           );
         }
         const key = `${col}_rolling_${window}_${fn}`;
         const out: Array<Row & Record<string, number | null>> = [];
         for (let i = 0; i < rows.length; i++) {
           const start = Math.max(0, i - window + 1);
           const slice: number[] = [];
           for (let j = start; j <= i; j++) {
             const v = rows[j]?.[col];
             if (typeof v === "number" && Number.isFinite(v)) slice.push(v);
           }
           const agg = aggregate(slice, fn);
           out.push({ ...rows[i]!, [key]: agg } as Row & Record<string, number | null>);
         }
         return out;
       }
       ```

    2. Write `packages-ts/core/tests/transforms/rolling.test.ts`:
       - 7-row `temp_c: [10, 12, 14, 16, 18, 20, 22]`; `rolling(rows, 'temp_c', 3, 'mean')` → first row mean=10 (window of just itself); second row mean=11 (10,12); third row mean=12 (10,12,14); fourth=14; fifth=16; sixth=18; seventh=20.
       - `rolling(rows, 'temp_c', 3, 'min')` → `[10, 10, 10, 12, 14, 16, 18]`.
       - `rolling(rows, 'temp_c', 3, 'max')` → `[10, 12, 14, 16, 18, 20, 22]`.
       - `rolling(rows, 'temp_c', 3, 'median')` → `[10, 11, 12, 14, 16, 18, 20]` (middle of 3 sorted values).
       - `rolling(rows, 'temp_c', 3, 'std')` first row → null (n<2); second row → stdev of [10,12] with n-1 = sqrt(2) ≈ 1.4142.
       - `rolling(rows, 'temp_c', 3, 'count')` → `[1, 2, 3, 3, 3, 3, 3]`.
       - Null handling: `temp_c: [null, 10, null, 12, 14]`; `rolling(rows, 'temp_c', 3, 'count')` → `[0, 1, 1, 2, 2]`.
       - All-null window → 'mean'/'median'/'min'/'max'/'std' return null; 'count' returns 0.
       - `window=0` → RangeError; `window=-1` → RangeError; `window=1.5` → RangeError; `fn='sum'` → RangeError mentioning the valid list.
       - Source rows unchanged.
       - Output preserves all original columns + adds only the derived key.
       - Derived key matches naming convention exactly: `grep`-able as `temp_c_rolling_3_mean`.
  </action>
  <acceptance_criteria>
    - `grep -n "export function rolling\\|export const ROLLING_FNS\\|export type RollingFn" packages-ts/core/src/transforms/rolling.ts` confirms exports.
    - `grep -n "as const" packages-ts/core/src/transforms/rolling.ts` confirms const-union (NOT enum).
    - `grep -nE "\\benum\\s" packages-ts/core/src/transforms/rolling.ts` returns NO matches.
    - `grep -n "_rolling_" packages-ts/core/src/transforms/rolling.ts` confirms naming-convention template literal.
    - `grep -n "n - 1\\|n-1\\|vals\\.length - 1" packages-ts/core/src/transforms/rolling.ts` confirms Bessel's correction in std.
    - `pnpm --filter @tradewinds/core test -- transforms/rolling` ≥ 11 cases all green.
  </acceptance_criteria>
</task>

<task type="auto" tdd="true">
  <name>Task 3: Barrel + subpath export + tsup entry + size gate</name>
  <files>packages-ts/core/src/transforms/index.ts, packages-ts/core/package.json, packages-ts/core/tsup.config.ts, packages-ts/core/tests/transforms/barrel.test.ts</files>
  <read_first>
    - `packages-ts/core/src/temporal/index.ts` (the TS-W3 barrel pattern)
    - `packages-ts/core/tsup.config.ts` lines 53-67 (the temporal entry — copy the shape)
    - `packages-ts/core/package.json` lines 37-51 (temporal/formats subpath exports — mirror the pattern)
    - `package.json` size-limit block (core ≤ 25 KB ESM gzipped)
  </read_first>
  <behavior>
    - Barrel re-exports: `lag`, `diff`, `diff2`, `rolling`, `ROLLING_FNS`, `RollingFn` type.
    - Subpath: `./transforms` in `packages-ts/core/package.json` exports — types/import/require pointing to `./dist/transforms/index.{d.ts,mjs,cjs}`.
    - tsup config: new entry block emitting to `dist/transforms/`.
    - **Bundle gate**: after build, `pnpm run size` reports `@tradewinds/core` ≤ 25 KB. Transforms ship at the subpath; the root barrel does NOT re-export them (same pattern as temporal/formats — see `packages-ts/core/src/index.ts` lines 19-32 documenting the iter-4 H8 reasoning).
    - Consumer paths:
      - `import { lag, diff, diff2, rolling } from '@tradewinds/core/transforms'` (subpath — preferred)
      - The root `@tradewinds/core` barrel deliberately does NOT re-export transforms.
  </behavior>
  <action>
    1. Create `packages-ts/core/src/transforms/index.ts`:
       ```typescript
       // Barrel for @tradewinds/core/transforms — TS-W4 Plan 02.
       //
       // Pure functions porting Python tradewinds.transforms (lag/diff/diff2/
       // rolling). Lives at the subpath, NOT the root barrel, to keep the
       // @tradewinds/core main bundle under its 25 KB size-limit gate
       // (TS-BUNDLE-01). Consumers import with:
       //
       //   import { lag, diff, diff2, rolling } from "@tradewinds/core/transforms";

       export { lag } from "./lag.js";
       export { diff, diff2 } from "./diff.js";
       export { rolling, ROLLING_FNS, type RollingFn } from "./rolling.js";
       ```

    2. Update `packages-ts/core/package.json` exports block — add after the `./formats` entry:
       ```json
       "./transforms": {
         "types": "./dist/transforms/index.d.ts",
         "import": "./dist/transforms/index.mjs",
         "require": "./dist/transforms/index.cjs"
       }
       ```

    3. Update `packages-ts/core/tsup.config.ts` — add a new entry block after the formats block (mirror temporal block lines 53-67):
       ```typescript
       {
         // TS-W4 Plan 02 — temporal transforms (lag/diff/diff2/rolling).
         // Emitted at @tradewinds/core/transforms.
         entry: { index: "src/transforms/index.ts" },
         format: ["esm", "cjs"],
         dts: true,
         sourcemap: true,
         clean: false,
         target: "es2022",
         outDir: "dist/transforms",
         outExtension({ format }) {
           if (format === "esm") return { js: ".mjs" };
           return { js: ".cjs" };
         },
       },
       ```

    4. Write `packages-ts/core/tests/transforms/barrel.test.ts`:
       ```typescript
       import { describe, expect, it } from "vitest";
       import { lag, diff, diff2, rolling, ROLLING_FNS, type RollingFn } from "../../src/transforms/index.js";

       describe("@tradewinds/core/transforms barrel", () => {
         it("re-exports four transform functions", () => {
           expect(typeof lag).toBe("function");
           expect(typeof diff).toBe("function");
           expect(typeof diff2).toBe("function");
           expect(typeof rolling).toBe("function");
         });
         it("ROLLING_FNS contains exactly 6 reducers", () => {
           expect(ROLLING_FNS).toEqual(["mean", "median", "min", "max", "std", "count"]);
         });
         it("Output column naming matches {col}_{op}_{param} convention", () => {
           const rows = [{ temp_c: 10 }, { temp_c: 12 }];
           const lagged = lag(rows, "temp_c", 1);
           expect(Object.hasOwn(lagged[1]!, "temp_c_lag_1")).toBe(true);
           const diffed = diff(rows, "temp_c", 1);
           expect(Object.hasOwn(diffed[1]!, "temp_c_diff_1")).toBe(true);
           const diffed2 = diff2(rows.concat([{ temp_c: 14 }]));  // 3 rows for diff2
           // ... assertion: temp_c_diff2 key present at index 2
           const rolled = rolling(rows, "temp_c", 2, "mean");
           expect(Object.hasOwn(rolled[1]!, "temp_c_rolling_2_mean")).toBe(true);
         });
       });
       ```

    5. Run `pnpm --filter @tradewinds/core run build && pnpm run size` from root. Assert `@tradewinds/core` ≤ 25 KB AND `tradewinds meta` ≤ 30 KB unchanged.
  </action>
  <acceptance_criteria>
    - `grep -n '"./transforms"' packages-ts/core/package.json` confirms subpath export.
    - `grep -n "src/transforms/index.ts" packages-ts/core/tsup.config.ts` confirms tsup entry added.
    - `pnpm --filter @tradewinds/core run build` emits `dist/transforms/{index.mjs,index.cjs,index.d.ts}`.
    - `pnpm --filter @tradewinds/core test -- transforms` runs all 4 test files (lag, diff, rolling, barrel); ≥ 25 cases all green.
    - `pnpm --filter @tradewinds/core run typecheck` clean.
    - `pnpm run size` reports `@tradewinds/core` ≤ 25 KB (unchanged from TS-W3 floor).
    - From a downstream consumer: `import { lag, rolling } from "@tradewinds/core/transforms"` resolves AND `import { lag } from "@tradewinds/core"` does NOT resolve (subpath-only by design).
  </acceptance_criteria>
</task>

</tasks>

<verification>
1. `pnpm --filter @tradewinds/core test -- transforms` runs all 4 test files (lag, diff, rolling, barrel); ≥ 25 cases all green.
2. `pnpm --filter @tradewinds/core run typecheck` clean.
3. `pnpm --filter @tradewinds/core run build` emits `dist/transforms/{index.mjs,index.cjs,index.d.ts}`.
4. `pnpm -r run typecheck` clean — meta + weather + markets can consume `@tradewinds/core/transforms`.
5. `pnpm run size` reports `@tradewinds/core` ≤ 25 KB (transforms lives at subpath, not root barrel).
6. Column-naming convention verifiable by grep on test output: `temp_c_lag_1`, `temp_c_diff_2`, `temp_c_diff2`, `temp_c_rolling_3_mean` all appear.
</verification>

<success_criteria>
- TS-TRANSFORM-01 fully met — four transforms ported with `{col}_{op}_{param}` naming convention; pure (no input mutation); subpath export at `@tradewinds/core/transforms`.
- Bundle gate holds: `@tradewinds/core` ≤ 25 KB (subpath placement preserves the root bundle floor).
- 25+ unit tests covering happy paths, null propagation, RangeError guards (n=0, fn='sum'), no-mutation invariant, and exact column-naming verification.
- Wave 5 (QCEngine) can consume `{col}_diff_1` etc. naming convention without further negotiation.
</success_criteria>

<review_discipline>
TypeScript-only changes under `packages-ts/core/**`. Per `.planning/REVIEW-DISCIPLINE.md`:

- **Reviewers**: codex `high` + **TypeScript Architect** (parallel).
- **Severity gate**: CRITICAL or HIGH only.
- **Loop**: fix on branch, re-dispatch, cap at 3.
- **Rubric calibration**:
  - CRITICAL if `rolling` uses `n` denominator for std instead of `n-1` (defeats Bessel's correction; quants get wrong variance estimates that silently bias backtests).
  - CRITICAL if `lag`/`diff`/`rolling` mutate the input `rows` array (downstream pipelines silently corrupt; this is the row-immutability invariant from the TS Architect rubric §5).
  - CRITICAL if column naming uses different separator/format than `{col}_{op}_{param}` (breaks Python parity AND Wave 5 + 6 consumers).
  - HIGH if `rolling` uses `min_periods=window` semantics instead of `min_periods=1` (Python defaults to min_periods=1 in `transforms.py:65`; mismatch produces leading nulls that Python doesn't produce).
  - HIGH if `diff2` leaves the intermediate `{col}_diff_1` column in the output (should be `{col}_diff2` only — Python returns a single Series).
  - HIGH if `n=0` or `window=0` is silently accepted (would produce an unintelligible derived column; explicit RangeError required).
  - HIGH if transforms ship in the root `@tradewinds/core` barrel instead of the subpath (would push the main bundle over 25 KB — TS-W3 iter-4 H8 lesson).
  - HIGH if string `'3.5'` is auto-coerced to numeric (silent type confusion; should produce null).
</review_discipline>

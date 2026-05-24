---
phase: ts-w4-mode2-transforms-qc-alpha
plan: 04
type: execute
wave: 4
depends_on: []
files_modified:
  - packages-ts/core/src/transforms/cross.ts
  - packages-ts/core/src/transforms/weather.ts
  - packages-ts/core/src/transforms/clip.ts
  - packages-ts/core/src/transforms/index.ts
  - packages-ts/core/tests/transforms/cross.test.ts
  - packages-ts/core/tests/transforms/weather.test.ts
  - packages-ts/core/tests/transforms/clip.test.ts
autonomous: true
requirements:
  - TS-TRANSFORM-02
must_haves:
  truths:
    - "spread(rows, colA, colB) returns rows with `{colA}_minus_{colB}` numeric column"
    - "windChill(tempF, windMph) returns the NWS wind-chill F as a number when domain valid (tempF ≤ 50 AND windMph > 3); else returns tempF unchanged; null on null/undefined/non-finite inputs"
    - "heatIndex(tempF, rhPct) returns NWS Rothfusz heat-index F as a number when tempF ≥ 80; else returns tempF unchanged; null on null/undefined/non-finite inputs"
    - "heatIndex(90, 70) matches NWS reference table value 106 °F within 1 °F"
    - "windChill(20, 15) matches NWS reference table value 6 °F within 1 °F"
    - "Out-of-domain returns null is the wrong outcome — Python returns tempF unchanged (NOT null) below the domain bound"
    - "clipOutliers(rows, col, {bounds}) clips to explicit [lo, hi]; clipOutliers(rows, col, {std}) does sigma fallback with std > 0; clipOutliers(rows, col) uses PHYSICS_BOUNDS for the canonical observation columns"
    - "clipOutliers throws ValueError-equivalent if std <= 0 in the sigma branch (Phase 3.5 review-iter fix)"
    - "clipOutliers does NOT collapse rows to NaN when sigma=0 (the review-iter HIGH fix); passes through values unchanged"
  artifacts:
    - path: packages-ts/core/src/transforms/cross.ts
      provides: "spread function — pairwise diff between two columns"
    - path: packages-ts/core/src/transforms/weather.ts
      provides: "windChill + heatIndex NWS formulas, both returning number | null"
    - path: packages-ts/core/src/transforms/clip.ts
      provides: "clipOutliers with bounds + PHYSICS_BOUNDS + sigma fallback (std>0 guard)"
  key_links:
    - from: packages-ts/core/src/transforms/clip.ts
      to: "PHYSICS_BOUNDS table"
      via: "ported from packages/core/src/tradewinds/preprocessing.py:34-46"
      pattern: "PHYSICS_BOUNDS"
---

<objective>
Port the remaining Python transforms — `spread`, `wind_chill`, `heat_index`, `clip_outliers` — to TS at `@tradewinds/core/transforms`. Together with Waves 2-3, this completes TS-TRANSFORM-02.

**NWS reference-table tests are the load-bearing acceptance criterion.** The Python implementation has been pinned against published NWS tables; TS must match within 1 °F:
- `windChill(20°F, 15 mph)` → 6 °F (NWS table; matches Python at `transforms.py:108-116`).
- `heatIndex(90°F, 70% RH)` → 106 °F (NWS Rothfusz; matches Python at `transforms.py:119-147`).

**Domain handling (Python parity is non-obvious):**
- `windChill`: valid domain is `tempF ≤ 50 AND windMph > 3`. **Outside the domain**, Python returns `tempF` (i.e. "wind chill equals air temp when wind is calm or warm"). NOT null. Null is reserved for null/undefined/non-finite inputs.
- `heatIndex`: valid domain is `tempF ≥ 80`. Outside, Python returns `tempF`. Same null rule.
- The phase-level prompt says "out-of-domain → null". This is INCORRECT vs Python — the Python source explicitly returns `temp_f` (NOT None) for out-of-domain branches at `transforms.py:114` and `transforms.py:126`. **Honor Python source as canonical** and document a Parity-Ticket note in the task action explaining the deviation from the prompt.

**clipOutliers (Phase 3.5 review-iter fix):**
The Python source at `preprocessing.py:84-88` explicitly raises `ValueError` when `std <= 0` in the sigma fallback branch — the iter-1 architect HIGH was "std≤0 collapses every row to the mean (silent dataset corruption)". TS MUST refuse the same way. Additionally, when `sigma === 0` (all values identical), the clamp `[mu, mu]` collapses the column to a constant; the prompt's review-iter fix says "pass-through" in that case. **The Python source as-is DOES collapse to mu when sigma=0** (`mu ± std*0 = [mu, mu]`); the "pass-through" fix is a TS-side improvement the prompt is requesting. Implement: when `sigma === 0 || !Number.isFinite(sigma)`, pass values through unchanged.

**Subpath placement:** all three files (`cross.ts`, `weather.ts`, `clip.ts`) live in the existing `@tradewinds/core/transforms` module (shared with Wave 2 + Wave 3). Same barrel + subpath + tsup entry.

**Independence:** Wave 4 has NO hard dependency on Waves 1, 2, 3, 5, 6. The barrel + subpath wiring is shared with Wave 2 (idempotent — Wave 4 appends if Wave 2 already shipped, creates if not).
</objective>

<context_files>
- `.planning/REQUIREMENTS.md` TS-TRANSFORM-02 (canonical text — note "out-of-domain → null" wording is inaccurate vs Python; honor Python source per Parity-Ticket)
- `packages/core/src/tradewinds/transforms.py` lines 103-157 (Python `spread`, `wind_chill`, `heat_index`, `clip_outliers` — the canonical formulas)
- `packages/core/src/tradewinds/preprocessing.py` lines 30-91 (Python `PHYSICS_BOUNDS` + `clip_outliers` with std>0 guard — the review-iter HIGH fix)
- NWS wind-chill reference tables: https://www.weather.gov/safety/cold-wind-chill-chart (windChill(20, 15) = 6 °F)
- NWS heat-index reference tables: https://www.wpc.ncep.noaa.gov/html/heatindex.shtml (heatIndex(90, 70) = 106 °F)
- Wave 2 plan (ts-w4-02-PLAN.md) for the transforms subpath + tsup + barrel scaffolding.
</context_files>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: spread + windChill + heatIndex (NWS formulas)</name>
  <files>packages-ts/core/src/transforms/cross.ts, packages-ts/core/src/transforms/weather.ts, packages-ts/core/tests/transforms/cross.test.ts, packages-ts/core/tests/transforms/weather.test.ts</files>
  <read_first>
    - `packages/core/src/tradewinds/transforms.py` lines 103-147 (Python source — port verbatim)
    - NWS wind-chill formula reference: `wc = 35.74 + 0.6215*T - 35.75*V^0.16 + 0.4275*T*V^0.16` where T in °F, V in mph, domain T ≤ 50 °F, V > 3 mph.
    - NWS heat-index Rothfusz formula: see `transforms.py:131-147` for the 9-term polynomial + the two adjustment branches (low-humidity dry adjustment when h<13 and 80≤T≤112; high-humidity wet adjustment when h>85 and 80≤T≤87).
  </read_first>
  <behavior>
    - **`spread<Row>(rows, colA, colB)`** — derived column name: `${colA}_minus_${colB}`. Value at i = `Number(rows[i][colA]) - Number(rows[i][colB])` IF both are finite numbers; else `null`. Pure (no mutation).
    - **`windChill(tempF: number | null | undefined, windMph: number | null | undefined): number | null`**:
      - If either input is null/undefined/non-finite → return `null`.
      - If `tempF > 50.0 || windMph <= 3.0` → return `tempF` (NOT null — Python parity at `transforms.py:114`).
      - Else compute `35.74 + 0.6215 * tempF - 35.75 * windMph^0.16 + 0.4275 * tempF * windMph^0.16` and return the number.
    - **`heatIndex(tempF: number | null | undefined, rhPct: number | null | undefined): number | null`**:
      - If either input is null/undefined/non-finite → return `null`.
      - If `tempF < 80.0` → return `tempF` (NOT null — Python parity at `transforms.py:126`).
      - Compute simple approximation: `simple = 0.5 * (tempF + 61.0 + (tempF - 68.0) * 1.2 + rhPct * 0.094)`.
      - If `(simple + tempF) / 2.0 < 80.0` → return `simple`.
      - Else compute the 9-term Rothfusz regression EXACTLY as in `transforms.py:132-141`.
      - Apply low-humidity adjustment: `if rhPct < 13 && 80 ≤ tempF ≤ 112: hi -= ((13 - rhPct) / 4) * sqrt((17 - |tempF - 95|) / 17)`.
      - Apply high-humidity adjustment: `else if rhPct > 85 && 80 ≤ tempF ≤ 87: hi += ((rhPct - 85) / 10) * ((87 - tempF) / 5)`.
      - Return `hi`.
    - All three functions are pure / referentially transparent — no mutation, no I/O.
    - Type-narrowing: signatures accept `number | null | undefined` for the scalars; the type-narrowed null returns from `windChill` / `heatIndex` are the union return type. NOT a discriminated union — just `number | null`.
  </behavior>
  <action>
    1. Create `packages-ts/core/src/transforms/cross.ts`:
       ```typescript
       /** spread — pairwise diff between two numeric columns. Mirrors Python
        *  `transforms.spread(df, col_a, col_b)`. Derived col: `{colA}_minus_{colB}`. */
       export function spread<Row extends Record<string, unknown>>(
         rows: ReadonlyArray<Row>,
         colA: string,
         colB: string,
       ): ReadonlyArray<Row & Record<string, number | null>> {
         const key = `${colA}_minus_${colB}`;
         const out: Array<Row & Record<string, number | null>> = [];
         for (const r of rows) {
           const a = r?.[colA];
           const b = r?.[colB];
           const v = typeof a === "number" && Number.isFinite(a)
                  && typeof b === "number" && Number.isFinite(b)
                    ? a - b
                    : null;
           out.push({ ...r, [key]: v } as Row & Record<string, number | null>);
         }
         return out;
       }
       ```

    2. Create `packages-ts/core/src/transforms/weather.ts`:
       ```typescript
       /**
        * NWS wind-chill formula (valid: tempF ≤ 50 AND windMph > 3).
        *
        * Mirrors Python `transforms.wind_chill` at `transforms.py:108-116`.
        * Out-of-domain returns tempF unchanged (PARITY-NOTE: NOT null —
        * the requirements text says "out-of-domain → null" but Python
        * returns the unmodified temp; honor Python as canonical).
        */
       export function windChill(
         tempF: number | null | undefined,
         windMph: number | null | undefined,
       ): number | null {
         if (tempF === null || tempF === undefined
             || windMph === null || windMph === undefined) {
           return null;
         }
         if (typeof tempF !== "number" || !Number.isFinite(tempF)) return null;
         if (typeof windMph !== "number" || !Number.isFinite(windMph)) return null;
         if (tempF > 50.0 || windMph <= 3.0) return tempF;  // out-of-domain → tempF
         const v016 = Math.pow(windMph, 0.16);
         return 35.74 + 0.6215 * tempF - 35.75 * v016 + 0.4275 * tempF * v016;
       }

       /**
        * NWS heat index (Rothfusz regression, valid: tempF ≥ 80).
        *
        * Mirrors Python `transforms.heat_index` at `transforms.py:119-147`.
        * Includes both adjustment branches (low-humidity dry, high-humidity
        * wet). Out-of-domain returns tempF unchanged (PARITY-NOTE: NOT null).
        */
       export function heatIndex(
         tempF: number | null | undefined,
         rhPct: number | null | undefined,
       ): number | null {
         if (tempF === null || tempF === undefined
             || rhPct === null || rhPct === undefined) {
           return null;
         }
         if (typeof tempF !== "number" || !Number.isFinite(tempF)) return null;
         if (typeof rhPct !== "number" || !Number.isFinite(rhPct)) return null;
         if (tempF < 80.0) return tempF;  // out-of-domain → tempF

         const t = tempF;
         const h = rhPct;
         const simple = 0.5 * (t + 61.0 + (t - 68.0) * 1.2 + h * 0.094);
         if ((simple + t) / 2.0 < 80.0) return simple;

         let hi =
           -42.379
           + 2.04901523 * t
           + 10.14333127 * h
           - 0.22475541 * t * h
           - 0.00683783 * t * t
           - 0.05481717 * h * h
           + 0.00122874 * t * t * h
           + 0.00085282 * t * h * h
           - 0.00000199 * t * t * h * h;

         if (h < 13.0 && t >= 80.0 && t <= 112.0) {
           hi -= ((13.0 - h) / 4.0) * Math.sqrt((17.0 - Math.abs(t - 95.0)) / 17.0);
         } else if (h > 85.0 && t >= 80.0 && t <= 87.0) {
           hi += ((h - 85.0) / 10.0) * ((87.0 - t) / 5.0);
         }
         return hi;
       }
       ```

    3. Write `packages-ts/core/tests/transforms/cross.test.ts`:
       - `spread([{a:10,b:7}, {a:12,b:9}], 'a', 'b')` → derived `a_minus_b: [3, 3]`.
       - Null propagation: `spread([{a:null,b:7}], 'a', 'b')` → `a_minus_b: null`.
       - String value: `spread([{a:'10',b:7}], 'a', 'b')` → `a_minus_b: null` (no auto-coercion; matches Wave 2 strictness).
       - Source rows unchanged.

    4. Write `packages-ts/core/tests/transforms/weather.test.ts`:
       - **NWS reference table (load-bearing):**
         - `windChill(20, 15)` ≈ 6 °F → `expect(Math.abs(result! - 6) < 1)`.
         - `windChill(0, 25)` ≈ -24 °F → within 1 °F.
         - `windChill(40, 10)` ≈ 34 °F → within 1 °F.
         - `heatIndex(90, 70)` ≈ 106 °F → within 1 °F.
         - `heatIndex(80, 50)` ≈ 82 °F → within 1 °F.
         - `heatIndex(100, 60)` ≈ 129 °F → within 1 °F.
       - **Out-of-domain returns tempF (NOT null), Python parity:**
         - `windChill(60, 10) === 60` (tempF > 50 → returns tempF).
         - `windChill(20, 2) === 20` (windMph ≤ 3 → returns tempF).
         - `heatIndex(70, 50) === 70` (tempF < 80 → returns tempF).
       - **Null/undefined input → null:**
         - `windChill(null, 15) === null`.
         - `windChill(20, null) === null`.
         - `windChill(undefined, 15) === null`.
         - `heatIndex(null, 70) === null`.
         - `heatIndex(90, undefined) === null`.
       - **Non-finite input → null:**
         - `windChill(NaN, 15) === null`.
         - `windChill(Infinity, 15) === null`.
         - `heatIndex(90, NaN) === null`.
       - **Low-humidity dry adjustment branch:**
         - `heatIndex(95, 10)` → should be slightly LOWER than the unadjusted Rothfusz (the `(13-h)/4 * sqrt(...)` subtraction kicks in for h<13). Verify by computing both with and without adjustment and confirming the difference is the expected magnitude.
       - **High-humidity wet adjustment branch:**
         - `heatIndex(85, 90)` → adjusted upward by `(90-85)/10 * (87-85)/5 = 0.5 * 0.4 = 0.2`. Confirm the increment.
  </action>
  <acceptance_criteria>
    - `grep -n "export function spread\\|export function windChill\\|export function heatIndex" packages-ts/core/src/transforms/cross.ts packages-ts/core/src/transforms/weather.ts` confirms exports.
    - `grep -n "35.74\\|0.6215\\|-42.379\\|2.04901523" packages-ts/core/src/transforms/weather.ts` confirms NWS-formula constants ported verbatim.
    - `grep -n "tempF > 50.0\\|windMph <= 3.0\\|tempF < 80.0" packages-ts/core/src/transforms/weather.ts` confirms domain checks.
    - `grep -n "PARITY-NOTE\\|return tempF" packages-ts/core/src/transforms/weather.ts` confirms parity documentation and out-of-domain returns tempF.
    - `pnpm --filter @tradewinds/core test -- transforms/weather` ≥ 15 cases all green.
    - Reference table assertions explicitly check `windChill(20, 15) ≈ 6` and `heatIndex(90, 70) ≈ 106` within 1 °F.
  </acceptance_criteria>
</task>

<task type="auto" tdd="true">
  <name>Task 2: clipOutliers (PHYSICS_BOUNDS + bounds + sigma fallback with std>0 + sigma=0 pass-through)</name>
  <files>packages-ts/core/src/transforms/clip.ts, packages-ts/core/tests/transforms/clip.test.ts</files>
  <read_first>
    - `packages/core/src/tradewinds/preprocessing.py` lines 34-91 (the canonical Python implementation including std>0 guard at lines 84-88)
    - `packages/core/src/tradewinds/transforms.py` lines 150-157 (the legacy `clip_outliers` — note this is the OLDER form; the preprocessing.py form is the v0.1.0 canonical surface).
    - Mean + sample stdev (Bessel's correction n-1) — TS implementation re-used from Wave 2's rolling std logic.
  </read_first>
  <behavior>
    - Signature: `clipOutliers<Row extends Record<string, unknown>>(rows, col, opts?: ClipOutliersOptions): ReadonlyArray<Row & Record<string, number | null>>`.
    - `ClipOutliersOptions = { bounds?: [number, number]; std?: number }`. Default `std=3.0`.
    - **PHYSICS_BOUNDS table** — port from Python `preprocessing.py:34-46`:
      ```typescript
      export const PHYSICS_BOUNDS: ReadonlyMap<string, readonly [number, number]> = new Map([
        ["temp_c", [-89.0, 57.0]],
        ["dew_point_c", [-89.0, 35.0]],
        ["dewpoint_c", [-89.0, 35.0]],
        ["wind_speed_ms", [0.0, 100.0]],
        ["wind_speed_kt", [0.0, 200.0]],
        ["wind_dir_deg", [0.0, 360.0]],
        ["wind_dir_degrees", [0.0, 360.0]],
        ["slp_hpa", [870.0, 1085.0]],
        ["sea_level_pressure_mb", [870.0, 1085.0]],
        ["relative_humidity_pct_2m", [0.0, 100.0]],
        ["precip_mm_1h", [0.0, 305.0]],
      ]);
      ```
    - **Decision tree (mirrors Python `preprocessing.clip_outliers:75-91`):**
      1. If `opts.bounds` is provided → clip every numeric row[col] to `[bounds[0], bounds[1]]`. Derived column overwrites? No — return a new column `${col}_clipped`. Rationale: TS doesn't mutate; quants apply the new column explicitly. (This deviates slightly from Python which returns a Series; TS row-shape requires a column name. Document in JSDoc.)
      2. Else if `PHYSICS_BOUNDS.has(col)` → clip to physics defaults.
      3. Else → sigma fallback:
         a. If `opts.std <= 0` → throw `RangeError("clipOutliers: std must be > 0 for the sigma fallback (got ${std}); pass bounds=[lo, hi] or use a physics-default column")`. Matches Python `ValueError` at `preprocessing.py:84-88`.
         b. Compute `mu` = mean of non-null finite values in column.
         c. Compute `sigma` = sample stdev (n-1) of non-null finite values.
         d. **Sigma=0 pass-through (Phase 3.5 review-iter fix per the planning prompt):** if `sigma === 0 || !Number.isFinite(sigma)` → DO NOT clip; return rows with the original value copied into `${col}_clipped` (pass-through). Avoids the silent "collapse every row to mu" failure mode when all rows are identical.
         e. Else clip to `[mu - std*sigma, mu + std*sigma]`.
    - Non-numeric / null source values → derived column is `null` (pass-through nulls).
    - Output column: `${col}_clipped`. Source `col` is preserved unchanged (Python returns a Series; TS returns rows with new column).
    - Pure: source rows NOT mutated.
  </behavior>
  <action>
    1. Create `packages-ts/core/src/transforms/clip.ts`:
       ```typescript
       export const PHYSICS_BOUNDS: ReadonlyMap<string, readonly [number, number]> = new Map([
         ["temp_c", [-89.0, 57.0] as const],
         ["dew_point_c", [-89.0, 35.0] as const],
         ["dewpoint_c", [-89.0, 35.0] as const],
         ["wind_speed_ms", [0.0, 100.0] as const],
         ["wind_speed_kt", [0.0, 200.0] as const],
         ["wind_dir_deg", [0.0, 360.0] as const],
         ["wind_dir_degrees", [0.0, 360.0] as const],
         ["slp_hpa", [870.0, 1085.0] as const],
         ["sea_level_pressure_mb", [870.0, 1085.0] as const],
         ["relative_humidity_pct_2m", [0.0, 100.0] as const],
         ["precip_mm_1h", [0.0, 305.0] as const],
       ]);

       export interface ClipOutliersOptions {
         bounds?: readonly [number, number];
         std?: number;
       }

       /**
        * clipOutliers — winsorize a numeric column. Mirrors Python
        * `tradewinds.preprocessing.clip_outliers` (v0.1.0 canonical
        * surface; supersedes the older `transforms.clip_outliers`).
        *
        * Decision tree:
        *  - `opts.bounds` set            → clip to explicit [lo, hi]
        *  - `PHYSICS_BOUNDS.has(col)`    → clip to physics defaults
        *  - else                         → sigma fallback (mu ± std*sigma)
        *
        * @throws RangeError  if sigma fallback would use std ≤ 0
        *
        * Sigma=0 pass-through: when stdev is zero (all values identical),
        * the clamp [mu, mu] would collapse the column. We pass values
        * through unchanged instead (Phase 3.5 review-iter fix).
        *
        * @returns rows with derived `{col}_clipped` column. Source column
        *          is preserved unchanged.
        */
       export function clipOutliers<Row extends Record<string, unknown>>(
         rows: ReadonlyArray<Row>,
         col: string,
         opts: ClipOutliersOptions = {},
       ): ReadonlyArray<Row & Record<string, number | null>> {
         const std = opts.std ?? 3.0;
         const key = `${col}_clipped`;

         // Determine clip range.
         let lo: number;
         let hi: number;
         let passThrough = false;

         if (opts.bounds !== undefined) {
           [lo, hi] = opts.bounds;
         } else if (PHYSICS_BOUNDS.has(col)) {
           [lo, hi] = PHYSICS_BOUNDS.get(col)!;
         } else {
           if (!Number.isFinite(std) || std <= 0) {
             throw new RangeError(
               `clipOutliers: std must be > 0 for the sigma fallback (got ${std}); ` +
               `pass bounds=[lo, hi] or use a physics-default column`,
             );
           }
           // Compute mu + sigma over non-null finite values.
           const vals: number[] = [];
           for (const r of rows) {
             const v = r?.[col];
             if (typeof v === "number" && Number.isFinite(v)) vals.push(v);
           }
           if (vals.length < 2) {
             // Not enough values to compute sigma → pass-through.
             passThrough = true;
             lo = -Infinity;
             hi = Infinity;
           } else {
             const mu = vals.reduce((a, b) => a + b, 0) / vals.length;
             const sumSq = vals.reduce((a, b) => a + (b - mu) ** 2, 0);
             const sigma = Math.sqrt(sumSq / (vals.length - 1));
             if (sigma === 0 || !Number.isFinite(sigma)) {
               passThrough = true;
               lo = -Infinity;
               hi = Infinity;
             } else {
               lo = mu - std * sigma;
               hi = mu + std * sigma;
             }
           }
         }

         const out: Array<Row & Record<string, number | null>> = [];
         for (const r of rows) {
           const v = r?.[col];
           let clipped: number | null;
           if (typeof v === "number" && Number.isFinite(v)) {
             if (passThrough) {
               clipped = v;
             } else {
               clipped = Math.min(Math.max(v, lo), hi);
             }
           } else {
             clipped = null;
           }
           out.push({ ...r, [key]: clipped } as Row & Record<string, number | null>);
         }
         return out;
       }
       ```

    2. Write `packages-ts/core/tests/transforms/clip.test.ts`:
       - **Explicit bounds**: `clipOutliers([{x:5}, {x:50}, {x:-10}], 'x', { bounds: [0, 30] })` → `x_clipped: [5, 30, 0]`.
       - **PHYSICS_BOUNDS for temp_c**: `clipOutliers([{temp_c: -100}, {temp_c: 0}, {temp_c: 60}], 'temp_c')` → `temp_c_clipped: [-89, 0, 57]`.
       - **PHYSICS_BOUNDS for wind_speed_ms**: `clipOutliers([{wind_speed_ms: -5}, {wind_speed_ms: 50}, {wind_speed_ms: 200}], 'wind_speed_ms')` → `[0, 50, 100]`.
       - **Sigma fallback (std=3 default)**: `clipOutliers([{x:0},{x:1},{x:2},{x:3},{x:100}], 'x')` — mean ≈ 21.2, sigma ≈ 43.8 — clamp ≈ `[-110, 153]`. So values stay unclipped (`[0, 1, 2, 3, 100]`). Validate with a tighter `std=0.5` to force a clip.
       - **std=0 → RangeError**: `clipOutliers([{x:1},{x:2}], 'x', { std: 0 })` throws RangeError with message containing 'std must be > 0'.
       - **std=-1 → RangeError**: similar.
       - **std=NaN → RangeError**: `Number.isFinite(NaN) === false`.
       - **Sigma=0 pass-through (the review-iter fix)**: `clipOutliers([{x:5},{x:5},{x:5},{x:5}], 'x')` → output `x_clipped: [5, 5, 5, 5]` (NOT collapsed to NaN, NOT collapsed to mu=5 with a trivial clamp — explicit pass-through).
       - **Single-value fallback**: `clipOutliers([{x:5}], 'x', { std: 3 })` → cannot compute sigma (n<2) → pass-through → `x_clipped: [5]`.
       - **Null source**: `clipOutliers([{x:null},{x:5}], 'x', { bounds: [0, 10] })` → `x_clipped: [null, 5]`.
       - **String source**: `clipOutliers([{x:'5'}], 'x', { bounds: [0, 10] })` → `x_clipped: [null]` (no auto-coercion).
       - **Source rows unchanged** (deep-equal check on input).
       - **PHYSICS_BOUNDS has 11 entries**: `expect(PHYSICS_BOUNDS.size).toBe(11)`.
  </action>
  <acceptance_criteria>
    - `grep -n "export function clipOutliers\\|export const PHYSICS_BOUNDS" packages-ts/core/src/transforms/clip.ts` confirms exports.
    - `grep -n "RangeError.*std must be > 0" packages-ts/core/src/transforms/clip.ts` confirms the std>0 guard (Phase 3.5 review-iter HIGH fix).
    - `grep -n "sigma === 0\\|passThrough" packages-ts/core/src/transforms/clip.ts` confirms the sigma=0 pass-through (the planning-prompt review-iter fix).
    - `grep -n "temp_c.*-89\\|temp_c.*57\\|wind_speed_ms.*100\\|slp_hpa.*870\\|slp_hpa.*1085" packages-ts/core/src/transforms/clip.ts` confirms PHYSICS_BOUNDS values ported verbatim.
    - `pnpm --filter @tradewinds/core test -- transforms/clip` ≥ 11 cases all green.
    - Sigma-zero test explicitly asserts `[5, 5, 5, 5]` survives without clipping (NOT NaN, NOT 0).
  </acceptance_criteria>
</task>

<task type="auto" tdd="true">
  <name>Task 3: Add spread/windChill/heatIndex/clipOutliers to transforms barrel</name>
  <files>packages-ts/core/src/transforms/index.ts, packages-ts/core/tests/transforms/wave4.barrel.test.ts</files>
  <read_first>
    - `packages-ts/core/src/transforms/index.ts` (Wave 2 + Wave 3 output — barrel containing lag/diff/rolling/calendarFeatures)
    - Wave 2 + Wave 3 plans for the subpath + tsup scaffolding pattern.
  </read_first>
  <behavior>
    - Append to the existing barrel (or create with full set if Wave 2 hasn't shipped). Add exports for:
      - `spread` (from cross.ts)
      - `windChill`, `heatIndex` (from weather.ts)
      - `clipOutliers`, `PHYSICS_BOUNDS`, `ClipOutliersOptions` type (from clip.ts)
    - No new tsup entry / subpath — uses the existing `src/transforms/index.ts` from Wave 2.
    - Bundle gate: after build, `pnpm run size` confirms `@tradewinds/core` ≤ 25 KB. The Wave 4 additions are small (each function ~500 B); should fit easily.
  </behavior>
  <action>
    1. Append to `packages-ts/core/src/transforms/index.ts`:
       ```typescript
       export { spread } from "./cross.js";
       export { windChill, heatIndex } from "./weather.js";
       export { clipOutliers, PHYSICS_BOUNDS, type ClipOutliersOptions } from "./clip.js";
       ```

    2. Write `packages-ts/core/tests/transforms/wave4.barrel.test.ts`:
       ```typescript
       import { describe, expect, it } from "vitest";
       import {
         clipOutliers,
         heatIndex,
         PHYSICS_BOUNDS,
         spread,
         windChill,
         type ClipOutliersOptions,
       } from "../../src/transforms/index.js";

       describe("@tradewinds/core/transforms — Wave 4 barrel exports", () => {
         it("spread/windChill/heatIndex/clipOutliers exported", () => {
           expect(typeof spread).toBe("function");
           expect(typeof windChill).toBe("function");
           expect(typeof heatIndex).toBe("function");
           expect(typeof clipOutliers).toBe("function");
         });
         it("PHYSICS_BOUNDS exposed as a Map", () => {
           expect(PHYSICS_BOUNDS.get("temp_c")).toEqual([-89.0, 57.0]);
         });
         it("ClipOutliersOptions type compiles", () => {
           const opts: ClipOutliersOptions = { bounds: [0, 100] };
           const out = clipOutliers([{ x: 5 }], "x", opts);
           expect(out[0]!.x_clipped).toBe(5);
         });
         it("NWS reference: windChill(20,15) ≈ 6", () => {
           const v = windChill(20, 15);
           expect(v).not.toBeNull();
           expect(Math.abs(v! - 6)).toBeLessThan(1);
         });
         it("NWS reference: heatIndex(90,70) ≈ 106", () => {
           const v = heatIndex(90, 70);
           expect(v).not.toBeNull();
           expect(Math.abs(v! - 106)).toBeLessThan(1);
         });
       });
       ```

    3. Run `pnpm --filter @tradewinds/core run build && pnpm run size`. Assert `@tradewinds/core` ≤ 25 KB.
  </action>
  <acceptance_criteria>
    - `grep -n "spread\\|windChill\\|heatIndex\\|clipOutliers\\|PHYSICS_BOUNDS" packages-ts/core/src/transforms/index.ts` shows all five exports.
    - `pnpm --filter @tradewinds/core test -- transforms/wave4.barrel` 5 cases green.
    - `pnpm --filter @tradewinds/core run build` emits the updated transforms bundle.
    - `pnpm run size` reports `@tradewinds/core` ≤ 25 KB unchanged.
    - `pnpm -r run typecheck` clean.
  </acceptance_criteria>
</task>

</tasks>

<verification>
1. `pnpm --filter @tradewinds/core test -- transforms` runs all transforms test files (Wave 2 + 3 + 4); all green.
2. `pnpm --filter @tradewinds/core run typecheck` clean.
3. `pnpm --filter @tradewinds/core run build` emits the transforms subpath bundle with all 7 named exports (lag, diff, diff2, rolling, calendarFeatures, spread, windChill, heatIndex, clipOutliers) + PHYSICS_BOUNDS const.
4. `pnpm -r run typecheck` clean across the workspace.
5. `pnpm run size` reports `@tradewinds/core` ≤ 25 KB (transforms lives at subpath; root bundle unchanged).
6. NWS reference assertions: `windChill(20, 15) ≈ 6 °F` within 1 °F; `heatIndex(90, 70) ≈ 106 °F` within 1 °F.
7. Out-of-domain returns `tempF` (not null) — Python parity.
8. `clipOutliers` with `std ≤ 0` throws RangeError; with `sigma=0` passes values through unchanged (NOT collapse to mu).
</verification>

<success_criteria>
- TS-TRANSFORM-02 fully met (Waves 3 + 4 combined) — calendarFeatures + spread + windChill + heatIndex + clipOutliers all ported.
- NWS reference tables matched within 1 °F for the two canonical assertions.
- Phase 3.5 review-iter HIGH preserved: std≤0 throws; sigma=0 passes through (does NOT collapse to NaN or mu).
- Python parity on out-of-domain: windChill/heatIndex return tempF (NOT null) when domain bounds not satisfied (Parity-Ticket documented in JSDoc).
- Bundle gate holds: `@tradewinds/core` ≤ 25 KB.
- PHYSICS_BOUNDS has all 11 canonical observation-column entries.
</success_criteria>

<review_discipline>
TypeScript-only changes under `packages-ts/core/**`. Per `.planning/REVIEW-DISCIPLINE.md`:

- **Reviewers**: codex `high` + **TypeScript Architect** (parallel).
- **Severity gate**: CRITICAL or HIGH only.
- **Loop**: fix on branch, re-dispatch, cap at 3.
- **Rubric calibration**:
  - CRITICAL if `windChill`/`heatIndex` returns `null` for out-of-domain inputs instead of `tempF` (Python parity break — requirements text says null but Python source explicitly returns temp_f; honor Python).
  - CRITICAL if `clipOutliers` silently collapses to mu when sigma=0 (the Phase 3.5 review-iter HIGH the prompt explicitly calls out; silent dataset corruption).
  - CRITICAL if `clipOutliers` silently accepts `std ≤ 0` in the sigma branch (Python raises ValueError at `preprocessing.py:84-88`).
  - CRITICAL if heatIndex polynomial coefficient is mis-transcribed (any of the 9 Rothfusz terms wrong — heat-index quants would feed bad features into models).
  - CRITICAL if PHYSICS_BOUNDS values diverge from Python (e.g. wrong temp_c upper bound 57→55) — silent physics-bound corruption.
  - HIGH if NWS reference-table assertions absent or accept tolerance > 1 °F (the "match within 1 °F" success criterion is unverifiable).
  - HIGH if `spread` output column name uses different separator than `_minus_` (e.g. `_sub_` or `_diff_`).
  - HIGH if Wave 4 mutates source rows (the row-immutability invariant from Waves 2-3).
  - HIGH if `windChill`/`heatIndex` accepts string-coerced inputs (`'20'` for tempF) — should require explicit number.
</review_discipline>

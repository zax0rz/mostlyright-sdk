---
phase: ts-w2-parity-gate
plan: 05
type: execute
wave: 3
depends_on:
  - ts-w2-04
files_modified:
  - packages-ts/core/src/internal/pairs.ts
  - packages-ts/core/src/internal/index.ts
  - packages-ts/core/package.json
  - packages-ts/core/tests/internal/pairs.test.ts
autonomous: true
requirements:
  - TS-PARITY-01

must_haves:
  truths:
    - "buildPairs(station, dates, observationsByDate, climateByDate, opts?) returns one PairsRow per date, in input-date order."
    - "Each PairsRow has 19 columns matching Python pairs.build_pairs output: date, station, cli_high_f, cli_low_f, cli_report_type, obs_high_f, obs_low_f, obs_mean_f, obs_mean_dewpoint_f, obs_max_wind_kt, obs_max_gust_kt, obs_total_precip_in, obs_count, fcst_high_f, fcst_low_f, fcst_model, fcst_issued_at, fcst_pop_6hr_pct, fcst_qpf_6hr_in, market_close_utc."
    - "All fcst_* fields are null when forecastsByDate is undefined OR null (TS-W2 ships Mode 1 only — forecast wiring is deferred per stub Out-of-Scope)."
    - "_obsAggregates computes max(temp_f), min(temp_f), mean(temp_f), mean(dewpoint_f), max(wind_speed_kt), max(wind_gust_kt), sum(precip_1hr_inches), count over filtered (non-null) values."
    - "Mean uses arithmetic mean (sum / count); not weighted. Matches Python."
    - "Empty observations array → all obs_* fields null; obs_count = 0."
    - "market_close_utc is computed via marketCloseUtc(date, station) from @tradewinds/core (existing TS-W1 export)."
    - "pairsToRows(rows) returns rows unchanged (TS has no DataFrame; the function exists for surface-parity but is just identity OR a JSON.stringify helper for downstream serialization)."
    - "buildPairs is pure: same inputs → same outputs, no I/O."
  artifacts:
    - path: "packages-ts/core/src/internal/pairs.ts"
      provides: "buildPairs + _obsAggregates + pairsToRows + PairsRow type"
      exports: ["buildPairs", "pairsToRows", "type PairsRow"]
  key_links:
    - from: "packages-ts/core/src/internal/pairs.ts"
      to: "@tradewinds/core/snapshot (marketCloseUtc)"
      via: "import for 4:30 PM LST cutoff"
      pattern: "marketCloseUtc"
    - from: "packages-ts/core/src/internal/pairs.ts"
      to: "Observation (structural — only temp_f, dewpoint_f, wind_speed_kt, wind_gust_kt, precip_1hr_inches needed)"
      via: "structural interface — avoid core→weather coupling"
      pattern: "PairsObservationLike"
---

<objective>
Port Python's `tradewinds._internal._pairs.build_pairs` to TypeScript. This is the join logic that turns merged observation rows + climate rows + (optional) forecast rows into one row per settlement date. Plan 06's research orchestrator calls this; Plan 08's parity test consumes its output.

**Why this matters:** mergeObservations (Plan 04) dedups; buildPairs aggregates. Without correct aggregation (max temp, min temp, mean temp, mean dewpoint, max wind, max gust, sum precip, count), the parity fixtures break on every single row — even with byte-perfect merge output, the wrong aggregation produces the wrong final 19-column row.

**Scope cut:** TS-W2 is Mode 1 ONLY (no forecast). All `fcst_*` columns are unconditionally null. The full Python `_select_best_run` / `_aggregate_fcst_temps_*` IEM MOS + Open-Meteo handling is intentionally NOT ported (matches the TS-W1 research() pattern and the stub PLAN's Wave 5 spec).

**Output:** Single TS module under `@tradewinds/core/internal/pairs.ts`; full unit-test coverage with synthetic inputs.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@.planning/REVIEW-DISCIPLINE.md
@.planning/phases/ts-w2-parity-gate/PLAN.md
@.planning/phases/ts-w2-parity-gate/ts-w2-04-PLAN.md
@packages/core/src/tradewinds/_internal/_pairs.py
@packages-ts/core/src/snapshot.ts
@packages-ts/meta/src/research.ts
@packages-ts/core/src/internal/merge/observations.ts

<interfaces>
From `@tradewinds/core` (existing TS-W1 + Plan 04 outputs):
```typescript
export function marketCloseUtc(date: string, station: string): Date; // returns a Date in UTC; toISOString() for serialization
export function settlementDateFor(observedAt: Date, station: string): string; // YYYY-MM-DD LST
// Plan 04:
export function mergeObservations<T extends ObservationKey>(rows: ReadonlyArray<T>): ReadonlyArray<T>;
```

From the meta package's existing W1 ResearchRow shape (`packages-ts/meta/src/research.ts:48-70`), the target column order Plan 05 must produce matches:
```typescript
date, station, cli_high_f, cli_low_f, cli_report_type,
obs_high_f, obs_low_f, obs_mean_f, obs_mean_dewpoint_f,
obs_max_wind_kt, obs_max_gust_kt, obs_total_precip_in, obs_count,
fcst_high_f, fcst_low_f, fcst_model, fcst_issued_at, fcst_pop_6hr_pct, fcst_qpf_6hr_in,
market_close_utc
```

Python `build_pairs_row` returns dict with this exact field order (see `_pairs.py:346-359`). The TS port must use the same Object.freeze + insertion-order construction so JSON.stringify produces matching column order — the parity test (Plan 08) compares via row-equality but consistent ordering aids debugging.
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Port _obsAggregates pure function with unit tests</name>
  <files>packages-ts/core/src/internal/pairs.ts, packages-ts/core/tests/internal/pairs.test.ts</files>
  <behavior>
    - `_obsAggregates([])` returns `{ obs_high_f: null, obs_low_f: null, obs_mean_f: null, obs_mean_dewpoint_f: null, obs_max_wind_kt: null, obs_max_gust_kt: null, obs_total_precip_in: null, obs_count: 0 }`.
    - `_obsAggregates([{temp_f: 32, ...}])` → obs_high_f = 32, obs_low_f = 32, obs_mean_f = 32, obs_count = 1.
    - Multi-row: high/low = max/min over non-null temp_f; mean = arithmetic mean.
    - Mean of `[null, 30, 40]` (one null) → mean over non-null only → 35 (NOT 23.33).
    - obs_count counts ALL observations (including ones with all-null measures) — matches Python `len(observations)`.
    - All measures missing across all rows → returns nulls for max/min/mean/sum but obs_count = N (the input length).
    - obs_total_precip_in = `sum(non_null_precip)` OR null if no non-null precip rows (mirror Python `sum(precips) if precips else None`).
    - Output object key order matches Python field order in `_obs_aggregates` return dict.
  </behavior>
  <action>
    Port `packages/core/src/tradewinds/_internal/_pairs.py::_obs_aggregates` (L97-150).

    1. **Define the structural input type** (avoid coupling to weather's Observation):
       ```typescript
       /** Subset of fields _obsAggregates reads from each row. */
       export interface PairsObservationLike {
         readonly temp_f?: number | null;
         readonly dewpoint_f?: number | null;
         readonly wind_speed_kt?: number | null;
         readonly wind_gust_kt?: number | null;
         readonly precip_1hr_inches?: number | null;
       }
       ```

       The full Observation type (from `weather/_parsers/awc.ts`) structurally satisfies this. Generic parametrization NOT needed — output type is fixed.

    2. **Aggregation helper**:
       ```typescript
       function collectNonNull(obs: ReadonlyArray<PairsObservationLike>, key: keyof PairsObservationLike): number[] {
         const out: number[] = [];
         for (const o of obs) {
           const v = o[key];
           if (typeof v === "number" && Number.isFinite(v)) out.push(v);
         }
         return out;
       }

       function meanOrNull(vs: number[]): number | null {
         if (vs.length === 0) return null;
         let s = 0;
         for (const v of vs) s += v;
         return s / vs.length;
       }

       function maxOrNull(vs: number[]): number | null {
         if (vs.length === 0) return null;
         let best = vs[0]!;
         for (let i = 1; i < vs.length; i++) if (vs[i]! > best) best = vs[i]!;
         return best;
       }

       function minOrNull(vs: number[]): number | null {
         if (vs.length === 0) return null;
         let best = vs[0]!;
         for (let i = 1; i < vs.length; i++) if (vs[i]! < best) best = vs[i]!;
         return best;
       }

       function sumOrNull(vs: number[]): number | null {
         if (vs.length === 0) return null;
         let s = 0;
         for (const v of vs) s += v;
         return s;
       }
       ```

    3. **`_obsAggregates`**:
       ```typescript
       export interface ObsAggregates {
         readonly obs_high_f: number | null;
         readonly obs_low_f: number | null;
         readonly obs_mean_f: number | null;
         readonly obs_mean_dewpoint_f: number | null;
         readonly obs_max_wind_kt: number | null;
         readonly obs_max_gust_kt: number | null;
         readonly obs_total_precip_in: number | null;
         readonly obs_count: number;
       }

       export function _obsAggregates(observations: ReadonlyArray<PairsObservationLike>): ObsAggregates {
         if (observations.length === 0) {
           return Object.freeze({
             obs_high_f: null, obs_low_f: null, obs_mean_f: null,
             obs_mean_dewpoint_f: null, obs_max_wind_kt: null, obs_max_gust_kt: null,
             obs_total_precip_in: null, obs_count: 0,
           });
         }
         const temps = collectNonNull(observations, "temp_f");
         const dewps = collectNonNull(observations, "dewpoint_f");
         const winds = collectNonNull(observations, "wind_speed_kt");
         const gusts = collectNonNull(observations, "wind_gust_kt");
         const precips = collectNonNull(observations, "precip_1hr_inches");
         return Object.freeze({
           obs_high_f: maxOrNull(temps),
           obs_low_f: minOrNull(temps),
           obs_mean_f: meanOrNull(temps),
           obs_mean_dewpoint_f: meanOrNull(dewps),
           obs_max_wind_kt: maxOrNull(winds),
           obs_max_gust_kt: maxOrNull(gusts),
           obs_total_precip_in: sumOrNull(precips),
           obs_count: observations.length,
         });
       }
       ```

       **Note on numeric stability:** the mean of floats is non-associative (a + b + c can yield a different float than c + b + a). The Python parity gate relies on input order being deterministic — Plan 06's orchestrator must sort observations by `(observed_at, source)` BEFORE calling `buildPairs` to preserve byte-equivalent floats. Document this requirement in Plan 06's plan; do not handle it here.

    4. **Tests** (cover all 7 behavioral assertions above):
       - Empty → all-null aggregates, obs_count 0.
       - Single non-null temp_f row.
       - Multi-row with one null temp_f → mean excludes the null.
       - All-null temps but populated wind_speed_kt → temps null, wind populated, obs_count = N.
       - obs_total_precip_in with no non-null precip rows → null (not 0).
       - obs_total_precip_in with one non-null = 0.5 → 0.5.
       - obs_count counts ALL rows including all-null ones.
       - Object.isFrozen(returned) is true.
       - Object key order matches Python via `Object.keys()` returning the exact field-order array.
  </action>
  <verify>
    <automated>pnpm --filter @tradewinds/core test -- --run pairs.test</automated>
  </verify>
  <done>
    `_obsAggregates` exported from `packages-ts/core/src/internal/pairs.ts`; all behavioral tests pass; output is frozen; key order matches Python.
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Port buildPairs + buildPairsRow + pairsToRows with full-flow tests</name>
  <files>packages-ts/core/src/internal/pairs.ts, packages-ts/core/src/internal/index.ts, packages-ts/core/package.json, packages-ts/core/tests/internal/pairs.test.ts</files>
  <behavior>
    - `buildPairs("NYC", ["2025-01-08", "2025-01-09"], {"2025-01-08": [obs1, obs2], "2025-01-09": []}, {"2025-01-08": cli1, "2025-01-09": null})` returns 2 PairsRow objects.
    - Each PairsRow has 20 columns in this exact order: date, station, cli_high_f, cli_low_f, cli_report_type, obs_high_f, obs_low_f, obs_mean_f, obs_mean_dewpoint_f, obs_max_wind_kt, obs_max_gust_kt, obs_total_precip_in, obs_count, fcst_high_f, fcst_low_f, fcst_model, fcst_issued_at, fcst_pop_6hr_pct, fcst_qpf_6hr_in, market_close_utc.
    - cli null → cli_high_f, cli_low_f, cli_report_type all null.
    - cli object → cli_high_f, cli_low_f, cli_report_type pulled from cli.high_temp_f, cli.low_temp_f, cli.report_type respectively.
    - obs aggregates inlined via `_obsAggregates`.
    - All fcst_* = null (TS-W2 Mode 1 only).
    - market_close_utc = `marketCloseUtc(date, station).toISOString().slice(0,-5) + "Z"` (mirror Python `strftime("%Y-%m-%dT%H:%M:%SZ")` — no millis).
    - `pairsToRows(rows)` returns the array unchanged (identity).
    - Empty dates array → empty result.
  </behavior>
  <action>
    1. Build on Task 1's pairs.ts. Add these exports:

       ```typescript
       /** A single date-keyed pairs row — 20 columns, byte-shape-equivalent to Python build_pairs_row output. */
       export interface PairsRow {
         readonly date: string;            // YYYY-MM-DD
         readonly station: string;          // 3-letter NWS code
         readonly cli_high_f: number | null;
         readonly cli_low_f: number | null;
         readonly cli_report_type: string | null;
         readonly obs_high_f: number | null;
         readonly obs_low_f: number | null;
         readonly obs_mean_f: number | null;
         readonly obs_mean_dewpoint_f: number | null;
         readonly obs_max_wind_kt: number | null;
         readonly obs_max_gust_kt: number | null;
         readonly obs_total_precip_in: number | null;
         readonly obs_count: number;
         readonly fcst_high_f: null;
         readonly fcst_low_f: null;
         readonly fcst_model: null;
         readonly fcst_issued_at: null;
         readonly fcst_pop_6hr_pct: null;
         readonly fcst_qpf_6hr_in: null;
         readonly market_close_utc: string; // ISO 8601 UTC string ending in "Z"
       }

       /** Subset of ClimateObservation fields used by buildPairs. */
       export interface PairsClimateLike {
         readonly high_temp_f: number | null;
         readonly low_temp_f: number | null;
         readonly report_type: string;
       }

       export interface BuildPairsOptions {
         readonly tzOverride?: string; // forwarded to marketCloseUtc
       }
       ```

    2. **buildPairsRow** (port `_pairs.py:233-359`, Mode 1 subset):
       ```typescript
       export function buildPairsRow(
         dateStr: string,
         station: string,
         observations: ReadonlyArray<PairsObservationLike>,
         climate: PairsClimateLike | null,
         opts: BuildPairsOptions = {},
       ): PairsRow {
         const obsAgg = _obsAggregates(observations);
         const closeUtc = marketCloseUtc(dateStr, station /*, opts.tzOverride */);
         // Format YYYY-MM-DDTHH:MM:SSZ (no milliseconds; mirror Python strftime).
         const closeIso = `${closeUtc.toISOString().slice(0, 19)}Z`;
         return Object.freeze({
           date: dateStr,
           station,
           cli_high_f: climate ? climate.high_temp_f : null,
           cli_low_f: climate ? climate.low_temp_f : null,
           cli_report_type: climate ? climate.report_type : null,
           obs_high_f: obsAgg.obs_high_f,
           obs_low_f: obsAgg.obs_low_f,
           obs_mean_f: obsAgg.obs_mean_f,
           obs_mean_dewpoint_f: obsAgg.obs_mean_dewpoint_f,
           obs_max_wind_kt: obsAgg.obs_max_wind_kt,
           obs_max_gust_kt: obsAgg.obs_max_gust_kt,
           obs_total_precip_in: obsAgg.obs_total_precip_in,
           obs_count: obsAgg.obs_count,
           fcst_high_f: null,
           fcst_low_f: null,
           fcst_model: null,
           fcst_issued_at: null,
           fcst_pop_6hr_pct: null,
           fcst_qpf_6hr_in: null,
           market_close_utc: closeIso,
         });
       }
       ```

       **Note on tzOverride:** `marketCloseUtc` in `@tradewinds/core/snapshot` currently accepts `(date, station)`. Check signature. If it accepts a tz_override arg already (TS-W1 may have ported it), thread `opts.tzOverride` through; if not, leave the kwarg unused with a TODO comment citing `_pairs.py:62-66` (Python iter-6 F1 fix). Do NOT widen the marketCloseUtc signature here — that's outside Plan 05 scope.

    3. **buildPairs** (port `_pairs.py:402-445`, Mode 1 only):
       ```typescript
       export function buildPairs(
         station: string,
         dates: ReadonlyArray<string>,
         observationsByDate: Readonly<Record<string, ReadonlyArray<PairsObservationLike>>>,
         climateByDate: Readonly<Record<string, PairsClimateLike | null>>,
         opts: BuildPairsOptions = {},
       ): ReadonlyArray<PairsRow> {
         const out: PairsRow[] = [];
         for (const date of dates) {
           const obs = observationsByDate[date] ?? [];
           const climate = climateByDate[date] ?? null;
           out.push(buildPairsRow(date, station, obs, climate, opts));
         }
         return Object.freeze(out);
       }
       ```

       **No forecastsByDate parameter.** Mode 1 only per stub PLAN Out-of-Scope. If the orchestrator (Plan 06) needs to wire a future forecast path it can add a separate function later.

    4. **pairsToRows** (TS port equivalent of `pairs_to_dataframe`):
       ```typescript
       /**
        * Surface-parity alias of buildPairs output. Python's pairs_to_dataframe
        * converts the list[dict] into a pandas DataFrame indexed by date; TS
        * has no DataFrame, so this is identity. Exists for cross-SDK signature
        * parity per CROSS-SDK-SYNC.md.
        */
       export function pairsToRows(rows: ReadonlyArray<PairsRow>): ReadonlyArray<PairsRow> {
         return rows;
       }
       ```

    5. **Internal barrel** (`packages-ts/core/src/internal/index.ts`):
       ```typescript
       export * from "./merge/index.js"; // Plan 04
       export * from "./pairs.js";
       ```

       Add a subpath export in `packages-ts/core/package.json` under `./internal/pairs` mirroring the merge subpath pattern.

    6. **Tests**:
       - 2-date input, 1 with obs, 1 empty → 2 rows; first has obs_count > 0, second has obs_count = 0.
       - Climate present on date 1, null on date 2 → cli_high_f populated then null.
       - All fcst_* always null regardless of inputs.
       - market_close_utc formatting matches `YYYY-MM-DDTHH:MM:SSZ` regex.
       - PairsRow is frozen (`Object.isFrozen(rows[0])` true).
       - Returned array is frozen.
       - `Object.keys(pairsRow)` returns the 20-field array in EXACT order matching Python's `build_pairs_row` dict construction.
       - `pairsToRows(rows) === rows` (identity check).
       - Empty dates array → frozen empty result.

       Use real `marketCloseUtc` from `@tradewinds/core/snapshot` (NOT mocked) so the test catches any regression in the TS-W1 marketCloseUtc impl.

    7. Run: `pnpm --filter @tradewinds/core test -- --run pairs && pnpm --filter @tradewinds/core build`.
  </action>
  <verify>
    <automated>pnpm --filter @tradewinds/core test -- --run pairs</automated>
  </verify>
  <done>
    All buildPairs + buildPairsRow + pairsToRows tests pass; PairsRow type is exported from `@tradewinds/core/internal/pairs`; `pnpm typecheck` clean; subpath export resolves; `pnpm -r build` produces dist artifacts under `dist/internal/pairs.*`.
  </done>
</task>

</tasks>

<verification>
- All pairs unit tests pass.
- `pnpm --filter @tradewinds/core typecheck` clean.
- `pnpm -r test --run` green (no regression in TS-W1 or Plans 01-04).
- `pnpm -r build` green; subpath export `@tradewinds/core/internal/pairs` resolves.
- `pnpm -r biome check` clean.
- PairsRow has EXACTLY 20 fields in the order Python's build_pairs_row returns.
</verification>

<success_criteria>
Maps to TS-W2 stub Wave 5: "`_pairs.buildPairs` join + `pairsToRows` (TS equivalent of `pairs_to_dataframe`)."

- buildPairs ported (Mode 1 only — fcst_* all null) and tested.
- pairsToRows = identity (TS has no DataFrame; surface-parity preserved).
- Column order matches Python exactly.
</success_criteria>

<output>
After completion, create `.planning/phases/ts-w2-parity-gate/ts-w2-05-SUMMARY.md` documenting:
- Final API at `@tradewinds/core/internal/pairs` (buildPairs, pairsToRows, PairsRow, PairsObservationLike, PairsClimateLike).
- Decision to skip forecast handling (cite Mode 1 scope per stub PLAN).
- Note for Plan 06: orchestrator MUST sort observations by `(observed_at, source)` BEFORE calling buildPairs to preserve byte-equivalent float aggregation (non-associative).
- Note for Plan 08: parity test compares 19 fields per row; market_close_utc is the 20th but format-stable.
- Whether `marketCloseUtc` accepts tz_override (from TS-W1 snapshot impl); if not, file follow-up.
</output>

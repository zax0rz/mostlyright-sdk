---
phase: ts-w2-parity-gate
plan: 06
type: execute
wave: 4
depends_on:
  - ts-w2-05
files_modified:
  - packages-ts/meta/src/research.ts
  - packages-ts/meta/src/index.ts
  - packages-ts/meta/tests/research.test.ts
  - packages-ts/meta/tests/research-integration.test.ts
autonomous: true
requirements:
  - TS-PARITY-01

must_haves:
  truths:
    - "research(station, fromDate, toDate, opts?) returns ReadonlyArray<PairsRow> covering all 4 observation sources (AWC + IEM ASOS + GHCNh) merged via mergeObservations, plus IEM CLI via mergeClimate."
    - "research() removes the W1 null-column placeholders for obs_* — those now come from the real aggregation over all 3 observation sources."
    - "Observations are sorted by (observed_at, source) BEFORE buildPairs is called — required for byte-equivalent float aggregation per Plan 05 SUMMARY."
    - "Observations are bucketed by settlementDateFor(observedAt, station) — NOT observed_at.slice(0,10) — matches Python research.py orchestrator."
    - "IEM ASOS fetched per-year over [fromDate.year, extendedTo.year] with both report_types (3=METAR, 4=SPECI), then filtered to (year, month) bucket — mirrors Python _fetch_iem_month."
    - "GHCNh fetched per-year over [fromDate.year, extendedTo.year] for US stations only (mirrors Python is_us_station() gate; intl is out-of-scope for v0.1 research)."
    - "extendedTo = toDate + 1 day so the last LST settlement window's pre-midnight UTC tail observations are included."
    - "AWC fetched once for the full window with hours = (toDate - now).inHours + 1 hour buffer, clamped to AWC_MAX_HOURS = 168."
    - "AWC NOT called if no date in range overlaps the AWC 168h window (matches Python _month_overlaps_awc_window)."
    - "Climate fetched per-year via downloadCliRange + parseCliResponse + mergeClimate over [fromYear, toYear]."
    - "PairsRow column order matches Python pairs_to_dataframe output exactly."
  artifacts:
    - path: "packages-ts/meta/src/research.ts"
      provides: "Updated research() — now AWC+IEM+GHCNh merge + buildPairs"
      exports: ["research", "type ResearchOptions"]
  key_links:
    - from: "packages-ts/meta/src/research.ts"
      to: "@tradewinds/core/internal/merge + @tradewinds/core/internal/pairs"
      via: "imports mergeObservations + mergeClimate + buildPairs"
      pattern: "@tradewinds/core/internal/(merge|pairs)"
    - from: "packages-ts/meta/src/research.ts"
      to: "@tradewinds/weather (all 4 fetchers + parsers + station map)"
      via: "imports downloadIemAsos, parseIemCsv, downloadGhcnhRange, parseGhcnhPsv, downloadCliRange, parseCliResponse, fetchAwcMetars, awcToObservation"
      pattern: "@tradewinds/weather"
---

<objective>
Update the existing W1 `research()` orchestrator in `packages-ts/meta/src/research.ts` to wire all 4 observation sources (AWC + IEM ASOS + GHCNh + IEM CLI), call `mergeObservations` + `mergeClimate` + `buildPairs`, and return the real 19-column row shape with NO null-placeholder `obs_*` fields.

**Why this matters:** Plan 08's parity test calls `research()` against 5 case windows; without this plan, `research()` still only fetches AWC + CLI and emits null `obs_*` placeholders. The parity test would fail every case immediately because Python's `obs_high_f`/`obs_low_f`/etc. are populated from the full 3-source merge, while TS would emit null.

**Scope boundaries:**
- IN: AWC + IEM ASOS + GHCNh observation merge; CLI climate merge; buildPairs join; row-shape parity.
- OUT: Cache (TS-W3), Mode 2 (TS-W4), QC (TS-W4), forecast (TS-W5+), parallel prefetch (TS-W3+ — sequential is fine for parity).

**Output:** Rewritten `research.ts`; new unit + integration tests asserting the 19-column row shape AND source-priority observable in output.
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
@.planning/phases/ts-w2-parity-gate/ts-w2-05-PLAN.md
@packages/core/src/tradewinds/research.py
@packages-ts/meta/src/research.ts
@packages-ts/meta/tests/research.test.ts
@packages-ts/weather/src/_parsers/awc.ts
@packages-ts/weather/src/index.ts

<interfaces>
Plan 01 outputs:
```typescript
export function downloadIemAsos(stationCode: string, start: string, end: string, opts: { reportType: 3 | 4; politenessMs?: number; signal?: AbortSignal }): Promise<ReadonlyArray<{ chunkStart: string; chunkEnd: string; csv: string }>>;
export function parseIemCsv(csv: string, opts?: { observationTypeOverride?: "METAR" | "SPECI" }): ReadonlyArray<Observation>;
```

Plan 02 outputs:
```typescript
export function downloadGhcnhRange(stationId: string, startYear: number, endYear: number, opts?: { politenessMs?: number; signal?: AbortSignal }): Promise<ReadonlyArray<{ stationId: string; year: number; psv: string }>>;
export function parseGhcnhPsv(psv: string): ReadonlyArray<Observation>;
```

Plan 04 outputs:
```typescript
export function mergeObservations<T extends ObservationKey>(rows: ReadonlyArray<T>): ReadonlyArray<T>;
export function mergeClimate<T extends ClimateKey>(rows: ReadonlyArray<T>): ReadonlyArray<T>;
```

Plan 05 outputs:
```typescript
export interface PairsRow { /* 20 fields */ }
export function buildPairs(station, dates, observationsByDate, climateByDate, opts?): ReadonlyArray<PairsRow>;
```

Existing W1 (`@tradewinds/weather`):
```typescript
export function fetchAwcMetars(icaos: ReadonlyArray<string>, opts?: { hours?: number; signal?: AbortSignal }): Promise<ReadonlyArray<AwcMetarRaw>>;
export function awcToObservation(raw: AwcMetarRaw): Observation | null;
export function downloadCliRange(stationIcao, fromYear, toYear, opts?): Promise<ReadonlyArray<CliRawRecord>>;
export function parseCliResponse(records, stationCode): ReadonlyArray<ClimateObservation>;
```

Existing `@tradewinds/core`:
```typescript
export function settlementDateFor(observedAt: Date, station: string): string;
export const STATION_BY_CODE: Map<string, StationInfo>;
export const STATION_BY_ICAO: Map<string, StationInfo>;
// StationInfo includes: code, icao, tz, country, ghcnh_id?
```

**IMPORTANT — ghcnh_id availability check:** the TS station table (`packages-ts/core/src/data/generated/stations.ts` via Group A codegen) MAY or MAY NOT carry `ghcnh_id`. Read the codegen output during execution. If missing, file a follow-up to extend the exporter — but ALSO add a defensive lookup: read `STATION_BY_CODE.get(code)?.ghcnh_id` and skip GHCNh fetch when empty. The Python source `_stations.py` carries ghcnh_id per station; TS codegen should too. If the codegen lacks it, Plan 06 still ships AWC + IEM, and case 5 (Hurricane Francine) will fail parity — that's a Plan 03 SUMMARY follow-up to capture; do NOT block the plan.

**isUsStation gate:** Python `is_us_station(icao)` lives in `_internal._stations.py`. TS equivalent: check `STATION_BY_CODE.get(code)?.country === "US"` (or === undefined defaulting to US). Use a helper `function isUsStation(station: StationInfo): boolean`.
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Rewrite research() to integrate all 4 sources + buildPairs</name>
  <files>packages-ts/meta/src/research.ts, packages-ts/meta/src/index.ts</files>
  <behavior>
    - `research("KNYC", "2025-01-06", "2025-01-12")` returns a `ReadonlyArray<PairsRow>` with 7 rows.
    - Each row has all 20 fields per Plan 05 PairsRow type.
    - `obs_high_f` etc. populated from real merged observations (NOT null placeholders).
    - `fcst_*` all null (Mode 1 only).
    - For windows entirely outside the AWC 168h window, AWC is NOT called.
    - For non-US stations (if any sneak through), GHCNh is NOT called.
    - Observations are sorted `(observed_at, source)` before buildPairs.
    - Observations are bucketed by `settlementDateFor(observedAt, code)` — NOT by `observedAt.slice(0,10)`.
  </behavior>
  <action>
    Rewrite `packages-ts/meta/src/research.ts`. The current file (TS-W1) covers AWC + CLI only; this plan extends to all 4 sources.

    **High-level structure** (mirror Python `research.py` orchestrator):
    1. Validate + normalize station code (existing `normalizeStation` helper — keep).
    2. Build inclusive date list (existing `buildDateList` — keep).
    3. Compute `extendedTo = formatDate(parseIsoDate(toDate) + 1 day)`.
    4. Compute the IEM ASOS year range: `[fromDate.year, extendedTo.year]`.
    5. Compute the climate year range: `[fromDate.year, toDate.year]`.
    6. **Fetch + parse AWC**: only if any date in `[fromDate, extendedTo]` overlaps the 168h window. Use `monthOverlapsAwcWindow(year, month)` helper. If overlap, fetch with `hours = Math.min(168, hoursSince(fromDate))`. Convert via `awcToObservation`. Each row's `source = "awc"`.
    7. **Fetch + parse IEM ASOS**: for each year in range, for each reportType in {3, 4}:
       - `downloadIemAsos(code, year-01-01, year-12-31, { reportType })` → returns N CSV bodies.
       - For each CSV body, `parseIemCsv(body, { observationTypeOverride: reportType === 3 ? "METAR" : "SPECI" })`.
       - Filter parsed rows to `[fromDate, extendedTo]` window (string compare on `observed_at[0:10]` against the bounds).
       - Each row's `source = "iem"`.
    8. **Fetch + parse GHCNh** (skip if `!isUsStation(stationInfo)` OR if `ghcnh_id` is empty):
       - For each year in range:
         - `downloadGhcnhRange(ghcnhId, year, year)` (single-year call to inherit the 404-skip behavior; alternatively `downloadGhcnh` + try/catch NotFoundError).
         - For each result, `parseGhcnhPsv(body)`.
         - Filter parsed rows to the window (same `observed_at[0:10]` slice).
         - Each row's `source = "ghcnh"`.
    9. **Merge observations**: combine `awcRows + iemRows + ghcnhRows` into one array. **Sort by `(observed_at, source)`** (alphabetic on source = `awc < ghcnh < iem` — which differs from Python's source priority but the sort is for byte-stable mean aggregation, not priority resolution; priority is handled by mergeObservations). Then call `mergeObservations(combined)`.
    10. **Fetch + parse + merge climate** (mostly unchanged from W1):
        - `downloadCliRange(icao, fromYear, toYear)`.
        - `parseCliResponse(records, code)`.
        - `mergeClimate(parsed)` (now from `@tradewinds/core/internal/merge`).
    11. **Bucket observations by settlement date** (replace the W1 `observedSettlementDate` helper — port the Python `settlement_date_for` semantics):
        - For each merged observation:
          - `const observedAtDate = new Date(obs.observed_at)`.
          - `const settleDate = settlementDateFor(observedAtDate, code)`.
          - Push into `observationsByDate[settleDate]`.
        - Skip rows where settleDate is outside `dates`.
    12. **Bucket climate by date** (single dict, last-write-wins; mergeClimate already dedupped):
        - For each merged climate row: `climateByDate[row.observation_date] = row` (mapping to PairsClimateLike shape).
    13. **Call buildPairs**:
        - `const rows = buildPairs(code, dates, observationsByDate, climateByDate, {/* tzOverride if Plan 05 wires it */});`
        - Return `rows`.

    **Critical details:**
    - REMOVE the W1 `ResearchRow` interface declared in `meta/src/research.ts`. Use the canonical `PairsRow` from `@tradewinds/core/internal/pairs`. Update `packages-ts/meta/src/index.ts` exports accordingly. Existing consumers should switch to `PairsRow`.
    - REMOVE the W1 `obs_*` aggregation helpers (`average`, `maxOf`, `minOf`, `sumOf`, `nonNullField`) — those are subsumed by `_obsAggregates` inside `buildPairs`. Delete dead code.
    - The signature stays `async function research(station, fromDate, toDate, opts?: ResearchOptions): Promise<ReadonlyArray<PairsRow>>`.
    - **ResearchOptions**: extend the existing interface to support `iemPolitenessMs?: number`, `ghcnhPolitenessMs?: number`, `awcHours?: number` (already there). Pass-through to fetchers; default values match TS-W1 (1000ms / 1000ms / 168).
    - **AWC-window overlap helper**: TS port of Python `_month_overlaps_awc_window`. Simple version: `function anyDateOverlapsAwc(dates: ReadonlyArray<string>, hours: number, now: Date): boolean` — check if max(dates) is within `hours` of now.

    **Update `packages-ts/meta/src/index.ts`**: re-export `PairsRow` from `@tradewinds/core/internal/pairs` so consumers can `import { research, type PairsRow } from "tradewinds"` (the meta package).
  </action>
  <verify>
    <automated>pnpm --filter tradewinds typecheck</automated>
  </verify>
  <done>
    `research.ts` compiles cleanly with all 4 sources wired; `PairsRow` exported from meta; W1 ResearchRow type is removed; AWC-window short-circuit preserved.
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Test research() against synthetic msw recordings — source-priority + row-shape</name>
  <files>packages-ts/meta/tests/research.test.ts, packages-ts/meta/tests/research-integration.test.ts</files>
  <behavior>
    - `research("KNYC", "2025-01-06", "2025-01-08", opts)` with msw returning small synthetic AWC + IEM CSV + GHCNh PSV + CLI JSON bodies produces 3 PairsRow objects.
    - Each row has the 20 fields in correct order.
    - Source-priority observable: when AWC and IEM rows exist for the same observed_at + observation_type, the surviving row (via mergeObservations inside research) produces obs aggregates consistent with the AWC row's measurements (not IEM's).
    - When AWC has a gap and IEM fills it, the IEM measurements DO appear in the aggregate.
    - When AWC and IEM both gap and GHCNh has data, the GHCNh measurements appear.
    - Date windows entirely older than 168h → AWC fetcher is NOT called (msw assertion: 0 awc requests).
    - GHCNh fetch is skipped (NOT called) for an international ICAO (e.g. EGLL) — msw assertion: 0 ghcnh requests.
  </behavior>
  <action>
    1. **Restructure existing W1 test file** `packages-ts/meta/tests/research.test.ts`:
       - Keep coverage of station normalization, date validation, fromDate > toDate rejection.
       - REMOVE assertions on the W1-specific ResearchRow shape (replaced by PairsRow).
       - Add a column-count assertion: `Object.keys(rows[0]).length === 20`.
       - Add a column-order assertion: `Object.keys(rows[0])` matches the exact field list (date, station, cli_high_f, ..., market_close_utc).
       - Add a "fcst_* all null" assertion.

    2. **Create new integration test** `packages-ts/meta/tests/research-integration.test.ts` using msw 2.x:
       - `setupServer(...handlers)` with handlers for:
         - `https://aviationweather.gov/api/data/metar` → returns small synthetic AWC JSON (3 METARs).
         - `https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py` (matches any year/report_type combo) → returns small synthetic IEM CSV.
         - `https://www.ncei.noaa.gov/oa/global-historical-climatology-network/hourly/access/by-year/*/psv/GHCNh_*.psv` → returns small synthetic PSV.
         - `https://mesonet.agron.iastate.edu/json/cli.py` → returns small synthetic CLI JSON.

       Tests:
       a) **Row count + column order**: `research("KNYC", "2025-01-06", "2025-01-08")` returns 3 rows; column keys match canonical order.
       b) **AWC-only window short-circuit**: `research("KNYC", "2020-01-01", "2020-01-03")` (3+ years stale) → msw event tracker shows zero AWC requests (assert via `server.events.on("request:start", ...)` listener).
       c) **GHCNh skipped for international**: if STATION_BY_ICAO includes any non-US entry, call research with that ICAO and assert zero GHCNh requests. If TS station table only has US stations as of TS-W0, skip this test with a `.todo()` and a comment pointing at INTL station codegen in TS-W6.
       d) **Source-priority observable**: hand-craft synthetic AWC and IEM rows for the same (station, observed_at, observation_type) but with different temp_f values. After research(), the surviving aggregate should match the AWC temp.

       Use small (<10 rows each) synthetic bodies. Set polite-delay options to 0 in opts so tests run in <1s each.

    3. Run `pnpm --filter tradewinds test -- --run` and verify all tests green.
  </action>
  <verify>
    <automated>pnpm --filter tradewinds test -- --run</automated>
  </verify>
  <done>
    `research()` produces row-shape-correct PairsRow output across all integration scenarios; AWC short-circuit verified; source-priority observable through aggregates; column order + count assertions pass.
  </done>
</task>

</tasks>

<verification>
- All meta-package tests pass.
- `pnpm -r typecheck` clean.
- `pnpm -r test --run` green across all 5 packages (no regression from Plans 01-05).
- `pnpm -r build` green.
- `pnpm -r biome check` clean.
- Bundle size for meta (`@tradewinds/meta`): check via `pnpm --filter tradewinds build` + size-limit if configured. Plan 06 SHOULD increase the meta bundle size meaningfully (adds parsers + merge + pairs); flag in SUMMARY if it breaches a configured gate.
- `research()` is the new W2 surface; W1 ResearchRow type is removed.
</verification>

<success_criteria>
Maps to TS-W2 stub Wave 6: "Update `research()` to include all 4 sources; remove W1's null-column placeholders."

- All 4 sources wired (AWC + IEM ASOS + GHCNh + IEM CLI).
- Mode 1 row shape matches PairsRow (20 fields with fcst_* null).
- Real obs aggregates (no null placeholders for obs_high_f, obs_low_f, etc. unless the source data truly lacks values for a date).
</success_criteria>

<output>
After completion, create `.planning/phases/ts-w2-parity-gate/ts-w2-06-SUMMARY.md` documenting:
- Updated `research()` signature.
- Sequential fetch order (AWC, IEM, GHCNh, CLI) — no parallel prefetch (deferred to TS-W3).
- ghcnh_id codegen status: present in TS station table? If not, follow-up filed.
- Bundle-size impact for `@tradewinds/meta`.
- Any divergences from Python research.py noted (e.g. no QC opt-in, no qc=True kwarg).
- Confirmation that `obs_*` columns now produce real values (no W1 nulls).
</output>

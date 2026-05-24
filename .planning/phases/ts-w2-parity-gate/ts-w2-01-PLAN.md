---
phase: ts-w2-parity-gate
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - packages-ts/weather/src/_fetchers/_iem_chunks.ts
  - packages-ts/weather/src/_fetchers/iem-asos.ts
  - packages-ts/weather/src/_parsers/iem.ts
  - packages-ts/weather/src/index.ts
  - packages-ts/weather/tests/iem-chunks.test.ts
  - packages-ts/weather/tests/iem-asos.test.ts
  - packages-ts/weather/tests/iem.test.ts
autonomous: true
requirements:
  - TS-WEATHER-03
  - TS-PARSER-01
  - TS-PARSER-02

must_haves:
  truths:
    - "yearlyChunksExclusiveEnd(start, end) splits a date range into per-calendar-year tuples where the second element is date(year+1, 1, 1) — IEM day2 exclusive."
    - "downloadIemAsos normalizes the caller's start to date(start.year, 1, 1) so per-month callers share a yearly cache key."
    - "downloadIemAsos returns a list of in-memory CSV bodies (TS port has no disk cache in TS-W2; cache lands in TS-W3) — one entry per yearly chunk, in chunker-natural order."
    - "downloadIemAsos rejects report_type values outside {3, 4} and reversed ranges (start > end) returns [] without firing any HTTP request."
    - "iemToObservation skips comment lines starting with `#`, parses `M`/empty as null, parses `T` (precip trace) as 0.0, detects METAR vs SPECI from raw text when no override is set."
    - "parseIemCsv returns an array of Observation rows whose shape matches the Python `iem_to_observation` dict 1:1 (all 30 fields, including raw_metar passthrough)."
    - "Polite 1000ms delay fires AFTER each successful network round-trip (not before; not on rejected chunks)."
  artifacts:
    - path: "packages-ts/weather/src/_fetchers/_iem_chunks.ts"
      provides: "yearlyChunksExclusiveEnd (PR #85 cf9eb85 port; leap-year safe via date(year+1, 1, 1))"
      exports: ["yearlyChunksExclusiveEnd"]
    - path: "packages-ts/weather/src/_fetchers/iem-asos.ts"
      provides: "downloadIemAsos — yearly-chunked CSV body fetcher with 1s polite delay"
      exports: ["downloadIemAsos", "buildIemUrl", "IEM_BASE_URL", "IEM_POLITE_DELAY_MS"]
    - path: "packages-ts/weather/src/_parsers/iem.ts"
      provides: "iemToObservation + parseIemCsv (CSV body in-memory parsing; # comment strip; M/T sentinels)"
      exports: ["iemToObservation", "parseIemCsv"]
  key_links:
    - from: "packages-ts/weather/src/_fetchers/iem-asos.ts"
      to: "packages-ts/weather/src/_fetchers/_iem_chunks.ts"
      via: "yearlyChunksExclusiveEnd(date(start.year, 1, 1), end)"
      pattern: "yearlyChunksExclusiveEnd"
    - from: "packages-ts/weather/src/_parsers/iem.ts"
      to: "@tradewinds/core/internal/bounds + @tradewinds/core/internal/convert"
      via: "subpath imports (TS-W1 iter-1 HIGH 4 pattern)"
      pattern: "@tradewinds/core/internal/(bounds|convert)"
    - from: "packages-ts/weather/src/index.ts"
      to: "iem-asos.ts + iem.ts + _iem_chunks.ts"
      via: "barrel re-exports"
      pattern: "export.*iem"
---

<objective>
Port the Python IEM ASOS yearly-chunk fetcher (`packages/weather/src/tradewinds/weather/_fetchers/iem_asos.py` + `_iem_chunks.py`) and the IEM CSV parser (`packages/weather/src/tradewinds/weather/_iem.py::iem_to_observation`) to TypeScript. These three modules together produce the multi-source observation row stream that mergeObservations (Plan 04) will dedup.

**Why this matters:** IEM ASOS is the lift-source-of-truth for historical METAR aggregates. Without it, the TS parity gate cannot replay v0.14.1's `pairs()` output — AWC only covers the last 168h, so every fixture older than a week needs IEM rows. The chunker semantics (`day2` exclusive → Jan 1 of next year) AND the parser semantics (`#`-prefix comment strip, `M`/`T` sentinels, multi-column sky/precip expansion) are both load-bearing for byte-equivalence.

**Output:** Three TS modules under `packages-ts/weather/src/`, one barrel update, and full unit-test coverage (vitest + msw for the fetcher; pure-function tests for the chunker and parser).
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@.planning/REVIEW-DISCIPLINE.md
@.planning/research/TS-SDK-DESIGN.md
@.planning/research/PYTHON-SURFACE-INVENTORY.md
@.planning/phases/ts-w2-parity-gate/PLAN.md
@packages/weather/src/tradewinds/weather/_fetchers/iem_asos.py
@packages/weather/src/tradewinds/weather/_fetchers/_iem_chunks.py
@packages/weather/src/tradewinds/weather/_iem.py
@packages-ts/core/src/internal/bounds.ts
@packages-ts/core/src/internal/convert.ts
@packages-ts/core/src/internal/http.ts
@packages-ts/weather/src/_fetchers/iem-cli.ts
@packages-ts/weather/src/_parsers/awc.ts
@packages-ts/weather/tests/iem-cli.test.ts

<interfaces>
<!-- Existing TS-side contracts the executor reuses. -->

From `@tradewinds/core/internal/http`:
```typescript
export interface FetchWithRetryOptions {
  signal?: AbortSignal;
  retries?: number;
  baseDelayMs?: number;
  timeoutMs?: number;
}
export function fetchWithRetry(url: string, opts?: FetchWithRetryOptions): Promise<Response>;
```

From `@tradewinds/core/internal/bounds` (consumed by parser):
```typescript
export const STATION_CODE_RE: RegExp;
export const TEMP_MIN_C: number;
export const TEMP_MAX_C: number;
export const WIND_DIR_BOUNDS: readonly [number, number];
export const WIND_SPEED_MAX: number;
export const WIND_GUST_MAX: number;
export const SLP_MIN_MB: number;
export const SLP_MAX_MB: number;
export const SKY_BASE_MAX_FT: number;
export const MAX_VISIBILITY_MILES: number;
export const MAX_WX_CODES_LEN: number;
export const MAX_RAW_METAR_LEN: number;
export const MIN_YEAR: number;
export const MAX_YEAR: number;
export function boundedFloat(v: number | null, lo: number, hi: number, opts?: { field?: string }): number | null;
export function boundedFloatMin(v: number | null, lo: number): number | null;
export function boundedInt(v: number | null, lo: number, hi: number): number | null;
```

From `@tradewinds/core/internal/convert`:
```typescript
export function fahrenheitToCelsius(f: number | null): number | null;
```

From `packages-ts/weather/src/_parsers/awc.ts` (reuse the Observation type AND the icaoToStationCode + mapCloudCover helpers):
```typescript
export interface Observation { /* 30 fields — see file */ }
export function icaoToStationCode(icao: string): string;
export function mapCloudCover(code: string): string | null;
```
**Important:** the `Observation.source` literal currently types as `"awc"` — Plan 01 must widen the type to `"awc" | "iem" | "ghcnh"` in this plan (a single small edit to `awc.ts` Observation interface; the AWC parser still emits `"awc"`, but the type contract becomes shared). DO NOT create a parallel Observation type.
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Port yearlyChunksExclusiveEnd + write iem-chunks.test.ts</name>
  <files>packages-ts/weather/src/_fetchers/_iem_chunks.ts, packages-ts/weather/tests/iem-chunks.test.ts</files>
  <behavior>
    - `yearlyChunksExclusiveEnd(date('2024-03-15'), date('2024-08-20'))` → `[(2024-03-15, 2025-01-01)]`
    - `yearlyChunksExclusiveEnd(date('2023-11-01'), date('2025-02-15'))` → `[(2023-11-01, 2024-01-01), (2024-01-01, 2025-01-01), (2025-01-01, 2026-01-01)]`
    - `yearlyChunksExclusiveEnd(date('2024-02-29'), date('2024-03-01'))` → `[(2024-02-29, 2025-01-01)]` (leap year safe — no off-by-one)
    - `yearlyChunksExclusiveEnd(date('2025-01-01'), date('2024-12-31'))` → `[]` (reversed range)
    - chunk_start uses `max(date(start.year, 1, 1), start)` — for mid-year start the first chunk starts at the caller's date, NOT Jan 1
  </behavior>
  <action>
    Port the Python helper at `packages/weather/src/tradewinds/weather/_fetchers/_iem_chunks.py::yearly_chunks_exclusive_end` byte-faithfully.

    Implementation rules:
    1. Use a `LocalDate` representation (NOT `Date`) — avoid timezone drift. Recommended: a `{year: number, month: number, day: number}` interface OR an ISO string `YYYY-MM-DD`. Choose ISO strings for simplicity — they sort lexicographically and round-trip cleanly. Define `type IsoDate = string` with a runtime guard.
    2. The advance step MUST be `date(currentYear + 1, 1, 1)` — NEVER `+365` days (drops Feb 29 in leap years; PR #85's primary anti-pattern).
    3. Reversed range (`start > end` lexicographic compare on ISO) returns `[]`. Do not throw.
    4. Export `yearlyChunksExclusiveEnd(start: IsoDate, end: IsoDate): ReadonlyArray<readonly [IsoDate, IsoDate]>`. Use `readonly` tuple/array to flag immutable returns (per REVIEW-DISCIPLINE TS Architect rubric §5).
    5. Match Python's chunk_start clamping: `max(currentYearStart, start)` — important for first chunk only; subsequent chunks always start at Jan 1.

    DO NOT port `yearly_chunks_inclusive` — the IEM ASOS path uses exclusive-end only, per stub PLAN Wave 1 spec.

    DO NOT use the JS `Date` constructor for arithmetic — it silently shifts to local TZ. Operate on year/month/day integers; emit ISO strings via `${y}-${m.padStart(2,'0')}-${d.padStart(2,'0')}`.

    Write the test alongside: cover all 5 behaviors above plus:
    - Same-year mid-range (`2024-06-01` → `2024-09-30`): single chunk `(2024-06-01, 2025-01-01)`.
    - Year boundary span where start IS Jan 1: chunk_start equals input.
    - Three-year span: verify chunk count is 3 AND all intermediate chunk_starts are Jan 1.

    Use vitest `describe` / `it` / `expect` (see `packages-ts/weather/tests/iem-cli.test.ts` for project conventions).
  </action>
  <verify>
    <automated>pnpm --filter @tradewinds/weather test -- --run iem-chunks</automated>
  </verify>
  <done>
    `_iem_chunks.ts` exports `yearlyChunksExclusiveEnd` matching all 5 behavioral assertions; vitest run is green; `pnpm typecheck` clean.
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Port downloadIemAsos with msw recording test</name>
  <files>packages-ts/weather/src/_fetchers/iem-asos.ts, packages-ts/weather/tests/iem-asos.test.ts</files>
  <behavior>
    - `downloadIemAsos(stationCode, start, end, {reportType: 3})` issues one HTTP request per yearly chunk (verified by msw call count).
    - URL shape matches Python `_build_iem_url`: `https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py?station={code}&data=all&tz=Etc/UTC&format=comma&latlon=no&elev=no&missing=M&trace=T&direct=no&report_type={3|4}&year1=...&month1=...&day1=...&year2=...&month2=...&day2=...`
    - Caller's `start` is normalized to `date(start.year, 1, 1)` internally → 2024-06-15 caller → URL day1=2024-01-01 (and `day2=2025-01-01` per chunker).
    - Returns `ReadonlyArray<{ chunkStart: IsoDate; chunkEnd: IsoDate; csv: string }>` — one entry per chunk, order = chunker-natural.
    - `reportType` outside `{3, 4}` throws `Error` with message including the bad value.
    - Reversed range (`start > end`) returns `[]` with ZERO HTTP requests.
    - Polite delay (`IEM_POLITE_DELAY_MS = 1000`) fires AFTER each successful response — test with a `delayMs` injection option set to 0 for fast unit tests; verify the default constant export equals `1000`.
    - 4xx/5xx propagates the error from `fetchWithRetry`; do NOT swallow.
  </behavior>
  <action>
    Port `packages/weather/src/tradewinds/weather/_fetchers/iem_asos.py::download_iem_asos`. Key adaptations:

    1. **NO disk cache in TS-W2.** Python writes CSVs to `dest_dir/{station}/iem_*.csv`; TS returns the CSV body in-memory as `{ chunkStart, chunkEnd, csv: string }`. The TS disk cache lands in TS-W3 (out of scope). Drop ALL filename / cache-skip / partial-namespace logic. Drop `dest_dir`, `skip_cache`, `today_utc` checks.

    2. **Validate station code** at boundary: regex `^[A-Z]{3,4}$` (mirror the `validateIcao` pattern from `iem-cli.ts`). Reject mismatch with a thrown Error citing path-traversal defense. Do NOT use `validateIcaoForPath` from Python — there's no path here.

    3. **Validate report_type**: only `3` (METAR) or `4` (SPECI). Throw on other values.

    4. **Reversed-range guard**: if `start > end` (ISO string compare), return `[]` immediately. Mirror Python L201-202.

    5. **Normalize start**: set `normalizedStart = '${start.slice(0,4)}-01-01'`. Pass to `yearlyChunksExclusiveEnd(normalizedStart, end)`.

    6. **Per-chunk loop**:
       - Build URL via `buildIemUrl(stationCode, chunkStart, chunkEnd, reportType)`.
       - `await fetchWithRetry(url, { signal: opts.signal })`.
       - Read body as text: `await response.text()`.
       - Push `{ chunkStart, chunkEnd, csv }` to output.
       - `await sleep(opts.politenessMs ?? IEM_POLITE_DELAY_MS)` AFTER push (skip on last iteration is OK but not required; mirror Python which sleeps always).

    7. Exports: `downloadIemAsos`, `buildIemUrl`, `IEM_BASE_URL`, `IEM_POLITE_DELAY_MS`. Match `iem-cli.ts` export style.

    8. **Test setup (msw)**:
       - Use `msw/node` `setupServer` (vitest already pulls msw 2.x via the project's deps).
       - Register handler for `IEM_BASE_URL` returning a small synthetic CSV body for each (year1, year2) pair.
       - Assert: call count = chunk count; each URL has correct year1/year2/day1/day2 + station + report_type params; returned array length = chunk count; csv strings match the handler's response.
       - Separate test: reversed range → 0 HTTP calls (server.events tracking).
       - Separate test: invalid report_type throws synchronously (no HTTP).
       - Separate test: polite delay default = `1000`.

    Use `politenessMs: 0` in all tests so they complete in <1s.

    Reference `packages-ts/weather/tests/iem-cli.test.ts` for the msw setup pattern.
  </action>
  <verify>
    <automated>pnpm --filter @tradewinds/weather test -- --run iem-asos</automated>
  </verify>
  <done>
    All msw-backed tests pass; URL shape byte-faithful to Python; reversed range short-circuits; the start-normalization-to-Jan-1 invariant is observable in the captured request URLs; `pnpm typecheck` clean.
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 3: Port iemToObservation + parseIemCsv with fixture-replay tests</name>
  <files>packages-ts/weather/src/_parsers/iem.ts, packages-ts/weather/tests/iem.test.ts, packages-ts/weather/src/index.ts</files>
  <behavior>
    - `parseIemCsv(csvBody, override?)` parses a string CSV body (NOT a file path — the fetcher returns bodies).
    - Comment lines starting with `#` are stripped BEFORE the `csv.DictReader` (or its TS equivalent) sees the header.
    - `M` and `""` (empty) parse as `null` for numeric fields.
    - `T` parses as `0.0` for `p01i` (precipitation only — other fields treat `T` as null).
    - Timestamp `YYYY-MM-DD HH:MM` converts to ISO 8601 `YYYY-MM-DDTHH:MM:00Z`.
    - Out-of-bounds values null out (e.g. temp_f → temp_c outside [-100, 60] → null for BOTH temp_c and temp_f, consistency rule from Python L170-171).
    - If `observationTypeOverride === "METAR"|"SPECI"` is set, every row gets that type (no raw-text inspection). If unset, detect SPECI from leading `SPECI ` word; default to `METAR`.
    - Row skipped (returns null from `iemToObservation`) when station_code invalid OR timestamp unparseable OR all 4 key vars (raw temp_f, raw dewp_f, wind_speed, slp) are null.
    - Sky cover/base columns 1-4 expand to 8 fields; missing columns null out.
    - Output object has EXACTLY 30 fields matching the Python `iem_to_observation` return dict; `source: "iem"`.
  </behavior>
  <action>
    Port `packages/weather/src/tradewinds/weather/_iem.py::iem_to_observation` + `parse_iem_file` byte-faithfully. TS adaptations:

    1. **Input is a string (CSV body), not a file path.** Drop `Path` / file I/O. Signature: `parseIemCsv(csvBody: string, opts?: { observationTypeOverride?: "METAR" | "SPECI" }): ReadonlyArray<Observation>`.

    2. **CSV parser:** use a minimal hand-rolled CSV reader OR add a tiny dep. The project does NOT have a csv lib installed. RECOMMENDATION: hand-roll. IEM emits comma-separated, NO embedded commas in fields per the Python parser's experience (it uses `csv.DictReader` without quoting tricks). Implement a simple line-split + comma-split + header-map. Strip `\r` from line ends. Skip lines starting with `#` BEFORE splitting (mirror Python's `filtered = (line for line in f if not line.startswith("#"))`).

       Alternative: use `papaparse` (already a likely-existing dep — verify with `pnpm ls`). If not present, DO NOT add it; hand-roll. Keep the bundle-size gate from REVIEW-DISCIPLINE TS Architect rubric §2 in mind — IEM CSV parsing is hot path and must not balloon the bundle.

    3. **Helpers — port verbatim:** `safeFloat` (val: string → number|null; M/empty/non-finite → null), `safeInt` (via safeFloat + Math.round), `parsePrecip` (T→0, M→null, numeric passthrough), `parseTimestamp` (regex + Date.UTC roundtrip — mirror the `cli.ts::parseProductTimestamp` pattern for calendar-validity rejection), `parsePeakWindTime` (`YYYY-MM-DD HH:MM` → `HHMM`), `detectObsType` (raw text → "METAR"|"SPECI").

    4. **Observation type override validation:** if `observationTypeOverride` is set AND not in `{METAR, SPECI}`, throw an Error (mirror Python L152-156).

    5. **Reuse from `awc.ts`:** `icaoToStationCode`, `mapCloudCover`, `Observation` interface. **IMPORTANT:** widen `Observation.source` from `"awc"` to `"awc" | "iem" | "ghcnh"` in `awc.ts` — single edit, AWC parser still literally emits `"awc"`. This is the shared row contract for mergeObservations (Plan 04). Do NOT duplicate the Observation type.

    6. **Bounds + conversions:** import from `@tradewinds/core/internal/bounds` and `@tradewinds/core/internal/convert` (same pattern as `awc.ts` — subpath imports).

    7. **Output dict order:** match Python's return-dict key order exactly (station_code, observed_at, observation_type, source, temp_c, dewpoint_c, temp_f, dewpoint_f, wind_dir_degrees, wind_speed_kt, wind_gust_kt, altimeter_inhg, sea_level_pressure_mb, sky_cover_1, sky_base_1_ft, sky_cover_2, sky_base_2_ft, sky_cover_3, sky_base_3_ft, sky_cover_4, sky_base_4_ft, visibility_miles, weather_codes, precip_1hr_inches, peak_wind_gust_kt, peak_wind_dir, peak_wind_time, snow_depth_inches, qc_field, raw_metar). 30 fields. `JSON.stringify` ordering matters for downstream diff debugging.

    8. **Tests:**
       - Comment line stripping: feed a header preceded by 3 `#` lines → parser still reads header correctly.
       - `M` sentinel → null for tmpf, dwpf, drct, sknt.
       - `T` sentinel: `p01i="T"` → `precip_1hr_inches: 0`, `tmpf="T"` → temp_c: null (T only valid for precip).
       - Timestamp roundtrip: `valid="2025-01-01 00:51"` → `observed_at: "2025-01-01T00:51:00Z"`.
       - SPECI detection: row with metar=`SPECI KJFK ...` → observation_type: "SPECI" when override unset.
       - Override: same row with override="METAR" → observation_type: "METAR" regardless of raw text.
       - Skip-row: all 4 key vars empty → returns null from `iemToObservation`; not present in `parseIemCsv` output.
       - Out-of-bounds consistency: tmpf=2000 → both temp_c AND temp_f null.
       - Bad observation_type_override (e.g. "foo") throws.
       - Use 2-3 small synthetic CSV strings (5-10 rows each) embedded in the test file. NO file I/O.

    9. **Update barrel `packages-ts/weather/src/index.ts`**: re-export `iemToObservation`, `parseIemCsv`, `downloadIemAsos`, `buildIemUrl`, `IEM_BASE_URL`, `IEM_POLITE_DELAY_MS`, `yearlyChunksExclusiveEnd`. Also re-export the widened `Observation` type (it already comes through from `_parsers/awc.js` — keep the existing export line but rename the section comment from "TS-W1 Wave 3" to indicate IEM ASOS lands in TS-W2 Plan 01).
  </action>
  <verify>
    <automated>pnpm --filter @tradewinds/weather test -- --run iem.test</automated>
  </verify>
  <done>
    All parser tests pass; barrel exports updated and consumed by typecheck (`pnpm --filter @tradewinds/weather typecheck`); the `Observation` type has been widened to `"awc" | "iem" | "ghcnh"` and AWC test suite still green (regression check); `pnpm -r test --run` green for weather package.
  </done>
</task>

</tasks>

<verification>
- All three tasks pass their dedicated vitest runs.
- `pnpm --filter @tradewinds/weather typecheck` clean (strict mode + noUncheckedIndexedAccess).
- `pnpm --filter @tradewinds/weather test -- --run` (full weather suite) is green — TS-W1 AWC + CLI tests unaffected.
- `pnpm -r biome check` clean.
- No new external runtime deps added (bundle-size gate per REVIEW-DISCIPLINE §2).
- The `Observation.source` widening is the only edit to `awc.ts`; no other AWC logic changed.
</verification>

<success_criteria>
Maps to TS-W2 stub SC#2: "IEM ASOS fetcher uses yearly chunks (calendar-aligned, leap-year safe — port of `_iem_chunks.yearly_chunks_exclusive_end`, NOT `yearly_chunks_inclusive`; IEM's `day2` is EXCLUSIVE, so chunks end on Jan 1 of the following year) at 1 req/sec politeness; CSV parser handles `#`-prefix comments + `M`/`T` sentinels + multi-column expansion identical to `_iem.iem_to_observation`."

- Yearly chunks proven via Task 1 unit tests.
- IEM URL shape + start normalization proven via Task 2 msw assertions.
- CSV parser semantics proven via Task 3 synthetic-fixture tests.
</success_criteria>

<output>
After completion, create `.planning/phases/ts-w2-parity-gate/ts-w2-01-SUMMARY.md` documenting:
- Final TS API surface for the 3 new modules (signatures + exported constants).
- Any deviations from byte-faithful Python port (with rationale — e.g. in-memory CSV bodies instead of files because TS-W3 hasn't shipped the cache layer yet).
- Test count delta vs the TS-W1 271-test baseline.
- Bundle-size impact (`pnpm --filter @tradewinds/weather build` + size-limit output if available).
- Notes for Plan 04 (merge) on the widened `Observation.source` type.
</output>

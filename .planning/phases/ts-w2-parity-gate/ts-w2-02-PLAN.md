---
phase: ts-w2-parity-gate
plan: 02
type: execute
wave: 1
depends_on: []
files_modified:
  - packages-ts/weather/src/_fetchers/ghcnh.ts
  - packages-ts/weather/src/_parsers/ghcnh.ts
  - packages-ts/weather/src/_parsers/_station_translator.ts
  - packages-ts/weather/src/index.ts
  - packages-ts/weather/tests/ghcnh-fetcher.test.ts
  - packages-ts/weather/tests/ghcnh-parser.test.ts
  - packages-ts/weather/tests/station-translator.test.ts
autonomous: true
requirements:
  - TS-WEATHER-04
  - TS-PARSER-03
  - TS-PARSER-04

must_haves:
  truths:
    - "downloadGhcnh(stationId, year) fetches a single PSV body for one station-year, returning the body as text."
    - "downloadGhcnhRange(stationId, startYear, endYear) iterates inclusive years; HTTP 404 → silent skip (no throw); other HTTP errors propagate."
    - "GHCNh URL pattern matches Python verbatim: `https://www.ncei.noaa.gov/oa/global-historical-climatology-network/hourly/access/by-year/<YEAR>/psv/GHCNh_<station_id>_<YEAR>.psv`."
    - "parseGhcnhPsv handles `|` (pipe) delimiter (NOT comma)."
    - "Quality_Code filter accepts `{0, 1, 4, 5}` AND empty string; rejects `{2, 3, 6, 7, I, P, R, U}`."
    - "Station-id translator converts `ICAO-KJFK` → station_code `JFK` (via `icaoToStationCode`); WMO-formatted IDs like `744860-94789` return null (cannot extract)."
    - "Output observation rows have `source: 'ghcnh'` and the same 30-field schema as IEM/AWC parsers."
    - "Non-US stations: GHCNh PSV is US-only — fetcher does not special-case; caller (research orchestrator in Plan 06) gates by `isUsStation()`."
    - "Polite 1000ms delay fires AFTER each successful HTTP response in the range path."
  artifacts:
    - path: "packages-ts/weather/src/_fetchers/ghcnh.ts"
      provides: "downloadGhcnh + downloadGhcnhRange (PSV body fetcher; 404-skip in range)"
      exports: ["downloadGhcnh", "downloadGhcnhRange", "GHCNH_BASE_URL", "NCEI_POLITE_DELAY_MS"]
    - path: "packages-ts/weather/src/_parsers/ghcnh.ts"
      provides: "parseGhcnhPsv + parseGhcnhRow with Quality_Code filtering + station-code extraction"
      exports: ["parseGhcnhPsv", "parseGhcnhRow", "ghcnhStationToCode"]
    - path: "packages-ts/weather/src/_parsers/_station_translator.ts"
      provides: "Source_Station_ID column scan + ICAO→station_code resolution"
      exports: ["extractStationCode", "SSID_COLUMNS"]
  key_links:
    - from: "packages-ts/weather/src/_fetchers/ghcnh.ts"
      to: "@tradewinds/core (fetchWithRetry + NotFoundError)"
      via: "import for HTTP + 404 detection"
      pattern: "fetchWithRetry|NotFoundError"
    - from: "packages-ts/weather/src/_parsers/ghcnh.ts"
      to: "_station_translator.ts + @tradewinds/core/internal/{bounds,convert}"
      via: "subpath imports for unit conversions + bounds + station resolution"
      pattern: "@tradewinds/core/internal/(bounds|convert)|_station_translator"
    - from: "packages-ts/weather/src/_parsers/ghcnh.ts"
      to: "packages-ts/weather/src/_parsers/iem.ts (Observation type via awc.ts barrel)"
      via: "shared Observation interface (widened in Plan 01)"
      pattern: "import.*Observation"
---

<objective>
Port the NCEI GHCNh PSV fetcher (`packages/weather/src/tradewinds/weather/_fetchers/ghcnh.py`) and the PSV parser (`packages/weather/src/tradewinds/weather/_ghcnh.py`) to TypeScript. GHCNh is the third observation source feeding `mergeObservations` (Plan 04) and provides the fallback when AWC and IEM both have gaps (e.g. cases 4-5 of the parity gate).

**Why this matters:** Without GHCNh rows feeding mergeObservations, the parity fixtures for case 5 (KMSY Hurricane Francine AWC gap) cannot reproduce v0.14.1's output — GHCNh is the priority-1 fallback when both AWC (priority 3) and IEM (priority 2) miss an observation slot.

**Output:** Three TS modules (fetcher, parser, station translator), barrel update, full unit-test coverage with msw + synthetic PSV fixtures.

**Independence note:** This plan runs PARALLEL to Plan 01 (different files, no shared module edits). Same Wave 1.
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
@packages/weather/src/tradewinds/weather/_fetchers/ghcnh.py
@packages/weather/src/tradewinds/weather/_ghcnh.py
@packages-ts/core/src/internal/http.ts
@packages-ts/core/src/exceptions/index.ts
@packages-ts/weather/src/_parsers/awc.ts
@packages-ts/weather/src/_fetchers/iem-cli.ts

<interfaces>
From `@tradewinds/core` (existing exports):
```typescript
export function fetchWithRetry(url: string, opts?: FetchWithRetryOptions): Promise<Response>;
export class NotFoundError extends TradewindsError { /* 404 marker */ }
```

From `@tradewinds/core/internal/bounds` (consumed):
```typescript
export const STATION_CODE_RE: RegExp;
export const SKY_BASE_MAX_FT: number;
export const SLP_MIN_MB: number;
export const SLP_MAX_MB: number;
export const TEMP_MIN_C: number;
export const TEMP_MAX_C: number;
export const MAX_VISIBILITY_MILES: number;
export const MAX_WX_CODES_LEN: number;
export const MAX_RAW_METAR_LEN: number;
export const MIN_YEAR: number;
export const MAX_YEAR: number;
export function boundedFloat / boundedFloatMin / boundedInt(...);
```

From `@tradewinds/core/internal/convert`:
```typescript
export function celsiusToFahrenheit(c: number | null): number | null;
export function hpaToInhg(hpa: number | null): number | null;
```

From `_parsers/awc.ts` (post-Plan 01 widening):
```typescript
export interface Observation { /* 30 fields, source: "awc" | "iem" | "ghcnh" */ }
export function icaoToStationCode(icao: string): string;
export function mapCloudCover(code: string): string | null;
```

**Note:** This plan depends on `Observation.source` being widened to include `"ghcnh"`. Plan 01 owns that edit. If Plan 01 has NOT shipped the widening when Plan 02 executes, the GHCNh parser MUST land the widening as a defensive single-line edit (with a comment crediting Plan 01 ownership).
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Port station translator with ICAO/WMO disambiguation tests</name>
  <files>packages-ts/weather/src/_parsers/_station_translator.ts, packages-ts/weather/tests/station-translator.test.ts</files>
  <behavior>
    - `ghcnhStationToCode("ICAO-KJFK")` → `"JFK"` (strip `ICAO-` prefix, apply icao→code conversion).
    - `ghcnhStationToCode("744860-94789")` → `null` (WMO USAF-WBAN format, no ICAO prefix).
    - `ghcnhStationToCode("")` → `null`.
    - `ghcnhStationToCode("ICAO-")` → `null` (empty ICAO after prefix).
    - `extractStationCode(row)` walks `SSID_COLUMNS` (11 columns in priority order) and returns the first non-null result from `ghcnhStationToCode`. Returns `null` if all columns miss.
    - `SSID_COLUMNS` ordering matches Python `_SSID_COLUMNS` tuple at `_ghcnh.py:45-57` EXACTLY (priority by sensor relevance: temperature → dew_point → wind_speed → ...).
  </behavior>
  <action>
    Port `packages/weather/src/tradewinds/weather/_ghcnh.py::ghcnh_station_to_code` (L133-145) and `_extract_station_code` (L148-155) + the `_SSID_COLUMNS` tuple verbatim.

    1. Define `SSID_COLUMNS` as a `const` tuple (use `as const` for type narrowing). Order = Python L46-57 exactly.

    2. `ghcnhStationToCode(sourceStationId: string): string | null`:
       - Empty input → null.
       - Not prefixed with `ICAO-` → null.
       - Slice from index 5; pass through `icaoToStationCode` (imported from `_parsers/awc.ts`).
       - Validate the resulting code against `STATION_CODE_RE`. If matches → return code; else null.

    3. `extractStationCode(row: Record<string, string>): string | null`:
       - For each column in `SSID_COLUMNS`: read `row[col] ?? ""`, call `ghcnhStationToCode`, return first non-null.
       - All columns null → return null.

    4. Tests cover all 6 behavioral assertions plus:
       - First-column hit (`temperature_Source_Station_ID = "ICAO-KORD"`) returns `"ORD"` without checking later columns (mock by inserting bad WMO IDs in lower-priority columns).
       - Cascading fallback: temperature_Source_Station_ID empty, dew_point_temperature_Source_Station_ID = "ICAO-KJFK" → "JFK".
  </action>
  <verify>
    <automated>pnpm --filter @tradewinds/weather test -- --run station-translator</automated>
  </verify>
  <done>
    All translator unit tests pass; `SSID_COLUMNS` byte-matches Python tuple order; the icao→station_code conversion delegates to `awc.ts::icaoToStationCode` (no re-implementation).
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Port downloadGhcnh + downloadGhcnhRange with msw 404-skip test</name>
  <files>packages-ts/weather/src/_fetchers/ghcnh.ts, packages-ts/weather/tests/ghcnh-fetcher.test.ts</files>
  <behavior>
    - URL: `https://www.ncei.noaa.gov/oa/global-historical-climatology-network/hourly/access/by-year/{year}/psv/GHCNh_{station_id}_{year}.psv`.
    - `downloadGhcnh("744860-94789", 2024)` returns `{ stationId, year, psv: string }`.
    - `downloadGhcnhRange("ID", 2020, 2024)` iterates [2020..2024] inclusive, returns array of successful fetches; 404 years are silently dropped (NOT in array); other HTTP errors propagate.
    - `downloadGhcnhRange("ID", 2024, 2020)` (reversed) returns `[]` with zero HTTP requests.
    - Validates station id format via a `GHCNH_STATION_ID_RE` (digits + hyphen) — reject path-separator inputs at boundary.
    - Polite delay (1000ms default, injectable as `politenessMs`) AFTER each successful response only.
  </behavior>
  <action>
    Port `packages/weather/src/tradewinds/weather/_fetchers/ghcnh.py::download_ghcnh` + `download_ghcnh_range`. TS adaptations:

    1. **NO disk cache in TS-W2.** Return `{ stationId, year, psv: string }` in-memory (mirrors Plan 01's IEM ASOS shape). TS-W3 owns disk caching. Drop `dest_dir` / `skip_cache` params.

    2. **GHCNH_STATION_ID_RE:** mirror Python `validate_ghcnh_id_for_path`. GHCNh IDs carry digits, letters, hyphens — pattern `^[A-Z0-9-]{1,32}$` is safe. Throw on mismatch.

    3. **`downloadGhcnh(stationId, year, opts?)`**:
       - Validate stationId.
       - Build URL: `${GHCNH_BASE_URL}/by-year/${year}/psv/GHCNh_${stationId}_${year}.psv`.
       - `await fetchWithRetry(url, opts)` → `await response.text()` → return `{ stationId, year, psv }`.
       - 404 propagates as `NotFoundError` (raised by `fetchWithRetry`).

    4. **`downloadGhcnhRange(stationId, startYear, endYear, opts?)`**:
       - Reversed range (`endYear < startYear`) → return `[]` (mirror Python L160 implicit via range()).
       - Loop `for (let year = startYear; year <= endYear; year++)`:
         - `try { downloadGhcnh(...) }`.
         - `catch (err) { if (err instanceof NotFoundError) continue; throw err; }`.
         - On success: push to out, sleep `politenessMs` (default `NCEI_POLITE_DELAY_MS = 1000`).
       - Same `politenessMs` injection pattern as `iem-cli.ts::downloadCliRange` — extract from opts before forwarding to `fetchWithRetry`.

    5. Exports: `downloadGhcnh`, `downloadGhcnhRange`, `GHCNH_BASE_URL`, `NCEI_POLITE_DELAY_MS`, type `DownloadGhcnhRangeOptions`.

    6. Tests (msw 2.x):
       - Single-year fetch: handler returns synthetic PSV body; assert returned shape includes the body.
       - Range 2020-2024 with msw returning 200 for 2020, 2021, 2022, 2024 and 404 for 2023 → returned array has 4 entries (skipped year 2023); assert specific years.
       - Range with non-404 HTTP error (mock 500) → throws on first failing year.
       - Reversed range → zero msw events fired.
       - Invalid stationId (e.g. `"FOO/../etc"` with slash) → throws synchronously.
       - Polite delay default constant test: `NCEI_POLITE_DELAY_MS === 1000`.

    Use `politenessMs: 0` in all multi-year tests so they complete in <1s.
  </action>
  <verify>
    <automated>pnpm --filter @tradewinds/weather test -- --run ghcnh-fetcher</automated>
  </verify>
  <done>
    URL shape byte-faithful to Python; 404-skip behavior verified; range function exits cleanly on reversed ranges; `pnpm typecheck` clean.
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 3: Port parseGhcnhPsv with Quality_Code filter + unit conversion tests</name>
  <files>packages-ts/weather/src/_parsers/ghcnh.ts, packages-ts/weather/tests/ghcnh-parser.test.ts, packages-ts/weather/src/index.ts</files>
  <behavior>
    - `parseGhcnhPsv(psvBody): ReadonlyArray<Observation>` parses pipe-delimited body.
    - Per-variable Quality_Code filter: each row variable accepts only if `qc ∈ {0, 1, 4, 5, ""}` (empty string passes).
    - Letter flags `{I, P, R, U}` and codes `{2, 3, 6, 7}` REJECT the variable (set to null).
    - Row dropped (parseGhcnhRow returns null) when station_code can't be extracted OR DATE is invalid OR all 4 key vars (temp, dewp, wind_speed, slp) fail QC.
    - Unit conversions: `wind_speed` (m/s → kt via 1/0.514444, then round), `wind_gust` (m/s → kt), `visibility` (km → mi via 1/1.60934), `precipitation` (mm → in via 1/25.4), `snow_depth` (cm → in via 1/2.54), `sky_cover_summation_baseht_N` (m → ft via 3.28084, round).
    - `temperature_Report_Type === "FM16"` → observation_type "SPECI"; else "METAR".
    - DATE format: `YYYY-MM-DDTHH:MM:SS` or `YYYY-MM-DDTHH:MM:SSZ`; output `observed_at` always ends in `Z`.
    - Sky cover columns 1-4 with their own per-layer Quality_Code; layer null if QC fails.
    - Weather codes: `pres_wx_AW1..3`, extract substring before colon, filter bare-numeric WMO codes, filter QC flags `{3, P}`.
    - `raw_metar` extracted from `REM` column — find `METAR ` or `SPECI ` substring, slice from there; fallback to raw REM if marker not found.
    - Output: 30-field Observation with `source: "ghcnh"`.
  </behavior>
  <action>
    Port `packages/weather/src/tradewinds/weather/_ghcnh.py::parse_ghcnh_row` + `parse_ghcnh_file` byte-faithfully. TS adaptations:

    1. **Input is a string (PSV body), not a file.** Signature: `parseGhcnhPsv(psvBody: string): ReadonlyArray<Observation>`.

    2. **PSV reader:** hand-roll the pipe-split + header-map. NO `csv` dep. Strip `\r`, split on `\n`, first non-empty line is header, subsequent lines are data. Skip blank lines.

    3. **Constants — port verbatim:**
       - `_ALLOWED_QC = new Set(["0", "1", "4", "5"])`. Empty string short-circuits `_isQcAccepted` to true.
       - Conversion factors: `MS_TO_KT = 1 / 0.514444`, `KM_TO_MI = 1 / 1.60934`, `M_TO_FT = 3.28084`, `MM_TO_IN = 1 / 25.4`, `CM_TO_IN = 1 / 2.54`.
       - `DATE_RE = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z?$/`.

    4. **Helpers — port:** `safeFloat`, `safeInt`, `isQcAccepted`, `parseSkyCover` (split on `:` then `mapCloudCover`), `parseSkyBaseht` (m → ft, round, bound), `parseWeatherCodes` (loop pres_wx_AW1-3 with per-column QC, split colon, drop numeric-only).

    5. **`parseGhcnhRow(row): Observation | null`**:
       - Extract station_code via `extractStationCode(row)` from Task 1. If null → return null.
       - Parse DATE via `DATE_RE` + calendar-validity roundtrip (mirror `cli.ts::parseObservationDate`). If invalid → return null.
       - Validate year is in `[MIN_YEAR, MAX_YEAR]`.
       - `observed_at`: append `Z` if missing.
       - Per-variable QC: compute `temp_ok`, `dewp_ok`, `wspd_ok`, `wdir_ok`, `wgust_ok`, `slp_ok`, `altim_ok`, `vis_ok`, `precip_ok`, `snow_ok` — each via `isQcAccepted(row[varName + "_Quality_Code"] ?? "")`.
       - **Skip-row gate** (mirror Python L200-201): if `!(temp_ok || dewp_ok || wspd_ok || slp_ok)` → return null.
       - Temperature: temp_c from `temperature` if temp_ok, bounded. dewp_c from `dew_point_temperature` if dewp_ok. temp_f via `celsiusToFahrenheit`, same for dewp_f.
       - Wind: wind_speed_ms × `MS_TO_KT`, round, bounded[0, 200]. Same for gust → [0, 250]. wind_dir bounded[0, 360].
       - Pressure: slp from `sea_level_pressure`, bounded[SLP_MIN_MB, SLP_MAX_MB]. altim_hpa via `hpaToInhg`.
       - Visibility: vis_km × `KM_TO_MI`, clamped[0, MAX_VISIBILITY_MILES]. Skip if vis_km < 0.
       - Precip: mm × `MM_TO_IN`, boundedFloatMin(0).
       - Snow: cm × `CM_TO_IN`, boundedFloatMin(0).
       - Sky cover 1-4: per-layer QC check; if cov_qc → `parseSkyCover`; if base_qc → `parseSkyBaseht`.
       - Weather codes via `parseWeatherCodes`.
       - raw_metar from REM: `find("METAR ")` + `find("SPECI ")`, slice from earlier index; fallback to full REM; truncate to MAX_RAW_METAR_LEN.
       - Return 30-field object with `source: "ghcnh"` and Python's key order.

    6. **`parseGhcnhPsv(psvBody: string): ReadonlyArray<Observation>`**: split + header-map + loop + filter nulls.

    7. **Update barrel `packages-ts/weather/src/index.ts`**: re-export `downloadGhcnh`, `downloadGhcnhRange`, `GHCNH_BASE_URL`, `NCEI_POLITE_DELAY_MS`, `parseGhcnhPsv`, `parseGhcnhRow`, `ghcnhStationToCode`, `extractStationCode`, `SSID_COLUMNS`.

    8. **Tests:**
       - Synthetic PSV header + 3 rows: one all-valid, one with temperature_Quality_Code=3 (temp nulled), one with all four key vars QC-rejected (row dropped).
       - Empty Quality_Code: variable kept (empty == accepted).
       - Letter QC flag `I`: variable rejected.
       - `temperature_Report_Type=FM16` → observation_type "SPECI".
       - Wind speed conversion: `wind_speed=10` m/s → `wind_speed_kt=19` (10 / 0.514444 ≈ 19.438 → round → 19).
       - Visibility km→mi: `visibility=16.0934` km → `visibility_miles ≈ 10`.
       - sky_cover_summation_1=`SCT:04;` → sky_cover_1="SCT" (via mapCloudCover).
       - DATE invalid (e.g. `2025-02-30T00:00:00Z`) → row dropped.
       - Station unresolvable (all SSID columns empty) → row dropped.
       - REM with prefix `MET2024-09-10 14:51:00 METAR KMSY 101451Z ...` → raw_metar starts with `METAR KMSY`.
       - Weather codes: `pres_wx_AW1="TS:90"` with `pres_wx_AW1_Quality_Code="3"` → dropped; with QC empty → "TS" appended.

    Use small synthetic PSV strings (10-50 lines max) embedded in the test file. NO file I/O.
  </action>
  <verify>
    <automated>pnpm --filter @tradewinds/weather test -- --run ghcnh-parser</automated>
  </verify>
  <done>
    All parser tests pass; QC filter byte-faithful (empty string accepted, letter flags rejected); unit conversions match Python's constants; barrel updated; `pnpm --filter @tradewinds/weather test --run` green for full weather suite; `pnpm typecheck` clean.
  </done>
</task>

</tasks>

<verification>
- Three vitest test files all pass.
- `pnpm --filter @tradewinds/weather typecheck` clean (strict + noUncheckedIndexedAccess + exactOptionalPropertyTypes).
- `pnpm -r biome check` clean.
- No new external runtime deps.
- The Quality_Code filter accepts empty string as valid (critical — without this, every observation lacking explicit QC info is silently dropped, breaking parity case 5).
- `_station_translator.ts` is consumed by `parseGhcnhRow` (no duplicate impl).
</verification>

<success_criteria>
Maps to TS-W2 stub SC#3: "GHCNh PSV fetcher handles 404-as-no-data per Python `download_ghcnh_range`; CORS workaround documented in TS-CORS-MATRIX.md if blocked; PSV parser filters `Quality_Code ∈ {"0","1","4","5",""}`."

- 404-skip verified via msw test (Task 2).
- CORS: GHCNh is in TS-CORS-MATRIX.md as `OPEN` (TS-W0 deliverable) — no new matrix update needed unless the live test in TS-W2 SC#3 fixture-capture reveals drift. NOT a Plan 02 responsibility; Plan 07 owns fixture capture.
- Quality_Code filter verified via Task 3 with empty-string acceptance covered.
</success_criteria>

<output>
After completion, create `.planning/phases/ts-w2-parity-gate/ts-w2-02-SUMMARY.md` documenting:
- Final TS API for the 3 new modules (fetcher, parser, station translator).
- Note any deviation from byte-faithful Python port (e.g. in-memory PSV bodies vs file paths).
- Test count delta.
- Confirmation that `Observation.source` is widened to `"awc" | "iem" | "ghcnh"` (cross-reference Plan 01 — if Plan 01 has not yet landed the widening, this plan owns the same one-line edit defensively).
</output>

---
phase: ts-w4-mode2-transforms-qc-alpha
plan: 03
type: execute
wave: 3
depends_on: []
files_modified:
  - packages-ts/core/src/transforms/calendar.ts
  - packages-ts/core/src/transforms/index.ts
  - packages-ts/core/tests/transforms/calendar.test.ts
autonomous: true
requirements:
  - TS-TRANSFORM-02
must_haves:
  truths:
    - "calendarFeatures(rows, dateCol, tz?) returns rows with 8 cyclical-pair columns: month_sin, month_cos, dow_sin, dow_cos, hour_sin, hour_cos, day_of_year_sin, day_of_year_cos"
    - "Each cyclical pair satisfies sin² + cos² ≈ 1 to within 1e-10 (the wraparound invariant)"
    - "When tz is undefined, extraction uses UTC parts of the parsed date"
    - "When tz is a valid IANA name (e.g. 'America/New_York'), extraction uses Intl.DateTimeFormat with timeZone option — month/dow/hour/dayOfYear come from the LOCAL clock in that tz"
    - "Invalid tz (e.g. 'Invalid/Zone') throws RangeError before any row processing"
    - "Rows with non-parseable / null date column produce NULL for all 8 derived columns (NOT NaN; matches Python None)"
    - "Source rows are NOT mutated"
    - "Function is the same module as lag/diff/rolling — @tradewinds/core/transforms"
  artifacts:
    - path: packages-ts/core/src/transforms/calendar.ts
      provides: "calendarFeatures function + tz-aware Intl.DateTimeFormat extraction helpers"
    - path: packages-ts/core/src/transforms/index.ts
      provides: "Barrel re-exports calendarFeatures alongside lag/diff/rolling"
  key_links:
    - from: packages-ts/core/src/transforms/calendar.ts
      to: "Intl.DateTimeFormat (browser + Node built-in)"
      via: "tz-aware extraction; NO luxon/date-fns dep (TS Architect rubric §2 bundle gate)"
      pattern: "Intl\\.DateTimeFormat"
---

<objective>
Port Python `tradewinds.transforms.calendar_features` to TS at `@tradewinds/core/transforms` (same module as Wave 2's lag/diff/rolling). Adds 8 cyclical-pair columns to each input row:

- `month_sin` / `month_cos` (period 12)
- `dow_sin` / `dow_cos` (period 7, Mon=0..Sun=6 per Python `pd.dt.dayofweek` — Monday-first ISO ordering)
- `hour_sin` / `hour_cos` (period 24)
- `day_of_year_sin` / `day_of_year_cos` (period 365)

**TZ awareness (the load-bearing detail):** when the caller passes `tz` (an IANA timezone name like `'America/New_York'`), the calendar extraction MUST use that timezone — NOT UTC. Implementation uses `Intl.DateTimeFormat` (browser + Node built-in; NO `luxon`/`date-fns` dep to keep the bundle under TS-BUNDLE-01).

When `tz` is omitted, fall back to UTC parts of the parsed date (`getUTCMonth`, `getUTCDay`, etc.).

**Subpath placement:** `calendarFeatures` lives in the SAME barrel as Wave 2's transforms — `@tradewinds/core/transforms` — because the rubric semantically groups them ("transforms DSL surface"). Wave 2 ships the subpath + tsup entry + size gate; Wave 3 just adds a file to the existing module.

**Independence:** Wave 3 has NO dependency on Waves 1, 2, 4, 5, 6 — except a soft sequencing dependency on Wave 2 having created the `src/transforms/index.ts` barrel + subpath wiring. If Wave 3 runs before Wave 2, it must create those scaffolding files. Pragmatically: Wave 2 should ship first OR Wave 3's executor checks for the barrel and adds to it (idempotent).
</objective>

<context_files>
- `.planning/REQUIREMENTS.md` TS-TRANSFORM-02 (canonical text)
- `packages/core/src/tradewinds/transforms.py` lines 71-100 (Python `calendar_features` — `np.sin(2 * np.pi * ts.dt.month / 12)` etc.; uses `pd.to_datetime`)
- `packages-ts/core/src/temporal/timepoint.ts` (TS-W3 reference for `Intl.DateTimeFormat` tz extraction — `asZone(tz: string)` method)
- Node + browser `Intl.DateTimeFormat` docs: `formatToParts(date)` returns `[{type: 'year', value: '2024'}, {type: 'month', value: '06'}, ...]` — use `type` to pluck fields.
- Wave 2 plan (ts-w4-02-PLAN.md) for the barrel + subpath + tsup scaffolding context.
</context_files>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: calendarFeatures with tz-aware Intl.DateTimeFormat extraction</name>
  <files>packages-ts/core/src/transforms/calendar.ts, packages-ts/core/tests/transforms/calendar.test.ts</files>
  <read_first>
    - `packages/core/src/tradewinds/transforms.py` lines 71-100 (full `calendar_features`)
    - `packages-ts/core/src/temporal/timepoint.ts` lines 149-156 (`asZone(tz)` — the `Intl.DateTimeFormat` invocation pattern)
    - MDN docs on `Intl.DateTimeFormat.prototype.formatToParts` — returns `[{type, value}]` array; pluck by `type === 'month'` etc.
    - Note: `dayOfWeek` is NOT a direct part type; derive from `weekday: 'short'` + a lookup, OR compute via `(jsDay + 6) % 7` to convert JS Sunday=0 to ISO Monday=0.
  </read_first>
  <behavior>
    - Signature: `calendarFeatures<Row extends Record<string, unknown>>(rows: ReadonlyArray<Row>, dateCol: string, tz?: string): ReadonlyArray<Row & Record<string, number | null>>`.
    - Parse each row's `dateCol` value into a `Date`:
      - If `string` → `new Date(value)`; reject if `!isFinite(.getTime())`.
      - If `Date` → use directly; reject if NaN.
      - If `null`/`undefined`/other → all 8 derived columns are `null`.
    - **TZ validation upfront:** if `tz` is provided, validate by attempting `new Intl.DateTimeFormat('en-US', { timeZone: tz })`. Catch RangeError (invalid tz string) and re-throw with a clearer message. Run this BEFORE any row processing (fail-fast).
    - **Extraction:**
      - When `tz === undefined`: use `date.getUTCMonth() + 1` (1..12), `(date.getUTCDay() + 6) % 7` (0..6 ISO), `date.getUTCHours()` (0..23), and a computed day-of-year (helper: `Math.floor((date.getTime() - Date.UTC(date.getUTCFullYear(), 0, 1)) / 86400000) + 1` for the UTC year-start).
      - When `tz` is set: use `Intl.DateTimeFormat('en-US', { timeZone: tz, ... })` with `formatToParts` to extract year/month/day/hour/weekday in that tz. Compute dayOfYear from (yyyy, MM, dd) in that tz (use a Date.UTC trick: `Math.floor((Date.UTC(y, m-1, d) - Date.UTC(y, 0, 1)) / 86400000) + 1` — this gives day-of-year for the tz-local calendar date).
      - Day-of-week extraction: use `weekday: 'short'` and map `Mon→0, Tue→1, ..., Sun→6` (matches Python `dt.dayofweek` ISO ordering).
    - **Cyclical formulas (verbatim from Python):**
      - `month_sin = sin(2π * month / 12)` where month ∈ [1, 12]
      - `month_cos = cos(2π * month / 12)`
      - `dow_sin = sin(2π * dow / 7)` where dow ∈ [0, 6]
      - `dow_cos = cos(2π * dow / 7)`
      - `hour_sin = sin(2π * hour / 24)` where hour ∈ [0, 23]
      - `hour_cos = cos(2π * hour / 24)`
      - `day_of_year_sin = sin(2π * doy / 365.0)` (note: Python uses 365.0 NOT 365.25; matches `transforms.py:98`)
      - `day_of_year_cos = cos(2π * doy / 365.0)`
    - **Invariant:** `sin²+cos² ≈ 1` for each pair (sanity test for the implementation).
    - **Output:** new array; rows fresh objects; source unchanged. Each derived value is a `number` (0..1 range for the cyclical pairs after sin/cos) OR `null`.
  </behavior>
  <action>
    1. Create `packages-ts/core/src/transforms/calendar.ts`:
       ```typescript
       /**
        * calendarFeatures — add 8 cyclical-pair columns to each row.
        *
        * Mirrors Python `tradewinds.transforms.calendar_features` at
        * `packages/core/src/tradewinds/transforms.py:71-100`.
        *
        * Cyclical pairs (sin²+cos² ≈ 1) let a model see wraparound
        * (Dec → Jan is 1 month apart, not 11).
        *
        * TZ handling: when `tz` is an IANA name like 'America/New_York',
        * month/dow/hour/dayOfYear are extracted from the LOCAL clock in
        * that tz (via Intl.DateTimeFormat). When tz is omitted, UTC parts
        * are used.
        *
        * @throws RangeError  if tz is provided but not a valid IANA zone
        */
       export function calendarFeatures<Row extends Record<string, unknown>>(
         rows: ReadonlyArray<Row>,
         dateCol: string,
         tz?: string,
       ): ReadonlyArray<Row & Record<string, number | null>> {
         // Validate tz upfront (fail-fast before per-row work).
         let formatter: Intl.DateTimeFormat | null = null;
         if (tz !== undefined) {
           try {
             formatter = new Intl.DateTimeFormat("en-US", {
               timeZone: tz,
               year: "numeric",
               month: "2-digit",
               day: "2-digit",
               hour: "2-digit",
               minute: "2-digit",
               second: "2-digit",
               hour12: false,
               weekday: "short",
             });
           } catch (e) {
             throw new RangeError(
               `calendarFeatures: invalid IANA timezone '${tz}': ${String(e)}`,
             );
           }
         }

         const TAU = 2 * Math.PI;
         const NULLS = {
           month_sin: null, month_cos: null,
           dow_sin: null, dow_cos: null,
           hour_sin: null, hour_cos: null,
           day_of_year_sin: null, day_of_year_cos: null,
         };

         const WEEKDAY_INDEX: Record<string, number> = {
           Mon: 0, Tue: 1, Wed: 2, Thu: 3, Fri: 4, Sat: 5, Sun: 6,
         };

         const out: Array<Row & Record<string, number | null>> = [];
         for (const r of rows) {
           const raw = r?.[dateCol];
           let d: Date | null = null;
           if (raw instanceof Date) {
             d = Number.isFinite(raw.getTime()) ? raw : null;
           } else if (typeof raw === "string") {
             const parsed = new Date(raw);
             d = Number.isFinite(parsed.getTime()) ? parsed : null;
           } else if (typeof raw === "number" && Number.isFinite(raw)) {
             d = new Date(raw);
           }

           if (d === null) {
             out.push({ ...r, ...NULLS } as Row & Record<string, number | null>);
             continue;
           }

           let month: number;  // 1..12
           let dow: number;    // 0..6 (Mon=0)
           let hour: number;   // 0..23
           let doy: number;    // 1..366

           if (formatter !== null) {
             const parts = formatter.formatToParts(d);
             const get = (t: string): string =>
               parts.find((p) => p.type === t)?.value ?? "";
             const y = Number.parseInt(get("year"), 10);
             month = Number.parseInt(get("month"), 10);
             const dom = Number.parseInt(get("day"), 10);
             hour = Number.parseInt(get("hour"), 10);
             const wd = WEEKDAY_INDEX[get("weekday")] ?? 0;
             dow = wd;
             // doy from tz-local (y, month, dom):
             doy = Math.floor(
               (Date.UTC(y, month - 1, dom) - Date.UTC(y, 0, 1)) / 86400000,
             ) + 1;
           } else {
             month = d.getUTCMonth() + 1;
             dow = (d.getUTCDay() + 6) % 7;  // JS Sun=0 → ISO Mon=0
             hour = d.getUTCHours();
             const yStart = Date.UTC(d.getUTCFullYear(), 0, 1);
             doy = Math.floor((d.getTime() - yStart) / 86400000) + 1;
           }

           const derived = {
             month_sin: Math.sin((TAU * month) / 12),
             month_cos: Math.cos((TAU * month) / 12),
             dow_sin: Math.sin((TAU * dow) / 7),
             dow_cos: Math.cos((TAU * dow) / 7),
             hour_sin: Math.sin((TAU * hour) / 24),
             hour_cos: Math.cos((TAU * hour) / 24),
             day_of_year_sin: Math.sin((TAU * doy) / 365.0),
             day_of_year_cos: Math.cos((TAU * doy) / 365.0),
           };

           out.push({ ...r, ...derived } as Row & Record<string, number | null>);
         }
         return out;
       }
       ```

    2. Write `packages-ts/core/tests/transforms/calendar.test.ts`:
       - 4-row UTC fixture: `date_utc: ['2024-01-15T00:00:00Z', '2024-04-15T12:00:00Z', '2024-07-15T06:00:00Z', '2024-10-15T18:00:00Z']`. No tz → assert:
         - Row 0 (Jan 15 UTC): month=1; dow=0 (Mon); hour=0; doy=15.
         - Row 1 (Apr 15 UTC): month=4; dow=0 (Mon); hour=12; doy=106.
         - Row 2 (Jul 15 UTC): month=7; dow=0 (Mon); hour=6; doy=197.
         - Row 3 (Oct 15 UTC): month=10; dow=1 (Tue); hour=18; doy=289.
       - Cyclical-pair invariant: for each row, `month_sin² + month_cos² ≈ 1` within 1e-10. Same for dow, hour, day_of_year. Assert all 32 sin²+cos² values.
       - **TZ check (the load-bearing test):** input `date_utc: '2024-06-15T00:00:00Z'` with `tz: 'America/New_York'`. June 15 00:00 UTC = June 14 20:00 EDT. So month=6, dow=4 (Fri), hour=20, doy=166. Assert these.
       - **TZ DST transition:** `date_utc: '2024-11-03T06:00:00Z'` (fall-back day at 02:00 EST = 06:00 UTC) with `tz: 'America/New_York'`. Nov 3 06:00 UTC = Nov 3 01:00 EST (after fall-back). month=11, dow=6 (Sun), hour=1, doy=308. Assert.
       - **Invalid tz:** `tz: 'Invalid/Zone'` → throws RangeError BEFORE iterating rows. Assert the throw message contains 'Invalid/Zone'.
       - Non-parseable date: row with `date_utc: 'not-a-date'` → all 8 derived columns are `null`.
       - `date_utc: null` → all 8 derived columns are `null`.
       - Date input (not string): `date_utc: new Date('2024-06-15T00:00:00Z')` → works the same as the string equivalent.
       - Empty rows → empty output.
       - Source rows unchanged after call (`JSON.stringify` deep-equal).
       - All original keys preserved + 8 new keys added.
       - Dec 31 → Jan 1 wraparound: month_sin/month_cos values for Dec are nearly identical to Jan values when interpolated cyclically (sanity check the wraparound).
  </action>
  <acceptance_criteria>
    - `grep -n "export function calendarFeatures" packages-ts/core/src/transforms/calendar.ts` matches.
    - `grep -n "Intl.DateTimeFormat" packages-ts/core/src/transforms/calendar.ts` confirms tz-aware extraction.
    - `grep -nE "(month_sin|month_cos|dow_sin|dow_cos|hour_sin|hour_cos|day_of_year_sin|day_of_year_cos)" packages-ts/core/src/transforms/calendar.ts` shows all 8 derived-column names verbatim.
    - `grep -n "365.0" packages-ts/core/src/transforms/calendar.ts` confirms Python parity on day-of-year denominator (NOT 365.25, NOT 366).
    - `grep -n "RangeError.*invalid IANA\\|invalid IANA timezone" packages-ts/core/src/transforms/calendar.ts` confirms the upfront tz validation.
    - `grep -n "(d.getUTCDay() + 6) % 7\\|JS Sun=0.*ISO Mon=0" packages-ts/core/src/transforms/calendar.ts` confirms ISO Monday-first dow encoding.
    - `pnpm --filter @tradewinds/core test -- transforms/calendar` ≥ 10 cases all green.
    - Cyclical invariant test passes: every (sin, cos) pair satisfies `sin² + cos² ≈ 1` within 1e-10.
  </acceptance_criteria>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Add calendarFeatures to transforms barrel</name>
  <files>packages-ts/core/src/transforms/index.ts, packages-ts/core/tests/transforms/calendar.barrel.test.ts</files>
  <read_first>
    - `packages-ts/core/src/transforms/index.ts` (Wave 2 output — barrel containing lag/diff/rolling)
    - Wave 2's barrel test (`packages-ts/core/tests/transforms/barrel.test.ts`) for pattern
  </read_first>
  <behavior>
    - Update the barrel to add `calendarFeatures` alongside lag/diff/rolling.
    - No new tsup entry needed — `calendarFeatures` is imported transitively via the existing `src/transforms/index.ts` entry.
    - No new package.json subpath needed — already exists from Wave 2.
    - Idempotency: if Wave 2 hasn't shipped yet, this task creates the barrel + subpath + tsup entry itself (copy from Wave 2's spec); otherwise just appends the export.
  </behavior>
  <action>
    1. Open `packages-ts/core/src/transforms/index.ts`. If it exists (Wave 2 already shipped), APPEND:
       ```typescript
       export { calendarFeatures } from "./calendar.js";
       ```
       If it does NOT exist (Wave 3 ran first), create the full barrel per Wave 2's spec and add the calendar export.

    2. Verify `packages-ts/core/package.json` has `"./transforms"` subpath. If missing, add it (mirrors Wave 2 spec).

    3. Verify `packages-ts/core/tsup.config.ts` has the transforms entry. If missing, add the block from Wave 2.

    4. Write `packages-ts/core/tests/transforms/calendar.barrel.test.ts`:
       ```typescript
       import { describe, expect, it } from "vitest";
       import { calendarFeatures } from "../../src/transforms/index.js";

       describe("@tradewinds/core/transforms — calendarFeatures barrel re-export", () => {
         it("calendarFeatures is exported from the barrel", () => {
           expect(typeof calendarFeatures).toBe("function");
         });
         it("calendarFeatures returns the 8 expected columns", () => {
           const rows = [{ d: "2024-06-15T00:00:00Z" }];
           const out = calendarFeatures(rows, "d");
           const r = out[0]!;
           expect(Object.hasOwn(r, "month_sin")).toBe(true);
           expect(Object.hasOwn(r, "month_cos")).toBe(true);
           expect(Object.hasOwn(r, "dow_sin")).toBe(true);
           expect(Object.hasOwn(r, "dow_cos")).toBe(true);
           expect(Object.hasOwn(r, "hour_sin")).toBe(true);
           expect(Object.hasOwn(r, "hour_cos")).toBe(true);
           expect(Object.hasOwn(r, "day_of_year_sin")).toBe(true);
           expect(Object.hasOwn(r, "day_of_year_cos")).toBe(true);
         });
       });
       ```

    5. Run `pnpm --filter @tradewinds/core run build && pnpm run size`. Assert `@tradewinds/core` ≤ 25 KB (calendarFeatures adds ~1.5 KB to the transforms bundle; well within the 25 KB main-bundle gate since transforms is a subpath).
  </action>
  <acceptance_criteria>
    - `grep -n "calendarFeatures" packages-ts/core/src/transforms/index.ts` confirms barrel re-export.
    - `pnpm --filter @tradewinds/core test -- transforms/calendar.barrel` 2 cases green.
    - `pnpm --filter @tradewinds/core run build` emits `dist/transforms/index.{mjs,cjs,d.ts}` containing the calendarFeatures export.
    - `pnpm run size` reports `@tradewinds/core` ≤ 25 KB unchanged.
    - From a downstream consumer: `import { calendarFeatures } from "@tradewinds/core/transforms"` resolves.
  </acceptance_criteria>
</task>

</tasks>

<verification>
1. `pnpm --filter @tradewinds/core test -- transforms/calendar` runs the calendar unit + barrel test files; ≥ 12 cases all green.
2. `pnpm --filter @tradewinds/core run typecheck` clean.
3. `pnpm --filter @tradewinds/core run build` emits `dist/transforms/index.{mjs,cjs,d.ts}` with calendarFeatures exported.
4. `pnpm -r run typecheck` clean across the workspace.
5. `pnpm run size` reports `@tradewinds/core` ≤ 25 KB (calendar additions live in the transforms subpath).
6. Cyclical-pair invariant `sin² + cos² ≈ 1` holds within 1e-10 for ALL 4 derived pairs (32 assertions in the unit test).
7. TZ behavior: `'2024-06-15T00:00:00Z'` with tz='America/New_York' produces hour=20 (NOT 0), confirming Intl.DateTimeFormat tz extraction works.
</verification>

<success_criteria>
- TS-TRANSFORM-02 (part 1) fully met for calendarFeatures — all 8 cyclical-pair columns added; tz-aware via Intl.DateTimeFormat; invalid tz throws RangeError; non-parseable rows produce nulls.
- Bundle gate holds: `@tradewinds/core` ≤ 25 KB (subpath placement).
- ZERO third-party date deps added (no luxon, no date-fns — `Intl.DateTimeFormat` is built-in).
- Wraparound invariant verified: sin²+cos² ≈ 1 across all 4 pairs (the "the model sees wraparound" success criterion from Python `transforms.py:80-84`).
</success_criteria>

<review_discipline>
TypeScript-only changes under `packages-ts/core/**`. Per `.planning/REVIEW-DISCIPLINE.md`:

- **Reviewers**: codex `high` + **TypeScript Architect** (parallel).
- **Severity gate**: CRITICAL or HIGH only.
- **Loop**: fix on branch, re-dispatch, cap at 3.
- **Rubric calibration**:
  - CRITICAL if dow encoding uses JS Sun=0 instead of ISO Mon=0 (Python's `dt.dayofweek` is Monday-first; mismatch silently corrupts every model that uses day-of-week features).
  - CRITICAL if day_of_year_sin/cos uses 365.25 or 366 instead of 365.0 (Python uses 365.0 verbatim at `transforms.py:98`; parity break).
  - CRITICAL if calendar extraction silently uses UTC when a tz is provided (silent timezone corruption — a quant gets June 14 20:00 EDT calendar features for what they believe is June 15 EDT data).
  - HIGH if luxon or date-fns is imported (bundle bloat; Intl.DateTimeFormat is the canonical zero-dep choice).
  - HIGH if invalid tz string silently falls through to UTC instead of throwing RangeError (silent misconfiguration).
  - HIGH if a row with `dateCol: null` throws instead of producing nulls (Python returns NaN/NaT for invalid dates without throwing; TS analog is null).
  - HIGH if source rows are mutated (the row-immutability invariant from Wave 2; also TS Architect rubric §5).
  - HIGH if cyclical-pair invariant tests are missing (the explicit "model sees wraparound" success criterion can't pass without them).
</review_discipline>

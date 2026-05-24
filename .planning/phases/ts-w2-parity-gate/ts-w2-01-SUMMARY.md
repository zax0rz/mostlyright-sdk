---
phase: ts-w2-parity-gate
plan: 01
subsystem: weather-fetchers
tags: [iem-asos, csv-parser, yearly-chunks, ts-port, vitest, observation-row]

# Dependency graph
requires:
  - phase: ts-w1-chrome-extension-mvp-awc-cli
    provides: "Observation interface (AWC parser), @tradewinds/core fetchWithRetry + bounds + convert subpath exports, vi.spyOn(fetch) test pattern, biome + size-limit gates"
provides:
  - yearlyChunksExclusiveEnd (TS port of Python `_iem_chunks.yearly_chunks_exclusive_end`) — leap-year-safe yearly chunker for the IEM ASOS day2-exclusive endpoint
  - downloadIemAsos + buildIemUrl — yearly-chunk fetcher with Jan-1 start-normalization (cache-key parity with Python) and 1-sec polite delay
  - iemToObservation + parseIemCsv — IEM CSV-body parser emitting 30-field Observation rows (source="iem") byte-faithful to Python `_iem.iem_to_observation`
  - Widened `Observation.source` type: `"awc" | "iem" | "ghcnh"` — shared row contract for mergeObservations (TS-W2 Plan 04)
affects:
  - ts-w2-parity-gate (Plan 02 — GHCNh fetcher reuses CORS-OPEN + politenessMs pattern)
  - ts-w2-parity-gate (Plan 04 — mergeObservations consumes the widened Observation contract from all 3 source parsers)
  - ts-w2-parity-gate (Plan 05 — _pairs.buildPairs joins on Observation rows produced here)
  - ts-w3-cache-temporal-validator (disk-cache layer wraps the in-memory IemChunkResult envelope)

# Tech tracking
tech-stack:
  added: []  # No new runtime deps — hand-rolled CSV split, no msw, no papaparse
  patterns:
    - "ISO 8601 date strings (no JS Date constructor for arithmetic) — avoids silent local-TZ shifts that would poison cache keys at midnight boundaries"
    - "In-memory CSV body envelopes from fetcher → string parser → Observation[] (cache layer wraps later in TS-W3)"
    - "Inline regex validation at URL boundary (matches iem-cli.ts pattern; deep-import isolation per TS-W1 review)"
    - "vi.spyOn(globalThis, 'fetch') for fetcher tests (msw NOT installed; matches TS-W1 convention + bundle gate)"
    - "Object literal returns in canonical Python key order — byte-stable JSON.stringify across SDKs for downstream diff tooling"

key-files:
  created:
    - packages-ts/weather/src/_fetchers/_iem_chunks.ts
    - packages-ts/weather/src/_fetchers/iem-asos.ts
    - packages-ts/weather/src/_parsers/iem.ts
    - packages-ts/weather/tests/iem-chunks.test.ts
    - packages-ts/weather/tests/iem-asos.test.ts
    - packages-ts/weather/tests/iem.test.ts
  modified:
    - packages-ts/weather/src/_parsers/awc.ts  # Observation.source widened "awc" → "awc" | "iem" | "ghcnh"
    - packages-ts/weather/src/index.ts          # barrel exports the 3 new modules

key-decisions:
  - "ISO 8601 string representation for IsoDate (no JS Date arithmetic) — avoids local-TZ silent shifts; Python `_iem_chunks.py` module docstring documents this exact class of bug"
  - "Hand-rolled CSV split-on-comma in parseIemCsv — no papaparse dep (IEM format=comma doesn't quote embedded commas; Python parser confirms empirically). Keeps bundle gate happy."
  - "Inline STATION_CODE_RE in iem-asos.ts (mirror iem-cli.ts) instead of importing validateIcaoForPath — matches TS-W1 review pattern of narrow per-fetcher dep graphs"
  - "Polite delay (politenessMs) fires AFTER each successful round-trip including the last chunk (mirror Python L224 which sleeps unconditionally) — skipping trailing sleep would be a TS-side micro-optimization not present in source-of-truth"
  - "vi.spyOn(globalThis, 'fetch') instead of msw — msw is intentionally NOT installed in TS-W2 per plan 'DO NOT add deps' note + REVIEW-DISCIPLINE bundle-size rubric §2; matches existing iem-cli.test.ts and awc.test.ts test patterns"
  - "Observation.source widening done as single edit to awc.ts (not a separate shared-row-contract file) — the Observation interface remains the canonical row shape; future GHCNh parser will also import it directly"

patterns-established:
  - "ISO-date chunker pattern: { year, month, day } via regex split; never new Date() for arithmetic; advance via formatIsoDate(year+1, 1, 1) for leap-year safety"
  - "Fetcher-returns-envelope pattern: { chunkStart, chunkEnd, csv } in TS-W2 (no disk cache); TS-W3 will wrap with a cache layer that reads/writes parquet at the same envelope boundary"
  - "Parser key-order parity pattern: return literal in object initializer matches Python return-dict key order verbatim — JSON.stringify byte-stable across SDKs"
  - "Per-row source-tag widening pattern: shared Observation contract accepts the union of all source literals; each parser still emits its own literal"

requirements-completed:
  - TS-WEATHER-03
  - TS-PARSER-01
  - TS-PARSER-02

# Metrics
duration: 11min
completed: 2026-05-24
---

# Phase TS-W2 Plan 01: IEM ASOS Yearly-Chunk Fetcher + CSV Parser Summary

**Byte-faithful TS port of Python IEM ASOS yearly-chunk fetcher + CSV parser; widened `Observation.source` to the shared `"awc" | "iem" | "ghcnh"` row contract that mergeObservations (Plan 04) will consume.**

## Performance

- **Duration:** ~11 min (641 sec executor wall-clock)
- **Started:** 2026-05-24T05:34:01Z
- **Completed:** 2026-05-24T05:44:42Z
- **Tasks:** 3
- **Files modified:** 8 (6 created + 2 modified)
- **Tests added:** +61 net new (9 chunker + 18 fetcher + 34 parser)
- **Workspace test total:** 271 baseline → 332 (core 124, markets 41, weather 144, meta 20, codegen 3)
- **Bundle size delta:** @tradewinds/weather 7.32 KB → 8.85 KB (gzip+brotli) — well under the 20 KB TS-W2 gate

## Accomplishments

- **`yearlyChunksExclusiveEnd`** ([_iem_chunks.ts](../../../packages-ts/weather/src/_fetchers/_iem_chunks.ts)): leap-year-safe ISO-date chunker via calendar arithmetic (year+1, 1, 1) — never +365 days. Matches PR #85 cf9eb85 semantics; first chunk clamps to caller's `start` via `max(currentYearStart, start)`; reversed range returns `[]` without throwing.
- **`downloadIemAsos` + `buildIemUrl`** ([iem-asos.ts](../../../packages-ts/weather/src/_fetchers/iem-asos.ts)): URL shape byte-faithful to Python `_build_iem_url` (no zero-padding on month/day); start normalized to `date(start.year, 1, 1)` so per-month callers share the yearly cache key; 1-sec polite delay after each successful chunk; report_type validated against {3, 4}; station validated against `^[A-Z]{3,4}$` at URL boundary; reversed range short-circuits; errors propagate without swallowing (parity-critical path).
- **`iemToObservation` + `parseIemCsv`** ([iem.ts](../../../packages-ts/weather/src/_parsers/iem.ts)): comment-line strip BEFORE header consumption; M/empty → null; T → 0.0 for precip only; ISO 8601 UTC timestamp roundtrip with calendar-validity rejection; SPECI auto-detect with overrideable; out-of-bounds Celsius consistency (bad °C → BOTH °F and °C nulled); ALL-4-key-vars-missing row skip; 30-field output in exact Python key order.
- **`Observation.source` widening** ([awc.ts](../../../packages-ts/weather/src/_parsers/awc.ts)): single edit from `"awc"` to `"awc" | "iem" | "ghcnh"` — establishes the shared row contract mergeObservations (Plan 04) will consume. AWC parser still emits `"awc"`; IEM parser emits `"iem"`; future GHCNh parser will emit `"ghcnh"`. Matches Python `schema.observation.v1.source` enum.

## Task Commits

Each task committed atomically:

1. **Task 1: Port `yearlyChunksExclusiveEnd` + tests** — [`a2fa84a`](../../../) (`feat(ts-w2/iem-asos): port yearlyChunksExclusiveEnd + tests`)
2. **Task 2: Port `downloadIemAsos` + `buildIemUrl` + tests** — [`6da694b`](../../../) (`feat(ts-w2/iem-asos): port downloadIemAsos + buildIemUrl with tests`)
3. **Task 3: Port `iemToObservation` + `parseIemCsv` + barrel + Observation widening** — [`8152f34`](../../../) (`feat(ts-w2/iem-asos): port iemToObservation + parseIemCsv with tests`)

_All three were single-commit tasks (Vitest RED → GREEN within one cycle); no separate REFACTOR commits were needed._

## Files Created/Modified

- `packages-ts/weather/src/_fetchers/_iem_chunks.ts` (created, 95 lines) — `yearlyChunksExclusiveEnd` + `IsoDate` brand alias
- `packages-ts/weather/src/_fetchers/iem-asos.ts` (created, ~190 lines) — `downloadIemAsos`, `buildIemUrl`, `IEM_BASE_URL`, `IEM_POLITE_DELAY_MS`, `IemChunkResult`, `DownloadIemAsosOptions`
- `packages-ts/weather/src/_parsers/iem.ts` (created, ~330 lines) — `iemToObservation`, `parseIemCsv`, plus `safeFloat`, `safeInt`, `parsePrecip`, `parseTimestamp`, `parsePeakWindTime`, `detectObsType` helpers byte-faithful to Python
- `packages-ts/weather/tests/iem-chunks.test.ts` (created, 9 tests)
- `packages-ts/weather/tests/iem-asos.test.ts` (created, 18 tests)
- `packages-ts/weather/tests/iem.test.ts` (created, 34 tests)
- `packages-ts/weather/src/_parsers/awc.ts` (modified, 2 lines + comment) — `Observation.source` type widened to union
- `packages-ts/weather/src/index.ts` (modified, +18 lines) — barrel exports the 3 new modules + types

## TS API Surface (final)

```typescript
// @tradewinds/weather — TS-W2 Plan 01 additions

// _fetchers/_iem_chunks.ts
export type IsoDate = string;
export function yearlyChunksExclusiveEnd(
  start: IsoDate,
  end: IsoDate,
): ReadonlyArray<readonly [IsoDate, IsoDate]>;

// _fetchers/iem-asos.ts
export const IEM_BASE_URL: "https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py";
export const IEM_POLITE_DELAY_MS: 1000;
export interface IemChunkResult {
  readonly chunkStart: IsoDate;
  readonly chunkEnd: IsoDate;
  readonly csv: string;
}
export interface DownloadIemAsosOptions extends FetchWithRetryOptions {
  reportType?: 3 | 4;
  politenessMs?: number;
}
export function buildIemUrl(
  stationCode: string,
  start: IsoDate,
  end: IsoDate,
  reportType: number,
): string;
export function downloadIemAsos(
  stationCode: string,
  start: IsoDate,
  end: IsoDate,
  opts?: DownloadIemAsosOptions,
): Promise<ReadonlyArray<IemChunkResult>>;

// _parsers/iem.ts
export type IemObservationTypeOverride = "METAR" | "SPECI";
export type IemCsvRow = Record<string, string>;
export interface IemToObservationOptions {
  observationTypeOverride?: IemObservationTypeOverride;
}
export function iemToObservation(
  row: IemCsvRow,
  opts?: IemToObservationOptions,
): Observation | null;
export function parseIemCsv(
  csvBody: string,
  opts?: IemToObservationOptions,
): ReadonlyArray<Observation>;

// _parsers/awc.ts (modified)
export interface Observation {
  // ... (29 other fields unchanged)
  readonly source: "awc" | "iem" | "ghcnh";  // widened from "awc"
}
```

## Decisions Made

See `key-decisions` in the frontmatter. Highlights:

1. **ISO-string `IsoDate`** instead of JS `Date` — Python `_iem_chunks.py` module docstring documents the cache-key-poisoning bug class that JS `Date` arithmetic would silently introduce; ISO strings sort lexicographically equivalent to calendar order.
2. **Hand-rolled CSV split** instead of `papaparse` — bundle gate compliance + matches Python's empirically-validated assumption (IEM `format=comma` doesn't quote embedded commas).
3. **`vi.spyOn(globalThis, "fetch")` over msw** — msw is intentionally NOT installed in TS-W2 per the plan's "DO NOT add deps" note; matches existing TS-W1 patterns in `iem-cli.test.ts` and `awc.test.ts`.
4. **`Observation.source` widening as single edit to awc.ts** — keeps the shared row contract in one canonical location; future GHCNh parser (Plan 02) will import the same interface.

## Deviations from Plan

The plan's expected behaviors all matched implementation 1:1 — no auto-fix Rule deviations. Two test-suite adjustments worth flagging:

### Test-only adjustments (not deviations)

**1. msw → vi.spyOn(fetch) for HTTP mocking**
- **Found during:** Task 2 setup
- **Issue:** Plan suggested `msw` for fetcher tests; the project does NOT have msw installed and the plan itself notes "the project does NOT have a csv lib installed ... DO NOT add it" + the bundle-size rubric.
- **Fix:** Used `vi.spyOn(globalThis, "fetch")` matching the existing TS-W1 test convention (see `iem-cli.test.ts` line 22-30, `awc.test.ts` line 64-72). All 18 fetcher behaviors are still verifiable via spy call-count + mock.calls[N][0] URL inspection.
- **Files modified:** packages-ts/weather/tests/iem-asos.test.ts
- **Justification:** Plan explicitly notes "If not present, DO NOT add it" (Task 3 wording about papaparse, but the principle applies to msw too). REVIEW-DISCIPLINE TS Architect rubric §2 (bundle/dev-dep impact) supports the no-msw choice.

**2. Test assertion correction during Task 2 RED/GREEN cycle**
- **Found during:** Task 2 first test execution
- **Issue:** Initial test assertion expected `chunkStart: 2023-06-15` for `start=2023-06-15`. The Python parity contract is that `start` is normalized to `date(start.year, 1, 1)` BEFORE the chunker, so the actual first chunkStart is `2023-01-01`. The test was wrong, not the implementation.
- **Fix:** Updated the test assertion to `2023-01-01` and added a comment explaining the start-normalization parity contract.
- **Files modified:** packages-ts/weather/tests/iem-asos.test.ts (test only — implementation was correct)
- **Justification:** This is the parity-critical invariant being verified; the corrected assertion now documents it.

**3. Test mock-return-value pattern**
- **Found during:** Task 2 first GREEN run
- **Issue:** Used `mockResolvedValue(csvResponse(...))` which returns the SAME Response instance for every call — `Response.text()` consumes the body, so the second await failed with "Body has already been read".
- **Fix:** Changed to `mockImplementation(async () => csvResponse(...))` which returns a fresh Response per call.
- **Files modified:** packages-ts/weather/tests/iem-asos.test.ts
- **Justification:** Pure test-infrastructure correction; no implementation change.

### Worktree git stash recovery

During Task 1's baseline verification, an unrelated `git stash pop` pulled in a polluted stash from a different worktree, creating 38 add/add merge conflicts (`AA` index state). Recovered cleanly via `git reset HEAD && git checkout -- <conflicted paths>` then `git stash drop`. No code or tests were lost; the 3 new Task 1 files remained safely untracked through the recovery. No commits were polluted.

---

**Total deviations:** 0 (no auto-fix Rules triggered)
**Test-only adjustments:** 3 (all in test setup, not implementation)
**Impact on plan:** None. The TS implementation is byte-faithful with Python on all 9 behavioral assertions from Task 3 plus the 7 from Tasks 1+2.

## Issues Encountered

- **`@tradewinds/core` types unresolved at typecheck baseline:** First `pnpm --filter @tradewinds/weather typecheck` after install showed `Cannot find module '@tradewinds/core'` etc. Resolved by running `pnpm --filter @tradewinds/core build` once to populate `dist/` — known TS-W1 quirk (vitest has runtime aliases via vitest.config.ts but `tsc --noEmit` resolves through `dist/`).
- **Biome formatting on first test write:** Tests + parser passed biome lint but failed format (template-literal concatenation + long string lines). Resolved via `pnpm biome check --write --unsafe` — auto-fixes applied without semantic change.

## User Setup Required

None — pure TS source addition; no env vars, no dashboard config, no external services. The IEM ASOS endpoint has CORS=OPEN (per `.planning/research/TS-CORS-MATRIX.md` §IEM-ASOS) so this works in browsers, Node 20+, Cloudflare Workers, and Deno without a proxy.

## Next Phase Readiness

Ready for Plan 02 (GHCNh fetcher + PSV parser + station-id translator). Plan 02 will:
- Reuse the `vi.spyOn(globalThis, "fetch")` test pattern from this plan
- Reuse the `politenessMs` option pattern from `downloadIemAsos`
- Emit `Observation` rows with `source: "ghcnh"` consuming the widened type from this plan

Ready for Plan 04 (`mergeObservations` + `mergeClimate`). The widened `Observation.source` union is in place; `mergeObservations` will dedup by `(stationCode, observedAt, observationType)` and source-priority-rank `{ awc: 3, iem: 2, ghcnh: 1 }` per Python source-of-truth.

The in-memory `IemChunkResult` envelope ({chunkStart, chunkEnd, csv}) is intentionally cache-free — TS-W3 will wrap this same envelope with disk-cache write/read at the chunk-key boundary (filename pattern equivalent to Python's `iem_{start_iso}_{end_iso}_{partial}_{suffix}.csv` + the `_partial` namespace for skip-cache / today-UTC poisoning paths).

## Notes for Plan 04 (mergeObservations)

- `Observation.source` is now the union `"awc" | "iem" | "ghcnh"`. AWC parser literally emits `"awc"`; IEM parser literally emits `"iem"`; GHCNh parser (Plan 02) must emit `"ghcnh"` for the merge predicate to work.
- The IEM parser preserves Python's exact 30-field key order in the return object literal — `JSON.stringify(row)` is byte-stable with Python on every field. This will matter for the 5-fixture parity gate (Plan 08).
- IEM rows have `qc_field: null` always (IEM CSV doesn't carry the QC bitmask). AWC populates qc_field from `m.qcField`. mergeObservations should NOT use qc_field as a tiebreak field.
- IEM rows do NOT carry T-group temperature overrides (that's an AWC-only METAR-remarks parse). IEM's `tmpf`/`dwpf` are already pre-parsed by the upstream IEM service.

## Self-Check: PASSED

- [x] All 6 created files exist on disk: verified via `git log --stat` on the 3 Task commits
- [x] All 2 modified files have the documented edits: `awc.ts` widened, `index.ts` re-exports
- [x] All 3 task commits exist: `a2fa84a`, `6da694b`, `8152f34` (verified via `git log --oneline`)
- [x] Workspace tests all pass: 332/332 green (`pnpm -r test -- --run`)
- [x] Workspace typecheck clean: 5/5 packages green (`pnpm -r typecheck`)
- [x] Biome check clean on all new/modified files
- [x] Bundle gate: 8.85 KB < 20 KB for @tradewinds/weather

---
*Phase: ts-w2-parity-gate*
*Plan: 01*
*Completed: 2026-05-24*

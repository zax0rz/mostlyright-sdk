---
phase: ts-w2-parity-gate
plan: 08
type: execute
wave: 6
depends_on:
  - ts-w2-07
files_modified:
  - packages-ts/meta/tests/parity/parity.test.ts
  - packages-ts/meta/tests/parity/_load_handlers.ts
  - packages-ts/meta/tests/parity/_assertions.ts
  - packages-ts/meta/package.json
  - packages-ts/meta/vitest.config.ts
  - .github/workflows/drift-rotate-ts.yml
  - packages-ts/meta/tests/parity/drift_capture.ts
  - packages-ts/meta/tests/parity/drift_compare.ts
  - packages-ts/meta/tests/parity/drift/.gitkeep
autonomous: false
requirements:
  - TS-PARITY-01

must_haves:
  truths:
    - "parity.test.ts runs 5 cases. For each case: load handlers.json → install msw → call research(station, from, to) → compare against the matching tests/fixtures/parity/ts/case_N_*.json → row-by-row equality."
    - "Numeric equality is EXACT for integers (===), and tolerance-zero for floats by default. If a float column is later established as non-deterministic across platforms (rare; IEEE arithmetic should be byte-stable on x86/arm64), revisit with documented rationale."
    - "Each case passing means: row count matches, every column for every row matches Python output."
    - "msw setupServer uses onUnhandledRequest: 'error' so any TS-side request shape drift is caught immediately."
    - "Test gate is HARD: any one case failing → vitest exits non-zero → CI fails."
    - "drift-rotate-ts.yml is a weekly cron workflow that captures current research() output and diffs against the JSON fixtures; SOFT-FAILS (never blocks CI), opens a GH issue on mismatch."
    - "drift-rotate-ts.yml MUST NEVER fail the build — it only creates/updates a GitHub issue labeled 'drift-ts'."
    - "drift workflow runs research() against live APIs (not msw replays) so it catches upstream-shape drift."
  artifacts:
    - path: "packages-ts/meta/tests/parity/parity.test.ts"
      provides: "HARD parity gate — 5 cases × 19 columns × N rows = full byte-equivalence assertion"
      contains: "describe.each(CASES)"
    - path: "packages-ts/meta/tests/parity/_load_handlers.ts"
      provides: "Helper: handlers.json → msw HttpHandler[]"
      exports: ["loadHandlers"]
    - path: "packages-ts/meta/tests/parity/_assertions.ts"
      provides: "assertRowsRowEqual + canonicalSort helpers"
      exports: ["assertRowsRowEqual", "canonicalSort"]
    - path: ".github/workflows/drift-rotate-ts.yml"
      provides: "Weekly soft-fail watchdog cron"
      contains: "schedule:.*cron"
    - path: "packages-ts/meta/tests/parity/drift_capture.ts"
      provides: "Live capture script for drift cron (writes to drift/ dir)"
      contains: "TRADEWINDS_TS_LIVE"
    - path: "packages-ts/meta/tests/parity/drift_compare.ts"
      provides: "Compare drift/ vs ts/ fixtures; writes drift-report.md on mismatch"
      contains: "drift-report.md"
  key_links:
    - from: "parity.test.ts"
      to: "tests/fixtures/parity/ts/case_*.json + packages-ts/meta/tests/parity/recordings/case_*/handlers.json"
      via: "load both per case; assert research() output matches expected"
      pattern: "tests/fixtures/parity/ts"
    - from: ".github/workflows/drift-rotate-ts.yml"
      to: "drift_capture.ts + drift_compare.ts"
      via: "weekly job runs capture then compare"
      pattern: "schedule"
---

<objective>
Wire the HARD parity gate: TS `research()` output, replayed from the Plan 07 recordings, must match the Plan 03 JSON fixtures byte-by-byte on every column of every row of every case. Land the soft-fail drift cron `drift-rotate-ts.yml` alongside.

**Why this matters:** This is the gate the entire TS-W2 phase exists to clear. SC#1 of the stub PLAN: "All 5 Python parity fixtures pass against the TS implementation with exact numeric equality on every column."

**Why drift cron co-lives here:** the drift watchdog uses the same JSON fixtures + the same case windows. Building both in one plan keeps them aligned. Drift is SOFT-fail per stub SC#5 ("NEVER blocks CI; writes drift-report.md, opens GH issue").

**This plan has 1 checkpoint:** after the parity gate runs locally and all 5 cases are green, a `checkpoint:human-verify` lets the operator confirm the row counts match the parent README before pushing.

**Output:** parity.test.ts + 2 helpers + 2 drift scripts + 1 workflow YAML.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@.planning/REVIEW-DISCIPLINE.md
@.planning/phases/ts-w2-parity-gate/PLAN.md
@.planning/phases/ts-w2-parity-gate/ts-w2-03-PLAN.md
@.planning/phases/ts-w2-parity-gate/ts-w2-06-PLAN.md
@.planning/phases/ts-w2-parity-gate/ts-w2-07-PLAN.md
@.github/workflows/drift-rotate.yml
@tests/fixtures/parity/README.md
@tests/fixtures/parity/ts/manifest.json
@packages-ts/meta/tests/parity/recordings/manifest.json

<interfaces>
From Plan 03 (`tests/fixtures/parity/ts/case_N_*.json`):
```typescript
type ExpectedRow = {
  date: string;       // YYYY-MM-DD
  station: string;
  cli_high_f: number | null;
  cli_low_f: number | null;
  cli_report_type: string | null;
  obs_high_f: number | null;
  // ...full 19+1 column set per Plan 05 PairsRow
};
```

From Plan 07 (`packages-ts/meta/tests/parity/recordings/case_N/handlers.json`):
```typescript
type RecordedRequest = {
  method: string;
  url: string;
  responseStatus: number;
  responseBody: string;
  contentType: string;
};
```

From Plan 06 (`research()`):
```typescript
function research(station, fromDate, toDate, opts?): Promise<ReadonlyArray<PairsRow>>;
```

Reference workflow: `.github/workflows/drift-rotate.yml` (Python equivalent). Mirror its structure (cron, soft-fail, peter-evans/create-issue-from-file, labels `drift-ts`).
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Write the HARD parity test — 5 cases × full row equivalence</name>
  <files>packages-ts/meta/tests/parity/parity.test.ts, packages-ts/meta/tests/parity/_load_handlers.ts, packages-ts/meta/tests/parity/_assertions.ts, packages-ts/meta/vitest.config.ts</files>
  <behavior>
    - `pnpm --filter tradewinds test -- --run parity` runs 5 cases.
    - For each case: handlers.json → msw setupServer → research() → assert row-equivalent to JSON fixture.
    - Row count must match exactly.
    - For every row, every column must match: integers via `===`, floats via `===` (no tolerance unless explicitly justified in the test comment).
    - On unhandled request (i.e. TS fetcher emitted a URL the recording doesn't cover), msw throws → test fails with a clear "unhandled URL" message.
    - Test runs in <30 seconds total (in-memory replay; no network).
  </behavior>
  <action>
    1. **`packages-ts/meta/tests/parity/_load_handlers.ts`** (helper to convert recordings → msw handlers):

       ```typescript
       import { http, HttpResponse, type HttpHandler } from "msw";

       interface RecordedRequest {
         method: string;
         url: string;
         responseStatus: number;
         responseBody: string;
         contentType: string;
       }

       /**
        * Convert a recorded-request tape into msw 2.x handlers.
        * Each handler matches on exact URL + method and returns the recorded body.
        * If the test issues a request not in the tape, msw's
        * `onUnhandledRequest: "error"` policy throws — caught regression.
        */
       export function loadHandlers(records: ReadonlyArray<RecordedRequest>): HttpHandler[] {
         return records.map((r) => {
           const method = r.method.toLowerCase() as keyof typeof http;
           const factory = http[method] as typeof http.get | undefined;
           if (!factory) {
             throw new Error(`Unsupported HTTP method in recording: ${r.method}`);
           }
           return factory(r.url, () =>
             new HttpResponse(r.responseBody, {
               status: r.responseStatus,
               headers: { "content-type": r.contentType || "text/plain" },
             }),
           );
         });
       }
       ```

       **Note on multiple requests to same URL:** if a case has 2+ requests to the same URL (e.g. same year, same IEM ASOS chunk for different report_types — but the URL includes report_type as a param so that's actually a different URL), they get distinct handler entries. Each handler in msw 2.x handles ALL requests to that URL → if there are repeats, the first one wins on every call. For correct parity replay we need ordered tape semantics: install handler N, consume once, then handler N+1. Implement via a request counter per URL+method key.

       Revised approach:
       ```typescript
       export function loadHandlers(records: ReadonlyArray<RecordedRequest>): HttpHandler[] {
         // Group by URL+method; serve in declared order.
         const calls = new Map<string, number>();
         const queues = new Map<string, RecordedRequest[]>();
         for (const r of records) {
           const k = `${r.method.toUpperCase()} ${r.url}`;
           if (!queues.has(k)) queues.set(k, []);
           queues.get(k)!.push(r);
         }
         const handlers: HttpHandler[] = [];
         for (const [k, queue] of queues) {
           const [method, ...urlParts] = k.split(" ");
           const url = urlParts.join(" ");
           const m = method!.toLowerCase() as keyof typeof http;
           const factory = http[m] as typeof http.get | undefined;
           if (!factory) throw new Error(`Unsupported HTTP method: ${method}`);
           handlers.push(
             factory(url, () => {
               const idx = calls.get(k) ?? 0;
               calls.set(k, idx + 1);
               const r = queue[Math.min(idx, queue.length - 1)]!;
               return new HttpResponse(r.responseBody, {
                 status: r.responseStatus,
                 headers: { "content-type": r.contentType || "text/plain" },
               });
             }),
           );
         }
         return handlers;
       }
       ```

       This handles repeat URLs without dropping rows. If `idx >= queue.length`, returns the last response (mirrors infinite-replay). In practice repeats SHOULD NOT occur for TS-W2's stateless research() — each (station, year, report_type) URL is unique — but the helper is defensively correct.

    2. **`packages-ts/meta/tests/parity/_assertions.ts`**:

       ```typescript
       import { expect } from "vitest";
       import type { PairsRow } from "@tradewinds/core/internal/pairs";

       export function canonicalSort(rows: ReadonlyArray<PairsRow>): PairsRow[] {
         return [...rows].sort((a, b) => {
           if (a.date < b.date) return -1;
           if (a.date > b.date) return 1;
           if (a.station < b.station) return -1;
           if (a.station > b.station) return 1;
           return 0;
         });
       }

       /**
        * Strict row-equivalence assertion. Same-shape, exact field equality.
        * - Integers (cli_high_f when int64): ===.
        * - Floats: === (IEEE-stable on x86/arm64; if a future case has a
        *   numerically unstable column, document the diff and decide whether
        *   to add a tolerance — DO NOT add a blanket tolerance up front).
        * - Strings: ===.
        * - null: ===.
        */
       export function assertRowsRowEqual(
         actualRaw: ReadonlyArray<PairsRow>,
         expectedRaw: ReadonlyArray<Record<string, unknown>>,
         label: string,
       ): void {
         const actual = canonicalSort(actualRaw);
         const expected = [...expectedRaw].sort((a, b) => {
           const ad = String(a.date), bd = String(b.date);
           if (ad < bd) return -1;
           if (ad > bd) return 1;
           const as = String(a.station), bs = String(b.station);
           if (as < bs) return -1;
           if (as > bs) return 1;
           return 0;
         });
         expect(actual.length, `${label}: row count`).toEqual(expected.length);
         for (let i = 0; i < expected.length; i++) {
           const a = actual[i]!;
           const e = expected[i]!;
           const expectedKeys = Object.keys(e).sort();
           // Drop market_close_utc from this comparison ONLY IF Plan 05 SUMMARY
           // indicates a format discrepancy. Default: compare ALL 20 columns.
           for (const k of expectedKeys) {
             expect((a as Record<string, unknown>)[k], `${label}: row ${i} col ${k} (date=${e.date})`).toEqual(e[k]);
           }
         }
       }
       ```

       Critical: the assertion message includes the row's date so debugging is fast.

    3. **`packages-ts/meta/tests/parity/parity.test.ts`**:

       ```typescript
       import * as fs from "node:fs";
       import * as path from "node:path";
       import { describe, it, beforeAll, afterEach, afterAll, expect } from "vitest";
       import { setupServer } from "msw/node";
       import { research } from "../../src/research.js";
       import { loadHandlers } from "./_load_handlers.js";
       import { assertRowsRowEqual } from "./_assertions.js";

       interface Case { n: number; station: string; from: string; to: string; }

       const CASES: ReadonlyArray<Case> = [
         { n: 1, station: "KNYC", from: "2025-01-06", to: "2025-01-12" },
         { n: 2, station: "KMDW", from: "2025-04-01", to: "2025-04-30" },
         { n: 3, station: "KLAX", from: "2025-03-01", to: "2025-03-31" },
         { n: 4, station: "KMIA", from: "2024-12-01", to: "2025-11-30" },
         { n: 5, station: "KMSY", from: "2024-09-08", to: "2024-09-22" },
       ];

       const FIXTURES_DIR = path.resolve(__dirname, "../../../../tests/fixtures/parity/ts");
       const RECORDINGS_DIR = path.resolve(__dirname, "recordings");

       function loadFixture(c: Case): Array<Record<string, unknown>> {
         const filename = `case_${c.n}_${c.station}_${c.from}_${c.to}.json`;
         const raw = fs.readFileSync(path.join(FIXTURES_DIR, filename), "utf-8");
         return JSON.parse(raw) as Array<Record<string, unknown>>;
       }

       function loadRecordings(c: Case): Array<{method: string; url: string; responseStatus: number; responseBody: string; contentType: string}> {
         const raw = fs.readFileSync(path.join(RECORDINGS_DIR, `case_${c.n}`, "handlers.json"), "utf-8");
         return JSON.parse(raw);
       }

       describe("TS-W2 HARD parity gate (SC#1)", () => {
         // One msw server per test, swapped per case.
         describe.each(CASES)("case $n: $station $from → $to", (c) => {
           const handlers = loadHandlers(loadRecordings(c));
           const server = setupServer(...handlers);
           beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
           afterEach(() => server.resetHandlers(...handlers));
           afterAll(() => server.close());

           it("research() produces row-equivalent output to the JSON fixture", async () => {
             const expected = loadFixture(c);
             const actual = await research(c.station, c.from, c.to, {
               // Politeness 0 for fast tests; the recordings already encode the rate-limit-respecting capture.
               // Pass options matching the meta/research.ts ResearchOptions shape.
             });
             assertRowsRowEqual(actual, expected, `case_${c.n}`);
           }, 30_000); // 30s budget per case
         });
       });
       ```

    4. Update `packages-ts/meta/vitest.config.ts` if needed to include the `tests/parity/` directory + the `msw/node` polyfill. msw 2.x in Node 20+ works without polyfills, but verify the `setupFiles` array doesn't exclude it.

    5. **Run locally**: `pnpm --filter tradewinds test -- --run parity`. Expect 5 green cases.

    **If any case fails:**
    - Read the failing column. Is it cli_high_f (CLI data) → check Plan 06's CLI wiring.
    - Is it obs_high_f → check Plan 04's mergeObservations + Plan 05's _obsAggregates.
    - Is it market_close_utc → check Plan 05's ISO formatting.
    - Re-run capture (Plan 07) if recordings appear stale.
    - DO NOT loosen tolerance to make tests pass. Per stub PLAN: "If TS-side fixture drifts from Python output for reasons unrelated to a bug (e.g., float-precision edge case), DO NOT loosen the tolerance — refactor to avoid the precision-loss path or document the divergence as an explicit decision."
  </action>
  <verify>
    <automated>pnpm --filter tradewinds test -- --run parity</automated>
  </verify>
  <done>
    All 5 parity cases pass in vitest; the test command exits 0; no `onUnhandledRequest` errors fire; row counts match parent README (7 + 30 + 31 + 365 + 15 = 448 total row comparisons across all cases).
  </done>
</task>

<task type="checkpoint:human-verify" gate="blocking">
  <name>Task 2: Operator verifies parity gate locally before drift workflow ships</name>
  <what-built>
    Plan 06+07+08 collectively ship the TS parity gate. Task 1 of this plan runs all 5 cases and asserts byte-equivalence. The remaining work is the drift cron, which is non-blocking. Before that ships, the operator verifies the parity gate is genuinely green AND understands what "green" means.
  </what-built>
  <how-to-verify>
    1. Run the full TS test suite from repo root:
       ```bash
       pnpm -r test --run
       ```
       Expected: all packages green; the new `parity.test.ts` block shows 5/5 cases passing.

    2. Spot-check the row count per case:
       ```bash
       for n in 1 2 3 4 5; do
         python -c "import json; print(f'case_{$n}:', len(json.load(open('tests/fixtures/parity/ts/case_${n}_'+'KNYC KMDW KLAX KMIA KMSY'.split()[${n}-1]+'_'+open('tests/fixtures/parity/ts/manifest.json').read().split())))" 2>/dev/null || true
       done
       ```
       (Simpler: `cat tests/fixtures/parity/ts/manifest.json` and check row_count per case = {7, 30, 31, 365, 15}.)

    3. Open one fixture + one actual output side by side (the test failure message includes paths). Mentally verify the obs_* aggregates look plausible for a real weather window — e.g. obs_high_f for KMIA in summer should be in the 80s/90s.

    4. Run `pnpm -r typecheck` and `pnpm -r biome check`.
  </how-to-verify>
  <resume-signal>
    Type "parity green" to proceed to Task 3 (drift cron). If any case fails, describe + diagnose; we may iterate on Plan 04/05/06 before continuing.
  </resume-signal>
</task>

<task type="auto">
  <name>Task 3: Build drift_capture.ts + drift_compare.ts + drift-rotate-ts.yml workflow</name>
  <files>packages-ts/meta/tests/parity/drift_capture.ts, packages-ts/meta/tests/parity/drift_compare.ts, packages-ts/meta/tests/parity/drift/.gitkeep, .github/workflows/drift-rotate-ts.yml, packages-ts/meta/package.json</files>
  <action>
    1. **`packages-ts/meta/tests/parity/drift_capture.ts`** — similar to Plan 07's `capture_recordings.ts` but writes to `tests/parity/drift/case_N.json` (NOT `recordings/`). Captures live `research()` OUTPUT (the rows themselves, in JSON format matching Plan 03's projection), not the HTTP tapes.

       ```typescript
       /**
        * Capture current research() output for drift detection.
        * Writes JSON rows to packages-ts/meta/tests/parity/drift/case_N.json.
        * Compared against tests/fixtures/parity/ts/ by drift_compare.ts.
        */
       import * as fs from "node:fs";
       import * as path from "node:path";
       import { research } from "../../src/research.js";

       if (process.env.TRADEWINDS_TS_LIVE !== "1") {
         console.error("Refusing: TRADEWINDS_TS_LIVE=1 required");
         process.exit(1);
       }

       const CASES = [
         { n: 1, station: "KNYC", from: "2025-01-06", to: "2025-01-12" },
         { n: 2, station: "KMDW", from: "2025-04-01", to: "2025-04-30" },
         { n: 3, station: "KLAX", from: "2025-03-01", to: "2025-03-31" },
         { n: 4, station: "KMIA", from: "2024-12-01", to: "2025-11-30" },
         { n: 5, station: "KMSY", from: "2024-09-08", to: "2024-09-22" },
       ];

       const DRIFT_DIR = path.resolve(__dirname, "drift");

       async function main() {
         fs.mkdirSync(DRIFT_DIR, { recursive: true });
         for (const c of CASES) {
           console.log(`[drift] capturing case_${c.n} ${c.station} ${c.from} → ${c.to}`);
           const rows = await research(c.station, c.from, c.to);
           const outPath = path.join(DRIFT_DIR, `case_${c.n}_${c.station}_${c.from}_${c.to}.json`);
           fs.writeFileSync(outPath, JSON.stringify([...rows].sort((a, b) =>
             a.date < b.date ? -1 : a.date > b.date ? 1 : 0
           ), null, 2) + "\n", "utf-8");
         }
         console.log("✓ drift capture complete");
       }
       main().catch((err) => { console.error("drift capture failed:", err); process.exit(2); });
       ```

    2. **`packages-ts/meta/tests/parity/drift_compare.ts`** — diff drift/ vs ts/ fixtures; write `drift-report.md` on any mismatch; exit 0 always (soft-fail).

       ```typescript
       /**
        * Compare drift/ vs tests/fixtures/parity/ts/ JSON fixtures.
        * On mismatch: write drift-report.md with per-case diff summary.
        * ALWAYS exits 0 — drift cron is SOFT-FAIL per stub SC#5.
        */
       import * as fs from "node:fs";
       import * as path from "node:path";

       const FIXTURES_DIR = path.resolve(__dirname, "../../../../tests/fixtures/parity/ts");
       const DRIFT_DIR = path.resolve(__dirname, "drift");
       const REPORT_PATH = path.resolve(__dirname, "drift-report.md");

       const CASES = [
         { n: 1, station: "KNYC", from: "2025-01-06", to: "2025-01-12" },
         { n: 2, station: "KMDW", from: "2025-04-01", to: "2025-04-30" },
         { n: 3, station: "KLAX", from: "2025-03-01", to: "2025-03-31" },
         { n: 4, station: "KMIA", from: "2024-12-01", to: "2025-11-30" },
         { n: 5, station: "KMSY", from: "2024-09-08", to: "2024-09-22" },
       ];

       interface Mismatch {
         case_n: number;
         rowIndex: number;
         column: string;
         expected: unknown;
         actual: unknown;
         date: string;
       }

       function diffCase(c: typeof CASES[number]): Mismatch[] {
         const filename = `case_${c.n}_${c.station}_${c.from}_${c.to}.json`;
         const expected = JSON.parse(fs.readFileSync(path.join(FIXTURES_DIR, filename), "utf-8"));
         const driftPath = path.join(DRIFT_DIR, filename);
         if (!fs.existsSync(driftPath)) {
           return [{ case_n: c.n, rowIndex: -1, column: "<missing-drift-file>", expected: filename, actual: null, date: "-" }];
         }
         const actual = JSON.parse(fs.readFileSync(driftPath, "utf-8"));
         const mismatches: Mismatch[] = [];
         if (actual.length !== expected.length) {
           mismatches.push({ case_n: c.n, rowIndex: -1, column: "<row-count>", expected: expected.length, actual: actual.length, date: "-" });
           return mismatches;
         }
         for (let i = 0; i < expected.length; i++) {
           for (const k of Object.keys(expected[i])) {
             if (JSON.stringify(actual[i][k]) !== JSON.stringify(expected[i][k])) {
               mismatches.push({ case_n: c.n, rowIndex: i, column: k, expected: expected[i][k], actual: actual[i][k], date: String(expected[i].date) });
             }
           }
         }
         return mismatches;
       }

       function main() {
         const allMismatches: Mismatch[] = [];
         for (const c of CASES) {
           try {
             allMismatches.push(...diffCase(c));
           } catch (err) {
             console.warn(`case_${c.n} diff failed:`, err);
           }
         }
         if (allMismatches.length === 0) {
           console.log("✓ no drift detected across 5 cases");
           if (fs.existsSync(REPORT_PATH)) fs.unlinkSync(REPORT_PATH);
           return; // exit 0
         }
         // Build report
         const lines: string[] = [`# Drift detected — TS parity watchdog`, ``];
         lines.push(`Runtime: ${new Date().toISOString()}`, ``);
         lines.push(`| Case | Row | Date | Column | Expected | Actual |`);
         lines.push(`|------|-----|------|--------|----------|--------|`);
         for (const m of allMismatches.slice(0, 200)) {
           lines.push(`| ${m.case_n} | ${m.rowIndex} | ${m.date} | \`${m.column}\` | \`${JSON.stringify(m.expected)}\` | \`${JSON.stringify(m.actual)}\` |`);
         }
         if (allMismatches.length > 200) {
           lines.push(``, `_Showing first 200 of ${allMismatches.length} total mismatches._`);
         }
         lines.push(``, `## Triage`, ``);
         lines.push(`Likely causes:`);
         lines.push(`1. **Upstream API drift** (IEM/AWC/GHCNh/CLI changed response shape) — re-capture Plan 07 recordings + investigate.`);
         lines.push(`2. **Plan 04 merge regression** — check mergeObservations / mergeClimate.`);
         lines.push(`3. **Plan 05 aggregation regression** — check _obsAggregates math.`);
         lines.push(`4. **Plan 06 orchestrator regression** — check observation bucketing by settlementDateFor.`);
         lines.push(``);
         lines.push(`Cross-reference Python drift cron output (`.github/workflows/drift-rotate.yml`):`);
         lines.push(`- Python green + TS red → TS-side bug.`);
         lines.push(`- Both red → real upstream-shape drift.`);
         lines.push(`- Python red + TS green → likely upstream change affecting only Python's fetcher path.`);
         fs.writeFileSync(REPORT_PATH, lines.join("\n") + "\n", "utf-8");
         console.log(`drift-report.md written with ${allMismatches.length} mismatches`);
         // STILL exit 0 — soft-fail policy.
       }

       main();
       ```

    3. **`packages-ts/meta/tests/parity/drift/.gitkeep`** — empty file so the dir exists in git but content stays gitignored. Add `packages-ts/meta/tests/parity/drift/*.json` to `.gitignore` (the drift outputs ARE transient).

    4. **`.github/workflows/drift-rotate-ts.yml`** — mirror the Python `drift-rotate.yml` structure:

       ```yaml
       name: Drift Watchdog TS (weekly)

       # TS-W2 Plan 08 SC#5 — weekly Mon 07:00 UTC cron. Captures the current
       # TS research() output against the 5 parity cases, diffs against
       # tests/fixtures/parity/ts/ JSON fixtures.
       #
       # SOFT-FAIL POLICY: this workflow NEVER fails CI. Drift is a watchdog
       # signal — labelled GH issue is the only side-effect on mismatch.
       # Mirror of .github/workflows/drift-rotate.yml (Python) — see that file
       # + .planning/phases/ts-w2-parity-gate/PLAN.md SC#5 + §Sync-process discipline.

       on:
         schedule:
           - cron: "0 7 * * 1"   # Mondays 07:00 UTC
         workflow_dispatch:

       permissions:
         contents: read
         issues: write

       jobs:
         drift-ts:
           runs-on: ubuntu-latest
           steps:
             - uses: actions/checkout@v4

             - name: Install pnpm
               uses: pnpm/action-setup@v4
               with:
                 version: 9

             - name: Set up Node
               uses: actions/setup-node@v4
               with:
                 node-version: "20"
                 cache: "pnpm"

             - name: Install deps
               run: pnpm install --frozen-lockfile

             - name: Build packages
               run: pnpm -r build

             - name: Capture current research() output → drift/
               env:
                 TRADEWINDS_TS_LIVE: "1"
               run: pnpm --filter tradewinds tsx tests/parity/drift_capture.ts

             - name: Compare drift/ vs ts/ JSON fixtures (soft-fail watchdog)
               run: pnpm --filter tradewinds tsx tests/parity/drift_compare.ts

             - name: Check for drift report
               id: report
               run: |
                 if [ -f packages-ts/meta/tests/parity/drift-report.md ]; then
                   echo "report_exists=true" >> "$GITHUB_OUTPUT"
                 else
                   echo "report_exists=false" >> "$GITHUB_OUTPUT"
                 fi

             - name: Open drift issue (if report exists)
               if: steps.report.outputs.report_exists == 'true'
               uses: peter-evans/create-issue-from-file@v5
               with:
                 title: "Drift detected: TS weekly watchdog (${{ github.run_id }})"
                 content-filepath: packages-ts/meta/tests/parity/drift-report.md
                 labels: |
                   drift-ts
                   ts-w2
       ```

       **Key invariants:**
       - `cron: "0 7 * * 1"` — Mondays 07:00 UTC, matches Python.
       - No `if: failure()` gates; the steps complete with exit 0 even on diff mismatch (the script writes the report and exits 0).
       - Issue creation runs ONLY when `drift-report.md` exists.
       - Labels include `drift-ts` (distinguishes from Python's `drift`).

    5. Add to `packages-ts/meta/package.json` scripts:
       ```jsonc
       "drift-capture": "tsx tests/parity/drift_capture.ts",
       "drift-compare": "tsx tests/parity/drift_compare.ts"
       ```

    6. **DO NOT** add the parity test to a CI workflow in this plan. The parity test runs as part of `pnpm -r test --run` which already runs in the existing `test-ts.yml` workflow (TS-W0 deliverable). It's a hard gate at PR/push time.

       However, verify `test-ts.yml` doesn't filter out the parity test directory. If it uses `--exclude tests/parity/**`, remove that filter. Read `.github/workflows/test-ts.yml` first.
  </action>
  <verify>
    <automated>test -f .github/workflows/drift-rotate-ts.yml &amp;&amp; pnpm --filter tradewinds typecheck</automated>
  </verify>
  <done>
    drift-rotate-ts.yml exists with cron + soft-fail + issue-create steps; drift_capture.ts + drift_compare.ts compile cleanly; .gitignore updated to exclude drift/*.json; test-ts.yml NOT filtering out parity tests (verified by reading the YAML).
  </done>
</task>

</tasks>

<verification>
- `pnpm --filter tradewinds test -- --run parity` → 5/5 green cases.
- `pnpm -r test --run` → all packages green; the parity test block is included.
- `pnpm -r typecheck` clean.
- `pnpm -r biome check` clean.
- `.github/workflows/drift-rotate-ts.yml` is a valid YAML (mock-validate with `yq` or just read it).
- `drift-rotate-ts.yml` cron matches Python's (`0 7 * * 1`).
- Both `drift_capture.ts` and `drift_compare.ts` script-resolvable via `pnpm --filter tradewinds drift-capture` / `drift-compare`.
- `tests/parity/drift/` exists in git (via `.gitkeep`) but `drift/*.json` is gitignored.
</verification>

<success_criteria>
Maps to TS-W2 stub SC#1 + SC#5:

**SC#1 (HARD GATE):** "All 5 Python parity fixtures pass against the TS implementation with exact numeric equality on every column. HTTP replay via msw against recordings captured from the Python tests."
- 5 cases × full row × all 19 columns → byte-equivalent.
- Verified via `pnpm --filter tradewinds test -- --run parity` in Task 1 + the checkpoint in Task 2.

**SC#5:** "Weekly drift cron drift-rotate-ts.yml lands — captures research() for 5 parity cases into tests/fixtures/ts/drift/, soft-fails on mismatch (writes drift-report.md, opens GH issue, NEVER blocks CI)."
- drift-rotate-ts.yml exists with cron + soft-fail + issue-create.
- drift_compare.ts always exits 0; the workflow never fails (no `if: failure()` chains).
- Verified in Task 3.

**Overall TS-W2 closeout:** if Task 1 passes and Task 3 ships, the phase is COMPLETE pending the review-discipline loop (codex high + TS Architect parallel).
</success_criteria>

<output>
After completion, create `.planning/phases/ts-w2-parity-gate/ts-w2-08-SUMMARY.md` documenting:
- Final 5-case parity result (all green).
- Total row comparisons performed (sum of row counts across cases).
- Total parity test runtime (should be < 30s).
- Drift cron schedule + label.
- Any deviations from Python drift-rotate.yml structure.
- Followups (if any):
  - Whether `market_close_utc` format matches byte-for-byte across SDKs.
  - Whether any float columns required tolerance (should be NONE per stub PLAN's "DO NOT loosen tolerance" rule).
</output>

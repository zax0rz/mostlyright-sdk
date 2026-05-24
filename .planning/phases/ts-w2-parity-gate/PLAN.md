# Phase TS-W2 — Parity Gate

**Status:** Planned (8 sub-plans below; ready for `/gsd-execute-phase ts-w2`).
**Milestone:** TypeScript v0.1.0
**Lane:** Rob (primary) + Vu (Python fixture export — Plan 03 — + parity-comparison helper)
**Depends on:** Phase TS-W1
**Blocks:** TS-W3, TS-W4, TS-W5, TS-W6 (everything depends on a green parity gate as the trust foundation)

## Goal

Pass the 5-fixture parity gate against Python `research()` Mode 1 output. Land IEM ASOS + GHCNh fetchers + parsers + the two merge policies that Python ships with strict-`>` priority + first-seen tiebreak. Without this gate, the TS port is "looks similar" — with it, the TS SDK is byte-equivalent on the canonical demo cases.

**HARD GATE — TS v0.1.0 ships only if all 5 fixtures green.**

## Requirements

- TS-WEATHER-03 (IEM ASOS yearly-chunk fetcher)
- TS-WEATHER-04 (GHCNh fetcher)
- TS-PARSER-01..04 (full parser set)
- TS-MERGE-01 (mergeObservations + mergeClimate)
- TS-PARITY-01 (parity gate)

## Success Criteria

1. All 5 Python parity fixtures pass against the TS implementation with exact numeric equality on every column. HTTP replay via `msw` against recordings captured from the Python tests.
2. IEM ASOS fetcher uses yearly chunks (calendar-aligned, leap-year safe — port of Python `_iem_chunks.yearly_chunks_exclusive_end`, NOT `yearly_chunks_inclusive`; IEM's `day2` is EXCLUSIVE, so chunks end on Jan 1 of the following year) at 1 req/sec politeness; CSV parser handles `#`-prefix comments + `M`/`T` sentinels + multi-column expansion identical to `_iem.iem_to_observation`.
3. GHCNh PSV fetcher handles 404-as-no-data per Python `download_ghcnh_range`; CORS workaround documented in `TS-CORS-MATRIX.md` if blocked; PSV parser filters `Quality_Code ∈ {"0","1","4","5",""}`.
4. `mergeObservations(rows)` reproduces Python source priority `{awc: 3, iem: 2, ghcnh: 1}` + strict-`>` + first-seen tiebreak. `mergeClimate(rows)` dedups by `(stationCode, observationDate)` with `REPORT_TYPE_PRIORITY` from codegen. **Property test (fast-check)** asserts merge produces row-equivalent output across `shuffleRows(rows)` for the restricted input class where no two rows share the same `(stationCode, observedAt, observationType)` AND `sourcePriority` — i.e. permutation-stable on inputs WITHOUT same-priority duplicate-key conflicts (this preserves the parity-faithful first-seen semantics that Python's `merge_observations` exhibits; an arbitrary-shuffle stability test would FALSELY require TS to diverge from Python's order-dependent same-priority-tiebreak behavior). A separate **canonical-fetch-order replay test** asserts the parity-fixture HTTP recordings, replayed in their captured order, produce byte-equivalent merged output across runs.
5. Weekly drift cron `drift-rotate-ts.yml` lands — captures `research()` for 5 parity cases into `tests/fixtures/ts/drift/`, soft-fails on mismatch (writes `drift-report.md`, opens GH issue, NEVER blocks CI).

## Sub-Plans + Execution Waves

The 8-wave breakdown collapses into 6 execution waves once dependencies are mapped. Plans inside the same wave can run in parallel (no file-overlap; independent fetchers/parsers).

| Plan | File | Wave | Depends on | Touches | What it ships |
|------|------|------|------------|---------|---------------|
| 01 | [ts-w2-01-PLAN.md](./ts-w2-01-PLAN.md) | 1 | — | `packages-ts/weather/{src,tests}/...iem*` | IEM ASOS fetcher + yearly-chunk helper + IEM CSV parser (stub Waves 1+2 fused — chunker+fetcher+parser are tightly coupled; the parser consumes CSV bodies the fetcher emits). |
| 02 | [ts-w2-02-PLAN.md](./ts-w2-02-PLAN.md) | 1 | — | `packages-ts/weather/{src,tests}/...ghcnh*`, `_station_translator.ts` | GHCNh fetcher + PSV parser + station-id translator (stub Wave 3). Parallel to Plan 01 — no shared files. |
| 03 | [ts-w2-03-PLAN.md](./ts-w2-03-PLAN.md) | 1 | — | `tests/fixtures/parity/{export_for_ts.py,ts/*.json,test_parity_ts_export.py}` | Python-side: export 5 parquet parity fixtures as JSON. Plan 07 captures HTTP recordings; this plan captures FIXTURES. Parallel to Plans 01+02 (Python-only edits). |
| 04 | [ts-w2-04-PLAN.md](./ts-w2-04-PLAN.md) | 2 | 01, 02 | `packages-ts/core/{src,tests}/internal/merge/`, `packages-ts/weather/src/_parsers/cli.ts` migration | `mergeObservations` + `mergeClimate` migration to `@tradewinds/core/internal/merge` + fast-check property test for restricted-input permutation stability + canonical-fetch-order replay test (stub Wave 4). |
| 05 | [ts-w2-05-PLAN.md](./ts-w2-05-PLAN.md) | 3 | 04 | `packages-ts/core/{src,tests}/internal/pairs.ts` | `buildPairs` + `_obsAggregates` + `pairsToRows` ported (Mode 1 only, no forecast — stub Wave 5). |
| 06 | [ts-w2-06-PLAN.md](./ts-w2-06-PLAN.md) | 4 | 05 | `packages-ts/meta/{src,tests}/research.ts` rewrite | `research()` updated to call all 4 sources + merge + buildPairs; W1 null-column placeholders removed (stub Wave 6). |
| 07 | [ts-w2-07-PLAN.md](./ts-w2-07-PLAN.md) | 5 | 06 | `packages-ts/meta/tests/parity/{capture_recordings.ts, recordings/}` | Capture msw recordings via operator-gated live run against the 5 case windows (stub Wave 7 — recordings half; fixture-JSON half is Plan 03). |
| 08 | [ts-w2-08-PLAN.md](./ts-w2-08-PLAN.md) | 6 | 07 | `packages-ts/meta/tests/parity/{parity.test.ts,_load_handlers.ts,_assertions.ts,drift_*}`, `.github/workflows/drift-rotate-ts.yml` | HARD parity test (5 cases × full byte-equivalence) + drift-rotate-ts.yml weekly soft-fail cron (stub Wave 8). |

### Wave-by-wave execution map

```
Wave 1 (parallel):  [Plan 01: IEM]    [Plan 02: GHCNh]   [Plan 03: JSON export]
                          ╲                 ╱                       │
                           ╲               ╱                        │
Wave 2:                [Plan 04: merge policies]                    │
                                │                                    │
Wave 3:                [Plan 05: buildPairs join]                    │
                                │                                    │
Wave 4:                [Plan 06: research() orchestrator]            │
                                │                                    │
Wave 5:                [Plan 07: msw recording capture] ─────────────┤
                                │                                    │
Wave 6:                [Plan 08: HARD parity test + drift cron] ─────┘
```

Plan 03 runs in Wave 1 (Python-only, no TS deps) but its output (`tests/fixtures/parity/ts/*.json`) is consumed in Wave 6 (Plan 08's HARD parity comparison). Plan 07's recordings are also consumed in Wave 6.

### Critical invariants (carry across all sub-plans)

1. **`yearly_chunks_exclusive_end`** (NOT `_inclusive`) — IEM's `day2` is exclusive; chunks end on Jan 1 of next year. Plan 01.
2. **Parsers byte-faithful:** `#` comments stripped, `M`/`T` sentinels, multi-column expansion. Plans 01 (IEM), 02 (GHCNh).
3. **mergeObservations priority** `{awc: 3, iem: 2, ghcnh: 1}` with **STRICT >** + first-seen tiebreak. Plan 04.
4. **mergeClimate dedup** by `(stationCode, observationDate)` with REPORT_TYPE_PRIORITY (codegen-sourced). Plan 04.
5. **Property test** asserts RESTRICTED-input permutation stability ONLY (no arbitrary-shuffle stability — that would falsely require divergence from Python's order-dependent tiebreak). Plan 04.
6. **drift-rotate-ts.yml SOFT-FAIL** — never blocks CI; opens labeled issue. Plan 08.
7. **GHCNh Quality_Code** filter accepts `{0, 1, 4, 5, ""}` (empty string IS valid, critical for case 5). Plan 02.
8. **No tolerance loosening** if fixtures fail — refactor away the precision loss OR document the divergence per CROSS-SDK-SYNC §2.3. Plan 08.

## Out of Scope

- Cache (TS-W3).
- Mode 2 dispatch (TS-W4).
- Validator beyond the parity-test internal use.
- Forecast wiring (TS-W5+).
- Parallel prefetch — TS-W2's `research()` is sequential (no `_prefetch_sources` analog). Lands in TS-W3+.
- ajv-standalone validators on TS schemas — deferred to TS-W3 per TS-W0 follow-up #1.

## Review panel

3-reviewer panel temporarily (codex `high` + TypeScript Architect + python-architect) — chunk-size + cache-poisoning paths are parity-critical and security-adjacent (same threshold Python Phase 1.5 used). Drift cron MUST never block CI (soft-fail discipline). Plan 03's Python-side edits route under `python-architect`; Plans 01, 02, 04, 05, 06, 07, 08 (TS-only) route under `TypeScript Architect`. See `.planning/REVIEW-DISCIPLINE.md` Language-routing matrix for the per-Plan reviewer pair.

## Parity gate handling

Same pre-flight gate as Python Phase 1.5 / 2.1: any merge-policy change MUST re-run all 5 parity fixtures before merging to `main`. If TS-side fixture drifts from Python output for reasons unrelated to a bug (e.g., float-precision edge case), DO NOT loosen the tolerance — refactor to avoid the precision-loss path or document the divergence as an explicit decision (Key Decision entry in PROJECT.md + `accepted_drift` parity ticket per CROSS-SDK-SYNC §2.3).

## Sync-process discipline

Same parity-ticket workflow as TS-W1. Additionally, the **drift-cron output is shared** with Python's `drift-rotate.yml` — both watchdogs compare against the SAME `tests/fixtures/parity/` expected JSON (the canonical Python output). If Python drift cron fires AND TS drift cron stays green, that's almost certainly an upstream API change affecting Python's fetcher path; if both fire, it's a real upstream-shape drift; if only TS fires, it's a TS-side bug. Issue templates auto-populated by each cron job include a "diagnosis" line based on this matrix.

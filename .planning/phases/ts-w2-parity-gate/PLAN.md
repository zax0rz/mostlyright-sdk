# Phase TS-W2 — Parity Gate

**Status:** Stub (run `/gsd-plan-phase ts-w2`).
**Milestone:** TypeScript v0.1.0
**Lane:** Rob (primary) + Vu (Python fixture export + parity-comparison helper)
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

## Waves (to be detailed)

- **Wave 1**: IEM ASOS fetcher + yearly-chunk helper (port of `_iem_chunks.yearly_chunks_exclusive_end` — the helper `download_iem_asos` actually uses per `packages/weather/src/tradewinds/weather/_fetchers/iem_asos.py:209`; NOT `yearly_chunks_inclusive`).
- **Wave 2**: IEM CSV parser + `iemToObservation`.
- **Wave 3**: GHCNh fetcher + PSV parser + station-id translator.
- **Wave 4**: `mergeObservations` + `mergeClimate` + fast-check property tests for restricted-input permutation stability + canonical-fetch-order replay test.
- **Wave 5**: `_pairs.buildPairs` join + `pairsToRows` (TS equivalent of `pairs_to_dataframe`).
- **Wave 6**: Update `research()` to include all 4 sources; remove W1's null-column placeholders.
- **Wave 7**: Export 5 Python parity fixtures as JSON + capture HTTP recordings via `msw` recordHandlers OR replay vcrpy cassettes.
- **Wave 8**: TS parity test (loads fixture → msw → `research()` → row-equivalent assertion). `drift-rotate-ts.yml` workflow.

## Out of Scope

- Cache (TS-W3).
- Mode 2 dispatch (TS-W4).
- Validator beyond the parity-test internal use.

## Review panel

3-reviewer panel temporarily (codex `high` + python-architect + security) — chunk-size + cache-poisoning paths are parity-critical and security-adjacent (same threshold Python Phase 1.5 used). Drift cron MUST never block CI (soft-fail discipline).

## Parity gate handling

Same pre-flight gate as Python Phase 1.5 / 2.1: any merge-policy change MUST re-run all 5 parity fixtures before merging to `main`. If TS-side fixture drifts from Python output for reasons unrelated to a bug (e.g., float-precision edge case), DO NOT loosen the tolerance — refactor to avoid the precision-loss path or document the divergence as an explicit decision (Key Decision entry in PROJECT.md + `accepted_drift` parity ticket per CROSS-SDK-SYNC §2.3).

## Sync-process discipline

Same parity-ticket workflow as TS-W1. Additionally, the **drift-cron output is shared** with Python's `drift-rotate.yml` — both watchdogs compare against the SAME `tests/fixtures/parity/` expected JSON (the canonical Python output). If Python drift cron fires AND TS drift cron stays green, that's almost certainly an upstream API change affecting Python's fetcher path; if both fire, it's a real upstream-shape drift; if only TS fires, it's a TS-side bug. Issue templates auto-populated by each cron job include a "diagnosis" line based on this matrix.

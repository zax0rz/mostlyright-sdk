# Phase TS-W4 — Mode 2 + Transforms + QC Alpha

**Status:** Ready to execute (6 sub-plans). Run `/gsd-execute-phase ts-w4-mode2-transforms-qc-alpha` to execute.
**Milestone:** TypeScript v0.1.0
**Lane:** Rob
**Depends on:** Phase TS-W3 AND Python Phase 3.4 QC-01 (materialization of `tradewinds.qc.ALPHA_RULES`, sourced into the codegen output `packages-ts/core/src/data/generated/qc-alpha-rules.ts` per CROSS-SDK-SYNC.md §1.2). The codegen output is already in place — verified before sub-plan authoring; Wave 5 (QCEngine) consumes it directly.
**Blocks:** TS-W5 (Polymarket settlement uses transforms-equivalent rounding), TS-W6 (transforms surface in `featureCatalog()`)

## Goal

Quality layer matching Python Phase 3 + 3.4 + 3.5: source-explicit dispatch with role-scoped source-identity errors, transforms (lag/diff/rolling/calendar/cross-features) for baseline quant ergonomics, QC alpha rules producing the `obsQcStatus` bitfield.

## Requirements

- TS-RESEARCH-02 (`researchBySource` + `assertSourceIdentity`)
- TS-MODE2-01 (source enum + Mode 2 dispatch table)
- TS-TRANSFORM-01 (temporal transforms: lag/diff/diff2/rolling)
- TS-TRANSFORM-02 (calendar + cross-features + clipOutliers)
- TS-QC-01 (QCEngine + 5 alpha rules sourced from codegen)
- TS-QC-02 (crosscheckIemGhcnh)

## Success Criteria

1. `researchBySource(station, source, fromDate, toDate)` dispatches per `source ∈ {iem.archive, iem.live, awc.live, ghcnh.archive}` (TS-MODE2-01 source enum). `assertSourceIdentity(rows, expectedSource, role)` throws `SourceMismatchError` naming the offending role (`observations`/`forecasts`/`settlement`) per Python contract.
2. Transforms (`lag`/`diff`/`diff2`/`rolling`/`calendarFeatures`/`spread`/`windChill`/`heatIndex`/`clipOutliers`) match Python `transforms.*` output byte-for-byte on a shared 50-row fixture. Column-naming convention `{col}_{op}_{param}` honored.
3. `heatIndex(90, 70)` and `windChill(20, 15)` match NWS reference table values within 1°F. Out-of-domain inputs return `tempF` unchanged (matches Python; the requirement text's "→ null" is corrected per Parity-Ticket in Wave 4 — Python returns the unmodified temperature, NOT None).
4. `QCEngine.apply(rows)` adds an `obsQcStatus` Int (32-bit bitfield) column. The 5 alpha rules ported with EXACT rule IDs and bit positions consumed from codegen `packages-ts/core/src/data/generated/qc-alpha-rules.ts`: `temp_c.out_of_range` (bit 0), `dew_point_c.exceeds_temp` (bit 1), `wind_speed_ms.negative` (bit 2), `wind_dir_deg.out_of_range` (bit 3), `slp_hpa.out_of_range` (bit 4). Bit positions and rule IDs come from the codegen table — TS implementation MUST NOT hand-redefine.
5. `crosscheckIemGhcnh(iemRows, ghcnhRows, opts={tolC: 2.0})` returns disagreement rows with `{station, eventTime, tempCIem, tempCGhcnh, deltaC}` camelCase columns. The strict `>` boundary (NOT `>=`) matches Python qc.py:228.

## Sub-plans

Six sub-plans, organized into 6 waves. Waves 2, 3, 4, 6 are independent of each other (parallel-eligible). Wave 5 sequenced after 2/3/4 so the column-naming convention they establish is in flight by the time QC consumes it; Wave 5 also creates the `@tradewinds/core/qc` subpath that Wave 6 extends.

| Wave | Plan | Objective | Requirements | Autonomous |
|------|------|-----------|--------------|------------|
| 1 | [ts-w4-01](./ts-w4-01-PLAN.md) | Mode 2 dispatch (`researchBySource` + `assertSourceIdentity` + `Mode2Source` const-union + per-row identity tests) | TS-RESEARCH-02, TS-MODE2-01 | yes |
| 2 | [ts-w4-02](./ts-w4-02-PLAN.md) | `lag`/`diff`/`diff2`/`rolling` at `@tradewinds/core/transforms` with `{col}_{op}_{param}` naming + min_periods=1 + Bessel-corrected std | TS-TRANSFORM-01 | yes |
| 3 | [ts-w4-03](./ts-w4-03-PLAN.md) | `calendarFeatures` with tz-aware `Intl.DateTimeFormat` extraction; 8 cyclical-pair columns; sin²+cos²≈1 invariant | TS-TRANSFORM-02 (part 1) | yes |
| 4 | [ts-w4-04](./ts-w4-04-PLAN.md) | `spread` + `windChill` (NWS formula) + `heatIndex` (NWS Rothfusz) + `clipOutliers` (PHYSICS_BOUNDS + std>0 guard + sigma=0 pass-through); NWS reference-table tests | TS-TRANSFORM-02 (part 2) | yes |
| 5 | [ts-w4-05](./ts-w4-05-PLAN.md) | `QCEngine` + 5 alpha rules at `@tradewinds/core/qc`; bit positions sourced from `data/generated/qc-alpha-rules.ts`; `obsQcStatus` 32-bit bitfield; codegen-parity regression guard | TS-QC-01 | yes |
| 6 | [ts-w4-06](./ts-w4-06-PLAN.md) | `crosscheckIemGhcnh` inner-join + tolerance (default 2.0 °C, strict `>`); camelCase disagreement-row shape | TS-QC-02 | yes |

### Wave dependency graph

```
Wave 1 (Mode 2 — independent)
Wave 2 (lag/diff/rolling — independent)        \
Wave 3 (calendarFeatures — independent)         } Waves 2, 3, 4 parallel-eligible
Wave 4 (spread/windChill/heatIndex/clip — indep) /
            \                                                   \
             \--→ Wave 5 (QCEngine — soft seq on 2/3/4)         |
                       \                                         |
                        \-→ Wave 6 (crosscheck — soft seq on 5)  |
Wave 6 also runs independent of 1-4; the only shared file with Wave 5
is `packages-ts/core/src/qc/index.ts` (idempotent appends).
```

Hard data dependencies: NONE between waves. Wave 5/6 share the qc subpath scaffolding; whichever wave runs first creates it. Wave 2/3/4 share the transforms subpath scaffolding (Wave 2 creates; 3/4 append). Plans are written to be idempotent on subpath creation.

## Out of Scope (deferred)

- QC sidecar parquet writes (TS doesn't ship parquet in v0.1).
- Forecast QC (deferred to v0.2 in both Python and TS).
- Climate QC.
- Polymarket settlement (TS-W5).
- Mode 2 source `iem.live` (v0.1.0 parity gap — explicit throw in Wave 1; v0.2 will add the per-month live IEM endpoint).
- Python `preprocessing.iem_crosscheck` flexible-column auto-derivation (TS narrows to `{station, eventTime, temp_c}` explicit input shape; callers normalize before calling).

## Critical Parity Notes

- **Source enum (TS-MODE2-01):** TS narrows Python's 7-value `_VALID_OBSERVATION_SOURCES` to the 4 canonical dotted forms: `'iem.archive' | 'iem.live' | 'awc.live' | 'ghcnh.archive'`. Bare `iem`/`awc`/`ghcnh` are NOT accepted at the TS input boundary (the dispatch table aliases them internally via `SOURCE_ALIASES`). Per-row `source` field is NEVER rewritten — Python's parser-emitted bare tag survives in TS output rows (mode2.py:161-166 silent-rewrite warning preserved).
- **Out-of-domain behavior for windChill / heatIndex (TS-TRANSFORM-02):** Python source explicitly returns `temp_f` (NOT None) when domain bounds not satisfied — `transforms.py:114` and `transforms.py:126`. The requirement text says "→ null" but Python is the canonical source; TS returns `tempF` to match. Documented as Parity-Ticket in Wave 4's task action.
- **clipOutliers sigma=0 pass-through (Phase 3.5 review-iter):** when `sigma === 0` (all values identical), Python's `mean ± std * 0 = [mu, mu]` collapses the column; the TS implementation pass-through-s values unchanged to avoid silent dataset corruption. Python `std <= 0` guard is also ported (raises ValueError-equivalent RangeError).
- **QC rule IDs + bit positions:** SOURCED from `packages-ts/core/src/data/generated/qc-alpha-rules.ts` via `QC_ALPHA_RULES_BY_ID.get(ruleId)`. NEVER hand-coded. A regression-guard test (`codegen-parity.test.ts`) asserts the runtime ALPHA_RULES match the codegen table byte-for-byte; future codegen drift fires loud.
- **QC column naming (Parity-Ticket):** Python uses `obs_qc_status` snake_case; TS row keys use `obsQcStatus` camelCase to match the TS idiom established by other transforms. Wire-format conversion to snake_case is the JSON serializer's responsibility (TS-W3 Plan 07 `jsonDumps`).
- **Crosscheck threshold (TS-QC-02):** strict `>` (NOT `>=`) per Python qc.py:228. `delta_c === tolC` produces NO disagreement.
- **Crosscheck output shape (Parity-Ticket):** Python `{station, event_time, temp_c_iem, temp_c_ghcnh, delta_c}` (snake_case); TS `{station, eventTime, tempCIem, tempCGhcnh, deltaC}` (camelCase). Same wire-format conversion strategy as obsQcStatus.
- **Bundle size (TS-BUNDLE-01):** `@tradewinds/core` ≤ 25 KB main-bundle gate enforced. Transforms + QC live at subpaths (`@tradewinds/core/transforms`, `@tradewinds/core/qc`), NOT in the root barrel — same pattern TS-W3 iter-4 H8 established for temporal/formats/validator. Mode 2 lives in `@tradewinds/meta` (NOT `@tradewinds/core`) to avoid the core→weather dep cycle that `Observation`-type consumption would create.
- **JS bitwise OR ceiling:** `obsQcStatus` is a 32-bit signed integer (JS `|` semantics). The 5 alpha rules use bits 0-4; ample room for Phase 3.5+ additions up to bit 31. Wave 5 defensively throws if any rule's `bitPosition >= 32`.

## Review discipline

Every sub-plan ends with a `<review_discipline>` block. TypeScript-only PRs route to **codex `high` + TypeScript Architect** (parallel dispatch) per `.planning/REVIEW-DISCIPLINE.md`. Loop on CRITICAL/HIGH only; cap at 3 iterations; escalate at 3. No MEDIUM/LOW; no style nits.

Mixed PRs (e.g. a Python-side codegen change shipping with a TS-side consumer change in the same PR) follow the routing matrix in REVIEW-DISCIPLINE.md — codex `high` + Python Architect + TypeScript Architect running in parallel until ALL THREE return clean.

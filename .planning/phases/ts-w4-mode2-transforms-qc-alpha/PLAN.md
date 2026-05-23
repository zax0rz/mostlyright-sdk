# Phase TS-W4 — Mode 2 + Transforms + QC Alpha

**Status:** Stub (run `/gsd-plan-phase ts-w4`).
**Milestone:** TypeScript v0.1.0
**Lane:** Rob
**Depends on:** Phase TS-W3 AND Python Phase 3.4 QC-01 (materialization of `tradewinds.qc.ALPHA_RULES`, sourced into Group B gated codegen output `schemas/qc-alpha-rules.json` per CROSS-SDK-SYNC.md §1.2). If the Group B output is empty at TS-W4 time, Wave 5 (QCEngine) is BLOCKED until that Python source ships; Waves 1-4 + 6 (Mode 2, transforms, crosscheck) can still proceed.
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

1. `researchBySource(station, source, fromDate, toDate)` dispatches per `source ∈ {iem.archive, iem.live, awc.live, ghcnh.archive}` (TS-MODE2-01 source enum). `assertSourceIdentity(rows, expectedSource)` throws `SourceMismatchError` naming the offending role (`observations`/`forecasts`/`settlement`) per Python contract.
2. Transforms (`lag`/`diff`/`diff2`/`rolling`/`calendarFeatures`/`spread`/`windChill`/`heatIndex`/`clipOutliers`) match Python `transforms.*` output byte-for-byte on a shared 50-row fixture. Column-naming convention `{col}_{op}_{param}` honored.
3. `heatIndex(90, 70)` and `windChill(20, 15)` match NWS reference table values within 1°F. Out-of-domain inputs return `null` (matching Python's `None`); does NOT throw (Python returns `None`).
4. `QCEngine.apply(rows)` adds an `obsQcStatus` Int (32-bit bitfield) column. The 5 alpha rules ported with EXACT rule IDs and bit positions Python `ALPHA_RULES` ships at `packages/core/src/tradewinds/qc.py:103`: `temp_c.out_of_range` (bit 0), `dew_point_c.exceeds_temp` (bit 1), `wind_speed_ms.negative` (bit 2), `wind_dir_deg.out_of_range` (bit 3), `slp_hpa.out_of_range` (bit 4). Rule IDs + bit positions loaded from codegen `schemas/qc-alpha-rules.json` (Group B gated); TS implementation MUST NOT hand-redefine.
5. `crosscheckIemGhcnh(iemRows, ghcnhRows, opts={tolC: 2.0})` returns disagreement rows with `{station, eventTime, tempCIem, tempCGhcnh, deltaC}` columns matching Python output.

## Waves

- **Wave 1**: Mode 2 dispatch (`researchBySource`) + `assertSourceIdentity` + per-role source-identity tests + TS-MODE2-01 source enum.
- **Wave 2**: Lag/diff/diff2/rolling transforms (pure functions; same column-naming convention) — covers TS-TRANSFORM-01.
- **Wave 3**: `calendarFeatures` (uses `Intl.DateTimeFormat` for tz-aware month/dow/hour extraction) — part of TS-TRANSFORM-02.
- **Wave 4**: Cross-features: `spread`, `windChill` (NWS formula), `heatIndex` (NWS Rothfusz), `clipOutliers`. NWS reference-table tests — completes TS-TRANSFORM-02.
- **Wave 5**: `QCEngine` + 5 alpha rules with EXACT Python rule IDs + bit positions from codegen `schemas/qc-alpha-rules.json`: `temp_c.out_of_range` (bit 0), `dew_point_c.exceeds_temp` (bit 1), `wind_speed_ms.negative` (bit 2), `wind_dir_deg.out_of_range` (bit 3), `slp_hpa.out_of_range` (bit 4). Bitfield aggregation. **Blocked if Python Phase 3.4 hasn't materialized `ALPHA_RULES` yet** (gated codegen output empty).
- **Wave 6**: `crosscheckIemGhcnh` disagreement output + tolerance config.

## Out of Scope

- QC sidecar parquet writes (TS doesn't ship parquet in v0.1).
- Forecast QC (deferred to v0.2 in both Python and TS).
- Climate QC.
- Polymarket settlement (TS-W5).

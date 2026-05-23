# Phase TS-W4 — Mode 2 + Transforms + QC Alpha

**Status:** Stub (run `/gsd-plan-phase ts-w4`).
**Milestone:** TypeScript v0.1.0
**Lane:** Rob
**Depends on:** Phase TS-W3
**Blocks:** TS-W5 (Polymarket settlement uses transforms-equivalent rounding), TS-W6 (transforms surface in `featureCatalog()`)

## Goal

Quality layer matching Python Phase 3 + 3.4 + 3.5: source-explicit dispatch with role-scoped source-identity errors, transforms (lag/diff/rolling/calendar/cross-features) for baseline quant ergonomics, QC alpha rules producing the `obsQcStatus` bitfield.

## Requirements

- TS-RESEARCH-02 (`researchBySource` + `assertSourceIdentity`)
- TS-TRANSFORM-01 (9 transforms)
- TS-QC-01 (QCEngine + ≥5 alpha rules)
- TS-QC-02 (crosscheckIemGhcnh)

## Success Criteria

1. `researchBySource(station, source, fromDate, toDate)` dispatches per `source ∈ {iem.archive, iem.live, awc.live, ghcnh.archive}`. `assertSourceIdentity(rows, expectedSource)` throws `SourceMismatchError` naming the offending role (`observations`/`forecasts`/`settlement`) per Python contract.
2. Transforms (`lag`/`diff`/`diff2`/`rolling`/`calendarFeatures`/`spread`/`windChill`/`heatIndex`/`clipOutliers`) match Python `transforms.*` output byte-for-byte on a shared 50-row fixture. Column-naming convention `{col}_{op}_{param}` honored.
3. `heatIndex(90, 70)` and `windChill(20, 15)` match NWS reference table values within 1°F. Out-of-domain inputs return `null` (matching Python's `None`); does NOT throw (Python returns `None`).
4. `QCEngine.apply(rows)` adds an `obsQcStatus` Int (32-bit bitfield) column. ≥ 5 alpha rules ported (temp/dewpoint/wind/pressure physics bounds + METAR-corruption); same rule IDs and bit positions as Python `ALPHA_RULES`.
5. `crosscheckIemGhcnh(iemRows, ghcnhRows, opts={tolC: 2.0})` returns disagreement rows with `{station, eventTime, tempCIem, tempCGhcnh, deltaC}` columns matching Python output.

## Waves

- **Wave 1**: Mode 2 dispatch (`researchBySource`) + `assertSourceIdentity` + per-role source-identity tests.
- **Wave 2**: Lag/diff/diff2/rolling transforms (pure functions; same column-naming convention).
- **Wave 3**: `calendarFeatures` (uses `Intl.DateTimeFormat` for tz-aware month/dow/hour extraction).
- **Wave 4**: Cross-features: `spread`, `windChill` (NWS formula), `heatIndex` (NWS Rothfusz), `clipOutliers`. NWS reference-table tests.
- **Wave 5**: `QCEngine` + ≥5 alpha rules (temp bounds, dewpoint > temp, wind neg/huge, pressure bounds, METAR-corruption) + bitfield aggregation.
- **Wave 6**: `crosscheckIemGhcnh` disagreement output + tolerance config.

## Out of Scope

- QC sidecar parquet writes (TS doesn't ship parquet in v0.1).
- Forecast QC (deferred to v0.2 in both Python and TS).
- Climate QC.
- Polymarket settlement (TS-W5).

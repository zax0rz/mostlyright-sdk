# Phase TS-W6 — Discovery + Snapshot + DataVersion

**Status:** Stub (run `/gsd-plan-phase ts-w6`).
**Milestone:** TypeScript v0.1.0
**Lane:** Rob
**Depends on:** Phase TS-W3 (CacheStore + temporal primitives) + Phase TS-W4 (transforms surface for `featureCatalog()`)
**Parallel with:** TS-W5 (independent file scope)

## Goal

Ergonomic surface — "what do I have for KNYC?" answers + `DataSnapshot` with TOON encoding + `DataVersion` reproducibility token via Web Crypto SHA-256.

## Requirements

- TS-DISCOVERY-01 (availability)
- TS-DISCOVERY-02 (describe + featureCatalog + climateGaps stub)
- TS-INTL-01 (internationalDailyExtremes)
- TS-SNAPSHOT-01 (buildSnapshot + DataSnapshot toDict/toToon — partially shipped in TS-W1)
- TS-VERSION-01 (DataVersion via Web Crypto)

## Success Criteria

1. `availability(station)` returns `{station, monthsCached, firstMonth, lastMonth}` sourced from `CacheStore` (counts both observation cache + climate cache).
2. `internationalDailyExtremes(rows, {stationTz})` rolls per-local-calendar-day `{tempMaxC, tempMinC, tempMaxF, tempMinF}` at whole-°C precision. UTC-wrap edge cases tested for RJTT (UTC+9), SAEZ (UTC-3), NZWN (UTC+12/13 DST). Uses `Intl.DateTimeFormat` for tz-aware day extraction.
3. `buildSnapshot(...)` returns a frozen `DataSnapshot` (interface + `Object.freeze`) with `.toDict()` (JSON-safe) and `.toToon()` (TOON v3.0 encoded string) methods matching Python output byte-for-byte on a 3-case fixture.
4. `DataVersion.fromComponents(sdkVersion, schemaIds, sources, codeSha, dataSha)` via `crypto.subtle.digest('SHA-256', ...)` produces the same `token` as the Python `discovery.DataVersion` for identical inputs. Round-trip property test (same inputs → same token across calls).
5. `describe(schemaId)` returns multi-line string from JSON-Schema `description` fields. `featureCatalog()` returns the transforms surface in stable order. `climateGaps(station, from, to)` throws `NotImplementedError` matching Python.

## Waves

- **Wave 1**: `availability(station)` reading from `CacheStore` (browser + Node paths tested).
- **Wave 2**: `internationalDailyExtremes` + UTC-wrap edge cases (RJTT/SAEZ/NZWN).
- **Wave 3**: `buildSnapshot` + `DataSnapshot` interface + `toDict()` + `toToon()` (TOON v3.0 encoder lifted/ported from Python `_toon`).
- **Wave 4**: `DataVersion.fromComponents` via Web Crypto; cross-language token-equality test.
- **Wave 5**: `describe(schemaId)` + `featureCatalog()` + `climateGaps` stub.

## Out of Scope

- Top-level `tradewinds.DataVersion` legacy v1 shape (port as `LegacyDataVersion` if needed; otherwise skip).
- Cross-station discovery (`availableStations(market)`) — deferred to v0.1.x.
- Kalshi-specific catalog annotations in `featureCatalog()` — deferred to MCP (Python v0.2 Phase 5 PLAN-02).

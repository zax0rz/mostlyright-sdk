# Phase TS-W1 — Chrome-extension MVP (AWC + CLI subset of `research()`)

**Status:** Stub (run `/gsd-plan-phase ts-w1` to expand).
**Milestone:** TypeScript v0.1.0
**Lane:** Rob (primary)
**Depends on:** Phase TS-W0
**Blocks:** TS-W2 (parity gate needs full source set on top of W1's MVP)

## Goal

Ship the smallest useful TS surface to unblock Rob's Chrome extension overlay on kalshi.com. Station lookup + Kalshi NHIGH/NLOW resolver + AWC live observations + IEM CLI settlement readings + a minimal `research()` that pulls AWC + CLI only (no IEM ASOS, no GHCNh, no cache yet). Bundle size must stay tight so the extension service worker loads fast.

## Requirements

- TS-CORE-01 (exception hierarchy)
- TS-CORE-02 (unit conversions)
- TS-WEATHER-01 (AWC fetcher)
- TS-WEATHER-02 (IEM CLI fetcher + range)
- TS-MARKETS-01 (Kalshi resolvers)
- TS-RESEARCH-01 (Mode 1 research, partial — AWC + CLI subset)
- TS-SNAPSHOT-01 (settlement math)

## Success Criteria

1. `await research('NYC', '2025-01-01', '2025-01-07')` from a Node script returns `ResearchRow[]` with non-null `cliHighF`/`cliLowF` AND non-null `obsHighF`/`obsLowF`. Forecast + GHCNh-derived columns may be null.
2. `kalshiNhighResolve('KHIGHNYC', new Date('2025-01-06'))` returns frozen `{settlementSource: 'cli.archive', settlementStation: 'KNYC', cityTicker: 'NYC', contractDate: '2025-01-06'}`. `KNOWN_WRONG_STATIONS` contract test passes.
3. Exception hierarchy ships with `toDict()` matching Python `to_json_safe` on null/NaN/inf/cycle edge cases.
4. Chrome-extension end-to-end smoke test (one-page test extension fetching `research()` from its service worker against AWC + IEM CLI live) passes. Smoke test lives in `packages-ts/examples/chrome-extension-mvp/`.
5. `size-limit` reports W1 subset (`@tradewinds/core` + `@tradewinds/weather`'s W1 surface + `@tradewinds/markets`) ≤ 30 KB minified+gzipped.

## Waves (to be detailed)

- **Wave 1**: `@tradewinds/core/exceptions` + `internal/convert` + `internal/bounds` + `internal/http` retry wrapper (pure-function bedrock, no I/O).
- **Wave 2**: `@tradewinds/markets` — codegen-sourced Kalshi map + NHIGH/NLOW resolvers + `KNOWN_WRONG_STATIONS` contract test.
- **Wave 3**: `@tradewinds/weather/_fetchers/awc` + AWC parser ported byte-faithful from `_awc.awc_to_observation`.
- **Wave 4**: `@tradewinds/weather/_fetchers/iem-cli` + range fetcher + CLI parser + `inferReportType` + `REPORT_TYPE_PRIORITY` from codegen.
- **Wave 5**: `@tradewinds/core/snapshot` math (LST offset, `settlementDateFor`, `settlementWindowUtc`, `cliAvailableAt`, `marketCloseUtc`).
- **Wave 6**: Minimal `research()` orchestrator — AWC + CLI only, in-memory, no cache. Returns `ResearchRow[]` with the 19 columns (some null).
- **Wave 7**: Chrome-extension smoke test example app + size-limit gate verification.

## Out of Scope

- IEM ASOS + GHCNh (TS-W2).
- Cache (TS-W3).
- Temporal primitives / validator (TS-W3).
- Mode 2 dispatch (TS-W4).
- Forecast columns / NWP (deferred to v0.2 per Python disposition).

## Review panel

Standard 2-reviewer. Bundle-size + parser-correctness against shared AWC/CLI fixtures are the gates.

## Sync-process discipline (carried over from TS-W0)

Every PR in this phase that introduces a Python-paired surface MUST follow [`.planning/CROSS-SDK-SYNC.md`](../../CROSS-SDK-SYNC.md):

- AWC parser + IEM CLI parser ports — **no parity ticket needed** (these port _existing_ Python behavior; the gate is parity-test equivalence, not a behavior change).
- Any new behavior or signature deviation from Python — parity ticket required per CROSS-SDK-SYNC §2.1.
- `parity-ticket-check.yml` (shipped in TS-W0 Wave 4) gates merge.

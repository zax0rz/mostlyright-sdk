---
gsd_state_version: 1.0
milestone: v0.1.0
milestone_name: — `@tradewinds/*` on npm)
status: Phase 8 (Polymarket US + per-issuer denylist) code-complete. Python v0.1.0rc1 ready to publish (operator-gated). 8/8 TS phases code-complete (npm publish operator-gated).
stopped_at: "Phase 8 ready to merge to main (4 review iterations; codex + python-architect + ts-architect all PASS)"
last_updated: "2026-05-24T23:30:00.000Z"
last_activity: "2026-05-24 - Phase 8 Polymarket US coverage + per-issuer denylist code-complete (4-iter review, all reviewers PASS)"
progress:
  total_phases: 22
  completed_phases: 2
  total_plans: 22
  completed_plans: 15
  percent: 68
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-05-21; STATE.md refreshed 2026-05-24)

**Core value:** `research(contract, station, from_date, to_date)` returns clean, leakage-free, source-identified training pairs that backtest the same way they trade — and any train/infer source mismatch errors loudly instead of silently corrupting a model.
**Current focus:** Phase 8 (Polymarket US + per-issuer denylist) merging next; Phase 9 (Markets Trade History) + Phase 10 (Composable research()) queued

## Current Position

Phase: Python v0.1.0 (12/12 phases, all REAL impls) COMPLETE + TS v0.1.0 (8/8 phases TS-W0..TS-W7) COMPLETE + **Phase 8 (Polymarket US Coverage + Per-Issuer Settlement Invariants) code-complete + review-clean**
Plan: Phase 8 ready to merge to main; Phase 9 (Markets Trade History) next.
Status: 1743 Python tests pass + 1228 TS tests pass. All review iterations PASS. Phase 8 closes the Polymarket-vs-Kalshi silent-corruption gap for US cities.
Last activity: 2026-05-24 - Phase 8 shipped (4-iter codex + python-architect + ts-architect review, all PASS)

Progress: Python [██████████] 100% (12/12 phases, 1743 tests) | TS [8/8 phases shipped — TS-W0 → TS-W7 code-complete; 1228 TS tests; npm publish operator-gated] | **Phase 8 (paired Python + TS) code-complete + review-clean**

## Phase 8 closeout (2026-05-24) — Polymarket US Coverage + Per-Issuer Settlement Invariants

Merge commit pending. Closes the silent-corruption invariant gap and unblocks cross-issuer (Kalshi vs Polymarket) basis-trade research for US cities. Phase 8 is **dual-SDK** (paired Python + TS in same merge).

**Requirements shipped (6/6):**
- POLY-US-01 — Polymarket city catalog extended with 17 US cities (NYC→KLGA NOT KNYC, Chicago→KORD NOT KMDW, LAX/MIA/DEN/BOS/AUS/DC/PHL/SFO/SEA/ATL/HOU/DAL/PHX/MSP/DTW). Per-city `POLYMARKET_CITY_CITATIONS` audit-trail registry (`polymarket_city_citations.py`) — each entry carries the canonical Polymarket event URL + Wunderground proof.
- POLY-US-02 — `polymarket.KNOWN_WRONG_STATIONS: Mapping[str, frozenset[str]]` (MappingProxyType, runtime-read-only) symmetric to `kalshi_stations.KNOWN_WRONG_STATIONS`. Per-city granularity because Polymarket catalog is multi-city; flat denylist would forbid KLGA from ever resolving even though KLGA IS the correct NYC Polymarket station.
- POLY-US-03 — Tier 1.5 Wunderground URL extraction in `_per_event_station.py` (Python) + `resolver.ts` (TS). Canonical-anchor regex (`/pws/`, `/dashboard/pws/`, `/history/daily/`, `/history/airport/`, `/weather-station/`, `/cat/forecasts/`) + optional lowercase-slug intermediate segments + negative-lookahead `(?![A-Za-z0-9_-])` for Markdown URL terminators. Case-sensitive (iter-3 fix) so intermediate slugs cannot consume uppercase station segments. Multi-URL disambiguation: ALL extracted ICAOs must agree, else abstain.
- POLY-US-04 — `tests/test_cross_issuer_station_identity.py` (Python, 9 tests) + `packages-ts/markets/tests/polymarket/cross-issuer.test.ts` (TS, 6 tests). Asserts NYC: Kalshi=KNYC vs Polymarket=KLGA + Chicago: KMDW vs KORD + namespace-isolated denylist semantics.
- POLY-US-05 — `schemas/polymarket-city-stations.json` regenerated via `scripts/export_schemas.py` (determinism `--check` green). `packages-ts/markets/src/data/generated/polymarket-city-stations.ts` regenerated via `pnpm codegen`. No hand-edits.
- POLY-US-06 — Parity-fixture pre-flight gate green (non-live dtype lock, `tests/test_parity.py::test_dtypes_match_ground_truth`). Phase 8 does NOT touch parity-locked `_internal/_pairs.py` / `_internal/merge/` — catalog-data + resolver-layer only.

**Review discipline:** Mixed Python+TS PR per REVIEW-DISCIPLINE.md routing. 4-iteration loop with codex `high` + python-architect + ts-architect dispatched in parallel:
- iter-1: codex CRITICAL (loose regex extracted "KONG" from `wunderground.com/weather/hk/hong-kong/VHHH`), python-architect 3 HIGH (regex too loose / multi-URL first-match-wins / tautological test), ts-architect CRITICAL (`city` field drift between Python + TS via `findCityForIcao` reverse-lookup).
- iter-2: codex CRITICAL (regex over-tightened — Markdown terminators broke), python-architect CRITICAL (real Polymarket URLs use `/history/daily/us/ny/new-york-city/KLGA` shape — iter-1 fix missed every real URL), ts-architect 2 HIGH (`city`/`stationMeasure` parity drift).
- iter-3: codex CRITICAL (IGNORECASE let intermediate slugs consume uppercase station segments — `/history/daily/KORD/date/KLAX` extracted KLAX). Dropped IGNORECASE entirely; case-sensitive matching pins ICAO to canonical station slot.
- iter-4: **codex + python-architect + ts-architect ALL PASS**. Loop terminated 1 iteration under the user-specified 5-iter cap.

**Test coverage delta:**
- Python: +85 tests (`test_polymarket_us_coverage.py` 18 + `test_per_event_station.py` +47 Tier 1.5 / URL coverage + `test_cross_issuer_station_identity.py` 9 + helpers). Total Python: 1743 passing (up from 1662 baseline).
- TS: +29 tests across `polymarket/{known-wrong-stations,url-extract,resolver,cross-issuer}.test.ts`. Total TS: 1228 passing (up from ~1199 baseline).

**Files modified (Python + TS, paired):**
- `packages/markets/src/tradewinds/markets/polymarket_city_stations.json`
- `packages/markets/src/tradewinds/markets/polymarket_city_citations.py` (new)
- `packages/markets/src/tradewinds/markets/polymarket.py` (KNOWN_WRONG_STATIONS)
- `packages/markets/src/tradewinds/markets/_per_event_station.py` (extract_icao_from_resolution_source + Tier 1.5 wiring)
- `packages/markets/tests/test_polymarket_us_coverage.py` (new)
- `packages/markets/tests/test_per_event_station.py` (Tier 1.5 coverage)
- `tests/test_cross_issuer_station_identity.py` (new)
- `schemas/polymarket-city-stations.json` (codegen-regenerated)
- `packages-ts/markets/src/data/generated/polymarket-city-stations.ts` (codegen-regenerated)
- `packages-ts/markets/src/polymarket/known-wrong-stations.ts` (new, hand-paired)
- `packages-ts/markets/src/polymarket/resolver.ts` (extractIcaoFromResolutionSource + Tier 1.5 wiring)
- `packages-ts/markets/src/polymarket/discover.ts` (city boundary normalization)
- `packages-ts/markets/src/polymarket/index.ts` (barrel exports)
- `packages-ts/markets/tests/polymarket/{known-wrong-stations,url-extract,resolver,cross-issuer}.test.ts` (new + updated)

**Unblocks:**
- Phase 9 (Markets Trade History) — needs Polymarket US settlement working.
- Phase 10 (Composable research()) — needs multi-contract Polymarket US resolution.

## TS-W7 Docs + Release Workflow closeout (2026-05-24)

Merge commit pending. Lands docs + Changesets + `release-ts.yml` for the four-package v0.1.0 npm publish. Waves 1+2 of the plan shipped in-tree; Waves 3-6 (npm OIDC pending-publisher registration, tagging `vts-0.1.0rc1`/`vts-0.1.0`, external README timer, browser smoke test) are operator-gated and mirror the Python Phase 4 trusted-publishing playbook.

Shipped:
- `docs/ts-quickstart.md` — Node + browser quickstart, cache wiring, Polymarket discover/settle example, Kalshi helper, discovery surface, scope of v0.1.0 vs v0.2.
- `docs/browser-integration.md` — four browser patterns (MV3 SW, MV3 content script, IIFE, Workers), CORS posture table referencing `.planning/research/TS-CORS-MATRIX.md`, CSP cleanliness, common pitfalls.
- `README.md` — top-level dual-SDK summary (Python on PyPI + TS on npm) replacing the Python-only intro.
- `.changeset/{config.json, README.md}` — Changesets configured with `fixed` group for all four packages (lockstep version bumps); `commit: false` so maintainer approves release PR; `access: public` for first-publish.
- `.github/workflows/release-ts.yml` — fires on `vts-*` tags; rc tags publish `--tag next`, non-rc tags publish `--tag latest`. Reuses Python's `parity_status.py` P0 gate for non-rc tags. OIDC trusted publishing (no NPM_TOKEN); `environment: npm` (operator creates with required reviewers).

Operator-gated follow-ups (mirrors Python Phase 4 closeout):
1. Register 4 npm OIDC pending publishers on npmjs.com — package names `@tradewinds/core`, `@tradewinds/weather`, `@tradewinds/markets`, `tradewinds`; repo `helloiamvu/tradewinds`; workflow filename `release-ts.yml`; environment `npm`.
2. Create GH repo environment `npm` with required reviewers.
3. Run `pnpm changeset` + `pnpm changeset version` to land the v0.1.0 bump PR. Confirm `@tradewinds` npm scope availability; if unavailable, fall back to unscoped per TS-SDK-DESIGN §13.1.
4. Tag `vts-0.1.0rc1` → soak `--tag next` for ≥1 week against in-repo `packages-ts/examples/chrome-extension-mvp/`.
5. External README quickstart timer (<5 min target).
6. Tag `vts-0.1.0` → publish `--tag latest` after the P0 parity-ticket gate clears.

## TS-W5 Polymarket + Kalshi Helper closeout (2026-05-24)

Merge commit: `001d855 Merge ts-w5/polymarket-markets — TS-W5 Polymarket Discover/Settle + Kalshi Helper` (`--no-ff` into main).

5 waves shipped (~14 commits including 5-iteration review loop):

- Wave 1: PolymarketClient over `gamma-api.polymarket.com`, 0.2s politeness, 429+5xx retries, offset pagination ≤10000, slug dedup. Tolerates `{data: [...]}` envelope; throws on unknown shapes. `fetchEventById` returns null on NotFoundError thrown by fetchWithRetry.
- Wave 2: Tier 0 deferred-station guard (Taipei RCTP always; HK VHHH low). Tier 1/2/3 resolution with WORD-BOUNDARY city matching (closes substring false-positives like "comparison" → paris).
- Wave 3: `polymarketDiscover()` enriches each event with city+ICAO+measure+resolution-source. Deferred markets surface with `icao: null` but PRESERVE the matched city. Empty descriptions classify as `'other'` (24h fallback).
- Wave 4: `polymarketSettle()` enforces security defenses (EVENT_ID_RE alphanumeric 1-128, 16KB description cap, netloc allowlist `{wunderground.com, weather.gov}`), publication-delay gate against station-local end-of-day via Intl.DateTimeFormat (15-min IANA offset granularity for Asia/Kolkata, Asia/Kathmandu), pulls daily extremes from `@tradewinds/core/discovery.internationalDailyExtremes`. Returns BOTH C+F values + `unit` defaulting to station-native (F for US, C for international Polymarket whole-°C buckets). dataQualityAlert compares in matching unit. Ambiguous markets ("default" measure) refused.
- Wave 5: `kalshiSettlementFor(contractId, date)` dispatches KHIGH*/KLOW* prefixes.

Polymarket subpath lives at `/polymarket` (NOT root barrel) — keeps the IIFE bundle lean. Polymarket is server-side discover/settle by design (CORS-blocked from browsers per `.planning/research/TS-CORS-MATRIX.md`).

Review discipline: 5 codex `high` iterations against the integration branch diff vs main. Findings/iter: iter-1 4 (PayloadTooLargeError catch widening, ambiguous-measure refusal, TooEarly toDict payload, half-hour tz); iter-2 2 (page shape validation, NotFoundError → null); iter-3 1 (native unit C/F); iter-4 2 (preserve city, empty-desc → other); iter-5 2 (word-boundary city match, forward signal to fetchFn). All closed in subsequent iterations. Iter-5 was the user-specified review cap.

Test coverage: 107 markets tests passing; full TS suite stable.

## TS-W6 Discovery + Snapshot + DataVersion closeout (2026-05-24)

Merge commit: `287f2b4 Merge ts-w6/discovery-snapshot-dataversion — TS-W6 Discovery + Snapshot + DataVersion` (`--no-ff` into main).

5 waves shipped at `@tradewinds/core/discovery` subpath:

- Wave 1: `availability(station, cache, opts?)` reads CacheStore via optional `listKeys`; resolves KNYC → NYC (3-letter NWS code that `research()` writes under) AND scans both forms so direct cacheKey writes are also counted. Optional `{validate: true}` confirms each candidate via `cache.get()` for TTL-aware stores.
- Wave 2: `internationalDailyExtremes(rows, opts)` — UTC → local-day rollup via `Intl.DateTimeFormat`; HALF_UP rounding (precision configurable; matches Python Decimal); RJTT/SAEZ/NZWN UTC-wrap tests pass. Guards zero-temperature buckets when `minObs=0`.
- Wave 3: `buildSnapshot(...)` + frozen `DataSnapshot` interface with `toDict()` (JSON-safe via toJsonSafe) and `toToon()` (TOON v3 tabular). schemaId/source captured into local consts so post-build opts mutation can't leak into provenance.
- Wave 4: `dataVersionFromComponents` / `dataVersionForResearch` via `crypto.subtle.digest('SHA-256', ...)`. Canonical concatenation matches Python `DataVersion.from_components` byte-for-byte (sorts schemaIds + sources internally for hash; preserves caller's tuple on the stored object).
- Wave 5: `describe(schemaId)` returns multi-line description from a built-in registry pre-seeded with the 5 v0.1.0 schemas (consumers don't need `registerSchema` for canonical schemas); `featureCatalog()` returns the transforms surface in stable order; `climateGaps` throws `ClimateGapsNotImplementedError` (TS climate cache is v0.2).

MemoryStore / IndexedDBStore / FsStore each gained `listKeys(prefix)`.

Review discipline: 5 codex `high` iterations. Findings/iter: iter-1 2 (snapshot opts-closure leak, describe registry empty for built-ins); iter-2 1 (availability missed `research()` 3-letter NWS code form); iter-3 1 (persistent stores' `listKeys` may return expired TTLs); iter-4 1 (minObs=0 + empty temps crashed); iter-5 2 (availability missed ICAO-form keys, DataVersion alphabetized stored tuple).

Test coverage: 761 core tests, +61 new (`@tradewinds/core` suite). Full TS suite stable.

## TS-W4 Mode 2 + Transforms + QC Alpha closeout (2026-05-24)

Merge commit: `0d541ec Merge ts-w4/mode2-transforms-qc-alpha — TS-W4 Mode 2 + Transforms + QC Alpha` (`--no-ff` into main).

**6 sub-plans landed (25 commits = 21 feature/test commits + 3 plan-docs + 1 inline P2 fix; review loop terminated at iter 1):**

- Plan 01 — Mode 2 dispatch at `@tradewinds/meta`: `researchBySource(station, source, fromDate, toDate)` + `Mode2Source` const-union (`'iem.archive' | 'iem.live' | 'awc.live' | 'ghcnh.archive'`) + `SOURCE_ALIASES` (canonical → bare parser-tag set) + `assertSourceIdentity(rows, expected, role?)`. Unknown source rejected BEFORE any HTTP call; `iem.live` throws v0.2 placeholder. Per-row `source` field NEVER rewritten (Python mode2.py:161-166 silent-rewrite warning preserved). Wave 1 placed Mode 2 in @tradewinds/meta (NOT @tradewinds/core) to avoid the core→weather dep cycle.
- Plan 02 — `lag`/`diff`/`diff2`/`rolling` at NEW `@tradewinds/core/transforms` subpath. `{col}_{op}_{param}` column naming. `min_periods=1` semantics. Bessel-corrected sample std (`ddof=1`). Strict numeric coercion (string `'3.5'` → `null`). Pure row→row, no input mutation.
- Plan 03 — `calendarFeatures(rows, dateCol, tz?)` with `Intl.DateTimeFormat.formatToParts` tz-aware extraction. 8 cyclical-pair columns (`month_sin/cos`, `dow_sin/cos`, `hour_sin/cos`, `day_of_year_sin/cos`). ISO Monday-first dow (`(getUTCDay() + 6) % 7`). day-of-year uses 365.0 denominator (Python transforms.py:98 parity). sin²+cos²≈1 invariant test.
- Plan 04 — `spread`/`windChill` (NWS 2001)/`heatIndex` (NWS Rothfusz 9-term)/`clipOutliers` (with `PHYSICS_BOUNDS` table). **windChill/heatIndex return tempF UNCHANGED out-of-domain** (Python parity at transforms.py:114 + :126; NOT null as REQUIREMENTS.md text said — Parity-Ticket documented in plan). NWS reference table assertions: `windChill(20, 15) ≈ 6°F`, `heatIndex(90, 70) ≈ 106°F` within 1°F. `clipOutliers` Phase 3.5 review-iter fixes preserved: `opts.std <= 0` throws `RangeError`; `sigma === 0 || !Number.isFinite(sigma)` pass-through unchanged.
- Plan 05 — `QCEngine` + 5 alpha rules at NEW `@tradewinds/core/qc` subpath. Bit positions + rule IDs CONSUMED from codegen `packages-ts/core/src/data/generated/qc-alpha-rules.ts` via `QC_ALPHA_RULES_BY_ID.get(ruleId)` — NEVER hand-coded. `obsQcStatus` Int 32-bit signed bitfield column. Defensive throw at module load if any rule's `bitPosition >= 32`. `codegen-parity.test.ts` regression-guard test asserts runtime ALPHA_RULES match codegen table byte-for-byte. obsQcStatus column uses camelCase (TS idiom); wire-format conversion to snake_case is jsonDumps' responsibility.
- Plan 06 — `crosscheckIemGhcnh(iemRows, ghcnhRows, opts={tolC: 2.0})` returns disagreement rows with `{station, eventTime, tempCIem, tempCGhcnh, deltaC}` camelCase shape. **Strict `>` boundary** (NOT `>=`): `delta === tolC` exactly produces NO disagreement (Python qc.py:228 parity). Inner-join on composite `(station, eventTime)` key. Throws on missing required columns. Empty input on either side → empty array.

**Key technical decisions:**

- **Bundle discipline**: transforms + QC ship at SUBPATHS only (`@tradewinds/core/transforms`, `@tradewinds/core/qc`); root `@tradewinds/core` barrel does NOT re-export them. Same pattern TS-W3 iter-4 H8 established. `@tradewinds/core` root bundle stays at 6.02 KB / 25 KB; meta at 19.52 KB / 30 KB.
- **Codegen-sourced QC rules**: Wave 5 imports `QC_ALPHA_RULES` and `QC_ALPHA_RULES_BY_ID` from `../data/generated/qc-alpha-rules.js`; predicates evaluate per-row and look up bit position via the codegen map. Future codegen drift (e.g., Phase 3.5 adds a 6th alpha rule) fires loud via the regression test.
- **Parity-Tickets honored**: (1) windChill/heatIndex out-of-domain returns tempF unchanged (NOT null per REQUIREMENTS.md text), (2) `obsQcStatus` camelCase (Python snake_case), (3) crosscheck disagreement row camelCase (Python snake_case), (4) TS narrows source enum to 4 canonical dotted forms (Python widens to 7-value frozenset including bare tags), (5) per-row source field PRESERVED through Mode 2 dispatch (Python silent-rewrite warning preserved).
- **`assertSourceIdentity` signature** accepts `string | ReadonlySet<string>` for `expected` so callers can pass `SOURCE_ALIASES.get(source)` to tolerate parser-emitted bare tags. `role` parameter defaults to `'observations'` (v0.2 will exercise `'forecasts'`/`'settlement'`).
- **`SourceMismatchError` already exists** in `packages-ts/core/src/exceptions/index.ts` from TS-W2 with snake_case `.toDict()` wire shape (`{ name, message, role, schema_source, data_source, catalog_warning }`). NO changes to exceptions in TS-W4 — Wave 1 consumes the existing class.

**Test coverage:** 1045 TS tests across 5 packages (was 766 at TS-W3 close; +279). codegen 6, core 694 (+232: 168 transforms + 95 qc + smoke + barrel coverage), markets 41 (unchanged), weather 218 (unchanged), meta 86 + 1 skipped + 6 todo (+35: Mode 2 + AWC date-filter regression test). All green via `CI=1 pnpm -r run test`. Typecheck clean. All four bundle artifacts under their size-limit gates.

**Review discipline:** Single-iteration loop per `.planning/REVIEW-DISCIPLINE.md` (codex `high` + TS Architect, parallel dispatch). Closed at iter-1 PASS:

- **TS Architect:** PASS clean. No CRITICAL or HIGH findings. All 15 critical parity points verified in source. All four mandated tsconfig flags hold (strict, noUncheckedIndexedAccess, exactOptionalPropertyTypes, verbatimModuleSyntax). No `as any`, no `@ts-expect-error`, no `enum`, no `import *` of heavy deps, no Node-only API in shared surface. Root barrel discipline preserved.
- **Codex high:** 1 P2 finding only (below the CRITICAL/HIGH blocking threshold). AWC Mode 2 dispatch was returning every parsed METAR from `fetchAwcMetars` without filtering by `[fromDate, toDate]` — IEM/GHCNh branches already filtered. Closed inline at `a346fc4` with regression test before merge.

**Deferred to follow-up phases (NOT blockers):**

- Forecast QC (deferred to v0.2 in both Python and TS).
- Climate QC.
- Mode 2 source `'iem.live'` (v0.1.0 parity gap — currently throws; v0.2 will add the per-month live IEM endpoint).
- Python `preprocessing.iem_crosscheck` flexible-column auto-derivation (TS narrows to `{station, eventTime, temp_c}` explicit input shape; callers normalize before calling).
- Operator: run `pnpm run capture-recordings` to populate TS-W2 msw recordings; flip parity tests from `it.todo` → live assertions.

**Outstanding for TS-W5:**

- Polymarket settlement integration (`PolymarketClient`, `polymarketDiscover`, `polymarketSettle`).
- `kalshiSettlementFor` higher-level ergonomic helper.

## TS-W3 Cache + Temporal + Validator closeout (2026-05-24)

Merge commit: `d8b4ff4 Merge ts-w3/cache-temporal-validator — TS-W3 Cache + Temporal Primitives + Validator` (`--no-ff` into main).

**7 sub-plans landed (51 commits = 14 features + 37 review-fix commits across 14 iterations):**

- Plan 01 — `CacheStore` interface + `MemoryStore` + `FsStore` at `@tradewinds/core/internal/cache` (encodeURIComponent injective key→file mapping after iter-13 C16)
- Plan 02 — `IndexedDBStore` + Web Locks API + `defaultCacheStore()` runtime auto-detect; jsdom test routing
- Plan 03 — Cache-skip rules (LST current-month, `.live`-source, 30-day volatile-window inclusive, `isWritableMonth`/`isWritableYear` strictly-past-UTC gates) + 5-case behavior fixture
- Plan 04 — `TimePoint` + `KnowledgeView<T>` + `LeakageDetector` + `assertNoLeakage` at `@tradewinds/core/temporal`; **BigInt epoch microseconds** for µs-aware comparisons (iter-11 C13); fast-check property test over `[2018-01-01, 2027-12-31]` UTC
- Plan 05 — `validateRows` consuming ajv-standalone validators (codegen-emitted, MV3-CSP-safe, no runtime ajv); 9 Python-vocabulary violations; date/date-time format post-pass; column-max retrieved_at resolution
- Plan 06 — Wire cache into `research()` (per-month read/write-through for IEM ASOS + GHCNh + per-year for CLI); 5-case skip behavior replay including RJTT UTC+9 year-wrap; ≥ 88% branch coverage gate on `@tradewinds/core`
- Plan 07 — `jsonDumps/jsonLoads` + `csvDumps/csvLoads` (stateful RFC-4180 parser preserving quoted newlines) + `toonDumps/toonLoads` (rejects non-uniform / non-primitive rows) at `@tradewinds/core/formats`

**Key technical decisions:**

- Conditional package.json `exports` field — `"node"` condition resolves `@tradewinds/core/internal/cache` to FsStore-aware entry; `"default"` (browser/MV3) resolves to `index.browser.ts` (MemoryStore + IndexedDBStore only). All three meta artifacts (`index.mjs`, `index.bundle.mjs`, `index.global.js`) clean of `node:*` / `proper-lockfile` imports.
- `LeakageError.toDict()` emits Python-isoformat (`...+00:00`, not `.000Z`) and snake_case payload.
- `SchemaValidationError.violations[].rule` uses Python vocab: `source_attr_required`, `source_column_required`, `retrieved_at_required`, `required_column_missing`, `non_nullable_has_nulls`, `mixed_null_sentinels`, `dtype_mismatch`, `enum_value_violation`, `unknown_schema_id`.
- `TimePoint` rejects naive ISO, date-only ISO, NaN/Infinity, AND impossible calendar dates (Feb 30, month 13, etc.) via round-trip check; preserves µs precision via BigInt.
- `FsStore.set` uses unique per-write temp filename (`${path}.${randomUUID()}.tmp`) so concurrent same-key writes don't race; split try/catch isolates cache.set failures from fetch failures (cache.set fails → log + preserve in-memory rows, don't degrade to null data).
- Bundle-sanity test walks BOTH static and dynamic imports across all four built artifacts (Node entry, browser entry, MV3 bundle, IIFE).
- Cache writes gated on `isWritableMonth(year, month, now)` (observations) / `isWritableYear(year, now)` (climate) — strictly-past-UTC, prevents future-month/UTC-rollover poisoning.

**Test coverage:** 766 TS tests across 5 packages (was 470 at TS-W2 close; +296). Core 451, weather 218, markets 41, codegen 6, meta 50 + 1 skipped + 6 todo. All green via `CI=1 pnpm -r run test`. Typecheck clean. All four bundle artifacts clean of Node imports.

**Review discipline:** 14-iteration loop per `.planning/REVIEW-DISCIPLINE.md` (codex `high` + TS Architect, parallel dispatch). Closed **16 CRITICAL** (C1-C16) + **21 HIGH** (H1-H21) findings:

- Iter 1: 4C (TimePoint date-only-Z, validator source map, TOON corruption, CSV roundtrip) + 4H (LeakageError ISO shape, KnowledgeView vocab, MV3 cache subbundle, vacuous test)
- Iter 2: 3C (date format ignored, FsStore race, CSV header escape) + 3H (FsStore re-export, sanity test scope, skipLive on keys)
- Iter 3: 2C (TimePoint calendar dates, assertNoLeakage skipping invalid rows)
- Iter 4: 2C (typecheck failures) + 1H (bundle size 25 KB exceeded)
- Iter 5: 2H (volatile-window wire-in + boundary off-by-one)
- Iter 6: 1C (CLI cache failures swallowed) + 2H (retrieved_at masks violations, RJTT skipped)
- Iter 7: 2H (per-month cache contract gap + GHCNh missing cache)
- Iter 8: 2H (MV3 bundle still pulled FsStore + sanity test missed dynamic imports)
- Iter 9: 2H (meta bundle picked Node condition + sanity scanned wrong artifact)
- Iter 10: 3H (IIFE bundle leak + validator retrieved_at row-0 only + skipLive vacuous v2)
- Iter 11: 1C (TimePoint µs precision via BigInt — closed the "fundamental JS limitation" deferral)
- Iter 12: 2C (future-month + future-year cache write gates)
- Iter 13: 1C (FsStore key→file non-injective)
- Iter 14: **PASS PASS** — both reviewers clean

**Deferred to follow-up phases (NOT blockers):**

- Banker's rounding vs Math.round (Python rounds half-to-even; cosmetic for current weather precision)
- Coverage gate CI config drift (the `--` separator in test-ts.yml prevents `--coverage` from reaching vitest)
- TS-BUNDLE-01 size-limit not actually wired into CI (continue-on-error step)
- Other international stations beyond RJTT in `_STATION_TZ` (TS-W6 scope)
- Operator: run `pnpm run capture-recordings` to populate TS-W2 msw recordings; flip parity tests from `it.todo` → live assertions

**Outstanding for TS-W4:**

- Mode 2 dispatch (`researchBySource`)
- Transforms (`lag`/`diff`/`rolling`/`calendarFeatures`/etc.)
- QC alpha rules + `obsQcStatus` bitfield

## TS-W2 Parity Gate closeout (2026-05-24)

Merge commit: `9d9ada0 Merge ts-w2/parity-gate — TS-W2 Parity Gate (8 plans)` (`--no-ff` into main).

**8 sub-plans landed (15 commits on the branch + 3 review-loop fix commits):**

- Plan 01 — IEM ASOS yearly-chunk fetcher + chunker + CSV parser (96 tests)
- Plan 02 — GHCNh PSV fetcher + parser + station-id translator (73 tests)
- Plan 03 — Python→JSON parity fixture exporter (5 fixtures + manifest + 5 pytests)
- Plan 04 — mergeObservations + mergeClimate canonical home at `@tradewinds/core/internal/merge` (31 tests inc. fast-check property + canonical-fetch-order replay)
- Plan 05 — buildPairs + _obsAggregates + pairsToRows at `@tradewinds/core/internal/pairs` (26 tests, 20-field PairsRow byte-shape-equivalent to Python)
- Plan 06 — research() full rewrite: all 4 sources (AWC + IEM ASOS + GHCNh + CLI) merged + buildPairs; W1 ResearchRow + null-placeholder obs_* aggregation removed (8 new integration tests)
- Plan 07 — msw recording-capture script + README (operator-gated via `TRADEWINDS_TS_LIVE=1 pnpm --filter tradewinds capture-parity`)
- Plan 08 — HARD parity test + drift-rotate-ts.yml weekly soft-fail cron

**Review discipline (per .planning/REVIEW-DISCIPLINE.md, 3-iter loop):**

- iter-1: TS Architect 2 CRITICAL (parity.test.ts forced AWC fetch via `now` override that broke msw replay; drift_capture.ts violated SC#5 SOFT-FAIL contract with outer `process.exit(2)`); Codex 1 P1 (test-ts.yml typecheck failed because subpath imports need `dist/`). Fixed: 41e6913 + b3be533.
- iter-2: TS Architect PASS; Codex 1 P1 (research.ts passed `resolved.icao` to IEM ASOS but Python uses `station.code` — would have produced empty/mismatched archive rows for cases 1+5). Fixed: d6bef33.
- iter-3: TS Architect PASS; Codex 1 P2 backwards-compat (ResearchRow type removal) — below CRITICAL/HIGH gate, deferred to TS-W3.

**Test status (post-merge, on main):**

- core: 181 tests (incl. 16 merge + 8 climate + 1 fast-check property + 6 canonical-replay + 26 pairs)
- weather: 218 tests (incl. 15 station-translator + 15 GHCNh fetcher + 43 GHCNh parser + 18 IEM ASOS fetcher + 9 IEM chunks + 34 IEM parser + 1 cli-merge re-export)
- markets: 41 tests
- meta: 27 passing + 6 todo (1 intl-station GHCNh skip blocked on TS-W6; 5 parity-test cases waiting on operator-gated Plan 07 recordings)
- codegen: 11 tests

**Operator next step:**

```bash
TRADEWINDS_TS_LIVE=1 pnpm --filter tradewinds capture-parity
git add packages-ts/meta/tests/parity/recordings/
git commit -m "ts-w2-07: capture parity recordings (5 cases)"
git push
```

Once recordings land, the parity test transitions from `todo` to HARD GATE (any case failing → CI red).

**CI change:** test-ts.yml now runs `pnpm -r run build` between `pnpm codegen` and `pnpm -r run typecheck` — required for subpath imports to resolve via `dist/`.

## TS-W1 Chrome-extension MVP closeout (2026-05-24)

Merged at the commit just landed on main. TS-W1 ships the smallest useful TS surface to unblock the Chrome extension overlay on kalshi.com: `@tradewinds/core` foundations (exceptions + convert + bounds + http + snapshot math), `@tradewinds/markets` Kalshi NHIGH/NLOW resolvers, `@tradewinds/weather` AWC + IEM CLI fetchers + parsers + `mergeClimate`, and a minimal `research()` orchestrator in `packages-ts/meta/src/research.ts` covering the AWC + CLI subset.

**Branch lineage (10 commits on top of 42e2772 TS-W0 closeout):**

- `985c930` — Wave 1+5: core exceptions (15-class hierarchy) + internal/convert + internal/bounds + internal/http (fetchWithRetry) + snapshot LST math
- `c126be4` — Wave 2: Kalshi NHIGH/NLOW resolvers + KNOWN_WRONG_STATIONS contract test
- `0a90ebc` — octopus merge Round 1
- `54016c2` — Wave 3: AWC fetcher + parser (CORS=NONE noted in header; graceful-degrade contract — never throws)
- `1d33b88` — Wave 4: IEM CLI fetcher + range + parser; consumes CLIMATE_REPORT_TYPE_PRIORITY from codegen
- `c06e46a` + `96f3f87` — Round 2 merge (with weather/src/index.ts conflict resolution)
- `dc7362d` — Wave 6+7: research() orchestrator + Chrome extension MVP smoke + size-limit config
- `c243418` — Round 3 merge
- `750411c` — vitest alias for weather (mirrors TS-W0 meta fix)
- `08eb906` — review iter-1 fixes (1 CRITICAL + 4 HIGH)

**Key technical decisions:**

- `@tradewinds/core` exports `./internal/bounds` and `./internal/convert` as subpath exports so `@tradewinds/weather` can consume without inlining (closed an iter-1 HIGH).
- `research()` lives in the meta package (`tradewinds`), NOT in `@tradewinds/core`, to avoid a core→weather circular dep.
- AWC obs are grouped by LST settlement date (via `settlementDateFor()` from snapshot), NOT DST-aware local date — matches Python `_lst_offset()`.
- CLI rows go through `mergeClimate()` (Python `merge_climate` byte-faithful port) with strict-`>` `report_type_priority` and first-seen tiebreak. Without this, preliminary→final updates would silently keep the preliminary value.
- AWC parser emits `source: "awc"` (Python schema enum short form), NOT `"awc.live"` (the catalog/orchestrator source-id is a separate concept).
- Chrome extension uses a NEW `dist/index.bundle.mjs` target with `noExternal: ['@tradewinds/core', '@tradewinds/weather', '@tradewinds/markets']` so MV3 service workers can load it without bare-specifier resolution.
- `mergeClimate()` lives in `packages-ts/weather/src/_parsers/cli.ts` (NOT a separate `merge/` module yet — that lifts in TS-W2 alongside `mergeObservations`).

**Test coverage:** 271 TS tests across 5 packages — core 124, markets 41, weather 83, meta 20, codegen 3. All green via `pnpm -r test -- --run`. Typecheck clean, biome clean.

**Size-limit results (TS-W1 SC#5: ≤ 30 KB):** core=6.02KB, weather=7.32KB, markets=1.59KB, meta=12.03KB. All well under gate. Bundle target (`index.bundle.mjs`) is 71.84KB — intentionally outside the gate; it's a single-file artifact for MV3 service workers, not the npm-published surface.

**Review discipline:** 2-iteration loop per `.planning/REVIEW-DISCIPLINE.md` (codex `high` reasoning + python-architect, parallel dispatch):

- Iter 1 (against `750411c`): REVISE — 1 CRITICAL + 4 HIGH
  - [CRITICAL codex] CLI duplicate merge ignored report priority
  - [HIGH codex] AWC obs grouped by DST-aware local date instead of LST
  - [HIGH PA] AWC parser emitted `source: "awc.live"` but schema enum is `["awc","iem","ghcnh"]`
  - [HIGH PA] Inlined bounds/convert constants in AWC parser (drift-prone)
  - [HIGH codex] Chrome extension imported ESM with bare workspace specifiers (would fail MV3)
- Iter 2 (against `08eb906`): **PASS PASS clean** (both reviewers, zero findings)

**Outstanding follow-ups (for TS-W2):**

- Lift `mergeObservations` (Python `_internal.merge.observations.merge_observations`) for AWC + IEM ASOS + GHCNh source dedup — currently TS only merges CLI.
- Add `_pairs.buildPairs` proper join (not just per-date aggregation). Python's `_pairs` is the parity-gate target.
- Wire the 5 Python parity fixtures into TS via msw recordings.
- IEM ASOS fetcher + GHCNh fetcher.
- Drift cron `drift-rotate-ts.yml`.

## TS-W0 Foundations closeout (2026-05-23)

Merge commit: `c3489b0 Merge claude/lucid-grothendieck-47fe70 (TS-W0 Foundations)` (`--no-ff` into main).

**Branch lineage (11 commits on top of `6191ff3` — TS planning closeout):**

- `d766b88` — Wave 1: pnpm workspace + 5 package scaffolds + build/test/lint
- `5a1f65c` — Wave 2: scripts/export_schemas.py + canonical schemas/ (11 files)
- `221c82e` — Wave 4: CI workflows + PR/issue templates + parity scripts
- `b6f63da` — Wave 5: TS-CORS-MATRIX.md (empirical capture)
- `207dbc1` — octopus merge of Waves 1+2+4+5
- `4c04f5a` — Wave 3: @tradewinds/codegen + 14 generated TS files
- `9379db2` — merge Wave 3
- `eda0056` — review iter-1 fixes (2 CRITICAL + 5 HIGH)
- `96c564e` — review iter-2 fix: nullable enum includes null
- `959f9af` — review iter-2 fix: biome-ignore schemas/ so exporter owns format
- `6999136` — lefthook pre-push test arg-passthrough fix

**What ships:**

- pnpm workspace at `packages-ts/` with 5 packages: `@tradewinds/core`, `@tradewinds/weather`, `@tradewinds/markets`, `tradewinds` (meta), `@tradewinds/codegen`
- TypeScript build/test/lint tooling: tsup 8.3, vitest 2.1, biome 1.9, lefthook 1.7, size-limit, TypeScript 5.6 strict mode (4 mandated flags: strict, noUncheckedIndexedAccess, exactOptionalPropertyTypes, verbatimModuleSyntax)
- `scripts/export_schemas.py` — deterministic Python→JSON Schema exporter emitting 11 canonical artifacts to `schemas/`:
  - Group A (always-emitted, 9 files): 5 JSON Schemas (observation/forecast.iem_mos/settlement.cli/observation_ledger/observation_qc) + stations.json (61 stations: 20 US + 41 intl) + kalshi-settlement-stations.json (20 cities + known-wrong) + source-priority.json + EXPORT_MANIFEST.json
  - Group B (gated, 2 files — both materialized REAL at TS-W0 time): polymarket-city-stations.json (40 cities incl. paris LFPG-high/LFPB-low) + qc-alpha-rules.json (5 rules at bit positions 0..4)
  - `--check` mode + deterministic-output unit test
- `@tradewinds/codegen` — TS-side consumer emitting 14 generated files: 5 TS schema interfaces + barrel + 3 core data modules (stations/source-priority/qc-alpha-rules) + 2 markets data modules (kalshi-stations/polymarket-city-stations) + barrels + validators placeholder (ajv-standalone deferred to TS-W3)
- CI workflows: `test-ts.yml` (pnpm + codegen + typecheck + biome + vitest + size-limit), `schema-drift.yml` (exporter+codegen → `git diff --exit-code`), `parity-ticket-check.yml` (PR-body parsing with HTML-comment + code-fence stripping)
- Sync-process artifacts: `.github/PULL_REQUEST_TEMPLATE.md`, `.github/ISSUE_TEMPLATE/parity_ticket.md`, `.github/parity-trigger-paths.json` (14 Python + 4 TS globs), `scripts/parity_status.py` (release-readiness gate), `scripts/parity_ticket_check.py` (workflow helper)
- `.planning/research/TS-CORS-MATRIX.md` — empirical capture: AWC=NONE (needs extension host_permissions or proxy); IEM-ASOS/IEM-CLI/GHCNh/Polymarket-Gamma=OPEN (`ACAO: *`)

**Test coverage:** 27 TS tests (5 packages, all green) + 12 new Python tests (export_schemas + parity_ticket_check) on top of the existing 1662 = 1686 Python tests + 27 TS tests total.

**Review discipline:** 3-iteration loop per `.planning/REVIEW-DISCIPLINE.md` (codex `high` reasoning + python-architect, parallel dispatch):

- Iter 1 (against `9379db2`): REVISE — 2 CRITICAL + 5 unique HIGH
  - [CRITICAL] Polymarket measure-specific mappings dropped (paris would silently route to LFPG instead of LFPB)
  - [CRITICAL] Parity gate bypassed by default PR template example (HTML-comment example matched the regex)
  - [HIGH ×5] Nullable columns used OpenAPI `nullable: true` vs draft-2020-12 `type: [...,"null"]`; StationInfo dropped `country` field; schema-drift workflow path filter missed `core/merge.py`; tsconfig `rootDir` + tests include → TS6059; meta package vitest couldn't resolve `@tradewinds/core` without pre-build
- Iter 2 (against `eda0056`): PA PASS clean; codex REVISE — 1 NEW HIGH
  - [HIGH] Nullable enum schemas still rejected `null` because enum array lacked it
  - [HIGH pre-existing surfaced during fixing] biome reformatted JSON; exporter wrote raw → schema-drift CI would fail
- Iter 3 (against `959f9af`): **PASS PASS clean** (both reviewers, zero findings)

Plus one post-review lefthook bug fix (`6999136`): pre-push test command — `pnpm test --run` was being intercepted by pnpm; needed `pnpm test -- --run`.

**Outstanding follow-ups (none operator-gated; tracked for TS-W1+):**

1. ajv-standalone validators deferred to TS-W3 (TS-VALIDATOR-01) — placeholder file `packages-ts/core/src/schemas/validators/index.ts` cites the work-item.
2. Bundle size-limit gate is currently `continue-on-error` (soft-gate); upgrade to hard-gate when first stable bundle ships in TS-W2.
3. Polymarket `/events` endpoint returns deprecation header pointing at `/events/keyset` (sunset 2026-05-01 already passed). Re-capture CORS against keyset endpoint in TS-W5 if the deprecation actually takes effect.

Next: `/gsd-plan-phase ts-w1` then TS-W1 execution (Chrome-extension MVP — AWC + CLI subset of research()).

## TS SDK milestone planning closeout (2026-05-23)

Merge commit: `9d6b738 Merge branch 'claude/lucid-grothendieck-47fe70'` (`--no-ff` into main, on top of `d062b3f Phase 3.4-3.6 + Mode 2 REAL impls`).

**Branch lineage (6 commits on top of the prior `c3b7504` Phase 4 closeout):**

- `fa4cee3` — initial TS planning + cross-SDK sync (14 files, 3596 insertions)
- `17bfb01` + `d117b33` — retroactive GSD wrapping as quick task 260523-thb
- `5725129` — review-iter-1 fixes (1 CRITICAL + 9 HIGH from codex + python-architect)
- `e4cf682` — review-iter-2 fixes (3 HIGH)
- `2e088a2` — review-iter-3 residual (1 HIGH)

**Documents landed:**

- `.planning/research/PYTHON-SURFACE-INVENTORY.md` (1147 lines) — Python public surface map; the spec the TS port works against
- `.planning/research/TS-SDK-DESIGN.md` (~847 lines, incl. §14 ongoing-maintenance workflow) — TS port design contract
- `.planning/CROSS-SDK-SYNC.md` (~480 lines) — binding cross-SDK sync contract: schema codegen (Group A/B taxonomy), parity-ticket workflow, MCP-sync rules (catalog-tool model matching Phase 5 PLAN-01), CI enforcement matrix, ownership model, change-process recipes
- 8 phase stubs at `.planning/phases/ts-w0..ts-w7/PLAN.md`
- Updated `ROADMAP.md` (dual-SDK overview + 8 TS phases), `PROJECT.md` (TS scope + 17 Key Decisions), `REQUIREMENTS.md` (42 TS-* requirements traceable to TS-W0..TS-W7)

**TS execution order:** `TS-W0 → TS-W1 → TS-W2 (parity gate; HARD) → TS-W3 → TS-W4 → TS-W6 → TS-W5 → TS-W7`. Strictly serial; no in-milestone parallelism (TS-POLY-03 in W5 reads `internationalDailyExtremes` from W6). Estimate 18-25 days single-lane wall-clock.

**Review discipline:** Two-reviewer loop per `.planning/REVIEW-DISCIPLINE.md` (codex `high` reasoning + python-architect, parallel dispatch). 4 iterations:

- Iter 1 (against `d117b33`): REVISE — 1 CRITICAL (TS-QC-01 alpha-rules contract mismatch with Python `ALPHA_RULES`) + 9 HIGH (output-list misalignment, missing IDs, wrong chunker reference, branch-policy contradiction, MCP-model mismatch with Phase 5, etc.)
- Iter 2 (against `5725129`): REVISE — 3 HIGH (cross-doc text-mirror drift not propagated to status table)
- Iter 3 (against `e4cf682`): REVISE — 1 HIGH (residual stale status-table row)
- Iter 4 (against `2e088a2`): **PASS PASS** (both reviewers clean, zero findings)

`.planning/REVIEW-DISCIPLINE.md` says 3-iteration cap is a smell-escalate. We exceeded it by 1 iteration (4 total). The pattern was convergent: each iteration caught a single one-line text-mirror omission, all classes of "I updated the canonical paragraph but not the cross-reference table." Acceptable here because each finding was narrowly-scoped and clearly resolved by the same family of fix (mirror the canonical text). Going forward, the parity-ticket-check.yml workflow (TS-W0 deliverable) + the schema-drift gate should catch this class earlier.

**Outstanding follow-ups (none operator-gated for this milestone planning round):**

1. When TS-W0 starts: `/gsd-plan-phase ts-w0` to expand the foundations stub into a full task breakdown.
2. CROSS-SDK-SYNC.md §8 open questions to resolve early in TS-W0: `schemas/` location, GitHub-issues-vs-files for parity tickets, `ts-architect` reviewer agent definition, `scripts/parity_status.py` impl details.

Tests: no change (planning-only round; 1662 tests still passing as of the prior `d062b3f` Phase 3.4/3.5/3.6/Mode 2 REAL closeout).

## Phase 3.4 / 3.5 / 3.6 / Mode 2 REAL implementations closeout (2026-05-23)

Four seams replaced in sequence, each through the two-reviewer loop
(codex high + python-architect). 1603 → 1662 tests (+59 net new).

**Phase 3.4 (QC engine wired into research):**

- `691b228 Merge phase-3.4: QC engine + IEM/GHCNh crosscheck`.
- `research(qc=True)` opt-in runs QCEngine + crosscheck against raw
  observations; sidecar parquet written to
  `~/.tradewinds/cache/v1/observations_qc/{station}/{YYYY}/{MM}.parquet`.

- `df.attrs["qc"]` summary (rules_fired, rows_flagged, sidecar_paths,
  crosscheck_disagreements). Mode 1 parity rows unchanged.

- New `tradewinds.weather.qc_sidecar` module.
- Iter 1 closed 2 architect HIGH (production parser column-name
  mismatch) + 2 codex P2 (same root cause).

**Phase 3.5 (transforms polish + preprocessing):**

- `11d167a Merge phase-3.5: transforms polish + preprocessing module`.
- New `tradewinds.preprocessing` module: `PHYSICS_BOUNDS`,
  `clip_outliers()`, `iem_crosscheck()` standalone.

- Added `day_of_year_sin/cos` cyclical features to `calendar_features`.
- Hypothesis property test asserts sin²+cos²≈1 across 50 examples.
- Iter 1 closed 1 architect HIGH (clip_outliers std<=0 silent collapse).

**Phase 3.6 (discovery + DataVersion + settlement primitives):**

- `922225b Merge phase-3.6: discovery + DataVersion + settlement primitives`.
- Real `climate_gaps()` (year-cache scan) + real
  `settlement_window_utc()` wrapper (was NotImplementedError seams).

- `availability()` extended with climate years + QC sidecar counts.
- `DataVersion.for_research()` factory: SHA-256 over
  `(sdk_version, schema_ids, sources, query, data_cache_fingerprint)`.

- Architect iter-1 PASS clean.

**Mode 2 (research_by_source):**

- `f4d75d7 Merge mode-2: real research_by_source`.
- Routes through `_fetch_observations_range`, filters by source via
  `_SOURCE_ALIASES` table that bridges parser-emitted bare tags
  (`iem`/`awc`/`ghcnh`) with tradewinds' canonical dotted vocabulary
  (`iem.archive`/`awc.live`/`ghcnh.archive`). Both forms accepted at
  input; per-row source preserves parser-truthful provenance.

- Iter 1 closed 1 architect CRITICAL (parser-tag mismatch — every
  production IEM/AWC call silently returned zero rows) + 1 architect
  HIGH (silent identity column rewrite) + 2 codex P1 (same root cause).

- v0.2 follow-up documented: `_fetch_observations_range` pre-merges
  per Mode 1 priority, so Mode 2 sees the post-merge view. True
  pre-merge isolation ships in v0.2.

**Tests grew 1603 → 1662 (+59 net new across 4 phases).**

## Phase 3.3 REAL implementation closeout summary (2026-05-23)

Merge commits: `1255d28 Merge phase-3.3: Polymarket Integration (Discovery + Settlement)` + `3b63870 Merge phase-3.3/review-iter2` on `main`.

Replaces the Phase 3.3 dispatch seam (both `polymarket_discover()` and `polymarket_settle()` raised NotImplementedError) with a working implementation against Polymarket's public Gamma API. Lift inspiration: mostlyright Sprint 2t s1+s4 (RESEARCH §3.3 documents the resolver architecture).

**What ships:**

- `tradewinds.markets._polymarket_client` — REST client over `gamma-api.polymarket.com`. Paginates `/events` (limit=100, dedup by slug, cap at 10k), `/events/{id}` for single lookup, polite 0.2s inter-request sleep, defensive on payload-shape changes (non-list/non-dict raises ValueError loudly).
- `tradewinds.markets.polymarket.polymarket_discover()` — returns DataFrame with one row per active weather event. Columns: `event_id, slug, title, city, icao, measure, end_time, resolution_source_type, source`. Stamps `df.attrs["source"]="polymarket_gamma"` + `df.attrs["retrieved_at"]`. Filters via per-event station resolver; events that don't match a tradewinds-known city are dropped + logged at INFO so quants can audit. Derives city from slug/title/tags for real Gamma payloads (which lack a `city` field).
- `tradewinds.markets.polymarket.polymarket_settle(event_id)` — settlement engine. Validates event_id (`[A-Za-z0-9_-]{1,128}` — accepts both numeric Gamma IDs and UUIDs), description (16 KB cap + netloc allowlist `wunderground.com` / `weather.gov`) BEFORE any HTTP fetch. Resolves station via per-event resolver, detects market measure (high/low) from event title independently of station_measure, parses settlement date from slug (last YYYY-MM-DD match), refuses ambiguous events with `PolymarketSettlementError`, enforces finalization-window delay using **station-local end-of-day** (TZ-correct for all 60 stations), defense-in-depth via `DEFERRED_STATION_MEASURES`, calls `daily_extremes()`, picks `tmax_c` or `tmin_c` per measure, returns settlement payload dict.
- `tradewinds.markets.polymarket` exceptions: `PolymarketEventError` (boundary), `PolymarketSettlementError` (resolution failures), `TooEarlyToSettleError` (carries `wait_hours` for v0.2 MCP serialization).
- `tradewinds-markets[polymarket]` optional extra — `pandas>=2.2,<3.0` + `tradewinds-weather>=0.1.0rc1,<0.2`. `_require_pandas()` + `_require_weather()` guards raise `SourceUnavailableError` with install hint when missing.

**Out of scope (deferred to v0.2 per ROADMAP):**

- Polymarket order book / fills (MARKETS-04 Sprint 0.5+).
- UMA Oracle on-chain validation.
- Taipei + HK-low markets (CWA + HKO clients — `DeferredMarketError`).
- Persistent settlement-record parquet.

**Review discipline (per .planning/REVIEW-DISCIPLINE.md):**

- Iter 1: Architect (5 HIGH closed) — UTC-vs-station-local end-of-day, defense-in-depth via DEFERRED_STATION_MEASURES, ambiguous-title silent default, slug-date-rightmost, per-row source overlay column. Codex (1 P1 + 3 P2 closed) — silent drop logging, pandas dep, weather dep, station-local TZ (covered by architect HIGH-1).
- Iter 2: Architect PASS clean. Codex (2 P1 closed) — `city` derivation from slug for real Gamma events, numeric event_id support for discover→settle round-trip.

**Tests grew 1568 → 1603 (+35 net new).**

## Phase 3.2 REAL implementation closeout summary (2026-05-23)

Merge commits: `f965cab Merge phase-3.2: Multi-Forecast Live Path (HRRR/GFS/NBM)` + `de9b3af Merge phase-3.2/review-iter3` on `main`.

Replaces the v0.1.0a1 NWP dispatch seam (`forecast_nwp` raised NotImplementedError) with a working live-fetch pipeline against NOAA Big Data Program S3 mirrors. Lift source: mostlyright Sprint 2r-impl-bundle (RESEARCH §3.2 documents the architecture).

**What ships:**

- `tradewinds.weather._fetchers._nwp_idx` — pure-Python `.idx` parser with `compute_byte_end` HEAD-resolution (closes Pitfall 1).
- `tradewinds.weather._fetchers._nwp_archive` — NOAA BDP mirror URLs (AWS + NOMADS), SSRF-allowlist gated, per-model path builders (HRRR sfcf, GFS pre/post-v16 split per Pitfall 4, NBM core), byte-range fetch with UTC-normalized cycle.
- `tradewinds.weather._fetchers._nwp_grids/{hrrr,gfs,nbm}.py` — per-model variable maps (9-row subset covering 2m temp/dewpoint/RH, 10m wind, gust, precip, surface + MSLP pressure).
- `tradewinds.weather._fetchers._nwp_extract` — cached `BallTree(haversine, radians)` station extraction with 0..360 → -180..180 longitude wrap (closes Pitfall 3).
- `tradewinds.weather.forecast_nwp` — public pipeline: mirror fallback chain, .idx + byte-range fetch (now with HTTP-failure fallback per iter-3), one-message-per-file cfgrib decode via tempdir, inline 9-rule physics-bounds QC tagging rows `clean`/`flagged`/`suspect`.
- `tradewinds.core.schemas.forecast_nwp` — `schema.forecast_nwp.v1` registered day-one with the full 7-model enum (4 ECMWF reserved for v0.2) + 8-mirror enum.
- `tradewinds.core.exceptions` — `NwpError` base + `NwpModelNotAvailableError`, `NoLiveForNwpError`, `GribIntegrityError` subclasses with `to_dict()` for v0.2 MCP serialization.
- `tradewinds-weather[nwp]` optional extra: `cfgrib>=0.9.15,<1.0`, `xarray>=2024.0`, `scikit-learn>=1.3,<2.0`, `pandas`.

**Out of scope (deferred to v0.2 per ROADMAP):**

- ECMWF Tier-2 (4 models reserved in enum; raises `NwpModelNotAvailableError`).
- Historical NWP backfill (~35 GB; requires hosted parquet mirror).
- Bitemporal `snapshot_as_of` queries (persistent ledger).
- `forecast_nwp_payloads` sidecar (replay via stored sha256+byte_range).
- Forecast-side QC sidecar (Phase 3.4 ships observation QC engine; forecast QC stays deferred).

**Review discipline (per .planning/REVIEW-DISCIPLINE.md):**

- Iter 1: Architect (4 HIGH closed) + Codex (4 P2 closed) — alias dedup, test fidelity, cfgrib model context, math clarity, UTC normalization, df.attrs, dtype, ambiguous .idx.
- Iter 2: Codex (3 P2 closed) — per-row source overlay column, empty retrieved_at attr, empty filter_records as false success.
- Iter 3: Architect PASS clean. Codex (2 P2 closed) — mirror fallback now extends to byte-range HTTP failures; issued_at/valid_at UTC-normalized.

**Tests grew 1501 → 1568 (+67 net new).**

## Phase 4 closeout summary (2026-05-23)

- **CI workflows** (CI-01, CI-02, CI-03, CI-04):
  - `test.yml` — push/PR matrix (3.11/3.12/3.13 + macOS 3.12); pytest -m "not live"; ruff check + ruff format --check; mypy --strict on `tradewinds.core/` as soft gate (continue-on-error); doctests on 4 public-surface modules; coverage-gate job with `--cov-fail-under=85` (enforced floor; 90% aspirational).
  - `wheel-metadata-check.yml` — runs on `pyproject.toml` + `scripts/check_wheel_metadata.py` changes; `uv build --all` → grep METADATA for `Requires-Dist: tradewinds >=0.1.0rc1,<0.2` semantic sentinel.
  - `release.yml` — fires on `v*` tag with `!v*rc*` negation to skip rc; 3 parallel jobs (one per distro) using `pypa/gh-action-pypi-publish@release/v1` with `environment: pypi`.
  - `release-testpypi.yml` — fires on `v*rc*` tag; identical pipeline against `https://test.pypi.org/legacy/` with `environment: testpypi`.
  - `drift-rotate.yml` — weekly Mon 07:00 UTC cron; captures `research()` for 5 parity cases into `tests/fixtures/drift/`; soft-fails (writes `drift-report.md`, opens GH issue on mismatch; NEVER blocks CI).
- **Coverage** (CI-01 SC-1): empirical 94.20% branch on `tradewinds.core` semantic surface (Validator + temporal primitives + exception hierarchy + merge + public format wrappers). `core/schemas/*` and `core/formats/_toon*` excluded per [tool.coverage.run].omit (pure-data ColumnSpec lists and lifted TOON encoder; documented as scope honesty per codex iter-4).
- **Docs** (DOCS-01, DOCS-02, DOCS-03):
  - `pytest --doctest-modules` runs on `research.py`, `knowledge_view.py`, `leakage.py`, `validator.py`. Network-bound `research()` example uses `# doctest: +SKIP`.
  - `docs/adapters/{iem,awc,cli,ghcnh}.md` — 4 adapter knowledge-resource pages (schema + gotchas + timezone notes + source-pairing rules).
  - README expanded with quickstart preamble + Mode 1 parity example + temporal primitives section + Kalshi resolver + "why local-first" rationale (DOCS-02 external timer pending operator).
- **PKG-01 rc1 prep**: versions bumped `0.1.0a1` → `0.1.0rc1` across 3 pyprojects + `__version__` strings; PEP 440 inter-package pins normalized to `>=0.1.0rc1,<0.2`; `scripts/check_wheel_metadata.py` validates with semantic lower-bound sentinel.
- **CI-05 two-tier fixtures**: `tests/fixtures/parity/` frozen + `tests/fixtures/README.md` documents the never-re-record discipline; `tests/fixtures/drift/` scaffold + capture + compare scripts + soft-fail pytest skeleton.

Review discipline:

- 6 codex review iterations against the initial 08311ef commit (PEP 440 normalize, setup-python for PEP 668, CI branch filter including integration branches, coverage scope honesty, uv.lock path inclusion, semantic METADATA lower-bound sentinel).
- Python Architect against the consolidated Wave 1 diff: PASS clean. Codex final review: only 1 P2 finding (non-blocking) re: NaN-only numeric drift edge case in `compare.py:103` — noted for follow-up.

User decisions:

- Coverage gate softened from 90% hard → 85% enforced floor, 90% aspirational. Empirical 94.20% leaves headroom.
- PyPI publish: workflows shipped but NOT gated. Operator will configure trusted publishers separately.

Outstanding follow-ups (post-merge, operator-gated):

1. Register 3 PyPI pending publishers (prod) + 3 TestPyPI pending publishers on pypi.org/manage/account/publishing/ — project names `tradewinds`, `tradewinds-weather`, `tradewinds-markets`; repo `helloiamvu/tradewinds`; workflow filename `release.yml` (prod) / `release-testpypi.yml` (test); environment `pypi` / `testpypi`.
2. Create GH repo environments `pypi` and `testpypi` with appropriate required reviewers.
3. Tag `v0.1.0rc1` → fires `release-testpypi.yml` → 3 wheels on TestPyPI.
4. External-person README quickstart timer (<5 min target per DOCS-02 SC).
5. After timer green: bump 0.1.0rc1 → 0.1.0 lockstep + tag `v0.1.0` → fires `release.yml` → 3 wheels on prod PyPI.
6. Fix codex P2: `tests/fixtures/drift/compare.py:103` — handle all-NaN `abs_diff` case (use `np.where(np.isnan(abs_diff)) | np.argwhere` fallback) so the soft-fail watchdog writes a drift report instead of `ValueError`-ing out.

Tests grew 1451 → 1453 (+2 doctest collections + drift skeleton).

## Phase 2 / 2.1 / 3 / 3.x closeout summary (2026-05-23)

- Phase 2 (CORE/CATALOG/MARKETS/PKG): `_v02/ → tradewinds.core/` rebrand
  preserving 266 tests; TradewindsError hierarchy with deprecation alias;
  KnowledgeView + LeakageDetector temporal primitives; jsonschema-backed
  Validator with source-identity invariant; 4 weather catalog adapters with
  canonical-units projection; Kalshi NHIGH/NLOW resolvers + 20-station whitelist;
  markets pkg PKG-03 pin. 10 codex review iterations + 1 architect pass.

- Phase 2.1 (LINEAGE-01..05): silver-tier observation_ledger.v1 schema +
  observation_qc.v1 sidecar; query_time_merge(silver_df, policy=LIVE_V1)
  materializes single-row-per-key gold from rows-per-source silver;
  ObservationMergePolicy properly immutable via MappingProxyType.

- Phase 3: tradewinds.mode2.research_by_source() Mode 2 dispatch seam +
  assert_source_identity() per-row check. Catalog adapter dispatch wired;
  fetch wiring deferred to Phase 3.1/3.2 alphas.

- Phase 3.1 (International) — REAL IMPLEMENTATION (merged 19d7416, replacing earlier seam):
  - SC1: STATIONS registry grew 20→60 (20 US + 40 international ICAOs);
    country field added (default 'US'); intl ghcnh_id='' since NCEI is US-only;
    is_us_station() helper for adapter-coverage gating.

  - SC2: resolve_station_for_event(event, city_map) + bundled
    polymarket_city_stations.json catalog. Paris LFPG (high) / LFPB (low)
    split lifted; ambiguous-title (both keywords) falls back to 'default';
    DeferredMarketError for Taipei + HK-low.

  - SC3: daily_extremes(station, from_date, to_date, merge='live_v1') reads
    from cached observations (read_cache), buckets by station-local IANA
    calendar day with correct UTC-month envelope across non-UTC stations,
    low_coverage gate (n_obs<12 → nulls + WARN), whole-°C precision intl /
    0.1-°C precision US.

  - SC4: schema.daily_extreme.v1 registered as 'daily_extreme' entity in
    _capabilities._SCHEMA_FILES.

  - SC5: research() rejects non-US stations with pointer to daily_extremes;
    GHCNh fetch+parse short-circuit for non-US; adapter coverage documented
    via is_us_station().

  - Review discipline: iter-1 closed 1 CRITICAL + 4 HIGH from codex + architect;
    iter-2 PASS clean.

- Phase 3.2 (NWP): SUPPORTED_NWP_MODELS = {hrrr, gfs, nbm}; forecast_nwp()
  dispatch seam with [nwp] optional-extra check.

- Phase 3.3 (Polymarket): polymarket_discover/settle with strict UUID4 +
  16KB description cap + netloc allowlist (wunderground.com, weather.gov).

- Phase 3.4 (QC): 5 ALPHA_RULES (temp/dewpoint/wind/pressure bounds) +
  QCEngine.apply() bitfield + build_sidecar_rows() + crosscheck_iem_ghcnh().

- Phase 3.5 (Transforms): lag/diff/rolling/calendar_features/spread +
  wind_chill + heat_index (NWS algorithms) + clip_outliers.

- Phase 3.6 (Discovery): DataVersion reproducibility token + availability /
  describe / feature_catalog / settlement_date_for top-level wrappers.

Tests grew 1342 → 1451 (+109 across the 6 phases). Phase 3.1 REAL impl bumped 1453 → 1501 (+48).

## Phase 1.5 closeout summary (2026-05-23)

Merge commit: `738232e Merge phase-1-5/integration: Phase 1.5 fetcher optimization + cross-source parallelism` (--no-ff on main, pushed to origin/main).

Plans shipped:

- **PLAN-01 (PERF-01/02/03)** — Lifted mostlyright PR #85 commit `cf9eb85`. Yearly chunks via shared `_iem_chunks.py` (leap-year safe), cache-window filename + `_partial` namespace, HTTP_TIMEOUT 30→60s. Tradewinds-specific deviation documented: caller's `start` is normalized to `date(start.year, 1, 1)` before the chunker fires, for cache idempotence under per-month research.py callers. Required a parity-preserving month-filter in `_fetch_iem_month` post-parse.
- **PLAN-02 (PERF-05)** — `spike/source_limits/` (3 CLI scripts + shared helpers) characterizing AWC, GHCNh, IEM concurrent-request behavior; output `.planning/research/SOURCE-LIMITS.md` with deterministic Option-C recommendation (smoke-run scale; caveat documented). Spike scripts kept under version control for v0.2 re-validation.
- **PLAN-03 (PERF-04)** — `_prefetch_sources` in research.py: 4-way ThreadPoolExecutor (Option C per SOURCE-LIMITS.md) with Pitfall-6 timing pattern (submitted_at captured immediately after ex.submit()), narrow-except contract (httpx.HTTPStatusError, httpx.RequestError, OSError only — programming bugs propagate via f.result()), current-UTC-year skip (no double-fetch), AWC-window-relevance skip (preserves no-network invariant for cached re-runs). Live perf gate: KNYC 5-year backfill 50.3s vs 720s (12 min) gate.

Review discipline (per .planning/REVIEW-DISCIPLINE.md):

- Iter 1: codex `high` + python-architect ran in parallel against the integration branch diff vs main. Returned 3 + 6 HIGH findings (overlap; 6 unique). Commit `7e26fa2` closed all six: reversed-range guard in download_iem_asos, narrowed except clauses in `_warm_*`, current-year skip, parallelism-ratio assertion in live perf test, strengthened Pitfall-6 AST scan, RuntimeError-based propagation contract test.
- Iter 2: BOTH reviewers PASS clean. No CRITICAL or HIGH findings.

Wins:

- IEM ASOS: ~12x fewer HTTP requests per backfill (monthly → yearly chunks).
- research() parity gate: 97s → 49s (~2x faster after PERF-04).
- research() KNYC 5-year live: ~14x under the ROADMAP 12-min gate.
- HTTP_TIMEOUT=60s confirmed load-bearing for GHCNh ~10 MB PSV downloads at N=4 concurrent.

Validation:

- 5-fixture parity gate (Phase 1 HARD GATE invariant): green.
- Fast suite: 976 passed, 10 deselected (live).
- Live perf gate: green.

**Phase count by milestone (post-2026-05-22 expansion):**

- v0.1.0: 12 phases (1, 1.5, 2, 2.1, 3, 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 4)
- v0.2+: 1+ phase (5 — MCP Data Platform; future phases TBD)

## Performance Metrics

**Velocity:**

- Total plans completed: 0
- Average duration: N/A
- Total execution time: 0 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| - | - | - | - |

**Recent Trend:**

- Last 5 plans: N/A
- Trend: N/A

*Updated after each plan completion*
| Phase ts-w2-parity-gate P01 | 11 | 3 tasks | 8 files |
| Phase ts-w4-mode2-transforms-qc-alpha P05 | 5min | 3 tasks | 8 files |
| Phase ts-w4-mode2-transforms-qc-alpha P06 | 7min | 2 tasks | 4 files |

## Accumulated Context

### Roadmap Evolution

- 2026-05-22: Phase 1.5 inserted after Phase 1 (Fetcher Optimization + Cross-Source Parallelism — lift mostlyright PR #85) — URGENT/optimization
- 2026-05-22: Phase 2.1 inserted after Phase 2 (Sprint 2o Lineage Refactor — per-source provenance from mostlyright PR #101) — scope expansion (prereq for 3.1/3.3)
- 2026-05-22: Phase 3.1 inserted after Phase 3 (International Station Expansion — 20 US → 60 stations via mostlyright Sprint 2t s1+s2+s3) — scope expansion
- 2026-05-22: Phase 3.2 inserted after Phase 3 (Multi-Forecast Live Path — HRRR/GFS/NBM via NOAA BDP, lift live subset of mostlyright Sprint 2r; ECMWF Tier-2 + historical backfill defer to v0.2) — scope expansion
- 2026-05-22: Phase 3.3 inserted after Phase 3 (Polymarket Integration — discovery + settlement via mostlyright Sprint 2t s1+s4; depends on Phase 3.1) — scope expansion
- 2026-05-22: Phase 3.4 inserted after Phase 3.3 (QC Engine Alpha + Sidecar + Crosscheck — lift `mostlyright/src/mostlyright/qc/`; flag-and-keep semantics + IEM/GHCNh crosscheck + 5-8 alpha rules) — scope expansion (closes biggest mostlyright→tradewinds feature gap)
- 2026-05-22: Phase 3.5 inserted after Phase 3.3 (Transforms DSL + Preprocessing Primitives — lift `mostlyright/src/mostlyright/{transforms,preprocessing}.py`; lag/diff/rolling/calendar/cross-features + `clip_outliers` + standalone `iem_crosscheck`) — scope expansion (removes the Sprint-0.5+ preprocessing defer)
- 2026-05-22: Phase 3.6 inserted after Phase 3.3 (Discovery API + Public Settlement + DataVersion — `availability()`/`climate_gaps()`/`describe()`/`feature_catalog()` + `settlement_date_for()`/`settlement_window_utc()` at top level + `DataVersion` reproducibility token) — scope expansion (closes day-one quant ergonomics gap)
- 2026-05-22: Phase 5 (MCP Data Platform) PLAN-00..PLAN-05 committed on merged-vision; execution gated on v0.1.0 ship
- 2026-05-24: Phase 7 added after Phase 5 (Ingest Auto-Planner + `tw.weather.obs()` Public Surface — `exact_window` / `warm_cache` / `hosted` strategy modes; closes the empirical 13.4 MB-for-1mo year-normalization waste documented in `.planning/research/INGEST-PLANNER-RESEARCH.md`). Numbered 7 (skipping 6) because Phase 6 (pandas3-polars) is reserved on `main` at commit `e909859` — this branch is behind main and `gsd-tools phase add` computed the next int as 6 from the local ROADMAP; fixed manually. Run `/gsd-plan-phase 7` to break down into Plans.
- 2026-05-24: Phases 8 + 9 + 10 added after Phase 7 (Markets composability initiative, paired Python + TS per Dual-SDK Rule): **Phase 8** — Polymarket US Coverage + Per-Issuer Settlement Invariants (adds US cities to Polymarket city catalog with empirically-verified Wunderground stations like NYC → KLGA NOT KNYC; adds `polymarket.KNOWN_WRONG_STATIONS` symmetric to Kalshi's denylist; Tier 1.5 URL extraction; cross-issuer assertion test — silent-corruption invariant); **Phase 9** — Markets Trade History promoting deferred MARKETS-04 from Sprint 0.5+ (`markets.kalshi.trades` candles/fills/orderbook + `markets.polymarket.trades` Gamma price history); **Phase 10** — Composable `research()` with mutually-exclusive selectors (`contract=`, `contracts=` for multi-issuer basis trade with computed `basis_f`, `city=`, `station_override=`, `sources=` / `source=`). Dependency chain: 8 → 9 → 10. `gsd-tools phase add` again numbered as 1 (it doesn't parse the `## Phases` overview's checkbox-bullet format); fixed manually following the Phase 7 precedent. Run `/gsd-plan-phase 08`, `/gsd-plan-phase 09`, `/gsd-plan-phase 10` to break down into Plans.

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- Merge mostlyright-mcp vision into tradewinds workspace, not standalone — Pending
- Defer MCP server to v0.2 — Pending
- Three-package workspace (`tradewinds`/`tradewinds-weather`/`tradewinds-markets`) — Pending
- `research()` two-mode (parity + source-explicit) — Pending
- Lift source pinned to `monorepo-v0.14.1/` tag (NOT head) — ✓ Good (Decided, per PROJECT.md Key Decisions)
- Open-Meteo NOT in v0.1 (licensing) — ✓ Good (Decided, per PROJECT.md Key Decisions)
- **v0.1.0 scope expansion (2026-05-22): include international cities + multi-forecast live + Polymarket** — Decided (user direction); ~26-day timeline extension absorbed via 4 new phases (2.1, 3.1, 3.2, 3.3)
- **2o lineage gap (per-source provenance): lift Sprint 2o into Phase 2.1** — Decided (user direction); rejected the "lossy single-source field" workaround to keep `source_tmin`/`source_tmax` provenance through to Polymarket settlement
- **ECMWF Tier-2 + historical NWP backfill: defer to v0.2** — Decided (research finding); local-first SDK can't satisfy ECMWF's 3-day rolling archive without hosted infra; Tier-1 HRRR/GFS/NBM live-fetch path ships in v0.1
- **Polymarket order book / Kalshi orderbook: stay deferred (Sprint 0.5+)** — Decided; v0.1 ships contract specs + settlement only, not paid market data
- [Phase ts-w4-mode2-transforms-qc-alpha]: QC bit positions + rule IDs CONSUMED from codegen QC_ALPHA_RULES_BY_ID; never hand-coded (TS-W4 critical-rule #4)
- [Phase ts-w4-mode2-transforms-qc-alpha]: obsQcStatus camelCase TS-side; Python uses snake_case obs_qc_status; conversion at jsonDumps wire boundary
- [Phase ts-w4-mode2-transforms-qc-alpha]: Module-load drift guard throws if QC_ALPHA_RULES.length !== ALPHA_RULES.length — Phase 3.5+ additions caught loud
- [Phase ts-w4-mode2-transforms-qc-alpha]: QC at @tradewinds/core/qc subpath only; root @tradewinds/core barrel unchanged (size 6.02 kB / 25 kB gate intact)
- [Phase ts-w4-mode2-transforms-qc-alpha]: Wave 6: crosscheckIemGhcnh uses STRICT > (NOT >=) boundary — Python qc.py:228 parity. delta === tolC produces NO disagreement.
- [Phase ts-w4-mode2-transforms-qc-alpha]: Wave 6: deltaC is ABSOLUTE (Math.abs); camelCase output keys (eventTime, tempCIem, tempCGhcnh, deltaC); Python snake_case Parity-Ticket lives at jsonDumps boundary.

### Pending Todos

Open decisions to resolve during execution (per research SUMMARY.md):

- Pandera vs jsonschema for Validator engine — Day 5 spike (Phase 2)
- `research()` import path resolution (`from tradewinds.research import research` vs `from tradewinds.api import research`) — decide before Phase 2 Day 5

### Blockers/Concerns

[Pre-execution context — risks flagged by research]

- Phase 1 Day 1 must complete the Day-1 Morning Sync addendum (7 items, ~2 hours): AWC URL smoke + PEP 420 migration + dtype ground-truth capture + version pins + `tradewinds.core` public surface stub + `TRADEWINDS_CACHE_DIR` wiring + `_vendor/__init__.py` inventory. Skipping any of these compromises the Day 3 parity gate.
- Phase 2 must hard-code `KALSHI_SETTLEMENT_STATIONS` (KNYC, KMDW, etc.) before Phase 3 migration gate — silent data corruption risk if wrong station IDs are used.
- Phase 4 PyPI trusted publishing needs three separate registrations (one per package); use PyPI "pending publisher" feature to bypass chicken-and-egg on first publish.
- **Phase 2.1 parity-fixture pre-flight gate is HARD.** Any change to `ObservationMergePolicy.apply()` MUST re-run the 5 byte-equivalent parity fixtures before merging to `merged-vision`. The strict-`>` vs strict-`>=` ambiguity that mostlyright Sprint 2o codex review caught (resolved with secondary deterministic key on `(source, observation_received_at)`) carries forward to tradewinds Phase 2.1.
- **Phase 3.1 timezone correctness is parity-critical.** `daily_extremes()` station-local IANA calendar day must handle UTC wrap correctly. Test fixtures must include at least 3 UTC-wrap edge cases (RJTT UTC+9, SAEZ UTC-3, NZWN UTC+12/13 DST). Wrong calendar day → wrong settlement → silent data corruption.
- **Phase 3.2 `cfgrib`/`eccodes` supply-chain pin floors.** New `[nwp]` optional extra adds binary toolchain deps. Pin floors documented in REQUIREMENTS.md (NWP-06). Wheel-install on macOS/Windows verified before alpha publish.
- **Phase 3.3 URL parsing is security-adjacent.** Resolution-source URLs come from untrusted Polymarket event descriptions. Strict netloc allowlist (`wunderground.com`, `weather.gov`) + 16 KB description cap + UUID4 event_id regex validation tested in the codex review pass.
- **Lift sources for new phases are in-flight (NOT yet merged to mostlyright main).** Phase 2.1 source: mostlyright `sprint2/2o-s8-backfill-and-cutover` (PR #101 — claim "merged" but the worktree shows R7 fix iterations still). Phase 3.2 source: mostlyright `sprint2/2r-impl-bundle` (PR #123 open, R8 fix stage). Phase 3.1+3.3 source: mostlyright `sprint2/2t-polymarket-international` (78 commits ahead, no PR yet). **Pin lift source to specific branch commit SHA per phase** when planning (mirrors how Phase 1 pins to `monorepo-v0.14.1`).
- **2t branch reads observations_ledger (post-2o shape).** Lifting Sprint 2t s3+s4 verbatim requires Phase 2.1 to land first. Sequencing in ROADMAP enforces this (Phase 3.1 `depends_on: Phase 2.1`).

### Quick Tasks Completed

| # | Description | Date | Commit | Directory |
|---|-------------|------|--------|-----------|
| 260522-9uj | Move pytest from pre-commit to pre-push hook | 2026-05-22 | 1589398 | [260522-9uj-move-pytest-from-pre-commit-to-pre-push-](./quick/260522-9uj-move-pytest-from-pre-commit-to-pre-push-/) |
| 260522-axd | Wire REVIEW-DISCIPLINE.md as canonical review policy source | 2026-05-22 | fb9cd61 | [260522-axd-wire-review-discipline-md-as-canonical-r](./quick/260522-axd-wire-review-discipline-md-as-canonical-r/) |
| 260522-ea7 | Fix stale STATE.md and REQUIREMENTS.md footer/decisions/phase count | 2026-05-22 | eba690a | [260522-ea7-fix-stale-state-md-and-requirements-md-f](./quick/260522-ea7-fix-stale-state-md-and-requirements-md-f/) |
| 260522-h6a | Clean up duplicate MCP-01..06 IDs in REQUIREMENTS.md per Phase 5 PLAN-00 (option b) | 2026-05-22 | e92aa36 | [260522-h6a-clean-up-duplicate-mcp-01-06-ids-in-requ](./quick/260522-h6a-clean-up-duplicate-mcp-01-06-ids-in-requ/) |
| 260522-lah | Fix 5 REVIEW-DISCIPLINE iteration 4 findings | 2026-05-22 | 5ec7fc4 | [260522-lah-fix-5-review-discipline-iteration-4-find](./quick/260522-lah-fix-5-review-discipline-iteration-4-find/) |
| 260522-lz3 | Fix 5 REVIEW-DISCIPLINE iteration 5 findings | 2026-05-22 | 0feccec | [260522-lz3-fix-5-review-discipline-iteration-5-find](./quick/260522-lz3-fix-5-review-discipline-iteration-5-find/) |
| 260522-miq | Fix 2 codex iteration 6 findings (write-wins race + class-B order) | 2026-05-22 | 6c3c282 | [260522-miq-fix-2-codex-iteration-6-findings-write-w](./quick/260522-miq-fix-2-codex-iteration-6-findings-write-w/) |
| 260522-msx | Fix 3 iter-7 findings (count drift + self-lock + non-deterministic race) | 2026-05-22 | 3d35cd2 | [260522-msx-fix-3-iter-7-findings-count-drift-self-l](./quick/260522-msx-fix-3-iter-7-findings-count-drift-self-l/) |
| 260522-n2e | Fix iter-8 P2 (migrate_to_v2 CLI needs lock around lock-free helper) | 2026-05-22 | 068c9c4 | [260522-n2e-fix-iter-8-p2-migrate-to-v2-cli-needs-lo](./quick/260522-n2e-fix-iter-8-p2-migrate-to-v2-cli-needs-lo/) |
| 260522-n7n | Fix iter-9 P1/P2 (lock parent dir + dry-run no lock touch) | 2026-05-22 | 2238b2c | [260522-n7n-fix-iter-9-p1-p2-lock-parent-dir-dry-run](./quick/260522-n7n-fix-iter-9-p1-p2-lock-parent-dir-dry-run/) |
| 260522-nbw | Apply iter-9 P1 mkdir pattern to all 3 FileLock sites (iter-10 architect) | 2026-05-22 | 1c1681d | [260522-nbw-fix-iter-10-architect-high-p1-bug-in-wri](./quick/260522-nbw-fix-iter-10-architect-high-p1-bug-in-wri/) |
| 260522-ng9 | Fix Task 1 mkdir variable name + ordering (iter-11) | 2026-05-22 | b166e2b | [260522-ng9-fix-iter-11-task-1-mkdir-uses-wrong-var-](./quick/260522-ng9-fix-iter-11-task-1-mkdir-uses-wrong-var-/) |
| 260523-thb | Retroactively register TS SDK milestone + cross-SDK sync planning work | 2026-05-23 | 17bfb01 | [260523-thb-retroactively-register-ts-sdk-milestone-](./quick/260523-thb-retroactively-register-ts-sdk-milestone-/) |
| 260524-9pq | Update REVIEW-DISCIPLINE.md to add a TypeScript Architect reviewer | 2026-05-24 | b1614f9 | [260524-9pq-update-review-discipline-md-to-add-a-typ](./quick/260524-9pq-update-review-discipline-md-to-add-a-typ/) |

## Session Continuity

Last session: 2026-05-24T16:45:18.169Z
Stopped at: Completed ts-w4-06-PLAN.md (Wave 6: crosscheckIemGhcnh)
Resume file: None
Branch state: Working on `planning/v01-intl-nwp-polymarket` off `merged-vision@d698886`. Commits not yet made — user decides when to commit. Suggested commit sequence: (a) ROADMAP + STATE updates as one commit; (b) REQUIREMENTS.md additions as separate commit; (c) PROJECT.md update as separate commit; (d) per-phase PLAN.md files in subsequent commits via `/gsd-plan-phase`.

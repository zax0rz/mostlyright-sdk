# Roadmap: tradewinds

## Overview

tradewinds is now a **dual-SDK platform** (Python + TypeScript) for prediction-market weather contracts on Kalshi (US NHIGH/NLOW) and Polymarket (US + international daily-extremes). Both SDKs call the SAME public APIs (AWC, IEM, GHCNh, NWS CLI, NOAA BDP, Polymarket Gamma) directly with no backend, mirror the SAME canonical schemas (codegen-shared via JSON Schema), and return row-equivalent output. Python ships first; TypeScript follows the same v0.1.0 surface so a Chrome extension (Rob, kalshi.com overlay) and future web dashboards can consume tradewinds in-browser.

**Status snapshot (2026-05-23):**
- **Python v0.1.0** — 12/12 phases complete on `main`, 1453 tests passing, rc1 ready to tag (operator-gated PyPI trusted-publisher setup). Three PyPI distributions: `tradewinds` / `tradewinds-weather` / `tradewinds-markets`.
- **TypeScript v0.1.0** — Planning underway (2026-05-23). 8 phases (TS-W0 → TS-W7) scoped against the Python public surface. npm topology: `@tradewinds/core` / `@tradewinds/weather` / `@tradewinds/markets` + meta `tradewinds`, pnpm workspace under `packages-ts/`.

The Python v0.1.0 release followed a ~45-day phased plan (single-lane wall-clock; ~28 days with 2 parallel lanes): **Phase A — Parity Foundation** (Days 1-9) lifted v0.14.1 parity behavior verbatim, built core primitives + catalog adapters, gated on a 5-fixture byte-equivalent parity test; **Phase B — Lineage** (Days 9.5-15.5) lifted mostlyright Sprint 2o per-source provenance refactor so observations carry per-source identity; **Phase C — Scope Expansion** (Days 16-41) wired Mode 2 dispatch + international stations (40 ICAOs) + multi-forecast live path (HRRR/GFS/NBM via NOAA Big Data Program) + Polymarket discovery & settlement + **QC engine alpha** (flag-and-keep semantics + IEM/GHCNh crosscheck) + **transforms DSL** (lag/diff/rolling/calendar/cross-features) + **discovery + public settlement + DataVersion** (ergonomic surface quants hit on session one); **Phase D — Release** (Days 42-45) shipped coverage + docs + CI/CD + v0.1.0 final.

The MCP server is deferred to v0.2 (Python phase 5); its seam (`packages/mcp/`) is scaffolded as a stub only. ECMWF Tier-2, historical NWP backfill, forecast QC, climate QC, Polymarket order book, and Kalshi orderbook clients are also deferred to v0.2 (hosted-backend gates or Sprint 0.5+ scope).

**Dual-SDK rule going forward:** Every new feature opened under this roadmap MUST have a paired TS work item once the surface lands in Python (or a paired Python work item if TS leads — rare). Schemas are codegen-shared via `scripts/export_schemas.py` writing to `schemas/json/`; manual schema duplication in TS is forbidden. New features either ship Python-first with a `paired_ts:` reference, ship simultaneously with both lanes planned in one PLAN.md, or get a `python_only: true` / `typescript_only: true` flag explaining why.

Two-lane parallel execution (Lane V / Lane F — Vu ↔ Rob) with cross-review is mandatory throughout; PR cadence is per-wave per `REVIEW-DISCIPLINE.md`. Rob's lane shifts toward TypeScript starting the TS milestone.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3, 4): Python v0.1.0 milestone work (complete)
- Decimal phases (1.5, 2.1, 3.1-3.6): Urgent insertions to Python v0.1.0 (complete)
- Phase 5+: Post-v0.1 Python milestones (v0.2+)
- **TS-W0..TS-W7**: TypeScript v0.1.0 milestone (planning — runs in parallel with Python v0.2 work)

Decimal phases appear between their surrounding integers in numeric order. TS phases sort separately under their own milestone heading.

- [ ] **Phase 1: v0.14.1 Parity Lift** - Day 1 scaffold-prep + lift v0.14.1 parsers/cache; ship 5-fixture byte-equivalent parity gate and alpha1 wheels (Days 1-4)
- [ ] **Phase 1.5: Fetcher Optimization + Cross-Source Parallelism** [INSERTED 2026-05-22] - Lift mostlyright PR #85 (365-day chunks, cache-poison fix, leap-year + UTC + HTTP_TIMEOUT) + add cross-source parallelism in `research.py` + rate-limit spike for AWC/GHCNh (Days 4.5-5.5). **Sequenced strictly between Phase 1 and Phase 2** — see architect-review notes; co-execution with Phase 2 was rejected.
- [ ] **Phase 2: Core Primitives + Catalog Adapters** - Temporal/schema/validator/leakage/exceptions/formats in `core/`; four weather adapters + Kalshi market specs; two-lane parallel build (Days 5.5-9)
- [ ] **Phase 2.1: Sprint 2o Lineage Refactor (Per-Source Provenance)** [INSERTED 2026-05-22] - Lift mostlyright Sprint 2o (PR #101): silver-tier observation ledger in **rows-per-source long format** (multiple rows per (station, observed_at), one per contributing source) + read-time `ObservationMergePolicy.apply()` materializes single-row-per-key gold for Mode 1 parity callers. Lineage columns: `source`, `parser_name`, `parser_version`, `as_of_time`, `ingestion_id`, `observation_quality` enum, `source_received_at`. Enables Phase 3.1 international + 3.3 Polymarket to record per-source identity. Parity-fixture pre-flight gate mandatory (Days 9.5-15.5)
- [ ] **Phase 3: Mode 2 Integration + Migration Gate** - `research()` Mode 2 source-explicit dispatch; cache enhancements (filelock, LST-skip, volatile window); contract tests + `mostly-light/kxhigh` dry-run migration parity (Days 16-17)
- [ ] **Phase 3.1: International Station Expansion + Observations + Daily Extremes** [INSERTED 2026-05-22] - Lift mostlyright Sprint 2t s1+s2+s3: `STATIONS` registry grows 20 US → 60 (20 US + 40 international ICAOs); per-event station resolver (Paris LFPG/LFPB split); `daily_extremes()` rollup with station-local IANA calendar; whole-°C source-precision honored for international (Days 18-20)
- [ ] **Phase 3.2: Multi-Forecast Live Path (HRRR + GFS + NBM)** [INSERTED 2026-05-22] - Lift mostlyright Sprint 2r live subset: `client.forecast_nwp(station, model, ...)` direct-fetch from NOAA Big Data Program; `.idx` byte-range + cfgrib decode + BallTree station extraction; 12-rule QC at ingest. IEM MOS stays unchanged as separate source. `[nwp]` optional extra for `cfgrib`/`xarray`/`scikit-learn`. **ECMWF Tier-2 + historical NWP backfill defer to v0.2** (hosted-backend gates) (Days 21-25)
- [ ] **Phase 3.3: Polymarket Integration (Discovery + Settlement)** [INSERTED 2026-05-22] - Lift mostlyright Sprint 2t s1+s4: `polymarket_discover()` (Gamma API, no auth) + `polymarket_settle(event_id)` settlement engine; uses internal `daily_extremes()` (Phase 3.1) as resolution source; Wunderground + NOAA WRH `resolution_source_type` markets; Taipei + HK-lowest raise `DeferredMarketError` (re-enable via CWA/HKO clients post-v0.1) (Days 26-29)
- [ ] **Phase 3.4: QC Engine Alpha + Sidecar + Crosscheck** [INSERTED 2026-05-22] - Lift `mostlyright/src/mostlyright/qc/`: QCEngine + bitfield rule registry + observation QC sidecar writer (Phase 2.1 ships the schema; 3.4 lands the engine and 5-8 alpha rules) + IEM-vs-GHCNh crosscheck. Mode 2 `research()` surfaces `obs_qc_status` bitfield column; Mode 1 stays parity-clean. Forecast QC + climate QC defer to v0.2 (Days 30-34)
- [ ] **Phase 3.5: Transforms DSL + Preprocessing Primitives** [INSERTED 2026-05-22] - Lift `mostlyright/src/mostlyright/transforms.py` + `preprocessing.py`: `tradewinds.transforms.{lag, diff, diff2, rolling, calendar_features, spread, wind_chill, heat_index}` + `tradewinds.preprocessing.{clip_outliers, iem_crosscheck}`. Baseline quant ergonomics: lag/diff/rolling stats + cyclical calendar encoding + cross-features. Removes the "Sprint 0.5+ preprocessing" defer (Days 35-38)
- [ ] **Phase 3.6: Discovery API + Public Settlement + DataVersion** [INSERTED 2026-05-22] - `tradewinds.discovery.{availability, climate_gaps, describe, feature_catalog}` answers "what do I have for KNYC?" on session one; `tradewinds.settlement.{settlement_date_for, settlement_window_utc}` exposes the math from `snapshot.py` at top level; `tradewinds.DataVersion` reproducibility token stamps every `research()` call. 3 small surface bundles — pure additive (Days 39-41)
- [ ] **Phase 4: Coverage, Docs, CI/CD, Release** - ≥90% branch coverage on `core/`; <5-min quickstart timed by external person; GH Actions trusted publishing; two-tier fixture set; v0.1.0 ship (Days 42-45)
- [ ] **Phase 5: MCP Data Platform** [Python v0.2+] - MCP server layer at `packages/mcp/` exposing tradewinds as MCP-native data platform for prediction market ML; 5-layer context-engineered data catalog; agent-generated connector pipeline; server-enforced temporal safety; multi-vertical expansion (weather → sports → politics → finance). See [`phases/05-mcp-data-platform/VISION.md`](phases/05-mcp-data-platform/VISION.md). **Post-v0.1.0; depends on Phase 2 (temporal primitives + catalog) and Phase 4 (CI/CD).**

### TypeScript SDK milestone (v0.1.0 — `@tradewinds/*` on npm)

Mirrors the Python v0.1.0 public surface from the same repo (`packages-ts/`). Same APIs, same schemas (codegen-shared), row-equivalent output (no DataFrames; plain object arrays). Primary consumer: Rob's Chrome extension overlay on kalshi.com. See [`research/TS-SDK-DESIGN.md`](research/TS-SDK-DESIGN.md) for the design contract and [`research/PYTHON-SURFACE-INVENTORY.md`](research/PYTHON-SURFACE-INVENTORY.md) for the surface map the port works against. **Runs in parallel with Python v0.2 (Phase 5) work.**

- [ ] **Phase TS-W0: Foundations + Schema Codegen + CORS Matrix** - pnpm workspace under `packages-ts/`, tsup/vitest/biome scaffolds, `scripts/export_schemas.py` Python→JSON-Schema exporter, `@tradewinds/codegen` reads `schemas/json/` and emits typed station registry + Kalshi map + ajv-standalone validators, one-shot CORS empirical test against AWC/IEM/GHCNh/Polymarket endpoints written to `.planning/research/TS-CORS-MATRIX.md`, CI workflows `test-ts.yml` + `schema-drift.yml`.
- [ ] **Phase TS-W1: Chrome-extension MVP (AWC + CLI subset of `research()`)** - Exception hierarchy, `_convert`/`_bounds` ports, retry wrapper around `fetch()`, station registry + Kalshi NHIGH/NLOW resolvers, AWC live-METAR fetcher+parser, IEM CLI fetcher+parser+range, `market_close_utc` + `settlement_*` math, minimal `research()` (AWC + CLI only, no cache). Unblocks Rob's extension overlay. Bundle ≤30KB minified+gzipped.
- [ ] **Phase TS-W2: Parity Gate** - IEM ASOS fetcher (yearly chunks, lifted from Python Phase 1.5), GHCNh fetcher (with CORS workaround), CSV/PSV parsers, `merge_observations` + `merge_climate` ports with strict-`>` priority and first-seen tiebreak, `build_pairs` join, 5 Python parity fixtures re-exported as JSON+msw recordings, parity test asserts row-equivalent output, drift cron `drift-rotate-ts.yml`.
- [ ] **Phase TS-W3: Cache + Temporal Primitives + Validator** - `CacheStore` interface + `IndexedDBStore`/`FsStore`/`MemoryStore` implementations + `defaultCacheStore()` auto-detection, LST/`.live`/30-day-volatile cache-skip rules, Web Locks API (browser) + `proper-lockfile` (Node) for `withLock`, `TimePoint`/`KnowledgeView<T>`/`LeakageDetector`+`assertNoLeakage`, `validateRows(rows, schemaId, opts)` using ajv-standalone, fast-check property tests.
- [ ] **Phase TS-W4: Mode 2 + Transforms + QC Alpha** - `researchBySource` dispatch + `assertSourceIdentity`, transforms (lag/diff/diff2/rolling/calendarFeatures/spread/windChill/heatIndex/clipOutliers) with NWS-reference-table tests, QC alpha rules (≥5: temp/dewpoint/wind/pressure bounds + METAR-corruption) populating `obsQcStatus` bitfield, `crosscheckIemGhcnh` disagreement output.
- [ ] **Phase TS-W5: Markets (Polymarket Live + Kalshi Wiring)** - Polymarket Gamma API client (rate-limit 0.2s, retries, pagination, dedup), `polymarketDiscover()` + Tier 0/1/2/3 resolver, `polymarketSettle(eventId)` engine using `internationalDailyExtremes()` resolution + half-up whole-degree rounding + `TooEarlyToSettleError`, UUID4/16KB-cap/netloc-allowlist defenses tested.
- [ ] **Phase TS-W6: Discovery + Snapshot + DataVersion** - `availability(station)` reads from `CacheStore`, `describe(schemaId)`/`featureCatalog()`, `internationalDailyExtremes(rows, {stationTz})` with UTC-wrap tests (RJTT/SAEZ/NZWN DST), `buildSnapshot(...)` + `DataSnapshot` interface + `toDict()`/`toToon()`, `DataVersion` (discovery v2 shape) via Web Crypto SHA-256, reproducibility round-trip property test.
- [ ] **Phase TS-W7: Docs + npm Publish** - README quickstart (<5min external-timer), typedoc, `docs/chrome-extension-integration.md`, Changesets + npm OIDC trusted publishing (4 pending publishers: 3 scoped + 1 meta), `release-ts.yml` workflow, tag `vts-0.1.0rc1` → npm `--tag next` for soak, then `vts-0.1.0` → npm `latest`, Chrome-extension end-to-end smoke test on `latest`.

## Phase Details

### Phase 1: v0.14.1 Parity Lift
**Goal**: Establish ground-truth parity with `mostlyright==0.14.1` by lifting parsers, cache, and merge logic verbatim — proving the Day 3 byte-equivalent gate before any new architecture is built on top.
**Depends on**: Nothing (first phase)
**Requirements**: PARITY-01, PARITY-02, PARITY-03, CORE-06, CATALOG-06, PKG-02, PKG-04, PKG-05, PKG-06, CACHE-01, CACHE-07
**Success Criteria** (what must be TRUE):
  1. All 5 byte-equivalent parity fixtures green against `mostlyright==0.14.1` (HARD GATE — Day 3): `research(station, from_date, to_date)` Mode 1 returns DataFrames matching captured fixtures on both values (`np.allclose(rtol=0, atol=0)`) AND dtypes (`df.dtypes.equals(expected_dtypes)`)
  2. `tradewinds==0.1.0a1` and `tradewinds-weather==0.1.0a1` wheels published to PyPI (Day 4); `uv build --all` produces three wheels with no `tradewinds/__init__.py` collision across distributions (PEP 420 verified)
  3. `pandas` and `pyarrow` floors pinned to `monorepo-v0.14.1` lockfile exact versions; `pandas<3.0` upper bound enforced; expected_dtypes.json captured Day 0.5 and committed as ground truth
  4. AWC `/cgi-bin/` → `/api/data/` URL migration (Sept 2025) applied as `# LIFT-FIX` in `_vendor/_awc.py`; live smoke confirms endpoint returns valid JSON
  5. `_vendor/__init__.py` documents lift inventory (per-module source path + git SHA from `monorepo-v0.14.1` worktree); cache path versioned as `~/.tradewinds/cache/v1/observations/{station}/{year}/{month}.parquet` with `TRADEWINDS_CACHE_DIR` env-var honored from first commit
**Plans**: TBD

### Phase 1.5: Fetcher Optimization + Cross-Source Parallelism
**Goal**: Make ingestion fast by default. Lift the empirically validated improvements that landed in `mostlyright` PR #85 (commit `cf9eb85`, 2026-05-12) AFTER the v0.14.1 tag we lifted from, and add cross-source parallelism in `research.py`. Verified-or-go-empirical for AWC and GHCNh rate-limit headroom.
**Depends on**: Phase 1 (parity gate green, alpha1 published — must NOT break Day 3 byte-equivalence)
**Sequencing**: **Strictly serial after Phase 1, strictly before Phase 2.** Co-execution with Phase 2 Wave 1 was rejected by architect review: both phases touch `_internal/_http.py` import graph (Wave 1 `_v02 → core` git-mv vs PERF-03 timeout bump) — concurrent edits on `merged-vision` guarantee rebase conflicts on parity-fixture test runs.
**Requirements**: PERF-01, PERF-02, PERF-03, PERF-04, PERF-05
**Success Criteria** (what must be TRUE):
  1. **IEM ASOS + MOS chunk size = 365 days** (was monthly). Calendar-aligned via shared `_iem_chunks()` helper (leap-year safe). Empirically validated: **KNYC 5-year backfill ≤12 min** wall time at unchanged 1 req/sec politeness (PR #85 measured 10 min for KNYC; allow 20% headroom for this specific station). Other-station regression check: pick one of {KMDW, KLAX, KMIA} from parity fixtures and confirm backfill completes within station-specific empirical wall time recorded during the Phase 1.5 spike — no fixed cross-station threshold.
  2. **IEM CSV staging cache filename encodes the full chunk window** (`iem_{start_iso}_{end_iso}_{suffix}.csv`) inside `_fetchers/iem_asos.py` — this is the fetcher-internal raw-CSV staging cache, **distinct from `tradewinds.weather.cache`'s path-based parquet cache** (`v1/observations/{station}/{YYYY}/{MM}.parquet`, untouched by Phase 1.5). `skip_cache=True` AND `chunk_end > today_utc` routes to `_partial` namespace that backfill never reads. Prevents the 3 cache-poisoning paths PR #85 documented.
  3. **`HTTP_TIMEOUT` bumped 30s → 60s** in `_internal._http` to match the 12x payload increase per chunk. Live smoke test: 365-day KNYC ASOS pull completes inside 60s p95.
  4. **`research.py` orchestrator fires AWC + IEM + GHCNh + NWS CLI concurrently** for the same time window via `concurrent.futures.ThreadPoolExecutor` (max_workers=4, one per source). Parallelism check: `wall_time ≤ max(per_source_t_i) * 1.2` (proves no serial stall) — replaces an earlier `≤45% of sum` threshold that architect review caught as mathematically invalid when per-source times are uneven (max-source dominates the sum).
  5. **AWC + GHCNh rate-limit headroom verified** via a one-shot spike committed under `.planning/research/SOURCE-LIMITS.md`. Documents max concurrent connections per source + actual response-size measurements (1-year, 5-year requested where API permits). Spike script kept under `spike/source_limits/` so re-validation in v0.2 is one command.

**Review panel**: 3 reviewers temporarily (codex `high` + python-architect + security) — chunk-size + cache-filename + timeout changes are parity-critical and security-adjacent (HTTP timeout × payload-size attack surface). Per `REVIEW-DISCIPLINE.md`'s lineage note: "v0.2 likely adds security-reviewer + architect as separate roles once the surface grows" — Phase 1.5 hits that threshold sooner. Codex reasoning effort is `high` (the only tier used per `REVIEW-DISCIPLINE.md` — no second-pass at lower effort).

**Parity gate handling**: chunk size affects request pattern. Merge-output sensitivity is REAL — `_internal/merge/observations.py` uses strict `>` priority comparison (first-row-seen wins on same-priority ties), so row-iteration-order from the fetcher matters at tie boundaries (SPECI-vs-METAR at same `(station, observed_at, observation_type)`, cross-source same-priority). **Mandatory pre-flight before Phase 1.5 merges to `merged-vision`**: re-run all 5 parity fixtures against 365-day-chunked `research()` output. If any fixture drifts, either (a) revert Phase 1.5 chunk-size change, OR (b) change merge to `>=` with deterministic secondary key (`source` then `chunk_start`) and re-validate. Decision is post-spike; phase doesn't merge until parity green.

**Plans:** 3 plans
- [ ] PLAN-01-lift-pr85.md — Wave 1; PERF-01/02/03; lift PR #85 verbatim (yearly chunker + _partial cache namespace + HTTP_TIMEOUT 30→60s) with TDD + pre-merge parity sweep
- [ ] PLAN-02-source-limits-spike.md — Wave 1 (parallel sub-branch); PERF-05; one-shot empirical spike of AWC + GHCNh + IEM-shared-IP concurrent tolerance → `.planning/research/SOURCE-LIMITS.md`
- [ ] PLAN-03-cross-source-parallelism.md — Wave 2 (depends on Plans 01 + 02); PERF-04; `research.py` ThreadPoolExecutor fan-out using IEM-sharing Option A/B/C chosen from SOURCE-LIMITS.md + live KNYC 5-year ≤12 min gate

### Phase 2: Core Primitives + Catalog Adapters
**Goal**: Build the architectural spine — temporal-safety primitives (`TimePoint`, `KnowledgeView`, `LeakageDetector`), schema registry with canonical schemas, source-identity Validator, exception hierarchy, format serializers, four catalog adapters wrapping `_vendor/` parsers, and Kalshi NHIGH/NLOW contract specs — all on top of the now-stable v0.14.1 parity baseline.
**Depends on**: Phase 1
**Requirements**: CORE-01, CORE-02, CORE-03, CORE-04, CORE-05, CORE-07, CORE-08, CATALOG-01, CATALOG-02, CATALOG-03, CATALOG-04, CATALOG-05, MARKETS-01, MARKETS-02, MARKETS-03, PKG-03
**Success Criteria** (what must be TRUE):
  1. `tradewinds.core.temporal.KnowledgeView` filters DataFrames by `knowledge_time <= as_of` as a plain wrapper class with `__slots__` (not a pandas accessor, not a DataFrame subclass); property tests (Hypothesis) pass with datetime range constrained to `[2018-01-01, 2027-12-31]` UTC
  2. Three canonical schemas registered eagerly via `tradewinds.core.schemas/__init__.py`: `schema.observation.v1`, `schema.forecast.iem_mos.v1`, `schema.settlement.cli.v1`; `validate_dataframe(df, schema_id)` enforces source-identity invariant and raises `SourceMismatchError` with both train/infer source names when violated
  3. All four catalog adapters (`iem`, `awc`, `cli`, `ghcnh`) wrap `_vendor/` parsers, declare `SUPPORTED_SOURCES: list[str]` at class level, emit canonical schema rows with `event_time`/`knowledge_time`/`source`/`retrieved_at` stamping; eager-import registry in `tradewinds.weather.catalog.__init__` dispatches by source ID; recorded-fixture tests green for all four
  4. `KALSHI_SETTLEMENT_STATIONS` constant hard-coded with citations (NYC=KNYC Central Park, Chicago=KMDW Midway, NOT LGA/JFK/ORD); `kalshi_nhigh` and `kalshi_nlow` contract specs map `(contract_id, date) → (settlement_source, settlement_station)` deterministically
  5. `TradewindsError` exception hierarchy with `to_dict()` for v0.2 MCP JSON-RPC serialization (`SourceUnavailableError`, `SchemaValidationError`, `SourceMismatchError`, `LeakageError`); format serializers (`dataframe`, `json`, `parquet`, `toon`, `csv`) pass roundtrip tests preserving dtypes; pandera-vs-jsonschema decision documented as Key Decision outcome after Day 5 spike
**Plans**: TBD

### Phase 2.1: Sprint 2o Lineage Refactor (Per-Source Provenance)
**Goal**: Lift mostlyright Sprint 2o (PR #101, 9 sub-sprints) into tradewinds so observations carry per-source provenance via a **rows-per-source silver-tier ledger** — multiple rows per `(station, observed_at)` with one row per contributing source — and a read-time merge policy (`ObservationMergePolicy.apply()`) that materializes the v0.14.1-equivalent single-row-per-key gold shape for Mode 1 parity callers, replacing the ingest-time strict-`>` priority. This is the prerequisite shape that Phase 3.1 international stations and Phase 3.3 Polymarket settlement (per-event resolution-source tracking) were both designed against.
**Depends on**: Phase 2 (canonical schema registry + catalog adapter pattern + exception hierarchy must exist before observation_ledger schema lands)
**Sequencing**: Strictly serial after Phase 2, strictly before Phase 3. The Mode-1 parity-fixture gate (Phase 1 Day 3) is re-asserted before merge — `ObservationMergePolicy.apply(silver_df)` MUST produce a gold_df identical to v0.14.1's `_dedup_observations()` output for the 5 parity fixtures.
**Requirements**: LINEAGE-01, LINEAGE-02, LINEAGE-03, LINEAGE-04, LINEAGE-05
**Success Criteria** (what must be TRUE):
  1. **Silver-tier ledger schema (rows-per-source long format)**: new canonical `schema.observation_ledger.v1` registered with natural key `(station, observed_at, source, parser_name, as_of_time, ingestion_id)`. **One row per `(station, observed_at, source)`** — multiple rows per `(station, observed_at)` natural key are valid silver-tier outputs (one per contributing source: AWC, IEM, GHCNh). Columns: canonical observation fields (temperature, dewpoint, wind, etc.) + 9 lineage fields (`source`, `parser_name`, `parser_version`, `ingestion_id`, `as_of_time`, `source_received_at`, `qc_status`, `observation_kind`, `provenance`, `observation_quality` enum `{clean, flagged, suspect}`). Cache writes append-only. `source_received_at` is the secondary-tiebreak column the merge consumes (per Success Criterion #2); not `observation_received_at`.
  2. **Read-time merge policy**: `tradewinds.core.merge.query_time_merge(silver_df, policy=LIVE_V1) → gold_df` materializes the single-row-per-`(station, observed_at)` shape using strict-`>` priority on `source_priority` (AWC=3, IEM=2, GHCNh=1; `ncei` reserved per D-2.1-09) with secondary deterministic key `(source_received_at, ingestion_id)`. Property-tested via Hypothesis: same `silver_df` produces byte-identical `gold_df` across invocations AND across row-shuffle permutations.
  3. **Parity gate preserved**: all 5 byte-equivalent parity fixtures from Phase 1 still pass against `research()` Mode 1 output post-refactor. Cache reader applies `ObservationMergePolicy.apply()` transparently — Mode 1 callers see no shape change.
  4. **Per-source provenance threads into `research()` Mode 2**: Mode 2 returns new columns `obs_source_tmin`, `obs_source_tmax` (one per role); `SourceMismatchError` carries per-role source identity (not collapsed). Tests for source-identity invariant updated.
  5. **Cache backward-compat**: pre-2.1 cache files (v0.14.1 single-row-per-key shape) auto-upgrade on read via a `_legacy_v014_to_v021_migration()` adapter, OR a one-time `tradewinds.weather.cache.migrate_to_v2()` CLI rewrites them. No silent data loss. QC sidecar (`observation_qc/{station}/{year}/{month}.parquet`) writes one row per QC rule firing.

**Review panel**: Standard 2-reviewer (codex `high` + python-architect) per REVIEW-DISCIPLINE.md, plus parity-fixture pre-flight gate (mandatory). Any change to merge policy MUST re-run all 5 parity fixtures before merging to `merged-vision` — same gate Phase 1.5 has. The strict-`>` vs strict-`>=` ambiguity that mostlyright Sprint 2o codex review caught (and resolved with secondary deterministic key) carries forward.

**Out of scope**:
- Climate lineage refactor (mostlyright Sprint 2p) — climate stays at v0.14.1 shape unless Phase 3.1/3.3 forces it
- Forecast lineage refactor (mostlyright Sprint 2q) — IEM MOS stays at v0.14.1 shape; Phase 3.2 introduces `forecast_nwp` ledger separately
- Hosted-backend ingest worker, S3/R2 storage, dual-write shadow ledger — local-first SDK uses parquet cache only

**Plans**: TBD (run `/gsd-plan-phase 2.1` to break down — directory: `.planning/phases/02.1-sprint-2o-lineage-refactor-per-source-provenance/`)

### Phase 3: Mode 2 Integration + Migration Gate
**Goal**: Wire `research()` Mode 2 source-explicit dispatch on top of `KnowledgeView`, complete cache policy (filelock + LST-skip + 30-day volatile window + source-identity preservation), and prove `mostly-light/strategies/kxhigh` dry-run matches `therminal-py>=1.0.7` baseline byte-for-byte (the executable ship test).
**Depends on**: Phase 2
**Requirements**: RESEARCH-01, RESEARCH-02, RESEARCH-03, RESEARCH-04, RESEARCH-05, CACHE-02, CACHE-03, CACHE-04, CACHE-05, CACHE-06, MIGRATION-01, MIGRATION-02, MIGRATION-03
**Success Criteria** (what must be TRUE):
  1. `research()` Mode 1 (no `sources` kwarg, `units="imperial"`) returns v0.14.1 parity columns and continues to pass the 5-fixture parity gate; Mode 2 (`sources={observations, forecasts, settlement}` dict) returns 6 source/retrieved_at columns and validates each role independently — `SourceMismatchError` names the offending role
  2. `research()` resolves the weather catalog via lazy `importlib.import_module("tradewinds.weather")` to break cross-package circular import; raises `SourceUnavailableError` with `pip install tradewinds-weather` install hint when weather distribution is not installed; Mode 1 emits deprecation warning starting v0.2 (test asserts warning class registered)
  3. Cache enhancements: `filelock`-guarded for concurrent writes with cloud-sync FS detection (iCloud/Dropbox → `SoftFileLock` fallback or `CacheLockTimeout`); LST current-month-skip for the station; 30-day volatile-window exclusion for archive endpoints; `*.live` endpoints never cached; cache rows preserve source-of-record `source` ID and `retrieved_at` (speedup, not a different source ID)
  4. `mostly-light/strategies/kxhigh` dry-run end-to-end against tradewinds (editable install via `python scripts/run_live_strategy.py --strategy kxhigh --dry-run --city atlanta`) matches `therminal-py>=1.0.7` baseline byte-for-byte; all 5 named `mostly-light` call sites (`client.observations`, `client.climate`, `MostlyRightMCPError` alias for `TherminalError`, `WeatherLive`, public IEM record parser) work against tradewinds
  5. `mostly-light/core/weather/sources/metar_parser.py` (local METAR JSON parsing duplication) is deleted OR documented as intentionally out of scope in tradewinds README
**Plans**: TBD

### Phase 3.1: International Station Expansion + Observations + Daily Extremes
**Goal**: Lift mostlyright Sprint 2t s1+s2+s3 so tradewinds supports international weather contracts (Polymarket-traded). `STATIONS` registry grows from 20 US-only → 60 (20 US + 40 international ICAOs across Europe, East/SE Asia, MENA, South Asia, Americas non-US, Africa, Oceania). Per-event station resolver handles Paris LFPG/LFPB split (and similar future cases). `daily_extremes()` function rolls hourly observations into per-station per-local-date TMIN/TMAX/TMEAN/precip at whole-°C precision (matches international METAR source resolution).
**Depends on**: Phase 2.1 (per-source provenance — `daily_extremes()` populates `source_tmin`/`source_tmax` for downstream Polymarket settlement) and Phase 3 (Mode 2 dispatch shape established)
**Requirements**: INTL-01, INTL-02, INTL-03, INTL-04, INTL-05
**Success Criteria** (what must be TRUE):
  1. **`STATIONS` registry expanded**: 60 `StationInfo` entries total. New international ICAOs include EGLC London, LFPG/LFPB Paris (split), EDDM Munich, EHAM Amsterdam, LIMC Milan, LEMD Madrid, EFHK Helsinki, EPWA Warsaw, RJTT Tokyo Haneda, RKSI Seoul Incheon, RKPK Pohang, CYYZ Toronto, MMMX Mexico City, MPMG Panama City, FACT Cape Town, NZWN Wellington, OEJN Jeddah, OPKC Karachi, LLBG Tel Aviv, LTAC Ankara, LTFM Istanbul, DNMM Lagos, SBGR São Paulo, SAEZ Buenos Aires, plus China/SE Asia/South Asia coverage. Each entry carries IANA `tz` (load-bearing for daily-extremes calendar-day rollup).
  2. **Per-event station resolver**: `tradewinds.markets._per_event_station.resolve_station_for_event(event, city_map) → (icao, measure)` handles Paris LFPG-highest / LFPB-lowest split (canary case from mostlyright Sprint 2t). `polymarket_city_stations.json` catalog (39 cities → 40 ICAOs) shipped as data file.
  3. **`daily_extremes()` rollup**: `tradewinds.weather.daily_extremes(station, from_date, to_date, merge="live_v1") → list[DailyExtreme]` rolls cached hourly observations into per-station per-local-date `(tmin_c, tmax_c, tmean_c, precip_inches, source_tmin, source_tmax, n_obs)` using **station-local IANA calendar day** (UTC wrap correctness — RJTT UTC+9, SAEZ UTC-3). Whole-°C precision for international (METAR source resolution); 0.1°C precision for US (T-group available). Coverage gate: `n_obs_temp_valid < 12` → tmin/tmax/tmean = null, logged `low_coverage` (not a hard fail).
  4. **Canonical `DailyExtreme` schema**: new `schema.daily_extreme.v1` registered alongside existing observation/forecast/settlement schemas. Computed at query time on the silver-tier ledger (Phase 2.1 shape); no pre-materialization in v0.1.
  5. **Catalog adapter wiring**: existing AWC/IEM/GHCNh adapters extended to handle non-US ICAOs (US-only NWS CLI adapter stays unchanged). For international stations, effective source priority drops to IEM > GHCNh (AWC METAR coverage is US-CONUS-dominated). `WeatherAdapter.SUPPORTED_STATIONS` Protocol member or similar mechanism documents coverage per adapter.

**Out of scope**:
- Polymarket discovery + settlement engine (Phase 3.3)
- Deferred markets: Taipei + HK-lowest (require CWA + HKO clients; deferred to v0.1.x via `DeferredMarketError` raise sites in `_per_event_station.py`)
- Eager 40-station historical bulk download — cache populates lazily on first `research()` call per local-first model; users can opt into bulk via explicit `prefetch()` API in v0.1.x

**Review panel**: Standard 2-reviewer (codex `high` + python-architect). Per-station timezone correctness is parity-critical; test fixtures must include at least 3 UTC-wrap edge cases (Tokyo UTC+9, Buenos Aires UTC-3, Wellington UTC+12/13 DST).

**Plans**: TBD (run `/gsd-plan-phase 3.1` to break down — directory: `.planning/phases/03.1-international-station-expansion-observations-daily-extremes/`)

### Phase 3.2: Multi-Forecast Live Path (HRRR + GFS + NBM via NOAA BDP)
**Goal**: Lift the *live direct-fetch subset* of mostlyright Sprint 2r (PR #123, 33 commits, ~21k LOC) — HRRR + GFS + NBM Tier-1 (NOAA Big Data Program, public-domain) — into tradewinds as a new catalog adapter family. `client.forecast_nwp(station, model, ...)` hits BDP via `.idx` byte-range, decodes via cfgrib, extracts via BallTree, returns a DataFrame. **Live-only, no historical backfill, no ledger, no gold materialization** — those require hosted infrastructure mostlyright has (R2) and tradewinds doesn't. IEM MOS (existing forecast source) stays separate as `iem.archive`/`iem.live`.
**Depends on**: Phase 2 (canonical schema registry + catalog adapter pattern + exception hierarchy). Independent of Phase 2.1/3.1 (no observation-ledger coupling); independent of Phase 3.3 (no Polymarket coupling).
**Requirements**: NWP-01, NWP-02, NWP-03, NWP-04, NWP-05, NWP-06
**Success Criteria** (what must be TRUE):
  1. **Canonical NWP schema**: `schema.forecast_nwp.v1` registered with 36 columns + sidecar — locks 7-model enum (`hrrr, gfs, nbm, ecmwf_ifs_hres, ecmwf_ifs_ens, ecmwf_aifs_single, ecmwf_aifs_ens`) and 8-archive-mirror enum (`aws_bdp, gcp_bdp, azure_bdp, nomads, ecmwf_data_portal, ecmwf_aws, ecmwf_azure, ecmwf_gcp`) day-one; ECMWF model values raise `NwpModelNotAvailableError` (400-equivalent) until v0.2 ships ECMWF.
  2. **Three Tier-1 adapters**: `tradewinds.weather.catalog.{hrrr, gfs, nbm}` wrap pure-Python parsers — `_nwp_idx.py` (`.idx` parser with HEAD-request EOF resolution for final byte_end), `_nwp_grids/{hrrr,gfs,nbm}.py` (cfgrib decoders + BallTree station extractors). Per-model archive starts honored (GFS 2021-01-01, NBM 2020-05-18, HRRR earliest available). NBM v5.0 cutover (2026-05-05) handled in NBM parser.
  3. **Public SDK surface**: `client.forecast_nwp(station, model=None, issued_at_from=None, issued_at_to=None, valid_at_from=None, valid_at_to=None, forecast_kind=None, qc="clean", limit=None) → pd.DataFrame` returns 37-column fixed-shape DataFrame regardless of filter. `qc` filter: `Literal["clean", "all", "include_suspect"]` (default `"clean"`). Typed exceptions: `NwpModelNotAvailableError`, `NoLiveForNwpError`, `GribIntegrityError`. Model-native units only (Kelvin/m/s/mm/Pa) — no unit-conversion helpers; quants do their own.
  4. **QC engine alpha**: 12 physics-bounds + cross-cycle continuity rules per model, run at fetch time, populate `qc_status` enum `{clean, flagged, suspect}` per row. `tradewinds.weather.qc.rules_nwp.QC_RULES_NWP: dict[NwpModel, list[QCRule]]` typed for all 7 models day-one (ECMWF rules registered but unreachable until v0.2).
  5. **Optional install**: `tradewinds-weather[nwp]` extra adds `cfgrib>=0.9.10`, `xarray>=2024.0`, `scikit-learn>=1.3`. Default install stays lean (no GRIB2 toolchain). Per-station cache at `~/.tradewinds/cache/v1/forecast_nwp/{model}/{station}/{year}/{month}.parquet` mirrors observations cache pattern; cache is best-effort (not source-of-truth — re-fetch via stored `(sha256, byte_range)` always available).

**Out of scope (deferred to v0.2)**:
- **ECMWF Tier-2** (IFS HRES, IFS ENS, AIFS Single, AIFS ENS): rolling 2-3 day upstream archive means bytes are unrecoverable after 3 days — only a hosted backend that ingested at the time can serve historical ECMWF queries. CC-BY-4.0 5-channel attribution gate also presupposes hosted dataset surface.
- **Historical NWP backfill** (~35 GB Tier-1 across HRRR+GFS+NBM × 20 stations × 8 years): no quant wants 35 GB on their laptop. v0.2 adds a hosted parquet mirror with byte-range API for "fetch only what you need" historical access.
- **Bitemporal `snapshot_as_of` queries**: requires persistent ledger; v0.2.
- **Live polling worker + heartbeat + quarantine sidecar alerts**: ops infrastructure; not a local-SDK concern.
- **Gold-tier materialization + cutover env flag**: no ledger → no gold layer.

**Review panel**: Standard 2-reviewer (codex `high` + python-architect). New optional-deps surface adds supply-chain attack surface — `cfgrib` + `eccodes` pin floors documented in REQUIREMENTS.md.

**Plans**: TBD (run `/gsd-plan-phase 3.2` to break down — directory: `.planning/phases/03.2-multi-forecast-live-path-hrrr-gfs-nbm-via-noaa-bdp/`)

### Phase 3.3: Polymarket Integration (Discovery + Settlement)
**Goal**: Lift mostlyright Sprint 2t s1+s4 so tradewinds can answer "which Polymarket weather contract bucket resolves YES, with full lineage." `client.polymarket_discover() → list[event]` enumerates active markets via the Polymarket Gamma API (no auth, public REST). `client.polymarket_settle(event_id) → PolymarketSettlementRecord` uses internal `daily_extremes()` (Phase 3.1 output) as the resolution source and returns the bucket + lineage chain. Both Wunderground and NOAA WRH `resolution_source_type` markets supported.
**Depends on**: Phase 2.1 (per-source provenance — settlement records carry per-source observation identity) and Phase 3.1 (international stations + `daily_extremes()` + `_per_event_station.py` resolver). Independent of Phase 3.2 (Polymarket settles on observations, not forecasts).
**Requirements**: POLY-01, POLY-02, POLY-03, POLY-04, POLY-05
**Success Criteria** (what must be TRUE):
  1. **`PolymarketClient`**: REST client over `https://gamma-api.polymarket.com`. No auth. ~300 LOC. User-Agent header required (Cloudfront 403s on blank UA). 0.2 s rate limit (~300 req/min ceiling), `asyncio.Lock`-serialized, retries on 429+5xx, paginates `/events` by `offset += 100`, caps at 10000 events, dedups by slug. Honors public REST contract — no order book, no fills (those stay deferred as `MARKETS-04` Sprint-0.5+).
  2. **Discovery + Tier 0/1/2/3 resolver**: `polymarket_discover() → list[event_metadata]` returns active weather events. `polymarket_discovery.extract_resolution_station(event, city_map)` chains Tier 0 (deferred hard-stop for Taipei + HK-lowest → raises `DeferredMarketError`) → Tier 1 `resolutionSource` URL match (Wunderground/NOAA WRH regex) → Tier 2 description URL match → Tier 3 catalog fallback via `_per_event_station.resolve_station_for_event()`. Drops 11 US slugs already covered by the existing US station registry.
  3. **`PolymarketSettlementRecord` schema**: new `schema.polymarket_settlement_record.v1` registered (sibling of Kalshi-shaped `settlement_record.json`, existing one untouched). Surfaces BOTH `settlement_value_c` and `settlement_value_f` always. Records `resolution_source_type` enum `{wunderground, noaa_wrh, hko, cwa, other}` (per-event resolution source — distinct from per-row observation source).
  4. **Settlement engine**: `client.polymarket_settle(event_id) → PolymarketSettlementRecord` parses `event.description` (16 KB cap — ReDoS defense), extracts `(bucket_definitions, resolution_source_type, resolution_icao, observation_date)` (date from `event.slug`, NOT `event.endDate`), reads from `daily_extremes()` for `(resolution_icao, observation_date)`, rounds half-up to whole-degree-native at settle step, matches bucket. Refuses to settle with `TooEarlyToSettleError` until per-source finalization delay elapses (Wunderground 6h, NOAA WRH 4h, default 24h). Tolerance per Polymarket §22: ≤1°F / 0.6°C between tradewinds' value and Polymarket's published value emits `data_quality_alert` (does not raise).
  5. **Exception hierarchy**: `PolymarketError` (base) → `DeferredMarketError`, `ResolutionParseError`, `EventNotFound`, `TooEarlyToSettleError`. All subclass `TradewindsError` and carry `to_dict()` for v0.2 MCP JSON-RPC serialization. Allowlisted URL netlocs hardcoded: `wunderground.com`, `www.wunderground.com`, `weather.gov`, `www.weather.gov`.

**Out of scope**:
- **Polymarket order book / fills / paid market data** (stays as `MARKETS-04` Sprint 0.5+)
- **UMA Oracle on-chain validation** (deferred — Polymarket's own settlement mechanism; tradewinds settles via the documented resolution source independently)
- **Taipei + HK-lowest markets** (require CWA + HKO clients with their own API keys; deferred to v0.1.x via the `DeferredMarketError` pattern — mostlyright Sprint 2u TODO documents the path: CWA station `466920` Songshan with `MOSTLYRIGHT_CWA_API_KEY` from opendata.cwa.gov.tw; HKO XML endpoint `dailyExtract_YYYYMM.xml`)
- **Persistent settlement-record parquet** (settlements compute on-demand; no `settlements_ledger/` table in v0.1)
- **Settlement DoS guards from the hosted API** (60 req/min/IP, 5-min negative cache, 100 distinct event_ids/IP/hour caps) — moot in single-process local SDK; replaced by an in-memory LRU for the negative-cache pattern

**Review panel**: Standard 2-reviewer (codex `high` + python-architect). URL-parsing logic is security-adjacent (resolution-source URLs come from untrusted Polymarket event descriptions); strict netloc allowlist + 16 KB description cap + UUID4 event_id validation tested in the codex pass.

**Plans**: TBD (run `/gsd-plan-phase 3.3` to break down — directory: `.planning/phases/03.3-polymarket-integration-discovery-settlement/`)

### Phase 3.4: QC Engine Alpha + Sidecar + Crosscheck
**Goal**: Lift mostlyright `src/mostlyright/qc/` package — QC engine + bitfield rule registry + observation QC sidecar + IEM-vs-GHCNh crosscheck — so tradewinds users get **flag-and-keep** semantics instead of the current clean-or-discard. Phase 2.1 ships the QC sidecar schema + writer hooks but NO rules; Phase 3.4 lands the engine and the alpha rule set so the sidecar actually gets written to. Forecast QC and climate-specific QC stay deferred to v0.2.
**Depends on**: Phase 2.1 (QC sidecar schema must exist; rows-per-source ledger semantics fixed). Independent of Phase 3.1/3.2/3.3 — runs in parallel with those after Phase 2.1 lands.
**Requirements**: QC-01, QC-02, QC-03, QC-04, QC-05
**Success Criteria** (what must be TRUE):
  1. **QC engine + bitfield rule registry**: `tradewinds.weather.qc.engine.QCEngine` ports `mostlyright/src/mostlyright/qc/engine.py` verbatim. `QCFlag` registry assigns each rule a power-of-2 bitfield ID; a row's `obs_qc_status` bitmask records every rule it tripped (allows "flagged AND suspect" composition). `QCEngine.run(rows) → list[QCEntry]` returns one sidecar entry per rule firing per row.
  2. **Observation QC sidecar populated**: `tradewinds.weather.qc.sidecar.ObservationQCSidecar.write_entries(entries, station, year_month)` writes to `~/.tradewinds/cache/v1/observations_qc/{station}/{YYYY}/{MM}.parquet` (path established by Phase 2.1 LINEAGE-05). Sidecar schema: `(observed_at, source, rule_id, severity {info|warn|fail}, message, value_at_fire, expected_range, fired_at)`. Sidecar join-key compatible with silver ledger.
  3. **IEM-vs-GHCNh crosscheck**: `tradewinds.weather.qc.crosscheck.iem_ghcnh_crosscheck(silver_df) → list[QCEntry]` ports `mostlyright/src/mostlyright/qc/crosscheck.py`. Fires `crosscheck_disagreement` (severity=warn) when same `(station, observed_at)` IEM + GHCNh rows disagree beyond per-field tolerance (temp ±1°C, dewpoint ±2°C, wind_speed ±2.5 m/s). Tolerances documented in source citing mostlyright spec.
  4. **Alpha rule set (5-8 rules)**: At minimum: (a) `temp_out_of_physics` (-50°C..+60°C); (b) `dewpoint_gt_temp` (dewpoint > temp impossible); (c) `wind_speed_negative_or_huge` (<0 or >100 m/s); (d) `pressure_out_of_physics` (<870 hPa or >1085 hPa); (e) `crosscheck_disagreement` (from §3); (f) `metar_corrupted_groups` (parser detected unrecoverable METAR codes). Each rule has a `# LIFT` comment citing the mostlyright function it ports.
  5. **`research()` Mode 2 surfaces qc_status**: Mode 2 DataFrames carry an `obs_qc_status` column (bitfield int) per role; documented in research() docstring. Mode 1 stays unchanged (no QC column leakage to maintain parity gate). Users can join sidecar back via `(observed_at, source)` for rule-firing details.

**Out of scope** (v0.2 follow-up):
- `qc/forecast_sidecar.py` + `qc/forecast_rules.py` — forecast QC sidecar/rules (v0.15.0 mostlyright work; tradewinds v0.2 with multi-forecast historical backfill)
- `qc/rules_climate.py` — CLI-specific guards and Kalshi reconciliation rules (depends on settlement-time finality semantics that Phase 3.3 doesn't fully cover)
- Quarantine sidecar (mostlyright `forecast_nwp_quarantine` shape) — ops infrastructure, not local-SDK
- Active alerting + heartbeat — ops infrastructure

**Review panel**: Standard 2-reviewer (codex `high` + python-architect). QC rule physics bounds are parity-adjacent — if rules fire on the 5 parity fixtures, ROADMAP'd parity gate still must pass (rules ADD `obs_qc_status` column but MUST NOT mutate observation rows).

**Plans**: TBD (run `/gsd-plan-phase 3.4` to break down — directory: `.planning/phases/03.4-qc-engine-alpha-sidecar-crosscheck/`)

### Phase 3.5: Transforms DSL + Preprocessing Primitives
**Goal**: Lift mostlyright `transforms.py` (temporal feature engineering DSL) + `preprocessing.py` (physics-bounds outlier clipping + standalone crosscheck) so tradewinds ships baseline quant ergonomics. Lag/diff/rolling stats + cyclical calendar encoding + cross-features (wind_chill, heat_index, spread) are table-stakes for any temperature model — ROADMAP previously deferred these to "Sprint 0.5+" with no DSL plan; now they ship in v0.1.0.
**Depends on**: Phase 2 (canonical schema registry + format serializers — DSL operates on DataFrames returned by `research()`). Independent of Phase 2.1/3.1/3.2/3.3/3.4 — pure functional layer on top.
**Requirements**: TRANSFORM-01, TRANSFORM-02, TRANSFORM-03, TRANSFORM-04
**Success Criteria** (what must be TRUE):
  1. **Transforms DSL** at `tradewinds.transforms.*`: ports `mostlyright/src/mostlyright/transforms.py`. Public functions: `lag(df, col, n)`, `diff(df, col, n=1)`, `diff2(df, col)`, `rolling(df, col, window, agg={"mean","median","min","max","std","count"})`. All chain-friendly (return DataFrames); column-naming convention `{col}_{op}_{param}` (e.g., `temp_c_lag_3`, `temp_c_rolling_24h_mean`). Documented in docstrings with NumPy-style examples.
  2. **Calendar features**: `tradewinds.transforms.calendar_features(df, ts_col="observed_at") → df` adds `day_of_year_sin`, `day_of_year_cos`, `hour_sin`, `hour_cos` (radians from `2 * pi * (value / period)`). Uses station-local IANA timezone from station registry (Phase 3.1 dependency: international stations get correct local calendar/hour). 12-row Hypothesis property test asserts sin² + cos² ≈ 1 for all rows.
  3. **Cross-features**: `tradewinds.transforms.spread(df, "tmax", "tmin")`, `tradewinds.transforms.wind_chill(df, temp_col, wind_col)`, `tradewinds.transforms.heat_index(df, temp_col, rh_col)` — physics formulas with citations (NWS heat index polynomial, Joint Action Group wind chill). Refuses to compute outside formula validity domains (heat_index requires temp ≥ 27°C; wind_chill requires temp ≤ 10°C AND wind ≥ 4.8 km/h) — raises `OutOfDomainError`.
  4. **Preprocessing primitives** at `tradewinds.preprocessing.*`: ports `mostlyright/src/mostlyright/preprocessing.py`. Public: `clip_outliers(df, col, bounds=None) → df` (physics-based defaults; ports the `_internal/_bounds.py` constants); `iem_crosscheck(silver_df, *, tolerance="default") → list[QCEntry]` (standalone-callable version of Phase 3.4's crosscheck — quants can run after `research()` without going through QC engine). Both NumPy-docstring documented.

**Out of scope**:
- ML feature pipelines / fit-transform sklearn-style estimators — let user own this layer
- Time-series imputation (missing-value fill) — domain decision per quant
- Per-station model templates — out of scope, user owns modeling

**Review panel**: Standard 2-reviewer (codex `high` + python-architect). Cross-feature formulas (heat_index, wind_chill) get extra scrutiny — wrong formulas produce silently-bad features. Tests must compare against published NWS reference tables.

**Plans**: TBD (run `/gsd-plan-phase 3.5` to break down — directory: `.planning/phases/03.5-transforms-dsl-preprocessing-primitives/`)

### Phase 3.6: Discovery API + Public Settlement + DataVersion
**Goal**: Bundle three small surface additions that close ergonomic gaps quants hit on session one: (a) **discovery API** answers "what do I have for KNYC?" with `availability()`, `climate_gaps()`, `describe()`, `feature_catalog()`; (b) **public settlement primitives** expose `settlement_date_for(utc_moment)` and `settlement_window_utc(settlement_date)` at the `tradewinds.*` top level (math lives in `snapshot.py` but never surfaces); (c) **`DataVersion` reproducibility token** — same query + same `DataVersion` = identical bytes, useful for backtest pinning.
**Depends on**: Phase 2 (catalog adapters registered), Phase 2.1 (per-source provenance — `availability()` returns per-source coverage). Independent of Phase 3.1-3.5 — pure additive surface.
**Requirements**: DISCOVERY-01, DISCOVERY-02, DISCOVERY-03, SETTLEMENT-API-01, VERSION-01
**Success Criteria** (what must be TRUE):
  1. **Discovery API public surface** at `tradewinds.discovery.*`:
     - `availability(station: str) → AvailabilityRecord` returns `(station, observation_range, climate_range, forecast_range, per_source_coverage: dict[source, (start, end, row_count)])`. Sourced from silver-tier ledger + climate parquet metadata.
     - `climate_gaps(station: str, from_date, to_date) → list[DateRange]` returns missing-date ranges. Ports `mostlyright/src/mostlyright/discovery.py:climate_gaps()`.
     - `describe(station: str) → str` returns human-readable Markdown: station metadata + ICAO + tz + lat/lon + coverage summary + known-issues. Ports `mostlyright/src/mostlyright/discovery.py:describe()`.
     - `feature_catalog() → list[FeatureSpec]` returns structured feature registry (observation columns + transforms surface + cross-features). Each `FeatureSpec` has `(name, dtype, units, source, transform_chain, settlement_role)`. Ports mostlyright `catalog.py` minus the Kalshi-specific settlement annotations (those stay v0.2 per Phase 5 PLAN-02).
  2. **Public settlement primitives** at `tradewinds.settlement.*`:
     - `settlement_date_for(utc_moment, station: str) → date` — given a UTC moment + station, returns the Kalshi-settlement-calendar date it falls into (handles DST + station-local-day rollover). Lifts math from existing `snapshot.py`.
     - `settlement_window_utc(settlement_date: date, station: str) → tuple[datetime, datetime]` — given a settlement date + station, returns the `(start_utc, end_utc)` window of observations that resolve that date's NHIGH/NLOW. Already used internally; just surfaced.
     - Both functions documented with examples covering: spring-forward DST transition (NYC 2024-03-10), fall-back DST transition (NYC 2024-11-03), and a non-DST station (PHX, no transitions).
  3. **`DataVersion` token + cache-layer stamping**:
     - `tradewinds.DataVersion(content_hash: str, schema_version: str, lift_sha: str, fetched_at: datetime)` — frozen dataclass. Computed at every `research()` call. Available via `client.data_version()` or as `df.attrs["data_version"]` on returned DataFrames.
     - `content_hash` = sha256 over (silver-tier rows AS-OF the call). `schema_version` = canonical schema versions concatenated. `lift_sha` = mostlyright lift SHA from `_lift_inventory.py`. `fetched_at` = wall-clock at fetch.
     - Round-trip property: `research(...)` called twice with same args + same `DataVersion` returns byte-identical DataFrames (Hypothesis-tested).
  4. **Documentation**: each new public surface gets a docs/api/{module}.md page; README quickstart updated to show `availability()` and `DataVersion` usage in <50 lines.

**Out of scope**:
- Kalshi-specific settlement field annotations in `feature_catalog()` — defer to Phase 5 PLAN-02 (MCP catalog format)
- Polymarket-specific catalog entries — same
- Cross-station discovery (`available_stations(market="kalshi_nhigh") → list[Station]`) — defer to v0.1.x

**Review panel**: Standard 2-reviewer (codex `high` + python-architect). Settlement window math is settlement-correctness-critical; tests must include the 3 DST edge cases (spring-forward, fall-back, non-DST) + at least 2 international stations (Phase 3.1 dependency: tz from station registry).

**Plans**: TBD (run `/gsd-plan-phase 3.6` to break down — directory: `.planning/phases/03.6-discovery-api-public-settlement-dataversion/`)

### Phase 4: Coverage, Docs, CI/CD, Release
**Goal**: Meet the ≥90% branch-coverage gate on `tradewinds.core`, ship documentation that a fresh installer can follow in <5 minutes, stand up GitHub Actions with PyPI trusted publishing and two-tier fixture rotation, and tag v0.1.0 final on Day 14.
**Depends on**: Phase 3
**Requirements**: PKG-01, DOCS-01, DOCS-02, DOCS-03, CI-01, CI-02, CI-03, CI-04, CI-05
**Success Criteria** (what must be TRUE):
  1. CI reports ≥90% branch coverage on `tradewinds.core.*` (HARD GATE — Day 12); 80% line coverage on `catalog/` and adapter wrappers; lifted `_vendor/` retains monorepo-v0.14.1 coverage
  2. README quickstart works end-to-end in <5 minutes for a fresh installer, timed by an external person (not the author); `pytest --doctest-modules` passes on NumPy-style docstrings for `research()`, `KnowledgeView`, `Validator`, `LeakageDetector`; one adapter knowledge-resource page per adapter in `docs/adapters/` (schema, gotchas, timezone notes, source-pairing rules)
  3. Three PyPI distributions tagged and published at v0.1.0: `tradewinds`, `tradewinds-weather`, `tradewinds-markets`; trusted publishing configured per package; GH Actions workflow `release.yml` triggers on `v*` tag and publishes via `astral-sh/trusted-publishing-examples` pattern
  4. Pre-publish METADATA grep CI step inspects each built wheel's `Requires-Dist` and fails the build if explicit version range for sibling `tradewinds-*` packages is missing (`tradewinds-weather>=0.1.0,<0.2` etc.); `pytest -m "not live"` runs in CI on every push; `@pytest.mark.live` tests excluded from CI; pre-commit hooks (`ruff check --fix` + `ruff format` + optional `mypy --strict` on `core/`) enforced, no `--no-verify`
  5. Two-tier fixture structure in place: `tests/fixtures/parity/` (frozen, never re-recorded — 5 byte-equivalent fixtures from Day 0.5) + `tests/fixtures/drift/` (weekly cron-rotated, compared against parity set); rotation policy documented in `tests/fixtures/README.md`
**Plans**: TBD

### Phase TS-W0: TypeScript Foundations + Schema Codegen + CORS Matrix
**Goal**: Establish the TS workspace, build/test tooling, and the codegen pipeline so every subsequent TS phase consumes Python schemas + station registry + Kalshi map from a single source of truth. Capture empirical CORS posture per upstream endpoint before any fetcher port — this gates which sources are usable in non-extension web-app consumers.
**Depends on**: Python v0.1.0 final (canonical schemas + station registry + Kalshi map must be frozen for codegen)
**Requirements**: TS-PKG-01, TS-PKG-02, TS-CODEGEN-01, TS-CODEGEN-02, TS-CORS-01, TS-CI-01
**Success Criteria** (what must be TRUE):
  1. `pnpm install && pnpm codegen && pnpm -r build && pnpm -r test --run` from a clean clone exits 0 (no network).
  2. `scripts/export_schemas.py` is deterministic — two consecutive runs produce identical `schemas/json/*.json` + `schemas/stations.json` + `schemas/kalshi-settlement-stations.json` + `schemas/source-priority.json`.
  3. `@tradewinds/codegen` reads `schemas/` and emits typed station registry + Kalshi map + ajv-standalone validators into `packages-ts/*/src/**/generated/`; CI `schema-drift.yml` workflow fails the build on uncommitted diff.
  4. `.planning/research/TS-CORS-MATRIX.md` documents empirical CORS posture (Access-Control-Allow-Origin headers) for AWC, IEM ASOS, IEM CLI, GHCNh, Polymarket Gamma — captured from a real browser fetch, not theorized.
  5. CI workflow `test-ts.yml` green: biome check + `tsc --noEmit` + vitest with `@vitest/coverage-v8` + `size-limit` bundle-size gate on all 5 TS packages.
**Plans**: TBD (run `/gsd-plan-phase ts-w0` to break down — directory: `.planning/phases/ts-w0-foundations-schema-codegen-cors-matrix/`)

### Phase TS-W1: Chrome-extension MVP (AWC + CLI subset of `research()`)
**Goal**: Smallest useful TS surface to unblock Rob's Chrome extension overlay. Ship station lookup + Kalshi NHIGH/NLOW resolver + AWC live observations + IEM CLI settlement readings + a minimal `research()` (AWC + CLI only, no cache, no GHCNh, no IEM ASOS yet). Bundle size must stay tight so the extension service worker loads fast.
**Depends on**: Phase TS-W0
**Requirements**: TS-CORE-01, TS-CORE-02, TS-WEATHER-01, TS-WEATHER-02, TS-MARKETS-01, TS-RESEARCH-01
**Success Criteria** (what must be TRUE):
  1. `await research('NYC', '2025-01-01', '2025-01-07')` from a Node script returns `ResearchRow[]` with non-null `cliHighF`/`cliLowF` AND non-null `obsHighF`/`obsLowF` (forecast + GHCNh-derived columns may be null in W1).
  2. `resolve('KHIGHNYC', new Date('2025-01-06'))` returns `{settlementSource: 'cli.archive', settlementStation: 'KNYC', cityTicker: 'NYC', contractDate: '2025-01-06'}`; `KNOWN_WRONG_STATIONS` contract test passes (no `KLGA`/`KJFK`/`KORD`/`KIAD`/`KBWI`/`KOAK`/`KHOU`/`KDAL` appears as a Kalshi-station value).
  3. Exception hierarchy (`TradewindsError` + 7 first-class subclasses) ships with `toDict()` matching Python `to_json_safe` shape on `null/NaN/inf/cycle` edge cases.
  4. Chrome-extension end-to-end smoke test (one-page test extension fetching `research()` from its service worker against AWC + IEM CLI live) passes.
  5. `size-limit` reports W1 subset (`@tradewinds/core` + `@tradewinds/weather`'s W1 surface + `@tradewinds/markets`) ≤ 30 KB minified+gzipped.
**Plans**: TBD (run `/gsd-plan-phase ts-w1` to break down — directory: `.planning/phases/ts-w1-chrome-extension-mvp-awc-cli/`)

### Phase TS-W2: Parity Gate
**Goal**: Pass the 5-fixture parity gate against Python `research()` Mode 1 output. Land IEM ASOS + GHCNh fetchers + parsers + the two merge policies that Python ships with strict-`>` priority + first-seen tiebreak. Without this, the TS port is a "looks similar" port — with it, the TS SDK is byte-equivalent for the canonical demo cases.
**Depends on**: Phase TS-W1
**Requirements**: TS-WEATHER-03, TS-WEATHER-04, TS-MERGE-01, TS-PARITY-01
**Success Criteria** (what must be TRUE):
  1. All 5 Python parity fixtures pass against the TS implementation with exact numeric equality on every column (no tolerance loosening). HTTP replay via `msw` against recordings captured from the Python tests.
  2. IEM ASOS fetcher uses yearly chunks (calendar-aligned, leap-year safe — lifted from Python Phase 1.5 logic) at 1 req/sec politeness; CSV parser handles `#`-prefix comments + `M`/`T` sentinel values + multi-column expansion identical to `_iem.iem_to_observation`.
  3. GHCNh PSV fetcher handles 404-as-no-data per Python `download_ghcnh_range`; CORS workaround documented in `TS-CORS-MATRIX.md` if blocked.
  4. `mergeObservations` and `mergeClimate` reproduce Python source priority + secondary-key behavior. Property test (fast-check) asserts `mergeObservations(shuffleRows(rows))` is row-equivalent to `mergeObservations(rows)` ONLY for the restricted input class where no two rows share the same `(stationCode, observedAt, observationType)` AND same `sourcePriority` — i.e. permutation-stable on inputs WITHOUT same-priority duplicate-key conflicts (preserves Python `merge_observations` first-seen tiebreak; unrestricted shuffle would FALSELY require TS to diverge from Python parity). Separate canonical-fetch-order replay test against the parity-fixture HTTP recordings asserts byte-equivalent merged output across runs.
  5. Weekly drift cron `drift-rotate-ts.yml` lands and writes `drift-report.md` on mismatch (soft-fail, opens GH issue, NEVER blocks CI).
**Plans**: TBD (run `/gsd-plan-phase ts-w2` to break down — directory: `.planning/phases/ts-w2-parity-gate/`)

### Phase TS-W3: Cache + Temporal Primitives + Validator
**Goal**: Persistence layer + temporal safety + structural validation. After this phase, repeat `research()` calls hit cache (≤10% of first-call wall time), the SDK enforces no-leakage and source-identity invariants the same way Python does, and `validateRows` ships with ajv-standalone validators generated by the codegen pipeline (no runtime ajv dependency).
**Depends on**: Phase TS-W2
**Requirements**: TS-CACHE-01, TS-CACHE-02, TS-TEMPORAL-01, TS-TEMPORAL-02, TS-VALIDATOR-01
**Success Criteria** (what must be TRUE):
  1. `CacheStore` interface + `IndexedDBStore` (browser, via `idb`) + `FsStore` (Node, via `node:fs/promises` + `proper-lockfile`) + `MemoryStore` (default for Workers); `defaultCacheStore()` auto-detects runtime correctly under vitest + jsdom + Node + msw simulated worker.
  2. Second `research()` call for same `(station, fromDate, toDate)` is ≤ 10% of first-call wall time on cached-month data; LST current-month skip + `.live`-source skip + 30-day volatile-window rules match Python behavior on a 5-case fixture.
  3. `TimePoint(value)` rejects naive datetimes + date-only strings + `NaN`/`Infinity`; `KnowledgeView<Row>(rows, asOf).rows()` returns only rows where `knowledge_time <= asOf` (property tested with fast-check over constrained date range `[2018-01-01, 2027-12-31]` UTC).
  4. `assertNoLeakage(rows, asOf)` throws `LeakageError` whose `toDict()` includes `as_of`/`violating_count`/`sample_violations` with the same shape Python emits.
  5. `validateRows(rows, schemaId, {allowSourceDrift?})` throws `SchemaValidationError` with the Python-vocabulary `violations` array (`source_attr_required`/`source_column_required`/`retrieved_at_required`/`required_column_missing`/`non_nullable_has_nulls`/`mixed_null_sentinels`/`dtype_mismatch`/`enum_value_violation`/etc); ≥ 90% branch coverage on `@tradewinds/core`.
**Plans**: TBD (run `/gsd-plan-phase ts-w3` to break down — directory: `.planning/phases/ts-w3-cache-temporal-validator/`)

### Phase TS-W4: Mode 2 + Transforms + QC Alpha
**Goal**: Quality layer matching Python Phase 3 + 3.4 + 3.5 — source-explicit dispatch with role-scoped source-identity errors, transforms (lag/diff/rolling/calendar/cross-features) for baseline quant ergonomics, QC alpha rules producing the `obsQcStatus` bitfield.
**Depends on**: Phase TS-W3 AND Python Phase 3.4 QC-01 (the Group B gated codegen output `schemas/qc-alpha-rules.json` must be populated for Wave 5; Waves 1-4 + 6 can proceed without it).
**Requirements**: TS-RESEARCH-02, TS-MODE2-01, TS-TRANSFORM-01, TS-TRANSFORM-02, TS-QC-01, TS-QC-02
**Success Criteria** (what must be TRUE):
  1. `researchBySource(station, source, fromDate, toDate)` dispatches per `source ∈ {iem.archive, iem.live, awc.live, ghcnh.archive}`; `assertSourceIdentity(rows, expectedSource)` throws `SourceMismatchError` naming the offending role (`observations`/`forecasts`/`settlement`) per Python contract.
  2. Transforms (`lag`/`diff`/`diff2`/`rolling`/`calendarFeatures`/`spread`/`windChill`/`heatIndex`/`clipOutliers`) match Python `transforms.*` output byte-for-byte on a shared 50-row fixture; column-naming convention `{col}_{op}_{param}` honored.
  3. `heatIndex(90, 70)` and `windChill(20, 15)` match NWS reference table values within 1°F; out-of-domain inputs return `null` (matching Python's `None`).
  4. `QCEngine.apply(rows)` adds an `obsQcStatus` Int (32-bit bitfield) column; the 5 alpha rules ported with EXACT rule IDs + bit positions Python `ALPHA_RULES` ships at `packages/core/src/tradewinds/qc.py:103`: `temp_c.out_of_range` (bit 0), `dew_point_c.exceeds_temp` (bit 1), `wind_speed_ms.negative` (bit 2), `wind_dir_deg.out_of_range` (bit 3), `slp_hpa.out_of_range` (bit 4); loaded from codegen `schemas/qc-alpha-rules.json`.
  5. `crosscheckIemGhcnh(iemRows, ghcnhRows, {tolC?})` returns disagreement rows with `{station, eventTime, tempCIem, tempCGhcnh, deltaC}` columns matching Python `crosscheck_iem_ghcnh` output.
**Plans**: TBD (run `/gsd-plan-phase ts-w4` to break down — directory: `.planning/phases/ts-w4-mode2-transforms-qc-alpha/`)

### Phase TS-W5: Markets (Polymarket Live + Kalshi Wiring)
**Goal**: Activate Polymarket discover/settle in TS. Python v0.1.0 ships only boundary stubs (`NotImplementedError`); the substantive engine lives in TS. Maintain Python's security defenses verbatim — UUID4 regex, 16 KB description cap, netloc allowlist.
**Depends on**: Phase TS-W4 (transforms + per-source role tracking) AND Phase TS-W6 (`internationalDailyExtremes()` from TS-INTL-01 is consumed by `polymarketSettle`) AND Python Phase 3.1 INTL-02 (Group B gated codegen output `schemas/polymarket-city-stations.json` populated). **Strictly serial after TS-W6 — NOT parallel.**
**Requirements**: TS-MARKETS-02, TS-POLY-01, TS-POLY-02, TS-POLY-03
**Success Criteria** (what must be TRUE):
  1. `PolymarketClient` over `https://gamma-api.polymarket.com`: User-Agent header required, 0.2s rate limit, 429+5xx retries, pagination by `offset += 100` up to 10000 events, dedup by slug.
  2. `polymarketDiscover()` against live Gamma API returns ≥ 50 active weather events end-to-end; Tier 0 deferred-station check raises `DeferredMarketError` for Taipei/HK-lowest; Tier 1/2/3 resolver chain matches Python.
  3. `polymarketSettle(eventId, {description?})` enforces UUID4 regex on `eventId` (rejects non-UUID), enforces 16 KB description cap (`PayloadTooLargeError`), enforces netloc allowlist (`wunderground.com`/`weather.gov` + `www.` variants); `TooEarlyToSettleError` raised when source-specific finalization delay hasn't elapsed.
  4. Settlement value rounding uses half-up to whole-degree-native (matches Python `round(value + 0.5)` semantics on positive numbers and the half-up rule on negatives); ±1°F / 0.6°C diff vs published Polymarket value emits `dataQualityAlert` (does not raise).
  5. Kalshi resolver wired into a `kalshiSettlementFor(contractId, date)` higher-level helper that returns `{settlementSource, settlementStation, cityTicker, contractDate}` — same shape both NHIGH and NLOW (city-suffix dispatch).
**Plans**: TBD (run `/gsd-plan-phase ts-w5` to break down — directory: `.planning/phases/ts-w5-markets-polymarket-kalshi/`)

### Phase TS-W6: Discovery + Snapshot + DataVersion
**Goal**: Ergonomic surface — "what do I have for KNYC?" answers + `DataSnapshot` with TOON encoding + `DataVersion` reproducibility token via Web Crypto.
**Depends on**: Phase TS-W3 (CacheStore + temporal primitives must exist before `availability()` can read coverage and `DataSnapshot` can stamp `knowledge_time`)
**Requirements**: TS-DISCOVERY-01, TS-DISCOVERY-02, TS-SNAPSHOT-01, TS-VERSION-01
**Success Criteria** (what must be TRUE):
  1. `availability(station)` returns `{station, monthsCached, firstMonth, lastMonth}` sourced from `CacheStore` (counts both observation cache + climate cache).
  2. `internationalDailyExtremes(rows, {stationTz})` rolls up to per-local-calendar-day `{tempMaxC, tempMinC, tempMaxF, tempMinF}` at whole-°C precision; UTC-wrap edge cases tested for RJTT (UTC+9), SAEZ (UTC-3), NZWN (UTC+12/13 DST).
  3. `buildSnapshot(...)` returns a frozen `DataSnapshot` (interface + `Object.freeze`) with `.toDict()` (JSON-safe) + `.toToon()` (TOON v3.0 encoded string) methods matching Python output byte-for-byte on a 3-case fixture.
  4. `DataVersion.fromComponents(...)` SHA-256 hash via `crypto.subtle.digest('SHA-256', ...)` produces the same `token` as the Python `discovery.DataVersion` for identical inputs; round-trip property test (same args → same `token`).
  5. `describe(schemaId)` returns multi-line string sourced from JSON-Schema `description` fields; `featureCatalog()` returns the transforms surface list in stable order.
**Plans**: TBD (run `/gsd-plan-phase ts-w6` to break down — directory: `.planning/phases/ts-w6-discovery-snapshot-dataversion/`)

### Phase TS-W7: Docs + npm Publish
**Goal**: Ship `@tradewinds/core` + `@tradewinds/weather` + `@tradewinds/markets` + `tradewinds` meta to npm at v0.1.0. Mirror Python Phase 4 discipline: external-timer quickstart, drift fixtures rotated, trusted publishing (npm OIDC) configured.
**Depends on**: Phase TS-W6
**Requirements**: TS-DOCS-01, TS-DOCS-02, TS-DOCS-03, TS-CI-02, TS-RELEASE-01
**Success Criteria** (what must be TRUE):
  1. README quickstart (Node sample + browser sample) timed by an external person at < 5 minutes; typedoc-generated API reference committed under `docs/ts-api/`; `docs/chrome-extension-integration.md` documents Rob's integration path end-to-end.
  2. Changesets configured (`@changesets/cli` + `.changeset/config.json`); `release-ts.yml` workflow fires on `vts-*` tag, builds + tests + publishes the 4 packages to npm via OIDC trusted publishing.
  3. `vts-0.1.0rc1` tag → npm `--tag next` publish; soak for a week with internal use; then `vts-0.1.0` tag → npm `--tag latest`.
  4. `npm install @tradewinds/core @tradewinds/weather @tradewinds/markets` in a clean directory works; `npm install tradewinds` (meta) works.
  5. Chrome-extension end-to-end smoke test (separate repo or `examples/` subdir) green against `latest` published packages; bundle-size gate green for all 4 packages.
**Plans**: TBD (run `/gsd-plan-phase ts-w7` to break down — directory: `.planning/phases/ts-w7-docs-npm-publish/`)

### Phase 5: MCP Data Platform
**Goal**: Transform tradewinds from a single-vertical SDK into an MCP-native data platform for prediction market ML. Ship the MCP server layer at `packages/mcp/`, a 5-layer context-engineered data catalog, an agent-generated connector pipeline for sources not yet pre-indexed, server-enforced temporal safety (no agent bypass), and the first multi-vertical expansion beyond weather.
**Depends on**: Phase 2 (TimePoint/KnowledgeView/LeakageDetector + catalog adapters + canonical schemas), Phase 4 (CI/CD trusted publishing carries forward)
**Requirements**: MCP-01..MCP-10 (see REQUIREMENTS.md § Phase 5: MCP Data Platform)
**Vision doc**: [`phases/05-mcp-data-platform/VISION.md`](phases/05-mcp-data-platform/VISION.md)
**Success Criteria** (what must be TRUE):
  1. MCP server at `packages/mcp/` exposes `list_sources`, `describe_source`, `ingest`, `query`, `get_schema` tools via the MCP protocol; AI agents (Claude, Cursor, any MCP client) can connect and orchestrate end-to-end data pipelines without touching the Python SDK directly
  2. Data catalog stores 5-layer context per pre-indexed source (schema semantics, temporal rules, quality notes, relationship mappings, operational context); catalog entries function as agent-readable onboarding docs; pre-indexed coverage for the top 10 prediction-market data sources at v0.2 ship
  3. Agent-generated connector pipeline accepts API docs/HTML/PDF and produces stored extraction configs; generated configs are persisted so re-use by the next agent is incremental, not from scratch; quality-review gate promotes vetted configs to pre-indexed status
  4. Temporal safety is SERVER-ENFORCED: `dataset.at_time("2024-01-15")`, `.between(...)`, `.as_of(...)` return exactly and only what was knowable on that date; the constraint is structural (no agent bypass possible); deterministic replay holds — same query + same cutoff = identical results
  5. Multi-vertical expansion proven: at least one non-weather vertical (sports prediction markets) ships as catalog entries + adapters atop the same temporal-safety layer; full provenance chain auditable for every transformation; schema contracts validated on both ingest and query
**Plans:** 6 plans
- [ ] PLAN-00-requirements-id-cleanup.md — Wave 0 (prereq); pre-Phase-5 hygiene; deletes superseded narrow MCP-01..06 entries from REQUIREMENTS.md so MCP-01..MCP-10 is canonical
- [ ] PLAN-01-mcp-server-skeleton-temporal-middleware.md — Wave 1; MCP-01 (partial) + MCP-04 + MCP-06 + MCP-07 + MCP-08; FastMCP server + 5 tool stubs + TemporalSafetyMiddleware + AuditLogger + CallerContext + Dataset point-in-time API
- [ ] PLAN-02-catalog-format-weather-entries.md — Wave 2; MCP-02 + MCP-10 (weather portion, 7/10); 5-layer YAML catalog meta-schema + CatalogLoader + 7 weather catalog entries + _adapter_bridge dispatch
- [ ] PLAN-03-agent-generated-connector-pipeline.md — Wave 3; MCP-03; scaffold + validator (4 checks + 3 warnings) + promotion CLI + catalog-promotion-gate CI workflow + CONTRIBUTING + AGENT-CONNECTOR-GUIDE
- [ ] PLAN-04-second-vertical-macro.md — Wave 4a; MCP-05 + MCP-10 (macro portion, 3/10); USER_DECISION_GATE for vertical choice (researcher recommends macro over sports per 2026 legal blockers) + tradewinds-macro distribution (FRED+ALFRED+Kalshi macro) + 3 promoted catalog entries
- [ ] PLAN-05-integration-tests-deterministic-replay-release.md — Wave 4b (parallel to PLAN-04); MCP-01 + MCP-04 + MCP-06 + MCP-09 (full E2E); JSON-RPC subprocess integration tests + deterministic-replay tests + cross-vertical join allow-list (RESEARCH.md §I.8) + v0.2.0 release infrastructure (CHANGELOG + release.yml extension + RELEASE-CHECKLIST)

## Progress

**Execution Order (Python v0.1.0 — COMPLETE):**
Phases executed in numeric order: 1 → **1.5** → 2 → **2.1** → 3 → **3.1** → **3.2** → **3.3** → **3.4** → **3.5** → **3.6** → 4 → **(v0.1.0rc1 ready to publish)** → 5 (decimal phases sequence between their surrounding integers per the numbering convention above; Phase 5 is post-v0.1 Python and starts the v0.2+ Python milestone).

**Execution Order (TypeScript v0.1.0 — PLANNING):**
TS phases execute strictly serial after Python v0.1.0 final: **TS-W0** → **TS-W1** → **TS-W2** (parity gate; HARD) → **TS-W3** → **TS-W4** → **TS-W6** → **TS-W5** → **TS-W7** (v0.1.0 ship). TS-W5 is strictly serial AFTER TS-W6, NOT parallel — `polymarketSettle` (TS-POLY-03) reads `internationalDailyExtremes` (TS-INTL-01 in TS-W6). TS-W1 unblocks Rob's Chrome extension overlay; TS-W2's parity gate is the load-bearing trust gate (without it, the TS port is unverified).

**Python timeline (historical):** v0.1.0rc1 ready on 2026-05-23 (12/12 phases complete on `main`, 1453 tests passing, operator-gated PyPI trusted publish).

**TS timeline (estimate):** TS-W0..TS-W7 ≈ 18-25 days single-lane wall-clock. With the W6-before-W5 dependency there is no in-milestone parallelism for the TS lane; the schedule is mostly single-lane. Rob owns the TS lane; Vu reviews. Cross-language schema drift CI gate makes pairing additive features (Python v0.2 + TS v0.1.x) safe.

**Parallelism note (carried over from Python v0.1):** Multiple lanes still run in parallel:
- Phase 3.1 (international stations) and Phase 3.2 (multi-forecast) were independent — different files.
- Phase 3.4 (QC engine), Phase 3.5 (transforms DSL), and Phase 3.6 (discovery + settlement + DataVersion) were also independent of each other and of 3.1/3.2 — additive layers on top of canonical data.
- Phase 3.3 strictly depended on 3.1 (Polymarket settlement consumes `daily_extremes()` output).
- With 2 lanes (Rob + Vu) the post-2.1 wall-clock collapsed from ~30 days serial → ~16 days parallel (Lane A: 3.1 → 3.3 → 3.5; Lane B: 3.2 → 3.4 → 3.6). PR cadence stays per-wave.

### Python v0.1.0

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. v0.14.1 Parity Lift | done/done | ✅ Merged to `main` | 2026-05-22 |
| 1.5. Fetcher Optimization + Cross-Source Parallelism | 3/3 | ✅ Merged at 738232e | 2026-05-23 |
| 2. Core Primitives + Catalog Adapters | done/done | ✅ Merged | 2026-05-23 |
| 2.1. Sprint 2o Lineage Refactor (Per-Source Provenance) | done/done | ✅ Merged | 2026-05-23 |
| 3. Mode 2 Integration + Migration Gate | done/done | ✅ Merged (dispatch seam; fetch wiring deferred to 3.1/3.2 alphas) | 2026-05-23 |
| 3.1. International Station Expansion + Observations + Daily Extremes | done/done | ✅ Merged | 2026-05-23 |
| 3.2. Multi-Forecast Live Path (HRRR + GFS + NBM) | done/done | ✅ Merged (dispatch + `[nwp]` extra check; live HTTP wiring deferred to v0.2) | 2026-05-23 |
| 3.3. Polymarket Integration (Discovery + Settlement) | done/done | ✅ Merged (boundary + stub; live wiring deferred to v0.2) | 2026-05-23 |
| 3.4. QC Engine Alpha + Sidecar + Crosscheck | done/done | ✅ Merged | 2026-05-23 |
| 3.5. Transforms DSL + Preprocessing Primitives | done/done | ✅ Merged | 2026-05-23 |
| 3.6. Discovery API + Public Settlement + DataVersion | done/done | ✅ Merged | 2026-05-23 |
| 4. Coverage, Docs, CI/CD, Release | done/done | ✅ Merged at 7655b0e (1453 tests; 94.20% coverage; rc1 ready) | 2026-05-23 |
| 5. MCP Data Platform [Python v0.2+] | 0/6 | Plans committed (PLAN-00..PLAN-05); execution gated on TS v0.1.0 ship + Python v0.2 milestone open | - |

### TypeScript v0.1.0 (`@tradewinds/*` on npm)

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| TS-W0. Foundations + Schema Codegen + CORS Matrix | 0/TBD | Planning — depends on Python v0.1.0 final | - |
| TS-W1. Chrome-extension MVP (AWC + CLI subset of `research()`) | 0/TBD | Planning — unblocks Rob's overlay | - |
| TS-W2. Parity Gate | 0/TBD | Planning — HARD GATE against 5 Python parity fixtures | - |
| TS-W3. Cache + Temporal Primitives + Validator | 0/TBD | Planning | - |
| TS-W4. Mode 2 + Transforms + QC Alpha | 0/TBD | Planning | - |
| TS-W5. Markets (Polymarket Live + Kalshi Wiring) | 0/TBD | Planning — activates Python's `NotImplementedError` Polymarket stubs | - |
| TS-W6. Discovery + Snapshot + DataVersion | 0/TBD | Planning — can parallel TS-W5 after TS-W4 lands | - |
| TS-W7. Docs + npm Publish | 0/TBD | Planning — 4 npm OIDC pending publishers + Changesets | - |

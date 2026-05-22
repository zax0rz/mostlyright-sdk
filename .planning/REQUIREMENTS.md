# Requirements: tradewinds

**Defined:** 2026-05-21
**Core Value:** `research(contract, station, from_date, to_date)` returns clean, leakage-free, source-identified training pairs that backtest the same way they trade — and any train/infer source mismatch errors loudly instead of silently corrupting a model.

## v1 Requirements (v0.1.0)

Requirements for initial release. Each maps to a roadmap phase.

### Parity

- [ ] **PARITY-01**: `research(station, from_date, to_date)` (Mode 1, no `sources` kwarg) is byte-equivalent to `mostlyright==0.14.1`'s `client.pairs(...)` across all 5 captured fixtures
- [ ] **PARITY-02**: Parity assertion verifies dtype equivalence (`df.dtypes.equals(expected_dtypes)`) AND value equivalence (`np.allclose(rtol=0, atol=0)`), not just `df.equals()`
- [ ] **PARITY-03**: `expected_dtypes.json` captured against `mostlyright==0.14.1` on Day 0.5 and committed as ground truth (`float64` vs `Float64`, `np.nan` vs `pd.NA`, timestamp resolution `ns` vs `us`)

### Core (Temporal Safety + Schemas)

- [ ] **CORE-01**: `TimePoint`, `KnowledgeView`, `LeakageDetector` implemented with property-based tests (Hypothesis), ≥90% branch coverage on `tradewinds.core`
- [ ] **CORE-02**: `Schema` + `Validator` enforce source-identity invariant — train/infer source mismatch raises `SourceMismatchError` with both sources named
- [ ] **CORE-03**: Three canonical schemas pinned with contract tests: `schema.observation.v1`, `schema.forecast.iem_mos.v1`, `schema.settlement.cli.v1`
- [ ] **CORE-04**: Exception hierarchy: `TradewindsError` root + `SourceUnavailableError`, `SchemaValidationError`, `SourceMismatchError`, `LeakageError` — each plain class with `to_dict()` for v0.2 MCP JSON-RPC serialization
- [ ] **CORE-05**: Format serializers (`dataframe`, `json`, `parquet`, `toon`, `csv`) with roundtrip tests; TOON lifted from `monorepo-v0.14.1/.../_toon.py`
- [ ] **CORE-06**: HTTP layer in `_internal/_http.py` has retry/timeout/User-Agent — audit lifted code; add `tenacity>=9.0` with exponential backoff if missing
- [ ] **CORE-07**: `KnowledgeView` is a plain class wrapping a DataFrame with `__slots__` and constructor validation — NOT a pandas accessor, NOT a DataFrame subclass
- [ ] **CORE-08**: Property-based tests for `KnowledgeView` and `LeakageDetector` use constrained datetime ranges (`[2018-01-01, 2027-12-31]` UTC, `timezones=just(UTC)`) to avoid Hypothesis shrinking pathology

### Catalog (Adapters)

- [ ] **CATALOG-01**: IEM adapter (observations + MOS forecasts) — source IDs `iem.archive`, `iem.live`. Emits canonical `schema.observation.v1` and `schema.forecast.iem_mos.v1`. Recorded-fixture test passes.
- [ ] **CATALOG-02**: AWC adapter (METAR JSON) — source ID `awc.live`. Fixtures captured against post-Sept-2025 endpoint (`/api/data/`, NOT `/cgi-bin/`). LIFT-FIX comment on URL change.
- [ ] **CATALOG-03**: NWS CLI adapter (daily settlement) — source ID `cli.archive`. Preliminary/final/correction dedup applied. `cli_data_quality` enum + `settlement_finality` field populated from CLI REMARKS parsing (substitution detection).
- [ ] **CATALOG-04**: GHCNh adapter (hourly historical) — source ID `ghcnh.archive`. Recorded-fixture test passes.
- [ ] **CATALOG-05**: Adapter dispatch via eager registry in `tradewinds.weather.catalog.__init__` + `WeatherAdapter` Protocol — each adapter declares `SUPPORTED_SOURCES: list[str]` at class level
- [ ] **CATALOG-06**: `_vendor/__init__.py` documents provenance (monorepo-v0.14.1 git SHA, lift date, modifications)

### Markets

- [ ] **MARKETS-01**: `KALSHI_SETTLEMENT_STATIONS` constant hard-coded with Kalshi market page citations (NYC = KNYC Central Park, Chicago = KMDW Midway, etc. — NOT LGA/JFK/ORD)
- [ ] **MARKETS-02**: `tradewinds.markets.catalog.kalshi_nhigh` + `kalshi_nlow` contract specs implemented; contract test asserts every supported ticker resolves to a known station
- [ ] **MARKETS-03**: Contract spec maps `(contract_id, date) → (settlement_source, settlement_station)` deterministically

### Research (Top-level Join)

- [ ] **RESEARCH-01**: `research()` Mode 1 (no `sources` kwarg, default `units="imperial"`) returns v0.14.1 parity columns
- [ ] **RESEARCH-02**: `research()` Mode 2 (`sources={...}` dict required) returns 6 source/retrieved_at columns: `obs_source`, `obs_retrieved_at`, `fcst_source`, `fcst_retrieved_at`, `settle_source`, `settle_retrieved_at`
- [ ] **RESEARCH-03**: Mode 2 validates each role's source identity independently — `SourceMismatchError` names offending role (`observations` | `forecasts` | `settlement`)
- [ ] **RESEARCH-04**: Mode 1 deprecation warning fires starting v0.2; removed in v0.3
- [ ] **RESEARCH-05**: `research()` uses lazy `importlib.import_module("tradewinds.weather")` to break cross-package circular dependency; raises `SourceUnavailableError` with install hint if weather missing

### Cache

- [ ] **CACHE-01**: Local parquet cache at `$HOME/.tradewinds/cache/v1/observations/{station}/{year}/{month}.parquet` (schema version `v1` in path); honors `TRADEWINDS_CACHE_DIR` env var
- [ ] **CACHE-02**: `filelock`-guarded for concurrent writes; detects cloud-sync FS (iCloud/Dropbox) and falls back to `SoftFileLock` or rejects with `CacheLockTimeout`
- [ ] **CACHE-03**: LST current-month-skip (cache-skip when queried month equals current LST month for that station)
- [ ] **CACHE-04**: 30-day volatile-window exclusion for archive endpoints (no cache writes for archive data within last 30 days)
- [ ] **CACHE-05**: `*.live` endpoints never cached
- [ ] **CACHE-06**: Cache rows carry the same `source` ID and `retrieved_at` as the source-of-record (cache is a speedup, not a different source ID)
- [ ] **CACHE-07**: Parquet write uses `version="2.6"`, `coerce_timestamps="us"`, `read_dictionary=[...]` for categoricals — defends against pyarrow dtype/timestamp/categorical roundtrip loss

### Performance (Phase 1.5)

- [ ] **PERF-01**: IEM ASOS + MOS forecast chunk size = 365 calendar-aligned days (was monthly). Shared `_iem_chunks()` helper is leap-year safe. **KNYC** 5-year backfill ≤12 min wall time at 1 req/sec politeness (PR #85 measured 10 min for KNYC; allow 20% headroom for this benchmark station). Other-station regression: pick one of {KMDW, KLAX, KMIA} and confirm backfill completes within per-station wall time recorded during the Phase 1.5 spike — no fixed cross-station threshold.
- [ ] **PERF-02**: **IEM CSV staging cache** filename encodes the full chunk window (`iem_{start_iso}_{end_iso}_{suffix}.csv`) inside `_fetchers/iem_asos.py` — this is the fetcher-internal raw-CSV staging cache, **distinct from `tradewinds.weather.cache`'s path-based parquet cache** (`v1/observations/{station}/{YYYY}/{MM}.parquet`, untouched by Phase 1.5). `skip_cache=True` AND `chunk_end > today_utc` routes to `_partial` namespace that backfill never reads. Closes 3 cache-poisoning paths from mostlyright PR #85.
- [ ] **PERF-03**: `tradewinds._internal._http.HTTP_TIMEOUT` raised 30s → 60s to match 12x payload per chunk. 365-day KNYC ASOS pull completes inside 60s p95.
- [ ] **PERF-04**: `research.py` orchestrator fires AWC + IEM + GHCNh + NWS CLI concurrently for the same time window (4 parallel workers, one per source). Parallelism check: 1-year `research()` wall time ≤ `max(per_source_t_i) * 1.2` (proves no serial stall). Replaces an earlier `≤45% of sum` threshold that was mathematically invalid when per-source times are uneven (slowest-source dominates the sum).
- [ ] **PERF-05**: AWC + GHCNh rate-limit headroom empirically verified in a one-shot spike committed under `.planning/research/SOURCE-LIMITS.md` + `spike/source_limits/`. Documents max concurrent connections + response sizes (1-year, 5-year) per source.

### Lineage (Phase 2.1)

- [ ] **LINEAGE-01**: Canonical `schema.observation_ledger.v1` registered with 9 additive nullable lineage columns (`parser_name`, `parser_version`, `ingestion_id`, `as_of_time`, `source_received_at`, `qc_status`, `observation_kind`, `provenance`, `observation_quality` enum `{clean, flagged, suspect}`) on top of the v0.14.1 30-field observation schema. Natural key: `(station, observed_at, source, parser_name, as_of_time, ingestion_id)` — rows-per-source long format. Source enum reserves `ncei` for forward-compat (registered but never written in v0.1.0). QC sidecar schema `schema.observation_qc.v1` registered alongside (writer hooks ship; no rules registered in v0.1).
- [ ] **LINEAGE-02**: Silver-tier append-only ledger at `~/.tradewinds/cache/v1/observations_ledger/{station}/{YYYY}/{MM}.parquet` — rows-per-source long format. Multiple rows per `(station, observed_at)` natural key are valid silver-tier outputs (one row per contributing source). Gold-tier view materialized at read time via `ObservationMergePolicy.apply()`; cache reader applies merge transparently for Mode 1 callers. QC sidecar root at `~/.tradewinds/cache/v1/observations_qc/{station}/{YYYY}/{MM}.parquet`.
- [ ] **LINEAGE-03**: `tradewinds.core.merge.query_time_merge(rows, policy=LIVE_V1)` materializes single-row-per-`(station, observed_at, observation_kind)` gold using strict-`>` priority on `source_priority` (AWC=3, IEM=2, GHCNh=1) with secondary deterministic key `(source_received_at, ingestion_id)`. Property-tested via Hypothesis: same `silver_df` produces byte-identical `gold_df` across invocations AND across row-shuffle permutations. Backward-compat shim `merge_observations(rows)` retained as thin wrapper calling `query_time_merge(rows, LIVE_V1)`.
- [ ] **LINEAGE-04**: Pre-2.1 cache files (v0.14.1 30-column single-row-per-key shape) auto-upgrade on read via `_legacy_v014_to_v021_migration()` adapter (primary path) OR via explicit `python -m tradewinds.weather.cache_migration` CLI (predictable-timing path). Legacy `as_of_time = observed_at + 1h`; `ingestion_id = legacy:{sha256(relative_path)[:16]}:{row_idx:08d}` (machine-deterministic, lifted from mostlyright Vu Sprint-2o-s8 R4 M-7 mitigation). Legacy files renamed to `.parquet.legacy`, NEVER deleted — no silent data loss.
- [ ] **LINEAGE-05**: QC sidecar parquet root `~/.tradewinds/cache/v1/observations_qc/{station}/{YYYY}/{MM}.parquet` ships with schema + writer hooks in Phase 2.1. **NO QC rules registered or executed in Phase 2.1** — sidecar directories exist but files only get written once Phase 3.4 lands the QC engine + 5-8 alpha rules. Phase 2.1 smoke test asserts the sidecar directory layout exists and is writable. **Sequencing**: Phase 2.1 ships schema + path layout + writer hooks; Phase 3.4 ships engine + rules that consume them (forecast QC + climate QC stay deferred to v0.2 per Phase 3.4 out-of-scope).

### International (Phase 3.1)

> Detailed requirements (each with verifiable success criterion) land via `/gsd-plan-phase 3.1`. Stubs registered here so ROADMAP `Requirements: INTL-01..05` references resolve to canonical IDs and traceability checks pass. Scope per ROADMAP Phase 3.1 `### Phase 3.1` block.

- [ ] **INTL-01**: TBD — defined when Phase 3.1 PLAN.md is written. Scope: STATIONS registry grows 20 US → 60 with 40 international ICAOs + per-station IANA timezones.
- [ ] **INTL-02**: TBD — `_per_event_station.resolve_station_for_event()` handles Paris LFPG/LFPB split + `polymarket_city_stations.json` catalog ships.
- [ ] **INTL-03**: TBD — `daily_extremes()` rollup with station-local IANA calendar day; whole-°C international, 0.1°C US.
- [ ] **INTL-04**: TBD — `schema.daily_extreme.v1` registered.
- [ ] **INTL-05**: TBD — catalog adapter wiring honors per-source priority for non-US (IEM > GHCNh; AWC US-only).

### NWP Forecast (Phase 3.2)

> Stubs for ROADMAP Phase 3.2. Detailed requirements via `/gsd-plan-phase 3.2`.

- [ ] **NWP-01**: TBD — `schema.forecast_nwp.v1` (36 cols + sidecar) with 7-model enum (incl. 4 ECMWF reserved) + 8-archive-mirror enum.
- [ ] **NWP-02**: TBD — 3 Tier-1 adapters (HRRR/GFS/NBM) via `_nwp_idx.py` + cfgrib + BallTree.
- [ ] **NWP-03**: TBD — `client.forecast_nwp(...)` SDK surface with 37-col fixed-shape DataFrame.
- [ ] **NWP-04**: TBD — 12 QC rules per model run at fetch time, populate `qc_status`.
- [ ] **NWP-05**: TBD — `tradewinds-weather[nwp]` optional extra; per-station per-month cache layout.
- [ ] **NWP-06**: TBD — ECMWF Tier-2 + historical NWP backfill explicitly OUT of v0.1.

### Polymarket (Phase 3.3)

> Stubs for ROADMAP Phase 3.3. Detailed requirements via `/gsd-plan-phase 3.3`. Activates `POLY-01` (formerly Sprint 0.5+ deferral; now Phase 3.3 v0.1.0 scope).

- [ ] **POLY-02**: TBD — `PolymarketClient` over Gamma API (no auth) with rate limit + retries + dedup.
- [ ] **POLY-03**: TBD — `polymarket_discover()` + Tier 0/1/2/3 resolver; drops 11 US slugs.
- [ ] **POLY-04**: TBD — `schema.polymarket_settlement_record.v1` with both °C and °F + `resolution_source_type` enum.
- [ ] **POLY-05**: TBD — `polymarket_settle()` engine using `daily_extremes()` resolution; per-source finalization delay; tolerance-based `data_quality_alert`.

(Note: `POLY-01` repurposed from `Sprint 0.5+` to Phase 3.3 v0.1.0 scope as of 2026-05-22 expansion. Its earlier "v0.x+ as demand emerges" entry in "Markets API Client (Sprint 0.5+)" below is superseded; see Phase 3.3 in ROADMAP.)

### QC Engine (Phase 3.4)

> Stubs for ROADMAP Phase 3.4. Detailed requirements via `/gsd-plan-phase 3.4`.

- [ ] **QC-01**: TBD — `QCEngine` + bitfield rule registry ported from `mostlyright/src/mostlyright/qc/engine.py`.
- [ ] **QC-02**: TBD — `ObservationQCSidecar.write_entries()` populates the LINEAGE-05 sidecar layout.
- [ ] **QC-03**: TBD — IEM-vs-GHCNh crosscheck with per-field tolerances.
- [ ] **QC-04**: TBD — Alpha rule set (5-8 rules: physics bounds + crosscheck + METAR-corruption).
- [ ] **QC-05**: TBD — `research()` Mode 2 surfaces `obs_qc_status` bitfield (Mode 1 stays parity-clean).

### Transforms (Phase 3.5)

> Stubs for ROADMAP Phase 3.5. Detailed requirements via `/gsd-plan-phase 3.5`.

- [ ] **TRANSFORM-01**: TBD — `tradewinds.transforms.{lag, diff, diff2, rolling}` ported from `mostlyright/src/mostlyright/transforms.py`.
- [ ] **TRANSFORM-02**: TBD — `tradewinds.transforms.calendar_features` with station-local tz (sin/cos cyclical encoding).
- [ ] **TRANSFORM-03**: TBD — Cross-features (spread, wind_chill, heat_index) with documented physics-formula domains.
- [ ] **TRANSFORM-04**: TBD — `tradewinds.preprocessing.{clip_outliers, iem_crosscheck}` ported from `mostlyright/src/mostlyright/preprocessing.py`.

### Discovery + Settlement + Versioning (Phase 3.6)

> Stubs for ROADMAP Phase 3.6. Detailed requirements via `/gsd-plan-phase 3.6`.

- [ ] **DISCOVERY-01**: TBD — `tradewinds.discovery.availability(station)` returns per-source coverage record.
- [ ] **DISCOVERY-02**: TBD — `tradewinds.discovery.{climate_gaps, describe, feature_catalog}` ports.
- [ ] **DISCOVERY-03**: TBD — `feature_catalog()` returns structured `FeatureSpec` list (Kalshi-specific annotations defer to Phase 5 PLAN-02).
- [ ] **SETTLEMENT-API-01**: TBD — `tradewinds.settlement.{settlement_date_for, settlement_window_utc}` at top level with DST-edge-case tests.
- [ ] **VERSION-01**: TBD — `tradewinds.DataVersion` reproducibility token: `(content_hash, schema_version, lift_sha, fetched_at)`. Property test: same args + same DataVersion → byte-identical DataFrame.

### Packaging

- [ ] **PKG-01**: Three PyPI distributions publish at v0.1.0: `tradewinds`, `tradewinds-weather`, `tradewinds-markets`
- [ ] **PKG-02**: PEP 420 native namespace packaging — only `packages/core/src/tradewinds/__init__.py` exists; `weather/src/tradewinds/` and `markets/src/tradewinds/` have NO `__init__.py` at that level
- [ ] **PKG-03**: Cross-package version pins enforced: `tradewinds-weather`'s `Requires-Dist: tradewinds>=0.1.0,<0.2`; same for markets. Pre-publish CI step inspects wheel METADATA and fails build if loose.
- [ ] **PKG-04**: Wheel build verification — Day 1 task: `uv build --all` + unzip wheels + confirm no two wheels both ship `tradewinds/__init__.py`
- [ ] **PKG-05**: `pandas>=2.2,<3.0` pinned across all packages (Pandas 3.0 breaking changes deferred to v0.2 migration with re-captured parity fixtures)
- [ ] **PKG-06**: `pyarrow` version pinned to exact `monorepo-v0.14.1` lockfile version

### Documentation

- [ ] **DOCS-01**: NumPy-style docstrings on all public surface (`research()`, adapters, core primitives); `pytest --doctest-modules` runs in CI
- [ ] **DOCS-02**: README quickstart works end-to-end in <5 minutes for a fresh installer, timed by an external person (not the author)
- [ ] **DOCS-03**: Adapter knowledge-resource pages (1 page each in `docs/adapters/`): schema, gotchas, timezone notes, source-pairing rules

### Migration

- [ ] **MIGRATION-01**: `mostly-light/strategies/kxhigh` dry-run end-to-end against tradewinds (editable install) matches `therminal-py>=1.0.7` baseline. Run via `python scripts/run_live_strategy.py --strategy kxhigh --dry-run --city atlanta`. Diff dry-run output rows for byte-equivalence.
- [ ] **MIGRATION-02**: All 5 named `mostly-light` call sites (per ROADMAP.md "Integration parity criterion") work against tradewinds: `client.observations`, `client.climate`, `MostlyRightMCPError` (alias for `TherminalError`), `WeatherLive`, public IEM record parser
- [ ] **MIGRATION-03**: `mostly-light/core/weather/sources/metar_parser.py` (local duplication of METAR JSON parsing) is either deleted or documented as intentionally out of scope in tradewinds README

### CI / Release

- [ ] **CI-01**: GitHub Actions: test on push, release on tag (`v*`), PyPI trusted publishing via `astral-sh/trusted-publishing-examples` pattern
- [ ] **CI-02**: Pre-publish METADATA grep: each built wheel's `Requires-Dist` must include explicit version range for sibling `tradewinds-*` packages — fail build if missing
- [ ] **CI-03**: Pre-commit hooks: `ruff check --fix` + `ruff format` + (optional) `mypy --strict` on `core/`. No `--no-verify` allowed.
- [ ] **CI-04**: `pytest -m "not live"` runs in CI; `@pytest.mark.live` tests excluded (hit real public APIs, run manually before publish)
- [ ] **CI-05**: Two-tier fixture set: frozen parity fixtures (immutable, in `tests/fixtures/parity/`) + weekly drift fixtures (cron-rotated, in `tests/fixtures/drift/`)

## v2 Requirements (Deferred)

Acknowledged but not in v0.1.0 roadmap.

### Pandas 3.0 Migration (v0.2)

- **PANDAS3-01**: Pandas 3.0 compatibility — re-capture parity fixtures, audit CoW assumptions, migrate offset aliases, validate timestamp resolution handling
- **PANDAS3-02**: Drop `pandas<3.0` upper bound; pin `pandas>=3.0,<4.0`

### Cross-Source Diff Job (v0.1.1)

- **DIFF-01**: Empirical cross-source divergence measurement: `iem.archive` vs `awc.live` for same 3-5 stations × 90-day window — mean / p50 / p95 / p99 abs diff per shared column
- **DIFF-02**: Same diff for `iem.archive` vs `iem.live` overlap window
- **DIFF-03**: Results power `catalog_search` warning numbers (currently `"status": "unmeasured"` placeholders in v0.1)

### Markets API Client (Sprint 0.5+)

- **KALSHI-01**: Kalshi API client (orderbook, fills, settlement queries)
- **POLY-01**: Polymarket adapter (out of v0.1 scope; v0.x+ as demand emerges)

### Preprocessing (Sprint 0.5+)

- **PREP-01**: RH, feels_like, wind chill derivations (opt-in via explicit transform calls)
- **PREP-02**: MetPy re-parse workflow (Vojtech's documented path) wrapped as `tradewinds.weather.transforms.metpy()`

## v3+ Requirements (Distant)

- **HOSTED-01**: Hosted R2 read-through cache (Phase C+, requires 60-day validation gate to pass)
- **VERTICAL-02**: Second vertical (sports, politics, or finance) — only after 60-day gate confirms productize thesis
- **POLARS-01**: Polars return type (alongside pandas) — only if user demand emerges

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| MCP server in v0.1 | Deferred to v0.2; seam preserved at `packages/mcp/` |
| Hosted R2 cache | Requires 60-day validation gate first |
| Sports / politics / finance verticals | v0.1 is weather only |
| Open-Meteo adapter | Licensing blocks redistribution (any v0.x) |
| Preprocessing (RH, feels_like, MetPy re-parse) | Sprint 0.5+; raw `metar_raw` preserved |
| Kalshi API client (orderbook, fills) | Sprint 0.5+; v0.1 ships contract specs only |
| CLI surface | Python SDK only; CLI is v1.1+ |
| Agent-generated connectors | Original mostlyright-mcp Layer 2 idea; v2+ |
| `as_of_query` MCP tool | v0.2+ only on named user request |
| Async API surface (`aresearch()`, async adapters) | v0.2 if demand emerges; `httpx` seam preserved |
| Built-in backtesting engine | Out of scope — user owns modeling and backtest |
| Hosted feature store integration (Feast/Tecton) | Feast/Tecton too heavy a dep for local-first SDK; build, don't buy |
| Pydantic models as primary API | Row-wise doesn't scale; DataFrame-first |
| Polars as primary return type in v0.1 | Breaks v0.14.1 parity and mostly-light downstream |
| Real-time websocket data | Out of scope; not relevant for daily settlement |

## Traceability

Per-requirement phase assignments (filled by roadmapper 2026-05-21).

| Requirement | Phase | Status |
|-------------|-------|--------|
| PARITY-01 | Phase 1 | Pending |
| PARITY-02 | Phase 1 | Pending |
| PARITY-03 | Phase 1 | Pending |
| CORE-01 | Phase 2 | Pending |
| CORE-02 | Phase 2 | Pending |
| CORE-03 | Phase 2 | Pending |
| CORE-04 | Phase 2 | Pending |
| CORE-05 | Phase 2 | Pending |
| CORE-06 | Phase 1 | Pending |
| CORE-07 | Phase 2 | Pending |
| CORE-08 | Phase 2 | Pending |
| CATALOG-01 | Phase 2 | Pending |
| CATALOG-02 | Phase 2 | Pending |
| CATALOG-03 | Phase 2 | Pending |
| CATALOG-04 | Phase 2 | Pending |
| CATALOG-05 | Phase 2 | Pending |
| CATALOG-06 | Phase 1 | Pending |
| MARKETS-01 | Phase 2 | Pending |
| MARKETS-02 | Phase 2 | Pending |
| MARKETS-03 | Phase 2 | Pending |
| RESEARCH-01 | Phase 3 | Pending |
| RESEARCH-02 | Phase 3 | Pending |
| RESEARCH-03 | Phase 3 | Pending |
| RESEARCH-04 | Phase 3 | Pending |
| RESEARCH-05 | Phase 3 | Pending |
| CACHE-01 | Phase 1 | Pending |
| CACHE-02 | Phase 3 | Pending |
| CACHE-03 | Phase 3 | Pending |
| CACHE-04 | Phase 3 | Pending |
| CACHE-05 | Phase 3 | Pending |
| CACHE-06 | Phase 3 | Pending |
| CACHE-07 | Phase 1 | Pending |
| PERF-01 | Phase 1.5 | Pending |
| PERF-02 | Phase 1.5 | Pending |
| PERF-03 | Phase 1.5 | Pending |
| PERF-04 | Phase 1.5 | Pending |
| PERF-05 | Phase 1.5 | Pending |
| LINEAGE-01 | Phase 2.1 | Pending |
| LINEAGE-02 | Phase 2.1 | Pending |
| LINEAGE-03 | Phase 2.1 | Pending |
| LINEAGE-04 | Phase 2.1 | Pending |
| LINEAGE-05 | Phase 2.1 | Pending (engine deferred to Phase 3.4) |
| INTL-01..05 | Phase 3.1 | Stubbed (defined per /gsd-plan-phase 3.1) |
| NWP-01..06 | Phase 3.2 | Stubbed (defined per /gsd-plan-phase 3.2) |
| POLY-02..05 | Phase 3.3 | Stubbed (defined per /gsd-plan-phase 3.3); POLY-01 repurposed from Sprint-0.5+ |
| QC-01..05 | Phase 3.4 | Stubbed (defined per /gsd-plan-phase 3.4) |
| TRANSFORM-01..04 | Phase 3.5 | Stubbed (defined per /gsd-plan-phase 3.5) |
| DISCOVERY-01..03, SETTLEMENT-API-01, VERSION-01 | Phase 3.6 | Stubbed (defined per /gsd-plan-phase 3.6) |
| PKG-01 | Phase 4 | Pending |
| PKG-02 | Phase 1 | Pending |
| PKG-03 | Phase 2 | Pending |
| PKG-04 | Phase 1 | Pending |
| PKG-05 | Phase 1 | Pending |
| PKG-06 | Phase 1 | Pending |
| DOCS-01 | Phase 4 | Pending |
| DOCS-02 | Phase 4 | Pending |
| DOCS-03 | Phase 4 | Pending |
| MIGRATION-01 | Phase 3 | Pending |
| MIGRATION-02 | Phase 3 | Pending |
| MIGRATION-03 | Phase 3 | Pending |
| CI-01 | Phase 4 | Pending |
| CI-02 | Phase 4 | Pending |
| CI-03 | Phase 4 | Pending |
| CI-04 | Phase 4 | Pending |
| CI-05 | Phase 4 | Pending |

**Coverage:**
- v1 requirements: 54 total
- Mapped to phases: 54 ✓
- Unmapped: 0 ✓

**Phase Distribution:**
- Phase 1 (Parity Lift): 11 requirements (PARITY-01..03, CORE-06, CATALOG-06, CACHE-01, CACHE-07, PKG-02, PKG-04, PKG-05, PKG-06)
- Phase 1.5 (Fetcher Optimization + Parallelism): 5 requirements (PERF-01..05)
- Phase 2 (Core + Catalog): 16 requirements (CORE-01..05, CORE-07, CORE-08, CATALOG-01..05, MARKETS-01..03, PKG-03)
- Phase 3 (Mode 2 + Migration): 13 requirements (RESEARCH-01..05, CACHE-02..06, MIGRATION-01..03)
- Phase 4 (Coverage + Release): 9 requirements (PKG-01, DOCS-01..03, CI-01..05)

## Phase 5: MCP Data Platform (v0.2+)

Post-v0.1.0 requirements for the MCP-native data platform vision. See [`phase-05-mcp-data-platform/VISION.md`](phase-05-mcp-data-platform/VISION.md).

- [ ] **MCP-01**: MCP server exposes `list_sources`, `describe_source`, `ingest`, `query`, `get_schema` tools via the MCP protocol; any MCP client (Claude, Cursor, custom) can drive end-to-end pipelines
- [ ] **MCP-02**: Data catalog stores 5-layer context per source — schema semantics, temporal rules, quality notes, relationship mappings, operational context — functioning as agent-readable onboarding docs
- [ ] **MCP-03**: Agent-generated connector pipeline accepts API docs/HTML/PDF, builds schema mental model, generates extraction config, persists for re-use; quality-review gate before promotion to pre-indexed status
- [ ] **MCP-04**: Server-enforced temporal safety — no agent bypass possible; constraint is structural (not honor-system), enforced inside the MCP server before any row is returned to the agent
- [ ] **MCP-05**: Multi-vertical catalog expansion: v0.2 = weather + MCP server; v0.3 = sports prediction markets; v0.4 = politics + finance. Same temporal-safety layer across verticals.
- [ ] **MCP-06**: Auditable provenance chain — every data transformation logs source, retrieval timestamp, schema version, and transformation identity; replayable end-to-end
- [ ] **MCP-07**: Schema contract validation on BOTH ingest and query paths; mismatches raise structured errors with `to_dict()` JSON-RPC payloads (reuses Phase 2 exception hierarchy)
- [ ] **MCP-08**: Point-in-time query API — `dataset.at_time(date)`, `.between(start, end)`, `.as_of(timestamp)`; returns exactly and only what was knowable on the given date
- [ ] **MCP-09**: Deterministic replay — same query + same cutoff = identical result bytes across runs; tested via property-based fixtures
- [ ] **MCP-10**: Pre-indexed catalog entries for the top 10 prediction-market data sources at v0.2 ship (concrete list to be defined in Phase 5 PLAN.md; weather sources already covered by Phase 2 adapters)

### Phase 5 Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| MCP-01 | Phase 5 | Pending |
| MCP-02 | Phase 5 | Pending |
| MCP-03 | Phase 5 | Pending |
| MCP-04 | Phase 5 | Pending |
| MCP-05 | Phase 5 | Pending |
| MCP-06 | Phase 5 | Pending |
| MCP-07 | Phase 5 | Pending |
| MCP-08 | Phase 5 | Pending |
| MCP-09 | Phase 5 | Pending |
| MCP-10 | Phase 5 | Pending |

**Phase 5 coverage:** 10 requirements, all mapped. Depends on Phase 2 (temporal primitives, catalog adapters, canonical schemas) and Phase 4 (CI/CD trusted publishing).

---
*Requirements defined: 2026-05-21*
*Last updated: 2026-05-22 — resolved MCP-01..06 ID collision; Phase 5 entries are canonical*

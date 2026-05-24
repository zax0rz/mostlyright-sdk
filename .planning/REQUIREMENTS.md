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

(Note: `POLY-01` repurposed from `Sprint 0.5+` to Phase 3.3 v0.1.0 scope as of 2026-05-22 expansion. The earlier "v0.x+ as demand emerges" entry under "Markets API Client (Sprint 0.5+)" was removed 2026-05-22 as part of this fix; see Phase 3.3 in ROADMAP.)

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

### Ingest Auto-Planner + obs() Surface (Phase 7)

- [x] **INGEST-01**: `tw.weather.obs(...)` public surface at `packages/weather/src/tradewinds/weather/obs.py`; re-export at `tradewinds.weather.obs`.
- [x] **INGEST-02**: `exact_window` strategy bypasses year-normalization (`iem_asos.py:204-209`); day-granular IEM URL params; separate `sources/iem_asos_exact/` cache directory namespace (B-5: directory-level separation, not filename infix).
- [x] **INGEST-03**: `warm_cache` strategy preserves current `research()` orchestration; obs aggregates byte-equivalent to `research()` Mode-1 for the 5 Phase 1 parity fixtures (live-only test).
- [x] **INGEST-04**: `hosted` strategy seam: `TW_HOSTED_URL` env-var gate; raises `NotImplementedError("hosted strategy deferred to v0.2.x — set TW_HOSTED_URL to enable once client lands")`.
- [x] **INGEST-05**: `strategy="auto"` decision tree: window-size + cache-warmth + env-var triage; W-2 multi-year cache scan; 90-day threshold per empirical research doc.
- [x] **INGEST-06**: `source=None | "iem" | "ghcnh" | "awc"` single-source path skips other fetchers at the fetcher boundary (preserves merge-priority semantics).
- [x] **INGEST-07**: Mutable-period invariants preserved across all strategies — `_is_writable_month`, `_is_current_lst_month`, `_is_current_lst_year`, UNION skip predicate; helpers are REUSED, never reinvented.
- [x] **INGEST-08**: Empirical-timing harness at `tests/perf/test_ingest_obs.py` gates `exact_window` ≤ 2 MB cold for 1mo KNYC (live-only; run pre-publish).

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

### Pandas 3 + Polars Backend (Phase 6)

Promoted from deferred to active. See `## Phase 6: Pandas 3 Readiness + Optional Polars Backend (v0.2+)` section near the end of this document for the full PANDAS3-01..06 + POLARS-01..08 spec. Listed here as a forward reference for diff readers who land at the v2 section first.

### Cross-Source Diff Job (v0.1.1)

- **DIFF-01**: Empirical cross-source divergence measurement: `iem.archive` vs `awc.live` for same 3-5 stations × 90-day window — mean / p50 / p95 / p99 abs diff per shared column
- **DIFF-02**: Same diff for `iem.archive` vs `iem.live` overlap window
- **DIFF-03**: Results power `catalog_search` warning numbers (currently `"status": "unmeasured"` placeholders in v0.1)

### Markets API Client (Sprint 0.5+)

- **KALSHI-01**: Kalshi API client (orderbook, fills, settlement queries)

### Preprocessing (Sprint 0.5+)

- **PREP-01**: RH, feels_like, wind chill derivations (opt-in via explicit transform calls)
- **PREP-02**: MetPy re-parse workflow (Vojtech's documented path) wrapped as `tradewinds.weather.transforms.metpy()`

## v3+ Requirements (Distant)

- **HOSTED-01**: Hosted R2 read-through cache (Phase C+, requires 60-day validation gate to pass)
- **VERTICAL-02**: Second vertical (sports, politics, or finance) — only after 60-day gate confirms productize thesis
- **POLARS-LAZY-01**: Polars LazyFrame default (alongside eager) — v0.3 follow-up to Phase 6's eager-only first cut
- **PYARROW-BACKEND-01**: pyarrow Table backend (third option alongside pandas + polars) — v0.3 if user demand emerges; narwhals supports it natively

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

## TS Requirements (TypeScript SDK v0.1.0)

> Mirror of Python public surface for `@tradewinds/core` + `@tradewinds/weather` + `@tradewinds/markets` + `tradewinds` (meta) on npm. See [`research/TS-SDK-DESIGN.md`](research/TS-SDK-DESIGN.md) for the design contract and [`research/PYTHON-SURFACE-INVENTORY.md`](research/PYTHON-SURFACE-INVENTORY.md) for the surface map.

### Foundations (Phase TS-W0)

- [ ] **TS-PKG-01**: pnpm workspace under `packages-ts/` with 5 packages (`core`, `weather`, `markets`, `meta`, `codegen`); `pnpm install && pnpm -r build && pnpm -r test` exits 0 from clean clone (no network).
- [ ] **TS-PKG-02**: Each package builds ESM (`.mjs`) + CJS (`.cjs`) + IIFE (`.global.js`) + types (`.d.ts`) via `tsup`. TypeScript `strict: true, noUncheckedIndexedAccess: true, exactOptionalPropertyTypes: true`.
- [ ] **TS-CODEGEN-01**: `scripts/export_schemas.py` is deterministic — two consecutive runs produce byte-identical outputs across the full set defined in [CROSS-SDK-SYNC.md §1.2](CROSS-SDK-SYNC.md). **Group A (always emitted)**: `schemas/json/{observation,forecast.iem_mos,settlement.cli,observation_ledger,observation_qc}.v1.json` + `schemas/stations.json` + `schemas/kalshi-settlement-stations.json` + `schemas/source-priority.json` + `schemas/EXPORT_MANIFEST.json`. **Group B (gated on Python source artifact existing)**: `schemas/polymarket-city-stations.json` (gated on Python Phase 3.1 INTL-02 `markets._per_event_station`) + `schemas/qc-alpha-rules.json` (gated on Python Phase 3.4 QC-01 `tradewinds.qc.ALPHA_RULES` materialization). CI workflow `schema-drift.yml` fails on uncommitted diff for Group A; Group B follows the gated-output rule in CROSS-SDK-SYNC §1.2 (recorded as `{"gated": true, "reason": "..."}` in `EXPORT_MANIFEST.json` when the Python source is absent).
- [ ] **TS-CODEGEN-02**: `@tradewinds/codegen` reads `schemas/` and emits typed station registry + Kalshi map + ajv-standalone validators into `packages-ts/*/src/**/generated/`. Generated files committed; CI checks `git diff --exit-code packages-ts/*/src/**/generated/`.
- [ ] **TS-CORS-01**: `.planning/research/TS-CORS-MATRIX.md` documents empirical CORS posture per upstream endpoint (AWC, IEM ASOS, IEM CLI, GHCNh, Polymarket Gamma) captured from a real browser fetch + per-endpoint workaround notes (CORS proxy template, Chrome extension `host_permissions` snippet).
- [ ] **TS-CI-01**: GitHub Actions workflows `test-ts.yml` (push/PR) + `schema-drift.yml` (push/PR) green. `test-ts.yml`: pnpm install → codegen drift → biome → typecheck → vitest with coverage → `size-limit` bundle gate.
- [ ] **TS-SYNC-01**: Cross-SDK sync process enforced via [`CROSS-SDK-SYNC.md`](CROSS-SDK-SYNC.md), `parity-ticket-check.yml` workflow, and a populated `.github/PULL_REQUEST_TEMPLATE.md` carrying the parity-ticket prompt block (`Parity-Ticket: #N` line or `python_only: true` / `typescript_only: true` opt-out with justification).
- [ ] **TS-SYNC-02**: `scripts/parity_status.py --milestone <name>` lists open parity tickets per milestone (reads from GitHub via `gh issue list --label parity-ticket` or from `.planning/parity-tickets/*.md` front-matter). Consumed by release-readiness gate in TS-RELEASE-01 and equivalent Python release workflow; refuses to release on non-empty P0 list.
- [ ] **TS-SYNC-03**: `.github/ISSUE_TEMPLATE/parity_ticket.md` ships, matching the template in [CROSS-SDK-SYNC.md §2.2](CROSS-SDK-SYNC.md) byte-for-byte; new parity tickets opened in GitHub Issues use this template by default.

### Core / Exceptions / Conversions (Phase TS-W1)

- [ ] **TS-CORE-01**: TS exception hierarchy mirrors Python: `TradewindsError` base + `SourceUnavailableError`, `SchemaValidationError`, `SourceMismatchError`, `LeakageError`, `TemporalDriftError`, `PayloadTooLargeError`, `DeferredMarketError`, `PolymarketEventError`. Each carries `errorCode`, `source`, `requestId`, plus subclass-specific fields. `toDict()` JSON-safe per Python `to_json_safe`: `null` for `NaN`/`Infinity`/`null`, ISO strings for dates, cycles → `{_cycle: true, value: String(obj)}`, dict keys must be strings.
- [ ] **TS-CORE-02**: Unit conversions in `@tradewinds/core/internal/convert`: `ktToMs`, `ktToMph`, `miToKm`, `miToM`, `ftToM`, `inchesToMm`, `celsiusToFahrenheit`, `fahrenheitToCelsius`, `hpaToInhg`, `computeRelativeHumidity` (Magnus), `computeFeelsLike` (NWS wind chill + heat index). Same constants as Python (`_KT_TO_MPH = 1.15078`, `_KT_TO_MS = 1852.0/3600.0`, `_IN_TO_MM = 25.4`, `_HPA_TO_INHG = 0.0295299875`, `_MAGNUS_A = 17.625`, `_MAGNUS_B = 243.04`).

### Weather Fetchers (Phases TS-W1 + TS-W2)

- [ ] **TS-WEATHER-01**: AWC live-METAR fetcher (`fetchAwcMetars(stationIcaos, hours=168)`) hits `https://aviationweather.gov/api/data/metar` with same query shape as Python; retry/backoff on 429+5xx via `fetch()` + `AbortController` + exponential delay; returns `[]` (never throws) on 4xx / exhausted retries / non-array body.
- [ ] **TS-WEATHER-02**: IEM CLI fetcher (`downloadCli(stationIcao, year)` + `downloadCliRange`) hits `https://mesonet.agron.iastate.edu/json/cli.py?station=<ICAO>&year=<YYYY>`; 404 → no data for year (skipped by range fetcher); 1s politeness delay; cache path key matches Python `dest_dir/<icao>/cli_<year>.json` layout (under TS cache root).
- [x] **TS-WEATHER-03**: IEM ASOS fetcher (`downloadIemAsos(station, start, end)`) uses yearly chunks (calendar-aligned, leap-year safe — port of Python Phase 1.5 `_iem_chunks.yearly_chunks_exclusive_end`, NOT `yearly_chunks_inclusive`; IEM's `day2` query parameter is EXCLUSIVE, so per-year chunks end on Jan 1 of the following year). 1s politeness; 60s timeout; CSV staging cache filename `iem_{startIso}_{endIso}_{suffix}.csv`; `skipCache: true && chunkEnd > todayUtc` routes to `_partial` namespace.
- [ ] **TS-WEATHER-04**: GHCNh fetcher (`downloadGhcnh(stationId, year)` + range) hits `https://www.ncei.noaa.gov/oa/global-historical-climatology-network/hourly/access/by-year/<YEAR>/psv/GHCNh_<station_id>_<YEAR>.psv`; 404 → no data (skipped by range fetcher); 1s politeness AFTER successful download (cache hits + 404s skip delay); PSV parser filters `Quality_Code ∈ {"0","1","4","5",""}`.

### Parsers + Merge (Phase TS-W2)

- [x] **TS-PARSER-01**: AWC JSON parser (`awcToObservation`) handles same fields as Python `_awc.awc_to_observation`: `icaoId`, `obsTime`, `metarType`, `wdir`/`wspd`/`wgst`/`altim`/`slp`/`temp`/`dewp`, `visib` (with `10+` / `1/2` / `2 1/4` forms), `clouds`, `rawOb`, `wxString`, `precip` (`"T"` = trace), `qcField`. Bounds checks per `_bounds` constants.
- [x] **TS-PARSER-02**: IEM CSV parser (`iemToObservation`, `parseIemFile`) handles `#`-prefix comment lines, header, rows with `valid`, `tmpf`, `dwpf`, `drct`, `sknt`, `gust`, `alti`, `mslp`, `vsby`, `skyc1..4`, `skyl1..4`, `wxcodes`, `p01i`, `snowdepth`, `peak_wind_*`, `metar`. `M`/`T` sentinels → null/trace.
- [ ] **TS-PARSER-03**: NWS CLI parser (`parseCliRecord`, `parseCliResponse`) handles `valid` (YYYY-MM-DD), `high`/`low` (int|"M"|""), `product` (first 12 chars = UTC YYYYMMDDHHmm). `inferReportType(product, observationDate)` matches Python; `REPORT_TYPE_PRIORITY` constant from codegen.
- [ ] **TS-PARSER-04**: GHCNh PSV parser (`parseGhcnhRow`, `parseGhcnhFile`) handles `DATE`, `temperature*`/`dew_point_temperature*`/`wind_direction*`/`wind_speed*`/`wind_gust*`/`sea_level_pressure*`/`altimeter*`/`visibility*`/`precipitation*`/`snow_depth*`/`sky_cover_summation_*`/`pres_wx_AW*`/`REM` columns. Quality_Code filtering. `ghcnhStationToCode` translates NCEI id → 3-letter station code.
- [ ] **TS-MERGE-01**: `mergeObservations(rows)` dedups by `(stationCode, observedAt, observationType)`, strict-`>` priority `{awc: 3, iem: 2, ghcnh: 1}`, unknown source = 0, first-seen wins at tie. Property test via fast-check: same input across row-shuffle permutations produces identical output. `mergeClimate(rows)` dedups by `(stationCode, observationDate)`, strict-`>` on `reportTypePriority`. Source priorities loaded from codegen `schemas/source-priority.json`.

### Research / Snapshot / Mode 2 (Phases TS-W1 + TS-W2 + TS-W4)

- [ ] **TS-RESEARCH-01**: `research(station, fromDate, toDate, opts?): Promise<ResearchRow[]>` — Mode 1, async, returns the 19-column shape Python returns. AWC + CLI live in TS-W1; full source set (+ IEM ASOS + GHCNh) in TS-W2. `tzOverride` / `casing` / `signal` (AbortSignal) / `cache` (CacheStore) options.
- [ ] **TS-RESEARCH-02**: `researchBySource(station, source, fromDate, toDate)` — Mode 2 dispatch; rejects unknown source; `assertSourceIdentity(rows, expectedSource)` throws `SourceMismatchError` with `role` (`observations` / `forecasts` / `settlement`) per Python contract.
- [ ] **TS-MODE2-01**: Source enum + dispatch table for Mode 2 mirrors Python `tradewinds.mode2._VALID_OBSERVATION_SOURCES = frozenset({"iem.archive", "iem.live", "awc.live", "ghcnh.archive"})`. Unknown source → `ValueError` matching Python; per-row source-identity invariant: all rows in a Mode-2 return value carry `source === expectedSource` (no mixed-source rows). Empty-result returns empty array, not throw.
- [ ] **TS-SNAPSHOT-01**: `settlementDateFor(asOf, station, tzOverride?)`, `settlementWindowUtc(date, station, tzOverride?)`, `cliAvailableAt(date, station, delayHours=10, tzOverride?)`, `marketCloseUtc(date, station, tzOverride?)`, `buildSnapshot(...)`. LST = January UTC offset of station's IANA tz (DST ignored). `buildSnapshot` returns frozen `DataSnapshot` with `.toDict()` (JSON-safe) and `.toToon()` (TOON v3.0 encoded) methods matching Python output on 3-case fixture.
- [ ] **TS-PARITY-01**: All 5 Python parity fixtures pass against TS `research()` with exact numeric equality on every column. HTTP replay via `msw` against recordings captured from Python; no tolerance loosening.

### Markets (Phases TS-W1 + TS-W5)

- [ ] **TS-MARKETS-01**: Kalshi `KALSHI_SETTLEMENT_STATIONS` + `KNOWN_WRONG_STATIONS` from codegen. `kalshiNhighResolve(contractId, date)` and `kalshiNlowResolve(contractId, date)` return frozen `{settlementSource: 'cli.archive', settlementStation, cityTicker, contractDate}`. Type check: `date` must be `Date | string` (YYYY-MM-DD), not arbitrary timestamp. Contract test: no `KNOWN_WRONG_STATIONS` value appears in the resolver map.
- [ ] **TS-MARKETS-02**: `kalshiSettlementFor(contractId, date)` higher-level helper for ergonomic single-call settlement resolution. Dispatches by contract prefix (`KHIGH*` → `kalshiNhighResolve`, `KLOW*` → `kalshiNlowResolve`); returns the same frozen resolution shape. Wraps TS-MARKETS-01; documented in `docs/browser-integration.md`.
- [ ] **TS-POLY-01**: `PolymarketClient` over `https://gamma-api.polymarket.com` (no auth). User-Agent header required. 0.2s rate limit, 429+5xx retries, pagination `offset += 100` up to 10000 events, dedup by slug. Ports Python Sprint 2t s1+s4 client.
- [ ] **TS-POLY-02**: `polymarketDiscover()` returns active weather events; Tier 0/1/2/3 resolver (Tier 0 → `DeferredMarketError` for Taipei/HK-lowest; Tier 1 `resolutionSource` URL match on Wunderground/NOAA WRH; Tier 2 description URL match; Tier 3 catalog fallback via `resolveStationForEvent`).
- [ ] **TS-POLY-03**: `polymarketSettle(eventId, opts?)` enforces UUID4 regex on `eventId`, 16 KB description cap (→ `PayloadTooLargeError`), netloc allowlist (`wunderground.com`, `weather.gov`, + `www.` variants). Reads `internationalDailyExtremes()` (TS-INTL-01) for resolution; half-up rounding to whole-degree-native; ≤1°F / 0.6°C diff vs the **published Polymarket settlement value** (NOT vs Python `polymarket_settle` — Python v0.1.0 ships only the boundary stub; the substantive engine lives in TS) emits `dataQualityAlert` (not throw); `TooEarlyToSettleError` for unfinalized. **Verification basis:** fixture set of ≥5 historically-resolved Polymarket weather events, each with `{eventId, expectedBucket, expectedValue, polymarketPublishedValue}` — TS engine must produce `expectedBucket` and a value within tolerance of `polymarketPublishedValue`. **Depends on TS-INTL-01 (`internationalDailyExtremes` from TS-W6) AND Python Phase 3.1 INTL-02 (`polymarket-city-stations.json` Group B gated codegen output).**

### Cache + Temporal + Validator (Phase TS-W3)

- [ ] **TS-CACHE-01**: `CacheStore` interface with `get<T>(key)`, `set<T>(key, value, opts?)`, `delete(key)`, `withLock<T>(key, fn)`. Concrete impls: `IndexedDBStore` (browser, via `idb`, lock via Web Locks API), `FsStore` (Node, via `node:fs/promises` + `proper-lockfile`), `MemoryStore` (Workers). `defaultCacheStore()` auto-detects runtime.
- [ ] **TS-CACHE-02**: Cache-skip rules match Python: current LST month/year skipped; any `.live` source skipped; archive endpoints within 30-day volatile window skipped. Cache root `process.env.TRADEWINDS_CACHE_DIR ?? path.join(os.homedir(), '.tradewinds', 'cache-ts')` (Node); IndexedDB DB `tradewinds-cache-v1` (browser). Distinct from Python cache root.
- [ ] **TS-TEMPORAL-01**: `TimePoint(value: Date | string)` rejects naive datetimes, date-only ISO, `NaN`/`Infinity`. Methods: `toUTCDate()`, `toISOString()`, `asZone(tz)` (via `Intl.DateTimeFormat`), `equals/before/after`. Class-level `TimePoint.now()`.
- [ ] **TS-TEMPORAL-02**: `KnowledgeView<Row extends {knowledge_time: string}>(rows, asOf)` provides `.rows()` filtered to `knowledge_time <= asOf` and `.asOf` getter. `LeakageDetector(asOf).check(rows)` and `assertNoLeakage(rows, asOf)` throw `LeakageError` with `toDict()` matching Python `as_of/violating_count/sample_violations` shape.
- [ ] **TS-VALIDATOR-01**: `validateRows(rows, schemaId, opts?)` uses ajv-standalone compiled validators (no runtime ajv dep). Throws `SchemaValidationError` with Python-vocabulary violations: `source_attr_required` / `source_column_required` / `retrieved_at_required` / `required_column_missing` / `non_nullable_has_nulls` / `mixed_null_sentinels` / `dtype_mismatch` / `enum_value_violation` / `unknown_schema_id`. Honors `allowSourceDrift` opt.

### Transforms + QC (Phase TS-W4)

- [ ] **TS-TRANSFORM-01**: Temporal transforms ported with identical column-naming convention `{col}_{op}_{param}`: `lag(rows, col, n)`, `diff(rows, col, n=1)`, `diff2(rows, col)`, `rolling(rows, col, window, fn='mean'|'median'|'min'|'max'|'std'|'count')`. Pure functions over row arrays; produce derived columns with deterministic naming. Match Python `tradewinds.transforms` output byte-for-byte on a shared 50-row fixture.
- [ ] **TS-TRANSFORM-02**: Calendar + cross-feature + preprocessing transforms ported: `calendarFeatures(rows, dateCol, tz?)` (adds `month_sin/cos`, `dow_sin/cos`, `hour_sin/cos` using `Intl.DateTimeFormat` for tz-aware extraction), `spread(rows, colA, colB)`, `windChill(tempF, windMph)` (NWS formula; out-of-domain → null), `heatIndex(tempF, rhPct)` (NWS Rothfusz; out-of-domain → null), `clipOutliers(rows, col, opts={std: 3.0})`. Heat-index `heatIndex(90, 70)` and wind-chill `windChill(20, 15)` match NWS reference tables within 1°F. Out-of-domain inputs return `null` (matching Python's `None`); does NOT throw.
- [x] **TS-QC-01**: `QCEngine.apply(rows)` adds an `obsQcStatus` Int (32-bit bitfield) column. The 5 alpha rules ported with the EXACT rule IDs and bit positions Python `ALPHA_RULES` ships at `packages/core/src/tradewinds/qc.py:103`: `temp_c.out_of_range` (bit 0), `dew_point_c.exceeds_temp` (bit 1), `wind_speed_ms.negative` (bit 2), `wind_dir_deg.out_of_range` (bit 3), `slp_hpa.out_of_range` (bit 4). The rule IDs and bit positions are loaded from codegen `schemas/qc-alpha-rules.json` (a Group B gated output per CROSS-SDK-SYNC.md §1.2) — TS implementation MUST NOT hand-redefine them. `QCRule` Protocol equivalent (TS interface) carries `ruleId: string` + `bitPosition: number` + `evaluate(rows) → boolean[]` fields. **Depends on Python Phase 3.4 QC-01 materialization of `ALPHA_RULES`; if the gated codegen output is empty at TS-W4 time, TS-W4's QC implementation is blocked until that ships.**
- [x] **TS-QC-02**: `crosscheckIemGhcnh(iemRows, ghcnhRows, opts={tolC: 2.0})` returns disagreement rows with `{station, eventTime, tempCIem, tempCGhcnh, deltaC}` columns matching Python output. `clipOutliers` is preprocessing twin.

### Discovery + International + Versioning (Phase TS-W6)

- [ ] **TS-DISCOVERY-01**: `availability(station)` returns `{station, monthsCached, firstMonth, lastMonth}` sourced from `CacheStore` (observation cache + climate cache combined).
- [ ] **TS-DISCOVERY-02**: `describe(schemaId)` returns multi-line description from JSON-Schema `description` fields. `featureCatalog()` returns transforms surface in stable order. `climateGaps(station, from, to)` throws `NotImplementedError` matching Python.
- [ ] **TS-INTL-01**: `internationalDailyExtremes(rows, {stationTz})` rolls per-local-calendar-day `{tempMaxC, tempMinC, tempMaxF, tempMinF}` at whole-°C precision; UTC-wrap edge cases tested for RJTT (UTC+9), SAEZ (UTC-3), NZWN (UTC+12/13 DST). Uses `Intl.DateTimeFormat` for tz-aware day extraction.
- [ ] **TS-VERSION-01**: `DataVersion.fromComponents(...)` via Web Crypto `crypto.subtle.digest('SHA-256')` produces same token as Python `discovery.DataVersion` for identical inputs. Round-trip property test: same inputs → same token across two calls.

### Format Serializers (Phase TS-W3 / TS-W4 partial)

- [ ] **TS-FORMAT-01**: `jsonDumps/jsonLoads`, `csvDumps/csvLoads`, `toonDumps/toonLoads` ported. `parquet` and `dataframe` skipped in v0.1.0 (no DataFrames; parquet deferred to v0.2 via `parquet-wasm`). JSON empty-frame envelope `{columns: [...], data: []}` matches Python.

### Packaging + Release (Phase TS-W7)

- [ ] **TS-BUNDLE-01**: `size-limit` per-package gates enforced in CI: `@tradewinds/core` ≤ 25 KB, `@tradewinds/weather` ≤ 35 KB, `@tradewinds/markets` ≤ 10 KB, `tradewinds` meta ≤ 70 KB (all min+gzip).
- [ ] **TS-RELEASE-01**: Changesets + npm OIDC trusted publishing. 4 pending publishers registered on npmjs.com pointing at `helloiamvu/tradewinds` + workflow `release-ts.yml` + environment `npm`. `vts-0.1.0rc1` tag → npm `--tag next` for soak; `vts-0.1.0` tag → npm `--tag latest`.
- [ ] **TS-DOCS-01**: NumPy-style equivalent JSDoc on all public surface; typedoc generation under `docs/ts-api/`.
- [ ] **TS-DOCS-02**: README quickstart (Node + browser samples) timed at <5 minutes by an external person (not the author).
- [ ] **TS-DOCS-03**: `docs/browser-integration.md` end-to-end guide for browser consumers (Chrome extensions, web dashboards, Cloudflare Workers): MV3 `host_permissions` (when applicable), service-worker import pattern, content-script ↔ service-worker `chrome.runtime.sendMessage` pattern, IIFE bundle alternative for content-script use. In-repo `packages-ts/examples/chrome-extension-mvp/` is the worked example referenced from the guide.
- [ ] **TS-CI-02**: `release-ts.yml` + `drift-rotate-ts.yml` (weekly Mon 07:30 UTC, soft-fail watchdog mirroring Python `drift-rotate.yml`).

### TS Phase Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| TS-PKG-01, TS-PKG-02, TS-CODEGEN-01, TS-CODEGEN-02, TS-CORS-01, TS-CI-01, TS-SYNC-01, TS-SYNC-02, TS-SYNC-03 | TS-W0 | Pending |
| TS-CORE-01, TS-CORE-02, TS-WEATHER-01, TS-WEATHER-02, TS-MARKETS-01, TS-RESEARCH-01, TS-SNAPSHOT-01 | TS-W1 | Pending |
| TS-WEATHER-03, TS-WEATHER-04, TS-PARSER-01..04, TS-MERGE-01, TS-PARITY-01 | TS-W2 | Pending |
| TS-CACHE-01, TS-CACHE-02, TS-TEMPORAL-01, TS-TEMPORAL-02, TS-VALIDATOR-01, TS-FORMAT-01 | TS-W3 | Pending |
| TS-RESEARCH-02, TS-MODE2-01, TS-TRANSFORM-01, TS-TRANSFORM-02, TS-QC-01, TS-QC-02 | TS-W4 | Pending |
| TS-MARKETS-02, TS-POLY-01, TS-POLY-02, TS-POLY-03 | TS-W5 | Pending |
| TS-DISCOVERY-01, TS-DISCOVERY-02, TS-INTL-01, TS-VERSION-01 | TS-W6 | Pending |
| TS-BUNDLE-01, TS-RELEASE-01, TS-DOCS-01, TS-DOCS-02, TS-DOCS-03, TS-CI-02 | TS-W7 | Pending |

**TS coverage:** 42 requirements, all mapped to TS-W0..TS-W7.

## Phase 6: Pandas 3 Readiness + Optional Polars Backend (v0.2+)

Two paired tracks. **PANDAS3** drops the `pandas<3.0` cap (PKG-05) and re-captures the parity fixtures against 3.x; **POLARS** ships an opt-in backend so quants who prefer Polars don't pay the pandas-only tax. See ROADMAP § "Phase 6" for the full goal statement.

### Pandas 3 Track

- [ ] **PANDAS3-01**: Audit + remediate every datetime/dtype risk site flagged in the Phase 6 recon. At minimum: validator string-vs-object branching (`packages/core/src/tradewinds/core/validator.py:84,100,119-121,150`); `pd.Series([], dtype="datetime64[ns, UTC]")` literal in `packages/weather/src/tradewinds/weather/catalog/cli.py:158,216`; `to_datetime` calls in `_internal/_pairs.py:397`, `cli.py:149-151,225`, `_obs_projection.py:172`, `forecast_nwp.py` (3 sites). Each site lands a remediation comment citing the pandas 3.0 whatsnew section that motivated it.
- [ ] **PANDAS3-02**: Drop the `pandas<3.0` cap in all 6 affected extras: `tradewinds[parquet]`, `tradewinds[research]`, `tradewinds-weather[parquet]`, `tradewinds-weather[nwp]`, `tradewinds-markets[parquet]`, `tradewinds-markets[polymarket]`. New pin: `pandas>=2.2,<4.0`. CHANGELOG entry documents the move.
- [ ] **PANDAS3-03**: CI test matrix runs the fast-suite (`pytest -m "not live"`) under BOTH `pandas==2.2.x` (lower-bound lockfile) AND `pandas>=3.0,<4.0` (upper-bound lockfile). Matrix failure on either side blocks merge. uv tox-equivalent uses `--resolution lowest-direct` / `--resolution highest`.
- [ ] **PANDAS3-04**: Pandas-3 parity bridge (NOT fixture re-capture). The canonical 2.x fixtures at `tests/fixtures/parity/case_*.parquet` stay immutable (v0.1.0 contract). New `tests/fixtures/parity/coerce_pd3.py` defines an invertible transform: `coerce_2x_to_3x(parquet_path)` → pd.DataFrame (applies `ns→us` datetime coercion + `object→string` dtype promotion); `coerce_3x_to_2x(df)` → pd.DataFrame is the documented inverse. Parity test under pandas 3.x reads the 2.x fixture, applies the forward coercion, compares against live `research()` output. Round-trip test asserts `coerce_3x_to_2x(coerce_2x_to_3x(case)) == case`. NO new fixture files on disk. Tolerance ladder carries forward from `test_parity.py`: `obs_mean_f` / `obs_mean_dewpoint_f` / `obs_total_precip_in` keep `atol=1e-12` (worst-case ULP drift ~2.84e-14 under pandas 2.x). Sub-task: re-measure worst-case ULP drift on pandas 3.x before merging; if drift > 1e-12, the rung promotes to atol=1e-10 with the measurement documented in `tests/fixtures/parity/README.md`. See PLAN W1-T5 for the full spec.
- [ ] **PANDAS3-05**: CoW (Copy-on-Write) audit on every `.copy()` / `.loc[...] = ` / chained-write site in the SDK. Confirm none of the parity-locked modules (`_internal/_pairs.py`, `core/merge.py`, `core/_climate.py`, validator) silently changed semantics when CoW becomes the default. Document any required `.copy()` insertions per site.
- [ ] **PANDAS3-06**: Doctest examples in `validator.py:209-217`, `knowledge_view.py:46-58`, `leakage.py:54-73` updated to be pandas-3-clean (or `# doctest: +SKIP` if the bytes shift across versions). `pytest --doctest-modules` passes on both pandas lockfiles.

### Polars Backend Track

- [ ] **POLARS-01**: `backend: Literal["pandas","polars"]="pandas"` kwarg on every public DataFrame-returning entry point: `tradewinds.research()`, `tradewinds.mode2.research_by_source()`, `tradewinds.markets.polymarket.polymarket_discover()`, `tradewinds.forecasts.forecast_nwp()`, `tradewinds.international.daily_extremes()`. Default stays pandas. `daily_extremes()` default return stays `list[dict]` (preserves v0.1.0 contract); the four DataFrame-returning surfaces default to `return_type="dataframe"` (pandas frame; v0.1.0 shape). `backend="polars"` requires `return_type="wrapper"` and returns a `TradewindsResult` carrying a Polars frame; calling `backend="polars"` with the default `return_type="dataframe"` raises `ValueError`. See PLAN W3-T2 + W3-T3 for the canonical spec.
- [ ] **POLARS-02**: New `tradewinds.core.result.TradewindsResult` dataclass. Fields: `frame: pd.DataFrame | pl.DataFrame`, `source: str`, `retrieved_at: datetime`, `schema_id: str | None`, `qc: dict | None`, `data_version: DataVersion | None`. Carries provenance separate from the frame so polars (no `.attrs`) works equivalently to pandas. New backend-aware paths return `TradewindsResult`; legacy DataFrame-direct return kept under a one-release deprecation shim.
- [ ] **POLARS-03**: Narwhals internal data layer for the 5 cleanly-portable modules: `transforms.py`, `preprocessing.py`, `qc.crosscheck_iem_ghcnh`, `core/temporal/knowledge_view.py`, `core/formats/{json,csv,toon}.py`. Each refactored to `nw.from_native(df) → ops → nw.to_native(...)`. Per-backend test matrix asserts identical output on both pandas + polars inputs.
- [ ] **POLARS-04**: Parity-locked modules (`_internal/_pairs.py`, `core/merge.py`, `core/_climate.py`, `core/validator.py`, `core/temporal/leakage.py`, `core/temporal/timepoint.py`, `core/_json_safe.py`) stay pandas-only. Their lift-pinned status is unchanged. Any polars-mode caller hitting these paths flows through a pandas-mediated thunk; the conversion is documented in the module docstring + a `polars→pandas conversion at parity-locked boundary` comment.
- [ ] **POLARS-05**: New `[polars]` optional extra on all three packages: `tradewinds[polars]`, `tradewinds-weather[polars]`, `tradewinds-markets[polars]`. Adds `polars>=1.0,<2.0` + `narwhals>=1.20,<2.0`. Default install never pulls polars. Calling a public surface with `backend="polars"` without the extra raises `SourceUnavailableError` carrying `"Install with: pip install tradewinds[polars]"` install hint (matching the `[nwp]` pattern).
- [ ] **POLARS-06**: Round-trip parity property test: for every parity fixture, `polars_df.to_pandas().equals(pandas_df)` holds (allowing for the pandas→polars datetime-resolution conversion documented as acceptable in the test). Hypothesis-driven random-fixture variant strengthens the invariant beyond the 5 frozen cases.
- [ ] **POLARS-07**: Sort-stability invariant — narwhals `sort()` MUST preserve the `kind="mergesort"` ordering the parity gate locked. Test asserts identical row ordering across pandas + polars for the merge layer's per-source dedup. If narwhals can't guarantee this, the polars merge path falls back to pandas (the merge module is on the POLARS-04 exclusion list anyway).
- [ ] **POLARS-08**: CI matrix gates: cross-backend test job installs `[polars]` extra and runs the polars-only path of every public surface. Job is required on every PR touching `tradewinds.research`, `tradewinds.mode2`, `tradewinds.discovery`, `tradewinds.transforms`, `tradewinds.preprocessing`, or the new `tradewinds.core.result` module. Marker `@pytest.mark.polars` gates the suite; ungated runs skip cleanly without the extra.

### Phase 6 Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| PANDAS3-01..PANDAS3-06 | 6 (PANDAS3 track) | Pending |
| POLARS-01..POLARS-08 | 6 (POLARS track) | Pending |

**Phase 6 coverage:** 14 requirements (6 pandas-3 + 8 polars), all mapped to Phase 6.

## Phase 8: Polymarket US Coverage + Per-Issuer Settlement Invariants (v0.2+)

Closes the silent-corruption gap when Polymarket and Kalshi disagree on which station settles the same US city. Today the Polymarket city catalog is international-only (40 entries, zero US) — US Polymarket events bottom out in `PolymarketSettlementError`. `polymarket.KNOWN_WRONG_STATIONS` doesn't exist, so the per-issuer denylist namespace is asymmetric with `kalshi_stations.KNOWN_WRONG_STATIONS`. Adds US cities with empirically-verified Wunderground stations (NYC → KLGA, NOT KNYC) + symmetric per-issuer denylists + Tier 1.5 URL extraction so events embedding `wunderground.com/.../KLGA` resolve without catalog dependency.

- [ ] **POLY-US-01**: Polymarket city catalog (`polymarket_city_stations.json`) extended with US cities. Each entry shaped `{"high": "ICAO", "low": "ICAO", "default": "ICAO"}`. Stations empirically verified by parsing Polymarket event `resolutionSource` URLs (Wunderground regex), NOT mirrored from Kalshi. Per-city Polymarket-event citation URL recorded in a sibling registry (`POLYMARKET_CITY_CITATIONS`) so the source-of-truth is provable + auditable.
- [ ] **POLY-US-02**: `polymarket.KNOWN_WRONG_STATIONS: Final[Mapping[str, frozenset[str]]]` introduced symmetric to `kalshi_stations.KNOWN_WRONG_STATIONS`. For `nyc`: `{KNYC, KJFK, KEWR}` (Polymarket uses KLGA). Namespace-isolated per issuer (Polymarket's `KLGA` is correct; Kalshi's denylist includes `KLGA` because Kalshi uses `KNYC`). Contract test asserts no Polymarket catalog entry resolves to its own per-city denylist value.
- [ ] **POLY-US-03**: Tier 1.5 URL extraction in `polymarket._per_event_station` (Python) + `polymarket/resolver.ts` (TS). New helper `extract_icao_from_resolution_source(text)` runs a Wunderground URL regex (`https?://(?:www\.)?wunderground\.com/[^\s]*?\b(K[A-Z]{3})\b`) against `event.description` / `event.resolutionSource` and returns the first matched ICAO. Inserted between Tier 1 (`event.city`) and Tier 2 (slug derive) — when the URL extractor returns a value, it overrides catalog-derived stations and bypasses both `_derive_city` and the city map. Records `resolution_tier="url_extract"` on the discovery/settlement record.
- [ ] **POLY-US-04**: Cross-issuer assertion test (`tests/test_cross_issuer_station_identity.py`) asserts: `KALSHI_SETTLEMENT_STATIONS["NYC"].station == "KNYC"` AND `POLYMARKET_CITY_STATIONS["nyc"]["default"] == "KLGA"` AND `"KLGA" not in polymarket.KNOWN_WRONG_STATIONS["nyc"]` AND `"KLGA" in kalshi_stations.KNOWN_WRONG_STATIONS` AND `"KNYC" in polymarket.KNOWN_WRONG_STATIONS["nyc"]`. Plus the parametric loop: every Polymarket US city's `default` station does NOT appear in its own per-city denylist; every Kalshi city's station does NOT appear in Kalshi's global denylist.
- [ ] **POLY-US-05**: Paired TS update via codegen. `schemas/polymarket-city-stations.json` regenerates from the Python source via `scripts/export_schemas.py` (already wired). `packages-ts/markets/src/data/generated/polymarket-city-stations.ts` regenerates via `pnpm codegen`. Schema shape is unchanged (cities map allows additional keys); no manifest version bump. `polymarket.KNOWN_WRONG_STATIONS` is paired in TS as `POLYMARKET_KNOWN_WRONG_STATIONS` (NOT codegen — small enough to maintain hand-paired; alphabetized JSON exporter side-effect would conflate it with the cities map).
- [ ] **POLY-US-06**: Parity-fixture pre-flight gate. Re-run all 5 Python parity fixtures (`uv run pytest tests/test_parity.py -q`) + TS parity gate (`pnpm --filter @tradewinds/core test parity`) before merging. Phase 8 touches catalog-data + resolver logic but does not touch parity-locked `_internal/_pairs.py` / `_internal/merge/`, so the gate should be green; the run is the empirical proof.

### Phase 8 Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| POLY-US-01..POLY-US-06 | 8 | Pending |

**Phase 8 coverage:** 6 requirements, all mapped to Phase 8 (paired Python + TS per Dual-SDK Rule).

## Phase 9: Markets Trade History — Kalshi + Polymarket (v0.2+)

Promotes deferred MARKETS-04 from Sprint 0.5+ into a first-class phase. Adds `tradewinds.markets.kalshi.trades` (candles + fills + orderbook snapshots) + `tradewinds.markets.polymarket.trades` (Gamma price history + snapshot) with paired TS subpath `@tradewinds/markets/trades`. Today there is NO way to get trade data for any market; this phase unblocks the `include_trades=True` path in Phase 10's composable `research()`.

- [ ] **TRADES-01**: `tradewinds.markets.kalshi.trades.candles(ticker, *, interval, from_, to)` — OHLCV via `/markets/{ticker}/candlesticks`. Rate-limited shared HTTP client. `source="kalshi"` column preserved on every row.
- [ ] **TRADES-02**: `tradewinds.markets.kalshi.trades.fills(ticker, *, since)` — historical fills via `/markets/trades`. Pagination cursors handled (Kalshi uses `cursor` field).
- [ ] **TRADES-03**: `tradewinds.markets.kalshi.trades.orderbook(ticker)` — current book snapshot via `/markets/{ticker}/orderbook`. Snapshot only in v0.2; orderbook tape deferred to v0.3.
- [ ] **TRADES-04**: `tradewinds.markets.polymarket.trades.history(event_id, *, from_, to)` — Gamma price history endpoint (`/markets/timeseries`). Returns time-indexed price + volume rows (Polymarket reports last_price + volume per interval; no separate H/L/C).
- [ ] **TRADES-05**: `tradewinds.markets.polymarket.trades.snapshot(event_id)` — current state from Gamma `/events/{id}`. Returns latest price + volume per outcome.
- [ ] **TRADES-06**: Cache layer: trades cached in `~/.tradewinds/cache/v1/trades/{issuer}/{ticker}/{YYYY-MM}.parquet` (Python) / IndexedDB equivalent (TS). Volatile-window rules apply (current UTC month rewriteable; trades aren't LST-localized so UTC is the right granularity).
- [ ] **TRADES-07**: Paired TS modules at `@tradewinds/markets/trades` subpath. Same surface, row-equivalent output. tsup entry + package.json export added.
- [ ] **TRADES-08**: Rate-limit politeness floors documented at `.planning/research/MARKETS-RATE-LIMITS.md` per source — Kalshi (10 req/sec per public docs; settle for 0.1s polite floor), Polymarket Gamma (0.2s polite floor inherited from `_polymarket_client.py`). Empirical spike deferred (manual smoke test only — running a real spike against live endpoints in CI is a DoS concern).

### Phase 9 Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| TRADES-01..TRADES-08 | 9 | Pending |

**Phase 9 coverage:** 8 requirements, all mapped to Phase 9 (paired Python + TS per Dual-SDK Rule).

## Phase 10: Composable `research()` — Multi-Contract Basis Trade (v0.2+)

Evolves `research()` from station-only into the composable surface quants actually need: "give me Kalshi NYC paired with KNYC weather", "give me Polymarket NYC paired with KLGA weather", "give me BOTH and compute the basis spread in one call". Adds mutually-exclusive selectors (`station=` | `city=` | `contract=` | `contracts=`) + optional kwargs (`station_override=`, `sources=` / `source=`, `include_trades=`) + a `discover(city=...)` ergonomic surface that shows which station settles which issuer's market BEFORE the user picks.

- [ ] **COMPOSE-01**: `research(station=, city=, contract=, contracts=)` selectors mutually-exclusive at the dispatch layer. Validation error on multiple selectors.
- [ ] **COMPOSE-02**: `research(contract="kalshi:KXHIGHNY-25MAY26-T79")` auto-resolves to settlement station via Phase 8 catalog + Phase 9 trades, returns existing `research(station=...)` columns + market metadata (settlement_value, market_close_utc) per date.
- [ ] **COMPOSE-03**: `research(contracts=[...], include_trades=True)` returns multi-issuer DataFrame with per-station weather columns + per-issuer trade columns + computed `basis_f` column (cross-issuer station difference) where applicable.
- [ ] **COMPOSE-04**: `research(city="NYC")` returns multi-station DataFrame (KNYC + KLGA + KJFK + KEWR rows for that date range). `settles_for` annotation column lists which markets settle against each.
- [ ] **COMPOSE-05**: `research(contract=..., station_override=...)` allows basis-research with explicit station mismatch. Emits `StationOverrideWarning` loudly. Output row carries `settlement_mismatch=True` flag.
- [ ] **COMPOSE-06**: `sources=[...]` (plural — Mode 1 subset, dedupe within) and `source=...` (singular — Mode 2 pin, error on mismatch) — mutually exclusive. Inherits existing Mode 1 / Mode 2 semantics.
- [ ] **COMPOSE-07**: `discover(city=...)` ergonomic surface (separate function, not a `research()` selector) — returns per-station table with `settles_for` annotations so cross-issuer station asymmetry visible before user picks.
- [ ] **COMPOSE-08**: Paired TS evolution. Same surface shape via `research({ station, city, contract, contracts, ... })` options object. Mutual-exclusion enforced by TypeScript union types.
- [ ] **COMPOSE-09**: Backwards compatibility: existing `research(station, from_date, to_date)` signature MUST still work unchanged. New surface is additive — no breaking change.

### Phase 10 Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| COMPOSE-01..COMPOSE-09 | 10 | Pending |

**Phase 10 coverage:** 9 requirements, all mapped to Phase 10 (paired Python + TS per Dual-SDK Rule).

---
*Requirements defined: 2026-05-21; Phase 8 added 2026-05-24; Phase 9 added 2026-05-24; Phase 10 added 2026-05-25*
*Last updated: 2026-05-23 — Phase 6 (pandas 3 readiness + optional polars backend) added; PANDAS3-01..06 and POLARS-01..08 promoted from deferred; 14 new IDs mapped to Phase 6*

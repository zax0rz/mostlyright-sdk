---
gsd_state_version: 1.0
milestone: v0.1.0
milestone_name: Local-first SDK ship (RC1 ready)
status: ready_to_publish
stopped_at: "12/12 phases of v0.1.0 complete on main with ALL SEAMS REPLACED. Phase progression: 4 at 7655b0e; 3.1 REAL at 19d7416; 3.2 REAL at de9b3af; 3.3 REAL at 3b63870; 3.4 REAL at 691b228; 3.5 REAL at 11d167a; 3.6 REAL at 922225b; Mode 2 REAL at f4d75d7. 1662 tests passing (was 1603; +59 net new for Phase 3.4 QC wiring + 3.5 preprocessing + 3.6 discovery + Mode 2). Phase 3.4 ships QC engine wired into research(qc=True) with sidecar writer; Phase 3.5 ships tradewinds.preprocessing module + day_of_year cyclical features; Phase 3.6 ships availability/climate_gaps/describe/feature_catalog + DataVersion.for_research() reproducibility token + settlement_date_for / settlement_window_utc wrappers; Mode 2 ships research_by_source() with parser-tag alias bridge and truthful per-row source provenance. CI workflows shipped: test.yml + wheel-metadata-check.yml + release.yml + release-testpypi.yml + drift-rotate.yml. PyPI publish workflows EXIST but are operator-gated."
last_updated: "2026-05-23T22:00:00.000Z"
last_activity: 2026-05-23 -- Mode 2 REAL impl merged to main at f4d75d7; 1662 tests passing. ALL seams (Phase 3.2 NWP + Phase 3.3 Polymarket + Phase 3.4 QC wire + Phase 3.5 preprocessing + Phase 3.6 discovery + Mode 2) replaced with real implementations across 7 review iterations. Each phase ran codex high + python-architect; closed 5 CRITICAL/HIGH + 22 P1/P2 cumulatively.
progress:
  total_phases: 12
  completed_phases: 12
  total_plans: 36
  completed_plans: 36
  percent: 100
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-05-21; STATE.md refreshed 2026-05-23)

**Core value:** `research(contract, station, from_date, to_date)` returns clean, leakage-free, source-identified training pairs that backtest the same way they trade — and any train/infer source mismatch errors loudly instead of silently corrupting a model.
**Current focus:** v0.1.0rc1 publish (operator-gated PyPI trusted-publisher setup)

## Current Position

Phase: ALL 12 of 12 v0.1.0 phases complete on `main`
Plan: Phase 4 PLAN.md committed; all 5 waves shipped via parallel execution
Status: v0.1.0rc1 ready to publish (operator-gated)
Last activity: 2026-05-23 — Phase 4 merged to main at 7655b0e (1453 tests passing)

Progress: [██████████] 100% (12/12 phases complete in v0.1.0; ready to tag rc1)

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

## Session Continuity

Last session: 2026-05-22
Stopped at: ROADMAP enriched with 4 new phases (2.1, 3.1, 3.2, 3.3) for v0.1.0 scope expansion (international + multi-forecast + Polymarket + Sprint 2o lineage). Phase stubs created via `gsd-tools phase insert`; ROADMAP entries enriched with full Goal/Depends-on/Requirements/Success Criteria/Out-of-Scope/Review-panel blocks. STATE.md updated with Roadmap Evolution section + new decisions + new blockers/concerns. **Pending follow-ups before execution:** (1) add LINEAGE-01..05 + INTL-01..05 + NWP-01..06 + POLY-01..05 entries to REQUIREMENTS.md (POLY-01 currently a Sprint 0.5+ deferral — activate and split); (2) update PROJECT.md "Active scope" to reflect expanded v0.1.0; (3) run `/gsd-plan-phase` per new phase to write detailed PLAN.md; (4) decide whether to migrate existing `.planning/phase-NN-...` dirs to new `.planning/phases/NN.M-...` convention created by gsd-tools, or move the new dirs to match existing convention.
Resume file: Run `/gsd-plan-phase 2.1` (next blocking sequence) — Phase 2.1 must land before 3.1/3.3.
Branch state: Working on `planning/v01-intl-nwp-polymarket` off `merged-vision@d698886`. Commits not yet made — user decides when to commit. Suggested commit sequence: (a) ROADMAP + STATE updates as one commit; (b) REQUIREMENTS.md additions as separate commit; (c) PROJECT.md update as separate commit; (d) per-phase PLAN.md files in subsequent commits via `/gsd-plan-phase`.

# Roadmap: tradewinds

## Overview

tradewinds is a local-first Python SDK for Kalshi NHIGH/NLOW prediction-market weather contracts, shipping in v0.1.0 with three-package PyPI distribution (`tradewinds` / `tradewinds-weather` / `tradewinds-markets`), byte-equivalent parity to `mostlyright==0.14.1`, structural temporal-safety primitives (`KnowledgeView`, `TimePoint`), and source-identity enforcement (`SourceMismatchError`). The v0.1.0 release follows a 14-day two-phase plan: Phase A (Days 1-4) lifts v0.14.1 parity behavior verbatim and gates on a 5-fixture byte-equivalent parity test; Phase B (Days 5-14) layers the temporal + source-identity primitives, catalog adapters, Kalshi contract specs, and migration test on top. The MCP server is deferred to v0.2; its seam (`packages/mcp/`) is scaffolded as a stub only. Two-lane parallel execution (Lane V / Lane F) with cross-review is mandatory throughout.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3, 4): Planned milestone work for v0.1.0
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: v0.14.1 Parity Lift** - Day 1 scaffold-prep + lift v0.14.1 parsers/cache; ship 5-fixture byte-equivalent parity gate and alpha1 wheels (Days 1-4)
- [ ] **Phase 1.5: Fetcher Optimization + Cross-Source Parallelism** [INSERTED 2026-05-22] - Lift mostlyright PR #85 (365-day chunks, cache-poison fix, leap-year + UTC + HTTP_TIMEOUT) + add cross-source parallelism in `research.py` + rate-limit spike for AWC/GHCNh (Days 4.5-5.5). **Sequenced strictly between Phase 1 and Phase 2** — see architect-review notes; co-execution with Phase 2 was rejected.
- [ ] **Phase 2: Core Primitives + Catalog Adapters** - Temporal/schema/validator/leakage/exceptions/formats in `core/`; four weather adapters + Kalshi market specs; two-lane parallel build (Days 5-9)
- [ ] **Phase 3: Mode 2 Integration + Migration Gate** - `research()` Mode 2 source-explicit dispatch; cache enhancements (filelock, LST-skip, volatile window); contract tests + `mostly-light/kxhigh` dry-run migration parity (Days 10-11)
- [ ] **Phase 4: Coverage, Docs, CI/CD, Release** - ≥90% branch coverage on `core/`; <5-min quickstart timed by external person; GH Actions trusted publishing; two-tier fixture set; v0.1.0 ship (Days 12-14)

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

### Phase 1.5: Fetcher Optimization + Cross-Source Parallelism [INSERTED 2026-05-22]
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

**Review panel**: 4 reviewers temporarily (codex + python-architect + security + pure-codex-medium) — chunk-size + cache-filename + timeout changes are parity-critical and security-adjacent (HTTP timeout × payload-size attack surface). Per `REVIEW-DISCIPLINE.md`'s lineage note: "v0.2 likely adds security-reviewer + architect as separate roles once the surface grows" — Phase 1.5 hits that threshold sooner.

**Parity gate handling**: chunk size affects request pattern. Merge-output sensitivity is REAL — `_internal/merge/observations.py` uses strict `>` priority comparison (first-row-seen wins on same-priority ties), so row-iteration-order from the fetcher matters at tie boundaries (SPECI-vs-METAR at same `(station, observed_at, observation_type)`, cross-source same-priority). **Mandatory pre-flight before Phase 1.5 merges to `merged-vision`**: re-run all 5 parity fixtures against 365-day-chunked `research()` output. If any fixture drifts, either (a) revert Phase 1.5 chunk-size change, OR (b) change merge to `>=` with deterministic secondary key (`source` then `chunk_start`) and re-validate. Decision is post-spike; phase doesn't merge until parity green.

**Plans**: TBD

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

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → **1.5** → 2 → 3 → 4 (decimal phases sequence between their surrounding integers per the numbering convention above).

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. v0.14.1 Parity Lift | 0/TBD | Wave 1 of 4 done (cache + merge + snapshot/_stations on `merged-vision`) | - |
| 1.5. Fetcher Optimization + Cross-Source Parallelism | 0/TBD | Not started — strictly serial after Phase 1, strictly before Phase 2 | - |
| 2. Core Primitives + Catalog Adapters | 0/TBD | Not started (PLAN.md committed) | - |
| 3. Mode 2 Integration + Migration Gate | 0/TBD | Not started | - |
| 4. Coverage, Docs, CI/CD, Release | 0/TBD | Not started | - |

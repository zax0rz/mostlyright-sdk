# Roadmap: tradewinds

## Overview

tradewinds is a local-first Python SDK for Kalshi NHIGH/NLOW prediction-market weather contracts, shipping in v0.1.0 with three-package PyPI distribution (`tradewinds` / `tradewinds-weather` / `tradewinds-markets`), byte-equivalent parity to `mostlyright==0.14.1`, structural temporal-safety primitives (`KnowledgeView`, `TimePoint`), and source-identity enforcement (`SourceMismatchError`). The v0.1.0 release follows a 14-day two-phase plan: Phase A (Days 1-4) lifts v0.14.1 parity behavior verbatim and gates on a 5-fixture byte-equivalent parity test; Phase B (Days 5-14) layers the temporal + source-identity primitives, catalog adapters, Kalshi contract specs, and migration test on top. The MCP server is deferred to v0.2; its seam (`packages/mcp/`) is scaffolded as a stub only. Two-lane parallel execution (Lane V / Lane F) with cross-review is mandatory throughout.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3, 4): Planned milestone work for v0.1.0
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: v0.14.1 Parity Lift** - Day 1 scaffold-prep + lift v0.14.1 parsers/cache; ship 5-fixture byte-equivalent parity gate and alpha1 wheels (Days 1-4)
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
Phases execute in numeric order: 1 → 2 → 3 → 4

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. v0.14.1 Parity Lift | 0/TBD | Not started | - |
| 2. Core Primitives + Catalog Adapters | 0/TBD | Not started | - |
| 3. Mode 2 Integration + Migration Gate | 0/TBD | Not started | - |
| 4. Coverage, Docs, CI/CD, Release | 0/TBD | Not started | - |

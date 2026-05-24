# Changelog

All notable changes to tradewinds. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); the project adheres
to [Semantic Versioning](https://semver.org/spec/v2.0.0.html) once it ships
0.1.0 to PyPI.

## [Unreleased]

### Phase 6 — Pandas 3 readiness + Optional Polars Backend (v0.2)

#### Added
- **`tradewinds.core.TradewindsResult`** — backend-neutral provenance
  wrapper (frame + source + retrieved_at + schema_id + qc + data_version).
  Both pandas and polars backends produce the same wrapper shape;
  `.legacy_df_with_attrs()` bridges callers still consuming
  `df.attrs["source"]` directly for one release cycle.
- **Opt-in `backend="polars"` kwarg** on every public DataFrame-returning
  entry point: `research()`, `research_by_source()`, `polymarket_discover()`,
  `forecast_nwp()`, `daily_extremes()`. Default stays `backend="pandas"`
  so v0.1.0 callers see zero behaviour change. Pairs with a new
  `return_type="dataframe"|"wrapper"` kwarg; polars output requires
  `return_type="wrapper"` (polars frames have no `df.attrs`).
- **`[polars]` optional extra** on all three packages (`polars>=1.0,<2.0`
  + `narwhals>=1.20,<2.0`). Calling `backend="polars"` without the extra
  raises `SourceUnavailableError` with install hint (mirrors `[nwp]`).
- **Pandas 3 compatibility** — the `pandas<3.0` cap is dropped across
  all 6 affected extras (`pandas>=2.2,<4.0`). Dual-pandas CI matrix
  re-runs the fast suite on the latest pandas 3.x lockfile.
  `tests/fixtures/parity/coerce_pd3.py` defines the invertible
  `ns→us` + `object→string` bridge; `ulp_drift_pd3.json` carries the
  committed per-column max-abs drift measurement; `measure_ulp_drift.py`
  refreshes the artifact under pandas 3.x.
- **`@pytest.mark.polars` marker** registered + cross-backend CI job
  (`polars-suite`) that installs the `[polars]` extra on each member
  package and runs the polars-marked tests. `with-polars=false` runs
  default install with `pytest -m "not live and not polars"`.
- 5 cleanly-portable modules (`transforms`, `preprocessing`,
  `qc.crosscheck_iem_ghcnh`, `core.formats.{json,csv,toon}`,
  `KnowledgeView` via wrapper) now accept pandas OR polars input via a
  narwhals-mediated boundary shim — return type follows caller backend.

#### Changed
- Parity-locked modules (`_internal/_pairs`, `core/merge`,
  `core/validator`, `core/_json_safe`, `core/temporal/timepoint`,
  `core/temporal/leakage`, `core/_climate`) stay pandas end-to-end;
  polars-mode `research()` converts ONLY at the outer return boundary.
  Defense-in-depth grep test rejects future narwhals/polars imports
  in these modules.

#### Migration
- v0.1.0 `df = research(...)` continues to work unchanged.
- New v0.2: `result = research(..., return_type="wrapper")` returns a
  `TradewindsResult` with `result.frame`, `result.source`,
  `result.retrieved_at`.
- New v0.2: `result = research(..., backend="polars", return_type="wrapper")`
  returns a polars `DataFrame` on `result.frame` plus the same
  provenance fields.
- Callers consuming `df.attrs["source"]` directly should migrate to
  `result.source` over the v0.2 → v0.3 window; v0.2 supports both.

### Phase 4 — Coverage, Docs, CI/CD, Release

#### Added
- `.github/workflows/test.yml` — fast test suite (`pytest -m "not live"`) +
  ruff lint + ruff format check on every push (no branch filter) /
  PR (Python 3.11/3.12/3.13 matrix). Separate `coverage-gate` job enforces
  **≥90% branch coverage on the CORE SEMANTIC SURFACE of `tradewinds.core`**
  (Phase 4 SC-1 HARD GATE) via `--cov-fail-under=90 --cov-branch`.
  Scope explicitly excludes `core/schemas/*` (pure-data ColumnSpec lists)
  and `core/formats/_toon*` (~557 LOC of internal TOON encoder edge cases;
  direct coverage deferred to Phase 5 MCP when TOON starts going over the
  wire). Documented as a known coverage gap; the SC-1 wording should be
  read as "core semantic surface", not "every byte under `core/`".
- `.github/workflows/wheel-metadata-check.yml` — runs on every push that
  touches `packages/*/pyproject.toml`; builds all three sibling wheels and
  greps each one's `METADATA` for the explicit `Requires-Dist: tradewinds
  >=0.1.0,<0.2` pin. Blocks merges that drop the pin (Phase 4 SC-4 / CI-04).
- `.github/workflows/release.yml` — PEP 740 trusted-publishing workflow that
  fires on every `v*` tag and publishes the three sibling distributions to
  PyPI (one job per package because trusted publishing is registered
  per-package). Includes the CI-04 METADATA gate before publish (Phase 4
  SC-3 / CI-03).
- `scripts/check_wheel_metadata.py` — local + CI script that greps each
  built wheel's `Requires-Dist` line for both the `<0.2` upper bound AND a
  `>=0.1.0` lower bound (any order; hatchling normalizes the order in
  METADATA). Exits 0 when every sibling-package wheel passes.
- `tests/fixtures/README.md` + `tests/fixtures/drift/.gitkeep` — scaffolds
  the two-tier fixture policy (Phase 4 SC-5): `parity/` is FROZEN (Phase 1
  Day 0.5 baseline), `drift/` will be weekly-rotated by a cron job in a
  follow-up alpha. README documents the never-refresh policy on `parity/`
  + the refresh mechanism + drift-tolerance band.
- README expanded: Mode 1 v0.14.1 parity example,
  `TimePoint`/`KnowledgeView`/`LeakageDetector` temporal-safety primitives,
  `validate_dataframe()` source-identity invariant, `kalshi_nhigh`/`kalshi_nlow`
  Kalshi resolvers, "Why local-first" rationale, link to per-adapter docs.

#### Changed
- `pyproject.toml` adds `[tool.coverage.run]` + `[tool.coverage.report]`
  config so a local
  `uv run pytest --cov=packages/core/src/tradewinds/core --cov-branch`
  matches the CI gate. `omit` excludes `core/schemas/*` (pure-data
  ColumnSpec lists; coverage dominated by import-time evaluation already
  asserted by the existing contract tests).

### Phase 1.5 — Fetcher Optimization + Cross-Source Parallelism

#### Added
- `tradewinds.weather._fetchers._iem_chunks` — shared calendar-year chunkers
  (`yearly_chunks_inclusive`, `yearly_chunks_exclusive_end`), leap-year-safe.
- `tradewinds.research._prefetch_sources` — PERF-04 concurrent fan-out of the
  4 source-fetch operations (IEM ASOS, IEM CLI, GHCNh, AWC) via
  `concurrent.futures.ThreadPoolExecutor(max_workers=4)`. Implements **Option C**
  from `.planning/research/SOURCE-LIMITS.md` (no shared `threading.Lock`; each
  fetcher preserves its own politeness delay; spike confirmed zero 503s at
  this load). Pitfall 6 timing pattern: `submitted_at[name]` captured
  immediately after `ex.submit()` so per-source timing measures actual work,
  not iteration-order accident. Empirical: KNYC 5-year backfill ~50s wall
  time vs the 720s (12 min) ROADMAP gate.
- `tests/test_live_perf.py` — `@pytest.mark.live` KNYC 5-year wall-time gate
  + KMDW other-station regression. Excluded from CI; run manually pre-merge.
- `spike/source_limits/` — 3 stand-alone CLI scripts characterizing AWC,
  GHCNh, and IEM concurrent-request behavior; `.planning/research/SOURCE-LIMITS.md`
  documents the Option-C recommendation grounded in real spike data.

#### Changed
- **IEM ASOS fetcher now uses 365-day calendar-aligned chunks** (was: monthly).
  Lift target: mostlyright PR #85 commit `cf9eb85` (2026-05-12). ~12x fewer HTTP
  requests, ~12x larger payload per request. PR #85 measured KNYC 5-year backfill
  at ~10 min; tradewinds gates at 12 min (20% headroom). PERF-01.
- **IEM ASOS cache filename now encodes the full chunk window**
  (`iem_{start_iso}_{end_iso}_{suffix}.csv` canonical;
  `iem_{start_iso}_{end_iso}_partial_{suffix}.csv` partial). Old
  `iem_<YYYYMM>_<suffix>.csv` files are harmless and will be regenerated by the
  next backfill into the new yearly-chunk format — no migration required.
  `skip_cache=True` OR `chunk_end > today_utc` routes to the `_partial_`
  namespace that backfill never reads (closes three cache-poisoning paths PR #85
  documented). Cutoff uses `datetime.now(UTC).date()`, NOT `date.today()` —
  non-UTC hosts (e.g. Europe/Prague UTC+1/+2) would silently truncate at the day
  boundary. PERF-02.
- **`tradewinds._internal._http.HTTP_TIMEOUT` raised 30 → 60 seconds** to match
  the ~12x payload increase per yearly chunk. Retry policy (`MAX_RETRIES=3`,
  `BASE_DELAY=1.0`, `TRANSIENT_CODES={429,500,502,503,504}`) and atomic-write
  path are unchanged. PERF-03.
- `tradewinds.research._fetch_iem_month` now filters parsed IEM rows back to the
  requested `(year, month)` after parsing. Required by the chunker swap — the
  yearly fetcher returns Jan–Dec rows; without the boundary filter the per-month
  merge loop would see Jan–Dec IEM rows mixed with the month's AWC/GHCNh slice,
  changing merge composition (and therefore tie-break order on strict-`>`
  priority) at month boundaries. The 5-fixture parity gate gates this fix.

#### Tradewinds-specific deviations from PR #85 verbatim
- `iem_asos.download_iem_asos` normalizes the caller's `start` to
  `date(start.year, 1, 1)` before invoking the chunker. PR #85's chunker uses
  `chunk_start = max(current, start)` — that's fine for one-shot backfills but
  defeats cache idempotence when tradewinds' `research.py` calls the fetcher
  month-by-month. Normalization gives a year-stable cache key so per-month
  callers hit the cache on every month after the first. The chunker module
  itself remains PR-#85 verbatim.

## [0.1.0a1] — Phase 1 prepublish hygiene (2026-05-22, on `main`)

See git history for the four-wave Phase 1 lift (parity foundation): `_v02`
foundations port, `research.py` orchestrator, parity test harness + 5-fixture
HARD GATE green, prepublish pins + lift inventory.

## [0.0.1] — Initial scaffold

Workspace + three-package layout (`tradewinds`, `tradewinds-weather`,
`tradewinds-markets`); `_v02` foundations ported from mostlyright-mcp.

# Research Summary: tradewinds

**Project:** tradewinds — local-first Python SDK for Kalshi NHIGH/NLOW prediction-market weather contracts
**Domain:** Quantitative research SDK (financial data, temporal-safety primitives, weather data adapters)
**Researched:** 2026-05-21
**Confidence:** HIGH overall

---

## Executive Summary

tradewinds is a local-first Python SDK that must simultaneously satisfy three hard constraints: byte-equivalent parity with `mostlyright==0.14.1` as a migration gate, structural prevention of temporal leakage via `KnowledgeView`, and source-identity enforcement via `SourceMismatchError`. The architectural bet is that all three can ship in v0.1.0 by using a two-phase plan — Phase A lifts v0.14.1 parity behavior verbatim into a three-package uv workspace, then Phase B adds the temporal and source-identity primitives as an additive layer on top without breaking Mode 1 callers. The ROADMAP.md merges these concerns correctly. Research confirms all locked decisions.

The most dangerous risks are silent, not loud. Kalshi settlement station mappings (NYC=KNYC not KLGA; Chicago=KMDW not KORD) can produce training labels wrong by 1-3°F with no test failure signal. Float/timezone/categorical dtype loss through parquet cache roundtrips can fail the Day 3 parity gate in ways that look like data errors. The AWC `/cgi-bin/` URL migration from September 2025 means the lifted `_awc.py` likely needs a URL fix before any live test passes. All three are addressable in Phase A if caught on Day 1.

Research surfaced five concrete additions to PROJECT.md Active requirements and Out-of-Scope list that should be resolved before Phase A Day 1 lift begins: (1) audit `_internal/_http.py` for retry/timeout/User-Agent and add `CORE-06` if missing; (2) decide on `pandera==0.29` as Validator backing engine or explicitly reject it in a Key Decision; (3) add explicit Out-of-Scope entries for async API surface, built-in backtesting, and hosted feature store; (4) pin inter-package version constraints in all three `pyproject.toml` files before the first PyPI publish; (5) delete `packages/core/src/tradewinds/__init__.py` and migrate to PEP 420 native namespace packaging to prevent the pkgutil shadow-break failure mode.

---

## Key Findings

### Stack (from STACK.md)

The pinned stack is confirmed correct for v0.1.0. The critical constraint is `pandas>=2.2,<3.0` — pandas 3.0 (January 2026) enforces Copy-on-Write, changes `object` dtype to `str`, shifts datetime resolution from `ns` to `us`, and removes `M`/`Q`/`Y` offset aliases. Any of these would invalidate the parity fixtures against `mostlyright==0.14.1`. Parity work was built on pandas 2.x and must stay there for v0.1. The pandas-3.0 migration is an explicit v0.2 work item requiring parity fixture re-capture.

The uv workspace with `hatchling` build backend is confirmed correct. The uv native build backend (`uv_build`) does not yet fully support PEP 420 implicit namespace packages (astral-sh/uv issue 12832, open as of May 2026). `mcp==1.27.1` is mature enough for v0.2 work; FastMCP pattern is the recommended approach when v0.2 starts. Do not add it to v0.1 deps.

**Core technologies (runtime):**
- `httpx>=0.28,<1.0` — sync+async HTTP client; preserves async seam for v0.2 multi-station parallelism
- `pandas>=2.2,<3.0` — PARITY-CRITICAL; 3.0 floor breaks byte-equivalent gate; migrate as explicit v0.2 item
- `pyarrow>=18,<25` — parquet cache I/O; import confined to `weather/cache.py` only; keep `core` pyarrow-free
- `jsonschema>=4.25,<5` — JSON Schema validation for IEM forecast specs; Key Decision: pandera for Validator?
- `filelock>=3.20,<4` — cross-process parquet cache lock; floor bump picks up Windows stale-lock fixes
- `hatchling` — build backend; required for PEP 420 namespace package support; do NOT switch to `uv_build`
- `hypothesis>=6.140,<7` — property-based tests; only mainstream choice in 2026

**Dev group (workspace root only):** `pytest>=8.4,<10`, `pytest-cov>=6.0`, `pytest-recording>=0.13.4`, `ruff>=0.13,<1`, `mypy>=1.18,<2`, `pre-commit>=4,<5`

**Key constraint verified:** VCR.py 8.x (via `pytest-recording`) supports httpx for buffered (non-streaming) responses only. All catalog adapters MUST use buffered httpx responses. Document this constraint in `_internal/_http.py`.

### Features (from FEATURES.md)

The locked PROJECT.md Active requirements cover all table-stakes and differentiators correctly. The temporal-safety + source-identity + canonical-schemas + parity-gate combination is a genuine competitive gap — no adjacent SDK (`mostlyright==0.14.1`, `pyiem`, `vectorbt`, `feast`) enforces source-identity or structural leakage prevention at the SDK level.

**Must-add gaps (not in Active requirements):**
- `CORE-06` (proposed): HTTP retry/timeout/User-Agent in `_internal/_http.py` — audit v0.14.1 lift first; if absent, add `tenacity>=9.0`. Effort: 0.5 day.
- `DOCS-01` (proposed): NumPy-style docstrings + `pytest --doctest-modules` in CI on `research()`, `KnowledgeView`, `Validator`. Effort: 0.5 day.
- Key Decision: `Validator` backed by `pandera==0.29` vs. built on `jsonschema`. Pandera removes ~300 LOC, provides multi-backend (pandas+Polars+pyarrow from one schema). Decide by Phase B Day 5.
- Key Decision: "DataFrame-first, pandera for validation, no row-wise pydantic" — document the rejection explicitly.
- Key Decision: "pandas-first v0.1; Polars deferred to v0.2 if demand emerges" — forestalls Polars RFCs during sprint.

**Out-of-Scope additions (not yet explicit):**
- Async API surface (`aresearch()`) — sync only in v0.1; `httpx` preserves the seam
- Built-in backtesting engine — tradewinds returns training pairs; users plug into `vectorbt`/`quantstats`
- Hosted feature store integration (Feast/Tecton) — local-first; users build adapters externally

**Firmly NOT recommended:** Open-Meteo (licensing trap, already listed), Pydantic-model API surface (row-wise doesn't scale), Polars primary return type (breaks parity), Feast/Tecton (heavy deps, conflicts with local-first), Great Expectations/Soda (warehouse-side, wrong runtime location for SDK-internal validation).

### Architecture (from ARCHITECTURE.md)

The three-layer design is correct and confirmed. Seven implementation decisions were resolved that the ROADMAP left open.

**Critical change before Phase A Day 1:** Delete `packages/core/src/tradewinds/__init__.py` (pkgutil). Migrate to PEP 420 native namespace packaging. The pkgutil approach has a fatal failure mode: any downstream distribution that ships a `tradewinds/__init__.py` without the `extend_path` boilerplate silently shadows all sibling packages. PEP 420 has no such failure mode — there is nothing to forget.

**Critical dependency direction change:** `packages/core/pyproject.toml` currently declares `tradewinds-weather` as a runtime dependency. This must be reversed. Weather and markets should each declare `tradewinds` as a runtime dependency. `research()` resolves adapters via lazy `importlib.import_module` on the weather catalog, and raises `SourceUnavailableError` with a `pip install tradewinds-weather` hint if weather is not installed.

**Hatchling `packages =` must be explicit per dist:** core lists `["src/tradewinds/core", "src/tradewinds/research.py", "src/tradewinds/_internal"]`; weather lists `["src/tradewinds/weather"]`; markets lists `["src/tradewinds/markets"]`. The current `packages = ["src/tradewinds"]` works by accident and will break if a stray file lands in the namespace root.

**Major components:**
1. `tradewinds.core.temporal` — `TimePoint` (UTC-always frozen dataclass) + `KnowledgeView` (wrapper class, NOT pandas accessor; accessor has test-state leakage and conflicts with other libraries' registrations)
2. `tradewinds.core.schema` + `tradewinds.core.schemas/` — `Schema` frozen dataclass, module-level `_REGISTRY`, eager-import via `schemas/__init__.py`; `get_schema()` has lazy-init safety net for out-of-order imports
3. `tradewinds.core.validator` — function `validate_dataframe(df, schema_id)`, not class-bound; potentially pandera-backed (Key Decision pending Day 5)
4. `tradewinds.core.exceptions` — plain classes with explicit `__init__`, `to_dict()` for JSON-RPC; NOT `@dataclass` (dataclass+Exception is a known pickling/constructor footgun)
5. `tradewinds.weather.catalog.__init__` — eager-import registry (`_REGISTRY: dict[source_id, adapter_module]`), `WeatherAdapter` Protocol; NOT entry points, NOT decorators
6. `tradewinds.weather._vendor/` — verbatim lift from `monorepo-v0.14.1`; `_vendor/__init__.py` documents provenance per module
7. `tradewinds.weather.cache` — per-file partition (`v1/observations/station/year/month.parquet`); schema version in path from Day 1 to handle alpha→final schema evolution

### Critical Pitfalls (from PITFALLS.md — top 5)

1. **Kalshi settlement station mapping wrong** (PARITY-BREAKING + SILENT-DATA-CORRUPTION) — NYC=KNYC (Central Park), Chicago=KMDW (Midway), not KLGA/KJFK/KORD. Hard-code in `KALSHI_SETTLEMENT_STATIONS` constant with Kalshi-page citation. Contract test asserts `research(contract="KXHIGHNY").settlement_station == "KNYC"`. Phase B CATALOG-05 + Day 11 contract test.

2. **Float/timezone/categorical dtype loss through parquet roundtrip** (PARITY-BREAKING) — pyarrow silently shifts dtypes on read; categorical columns return as `object` without `read_dictionary=[...]`; float64 drifts through coerce paths. Mitigate: explicit `version="2.6"`, `coerce_timestamps="us"` on write; `read_dictionary=[...]` on read; capture `mostlyright==0.14.1` output dtypes on Day 1; parity test asserts dtype match in addition to value match.

3. **AWC `/cgi-bin/` URL migration (September 2025)** (PARITY-BREAKING) — lifted `_awc.py` likely has stale URLs that 404. Day 1 smoke: `curl -s "https://aviationweather.gov/api/data/metar?ids=KORD&format=json"`. Update URL, mark `# LIFT-FIX: AWC 2025-09 migration`. Refresh fixtures Phase A Day 2.

4. **uv workspace inter-package version constraints absent from built wheels** (PARITY-BREAKING for users post-v0.2) — uv generates unconstrained `Requires-Dist` (astral-sh/uv issue 9811). Manual fix: add `"tradewinds-weather>=0.1.0,<0.2"` in core's pyproject before first PyPI publish. Verify METADATA before releasing. Phase B Day 9 + Day 13 CI pre-publish check.

5. **Kalshi preliminary/final settlement finality silent** (SILENT-DATA-CORRUPTION) — between prelim (~3-5pm) and final (~12:30-5am next morning), `research(to_date=today)` returns prelim values that may differ from what Kalshi settles on. Mode 2 output includes `settlement_finality` column. Validator warns when `to_date >= today - 1`. Phase B Day 7 (`cli` adapter) + Day 9 (Kalshi spec).

---

## Implications for Roadmap

The existing ROADMAP.md is well-structured. These implications address open gaps and sequencing details.

### Phase A — v0.14.1 parity lift (Days 1-4, per ROADMAP.md)

**Rationale:** Establishes ground truth before any new code. Parity must be proven before Phase B builds on top — regressions cannot be diagnosed if the baseline is moving.

**Delivers:** `research()` Mode 1 byte-equivalent to `mostlyright==0.14.1`, all `_vendor/` parsers lifted, `_internal/` lifted, cache working, 5 parity fixtures green, PyPI alpha1 published.

**Must avoid:**
- Pitfall 2 (float/tz/categorical dtype): capture `mostlyright==0.14.1` output dtypes on Day 1, commit to `tests/fixtures/parity/expected_dtypes.json`, gate parity test on dtype match.
- Pitfall 3 (timezone-naive parquet): establish `version="2.6"` and explicit `coerce_timestamps="us"` in cache.py from Day 1.
- Pitfall 7 (AWC URL): manual smoke on Day 1, update URL in `_awc.py` before recorded fixtures are captured.
- Pitfall 4 (categorical dtype on read): add `read_dictionary=[...]` to cache read path before parity gate.

**Research flag:** No additional research needed; pattern is well-documented.

### Phase B — core + catalog refactor (Days 5-14, per ROADMAP.md)

**Rationale:** Temporal primitives and source-identity enforcement are the architectural spine. They must be correct-by-construction before adapters use them and before `research()` Mode 2 is wired. Phase B day-by-day order in ROADMAP.md (temporal → schema → validator → adapters → leakage → formats → exceptions → mode2 → cache-updates → contracts → coverage) is correct.

**Delivers:** CORE-01..05, CATALOG-01..05, RESEARCH-01, MIGRATION-01, v0.1.0 final.

**Must avoid:**
- Pitfall 1 (Kalshi station mapping): hard-code `KALSHI_SETTLEMENT_STATIONS` on Day 9 before Day 11 migration gate.
- Pitfall 5 (CLI DST parsing): lift `_parse_product_timestamp` verbatim; add DST-boundary contract test fixtures (2024-03-10, 2024-11-03) on Day 7.
- Pitfall 6 (NWS substitution): extract `cli_remarks` + `cli_data_quality` enum in `schema.settlement.cli.v1` on Day 7.
- Pitfall 8 (IEM "M" missing-data): preserve `M` as `pd.NA` in nullable `Float64` column, never convert to 0.
- Pitfall 10 (uv inter-package version constraints): explicit version ranges in pyproject Day 9; verify METADATA before Day 13 publish.
- Pitfall 11 (Hypothesis shrinking): constrain datetimes to `[2018-01-01, 2027-12-31]`, `timezones=just(timezone.utc)`, `@settings(deadline=2000, max_examples=200)` on Day 5.
- Pitfall 13 (therminal-py migration): grep full `mostly-light` package recursively; run full dry-run, not surface-level on Day 11.
- Pitfall 14 (filelock on iCloud/NFS): detect cloud-sync path, use `SoftFileLock` fallback, support `TRADEWINDS_CACHE_DIR` env var on Day 10.
- Pitfall 15 (`pd.NA` vs `np.nan`): canonical null representation in `schema.observation.v1` on Day 5; Validator asserts consistency.
- Pitfall 16 (preliminary/final finality): `settlement_finality` column in Mode 2 output on Day 7.
- Pitfall 17 (cache schema evolution): version cache path as `v1/observations/...` from Phase A Day 1; bumping schema increments to `v2/`.

**Research flag:** Phase B Day 5 — 2-hour pandera vs. jsonschema spike for Validator Key Decision. Phase B Day 6 — 1-hour IEM MOS deprecation check (NBM v5.0 live 2026-05-05); add deprecation notice in `catalog/iem.py`.

### Phase C — MCP server (v0.2, per ROADMAP.md)

**Rationale:** Deferred correctly. The seam (`packages/mcp/`) exists. v0.2 design is specified in mostlyright-mcp `docs/design.md`.

**Key v0.2 preparation (flag for planning):** pandas-3.0 migration, FastMCP pattern (`mcp>=1.27,<2`), DataFrame serialization via `toon` at tool boundary, exception `to_dict()` → JSON-RPC error responses (already in place), `catalog._REGISTRY.keys()` powers `catalog_search` enumeration without additional work.

**Research flag:** No research phase needed; mostlyright-mcp design.md is the complete spec.

### Phase Ordering Rationale

- Phase A precedes Phase B: parity gate provides the baseline truth; Mode 2 cannot be verified correct unless Mode 1 is first verified correct.
- Within Phase B, temporal primitives (Days 5-7) precede adapter work (Days 6-8) because adapters emit canonical schema rows requiring `Schema` and `knowledge_time` stamping rules.
- `exceptions.py` is assigned Day 9 in ROADMAP.md but has no dependencies — it can be built on Day 5 as a Lane V parallel task if capacity allows.
- Cache updates (Day 10) must follow adapter work (Days 6-8) because adapters produce the rows that cache stores.
- Contract tests and migration test (Day 11) are gates requiring all prior Phase B work; late position is correct.

---

## Must-Add to ROADMAP / PROJECT — Punch List

### Active Requirements additions

1. **CORE-06 (proposed):** "Audit `_internal/_http.py` lift from v0.14.1: if retry/timeout/User-Agent absent, add `tenacity>=9.0` and implement httpx retry transport, configurable timeout, `User-Agent: tradewinds/{version}`." Audit Phase A Day 1; implement if missing; gate on Phase B Day 6 before adapter tests run.

2. **DOCS-01 (proposed):** "NumPy-style docstrings with `Examples:` section on `research()`, `KnowledgeView`, `Validator`, `LeakageDetector`. `pytest --doctest-modules` in CI." Target Phase B Day 13 alongside QUICKSTART-01.

### Key Decisions to add

3. **"Validator engine: `pandera==0.29` vs. `jsonschema` — decide Phase B Day 5."** Accept pandera: removes ~300 LOC, multi-backend. Reject: jsonschema already in Constraints, aligned with lift. Document either outcome.

4. **"DataFrame-first, pandera for validation, no row-wise pydantic."** Reject pydantic-models-as-API; pandera docs explicitly warn row-wise pydantic doesn't scale for DataFrames.

5. **"pandas-first v0.1; Polars deferred to v0.2 if demand emerges."** Prevents Polars RFCs during sprint.

6. **"Async API surface deferred to v0.2+ with `httpx` seam preserved."** Not forgotten — deliberately deferred.

### Out-of-Scope additions

7. **"Async API surface (`aresearch()`) — sync only in v0.1; `httpx` preserves the seam for v0.2."**

8. **"Built-in backtesting engine — return clean training pairs; users compose with `vectorbt` / `quantstats`."**

9. **"Hosted feature store integration (Feast/Tecton) — local-first; users build thin adapters externally."**

### Architecture / scaffold changes

10. **Delete `packages/core/src/tradewinds/__init__.py` (pkgutil)** and migrate to PEP 420 native namespace packaging. Update all three `pyproject.toml` `[tool.hatch.build.targets.wheel] packages` to list each dist's own slices explicitly. Verify with `uv build --all` + wheel unzip. Do this on Phase A Day 1 morning sync.

11. **Reverse the core→weather dependency direction.** Remove `tradewinds-weather` from `packages/core/pyproject.toml` dependencies. Add `tradewinds` to weather and markets `pyproject.toml` dependencies. Add `[project.optional-dependencies] weather = ["tradewinds-weather"]` to core for `pip install tradewinds[weather]`.

12. **Add explicit inter-package version constraints** in all pyproject.toml files before first PyPI publish: `"tradewinds-weather>=0.1.0,<0.2"` in core's deps. Add pre-publish CI check: grep built wheel METADATA for versioned `Requires-Dist`. Phase B Day 9.

13. **Cache path includes schema version from Day 1:** `~/.tradewinds/cache/v1/observations/{station}/{year}/{month}.parquet`. Add startup check against `SCHEMA_VERSION` file. Phase A Day 2.

14. **Add `KALSHI_SETTLEMENT_STATIONS` constant** in `packages/markets/src/tradewinds/markets/catalog/kalshi_nhigh.py` with the city→station mapping (KNYC, KMDW, etc.) and per-city Kalshi page URL citation. Phase B Day 9, before Day 11 gate.

15. **Add two-tier fixture structure:** `tests/fixtures/parity/` (frozen, never re-recorded) + `tests/fixtures/drift/` (weekly cron, compared against parity set). Document rotation policy. Phase A Day 0.5 capture.

---

## Day 1 Morning Sync Addendum

Small scaffold and config fixes that must land before Phase A Day 1 lift work proceeds. Total time budget: 2 hours.

1. **AWC URL smoke test** (5 min): `curl -s "https://aviationweather.gov/api/data/metar?ids=KORD&format=json" | jq .`. If `_awc.py` has `/cgi-bin/`: update URL constant only; mark `# LIFT-FIX: AWC 2025-09 migration`. Do not touch parsing logic.

2. **Namespace packaging migration** (30 min): Delete `packages/core/src/tradewinds/__init__.py`. Update all three `pyproject.toml` `[tool.hatch.build.targets.wheel] packages` entries to explicit slices per dist. Run `uv build --all` and unzip each wheel to confirm no `tradewinds/__init__.py` in weather or markets wheels. Confirm `from tradewinds.research import research` works in an isolated venv.

3. **Capture `mostlyright==0.14.1` dtype ground truth** (20 min): In a clean venv, run `client.pairs(station, from_date, to_date)`. Print `df.dtypes.to_dict()`. Commit to `tests/fixtures/parity/expected_dtypes.json`. Parity test must assert both value AND dtype match, not just value.

4. **Pin exact `pandas` and `pyarrow` versions from `monorepo-v0.14.1/pyproject.toml`** (10 min): Read the monorepo lockfile. Set lower-bound floors in workspace `pyproject.toml` to match. If the monorepo used `pandas==2.2.3`, pin `>=2.2.3,<3.0`.

5. **Agree on `tradewinds.core` public surface names** (30 min, per ROADMAP.md Day 1 addition): Confirm `TimePoint`, `KnowledgeView`, `Schema`, `Validator`, `LeakageDetector`, `TradewindsError` hierarchy. Write `packages/core/src/tradewinds/core/__init__.py` with placeholder `__all__` listing these names — no implementations yet, just the outline so Lane F can stub against them.

6. **Wire `TRADEWINDS_CACHE_DIR` env-var in cache.py stub** (10 min): `cache_dir = Path(os.environ.get("TRADEWINDS_CACHE_DIR", Path.home() / ".tradewinds" / "cache"))`. Must be wired from the first commit so users can opt out before hitting the iCloud filelock failure.

7. **Write `_vendor/__init__.py` lift inventory comment** before any parser is copied (5 min): Provenance doc belongs in the first commit, per ARCHITECTURE.md Pattern 4 convention.

---

## Cross-Cutting Risks (Convergence Across Researchers)

Three areas were flagged independently by multiple researchers:

**1. Parquet dtype / timezone / categorical fidelity** (STACK.md + ARCHITECTURE.md + PITFALLS.md Pitfalls 2, 3, 4, 15): Four separate failure modes — float precision drift, tz-naive read, categorical lost on read, `np.nan` vs `pd.NA` — all produce parity failures that look like data errors. Single mitigation approach: explicit `version="2.6"`, `coerce_timestamps="us"`, explicit timezone on every timestamp column, `read_dictionary=[...]` on read, canonical null representation pinned in `schema.observation.v1`. Capture ground truth dtypes from `mostlyright==0.14.1` on Day 1.

**2. Domain-specific silent corruption in settlement data** (FEATURES.md + ARCHITECTURE.md + PITFALLS.md Pitfalls 1, 5, 6, 16): Kalshi station mapping, CLI DST parsing, NWS substitution remarks, and preliminary/final finality are all silent failures producing plausible-looking data detectable only via backtesting against known trade outcomes. All four require hard-coded reference data (station mapping, DST fixture dates, `cli_data_quality` enum, `settlement_finality` column) rather than derived logic.

**3. Packaging integrity of the three-package workspace** (STACK.md + ARCHITECTURE.md + PITFALLS.md Pitfall 10): Namespace package shadowing (pkgutil → PEP 420), reversed dependency direction (core must not depend on weather), and missing inter-package version constraints in built wheels are three separate packaging failure modes. All three are fixable in the Day 1 Morning Sync.

---

## Researcher Disagreements and Tensions

**1. Tension: `pandera==0.29` for Validator vs. `jsonschema`**

STACK.md recommends sticking with `jsonschema` (already in Constraints, aligned with v0.14.1 lift, no new dep). FEATURES.md recommends `pandera==0.29` as the Validator backing engine (dataframe-native, removes ~300 LOC, multi-backend). These are not fully contradictory — `jsonschema` handles JSON Schema validation of `_forecast_schema.py` spec files lifted from v0.14.1, while `pandera` could handle runtime `validate_dataframe()`. The question is whether they serve different purposes (both kept) or pandera supersedes jsonschema for the validation use case. Resolve as a Day 5 Key Decision spike before Phase B adapter work starts.

**2. Tension: `research()` import path with PEP 420**

ROADMAP.md implies `from tradewinds import research` works (namespace root has re-exports). ARCHITECTURE.md Pattern 1 recommends `from tradewinds.research import research` as the cleanest PEP 420 form since the namespace root has no `__init__.py`. Resolution options: (A) accept Option A and update ROADMAP.md example code; (B) use `tradewinds.api` module as a re-export hub at the namespace root, with `from tradewinds.api import research`. Pick one before Phase B Day 5. Either is fine; the inconsistency in docs is the actual risk.

**No disagreements on:** MCP deferral, three-package split, pandas 2.x constraint, `filelock` for cache, property tests via Hypothesis. All four researchers confirmed these independently.

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All version pins verified against official PyPI/docs; uv namespace packaging caveat verified against open GitHub issue |
| Features | HIGH | Cross-checked against 5+ adjacent SDKs; pandera recommendation backed by 2026 docs |
| Architecture | HIGH | Every load-bearing decision verified against official packaging.python.org, uv docs, pyarrow docs, or scaffold inspection |
| Pitfalls | HIGH (domain) / MEDIUM (ops) | Kalshi settlement specifics and parquet/pyarrow gotchas HIGH; IEM/AWC operational delays MEDIUM; v0.2-era MCP test flakiness LOW |

**Overall confidence: HIGH**

### Gaps to Address During Execution

- **IEM MOS deprecation timeline** (Pitfall 9): NBM v5.0 live 2026-05-05; IEM MOS archive continuation not publicly committed. Add `__deprecation_notice__` in `catalog/iem.py`; plan NBM adapter for v0.2; monitor IEM status page.
- **Per-source publication lag constants** (ROADMAP.md Open Question 5): `IEM_METAR_LAG` ships as conservative `15min` default; empirical calibration deferred to v0.1.1.
- **Cross-source divergence diff** (ROADMAP.md Open Question 3): `catalog_search` warnings ship with `"status": "unmeasured"` placeholder in v0.1.0; quantified in v0.1.1.
- **`$HOME` iCloud detection on macOS** (Pitfall 14): Heuristic check (path contains `iCloud`, `Dropbox`, `/mnt/`, `/nfs/`) is best-effort; `TRADEWINDS_CACHE_DIR` env var is the correct user-facing escape hatch.
- **`research()` import path resolution** (Tension 2 above): Decide before Phase B Day 5.
- **`pandera` vs `jsonschema` for Validator** (Tension 1 above): Decide by Phase B Day 5 spike.

---

## Sources

### Primary (HIGH confidence)
- pandas 3.0.0 whatsnew — CoW enforcement, string dtype, datetime resolution breaking changes
- httpx 0.28.1 PyPI — current version; no 1.0 stable yet
- pyarrow 24.0.0 PyPI — April 2026 release
- jsonschema 4.26.0 readthedocs — Draft 2020-12 support
- filelock 3.29.0 changelog — Windows stale-lock fixes
- ruff 0.15.14, hypothesis 6.152.9, pytest 9.0.3 — PyPI-verified
- uv workspaces docs (astral-sh) — workspace member resolution, `[tool.uv.sources]` behavior
- astral-sh/trusted-publishing-examples — GH Actions YAML for uv + PyPI trusted publishing
- packaging.python.org — PEP 420 native namespace packages
- pypa/hatch discussion #819 — hatchling namespace package configuration
- mcp 1.27.1 (Anthropic Python SDK) — FastMCP pattern, Pydantic integration

### Secondary (MEDIUM confidence)
- astral-sh/uv issue 12832 — uv_build PEP 420 limitation
- astral-sh/uv issue 9811 — inter-package version constraints not in built wheels
- Apache Arrow issue 38171 — datetime64[ns] → datetime64[us] silent cast
- Apache Arrow issue 37898 — schema evolution on parquet append
- kevin1024/vcrpy issue 597 — httpx async streaming fixed in 8.1.x
- pandera 0.29 — multi-backend support (pandas + Polars + pyarrow from one schema)
- Kalshi help docs — settlement station documentation and finality rules
- NWS Instruction 10-1003 — CLI product format, substitution rules, REMARKS section
- IEM API docs — ASOS `M` missing-data convention, archive amendment policy
- NOAA/MDL Service Change Notice 26-24 — NBM v5.0 live 2026-05-05

### Tertiary (LOW confidence)
- IEM MOS archive continuation timeline — no public commitment; monitor operationally
- uv_build PEP 420 fix timeline — issue open, no ETA

---
*Research completed: 2026-05-21*
*Ready for roadmap: yes — ROADMAP.md exists; this feeds into REQUIREMENTS.md refinement*

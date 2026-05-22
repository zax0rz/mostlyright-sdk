# Phase 2: Core Primitives + Catalog Adapters — Research

**Researched:** 2026-05-21
**Domain:** Python SDK architecture — temporal-safety primitives, declarative schemas, source-identified catalog adapters
**Confidence:** HIGH (most decisions backed by inspectable on-branch code at `packages/core/src/tradewinds/_v02/` + Phase 1 lifted parsers)

## Summary

Phase 2 builds the **architectural spine** on top of Phase 1's parity baseline: temporal-safety primitives (`TimePoint`, `KnowledgeView`, `LeakageDetector`), schema framework + 3 canonical schemas, source-identity-enforcing Validator, exception hierarchy, format serializers, and four catalog adapters wrapping the Phase 1 parsers. Markets gets `KALSHI_SETTLEMENT_STATIONS` + NHIGH/NLOW contract specs.

**The dominant Phase 2 reality:** `packages/core/src/tradewinds/_v02/` already contains a **266-test passing reference implementation** of 4 of the 7 core requirements (CORE-02/03/04/05), ported from the mostlyright-mcp `feat/wave-1-core` branch. It is currently quarantined under `_v02/` and uses the old `MostlyRightMCPError` brand. Phase 2's central work is **rebrand + reorganize from `_v02/` to `tradewinds.core/`**, then **build the new pieces** (`KnowledgeView`, `LeakageDetector`, `Validator`, catalog adapter wrappers, Kalshi contract specs).

**Primary recommendation:** Adopt `_v02/` as the basis for `tradewinds.core` via a git-mv rebrand (not rebuild), keep all 266 tests green through the move, then layer `KnowledgeView`/`LeakageDetector`/`Validator` on top. Defer the `pandera-vs-jsonschema` decision to a Day-5 spike with a default of `jsonschema` (smaller dep surface, aligned with v0.14.1 lift). Hard-code `KALSHI_SETTLEMENT_STATIONS` from the 20-station whitelist (`tests/fixtures/parity/README.md`) with Kalshi-page citations before Phase 3 migration gate.

## User Constraints (from CONTEXT.md)

CONTEXT.md does not exist for this phase. Locked constraints inherited from PROJECT.md / ROADMAP.md / REQUIREMENTS.md:

### Locked Decisions
- **Exception root:** `TradewindsError` (renamed from `MostlyRightMCPError`); alias for one release. [PROJECT.md Key Decisions]
- **Three-package workspace** (`tradewinds` / `tradewinds-weather` / `tradewinds-markets`) — PEP 420 native namespace.
- **Lift source pinned:** `monorepo-v0.14.1` tag, NOT head.
- **MCP deferred to v0.2.** Phase 2 must NOT add `mcp` runtime dep.
- **`KnowledgeView` is a plain class** with `__slots__` — NOT a pandas accessor, NOT a DataFrame subclass. [CORE-07]
- **Hypothesis datetime constrained to `[2018-01-01, 2027-12-31]` UTC**. [CORE-08]
- **Catalog adapters declare `SUPPORTED_SOURCES: list[str]` at class level**, eager-import registry. [CATALOG-05]
- **CLI settlement schema is canonical Fahrenheit** (no metric mode). [§BB.3]
- **Kalshi settlement stations:** NYC=KNYC (Central Park), Chicago=KMDW (Midway) — NOT LGA/JFK/ORD. [MARKETS-01]
- **PEP 420 namespace** — no `tradewinds/__init__.py` collision across wheels. [PKG-02 done in Phase 1]

### Claude's Discretion
- `_v02/` → `tradewinds.core` migration tactic (rename + move vs. wrap vs. rebuild).
- Validator engine: pandera 0.29 vs. jsonschema (ROADMAP says decide after Day-5 spike).
- `research()` import path resolution (`from tradewinds.research` vs. `from tradewinds.api`).
- Parser location naming: keep `tradewinds.weather._{awc,iem,climate,ghcnh}.py` or alias under `_vendor/`.
- Wave parallelization shape inside Phase 2.

### Deferred Ideas (OUT OF SCOPE)
- Phase 3: `research()` Mode 2, cache enhancements, mostly-light migration.
- `Schema.from_dataframe()` (BYO data inference) — explicitly deferred to v0.1.1 [`schema.py:332`].
- Audit-log persistence across `register()` calls — v0.1.1.
- `volatility_warning=True` metadata field — v0.1.1.
- Cross-source divergence diff job (Open Question 4) — v0.1.1.
- `TemporalDriftError`-driven reproducibility audit — keep as `_v02/` class, do NOT wire into Phase 2 Validator (Mode 2 territory).

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| CORE-01 | `TimePoint`, `KnowledgeView`, `LeakageDetector` with property tests, ≥90% branch | `TimePoint` REUSE from `_v02/timepoint.py` (253 LOC, 580-line test). `KnowledgeView`+`LeakageDetector` NEW. |
| CORE-02 | `Schema` + `Validator`, `SourceMismatchError` invariant | `Schema` REUSE from `_v02/schema.py` (344 LOC). `Validator` NEW (currently only a Validator-only audit-log seam exists). |
| CORE-03 | 3 canonical schemas + contract tests | REUSE verbatim from `_v02/schemas/{observation,forecast,settlement}.py` (455 LOC, 403-line tests). |
| CORE-04 | Exception hierarchy with `to_dict()` | REUSE from `_v02/exceptions.py` (331 LOC, 351-line test) + rebrand `MostlyRightMCPError` → `TradewindsError`. |
| CORE-05 | Format serializers (dataframe/json/parquet/toon/csv) roundtripped | REUSE from `_v02/formats/` (1247 LOC across 7 files, 760-line test). |
| CORE-07 | `KnowledgeView` is plain class with `__slots__` | NEW — pattern enforced by CORE-07 acceptance test. |
| CORE-08 | Hypothesis constrained datetime range | NEW — applies to KnowledgeView+LeakageDetector property tests. |
| CATALOG-01 | IEM adapter (obs + MOS forecasts), `iem.archive`/`iem.live` | NEW wrapper around Phase 1 `weather._iem.py` (286 LOC). MOS forecast parser NOT YET LIFTED — see Open Q1. |
| CATALOG-02 | AWC adapter, `awc.live`, post-Sept-2025 endpoint | NEW wrapper around Phase 1 `weather._awc.py` (347 LOC). LIFT-FIX comment on URL change. |
| CATALOG-03 | NWS CLI adapter, prelim/final/correction dedup | NEW wrapper around Phase 1 `weather._climate.py` (190 LOC). Note: parser already has `REPORT_TYPE_PRIORITY` dict; dedup ONCE LIVED in `pairs.py` (not parser) per design §F. |
| CATALOG-04 | GHCNh adapter, `ghcnh.archive` | NEW wrapper around Phase 1 `weather._ghcnh.py` (358 LOC). |
| CATALOG-05 | `WeatherAdapter` Protocol, `SUPPORTED_SOURCES`, eager registry | NEW — `tradewinds.weather.catalog.__init__` module + Protocol class. |
| MARKETS-01 | `KALSHI_SETTLEMENT_STATIONS` constant with citations | NEW — populated from 20-station whitelist (`tests/fixtures/parity/README.md`). |
| MARKETS-02 | `kalshi_nhigh` + `kalshi_nlow` contract specs | NEW — `tradewinds.markets.catalog.{kalshi_nhigh,kalshi_nlow}` modules. |
| MARKETS-03 | `(contract_id, date) → (settlement_source, settlement_station)` deterministic | NEW — pure-function resolver in MARKETS-02 modules. |
| PKG-03 | Inter-package `Requires-Dist` version pins enforced in built wheels | NEW pyproject edits + pre-publish CI check. |

## Standard Stack

### Core (already pinned)
| Library | Version | Purpose | Status |
|---------|---------|---------|--------|
| `pandas` | `>=2.2,<3.0` | DataFrame return types | [VERIFIED: pyproject.toml workspace root] |
| `pyarrow` | `>=17.0` | parquet+toon formats only (confined to formats/parquet.py + cache) | [VERIFIED: workspace root] |
| `httpx` | `>=0.27` | already in `_internal/_http.py` from Phase 1 | [VERIFIED] |
| `jsonschema` | `>=4.21` | currently used by v0.14.1 lift; default Validator backend | [VERIFIED] |
| `hypothesis` | `>=6.100` | property tests for CORE-01/CORE-08 | [VERIFIED workspace dev] |
| `pytest` | `>=8.0` | test runner | [VERIFIED] |
| `respx` | `>=0.23.1` | HTTP mocking for catalog adapter tests | [VERIFIED workspace dev] |

### Decision-pending
| Library | Version | Decision | Recommendation |
|---------|---------|----------|----------------|
| `pandera` | `0.29.x` | Validator engine (Day-5 spike per ROADMAP) | **REJECT for v0.1.0**: removes ~300 LOC but adds heavy dep (numpy 2.x conflict surface, slow first-import). `_v02/` Validator seam already exists via `SchemaRegistration._append_audit`; Validator can be implemented in <250 LOC using `jsonschema` + manual dtype checks. Document rejection as Key Decision. |

### Do NOT Add
- `mcp` — deferred to v0.2
- `pydantic` v2 row-models — design rejects (DataFrame-first)
- `polars` — v0.2 candidate, breaks parity
- `tenacity` — _internal/_http already has retry logic from Phase 1 lift [VERIFIED: `_http.py` has `BASE_DELAY`, `MAX_RETRIES`, `TRANSIENT_CODES`]

## Existing State Inventory

### `packages/core/src/tradewinds/_v02/` (REUSABLE — 266 tests passing on `feat/wave-1-core`)

| File | LOC | Phase 2 Status | Rebrand Needed |
|------|-----|----------------|----------------|
| `timepoint.py` | 253 | REUSE → `tradewinds.core.temporal.timepoint` | Move only (no API change). |
| `exceptions.py` | 331 | REUSE → `tradewinds.core.exceptions` | **YES**: `MostlyRightMCPError` → `TradewindsError`; keep alias `MostlyRightMCPError = TradewindsError` for one release. |
| `_json_safe.py` | 178 | REUSE → `tradewinds.core._json_safe` | Move only. |
| `schema.py` | 344 | REUSE → `tradewinds.core.schema` | Move only. Imports of `MostlyRightMCPError` (none in this file) unchanged. |
| `schemas/observation.py` | 205 | REUSE → `tradewinds.core.schemas.observation` | Move only. |
| `schemas/forecast.py` | 119 | REUSE → `tradewinds.core.schemas.forecast` | Move only. |
| `schemas/settlement.py` | 131 | REUSE → `tradewinds.core.schemas.settlement` | Move only. |
| `formats/_toon.py` | 346 | REUSE → `tradewinds.core.formats._toon` | Move only. |
| `formats/_toon_list_codec.py` | 213 | REUSE → `tradewinds.core.formats._toon_list_codec` | Move only. |
| `formats/{toon,parquet,json,csv,dataframe}.py` | 647 total | REUSE → `tradewinds.core.formats.*` | Move only. |
| `tests/_v02/test_*.py` | 2947 total | REUSE → `tests/core/test_*` (or alongside source per pkg layout) | Update `MostlyRightMCPError` imports + paths. |

**Critical observation:** `_v02/__init__.py:10` says "NOT used by Sprint 0 ... safe to ignore until then." Phase 2 IS that "then." The dormant 266-test reference IS Phase 2's foundation.

### `packages/core/src/tradewinds/_internal/` (Phase 1 — DEPENDED ON)

| File | LOC | Phase 2 Usage |
|------|-----|----------------|
| `_bounds.py` | 75 | Adapters call `bounded_float`/`bounded_int` from here. KEEP as-is. |
| `_capabilities.py` | 272 | LIVE_CAPABLE_SOURCES — adapters consult for `iem.live` vs `iem.archive` routing. |
| `_convert.py` | 221 | F↔C, hPa↔inHg, kt↔m/s — adapters call when projecting to canonical metric schema. |
| `_http.py` | 54 | HTTP client w/ retry — adapter `fetch()` uses this. |
| `exceptions.py` | 57 | `TherminalError` hierarchy (`NotFoundError`, `RateLimitError`, `ValidationError`, `AuthenticationError`). **Phase 2 needs to reconcile two exception hierarchies** — see Open Q2. |
| `versioning.py` | 134 | `DataVersion` model. Not load-bearing for Phase 2 core. |
| `models/*.py` | 369 | `Observation`, `Station`, `Availability` row models — likely v0.14.1 internal types, NOT the canonical schemas. Phase 2 should NOT export these. |

### `packages/weather/src/tradewinds/weather/` (Phase 1 — WRAPPED IN PHASE 2)

| Module | LOC | Phase 2 Wrap |
|--------|-----|--------------|
| `_awc.py` | 347 | `awc_to_observation(raw)` is the parser → wrap in `catalog.awc.AWCAdapter.fetch()`. URL constant lifted post-Sept-2025 (verified via `_fetchers/awc.py` comment). |
| `_iem.py` | 286 | IEM CSV row parser → wrap in `catalog.iem.IEMAdapter` for observations. **MOS forecast parser is NOT in this file** (see Open Q1). |
| `_climate.py` | 190 | `_parse_product_timestamp` + `REPORT_TYPE_PRIORITY` already lifted. Wrap in `catalog.cli.CLIAdapter`. Add `cli_data_quality` enum extraction in adapter (per Pitfall 6). |
| `_ghcnh.py` | 358 | PSV parser → wrap in `catalog.ghcnh.GHCNhAdapter`. |
| `_fetchers/{awc,iem_asos,iem_cli,ghcnh}.py` | 658 total | HTTP fetchers — adapter `fetch()` composes these with the parser. |

### `packages/markets/src/tradewinds/markets/` (PLACEHOLDER ONLY)

`__init__.py` (20 LOC) — placeholder. Phase 2 must create `markets.catalog.{kalshi_nhigh,kalshi_nlow}` from scratch. No existing code to reuse.

### Phase 1 fixtures (`tests/fixtures/parity/`)

5 parity fixtures captured (case_1 KNYC, case_2 KMDW, case_3 KLAX, case_4 KMIA, case_5 KMSY). 20-station whitelist documented in README.md: `ATL, AUS, BOS, DCA, DEN, DFW, HOU, LAS, LAX, MDW, MIA, MSP, MSY, NYC, OKC, PHL, PHX, SAT, SEA, SFO`. **All have ICAO `K` prefix** (CONUS). Phase 2 MARKETS-01 maps these 20 to Kalshi contract IDs.

## Per-Requirement Breakdown

### CORE-01 (TimePoint + KnowledgeView + LeakageDetector)

- **TimePoint**: REUSE `_v02/timepoint.py` verbatim. 580-line test suite already covers DST, ns→µs truncation, NaT/NaN rejection, naive rejection, ISO roundtrip. Move to `tradewinds.core.temporal.timepoint`.
- **KnowledgeView**: NEW. Plain class with `__slots__ = ("_df", "_as_of")` wrapping a DataFrame. Constructor validates: (1) DataFrame has `knowledge_time` column, (2) `as_of` is a `TimePoint`, (3) column is `timestamp_utc` dtype. Single method `.dataframe() -> pd.DataFrame` returns the filtered slice (`df[df.knowledge_time <= as_of]`). NO mutation, NO pandas accessor registration.
- **LeakageDetector**: NEW. Static-function style: `assert_no_leakage(df, as_of) -> None` raises `LeakageError` (already in `_v02/exceptions.py`) with `violating_count` + `sample_violations` capped at 10.
- Property tests: constrained datetime range per CORE-08; `timezones=just(UTC)`; `max_examples=200`, `deadline=2000` per Pitfall 11.

### CORE-02 (Schema + Validator + SourceMismatchError)

- **Schema framework**: REUSE `_v02/schema.py` (344 LOC, frozen dataclass `ColumnSpec`, `Schema` base class, `SchemaRegistration` audit log).
- **Validator**: NEW. Function `validate_dataframe(df, schema_id, *, allow_source_drift: str | None = None) -> SchemaRegistration`. Reads source from `df.attrs["source"]` (overlay) OR fails. Compares against `schema._registered_source` and raises `SourceMismatchError` (already in `_v02/exceptions.py:167`) with role=None for solo schemas. Per-column type check via `jsonschema` OR manual (decision Day 5).
- **Source-identity invariant**: Validator must call `reg._append_audit("source_drift_allowed", reason=allow_source_drift)` when caller opts out (audit-log seam at `_v02/schema.py:158` is already designed for exactly this).
- **`SourceMismatchError`**: already wired with `schema_source`/`data_source`/`role`/`catalog_warning` per design §D — REUSE.

### CORE-03 (Canonical schemas + contract tests)

REUSE `_v02/schemas/{observation,forecast,settlement}.py` verbatim:
- `schema.observation.v1` — 20 metric columns + 11-key IMPERIAL_RENAMES (preserves mostly-light 9-col contract).
- `schema.forecast.iem_mos.v1` — 11 columns (deliberate subset of v0.14.1's 37); event_time=valid_at, knowledge_time=issued_at.
- `schema.settlement.cli.v1` — 10 columns Fahrenheit-canonical with `station_tz` IANA zone column (load-bearing per §U).

Contract tests in `_v02/test_schemas/` (403 LOC total) — REUSE.

### CORE-04 (Exception hierarchy)

REUSE `_v02/exceptions.py` (331 LOC, 7 classes: `MostlyRightMCPError` base + `SourceUnavailableError`, `SchemaValidationError`, `SourceMismatchError`, `LeakageError`, `TemporalDriftError`, `PayloadTooLargeError`).

**Required edits:**
1. Rename `MostlyRightMCPError` → `TradewindsError`. Add module-level alias `MostlyRightMCPError = TradewindsError` deprecated in v0.2, removed v0.3.
2. Update `default_error_code = "MOSTLYRIGHT_MCP_ERROR"` to `"TRADEWINDS_ERROR"` (stable enum for callers).
3. Update docstrings throughout `_v02/` from "mostlyright-mcp" to "tradewinds".
4. Reconcile with `_internal/exceptions.py:TherminalError` hierarchy — see Open Q2.

**Keep `TemporalDriftError` + `PayloadTooLargeError` in source tree but DO NOT EXPORT from `tradewinds.core.exceptions.__all__`.** They are v0.2 MCP-era; Phase 2 leaves them dormant.

### CORE-05 (Format serializers)

REUSE all 7 files in `_v02/formats/` (1247 LOC, 760-line test). Five format pairs: `dataframe`, `parquet`, `json`, `csv`, `toon` with `dumps`/`loads` functions. TOON v3.0 implementation is non-trivial (346+213 LOC for `_toon.py` and `_toon_list_codec.py`).

**Lossy-format documentation** already lives in each module's docstring — keep as-is. Roundtrip test (`test_formats.py`) is the spec for what each format preserves.

### CORE-07 (KnowledgeView is plain class, not accessor)

Acceptance test: `from tradewinds.core import KnowledgeView; assert not hasattr(pd.api.extensions, "_register_accessor_called_for_knowledgeview")`. Simpler: assert `KnowledgeView` is a regular class, has `__slots__`, and constructing it doesn't side-effect any pandas accessor registry. New test file `tests/core/test_knowledgeview_no_accessor.py`.

### CORE-08 (Constrained Hypothesis datetimes)

All `KnowledgeView`/`LeakageDetector` property tests use:
```python
datetimes_utc = st.datetimes(
    min_value=datetime(2018, 1, 1),
    max_value=datetime(2027, 12, 31),
    timezones=st.just(UTC),
)
@settings(max_examples=200, deadline=2000)
```
This is Pitfall 11 mitigation — non-negotiable per ROADMAP success criterion §1.

### CATALOG-01 (IEM adapter — obs + MOS forecasts)

NEW wrapper at `packages/weather/src/tradewinds/weather/catalog/iem.py`:

```python
class IEMAdapter:
    SUPPORTED_SOURCES: ClassVar[list[str]] = ["iem.archive", "iem.live"]
    IEM_METAR_LAG = timedelta(minutes=15)  # design §"Definitions" — knowledge_time lag constant

    def fetch_observations(self, source, station, from_date, to_date) -> pd.DataFrame:
        # 1. _fetchers/iem_asos.py downloads CSV → text
        # 2. weather._iem.py parses rows → list[dict]
        # 3. project to schema.observation.v1 metric columns (use _internal._convert)
        # 4. add overlay columns: source, retrieved_at, knowledge_time (event_time + IEM_METAR_LAG)
        # 5. set df.attrs["source"] = source
        # 6. return DataFrame
```

**MOS forecast leg is OPEN QUESTION 1** — see Open Questions.

### CATALOG-02 (AWC adapter)

NEW wrapper at `packages/weather/src/tradewinds/weather/catalog/awc.py`:
- `SUPPORTED_SOURCES = ["awc.live"]` (post-Sept-2025; archive endpoint may exist but unverified — keep `awc.live` only for v0.1).
- Same shape as IEM adapter, calling `_fetchers/awc.py` + `weather._awc.awc_to_observation`.
- LIFT-FIX comment on URL change verified via `_fetchers/awc.py` docstring.

### CATALOG-03 (CLI adapter)

NEW wrapper at `packages/weather/src/tradewinds/weather/catalog/cli.py`:
- `SUPPORTED_SOURCES = ["cli.archive"]`.
- Wraps `weather._climate.py` parser.
- **Critical augmentation (design §F):** parser already extracts `_parse_product_timestamp`; adapter must emit `product_release_time` as a column. `REPORT_TYPE_PRIORITY` dedup currently lives in the v0.14.1 `pairs.py` builder (NOT the parser) — adapter must carry it. Apply dedup on `(station, observation_date)` → highest-priority row only, unless caller passes `include_revisions=True`.
- Add `cli_data_quality` extraction (Pitfall 6) — regex on REMARKS for `(?i)(estimated|substituted|nearby|representative|backup|cooperative)` → set quality enum. **NOTE:** This is NOT in the `schema.settlement.cli.v1` columns from `_v02/`. Either (a) add it to the schema now, or (b) defer to Phase 3. Recommendation: add it now — schema additions are cheap pre-release; post-release they're breaking.
- Add `station_tz` lookup (already a required schema column per `_v02/schemas/settlement.py:51`) from a static IANA mapping table for the 20-station whitelist.

### CATALOG-04 (GHCNh adapter)

NEW wrapper at `packages/weather/src/tradewinds/weather/catalog/ghcnh.py`:
- `SUPPORTED_SOURCES = ["ghcnh.archive"]`.
- Wraps `weather._ghcnh.py` PSV parser.
- **Limit to Kalshi settlement stations for v0.1** (per Pitfall 19) — stations in the 20-station whitelist with stable IDs post-2015.
- `station_id_history` mapping deferred to v0.1.1 (Pitfall 19 mitigation); v0.1 ships single-ID assumption with a docstring note.

### CATALOG-05 (Registry + Protocol)

NEW `packages/weather/src/tradewinds/weather/catalog/__init__.py`:

```python
from typing import Protocol, ClassVar
import pandas as pd

class WeatherAdapter(Protocol):
    SUPPORTED_SOURCES: ClassVar[list[str]]
    def fetch_observations(self, source: str, station: str, from_date: str, to_date: str) -> pd.DataFrame: ...

# Eager-import registry (not entry-points, not decorators per ARCHITECTURE.md)
from .iem import IEMAdapter
from .awc import AWCAdapter
from .cli import CLIAdapter
from .ghcnh import GHCNhAdapter

_REGISTRY: dict[str, type[WeatherAdapter]] = {}
for cls in (IEMAdapter, AWCAdapter, CLIAdapter, GHCNhAdapter):
    for src in cls.SUPPORTED_SOURCES:
        _REGISTRY[src] = cls

def get_adapter(source: str) -> WeatherAdapter:
    if source not in _REGISTRY:
        raise SourceUnavailableError(f"Unknown source {source!r}", source=source)
    return _REGISTRY[source]()
```

### MARKETS-01 (KALSHI_SETTLEMENT_STATIONS)

NEW `packages/markets/src/tradewinds/markets/catalog/kalshi_stations.py`:

```python
# Source: tests/fixtures/parity/README.md 20-station whitelist + Kalshi help pages
# CITED: https://help.kalshi.com/markets/popular-markets/weather-markets
KALSHI_SETTLEMENT_STATIONS: dict[str, dict] = {
    "KXHIGHNY":  {"station": "KNYC", "tz": "America/New_York",    "city": "NYC",     "cite": "https://kalshi.com/markets/kxhighny"},
    "KXHIGHCHI": {"station": "KMDW", "tz": "America/Chicago",     "city": "Chicago", "cite": "https://kalshi.com/markets/kxhighchi"},
    "KXHIGHLAX": {"station": "KLAX", "tz": "America/Los_Angeles", "city": "LA",      "cite": "..."},
    "KXHIGHMIA": {"station": "KMIA", "tz": "America/New_York",    "city": "Miami",   "cite": "..."},
    "KXHIGHDEN": {"station": "KDEN", "tz": "America/Denver",      "city": "Denver",  "cite": "..."},
    "KXHIGHBOS": {"station": "KBOS", "tz": "America/New_York",    "city": "Boston",  "cite": "..."},
    "KXHIGHAUS": {"station": "KAUS", "tz": "America/Chicago",     "city": "Austin",  "cite": "..."},
    # ... 13 more from the 20-station whitelist
}
```

**[ASSUMED]** The KXHIGH* contract ID format (`KXHIGH{CITY}`) and exact mapping for 18 cities beyond NYC + Chicago needs operator confirmation. Phase 2 planner should ask for the canonical Kalshi page URLs for each city before Phase 3.

### MARKETS-02 + MARKETS-03

NEW `packages/markets/src/tradewinds/markets/catalog/kalshi_nhigh.py` (+ kalshi_nlow.py twin):

```python
from datetime import date
from .kalshi_stations import KALSHI_SETTLEMENT_STATIONS

def resolve(contract_id: str, contract_date: date) -> tuple[str, str]:
    """Deterministic (contract_id, date) → (settlement_source, settlement_station)."""
    if contract_id not in KALSHI_SETTLEMENT_STATIONS:
        raise SourceUnavailableError(f"Unknown contract {contract_id}", source=contract_id)
    spec = KALSHI_SETTLEMENT_STATIONS[contract_id]
    return ("cli.archive", spec["station"])  # CLI is always settlement source
```

Contract test (CATALOG-05 + MARKETS-02): for every supported ticker, assert `resolve()[1] in {"KNYC","KMDW","KMIA","KAUS","KLAX","KDEN","KBOS",...}` and NEVER `{"KLGA","KJFK","KORD"}`.

### PKG-03 (Inter-package version pins in wheels)

Edit `packages/core/pyproject.toml`, `packages/weather/pyproject.toml`, `packages/markets/pyproject.toml`:
- `dependencies = ["tradewinds>=0.1.0,<0.2"]` in weather + markets (NOT loose `"tradewinds"`).
- core gets NO sibling dep (per ARCHITECTURE.md "reverse dependency direction"). Optional `[project.optional-dependencies] weather = ["tradewinds-weather>=0.1.0,<0.2"]` for `pip install tradewinds[weather]`.
- Pre-publish CI script: build all wheels, unzip, grep `METADATA` for `Requires-Dist: tradewinds-weather` — fail if no version constraint follows.

## Key Architecture Decisions (resolve BEFORE planning)

### Decision 1: `_v02/` → `tradewinds.core` migration tactic

**Options:**
- (A) **git-mv rebrand**: Move `_v02/` → `tradewinds/core/`, sed `MostlyRightMCPError` → `TradewindsError`, rename `_v02/__init__.py` quarantine docstring, update test imports. ~1 day. Preserves git history per-file.
- (B) **Wrap**: Keep `_v02/` as-is; create `tradewinds.core` as thin re-export shim. Confusing two-layer naming forever.
- (C) **Rebuild**: Reimplement from scratch using `_v02/` as reference. Loses 266 tests + 2947 lines of careful work.

**Recommendation: Option (A).** Single commit converts the dormant reference into the canonical implementation. All 266 tests stay green through the rename. Risk: 7-class exception rename touches every file; use `git mv` per file then a single search-and-replace commit for clarity.

### Decision 2: Validator engine (pandera vs jsonschema)

**Recommendation: jsonschema (default), 2-hour spike on Day 5 to confirm.**

Rationale:
- `_internal/_http.py` Phase 1 lift already pulls jsonschema 4.21+ from v0.14.1. No new dep.
- Pandera 0.29 multi-backend (pandas+polars+pyarrow) is overkill for v0.1 (pandas-only).
- Validator only needs: column-presence, dtype check, source-identity check (custom), null-rule check, enum-value check. <250 LOC with manual dtype matching against `ColumnSpec.dtype` strings.
- `_v02/schema.py` already provides `ColumnSpec.dtype` as canonical-string tags (`"timestamp_utc"`, `"float64"`, `"enum"`) — easier to dispatch on these than translate to pandera.

Document rejection as Key Decision. If Day-5 spike disproves, pivot.

### Decision 3: Exception base rename (`TradewindsError` vs `MostlyRightMCPError`)

**Locked by PROJECT.md:** `TradewindsError` with one-release alias `MostlyRightMCPError = TradewindsError`.

Implementation: keep both names exported from `tradewinds.core.exceptions`, with a `DeprecationWarning` on the alias (fire once per session, stacklevel=2).

### Decision 4: Parser location — `tradewinds.weather._{awc,iem,climate,ghcnh}` vs `_vendor/`

**Current state:** Parsers live at `packages/weather/src/tradewinds/weather/_{awc,iem,climate,ghcnh}.py` (Phase 1).
**ROADMAP language:** "lifted parsers verbatim into `_vendor/`."
**ARCHITECTURE.md language:** `_vendor/__init__.py` documents provenance.

**Recommendation: Leave parsers where they are (`tradewinds.weather._{awc,iem,climate,ghcnh}.py`).** No `_vendor/` rename. Rationale:
- Phase 1 is shipped on `merged-vision` with current paths; renaming touches every adapter import.
- Underscore prefix already signals "internal/not-public-API."
- `_vendor/` term in ROADMAP was inherited from mostlyright-mcp design.md — that doc explicitly notes the lift is "with augmentation" not "verbatim."
- Provenance documentation can live in `tradewinds.weather.__init__.py` docstring (already partially does — see `packages/weather/src/tradewinds/weather/__init__.py:3-18`).

If naming clarification is desired, do it as a tiny separate task — DO NOT block Phase 2 on it.

### Decision 5: `TherminalConfig` / `Config` lift

**Current state:** `_internal/__init__.py` docstring claims `config` is planned, but **NO `config.py` file exists** in `_internal/`. This was dropped in Wave 2.

**Question:** Does Phase 2 need a Config object?

**Recommendation: NO for Phase 2; defer to Phase 3.** Rationale:
- Phase 2 adapters take direct constructor args (e.g., `IEMAdapter().fetch(source, station, from, to)`).
- The only Phase 2 config knob is `TRADEWINDS_CACHE_DIR` env var (already wired in Phase 1 cache).
- `IEM_METAR_LAG = timedelta(minutes=15)` is a class-level constant per design — not a Config thing.
- A `Config` dataclass becomes useful for Phase 3's `research()` orchestration (cache toggles, HTTP timeout overrides, units default). Defer.

Update `_internal/__init__.py` docstring to remove the `config` planned line, or mark it as "Phase 3."

### Decision 6: Reconcile `TherminalError` (`_internal/exceptions.py`) vs. `TradewindsError` (`_v02/exceptions.py`)

**The mess:**
- `_internal/exceptions.py` has `TherminalError`/`NotFoundError`/`RateLimitError`/`ValidationError`/`AuthenticationError` — drop-in v0.14.1 hierarchy used by Phase 1 fetchers + `_http.py`.
- `_v02/exceptions.py` has `MostlyRightMCPError`/`SourceUnavailableError`/`SchemaValidationError`/`SourceMismatchError`/`LeakageError` — MCP-shaped hierarchy.

**Recommendation:**
1. After rebrand, `tradewinds.core.exceptions.TradewindsError` is the canonical user-facing base.
2. `_internal/exceptions.py:TherminalError` is downgraded to an internal HTTP-error wrapper — make it subclass `TradewindsError` (so user code catching `TradewindsError` catches HTTP errors too). Rename file to `_internal/_http_exceptions.py` to signal it's HTTP-layer only. **OR** keep `TherminalError` as a legacy v0.14.1-migration alias for `TradewindsError` (matches MIGRATION-02 requirement: "MostlyRightMCPError (alias for TherminalError)" — a 3-way name reconciliation).
3. `SchemaValidationError` (in `_v02/`) is NOT the same as `_internal/exceptions.py:ValidationError` (HTTP 400). Keep them as distinct subclasses of `TradewindsError`.

**Plan: build a compatibility shim** so `from tradewinds.core import TradewindsError` works AND `from tradewinds._internal.exceptions import TherminalError` still works (where `TherminalError = TradewindsError`). Document in CHANGELOG that `TherminalError` is deprecated.

## Implementation Order

Phase 2 unblock graph:

```
   ┌─────────────────────────────────────────────────────┐
   │ Wave 0: Decisions + scaffolding (Day 5 morning)     │
   │   - Decision 1 (migration tactic) → commit          │
   │   - Decision 2 (Validator engine) → 2hr spike       │
   │   - Decision 6 (exception reconcile) → committed    │
   │   - Create tests/core/, tests/markets/ skeletons    │
   └─────────────────────────────────────────────────────┘
                          ↓
   ┌─────────────────────────────────────────────────────┐
   │ Wave 1: _v02 → tradewinds.core rebrand (Day 5 PM)   │
   │   git-mv files; sed MostlyRightMCPError→Tradewinds- │
   │   Error; update test imports; 266 tests stay green  │
   │   Delivers: CORE-03, CORE-04, CORE-05 (partial)     │
   └─────────────────────────────────────────────────────┘
                          ↓
   ┌─────────────────────────────────────────────────────┐
   │ Wave 2A (parallel): KnowledgeView + LeakageDetector │
   │   (Day 6) — depends on TimePoint                    │
   │   Delivers: CORE-01, CORE-07, CORE-08               │
   ├─────────────────────────────────────────────────────┤
   │ Wave 2B (parallel): Validator (Day 6) — depends on  │
   │   Schema framework + SourceMismatchError            │
   │   Delivers: CORE-02 (Validator implementation)      │
   ├─────────────────────────────────────────────────────┤
   │ Wave 2C (parallel): Catalog skeleton — Protocol +   │
   │   registry stub (Day 6)                             │
   │   Delivers: CATALOG-05 scaffolding                  │
   └─────────────────────────────────────────────────────┘
                          ↓
   ┌─────────────────────────────────────────────────────┐
   │ Wave 3 (parallel): Adapter implementations (Days 7-8)│
   │   CATALOG-01 IEM, CATALOG-02 AWC, CATALOG-03 CLI,   │
   │   CATALOG-04 GHCNh — each wraps Phase 1 parser      │
   │   Each adapter independently testable               │
   └─────────────────────────────────────────────────────┘
                          ↓
   ┌─────────────────────────────────────────────────────┐
   │ Wave 4: Markets (Day 9)                             │
   │   MARKETS-01 KALSHI_SETTLEMENT_STATIONS constant +  │
   │   MARKETS-02/03 kalshi_nhigh + kalshi_nlow specs    │
   │   Depends on: Phase 2 Wave 1 (TradewindsError)      │
   │   Contract test gates: every ticker → known station │
   └─────────────────────────────────────────────────────┘
                          ↓
   ┌─────────────────────────────────────────────────────┐
   │ Wave 5: Packaging + glue (Day 9)                    │
   │   PKG-03 pyproject.toml inter-package pins +        │
   │   pre-publish CI METADATA check; reverse dep direc- │
   │   tion (core no longer requires tradewinds-weather) │
   └─────────────────────────────────────────────────────┘
```

**Critical-path observations:**
- Wave 1 unblocks everything else. Must complete first.
- Waves 2A/2B/2C can fan out — `KnowledgeView` does not need Validator; adapter scaffolding does not need either.
- Wave 3 adapters fan out, but all depend on Wave 2C registry + Wave 1 schemas.
- Wave 4 markets is decoupled from weather adapters except for the contract test that asserts MARKETS-02 resolves to a station the CLI adapter (Wave 3) can fetch.

**Estimated Phase 2 duration:** Days 5-9 per ROADMAP, **5 days realistic with 2-3 lane parallelization.**

## Common Pitfalls (from `.planning/research/PITFALLS.md`)

Phase-2-applicable subset (numbers match PITFALLS.md):

### Pitfall 1: Kalshi station mapping wrong (PARITY-BREAKING + SDC)
**MARKETS-01 lands the fix.** Contract test in Wave 4 asserts every ticker → known-good station.

### Pitfall 3: Timezone-aware vs naive parquet roundtrip
**TimePoint solves this** (always UTC tz-aware). Property test on DST boundaries 2024-03-10 + 2024-11-03 in CORE-01.

### Pitfall 4: pandas categorical dtype lost on parquet roundtrip
**Validator handles via dtype check.** Format roundtrip tests (CORE-05) already cover this — `_v02/test_formats.py` validates dtype preservation.

### Pitfall 5: CLI DST late-night issuance parsing
**`_parse_product_timestamp` lifted verbatim from v0.14.1** (Phase 1) — DO NOT modify. CLI adapter (CATALOG-03) adds DST-boundary fixture tests in Wave 3.

### Pitfall 6: NWS substitution / `cli_data_quality`
**Recommend adding `cli_data_quality` enum column to `schema.settlement.cli.v1` NOW** (Wave 1 schema edit) — see CATALOG-03 above. Pre-release schema additions are cheap.

### Pitfall 8: IEM `M` missing-data three-way ambiguous
**IEM adapter (CATALOG-01) MUST convert `M` → `pd.NA`, never to 0 or NaN.** Validator (CORE-02) checks consistency. Property test feeds `M`/`0`/valid; asserts distinguishable.

### Pitfall 9: IEM MOS deprecation in favor of NBM
**Add `__deprecation_notice__` constant in `catalog/iem.py`.** v0.2 NBM adapter planned. No Phase 2 code change required beyond the notice.

### Pitfall 11: Hypothesis temporal shrinking pathology
**CORE-08 mitigation:** constrained datetime range + `timezones=just(UTC)` + `max_examples=200`, `deadline=2000`. Apply to all CORE-01/CORE-02 property tests.

### Pitfall 15: `pd.NA` vs `np.nan` vs `None` mixing
**Validator check `_no_mixed_nulls(col)`** — assert column has exactly one of the three. Schema defines canonical: nullable float → `Float64` + `pd.NA`.

### Pitfall 19: GHCNh station ID drift
**Defer `station_id_history` mapping to v0.1.1.** Phase 2 GHCNh adapter restricts to 20-station whitelist (post-2015 stable IDs) and emits docstring warning.

## Risk Register

| # | Risk | Likelihood | Impact | Mitigation |
|---|------|-----------|--------|------------|
| R1 | `_v02/` rebrand misses an import site → 266 tests fail | MEDIUM | HIGH (Wave 1 blocks all of Phase 2) | Single search-and-replace commit; `grep -r MostlyRightMCPError packages/ tests/` audit; CI runs full test suite on Wave-1 commit |
| R2 | Validator design conflict with `_v02/schema.py` audit-log seam | LOW | MEDIUM | Audit-log seam at `schema.py:158` is already designed for Validator-only writes; just implement against the documented contract |
| R3 | CLI adapter `REPORT_TYPE_PRIORITY` dedup currently lives in v0.14.1 `pairs.py` (not parser); Phase 2 must lift the dedup logic separately | HIGH | HIGH | Audit v0.14.1 `pairs.py` for dedup code; lift into CLIAdapter wrapper; test with prelim + final fixtures for same date |
| R4 | IEM MOS forecast parser may not be in `weather._iem.py` (only obs parser); CATALOG-01 forecast leg may need separate v0.14.1 lift | HIGH | MEDIUM | See Open Q1; budget extra day if lift needed; alternatively defer MOS forecasts to Phase 3 (still meets CATALOG-01 partial) |
| R5 | `schema.settlement.cli.v1` schema lacks `cli_data_quality` column → Pitfall 6 silent corruption | MEDIUM | HIGH | Wave 1 schema edit adds the column (pre-release add, cheap); also add `settlement_finality` per Pitfall 16 |
| R6 | KALSHI_SETTLEMENT_STATIONS mapping is wrong for cities beyond NYC/Chicago | MEDIUM | HIGH | [ASSUMED] data needs confirmation; planner should ask operator for Kalshi page URLs for all 20 cities before Wave 4 |
| R7 | Pandera Day-5 spike unexpectedly shows pandera is essential → 1-day Validator rewrite mid-phase | LOW | MEDIUM | Default jsonschema; reject pandera unless spike shows >$X benefit; document rejection |
| R8 | `TherminalError`/`TradewindsError`/`MostlyRightMCPError` 3-way reconcile breaks Phase 1 fetcher tests | MEDIUM | MEDIUM | Wave 0 commit: `TherminalError = TradewindsError` shim; run full Phase 1 test suite after shim |
| R9 | AWC `awc.archive` endpoint absent → CATALOG-02 has no historical fallback in v0.1 | LOW | LOW | Documented in design.md — `awc.live` only is intentional; IEM provides historical depth |
| R10 | Empty `tradewinds.markets` namespace; need to scaffold `catalog/` subpackage from scratch | LOW | LOW | Standard module creation; tests can be written first against the stub |

## v0.14.1 Quirks Discovered in Wave 3A (Phase 1)

From `_v02/` tests + Phase 1 parser code + design.md Amendments:

- **AWC visibility `"M1/4"` prefix**: leading `M` = "less than" per METAR convention. Already handled in `_awc.py:88` (W3A P2 fix).
- **GHCNh `REM` wrapper / quote handling**: TOON encoder switched to column-wise iteration (commit `98138c4`) to preserve `int64` dtype.
- **GHCNh QC code allowlist**: `_ALLOWED_QC = {"0","1","4","5"}` in `_ghcnh.py:42` — raw-only filtering.
- **IEM precipitation `"T"` → 0.0**: trace precip handled in `_iem.py:62`.
- **IEM peak_wind_time `YYYY-MM-DD HH:MM` → `HHMM`**: format conversion in `_iem.py:87`.
- **CLI `_parse_product_timestamp`**: first 12 chars of product field = `YYYYMMDDHHmm` in UTC. Already in `_climate.py:39`.
- **CLI report_type priority**: `{final: 3.0, ncei_final: 2.5, correction: 2.0, preliminary: 1.0, estimated: 0.0}` in `_climate.py:21`. Dedup uses **strict `>` first-seen-wins** at equal priority.
- **CLI `infer_report_type`**: same-day → preliminary, next-day 04:00-10:00 UTC → final, otherwise correction (`_climate.py:55`).
- **Decimal → float coercion** with documented loss (`_v02/formats/_toon.py` commit `9eede66`).
- **Empty DataFrame columns preserved through JSON roundtrip** (commit `bc89755`).
- **NaT/NaN rejection up-front** in TimePoint to avoid misleading "naive datetime" error (`timepoint.py:130`).

## Open Questions

1. **Where is the IEM MOS forecast parser?** Phase 1 `weather._iem.py` is the IEM CSV/METAR observation parser; MOS forecasts use a different IEM endpoint and different parse logic. Is the MOS parser in `monorepo-v0.14.1/src/mostlyright/_forecast_parse.py` lifted somewhere I haven't found, or does CATALOG-01 forecast leg need a fresh Phase 1-style lift in Phase 2?
   - **What I know:** `schema.forecast.iem_mos.v1` exists (`_v02/schemas/forecast.py`). Phase 1 commit list mentions `_forecast_parse.py` was load-bearing.
   - **What's unclear:** Whether the forecast parser is in `_internal/`, `weather/` somewhere I missed, or still to be lifted.
   - **Recommendation:** Planner must verify with `find packages/ -name "*forecast*"` before Wave 3 starts. If absent, add a "Wave 3.5: Lift MOS forecast parser" task with 0.5-day estimate from `monorepo-v0.14.1`.

2. **Kalshi contract ID format and 20-city mapping.** PROJECT.md/REQUIREMENTS.md reference `KXHIGHNY`, `KXHIGHCHI`, `KXHIGHNYC` — three slightly different forms. The 20-station whitelist in `tests/fixtures/parity/README.md` lists city codes (ATL/AUS/.../SFO) but not the Kalshi ticker prefix convention.
   - **Recommendation:** Planner asks operator for: (a) canonical contract ID format, (b) authoritative Kalshi market URL per city, (c) any cities where the settlement station deviates from the "Central Park / Midway-style historical climate station" pattern.

3. **`research()` import path** (`tradewinds.research` vs `tradewinds.api`). Inherited from `.planning/research/SUMMARY.md` Tension 2 — decide before Phase 3, but Phase 2 may need to know if writing any top-level `__init__.py` re-exports.
   - **Recommendation:** Punt to Phase 3. Phase 2 surface is `tradewinds.core.*`, `tradewinds.weather.catalog.*`, `tradewinds.markets.catalog.*` — no `tradewinds.research` touched.

4. **Should the contract spec's `resolve()` return `settlement_source`?** Currently CLI is the only settlement source ID — return value `("cli.archive", "KNYC")` is degenerate. But MARKETS-03 says "(contract_id, date) → (settlement_source, settlement_station)" — preserve the tuple for forward-compat (when sports/finance verticals add other settlement sources).
   - **Recommendation:** Keep the tuple shape; document `settlement_source` as always `"cli.archive"` in v0.1.

5. **`cli_data_quality` + `settlement_finality` schema additions — now or Phase 3?**
   - **What I know:** `_v02/schemas/settlement.py` does NOT have these columns. Pitfall 6 + 16 require them for correctness.
   - **Recommendation:** Add to schema in Wave 1 alongside the rebrand. Pre-release schema additions are zero-cost; post-release they break contract tests. The `_v02/` schema and tests are still in pre-release flux per `__init__.py` (`"NOT used by Sprint 0"`).

## Code Examples (verified patterns)

### Schema registration with audit-log seam (REUSE)
```python
# From _v02/schema.py:252 (verbatim)
reg = ObservationSchema.register(
    source="iem.archive",
    retrieved_at=datetime.now(UTC),
    rows=len(df),
)
# Validator opt-out via audit:
reg._append_audit("source_drift_allowed", reason="train/infer cross-source ok for v0.1 backfill")
```

### Source-stamped DataFrame return (NEW pattern for adapters)
```python
def fetch_observations(self, source, station, from_date, to_date) -> pd.DataFrame:
    raw_dicts = _iem.parse_iem_csv(_fetchers.iem_asos.download(station, from_date, to_date))
    df = pd.DataFrame(raw_dicts)
    df = self._project_to_canonical_metric(df)  # uses _convert + drops non-schema cols
    df["source"] = source
    df["retrieved_at"] = pd.Timestamp(datetime.now(UTC))
    df["knowledge_time"] = df["event_time"] + self.IEM_METAR_LAG
    df.attrs["source"] = source  # for Validator to read
    return df
```

### KnowledgeView (NEW)
```python
class KnowledgeView:
    __slots__ = ("_df", "_as_of")
    def __init__(self, df: pd.DataFrame, as_of: TimePoint):
        if "knowledge_time" not in df.columns:
            raise SchemaValidationError(...)
        if not isinstance(as_of, TimePoint):
            raise TypeError("as_of must be TimePoint")
        self._df = df
        self._as_of = as_of
    def dataframe(self) -> pd.DataFrame:
        return self._df[self._df["knowledge_time"] <= self._as_of.to_utc()].copy()
```

## Validation Architecture

(Per `.planning/config.json`: `nyquist_validation: false` — section omitted.)

## Sources

### Primary (HIGH confidence — inspected on-disk)
- `packages/core/src/tradewinds/_v02/*.py` — 17 files, 2947 lines of source
- `packages/core/tests/_v02/*.py` — 2947 lines of tests (266 tests)
- `packages/core/src/tradewinds/_internal/*.py` — Phase 1 lifted utilities
- `packages/weather/src/tradewinds/weather/{_awc,_iem,_climate,_ghcnh}.py` — Phase 1 parsers
- `packages/weather/src/tradewinds/weather/_fetchers/*.py` — Phase 1 HTTP fetchers
- `.planning/{PROJECT,REQUIREMENTS,ROADMAP,STATE}.md`
- `.planning/research/{SUMMARY,PITFALLS,ARCHITECTURE,STACK,FEATURES}.md` — pre-roadmap research
- `docs/design.md` — 884-line v0.2 foundations design (§A schemas, §B source-identity, §D exception payloads, §F lift plan, §H test bar)
- `tests/fixtures/parity/README.md` — 20-station whitelist + 5 captured fixtures
- `roadmap/sprint0.md` + `roadmap/sprint0-bootstrap-status.md` + `roadmap/lanes/{founder-build,vu-lift}-lane.md`

### Secondary (MEDIUM confidence)
- Pitfall references — `.planning/research/PITFALLS.md` numbered list 1-20
- Wave 3A v0.14.1 quirks — extracted from commit log + parser comments

### Tertiary (assumed)
- Kalshi contract ID format for 18 cities beyond NYC/Chicago — needs operator confirmation
- Kalshi page URLs per city for citation field — needs operator confirmation

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | KXHIGH{CITY} contract ID format applies uniformly across 20 cities | MARKETS-01 code example | Contract test will fail for nonconforming cities; reshape constant; ~2hr fix |
| A2 | Settlement source is always `cli.archive` for v0.1 (no Kalshi-specific override per city) | MARKETS-02/03 resolver | Sports/finance verticals will need to extend tuple; pre-shape now is correct |
| A3 | IEM MOS forecast parser exists in `monorepo-v0.14.1/src/mostlyright/_forecast_parse.py` and can be lifted analogously to other parsers | CATALOG-01 forecast leg | Open Q1; +0.5 day to budget if confirmed-missing |
| A4 | Phase 1 `_climate.py` parser does NOT include the `(station, observation_date)` dedup currently in v0.14.1 `pairs.py` | CATALOG-03 + R3 | High — must lift dedup separately. Verify by inspecting v0.14.1 `pairs.py` |
| A5 | Pandera offers <30% LOC reduction net of Validator integration cost — keep jsonschema | Decision 2 | Day-5 spike could disprove; default jsonschema with documented fallback |
| A6 | `TemporalDriftError` + `PayloadTooLargeError` from `_v02/exceptions.py` can be carried in source tree but unexported without breaking tests | CORE-04 | Low — verified `__all__` controls export; tests import them directly via class name |
| A7 | The 20-station whitelist (parity fixtures README) covers all v0.1 Kalshi cities | MARKETS-01 | If Kalshi has additional NHIGH/NLOW cities outside the whitelist, contract test will pass but `research()` will fail for those — document v0.1 supported cities in README |

**If user confirms A1, A4, A7 before Phase 2 start, all `[ASSUMED]` claims become `[VERIFIED]`.** The planner should surface these three as discussion points.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all deps verified in current pyproject.toml
- `_v02/` reusability: HIGH — code inspected, tests counted, line-LOC measured
- Existing parser availability: HIGH for obs+settlement; MEDIUM for MOS forecast (Open Q1)
- Kalshi contract data: MEDIUM — 20-station whitelist confirmed, per-city ticker mapping ASSUMED
- Validator engine: MEDIUM — jsonschema default is defensible but pandera spike is real

**Research date:** 2026-05-21
**Valid until:** 2026-06-21 (30 days; v0.1 stack pins are stable through ship)

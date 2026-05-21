---
phase: 02-core-primitives-catalog-adapters
type: execute
duration: Days 5-9 (5 working days)
waves: 5
depends_on: [phase-01-v0141-parity-lift]
branch_strategy: per-wave; sub-branch per parallel task; codex review before merge to wave branch; wave merges to merged-vision
requirements:
  - CORE-01
  - CORE-02
  - CORE-03
  - CORE-04
  - CORE-05
  - CORE-07
  - CORE-08
  - CATALOG-01
  - CATALOG-02
  - CATALOG-03
  - CATALOG-04
  - CATALOG-05
  - MARKETS-01
  - MARKETS-02
  - MARKETS-03
  - PKG-03
autonomous: false  # Open Q1 (MOS parser) RESOLVED — deferred to Phase 3; A1/A4/A7 still pending operator before Wave 5
files_modified:
  - packages/core/src/tradewinds/_v02/**
  - packages/core/src/tradewinds/core/**          # NEW (Wave 1 git-mv destination)
  - packages/core/tests/_v02/**
  - packages/core/tests/core/**                   # NEW (Wave 1 git-mv destination)
  - packages/core/src/tradewinds/_internal/exceptions.py
  - packages/weather/src/tradewinds/weather/catalog/**   # NEW (Wave 3)
  - packages/weather/tests/catalog/**                    # NEW (Wave 3)
  - packages/markets/src/tradewinds/markets/catalog/**   # NEW (Wave 4)
  - packages/markets/tests/catalog/**                    # NEW (Wave 4)
  - packages/core/pyproject.toml                  # Wave 5
  - packages/weather/pyproject.toml               # Wave 5
  - packages/markets/pyproject.toml               # Wave 5
  - .github/workflows/wheel-metadata-check.yml    # Wave 5
must_haves:
  truths:
    - "266 _v02 tests pass under tradewinds.core.* import paths (Wave 1 rebrand zero behavior change)."
    - "TradewindsError is the canonical exception base; MostlyRightMCPError alias raises DeprecationWarning once per session."
    - "TherminalError (in _internal) is a subclass of TradewindsError; Phase 1 fetcher tests continue to pass."
    - "KnowledgeView is a plain class with __slots__ that filters a DataFrame by knowledge_time <= as_of and is NOT a pandas accessor."
    - "LeakageDetector.assert_no_leakage(df, as_of) raises LeakageError listing up to 10 violating rows when knowledge_time > as_of."
    - "All three canonical schemas (observation.v1, forecast.iem_mos.v1, settlement.cli.v1) validate via Validator with source-identity invariant; SourceMismatchError names both data_source and schema_source."
    - "settlement.cli.v1 schema includes cli_data_quality enum and settlement_finality columns (Pitfall 6/16)."
    - "All four weather adapters (iem, awc, cli, ghcnh) declare SUPPORTED_SOURCES at class level, emit canonical-schema DataFrames with overlay columns (source, retrieved_at, knowledge_time, event_time), and pass recorded-fixture tests."
    - "Eager registry in tradewinds.weather.catalog.__init__ dispatches by source ID; get_adapter('iem.archive') returns an IEMAdapter instance."
    - "KALSHI_SETTLEMENT_STATIONS maps 20 city tickers to {KNYC, KMDW, KMIA, KAUS, KLAX, KDEN, KBOS, ...} with citation URLs; contract test asserts none resolve to {KLGA, KJFK, KORD}."
    - "kalshi_nhigh.resolve() and kalshi_nlow.resolve() return deterministic (settlement_source, settlement_station) tuples for every supported ticker."
    - "Built wheels for tradewinds-weather and tradewinds-markets contain Requires-Dist: tradewinds>=0.1.0,<0.2 (METADATA grep CI check passes)."
    - "Format roundtrip tests (dataframe, json, parquet, toon, csv) preserve dtypes for tz-aware timestamps, Float64 nullable, Int64 nullable, and categorical columns."
  artifacts:
    - path: packages/core/src/tradewinds/core/__init__.py
      provides: "Public surface for tradewinds.core (re-exports TimePoint, KnowledgeView, LeakageDetector, Schema, Validator, TradewindsError + subclasses)"
    - path: packages/core/src/tradewinds/core/exceptions.py
      provides: "TradewindsError + MostlyRightMCPError alias + 5 subclasses with to_dict()"
    - path: packages/core/src/tradewinds/core/temporal/timepoint.py
      provides: "TimePoint (REUSE from _v02/timepoint.py)"
    - path: packages/core/src/tradewinds/core/temporal/knowledge_view.py
      provides: "KnowledgeView plain class with __slots__"
    - path: packages/core/src/tradewinds/core/temporal/leakage.py
      provides: "LeakageDetector + assert_no_leakage"
    - path: packages/core/src/tradewinds/core/schema.py
      provides: "Schema base + ColumnSpec + SchemaRegistration (REUSE from _v02/schema.py)"
    - path: packages/core/src/tradewinds/core/validator.py
      provides: "validate_dataframe(df, schema_id, allow_source_drift=None) -> SchemaRegistration; jsonschema-backed"
    - path: packages/core/src/tradewinds/core/schemas/observation.py
      provides: "schema.observation.v1 (REUSE verbatim)"
    - path: packages/core/src/tradewinds/core/schemas/forecast.py
      provides: "schema.forecast.iem_mos.v1 (REUSE verbatim)"
    - path: packages/core/src/tradewinds/core/schemas/settlement.py
      provides: "schema.settlement.cli.v1 + new cli_data_quality + settlement_finality columns"
    - path: packages/core/src/tradewinds/core/formats/{dataframe,json,parquet,toon,csv}.py
      provides: "5 format serializers + _toon + _toon_list_codec (REUSE from _v02/formats/)"
    - path: packages/weather/src/tradewinds/weather/catalog/__init__.py
      provides: "WeatherAdapter Protocol + _REGISTRY + get_adapter(source)"
    - path: packages/weather/src/tradewinds/weather/catalog/{iem,awc,cli,ghcnh}.py
      provides: "Four adapter classes wrapping Phase 1 parsers"
    - path: packages/markets/src/tradewinds/markets/catalog/kalshi_stations.py
      provides: "KALSHI_SETTLEMENT_STATIONS constant (20 entries)"
    - path: packages/markets/src/tradewinds/markets/catalog/{kalshi_nhigh,kalshi_nlow}.py
      provides: "Deterministic resolve(contract_id, date) -> (source, station)"
  key_links:
    - from: tradewinds.weather.catalog.iem.IEMAdapter
      to: tradewinds.weather._iem.iem_to_observation
      via: "wraps row parser; projects to schema.observation.v1; sets df.attrs['source']"
    - from: tradewinds.weather.catalog.cli.CLIAdapter
      to: tradewinds.weather._climate.parse_cli_record + REPORT_TYPE_PRIORITY dedup
      via: "applies (station, observation_date) dedup lifted from v0.14.1 pairs.py"
    - from: tradewinds.core.validator.validate_dataframe
      to: tradewinds.core.schema.SchemaRegistration._append_audit
      via: "source-identity audit-log seam at _v02/schema.py:158"
    - from: tradewinds.markets.catalog.kalshi_nhigh.resolve
      to: tradewinds.markets.catalog.kalshi_stations.KALSHI_SETTLEMENT_STATIONS
      via: "dict lookup; returns ('cli.archive', station) tuple"
---

<objective>
Build the architectural spine of tradewinds v0.1.0 on top of the now-stable Phase 1 parity baseline: temporal-safety primitives (TimePoint, KnowledgeView, LeakageDetector), the declarative Schema framework + three canonical schemas, a source-identity-enforcing Validator, the renamed exception hierarchy, five format serializers, four weather catalog adapters wrapping Phase 1 parsers, and Kalshi NHIGH/NLOW contract specs with the 20-station settlement whitelist.

**Purpose** — the rebrand-not-rebuild insight: `packages/core/src/tradewinds/_v02/` already contains a 266-test passing reference implementation (2,947 source LOC + 2,947 test LOC across 17 files) ported from `mostlyright-mcp/feat/wave-1-core`. It implements 4 of the 7 core requirements (CORE-02/03/04/05) verbatim — only the `MostlyRightMCPError` brand and the import path are wrong. Phase 2's central insight is that we **promote the dormant reference into the canonical implementation via git-mv + sed**, then **build the four NEW pieces on top** (KnowledgeView, LeakageDetector, Validator, catalog adapter wrappers). Five days, five waves, two-lane parallel.

**Output** — `tradewinds.core.*` public surface, `tradewinds.weather.catalog.*` adapter registry, `tradewinds.markets.catalog.{kalshi_nhigh,kalshi_nlow}`, and inter-package version pins in built wheels.
</objective>

<execution_context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/REQUIREMENTS.md
@.planning/STATE.md
@.planning/phase-02-core-primitives-catalog-adapters/RESEARCH.md
@docs/design.md
</execution_context>

<phase_summary>

**Goal:** ship `tradewinds.core.*`, four weather catalog adapters, and Kalshi NHIGH/NLOW contract specs in 5 days.

**The rebrand-not-rebuild insight:** `_v02/` is the dormant Phase 2 implementation. We git-mv → sed → run-tests → commit. 266 tests stay green through the rename. Then we layer KnowledgeView/LeakageDetector/Validator/adapters/Kalshi on top of the renamed core.

**Wave structure (5 waves, Days 5-9):**

| Wave | Day | Branch | Goal | Parallel lanes |
|------|-----|--------|------|----------------|
| 1 | Day 5 AM + spike | `phase-2/wave-1-rebrand` | `_v02/` → `tradewinds.core` + exception rename + schema fixes | 1 lane (atomic) |
| 2 | Day 6 | `phase-2/wave-2-primitives` | KnowledgeView + LeakageDetector | 1 lane (single feature, tight coupling) |
| 3 | Day 7 | `phase-2/wave-3-validator` | Validator (jsonschema engine) | 1 lane |
| 4 | Day 8 | `phase-2/wave-4-adapters` | 4 catalog adapter wrappers + registry | 4 sub-branches (parallel) |
| 5 | Day 9 | `phase-2/wave-5-markets-pkg` | Kalshi specs + PKG-03 wheel pins | 2 sub-branches (parallel) |

**Branch flow per wave:** sub-branches off the wave branch → codex review per sub-branch → merge to wave branch → run full test suite → merge wave branch to `merged-vision`. No direct commits to `merged-vision`.

</phase_summary>

<wave id="1" name="Rebrand _v02 → tradewinds.core + exception rename + schema fixes">

**Day:** Day 5 (morning spike + afternoon execution)
**Branch:** `phase-2/wave-1-rebrand` off `merged-vision`
**Parallelism:** 1 lane — this wave is atomic and must complete before anything else fans out (R1 mitigation).
**Estimated effort:** 1 day (morning Validator spike + afternoon rebrand + late afternoon schema additions)
**Delivers:** CORE-03 (schemas pinned), CORE-04 (exception hierarchy), CORE-05 (format serializers), Decision 2 (Validator engine confirmation)

### Goal

Promote the dormant `packages/core/src/tradewinds/_v02/` reference implementation into the canonical `packages/core/src/tradewinds/core/` namespace, rename `MostlyRightMCPError` → `TradewindsError` with an alias shim, reconcile the `_internal/exceptions.py:TherminalError` hierarchy, and add the two pre-release schema columns (`cli_data_quality`, `settlement_finality`) that Pitfalls 6 + 16 require.

### Dependencies

- Phase 1 merged to `merged-vision` (✓ assumed by ROADMAP entry).
- Operator confirmation NOT required for Wave 1; can start Day 5 morning.

### Tasks

#### Task 1.0: Validator engine spike (Day 5 morning, 2 hours)

- **Branch:** `phase-2/wave-1-rebrand/spike-validator` (throwaway; outcome is a decision, not merged code).
- **Files:** `spike/validator_engine.py` (delete before wave merge); `.planning/phase-02-core-primitives-catalog-adapters/DECISIONS.md` (NEW, append).
- **Action:** Implement two prototype Validators against `_v02/schemas/observation.py` — one using `jsonschema` (≤200 LOC manual ColumnSpec→jsonschema translation), one using `pandera` 0.29 (sketch). Measure: LOC delta, first-import time, dep tree depth, runtime on a 10k-row fixture.
- **Decision rule:** keep jsonschema (RESEARCH.md Decision 2 default) unless pandera shows >30% LOC reduction net of deps AND first-import <500ms cold. Document outcome in `DECISIONS.md` under `D-02: Validator engine`.
- **Codex review priority:** medium (decision artifact, not shipped code).
- **Atomic commit:** `docs(phase-2): record D-02 Validator engine decision (jsonschema confirmed)`.
- **Test bar:** the spike produces measurements, not tests. The shipped Validator (Wave 3) is what carries tests.

#### Task 1.1: git-mv `_v02/` → `core/` (single coordinated commit set)

- **Files moved (per RESEARCH.md inventory):**
  - `packages/core/src/tradewinds/_v02/timepoint.py` → `packages/core/src/tradewinds/core/temporal/timepoint.py`
  - `packages/core/src/tradewinds/_v02/exceptions.py` → `packages/core/src/tradewinds/core/exceptions.py`
  - `packages/core/src/tradewinds/_v02/_json_safe.py` → `packages/core/src/tradewinds/core/_json_safe.py`
  - `packages/core/src/tradewinds/_v02/schema.py` → `packages/core/src/tradewinds/core/schema.py`
  - `packages/core/src/tradewinds/_v02/schemas/{__init__,observation,forecast,settlement}.py` → `packages/core/src/tradewinds/core/schemas/{...}`
  - `packages/core/src/tradewinds/_v02/formats/{__init__,_toon,_toon_list_codec,csv,dataframe,json,parquet,toon}.py` → `packages/core/src/tradewinds/core/formats/{...}`
  - `packages/core/tests/_v02/test_*.py` → `packages/core/tests/core/test_*.py`
  - `packages/core/tests/_v02/test_schemas/test_*.py` → `packages/core/tests/core/test_schemas/test_*.py`
- **Action:** Run `git mv` per file (preserves history). Create new empty dirs (`core/`, `core/temporal/`, `core/schemas/`, `core/formats/`, `tests/core/`) with `__init__.py` first. Then per-file moves.
- **Atomic commit:** `refactor(phase-2): git-mv _v02/ → tradewinds.core/ (no content change)`.
- **Codex review priority:** high (parity-critical — any missed file breaks 266 tests).
- **Test bar:** `pytest packages/core/tests/core/` MUST report identical pass count (266) as the pre-move `pytest packages/core/tests/_v02/`. Import paths in tests will still fail after the mv — the test pass happens after Task 1.2.

#### Task 1.2: sed rename `_v02` → `core`, `MostlyRightMCPError` → `TradewindsError`, `MOSTLYRIGHT_MCP_ERROR` → `TRADEWINDS_ERROR`

- **Files:** every `.py` under `packages/core/src/tradewinds/core/` and `packages/core/tests/core/`.
- **Action:**
  1. `grep -rl '_v02' packages/core/ | xargs sed -i '' 's|tradewinds\._v02|tradewinds.core|g'` (macOS sed -i variant).
  2. `grep -rl '_v02' packages/core/ | xargs sed -i '' 's|from \._v02|from .core|g'` and similar absolute-import variants — verify zero `_v02` references remain via `grep -r _v02 packages/core/` (must return empty).
  3. In `packages/core/src/tradewinds/core/exceptions.py`:
     - Rename class `MostlyRightMCPError` → `TradewindsError`.
     - Update `default_error_code = "MOSTLYRIGHT_MCP_ERROR"` → `"TRADEWINDS_ERROR"`.
     - Add at end of module: `MostlyRightMCPError = TradewindsError` and a `__getattr__` wrapper that emits `DeprecationWarning("MostlyRightMCPError is deprecated; use TradewindsError. Removal in v0.3.", stacklevel=2)` once per session (use `_warnings_emitted: set[str]` module-level state).
     - Update `__all__` to include both names.
  4. In every other file under `core/`: `sed 's|MostlyRightMCPError|TradewindsError|g'` then `sed 's|MOSTLYRIGHT_MCP_ERROR|TRADEWINDS_ERROR|g'`.
  5. Update docstrings: `sed 's|mostlyright-mcp|tradewinds|g; s|mostlyright_mcp|tradewinds|g'` across `core/`.
  6. Update `tests/core/test_exceptions.py` if it asserts on `default_error_code` string — verify the alias-emits-warning test exists (add if missing).
- **Action (followup, Decision 6 reconcile):** Edit `packages/core/src/tradewinds/_internal/exceptions.py`:
  - Add `from tradewinds.core.exceptions import TradewindsError` at top.
  - Change `class TherminalError(Exception)` → `class TherminalError(TradewindsError)`.
  - Add module-level: `# DEPRECATED in v0.2 — TherminalError remains as an HTTP-layer marker; subclass of TradewindsError so user code catching TradewindsError catches HTTP errors too.`
  - Keep `NotFoundError`, `RateLimitError`, `ValidationError`, `AuthenticationError` subclassing `TherminalError`. No public-API rename.
- **Atomic commits (3):**
  1. `refactor(phase-2): rename MostlyRightMCPError → TradewindsError + alias shim`.
  2. `refactor(phase-2): rename _v02 import paths to tradewinds.core`.
  3. `refactor(phase-2): TherminalError now subclasses TradewindsError`.
- **Codex review priority:** high (parity-critical — sed errors can silently break invariants).
- **Test bar:**
  - `pytest packages/core/tests/core/` — all 266 tests green.
  - `pytest packages/core/tests/_internal/` — all Phase 1 _internal tests green (R8 mitigation).
  - `pytest packages/weather/tests/` — all Phase 1 weather tests green (no regressions from TherminalError reparenting).
  - `grep -r _v02 packages/core/ tests/` — empty.
  - `grep -r MostlyRightMCPError packages/core/src/` — only the alias line in `core/exceptions.py`.
  - **`test_exception_to_dict_shape`** (codex P2-2 fix): parametrized over all 5 exception subclasses (`TradewindsError`, `SourceUnavailableError`, `SchemaValidationError`, `SourceMismatchError`, `LeakageError`). For each, construct a representative instance, call `.to_dict()`, assert: (a) result is JSON-serializable (`json.dumps(result)` succeeds), (b) required keys `error_code` + `message` present, (c) subclass-specific fields per design §D (e.g. `SourceMismatchError.to_dict()` carries `schema_source` + `data_source` + `role`). Asserts the MCP JSON-RPC contract (ROADMAP SC-5, CORE-04).
  - New test `tests/core/test_exceptions.py::test_mostlyright_mcp_error_alias_emits_deprecation_warning`.

#### Task 1.3: Delete `_v02/__init__.py` quarantine + scaffold `tradewinds.core.__init__.py` public surface

- **Files:**
  - DELETE: `packages/core/src/tradewinds/_v02/` (entire directory after Task 1.1 mv; should be empty).
  - DELETE: `packages/core/tests/_v02/` (likewise).
  - CREATE/EDIT: `packages/core/src/tradewinds/core/__init__.py` with explicit re-exports:
    ```python
    """tradewinds.core — canonical core primitives, schemas, exceptions, formats."""
    from .exceptions import (
        TradewindsError, MostlyRightMCPError,  # alias for deprecated callers
        SourceUnavailableError, SchemaValidationError,
        SourceMismatchError, LeakageError,
    )
    from .temporal.timepoint import TimePoint
    # KnowledgeView, LeakageDetector wired by Wave 2 (placeholders raise NotImplementedError until then).
    from .schema import Schema, ColumnSpec, SchemaRegistration
    # validate_dataframe wired by Wave 3.
    __all__ = [...]  # explicit
    ```
- **Action:** Do NOT export `TemporalDriftError` or `PayloadTooLargeError` (per RESEARCH.md CORE-04 — kept in source tree, omitted from `__all__`).
- **Action (codex P2-1 fix — eager schema registration):** Edit `packages/core/src/tradewinds/core/schemas/__init__.py` to eagerly import all three concrete schemas AND call `Schema.register()` on each at import time so the source-identity invariant is enforced for canonical schemas without the caller having to register first. Specifically:
  ```python
  """tradewinds.core.schemas — canonical schemas registered eagerly at import."""
  from datetime import UTC, datetime
  from .observation import ObservationSchema
  from .forecast import ForecastSchema
  from .settlement import SettlementSchema

  # Eager registration with canonical source IDs. ROADMAP SC-2 + design §B require this.
  # Validator's source-identity invariant depends on Schema._registered_source being set.
  _now = datetime.now(UTC)
  ObservationSchema.register(source="iem.archive", retrieved_at=_now, rows=0)
  ForecastSchema.register(source="iem.archive", retrieved_at=_now, rows=0)
  SettlementSchema.register(source="cli.archive", retrieved_at=_now, rows=0)
  __all__ = ["ObservationSchema", "ForecastSchema", "SettlementSchema"]
  ```
- **Atomic commit:** `feat(phase-2): scaffold tradewinds.core public surface + eager schema registration`.
- **Codex review priority:** medium.
- **Test bar:**
  - `from tradewinds.core import TradewindsError, TimePoint, Schema` works.
  - `from tradewinds.core import TemporalDriftError` raises ImportError.
  - **`test_schemas_eagerly_registered`** (codex P2-1 fix): import `tradewinds.core.schemas` and assert each of the three concrete schema classes has `._registered_source` set to its canonical ID (`iem.archive` for obs + forecasts, `cli.archive` for settlement). Without this, Validator's source-identity invariant silently no-ops on canonical schemas.

#### Task 1.4: Schema additions — `cli_data_quality` + `settlement_finality` (Pitfall 6 + 16)

- **Files:**
  - EDIT: `packages/core/src/tradewinds/core/schemas/settlement.py` — add two ColumnSpec entries.
  - EDIT: `packages/core/tests/core/test_schemas/test_settlement.py` — extend contract test.
- **Action:** Append two ColumnSpec entries to `SettlementSchema.COLUMNS`:
  ```python
  ColumnSpec(
      name="cli_data_quality",
      dtype="enum",
      units=None,
      nullable=True,
      enum_values=("estimated", "substituted", "nearby", "representative", "backup", "cooperative", None),
      notes="Pitfall 6 — REMARKS-derived quality flag; None = no quality concern noted.",
  ),
  ColumnSpec(
      name="settlement_finality",
      dtype="enum",
      units=None,
      nullable=False,
      enum_values=("prelim", "final", "corrected"),
      notes="Pitfall 16 — finality state separate from report_type; corrections that match original prelim/final still flagged corrected.",
  ),
  ```
- **Codex review priority:** high (schema additions are pre-release-cheap, post-release-breaking — get them right now).
- **Atomic commit:** `feat(CORE-03): add cli_data_quality + settlement_finality to settlement.cli.v1`.
- **Test bar:** `test_settlement.py::test_schema_columns_match_design` updated to expect the two new columns. Contract test (column names + dtypes + null tolerance + enum values) green.

### Wave 1 Success Criteria

- [ ] All 266 `_v02/`-origin tests green under new `tests/core/` paths.
- [ ] All Phase 1 `tests/_internal/` and `packages/weather/tests/` green (no regressions from TherminalError reparenting).
- [ ] `grep -r MostlyRightMCPError packages/core/src/` returns only the alias declaration line.
- [ ] `from tradewinds.core import TradewindsError, TimePoint, Schema` works at REPL.
- [ ] DeprecationWarning fires exactly once per session when importing `MostlyRightMCPError`.
- [ ] `schema.settlement.cli.v1` has 12 columns (10 original + cli_data_quality + settlement_finality).
- [ ] `DECISIONS.md` records Validator engine spike outcome.
- [ ] Wave 1 branch merged to `merged-vision` with full test suite green.

</wave>

<wave id="2" name="KnowledgeView + LeakageDetector (NEW core primitives)">

**Day:** Day 6
**Branch:** `phase-2/wave-2-primitives` off updated `merged-vision`
**Parallelism:** 1 lane — KnowledgeView and LeakageDetector share property-test infrastructure (CORE-08 constrained datetimes) and are tightly coupled.
**Estimated effort:** 1 day
**Delivers:** CORE-01 (TimePoint reused + KnowledgeView + LeakageDetector NEW), CORE-07 (plain class with __slots__), CORE-08 (constrained Hypothesis ranges)

### Goal

Add the two new temporal-safety primitives that `_v02/` doesn't ship. KnowledgeView is a plain class with `__slots__ = ("_df", "_as_of")` that filters `df[df.knowledge_time <= as_of]`. LeakageDetector raises `LeakageError` with up to 10 sample violations when an as-of cutoff is violated.

### Dependencies

- Wave 1 merged (need `tradewinds.core.exceptions.LeakageError`, `tradewinds.core.temporal.timepoint.TimePoint`).

### Tasks

#### Task 2.1: Implement `KnowledgeView`

- **Branch:** `phase-2/wave-2-primitives/knowledge-view` off `phase-2/wave-2-primitives`.
- **Files:**
  - CREATE: `packages/core/src/tradewinds/core/temporal/knowledge_view.py` (~80 LOC).
  - CREATE: `packages/core/tests/core/temporal/test_knowledge_view.py` (~250 LOC property + unit tests).
  - CREATE: `packages/core/tests/core/test_knowledgeview_no_accessor.py` (~30 LOC — CORE-07 acceptance).
- **Action:** Implement per RESEARCH.md verified pattern:
  ```python
  class KnowledgeView:
      __slots__ = ("_df", "_as_of")
      def __init__(self, df: pd.DataFrame, as_of: TimePoint):
          if "knowledge_time" not in df.columns:
              raise SchemaValidationError(
                  message="KnowledgeView requires 'knowledge_time' column",
                  schema_id="<runtime>",
                  violations=[{"column": "knowledge_time", "rule": "required"}],
              )
          if not isinstance(as_of, TimePoint):
              raise TypeError("as_of must be a TimePoint")
          # dtype check — must be tz-aware UTC timestamp
          col = df["knowledge_time"]
          if not (pd.api.types.is_datetime64_any_dtype(col) and getattr(col.dt, "tz", None) is not None):
              raise SchemaValidationError(
                  message="knowledge_time must be tz-aware UTC",
                  schema_id="<runtime>",
                  violations=[{"column": "knowledge_time", "rule": "tz_aware_utc"}],
              )
          self._df = df
          self._as_of = as_of
      def dataframe(self) -> pd.DataFrame:
          return self._df.loc[self._df["knowledge_time"] <= self._as_of.to_utc()].copy()
      @property
      def as_of(self) -> TimePoint:
          return self._as_of
  ```
- **Property tests (Hypothesis, CORE-08 constrained):**
  ```python
  @given(
      events=st.lists(
          st.datetimes(
              min_value=datetime(2018, 1, 1),
              max_value=datetime(2027, 12, 31),
              timezones=st.just(UTC),
          ),
          min_size=0, max_size=50,
      ),
      as_of=st.datetimes(min_value=datetime(2018, 1, 1), max_value=datetime(2027, 12, 31), timezones=st.just(UTC)),
  )
  @settings(max_examples=200, deadline=2000)
  def test_kv_filter_is_correct(events, as_of):
      # property: every row in result has knowledge_time <= as_of
      # property: no row dropped that should have been kept (count equality vs manual filter)
  ```
- **Acceptance test (CORE-07):** `test_knowledgeview_no_accessor.py` asserts (a) `KnowledgeView` has `__slots__`, (b) `hasattr(pd.DataFrame, "knowledge_view") is False`, (c) instantiation does not call `pd.api.extensions.register_dataframe_accessor`.
- **Codex review priority:** high (NEW primitive, load-bearing for v0.2 research() Mode 2).
- **Atomic commit:** `feat(CORE-01): KnowledgeView plain class with __slots__ + Hypothesis property tests`.
- **Test bar:** property tests pass with `max_examples=200, deadline=2000`; DST-boundary cases 2024-03-10, 2024-11-03 explicit fixtures; 90%+ branch coverage on `knowledge_view.py`.

#### Task 2.2: Implement `LeakageDetector`

- **Branch:** `phase-2/wave-2-primitives/leakage-detector` off `phase-2/wave-2-primitives`.
- **Files:**
  - CREATE: `packages/core/src/tradewinds/core/temporal/leakage.py` (~60 LOC).
  - CREATE: `packages/core/tests/core/temporal/test_leakage.py` (~200 LOC).
- **Action:**
  ```python
  def assert_no_leakage(df: pd.DataFrame, as_of: TimePoint) -> None:
      """Raise LeakageError if any row's knowledge_time > as_of."""
      if "knowledge_time" not in df.columns:
          raise SchemaValidationError(...)
      mask = df["knowledge_time"] > as_of.to_utc()
      n = int(mask.sum())
      if n == 0:
          return
      sample = df.loc[mask].head(10)
      sample_violations = [
          {"row_idx": int(idx), "knowledge_time": pd.Timestamp(row["knowledge_time"]).isoformat()}
          for idx, row in sample.iterrows()
      ]
      raise LeakageError(
          message=f"Found {n} row(s) with knowledge_time > as_of",
          as_of=as_of.to_utc().isoformat(),
          violating_count=n,
          sample_violations=sample_violations,
      )

  class LeakageDetector:
      """Convenience wrapper for repeated detection against a fixed as_of."""
      __slots__ = ("_as_of",)
      def __init__(self, as_of: TimePoint):
          if not isinstance(as_of, TimePoint):
              raise TypeError("as_of must be TimePoint")
          self._as_of = as_of
      def check(self, df: pd.DataFrame) -> None:
          assert_no_leakage(df, self._as_of)
  ```
- **Property tests:** same constrained-datetime range; assert exactly `mask.sum()` violations are sampled (capped at 10).
- **Negative tests:** missing `knowledge_time` column raises `SchemaValidationError` (not `LeakageError`); naive timestamps in column raise upstream.
- **Codex review priority:** high.
- **Atomic commit:** `feat(CORE-01): LeakageDetector + assert_no_leakage with sample_violations cap=10`.
- **Test bar:** property tests pass; sample_violations payload validated against design §D `LeakageError` shape; 90%+ branch coverage on `leakage.py`.

#### Task 2.3: Wire into `tradewinds.core.__init__`

- **Branch:** merge 2.1 + 2.2 into `phase-2/wave-2-primitives`, then this small wiring commit.
- **Files:** EDIT `packages/core/src/tradewinds/core/__init__.py`.
- **Action:** Replace the Wave 1 placeholder lines with real imports:
  ```python
  from .temporal.knowledge_view import KnowledgeView
  from .temporal.leakage import LeakageDetector, assert_no_leakage
  ```
- **Atomic commit:** `feat(CORE-01): export KnowledgeView + LeakageDetector from tradewinds.core`.
- **Codex review priority:** low.
- **Test bar:** `from tradewinds.core import KnowledgeView, LeakageDetector, assert_no_leakage` works at REPL.

### Wave 2 Success Criteria

- [ ] CORE-01 acceptance: `KnowledgeView` and `LeakageDetector` implemented with property tests using constrained datetime range.
- [ ] CORE-07 acceptance: `KnowledgeView` is a plain class with `__slots__`, does NOT register a pandas accessor.
- [ ] CORE-08 acceptance: all property tests use `min=2018-01-01, max=2027-12-31, tz=just(UTC), max_examples=200, deadline=2000`.
- [ ] `tests/core/temporal/test_knowledge_view.py` and `test_leakage.py` branch coverage ≥90%.
- [ ] Wave 2 branch merges cleanly to `merged-vision` with full test suite green.

</wave>

<wave id="3" name="Validator (jsonschema-backed, source-identity enforcement)">

**Day:** Day 7
**Branch:** `phase-2/wave-3-validator` off updated `merged-vision`
**Parallelism:** 1 lane (single component; ~250 LOC + 350 LOC tests).
**Estimated effort:** 1 day
**Delivers:** CORE-02 (Validator + source-identity invariant via SourceMismatchError)

### Goal

Implement `validate_dataframe(df, schema_id, *, allow_source_drift: str | None = None) -> SchemaRegistration` using the jsonschema engine confirmed in Wave 1 Task 1.0. Validator reads `df.attrs["source"]`, compares against `Schema._registered_source`, and raises `SourceMismatchError` when they differ — unless the caller opts out via `allow_source_drift` (logged to `SchemaRegistration._append_audit`).

### Dependencies

- Wave 1 (Schema framework + SourceMismatchError available under `tradewinds.core.*`).
- D-02 decision (Wave 1 Task 1.0) confirms jsonschema.

### Tasks

#### Task 3.1: Build Validator core

- **Files:**
  - CREATE: `packages/core/src/tradewinds/core/validator.py` (~220 LOC).
  - CREATE: `packages/core/tests/core/test_validator.py` (~350 LOC).
- **Action:** Implement per RESEARCH.md CORE-02 sketch:
  ```python
  def validate_dataframe(
      df: pd.DataFrame,
      schema_id: str,
      *,
      allow_source_drift: str | None = None,
  ) -> SchemaRegistration:
      schema_cls = _lookup_schema(schema_id)
      # 1. Source-identity check (the load-bearing invariant)
      data_source = df.attrs.get("source")
      if data_source is None:
          raise SchemaValidationError(
              message="DataFrame missing df.attrs['source']; cannot validate source-identity",
              schema_id=schema_id,
              violations=[{"rule": "source_attr_required"}],
              quarantine_count=len(df),
              sample_violations=[],
          )
      registered_source = schema_cls._registered_source  # populated by Schema.register()
      if registered_source is not None and data_source != registered_source:
          if allow_source_drift is None:
              raise SourceMismatchError(
                  message=f"Source drift: data is {data_source!r}, schema expects {registered_source!r}",
                  schema_source=registered_source,
                  data_source=data_source,
                  role=None,  # solo-schema validation; per-role version lives in research() Mode 2
                  catalog_warning=None,
              )
          # Opted-out: log to audit
          reg = schema_cls.current_registration()
          reg._append_audit("source_drift_allowed", reason=allow_source_drift)
      # 2. Column-presence check
      missing = [col.name for col in schema_cls.COLUMNS if col.name not in df.columns and not col.nullable]
      # 3. Dtype check (dispatch on ColumnSpec.dtype canonical tag)
      # 4. Null-rule check
      # 5. Enum-value check (use jsonschema for enum columns specifically)
      # ... collect violations into list; raise SchemaValidationError if any
      # 6. Returns the updated SchemaRegistration
  ```
- **Action (dtype dispatch table):**
  ```python
  _DTYPE_CHECKERS = {
      "string":         lambda s: pd.api.types.is_string_dtype(s) or s.dtype == "object",
      "float64":        lambda s: pd.api.types.is_float_dtype(s),
      "int":            lambda s: pd.api.types.is_integer_dtype(s),
      "date":           lambda s: pd.api.types.is_datetime64_any_dtype(s),  # date is timestamp truncated
      "timestamp_utc":  lambda s: pd.api.types.is_datetime64_any_dtype(s) and getattr(s.dt, "tz", None) is not None,
      "enum":           lambda s: True,  # enum_values check is separate
  }
  ```
- **Action (null check):** `if not col_spec.nullable and df[col].isna().any(): violations.append({"column": col, "rule": "non_nullable"})`. Pitfall 15 mitigation: also flag mixed null sentinels per column (`pd.NA` vs `np.nan` vs `None`) — `_no_mixed_nulls(s)` helper.
- **Action (enum check):** for `dtype="enum"` columns, build a jsonschema fragment `{"type": "string", "enum": list(col_spec.enum_values)}` and validate column values against it; collect violating row indices (capped at 10 for `sample_violations`).
- **Codex review priority:** high (load-bearing invariant; D-02 decision implementation).
- **Atomic commit:** `feat(CORE-02): Validator with source-identity invariant + jsonschema enum check`.

#### Task 3.2: Negative-test matrix (design §H test bar)

- **Files:** extend `test_validator.py`.
- **Action:** Tests for each row of design §H test bar that applies to Validator:
  1. Source mismatch raises `SourceMismatchError` with both `schema_source` and `data_source` named.
  2. `allow_source_drift="reason"` → no raise, audit entry appended with `reason`.
  3. Missing `df.attrs["source"]` raises `SchemaValidationError`, not `SourceMismatchError`.
  4. Missing required column → `SchemaValidationError` with violation row.
  5. Dtype mismatch (`float64` schema column receiving `Int64` data) → violation collected.
  6. Enum violation → violation collected with sample_violations capped at 10.
  7. Mixed null sentinels (`pd.NA` + `np.nan` in same column) → violation collected (Pitfall 15).
  8. **Pitfall 8 — IEM `M` sentinel preservation (codex cross-ref fix):** the IEM parser converts `"M"` (IEM's missing-data sentinel) to `pd.NA`. Validator must NOT confuse `pd.NA` with `0` or `np.nan` downstream — a column with `pd.NA` in a nullable position must validate without error, but a column where `pd.NA` was silently coerced to `0` (e.g. a buggy adapter using `.fillna(0)` upstream) must FAIL the Validator's distinct-sentinel check. This is the W3 mirror of the W4 IEMAdapter Pitfall 8 property test — guards the invariant from both the schema side (here) and the source side (Wave 4 Task 4.1).
- **Atomic commit:** `test(CORE-02): negative-test matrix for Validator per design §H`.
- **Codex review priority:** high.

#### Task 3.3: Wire into `tradewinds.core.__init__`

- **Files:** EDIT `packages/core/src/tradewinds/core/__init__.py`.
- **Action:** Add `from .validator import validate_dataframe` and append to `__all__`.
- **Atomic commit:** `feat(CORE-02): export validate_dataframe from tradewinds.core`.
- **Codex review priority:** low.

### Wave 3 Success Criteria

- [ ] `validate_dataframe(good_df, "schema.observation.v1")` returns a `SchemaRegistration` instance.
- [ ] Source drift raises `SourceMismatchError` with both `schema_source` and `data_source` populated.
- [ ] `allow_source_drift="backfill"` opts out cleanly and the SchemaRegistration audit log contains an entry.
- [ ] Wave 3 branch ≥90% branch coverage on `validator.py`; full test suite green; merges to `merged-vision`.

</wave>

<wave id="4" name="Catalog adapters (4 parallel sub-branches)">

**Day:** Day 8
**Branch:** `phase-2/wave-4-adapters` off updated `merged-vision`
**Parallelism:** **4 parallel sub-branches** (Day-8 high parallelism — agents fan out, codex reviews each independently).
**Estimated effort:** 1 day with 4-lane parallelism (each adapter is ~250 LOC + ~250 LOC tests)
**Delivers:** CATALOG-01 (IEM), CATALOG-02 (AWC), CATALOG-03 (CLI), CATALOG-04 (GHCNh), CATALOG-05 (Protocol + registry)

### Goal

Wrap the four Phase 1 parsers (`tradewinds.weather._{iem,awc,climate,ghcnh}.py`) in adapter classes that emit canonical-schema DataFrames with overlay columns. Build the eager-import registry + `WeatherAdapter` Protocol.

### Dependencies

- Wave 1 (canonical schemas + TradewindsError); Wave 2 (TimePoint); **Wave 3 (Validator) is a HARD prerequisite**.
- **Wave 4 cannot start sub-branches until Wave 3 merges to `merged-vision`** (codex P2-3 fix). Adapter integration tests in 4.1-4.4 each call `validate_dataframe(adapter_output, "schema.observation.v1")`; without Validator merged, those tests fail at import time and the parallel sub-branches block. The Day-8 4-lane parallelism is therefore Wave-3-merge-then-fan-out (not concurrent with Wave 3). If Wave 3 slips, Wave 4's start slips identically.
- Phase 1 parsers (`packages/weather/src/tradewinds/weather/_{iem,awc,climate,ghcnh}.py`) and fetchers (`_fetchers/{iem_asos,iem_cli,awc,ghcnh}.py`).
- **R3 mitigation:** Wave 4 Task 4.3 (CLI adapter) requires lifting the `(station, observation_date)` dedup logic from `monorepo-v0.14.1/src/mostlyright/pairs.py` (NOT just the parser's `REPORT_TYPE_PRIORITY` dict). The adapter must carry this dedup.
- **Open Q1 RESOLVED — MOS forecast parser CONFIRMED ABSENT (codex P3-1 fix).** Plan-checker grep'd `packages/weather/` on 2026-05-21 — no `_forecast_parse.py` or equivalent lifted in Phase 1. Resolution: **defer the MOS forecast leg to Phase 3** (not Wave 4.5). `CATALOG-01` scope reduced to observations-only for v0.1.0; this matches ROADMAP Phase 2 SC-3 which lists "wrap `_vendor/` parsers" + "recorded-fixture tests green" without explicitly requiring the forecast leg. IEM adapter `fetch_forecasts()` raises `NotImplementedError("MOS forecasts deferred to Phase 3; see Open Q1 resolution in Phase 2 PLAN.md")`. Phase 3 PLAN will lift `monorepo-v0.14.1/src/mostlyright/_forecast_parse.py` + add forecast leg to IEM adapter as part of the Mode-2 integration work. Wave 4.5 (0.5-day MOS lift) is REMOVED from Phase 2.

### Tasks

#### Task 4.0: Scaffold registry + Protocol (kicks off wave, blocks 4.1-4.4)

- **Branch:** `phase-2/wave-4-adapters/scaffold` (small, fast — merged into `phase-2/wave-4-adapters` before 4.1-4.4 branch off).
- **Files:**
  - CREATE: `packages/weather/src/tradewinds/weather/catalog/__init__.py` (~50 LOC).
  - CREATE: `packages/weather/tests/catalog/test_registry.py` (~80 LOC).
- **Action:** Per RESEARCH.md CATALOG-05 sketch:
  ```python
  from typing import Protocol, ClassVar
  import pandas as pd
  from tradewinds.core.exceptions import SourceUnavailableError

  class WeatherAdapter(Protocol):
      SUPPORTED_SOURCES: ClassVar[list[str]]
      def fetch_observations(self, source: str, station: str, from_date: str, to_date: str) -> pd.DataFrame: ...

  # imports below filled by 4.1-4.4 in their respective sub-branches; wave-merge stitches them.
  # Initially scaffold:
  _REGISTRY: dict[str, type] = {}

  def get_adapter(source: str) -> WeatherAdapter:
      if source not in _REGISTRY:
          raise SourceUnavailableError(
              message=f"Unknown source {source!r}; known sources: {sorted(_REGISTRY)}",
              source=source,
          )
      return _REGISTRY[source]()
  ```
- **Atomic commit:** `feat(CATALOG-05): scaffold WeatherAdapter Protocol + empty registry`.
- **Codex review priority:** medium.
- **Test bar:** `get_adapter('unknown')` raises `SourceUnavailableError` with install hint; placeholder until adapter sub-branches populate `_REGISTRY`.

#### Task 4.1: IEMAdapter (parallel sub-branch)

- **Branch:** `phase-2/wave-4-adapters/iem` off `phase-2/wave-4-adapters`.
- **Files:**
  - CREATE: `packages/weather/src/tradewinds/weather/catalog/iem.py` (~250 LOC).
  - CREATE: `packages/weather/tests/catalog/test_iem.py` (~250 LOC).
  - CREATE: `packages/weather/tests/catalog/fixtures/iem_*.csv` (recorded fixtures — 2 stations × 2 days from Phase 1 fixtures).
- **Action:**
  ```python
  class IEMAdapter:
      SUPPORTED_SOURCES: ClassVar[list[str]] = ["iem.archive", "iem.live"]
      IEM_METAR_LAG = timedelta(minutes=15)  # design §"Definitions"
      __deprecation_notice__ = "IEM MOS forecasts deprecated in favor of NBM; v0.2 adds NBM adapter (Pitfall 9)."

      def fetch_observations(self, source, station, from_date, to_date) -> pd.DataFrame:
          # 1. _fetchers/iem_asos.py downloads CSV → text
          # 2. iem_to_observation rows → list[dict]
          # 3. project to schema.observation.v1 metric columns (use _internal._convert)
          # 4. add overlay: source, retrieved_at = datetime.now(UTC), knowledge_time = event_time + IEM_METAR_LAG
          # 5. df.attrs["source"] = source
          # 6. return DataFrame
  ```
- **Pitfall 8 mitigation:** IEM `M` → `pd.NA` exactly, NEVER 0 or `np.nan`. Property test feeds `M`/`0`/valid; asserts distinguishable downstream.
- **MOS forecast leg:** DEFERRED to Phase 3 per Open Q1 resolution (parser confirmed absent in `packages/weather/` on 2026-05-21). `IEMAdapter.fetch_forecasts()` raises `NotImplementedError("MOS forecasts deferred to Phase 3 — see Open Q1 resolution in Phase 2 PLAN.md")`. CATALOG-01 v0.1.0 scope is observations-only; ROADMAP Phase 2 SC-3 ("wrap parsers" + "recorded-fixture tests green") satisfied by the obs leg alone.
- **Codex review priority:** high (parity-critical wrapping).
- **Atomic commits (2):**
  1. `feat(CATALOG-01): IEMAdapter.fetch_observations wraps weather._iem`.
  2. `test(CATALOG-01): IEMAdapter recorded-fixture + Pitfall 8 missing-data property test`.
- **Test bar:**
  - Recorded-fixture test: load `tests/fixtures/parity/case_1_KNYC_iem.csv`, run through adapter, assert canonical-schema columns + `df.attrs["source"] == "iem.archive"`.
  - Validator integration test: `validate_dataframe(adapter_output, "schema.observation.v1")` passes.
  - Pitfall 8 test: `M`-input rows surface as `pd.NA` for the affected metric column.

#### Task 4.2: AWCAdapter (parallel sub-branch)

- **Branch:** `phase-2/wave-4-adapters/awc` off `phase-2/wave-4-adapters`.
- **Files:**
  - CREATE: `packages/weather/src/tradewinds/weather/catalog/awc.py` (~200 LOC).
  - CREATE: `packages/weather/tests/catalog/test_awc.py` (~200 LOC).
  - CREATE: `packages/weather/tests/catalog/fixtures/awc_*.json` (recorded fixtures, post-Sept-2025 endpoint).
- **Action:**
  ```python
  class AWCAdapter:
      SUPPORTED_SOURCES: ClassVar[list[str]] = ["awc.live"]
      # Note: awc.archive intentionally absent in v0.1 (R9 — IEM provides historical depth)
      def fetch_observations(self, source, station, from_date, to_date) -> pd.DataFrame:
          # _fetchers/awc.py → post-Sept-2025 /api/data/ endpoint
          # awc_to_observation per row
          # same canonical projection + overlay as IEMAdapter
  ```
- **Pitfall: AWC `M1/4` visibility prefix** — already handled in `_awc.py:88`; adapter verifies via property test.
- **Codex review priority:** high.
- **Atomic commits (2):**
  1. `feat(CATALOG-02): AWCAdapter.fetch_observations wraps weather._awc (post-Sept-2025 /api/data/)`.
  2. `test(CATALOG-02): AWCAdapter recorded-fixture + visibility-M1/4 sanity test`.
- **Test bar:** recorded-fixture test green; URL constant matches `/api/data/` (LIFT-FIX comment present in `_fetchers/awc.py`).

#### Task 4.3: CLIAdapter (parallel sub-branch — highest complexity)

- **Branch:** `phase-2/wave-4-adapters/cli` off `phase-2/wave-4-adapters`.
- **Files:**
  - CREATE: `packages/weather/src/tradewinds/weather/catalog/cli.py` (~300 LOC — dedup carries weight).
  - CREATE: `packages/weather/tests/catalog/test_cli.py` (~300 LOC).
  - CREATE: `packages/weather/tests/catalog/fixtures/cli_*.txt` (recorded CLI products with prelim + final + correction triple for same date).
  - CREATE: `packages/weather/src/tradewinds/weather/catalog/_cli_station_tz.py` (~50 LOC, 20-station IANA mapping table from RESEARCH.md whitelist).
- **Action:**
  ```python
  class CLIAdapter:
      SUPPORTED_SOURCES: ClassVar[list[str]] = ["cli.archive"]
      def fetch_settlement(self, source, station, from_date, to_date, *, include_revisions: bool = False) -> pd.DataFrame:
          # 1. _fetchers/iem_cli.py downloads CLI products
          # 2. parse_cli_response per product → rows
          # 3. project to schema.settlement.cli.v1 columns
          # 4. add product_release_time from _parse_product_timestamp (already in parser)
          # 5. add station_tz from _cli_station_tz.py mapping (load-bearing per §U)
          # 6. extract cli_data_quality enum via REMARKS regex (Pitfall 6)
          # 7. assign settlement_finality enum (Pitfall 16)
          # 8. apply REPORT_TYPE_PRIORITY dedup on (station, observation_date) unless include_revisions
          # 9. overlay: source, retrieved_at, event_time (00:00 local → UTC), knowledge_time = product_release_time
          # 10. df.attrs["source"] = source
  ```
- **R3 mitigation (lift dedup from `monorepo-v0.14.1/src/mostlyright/pairs.py`):** the `_climate.py` parser ships `REPORT_TYPE_PRIORITY = {final: 3.0, ncei_final: 2.5, correction: 2.0, preliminary: 1.0, estimated: 0.0}` (verified at `_climate.py:21`) with **strict `>` first-seen-wins at equal priority** (verified `_climate.py:55`). Adapter applies: groupby `(station, observation_date)`, take max-priority row, tiebreak on first-seen.
- **Pitfall 6 (`cli_data_quality`):** regex on REMARKS for `(?i)(estimated|substituted|nearby|representative|backup|cooperative)` → enum tag; `None` if no match.
- **Pitfall 5 (DST late-night issuance):** parser's `_parse_product_timestamp` lifted verbatim — adapter ADDS fixture tests for DST-boundary issuances (2024-03-10 02:30 UTC, 2024-11-03 02:30 UTC) to confirm no regression.
- **Codex review priority:** high (R3 lift correctness is parity-critical for Phase 3 migration gate).
- **Atomic commits (4):**
  1. `feat(CATALOG-03): CLIAdapter scaffold + station_tz mapping table`.
  2. `feat(CATALOG-03): lift REPORT_TYPE_PRIORITY dedup from v0.14.1 pairs.py into CLIAdapter`.
  3. `feat(CATALOG-03): cli_data_quality REMARKS regex + settlement_finality assignment`.
  4. `test(CATALOG-03): recorded-fixture prelim+final+correction dedup + DST-boundary + Pitfall 6 tests`.
- **Test bar:**
  - Fixture with prelim + final + correction for same `(KNYC, 2024-12-15)` → dedup returns 1 row (correction wins).
  - `include_revisions=True` returns all 3 rows.
  - DST-boundary fixtures green.
  - `cli_data_quality` correctly extracted for REMARKS containing each of 6 enum values.

#### Task 4.4: GHCNhAdapter (parallel sub-branch)

- **Branch:** `phase-2/wave-4-adapters/ghcnh` off `phase-2/wave-4-adapters`.
- **Files:**
  - CREATE: `packages/weather/src/tradewinds/weather/catalog/ghcnh.py` (~220 LOC).
  - CREATE: `packages/weather/tests/catalog/test_ghcnh.py` (~250 LOC).
  - CREATE: `packages/weather/tests/catalog/fixtures/ghcnh_*.psv` (recorded fixtures).
- **Action:**
  ```python
  class GHCNhAdapter:
      SUPPORTED_SOURCES: ClassVar[list[str]] = ["ghcnh.archive"]
      # v0.1 restriction (Pitfall 19): supported stations limited to 20-station whitelist
      # (post-2015 stable IDs); station_id_history mapping deferred to v0.1.1.
      _SUPPORTED_STATIONS: frozenset[str] = frozenset(["KATL", "KAUS", "KBOS", "KDCA", "KDEN", "KDFW",
                                                        "KHOU", "KLAS", "KLAX", "KMDW", "KMIA", "KMSP",
                                                        "KMSY", "KNYC", "KOKC", "KPHL", "KPHX", "KSAT",
                                                        "KSEA", "KSFO"])

      def fetch_observations(self, source, station, from_date, to_date) -> pd.DataFrame:
          if station not in self._SUPPORTED_STATIONS:
              raise SourceUnavailableError(
                  message=f"GHCNh v0.1 supports {len(self._SUPPORTED_STATIONS)} stations; {station!r} not in whitelist. v0.1.1 will add station_id_history.",
                  source="ghcnh.archive",
              )
          # _fetchers/ghcnh.py → PSV file
          # parse_ghcnh_file per row → list[dict]
          # filter to _ALLOWED_QC = {"0","1","4","5"} (already in parser)
          # canonical projection + overlay
  ```
- **Codex review priority:** medium.
- **Atomic commits (2):**
  1. `feat(CATALOG-04): GHCNhAdapter restricted to 20-station whitelist (v0.1)`.
  2. `test(CATALOG-04): GHCNhAdapter recorded-fixture + unsupported-station error test`.
- **Test bar:** recorded-fixture green; unsupported station raises `SourceUnavailableError` with v0.1.1-hint message.

#### Task 4.5: Wave-merge — populate registry

- **Branch:** merge 4.1-4.4 into `phase-2/wave-4-adapters`.
- **Files:** EDIT `packages/weather/src/tradewinds/weather/catalog/__init__.py`.
- **Action:** Replace empty `_REGISTRY` with real population:
  ```python
  from .iem import IEMAdapter
  from .awc import AWCAdapter
  from .cli import CLIAdapter
  from .ghcnh import GHCNhAdapter

  _REGISTRY = {}
  for cls in (IEMAdapter, AWCAdapter, CLIAdapter, GHCNhAdapter):
      for src in cls.SUPPORTED_SOURCES:
          _REGISTRY[src] = cls
  ```
- **Atomic commit:** `feat(CATALOG-05): populate registry with 4 adapters`.
- **Codex review priority:** medium.
- **Test bar:**
  - `get_adapter("iem.archive")` → `IEMAdapter` instance.
  - `get_adapter("awc.live")` → `AWCAdapter` instance.
  - `get_adapter("cli.archive")` → `CLIAdapter` instance.
  - `get_adapter("ghcnh.archive")` → `GHCNhAdapter` instance.
  - `get_adapter("iem.live")` → `IEMAdapter` instance.
  - `get_adapter("foo.bar")` → raises `SourceUnavailableError`.

### Wave 4 Success Criteria

- [ ] CATALOG-01: IEMAdapter recorded-fixture green; observations leg complete. MOS forecast leg DEFERRED to Phase 3 per Open Q1 resolution — `IEMAdapter.fetch_forecasts()` raises `NotImplementedError("MOS forecasts deferred to Phase 3 …")`. v0.1.0 obs-only scope is sufficient for ROADMAP Phase 2 SC-3.
- [ ] CATALOG-02: AWCAdapter recorded-fixture green; post-Sept-2025 URL verified.
- [ ] CATALOG-03: CLIAdapter recorded-fixture green; dedup correctness verified on prelim+final+correction triple; cli_data_quality + settlement_finality populated.
- [ ] CATALOG-04: GHCNhAdapter recorded-fixture green; 20-station whitelist enforced.
- [ ] CATALOG-05: registry dispatches all 5 source IDs (`iem.archive`, `iem.live`, `awc.live`, `cli.archive`, `ghcnh.archive`).
- [ ] All adapter outputs `validate_dataframe(out, schema_id)` pass.
- [ ] Wave 4 branch merges to `merged-vision`; full test suite green.

</wave>

<wave id="5" name="Kalshi market specs + inter-package wheel pins (PKG-03)">

**Day:** Day 9
**Branch:** `phase-2/wave-5-markets-pkg` off updated `merged-vision`
**Parallelism:** **2 parallel sub-branches** (markets + packaging are independent).
**Estimated effort:** 1 day
**Delivers:** MARKETS-01 (KALSHI_SETTLEMENT_STATIONS), MARKETS-02 (kalshi_nhigh + kalshi_nlow specs), MARKETS-03 (deterministic resolver), PKG-03 (wheel METADATA pins)
**Blocking decision:** operator must confirm A1, A4, A7 (RESEARCH.md Assumptions Log) before this wave starts. Pre-wave checkpoint required.

### Goal

Hard-code `KALSHI_SETTLEMENT_STATIONS` with citations, ship `kalshi_nhigh.resolve()` + `kalshi_nlow.resolve()` deterministic mappers, and enforce inter-package version pins in built wheels via a CI METADATA grep step.

### Dependencies

- Wave 1 (TradewindsError + SourceUnavailableError available).
- Operator confirmation of:
  - **A1:** Kalshi contract ID format `KXHIGH{CITY}` / `KXLOW{CITY}` confirmed across all 20 cities.
  - **A4:** REPORT_TYPE_PRIORITY dedup logic (already verified in Wave 4 Task 4.3).
  - **A7:** 20-station whitelist covers all v0.1-supported Kalshi cities.

### Tasks

#### Task 5.0: Operator-confirmation checkpoint for KALSHI_SETTLEMENT_STATIONS (BLOCKING)

**🚨 BLOCKING: operator input required (codex P3-2 fix).**

- **Purpose:** Wave 5 Task 5.1 hard-codes the 20-row Kalshi ticker → station mapping in `KALSHI_SETTLEMENT_STATIONS`. Wrong mapping = silent settlement data corruption (Pitfall 1). The plan must NOT proceed to 5.1 with placeholder data ("NY=KNYC, Chicago=KMDW, # ... 18 more" is unsafe).
- **Action:** Pause Wave 5 sub-branches until operator provides the canonical 20-row table:
  ```
  | Kalshi ticker      | City           | ICAO station | Kalshi page URL |
  |--------------------|----------------|--------------|------------------|
  | KXHIGHNY           | New York       | KNYC         | https://...      |
  | KXHIGHCHI          | Chicago        | KMDW         | https://...      |
  | ...                | ...            | ...          | ...              |
  | (18 more rows)     |                |              |                  |
  ```
- **What the executor does:** if Task 5.0 unblocked: proceed to 5.1. If blocked at wave start: skip Wave 5 entirely for now, mark CATALOG-04/MARKETS-01/02/03 as "blocked on operator", and continue to Phase 3 planning. Wave 5 can resume out-of-band when operator delivers the table.
- **Acceptance:** operator pastes (or commits to a NEW file `.planning/phase-02-core-primitives-catalog-adapters/kalshi_stations_OPERATOR.md`) the 20-row table with Kalshi page URLs as citations. The Task 5.1 implementation copies from this operator file verbatim.

#### Task 5.1: KALSHI_SETTLEMENT_STATIONS constant + contract specs (parallel sub-branch)

- **Branch:** `phase-2/wave-5-markets-pkg/markets` off `phase-2/wave-5-markets-pkg`.
- **Files:**
  - CREATE: `packages/markets/src/tradewinds/markets/catalog/__init__.py` (~20 LOC).
  - CREATE: `packages/markets/src/tradewinds/markets/catalog/kalshi_stations.py` (~150 LOC for 20-entry constant with citations).
  - CREATE: `packages/markets/src/tradewinds/markets/catalog/kalshi_nhigh.py` (~50 LOC).
  - CREATE: `packages/markets/src/tradewinds/markets/catalog/kalshi_nlow.py` (~50 LOC).
  - CREATE: `packages/markets/tests/catalog/test_kalshi_stations.py` (~100 LOC).
  - CREATE: `packages/markets/tests/catalog/test_kalshi_nhigh.py` (~100 LOC).
  - CREATE: `packages/markets/tests/catalog/test_kalshi_nlow.py` (~100 LOC).
- **Action (kalshi_stations.py):**
  ```python
  """Kalshi NHIGH/NLOW settlement station constants.

  Source whitelist: tests/fixtures/parity/README.md (20 cities, K-prefix CONUS only).
  Citations: per-row Kalshi help page URL (confirmed with operator 2026-05-XX before Phase 2 Wave 5 start).
  """
  KALSHI_SETTLEMENT_STATIONS: dict[str, dict] = {
      "KXHIGHNY":  {"station": "KNYC", "tz": "America/New_York",    "city": "NYC",     "cite": "https://kalshi.com/markets/kxhighny"},
      "KXHIGHCHI": {"station": "KMDW", "tz": "America/Chicago",     "city": "Chicago", "cite": "https://kalshi.com/markets/kxhighchi"},
      # ... 18 more (LA, Miami, Denver, Boston, Austin, Atlanta, DCA, DFW, Houston, Las Vegas, Minneapolis, MSY, OKC, Philadelphia, Phoenix, San Antonio, Seattle, SFO)
  }
  ```
- **Action (kalshi_nhigh.py + kalshi_nlow.py twin):**
  ```python
  from datetime import date
  from tradewinds.core.exceptions import SourceUnavailableError
  from .kalshi_stations import KALSHI_SETTLEMENT_STATIONS

  def resolve(contract_id: str, contract_date: date) -> tuple[str, str]:
      """Map (contract_id, date) → (settlement_source, settlement_station)."""
      if contract_id not in KALSHI_SETTLEMENT_STATIONS:
          raise SourceUnavailableError(
              message=f"Unknown contract {contract_id!r}; v0.1 supports {sorted(KALSHI_SETTLEMENT_STATIONS)}.",
              source=contract_id,
          )
      spec = KALSHI_SETTLEMENT_STATIONS[contract_id]
      return ("cli.archive", spec["station"])
  ```
- **Contract test (MARKETS-02 + CATALOG-05):**
  ```python
  GOOD_STATIONS = {"KNYC","KMDW","KMIA","KAUS","KLAX","KDEN","KBOS","KATL","KDCA","KDFW","KHOU","KLAS","KMSP","KMSY","KOKC","KPHL","KPHX","KSAT","KSEA","KSFO"}
  BAD_STATIONS = {"KLGA","KJFK","KORD","KIAD","KEWR"}

  @pytest.mark.parametrize("ticker", sorted(KALSHI_SETTLEMENT_STATIONS))
  def test_every_ticker_resolves_to_good_station(ticker):
      source, station = kalshi_nhigh.resolve(ticker, date(2024, 12, 15))
      assert source == "cli.archive"
      assert station in GOOD_STATIONS
      assert station not in BAD_STATIONS

  def test_nhigh_and_nlow_produce_identical_resolution():
      for ticker in KALSHI_SETTLEMENT_STATIONS:
          assert kalshi_nhigh.resolve(ticker, date(2024, 12, 15)) == kalshi_nlow.resolve(ticker, date(2024, 12, 15))
  ```
- **Codex review priority:** high (Pitfall 1 — wrong station mapping is parity-breaking + silent data corruption).
- **Atomic commits (3):**
  1. `feat(MARKETS-01): KALSHI_SETTLEMENT_STATIONS constant for 20-station whitelist with citations`.
  2. `feat(MARKETS-02): kalshi_nhigh + kalshi_nlow contract specs with deterministic resolve()`.
  3. `test(MARKETS-02+03): contract tests asserting every ticker resolves to known-good station; never LGA/JFK/ORD`.
- **Test bar:**
  - Every entry in `KALSHI_SETTLEMENT_STATIONS` resolves to a station in `GOOD_STATIONS` set.
  - NO entry resolves to `KLGA`, `KJFK`, `KORD`, `KIAD`, `KEWR` (the forbidden set per PROJECT.md Key Decision + Pitfall 1).
  - `nhigh.resolve()` and `nlow.resolve()` produce identical tuples for every ticker (settlement station does not depend on high-vs-low direction).
  - Unknown ticker raises `SourceUnavailableError` with v0.1-supported-tickers hint.

#### Task 5.2: PKG-03 — inter-package version pins + CI METADATA grep (parallel sub-branch)

- **Branch:** `phase-2/wave-5-markets-pkg/packaging` off `phase-2/wave-5-markets-pkg`.
- **Files:**
  - EDIT: `packages/core/pyproject.toml` (NO sibling dep change; optionally add `[project.optional-dependencies] weather = ["tradewinds-weather>=0.1.0,<0.2"]`).
  - EDIT: `packages/weather/pyproject.toml` — change `dependencies = ["tradewinds"]` → `dependencies = ["tradewinds>=0.1.0,<0.2", "pandas>=2.2,<3.0", "pyarrow>=17.0", "httpx>=0.27"]`.
  - EDIT: `packages/markets/pyproject.toml` — change `dependencies = ["tradewinds"]` → `dependencies = ["tradewinds>=0.1.0,<0.2"]`.
  - CREATE: `.github/workflows/wheel-metadata-check.yml` (~50 LOC) — runs after `uv build --all`, unzips each wheel, greps `METADATA` for `Requires-Dist: tradewinds` with `>=` and `<` constraints, fails build if loose.
  - CREATE: `scripts/check_wheel_metadata.py` (~40 LOC) — local script for pre-publish use.
- **Action (`scripts/check_wheel_metadata.py`):**
  ```python
  """Pre-publish METADATA check: every built wheel must declare explicit version ranges
  for sibling tradewinds-* packages. Fail loudly if missing."""
  import re, sys, zipfile
  from pathlib import Path

  REQUIRED_PINS = {
      "tradewinds_weather": [r"Requires-Dist: tradewinds\s*\(?\s*>=\s*0\.1\.0\s*,\s*<\s*0\.2"],
      "tradewinds_markets": [r"Requires-Dist: tradewinds\s*\(?\s*>=\s*0\.1\.0\s*,\s*<\s*0\.2"],
  }

  def check_wheel(wheel_path: Path) -> list[str]:
      errors = []
      pkg_name = wheel_path.name.split("-")[0]
      with zipfile.ZipFile(wheel_path) as z:
          metadata = next(name for name in z.namelist() if name.endswith("METADATA"))
          content = z.read(metadata).decode()
      for pattern in REQUIRED_PINS.get(pkg_name, []):
          if not re.search(pattern, content):
              errors.append(f"{wheel_path.name}: missing pin matching /{pattern}/")
      return errors

  if __name__ == "__main__":
      all_errors = []
      for wheel in Path("dist").glob("*.whl"):
          all_errors.extend(check_wheel(wheel))
      if all_errors:
          for e in all_errors:
              print(f"ERROR: {e}", file=sys.stderr)
          sys.exit(1)
  ```
- **Action (`.github/workflows/wheel-metadata-check.yml`):** runs on every push that touches `packages/*/pyproject.toml`; steps: `uv build --all` → `python scripts/check_wheel_metadata.py`.
- **Codex review priority:** medium (CI infra; correctness matters but not blast-radius-load-bearing).
- **Atomic commits (3):**
  1. `chore(PKG-03): pin tradewinds>=0.1.0,<0.2 in weather + markets pyproject.toml`.
  2. `chore(PKG-03): scripts/check_wheel_metadata.py for pre-publish METADATA grep`.
  3. `ci(PKG-03): wheel-metadata-check workflow runs check on every relevant push`.
- **Test bar:**
  - `uv build --all` produces 3 wheels: `tradewinds-0.1.0a2-*.whl`, `tradewinds_weather-0.1.0a2-*.whl`, `tradewinds_markets-0.1.0a2-*.whl` (alpha bump from a1; final a2 versioning at planner discretion).
  - `python scripts/check_wheel_metadata.py` exits 0 with all 3 wheels present.
  - Negative test: temporarily remove the version pin from `packages/weather/pyproject.toml` → rerun `uv build --all` + script → script exits 1 with descriptive error. Revert immediately.

### Wave 5 Success Criteria

- [ ] MARKETS-01: `KALSHI_SETTLEMENT_STATIONS` populated with 20 entries; all citations present; contract test asserts no entry maps to forbidden station set.
- [ ] MARKETS-02: `kalshi_nhigh.resolve()` and `kalshi_nlow.resolve()` deterministic for every supported ticker.
- [ ] MARKETS-03: tuple shape `(settlement_source, settlement_station)` preserved (forward-compat for non-CLI sources).
- [ ] PKG-03: `uv build --all` produces 3 wheels with explicit `Requires-Dist: tradewinds>=0.1.0,<0.2` in weather + markets METADATA; CI workflow blocks builds missing the pin.
- [ ] Wave 5 branch merges to `merged-vision`; full test suite green.

</wave>

<cross_cutting_concerns>

### 1. `_v02/` → `tradewinds.core` migration tactic (Decision 1 / RESEARCH.md)

**Decided:** Option (A) git-mv + sed (NOT rebuild, NOT wrap).
**Why:** preserves git history per-file; 266 tests stay green through atomic rename; single commit makes diff legible to codex review.
**Mitigation for R1:** Wave 1 Task 1.2 includes the `grep -r _v02 packages/core/` zero-result audit AND a full test suite run before commit.
**Anti-pattern guard:** do NOT keep `_v02/` as a re-export shim. After Wave 1 Task 1.3 deletes `_v02/__init__.py`, any code importing `tradewinds._v02` errors loudly.

### 2. Exception rename `MostlyRightMCPError` → `TradewindsError` + alias shim (Decision 6)

**Decided:** rename canonical class; keep `MostlyRightMCPError = TradewindsError` as a module-level alias with `DeprecationWarning` emitted once per session.
**Lifetime:** alias present in v0.1 and v0.2; removed in v0.3 (per RESEARCH.md).
**TherminalError reconciliation:** `_internal/exceptions.py:TherminalError` now subclasses `TradewindsError`. User code catching `TradewindsError` catches HTTP errors too. Phase 1 fetcher tests unchanged.
**Caller-facing impact for MIGRATION-02 (Phase 3):** `from tradewinds import MostlyRightMCPError as TherminalError` works because both are aliases of the same base.

### 3. Validator engine — jsonschema (Decision 2 / RESEARCH.md)

**Decided:** jsonschema (default, ≤250 LOC), confirmed via Wave 1 Task 1.0 spike.
**Why reject pandera:** heavy dep (numpy 2.x conflict surface), slow cold first-import (>500ms typical), overkill for v0.1 (pandas-only), and `_v02/schema.py` ColumnSpec.dtype canonical strings dispatch more naturally to manual checks + jsonschema enum than to pandera schemas.
**Recorded in:** `DECISIONS.md` (created Wave 1 Task 1.0).
**Fallback if Day-5 spike disproves:** pivot Wave 3 to pandera — adds ~1 day to Phase 2 (Wave 3 slips to Day 8 morning; Wave 4 starts Day 8 afternoon with 3-lane parallel instead of 4-lane). Document slip in STATE.md.

### 4. Parser location — KEEP at `tradewinds.weather._{awc,iem,climate,ghcnh}.py` (Decision 4 / RESEARCH.md)

**Decided:** do NOT rename to `_vendor/`.
**Why:** Phase 1 is shipped on `merged-vision` with current paths; renaming touches every adapter import and yields no functional benefit. The underscore prefix already signals "internal/not-public-API". Provenance documentation lives in `packages/weather/src/tradewinds/weather/__init__.py` docstring (currently partial — Wave 1 expands to match CATALOG-06).
**Phase 1 CATALOG-06 obligation:** the existing `tradewinds.weather.__init__.py` docstring already documents lift inventory per-module; verify completeness during Wave 4 Task 4.0 codex review.
**If naming clarification later desired:** ship as a Phase 3+ tiny separate task; do NOT block Phase 2.

### 5. Branch + review discipline

- Every wave gets its own branch off `merged-vision`.
- Within a wave, parallel tasks get sub-branches off the wave branch.
- Each sub-branch goes through codex review at the priority noted per task (`high` for parity-critical lifts and source-identity invariants; `medium` for new code; `low` for wiring/exports).
- No direct commits to `merged-vision`; wave branch merges to `merged-vision` only after full test suite (`pytest packages/`) passes.
- No `--no-verify` on commits — pre-commit hooks (`ruff check --fix` + `ruff format`) must run.

### 6. Test bar (design §H + ROADMAP success criteria)

- **Wave 1:** 266 pre-existing `_v02/` tests stay green at 100% pass count. Schema additions (`cli_data_quality`, `settlement_finality`) add new contract-test assertions.
- **Wave 2:** ≥90% branch coverage on `knowledge_view.py` + `leakage.py`; Hypothesis property tests with constrained datetime range per CORE-08 (NON-NEGOTIABLE).
- **Wave 3:** ≥90% branch coverage on `validator.py`; design §H negative-test matrix (source mismatch, source_attr_required, dtype mismatch, enum violation, mixed nulls) all green.
- **Wave 4:** Each adapter has recorded-fixture tests using Phase 1 `tests/fixtures/parity/` fixtures; Validator integration test on each adapter output.
- **Wave 5:** Contract tests for every Kalshi ticker → known-good station. Wheel METADATA grep CI step green.

</cross_cutting_concerns>

<open_questions_and_blocking_decisions>

### Open Q1 — IEM MOS forecast parser location — RESOLVED (2026-05-21)

- **State: RESOLVED.** Plan-checker verified on 2026-05-21 via `find packages/weather/ -iname "*forecast*"` — no `_forecast_parse.py` lifted in Phase 1; MOS forecast parser is ABSENT in tradewinds. The source-of-truth at `monorepo-v0.14.1/src/mostlyright/_forecast_parse.py` exists and is liftable but not lifted yet.
- **Resolution: DEFER to Phase 3.** v0.1.0 CATALOG-01 scope reduced to observations-only. `IEMAdapter.fetch_forecasts()` raises `NotImplementedError("MOS forecasts deferred to Phase 3 — see Open Q1 resolution in Phase 2 PLAN.md")`. ROADMAP Phase 2 SC-3 ("wrap `_vendor/` parsers" + "recorded-fixture tests green") does NOT explicitly require the forecast leg, so the deferral is consistent with the phase goal.
- **Phase 3 follow-up:** Phase 3 PLAN will lift `_forecast_parse.py` from `monorepo-v0.14.1` and add `IEMAdapter.fetch_forecasts()` as part of the Mode-2 integration work. No timeline impact on Phase 2 (no Wave 4.5 added; phase stays 5 days).
- **Wave 4.5 status:** REMOVED. The plan does not introduce a Wave 4.5; Wave 5 follows Wave 4 directly.

### Open Q2 — Operator must confirm before Wave 5 start

- **A1 (Kalshi contract ID format `KXHIGH{CITY}` across 20 cities):** operator provides the canonical 20-row mapping (ticker → city → station + Kalshi page URL). Without this, Wave 5 Task 5.1 cannot fill `KALSHI_SETTLEMENT_STATIONS` correctly. Pitfall 1 risk: silent data corruption if mapping is wrong.
- **A4 (REPORT_TYPE_PRIORITY dedup logic location):** already verified inline (`_climate.py:21`) — no operator confirmation needed; A4 marked VERIFIED.
- **A7 (20-station whitelist covers all v0.1 cities):** operator confirms no Kalshi cities exist outside the 20-station whitelist for v0.1. If exceptions exist, those tickers are flagged "v0.1.1+" and excluded from `KALSHI_SETTLEMENT_STATIONS`.
- **Checkpoint:** Day 8 evening (end of Wave 4) — present operator with the table to confirm before Wave 5 starts Day 9.

### Open Q3 — Pandera spike could disprove jsonschema default

- **Trigger:** Wave 1 Task 1.0 spike (Day 5 09:00-11:00) shows pandera reduces Validator LOC by >30% AND first-import time <500ms.
- **Decision rule:** if both conditions met → pivot Wave 3 to pandera (adds ~1 day to Phase 2).
- **Default if spike inconclusive:** jsonschema (R7 mitigation).

</open_questions_and_blocking_decisions>

<goal_backward_verification>

Each Phase 2 ROADMAP success criterion (5 criteria total per ROADMAP §"Phase 2 Success Criteria") mapped to wave + task that achieves it:

| ROADMAP SC | Achieved by Wave + Task | Verification |
|------------|--------------------------|--------------|
| **SC-1:** `tradewinds.core.temporal.KnowledgeView` filters DataFrames by `knowledge_time <= as_of` as a plain wrapper class with `__slots__` (not accessor, not subclass); Hypothesis property tests pass with `[2018-01-01, 2027-12-31]` UTC range | **Wave 2 Task 2.1** (KnowledgeView impl) + **Wave 2 Task 2.3** (export); CORE-07 acceptance test `test_knowledgeview_no_accessor.py`; CORE-08 constrained datetime range in property tests | `from tradewinds.core import KnowledgeView; assert KnowledgeView.__slots__ == ("_df", "_as_of")` + property tests green |
| **SC-2:** Three canonical schemas registered eagerly via `tradewinds.core.schemas/__init__.py`; `validate_dataframe(df, schema_id)` enforces source-identity invariant and raises `SourceMismatchError` with both train/infer source names | **Wave 1 Task 1.1** (schemas moved verbatim) + **Wave 3 Task 3.1** (Validator + source-identity) + **Wave 3 Task 3.2** (negative-test matrix) | `validate_dataframe(iem_df, "schema.observation.v1")` with mismatched `df.attrs["source"]` raises `SourceMismatchError(schema_source=..., data_source=...)` |
| **SC-3:** All four catalog adapters (`iem`, `awc`, `cli`, `ghcnh`) wrap `_vendor/` parsers, declare `SUPPORTED_SOURCES: list[str]`, emit canonical schema rows with `event_time`/`knowledge_time`/`source`/`retrieved_at` stamping; eager-import registry dispatches by source ID; recorded-fixture tests green | **Wave 4 Tasks 4.1-4.4** (adapters) + **Wave 4 Task 4.0+4.5** (registry scaffold + populate) | `get_adapter("iem.archive").fetch_observations(...)` returns canonical-schema DataFrame with 4 overlay columns; recorded-fixture roundtrip green |
| **SC-4:** `KALSHI_SETTLEMENT_STATIONS` hard-coded with citations (NYC=KNYC, Chicago=KMDW, NOT LGA/JFK/ORD); `kalshi_nhigh` and `kalshi_nlow` map `(contract_id, date) → (settlement_source, settlement_station)` deterministically | **Wave 5 Task 5.1** (markets impl) — contract test asserts no entry resolves to `{KLGA, KJFK, KORD, KIAD, KEWR}` | `kalshi_nhigh.resolve("KXHIGHNY", date(2024,12,15))` → `("cli.archive", "KNYC")`; parametrize test over all 20 tickers |
| **SC-5:** `TradewindsError` exception hierarchy with `to_dict()` for v0.2 MCP JSON-RPC serialization; format serializers (`dataframe`, `json`, `parquet`, `toon`, `csv`) pass roundtrip tests preserving dtypes; pandera-vs-jsonschema decision documented | **Wave 1 Tasks 1.1+1.2** (exceptions + format mv) + **Wave 1 Task 1.0** (D-02 decision doc) — format roundtrip test inherited from `_v02/test_formats.py` (760 LOC) | `TradewindsError().to_dict()` returns JSON-safe dict per design §D; `dumps→loads` roundtrip preserves dtypes; `DECISIONS.md` records D-02 |

**Cross-check — every requirement ID maps to at least one wave/task:**

| Req ID | Wave | Task |
|--------|------|------|
| CORE-01 | 2 | 2.1, 2.2 |
| CORE-02 | 3 | 3.1, 3.2 |
| CORE-03 | 1 | 1.1 (schemas moved), 1.4 (cli additions) |
| CORE-04 | 1 | 1.2 (rename + alias) |
| CORE-05 | 1 | 1.1 (formats moved verbatim) |
| CORE-07 | 2 | 2.1 (no_accessor test) |
| CORE-08 | 2 | 2.1, 2.2 (constrained datetimes) |
| CATALOG-01 | 4 | 4.1 |
| CATALOG-02 | 4 | 4.2 |
| CATALOG-03 | 4 | 4.3 |
| CATALOG-04 | 4 | 4.4 |
| CATALOG-05 | 4 | 4.0, 4.5 (scaffold + populate) |
| MARKETS-01 | 5 | 5.1 |
| MARKETS-02 | 5 | 5.1 |
| MARKETS-03 | 5 | 5.1 |
| PKG-03 | 5 | 5.2 |

All 16 requirements assigned. No orphans.

</goal_backward_verification>

<verification>

**Continuous verification (every wave merge):**

1. `pytest packages/` — full test suite green.
2. `ruff check packages/` — no lint errors.
3. `ruff format --check packages/` — no format drift.
4. `grep -r MostlyRightMCPError packages/core/src/` returns only the alias declaration line.
5. `grep -r _v02 packages/core/` returns empty (after Wave 1).

**Phase 2 ship gate (end of Wave 5):**

1. All 16 requirements green (per goal_backward_verification table).
2. All 5 ROADMAP §"Phase 2 Success Criteria" green.
3. `uv build --all` produces 3 wheels with correct METADATA pins.
4. Full test suite green: `pytest packages/ -m "not live"` exits 0.
5. Branch coverage report: `tradewinds.core.*` ≥90% (HARD GATE deferred to Phase 4, but Phase 2 should be tracking ≥90% to leave Phase 4 headroom).
6. `DECISIONS.md` records D-02 (Validator engine).
7. Operator-confirmed A1 / A7 entries in RESEARCH.md flipped to VERIFIED.

</verification>

<success_criteria>

Phase 2 is complete when:

- All 16 phase requirements (CORE-01..05, CORE-07, CORE-08, CATALOG-01..05, MARKETS-01..03, PKG-03) are marked `[x]` in REQUIREMENTS.md.
- `merged-vision` branch contains all 5 wave merges.
- `tradewinds.core`, `tradewinds.weather.catalog`, `tradewinds.markets.catalog` are importable and tested.
- 266+ `_v02/`-origin tests + new Wave 2/3/4/5 tests all pass.
- Phase 3 can start Day 10 morning with the architectural spine in place.

</success_criteria>

<output>

Wave-merge SUMMARY files will be created per wave at `.planning/phase-02-core-primitives-catalog-adapters/SUMMARY-wave-{N}.md` documenting:
- Files created/modified
- Atomic commits made
- Codex review outcomes (per sub-branch)
- Open questions resolved (e.g., Open Q1 outcome at Wave 4)
- Test counts before/after

Phase-level SUMMARY at `.planning/phase-02-core-primitives-catalog-adapters/SUMMARY.md` after Wave 5 merge, covering:
- Total LOC added/moved (target: ~3,500 LOC moved from `_v02/` + ~2,500 LOC new for KnowledgeView/LeakageDetector/Validator/adapters/Kalshi)
- Total test count (target: 266 retained + ~250 new)
- Branch coverage on `tradewinds.core.*`
- Decisions recorded in DECISIONS.md
- Assumptions verified (A1, A4, A7)
- Phase 3 prerequisites green-light status

</output>

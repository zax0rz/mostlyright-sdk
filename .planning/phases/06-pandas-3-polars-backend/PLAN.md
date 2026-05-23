# Phase 6 PLAN — Pandas 3 Readiness + Optional Polars Backend

**Phase**: 6
**Milestone**: Python v0.2+
**Status**: Planned (2026-05-23) — PLANNING ONLY
**Depends on**: Phase 4 (CI/CD trusted publishing) — re-runs the parity gate against pandas 3 fixtures
**Independent of**: Phase 5 (MCP) — backend choice is orthogonal to MCP server
**Requirements**: PANDAS3-01..PANDAS3-06 + POLARS-01..POLARS-08 (14 IDs)
**Documents**: see [CONTEXT.md](CONTEXT.md) for user decisions + scope; [RESEARCH.md](RESEARCH.md) for the recon agent's pandas-usage audit driving every wave.

## Goal

Ship two paired tracks of data-layer infrastructure that unblock backend choice for downstream consumers:

1. **PANDAS3** — drop the `pandas<3.0` cap (locked by Phase 1 parity gate), audit + remediate 6 datetime/dtype risk sites, re-capture the 5 parity fixtures against pandas 3.x, so byte-equivalence holds on both 2.x and 3.x lockfiles via a dual-pandas CI matrix.

2. **POLARS** — opt-in `backend="polars"` kwarg on every public DataFrame-returning entry point. Narwhals-mediated internal data layer for 5 cleanly-portable modules. Pandas stays canonical for the 7 parity-locked modules. `TradewindsResult` thin wrapper carries provenance separately so both backends preserve source-identity invariants without `.attrs` writes that Polars cannot represent.

## Success Criteria (Goal-Level)

These mirror ROADMAP § "Phase 6" verbatim — verifier checks them post-execution:

1. **Pandas 3 dual-lock parity:** the 5 Phase 1 parity fixtures pass byte-equivalent under BOTH `pandas==2.2.x` AND `pandas>=3.0,<4.0`. CI matrix runs both. `pandas<3.0` cap dropped in all 6 affected extras; new floor `pandas>=2.2,<4.0`. Fixture re-capture documented in `tests/fixtures/parity/README.md` with both-pandas SHAs side-by-side.

2. **Opt-in polars backend:** `backend: Literal["pandas","polars"]="pandas"` kwarg on `research()`, `research_by_source()`, `polymarket_discover()`, `forecast_nwp()`, `daily_extremes()`. Default stays pandas. With `backend="polars"`, every adapter returns a Polars DataFrame; row contents equivalent to pandas (verified by `polars_df.to_pandas().equals(pandas_df)` on the 5 parity fixtures); provenance lives on the wrapping `TradewindsResult`.

3. **`TradewindsResult` provenance wrapper:** new dataclass at `tradewinds.core.result.TradewindsResult` carries `frame` (pd.DataFrame | pl.DataFrame), `source` (str), `retrieved_at` (datetime), `schema_id` (str | None), `qc` (dict | None), `data_version` (DataVersion | None). Backend-aware paths return `TradewindsResult`; legacy DataFrame-direct return kept under a deprecation shim for one release cycle. Validator + KnowledgeView + LeakageDetector accept `TradewindsResult` and unwrap.

4. **Narwhals internal data layer:** the 5 cleanly-portable modules (`transforms.py`, `preprocessing.py`, `qc.crosscheck_iem_ghcnh`, `core/temporal/knowledge_view.py`, `core/formats/{json,csv,toon}.py`) are refactored to narwhals primitives. Per-backend test matrix verifies identical output. Parity-locked modules stay pandas-only.

5. **Optional extras:** `[polars]` extra on all three packages adds `polars>=1.0,<2.0` + `narwhals>=1.20,<2.0`. Default install never pulls polars. Calling polars without the extra raises `SourceUnavailableError` with install hint. CI matrix runs cross-backend tests gated on the extra.

## Wave Structure

Five waves, strictly serial within the phase (Wave N+1 depends on Wave N's surface). Each wave has its own success criteria + verification gate.

```
W0: TradewindsResult wrapper (foundation)
  ↓
W1: PANDAS3 track (independent of W2-W5; can run in parallel post-W0)
  ↓
W2: POLARS track A — narwhals migration of the 5 portable modules
  ↓
W3: POLARS track B — backend="polars" kwarg on 5 public entry points + [polars] extra
  ↓
W4: POLARS track C — parity invariant + sort-stability tests
  ↓
W5: POLARS track D — CI matrix gates + @pytest.mark.polars marker discipline
```

**Parallelism note:** W1 (pandas 3) and W2-W5 (polars) are mostly independent. The strict serial dependency is W0 → W1 and W0 → W2 → W3 → W4 → W5. W1 can run in parallel with W2-W5 after W0 lands (Lane A: pandas 3 audit + remediation + matrix; Lane B: polars wrapper + narwhals + public surface + tests). Estimate: ~12-16 days single-lane; ~8-11 days with 2 lanes.

---

## Wave 0 — `TradewindsResult` wrapper (foundation)

**Goal:** Land the backend-neutral provenance container that every subsequent wave depends on. Validator + KnowledgeView + LeakageDetector accept `TradewindsResult` as input and unwrap; legacy DataFrame-direct return preserved via shim.

**Tasks:**

- **W0-T1**: Create `tradewinds.core.result.TradewindsResult` dataclass at `packages/core/src/tradewinds/core/result.py`. Fields: `frame: pd.DataFrame | pl.DataFrame` (Polars type via `TYPE_CHECKING` import so default install doesn't require polars), `source: str`, `retrieved_at: datetime` (tz-aware), `schema_id: str | None`, `qc: dict | None`, `data_version: DataVersion | None`. Frozen dataclass. `__post_init__` validates `retrieved_at` is tz-aware (raises `ValueError` if naive — matches existing `schema.py:_require_tz_aware` discipline). `to_dict()` for v0.2 MCP JSON-RPC serialization.

- **W0-T2**: Method `result.legacy_df_with_attrs() → pd.DataFrame` — returns the underlying pandas DataFrame with `df.attrs` populated from the wrapper's provenance fields, for callers that still depend on the v0.1.0 `df.attrs`-stamped shape. Raises `TypeError` if `frame` is Polars (the legacy shape was pandas-only by definition).

- **W0-T3**: `TradewindsResult.frame_as_pandas() → pd.DataFrame` — if `frame` is already pandas, return as-is; if Polars, call `.to_pandas()`. Used by parity-locked modules (W4) when they need a pandas frame regardless of caller's backend choice.

- **W0-T4**: Update `tradewinds.core.validator.validate_dataframe(df_or_result, schema_id, ...)` to accept `TradewindsResult` as the first arg. Unwrap via `result.frame_as_pandas()` then proceed with existing logic. Add tests: `validate_dataframe(TradewindsResult(...))` works identically to `validate_dataframe(df)` for both pandas + polars backends.

- **W0-T5**: Update `tradewinds.core.temporal.knowledge_view.KnowledgeView` to accept `TradewindsResult` in its constructor. Unwrap to pandas if needed; subsequent operations stay pandas (the parity-locked validator dispatch requires it).

- **W0-T6**: Update `tradewinds.core.temporal.leakage.LeakageDetector` (same pattern). Tests: existing leakage tests pass with `TradewindsResult`-wrapped input.

- **W0-T7**: Tests. New `packages/core/tests/test_result.py`. Cover: dataclass field validation, naive-datetime rejection, `legacy_df_with_attrs()` mirroring v0.1.0 attrs shape, `frame_as_pandas()` round-trip for both backends (use a pandas-only stub for the polars path so this wave doesn't depend on polars install).

**Wave 0 Success Criteria:**

- `TradewindsResult` importable from `tradewinds.core.result`; no polars import required.
- Validator + KV + LeakageDetector accept `TradewindsResult` AND legacy DataFrames.
- `result.legacy_df_with_attrs()` returns a DataFrame byte-identical to what v0.1.0 adapters set today (the 5 attrs-stamping sites in RESEARCH §4 produce identical output through the legacy path).
- All 1662 existing v0.1.0 tests still pass (no regression).

**Wave 0 Verification:**
- Codex review + python-architect against the wrapper design (focus: validator dispatch correctness, dataclass immutability, `to_dict()` JSON-safety).
- Tests pass on the default pandas install.

---

## Wave 1 — PANDAS3 Track (independent of W2-W5 after W0)

**Goal:** Drop the `pandas<3.0` cap, audit + remediate the 6 risk sites the recon found, re-capture parity fixtures against pandas 3.x, dual-pandas CI matrix passes both.

**Tasks:**

- **W1-T1**: PANDAS3-01 — datetime/dtype risk-site remediation. Per RESEARCH §2, the WARN sites are:
  - `validator.py:84,100,119-121,150` — `s.dtype == "object"` fallback path branching. Refactor to use `pd.api.types.is_object_dtype(s)` (works on both 2.x + 3.x) plus an explicit string-detection arm for the pandas 3.x PyArrow-backed string dtype. Add tests with `pd.Series([], dtype="string")` AND `pd.Series([], dtype="object")` inputs.
  - `cli.py:158,216` — `pd.Series([], dtype="datetime64[ns, UTC]")` literal. Wrap in a helper `_empty_utc_series()` that picks `[ns, UTC]` on pandas 2.x and `[us, UTC]` on pandas 3.x via `pd.__version__` check. Doc the rationale in the helper docstring (citing pandas 3.0 whatsnew).
  - `_pairs.py:397`, `transforms.py:89`, `cli.py:149-151,225`, `_obs_projection.py:172`, `forecast_nwp.py` (3 sites) — `to_datetime` calls. Audit each: if input is timezone-aware ISO string, `utc=True` is already specified (stable across versions); if naive string parsed for date-only, add explicit `format=` to lock parsing semantics under 3.x. Document any byte-equivalence concerns inline.
  - Each remediated site lands a `# PANDAS3` comment with the whatsnew section number.

- **W1-T2**: PANDAS3-05 — CoW audit. Grep every `.copy()`, `.loc[...] =`, `[col] = value` site. Hot list:
  - `core/merge.py:silver_df.copy()` — already explicit copy; CoW-safe.
  - `mode2.py:obs_df = obs_df.copy()` (research path L985) — already explicit copy.
  - `validator.py` reads only; no chained writes per recon.
  - For each surviving `.loc[...] =`/`.iloc[...] =` write, confirm the LHS is a fresh DataFrame, not a view. Add an explicit `.copy()` if ambiguous.

- **W1-T3**: PANDAS3-02 — Drop the `pandas<3.0` cap in all 6 extras:
  - `packages/core/pyproject.toml:37-40` (`[parquet]`)
  - `packages/core/pyproject.toml:48-52` (`[research]`)
  - `packages/weather/pyproject.toml:42-44` (`[parquet]`)
  - `packages/weather/pyproject.toml:53-58` (`[nwp]`)
  - `packages/markets/pyproject.toml:31-34` (`[parquet]`)
  - `packages/markets/pyproject.toml:41-44` (`[polymarket]`)
  - New pin: `pandas>=2.2,<4.0`. CHANGELOG entry under `## [Unreleased]` documents the move + breaks-bytes warning.

- **W1-T4**: PANDAS3-03 — dual-pandas CI matrix. Extend `.github/workflows/test.yml` matrix:
  - `strategy.matrix.pandas-resolution: [lowest, highest]`
  - `lowest`: `uv sync --resolution lowest-direct` → pulls pandas 2.2.x.
  - `highest`: `uv sync --resolution highest` → pulls latest pandas 3.x.
  - `pytest -m "not live"` runs on both. Failure on either side blocks merge.
  - Run on a single Python version (3.13) initially to cap CI cost; expand to full Python matrix when 3.x bytes stabilize.

- **W1-T5**: PANDAS3-04 — re-capture parity fixtures against pandas 3.x. Path: `tests/fixtures/parity/pandas3/case_*.parquet`. Capture script: `tests/fixtures/parity/capture.py` extended with a `--pandas-version` flag. `tests/fixtures/parity/README.md` documents both-version SHAs side-by-side. Parity test (`tests/test_parity.py`) selects fixture set based on `pd.__version__.startswith("3.")`.

- **W1-T6**: PANDAS3-06 — doctest updates. Audit doctest examples in:
  - `validator.py:209-217` — output may differ between pandas 2.x/3.x for string dtype display. Either update expected output to be pandas-3-clean OR add `# doctest: +SKIP` with a note pointing to the dual-pandas test that covers the same case.
  - `knowledge_view.py:46-58`, `leakage.py:54-73` — same pattern.
  - `pytest --doctest-modules` passes on both pandas lockfiles.

**Wave 1 Success Criteria:**

- All 6 affected extras allow pandas 3.x. CI matrix runs both 2.2.x AND 3.x lockfiles; both pass `pytest -m "not live"` clean.
- The 5 parity fixtures pass byte-equivalent under both pandas versions (verified by the test that picks fixture set per pandas major version).
- Doctests pass on both lockfiles.
- No regression on the 1662 v0.1.0 tests.

**Wave 1 Verification:**
- Codex + python-architect: focus on CoW audit completeness + datetime resolution shift impact on parity fixtures.
- Manual: read CHANGELOG entry; review the new fixture README's both-SHA documentation.

---

## Wave 2 — POLARS Track A: Narwhals migration of cleanly-portable modules

**Goal:** Refactor the 5 modules RESEARCH §6 flagged as "cleanly narwhals-ifiable" to use narwhals primitives. Per-backend test matrix verifies identical output on both pandas + polars inputs.

**Order matters** — start with the lowest blast-radius module so any narwhals-API surprises surface early without touching critical paths:

**Tasks:**

- **W2-T1**: POLARS-03 — narwhals scaffolding. Install `narwhals>=1.20,<2.0` as a dev dep first (full extra wiring lands in W3). Create `tradewinds.core._narwhals_compat` shim module documenting the project's narwhals usage patterns: `nw.from_native(df_or_polars) → ops → nw.to_native(result, strict=True)`.

- **W2-T2**: Migrate `tradewinds.transforms.{lag, diff, diff2, rolling, calendar_features, spread, clip_outliers}` to narwhals. `wind_chill` and `heat_index` are scalar functions — no migration needed. New tests parametrize over `[pandas, polars]` input and assert identical output via `polars_out.to_pandas().equals(pandas_out)`. The existing Hypothesis property test for `calendar_features` sin²+cos²=1 invariant covers both backends.

- **W2-T3**: Migrate `tradewinds.preprocessing.{clip_outliers, iem_crosscheck}` to narwhals. `clip_outliers` is mostly column arithmetic; `iem_crosscheck` is a `.merge` + filter — both have narwhals equivalents. Per-backend test parametrization.

- **W2-T4**: Migrate `tradewinds.qc.crosscheck_iem_ghcnh` (the standalone variant, NOT the bitfield engine — that one stays pandas because it reads `obs_qc_status` from cache). `.merge` is straightforward; the `.loc[]` filter post-merge is the only friction (narwhals doesn't expose `.loc[]`; rewrite as a boolean-mask `.filter()`).

- **W2-T5**: Migrate `tradewinds.core.temporal.knowledge_view.KnowledgeView`. Recon §3 said the surface is small: `pd.api.types.is_datetime64_any_dtype(col)`, `col.dt.tz`, `df.loc[mask].copy()`. All three have narwhals equivalents. KV operations stay backend-aware; the wrapped frame keeps its native type.

- **W2-T6**: Migrate `tradewinds.core.formats.{json, csv, toon}` to narwhals row iteration. The `_toon` lift is byte-pinned per CLAUDE.md — DO NOT refactor that one; just wrap the entry point so polars input gets converted to pandas before hitting the lifted body. `json.py` and `csv.py` are net-new and safer to narwhals-ify.

- **W2-T7**: Module-by-module per-backend tests. `packages/core/tests/test_transforms_polars.py`, `test_preprocessing_polars.py`, `test_qc_polars.py`, `test_knowledge_view_polars.py`, `test_formats_polars.py`. Each file uses `@pytest.mark.polars` + `pytest.importorskip("polars")` so pandas-only environments skip cleanly. Output asserted via `polars_result.to_pandas().equals(pandas_result)` for each test case.

**Wave 2 Success Criteria:**

- 5 modules accept pandas OR polars input via narwhals; per-backend test matrix passes both.
- Sort-stability invariant verified for any module that calls `sort_values`/`sort`: identical row ordering across backends.
- No parity regression (the parity gate's 5 fixtures still pass because parity-locked modules weren't touched).
- 1662 → ~1700+ tests passing.

**Wave 2 Verification:**
- Codex + python-architect: focus on whether narwhals actually preserves the operations' semantics (especially `merge`, `sort`, dtype dispatch) across backends.
- Run the dual-pandas matrix from W1 + cross-backend matrix; both must be green.

---

## Wave 3 — POLARS Track B: `backend="polars"` kwarg on public surfaces + `[polars]` extra

**Goal:** Land the user-facing `backend` kwarg on the 5 public entry points; ship the `[polars]` optional extra; gate polars calls behind `SourceUnavailableError` when extra absent.

**Tasks:**

- **W3-T1**: POLARS-05 — `[polars]` optional extra on all three packages:
  - `tradewinds[polars]` → `polars>=1.0,<2.0` + `narwhals>=1.20,<2.0`.
  - `tradewinds-weather[polars]` → same.
  - `tradewinds-markets[polars]` → same.
  - `tradewinds.core._polars_compat` lazy-import helper raises `SourceUnavailableError("...install with: pip install tradewinds[polars]")` on miss. Mirrors the `[nwp]` pattern in `tradewinds.weather.forecast_nwp`.

- **W3-T2**: POLARS-01 — `backend: Literal["pandas","polars"]="pandas"` kwarg on:
  - `tradewinds.research()` (`packages/core/src/tradewinds/research.py:916`)
  - `tradewinds.mode2.research_by_source()` (`packages/core/src/tradewinds/mode2.py:42`)
  - `tradewinds.markets.polymarket.polymarket_discover()` (`packages/markets/src/tradewinds/markets/polymarket.py:347`)
  - `tradewinds.forecasts.forecast_nwp()` (`packages/core/src/tradewinds/forecasts.py:54`) — re-export to the weather impl
  - `tradewinds.international.daily_extremes()` — return type changes from `list[dict]` to `TradewindsResult` (frame is pandas or polars per kwarg). Document as a v0.2 breaking-ish change in CHANGELOG (callers using indexed access still work via `result.frame_as_pandas().to_dict(orient="records")`).

  For each entry point: validate `backend` kwarg, call the underlying pandas path, then if `backend=="polars"` convert the final DataFrame to polars via `pl.from_pandas(df)`. The conversion is at the public surface boundary, not deep in the pipeline (parity-locked modules stay pandas-only per W4).

- **W3-T3**: POLARS-02 — all 5 entry points return `TradewindsResult` (from W0). The frame is the requested backend; provenance is on the wrapper. Legacy DataFrame-direct return preserved under a `return_type: Literal["wrapper","dataframe"]="wrapper"` kwarg (default `"wrapper"` — v0.2 breaking-ish; documented in CHANGELOG with migration recipe). `return_type="dataframe"` returns `result.legacy_df_with_attrs()` for v0.1.0-shape callers.

- **W3-T4**: Install-hint tests. For each entry point, a `@pytest.mark.skipif(_HAS_POLARS, ...)` test asserts that `backend="polars"` without the extra raises `SourceUnavailableError` with the install hint in the message (matches the existing `[nwp]` extra-missing test pattern).

- **W3-T5**: Doc update — README quickstart gets a "Polars backend" section showing `tradewinds.research("KNYC", "2025-01-06", "2025-01-12", backend="polars")` returning a `TradewindsResult` wrapping a Polars DataFrame.

**Wave 3 Success Criteria:**

- All 5 public entry points accept `backend="polars"` kwarg. Default stays `"pandas"` so existing callers see zero behaviour change.
- Without `[polars]` extra, `backend="polars"` raises `SourceUnavailableError` with install hint.
- `TradewindsResult` is the default return for all 5; `return_type="dataframe"` shim preserves v0.1.0 shape for one release cycle.
- Per-entry-point smoke tests confirm both backends return equivalent rows.

**Wave 3 Verification:**
- Codex + python-architect: focus on default-arg compat + install-hint correctness + the `return_type` deprecation shim.
- README quickstart paragraph reviewed.

---

## Wave 4 — POLARS Track C: parity invariant + sort-stability tests

**Goal:** Prove the cross-backend invariants the parity gate depends on hold. The key risk per recon §5: parity-locked modules use `kind="mergesort"` for sort stability; narwhals' polars `sort()` MUST preserve identical row ordering or the parity test fails.

**Tasks:**

- **W4-T1**: POLARS-04 — document the parity-locked-thunk pattern. For each of the 7 parity-locked modules (`_internal/_pairs.py`, `core/merge.py`, `core/_climate.py`, `core/validator.py`, `core/temporal/leakage.py`, `core/temporal/timepoint.py`, `core/_json_safe.py`), the module docstring gets a paragraph: "POLARS-MODE THUNK: this module is parity-locked per CLAUDE.md and stays pandas-only. Polars-mode callers flow through `TradewindsResult.frame_as_pandas()` at the entry boundary; the conversion is documented here." Tests verify polars-mode → pandas-mode conversion at every parity-locked boundary.

- **W4-T2**: POLARS-06 — round-trip parity property test. For each of the 5 frozen parity fixtures: run `research(station, from, to, backend="pandas")` and `research(station, from, to, backend="polars")`. Assert `polars_result.frame.to_pandas().equals(pandas_result.frame)`. Acceptable resolution differences: pandas → polars datetime-resolution conversion (the `ns → us` shift documented in the test). Hypothesis-driven random-fixture variant strengthens the invariant beyond the 5 frozen cases.

- **W4-T3**: POLARS-07 — sort-stability invariant test. Construct a 1000-row DataFrame with duplicate keys; run the same `merge_observations` pipeline through both backends; assert row ordering is identical. If narwhals can't guarantee this, the polars-mode merge path falls back to pandas via the thunk pattern (the merge module is on the W4-T1 exclusion list anyway, so this is belt-and-suspenders).

- **W4-T4**: Cross-backend QC parity. Run `research(qc=True, backend="pandas")` and `research(qc=True, backend="polars")`. Assert the `qc` summary on both `TradewindsResult` instances is identical (rules_fired counts, sidecar_paths). The QC engine is on the W4 exclusion list (pandas-only) but the wrapping summary should be backend-neutral.

- **W4-T5**: Cross-backend DataVersion parity. Phase 3.6's `DataVersion.for_research()` hashes path/size/mtime of the cache files. Backend choice MUST NOT change the data_sha (it's a function of disk state, not in-memory representation). Test: `DataVersion.for_research(...)` returns identical tokens for pandas vs polars calls against the same cache.

**Wave 4 Success Criteria:**

- All 5 parity fixtures round-trip byte-equivalent across backends (modulo documented datetime-resolution shifts).
- Sort-stability holds: identical row ordering for the merge layer across backends.
- QC summary + DataVersion token are backend-invariant.
- Property tests pass for 50+ random fixture variants (Hypothesis).

**Wave 4 Verification:**
- Codex + python-architect: focus on sort-stability rigor + the parity-locked-thunk documentation accuracy.
- All tests on the cross-backend matrix pass.

---

## Wave 5 — POLARS Track D: CI matrix gates + marker discipline

**Goal:** Lock the cross-backend test matrix into CI; make `[polars]`-extra-missing environments skip cleanly via a `@pytest.mark.polars` marker.

**Tasks:**

- **W5-T1**: POLARS-08 — CI matrix extension. `.github/workflows/test.yml` adds a `with-polars` job dimension:
  - `with-polars: [false, true]`
  - When `true`: `uv sync --extra polars` for all three packages; `pytest -m "not live"` runs the full suite INCLUDING `@pytest.mark.polars`-marked tests.
  - When `false`: default install; `pytest -m "not live and not polars"` skips polars-only tests cleanly.
  - Both jobs are required status checks. Required on every PR touching `tradewinds.research`, `tradewinds.mode2`, `tradewinds.discovery`, `tradewinds.transforms`, `tradewinds.preprocessing`, or `tradewinds.core.result`.

- **W5-T2**: `@pytest.mark.polars` marker registration in `pyproject.toml` (root tool.pytest.ini_options.markers). All cross-backend tests get the marker (existing tests stay unmarked = run in both jobs).

- **W5-T3**: pre-commit hook (or pre-push) sanity check: `pytest -m "polars and not live" --co` (collect-only) on a `[polars]`-installed venv to catch test-discovery failures locally before they hit CI.

- **W5-T4**: README badge update — add a "polars" test-matrix badge alongside the existing pandas/coverage badges.

- **W5-T5**: CHANGELOG omnibus entry for v0.2.0 ship covering: pandas 3.x support, optional polars backend, `TradewindsResult` wrapper, install hint for missing extra, migration recipes (v0.1 → v0.2 `df.attrs` → `result.legacy_df_with_attrs()`).

**Wave 5 Success Criteria:**

- CI runs the cross-backend matrix on every PR; both `with-polars=false` and `with-polars=true` jobs pass.
- `@pytest.mark.polars` discipline holds: no polars-marked test fires without the extra installed.
- README + CHANGELOG documents both tracks clearly.

**Wave 5 Verification:**
- CI green on a real PR (use a no-op PR to validate the new matrix).
- Final codex + python-architect review against the full phase diff (W0..W5 combined).

---

## Cross-Wave Dependencies

```
W0 (TradewindsResult)
  ├── W1 (PANDAS3) — independent of W2-W5
  └── W2 (narwhals)
        └── W3 (backend kwarg)
              └── W4 (parity tests)
                    └── W5 (CI gates)
```

W1 can run in parallel with W2 → W5 after W0 ships. The two-lane parallelization is:
- **Lane A**: W0 → W1 (pandas-3 track).
- **Lane B**: W0 → W2 → W3 → W4 → W5 (polars track).

Both lanes merge into the same v0.2.0 release.

## Review Discipline

Per `.planning/REVIEW-DISCIPLINE.md`:

- Two-reviewer loop (codex `high` + python-architect) at every wave merge gate.
- Severity gate: CRITICAL / HIGH block; MEDIUM/LOW noted but non-blocking.
- The pandas 3 fixture re-capture (W1-T5) is **parity-adjacent** — extra scrutiny on whether the captured bytes truly match across versions.
- The narwhals sort-stability invariant (W4-T3) is **load-bearing** for the parity gate — codex must verify the test actually catches the failure mode, not just the happy path.
- Hypothesis-driven property tests (W4-T2) get a separate review pass: are the property invariants strong enough to catch a subtle row-ordering shift?

## Out of Scope (Deferred)

Per ROADMAP § Phase 6 "Out of scope":
- pyarrow Table backend (third option) — v0.3 follow-up via PYARROW-BACKEND-01.
- Polars LazyFrame default — v0.3 via POLARS-LAZY-01.
- Backend autodetection from environment — explicit `backend=` kwarg is the only contract in v0.2.
- Rewriting parity-locked paths in polars — would invalidate the lift-pinned SHA contract.
- `df.attrs` strict deprecation — v0.2 supports BOTH `df.attrs` reads (legacy) and `TradewindsResult` (new); strict deprecation lands v0.3.

## Open Questions (to resolve early in W0)

1. **`TradewindsResult` import location**: under `tradewinds.core.result` (recommended) or top-level `tradewinds.TradewindsResult` re-export? Pick before W0-T1 lands. Recommendation: both — module path is the canonical, top-level re-export is the ergonomic shortcut.
2. **`return_type` default**: `"wrapper"` (this plan's assumption — breaks v0.1.0 callers but is the long-term right shape) vs `"dataframe"` (v0.1.0-compat default — pushes the migration to v0.3). Recommendation: `"wrapper"` with a clear CHANGELOG migration recipe.
3. **Narwhals version floor**: `>=1.20` is the recon's suggestion (stable cross-backend API). Confirm against narwhals release notes before W2-T1.

## Estimate

- Single-lane wall-clock: 12-16 days.
- Two-lane parallel (post-W0): 8-11 days.
- Includes 2-3 review iterations per wave per the historical pattern (Phase 3.x averaged 1.7 iterations per wave).

---

*Plan committed: 2026-05-23. Driven by the recon agent's full-repo audit captured in [RESEARCH.md](RESEARCH.md). Verification gate: spawn `gsd-plan-checker` against this PLAN.md to confirm wave structure achieves the goal-level success criteria; iterate if checker reports gaps.*

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

1. **Pandas 3 dual-lock parity:** the 5 Phase 1 parity fixtures pass byte-equivalent under BOTH `pandas==2.2.x` AND `pandas>=3.0,<4.0` via the `coerce_pd3.py` bridge (NOT a second fixture set — see W1-T5). CI matrix runs both. `pandas<3.0` cap dropped in all 6 affected extras; new floor `pandas>=2.2,<4.0`. ULP-drift measurement carried forward + documented in `tests/fixtures/parity/README.md`.

2. **Opt-in polars backend:** `backend: Literal["pandas","polars"]="pandas"` kwarg on `research()`, `research_by_source()`, `polymarket_discover()`, `forecast_nwp()`, `daily_extremes()`. Default stays pandas. With `backend="polars"` (which requires `return_type="wrapper"` per W3-T3 — polars frames have no `df.attrs`), every adapter returns a `TradewindsResult` wrapping a Polars DataFrame; row contents equivalent to the pandas backend (verified by `polars_df.to_pandas().equals(pandas_df)` on the 5 parity fixtures); provenance lives on the wrapping `TradewindsResult`.

3. **`TradewindsResult` provenance wrapper:** new dataclass at `tradewinds.core.result.TradewindsResult` carries `frame` (pd.DataFrame | pl.DataFrame), `source` (str), `retrieved_at` (datetime), `schema_id` (str | None), `qc` (dict | None), `data_version` (DataVersion | None). `return_type="dataframe"` (default) returns a pandas DataFrame for v0.1.0-shape compat; `return_type="wrapper"` (opt-in v0.2; required for `backend="polars"`) returns the wrapper. Validator + KnowledgeView + LeakageDetector accept `TradewindsResult` and unwrap.

4. **Narwhals internal data layer for DIRECT user calls outside research()** (**architect iter-2 HIGH-B clarification**): the 5 cleanly-portable modules (`transforms.py`, `preprocessing.py`, `qc.crosscheck_iem_ghcnh`, `core/temporal/knowledge_view.py`, `core/formats/{json,csv,toon}.py`) are refactored to accept pandas OR polars via narwhals. These narwhals paths fire when a user calls them **directly** (e.g. `tw.transforms.lag(my_polars_df, "temp")` after their own data prep). They do NOT fire inside `research()` — per W4-T1 the research() pipeline stays pandas end-to-end with conversion ONLY at the outermost return boundary. The per-backend test matrix in W2-T7 exercises the direct-call surface; the `research()` cross-backend invariant in W4-T2 exercises the outer boundary. These are two distinct test classes.

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

- **W1-T5**: PANDAS3-04 — pandas-3 parity strategy. **Architect iter-1 CRITICAL fix:** The v0.1.0 parity contract is byte-equivalent to `mostlyright==0.14.1` (a single, immutable set of bytes per CLAUDE.md). Capturing a *second* set of fixtures from tradewinds' own pandas-3 output is circular — it proves tradewinds-2.x == tradewinds-3.x, NOT that pandas-3-tradewinds matches mostlyright-0.14.1. **Correct strategy:**
  - The canonical fixtures at `tests/fixtures/parity/case_*.parquet` stay 2.x-derived (immutable; the v0.1.0 contract).
  - New `tests/fixtures/parity/coerce_pd3.py` defines a documented, reversible transform from the 2.x parquet bytes to the pandas-3 representation: explicit `ns→us` datetime-resolution coercion + `object→string` dtype promotion. Function: `coerce_2x_to_3x(parquet_path: Path) → pd.DataFrame`. Inverse: `coerce_3x_to_2x(df: pd.DataFrame) → pd.DataFrame`.
  - Parity test under pandas 3.x: read the 2.x fixture, apply `coerce_2x_to_3x`, compare against the live `research()` output. NO new fixture files land on disk; the transform is the contract.
  - Round-trip test: `coerce_3x_to_2x(coerce_2x_to_3x(case)) == case` (the transform is invertible byte-for-byte for the documented coercions — `ns↔us` is lossless at second-resolution timestamps, `object↔string` is metadata only). Documents the exact resolution shift + dtype promotion the parity gate accepts as pandas-3-equivalent.
  - **Architect iter-2 HIGH-A + iter-3 HIGH-3 fix — ULP drift as a committed artifact + CI gate (not an instruction).** The existing parity gate (`tests/test_parity.py:27-30`) tolerates `atol=1e-12` on float aggregates (`obs_mean_f`, `obs_mean_dewpoint_f`, `obs_total_precip_in`) because non-associative FP add already produces ~2.84e-14 drift under pandas 2.x. **Concrete enforcement:**
    - New committed artifact: `tests/fixtures/parity/ulp_drift_pd3.json` — JSON object with shape `{"pandas_version": "3.0.x", "measured_at": "<ISO>", "tolerance_used": 1e-12, "per_column_max_abs_drift": {"obs_mean_f": ..., "obs_mean_dewpoint_f": ..., "obs_total_precip_in": ...}}`. Produced by a new script `tests/fixtures/parity/measure_ulp_drift.py` that runs the 5 parity cases under pandas 3 and records the max-abs-drift per column.
    - W1 merge gate: `tests/test_parity.py` reads `ulp_drift_pd3.json` at import time. If file is missing → `pytest.fail("ULP drift measurement required before pandas 3 lockfile lands; run tests/fixtures/parity/measure_ulp_drift.py")`. If any `per_column_max_abs_drift > tolerance_used` → fail with measurement details. CI's `pandas-resolution: highest` job will fail on a missing artifact, blocking the merge.
    - Promotion rule (codified in the script): if measured drift > `1e-12`, the script writes `tolerance_used=1e-10` and the parity test reads the looser tolerance. The promotion is documented in `tests/fixtures/parity/README.md` alongside the empirical numbers.
  - `tests/fixtures/parity/README.md` documents `coerce_pd3.py` as the bridge + cites the pandas 3.0 whatsnew sections that motivate each coercion + records the empirical ULP drift measurement.

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
  - `tradewinds.international.daily_extremes()` — default return stays `list[dict]` (preserves v0.1.0 zero-behaviour-change constraint per **codex iter-3 P2 fix**); `backend="polars"` + `return_type="wrapper"` is the opt-in path that returns a `TradewindsResult`. Calling `backend="polars"` without `return_type="wrapper"` raises `ValueError` per W3-T3.

  For each entry point: validate `backend` kwarg, call the underlying pandas path, then if `backend=="polars"` convert the final DataFrame to polars via `pl.from_pandas(df)`. The conversion is at the public surface boundary, not deep in the pipeline (parity-locked modules stay pandas-only per W4).

- **W3-T3**: POLARS-02 — `return_type: Literal["wrapper","dataframe"]="dataframe"` kwarg added to the 5 entry points. **Architect iter-1 HIGH-1 + Codex iter-1 P2 fix:** default stays `"dataframe"` for v0.2 so the v0.1.0 zero-behaviour-change constraint holds — every existing `df = research(...)["temp"]` notebook keeps working. `return_type="wrapper"` is opt-in for v0.2 and returns a `TradewindsResult`. Strict deprecation of the legacy default lands in v0.3 (separate REQUIREMENTS entry tracks the flip). The `backend="polars"` path requires `return_type="wrapper"` because polars frames don't have `df.attrs` to carry provenance — calling `backend="polars"` with the default `return_type="dataframe"` raises `ValueError("backend='polars' requires return_type='wrapper'")` with the migration recipe inline.

- **W3-T4**: Install-hint tests. For each entry point, a `@pytest.mark.skipif(_HAS_POLARS, ...)` test asserts that `backend="polars"` (passed with `return_type="wrapper"` to clear the W3-T3 ValueError gate first) without the extra installed raises `SourceUnavailableError` with the install hint. **Codex iter-3 P2 fix — validation order spec:** the entry-point body validates in this strict order: (1) `backend` value is in the supported set (else `ValueError`); (2) `backend="polars" + return_type="dataframe"` combination raises `ValueError`; (3) ONLY after kwargs are coherent, the lazy `_polars_compat` helper fires `SourceUnavailableError` if the extra is missing. This way the install-hint test calls `research(..., backend="polars", return_type="wrapper")` and reliably hits step 3, never step 2.

- **W3-T5**: Doc update — README quickstart gets a "Polars backend" section showing the canonical opt-in call: `result = tradewinds.research("KNYC", "2025-01-06", "2025-01-12", backend="polars", return_type="wrapper")` then `result.frame` is the Polars DataFrame and `result.source`, `result.retrieved_at` carry the provenance. The example explicitly shows the `return_type="wrapper"` opt-in matching W3-T3's locked spec.

**Wave 3 Success Criteria:**

- All 5 public entry points accept `backend="polars"` kwarg. Default stays `"pandas"` so existing callers see zero behaviour change.
- Without `[polars]` extra, `backend="polars"` raises `SourceUnavailableError` with install hint.
- `return_type="dataframe"` is the v0.2 default (legacy v0.1.0 shape preserved); `return_type="wrapper"` is opt-in. `backend="polars"` + default `return_type` raises `ValueError` directing the caller to `return_type="wrapper"`. Strict deprecation of the legacy default lands in v0.3.
- Per-entry-point smoke tests confirm both backends return equivalent rows.

**Wave 3 Verification:**
- Codex + python-architect: focus on default-arg compat + install-hint correctness + the `return_type` deprecation shim.
- README quickstart paragraph reviewed.

---

## Wave 4 — POLARS Track C: parity invariant + sort-stability tests

**Goal:** Prove the cross-backend invariants the parity gate depends on hold. The key risk per recon §5: parity-locked modules use `kind="mergesort"` for sort stability; narwhals' polars `sort()` MUST preserve identical row ordering or the parity test fails.

**Tasks:**

- **W4-T1**: POLARS-04 — parity-locked-thunk pattern. **Architect iter-1 HIGH-5 fix:** `frame_as_pandas()` is NOT lossless across the parity contract (`pl.DataFrame.to_pandas()` drops `df.attrs`, may coerce datetime resolution `us↔ns`, changes nullable-int representation; float aggregates already drift ~2.8e-14 per `test_parity.py:27`). **Load-bearing invariant:** polars-mode `research()` runs the ENTIRE parity-locked pipeline in pandas — the conversion to polars happens ONLY at the final return boundary in W3-T2's outer dispatch, NEVER inside `_internal/_pairs.py` / `core/merge.py` / `core/_climate.py` / validator / leakage / timepoint / `_json_safe`. For each of the 7 parity-locked modules, the module docstring gets a paragraph: "POLARS-MODE INVARIANT: this module is parity-locked per CLAUDE.md and stays pandas-end-to-end. Polars-mode callers do NOT hit this module with a polars frame at any point in the pipeline; the backend conversion is the OUTERMOST step of `research()`, applied to the already-pandas pairs DataFrame after this module finishes." Tests assert that any direct call into these modules with a polars frame raises `TypeError("parity-locked module: pass pandas frame")` — defense-in-depth so a future refactor can't silently re-introduce the lossy conversion.

- **W4-T2**: POLARS-06 — round-trip parity property test. For each of the 5 frozen parity fixtures: run `research(station, from, to, backend="pandas", return_type="wrapper")` and `research(station, from, to, backend="polars", return_type="wrapper")` (both opt in to the wrapper since `backend="polars"` requires it per W3-T3 and we want a like-for-like comparison). Assert `polars_result.frame.to_pandas().equals(pandas_result.frame)`. Acceptable resolution differences: pandas → polars datetime-resolution conversion (`ns → us` shift, documented in the test). Hypothesis-driven random-fixture variant strengthens the invariant beyond the 5 frozen cases.

- **W4-T3**: POLARS-07 — sort-stability invariant test. **Architect iter-1 HIGH-3 fix:** Polars' default `sort()` is NOT stable; stability requires `maintain_order=True`, and narwhals' translation of pandas `kind="mergesort"` is not documented as stable in the source narwhals docs cited in RESEARCH §6. The test as previously written ("assert row ordering is identical") would pass on small inputs and fail nondeterministically at scale. **Correct test:**
  - Construct an **adversarial** 10,000-row DataFrame with deliberately-pathological duplicate keys (every key appears 10+ times; insertion order randomized via a seeded RNG).
  - Run the W2 narwhals-migrated modules' sort paths through both pandas + polars. Assert byte-identical row ordering.
  - Assert (via AST inspection or by patching narwhals) that the polars backend translation explicitly sets `maintain_order=True` on every `sort()` call in the W2 modules. Failing this assertion fails the test loudly.
  - Belt-and-suspenders fallback: any W2 module whose narwhals translation cannot guarantee `maintain_order=True` gets promoted to the W4-T1 parity-locked thunk exclusion list (pandas-only end-to-end). Candidates: `transforms.rolling`, `preprocessing.iem_crosscheck` (its `.merge` invokes sort), `qc.crosscheck_iem_ghcnh`. W2-T2 through W2-T4 are revisited if any of these fail the invariant.

- **W4-T4**: Cross-backend QC parity. Run `research(qc=True, backend="pandas", return_type="wrapper")` and `research(qc=True, backend="polars", return_type="wrapper")` (both opt in to the wrapper so the `qc` summary is on a comparable surface). Assert the `qc` summary on both `TradewindsResult` instances is identical (rules_fired counts, sidecar_paths). The QC engine is on the W4 exclusion list (pandas-only) but the wrapping summary should be backend-neutral.

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
  - When `true`: install the `[polars]` extra on each member package (the workspace root has no `[polars]` extra — **Codex iter-1 P2 fix**: `uv sync --extra polars` at the root would fail). Correct invocation: `uv sync --package tradewinds --extra polars && uv sync --package tradewinds-weather --extra polars && uv sync --package tradewinds-markets --extra polars` (or equivalent matrix-step that iterates over the three member packages). Then `pytest -m "not live"` runs the full suite INCLUDING `@pytest.mark.polars`-marked tests.
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

### Explicit merge serialization (architect iter-1 HIGH-4 fix)

Both Lane A (W1-T1 — `validator.py:84,100,119-121,150` string-dtype branch refactor) and Lane B (W0-T4 — `validator.py` dispatch update for `TradewindsResult`; W2-T5 — `knowledge_view.py` changes the type flowing INTO validator) edit `tradewinds.core.validator.py`. Independent merges WILL conflict. Required serialization order:

1. **W0 merges first** (foundation). Validator gains `TradewindsResult`-accepting dispatch.
2. **W1 rebases on W0** before merging. W1's `validator.py:84,100,119-121,150` edits land on top of W0's dispatch shim; the union diff is reviewed once.
3. **W2 rebases on `W0 + W1`** before merging. W2-T5 KV migration goes through the already-extended validator dispatch.
4. W3 → W4 → W5 then proceed serially on Lane B.

If Lane A and Lane B both author validator edits in parallel branches, the second-to-merge MUST `git rebase merged-vision` and re-run the validator's test suite before merging. PR template gets a checkbox: "If this PR touches validator.py, confirm it was rebased on the latest `merged-vision`."

## Phase 5 (MCP) Interaction — architect iter-1 HIGH-2

Phase 5 PLAN-02 (weather catalog entries) consumes adapter outputs via `tradewinds.core.validator.validate_dataframe(df, ...)` at PLAN-02 call sites. Phase 6 W0-T4 changes the validator's first-arg contract to also accept `TradewindsResult`. Coordination required:

1. **Phase 5 PLAN-02 is currently written against a raw `pd.DataFrame`**. Phase 6 W0-T4 must preserve `validate_dataframe(pd.DataFrame, ...)` calls byte-identical — the dispatch is `isinstance(first_arg, TradewindsResult)` to unwrap, else pass straight through. Phase 5 callers see zero behaviour change.
2. **If Phase 6 W0 lands BEFORE Phase 5 PLAN-02 starts execution**, Phase 5 PLAN-02 should be revised to consume `TradewindsResult` directly (clean break — no shim needed for new code).
3. **If Phase 5 PLAN-02 lands BEFORE Phase 6 W0**, Phase 6 W0-T4 ships with explicit Phase 5 regression tests: every PLAN-02 catalog-roundtrip test that calls `validate_dataframe` is re-run through W0's dispatch shim to confirm byte-identical behaviour.
4. **MCP server JSON-RPC serialization** uses the existing `tradewinds.core.formats.*` writers. W2-T6 narwhals-ifies `json.py` and `csv.py` (NOT `_toon` — that's byte-pinned). Phase 5 MCP tools that serialize via these writers MUST work identically regardless of whether the source DataFrame came from a pandas-mode or polars-mode `research()` call (the writers see the wrapped frame after `frame_as_pandas()` conversion at the writer boundary).

Net: Phase 6 is designed to be additive vs Phase 5. The two phases can ship in either order. The coordination contract is "validator first-arg union + format-writer-boundary pandas conversion." A coordination ticket lands in W0-T4 + W2-T6 PR descriptions cross-referencing Phase 5 PLAN-02.

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
2. ~~**`return_type` default**~~ — **RESOLVED (architect iter-1 HIGH-1 + codex iter-1 P2):** default stays `"dataframe"` for v0.2 to preserve the v0.1.0 zero-behaviour-change constraint. `"wrapper"` is opt-in. `backend="polars"` requires `"wrapper"`. Strict deprecation of the legacy default tracked separately as a v0.3 follow-up. See W3-T3 for the locked spec.
3. **Narwhals version floor**: `>=1.20` is the recon's suggestion (stable cross-backend API). Confirm against narwhals release notes before W2-T1.

## Estimate

- Single-lane wall-clock: 12-16 days.
- Two-lane parallel (post-W0): 8-11 days.
- Includes 2-3 review iterations per wave per the historical pattern (Phase 3.x averaged 1.7 iterations per wave).

---

*Plan committed: 2026-05-23. Driven by the recon agent's full-repo audit captured in [RESEARCH.md](RESEARCH.md). Verification gate: spawn `gsd-plan-checker` against this PLAN.md to confirm wave structure achieves the goal-level success criteria; iterate if checker reports gaps.*

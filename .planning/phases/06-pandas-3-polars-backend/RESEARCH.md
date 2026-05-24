# Phase 6 Research — Pandas 3 Readiness + Optional Polars Backend

**Researched:** 2026-05-23
**Domain:** Python DataFrame backend abstraction; pandas 3.0 migration; narwhals compatibility layer; opt-in polars surface.
**Confidence:** HIGH (recon agent ran a complete grep audit of `packages/` for pandas APIs, df.attrs sites, parity-locked paths, narwhals candidates, and pyproject pins; findings reproduced verbatim below).

## Summary

Phase 6 is data-layer infrastructure that ships across two paired tracks:

1. **PANDAS3** — drop the `pandas<3.0` cap (set by Phase 1 parity gate, locked at PKG-05) and re-capture the 5 parity fixtures against pandas 3.x so byte-equivalence holds on both 2.x and 3.x lockfiles. Six datetime/dtype risk sites identified by recon need remediation.

2. **POLARS** — opt-in `backend="polars"` kwarg on every public DataFrame-returning entry point. Narwhals-mediated internal data layer for 5 cleanly-portable modules. Pandas stays canonical for the 7 parity-locked modules (their lift-pinned SHA contract is unchanged). `df.attrs` migration is the load-bearing design move — introduce `TradewindsResult` thin wrapper that carries provenance separately so both backends preserve source-identity invariants.

The two tracks are independent at the test level (pandas-3 lockfile matrix vs polars backend matrix) but share infrastructure (`TradewindsResult` wrapper, validator+KnowledgeView+LeakageDetector accept either input). Recommend executing them as separate waves with the wrapper landing first.

## Recon Inventory (from full-repo grep audit, 2026-05-23)

### 1. Pandas-coupled modules

**Hot paths** (every `research()` call traverses):

| Module | LOC w/ pd | Key pandas ops |
|---|---|---|
| `packages/core/src/tradewinds/research.py` | 8 sites | `pd.DataFrame(raw_obs)`, `pd.to_numeric`, `.loc[...startswith]`, `result.attrs["qc"]=...` (orchestrator; soft-imports pd at L956) |
| `packages/core/src/tradewinds/_internal/_pairs.py` | 4 sites | `pd.DataFrame(rows)`, `pd.to_datetime(df["date"])`, `df.set_index("date").sort_index()` (`pairs_to_dataframe` at L380; soft import L386) |
| `packages/core/src/tradewinds/core/validator.py` | 23 sites | `pd.api.types.is_*_dtype`, `pd.CategoricalDtype`, `pd.NA`, `col.isna/dropna/isin`, `df.attrs.get`, `s.dt.tz` (HARD pd import L26) |
| `packages/core/src/tradewinds/core/temporal/knowledge_view.py` | 8 sites | `pd.api.types.is_datetime64_any_dtype`, `col.dt.tz`, `df.loc[mask].copy()` |
| `packages/core/src/tradewinds/core/temporal/leakage.py` | 10 sites | dtype probes + `pd.Timestamp(ts).isoformat()`, `sample.iterrows()` (HARD pd import L21) |
| `packages/core/src/tradewinds/core/merge.py` | 4 sites | `silver_df.copy()`, `df["source"].map(...).fillna(-1).astype(int)`, `sort_values(..., kind="mergesort")`, `drop_duplicates`, `gold.attrs.update(silver_df.attrs)` |
| `packages/core/src/tradewinds/core/temporal/timepoint.py` | 18 sites | `pd.Timestamp`, `pd.NaT`, `ts.tz_convert/to_pydatetime` (HARD pd import L23) |
| `packages/core/src/tradewinds/core/_json_safe.py` | many | `pd.Timestamp`, `pd.NaT`, `pd.NA` identity checks (HARD pd import L32) |
| `packages/core/src/tradewinds/core/formats/{parquet,json,csv,toon,dataframe}.py` | per file | `df.to_parquet`, `pd.read_parquet`, `DataFrame(...)` construction |
| `packages/weather/src/tradewinds/weather/catalog/_obs_projection.py` | many | `pd.DataFrame`, `pd.to_numeric`, `pd.to_datetime(..utc=True)`, `pd.array(..,dtype="Int64")`, `astype("string")`, `pd.Timestamp(...).tz_convert("UTC")`, sets `df.attrs` |
| `packages/weather/src/tradewinds/weather/catalog/cli.py` | many | same shape; also `pd.Series([], dtype="datetime64[ns, UTC]")`, `pd.NaT` |
| `packages/weather/src/tradewinds/weather/catalog/{awc,iem,ghcnh}.py` | 3 each | `pd.DataFrame([project_row(r) for r in rows])`, `pd.Timedelta(LAG)` |

**Cold paths** (opt-in / advanced):

| Module | Notes |
|---|---|
| `packages/core/src/tradewinds/qc.py` | `engine.apply`, `crosscheck_iem_ghcnh` `.merge()`, `.iterrows()`; only runs when `qc=True` |
| `packages/core/src/tradewinds/transforms.py` | `lag/diff/calendar_features/clip_outliers` — public surface but not on parity path |
| `packages/core/src/tradewinds/preprocessing.py` | Sprint 0.5+; `pd.to_numeric(...).apply(lambda...)` |
| `packages/core/src/tradewinds/mode2.py` | `pd.DataFrame(filtered)`, sets `df.attrs["source"/"retrieved_at"/"accepted_sources"]` |
| `packages/core/src/tradewinds/forecasts.py` | wrapper, soft import L42 |
| `packages/weather/src/tradewinds/weather/forecast_nwp.py` | NWP path, sets `df.attrs` for `noaa_bdp` |
| `packages/markets/src/tradewinds/markets/polymarket.py` | lazy import + sets `df.attrs` at L520-521 |
| `packages/weather/src/tradewinds/weather/cache.py`, `qc_sidecar.py` | **pyarrow only — no pandas import; already polars-ready interop seam** |

### 2. Pandas 3.0 Risk Surface

| Risk | Hits | Verdict |
|---|---|---|
| `applymap` | 0 | clean |
| `Series.append` / `DataFrame.append` | 0 (only Python `list.append`) | clean |
| Offset aliases `freq='M'/'Q'/'Y'` | 0 | clean |
| `infer_objects`, `is_categorical`, `is_extension_array_dtype` | 0 | clean |
| Chained-assignment `.iloc[...] = ` writes | 0; all `.loc[]/.iloc[]` are reads | clean |
| `astype("object")` for strings | 0 | clean |
| `pd.api.types.is_string_dtype(s) or s.dtype == "object"` | `validator.py:84, 100, 119-121, 150` | **WARN** — pandas 3.0's `str` default dtype shift means the `s.dtype == "object"` fallback is what *currently* matches string columns |
| `to_datetime` calls | `_pairs.py:397`, `transforms.py:89`, `validator.py:211 (doctest)`, `cli.py:149-151, 225`, `_obs_projection.py:172`, 3 in `forecast_nwp.py` | **WARN** — datetime resolution may shift `ns→us` for naive-string parsing; `cli.py` & `_obs_projection` use `utc=True` (stable); `_pairs.py:397` parses date-only strings (resolution shift would be byte-visible) |
| `pd.Series([], dtype="datetime64[ns, UTC]")` | `cli.py:158, 216` | **WARN** — explicit `[ns]` literal may need `[us, UTC]` re-validation under 3.0 |
| `pd.NA`/`pd.NaT` identity checks | `_json_safe.py:96,99,134`, `cli.py:221`, `validator.py:155` | likely fine but needs re-test |

### 3. Validator + KnowledgeView + LeakageDetector dependence

**All three are tightly DataFrame-coupled — none can accept a polars frame as-is.**

- **`validator.py`**: `pd.api.types.is_{string,float,integer,datetime64_any}_dtype`, `pd.CategoricalDtype` isinstance check L121, `s.dt.tz`, `s.dtype == "object"`, `col.isna()/dropna()/isin()`, `df.attrs.get("source")`/`get("retrieved_at")` (L241, 388), `df.columns`, `s.head(5)`, `non_null.index[mask_bad]`, `non_null.loc[idx]`. Dtype dispatch (`_DTYPE_CHECKERS` L125) is the deepest pandas-API surface in the codebase.
- **`knowledge_view.py`**: `pd.api.types.is_datetime64_any_dtype(col)` (L75), `col.dt.tz` (L81), `self._df.loc[mask].copy()` (L94). Smaller surface.
- **`leakage.py`**: same datetime/tz probes + `df.loc[mask].head(_SAMPLE_CAP)` + `sample.iterrows()` and `pd.Timestamp(ts).isoformat()` (L103-108). Imports pandas at module scope.

All three rely on `df.attrs` (validator) or DataFrame index semantics (leakage `iterrows`). A polars/arrow frame needs a shim — `TradewindsResult.frame_as_pandas()` is the simplest contract.

### 4. `df.attrs` Usage Map

**Writes (12 sites — every one is a polars-incompatibility point):**
- `mode2.py:156-157, 167-169` (3 attrs: `source`, `retrieved_at`, `accepted_sources`)
- `research.py:1245` (`result.attrs["qc"]`)
- `core/merge.py:128` (`gold.attrs.update(silver_df.attrs)`)
- `weather/catalog/_obs_projection.py:177-178`
- `weather/catalog/cli.py:194-195`
- `weather/forecast_nwp.py:669-670, 750-751`
- `markets/polymarket.py:520-521`

**Reads (validator):**
- `validator.py:241` (`df.attrs.get("source")` — mandatory)
- `validator.py:388` (`df.attrs.get("retrieved_at")` — mandatory)

This is the single biggest polars blocker. `TradewindsResult` wrapper migration is the only clean path.

### 5. Parity-Locked Hot Paths (CANNOT switch backend)

- `_internal/_pairs.py` — entire module, SHA-pinned at file header L1-24.
- `research.py:1229-1238` — final `build_pairs → pairs_to_dataframe` call.
- `core/merge.py` — `query_time_merge` strict-`>` priority + `kind="mergesort"` (CLAUDE.md flags as load-bearing).
- `weather/_climate.py` `_dedup_climate_rows` (CLAUDE.md "Climate LIVE_V1").

Any backend switch on these re-triggers fixture re-capture and invalidates the lift-pinned SHA contract.

### 6. Narwhals Candidate Paths

**Cleanly narwhals-ifiable** (small surface, no `.attrs` writes, no deep dtype dispatch):
- `transforms.py` — pure column math (`lag/diff/calendar_features/spread/clip_outliers`).
- `preprocessing.py` — `to_numeric + arithmetic + DataFrame construction` only.
- `qc.py crosscheck_iem_ghcnh` (L191-228) — single `.merge` + `.loc[]` filter.
- `core/temporal/knowledge_view.py` — tiny surface (3 ops); only `df.attrs` blocker absent here.
- `core/formats/{json,csv,toon}.py` — serialization shims, mostly row-iteration.

**Cannot cleanly narwhals-ify:**
- `core/validator.py` — `pd.api.types.*` dispatch + `pd.CategoricalDtype` + `df.attrs` reads.
- `core/temporal/leakage.py` — `pd.Timestamp.isoformat()` + `iterrows()`.
- `core/temporal/timepoint.py` — `pd.Timestamp`/`pd.NaT` are first-class accepted input types.
- `core/_json_safe.py` — explicit `pd.NA`/`pd.NaT` identity checks.
- `core/merge.py` — parity-locked sort semantics.
- `_internal/_pairs.py` — parity-locked.
- `weather/catalog/*.py` + `weather/forecast_nwp.py` + `markets/polymarket.py` — every adapter sets `df.attrs`.

### 7. pyproject pandas pins (all consistent)

**`pandas>=2.2,<3.0` across all three packages.** No core runtime `[project.dependencies]` pin (pandas is only in extras).

Extras carrying the pin:
- `packages/core/pyproject.toml:30-52` — **`parquet`** (L37-40) AND **`research`** (L48-52).
- `packages/weather/pyproject.toml:37-58` — **`parquet`** (L42-44) AND **`nwp`** (L53-58).
- `packages/markets/pyproject.toml:28-44` — **`parquet`** (L31-34) AND **`polymarket`** (L41-44).

All five extras carry the explicit `pandas>=2.2,<3.0` cap with cross-package alignment comments (Codex iter-6 P2, PKG-05/06).

### 8. Other Findings

- `pyarrow` is also capped `<24.0` (parquet extra of core/markets) — Phase 6 may need to bump for arrow-native polars interop.
- `weather/cache.py` is **pyarrow-only** (no pandas import) — already polars-ready and a good interop seam.
- `_pairs.py` lift header (L1-24) SHA-pins the source blob; any backend-driven edit invalidates the lift-provenance comment.
- Doctest examples in `validator.py:209-217`, `knowledge_view.py:46-58`, `leakage.py:54-73` would all need polars equivalents or `# doctest: +SKIP`.

## Recommended Wave Structure (input to gsd-planner)

Based on the recon:

- **Wave 0 (foundation):** `TradewindsResult` wrapper + validator/KV/LeakageDetector unwrap support. Lands the data class that the polars track depends on, but standalone usable for the pandas-3 track (carries `df.attrs` data in a backend-neutral container).
- **Wave 1 (pandas-3 track):** PANDAS3-01..06. Audit + remediate 6 risk sites, drop the cap in 6 extras, dual-pandas CI matrix, parity-fixture re-capture, doctest updates.
- **Wave 2 (polars track A — narwhals migration):** POLARS-03. Refactor the 5 cleanly-portable modules to narwhals primitives. Per-backend test matrix verifies identical output. Order by blast radius: `transforms.py` first (lowest), `core/formats/*` last (highest because of serialization).
- **Wave 3 (polars track B — public surface):** POLARS-01, POLARS-02, POLARS-05. `backend="polars"` kwarg on the 5 public entry points; `[polars]` optional extra; `SourceUnavailableError` install-hint gate.
- **Wave 4 (polars track C — parity + sort invariant):** POLARS-04, POLARS-06, POLARS-07. Parity-locked thunk documentation; round-trip parity property test; sort-stability invariant test.
- **Wave 5 (polars track D — CI gates):** POLARS-08. Cross-backend CI matrix gating on `[polars]` extra; `@pytest.mark.polars` marker discipline.

## Verified Sources

- pandas 3.0 whatsnew — https://pandas.pydata.org/docs/dev/whatsnew/v3.0.0.html (CoW enforcement, str default dtype, datetime resolution inference, offset alias removals).
- narwhals docs — https://narwhals-dev.github.io/narwhals/ (cross-backend API; preserves sort stability per-backend).
- Polars 1.x stable — https://docs.pola.rs/ (eager + lazy; `to_pandas()` round-trip).
- CLAUDE.md `# Data + parity rules` section — defines `pandas<3.0` as PARITY-CRITICAL and reserves the migration as a v0.2 explicit work item.
- Tradewinds `packages/core/pyproject.toml`, `packages/weather/pyproject.toml`, `packages/markets/pyproject.toml` — current `pandas>=2.2,<3.0` pins (read 2026-05-23).

# Phase 6 Context

## Phase Goal

Two paired tracks of data-layer infrastructure work, scoped so they can ship as one
v0.2 milestone:

1. **Pandas 3 readiness** — audit the Python SDK for pandas 2.x-only APIs, deprecated
   methods, dtype changes. Plan migration so the SDK works on both pandas 2.x and 3.x
   (dual-pandas CI matrix). Drop the `pandas<3.0` cap in all 6 affected extras.
2. **Optional Polars backend** — design an opt-in `backend="polars"` kwarg so users
   can choose pandas or polars for output. Internal data layer is backend-agnostic
   where possible (narwhals-mediated for cleanly-portable modules); pandas remains
   canonical for parity-locked paths.

This is PLANNING ONLY — no implementation lands in this round.

## User Decisions (Locked)

1. **Backend choice is opt-in via kwarg.** `backend: Literal["pandas","polars"]="pandas"`
   on every public DataFrame-returning entry point. Default stays pandas so existing
   callers see zero behaviour change. No global config; no env-var autodetection.
2. **`df.attrs` is the polars blocker.** Polars frames have no `.attrs`. Migrate
   provenance off `df.attrs` onto a new `TradewindsResult` thin wrapper that carries
   `frame`, `source`, `retrieved_at`, `schema_id`, `qc`, `data_version` separately.
   Both backends produce the same wrapper shape.
3. **Parity-locked modules stay pandas-only.** `_internal/_pairs.py`, `core/merge.py`,
   `core/_climate.py`, validator are byte-faithful lifts from `mostlyright==0.14.1`
   per CLAUDE.md; switching their backend invalidates the lift-pinned SHA contract.
   Polars-mode callers hitting these paths flow through a pandas-mediated thunk.
4. **Narwhals is the compatibility layer.** narwhals (https://narwhals-dev.github.io/narwhals/)
   provides a unified API over pandas/polars/pyarrow. Use it for the 5 cleanly-portable
   modules (`transforms.py`, `preprocessing.py`, `qc.crosscheck_iem_ghcnh`,
   `core/temporal/knowledge_view.py`, `core/formats/{json,csv,toon}.py`).
5. **Dual-pandas CI matrix.** Tests run under BOTH pandas 2.2.x AND pandas 3.x.
   Parity fixtures re-captured against 3.x land at `tests/fixtures/parity/pandas3/`
   alongside the 2.x originals.
6. **Eager Polars only in v0.2.** LazyFrame default deferred to v0.3 (POLARS-LAZY-01).
   pyarrow Table backend deferred to v0.3 (PYARROW-BACKEND-01).
7. **`df.attrs` compatibility shim for v0.2.** Adapters return `TradewindsResult` from
   the new backend-aware paths AND keep legacy `df.attrs`-set behaviour under a
   `result.legacy_df_with_attrs()` accessor for one release cycle. Strict deprecation
   lands v0.3.

## Claude's Discretion

1. **Module-by-module narwhals migration order.** The recon flagged 5 candidates;
   pick whichever has the smallest blast radius for the first iteration.
2. **Whether to ship `daily_extremes()` backend kwarg in v0.2 or v0.2.x.** It returns
   `list[dict]` today, not a DataFrame, so the backend kwarg there is a return-type
   change (`TradewindsResult` wrapper). Recommend: ship in v0.2 to keep the surface
   consistent.
3. **`TradewindsResult` design granularity.** Either a single dataclass (this phase
   assumes this) or a Protocol that downstream extensions can implement. Pick whichever
   reads best with the validator changes.

## Constraints

- **No implementation in this round.** PLAN.md only, with explicit wave structure +
  task breakdown + dependencies + success criteria per wave.
- **Two-reviewer loop required.** Per `.planning/REVIEW-DISCIPLINE.md` (codex `high` +
  python-architect) against the plan before commit.
- **No breaking changes to v0.1.0 public surface.** Default `backend="pandas"` MUST
  preserve byte-equivalence with the v0.1.0 ship; the 5 parity fixtures (2.x) are
  the contract.
- **Optional extras gating.** Polars calls without `[polars]` extra installed must
  raise `SourceUnavailableError` with install hint (mirrors the `[nwp]` pattern).
- **CI cost budget.** Dual-pandas matrix doubles CI runtime; mitigate by running
  pandas-3 jobs on a single Python version (3.13) initially.

## Out of Scope

See ROADMAP § Phase 6 "Out of scope" — pyarrow backend, polars LazyFrame default,
backend autodetection, rewriting parity-locked paths in polars, df.attrs strict
deprecation are all deferred.

## Requirements Mapped

PANDAS3-01..PANDAS3-06 + POLARS-01..POLARS-08 (14 IDs total). See REQUIREMENTS.md
§ "Phase 6: Pandas 3 Readiness + Optional Polars Backend (v0.2+)".

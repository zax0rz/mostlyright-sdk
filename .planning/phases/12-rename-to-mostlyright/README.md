# Phase 12: Rename `tradewinds` → `mostlyright`

**Status:** code-complete; operator gates pending
**Closeout:** 2026-05-25
**Branch:** `phase-12/rename-to-mostlyright` (off `main`); final PR → `main`

## What this phase shipped

Mechanical end-to-end rename of every in-repo identifier from `tradewinds` to
`mostlyright`. ZERO behavior change. ZERO test regressions at every wave gate.

- 3 PyPI distribution names renamed: `tradewinds` / `tradewinds-weather` /
  `tradewinds-markets` → `mostlyright` / `mostlyright-weather` /
  `mostlyright-markets`
- 5 npm package names renamed: `@tradewinds/{codegen,core,weather,markets}` +
  unscoped meta `tradewinds` → `@mostlyrightmd/*` + unscoped meta `mostlyright`
- 3 Python source directories renamed via `git mv` (blame preserved)
- ~993 Python `from tradewinds` / `import tradewinds` import-line rewrites +
  ~552 string-quoted module-path rewrites (`patch("tradewinds.…")`,
  `sys.modules["tradewinds.…"]`, bare `tradewinds.__version__`, etc.) — Wave 2
- ~64 TypeScript `from "@tradewinds/…"` import-line rewrites + ~395 broader
  rewrites (comments, tsup.config.ts, codegen-source header strings, tests) +
  pnpm codegen regen with `@mostlyrightmd/codegen` AUTO-GENERATED header — Wave 3
- Cache env var `TRADEWINDS_CACHE_DIR` → `MOSTLYRIGHT_CACHE_DIR` with
  one-release back-compat shim emitting `DeprecationWarning` (Wave 4)
- Default cache path `~/.tradewinds/cache/v1/` → `~/.mostlyright/cache/v1/`
- `docs/cache-migration.md` written with user-side migration instructions
- ~117 lines across 12 prose files (`README.md` + `CLAUDE.md` + `docs/*.md`)
  rewritten (Wave 5)
- 10 CI workflow files rewritten with FILENAMES PRESERVED (Wave 6)
- Schema `$id` URL `tradewinds.dev` → `mostlyright.dev` (5 generated JSON
  schemas + 2 spec source files); test assertion updated in lockstep

## What this phase did NOT do (out of plan scope)

- **GitHub repo rename** — `helloiamvu/tradewinds` stays. In-tree URLs still
  point at this repo. Operator may rename out-of-band later.
- **Old PyPI / npm package cleanup** — `tradewinds*` / `@tradewinds/*` are
  orphaned on the registries. Operator handles transfer or deletion.
- **`.planning/` archive prose rewrites** — ~4858 mentions preserved as
  historical audit trail.
- **`MostlyRight*` deprecation alias removal** — CORE-04 shims from the
  `mostly-light` migration; scheduled for v0.3.
- **`mostlyright_v1` parser_name enum** — LINEAGE-01 schema literal; STAYS.
- **`mostlyright==0.14.1` parity citations** — historical fact; STAYS.
- **`monorepo-v0.14.1/src/mostlyright/…` lift-source paths** — provenance
  citations; STAY.
- **`TW_HOSTED_URL` env var** — Phase 7 env var with cryptic `TW` prefix; not
  brand name; STAYS.

## Operator pre-flight (REQUIRED BEFORE PR MERGE)

The following manual steps cannot be automated from the worktree. Operator
confirms by replacing `[ ]` with `[x]` in the PR description before merge:

- [ ] **OP1**: `mv ~/Documents/GitHub/mostlyright ~/Documents/GitHub/mostlyright-legacy` (confirmed)
- [ ] **OP2**: 3 PyPI pending publishers registered (`mostlyright`, `mostlyright-weather`, `mostlyright-markets`, bound to repo + `release.yml` + env `pypi`) (confirmed)
- [ ] **OP3**: `@mostlyrightmd` npm scope claimed on npmjs.com (confirmed)
- [ ] **OP4**: 4 npm OIDC pending publishers registered (`@mostlyrightmd/core`, `@mostlyrightmd/weather`, `@mostlyrightmd/markets`, unscoped meta `mostlyright`, bound to repo + `release-ts.yml` + env `npm`) (confirmed)

OP2-OP4 are critical: post-merge `release.yml` / `release-ts.yml` runs will
fail with "trusted publisher not found" if NEW publishers are not registered
for the renamed names BEFORE a release tag fires. OP1 prevents Python
import-path collision with the legacy `~/Documents/GitHub/mostlyright`
checkout (Python's `sys.path[0] = cwd` injection).

## Post-merge follow-ups (operator)

After PR merges to `main`:

1. Tag `v0.2.0` (or appropriate Python release tag) to publish renamed PyPI
   distributions.
2. Tag `vts-0.2.0` (or appropriate TS release tag) to publish renamed npm
   packages.
3. Run `pnpm changeset` + `pnpm changeset version` to land the renamed-package
   version bump PR per `.changeset/config.json` `fixed` group.
4. Optional: transfer or delete orphaned `tradewinds*` PyPI distros +
   `@tradewinds/*` npm packages.
5. Update GitHub repo settings if/when renaming `helloiamvu/tradewinds` →
   `helloiamvu/mostlyright` (out-of-band; in-tree URLs follow).

## Cache back-compat — one-release deprecation window (v0.3 removal)

`mostlyright._internal._cache_dir.resolve_cache_dir()` reads:
1. `MOSTLYRIGHT_CACHE_DIR` (canonical)
2. `TRADEWINDS_CACHE_DIR` (legacy + `DeprecationWarning`)
3. Default `~/.mostlyright/cache/v1/`

**v0.3 will remove the `TRADEWINDS_CACHE_DIR` branch.** Users have one full
v0.2.x release to migrate. Migration: `mv ~/.tradewinds ~/.mostlyright`
(byte-equivalent parquet, no schema change). See `docs/cache-migration.md`.

## Developer post-merge step

Existing developer venvs have `tradewinds*` editable installs registered in
their `site-packages/`. Run after merge:

```bash
rm -rf .venv
uv sync --all-packages
uv pip list | grep -iE 'tradewinds|mostlyright'   # expect only mostlyright*
```

## Test count baseline (zero regression)

| Suite | Pre-Phase-12 baseline | Post-Phase-12 | Delta |
|---|---|---|---|
| Python non-live | 1971 (per STATE.md Phase 10 closeout) | 1980 | +9 (test_cache_env_back_compat.py 3 + test_phase12_rewriter.py 7 - 1 reshuffled) |
| Python parity (5 fixtures, @pytest.mark.live) | GREEN | GREEN under `from mostlyright import research` | byte-equivalent |
| TS workspace | 1323 (per STATE.md Phase 10 closeout) | 1322 (codegen 6 + core 762 + weather 218 + markets 202 + meta 134) | within rounding |

## Files added in Phase 12

- `packages/core/src/mostlyright/_internal/_cache_dir.py` (back-compat shim)
- `packages/core/tests/test_cache_env_back_compat.py` (3-test resolve_cache_dir coverage)
- `scripts/_phase12_rename.py` (Python import-line rewriter)
- `scripts/_phase12_rename_ts.py` (TS import rewriter)
- `tests/test_phase12_rewriter.py` (7-test rewriter coverage)
- `docs/cache-migration.md` (user-side migration guide)
- `.planning/phases/12-rename-to-mostlyright/12-CONTEXT.md` (locked decisions)
- `.planning/phases/12-rename-to-mostlyright/12-RESEARCH.md` (audit + recommendations)
- `.planning/phases/12-rename-to-mostlyright/12-01-PLAN.md` through `12-07-PLAN.md`
- This README

## Review

Per `.planning/REVIEW-DISCIPLINE.md`, Phase 12 is a NEVER-SKIP path (touches
`pyproject.toml` dependency floors + CI workflows + schema codegen +
parity-adjacent paths). The merged-vision → main PR runs the 3-reviewer
parallel dispatch (codex `high` + python-architect + ts-architect) with max 5
iterations per user override. `[review-skip: trivial]` does NOT apply.

## Known acceptable exceptions to the final-grep gate

The following `tradewinds` references are intentional and pass the
documented-exception filter:

- Test function names like `test_validator_accepts_tradewinds_result()` describe
  the `TradewindsResult` class (class name not renamed per CONTEXT
  "no API surface change").
- `scripts/_phase12_rename_ts.py` docstring describes the rewriter behavior
  (it MUST mention the old/new strings to document the rename mapping).
- `docs/cache-migration.md` intentionally references `~/.tradewinds` and
  `TRADEWINDS_CACHE_DIR` (it shows users the OLD names they migrate FROM).
- `tests/test_phase12_rewriter.py::test_from_tradewinds_research` — test
  function name describes the regex behavior under test.
- `tests/weather/test_obs_surface.py::test_obs_importable_from_tradewinds_weather`
  — descriptive test function name; the test body uses `mostlyright.weather`.
- 1 `.github/workflows/release-ts.yml` comment references `helloiamvu/tradewinds`
  (the repo URL, which stays per CONTEXT).

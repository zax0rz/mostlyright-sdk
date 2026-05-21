# Lane V — Vu's Lift Lane

**Owner:** Vu (@helloiamvu)
**Scope:** Lift code from `../monorepo-v0.14.1/` into the tradewinds workspace. Pin to v0.14.1 tag, not monorepo head (head is v0.17.0 with diverged behavior). CI/CD scaffolding on Day 4.

**Coordination with Lane F (Founder):** Founder authors NEW code (HTTP fetchers, cache, orchestration). You author the LIFT. You review Founder's PRs; Founder reviews yours. Codex `model_reasoning_effort=high` on PRs touching `_internal/merge/` or `research.py`.

---

## Day 0.5 — Path reconnaissance + git worktree + parity fixtures (~2 hours)

### A) Create the v0.14.1 worktree

```bash
cd /Users/robe/Downloads/mostlyright/monorepo
git fetch --tags
git worktree add ../monorepo-v0.14.1 v0.14.1
```

Verify: `cd ../monorepo-v0.14.1 && cat pyproject.toml | grep version` should print `version = "0.14.1"`.

### B) Confirm source paths

Verify these exist under `../monorepo-v0.14.1/` (commit a `roadmap/sprint0-paths.md` listing them so Day 1 has no hedges):

- `src/mostlyright/weather/{_awc,_iem,_climate,_ghcnh,_bounds,live,forecasts,client}.py`
- `src/mostlyright/{snapshot,_http,_live_http,_convert,_types,config,exceptions,versioning}.py`
- `src/mostlyright/models/` (whole directory)
- `src/mostlyright/specs/*.json` (especially `observation.json`, `climate.json`, `forecast.json`)
- `src/mostlyright/pairs.py`
- `ingest/merge/{policies.py, policies_climate.py, _sort_utils.py}`
- `ingest/sources/{awc_poller.py, iem_gap_fill.py}` — for reference pattern only (Founder's Day 0.7 spike reads these)
- `.pre-commit-config.yaml`, `pyproject.toml` (deps reference)

### C) Capture 5 parity fixtures (CRITICAL)

In a clean Python venv (NOT this workspace), install the actual published `mostlyright==0.14.1` from PyPI:

```bash
cd /tmp && python3 -m venv mostlyright-v14-venv
source mostlyright-v14-venv/bin/activate
pip install "mostlyright[parquet]==0.14.1"
```

Run 5 reference queries against `client.pairs(...)` and save the resulting DataFrames as parquet under `tests/fixtures/parity/`:

| # | station | from_date | to_date | Why this case |
|---|---|---|---|---|
| 1 | KNYC | 2025-01-06 | 2025-01-12 | Single-week NYC, clean baseline |
| 2 | KORD | 2025-04-01 | 2025-04-30 | Single-month Chicago, exercises monthly aggregation |
| 3 | KLAX | 2025-03-01 | 2025-03-31 | LST month boundary case (PST/PDT transition) |
| 4 | KMIA | 2024-12-01 | 2025-11-30 | Full-year Miami, larger volume, year boundary |
| 5 | **smaller airport** with known AWC gap | (pick from `monorepo-v0.14.1/tests/test_merge_policies_2o_s7.py` fixtures) | | **HARD requirement: AWC-gap-IEM-fills case** — verifies observation `LIVE_V1` works at parity. Without this fixture, the merge policy isn't actually being tested. |

Pickling/parquet format: use `df.to_parquet("tests/fixtures/parity/case_N_<station>_<from>_<to>.parquet")` so Day 3 can `pd.read_parquet(...)` and compare against tradewinds output.

**Commit the fixtures to the repo.** They are settlement-grade reference data; never regenerate them in CI.

### D) Open PR

Branch: `sprint0/vu-day-0-5-paths-and-fixtures`
PR title: `Day 0.5: source paths + 5 parity fixtures`
Founder reviews. Merge once approved.

---

## Day 1 — Lift `core/_internal` + parsers (~1 day)

**Pre-requisite:** Founder's Day 1 morning bootstrap PR is merged (workspace structure ready, `uv sync` works).
**Sync at start of day:** 10-min call with Founder on `tradewinds._internal/` public API surface — which symbols Founder will import from your work on Day 2.

### A) Lift shared utilities → `packages/core/src/tradewinds/_internal/`

From `../monorepo-v0.14.1/src/mostlyright/`:
- `_http.py` → `_internal/_http.py`
- `_live_http.py` → `_internal/_live_http.py`
- `_convert.py` → `_internal/_convert.py`
- `_types.py` → `_internal/_types.py`
- `config.py` → `_internal/config.py` (**rename class `TherminalConfig` → `Config`** everywhere — search-and-replace then verify all importers)
- `exceptions.py` → `_internal/exceptions.py`
- `models/` (whole dir) → `_internal/models/`
- `versioning.py` → `_internal/versioning.py`

Rename namespace `mostlyright` → `tradewinds` throughout all lifted files:
- `from mostlyright.X` → `from tradewinds._internal.X` (for utils)
- `from mostlyright.models.observation import Observation` → `from tradewinds._internal.models.observation import Observation`

### B) Lift snapshot → `packages/core/src/tradewinds/snapshot.py`

From `../monorepo-v0.14.1/src/mostlyright/snapshot.py` → `packages/core/src/tradewinds/snapshot.py`. Adapt imports through new namespace.

### C) Lift weather parsers → `packages/weather/src/tradewinds/weather/`

From `../monorepo-v0.14.1/src/mostlyright/weather/`:
- `_awc.py` → `packages/weather/src/tradewinds/weather/_awc.py`
- `_iem.py` → `packages/weather/src/tradewinds/weather/_iem.py`
- `_climate.py` → `packages/weather/src/tradewinds/weather/_climate.py`
- `_ghcnh.py` → `packages/weather/src/tradewinds/weather/_ghcnh.py`
- `_bounds.py` → `packages/weather/src/tradewinds/weather/_bounds.py`

These are PARSERS only (no HTTP). They take a dict from the public API and return our schema.

### D) Lift schemas

From `../monorepo-v0.14.1/src/mostlyright/specs/`:
- `observation.json`, `climate.json`, `forecast.json` (and any others the parsers reference) → `packages/weather/src/tradewinds/weather/specs/`

### E) Lift tests

Lift relevant tests from `../monorepo-v0.14.1/tests/` that exercise `_awc`, `_iem`, `_climate`, `_ghcnh`, `_bounds`, `_convert`, `snapshot`, `models`. Rename imports. Run `uv run pytest -m "not live" -q` → all green.

### F) Open PR

Branch: `sprint0/vu-day-1-lift-core-internal-and-parsers`
PR title: `Day 1: lift core/_internal + weather parsers + tests`
Founder reviews end of day.

---

## Day 2 — Lift both merge policies + lift `pairs.py` → `research()` (~1 day)

### A) Lift merge policies → `packages/core/src/tradewinds/_internal/merge/`

From `../monorepo-v0.14.1/ingest/merge/`:
- `policies.py` → `_internal/merge/policies.py` (observations: `LIVE_V1` = AWC > IEM > GHCNh)
- `policies_climate.py` → `_internal/merge/policies_climate.py` (climate: `LIVE_V1` source_filter={iem, acis}, NO source_priority, different sort key — **see the docstring; any drift invalidates Kalshi settlements**)
- `_sort_utils.py` → `_internal/merge/_sort_utils.py`

Adapt imports through new namespace. Add a single `_internal/merge/__init__.py` that re-exports `LIVE_V1_OBSERVATIONS = policies.LIVE_V1` and `LIVE_V1_CLIMATE = policies_climate.LIVE_V1` for clean import paths.

### B) Lift `pairs.py` → `packages/core/src/tradewinds/research.py`

From `../monorepo-v0.14.1/src/mostlyright/pairs.py` → `packages/core/src/tradewinds/research.py`.

- Adapt imports: `from mostlyright.snapshot` → `from tradewinds.snapshot`, etc.
- The function `build_pairs` becomes the implementation of `research()`. Decide naming convention:
  - Option (i): rename `build_pairs` → `research` (cleanest public API)
  - Option (ii): keep `build_pairs` internal, add `def research(...): return build_pairs(...)` wrapper
- Re-export `research` from `packages/core/src/tradewinds/__init__.py`:
  ```python
  from tradewinds.research import research
  ```
- Smoke unit test: feed `build_pairs()` (or `research()` if renamed) a list of fixture rows and assert the returned dict shape matches v0.14.1's `pairs()` row structure.

### C) Lift `pairs.py` tests

From `../monorepo-v0.14.1/tests/`: find `test_pairs*.py`, `test_merge_policies_2o_s7.py`. Lift; rename imports. Run `uv run pytest -m "not live" -q` → all green.

### D) Open PR

Branch: `sprint0/vu-day-2-lift-merge-and-research`
PR title: `Day 2: lift LIVE_V1 (obs + climate) + pairs.py → research()`
**Codex `model_reasoning_effort=high` review REQUIRED** (parity-critical).
Founder reviews + Codex.

---

## Day 3 — Parity test (HARD GATE) + pair-debugging (~half day each)

### A) Implement parity test

Write `tests/test_parity.py`:

```python
# pseudocode
import pandas as pd
import tradewinds as tw

FIXTURES = [
    {"station": "KNYC", "from_date": "2025-01-06", "to_date": "2025-01-12", "file": "case_1_KNYC_20250106_20250112.parquet"},
    # ... 5 total
]

@pytest.mark.parametrize("fix", FIXTURES)
def test_parity_with_v0_14_1(fix):
    expected = pd.read_parquet(f"tests/fixtures/parity/{fix['file']}")
    actual = tw.research(
        station=fix["station"],
        from_date=fix["from_date"],
        to_date=fix["to_date"],
        as_dataframe=True,
    )
    pd.testing.assert_frame_equal(expected, actual, check_dtype=True, check_exact=True)
```

### B) Pair-debug with Founder on failures

This is the make-or-break day. Treat as joint debug rather than lane-split. **Sprint 0 ships only if all 5 parity tests pass.**

### C) Open PR

Branch: `sprint0/vu-day-3-parity-test`
PR title: `Day 3: parity test against v0.14.1 — HARD GATE`
Founder reviews + Codex.

---

## Day 4 — CI/CD scaffolding (~half day)

### A) GitHub Actions

Write `.github/workflows/ci.yml`:
- Triggers: pull_request, push to main
- Matrix: Python 3.11, 3.12, 3.13
- Steps: checkout, install uv, `uv sync`, `uv run ruff check`, `uv run ruff format --check`, `uv run pytest -m "not live" -q`

Write `.github/workflows/release.yml`:
- Trigger: manual workflow_dispatch with `package` input (one of: tradewinds, tradewinds-weather, tradewinds-markets)
- Steps: checkout, install uv, `uv build --package <input>`, `uv publish --package <input>` with PYPI_TOKEN secret

### B) Open PR

Branch: `sprint0/vu-day-4-ci-cd`
PR title: `Day 4: CI/CD workflows`
Founder reviews.

### C) Validation triage support

Help Founder prep `roadmap/sprint0-validation.md` template responses as N=2 outreach replies come in. Update yes/no counts.

---

## Day 4 + 7 days — Sprint 0.5 readiness

If N=3 yes signals → Sprint 0.5 starts. Your first task in Sprint 0.5 is the Kalshi metadata port from `therminal/therminal-ingest/src/sources/kalshi/` (TypeScript reference). Endpoints documented in `therminal/research/notes/research-kalshi-api.md`. No auth required. Three options to evaluate before starting:
- (a) Port TS to Python (durable, ~1-2 days)
- (b) Depend on `kalshi-py` 2.0.6.6 PyPI (stale, ~half day)
- (c) Depend on `kalshi-python` 2.1.4 PyPI (similar staleness)

Default plan: (a). Discuss with Founder.

If < N=3 → STOP, debrief with Founder. Consider Approach C (in-place mostlyright v0.15) per design doc Open Question #8.

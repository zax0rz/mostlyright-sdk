# tradewinds

Local-first Python SDK for quants researching prediction-market weather settlements. No hosted backend — calls public APIs (AWC, IEM, GHCNh, NWS CLI, Kalshi) directly. Sprint 0 v0.1.0 ships observations + NWS CLI climate + the `research()` join, byte-equivalent to `mostlyright==0.14.1`'s `client.pairs()`.

## Project structure

- `packages/core/` → `tradewinds` PyPI distribution: `research()`, `snapshot`, shared `_internal/` utils. Also contains `tradewinds/_v02/` — the v0.2 foundations port (TimePoint, Schema, exceptions, formats; see [`docs/design.md`](docs/design.md)).
- `packages/weather/` → `tradewinds-weather` PyPI distribution: AWC/IEM/GHCNh/NWS CLI clients + historical fetchers + cache
- `packages/markets/` → `tradewinds-markets` PyPI distribution: Kalshi/Polymarket (v0.0.1 placeholder; v0.1.0 in Sprint 0.5)
- `.planning/` → **THE canonical plan.** GSD-managed: ROADMAP.md (4 phases), PROJECT.md, REQUIREMENTS.md, STATE.md, per-phase PLAN.md + RESEARCH.md.
- `roadmap/` → Historical (lane-based Sprint 0 plan, archived to `roadmap/_archive/`).
- `docs/` → Forward-looking design. [`docs/design.md`](docs/design.md) is the v0.2 foundations spec (originally drafted as standalone "mostlyright-mcp v1," merged into tradewinds 2026-05-21).
- `tests/` → pytest, includes `@pytest.mark.live` for network tests (excluded from CI)

**Branch workflow:** `main` only receives PRs from `merged-vision` (master integration branch). All sprint + feature work branches off `merged-vision`, runs Codex self-review, merges back. One big PR from `merged-vision` → `main` when integration is ready.

## Commands

```bash
uv sync                                    # install workspace + dev deps
uv run pytest -m "not live" -q             # fast tests, no network
uv run pytest -q                           # all tests including live
uv run ruff check --fix .                  # lint + autofix
uv run ruff format .                       # format
uv build                                   # build all three packages
```

## Collaboration rules (Sprint 0 = lane-split)

**Default reviewer: @helloiamvu** (Vu).

- **Two parallel lanes:**
  - **Lane F (Founder):** new code — HTTP fetchers, cache, orchestration, README, outreach.
  - **Lane V (Vu):** lift from `monorepo-v0.14.1/` — parsers, merge policies, `pairs.py` → `research.py`, CI/CD.
  - **Cross-review:** each lane authors its own PRs; the OTHER lane reviews.
  - **Review discipline:** Every PR runs the two-reviewer loop (Codex + Python Architect) before merging to `merged-vision`. See [`.planning/REVIEW-DISCIPLINE.md`](.planning/REVIEW-DISCIPLINE.md) for the loop mechanics, severity gate, never-skip path list, and trivial-skip rules.
- **Feature branches per work unit.** Name: `sprint0/<lane>-<task>`. Examples: `sprint0/vu-lift-core-internal`, `sprint0/founder-historical-fetcher-awc`.
- **Never commit directly to main.** Always branch + PR.
- **TDD mandatory.** Write tests first. RED → GREEN → REFACTOR. 80% coverage minimum.
- **Pre-commit + pre-push hooks mandatory.** No `--no-verify`. Fix the underlying issue. Pre-commit runs fast checks (ruff, format, whitespace, YAML/TOML validation); pre-push runs `pytest -m "not live"`. Install both with `uv run pre-commit install && uv run pre-commit install --hook-type pre-push`.
- **All API calls direct from SDK.** No `api.mostlyright.md`, no hosted-API client calls anywhere in `tradewinds.*`. Verified via grep on built wheels before publish.

## Data + parity rules

- **Source priority (LIVE_V1 observations):** AWC > IEM > GHCNh. NCEI excluded from live (latency).
- **Climate LIVE_V1:** `source_filter={iem, acis}`, NO source_priority. Dedup by `(station_code, observation_date)`: keep highest `report_type_priority` with STRICT `>` (not `>=`), first-seen wins at equal priority. Byte-faithful port of `_dedup_climate_rows` from `monorepo-v0.14.1/ingest/storage/parquet.py:477-494` (there is NO separate `policies_climate.py` file in v0.14.1). Lives at [`packages/core/src/tradewinds/_internal/merge/climate.py`](packages/core/src/tradewinds/_internal/merge/climate.py). Any drift here invalidates every historical Kalshi NHIGH/NLOW settlement. Treat as load-bearing.
- **Any change to merge logic MUST update parity fixtures** in `tests/fixtures/parity/`.
- **v0.14.1 contract:** `research(station, from_date, to_date)` returns byte-equivalent output to `mostlyright==0.14.1`'s `client.pairs(...)`. Columns: `date, station, cli_high_f, cli_low_f, obs_high_f, obs_low_f, obs_high_at, obs_low_at` (+ `fcst_*` if `include_forecast=True`).
- **Lift source pinned to v0.14.1 tag.** All "lift from monorepo" instructions refer to `../monorepo-v0.14.1/` (git worktree from the v0.14.1 tag), NOT monorepo head (which is at v0.17.0 with diverged behavior — Open-Meteo removal, settlement_v1 intake, etc.).
- **Cache:** `$HOME/.tradewinds/cache/observations/{station}/{year}/{month}.parquet`. `filelock`-guarded. Cache-skip when queried month equals current LST month for that station (current month is incomplete; elapsed months stable). No user-visible `fresh=` kwarg.
- **No preprocessing in v0.1.0.** Preserve `raw_metar` in observation rows so MetPy re-parse works (Vojtech's documented workflow). RH/feels_like preprocessing comes in Sprint 0.5+.
- **Raw + preprocessed split:** quants want both. Default fetch returns raw; preprocessing is opt-in via explicit transform calls (Sprint 0.5+).

## Testing

- `uv run pytest -m "not live" -q` is the default fast run. Lives in CI.
- `@pytest.mark.live` decorator for tests that hit real public APIs. Skipped in CI per testing playbook; run manually before each publish.
- **Parity test (`tests/test_parity.py`) is the HARD GATE for Sprint 0.** Sprint 0 ships only if all 5 fixtures byte-match `mostlyright==0.14.1` output. Fixtures captured at Day 0.5 (Lane V).
- 80% coverage minimum on new code (`research`, `_fetchers`, `cache`, merge wrappers). Lifted code retains its monorepo coverage.

## License

MIT. See [LICENSE](LICENSE).

## Skill routing

When the user's request matches an available skill, invoke it via the Skill tool.

Key routing rules:
- Product ideas, brainstorming → invoke `/office-hours`
- Bugs, errors, "why is this broken" → invoke `/investigate`
- Ship, deploy, push, create PR → invoke `/ship`
- QA, test the site, find bugs → invoke `/qa`
- Code review, check my diff → invoke `/review`
- Update docs after shipping → invoke `/document-release`
- Architecture review → invoke `/plan-eng-review`

<!-- GSD:project-start source:PROJECT.md -->
## Project

**tradewinds**

A local-first Python SDK for quants researching prediction-market weather contracts (Kalshi NHIGH/NLOW, daily temperature high/low). Calls public APIs (AWC, IEM, GHCNh, NWS CLI) directly — no hosted backend. Subsumes the user's prior `mostlyright` package, adds temporal-safety primitives and source-identity invariants from day 1, and reserves a seam for an MCP server in v0.2.

**Core Value:** `research(contract, station, from_date, to_date)` returns clean, leakage-free, source-identified training pairs that backtest the same way they trade — and any train/infer source mismatch errors loudly instead of silently corrupting a model.

### Constraints

- **Tech stack:** Python 3.11+. uv workspace. `httpx`, `pandas`, `pyarrow`, `filelock`, `jsonschema`, `hypothesis` (dev). No FastAPI, no Docker, no hosted infra in v0.1.
- **Timeline:** 14 calendar days from Day 1. Phase A (parity lift) Days 1-4, Phase B (core+catalog) Days 5-14. v0.2 (MCP) is a later milestone.
- **Execution model:** Two-lane parallel — Lane V (Vu) lifts from `monorepo-v0.14.1/`, Lane F (Founder) builds new code. Cross-review mandatory. Every PR runs the two-reviewer loop (Codex `high` + Python Architect) per [`.planning/REVIEW-DISCIPLINE.md`](.planning/REVIEW-DISCIPLINE.md) — applies to ALL branches, not just parity-critical paths.
- **Testing discipline:** TDD mandatory (RED → GREEN → REFACTOR). Pre-commit hooks; no `--no-verify`. ≥90% branch coverage on `tradewinds.core`. 80% line coverage on `catalog/` and adapter wrappers. Lifted `_vendor/` code retains its monorepo coverage.
- **Parity gate (HARD):** Day 3 — all 5 byte-equivalent parity fixtures vs `mostlyright==0.14.1` must pass. Sprint 0 ships only if green.
- **License:** MIT (matches mostlyright, lowest friction for external adoption).
- **No direct commits to main:** every change goes through PR + cross-lane review.
<!-- GSD:project-end -->

<!-- GSD:stack-start source:research/STACK.md -->
## Technology Stack

## TL;DR — The pinned floors
# All three packages; runtime deps
# Dev group (workspace root only)
# Deferred to v0.2 (do NOT add to v0.1 deps; reserve seam):
## Recommended Stack
### Core (Runtime) Technologies
| Technology | Current Version | Recommended Floor | Purpose | Why |
|------------|-----------------|-------------------|---------|-----|
| **Python** | 3.13.x (3.14 GA) | **`>=3.11`** | Language | Already locked in PROJECT.md. 3.11 minimum needed for pandas 3.0-readiness and `tomllib`. 3.13 is the typical dev target in May 2026. |
| **httpx** | 0.28.1 (Dec 2024) | **`>=0.28,<1.0`** | Sync + async HTTP client for IEM/AWC/NWS/GHCNh calls | Drop-in successor to `requests`, supports both sync and async with the same API. v1.0 is in dev (`1.0.dev3` available) but not stable; pin below 1.0 until it ships. The bump from `0.27` is essentially free (mostly bug fixes since Feb 2024). |
| **pandas** | 3.0.3 (May 2026) | **`>=2.2,<3.0`** | DataFrame for `research()` return value, parquet roundtrip | **PARITY-CRITICAL.** Pandas 3.0 (Jan 2026) ships breaking changes: CoW enforced, `object` → `str` dtype shift, datetime resolution inference (`ns` → `us`), `M`/`Q`/`Y` offset aliases removed. The byte-equivalent parity gate against `mostlyright==0.14.1` was built on 2.x. Stay on 2.2 for v0.1.0; do the pandas-3.0 migration as an **explicit v0.2 work item** with parity fixtures re-captured. |
| **pyarrow** | 24.0.0 (Apr 2026) | **`>=18,<25`** | Parquet read/write, Arrow-backed columns for cache | Current bump from `>=17` to `>=18` is safe (no breaking surface for our parquet usage). Pandas 3.0 needs pyarrow >=7, so we're well clear regardless. |
| **jsonschema** | 4.26.0 (Jan 2026) | **`>=4.25,<5`** | Validate IEM forecast specs (`_forecast_schema.py`) + canonical `schema.observation.v1` / `schema.forecast.iem_mos.v1` / `schema.settlement.cli.v1` | Stable 4.x line for years; Draft 2020-12 support is what we need. No 5.x on horizon. |
| **filelock** | 3.29.0 (Apr 2026) | **`>=3.20,<4`** | Cross-process lock for `$HOME/.tradewinds/cache/.../month.parquet` writes | Battle-tested in pip/uv/tox internals. The 3.29 release improved Windows stale-lock detection — worth picking up the floor bump. |
### Supporting Libraries (Dev / Test)
| Library | Current Version | Recommended Floor | Purpose | When to Use |
|---------|-----------------|-------------------|---------|-------------|
| **pytest** | 9.0.3 (Apr 2026) | **`>=8.4,<10`** | Test runner | Allow 8.4.x AND 9.x. pytest 9 is current but 8.4 is what every existing tutorial and CI image ships; users running `uv sync` shouldn't be forced to 9. |
| **pytest-cov** | 6.x | `>=6.0,<8` | Coverage reporting → CI gate | Branch coverage on `tradewinds.core` (≥90% per ROADMAP). |
| **pytest-recording** | 0.13.4 (May 2025) | `>=0.13.4` | **Recorded-fixture integration tests for IEM/AWC/CLI/GHCNh adapters.** Captures real HTTP responses to YAML cassettes; replays in CI. | This is the canonical choice for VCR-style testing in 2026. Wraps `vcrpy>=8.0`. See §Testing strategy below for the httpx caveat. |
| **hypothesis** | 6.152.9 (May 2026) | `>=6.140,<7` | Property-based tests for `KnowledgeView` temporal invariants, source-identity invariant, `LeakageDetector` audit semantics | Mandatory per ROADMAP Day 5 + Day 12. The library has been at 6.x for years; no 7.x is planned. |
| **ruff** | 0.15.14 (May 2026) | `>=0.13,<1` | Lint + format (replaces black, isort, flake8, pyupgrade) | Releases ~weekly; the floor is generous on purpose. Floor at 0.13 because RUF-rule renumbering settled there. Pre-1.0 still but stable in practice for years now. |
| **mypy** | 1.18.x (Apr 2026) | `>=1.18,<2` | Static type checking on `tradewinds.core` public surface | See §Type checking strategy — **strict on `core/`, lax on `_vendor/`**. |
| **pre-commit** | 4.x | `>=4,<5` | Run ruff + mypy on every commit; ROADMAP makes this mandatory ("no `--no-verify`") | Already in workspace root pyproject; floor bump to 4.x. |
### Deferred to v0.2 — Reserve the Seam
| Library | Current Version | Purpose | Why Deferred |
|---------|-----------------|---------|--------------|
| **mcp** (Anthropic SDK) | **1.27.1 (May 2026)** | MCP server for `tradewinds.mcp` — exposes `pull_pairs`, `validate_dataframe`, `catalog_search` as MCP tools | ROADMAP defers all MCP work to v0.2. v0.1 ships `packages/mcp/` as stub only. **When v0.2 starts:** use FastMCP pattern (`from mcp.server.fastmcp import FastMCP`) — recommended for ~80% of cases, decorator-based tool registration, automatic Pydantic-model output handling. For DataFrame returns, serialize to one of our existing formats (`toon`/`parquet`/`json`) inside the tool function. Python 3.10+ required (we're at 3.11+ — fine). |
### Optional Extras (Already in Current Scaffold)
## Installation Commands
# Workspace install (dev)
# Build all three packages
# Test (fast, no network)
# Test with cassette refresh (live; pre-publish only)
# Lint + format
# Type check (strict on core only — see §Type checking)
# Publish (trusted publishing from GH Actions on `v*` tags only)
## uv Workspace Layout — The Namespace Question
### Why hatchling, not the uv build backend
### The layout that works (and that you already have)
### Workspace-level dev deps
## Testing Strategy — Why pytest-recording (with one caveat)
| Tool | Approach | Verdict for tradewinds |
|------|----------|-----------------------|
| **`pytest-recording` + `vcrpy>=8`** | Record real HTTP, replay from YAML cassettes | **Choose this.** Recorded fixtures match how mostlyright tested. Real responses, including edge cases (timeouts, malformed responses), live in version control. |
| **`pytest-httpx`** (0.36.2 current) | Pure mocking — you write the response | Use **alongside** pytest-recording for unit tests of error paths (e.g., "what if AWC returns 503?"). Not a substitute for integration testing. |
| **`respx`** | Pure mocking, route-based | Skip. pytest-httpx covers the same ground with cleaner ergonomics for our case. |
### The httpx caveat in VCR.py
### Recommended cassette layout
### Filtering sensitive data in cassettes
# tests/conftest.py
## Type Checking Strategy
### Tiered configuration (`pyproject.toml` workspace root)
# Strict on tradewinds.core only (the load-bearing safety layer)
# Strict-ish on research.py (the parity-critical join)
# Lax on adapters (calling untyped third-party HTTP)
# Ignore _vendor entirely (it's lifted; not our problem in v0.1)
## Pre-commit Configuration
## CI/CD — GitHub Actions, Trusted Publishing
# .github/workflows/release.yml
### Three PyPI trusted-publishing registrations
### CI test workflow (separate)
# .github/workflows/test.yml
## Alternatives Considered
| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| `httpx` | `requests` | Sync-only legacy code. tradewinds adapters might go async in v0.2 (parallel adapter fetches) — staying on httpx now is path-of-least-resistance for that future. |
| `hatchling` | `uv_build` | When uv_build adds full PEP 420 support and you want pyproject-only tooling. **Not now** — wait. |
| `hatchling` | `setuptools` | Existing setuptools-heavy project. Not us. Hatchling is the modern hatch.toml-free choice. |
| `pytest-recording` (vcrpy) | `pytest-httpx` only | Pure unit tests with no network coverage goal. We need real HTTP responses captured (catches parser regressions when upstream APIs change shape). Use pytest-httpx **additionally** for error-path tests. |
| `mypy` | `ty` (Astral's new type checker) | ty is alpha-quality as of May 2026. Wait until 1.0. mypy remains the safe default for SDK libraries. |
| `mypy` | `pyright` | Pyright is great but it's a node binary — adds a JS toolchain dep. mypy is pure Python and works inside the uv-managed venv. For an SDK, simpler wins. |
| `pandas 2.2` floor | `pandas 3.0` floor | After v0.2 when parity fixtures are re-captured against pandas-3.0 output. Do **not** do this in v0.1. |
| Pydantic v2 (data validation) | jsonschema | Pydantic is a great alternative to jsonschema for runtime validation. We're choosing jsonschema because: (a) mostlyright==0.14.1 lifts already use it; (b) JSON Schema is the cross-language spec (matters for MCP v0.2 tool schemas). Don't add Pydantic in v0.1; reconsider for v0.2 when MCP arrives (Pydantic plays well with FastMCP). |
## What NOT to Use
| Avoid | Why | Use Instead |
|-------|-----|-------------|
| **`requests`** | Sync-only, no native async, no HTTP/2. The whole industry has moved off it for new code. | `httpx` |
| **`black` + `isort` + `flake8`** | Three tools, slow, overlapping. ruff replaces all three with one Rust binary. | `ruff check` + `ruff format` |
| **`poetry`** | Lock-file format is non-standard, slow, conflicts with PEP 621 in subtle ways, no first-class workspace support comparable to uv | `uv` (already chosen, correctly) |
| **`pdm`** | Smaller ecosystem than uv, slower. Defensible 2024 choice; superseded by uv in 2026. | `uv` |
| **`setuptools` for new packages** | Heavy, opinion-rich, `setup.py` legacy. Hatchling is the modern PEP 621 baseline. | `hatchling` (already chosen) |
| **`Pipenv`** | Effectively abandoned. | `uv` |
| **`tox`** | Workspace install + matrix testing handled by uv + GitHub Actions matrix. Tox adds a layer. | `uv` + GH Actions `matrix:` |
| **`pandas` >= 3.0 in v0.1** | Breaking dtype/CoW changes ([whatsnew/v3.0.0](https://pandas.pydata.org/docs/dev/whatsnew/v3.0.0.html)) will invalidate parity fixtures. | `pandas>=2.2,<3.0`; plan pandas-3.0 migration as v0.2 work |
| **`pyarrow` directly imported across codebase** | Couples cache impl to a heavy dep. | Import inside `weather/cache.py` only; keep `core` pyarrow-free. |
| **`pickle` for cache** | Security, version-fragility, opaque. | `parquet` via pyarrow (already chosen) |
| **`asyncio` in v0.1 catalog adapters** | Adds complexity; mostlyright v0.14.1 is sync; parity is byte-equivalent. | Stay sync in v0.1. Revisit async in v0.2 if multi-station fetches become a bottleneck — httpx supports both APIs. |
| **`FastAPI`** | Explicitly out of scope per PROJECT.md. No hosted backend in v0.1. | (nothing — we don't need a web server) |
| **`pydantic` everywhere** | Don't proliferate it across `_vendor/` (parity-critical lift). | jsonschema for v0.1; introduce Pydantic only in `core/` if FastMCP requires it in v0.2. |
| **`uv_build` backend** | Doesn't fully support PEP 420 implicit namespace packages yet (May 2026). | `hatchling` |
| **Custom HTTP retry/backoff code** | Wheel reinvention. | `httpx` has `transport.retries`; use it. |
## Stack Patterns by Variant
### If the parity gate fails on pandas-2.2 → 2.x interaction
- Pin even tighter: `pandas==2.2.3` (the last 2.2 patch).
- Document in CHANGELOG and ROADMAP.
- v0.2 work item: re-capture parity fixtures against pandas 3.0; bump floor in v0.2.
### If a downstream user reports VCR.py async streaming bugs
- Document constraint: tradewinds catalog adapters use **buffered httpx responses only**, no streaming.
- If async is added in v0.2, validate VCR.py >= 8.2 (assuming an 8.2 lands by then) before merging.
### If MCP v0.2 work needs DataFrame I/O via FastMCP
- Serialize DataFrames at the tool boundary using one of our existing formats (`toon` is compact, JSON-compatible).
- Don't return `pd.DataFrame` directly from MCP tools — FastMCP wraps Pydantic/TypedDict; pandas isn't first-class.
- Pattern: tool returns `{"format": "toon", "data": <string>, "schema": "schema.observation.v1"}`.
### If three-package layout starts feeling overengineered
- All three packages can be merged into one without API change — they share the `tradewinds.*` namespace already.
- Cost of merging later: rewrite three PyPI registrations + bump major versions.
- Cost of keeping the split: ~100 lines of pyproject.toml triplication.
- **Recommendation:** stay split. The split has the cleanest deprecation story for vertical N+1 (sports, politics) which the design anticipates.
## Version Compatibility Matrix
| Package | Min | Max (exclusive) | Notes |
|---------|-----|-----------------|-------|
| Python | 3.11 | 3.15 | 3.14 ships fine; 3.15 untested |
| httpx | 0.28 | 1.0 | 1.0 in dev, pin below until stable |
| pandas | 2.2 | 3.0 | 3.0 has dtype/CoW breaks; parity is on 2.x |
| pyarrow | 18 | 25 | 24.0 current; 23/22/21 also fine |
| jsonschema | 4.25 | 5.0 | No 5.0 announced |
| filelock | 3.20 | 4.0 | No 4.0 announced |
| pytest | 8.4 | 10.0 | 9.0.3 current; supporting 8.4 keeps tutorial-CI compatibility |
| hypothesis | 6.140 | 7.0 | Years of 6.x; no 7.0 announced |
| ruff | 0.13 | 1.0 | Pre-1.0 but stable in practice; floor is generous |
| mypy | 1.18 | 2.0 | 1.x line stable since 2023 |
| mcp (v0.2 only) | 1.27 | 2.0 | Anthropic SDK; v1.27 is current as of May 2026 |
- pandas 2.2.x + pyarrow 24.0: ✓ (pyarrow supports pandas 2.x and 3.x)
- httpx 0.28 + vcrpy 8.x: ✓ (buffered responses only — no streaming)
- jsonschema 4.26 + Python 3.13: ✓
- hatchling + PEP 420 namespace packages: ✓ (production-tested for years)
## Decisions Already Locked — Confirmed Correct
| Locked decision | Status |
|-----------------|--------|
| Python 3.11+ | ✓ Confirmed. 3.11 is the floor pandas 3.0 requires; aligns us for the eventual pandas-3.0 migration. |
| uv workspace, three packages | ✓ Confirmed. The hatchling + src/ + PEP 420 layout works in 2026. |
| MIT license | ✓ Confirmed. Lowest friction for SDK adoption; matches mostlyright. |
| `httpx` over `requests` | ✓ Confirmed. Industry default for new Python HTTP code. |
| `pandas` + `pyarrow` | ✓ Confirmed for v0.1. Caveat: stay on pandas 2.2; 3.0 migration is v0.2. |
| `filelock` for cache | ✓ Confirmed. Battle-tested; 3.29 brings Windows improvements (cheap floor bump). |
| `jsonschema` for validation | ✓ Confirmed for v0.1. Reconsider Pydantic for v0.2 MCP work. |
| `hypothesis` for property tests | ✓ Confirmed. Only mainstream choice in Python. |
| No FastAPI, no Docker | ✓ Confirmed. Local-first SDK; no servers. |
| MCP deferred to v0.2 | ✓ Confirmed. The `mcp` SDK at 1.27.1 is mature enough for v0.2; deferring avoids the FastMCP + Pydantic dep proliferation in v0.1. |
## Decisions to Consider Revisiting (Soft Flags)
## Sources
### Context7 / Official Docs (HIGH confidence)
- [pandas 3.0.0 whatsnew](https://pandas.pydata.org/docs/dev/whatsnew/v3.0.0.html) — breaking changes, CoW enforcement, string dtype, datetime resolution
- [pandas 3.0.3 (current)](https://pandas.pydata.org/) — May 11, 2026 release
- [httpx PyPI](https://pypi.org/project/httpx/) — 0.28.1 current
- [pyarrow PyPI](https://pypi.org/project/pyarrow/) — 24.0.0 current, Apr 21 2026
- [jsonschema 4.26.0](https://python-jsonschema.readthedocs.io/en/stable/) — Jan 7, 2026
- [filelock 3.29.0](https://py-filelock.readthedocs.io/en/latest/changelog.html) — Apr 19, 2026
- [ruff 0.15.14](https://pypi.org/project/ruff/) — May 21, 2026
- [hypothesis 6.152.9](https://pypi.org/project/hypothesis/) — May 19, 2026
- [pytest 9.0.3](https://pypi.org/project/pytest/) — Apr 7, 2026
- [pytest-httpx 0.36.2](https://pypi.org/project/pytest-httpx/) — Apr 9, 2026
- [mcp 1.27.1](https://pypi.org/project/mcp/) — May 8, 2026 (Anthropic Python SDK)
- [uv workspaces docs](https://docs.astral.sh/uv/concepts/projects/workspaces/) — current canonical workspace layout
- [astral-sh/trusted-publishing-examples](https://github.com/astral-sh/trusted-publishing-examples) — current GH Actions YAML for uv + PyPI trusted publishing
### Verified via WebSearch (MEDIUM confidence)
- [uv PEP 420 namespace package limitations](https://github.com/astral-sh/uv/issues/12832) — uv_build doesn't fully support namespace packages yet; hatchling does
- [ribeirompl-soldersmith/uv-namespace-package-workspace](https://github.com/ribeirompl-soldersmith/uv-namespace-package-workspace) — working example of uv workspace + shared namespace
- [PDEP-10 pandas + pyarrow](https://pandas.pydata.org/pdeps/0010-required-pyarrow-dependency.html) — pyarrow is NOT required even in pandas 3.0
- [vcrpy httpx async streaming bug](https://github.com/kevin1024/vcrpy/issues/597) — fixed in 8.1.x; documented constraint
- [Astral-sh ruff-pre-commit](https://github.com/astral-sh/ruff-pre-commit) — current pre-commit hook setup
- [mypy strict mode flags](https://mypy.readthedocs.io/en/stable/config_file.html) — gradual strictness approach
### MCP SDK (HIGH confidence via official GitHub)
- [modelcontextprotocol/python-sdk](https://github.com/modelcontextprotocol/python-sdk) — FastMCP pattern, Pydantic integration, structured output via TypedDict/BaseModel
<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->
## Conventions

Conventions not yet established. Will populate as patterns emerge during development.
<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->
## Architecture

Architecture not yet mapped. Follow existing patterns found in the codebase.
<!-- GSD:architecture-end -->

<!-- GSD:skills-start source:skills/ -->
## Project Skills

No project skills found. Add skills to any of: `.claude/skills/`, `.agents/skills/`, `.cursor/skills/`, or `.github/skills/` with a `SKILL.md` index file.
<!-- GSD:skills-end -->

<!-- GSD:workflow-start source:GSD defaults -->
## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:
- `/gsd-quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd-debug` for investigation and bug fixing
- `/gsd-execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->

<!-- GSD:profile-start -->
## Developer Profile

> Profile not yet configured. Run `/gsd-profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->

# Stack Research

**Domain:** Local-first Python SDK (data-quant tooling, prediction-market weather research)
**Project:** tradewinds — three-package uv workspace, v0.1.0
**Researched:** 2026-05-21
**Confidence:** HIGH (most decisions Context7/PyPI-verified) / MEDIUM (uv-workspace namespace packaging — limited 2026 prescriptive docs)

---

## TL;DR — The pinned floors

```toml
# All three packages; runtime deps
"httpx>=0.28,<1.0"          # 0.28.1 is current; 1.0 not yet stable
"pandas>=2.2,<3.0"          # parity work; 3.0 has breaking dtype/CoW changes
"pyarrow>=18,<25"           # 24.0.0 current; pandas 3.0 needs >=7
"jsonschema>=4.25,<5"       # 4.26.0 current
"filelock>=3.20,<4"         # 3.29.0 current

# Dev group (workspace root only)
"pytest>=8.4,<10"           # 9.0.3 current; 8.4.x is LTS-shaped, ours
"pytest-cov>=6.0,<8"
"pytest-recording>=0.13.4"  # VCR-powered, httpx OK
"hypothesis>=6.140,<7"      # 6.152.9 current
"ruff>=0.13,<1"             # 0.15.14 current (releases ~weekly)
"mypy>=1.18,<2"             # gradual strict, see §Type checking
"pre-commit>=4,<5"

# Deferred to v0.2 (do NOT add to v0.1 deps; reserve seam):
"mcp>=1.27,<2"              # 1.27.1 current — official Anthropic SDK
```

The current scaffold's existing pins (`httpx>=0.27`, `pandas>=2.2`, `pyarrow>=17`, `jsonschema>=4.21`, `filelock>=3.12`) are all **still inside the support window** and are **fine to ship as-is**. Recommended bumps below are floor-raises, not breakage fixes.

---

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

The `[parquet]` extra (`pyarrow + pandas`) is already declared in all three packages. **Keep as-is.** This matches `mostlyright==0.14.1`'s pattern and lets non-DataFrame consumers (rare but possible — a JSON-only MCP client, e.g.) skip the heavy deps.

---

## Installation Commands

```bash
# Workspace install (dev)
uv sync --all-packages --all-extras

# Build all three packages
uv build --all

# Test (fast, no network)
uv run pytest -m "not live" -q

# Test with cassette refresh (live; pre-publish only)
uv run pytest --record-mode=once -m "live or not live"

# Lint + format
uv run ruff check --fix .
uv run ruff format .

# Type check (strict on core only — see §Type checking)
uv run mypy packages/core/src/tradewinds/core

# Publish (trusted publishing from GH Actions on `v*` tags only)
uv build && uv publish
```

---

## uv Workspace Layout — The Namespace Question

**The current scaffold layout (`packages/{core,weather,markets}/src/tradewinds/`) with hatchling is CORRECT for 2026** — and it's the only safe choice. Confirming this is important enough to call out:

### Why hatchling, not the uv build backend

uv 0.x ships its own build backend (`uv_build`), but as of May 2026 [it does not fully support PEP 420 implicit namespace packages](https://github.com/astral-sh/uv/issues/12832) without `__init__.py`. **The current scaffold's `build-backend = "hatchling.build"` is the right call** — hatchling handles namespace packages cleanly and has for years.

### The layout that works (and that you already have)

```
tradewinds/
├── pyproject.toml                          # workspace root, hatchling, bypass-selection=true
├── packages/
│   ├── core/
│   │   ├── pyproject.toml                  # name="tradewinds", packages=["src/tradewinds"]
│   │   └── src/
│   │       └── tradewinds/                 # NO __init__.py here (or empty marker only; PEP 420)
│   │           ├── __init__.py             # core package's own __init__ — exports research(), core types
│   │           ├── core/
│   │           ├── research.py
│   │           └── _internal/
│   ├── weather/
│   │   ├── pyproject.toml                  # name="tradewinds-weather", packages=["src/tradewinds"]
│   │   └── src/
│   │       └── tradewinds/                 # SAME top-level — namespace shared
│   │           └── weather/                # sub-package
│   │               ├── __init__.py
│   │               ├── catalog/
│   │               ├── _vendor/
│   │               └── cache.py
│   └── markets/
│       ├── pyproject.toml                  # name="tradewinds-markets", packages=["src/tradewinds"]
│       └── src/
│           └── tradewinds/
│               └── markets/
│                   ├── __init__.py
│                   └── catalog/
```

**Critical rule (the gotcha):** the top-level `src/tradewinds/` directory in `packages/weather/` and `packages/markets/` **must not declare itself a regular package** that conflicts with `core/`'s `__init__.py`. Two correct strategies:

1. **PEP 420 implicit namespace (cleanest):** only `packages/core/src/tradewinds/__init__.py` exists. The weather and markets packages have NO `__init__.py` at `src/tradewinds/` — they only have `__init__.py` at `src/tradewinds/weather/` and `src/tradewinds/markets/`. Python merges the three at import time.
2. **Explicit re-export from core:** `core` is the only package with `src/tradewinds/__init__.py`. Weather and markets register themselves there via entry points. More complex; not recommended for three packages.

**Recommendation:** go with strategy 1 (PEP 420). The current scaffold's pyproject `[tool.hatch.build.targets.wheel] packages = ["src/tradewinds"]` is compatible with this; hatchling will package whatever is under `src/tradewinds/` for each wheel, and since weather's wheel only contains `src/tradewinds/weather/...`, no file collision occurs at install time.

**Action item for Lane V Day 1:** verify by `uv build --all` then unzipping each wheel — confirm no wheel contains a `tradewinds/__init__.py` except `tradewinds-*.whl` (core). If two wheels both ship `tradewinds/__init__.py` → conflict → resolve before shipping.

### Workspace-level dev deps

The current workspace `pyproject.toml` uses `[dependency-groups] dev = [...]` (PEP 735). This is the **right modern approach** — keeps dev deps out of the published metadata of any individual package while making `uv sync` install them.

Add to the workspace dev group:
```toml
[dependency-groups]
dev = [
    "pytest>=8.4",
    "pytest-cov>=6.0",
    "pytest-recording>=0.13.4",
    "hypothesis>=6.140",
    "ruff>=0.13",
    "mypy>=1.18",
    "pre-commit>=4",
]
```

---

## Testing Strategy — Why pytest-recording (with one caveat)

The recorded-fixture story matters because four of our adapters (IEM, AWC, CLI, GHCNh) hit live public APIs. The 2026 ecosystem has three real choices:

| Tool | Approach | Verdict for tradewinds |
|------|----------|-----------------------|
| **`pytest-recording` + `vcrpy>=8`** | Record real HTTP, replay from YAML cassettes | **Choose this.** Recorded fixtures match how mostlyright tested. Real responses, including edge cases (timeouts, malformed responses), live in version control. |
| **`pytest-httpx`** (0.36.2 current) | Pure mocking — you write the response | Use **alongside** pytest-recording for unit tests of error paths (e.g., "what if AWC returns 503?"). Not a substitute for integration testing. |
| **`respx`** | Pure mocking, route-based | Skip. pytest-httpx covers the same ground with cleaner ergonomics for our case. |

### The httpx caveat in VCR.py

VCR.py 8.x supports httpx, but [async-streaming httpx had ongoing issues through 2025](https://github.com/kevin1024/vcrpy/issues/597), fixed in 8.1.x. We're not using streaming responses (our adapters are simple JSON/text fetches), so we're fine — but **document this constraint in `_internal/http.py`**: "do not use httpx streaming for catalog adapters; VCR.py compatibility depends on full-buffer responses."

### Recommended cassette layout

```
tests/
├── fixtures/
│   ├── parity/                             # 5 byte-equivalent parity fixtures (Day 3 GATE)
│   │   ├── kord_2024-01.json
│   │   └── ...
│   └── cassettes/                          # pytest-recording cassettes
│       ├── test_iem_observations/
│       │   └── test_fetch_kord_30days.yaml
│       ├── test_awc_metar/
│       └── test_cli_settlement/
├── conftest.py                             # vcr_config fixture: filter auth headers, redact `User-Agent`
└── ...
```

### Filtering sensitive data in cassettes

```python
# tests/conftest.py
@pytest.fixture(scope="module")
def vcr_config():
    return {
        "filter_headers": ["authorization", "user-agent", "cookie"],
        "filter_query_parameters": ["api_key", "token"],
        "record_mode": "none",  # CI default — fail rather than make real calls
    }
```

Use `--record-mode=once` flag to refresh cassettes during pre-publish runs only.

---

## Type Checking Strategy

mypy strict is the goal; **gradual adoption** is the path.

### Tiered configuration (`pyproject.toml` workspace root)

```toml
[tool.mypy]
python_version = "3.11"
files = ["packages/*/src"]
exclude = ["packages/.*/_vendor/"]    # Lifted v0.14.1 code retains its monorepo type story
strict = false                          # Workspace default: lax

# Strict on tradewinds.core only (the load-bearing safety layer)
[[tool.mypy.overrides]]
module = "tradewinds.core.*"
strict = true
warn_return_any = true
disallow_any_unimported = true

# Strict-ish on research.py (the parity-critical join)
[[tool.mypy.overrides]]
module = "tradewinds.research"
strict = true

# Lax on adapters (calling untyped third-party HTTP)
[[tool.mypy.overrides]]
module = "tradewinds.weather.catalog.*"
strict = false
disallow_untyped_defs = true            # Still require annotated public fns
check_untyped_defs = true

# Ignore _vendor entirely (it's lifted; not our problem in v0.1)
[[tool.mypy.overrides]]
module = "tradewinds.weather._vendor.*"
ignore_errors = true
```

**Rationale:** the `tradewinds.core.*` exception hierarchy and temporal primitives are where type safety pays off. Adapters are I/O glue. `_vendor/` is verbatim lift — touching it for typing risks breaking parity.

---

## Pre-commit Configuration

`.pre-commit-config.yaml`:

```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.15.14
    hooks:
      - id: ruff-check
        args: [--fix]
      - id: ruff-format    # MUST run after ruff-check --fix

  - repo: local
    hooks:
      - id: mypy
        name: mypy (core only)
        entry: uv run mypy packages/core/src/tradewinds/core
        language: system
        pass_filenames: false
        types_or: [python]
```

**Hook ordering matters:** `ruff-check --fix` first (it may rewrite code), then `ruff-format`. Don't add `black` — ruff format is byte-identical to black for our settings.

**Why mypy is `local` (not the upstream mypy pre-commit hook):** the upstream hook installs its own isolated venv; ours needs to see our installed deps. `uv run mypy ...` reuses the workspace venv.

---

## CI/CD — GitHub Actions, Trusted Publishing

The recommended workflow (cribbed from [astral-sh/trusted-publishing-examples](https://github.com/astral-sh/trusted-publishing-examples), adapted for our 3-package workspace):

```yaml
# .github/workflows/release.yml
name: Release

on:
  push:
    tags:
      - "v*"   # e.g., v0.1.0, v0.1.0a1

jobs:
  publish:
    name: Build & publish to PyPI
    runs-on: ubuntu-latest
    environment:
      name: pypi      # configure in GH repo Settings → Environments
    permissions:
      id-token: write # required for trusted publishing
      contents: read
    steps:
      - uses: actions/checkout@v5
      - uses: astral-sh/setup-uv@v6
      - run: uv python install 3.13
      - name: Build all three packages
        run: uv build --all   # produces dist/tradewinds-*, dist/tradewinds-weather-*, dist/tradewinds-markets-*
      - name: Smoke-test the wheels
        run: |
          uv run --isolated --no-project --with dist/tradewinds-*.whl tests/smoke/test_import.py
          uv run --isolated --no-project --with dist/tradewinds_weather-*.whl tests/smoke/test_import_weather.py
          uv run --isolated --no-project --with dist/tradewinds_markets-*.whl tests/smoke/test_import_markets.py
      - name: Publish to PyPI
        run: uv publish
```

### Three PyPI trusted-publishing registrations

You must configure trusted publishing **three times on PyPI** — once per package (`tradewinds`, `tradewinds-weather`, `tradewinds-markets`). All three can point to the same repo + workflow + environment. PyPI verifies the OIDC token's repository claim, not the package name.

**For the first publish only:** PyPI requires the package to exist before trusted publishing can be configured — workaround is the "pending publisher" feature, which lets you pre-register the package name + workflow before the first push. Use it; it's free and bypasses the chicken-and-egg.

### CI test workflow (separate)

```yaml
# .github/workflows/test.yml
on: [push, pull_request]
jobs:
  test:
    strategy:
      matrix:
        python-version: ["3.11", "3.12", "3.13"]
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v5
      - uses: astral-sh/setup-uv@v6
        with:
          enable-cache: true
      - run: uv python install ${{ matrix.python-version }}
      - run: uv sync --all-packages --all-extras
      - run: uv run pytest -m "not live" --cov=tradewinds --cov-branch
```

The `not live` marker filter is already in the workspace pyproject — keep it. Run live tests (`-m live`) **manually before each publish**, not in CI (per ROADMAP and current CLAUDE.md).

---

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

---

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

---

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

---

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

**Cross-package compatibility risks (verified, no known breaks):**
- pandas 2.2.x + pyarrow 24.0: ✓ (pyarrow supports pandas 2.x and 3.x)
- httpx 0.28 + vcrpy 8.x: ✓ (buffered responses only — no streaming)
- jsonschema 4.26 + Python 3.13: ✓
- hatchling + PEP 420 namespace packages: ✓ (production-tested for years)

---

## Decisions Already Locked — Confirmed Correct

These are NOT to be re-litigated (per milestone_context). My research **confirms** all are still right calls in May 2026:

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

---

## Decisions to Consider Revisiting (Soft Flags)

None of these block v0.1. All are v0.2+ items to think about.

1. **Pandas 3.0 migration is a v0.2 work item, not a v0.1 nice-to-have.** Re-capture parity fixtures. Touch points: datetime resolution (`ns` vs `us`), string dtype (affects `station`, `metar_raw`), `M`/`Q`/`Y` offset alias removals (audit `_climate.py` for these). Estimate: 2 days, mostly fixture re-capture and CI bisection.

2. **Async catalog adapters in v0.2.** If user reports slow multi-station fetches, the httpx `AsyncClient` swap is small (the existing scaffold already imports `httpx`). The VCR.py async-streaming caveat above stays a constraint.

3. **Pydantic introduction in v0.2 for MCP work.** FastMCP returns Pydantic models. Either:
   - Use Pydantic in `tradewinds.mcp.*` only (isolated), or
   - Migrate `tradewinds.core.exceptions` payloads to Pydantic models (better DX, but breaking change).
   - **Recommendation:** option 1. Pydantic stays out of `core` until v0.3+.

4. **uv_build backend swap when PEP 420 lands.** Watch [astral-sh/uv#12832](https://github.com/astral-sh/uv/issues/12832). If resolved by v0.2, swapping from hatchling → uv_build removes one dep. No urgency.

5. **MCP server returns format for DataFrames.** When MCP work starts in v0.2, default to `toon` (which the design already includes as a format). Document why: smaller payload than JSON, schema-attached, lossless roundtrip with pandas.

---

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

---

*Stack research for: tradewinds — local-first Python SDK, three-package uv workspace*
*Researched: 2026-05-21*
*Confidence: HIGH on versions, MEDIUM on namespace-package edge cases (verified via working repo)*

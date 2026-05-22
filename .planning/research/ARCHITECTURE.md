# Architecture Research

**Domain:** Local-first Python SDK, three-package uv workspace, shared `tradewinds.*` namespace
**Researched:** 2026-05-21
**Confidence:** HIGH (every load-bearing decision verified against official packaging.python.org, uv docs, pyarrow docs, or inspection of the existing scaffold)

> **Scope reminder.** ROADMAP.md locks the three-layer split (`core/`/`weather/`/`markets/` + `mcp/` deferred), the PyPI distribution names, the module paths, and the public API surface. This document does NOT redesign any of that — it answers the *implementation* questions the roadmap explicitly left open.

---

## Standard Architecture

### System Overview (locked by ROADMAP.md)

```
┌──────────────────────────────────────────────────────────────────────┐
│                       USER-FACING SURFACE                             │
│                                                                       │
│   tradewinds.research(contract, station, from_date, to_date,         │
│                       sources={...})  ──►  pd.DataFrame              │
│                                                                       │
│   (Mode 1: v0.14.1 parity, sources=None)                             │
│   (Mode 2: source-explicit, full mostlyright-mcp semantics)          │
└──────────────┬───────────────────────────────────────────────────────┘
               │
               ▼
┌──────────────────────────────────────────────────────────────────────┐
│  CORE LAYER  —  packages/core/  (dist: tradewinds)                   │
│                                                                       │
│  ┌─────────────┐  ┌──────────┐  ┌──────────┐  ┌─────────────────┐   │
│  │  temporal   │  │  schema  │  │ validator│  │    exceptions    │   │
│  │ TimePoint   │  │  Schema  │  │ Validator│  │ TradewindsError  │   │
│  │ KnowledgeV. │  │ registry │  │ +invariant│  │ + payload subcls│   │
│  └──────┬──────┘  └────┬─────┘  └────┬─────┘  └─────────────────┘   │
│         │              │             │                                │
│  ┌──────┴──────────────┴─────────────┴───────────────────────────┐  │
│  │              research()  +  formats/{json,parquet,toon,csv}    │  │
│  └────┬───────────────────────────────────────────────────────────┘  │
│       │                                                                │
│  ┌────┴─────────────────────────────────────────────────┐            │
│  │  _internal/  — http, cache backend, config (LIFTED) │            │
│  └──────────────────────────────────────────────────────┘            │
└─────────┬────────────────────────────────────┬───────────────────────┘
          │                                    │
          ▼                                    ▼
┌────────────────────────────────────┐  ┌──────────────────────────────┐
│  CATALOG: WEATHER                   │  │  CATALOG: MARKETS             │
│  packages/weather/                  │  │  packages/markets/            │
│  (dist: tradewinds-weather)         │  │  (dist: tradewinds-markets)   │
│                                     │  │                               │
│  catalog/                           │  │  catalog/                     │
│   ├── iem.py    (iem.archive|live)  │  │   ├── kalshi_nhigh.py        │
│   ├── awc.py    (awc.live)          │  │   └── kalshi_nlow.py         │
│   ├── cli.py    (cli.archive)       │  │                               │
│   └── ghcnh.py  (ghcnh.archive)     │  │  (contract-spec only in v0.1) │
│                                     │  │                               │
│  _vendor/  — lifted parsers          │  └──────────────────────────────┘
│   ├── _iem.py / _awc.py / _climate.py│                ▲
│   ├── _ghcnh.py                      │                │
│   ├── _forecast_{parse,schema}.py    │                │ contract.settlement_source
│   └── specs/*.json                   │                │ resolves to an adapter
│                                     │                │ source_id in weather pkg
│  cache.py  — parquet cache,         │                │
│              filelock, LST-skip      │◄───────────────┘
└─────────────────────────────────────┘
          ▲
          │ (HTTP)
          ▼
┌──────────────────────────────────────────────────────────────────────┐
│  EXTERNAL DATA SOURCES (no hosted backend in v0.1)                   │
│   AWC (NOAA)  IEM (Iowa)  GHCNh (NCEI)  NWS CLI  Kalshi API          │
└──────────────────────────────────────────────────────────────────────┘

                    ── DEFERRED TO v0.2 ──
┌──────────────────────────────────────────────────────────────────────┐
│  MCP SERVER  —  packages/mcp/  (dist: tradewinds-mcp)                │
│  catalog_search / pull_pairs / validate_dataframe  (stubs in v0.1)   │
└──────────────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Implementation pattern (2026-current) |
|-----------|----------------|----------------------------------------|
| `tradewinds.core.temporal` | `TimePoint` (UTC + tz), `KnowledgeView` (`knowledge_time <= as_of` filter) | Plain dataclasses + functions over DataFrames; NOT a pandas accessor |
| `tradewinds.core.schema` | `Schema` declarative spec + registry, `Schema.from_dataframe()` | Frozen dataclass; eager registration at import-time in `core.schemas` package |
| `tradewinds.core.validator` | Schema contract + source-identity + temporal-drift checks | Function `validate_dataframe(df, schema) -> ValidationResult`, NOT a class-bound method |
| `tradewinds.core.leakage` | Audit-only `LeakageDetector` for BYO training sets | Class with `audit(df) -> LeakageReport`; called explicitly by user |
| `tradewinds.core.exceptions` | `TradewindsError` hierarchy with structured payloads | Plain classes carrying typed attributes set in `__init__` (NOT `@dataclass`) |
| `tradewinds.core.formats.*` | dataframe/json/parquet/toon/csv serializers | Module-level `dumps(df, **opts)` / `loads(bytes) -> df` pairs |
| `tradewinds.research` | The top-level join — Mode 1 (parity) + Mode 2 (source-explicit) | Single function; dispatches on `sources=None` |
| `tradewinds.weather.catalog.{iem,awc,cli,ghcnh}` | Per-source adapters wrapping `_vendor/` parsers; emit canonical schema rows | Each module exposes `SUPPORTED_SOURCES: list[str]` + `fetch(source, station, range) -> DataFrame` |
| `tradewinds.weather.catalog.__init__` | Source-ID dispatch registry | Eager-import all adapter modules at package import; build `_REGISTRY: dict[source_id, adapter_module]` |
| `tradewinds.weather._vendor.*` | Verbatim parsers lifted from monorepo-v0.14.1 | Underscore prefix; documented as private; NO public-import contract |
| `tradewinds.weather.cache` | Parquet cache, `filelock`-guarded, LST current-month-skip, 30-day volatile skip | Per-file partition (`station/year/month.parquet`); read via `pyarrow.parquet.read_table` with row filters |
| `tradewinds.markets.catalog.{kalshi_nhigh,kalshi_nlow}` | Contract specs; map `contract` → settlement source ID | Frozen dataclass `ContractSpec(contract_id, settlement_source, ...)` |
| `tradewinds._internal.*` | Shared HTTP, retry, config — owned by `core` distribution, imported by sibling packages | Underscore prefix; no API stability guarantee across versions |

---

## Recommended Project Structure

Locked layout from ROADMAP.md (lines 38-91), with the **two correctness changes** flagged in the open-questions section below:

```
tradewinds/                              # workspace root
├── pyproject.toml                       # [tool.uv.workspace] members = ["packages/*"]
├── packages/
│   ├── core/                            # dist: tradewinds
│   │   ├── pyproject.toml               # depends on tradewinds-weather
│   │   └── src/
│   │       └── tradewinds/              # *** NO __init__.py at this level ***  (decision below)
│   │           ├── core/
│   │           │   ├── __init__.py
│   │           │   ├── temporal.py
│   │           │   ├── schema.py
│   │           │   ├── validator.py
│   │           │   ├── leakage.py
│   │           │   ├── exceptions.py
│   │           │   ├── schemas/         # canonical schemas, registered on import
│   │           │   │   ├── __init__.py  # eager-imports observation_v1, forecast_v1, settlement_v1
│   │           │   │   ├── observation_v1.py
│   │           │   │   ├── forecast_iem_mos_v1.py
│   │           │   │   └── settlement_cli_v1.py
│   │           │   └── formats/
│   │           │       ├── __init__.py
│   │           │       ├── dataframe.py
│   │           │       ├── json.py
│   │           │       ├── parquet.py
│   │           │       ├── toon.py
│   │           │       └── csv.py
│   │           ├── research.py          # research() — top-level join
│   │           └── _internal/           # shared utils (lifted)
│   │               ├── __init__.py
│   │               ├── _http.py
│   │               ├── _live_http.py
│   │               ├── _convert.py
│   │               ├── _types.py
│   │               ├── config.py
│   │               ├── exceptions.py    # narrow legacy aliases; main hierarchy lives in core/exceptions.py
│   │               ├── models.py
│   │               ├── versioning.py
│   │               └── merge/           # LIVE_V1 merge policies (lifted Day 2)
│   │
│   ├── weather/                         # dist: tradewinds-weather
│   │   ├── pyproject.toml               # depends on tradewinds (for core types)
│   │   └── src/
│   │       └── tradewinds/              # *** NO __init__.py at this level ***
│   │           └── weather/
│   │               ├── __init__.py      # re-exports catalog.fetch_observations etc.
│   │               ├── catalog/
│   │               │   ├── __init__.py  # eager-imports adapters; builds _REGISTRY dict
│   │               │   ├── iem.py       # SUPPORTED_SOURCES = ["iem.archive","iem.live"]
│   │               │   ├── awc.py       # SUPPORTED_SOURCES = ["awc.live"]
│   │               │   ├── cli.py       # SUPPORTED_SOURCES = ["cli.archive"]
│   │               │   └── ghcnh.py     # SUPPORTED_SOURCES = ["ghcnh.archive"]
│   │               ├── _vendor/         # *** keep _vendor name; see decision below ***
│   │               │   ├── __init__.py  # documents what's lifted, from where, at which tag
│   │               │   ├── _iem.py
│   │               │   ├── _awc.py
│   │               │   ├── _climate.py
│   │               │   ├── _ghcnh.py
│   │               │   ├── _forecast_parse.py
│   │               │   ├── _forecast_columns.py
│   │               │   ├── _forecast_schema.py
│   │               │   ├── _convert.py
│   │               │   ├── _bounds.py
│   │               │   └── specs/       # JSON forecast specs
│   │               └── cache.py
│   │
│   ├── markets/                         # dist: tradewinds-markets
│   │   ├── pyproject.toml               # depends on tradewinds (for core types)
│   │   └── src/
│   │       └── tradewinds/              # *** NO __init__.py at this level ***
│   │           └── markets/
│   │               ├── __init__.py
│   │               ├── catalog/
│   │               │   ├── __init__.py
│   │               │   ├── kalshi_nhigh.py
│   │               │   └── kalshi_nlow.py
│   │               └── _kalshi_api.py   # Sprint 0.5+
│   │
│   └── mcp/                             # dist: tradewinds-mcp (v0.2 — stub only in v0.1)
│       └── src/
│           └── tradewinds/              # *** NO __init__.py at this level ***
│               └── mcp/
│                   ├── __init__.py
│                   ├── __main__.py
│                   └── tools/
│                       ├── catalog_search.py
│                       ├── pull_pairs.py
│                       └── validate_dataframe.py
└── tests/                               # workspace-level integration + parity tests
```

### Structure Rationale

- **One `tradewinds/` directory per distribution, no `__init__.py` at the namespace root.** This is the PEP 420 "native namespace package" pattern, which is the official `packaging.python.org` recommendation for Python-3-only distributions. ([Python Packaging User Guide](https://packaging.python.org/en/latest/guides/packaging-namespace-packages/))
- **Concrete subpackages (`core/`, `weather/`, `markets/`, `mcp/`) DO have their own `__init__.py`.** The namespace-package rule only applies to the *namespace* directory (the shared `tradewinds/`), not to its concrete subpackages.
- **`_vendor/` keeps the underscore prefix.** Matches the established Python idiom (pip uses `pip/_vendor/`, pytest uses `_pytest/`, urllib3 ships under `pip/_vendor/urllib3/`). Underscore signals "private, not part of public API." ([pip vendoring policy](https://pip.pypa.io/en/stable/development/vendoring-policy/))
- **`_internal/` lives in core only**, weather and markets depend on `tradewinds` (the dist) and reach in via `from tradewinds._internal._http import ...`. The leading underscore is the contract: this is private and may break across patch versions.
- **Schemas as a package, not a module.** `tradewinds.core.schemas/` with one file per schema makes contract tests target `tests/contracts/test_schema_observation.py` cleanly and lets each schema's docstring live next to its declaration.

---

## Architectural Patterns (the seven open questions, answered)

### Pattern 1: Namespace packaging — PEP 420 (native), NOT pkgutil

**What.** Each distribution ships its slice of `src/tradewinds/` *without* an `__init__.py` at the namespace root. Python's import system stitches them together at runtime via `sys.path` lookup. ([PEP 420](https://peps.python.org/pep-0420/))

**Decision: PEP 420. Recommendation HIGH confidence.**

**Why PEP 420 over the current pkgutil scaffold:**

| Criterion | PEP 420 (native) | pkgutil.extend_path | Verdict |
|-----------|------------------|---------------------|---------|
| Official PyPA recommendation for Python-3-only | YES ([PyPA guide](https://packaging.python.org/en/latest/guides/packaging-namespace-packages/)) | Marked "obsolete unless backward-compat needed" | PEP 420 |
| Editable installs across `uv` workspace | Works transparently — `uv sync` puts all members on `sys.path` | Also works, but requires every dist to ship identical `__path__` boilerplate; one drift = silent breakage | PEP 420 |
| Single point of failure if a dist forgets the rule | None — every dist independently contributes | Any dist that ships an `__init__.py` *without* the `extend_path` call shadows siblings (silent breakage) | PEP 420 |
| Boilerplate in each dist | Zero (just omit the file) | `__path__ = __import__("pkgutil").extend_path(__path__, __name__)` in every dist's namespace root | PEP 420 |
| Tooling support (mypy, ruff, IDE) | Universal | Universal | tie |

**The killer argument for PEP 420 here:** in pkgutil-style, *every* distribution must ship an identical `__init__.py` with the `extend_path` call. If `tradewinds-weather` v0.2.0 forgets it (or someone "cleans up" the file thinking it's dead code), the weather distribution silently shadows everything else under `tradewinds.` and `import tradewinds.markets` breaks for users who have both installed. PEP 420 has no such failure mode — there's nothing to forget.

**Concrete change required in the existing scaffold:**

1. **DELETE** `packages/core/src/tradewinds/__init__.py` (the file currently exists, currently uses `pkgutil.extend_path`).
2. **MOVE** the `__version__` constant currently in that file. Two acceptable destinations:
   - `tradewinds.core.__version__` (recommended — each dist sets its own version in its own subpackage; the *namespace* has no single version)
   - `tradewinds._version` (read via `importlib.metadata.version("tradewinds")` from inside `core/__init__.py`)
3. **MOVE** the `research()` re-export. ROADMAP.md line 42 says `tradewinds.research()` is the public surface. Two options:
   - **Option A (recommended):** keep `packages/core/src/tradewinds/research.py` as a module (no `__init__.py` needed — it's an attribute of the `core` distribution's slice of the namespace, contributed at `tradewinds.research`). Users call `from tradewinds.research import research` or `import tradewinds.research as r`. **This is the cleanest PEP-420-native pattern.**
   - **Option B:** keep `tradewinds.research()` callable directly (`from tradewinds import research`). This requires either (a) reverting to pkgutil style, or (b) putting `research` in `tradewinds.api` and documenting `from tradewinds.api import research` as the canonical import. Option B(b) keeps PEP 420 cleanliness while preserving the short import path.

**Recommendation: Option A.** `from tradewinds.research import research` is one import-line longer but it's the only way to keep PEP 420 strict, and the existing docs (ROADMAP.md line 162) already reference the function-not-module form internally.

**Hatchling configuration** (verified pattern from [pypa/hatch discussion #819](https://github.com/pypa/hatch/discussions/819)):

```toml
# packages/core/pyproject.toml
[tool.hatch.build.targets.wheel]
packages = ["src/tradewinds/core", "src/tradewinds/research.py", "src/tradewinds/_internal"]
# Each dist explicitly lists its own contributions to the tradewinds namespace.
# The `src/tradewinds/` directory itself (the namespace root) is NOT listed —
# its absence of an __init__.py is what makes it a namespace package.
```

```toml
# packages/weather/pyproject.toml
[tool.hatch.build.targets.wheel]
packages = ["src/tradewinds/weather"]
```

```toml
# packages/markets/pyproject.toml
[tool.hatch.build.targets.wheel]
packages = ["src/tradewinds/markets"]
```

This is **different from the current** `packages = ["src/tradewinds"]` setting, which works by accident (because each dist's `src/tradewinds/` happens to contain only its own slice) but is fragile if anyone ever adds a stray file to one dist's namespace root.

---

### Pattern 2: Cross-package imports — `tool.uv.sources` workspace declaration

**What.** `tradewinds-weather` needs to `from tradewinds.core.schema import Schema`. In an editable workspace install, this Just Works because uv puts both packages on the same `sys.path`. The question is what to declare in `pyproject.toml` so it also works when users install from PyPI.

**Decision: every sibling package declares `tradewinds` as a runtime dependency, with `tool.uv.sources` resolving to the workspace member during local development.**

```toml
# packages/weather/pyproject.toml
[project]
dependencies = [
    "httpx>=0.27",
    "jsonschema>=4.21",
    "filelock>=3.12",
    "tradewinds",                    # ← runtime dep on the core dist (REQUIRED — currently missing)
]
```

```toml
# workspace root pyproject.toml — already correct
[tool.uv.sources]
tradewinds = { workspace = true }
tradewinds-weather = { workspace = true }
tradewinds-markets = { workspace = true }
```

The workspace-root `[tool.uv.sources]` declaration **inherits down to all members** ([uv workspaces docs](https://docs.astral.sh/uv/concepts/projects/workspaces/)), so when `tradewinds-weather` declares `"tradewinds"` as a dependency, uv resolves it from the local checkout for editable installs and from PyPI for wheel installs. Same `pyproject.toml`, both modes.

**Concrete changes required:**

1. `packages/weather/pyproject.toml`: add `"tradewinds"` to `[project] dependencies` (currently missing).
2. `packages/markets/pyproject.toml`: add `"tradewinds"` to `[project] dependencies` (currently missing).
3. `packages/core/pyproject.toml`: **REVERSE** the current `"tradewinds-weather"` dependency. Core should NOT depend on weather. The ROADMAP design has `research()` in core *call* the weather adapter registry, but it does so via a string source ID lookup — not an import. The actual import goes `tradewinds.weather.catalog` → `tradewinds.core.schema`, never the reverse.
   - **Exception to consider:** if `tradewinds.research()` needs to *eagerly* import the weather catalog to register source IDs, then yes, core must depend on weather. But the cleaner pattern is **lazy resolution** — `research()` accepts the source ID strings and resolves them on first call via `importlib.import_module("tradewinds.weather.catalog")`. This breaks the import cycle and keeps `tradewinds` installable standalone (e.g., for a user who only wants the MCP server with a different vertical).
   - **Recommendation: remove `tradewinds-weather` from core's deps.** Document the optional dependency under `[project.optional-dependencies] weather = ["tradewinds-weather"]` and have `research()` raise `SourceUnavailableError` with a "pip install tradewinds-weather" hint if the user calls it without weather installed.

**Build-order implication.** Because `weather` and `markets` depend on `tradewinds` (core), but core does NOT depend on them, the workspace build order is:

```
1. tradewinds        (core)      — depended on by everyone
2. tradewinds-weather            — can be built in parallel with markets
3. tradewinds-markets            — can be built in parallel with weather
4. tradewinds-mcp                — v0.2 only; depends on core + weather + markets
```

This matches the v0.1 release order in ROADMAP.md Day 4 (alpha1) and Day 14 (1.0): core+weather as 0.1.0, markets as 0.1.0 (contract specs only).

---

### Pattern 3: Adapter dispatch — eager-import registry, NOT entry points

**What.** Each adapter module declares `SUPPORTED_SOURCES: list[str]`. The `tradewinds.weather.catalog.__init__` builds a `dict[source_id -> adapter_module]` at import time. The dispatcher looks up by source ID and calls the adapter's `fetch()`.

**Decision: eager-import registry with explicit module enumeration. NOT setuptools entry points, NOT a decorator-based registry.**

```python
# packages/weather/src/tradewinds/weather/catalog/__init__.py
"""Source-ID dispatch for tradewinds.weather catalog adapters."""
from __future__ import annotations
from types import ModuleType
from typing import Protocol

from tradewinds.weather.catalog import iem, awc, cli, ghcnh   # eager — fixes the registry

class WeatherAdapter(Protocol):
    SUPPORTED_SOURCES: list[str]
    def fetch(self, source: str, station: str, from_date: str, to_date: str) -> "pd.DataFrame": ...

# Build registry at import time. Static. Deterministic.
_REGISTRY: dict[str, WeatherAdapter] = {}
for _mod in (iem, awc, cli, ghcnh):
    for _src_id in _mod.SUPPORTED_SOURCES:
        if _src_id in _REGISTRY:
            raise RuntimeError(
                f"Duplicate source ID {_src_id!r} registered by {_mod.__name__} "
                f"(already owned by {_REGISTRY[_src_id].__name__})"
            )
        _REGISTRY[_src_id] = _mod

def get_adapter(source: str) -> WeatherAdapter:
    """Look up the adapter that owns ``source``. Raise SourceUnavailableError if unknown."""
    try:
        return _REGISTRY[source]
    except KeyError as e:
        from tradewinds.core.exceptions import SourceUnavailableError
        raise SourceUnavailableError(
            source=source,
            known_sources=sorted(_REGISTRY.keys()),
        ) from e
```

Each adapter module:

```python
# packages/weather/src/tradewinds/weather/catalog/iem.py
from __future__ import annotations
from tradewinds.weather._vendor import _iem
from tradewinds.core.schema import Schema
# from tradewinds.core.schemas.observation_v1 import OBSERVATION_V1

SUPPORTED_SOURCES: list[str] = ["iem.archive", "iem.live"]

def fetch(source: str, station: str, from_date: str, to_date: str) -> "pd.DataFrame":
    """Fetch from the named IEM source. Emit canonical observation_v1 rows."""
    assert source in SUPPORTED_SOURCES, f"iem.fetch called with unsupported source {source!r}"
    raw = _iem.fetch_observations(station, from_date, to_date, live=(source == "iem.live"))
    df = _to_observation_v1(raw, source_id=source)
    return df
```

**Why eager-import registry over the alternatives:**

| Pattern | Pro | Con | Verdict for tradewinds |
|---------|-----|-----|------------------------|
| **Eager-import registry** (chosen) | Static, deterministic, errors at import time, IDE jump-to-definition works | One file (`catalog/__init__.py`) is the registration hub | YES — clearest match for "we own all adapters in one package" |
| Decorator-based registry | "Pythonic" feel | Decorators only fire when their module is imported; requires every adapter to also be imported somewhere; gotcha-prone ([DEV registry pattern article](https://dev.to/dentedlogic/stop-writing-giant-if-else-chains-master-the-python-registry-pattern-ldm)) | NO — solves a problem we don't have |
| Setuptools entry points | Third-party plugins can register without modifying the package | Slow (importlib.metadata scan), hides what's available, requires `pip install` to register | NO — we're not building a plugin system in v0.1; entry points become attractive in v0.3+ if external folks want to ship `tradewinds-aviation` etc. |
| ABC inheritance | Static type-checkable | Requires every adapter to subclass; harder to register a stateless module | NO — Protocol gives the same type-checking benefit without inheritance coupling ([mypy protocols](https://mypy.readthedocs.io/en/stable/protocols.html)) |
| Protocol-only, no registry | Maximum decoupling | No way to ask "what adapters exist?" — needed for `catalog_search` in v0.2 MCP | NO — registry is required for catalog discovery anyway |

**Recommendation: registry + Protocol.** Adapters declare conformance via `SUPPORTED_SOURCES` and `fetch()` signatures (structurally typed via `WeatherAdapter` Protocol); the registry is built explicitly at `catalog/__init__.py` import time. No decorators, no ABC, no entry points.

**v0.2 implication:** when MCP's `catalog_search` tool needs to enumerate sources, it's just `tradewinds.weather.catalog._REGISTRY.keys()`. The registry is already there.

---

### Pattern 4: Vendored code — `_vendor/` (keep current name)

**What.** Code lifted verbatim from `../monorepo-v0.14.1/src/mostlyright/` into `packages/weather/src/tradewinds/weather/_vendor/`. This is "internal vendoring" — code we own at both ends but want to mark as frozen/lifted so reviewers know not to bug-fix it directly (fix upstream first, re-lift).

**Decision: `_vendor/` name. HIGH confidence.**

**Why `_vendor/` over alternatives:**

| Name | Used by | Connotation | Fit for our case |
|------|---------|-------------|------------------|
| `_vendor/` | pip, urllib3 (in pip), botocore | "Third-party code we're shipping" | YES — the connotation is exactly right: this code came from elsewhere, is frozen, do not edit |
| `_internal/` | Used in our scaffold for shared utils | "Internal API of THIS package" | NO — conflates two different things. `_internal/` is "our private API." `_vendor/` is "imported from elsewhere." |
| `_lifted/` | Nobody | Made-up term | NO — non-discoverable; reviewers won't recognize the convention |
| `_legacy/` | Some Django subpackages | "Old code we'll delete" | NO — implies deletion intent; we don't have that |
| `_third_party/` | Sometimes used | "External, not ours" | NO — technically mostlyright IS ours, lifted from our own monorepo |

The `_vendor` name is the **established Python idiom** ([pip vendoring policy](https://pip.pypa.io/en/stable/development/vendoring-policy/)). Even though we own the lift source, the *semantic* claim is identical: "this code is frozen, came from a tagged upstream, do not modify in place — re-lift if you need a fix." Reviewers familiar with `pip/_vendor/` will instantly recognize the contract.

**Convention to enforce in `_vendor/__init__.py`:**

```python
"""Vendored from monorepo-v0.14.1 (git worktree at the v0.14.1 tag).

Modules in this package are frozen — they reproduce upstream behavior byte-for-byte.
Bugs in vendored code MUST be fixed upstream first (in the monorepo), then re-lifted
into this directory. DO NOT edit these files in place.

Lift inventory and provenance:
  _iem.py              ← monorepo-v0.14.1/src/mostlyright/weather/_iem.py
  _awc.py              ← monorepo-v0.14.1/src/mostlyright/weather/_awc.py
  _climate.py          ← monorepo-v0.14.1/src/mostlyright/weather/_climate.py
  _ghcnh.py            ← monorepo-v0.14.1/src/mostlyright/weather/_ghcnh.py
  _forecast_parse.py   ← monorepo-v0.14.1/src/mostlyright/weather/forecast/_parse.py
  ...
"""
```

**Coverage note:** ROADMAP.md line 140 specifies "lifted `_vendor/` code retains its monorepo coverage" — confirming this convention is already baked into the test plan.

---

### Pattern 5: Schema registry — eager registration at import time

**What.** `tradewinds.core.schemas.observation_v1` defines `OBSERVATION_V1: Schema = Schema(...)`. The question is whether `validate_dataframe(df, "schema.observation.v1")` finds this schema by registry lookup, and if so when the registry is populated.

**Decision: eager registration at import time, via the `tradewinds.core.schemas` package's `__init__.py`. HIGH confidence.**

```python
# packages/core/src/tradewinds/core/schemas/__init__.py
"""Canonical schemas for tradewinds. Registered eagerly on package import."""
from tradewinds.core.schema import Schema, _REGISTRY  # module-level dict
from tradewinds.core.schemas.observation_v1 import OBSERVATION_V1
from tradewinds.core.schemas.forecast_iem_mos_v1 import FORECAST_IEM_MOS_V1
from tradewinds.core.schemas.settlement_cli_v1 import SETTLEMENT_CLI_V1

# Eagerly register so validate_dataframe(df, "schema.observation.v1") works
# without the caller needing to import the schema module first.
for _schema in (OBSERVATION_V1, FORECAST_IEM_MOS_V1, SETTLEMENT_CLI_V1):
    _REGISTRY[_schema.id] = _schema

__all__ = ["OBSERVATION_V1", "FORECAST_IEM_MOS_V1", "SETTLEMENT_CLI_V1"]
```

```python
# packages/core/src/tradewinds/core/schema.py
"""Schema declarative spec + registry."""
from __future__ import annotations
from dataclasses import dataclass, field

_REGISTRY: dict[str, "Schema"] = {}  # populated by core/schemas/__init__.py

@dataclass(frozen=True, slots=True)
class Schema:
    id: str                          # e.g. "schema.observation.v1"
    columns: tuple[str, ...]
    required_columns: tuple[str, ...]
    knowledge_time_rule: str
    # ... see Amendments §A for full surface

def get_schema(schema_id: str) -> Schema:
    """Look up a schema. Triggers eager registration if not yet loaded."""
    if not _REGISTRY:
        # Lazy-import the schemas package to populate _REGISTRY exactly once.
        import tradewinds.core.schemas  # noqa: F401  — side effect: registers schemas
    try:
        return _REGISTRY[schema_id]
    except KeyError as e:
        from tradewinds.core.exceptions import SchemaValidationError
        raise SchemaValidationError(
            schema=schema_id,
            reason=f"unknown schema; known: {sorted(_REGISTRY.keys())}",
        ) from e
```

**Why eager-on-import over the alternatives:**

| Pattern | Pro | Con | Verdict |
|---------|-----|-----|---------|
| **Eager via `schemas/__init__.py`** (chosen) | Deterministic; one-shot registration; debuggable | Importing the `schemas` package costs a tiny amount upfront | YES — we have 3 schemas in v0.1, growing to ~6 in v0.2; cost is irrelevant |
| Lazy per-schema (import on first `get_schema` call) | Faster import of `tradewinds.core` if user never validates | Surprise: error reporting includes "known schemas: []" if you ask before importing any | NO — confuses validation errors |
| Decorator (`@register_schema("schema.observation.v1")` on a `Schema()` call) | "Pythonic" | Same trap as the adapter registry — module must be imported for decorator to fire | NO |
| Entry points | Lets v0.x users add custom schemas via `pip install` | Requires `importlib.metadata` scan; not needed for v0.1's 3 canonical schemas | NOT IN v0.1; revisit v0.3+ |
| PEP 810 lazy imports | Future-proof | PEP 810 is still in draft as of 2026 ([PEP 810](https://peps.python.org/pep-0810/)); also conflicts with the explicit eager-registration intent | NO |

The `get_schema()` function has a safety-net `import tradewinds.core.schemas` call in case a user does `from tradewinds.core.schema import get_schema` without ever touching the `schemas` package. This makes the API robust to "what order do I import things in?" surprises.

**v0.2 MCP-server compatibility:** when `validate_dataframe` MCP tool is wired, it imports `tradewinds.core.schemas` at server startup — same registry, no change.

---

### Pattern 6: `KnowledgeView` shape — wrapping function returning a thin view, NOT a pandas accessor

**What.** `KnowledgeView` is the structural prevention of temporal leakage: `kview.as_of("2025-01-15") → DataFrame` returns only rows with `knowledge_time <= 2025-01-15`. The question is whether to implement this as (a) a pandas accessor registered via `@pd.api.extensions.register_dataframe_accessor("knowledge")`, (b) a wrapper class around a DataFrame, or (c) a free function `as_of(df, ts) → df`.

**Decision: wrapper class around DataFrame, NOT an accessor. HIGH confidence.**

```python
# packages/core/src/tradewinds/core/temporal.py
from __future__ import annotations
from dataclasses import dataclass
from typing import TYPE_CHECKING
import pandas as pd

if TYPE_CHECKING:
    from datetime import datetime

@dataclass(frozen=True, slots=True)
class TimePoint:
    """UTC timestamp with explicit timezone semantics."""
    ts: pd.Timestamp  # always tz-aware

    @classmethod
    def from_str(cls, iso: str) -> "TimePoint":
        ts = pd.Timestamp(iso)
        if ts.tz is None:
            raise ValueError(f"TimePoint requires tz-aware input; got {iso!r}")
        return cls(ts.tz_convert("UTC"))

class KnowledgeView:
    """Temporal-safety primitive: rows where ``knowledge_time <= as_of``.

    Wraps a DataFrame that has a ``knowledge_time`` column. Calling
    ``view.as_of(ts)`` returns a new DataFrame containing only the rows
    visible at time ``ts``. Structural: there is no API to look ahead.
    """

    __slots__ = ("_df", "_knowledge_col")

    def __init__(self, df: pd.DataFrame, *, knowledge_col: str = "knowledge_time"):
        if knowledge_col not in df.columns:
            from tradewinds.core.exceptions import SchemaValidationError
            raise SchemaValidationError(
                schema="KnowledgeView",
                reason=f"DataFrame is missing required column {knowledge_col!r}",
            )
        # Defensive copy: we want the underlying df to be immutable from the
        # view's perspective. Slicing returns a new df each call anyway.
        self._df = df
        self._knowledge_col = knowledge_col

    def as_of(self, ts: TimePoint | str | pd.Timestamp) -> pd.DataFrame:
        """Return rows where knowledge_time <= ts. Returns a fresh DataFrame."""
        if isinstance(ts, str):
            ts = TimePoint.from_str(ts).ts
        elif isinstance(ts, TimePoint):
            ts = ts.ts
        # pd.Timestamp already tz-aware (validated above)
        mask = self._df[self._knowledge_col] <= ts
        return self._df.loc[mask].copy()

    def __repr__(self) -> str:
        return f"KnowledgeView(rows={len(self._df)}, knowledge_col={self._knowledge_col!r})"
```

**Why wrapper class over the alternatives:**

| Pattern | Pro | Con | Verdict |
|---------|-----|-----|---------|
| **Wrapper class** (chosen) | Explicit; constructor validates the schema; `__slots__` keeps it cheap; obvious in stack traces | One extra noun in the user's head ("a KnowledgeView, not a DataFrame") | YES — explicit is the point |
| pandas accessor (`df.knowledge.as_of(ts)`) | Monkey-patches into DataFrame — feels natural | Global pandas state; users who import tradewinds get every DataFrame in the process with `.knowledge` whether they want it or not; testing is harder (state across tests); subtle conflicts if another package registers same accessor | NO — leakage-prevention is too important to hide behind monkey patching |
| Free function `as_of(df, ts)` | Simplest possible signature | No place to validate the schema once; every call re-checks; can't carry state for memoization | NO — Validator-equivalent function would be fine, but KnowledgeView is intentionally stateful (it remembers which column is `knowledge_time`) |
| DataFrame subclass | Type-correct ("a KnowledgeView IS a DataFrame") | pandas DataFrame subclassing is famously broken — `df.copy()` returns a base DataFrame ([pandas extending docs](https://pandas.pydata.org/docs/development/extending.html)) | NO — pandas explicitly steers users away from this |

**Test-determinism point.** The accessor approach has caused real bugs in test suites where the accessor was registered in `conftest.py` of one suite and leaked into another. KnowledgeView as a plain class has no such failure mode. ([Extending pandas docs](https://pandas.pydata.org/docs/development/extending.html))

**Idiom alignment with the design.md Amendment.** The mostlyright-mcp design.md (referenced in ROADMAP.md line 110) names `KnowledgeView` as a *primitive* — not a method. A primitive is a noun; a method is a verb on someone else's noun. The class-wrapper form preserves that semantics.

---

### Pattern 7: Exception hierarchy with structured payloads — plain class, NOT `@dataclass`

**What.** ROADMAP.md line 118 references "Exception hierarchy (Amendments §D, lines 472-499) … `SourceUnavailableError`, `SchemaValidationError`, `SourceMismatchError`, `LeakageError`" — and the explicit requirement is that exceptions carry **structured payloads**, not just a string message. The question is whether to use `@dataclass` exceptions, `__init_subclass__` magic, or plain classes with explicit `__init__`.

**Decision: plain class with explicit `__init__`, payload attributes set on `self`, with a `to_dict()` helper for JSON-serialization (MCP-server-compatible). HIGH confidence.**

```python
# packages/core/src/tradewinds/core/exceptions.py
"""Exception hierarchy for tradewinds. All exceptions carry structured payloads
that can be JSON-serialized (for v0.2 MCP server JSON-RPC error responses)."""

from __future__ import annotations
from typing import Any


class TradewindsError(Exception):
    """Root of the tradewinds exception hierarchy.

    All subclasses MUST:
    - Accept keyword-only constructor arguments.
    - Build a human-readable message string in __init__ via super().__init__(msg).
    - Set every kwarg as a self.* attribute (so callers can inspect structured data).
    - Implement to_dict() for JSON-RPC error serialization.
    """

    def to_dict(self) -> dict[str, Any]:
        """Serializable payload. Override in subclasses."""
        return {"type": type(self).__name__, "message": str(self)}


class SourceUnavailableError(TradewindsError):
    """Raised when a source ID is unknown to the catalog registry,
    or when a network call to a known source fails after retries."""

    def __init__(
        self,
        *,
        source: str,
        known_sources: list[str] | None = None,
        underlying: Exception | None = None,
    ):
        self.source = source
        self.known_sources = known_sources or []
        self.underlying = underlying
        if known_sources is not None and source not in known_sources:
            msg = f"Source {source!r} is not registered. Known sources: {sorted(known_sources)}"
        else:
            msg = f"Source {source!r} is registered but unavailable" + (
                f" ({underlying!r})" if underlying else ""
            )
        super().__init__(msg)

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "SourceUnavailableError",
            "message": str(self),
            "source": self.source,
            "known_sources": self.known_sources,
            "underlying": repr(self.underlying) if self.underlying else None,
        }


class SchemaValidationError(TradewindsError):
    """Raised when a DataFrame fails schema contract checks."""

    def __init__(
        self,
        *,
        schema: str,
        reason: str,
        offending_rows: int | None = None,
        offending_columns: list[str] | None = None,
    ):
        self.schema = schema
        self.reason = reason
        self.offending_rows = offending_rows
        self.offending_columns = offending_columns or []
        msg = f"Schema {schema!r} validation failed: {reason}"
        if offending_rows is not None:
            msg += f" ({offending_rows} offending rows)"
        super().__init__(msg)

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "SchemaValidationError",
            "message": str(self),
            "schema": self.schema,
            "reason": self.reason,
            "offending_rows": self.offending_rows,
            "offending_columns": self.offending_columns,
        }


class SourceMismatchError(TradewindsError):
    """The source-identity invariant: train_source != infer_source for a paired role."""

    def __init__(
        self,
        *,
        role: str,                # "observations", "forecasts", "settlement"
        train_source: str,
        infer_source: str,
    ):
        self.role = role
        self.train_source = train_source
        self.infer_source = infer_source
        super().__init__(
            f"Source-identity invariant violated for role {role!r}: "
            f"training source {train_source!r} != inference source {infer_source!r}"
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "SourceMismatchError",
            "message": str(self),
            "role": self.role,
            "train_source": self.train_source,
            "infer_source": self.infer_source,
        }


class LeakageError(TradewindsError):
    """LeakageDetector found a row with knowledge_time > as_of_time in a training set."""

    def __init__(
        self,
        *,
        offending_count: int,
        as_of: str,
        sample_knowledge_times: list[str] | None = None,
    ):
        self.offending_count = offending_count
        self.as_of = as_of
        self.sample_knowledge_times = sample_knowledge_times or []
        super().__init__(
            f"Temporal leakage detected: {offending_count} rows have "
            f"knowledge_time > as_of={as_of}"
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "LeakageError",
            "message": str(self),
            "offending_count": self.offending_count,
            "as_of": self.as_of,
            "sample_knowledge_times": self.sample_knowledge_times,
        }


# Compatibility alias for one release (per Key Decision in PROJECT.md):
MostlyRightMCPError = TradewindsError
```

**Why plain class over the alternatives:**

| Pattern | Pro | Con | Verdict |
|---------|-----|-----|---------|
| **Plain class with explicit `__init__`** (chosen) | Full control over the message string; explicit constructor signature visible in IDE; works with isinstance; trivially picklable across processes (important for multiprocessing tests + v0.2 MCP JSON-RPC) | A few lines of `self.x = x` boilerplate per subclass | YES |
| `@dataclass(frozen=True)` exception | Less boilerplate | Mixing `@dataclass` with Exception is a known footgun — `__init__` from dataclass conflicts with Exception's `__init__(*args)` contract; pickling can break; subclasses inherit dataclass field declarations awkwardly ([Python dataclasses docs](https://docs.python.org/3/library/dataclasses.html)) | NO — the trap is worse than the win |
| `__init_subclass__` magic to auto-build constructors | Most-DRY | Hard to read; static type checkers can't infer constructor signatures; debugging stacktraces are mysterious | NO |
| Carry payload in `args[0]` as a dict | Trivially serializable | No type-checking on the payload; defeats the point of "structured" | NO |
| `BaseException.add_note` (PEP 678, Py 3.11+) | Native | Notes are strings — not structured payloads. Use as a complement to attributes, not a replacement. | Use ADDITIONALLY where helpful, not as the primary payload mechanism |

**Why this matters for v0.2 MCP server.** The MCP JSON-RPC protocol requires errors to be serializable. The `to_dict()` method on every exception means the v0.2 MCP error handler is:

```python
# packages/mcp/.../error_handler.py (v0.2)
try:
    return await handler(req)
except TradewindsError as e:
    return {"jsonrpc": "2.0", "id": req.id, "error": {"code": -32001, "data": e.to_dict()}}
```

No reflection, no isinstance ladder per error type — the polymorphism is in `to_dict()`. This is precisely why we avoid `@dataclass` exceptions: `dataclass.asdict()` doesn't gracefully handle the message-vs-fields distinction Exception needs.

---

### Pattern 8: Parquet cache layout — per-file partition (keep current scheme)

**What.** ROADMAP.md line 177 specifies `$HOME/.tradewinds/cache/observations/{station}/{year}/{month}.parquet`. This is a per-file partition with implicit directory hierarchy, NOT a Hive-style (`station=KORD/year=2024/month=07/data.parquet`) layout.

**Decision: keep per-file partition. HIGH confidence.**

**Why per-file over Hive-partitioned pyarrow.dataset:**

| Criterion | Per-file (`station/year/month.parquet`) | Hive-style (`station=X/year=Y/month=Z/`) | Verdict |
|-----------|----------------------------------------|------------------------------------------|---------|
| Cache eviction (delete stale entry) | `rm packages/.tradewinds/cache/observations/KORD/2025/01.parquet` — one file | `rmtree packages/.tradewinds/cache/observations/station=KORD/year=2025/month=01/` — directory of small parts | Per-file (atomic) |
| `filelock` granularity | One lockfile per partition (`01.parquet.lock`) — concurrent writes to different months are independent | Lock at directory level — concurrent writes to same month coordinate via filelock; writes to different months can use separate locks | Tie (per-file slightly simpler) |
| Query pattern: "give me 30 days centered on 2025-01-15" | Open 2 files (Dec 2024, Jan 2025); concat | `pyarrow.dataset.dataset(...).to_table(filter=...)` — pushdown via partition pruning | Hive wins for >12-month queries; per-file wins for ≤2-month queries |
| Typical query shape in tradewinds | Mode 1: 30-day windows (1-2 partitions); Mode 2: bigger but bounded by `from_date`/`to_date` | Same | Per-file is adequate; Hive over-engineered |
| Format-stability ("what file do I look at to debug?") | Path is human-readable: `KORD/2025/01.parquet` | Path includes `=` literals; tools (Finder, `ls`) show fine but readability marginal | Per-file (very slightly) |
| Read performance for small queries (~30 days) | One `pq.read_table(path)` per file; cheap | `pq.read_table(dataset)` with filter — same physical IO, slightly more overhead from dataset object construction | Per-file slightly faster for the common case |
| Read performance for big queries (>1 year) | Loop over many files, concat | Single dataset query with predicate pushdown | Hive wins materially |

**Per-file is correct for tradewinds v0.1 because:**

1. The product is a research SDK; queries are bounded by `(station, from_date, to_date)` with typical ranges of 30-90 days. The longest realistic Mode 2 call is a few years of one station's history — still <30 files.
2. `filelock` semantics are simpler at the file level. The `filelock>=3.12` dependency already specified in `packages/weather/pyproject.toml` is built around per-file locks.
3. The "LST current-month skip" rule and "30-day volatile-window skip" rule (ROADMAP.md lines 179-181) are easier to enforce when one file = one month. With Hive partitioning the volatile-window check has to look at the file mtime, not a clean partition boundary.
4. `pyarrow.dataset` is fully available *when we need it* (e.g., v0.2 hosted R2 cache, where queries cross thousands of station-months). Switching at that point is a one-paragraph migration — the schema is identical, only the directory layout changes.

**Verified read path** (the cache reads, after the cache decides "yes this partition is on disk"):

```python
# packages/weather/src/tradewinds/weather/cache.py
import pyarrow.parquet as pq
import pandas as pd
from pathlib import Path
from filelock import FileLock

def read_partition(station: str, year: int, month: int) -> pd.DataFrame | None:
    """Read one month's cached observations for one station. None if not cached."""
    path = Path.home() / ".tradewinds" / "cache" / "observations" / station / str(year) / f"{month:02d}.parquet"
    if not path.exists():
        return None
    with FileLock(str(path) + ".lock"):
        return pq.read_table(path).to_pandas()
```

For the eventual v0.2 query pattern (multi-station, multi-year), the migration is to drop `read_partition` per-call and replace with `pyarrow.dataset.dataset(cache_root).to_table(filter=...)`. Same files, same schemas — just a different reader.

**Reference:** [pyarrow.dataset.partitioning](https://arrow.apache.org/docs/python/generated/pyarrow.dataset.partitioning.html), [Tabular Datasets](https://arrow.apache.org/docs/python/dataset.html).

---

## Data Flow

### Worked example: a 30-day `research()` call (Mode 2, source-explicit)

User code:

```python
import tradewinds
from tradewinds.research import research

df = research(
    contract="KXHIGHNYC",
    station="KORD",
    from_date="2025-01-01",
    to_date="2025-01-30",
    sources={
        "observations": "iem.archive",
        "forecasts":    "iem.archive",
        "settlement":   "cli.archive",
    },
)
```

The call propagates through the architecture as follows:

```
┌──────────────────────────────────────────────────────────────────────────┐
│ STEP 1: research.py:research() entry                                     │
│   • Validates {observations, forecasts, settlement} keys present         │
│   • Resolves contract="KXHIGHNYC" → ContractSpec via                     │
│     tradewinds.markets.catalog.kalshi_nhigh.lookup("KXHIGHNYC")          │
│     → verifies sources["settlement"] is compatible with the contract's   │
│       declared settlement source family ("cli.*")                        │
│   • Computes (year, month) tuples covered: [(2024, 12), (2025, 1)]       │
└────────────────────────────────────┬─────────────────────────────────────┘
                                     │
                                     ▼
┌──────────────────────────────────────────────────────────────────────────┐
│ STEP 2: per-role fan-out                                                  │
│   ROLE: observations (source="iem.archive")                              │
│     ├─► tradewinds.weather.catalog.get_adapter("iem.archive") → iem.py   │
│     │    ├─► For each (station, year, month):                           │
│     │    │    ├─► cache.read_partition("KORD", 2024, 12)                │
│     │    │    │    └─► HIT  →  yield cached DataFrame                   │
│     │    │    ├─► cache.read_partition("KORD", 2025, 1)                 │
│     │    │    │    └─► MISS (current month) — skip cache;               │
│     │    │    │        OR within 30-day volatile window — skip cache    │
│     │    │    │        → iem.fetch("iem.archive", "KORD",               │
│     │    │    │              "2025-01-01", "2025-01-30")                │
│     │    │    │           └─► tradewinds.weather._vendor._iem.          │
│     │    │    │                  fetch_observations(...)                │
│     │    │    │                ├─► tradewinds._internal._http.get(...)  │
│     │    │    │                └─► returns raw rows                     │
│     │    │    └─► returns iem.archive-stamped rows in observation_v1    │
│     │    └─► concat partitions → DataFrame[observation_v1]              │
│     │                                                                    │
│   ROLE: forecasts (source="iem.archive") — parallel branch              │
│     └─► same flow → DataFrame[forecast_iem_mos_v1]                      │
│                                                                          │
│   ROLE: settlement (source="cli.archive") — parallel branch             │
│     └─► tradewinds.weather.catalog.get_adapter("cli.archive") → cli.py  │
│         └─► returns DataFrame[settlement_cli_v1]                        │
└────────────────────────────────────┬─────────────────────────────────────┘
                                     │
                                     ▼
┌──────────────────────────────────────────────────────────────────────────┐
│ STEP 3: per-role validation                                              │
│   For each role df:                                                      │
│     ├─► tradewinds.core.validator.validate_dataframe(df, schema_id)     │
│     │    ├─► schema = get_schema(schema_id)                             │
│     │    │    └─► triggers import tradewinds.core.schemas (lazy init)   │
│     │    ├─► Check columns match schema.columns                          │
│     │    ├─► Check non-null on schema.required_columns                  │
│     │    ├─► Check `source` column == declared source                   │
│     │    └─► Check knowledge_time tz-aware, knowledge_time <= now       │
│     │         (temporal-drift check — Amendments §B)                    │
│     └─► raises SchemaValidationError or SourceMismatchError on failure  │
└────────────────────────────────────┬─────────────────────────────────────┘
                                     │
                                     ▼
┌──────────────────────────────────────────────────────────────────────────┐
│ STEP 4: leakage-safe join via KnowledgeView                              │
│   For each market_close_utc in the contract series:                      │
│     ├─► obs_view = KnowledgeView(observations_df)                       │
│     ├─► row_obs = obs_view.as_of(market_close_utc).query(...)           │
│     │           └─► STRUCTURAL guarantee: row knowledge_time            │
│     │                <= market_close_utc                                │
│     ├─► (analogous for forecast and settlement)                         │
│     └─► join on (date, station)                                         │
└────────────────────────────────────┬─────────────────────────────────────┘
                                     │
                                     ▼
┌──────────────────────────────────────────────────────────────────────────┐
│ STEP 5: shape output                                                     │
│   Mode 2 output columns:                                                 │
│   date, station, contract,                                              │
│   cli_high_f, cli_low_f, obs_high_f, obs_low_f, fcst_high_f, fcst_low_f,│
│   obs_source, obs_retrieved_at,                                         │
│   fcst_source, fcst_retrieved_at,                                       │
│   settle_source, settle_retrieved_at                                    │
│                                                                          │
│   Mode 1 (sources=None) skips _source / _retrieved_at columns,          │
│   matching v0.14.1 byte-equivalent output.                              │
└────────────────────────────────────┬─────────────────────────────────────┘
                                     │
                                     ▼
                                   DataFrame
```

### State Management

There is **no** application state. Every primitive is either:

- A **frozen dataclass** (`TimePoint`, `Schema`, `ContractSpec`), or
- A **transient wrapper around an immutable DataFrame** (`KnowledgeView`), or
- A **module-level registry** populated once at import time (`_REGISTRY` in `catalog/__init__.py`, `_REGISTRY` in `schema.py`).

Module-level registries are not "state" in the application sense — they are populated deterministically on first import and never mutated. (The only writes happen in module body, before the module finishes importing.)

The closest thing to state is the **parquet cache on disk**. That is managed by `filelock` for concurrent process safety and is treated as an opaque speedup — the cache's contents are equivalent to (a subset of) what an `iem.archive` call would return today, so cache rows carry the same source ID. ROADMAP.md line 181 names this invariant explicitly.

### Key Data Flows

1. **`research()` Mode 1 (v0.14.1 parity).** Same as Mode 2 above, but: `sources=None` → defaults applied internally → output schema skips the `*_source` and `*_retrieved_at` columns. Mode 1 emits a `DeprecationWarning` starting v0.2 and is removed in v0.3.

2. **Validator-only flow (no fetch).** A user with an externally-sourced DataFrame: `validate_dataframe(df, "schema.observation.v1")`. Skips Steps 1-2 and the cache; touches the schema registry but no network. Returns `ValidationResult(ok=True/False, errors=[...])`.

3. **LeakageDetector audit flow.** A user with a BYO training set wants to confirm no future rows: `LeakageDetector(df).audit(as_of="2024-12-31")` → `LeakageReport(offending_rows=0)` or raises `LeakageError`. Independent from `KnowledgeView` because the user didn't build their training set through it.

4. **v0.2 MCP-server flow (future).** `catalog_search` MCP tool → reads `tradewinds.weather.catalog._REGISTRY` → returns source IDs. `pull_pairs` MCP tool → unwraps to `research()`. `validate_dataframe` MCP tool → unwraps to `tradewinds.core.validator.validate_dataframe`. Errors caught at the JSON-RPC boundary use `TradewindsError.to_dict()` for serializable payloads.

---

## Scaling Considerations

| Scale | Architecture adjustments |
|-------|--------------------------|
| **Single dev's laptop** (v0.1 target — user has cache of one station, last 90 days) | No adjustments needed. Per-file parquet, in-process registries, sync HTTP. |
| **Notebook user** (1-5 stations, last 2 years) | Per-file cache holds ~120 files; still fast. Sync HTTP is fine — fetches are bounded by `from_date`/`to_date` user input. |
| **Heavy backtester** (50+ stations × multi-year) | First bottleneck is HTTP — adapter fetches sequentially per (station, source). Mitigation: **async batch fetch** at the adapter level (`fetch_batch(stations, range, source)`) — requires extending `WeatherAdapter` Protocol with an optional `batch_fetch` method, falling back to a loop. Not in v0.1; v0.2 candidate. |
| **v0.2 hosted R2 cache** (multi-user shared cache) | Per-file → `pyarrow.dataset` Hive partitioning. Migration path: rewrite `cache.read_partition` → `cache.read_range`, drop the per-month iteration. Schema unchanged. |
| **v0.3+ external contributors registering adapters** | Add entry-points-based registration alongside the in-package eager registry. Reuses the same Protocol. |

### Scaling Priorities

1. **First bottleneck (when it shows up):** sequential HTTP from `_vendor/_iem.py` and friends. Each call is ~200ms; a 90-day fetch for one station is one call (the IEM endpoint is range-capable). A backtest over 50 stations × 1 source = 50 HTTP calls = ~10s, still acceptable.
2. **Second bottleneck:** parquet read on big jobs. At ~120 files/station/decade, a single `read_partition` loop over all files for one station is ~2s cold. Switching to `pyarrow.dataset` predicate pushdown brings this to <0.5s. This is the v0.2 migration if observed.
3. **Third bottleneck (theoretical, never reached in v0.1):** the schema registry's `dict[str, Schema]` is O(1) lookup; not a concern. The catalog registry is similarly O(1).

---

## Anti-Patterns

### Anti-Pattern 1: Mixing `__init__.py` styles in the namespace

**What people do:** Some distributions ship a `tradewinds/__init__.py` (e.g. for `__version__`), others don't.

**Why it's wrong:** Whichever package's namespace-root `__init__.py` is imported first shadows all sibling distributions. Symptoms: `import tradewinds.weather` works in dev (where one ordering happens) and breaks for some users (where a different sys.path ordering happens). This is the precise failure mode PEP 420 was created to eliminate.

**Do this instead:** **Every** distribution that contributes to `tradewinds.*` omits the `tradewinds/__init__.py`. Each places its content under `tradewinds.<subpkg>/__init__.py` exclusively. If you need `__version__`, put it in `tradewinds.<subpkg>.__version__` (every dist has its own).

### Anti-Pattern 2: Decorator-based adapter registration without explicit import

**What people do:** `@catalog.register("iem.archive")` on a class in `iem.py`, then in `catalog/__init__.py` write nothing, expecting "Python will discover it."

**Why it's wrong:** Python doesn't auto-discover. The decorator fires only when `iem.py` is imported. If `catalog/__init__.py` doesn't import it, the registry is empty. This is a 4am bug.

**Do this instead:** Explicit eager imports in `catalog/__init__.py`. Declarative. Greppable. (See Pattern 3 above.)

### Anti-Pattern 3: `@dataclass(frozen=True)` exceptions

**What people do:** `@dataclass(frozen=True)` on top of `class FooError(Exception)` to get free constructor + `__repr__` + immutability.

**Why it's wrong:** `dataclass` generates `__init__` from fields, but `Exception.__init__(*args)` expects positional args that become `self.args` for pickling. The interaction is subtle: pickling fails silently across processes, multiprocessing tests get hangs not errors, and `e.args` ends up containing the dataclass field tuple instead of `(msg,)`.

**Do this instead:** Plain class, explicit `__init__`, explicit `super().__init__(msg)` to populate `self.args = (msg,)`. (See Pattern 7 above.)

### Anti-Pattern 4: `pd.api.extensions.register_dataframe_accessor` for cross-cutting logic

**What people do:** `@pd.api.extensions.register_dataframe_accessor("knowledge")` so any DataFrame can do `df.knowledge.as_of(ts)`.

**Why it's wrong:** Pandas accessors are **global mutable state**. Importing `tradewinds.core.temporal` globally installs `.knowledge` on every DataFrame in the process. Two libraries that both try to register `.knowledge` conflict at import time. Test isolation requires explicit `del pd.DataFrame.knowledge` cleanup (which itself is fragile). Temporal-safety is far too important a guarantee to bury behind global pandas state.

**Do this instead:** Explicit wrapper class with constructor validation: `KnowledgeView(df).as_of(ts)`. (See Pattern 6 above.)

### Anti-Pattern 5: Vendoring code under a public-looking path

**What people do:** Put lifted parsers in `tradewinds.weather.parsers.iem` (no leading underscore).

**Why it's wrong:** Users will start importing it. Any bug fix that requires re-lifting from upstream is now a breaking change for those users.

**Do this instead:** `_vendor/` prefix (private contract). Public surface is the `catalog/` wrapper. (See Pattern 4 above.)

### Anti-Pattern 6: Hive-partitioning a small dataset for "future-proofing"

**What people do:** Set up `pyarrow.dataset` with Hive partitioning for ~50 cache files because "we'll need it later when we have more data."

**Why it's wrong:** Hive partitioning adds a dataset-construction overhead per query, complicates filelock semantics (now you need directory-level locks for atomic month writes), and makes the human-debug path harder (`station=KORD/year=2025/month=01/part-0.parquet` versus `KORD/2025/01.parquet`). For ~50 files, predicate pushdown isn't even faster than a plain loop.

**Do this instead:** Per-file partition until the query pattern actually requires `pyarrow.dataset` filtering. Migration is mechanical when needed. (See Pattern 8 above.)

---

## Integration Points

### External Services

| Service | Integration pattern | Notes |
|---------|---------------------|-------|
| **AWC (NOAA aviation)** | Per-request `httpx` GET to `aviationweather.gov`; JSON response | `awc.live` only; not cached (volatile). Adapter: `tradewinds.weather.catalog.awc`. |
| **IEM (Iowa State)** | `httpx` GET to `mesonet.agron.iastate.edu`; CSV/JSON | Both archive and live source IDs. Adapter: `tradewinds.weather.catalog.iem`. Cached for archive only. |
| **GHCNh (NCEI)** | `httpx` GET to `ncei.noaa.gov`; CSV | Archive only; cached. Adapter: `tradewinds.weather.catalog.ghcnh`. |
| **NWS CLI** | `httpx` GET to `forecast.weather.gov`; HTML scrape | Archive only; cached. Adapter: `tradewinds.weather.catalog.cli`. Settlement source for Kalshi NHIGH/NLOW. |
| **Kalshi API** | v0.1: spec only (no API client). Sprint 0.5+: `tradewinds.markets._kalshi_api` calls REST endpoints. | v0.1 ships static `ContractSpec` for NHIGH/NLOW. |

All HTTP calls go through `tradewinds._internal._http` (lifted from monorepo-v0.14.1), which provides retry, timeout, and User-Agent headers. The `_internal` underscore prefix means this is private — adapters import it but external users should not.

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| `tradewinds.research` → `tradewinds.weather.catalog` | **Lazy import** (`importlib.import_module`) keyed by source-ID family | Breaks the package import cycle. `tradewinds` (core) does NOT statically depend on `tradewinds-weather`. |
| `tradewinds.weather.catalog.*` → `tradewinds.core.schema` | Direct import; the catalog produces canonical-schema rows | Requires `tradewinds-weather` to declare `tradewinds` as a runtime dep (currently MISSING — see Pattern 2). |
| `tradewinds.weather.catalog.*` → `tradewinds.weather._vendor.*` | Direct import within same package | The wrapper-over-`_vendor` is the *raison d'être* of the catalog layer. |
| `tradewinds.weather.cache` → `tradewinds.weather.catalog.*` | The cache is INSIDE the weather package, called by adapters before going out to HTTP | Adapter is the public face; cache is internal to weather. |
| `tradewinds.markets.catalog.*` → `tradewinds.core.schema` | Direct import — markets package owns ContractSpec which contains schema references | Markets depends on `tradewinds` (core) at runtime — see Pattern 2. |
| `tradewinds.research` → `tradewinds.core.{temporal,validator,exceptions}` | Direct imports (same dist) | No cross-dist coupling. |
| **v0.2:** `tradewinds.mcp.tools.*` → all of the above | The MCP server is a thin shell over the core + catalog APIs | The seam is the JSON-RPC boundary; everything below is the same as the SDK. |

### Build order (verified against `tool.uv.sources` settings)

```
tradewinds (core)
    │
    ├─ tradewinds-weather  ──┐
    │                        │
    └─ tradewinds-markets  ──┤
                             ▼
                       tradewinds-mcp (v0.2)
```

**Concrete:** uv resolves the workspace in topological order. `uv sync` installs core first (no workspace deps), then weather and markets in parallel (both depend on core only), then mcp last (depends on everything). PyPI release order at v0.1.0 is core → (weather, markets) → mcp(v0.2).

---

## Sources

- [PEP 420 — Implicit Namespace Packages](https://peps.python.org/pep-0420/) — canonical PEP for native namespace packages
- [Python Packaging User Guide — Packaging namespace packages](https://packaging.python.org/en/latest/guides/packaging-namespace-packages/) — official PyPA recommendation
- [pypa/hatch discussion #819 — namespace package configuration](https://github.com/pypa/hatch/discussions/819) — hatchling-specific `[tool.hatch.build.targets.wheel]` settings
- [uv docs — Workspaces](https://docs.astral.sh/uv/concepts/projects/workspaces/) — `tool.uv.sources` workspace resolution
- [uv docs — Managing dependencies](https://docs.astral.sh/uv/concepts/projects/dependencies/) — cross-package deps
- [pip Vendoring Policy](https://pip.pypa.io/en/stable/development/vendoring-policy/) — `_vendor/` convention reference
- [pandas — Extending pandas](https://pandas.pydata.org/docs/development/extending.html) — accessor caveats
- [pyarrow.dataset.partitioning](https://arrow.apache.org/docs/python/generated/pyarrow.dataset.partitioning.html) — Hive vs Directory vs Filename partitioning
- [pyarrow Tabular Datasets](https://arrow.apache.org/docs/python/dataset.html) — predicate pushdown / dataset API
- [mypy — Protocols and structural subtyping](https://mypy.readthedocs.io/en/stable/protocols.html) — Protocol vs ABC
- [Python dataclasses docs](https://docs.python.org/3/library/dataclasses.html) — dataclass + Exception interaction caveats
- [Josh Cannon — Python Namespace Packages are a pain (2025)](https://joshcannon.me/2025/08/16/py-namespace-packages.html) — dissenting view considered, deemed not applicable for our case (single-namespace, single-author scenario)

---
*Architecture research for: tradewinds — three-layer local-first Python SDK with shared namespace*
*Researched: 2026-05-21*

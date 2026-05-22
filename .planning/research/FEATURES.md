# Feature Research

**Domain:** Local-first Python SDK for quantitative researchers (financial data + prediction-market settlement)
**Researched:** 2026-05-21
**Confidence:** HIGH (table stakes verified against 5+ contemporary financial-data SDKs; differentiators cross-checked against feature-store/data-contract literature; anti-features grounded in PROJECT.md Out-of-Scope)

## Reading guide for downstream consumer

Every row in the tables below is tagged with:

- **PROJECT.md status** — `COVERED` (an Active requirement already mandates this), `PARTIAL` (related requirement exists but explicit coverage is implicit), `GAP` (worth adding to Active or capturing as a Key Decision), `OUT-OF-SCOPE` (already listed in PROJECT.md Out of Scope), or `ANTI-FEATURE` (recommend explicitly NOT building).
- Buy-not-build candidates carry a specific package name + version in the Notes column.

No locked requirement (CORE-01..05, CATALOG-01..05, RESEARCH-01, CACHE-01..02, PARITY-01, PKG-01, QUICKSTART-01, MIGRATION-01, CI-01) is re-derived here. The exercise is to surround them with the ecosystem context that confirms or challenges their completeness.

## Feature Landscape

### Table Stakes (Users Expect These)

What a 2026 quant assumes will be present in a financial-data Python SDK. Missing = "this feels half-baked."

| Feature | Why Expected | Complexity | PROJECT.md status | Notes |
|---------|--------------|------------|-------------------|-------|
| Full type hints on public API | mypy/Pyright/Pylance is universal in 2026 quant codebases; SDKs without hints get rejected on first import | LOW | GAP (implicit in Python 3.11+ stack; worth pinning as a CI gate) | Add `ruff` rule + `mypy --strict` on `tradewinds.core.*` public surface |
| pandas DataFrame as default return | Notebook-first quant workflow; every adjacent library (`vectorbt`, `quantstats`, `pandas-ta`) consumes pandas | LOW | COVERED (CORE-05 `dataframe` format) | Default `format="dataframe"` is correct per ROADMAP line 161 |
| Multi-format serialization (JSON, parquet, CSV) | Persistence + cross-language handoff; parquet for cache, CSV for spreadsheet handoff, JSON for MCP/web | LOW | COVERED (CORE-05) | Five formats listed (dataframe, json, parquet, toon, csv); roundtrip tests are the right bar |
| Structured exception hierarchy | Quants want `try/except SourceUnavailableError` not `except Exception`. Stripe SDK, OpenAI SDK, Anthropic SDK all model this. | LOW | COVERED (CORE-04) | `TradewindsError` root + 4 typed subclasses with structured payloads = current best practice |
| Local cache with corruption safety | yfinance/alpha-vantage outages train users to cache; `filelock` for concurrent notebooks is non-negotiable | MEDIUM | COVERED (CACHE-01, CACHE-02) | `filelock` + parquet is the right choice; cache preserves source identity is the right invariant |
| Retry with exponential backoff + jitter | 429s from public APIs (IEM, AWC, NWS) are routine; SDKs without this get rate-limited into uselessness | LOW | GAP (not in Active requirements; assumed in `_internal/` lift from v0.14.1) | Buy-not-build: `tenacity==9.x` (or `httpx-retries` for an HTTP-transport-level approach). Verify v0.14.1 lift includes this; if not, add as CORE-06. |
| HTTP/2 + async-capable client | OpenAI/Anthropic SDKs use `httpx`; setting the bar | LOW | COVERED (PROJECT.md Constraints pin `httpx`) | `httpx` (not `requests`, not `aiohttp`) is the right call — sync API is sufficient for v0.1 notebook workflows; async seam preserved |
| Quickstart that works in <5 minutes | Notebook user attention budget; if `pip install + first-call` fails, they bounce | MEDIUM | COVERED (QUICKSTART-01 with timed external validator) | This is itself a differentiator vs `mostlyright==0.14.1` if v0.14.1's quickstart was rougher |
| Versioned schemas with explicit names | `schema.observation.v1` lets users pin against schema drift; this is how `dbt`, `Soda`, `Confluent Schema Registry` all model it | MEDIUM | COVERED (CORE-03) | Three schemas pinned with `.v1` suffix is exactly right — leaves room for `.v2` without breaking callers |
| Property-based tests on temporal primitives | High-bar libraries (NumPy, Pandas, OpenAI) use Hypothesis; quants reviewing code expect it for anything claiming "correctness" | MEDIUM | COVERED (CORE-01 mandates Hypothesis + ≥90% branch coverage) | The temporal-safety claim is unfalsifiable without it |
| Docstrings with `Examples:` section | Sphinx/NumPy/Google style is universal; doctest-runnable examples are the gold standard | LOW | GAP (not in Active requirements; QUICKSTART-01 covers README, not API docstrings) | Recommend: NumPy-style docstrings on `research()`, `KnowledgeView`, `Validator`. Run `doctest` in CI. Add to CI-01 or add as `DOCS-01`. |
| Pinned Python version with floor | Python 3.11+ stated; 3.10 EOL is October 2026 | LOW | COVERED (PROJECT.md Constraints: Python 3.11+) | uv workspace + `requires-python = ">=3.11"` |
| Version-pinned dependencies | Quant production envs are reproducibility-obsessed; `uv.lock` + version ranges are baseline | LOW | COVERED (PROJECT.md Constraints: uv workspace) | uv handles this |
| Configurable HTTP timeout | Public APIs (IEM especially) can be slow; defaults should be tunable per call | LOW | GAP (not in Active requirements; assumed in `_internal/`) | Verify v0.14.1 lift exposes this; if not, add to `_internal/http.py` constructor |
| Sensible logging (not `print`) | Notebook users want quiet by default; production users want to enable INFO/DEBUG | LOW | GAP (not in Active requirements) | `logging.getLogger("tradewinds")` with NullHandler default. Trivial; add to Day 5 core scaffolding. |
| User-Agent identifying the SDK | Public API operators (IEM, NWS) ask for this in their ToS; missing it gets you rate-limited harder | LOW | GAP (not in Active requirements; may be in v0.14.1 lift) | `User-Agent: tradewinds/0.1.0 (https://github.com/...)`. Verify in lift; if missing, add. |
| Stable column names in DataFrame output | Quants build pipelines against column names; renaming = breaking change | LOW | COVERED (PARITY-01 byte-equivalence + RESEARCH-01 Mode 2 schema) | Two-mode design (parity-mode columns frozen + source-explicit-mode schema-versioned) is exactly the right pattern |

### Differentiators (Competitive Advantage)

Features where tradewinds out-distances v0.14.1, mostlyright-mcp paper design, and the rest of the prediction-market Python ecosystem.

| Feature | Value Proposition | Complexity | PROJECT.md status | Notes |
|---------|-------------------|------------|-------------------|-------|
| Structural temporal-leakage prevention via `KnowledgeView` | Quants currently DIY this with `df[df.time <= as_of]` and bugs ensue. Built-in primitive that REFUSES to return future rows is unique in this segment. | HIGH | COVERED (CORE-01) | Most direct prior art: Feast's `point-in-time joins` and Databricks Feature Store `timestamp_keys`. Both are heavyweight platforms; tradewinds offers the primitive as a library, not infrastructure. **Buy-not-build assessment: BUILD.** Feast (`feast==0.63.0`, May 2026) is too heavy a dep for a local-first SDK and pulls in Pydantic v2, SQLAlchemy, FastAPI, etc. Pandas `merge_asof` + DuckDB `ASOF JOIN` are the building blocks but neither expresses the source-identity coupling we need. |
| Source-identity invariant (`SourceMismatchError` on train/infer mismatch) | The hidden killer in prediction-market modeling: model trained on `iem.archive`, scoring against `awc.live`, silently corrupting P&L. No competing SDK enforces this. | HIGH | COVERED (CORE-02, RESEARCH-01) | Conceptual prior art: data contracts (`Soda`, `Great Expectations`, `datacontract-specification`). None of those check the *runtime equivalence* of source IDs between training data and inference data. tradewinds invents this primitive for the prediction-market vertical. **Buy-not-build: BUILD.** |
| Canonical schemas with `event_time`, `knowledge_time`, `source`, `retrieved_at` required columns | Forces every downstream pipeline to carry temporal+lineage metadata. Most SDKs return raw API rows; this is opinionated. | MEDIUM | COVERED (CORE-03 + Amendments §A in ROADMAP) | Validates against `pandera==0.29` (Jan 2026) or `jsonschema`. **Buy-not-build (validation engine): pandera==0.29** — works against pandas + Polars + pyarrow with a single schema definition, integrates with pydantic. Recommend using pandera under the hood for `Validator.validate_dataframe()`, while still owning the canonical schema definitions. This swaps custom validation code for a maintained library. |
| Byte-equivalent parity gate against `mostlyright==0.14.1` | Migration risk killer; zero-cost cutover for existing users. No competing SDK does this. | HIGH | COVERED (PARITY-01 + MIGRATION-01) | Self-imposed hard gate is the right discipline; 5-fixture test is enough |
| Three-package workspace (`tradewinds` / `tradewinds-weather` / `tradewinds-markets`) | Notebook users don't drag Kalshi markets code into a weather-only workflow; pre-shapes for verticals N+1. | MEDIUM | COVERED (PKG-01 + Key Decision) | Right design; aligns with how `awesome-quant` libraries are factored |
| Settlement-source resolution from contract spec | `research(contract="KXHIGHNYC", ...)` resolves NHIGH → `cli.archive` automatically. Removes the most common source-identity error before it can happen. | MEDIUM | COVERED (CATALOG-05 + RESEARCH-01) | Differentiator over "raw API client" libraries (pyiem, etc.) |
| LeakageDetector audit tool for BYO training sets | Users who built data the OLD way can validate it. Critical for the migration story. | MEDIUM | COVERED (CORE-01 lists `LeakageDetector`) | Prior art: sklearn `TimeSeriesSplit` (split-only, not detect), `nannyml` + `evidently` (drift, not leakage). LeakageDetector is novel for this segment. **Buy-not-build: BUILD.** |
| 30-day volatile-window cache exclusion | Archive data within 30 days is still mutable (CLI corrections, IEM late-arriving METAR); excluding from cache is correct domain behavior most SDKs miss | MEDIUM | COVERED (CACHE-01) | Domain-correct policy; not a generic feature. v0.14.1 already has it; preserved correctly. |
| Local-first with NO hosted backend | Quants in trading shops can't legally send data to a vendor; local-first is a hard constraint for many | LOW | COVERED (PROJECT.md Core Value + Constraints) | Just don't build the alternative; this is a posture, not a feature |
| TOON serialization format | Compact-token format for LLM/agent handoff; preserves schema; rare in quant SDKs | LOW | COVERED (CORE-05) | Lifted from v0.14.1; useful for the v0.2 MCP server reuse. |
| MCP-server-shaped seam at `packages/mcp/` | Future-proofs for agentic workflows without paying the cost now | LOW | COVERED (PROJECT.md Out of Scope: "MCP server — deferred to v0.2; `packages/mcp/` scaffolded as stub only") | Seam without commitment; the right move |

### Anti-Features (Commonly Requested, Often Problematic)

Features that a 2026 quant might ask for but that would damage tradewinds. Categorized as DEFERRED (later milestone), OUT-OF-SCOPE-NEVER (anti-feature for this product), or ALREADY-LISTED (already in PROJECT.md Out of Scope).

| Feature | Why Requested | Why Problematic | Alternative | PROJECT.md status |
|---------|---------------|-----------------|-------------|-------------------|
| Open-Meteo adapter | Free forecast API, popular in hobbyist projects | Licensing blocks redistribution; would block v0.2 hosted cache and downstream redistribution by `mostly-light`. Hidden cost of one PR that nobody can ever undo. | Stick to AWC/IEM/GHCNh/NWS CLI (all government, redistributable) | ALREADY-LISTED (Out of Scope, all v0.x) — keep firm |
| Kalshi orderbook + fills API client | "It's a Kalshi SDK, why doesn't it trade?" | Bundles broker risk into a data SDK; doubles surface area; creates auth-token / key-management responsibilities; conflicts with local-first posture | `tradewinds-markets` v0.1 ships contract specs only; orderbook/fills wait for Sprint 0.5+ in their own boundary (or stay as a downstream library) | ALREADY-LISTED (Out of Scope: Kalshi API client) |
| MCP server in v0.1 | Hot in 2026; agents want to call `pull_pairs` | Adds 6 weeks of scope (JSON-RPC, tool wiring, subprocess integration tests) without moving the v0.1 user value. Failure mode of mostlyright-mcp's original plan. | Seam at `packages/mcp/` (stub only); real wiring in v0.2 with empirical demand evidence | ALREADY-LISTED (Out of Scope, deferred to v0.2) |
| Hosted R2 cache | "Speed up everyone's queries with a CDN" | Pays vendor + ops cost before the 60-day validation gate proves anyone wants the product. Sunk-cost trap. | Local cache only in v0.1; hosted-cache feasibility revisited only if 3 named external users persist 60 days | ALREADY-LISTED (Out of Scope; gated on validation) |
| Sports / politics / finance verticals | "I want to research NFL prediction markets" | Domain expertise per vertical is hard-won; weather has 1 trusted settlement source (NWS CLI), sports has a dozen, politics is contested. Doing two badly is worse than one well. | One vertical at a time; weather only for v0.x | ALREADY-LISTED (Out of Scope) |
| Preprocessing (RH, feels_like, MetPy re-parse) | "Just give me the engineered features" | Steals quants' modeling autonomy; opinions about feels_like differ; locks in a specific preprocessing version | Preserve `raw_metar` in observation rows; preprocessing is opt-in via explicit transform calls in Sprint 0.5+ | ALREADY-LISTED (Out of Scope, raw preserved) |
| CLI surface (`tradewinds research ...`) | DX convenience for quick checks | Diffuses the Python-first design; CLI surface drifts from Python surface; doubles maintenance | Python SDK only; CLI revisited at v1.1+ once API surface is stable | ALREADY-LISTED (Out of Scope) |
| `as_of_query` generic MCP tool | "Let agents query anything" | "Anything" = no schema enforcement = silent leakage. Inverts the temporal-safety thesis. | Build only named, schema-enforced tools (`pull_pairs`, `validate_dataframe`) in v0.2; `as_of_query` ships only when a named user requests it | ALREADY-LISTED (Out of Scope) |
| Async public API (`async def research(...)`) | OpenAI/Anthropic SDKs are async-first; "is this 2026 modern?" | Notebook quant workflow is sync; doubling the surface area for v0.1 adds maintenance + tests with no validated demand. **Note: this conflicts with FMP/OpenAI SDK 2026 conventions, so call it out explicitly.** | Sync API in v0.1; `httpx` chosen specifically to preserve the async seam at zero cost. Add `aresearch()` only when a named user requests it. | GAP — recommend adding to Out of Scope as "Async API surface — v0.1 sync only; async seam preserved via `httpx`" |
| Pydantic models as primary return type | "Type safety is hot" | Notebook quants work in DataFrames; row-wise pydantic doesn't scale (`pandera` docs explicitly warn this). | DataFrames are primary; offer pandera DataFrameSchema for validation, not row-wise pydantic | GAP — recommend adding as a Key Decision: "DataFrame-first, pandera for validation, no row-wise pydantic" |
| Polars as primary return type | Polars is faster; "make tradewinds 30x faster" | (a) Forces every downstream tool to convert; (b) `mostly-light` uses pandas; (c) v0.14.1 parity is pandas. Net cost > benefit for v0.1. | Pandas-first; pandera schemas portable to Polars in v0.2+ if demand emerges (pandera 0.29 supports both backends from one schema) | GAP — recommend adding as a Key Decision: "pandas-first v0.1; Polars support deferred to v0.2 if demand emerges" |
| Built-in backtesting engine (`tradewinds.backtest(...)`) | "While you're there, why not give me a backtest?" | vectorbt + quantstats already do this well; quants will use their own engine; bundling forces opinions about position sizing, P&L accounting, etc. | Return clean training pairs; let users plug into `vectorbt==0.27+`, `quantstats==0.0.85+`, or their own engine | GAP — recommend explicitly adding "Backtesting engine" to Out of Scope to forestall scope creep |
| Hosted feature store (Feast/Tecton-style) | "Modern ML practice" | Pays infrastructure cost; conflicts with local-first; Feast pulls in FastAPI + SQLAlchemy + Pydantic v2 (~30MB of deps for what we don't use) | tradewinds is a data SDK, not a feature store. Users wanting a feature store can write a thin adapter into Feast on top of tradewinds. | GAP — recommend adding to Out of Scope: "Hosted feature store — tradewinds returns dataframes; adapt to Feast/Tecton externally if needed" |
| Auto-generated connectors from API specs | mostlyright-mcp's original Layer 2 vision | Code-gen quality from public API specs is poor; debug surface explodes; doesn't compose with our `_vendor/` lifted-and-tested parsers | Hand-written adapters under `_vendor/` + `catalog/*.py`; lift from v0.14.1 | ALREADY-LISTED (Out of Scope: "Agent-generated connectors — v2+") |

## Buy-not-Build Candidates (Specific Library Recommendations)

Concrete libraries to adopt vs. write ourselves. Pin versions as of May 2026.

| Need | Recommended Library | Version | Why | PROJECT.md status |
|------|---------------------|---------|-----|-------------------|
| HTTP client (sync + async seam) | `httpx` | `>=0.27,<1.0` | Already pinned in Constraints; OpenAI/Anthropic standard; HTTP/2 ready | COVERED |
| File locking for cache writes | `filelock` | `>=3.13` | Already pinned in Constraints; cross-platform | COVERED |
| Retry with exponential backoff | `tenacity` | `>=9.0` | De facto standard 2026; composable; async-compatible; OR use `httpx-retries==0.3+` at transport layer | GAP — add to Constraints if not in v0.14.1 lift |
| DataFrame schema validation | `pandera` | `==0.29` (Jan 2026) | Use as backing engine for `Validator.validate_dataframe()` while keeping canonical schemas as our own Schema objects; supports pandas + Polars + pyarrow from one schema | GAP — recommend adopting; mentioned nowhere in current Active requirements (CORE-02 implies build-from-scratch). **Decision needed:** build `Validator` on top of pandera, or build from scratch using `jsonschema` (already in Constraints)? Pandera is more dataframe-native. |
| JSON Schema validation for IEM forecast spec files | `jsonschema` | `>=4.21` | Already pinned in Constraints; correct for the `_forecast_schema.py` use case (validating JSON specs lifted from v0.14.1) | COVERED |
| Property-based tests | `hypothesis` | `>=6.150` | Already pinned in Constraints (dev); essential for CORE-01 temporal invariants | COVERED |
| Parquet I/O | `pyarrow` | `>=15` | Already pinned in Constraints; powers both pandas parquet and CACHE-01 | COVERED |
| As-of joins (internal) | `pandas.merge_asof` (existing) or `duckdb==1.x` ASOF JOIN | n/a | For `KnowledgeView` implementation: `merge_asof` is sufficient and adds zero deps; DuckDB is overkill for v0.1 | COVERED (implicit; no new dep needed) |
| Drift detection (NOT recommended for v0.1) | `nannyml==0.13+` or `evidently==0.5+` | — | Out of scope for v0.1 — these detect drift, not leakage. Different problem. **Do not bring in.** | n/a — listed for completeness |
| Feature store (NOT recommended for v0.1) | `feast==0.63` (May 2026) | — | Too heavy a dep for local-first SDK; ~30MB deps incl FastAPI, SQLAlchemy, Pydantic v2. **Do not bring in.** | n/a — listed for completeness |
| Data contracts framework (NOT recommended) | `Soda v4` or `Great Expectations 1.x` | — | Designed for warehouse-side validation (post-load), not SDK-internal. **Do not bring in.** Our source-identity invariant is more specific. | n/a — listed for completeness |

## Feature Dependencies

```
PARITY-01 (byte-equivalent v0.14.1)
    └──depends-on──> v0.14.1 lift (Phase A)
                          └──depends-on──> _vendor/_iem.py, _awc.py, _climate.py, _ghcnh.py, _forecast_*.py

CORE-01 (TimePoint, KnowledgeView, LeakageDetector)
    └──depends-on──> Hypothesis dev dep
    └──depends-on──> nothing else in v0.1; structural

CORE-02 (Validator with source-identity)
    └──depends-on──> CORE-01 (Schema definition)
    └──enhanced-by──> pandera==0.29  [BUY-NOT-BUILD recommendation]

CORE-03 (canonical schemas)
    └──depends-on──> CORE-01 (Schema primitive)
    └──depends-on──> Amendments §A from ROADMAP

CORE-04 (exception hierarchy)
    └──depends-on──> nothing; can build Day 1

CATALOG-01..04 (adapters)
    └──depends-on──> CORE-03 (schemas to emit against)
    └──depends-on──> _vendor/ (lifted parsers)
    └──depends-on──> _internal/http.py (retry, timeout, User-Agent)

CATALOG-05 (Kalshi NHIGH/NLOW specs)
    └──depends-on──> CATALOG-03 (CLI adapter, for settlement source ID)

RESEARCH-01 (research() Mode 2)
    └──depends-on──> CORE-01 (KnowledgeView)
    └──depends-on──> CORE-02 (Validator for per-role validation)
    └──depends-on──> CATALOG-01..05 (sources to dispatch)

CACHE-01..02 (parquet cache)
    └──depends-on──> CATALOG-01..04 (sources to cache)
    └──depends-on──> pyarrow, filelock

MIGRATION-01 (mostly-light kxhigh dry-run)
    └──depends-on──> PARITY-01 (Mode 1 byte-equiv)
    └──depends-on──> PKG-01 (publishable artifacts)

GAP: retries/timeouts/User-Agent
    └──goes-into──> _internal/http.py
    └──either: lifted from v0.14.1 OR add as CORE-06

GAP: doctest + NumPy-style docstrings
    └──goes-into──> CI-01
    └──affects──> QUICKSTART-01 (examples in docstrings = examples in quickstart)
```

### Dependency Notes

- **CORE-02 enhanced by pandera:** Building `Validator` on top of `pandera==0.29` gives us multi-backend support (pandas+Polars+pyarrow from one schema) for free and removes ~300 LOC we'd otherwise own. Canonical schemas (`schema.observation.v1` etc.) remain ours; pandera is the engine.
- **CATALOG-* depend on _internal/http.py:** The GAP items (retries, timeouts, User-Agent) live here. Verify the v0.14.1 lift includes them; if not, they're additive to the Phase A scaffold without changing the parity contract (Mode 1 just doesn't exercise them deeply).
- **GAP: retries/timeouts/User-Agent:** A Phase A audit item — verify these are present in the v0.14.1 lift. If yes, no action. If no, add a CORE-06 requirement (`_internal/http.py` with retry/timeout/User-Agent semantics) before Phase B Day 6 (when adapters start using the shared HTTP layer).

## MVP Definition

### Launch With (v0.1.0)

Already locked in PROJECT.md Active requirements. No changes from research:

- All CORE-01..05 (temporal safety + validation + schemas + exceptions + serialization)
- All CATALOG-01..05 (IEM, AWC, CLI, GHCNh + Kalshi NHIGH/NLOW specs)
- RESEARCH-01 (Mode 2 source-explicit)
- CACHE-01..02 (parquet + source-preserving cache)
- PARITY-01 (5-fixture byte-equivalence)
- PKG-01 (three-package PyPI workspace)
- QUICKSTART-01 (<5min timed)
- MIGRATION-01 (mostly-light kxhigh)
- CI-01 (GH Actions + trusted publishing)

### Gaps Worth Adding to v0.1 Active Requirements

Items the research surfaced that aren't currently covered:

- [ ] **CORE-06 (proposed): HTTP layer with retry/timeout/User-Agent** — Audit `_internal/http.py` lift from v0.14.1. If present, mark COVERED. If absent, add `tenacity>=9.0` to Constraints and implement: `httpx.Client` with `transport=tenacity_retry_transport`, configurable timeout, `User-Agent: tradewinds/{version} (https://github.com/...)`. Effort: 0.5 day.
- [ ] **DOCS-01 (proposed): NumPy-style docstrings + doctest in CI** — Run `pytest --doctest-modules tradewinds/` in CI. Forces docstring examples to stay accurate. Effort: 0.5 day for setup; recurring cost is owned by code authors.
- [ ] **Key Decision (proposed): "DataFrame-first, pandera for validation, no row-wise pydantic"** — Documents the rejection of pydantic-models-as-API and explains the pandera adoption (if accepted).
- [ ] **Key Decision (proposed): "pandas-first v0.1; Polars deferred to v0.2 if demand emerges"** — Forestalls Polars-RFC noise during v0.1 sprint.
- [ ] **Out of Scope addition (proposed): "Async API surface (`aresearch()`)"** — Documents the deliberate sync-only choice in v0.1 with `httpx` preserving the seam.
- [ ] **Out of Scope addition (proposed): "Built-in backtesting engine"** — Forestalls future scope creep by being explicit that tradewinds returns training pairs, not P&L.
- [ ] **Out of Scope addition (proposed): "Hosted feature store integration"** — Documents that Feast/Tecton adapters are downstream concerns, not tradewinds concerns.

### Add After Validation (v0.2)

Already documented in PROJECT.md Out of Scope, listed here for completeness:

- MCP server (real, not stub)
- Hosted R2 cache (only if 60-day validation gate passes)
- Mode 1 deprecation warning (then removal in v0.3)

### Future Consideration (v1.x+)

- Polars return type (if demand)
- Async API surface (if demand)
- Sports / politics / finance verticals (each new vertical: separate `tradewinds-{vertical}` package)
- CLI surface (`tradewinds research ...`)
- Preprocessing helpers (`tradewinds.transforms.rh()`, `feels_like()`)

## Feature Prioritization Matrix

Only items NOT already locked in PROJECT.md Active requirements are scored. Locked items are assumed P1.

| Feature | User Value | Implementation Cost | Priority | Recommendation |
|---------|------------|---------------------|----------|----------------|
| Audit + (if missing) add retry/timeout/User-Agent (`CORE-06`) | HIGH | LOW | P1 | Audit Day 5; add if missing |
| Docstrings + doctest in CI (`DOCS-01`) | MEDIUM | LOW | P2 | Day 13 (alongside QUICKSTART-01) |
| Adopt `pandera==0.29` as Validator backend | MEDIUM | LOW (saves LOC) | P1-or-P2 | Day 5-6 decision; if adopted, simplifies CORE-02 |
| Document async/Polars/backtest as OOS in PROJECT.md | LOW (preventive) | LOW | P2 | Phase B Day 5 PROJECT.md update |
| Logging via `logging.getLogger("tradewinds")` | LOW | LOW | P2 | Day 5 core scaffolding |
| Build LeakageDetector for BYO training sets | HIGH | MEDIUM | P1 (locked in CORE-01) | Already scoped Day 7 |
| Build KnowledgeView with property tests | VERY HIGH | HIGH | P1 (locked in CORE-01) | Already scoped Day 5 |

**Priority key:**
- P1: Must have for v0.1.0
- P2: Should have, add when possible (likely v0.1.0 if cheap; v0.1.x if not)
- P3: Nice to have, future consideration

## Competitor / Adjacent Feature Analysis

| Feature | `mostlyright==0.14.1` | `feast==0.63` | `pyiem` | `vectorbt` + `quantstats` | tradewinds v0.1 |
|---------|----------------------|---------------|---------|---------------------------|-----------------|
| Temporal-leakage prevention | None (DIY) | Point-in-time joins (offline store) | None | None (consumer of pairs) | **`KnowledgeView` structural primitive** |
| Source-identity enforcement | None | Feature-view names (weak) | None | None | **`SourceMismatchError` runtime invariant** |
| Canonical schemas | Implicit (column names) | FeatureView declarations | Per-product types | Implicit | **`schema.observation.v1` + versioned registry** |
| Local-first | Yes | No (online store optional) | Yes | Yes | **Yes** |
| Cache layer | Yes (parquet, no source ID) | Yes (offline store) | No | Caller's job | **Parquet, source-ID preserving, LST-skip, 30d volatile** |
| HTTP retry/backoff | Unknown (lift target) | Internal | DIY | n/a | **Audit; add if missing** |
| Async API | No | Internal async | No | n/a | **Sync v0.1; httpx seam preserved** |
| Dataframe-native validation | No | Pandera-style via Pydantic | No | n/a | **Pandera-backed Validator (if adopted)** |
| Property-based tests | No | Some | Limited | Yes | **Hypothesis on all temporal invariants** |
| Kalshi settlement source resolution | Implicit | n/a | n/a | n/a | **`CATALOG-05` contract specs** |
| Multi-format serialization | dataframe + parquet + TOON | Various | Various | Dataframe-only | **5 formats (df + json + parquet + toon + csv)** |
| MCP server | No | No | No | No | **Seam at `packages/mcp/`; v0.2 real** |

## Quality Gate Self-Check

- [x] Categories clear — Table Stakes / Differentiators / Anti-Features (with sub-categories DEFERRED / OUT-OF-SCOPE-NEVER / ALREADY-LISTED)
- [x] Each item maps to PROJECT.md status — COVERED / PARTIAL / GAP / OUT-OF-SCOPE / ANTI-FEATURE columns
- [x] Buy-not-Build candidates have specific library names + version — `httpx>=0.27,<1.0`, `tenacity>=9.0`, `pandera==0.29`, `feast==0.63` (not recommended, listed for completeness), `nannyml==0.13+` (not recommended), `evidently==0.5+` (not recommended)
- [x] No re-derivation of locked requirements — CORE-01..05, CATALOG-01..05, RESEARCH-01, CACHE-01..02, PARITY-01, PKG-01, QUICKSTART-01, MIGRATION-01, CI-01 are referenced and contextualized, never restated as proposed work

## Summary for Requirements Refinement

**The locked PROJECT.md Active requirements cover all DIFFERENTIATORS and most TABLE STAKES.** The temporal-safety + source-identity + canonical-schemas + parity-gate combo is correctly identified as the differentiating bet for v0.1.

**Five small gaps worth closing before sprint:**

1. **GAP (P1):** Audit v0.14.1 lift for HTTP retry/timeout/User-Agent. If missing, add `CORE-06` + `tenacity>=9.0` dep.
2. **GAP (P2):** `DOCS-01` — NumPy-style docstrings + doctest in CI. Cheap; pairs with QUICKSTART-01.
3. **DECISION:** Build `Validator` on top of `pandera==0.29` vs. on top of `jsonschema`. Pandera is dataframe-native; if accepted, simplifies CORE-02 and removes ~300 LOC. Day-5 decision.
4. **OUT-OF-SCOPE additions (P2, defensive):** Explicitly add "Async API surface", "Built-in backtesting engine", "Hosted feature-store integration" to PROJECT.md Out of Scope to forestall scope-creep RFCs during sprint.
5. **KEY DECISION additions:** "DataFrame-first, pandera for validation, no row-wise pydantic" and "pandas-first v0.1; Polars deferred to v0.2 if demand emerges" — document the rejections to save future debate cycles.

**Strongly NOT recommended (despite ecosystem hype):**

- Bringing in Feast / Tecton / Hopsworks (feature-store frameworks — too heavy, conflicts with local-first)
- Bringing in Great Expectations / Soda (warehouse-side data contracts — wrong runtime location for SDK-internal validation)
- Bringing in NannyML / Evidently (drift detection ≠ leakage detection; different problem)
- Open-Meteo adapter (licensing trap — confirmed already-listed; keep firm)
- Pydantic-model API surface (row-wise validation doesn't scale; pandera docs explicitly warn this)
- Polars as primary return type in v0.1 (breaks v0.14.1 parity and `mostly-light` downstream)

## Sources

Verified against contemporary documentation and 2026 ecosystem surveys:

- [Pandera Python Validation Guide 2026](https://pythondatabench.com/article/data-validation-python-pandera-practical-guide) — pandera 0.29 release (Jan 2026), multi-backend support
- [pandera PyPI](https://pypi.org/project/pandera/) — version pin reference
- [Feature Store Comparison 2026: Feast, Tecton, Hopsworks](https://mlopsplatforms.com/posts/feature-store-comparison-2026/) — competitive landscape for point-in-time joins
- [Feast PyPI v0.63](https://pypi.org/project/feast/) — May 2026 release; dependency surface review
- [Feast point-in-time joins docs](https://docs.feast.dev/getting-started/concepts/point-in-time-joins) — prior art for KnowledgeView semantics
- [DuckDB ASOF Joins](https://duckdb.org/docs/current/guides/sql_features/asof_join) — building-block alternative to merge_asof
- [pandas.merge_asof docs](https://pandas.pydata.org/docs/reference/api/pandas.merge_asof.html) — building-block for KnowledgeView implementation
- [Polars vs Pandas in 2026](https://vrlatech.com/polars-vs-pandas-in-2026-which-python-dataframe-library-should-you-use/) — pandas-vs-Polars choice for SDK return type
- [Avoiding Data Leakage in Time Series Analysis with TimeSeriesSplit](https://codecut.ai/cross-validation-with-time-series/) — sklearn prior art; split, not detect
- [NannyML data drift docs](https://nannyml.readthedocs.io/en/stable/tutorials/detecting_data_drift.html) — drift vs leakage distinction
- [Data Contracts Explained (atlan)](https://atlan.com/data-contracts/) — Soda/GE/dbt landscape 2026
- [Soda Data Contract Verification](https://adriennevermorel.com/notes/soda-data-contract-verification/) — Soda v4 contract format
- [dbt vs Great Expectations vs Soda](https://cybersierra.co/blog/best-data-quality-tools/) — adoption guidance
- [HTTPX vs Requests vs AIOHTTP 2026](https://decodo.com/blog/httpx-vs-requests-vs-aiohttp) — confirms httpx pick
- [Tenacity GitHub](https://github.com/jd/tenacity) — retry library status 2026
- [Hypothesis on Hacker News (2026)](https://news.ycombinator.com/item?id=45818562) — property-based testing standard
- [The Ultimate Python Quantitative Trading Ecosystem 2025-2026](https://medium.com/@mahmoud.abdou2002/the-ultimate-python-quantitative-trading-ecosystem-2025-guide-074c480bce2e) — quant SDK conventions
- [awesome-quant](https://github.com/wilsonfreitas/awesome-quant) — Kalshi/prediction-market library landscape
- [Predict & Profit Kalshi automated trading](https://predictandprofit.io/) — adjacent product features (V2.2, May 2026)
- [Best API for Prediction Markets in 2026 (Kalshi, Polymarket)](https://www.predictionhunt.com/blog/best-api-for-prediction-markets) — prediction-market SDK landscape
- [IEM API Documentation](https://mesonet.agron.iastate.edu/api/) — IEM/ASOS data source confirmation

---
*Feature research for: local-first Python SDK for quants researching prediction-market weather contracts*
*Researched: 2026-05-21*

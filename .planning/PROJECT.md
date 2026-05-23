# tradewinds

## What This Is

A local-first SDK for quants and traders researching prediction-market weather contracts (Kalshi NHIGH/NLOW, daily temperature high/low). Calls public APIs (AWC, IEM, GHCNh, NWS CLI, NOAA BDP, Polymarket Gamma) directly — no hosted backend.

**Two SDKs, one repo, one roadmap:**
- **Python** (`tradewinds` / `tradewinds-weather` / `tradewinds-markets` on PyPI) — v0.1.0rc1 ready 2026-05-23. Primary consumer: quants in notebooks + `mostly-light` trading runtime.
- **TypeScript** (`@tradewinds/core` / `@tradewinds/weather` / `@tradewinds/markets` + meta `tradewinds` on npm) — v0.1.0 in planning 2026-05-23. Primary consumer: Rob's Chrome extension overlaying weather data on kalshi.com; future web dashboards; any browser-based consumer.

Both SDKs hit the same public endpoints, share canonical schemas via codegen (`scripts/export_schemas.py` writes `schemas/json/`), and return row-equivalent output. Going forward, **every new feature gets a paired work item in both lanes** unless explicitly flagged as `python_only` or `typescript_only` with a reason. Subsumes the user's prior `mostlyright` package, adds temporal-safety primitives and source-identity invariants from day 1, and reserves a seam for an MCP server in Python v0.2.

## Core Value

`research(contract, station, from_date, to_date)` returns clean, leakage-free, source-identified training pairs that backtest the same way they trade — and any train/infer source mismatch errors loudly instead of silently corrupting a model.

## Long-term Vision

**Tradewinds is becoming an MCP-native data platform for prediction market ML.** v0.1.0 ships the weather/Kalshi wedge as a local-first Python SDK with temporal-safety primitives and source-identity enforcement. v0.2+ adds an MCP server layer (at `packages/mcp/`, seam already reserved) that exposes those primitives to AI agents — so domain experts orchestrate data pipelines without becoming data engineers.

The platform pieces, post-v0.1.0:

1. **MCP server layer** at `packages/mcp/` exposing `list_sources`, `describe_source`, `ingest`, `query`, `get_schema` tools via the MCP protocol. Any MCP client (Claude, Cursor, custom) drives end-to-end pipelines.
2. **Data catalog with 5-layer context engineering** — every pre-indexed source carries schema semantics, temporal rules, quality notes, cross-source relationship mappings, and operational context. Catalog entries are onboarding docs for AI agents.
3. **Agent-generated connector pipeline** — for sources not yet pre-indexed, agents read API docs/HTML/PDF, build schema mental models, generate and persist extraction configs. Catalog grows organically; quality-review gates promote vetted configs.
4. **Server-enforced temporal safety as trust architecture** — `dataset.at_time(...)`, `.between(...)`, `.as_of(...)` return exactly and only what was knowable on the given date; the constraint is structural, not honor-system. This is why quants will trust the platform: they already distrust agents on leakage risk.
5. **Multi-vertical expansion** — v0.2 weather + MCP server → v0.3 sports prediction markets → v0.4 politics + finance, all on the same temporal-safety layer. New verticals = catalog entries + adapters, not rewrites.
6. **Architecture: core + wrappers** — `tradewinds` (Python SDK, what we're building now), `packages/mcp/` (MCP server wrapper, v0.2+), and an eventual CLI wrapper (v1.1+).

This vision lives in `phase-05-mcp-data-platform/VISION.md`. It depends on Phase 2 (TimePoint/KnowledgeView/LeakageDetector + catalog adapters + canonical schemas) and Phase 4 (CI/CD trusted publishing). It does NOT change v0.1.0 scope; Phase 5 begins only after v0.1.0 ships.

## Requirements

### Validated

(None yet — pre-Sprint-0)

### Validated (Python v0.1.0 — all 12 phases on `main`)

Python v0.1.0rc1 ships the entire Active list below. See STATE.md and REQUIREMENTS.md for traceability.

### Active (TypeScript v0.1.0 milestone — `@tradewinds/*` on npm)

> Specifies the TS surface, gates, and consumer contracts. Detailed IDs land in REQUIREMENTS.md §TS Requirements.

- [ ] **TS-PARITY-01**: TS `research(station, from, to)` row-equivalent (exact numeric equality on all 19 columns) to Python `research()` Mode 1 across all 5 parity fixtures; HTTP replay via `msw`
- [ ] **TS-CHROME-EXT-01**: `@tradewinds/core` + `@tradewinds/weather` + `@tradewinds/markets` run inside Chrome MV3 service worker; smoke test fetches AWC + IEM CLI live and resolves a Kalshi NHIGH/NLOW contract
- [ ] **TS-CODEGEN-01**: `scripts/export_schemas.py` writes deterministic JSON Schema files + station registry + Kalshi map to `schemas/`; CI fails on drift
- [ ] **TS-CORE-01**: TS port of `TradewindsError` + 7 first-class subclasses + `toDict()` JSON-safe coercion matching Python `to_json_safe` semantics (null/NaN/inf/cycle handling)
- [ ] **TS-CORE-02**: `TimePoint` / `KnowledgeView<T>` / `LeakageDetector` / `assertNoLeakage` ported; `validateRows(rows, schemaId, opts)` ships with ajv-standalone validators
- [ ] **TS-WEATHER-01**: AWC + IEM ASOS + IEM CLI + GHCNh fetchers + parsers; CSV/PSV parsing without DataFrames; retry/backoff/timeout via `fetch()` + `AbortController`
- [ ] **TS-MERGE-01**: `mergeObservations`/`mergeClimate` byte-equivalent to Python source-priority + first-seen-tiebreak semantics
- [ ] **TS-CACHE-01**: `CacheStore` interface + `IndexedDBStore` (browser) + `FsStore` (Node) + `MemoryStore` (Workers); `defaultCacheStore()` auto-detects runtime; LST/`.live`/30-day rules match Python
- [ ] **TS-TRANSFORM-01**: 9 transforms (`lag`/`diff`/`diff2`/`rolling`/`calendarFeatures`/`spread`/`windChill`/`heatIndex`/`clipOutliers`) match Python output byte-for-byte on shared fixture
- [ ] **TS-QC-01**: ≥ 5 QC alpha rules + `QCEngine.apply()` bitfield + `crosscheckIemGhcnh` matching Python rule IDs and bit positions
- [ ] **TS-MARKETS-01**: Kalshi NHIGH/NLOW resolvers from codegen; `KNOWN_WRONG_STATIONS` contract test ports
- [ ] **TS-POLY-01**: Polymarket Gamma client + discover + settle activated in TS (Python ships these as `NotImplementedError` in v0.1.0)
- [ ] **TS-DISCOVERY-01**: `availability(station)` reads from CacheStore; `describe(schemaId)` reads from JSON Schema descriptions; `featureCatalog()` enumerates transforms
- [ ] **TS-VERSION-01**: `DataVersion` via Web Crypto SHA-256 produces same token as Python `discovery.DataVersion` for identical inputs
- [ ] **TS-SNAPSHOT-01**: `buildSnapshot(...)` + `DataSnapshot` interface + `.toDict()` + `.toToon()` matching Python output on 3-case fixture
- [ ] **TS-PKG-01**: Four npm packages publish at v0.1.0: `@tradewinds/core`, `@tradewinds/weather`, `@tradewinds/markets`, `tradewinds` (meta) via OIDC trusted publishing
- [ ] **TS-BUNDLE-01**: `size-limit` gates: core ≤25KB, weather ≤35KB, markets ≤10KB, meta ≤70KB (all min+gzip)
- [ ] **TS-DOCS-01**: README quickstart timed <5min by external person; typedoc reference; `docs/chrome-extension-integration.md` guide for Rob
- [ ] **TS-CI-01**: GitHub Actions `test-ts.yml` + `schema-drift.yml` + `release-ts.yml` + `drift-rotate-ts.yml` (weekly soft-fail watchdog)

### Active (Python v0.2 milestone — Phase 5 MCP Data Platform)

See ROADMAP.md Phase 5 entry. Gated on Python v0.1.0 ship (operator-gated PyPI tag) AND TS v0.1.0 ship (resourcing constraint — TS lane is Rob's primary work for ~3 weeks).

### Out of Scope (TS v0.1.0)

- **NWP (HRRR/GFS/NBM) GRIB decode in browser** — Python ships dispatch stub; TS does the same (no `cfgrib`-equivalent in browser at acceptable bundle size in 2026). Deferred to TS v0.2.
- **Parquet I/O** — TS cache stores JSON; `parquet-wasm` integration is a v0.2 stretch.
- **Pandas-cache compatibility** — TS writes its own root `~/.tradewinds/cache-ts/v1/...`; Python writes `~/.tradewinds/cache/v1/...`. No cross-language read.
- **MCP server in TS** — entirely Python-side (Phase 5).
- **CLI binary** — both languages; v1.1+.
- **DataFrame API** — TS uses plain object arrays; `apache-arrow` adapter optional/opt-in.

### Out of Scope (Python v0.1 — unchanged from pre-TS-planning)

- **MCP server** — deferred to v0.2; `packages/mcp/` scaffolded as stub only
- **Hosted R2 cache** — deferred to v0.2; requires 60-day validation gate first
- **Sports / politics / finance verticals** — v0.1 is weather only
- **Open-Meteo adapter** — licensing blocks redistribution; not in any v0.x
- **Preprocessing (RH, feels_like, MetPy re-parse)** — Sprint 0.5+; raw `metar_raw` preserved in observation rows
- **Kalshi API client (orderbook, fills)** — Sprint 0.5+; v0.1 ships contract specs only
- **CLI surface** — Python SDK only; CLI is v1.1+
- **Agent-generated connectors** — original mostlyright-mcp Layer 2 idea; v2+
- **`as_of_query` MCP tool** — v0.2+ only on named user request

## Context

- **Background:** User shipped `mostlyright` (Python SDK for Kalshi weather contracts) to PyPI through ~v0.14.1, then continued the monorepo to v0.17.0 with diverged behavior (Open-Meteo removal, settlement_v1 intake). Considers the v1 architecture overengineered. tradewinds is the rebuild.
- **Lift source pinned:** `../monorepo-v0.14.1/` (git worktree from v0.14.1 tag), NOT monorepo head.
- **Parallel design history:** `mostlyright-mcp` was an earlier design pass with 3-layer architecture (core/catalog/mcp). That design is preserved in this project's `ROADMAP.md` and merged with tradewinds' execution discipline. MCP is deferred to v0.2 in this branch.
- **Downstream consumer:** `mostly-light` (Kalshi trading runtime) currently uses `therminal-py>=1.0.7`. v0.1 ship gate includes migrating its 5 call sites (`kxhigh` strategy) to tradewinds with no behavior change.
- **Domain pain:** temporal leakage is silent and fatal — training data containing future information makes models that backtest great and lose money live. Source drift (training on `iem.archive`, inferring on `awc.live`) is structurally identical in blast radius.
- **Demand evidence:** strong self-demand (user trades these contracts). Weak external demand — 1-2 named users to validate post-ship. 60-day validation gate of 3 active external users is the productize-thesis test.

## Constraints

### Python

- **Tech stack:** Python 3.11+. uv workspace. `httpx`, `pandas`, `pyarrow`, `filelock`, `jsonschema`, `hypothesis` (dev). No FastAPI, no Docker, no hosted infra in v0.1.
- **Timeline:** v0.1.0rc1 shipped on `main` 2026-05-23 (12/12 phases complete, 1453 tests). Operator-gated PyPI publish remains.
- **Execution model:** Two-lane parallel — Lane V (Vu) lifts from `monorepo-v0.14.1/`, Lane F (Rob, founder) builds new code. Cross-review mandatory. Every PR runs the two-reviewer loop (Codex `high` + Python Architect) per [`REVIEW-DISCIPLINE.md`](REVIEW-DISCIPLINE.md) — applies to ALL branches, not just parity-critical paths.
- **Testing discipline:** TDD mandatory (RED → GREEN → REFACTOR). Pre-commit hooks; no `--no-verify`. ≥90% branch coverage on `tradewinds.core` (empirical 94.20%); 85% enforced floor in CI. 80% line coverage on `catalog/` and adapter wrappers. Lifted `_vendor/` code retains its monorepo coverage.
- **Parity gate (HARD):** All 5 byte-equivalent parity fixtures vs `mostlyright==0.14.1` must pass. Frozen, never re-recorded.
- **License:** MIT (matches mostlyright, lowest friction for external adoption).
- **No direct commits to main:** every change goes through PR + cross-lane review.

### TypeScript

- **Tech stack:** TypeScript 5.x (strict mode). pnpm workspace under `packages-ts/`. `tsup` (build), `vitest` (test), `msw` (HTTP mock), `fast-check` (property-based), `biome` (lint+format), `idb` (IndexedDB), `proper-lockfile` (Node), `ajv` (compiled standalone validators — not runtime dep), `@changesets/cli` (release). Target ES2022. No backend, no FastAPI-equivalent, no Docker.
- **Runtime targets:** Chrome MV3 service worker (primary), modern browsers (ES2022+), Node ≥20, Bun, Deno, Cloudflare Workers. Bundle size gates: core ≤25KB, weather ≤35KB, markets ≤10KB, meta ≤70KB (min+gzip).
- **Timeline:** 8 phases (TS-W0..TS-W7). ~18-25 days single-lane; ~12-15 days with W5↔W6 parallelism after W4. Rob owns TS lane; Vu reviews.
- **Schema source of truth:** Python. `scripts/export_schemas.py` writes deterministic JSON Schema files + station registry + Kalshi map to `schemas/`. `@tradewinds/codegen` reads `schemas/` and emits TS types + ajv-standalone validators. Drift fails CI.
- **Testing discipline:** TDD per phase. Pre-commit via lefthook (biome + tsc + vitest --run -m '!live'). ≥90% branch on `@tradewinds/core`; ≥80% line on `@tradewinds/weather` and `@tradewinds/markets`.
- **Parity gate (HARD):** TS `research()` row-equivalent (exact numeric equality on all 19 columns) to Python `research()` Mode 1 across all 5 fixtures; HTTP via `msw` against recordings captured from Python.
- **License:** MIT (matches Python).
- **No direct commits to main:** same PR discipline as Python.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Merge mostlyright-mcp vision into tradewinds workspace, not standalone | tradewinds has the cleaner scaffold + parity gate; mostlyright-mcp has the spine. Both > either. | ✓ Good (Python v0.1.0rc1 shipped) |
| Defer MCP server to Python v0.2 | Cuts 6 weeks of work that doesn't move v0.1 user value. Seam at `packages/mcp/` preserves later integration. | ✓ Good (Python v0.1.0rc1 shipped without it) |
| Three-package PyPI workspace (`tradewinds`/`tradewinds-weather`/`tradewinds-markets`) instead of single package | Lets notebook users `pip install tradewinds-weather` without dragging in Kalshi markets code. Pre-shapes for vertical N+1. | ✓ Good (shipped) |
| `research()` two-mode: v0.14.1 parity mode + source-explicit mode | Parity mode passes the byte-equivalent test gate. Source-explicit mode introduces the mostlyright-mcp semantics without breaking v0.14.1 callers. Mode 1 deprecates v0.2, removes v0.3. | ✓ Good (shipped) |
| GHCNh in v0.1 (not deferred) | tradewinds had it in scope already; lift is cheap. | ✓ Good (shipped) |
| Lift source pinned to `monorepo-v0.14.1/` tag, not head | Monorepo head (v0.17.0) has diverged behavior (Open-Meteo removed, settlement_v1 intake) that would break parity. | ✓ Good |
| Exception root: `TradewindsError` (renamed from `MostlyRightMCPError`) | Repo name is tradewinds. Provide `MostlyRightMCPError = TradewindsError` alias for one release. | ✓ Good (shipped); TS drops the alias (clean start) |
| Open-Meteo NOT in v0.1 (or any v0.x) | Licensing blocks redistribution into the v0.2 hosted cache and out of `mostly-light`'s call path. | ✓ Good |
| **TS SDK lives in same repo as Python under `packages-ts/`, not standalone repo** | "Roadmap and planning must cover BOTH" (user direction 2026-05-23). Same repo = paired PLAN.md per feature, single CI source, codegen lives next to source schemas, single PR-review path for cross-language drift. | ✓ Good (Decided 2026-05-23) |
| **Python is canonical for schemas + station registry + Kalshi map; TS consumes via codegen** | One source of truth eliminates manual duplication risk. `scripts/export_schemas.py` + CI drift gate enforce this. | ✓ Good (Decided 2026-05-23) |
| **TS uses plain object arrays, not DataFrames; opt-in `apache-arrow` adapter** | Browser bundle size + zero-dep "just works" matter more than DataFrame API. Python keeps pandas as canonical surface; TS is a parallel-shape port. | ✓ Good (Decided 2026-05-23) |
| **TS cache root distinct from Python (`cache-ts/` vs `cache/`); JSON not parquet** | Avoids partial-write read between Python writer and TS reader. Cross-language cache compat is a v0.2 problem. | ✓ Good (Decided 2026-05-23) |
| **npm scope `@tradewinds/*` + unscoped meta `tradewinds`** | Mirrors PyPI three-distribution layout. Meta package for one-import ergonomics. Scope availability check is open decision (see TS-SDK-DESIGN.md §13). | Pending verification of npm scope availability |
| **TS port activates Polymarket discover/settle live (Python ships these as `NotImplementedError`)** | Chrome extension's primary use case is overlaying Kalshi + Polymarket settlement context. Stubs aren't useful. Python catches up in its v0.2 cycle. | ✓ Good (Decided 2026-05-23) |
| **NWP (HRRR/GFS/NBM) stays a `NotImplementedError` stub in TS v0.1 too** | GRIB decode in browser at acceptable bundle size doesn't exist in 2026. Same disposition as Python. | ✓ Good (Decided 2026-05-23) |
| **Schema drift CI gate is mandatory** | Without it, Python and TS schemas diverge silently. `schema-drift.yml` runs `scripts/export_schemas.py` and `git diff --exit-code schemas/` on every PR. | ✓ Good (Decided 2026-05-23) |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-05-21 after initialization (synthesized from ROADMAP.md + mostlyright-mcp/docs/design.md + tradewinds/CLAUDE.md)*

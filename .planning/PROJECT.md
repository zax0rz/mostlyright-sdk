# tradewinds

## What This Is

A local-first Python SDK for quants researching prediction-market weather contracts (Kalshi NHIGH/NLOW, daily temperature high/low). Calls public APIs (AWC, IEM, GHCNh, NWS CLI) directly — no hosted backend. Subsumes the user's prior `mostlyright` package, adds temporal-safety primitives and source-identity invariants from day 1, and reserves a seam for an MCP server in v0.2.

## Core Value

`research(contract, station, from_date, to_date)` returns clean, leakage-free, source-identified training pairs that backtest the same way they trade — and any train/infer source mismatch errors loudly instead of silently corrupting a model.

## Requirements

### Validated

(None yet — pre-Sprint-0)

### Active

- [ ] **PARITY-01**: `research(station, from_date, to_date)` is byte-equivalent to `mostlyright==0.14.1`'s `client.pairs(...)` (5 fixture parity test as hard gate)
- [ ] **CORE-01**: Temporal-safety primitives (`TimePoint`, `KnowledgeView`, `LeakageDetector`) with property-based tests (Hypothesis), ≥90% branch coverage
- [ ] **CORE-02**: `Schema` + `Validator` with source-identity invariant (train/infer source mismatch raises `SourceMismatchError`)
- [ ] **CORE-03**: Three canonical schemas pinned: `schema.observation.v1`, `schema.forecast.iem_mos.v1`, `schema.settlement.cli.v1` with contract tests
- [ ] **CORE-04**: Exception hierarchy with structured payloads (`TradewindsError`, `SourceUnavailableError`, `SchemaValidationError`, `SourceMismatchError`, `LeakageError`)
- [ ] **CORE-05**: Format serializers (dataframe, json, parquet, toon, csv) with roundtrip tests
- [ ] **CATALOG-01**: IEM adapter (observations + MOS forecasts, source IDs `iem.archive` + `iem.live`)
- [ ] **CATALOG-02**: AWC adapter (METAR JSON, source ID `awc.live`)
- [ ] **CATALOG-03**: NWS CLI adapter (daily settlement, source ID `cli.archive`, preliminary/final/correction dedup)
- [ ] **CATALOG-04**: GHCNh adapter (hourly historical, source ID `ghcnh.archive`)
- [ ] **CATALOG-05**: Kalshi NHIGH/NLOW contract specs (settlement source resolution)
- [ ] **RESEARCH-01**: `research()` Mode 2 (source-explicit) emits per-role source + retrieved_at columns; validates each role independently
- [ ] **CACHE-01**: Local parquet cache (`$HOME/.tradewinds/cache/`), `filelock`-guarded, LST current-month-skip, 30-day volatile-window exclusion
- [ ] **CACHE-02**: Cache rows preserve source identity (cache is a speedup, not a different source ID)
- [ ] **PKG-01**: Three-package workspace publishes as `tradewinds`, `tradewinds-weather`, `tradewinds-markets` to PyPI at v0.1.0
- [ ] **QUICKSTART-01**: README quickstart works end-to-end in <5 minutes for fresh installer (timed by external person)
- [ ] **MIGRATION-01**: `mostly-light/strategies/kxhigh` dry-run against tradewinds matches `therminal-py` baseline
- [ ] **CI-01**: GitHub Actions: test on push, release on tag, PyPI trusted publishing

### Out of Scope (v0.1)

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

- **Tech stack:** Python 3.11+. uv workspace. `httpx`, `pandas`, `pyarrow`, `filelock`, `jsonschema`, `hypothesis` (dev). No FastAPI, no Docker, no hosted infra in v0.1.
- **Timeline:** 14 calendar days from Day 1. Phase A (parity lift) Days 1-4, Phase B (core+catalog) Days 5-14. v0.2 (MCP) is a later milestone.
- **Execution model:** Two-lane parallel — Lane V (Vu) lifts from `monorepo-v0.14.1/`, Lane F (Founder) builds new code. Cross-review mandatory; Codex `model_reasoning_effort=high` on any PR touching `core/`, `_internal/merge/`, or `research.py`.
- **Testing discipline:** TDD mandatory (RED → GREEN → REFACTOR). Pre-commit hooks; no `--no-verify`. ≥90% branch coverage on `tradewinds.core`. 80% line coverage on `catalog/` and adapter wrappers. Lifted `_vendor/` code retains its monorepo coverage.
- **Parity gate (HARD):** Day 3 — all 5 byte-equivalent parity fixtures vs `mostlyright==0.14.1` must pass. Sprint 0 ships only if green.
- **License:** MIT (matches mostlyright, lowest friction for external adoption).
- **No direct commits to main:** every change goes through PR + cross-lane review.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Merge mostlyright-mcp vision into tradewinds workspace, not standalone | tradewinds has the cleaner scaffold + parity gate; mostlyright-mcp has the spine. Both > either. | — Pending |
| Defer MCP server to v0.2 | Cuts 6 weeks of work that doesn't move v0.1 user value. Seam at `packages/mcp/` preserves later integration. | — Pending |
| Three-package workspace (`tradewinds`/`tradewinds-weather`/`tradewinds-markets`) instead of single PyPI package | Lets notebook users `pip install tradewinds-weather` without dragging in Kalshi markets code. Pre-shapes for vertical N+1. | — Pending |
| `research()` two-mode: v0.14.1 parity mode (no `sources`) + source-explicit mode (`sources={...}`) | Parity mode passes the byte-equivalent test gate. Source-explicit mode introduces the mostlyright-mcp semantics without breaking v0.14.1 callers. Mode 1 deprecates v0.2, removes v0.3. | — Pending |
| GHCNh in v0.1 (not deferred to v0.2 as mostlyright-mcp planned) | tradewinds had it in scope already; lift is cheap. | — Pending |
| Lift source pinned to `monorepo-v0.14.1/` tag, not head | Monorepo head (v0.17.0) has diverged behavior (Open-Meteo removed, settlement_v1 intake) that would break parity. | ✓ Good |
| Exception root: `TradewindsError` (renamed from mostlyright-mcp's `MostlyRightMCPError`) | Repo name is tradewinds. Provide `MostlyRightMCPError = TradewindsError` alias for one release. | — Pending |
| Open-Meteo NOT in v0.1 (or any v0.x) | Licensing blocks redistribution into the v0.2 hosted cache and out of `mostly-light`'s call path. | ✓ Good |

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

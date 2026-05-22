# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-05-21; STATE.md refreshed 2026-05-22)

**Core value:** `research(contract, station, from_date, to_date)` returns clean, leakage-free, source-identified training pairs that backtest the same way they trade — and any train/infer source mismatch errors loudly instead of silently corrupting a model.
**Current focus:** Phase 1: v0.14.1 Parity Lift

## Current Position

Phase: 1.5 of 5 (Fetcher Optimization + Cross-Source Parallelism — INSERTED 2026-05-22)
Plan: 0 of TBD in current phase (Phase 1 Wave 1 of 4 merged on `merged-vision`; Phase 1 Waves 2-4 + Phase 1.5 pending)
Status: Phase 1.5 PLAN.md pending (strictly serial after Phase 1, strictly before Phase 2)
Last activity: 2026-05-22 - Phase 1 Wave 1 merged to merged-vision; Phase 1.5 (PERF-01..05) inserted into ROADMAP; quick task 260522-ea7: fix stale STATE.md + REQUIREMENTS.md

Progress: [█░░░░░░░░░] ~10% (Phase 1 Wave 1 of 4 complete)

## Performance Metrics

**Velocity:**
- Total plans completed: 0
- Average duration: N/A
- Total execution time: 0 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| - | - | - | - |

**Recent Trend:**
- Last 5 plans: N/A
- Trend: N/A

*Updated after each plan completion*

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- Merge mostlyright-mcp vision into tradewinds workspace, not standalone — Pending
- Defer MCP server to v0.2 — Pending
- Three-package workspace (`tradewinds`/`tradewinds-weather`/`tradewinds-markets`) — Pending
- `research()` two-mode (parity + source-explicit) — Pending
- Lift source pinned to `monorepo-v0.14.1/` tag (NOT head) — ✓ Good (Decided, per PROJECT.md Key Decisions)
- Open-Meteo NOT in v0.1 (licensing) — ✓ Good (Decided, per PROJECT.md Key Decisions)

### Pending Todos

Open decisions to resolve during execution (per research SUMMARY.md):
- Pandera vs jsonschema for Validator engine — Day 5 spike (Phase 2)
- `research()` import path resolution (`from tradewinds.research import research` vs `from tradewinds.api import research`) — decide before Phase 2 Day 5

### Blockers/Concerns

[Pre-execution context — risks flagged by research]

- Phase 1 Day 1 must complete the Day-1 Morning Sync addendum (7 items, ~2 hours): AWC URL smoke + PEP 420 migration + dtype ground-truth capture + version pins + `tradewinds.core` public surface stub + `TRADEWINDS_CACHE_DIR` wiring + `_vendor/__init__.py` inventory. Skipping any of these compromises the Day 3 parity gate.
- Phase 2 must hard-code `KALSHI_SETTLEMENT_STATIONS` (KNYC, KMDW, etc.) before Phase 3 migration gate — silent data corruption risk if wrong station IDs are used.
- Phase 4 PyPI trusted publishing needs three separate registrations (one per package); use PyPI "pending publisher" feature to bypass chicken-and-egg on first publish.

### Quick Tasks Completed

| # | Description | Date | Commit | Directory |
|---|-------------|------|--------|-----------|
| 260522-9uj | Move pytest from pre-commit to pre-push hook | 2026-05-22 | 1589398 | [260522-9uj-move-pytest-from-pre-commit-to-pre-push-](./quick/260522-9uj-move-pytest-from-pre-commit-to-pre-push-/) |
| 260522-axd | Wire REVIEW-DISCIPLINE.md as canonical review policy source | 2026-05-22 | fb9cd61 | [260522-axd-wire-review-discipline-md-as-canonical-r](./quick/260522-axd-wire-review-discipline-md-as-canonical-r/) |
| 260522-ea7 | Fix stale STATE.md and REQUIREMENTS.md footer/decisions/phase count | 2026-05-22 | eba690a | [260522-ea7-fix-stale-state-md-and-requirements-md-f](./quick/260522-ea7-fix-stale-state-md-and-requirements-md-f/) |

## Session Continuity

Last session: 2026-05-22
Stopped at: Phase 1 Wave 1 merged to merged-vision; Phase 1.5 inserted into ROADMAP (PERF-01..05); stale STATE.md/REQUIREMENTS.md/Phase 2 depends_on reconciled via quick task 260522-ea7. Ready to plan Phase 1.5.
Resume file: .planning/phase-01-5-fetcher-optimization-cross-source-parallelism/ (to be created when Phase 1.5 planning starts)

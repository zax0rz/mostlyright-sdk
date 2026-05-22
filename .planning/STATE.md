---
gsd_state_version: 1.0
milestone: v0.14.1
milestone_name: Parity Lift
status: executing
stopped_at: "ROADMAP enriched with 4 new phases (2.1, 3.1, 3.2, 3.3) for v0.1.0 scope expansion (international + multi-forecast + Polymarket + Sprint 2o lineage). Phase stubs created via `gsd-tools phase insert`; ROADMAP entries enriched with full Goal/Depends-on/Requirements/Success Criteria/Out-of-Scope/Review-panel blocks. STATE.md updated with Roadmap Evolution section + new decisions + new blockers/concerns. **Pending follow-ups before execution:** (1) add LINEAGE-01..05 + INTL-01..05 + NWP-01..06 + POLY-01..05 entries to REQUIREMENTS.md (POLY-01 currently a Sprint 0.5+ deferral — activate and split); (2) update PROJECT.md "Active scope" to reflect expanded v0.1.0; (3) run `/gsd-plan-phase` per new phase to write detailed PLAN.md; (4) decide whether to migrate existing `.planning/phase-NN-...` dirs to new `.planning/phases/NN.M-...` convention created by gsd-tools, or move the new dirs to match existing convention."
last_updated: "2026-05-22T11:52:40.503Z"
last_activity: 2026-05-22 -- Phase 2.1 planning complete
progress:
  total_phases: 10
  completed_phases: 0
  total_plans: 0
  completed_plans: 0
  percent: 8
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-05-21; STATE.md refreshed 2026-05-22)

**Core value:** `research(contract, station, from_date, to_date)` returns clean, leakage-free, source-identified training pairs that backtest the same way they trade — and any train/infer source mismatch errors loudly instead of silently corrupting a model.
**Current focus:** Phase 1: v0.14.1 Parity Lift

## Current Position

Phase: 1.5 of 12 (Fetcher Optimization + Cross-Source Parallelism — INSERTED 2026-05-22)
Plan: 0 of 3 in Phase 1.5 (Phase 1 Wave 1 of 4 merged on `merged-vision`; Phase 1 Waves 2-4 + Phase 1.5 pending)
Status: Ready to execute
Last activity: 2026-05-22 -- Phase 2.1 planning complete; added Phases 3.4 (QC engine), 3.5 (transforms DSL), 3.6 (discovery + settlement + DataVersion) to close mostlyright→tradewinds feature gaps

Progress: [█░░░░░░░░░] ~6% (Phase 1 Wave 1 of 4 complete; scope expanded from 5 → 12 numbered phases in v0.1.0)

**Phase count by milestone (post-2026-05-22 expansion):**

- v0.1.0: 12 phases (1, 1.5, 2, 2.1, 3, 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 4)
- v0.2+: 1+ phase (5 — MCP Data Platform; future phases TBD)

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

### Roadmap Evolution

- 2026-05-22: Phase 1.5 inserted after Phase 1 (Fetcher Optimization + Cross-Source Parallelism — lift mostlyright PR #85) — URGENT/optimization
- 2026-05-22: Phase 2.1 inserted after Phase 2 (Sprint 2o Lineage Refactor — per-source provenance from mostlyright PR #101) — scope expansion (prereq for 3.1/3.3)
- 2026-05-22: Phase 3.1 inserted after Phase 3 (International Station Expansion — 20 US → 60 stations via mostlyright Sprint 2t s1+s2+s3) — scope expansion
- 2026-05-22: Phase 3.2 inserted after Phase 3 (Multi-Forecast Live Path — HRRR/GFS/NBM via NOAA BDP, lift live subset of mostlyright Sprint 2r; ECMWF Tier-2 + historical backfill defer to v0.2) — scope expansion
- 2026-05-22: Phase 3.3 inserted after Phase 3 (Polymarket Integration — discovery + settlement via mostlyright Sprint 2t s1+s4; depends on Phase 3.1) — scope expansion
- 2026-05-22: Phase 3.4 inserted after Phase 3.3 (QC Engine Alpha + Sidecar + Crosscheck — lift `mostlyright/src/mostlyright/qc/`; flag-and-keep semantics + IEM/GHCNh crosscheck + 5-8 alpha rules) — scope expansion (closes biggest mostlyright→tradewinds feature gap)
- 2026-05-22: Phase 3.5 inserted after Phase 3.3 (Transforms DSL + Preprocessing Primitives — lift `mostlyright/src/mostlyright/{transforms,preprocessing}.py`; lag/diff/rolling/calendar/cross-features + `clip_outliers` + standalone `iem_crosscheck`) — scope expansion (removes the Sprint-0.5+ preprocessing defer)
- 2026-05-22: Phase 3.6 inserted after Phase 3.3 (Discovery API + Public Settlement + DataVersion — `availability()`/`climate_gaps()`/`describe()`/`feature_catalog()` + `settlement_date_for()`/`settlement_window_utc()` at top level + `DataVersion` reproducibility token) — scope expansion (closes day-one quant ergonomics gap)
- 2026-05-22: Phase 5 (MCP Data Platform) PLAN-00..PLAN-05 committed on merged-vision; execution gated on v0.1.0 ship

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- Merge mostlyright-mcp vision into tradewinds workspace, not standalone — Pending
- Defer MCP server to v0.2 — Pending
- Three-package workspace (`tradewinds`/`tradewinds-weather`/`tradewinds-markets`) — Pending
- `research()` two-mode (parity + source-explicit) — Pending
- Lift source pinned to `monorepo-v0.14.1/` tag (NOT head) — ✓ Good (Decided, per PROJECT.md Key Decisions)
- Open-Meteo NOT in v0.1 (licensing) — ✓ Good (Decided, per PROJECT.md Key Decisions)
- **v0.1.0 scope expansion (2026-05-22): include international cities + multi-forecast live + Polymarket** — Decided (user direction); ~26-day timeline extension absorbed via 4 new phases (2.1, 3.1, 3.2, 3.3)
- **2o lineage gap (per-source provenance): lift Sprint 2o into Phase 2.1** — Decided (user direction); rejected the "lossy single-source field" workaround to keep `source_tmin`/`source_tmax` provenance through to Polymarket settlement
- **ECMWF Tier-2 + historical NWP backfill: defer to v0.2** — Decided (research finding); local-first SDK can't satisfy ECMWF's 3-day rolling archive without hosted infra; Tier-1 HRRR/GFS/NBM live-fetch path ships in v0.1
- **Polymarket order book / Kalshi orderbook: stay deferred (Sprint 0.5+)** — Decided; v0.1 ships contract specs + settlement only, not paid market data

### Pending Todos

Open decisions to resolve during execution (per research SUMMARY.md):

- Pandera vs jsonschema for Validator engine — Day 5 spike (Phase 2)
- `research()` import path resolution (`from tradewinds.research import research` vs `from tradewinds.api import research`) — decide before Phase 2 Day 5

### Blockers/Concerns

[Pre-execution context — risks flagged by research]

- Phase 1 Day 1 must complete the Day-1 Morning Sync addendum (7 items, ~2 hours): AWC URL smoke + PEP 420 migration + dtype ground-truth capture + version pins + `tradewinds.core` public surface stub + `TRADEWINDS_CACHE_DIR` wiring + `_vendor/__init__.py` inventory. Skipping any of these compromises the Day 3 parity gate.
- Phase 2 must hard-code `KALSHI_SETTLEMENT_STATIONS` (KNYC, KMDW, etc.) before Phase 3 migration gate — silent data corruption risk if wrong station IDs are used.
- Phase 4 PyPI trusted publishing needs three separate registrations (one per package); use PyPI "pending publisher" feature to bypass chicken-and-egg on first publish.
- **Phase 2.1 parity-fixture pre-flight gate is HARD.** Any change to `ObservationMergePolicy.apply()` MUST re-run the 5 byte-equivalent parity fixtures before merging to `merged-vision`. The strict-`>` vs strict-`>=` ambiguity that mostlyright Sprint 2o codex review caught (resolved with secondary deterministic key on `(source, observation_received_at)`) carries forward to tradewinds Phase 2.1.
- **Phase 3.1 timezone correctness is parity-critical.** `daily_extremes()` station-local IANA calendar day must handle UTC wrap correctly. Test fixtures must include at least 3 UTC-wrap edge cases (RJTT UTC+9, SAEZ UTC-3, NZWN UTC+12/13 DST). Wrong calendar day → wrong settlement → silent data corruption.
- **Phase 3.2 `cfgrib`/`eccodes` supply-chain pin floors.** New `[nwp]` optional extra adds binary toolchain deps. Pin floors documented in REQUIREMENTS.md (NWP-06). Wheel-install on macOS/Windows verified before alpha publish.
- **Phase 3.3 URL parsing is security-adjacent.** Resolution-source URLs come from untrusted Polymarket event descriptions. Strict netloc allowlist (`wunderground.com`, `weather.gov`) + 16 KB description cap + UUID4 event_id regex validation tested in the codex review pass.
- **Lift sources for new phases are in-flight (NOT yet merged to mostlyright main).** Phase 2.1 source: mostlyright `sprint2/2o-s8-backfill-and-cutover` (PR #101 — claim "merged" but the worktree shows R7 fix iterations still). Phase 3.2 source: mostlyright `sprint2/2r-impl-bundle` (PR #123 open, R8 fix stage). Phase 3.1+3.3 source: mostlyright `sprint2/2t-polymarket-international` (78 commits ahead, no PR yet). **Pin lift source to specific branch commit SHA per phase** when planning (mirrors how Phase 1 pins to `monorepo-v0.14.1`).
- **2t branch reads observations_ledger (post-2o shape).** Lifting Sprint 2t s3+s4 verbatim requires Phase 2.1 to land first. Sequencing in ROADMAP enforces this (Phase 3.1 `depends_on: Phase 2.1`).

### Quick Tasks Completed

| # | Description | Date | Commit | Directory |
|---|-------------|------|--------|-----------|
| 260522-9uj | Move pytest from pre-commit to pre-push hook | 2026-05-22 | 1589398 | [260522-9uj-move-pytest-from-pre-commit-to-pre-push-](./quick/260522-9uj-move-pytest-from-pre-commit-to-pre-push-/) |
| 260522-axd | Wire REVIEW-DISCIPLINE.md as canonical review policy source | 2026-05-22 | fb9cd61 | [260522-axd-wire-review-discipline-md-as-canonical-r](./quick/260522-axd-wire-review-discipline-md-as-canonical-r/) |
| 260522-ea7 | Fix stale STATE.md and REQUIREMENTS.md footer/decisions/phase count | 2026-05-22 | eba690a | [260522-ea7-fix-stale-state-md-and-requirements-md-f](./quick/260522-ea7-fix-stale-state-md-and-requirements-md-f/) |
| 260522-h6a | Clean up duplicate MCP-01..06 IDs in REQUIREMENTS.md per Phase 5 PLAN-00 (option b) | 2026-05-22 | e92aa36 | [260522-h6a-clean-up-duplicate-mcp-01-06-ids-in-requ](./quick/260522-h6a-clean-up-duplicate-mcp-01-06-ids-in-requ/) |

## Session Continuity

Last session: 2026-05-22
Stopped at: ROADMAP enriched with 4 new phases (2.1, 3.1, 3.2, 3.3) for v0.1.0 scope expansion (international + multi-forecast + Polymarket + Sprint 2o lineage). Phase stubs created via `gsd-tools phase insert`; ROADMAP entries enriched with full Goal/Depends-on/Requirements/Success Criteria/Out-of-Scope/Review-panel blocks. STATE.md updated with Roadmap Evolution section + new decisions + new blockers/concerns. **Pending follow-ups before execution:** (1) add LINEAGE-01..05 + INTL-01..05 + NWP-01..06 + POLY-01..05 entries to REQUIREMENTS.md (POLY-01 currently a Sprint 0.5+ deferral — activate and split); (2) update PROJECT.md "Active scope" to reflect expanded v0.1.0; (3) run `/gsd-plan-phase` per new phase to write detailed PLAN.md; (4) decide whether to migrate existing `.planning/phase-NN-...` dirs to new `.planning/phases/NN.M-...` convention created by gsd-tools, or move the new dirs to match existing convention.
Resume file: Run `/gsd-plan-phase 2.1` (next blocking sequence) — Phase 2.1 must land before 3.1/3.3.
Branch state: Working on `planning/v01-intl-nwp-polymarket` off `merged-vision@d698886`. Commits not yet made — user decides when to commit. Suggested commit sequence: (a) ROADMAP + STATE updates as one commit; (b) REQUIREMENTS.md additions as separate commit; (c) PROJECT.md update as separate commit; (d) per-phase PLAN.md files in subsequent commits via `/gsd-plan-phase`.

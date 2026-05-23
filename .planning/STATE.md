---
gsd_state_version: 1.0
milestone: v0.14.1
milestone_name: Parity Lift
status: executing
stopped_at: "Phases 1 + 1.5 + 2 + 2.1 + 3 + 3.1-3.6 architectural seams merged to main. 1451 tests passing. Mode 2 dispatch + International stations + NWP forecast + Polymarket + QC engine + Transforms DSL + Discovery+DataVersion all ship their v0.1.0 surfaces. Live fetch wiring for catalog adapters' fetch_observations methods + Polymarket Gamma API + NWP byte-range remains for subsequent alphas. Next: Phase 4 — Coverage, Docs, CI/CD, Release."
last_updated: "2026-05-23T22:00:00.000Z"
last_activity: 2026-05-23 -- Phase 3.1-3.6 architectural seams consolidated + merged to main
progress:
  total_phases: 12
  completed_phases: 11
  total_plans: 35
  completed_plans: 32
  percent: 92
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-05-21; STATE.md refreshed 2026-05-23)

**Core value:** `research(contract, station, from_date, to_date)` returns clean, leakage-free, source-identified training pairs that backtest the same way they trade — and any train/infer source mismatch errors loudly instead of silently corrupting a model.
**Current focus:** Phase 4 — Coverage, Docs, CI/CD, Release (post v0.1.0a1 work)

## Current Position

Phase: 4 of 12 (Coverage / Docs / CI/CD / v0.1.0 ship — ready to start)
Plan: 0 of N in Phase 4 (Phases 1-3.6 complete on `main`)
Status: Ready to plan Phase 4
Last activity: 2026-05-23 — Phase 3.1-3.6 seams merged (1451 tests passing)

Progress: [█████████░] ~92% (11/12 phases complete in v0.1.0; Phase 4 release work remains)

## Phase 2 / 2.1 / 3 / 3.x closeout summary (2026-05-23)

- Phase 2 (CORE/CATALOG/MARKETS/PKG): `_v02/ → tradewinds.core/` rebrand
  preserving 266 tests; TradewindsError hierarchy with deprecation alias;
  KnowledgeView + LeakageDetector temporal primitives; jsonschema-backed
  Validator with source-identity invariant; 4 weather catalog adapters with
  canonical-units projection; Kalshi NHIGH/NLOW resolvers + 20-station whitelist;
  markets pkg PKG-03 pin. 10 codex review iterations + 1 architect pass.
- Phase 2.1 (LINEAGE-01..05): silver-tier observation_ledger.v1 schema +
  observation_qc.v1 sidecar; query_time_merge(silver_df, policy=LIVE_V1)
  materializes single-row-per-key gold from rows-per-source silver;
  ObservationMergePolicy properly immutable via MappingProxyType.
- Phase 3: tradewinds.mode2.research_by_source() Mode 2 dispatch seam +
  assert_source_identity() per-row check. Catalog adapter dispatch wired;
  fetch wiring deferred to Phase 3.1/3.2 alphas.
- Phase 3.1 (International): 41 ICAO → IANA tz map; Paris LFPG/LFPB/LFPO
  split; daily_extremes() rollup with whole-°C precision; DeferredMarketError
  for VHHH/RCTP.
- Phase 3.2 (NWP): SUPPORTED_NWP_MODELS = {hrrr, gfs, nbm}; forecast_nwp()
  dispatch seam with [nwp] optional-extra check.
- Phase 3.3 (Polymarket): polymarket_discover/settle with strict UUID4 +
  16KB description cap + netloc allowlist (wunderground.com, weather.gov).
- Phase 3.4 (QC): 5 ALPHA_RULES (temp/dewpoint/wind/pressure bounds) +
  QCEngine.apply() bitfield + build_sidecar_rows() + crosscheck_iem_ghcnh().
- Phase 3.5 (Transforms): lag/diff/rolling/calendar_features/spread +
  wind_chill + heat_index (NWS algorithms) + clip_outliers.
- Phase 3.6 (Discovery): DataVersion reproducibility token + availability /
  describe / feature_catalog / settlement_date_for top-level wrappers.

Tests grew 1342 → 1451 (+109 across the 6 phases).

## Phase 1.5 closeout summary (2026-05-23)

Merge commit: `738232e Merge phase-1-5/integration: Phase 1.5 fetcher optimization + cross-source parallelism` (--no-ff on main, pushed to origin/main).

Plans shipped:
- **PLAN-01 (PERF-01/02/03)** — Lifted mostlyright PR #85 commit `cf9eb85`. Yearly chunks via shared `_iem_chunks.py` (leap-year safe), cache-window filename + `_partial` namespace, HTTP_TIMEOUT 30→60s. Tradewinds-specific deviation documented: caller's `start` is normalized to `date(start.year, 1, 1)` before the chunker fires, for cache idempotence under per-month research.py callers. Required a parity-preserving month-filter in `_fetch_iem_month` post-parse.
- **PLAN-02 (PERF-05)** — `spike/source_limits/` (3 CLI scripts + shared helpers) characterizing AWC, GHCNh, IEM concurrent-request behavior; output `.planning/research/SOURCE-LIMITS.md` with deterministic Option-C recommendation (smoke-run scale; caveat documented). Spike scripts kept under version control for v0.2 re-validation.
- **PLAN-03 (PERF-04)** — `_prefetch_sources` in research.py: 4-way ThreadPoolExecutor (Option C per SOURCE-LIMITS.md) with Pitfall-6 timing pattern (submitted_at captured immediately after ex.submit()), narrow-except contract (httpx.HTTPStatusError, httpx.RequestError, OSError only — programming bugs propagate via f.result()), current-UTC-year skip (no double-fetch), AWC-window-relevance skip (preserves no-network invariant for cached re-runs). Live perf gate: KNYC 5-year backfill 50.3s vs 720s (12 min) gate.

Review discipline (per .planning/REVIEW-DISCIPLINE.md):
- Iter 1: codex `high` + python-architect ran in parallel against the integration branch diff vs main. Returned 3 + 6 HIGH findings (overlap; 6 unique). Commit `7e26fa2` closed all six: reversed-range guard in download_iem_asos, narrowed except clauses in `_warm_*`, current-year skip, parallelism-ratio assertion in live perf test, strengthened Pitfall-6 AST scan, RuntimeError-based propagation contract test.
- Iter 2: BOTH reviewers PASS clean. No CRITICAL or HIGH findings.

Wins:
- IEM ASOS: ~12x fewer HTTP requests per backfill (monthly → yearly chunks).
- research() parity gate: 97s → 49s (~2x faster after PERF-04).
- research() KNYC 5-year live: ~14x under the ROADMAP 12-min gate.
- HTTP_TIMEOUT=60s confirmed load-bearing for GHCNh ~10 MB PSV downloads at N=4 concurrent.

Validation:
- 5-fixture parity gate (Phase 1 HARD GATE invariant): green.
- Fast suite: 976 passed, 10 deselected (live).
- Live perf gate: green.

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
| 260522-lah | Fix 5 REVIEW-DISCIPLINE iteration 4 findings | 2026-05-22 | 5ec7fc4 | [260522-lah-fix-5-review-discipline-iteration-4-find](./quick/260522-lah-fix-5-review-discipline-iteration-4-find/) |
| 260522-lz3 | Fix 5 REVIEW-DISCIPLINE iteration 5 findings | 2026-05-22 | 0feccec | [260522-lz3-fix-5-review-discipline-iteration-5-find](./quick/260522-lz3-fix-5-review-discipline-iteration-5-find/) |
| 260522-miq | Fix 2 codex iteration 6 findings (write-wins race + class-B order) | 2026-05-22 | 6c3c282 | [260522-miq-fix-2-codex-iteration-6-findings-write-w](./quick/260522-miq-fix-2-codex-iteration-6-findings-write-w/) |
| 260522-msx | Fix 3 iter-7 findings (count drift + self-lock + non-deterministic race) | 2026-05-22 | 3d35cd2 | [260522-msx-fix-3-iter-7-findings-count-drift-self-l](./quick/260522-msx-fix-3-iter-7-findings-count-drift-self-l/) |
| 260522-n2e | Fix iter-8 P2 (migrate_to_v2 CLI needs lock around lock-free helper) | 2026-05-22 | 068c9c4 | [260522-n2e-fix-iter-8-p2-migrate-to-v2-cli-needs-lo](./quick/260522-n2e-fix-iter-8-p2-migrate-to-v2-cli-needs-lo/) |
| 260522-n7n | Fix iter-9 P1/P2 (lock parent dir + dry-run no lock touch) | 2026-05-22 | 2238b2c | [260522-n7n-fix-iter-9-p1-p2-lock-parent-dir-dry-run](./quick/260522-n7n-fix-iter-9-p1-p2-lock-parent-dir-dry-run/) |
| 260522-nbw | Apply iter-9 P1 mkdir pattern to all 3 FileLock sites (iter-10 architect) | 2026-05-22 | 1c1681d | [260522-nbw-fix-iter-10-architect-high-p1-bug-in-wri](./quick/260522-nbw-fix-iter-10-architect-high-p1-bug-in-wri/) |
| 260522-ng9 | Fix Task 1 mkdir variable name + ordering (iter-11) | 2026-05-22 | b166e2b | [260522-ng9-fix-iter-11-task-1-mkdir-uses-wrong-var-](./quick/260522-ng9-fix-iter-11-task-1-mkdir-uses-wrong-var-/) |

## Session Continuity

Last session: 2026-05-22
Stopped at: ROADMAP enriched with 4 new phases (2.1, 3.1, 3.2, 3.3) for v0.1.0 scope expansion (international + multi-forecast + Polymarket + Sprint 2o lineage). Phase stubs created via `gsd-tools phase insert`; ROADMAP entries enriched with full Goal/Depends-on/Requirements/Success Criteria/Out-of-Scope/Review-panel blocks. STATE.md updated with Roadmap Evolution section + new decisions + new blockers/concerns. **Pending follow-ups before execution:** (1) add LINEAGE-01..05 + INTL-01..05 + NWP-01..06 + POLY-01..05 entries to REQUIREMENTS.md (POLY-01 currently a Sprint 0.5+ deferral — activate and split); (2) update PROJECT.md "Active scope" to reflect expanded v0.1.0; (3) run `/gsd-plan-phase` per new phase to write detailed PLAN.md; (4) decide whether to migrate existing `.planning/phase-NN-...` dirs to new `.planning/phases/NN.M-...` convention created by gsd-tools, or move the new dirs to match existing convention.
Resume file: Run `/gsd-plan-phase 2.1` (next blocking sequence) — Phase 2.1 must land before 3.1/3.3.
Branch state: Working on `planning/v01-intl-nwp-polymarket` off `merged-vision@d698886`. Commits not yet made — user decides when to commit. Suggested commit sequence: (a) ROADMAP + STATE updates as one commit; (b) REQUIREMENTS.md additions as separate commit; (c) PROJECT.md update as separate commit; (d) per-phase PLAN.md files in subsequent commits via `/gsd-plan-phase`.

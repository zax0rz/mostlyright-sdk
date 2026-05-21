# Sprint 0 — Local-first wedge on PyPI

**Goal:** Ship `tradewinds` + `tradewinds-weather` v0.1.0 to PyPI with byte-equivalent parity to `mostlyright==0.14.1`'s `client.pairs(station, from_date, to_date)`. Local-first; no hosted backend; calls AWC, IEM, GHCNh, NWS CLI directly.

**Timeline:** 3-4 calendar days with parallel lanes (Vu lift + Founder build).

**HARD GATE (Day 3):** All 5 parity fixtures byte-match v0.14.1. Sprint 0 ships only if green.

## Pre-Sprint status (2026-05-21)

- [✓] Day 0 — Vojtech call (yes, switching from v0.14.1 to tradewinds)
- [✓] Day 0 — Vu conversation (Sprint 2o-s9-B paused; he authors the lift lane)
- [✓] Repo scaffolding (this commit) — workspace + foundational files + roadmap

## Lanes

- **[Lane F — Founder]** new code: Vojtech call (done ✓), historical-fetcher spike (Day 0.7), HTTP fetchers, cache, `observations.fetch()` orchestration, README, outreach.
  - Daily checklist: [`lanes/founder-build-lane.md`](lanes/founder-build-lane.md)
- **[Lane V — Vu]** lift from `../monorepo-v0.14.1/`: path reconnaissance (Day 0.5), fixture capture, `core/_internal/` shared utils, parsers, both merge policies, `pairs.py` → `research.py`, CI/CD scaffolding.
  - Daily checklist: [`lanes/vu-lift-lane.md`](lanes/vu-lift-lane.md)

Cross-review: each lane authors PRs in its area; the OTHER lane reviews. Codex `model_reasoning_effort=high` on any PR touching `_internal/merge/` or `research.py`.

## Sync points

| When | What | Gate |
|---|---|---|
| End of Day 0.5 | Vu: paths + parity fixtures committed | Founder can start Day 0.7 spike against the same fixtures |
| End of Day 0.7 | Founder: historical-fetcher spike works against public APIs | Day 1 lift+build can proceed; otherwise reopen timeline |
| End of Day 1 morning | Founder: workspace bootstrap PR merged. Vu + Founder sync on `_internal/` public API surface (10 min) | Vu unblocks on shared-utils shape |
| End of Day 1 | Vu: `core/_internal` skeleton merged. Founder: `_fetchers/awc` PR open | Day 2 build can import `_internal` symbols |
| End of Day 2 | Vu: merge policies + `research.py` merged. Founder: `observations.fetch()` orchestration + cache merged | First integration smoke green |
| End of Day 3 | Parity test green | Sprint 0 ships-or-doesn't decision |
| End of Day 4 | PyPI v0.1.0 published, N=2 outreach sent | 7-day validation window begins |

## Status checklist

- [ ] Day 0.5 — Path reconnaissance + fixture capture (Lane V)
- [ ] Day 0.7 — Historical-fetcher feasibility spike (Lane F)
- [ ] Day 1 — Bootstrap workspace + lift core/_internal + lift parsers
- [ ] Day 2 — Build fetchers + cache; lift merge policies + research()
- [ ] Day 3 — Parity test (HARD GATE) + live smoke tests
- [ ] Day 4 — PyPI v0.1.0 + N=2 outreach
- [ ] Day 4 + 7 days — N=3 yes signals per [`sprint0-validation.md`](sprint0-validation.md)

## Design source

The full design + plan-eng-review record lives at:
- `~/.gstack/projects/mostlyright/robe-unknown-design-20260521-121726.md` — design doc with 8 office-hours decisions + 8 plan-eng-review decisions + 9 Codex findings + lane split
- `~/.gstack/projects/mostlyright/robe-unknown-eng-review-test-plan-20260521-121726.md` — test plan with coverage diagram and parity-test requirements

Read those first if you need full context for any decision in this sprint.

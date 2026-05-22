# roadmap/

This directory previously held the lane-based Sprint 0 plan (`sprint0.md` + `lanes/`).
That plan **is now superseded by the GSD project planning at [`.planning/`](../.planning/)**.

## Where the current plan lives

- **[`.planning/ROADMAP.md`](../.planning/ROADMAP.md)** — 4 phases (v0.14.1 Parity Lift → Core Primitives + Catalog Adapters → Mode 2 + Migration Gate → Coverage + Docs + CI/CD + Release), Days 1-14, with success criteria per phase
- **[`.planning/PROJECT.md`](../.planning/PROJECT.md)** — vision + requirement IDs
- **[`.planning/REQUIREMENTS.md`](../.planning/REQUIREMENTS.md)** — full requirement specs
- **[`.planning/STATE.md`](../.planning/STATE.md)** — current position
- **[`.planning/phase-NN-<slug>/PLAN.md`](../.planning/phase-01-v0-14-1-parity-lift/PLAN.md)** — per-phase executable plan (RESEARCH.md, PLAN.md, eventually REVIEW.md + VERIFICATION.md)

## What's in `_archive/`

Historical record of how the project planning evolved. **Not authoritative.**

- `ROADMAP-merged-vision.md` — the 2026-05-21 "merged vision" narrative bridging mostlyright-mcp design + tradewinds Sprint 0 execution discipline. Read this if you want to know WHY the v0.2 foundations sit alongside the v0.1 parity work.
- `sprint0.md` — the original 3-4-day lane-based sprint plan. Days 0-4 numbering. Superseded by GSD Phase 1 (`.planning/phase-01-v0-14-1-parity-lift/PLAN.md`).
- `sprint0-validation.md` — original 7-day post-ship N=3 validation gate.
- `sprint0-bootstrap-status.md` — bootstrap status doc from Wave 1 work (now subsumed by `.planning/STATE.md`).
- `lanes/{founder,vu}-*-lane.md` — original two-lane (Vu lifts, Founder builds) daily checklists.

## Why the move

Two parallel planning sources caused confusion: lane-based "Sprint 0" with sub-day numbering (Day 0.5, 0.7, 1, …) ran in parallel with GSD's phase-based numbering. After 2026-05-22 cleanup, `.planning/` is canonical; this directory now exists only to preserve history.

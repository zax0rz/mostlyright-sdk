# mostlyright docs/

This directory is the **forward-looking design** for mostlyright. It explains where the codebase is heading after Sprint 0 ships v0.1.0.

## What lives here

| File | Scope |
|---|---|
| [`design.md`](./design.md) | **The v0.2 foundations design** (884 lines, approved 2026-05-21, amended across three Claude + Codex review passes). Describes the MCP-native primitives — `TimePoint`, `Schema` framework, source-identity invariants, MCP server with 3 tools — that build on top of Sprint 0's v0.1.0 wedge. Originally drafted under the working title "mostlyright-mcp v1" and merged into mostlyright on 2026-05-21. |

## What lives in `.planning/` (canonical project plan)

Current planning lives in the GSD-managed `.planning/` directory:

- [`.planning/ROADMAP.md`](../.planning/ROADMAP.md) — 4 phases over 14 days (v0.14.1 Parity Lift → Core Primitives → Mode 2 + Migration Gate → Coverage + Docs + CI/CD + Release)
- [`.planning/PROJECT.md`](../.planning/PROJECT.md) — vision + requirement IDs
- [`.planning/REQUIREMENTS.md`](../.planning/REQUIREMENTS.md) — full requirement specs
- [`.planning/STATE.md`](../.planning/STATE.md) — current position
- `.planning/phase-NN-<slug>/{RESEARCH.md, PLAN.md, REVIEW.md, VERIFICATION.md}` — per-phase artifacts

## What lives in `roadmap/` (historical)

`roadmap/` previously held a lane-based Sprint 0 plan that has been superseded by `.planning/`. Archived under `roadmap/_archive/`; see [`roadmap/README.md`](../roadmap/README.md) for the pointer.

## How docs/ and .planning/ relate

- **`.planning/` = THE PLAN.** Phase 1 (in progress) → Phase 2 (planned, awaiting Phase 1 ship) → Phase 3 → Phase 4 → v0.1.0 publish.
- **`docs/` = forward-looking design.** [`design.md`](./design.md) is the v0.2 foundations spec; not active planning. The 266-test reference implementation lives at `packages/core/src/mostlyright/_v02/` and gets rebranded to `mostlyright.core` in Phase 2.

## Branch workflow

- `main` — clean, only receives PRs from the master integration branch
- `merged-vision` — **master integration branch.** All sprint + feature work merges here.
- `feat/<feature>` and `sprint<N>/<task>` — sub-branches. Each runs a self-review loop with Codex before merging to `merged-vision`.
- One big PR from `merged-vision` → `main` when the integrated work is ready to land.

## History note

This design originated outside mostlyright as a separate project called `mostlyright-mcp`. On 2026-05-21 the visions were unified: mostlyright becomes the active repo for both the v0.1.0 wedge (lift from `mostlyright==0.14.1`, Sprint 0) and the v0.2+ MCP-native foundations (this doc). The old `mostlyright-mcp` repo at `~/Documents/GitHub/mostlyright-mcp/` retains the `feat/wave-1-core` branch as a frozen reference snapshot; the canonical work is now in mostlyright.

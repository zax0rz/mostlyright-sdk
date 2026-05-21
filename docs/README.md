# tradewinds docs/

This directory is the **forward-looking design** for tradewinds. It explains where the codebase is heading after Sprint 0 ships v0.1.0.

## What lives here

| File | Scope |
|---|---|
| [`design.md`](./design.md) | **The v0.2 foundations design** (884 lines, approved 2026-05-21, amended across three Claude + Codex review passes). Describes the MCP-native primitives — `TimePoint`, `Schema` framework, source-identity invariants, MCP server with 3 tools — that build on top of Sprint 0's v0.1.0 wedge. Originally drafted under the working title "mostlyright-mcp v1" and merged into tradewinds on 2026-05-21. |

## What lives in `roadmap/` (sibling directory)

Sprint plans and lane checklists for the **current sprint**:

- [`roadmap/sprint0.md`](../roadmap/sprint0.md) — Sprint 0 plan: ship `tradewinds` + `tradewinds-weather` v0.1.0 to PyPI with byte-equivalence to `mostlyright==0.14.1`'s `client.pairs()`. 3-4 days.
- `roadmap/lanes/{founder,vu}-*-lane.md` — daily checklists per lane.
- `roadmap/sprint0-validation.md` — N=3 yes-signal definition for the 7-day post-ship validation window.

## How docs/ and roadmap/ relate

- **`roadmap/` = NOW.** Sprint 0 is the next thing shipping; everything in `roadmap/` is execution-grade.
- **`docs/` = NEXT.** v0.2 foundations is the milestone after Sprint 0 (and after the 7-day validation window). The 266-test reference implementation already lives at `packages/core/src/tradewinds/_v02/` on the `feat/v0.2-foundations` branch (off `merged-vision`).

When Sprint 0 ships and the validation gate passes, Sprint 1 (v0.2 work) opens, and `roadmap/sprint1.md` will be derived from `docs/design.md`.

## Branch workflow

- `main` — clean, only receives PRs from the master integration branch
- `merged-vision` — **master integration branch.** All sprint + feature work merges here.
- `feat/<feature>` and `sprint<N>/<task>` — sub-branches. Each runs a self-review loop with Codex before merging to `merged-vision`.
- One big PR from `merged-vision` → `main` when the integrated work is ready to land.

## History note

This design originated outside tradewinds as a separate project called `mostlyright-mcp`. On 2026-05-21 the visions were unified: tradewinds becomes the active repo for both the v0.1.0 wedge (lift from `mostlyright==0.14.1`, Sprint 0) and the v0.2+ MCP-native foundations (this doc). The old `mostlyright-mcp` repo at `~/Documents/GitHub/mostlyright-mcp/` retains the `feat/wave-1-core` branch as a frozen reference snapshot; the canonical work is now in tradewinds.

---
quick_id: 260524-qdu
description: Add Dual-SDK Planning Rule to CLAUDE.md
date: 2026-05-24
branch: quick/260524-qdu-claude-md-dual-sdk-rule
commit: f52f0ab
---

# Quick Task 260524-qdu — Summary

## What shipped

Added a new `## Dual-SDK Planning Rule` H2 section to [`CLAUDE.md`](../../../CLAUDE.md) at line 43, between the existing `## Collaboration rules (Sprint 0 = lane-split)` and `## Data + parity rules` sections. The section codifies the TS Parity requirement on every plan that touches the public API surface.

## Section content

Three required items in the TS Parity block:

1. What the TS equivalent looks like (identical API, adapted implementation, or N/A).
2. Whether it ships in the same phase or gets a parity ticket per [`CROSS-SDK-SYNC.md`](../../CROSS-SDK-SYNC.md).
3. Any TS-specific constraints (bundle size, browser compatibility, no Node APIs).

Python-internal changes (DataFrame backend, parquet caching) are exempt.

Applies to every PLAN.md from `/gsd-plan-phase`, PROJECT.md "Active scope" updates, and ROADMAP entries that add/change `tradewinds.*` or `tradewinds.weather.*` public surface. Reviewers (codex + python-architect + TypeScript Architect) check for presence.

## Branch + commit

- **Branch:** `quick/260524-qdu-claude-md-dual-sdk-rule` (new branch off `claude/vigorous-meninsky-82f85e`)
- **Commit:** `f52f0ab docs(claude-md): add Dual-SDK Planning Rule near collaboration discipline`
- **Files changed:** `CLAUDE.md` (1 file, +12 lines)

## Verification

- `grep -n "^## Dual-SDK Planning Rule" CLAUDE.md` → line 43 (between Collaboration rules at 28 and Data + parity rules at 55).
- `grep -c "TS Parity" CLAUDE.md` → 2 matches.
- `grep -c "CROSS-SDK-SYNC.md" CLAUDE.md` → 1 match.
- `git show --stat HEAD` → 1 file changed (`CLAUDE.md` only). No collateral.

## How to merge

```bash
git checkout claude/vigorous-meninsky-82f85e
git merge --no-ff quick/260524-qdu-claude-md-dual-sdk-rule
# or open a PR from this branch directly to main once ready
```

## Why this is on a branch

Per user instruction: "Place on a NEW branch (not directly on the current `claude/vigorous-meninsky-82f85e` branch) so the user can decide when to merge." The new rule also bypasses the dual-SDK rule itself (CLAUDE.md is doc-only — no public API surface change), so no TS Parity section is required for this commit.

## Forward-looking impact

The rule applies retroactively to Phase 7 plans (just landed on `claude/vigorous-meninsky-82f85e` at commit `9ec559b`). Phase 7's plans currently note TS port as "Out of Scope" (deferred to TS-W3+ per `.planning/CROSS-SDK-SYNC.md`). When this branch merges back, the Phase 7 plans should be audited for a formal TS Parity block — the "Out of Scope" notes likely satisfy the rule (option N/A + parity-ticket route), but worth a confirming pass.

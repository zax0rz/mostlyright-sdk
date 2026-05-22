# Contributing to tradewinds

Read [`CLAUDE.md`](CLAUDE.md) first — it's the source of truth for collaboration rules, data + parity discipline, testing, and review process.

## Quick start

```bash
git clone <repo>
cd tradewinds
uv sync                                                # installs workspace + dev deps
uv run pre-commit install                              # pre-commit hook (fast checks)
uv run pre-commit install --hook-type pre-push         # pre-push hook (pytest)
uv run pytest -m "not live" -q                         # fast tests, no network
```

## Workflow

1. **Branch per work unit.** Name format: `sprint0/<lane>-<task>`, e.g. `sprint0/vu-lift-core-internal`.
2. **Write tests first** (TDD). RED → GREEN → REFACTOR.
3. **Open PR.** Reviewer is the OTHER lane (Lane F authors → Vu reviews; Lane V authors → Founder reviews).
4. **Codex review REQUIRED** on any PR touching `_internal/merge/` or `research.py` (parity-critical paths). Use `codex review` with `model_reasoning_effort=high`.
5. **Pre-commit + pre-push hooks** mandatory. No `--no-verify`. Fix the issue. Pre-commit = fast (ruff/format/whitespace); pre-push = `pytest -m "not live"`. Install both: `uv run pre-commit install && uv run pre-commit install --hook-type pre-push`.
6. **Merge only after approved review.**

## Lane assignments (Sprint 0)

See [`roadmap/sprint0.md`](roadmap/sprint0.md) for overview and [`roadmap/lanes/`](roadmap/lanes/) for per-lane day-by-day checklists.

- **Lane F (Founder):** new HTTP fetchers, cache, orchestration, README, outreach. Daily checklist: [`roadmap/lanes/founder-build-lane.md`](roadmap/lanes/founder-build-lane.md).
- **Lane V (Vu, @helloiamvu):** lift from `../monorepo-v0.14.1/`, CI/CD scaffolding. Daily checklist: [`roadmap/lanes/vu-lift-lane.md`](roadmap/lanes/vu-lift-lane.md).

## Issues / TODOs

See [`TODOS.md`](TODOS.md) for tracked follow-ups. Format follows monorepo's TODOS.md convention.

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
4. **Review discipline:** every PR runs the two-reviewer loop (Codex + Python Architect) before merging to `merged-vision`. See [`.planning/REVIEW-DISCIPLINE.md`](.planning/REVIEW-DISCIPLINE.md) for the loop mechanics, severity gate, never-skip path list, and trivial-skip rules.
5. **Pre-commit + pre-push hooks** mandatory. No `--no-verify`. Fix the issue. Pre-commit = fast (ruff/format/whitespace); pre-push = `pytest -m "not live"`. Install both: `uv run pre-commit install && uv run pre-commit install --hook-type pre-push`.
6. **Merge only after approved review.**

## Phase planning

Current authoritative plan lives under [`.planning/`](.planning/) (GSD structure):

- [`.planning/ROADMAP.md`](.planning/ROADMAP.md) — 4 phases + Phase 1.5 (v0.14.1 Parity Lift → Fetcher Optimization → Core Primitives → Mode 2 → Release), Days 1-14
- [`.planning/PROJECT.md`](.planning/PROJECT.md) — vision + requirement IDs
- [`.planning/REQUIREMENTS.md`](.planning/REQUIREMENTS.md) — full requirement specs
- [`.planning/STATE.md`](.planning/STATE.md) — current execution position
- [`.planning/phase-NN-<slug>/PLAN.md`](.planning/phase-01-v0-14-1-parity-lift/PLAN.md) — per-phase executable plan

Lane assignments (Lane V = Vu lifts from `monorepo-v0.14.1/`; Lane F = Founder builds new code) are described in `.planning/PROJECT.md` § Execution model. The earlier `roadmap/sprint0.md` + `roadmap/lanes/` lane-based plan is **superseded and archived** — see [`roadmap/README.md`](roadmap/README.md) for the redirect.

## Issues / TODOs

See [`TODOS.md`](TODOS.md) for tracked follow-ups. Format follows monorepo's TODOS.md convention.

# Planning Workspace Setup (Maintainers Only)

This SDK uses [GSD](https://github.com/anthropics/get-shit-done-cc) for phase planning. The planning workspace lives in `.planning/` and is **not part of this public repo** — it's a separate private repo at [mostlyrightmd/planning](https://github.com/mostlyrightmd/planning).

If you are a maintainer with write access, set up the planning workspace alongside your SDK clone:

```bash
cd ~/Documents/GitHub/mostlyright-sdk
git clone git@github.com:mostlyrightmd/planning.git .planning
```

That's it. The `.planning/` directory is gitignored in this repo (per [PR #5](https://github.com/mostlyrightmd/mostlyright-sdk/pull/5)), so its files won't show up in `git status` here. Edits to `.planning/` content are committed/pushed via the inner repo:

```bash
cd .planning
git add ROADMAP.md
git commit -m "phase XX: note about progress"
git push
```

## Why this is split

The planning workspace contains:

- Roadmap with internal phase ordering + decimal urgent inserts
- STATE.md with phase closeout notes
- Per-phase PLAN.md files with task breakdowns, dependency graphs, reviewer notes
- RESEARCH.md files capturing technical investigation
- Cross-AI review feedback and audit artifacts

This is useful to maintainers but noisy for SDK users. Keeping it in a separate private repo:

1. **Public repo stays clean** — no internal AI scratchpad in the released code
2. **Cross-machine sync still works** — clone the private repo on any machine where you do planning work
3. **Strategic content stays private** — roadmap timing and competitive positioning aren't visible to prediction-market competitors

## If you don't have write access

You don't need the planning workspace. `CLAUDE.md`, `CONTRIBUTING.md`, and `docs/` cover everything an external contributor needs. The `.planning/` references in CLAUDE.md will simply not resolve in your clone — that's expected.

## Adding a maintainer to the planning repo

```bash
gh api repos/mostlyrightmd/planning/collaborators/<github-username> -X PUT -F permission=push
```

Or via the GitHub UI: [planning repo settings → Collaborators](https://github.com/mostlyrightmd/planning/settings/access).

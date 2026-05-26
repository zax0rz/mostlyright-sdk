# Planning Workspace Setup (Maintainers Only)

This SDK uses [GSD](https://github.com/anthropics/get-shit-done-cc) for phase planning. The planning workspace is **not part of this public repo** — it's a separate private repo at [mostlyrightmd/planning](https://github.com/mostlyrightmd/planning).

If you're a maintainer with write access, follow the **nested-clone setup** below so the `.planning/` paths referenced throughout `CLAUDE.md`, `AGENTS.md`, `docs/`, and the GitHub workflows all resolve in your working tree.

## Standard setup (nested clone into `.planning/`)

```bash
# 1. Clone the SDK
git clone git@github.com:mostlyrightmd/mostlyright-sdk.git
cd mostlyright-sdk

# 2. Clone the planning repo into `.planning/`
git clone git@github.com:mostlyrightmd/planning.git .planning

# 3. (One-time) install
uv sync --all-packages
pnpm install
```

After this, `.planning/` is a self-contained inner git repo. The SDK's `.gitignore` ignores it entirely, so `git status` in the SDK ignores everything inside `.planning/`. To make planning edits, `cd .planning` and use git as normal:

```bash
cd .planning
git add ROADMAP.md
git commit -m "phase XX: note about progress"
git push
```

## What lives in `.planning/`

- `ROADMAP.md` — internal phase ordering with decimal urgent inserts
- `STATE.md` — phase closeout notes + accumulated decisions/blockers
- `PROJECT.md` — long-term vision + locked decisions table
- `REQUIREMENTS.md` — full traceability ID list (PARITY-XX, RENAME-XX, NPM-XX, etc.)
- `REVIEW-DISCIPLINE.md` — review-loop mechanics, severity gate, never-skip path list
- `CROSS-SDK-SYNC.md` — Python ↔ TypeScript parity contract (consumed by `docs-publish.yml` at CI time; the planning repo is now the single source of truth)
- `phases/NN-name/` — per-phase `PLAN.md` / `RESEARCH.md` / `CONTEXT.md` / `SUMMARY.md`
- `research/` — empirical-probe artifacts (rate limits, CORS matrix, NWP mirror concurrency, spike archives)
- `quick/` — ad-hoc task workspaces
- Cross-AI review feedback + audit logs

## Why the planning repo is split out

This material is useful to maintainers but noisy for SDK users. Keeping it in a separate private repo means:

1. **Public repo stays clean** — no internal AI scratchpad, review iteration logs, or strategic phase ordering in the released code.
2. **Cross-machine sync still works** — clone the planning repo on any machine you do planning on; the SDK clone is unaffected.
3. **Strategic content stays private** — roadmap timing, competitive positioning, and per-phase risk notes aren't visible to prediction-market competitors.

## Picking up on a new machine

Same two `git clone` commands as Step 1+2 above. The nested-clone pattern is portable; no symlinks, no submodules, no environment-specific paths.

If you've been using a sibling-clone pattern (e.g. `~/Documents/GitHub/planning/` as a sibling of the SDK clone), you can either keep doing that or migrate to the nested-clone pattern by `git clone`-ing the planning repo into the SDK's `.planning/` directory. Both patterns work for the planning repo itself; only the nested-clone makes the `.planning/X` doc references in CLAUDE.md / docs / workflows resolve directly.

## If you don't have write access

You don't need the planning workspace. `CLAUDE.md`, `AGENTS.md`, `CONTRIBUTING.md`, `SECURITY.md`, and `docs/` cover everything an external contributor needs. The `.planning/` references in those files will simply not resolve in your clone — that's expected. The public docs site at <https://mostlyright.md/docs/sdk/> is the canonical user-facing reference; the planning repo is internal-only.

## Adding a maintainer to the planning repo

```bash
gh api repos/mostlyrightmd/planning/collaborators/<github-username> -X PUT -F permission=push
```

Or via the GitHub UI: [planning repo settings → Collaborators](https://github.com/mostlyrightmd/planning/settings/access).

## Note on `CROSS-SDK-SYNC.md`

Earlier versions of this repo tracked `.planning/CROSS-SDK-SYNC.md` directly via a `.gitignore` exception (Phase 15 W3). That was removed for v1.0 — the planning repo is now the single source of truth for that file. `scripts/generate_parity_table.py` falls back to a built-in default registry when the file isn't present (e.g. during external contributors' builds), so the CI docs-publish job still works without the planning repo cloned alongside.

---
phase: 260522-9uj
plan: 01
subsystem: infra
tags: [pre-commit, pytest, dev-loop, git-hooks]

# Dependency graph
requires: []
provides:
  - Pre-commit / pre-push hook split (fast commits, pytest gate at push)
  - Updated CLAUDE.md + CONTRIBUTING.md describing the split
affects: [all-future-contributors-dev-loop]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Two-stage hook discipline: pre-commit = fast checks (ruff/format/whitespace/yaml/toml), pre-push = pytest fast suite"

key-files:
  created: []
  modified:
    - .pre-commit-config.yaml
    - CLAUDE.md
    - CONTRIBUTING.md

key-decisions:
  - "Use canonical pre-commit stage name `pre-push` (not deprecated `push` alias)"
  - "Re-install default pre-commit hook for safety after worktree config quirk"

patterns-established:
  - "Commits stay fast (~1s); pushes carry the pytest gate (~15s) before code leaves the laptop"

requirements-completed: [DEV-LOOP-01]

# Metrics
duration: ~8 min
completed: 2026-05-22
---

# Quick Task 260522-9uj: Move pytest from pre-commit to pre-push Summary

**Moved `pytest-fast` hook from default pre-commit stage to `pre-push` stage so commits stay snappy (~1s, ruff + basic checks only) while pushes still run the fast test suite (~15s) as the gate before code leaves the laptop.**

## Performance

- **Duration:** ~8 min
- **Started:** 2026-05-22T05:05:00Z (approx)
- **Completed:** 2026-05-22T05:13:09Z
- **Tasks:** 1
- **Files modified:** 3

## Accomplishments

- `.pre-commit-config.yaml` updated: added `stages: [pre-push]` to the `pytest-fast` local hook only; all other hooks (ruff, ruff-format, trailing-whitespace, end-of-file-fixer, check-yaml, check-toml, check-added-large-files) remain on the default commit stage
- Installed both hooks via `uv run pre-commit install` and `uv run pre-commit install --hook-type pre-push` (in the parent repo since worktree's `core.hooksPath` resolves there)
- CLAUDE.md collaboration-rules bullet rewritten to state pre-commit runs fast checks and pre-push runs `pytest -m "not live"`, with explicit install commands
- CONTRIBUTING.md workflow step 5 + Quick start updated with same split, plus added the two `pre-commit install` invocations to the bootstrap block

## Task Commits

1. **Task 1: Move pytest-fast to pre-push stage and install the hook** - `df23e7c` (chore)

_Note: docs commit (SUMMARY.md, STATE.md) is handled by the orchestrator per the quick-task workflow._

## Files Created/Modified

- `.pre-commit-config.yaml` - Added `stages: [pre-push]` line under the existing pytest-fast hook (1 line added)
- `CLAUDE.md` - Rewrote the pre-commit-mandatory bullet to describe the commit/push split and required install commands (1 line replaced)
- `CONTRIBUTING.md` - Updated Quick start (added two `pre-commit install` lines) and workflow step 5 (described split + install commands)

## Diff Applied to `.pre-commit-config.yaml`

```diff
@@ -26,3 +26,4 @@ repos:
         language: system
         pass_filenames: false
         always_run: true
+        stages: [pre-push]
```

(Single-line addition; no other hook touched.)

## Verification Outputs

**1. Config has `stages: [pre-push]` on pytest-fast:**
```
$ grep -A 8 "id: pytest-fast" .pre-commit-config.yaml | grep -q "stages: \[pre-push\]"
OK: stages: [pre-push] present
```

**2 & 3. Both hooks installed:**
```
$ pre-commit install --hook-type pre-push
pre-commit installed at .git/hooks/pre-push
$ pre-commit install
pre-commit installed at .git/hooks/pre-commit
```

**4. `pre-commit run --all-files` does NOT invoke pytest:**
```
ruff.....................................................................Passed
ruff-format..............................................................Failed  (pre-existing, unrelated file - see Deferred Issues)
trim trailing whitespace.................................................Passed
fix end of files.........................................................Passed
check yaml...............................................................Passed
check toml...............................................................Passed
check for added large files..............................................Passed
---
OK: pytest absent from pre-commit run
```

**5. `pre-commit run --hook-stage pre-push pytest-fast --all-files` DOES invoke pytest-fast:**
```
pytest fast tests (no live)..............................................Failed
- hook id: pytest-fast
- exit code: 2
ERROR collecting packages/core/tests/test_namespace.py
  ModuleNotFoundError: No module named 'tradewinds'
```
The hook fired (its name appeared in the output) and ran pytest. The failure is a pre-existing test-collection issue (workspace package not installed in venv yet — `uv sync` needed). Per the plan's done criteria: "runs pytest-fast and passes (or fails on real test failure — acceptable; the hook fired)". ✓ Satisfied.

**6. Ruff still runs on default stage:**
```
ruff.....................................................................Passed
OK: ruff still runs on default stage
```

**7. Docs updated:**
```
OK: CLAUDE.md mentions pre-push
OK: CONTRIBUTING.md mentions pre-push
```

**Round-trip sanity check (real commit):** Task 1's commit (`df23e7c`) succeeded with only the fast hooks running — confirmed by the pre-commit output captured during the commit:
```
ruff.................................................(no files to check)Skipped
ruff-format..........................................(no files to check)Skipped
trim trailing whitespace.................................................Passed
fix end of files.........................................................Passed
check yaml...............................................................Passed
check toml...........................................(no files to check)Skipped
check for added large files..............................................Passed
```
No `pytest fast tests` line — pytest did NOT run on commit. ✓ The dev loop is now: `git commit` → ~1s (ruff + basic checks); `git push` → ~15s (pytest fast suite).

## Decisions Made

- **Canonical stage name `pre-push`, not deprecated `push` alias** (per plan instruction; pre-commit ≥3.2 standard).
- **Re-ran `pre-commit install` (no flag) after the `--hook-type pre-push` install** as a safety net per the plan's Step B.
- **Installed hooks from the parent repo, not the worktree.** The worktree's local git config has `core.hooksPath` set to the parent's `.git/hooks/` (worktree-creation script default). `pre-commit install` refuses to install when `core.hooksPath` is set, so the install was run from the parent repo where the path is the natural default. The hooks fire correctly from the worktree because git resolves `core.hooksPath` at hook-invocation time.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Unset `core.hooksPath` in parent repo to allow `pre-commit install`**
- **Found during:** Task 1, Step B (hook installation)
- **Issue:** `pre-commit install` errored with `Cowardly refusing to install hooks with core.hooksPath set`. Both the worktree and the parent repo had `core.hooksPath = /Users/helloiamvu/Documents/GitHub/tradewinds/.git/hooks` set locally (likely from the worktree-creation script). The parent's setting was a no-op (it pointed to the default location anyway).
- **Fix:** `git config --local --unset core.hooksPath` in the parent repo, then `pre-commit install` and `pre-commit install --hook-type pre-push` from the parent. The worktree's local setting was left intact — it correctly points to the parent's `.git/hooks/` where pre-commit just installed, so hooks fire from the worktree too.
- **Files modified:** None (git config only; not tracked in source).
- **Verification:** Both `.git/hooks/pre-commit` and `.git/hooks/pre-push` contain the pre-commit shim (`grep -q "pre-commit"` succeeds). Real commit `df23e7c` showed the pre-commit hook firing in the worktree.
- **Committed in:** N/A (git config, not source).

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Necessary to complete Step B. No scope creep. Future contributors who run `pre-commit install` in their own clones should not hit this — `core.hooksPath` was a worktree-creation-script artifact, not a project convention.

## Deferred Issues

**1. `packages/core/tests/test_namespace.py` ruff-format diff (out of scope)**
- During `pre-commit run --all-files` (default stage), `ruff-format` reported the file was reformatted. The reformatting is a pre-existing formatting drift unrelated to this quick task (which only touches `.pre-commit-config.yaml`, `CLAUDE.md`, `CONTRIBUTING.md`).
- Action taken: `git checkout -- packages/core/tests/test_namespace.py` to revert; not included in the task commit.
- Suggested follow-up: run `uv run ruff format .` in a separate housekeeping commit (or let the next contributor who touches that file fix it on save).

**2. `pytest -m "not live"` test-collection error (out of scope)**
- During the pre-push hook verification (`pre-commit run --hook-stage pre-push pytest-fast --all-files`), pytest failed with `ModuleNotFoundError: No module named 'tradewinds'` while collecting `packages/core/tests/test_namespace.py`. The workspace package is not installed in the current `.venv` (likely needs `uv sync` rerun). This is the existing test-infrastructure state of the worktree, not a regression caused by this task.
- The plan explicitly accepts this state: "runs pytest-fast and passes (or fails on real test failure — acceptable; the hook fired)". The hook fired correctly.
- Suggested follow-up: separate task to ensure `uv sync` installs the workspace package into `.venv` (likely a workspace-source path or editable-install fix).

## Issues Encountered

- `core.hooksPath` block on `pre-commit install` (resolved — see Deviations Rule 3).
- Out-of-scope ruff-format diff on `test_namespace.py` (deferred — see Deferred Issues).
- Out-of-scope pytest test-collection error (deferred — see Deferred Issues).

## User Setup Required

None — the install commands are now documented in CLAUDE.md and CONTRIBUTING.md; new contributors will pick them up via the Quick start in CONTRIBUTING.md.

## Next Phase Readiness

- Dev loop now optimized: commits ~1s, pushes ~15s (vs. ~15s on every commit before).
- pytest gate preserved before code leaves the laptop.
- All other pre-commit hooks (ruff, format, whitespace, yaml/toml/large-files) continue to run on commit unchanged.
- No follow-up blocking work for this quick task; the orchestrator handles docs commit + worktree cleanup.

---
*Quick task: 260522-9uj*
*Completed: 2026-05-22*

## Self-Check: PASSED

Verified after writing this SUMMARY:

- `.pre-commit-config.yaml` modification present:
  ```
  $ grep -A 1 "always_run: true" .pre-commit-config.yaml | tail -1
          stages: [pre-push]
  ```
  FOUND.
- `CLAUDE.md` mentions `pre-push`: FOUND.
- `CONTRIBUTING.md` mentions `pre-push` and both `pre-commit install` invocations: FOUND.
- Task 1 commit `df23e7c` exists in git log: FOUND (`git log --oneline | grep df23e7c` matches `df23e7c chore(260522-9uj-01): move pytest-fast hook to pre-push stage`).
- `.git/hooks/pre-commit` and `.git/hooks/pre-push` both exist and reference pre-commit: FOUND.

# Phase 12: Rename `tradewinds` → `mostlyright` — Context

**Gathered:** 2026-05-25
**Status:** Ready for planning
**Source:** User brief (treated as PRD; 9-step execution order locked)

<domain>
## Phase Boundary

Mechanical end-to-end rename of every in-repo identifier from `tradewinds` to `mostlyright`. **Zero behavior change. Zero test regressions at any wave boundary.** The repo name on GitHub stays `helloiamvu/tradewinds` — only in-tree identifiers rename in Phase 12.

**What this phase ships in-tree:**
- 3 PyPI distribution names renamed (`tradewinds` / `tradewinds-weather` / `tradewinds-markets` → `mostlyright` / `mostlyright-weather` / `mostlyright-markets`)
- 5 npm package names renamed (`@tradewinds/{codegen,core,weather,markets}` + unscoped meta `tradewinds` → `@mostlyright/*` + unscoped meta `mostlyright`)
- 3 Python source directories renamed (`packages/*/src/tradewinds/` → `packages/*/src/mostlyright/`)
- ~1074 Python `import`/`from` rewrites
- ~77 TypeScript import rewrites
- Cache env var rename `TRADEWINDS_CACHE_DIR` → `MOSTLYRIGHT_CACHE_DIR` with one-release back-compat fallback (deprecation warning on the old name)
- Default cache directory `~/.tradewinds/cache/v1/` → `~/.mostlyright/cache/v1/`
- ~85 mentions in `docs/*.md`, ~20 in `CLAUDE.md`, root `README.md` rewritten
- CI workflows env-var refs updated (filenames `release.yml` / `release-ts.yml` STAY for git history continuity)

**What this phase does NOT ship (operator-gated, out of plan scope):**
- GitHub repo URL rename — repo stays `helloiamvu/tradewinds`. In-tree URLs to the repo (in `README.md` badges, package `repository` fields) stay pointing at `helloiamvu/tradewinds` for Phase 12. Operator may rename the GH repo out-of-band later.
- PyPI trusted-publisher registration for the new names — **operator pre-flight step, manual on pypi.org**
- npm `@mostlyright` scope claim — **operator pre-flight step, manual on npmjs.com**
- npm OIDC pending publisher registration — **operator pre-flight step**
- `~/Documents/GitHub/mostlyright` → `mostlyright-legacy` rename — **operator pre-flight step (cannot be automated from the worktree)**
- Old PyPI / npm package cleanup — `tradewinds*` / `@tradewinds/*` stay orphaned; operator transfers/deletes out-of-band
- `.planning/` archive prose rewrites (~4858 mentions) — left intact to preserve audit trail
- New behavior — Phase 12 is pure rename

**Public API surface change:** NONE on the Python or TS surface — every existing `tw.research(...)` / `tradewinds.weather.obs(...)` call site moves to `mostlyright.research(...)` / `mostlyright.weather.obs(...)` mechanically. No signature change. No behavior change.

</domain>

<decisions>
## Implementation Decisions (all LOCKED by user)

### Wave structure (LOCKED — 9 waves; goal is zero test regressions at every step)

The user's 9-step order maps 1:1 to Wave 1 → Wave 9 (well — 7 in-tree waves plus 2 operator-gated steps). Each in-tree wave must end with the full test suite green. RED at any wave boundary BLOCKS the next wave.

| # | Wave | Atomic edit | Test gate after wave |
|---|------|-------------|---------------------|
| W1 | Directory + pyproject + npm scope rename, atomic | `git mv packages/*/src/tradewinds packages/*/src/mostlyright`; rewrite each `pyproject.toml` `name` + `[tool.hatch.build.targets.wheel] packages`; rewrite inter-package version pins; rename 5 npm packages + workspace deps | `uv sync` succeeds; `uv build` produces 3 wheels; `pnpm install` succeeds; tests will RED until W2 — DOCUMENTED expected RED state |
| W2 | Python import rewrite | scripted `from tradewinds` / `import tradewinds` → `mostlyright` across `packages/`, `tests/`, `scripts/`, in 3 BATCHES with test gate after each | `uv run pytest -m "not live" -q` green after each batch; final state: `grep -rn 'tradewinds' --include='*.py' packages/ tests/ scripts/ \| wc -l` returns 0 |
| W3 | TS import rewrite | scripted `from "@tradewinds/...` → `from "@mostlyright/...` across `packages-ts/` | `pnpm -r run typecheck` green; `CI=1 pnpm -r run test` green |
| W4 | Cache env var migration with back-compat shim | rename `TRADEWINDS_CACHE_DIR` → `MOSTLYRIGHT_CACHE_DIR` (~204 occurrences); add `_cache_dir.py` back-compat shim reading both env vars; default path `~/.tradewinds/cache/v1/` → `~/.mostlyright/cache/v1/` | New `test_cache_env_back_compat.py` asserts: (a) MOSTLYRIGHT_CACHE_DIR wins when both set, (b) TRADEWINDS_CACHE_DIR-only emits DeprecationWarning, (c) neither falls back to `~/.mostlyright/cache/v1/`. Full suite green. |
| W5 | Docs + prose rewrite | rewrite ~85 mentions in `docs/*.md`, ~20 in `CLAUDE.md`, root `README.md`. Install commands → `pip install mostlyright[...]` / `npm install @mostlyright/*`. Code-fence examples updated. **LEAVE `.planning/` ARCHIVE ALONE.** | Lint: `grep -rn 'tradewinds' docs/ CLAUDE.md README.md` returns 0 (excluding URL fields). |
| W6 | CI workflow updates | keep `release.yml` + `release-ts.yml` filenames; update env-var names + any hardcoded `tradewinds*` references in YAML; verify trusted-publisher project names match new PyPI/npm names | `act` dry-run OR manual YAML review; in-repo CI run for `test.yml`/`test-ts.yml` green. |
| W7 | Parity-gate pre-flight + full test run + STATE.md + Phase 12 README | `uv run pytest -q` (INCLUDING `@pytest.mark.live` parity fixtures); `CI=1 pnpm -r run test`; write `phases/12-rename-to-mostlyright/README.md` documenting rename, legacy folder rename, orphaned names, back-compat removal timeline; update `.planning/STATE.md` with Phase 12 closeout section. | Parity test (`tests/test_parity.py`) byte-equivalent under new module name; full Python suite green; full TS suite green. |

**Operator pre-flight (BEFORE Wave 1 ships):**
- OP1: `mv ~/Documents/GitHub/mostlyright ~/Documents/GitHub/mostlyright-legacy` — manual.
- OP2: Register 3 PyPI pending publishers (`mostlyright`, `mostlyright-weather`, `mostlyright-markets`) bound to repo + `release.yml` + env `pypi` — manual on pypi.org.
- OP3: Claim `@mostlyright` npm scope — manual on npmjs.com.
- OP4: Register 4 npm OIDC pending publishers (`@mostlyright/core`, `@mostlyright/weather`, `@mostlyright/markets`, unscoped meta `mostlyright`) bound to repo + `release-ts.yml` + env `npm` — manual.

**Operator post-merge follow-ups (NOT in Phase 12):**
- Tag `v0.2.0` to publish renamed PyPI distributions.
- Tag `vts-0.2.0` to publish renamed npm packages.
- Optional: transfer or delete orphaned PyPI/npm names.

### Rename safety rules (LOCKED)

1. **No `git rm` then `git add`** — use `git mv` so blame history follows the file.
2. **No bulk find-replace across entire repo at once.** Wave by wave; test after each.
3. **`uv lock` regenerated as part of Wave 1** — the project pin in `uv.lock` references `tradewinds` and must move.
4. **`pnpm-lock.yaml` regenerated as part of Wave 1** — same reason.
5. **Pre-commit + pre-push hooks stay installed throughout.** Hooks block accidental `--no-verify`. If a hook fires false-positive on rename diffs (unlikely), fix the underlying issue, never `--no-verify`.
6. **No `[review-skip: trivial]` shortcut** — this is a never-skip path per REVIEW-DISCIPLINE.md (touches `pyproject.toml` dependency pins, schema codegen, CI workflows).
7. **`.planning/` left alone** — historical audit trail. The Phase 12 README explicitly documents this choice.
8. **Parity-locked modules stay byte-equivalent** under the new module name. The parity test reads `from mostlyright import research` and the 5 fixture files stay binary-identical.

### Cache back-compat semantics (LOCKED — one-release deprecation window)

Implementation lives at NEW file `packages/core/src/mostlyright/_internal/_cache_dir.py`:

```python
"""Resolve the on-disk cache directory.

Resolution order (highest precedence first):
1. ``MOSTLYRIGHT_CACHE_DIR`` env var (canonical, post-Phase-12).
2. ``TRADEWINDS_CACHE_DIR`` env var (legacy; emits DeprecationWarning;
   scheduled for removal in v0.3).
3. Default: ``~/.mostlyright/cache/v1/``.

In v0.3 the ``TRADEWINDS_CACHE_DIR`` branch will be removed; users on v0.2.x get
one full release to migrate. Migration is byte-equivalent: ``mv ~/.tradewinds
~/.mostlyright`` works without schema change.
"""

from __future__ import annotations

import os
import warnings
from pathlib import Path
from typing import Final

_DEFAULT: Final[Path] = Path.home() / ".mostlyright" / "cache" / "v1"
_LEGACY_ENV: Final[str] = "TRADEWINDS_CACHE_DIR"
_CANONICAL_ENV: Final[str] = "MOSTLYRIGHT_CACHE_DIR"


def resolve_cache_dir() -> Path:
    canonical = os.environ.get(_CANONICAL_ENV)
    if canonical:
        return Path(canonical)
    legacy = os.environ.get(_LEGACY_ENV)
    if legacy:
        warnings.warn(
            f"{_LEGACY_ENV} is deprecated; use {_CANONICAL_ENV}. "
            f"Support will be removed in v0.3. Run: "
            f"mv ~/.tradewinds ~/.mostlyright",
            DeprecationWarning,
            stacklevel=2,
        )
        return Path(legacy)
    return _DEFAULT
```

Tests (`packages/core/tests/test_cache_env_back_compat.py`, new):
- `MOSTLYRIGHT_CACHE_DIR=/tmp/x TRADEWINDS_CACHE_DIR=/tmp/y` → returns `Path("/tmp/x")`, NO warning.
- `TRADEWINDS_CACHE_DIR=/tmp/y` only → returns `Path("/tmp/y")`, emits `DeprecationWarning` matching `/TRADEWINDS_CACHE_DIR is deprecated/`.
- Neither set → returns `Path.home() / ".mostlyright" / "cache" / "v1"`, no warning.

All existing call sites that today read `os.environ["TRADEWINDS_CACHE_DIR"]` directly MUST be migrated to call `resolve_cache_dir()`. Find them via `grep -rn 'TRADEWINDS_CACHE_DIR' packages/ --include='*.py'`.

### Test-pass gate semantics (LOCKED)

- "Tests green" = `uv run pytest -m "not live" -q` exits 0.
- "Parity green" = `uv run pytest tests/test_parity.py -q` exits 0 (the @pytest.mark.live tests must run pre-merge).
- "TS tests green" = `CI=1 pnpm -r run test` exits 0.
- "Typecheck green" = `pnpm -r run typecheck` exits 0.

Wave 2's 3-batch Python rewrite gate is THE load-bearing safety mechanism: if Batch A leaves the suite RED, Batch B is BLOCKED. Document the recovery path: revert the batch's commit; investigate why the find-replace missed a site; iterate.

### Claude's Discretion

- The exact sed/perl/ts-morph script used to do the import rewrite — planner picks. BSD sed on macOS needs `-i ''`; GNU sed needs `-i`. Use a portable Python helper if cross-platform matters (CI is Linux-only so GNU sed suffices for CI; developer machines vary).
- The grep regex used for the "zero remaining tradewinds references" assertion — planner picks (must exclude `.planning/`, must exclude `node_modules/`, must exclude `dist/`, must exclude `.git/`).
- Whether to do the 5 npm package renames as 5 commits or 1 commit within W1 — planner picks (recommendation: 1 commit per atomic wave).
- Order within W1 (Python dirs first vs npm names first) — planner picks. Recommendation: Python first (more identifiers + bigger blast radius), then npm.
- Whether W2's 3 batches commit separately or amend together — planner picks. Recommendation: 3 separate commits so the RED→GREEN history is auditable per batch.
- The exact Phase 12 README structure — planner drafts; CLAUDE.md `phases/*/README.md` convention applies.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Research input (PRIMARY — read the prior conversation's rename audit)
The user's previous research turn produced a 700-word rename audit. Key numbers:
- ~1044 `from tradewinds` occurrences in `*.py`
- ~30 `import tradewinds` occurrences in `*.py`
- ~77 `from "@tradewinds/...` occurrences in `*.ts`/`*.tsx`
- ~204 `TRADEWINDS_CACHE_DIR` occurrences (heavy in tests via monkeypatch)
- 2 hardcoded `~/.tradewinds/cache` references (README + a test docstring)
- ~85 mentions in `docs/*.md`
- ~20 mentions in `CLAUDE.md`
- ~4858 mentions in `.planning/*.md` (LEAVE ALONE)
- ~5 references in `packages-ts/*/README.md` to `github.com/helloiamvu/tradewinds` (NOT updated — repo URL stays)
- 8 hardcoded GH URLs in `.planning/phases/*/PLAN*.md` (NOT updated — `.planning/` archive)
- 28 npm workspace dep refs (rewritten as part of W1)
- 3 PyPI distribution names + 5 npm package names

### File patterns by wave

**W1 (atomic):**
- `packages/core/pyproject.toml` + `packages/weather/pyproject.toml` + `packages/markets/pyproject.toml`
- `packages-ts/codegen/package.json` + `packages-ts/core/package.json` + `packages-ts/weather/package.json` + `packages-ts/markets/package.json` + `packages-ts/meta/package.json`
- 3 directory renames (Python): `packages/core/src/tradewinds/` → `packages/core/src/mostlyright/`, same for `weather` + `markets`
- `uv.lock` regen
- `pnpm-lock.yaml` regen

**W2 batches:**
- Batch A: `packages/` (all `.py` files under `packages/*/src/` and `packages/*/tests/` if present)
- Batch B: `tests/` (top-level repo tests)
- Batch C: `scripts/` + docs code-fence blocks if any

**W3:**
- All `*.ts` / `*.tsx` files under `packages-ts/` (excluding `dist/` + `node_modules/` + `generated/`)
- Codegen `generated/*.ts` files: re-run `pnpm codegen` (do NOT hand-edit per CROSS-SDK-SYNC §1)

**W4:**
- `packages/core/src/mostlyright/_internal/_cache_dir.py` (new file)
- All sites today reading `os.environ["TRADEWINDS_CACHE_DIR"]` directly — migrate to `resolve_cache_dir()`
- `packages/weather/src/mostlyright/weather/cache.py` (or wherever the cache default path lives today)
- All test fixtures that monkeypatch `TRADEWINDS_CACHE_DIR` → update env var name (or test BOTH for back-compat)
- `packages/core/tests/test_cache_env_back_compat.py` (new file)

**W5:**
- `README.md` (root)
- `docs/*.md` (all)
- `CLAUDE.md` (root)
- Code-fence install commands in any markdown file

**W6:**
- `.github/workflows/release.yml`, `release-ts.yml`, `test.yml`, `test-ts.yml`, `schema-drift.yml`, `release-testpypi.yml`, `drift-rotate-ts.yml`, others
- Filename stays — only env var refs + project name refs change

**W7:**
- `.planning/STATE.md` (closeout section)
- `.planning/phases/12-rename-to-mostlyright/README.md` (new, documenting rename history + operator follow-ups)

### Cross-SDK + review discipline
- `.planning/REVIEW-DISCIPLINE.md` — mixed PR (Python + TS) routes to codex `high` + python-architect + ts-architect parallel dispatch. Max 5 iters per user override. Phase 12 touches `pyproject.toml` dependency floors + CI workflows + schema codegen — **NEVER skip** per the discipline doc.
- `.planning/CROSS-SDK-SYNC.md` §1 schema codegen — re-run `pnpm codegen` after rename to verify schema-drift-clean.
- `CLAUDE.md` § Branch workflow — feature branch from `merged-vision`, codex self-review, merge back. Final big PR `merged-vision` → `main` when ready.

### Wrapped commands

- `git mv` (preserves blame)
- `uv sync` / `uv lock --upgrade-package <name>` / `uv build`
- `pnpm install` / `pnpm -r run typecheck` / `pnpm -r run test` / `pnpm -r run build`
- BSD sed: `sed -i '' 's/from tradewinds/from mostlyright/g'` (macOS)
- GNU sed: `sed -i 's/from tradewinds/from mostlyright/g'` (Linux/CI)
- Recommended: portable Python rewrite script under `scripts/_phase12_rename.py` (use `ast`-aware parsing for safety vs raw text regex)

</canonical_refs>

<specifics>
## Specific Concrete Requirements

From the user brief + ROADMAP.md Phase 12 section, mapped 1:1 to REQUIREMENTS.md RENAME-01..RENAME-10:

| Req | What | Wave |
|---|---|---|
| RENAME-01 | Wave 1 atomic: dir + pyproject + npm rename | W1 |
| RENAME-02 | Wave 2 batched Python import rewrite (~1074 sites, 3 batches, test after each) | W2 |
| RENAME-03 | Wave 3 TS import rewrite (~77 sites + pnpm typecheck/test green) | W3 |
| RENAME-04 | Wave 4 `TRADEWINDS_CACHE_DIR` → `MOSTLYRIGHT_CACHE_DIR` + back-compat shim + 3 unit tests | W4 |
| RENAME-05 | Wave 4 default cache path `~/.tradewinds/cache/v1/` → `~/.mostlyright/cache/v1/` + `docs/cache-migration.md` | W4 |
| RENAME-06 | Wave 5 docs + prose rewrite (docs/, CLAUDE.md, README.md) | W5 |
| RENAME-07 | Wave 6 CI workflow env-var + project-name refs (filenames stay) | W6 |
| RENAME-08 | Wave 7 full test pass (incl. `@pytest.mark.live` parity fixtures) zero-regression | W7 |
| RENAME-09 | Wave 7 operator pre-flight verification (PR description references confirmation) | W7 |
| RENAME-10 | Wave 7 Phase 12 README at `phases/12-rename-to-mostlyright/README.md` | W7 |

### Success Criteria (LOCKED — from ROADMAP)

1. `grep -rn 'tradewinds' packages/ packages-ts/ tests/ scripts/ docs/ --include='*.py' --include='*.ts' --include='*.tsx' --include='*.json' --include='*.toml' --include='*.md' --include='*.yml'` returns ONLY `.planning/` and git-history refs (which are not in the search scope).
2. `uv run pytest -m "not live" -q` passes zero-regression vs pre-Phase-12 baseline (1971 Python tests as of 2026-05-25).
3. `CI=1 pnpm -r run test` passes zero-regression vs pre-Phase-12 baseline (1323 TS tests).
4. Parity gate byte-equivalent under new module name (`from mostlyright import research`).
5. Env var resolution: new wins → no warn; legacy-only → returns + DeprecationWarning; neither → default new path.
6. `python -c "import mostlyright; print(mostlyright.__version__)"` works after `uv sync`.
7. `node -e "console.log(require('@mostlyright/core'))"` works after `pnpm install`.
8. Operator pre-flight steps documented in PR description with confirmation lines.

### Test additions (Phase 12-specific)

- `packages/core/tests/test_cache_env_back_compat.py` (new, 3 tests minimum: canonical-wins, legacy-warns, default-fallback)
- Existing tests that monkeypatch `TRADEWINDS_CACHE_DIR` are updated to use `MOSTLYRIGHT_CACHE_DIR` — OR a small subset is left on the legacy name to keep covering the deprecation path (planner picks; recommendation: leave 1-2 tests on legacy + add new tests on canonical)

</specifics>

<deferred>
## Deferred Ideas (explicitly out of scope per user brief)

- **GitHub repo rename** — `helloiamvu/tradewinds` → `helloiamvu/mostlyright`. Operator may do out-of-band; in-tree URLs stay pointing at the old repo.
- **Old PyPI / npm package cleanup** — orphaned names left as-is; operator handles.
- **`.planning/` archive prose rewrites** — historical audit trail preserved.
- **`v0.3` removal of TRADEWINDS_CACHE_DIR back-compat** — scheduled but not in Phase 12.
- **Brand voice changes** — Phase 12 is mechanical rename only; no marketing/voice updates beyond replacing the literal `tradewinds` string with `mostlyright`.
- **MostlyRightClient class names or API ergonomics** — no signature change anywhere in Phase 12.
- **New features** — pure rename; no new behavior.

</deferred>

---

*Phase: 12-rename-to-mostlyright*
*Context captured: 2026-05-25 via user brief in `/gsd-plan-phase` invocation*

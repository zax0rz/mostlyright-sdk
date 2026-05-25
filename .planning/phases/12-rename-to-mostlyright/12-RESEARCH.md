# Phase 12: Rename `tradewinds` → `mostlyright` — Research

**Researched:** 2026-05-25
**Domain:** Repo-wide mechanical rename across Python + TS dual SDK
**Confidence:** HIGH

## Summary

Phase 12 is a mechanical end-to-end rename of every in-repo identifier from `tradewinds` to `mostlyright`. Scope: 3 PyPI distros, 5 npm packages, 3 Python src dirs, ~1044 Python `from`/`import` rewrites, ~61 TS `from "@tradewinds/"` imports, 75 `TRADEWINDS_CACHE_DIR` env-var refs (with deprecation shim), 75 lines across `.github/workflows/`, 85 doc mentions, 20 in `CLAUDE.md`. Wave structure (9 waves, including 2 operator pre-flight) is locked in `12-CONTEXT.md`.

The investigation surfaced **one non-trivial nuance the audit missed**: the codebase already contains legitimate `mostlyright` literals (lift-source citations, deprecation aliases, the `parser_name="mostlyright_v1"` schema enum). A naive `sed s/tradewinds/mostlyright/g` would leave these untouched (good) but a `sed s/tradewinds/mostlyright/g` plus assertion `grep -rn 'tradewinds' returns 0` will succeed without addressing them. The opposite problem matters more: certain capitalized variants (`TradewindsError`, `TradewindsResult`) ARE in-scope for rename, and a regex restricted to lowercase will miss them.

Numbers update vs CONTEXT.md audit (run 2026-05-25 against worktree HEAD):

| Audit said | Actual (verified) | Delta |
|---|---|---|
| ~1044 `from tradewinds` (`.py`) | **1044** | exact |
| ~30 `import tradewinds` (`.py`) | **30** (with permissive regex `import\s+tradewinds`); 22 with `^[[:space:]]*import tradewinds` | audit used the permissive regex |
| ~77 `from "@tradewinds/` (`.ts`/`.tsx`) | **61** quoted-import lines; 230 lines of `.ts` mention `@tradewinds/` (incl. comments + test descriptions) | overcount by 16 — likely conflated source/comment refs |
| ~204 `TRADEWINDS_CACHE_DIR` | **75** lines total (58 `monkeypatch.setenv` + 4 `os.environ.get` + 13 docstring/test/docs) | audit overcounted — possibly double-counted across files |
| ~85 mentions `docs/*.md` | **85** | exact |
| ~20 in `CLAUDE.md` | **20** | exact |
| ~5 in `packages-ts/*/README.md` (github.com/...) | **5** | exact (stays — repo URL unchanged) |

**Primary recommendation:** Do not use a single bulk `sed` pass. Use a small Python rewriter (`scripts/_phase12_rename.py`) with token-aware substitution rules (Tier 1: imports + module paths; Tier 2: env-var literal; Tier 3: docstring/prose). Tier 1 is the only mechanical pass; Tier 3 (~doc prose) is hand-curated to preserve lift-source citations and `mostlyright_v1` enum literals. The 9 locked waves are correct; this research surfaces the rewriter design + 11 specific edge cases the planner must encode as tasks.

## User Constraints (from CONTEXT.md)

### Locked Decisions

**Wave structure (LOCKED — 9 waves):**

| # | Wave | Atomic edit | Test gate |
|---|------|-------------|-----------|
| W1 | Directory + pyproject + npm scope rename | `git mv packages/*/src/tradewinds packages/*/src/mostlyright`; rewrite each `pyproject.toml` `name` + `[tool.hatch.build.targets.wheel] packages`; rewrite inter-package version pins; rename 5 npm packages + workspace deps | `uv sync` succeeds; `uv build` produces 3 wheels; `pnpm install` succeeds; tests RED until W2 (DOCUMENTED expected RED) |
| W2 | Python import rewrite (3 BATCHES) | scripted rewrite across `packages/`, `tests/`, `scripts/` | `uv run pytest -m "not live"` green after each batch; final `grep -rn 'tradewinds' --include='*.py'` returns 0 |
| W3 | TS import rewrite | scripted `from "@tradewinds/...` → `from "@mostlyright/...` | `pnpm -r run typecheck` green; `CI=1 pnpm -r run test` green |
| W4 | Cache env var + back-compat shim | rename `TRADEWINDS_CACHE_DIR` → `MOSTLYRIGHT_CACHE_DIR` (75 sites); new `_cache_dir.py` reads both env vars with `DeprecationWarning`; default path `~/.tradewinds/cache/v1/` → `~/.mostlyright/cache/v1/` | 3 new tests in `test_cache_env_back_compat.py` pass; full suite green |
| W5 | Docs + prose rewrite | rewrite ~85 mentions `docs/*.md`, ~20 `CLAUDE.md`, root `README.md`; install commands; code-fence examples; **LEAVE `.planning/` ARCHIVE ALONE** | `grep -rn 'tradewinds' docs/ CLAUDE.md README.md` returns 0 (excluding URL fields) |
| W6 | CI workflow updates | keep `release.yml` + `release-ts.yml` filenames; update env-var names + hardcoded `tradewinds*` refs in YAML; verify trusted-publisher project names | `act` dry-run OR manual YAML review; in-repo CI for `test.yml`/`test-ts.yml` green |
| W7 | Parity-gate pre-flight + full test + STATE.md + Phase 12 README | `uv run pytest -q` (INCLUDING `@pytest.mark.live`); `CI=1 pnpm -r run test`; write phase README; update `.planning/STATE.md` | Parity test (`tests/test_parity.py`) byte-equivalent under new name; full suites green |

**Operator pre-flight (BEFORE Wave 1):**
- OP1: `mv ~/Documents/GitHub/mostlyright ~/Documents/GitHub/mostlyright-legacy` — manual
- OP2: Register 3 PyPI pending publishers (`mostlyright`, `mostlyright-weather`, `mostlyright-markets`) — pypi.org manual
- OP3: Claim `@mostlyright` npm scope — npmjs.com manual
- OP4: Register 4 npm OIDC pending publishers (`@mostlyright/core`, `/weather`, `/markets`, unscoped meta `mostlyright`) — manual

**Rename safety rules (LOCKED):**
1. `git mv` only (no `git rm` + `git add` — blame must follow file).
2. No bulk find-replace across entire repo at once. Wave by wave; test after each.
3. `uv lock` regenerated in W1.
4. `pnpm-lock.yaml` regenerated in W1.
5. Pre-commit + pre-push hooks stay installed; no `--no-verify`.
6. No `[review-skip: trivial]` shortcut (never-skip path per REVIEW-DISCIPLINE).
7. `.planning/` archive prose left intact (4858 mentions in 124 files — historical audit trail).
8. Parity-locked modules stay byte-equivalent under the new module name. The parity test reads `from mostlyright import research` and the 5 fixture files stay binary-identical.

**Cache back-compat semantics (LOCKED — one-release window):**
- `packages/core/src/mostlyright/_internal/_cache_dir.py` (new file) ships `resolve_cache_dir()`.
- Order: `MOSTLYRIGHT_CACHE_DIR` (canonical) → `TRADEWINDS_CACHE_DIR` (legacy + `DeprecationWarning`) → default `~/.mostlyright/cache/v1/`.
- Removed in v0.3.
- 3-test suite mandatory: canonical-wins, legacy-warns, default-fallback.

**Test-pass gate semantics (LOCKED):**
- "Tests green" = `uv run pytest -m "not live" -q` exits 0.
- "Parity green" = `uv run pytest tests/test_parity.py -q` exits 0 (live fixtures).
- "TS tests green" = `CI=1 pnpm -r run test` exits 0.
- "Typecheck green" = `pnpm -r run typecheck` exits 0.
- W2's 3-batch gate is the load-bearing safety: Batch A RED → Batch B BLOCKED.

### Claude's Discretion

- Exact sed/perl/ts-morph script for import rewrite — planner picks (recommendation in §Architecture below).
- Grep regex for "zero remaining tradewinds references" assertion — planner picks (must exclude `.planning/`, `node_modules/`, `dist/`, `.git/`, plus the legacy-deprecation-alias allow-list documented below).
- 5 npm renames as 5 commits or 1 commit — planner picks (recommendation: 1 commit per atomic wave).
- Order within W1 (Python dirs first vs npm names first) — planner picks. Recommendation: **Python first** (bigger blast radius + the dir rename gives `from mostlyright import ...` something to land on in W2).
- W2's 3 batches commit separately or amend — planner picks. Recommendation: **3 separate commits** so RED→GREEN history is auditable per batch.
- Exact Phase 12 README structure — planner drafts.

### Deferred Ideas (OUT OF SCOPE)

- **GitHub repo rename** `helloiamvu/tradewinds` → `helloiamvu/mostlyright`. In-tree URLs stay pointing at the old repo for Phase 12.
- **Old PyPI / npm package cleanup** — orphaned `tradewinds*` / `@tradewinds/*` stay; operator handles out-of-band.
- **`.planning/` archive prose rewrites** — 4858 mentions in 124 files preserved as audit trail.
- **v0.3 removal of `TRADEWINDS_CACHE_DIR` back-compat** — scheduled but not in Phase 12.
- **Brand voice changes** — pure mechanical rename only.
- **`MostlyRightClient` / `MostlyRightMCPError` class-name churn** — these are EXISTING deprecation aliases from the `mostly-light` migration; NOT part of the rename.
- **`mostlyright_v1` parser_name enum literal** — load-bearing LINEAGE-01 schema value referring to legacy lineage; STAYS.
- **`mostlyright==0.14.1` parity citations** — historical fact; STAYS.
- **`monorepo-v0.14.1/src/mostlyright/...` lift-source paths** — provenance citations; STAYS.

## Phase Requirements

| ID | Description | Wave | Research Support |
|----|-------------|------|------------------|
| RENAME-01 | W1 atomic: dir + pyproject + npm rename | W1 | §Architecture W1 task + §hatchling wheel verification |
| RENAME-02 | W2 batched Python import rewrite (~1074 sites, 3 batches, test after each) | W2 | §Python rewriter design + §11 edge cases (esp. preserve `mostlyright_v1`, `MostlyRight*`, lift citations) |
| RENAME-03 | W3 TS import rewrite (~77 sites + pnpm typecheck/test green) | W3 | §TS rewriter design + verified count 61 quoted imports |
| RENAME-04 | W4 `TRADEWINDS_CACHE_DIR` → `MOSTLYRIGHT_CACHE_DIR` + back-compat shim + 3 unit tests | W4 | §4 read sites identified + §58 monkeypatch sites enumerated |
| RENAME-05 | W4 default cache path rename + `docs/cache-migration.md` | W4 | §`~/.tradewinds` hardcoded sites (5 source files + 4 docs) |
| RENAME-06 | W5 docs + prose rewrite | W5 | §preserve-list for `mostlyright`/`MostlyRight`/`monorepo-v0.14.1` literals |
| RENAME-07 | W6 CI workflow env-var + project-name refs | W6 | §10 workflow files audited + exact YAML edits documented |
| RENAME-08 | W7 full test pass (incl. `@pytest.mark.live` parity) | W7 | §1971 Python + 1323 TS test baseline |
| RENAME-09 | W7 operator pre-flight verification | W7 | §operator pre-flight OP1-OP4 enumerated |
| RENAME-10 | W7 Phase 12 README | W7 | §STATE.md format reviewed (matches recent Phase 10 closeout) |

## Project Constraints (from CLAUDE.md)

- **Branch workflow:** `main` only receives PRs from `merged-vision`. Feature branches off `merged-vision`, Codex self-review, merge back. One big PR `merged-vision → main` when integration ready.
- **TDD mandatory.** RED → GREEN → REFACTOR.
- **Pre-commit + pre-push hooks mandatory.** No `--no-verify`. Pre-commit runs ruff + format + whitespace + YAML/TOML validation. Pre-push runs `pytest -m "not live"`.
- **All API calls direct from SDK.** No hosted-API client calls anywhere in `tradewinds.*` / `mostlyright.*` (verified via grep on built wheels before publish).
- **Dual-SDK Planning Rule:** Every public API change needs a TS Parity section. Phase 12 IS dual-SDK (Python + TS paired in same plan); planner must include a TS Parity section per CLAUDE.md.
- **Source priority + climate dedup:** `_dedup_climate_rows` STRICT `>` — load-bearing parity behavior; this rename must preserve byte-equivalent output.
- **Parity test (`tests/test_parity.py`) is the HARD GATE.** W7 re-runs it; if it fails, Phase 12 does not ship.
- **Cache path:** `$HOME/.tradewinds/cache/observations/...` — Phase 12 changes the parent prefix to `$HOME/.mostlyright/cache/v1/...` but the `v1/observations/{station}/{year}/{month}.parquet` shape stays identical.

## Standard Stack

### Core (versions already pinned in workspace; no change in Phase 12)
| Tech | Pinned | Purpose | Why Standard |
|------|--------|---------|--------------|
| Python | `>=3.11` | language | locked in PROJECT.md; required by pandas 3.0-readiness |
| uv | 0.11.3 | workspace + lockfile | already used; `uv sync --all-packages` consumes lockfile |
| hatchling | latest | wheel build backend | already chosen; supports PEP 420 namespace packages |
| pnpm | 9.12.0 (CI), 10 in release-ts.yml | TS workspace + publish | already chosen |
| pandas | `>=2.2,<4.0` | data layer | unchanged |
| pyarrow | `>=17.0,<24.0` | parquet | unchanged |
| filelock | `>=3.20,<4` | trades cache | unchanged |

**Verification (run 2026-05-25):** `uv 0.11.3 (45da18ac3 2026-04-01)`, `pnpm-lock.yaml v9.0`. [VERIFIED: `uv --version` / `head -3 pnpm-lock.yaml`]

### Supporting / Phase 12 specific (NEW dev-only tooling for the rewriter)

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| Python `ast` (stdlib) | n/a | parse imports for token-aware rewrite | use this for W2 — no third-party dep needed |
| Python `tokenize` (stdlib) | n/a | preserve comment/whitespace formatting | use IF `ast` rewrite is too destructive |
| Python `pathlib` (stdlib) | n/a | safe path-rewrite walker | use this for the rewriter driver |

**Do NOT add ts-morph or libcst as a runtime/dev dep for Phase 12.** Justification below in §TS rewriter design. [ASSUMED based on tradewinds policy of minimizing dev-dep surface]

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Custom Python rewriter | `bowler` / `libcst` | Heavier dep; bowler unmaintained as of 2024. The repo's needs are simple enough that stdlib `ast`-driven rewrite suffices. [VERIFIED: Bowler GitHub last release 2023; PyPI shows 0.9.0 as latest] |
| Custom TS rewriter | `ts-morph` / `jscodeshift` | The only TS substitution we need (`from "@tradewinds/` → `from "@mostlyright/`) is uniquely identified by the leading `from "` quote token; safe with grep+sed. ts-morph adds ~5MB to devDependencies. |
| BSD sed (macOS) | GNU sed (CI) | `sed -i ''` vs `sed -i ''` syntax differs; planner MUST use a Python wrapper or the rewrite is unportable. CI is Linux-only but developers run macOS. |

**Installation (Phase 12 introduces NO new install steps):** No new packages needed; everything is stdlib.

## Architecture Patterns

### Recommended Project Structure (post-rename)

```
packages/
├── core/
│   ├── pyproject.toml         # name = "mostlyright"
│   └── src/
│       └── mostlyright/        # was tradewinds/
│           ├── __init__.py     # __path__ = pkgutil.extend_path(...)
│           ├── research.py
│           ├── _internal/
│           │   └── _cache_dir.py  # NEW W4 — resolve_cache_dir()
│           └── ...
├── weather/
│   ├── pyproject.toml         # name = "mostlyright-weather"
│   └── src/
│       └── mostlyright/        # PEP 420 namespace (no __init__.py here)
│           └── weather/
│               ├── __init__.py
│               ├── cache.py    # DEFAULT_ROOT = ~/.mostlyright/cache
│               └── ...
└── markets/
    └── (same pattern: src/mostlyright/markets/...)

packages-ts/
├── core/        package.json name = "@mostlyright/core"
├── weather/     package.json name = "@mostlyright/weather"
├── markets/     package.json name = "@mostlyright/markets"
├── meta/        package.json name = "mostlyright"
└── codegen/     package.json name = "@mostlyright/codegen"
```

### Pattern 1: Python Rewriter Design (W2 — load-bearing for the 3-batch gate)

**What:** A single Python script (`scripts/_phase12_rename.py`) that walks a list of files, parses each as Python source via `ast`, and rewrites import statements in-place.

**When to use:** Wave 2, Batches A/B/C (packages/, tests/, scripts/).

**Why `ast` and not `sed`:**
1. Token-aware: a comment containing `"# from tradewinds import"` won't be rewritten by sed-without-care. ast leaves comments untouched by default.
2. Cross-platform: stdlib only; works identically on macOS BSD sed vs Linux GNU sed.
3. Reversible: failure mode is "ast raises SyntaxError on a malformed file" — the file isn't touched. sed would write partial output.
4. The 11 edge cases below (preserve `mostlyright_v1`, `MostlyRight*`, lift citations) are MUCH easier to encode as ast-walker conditionals than as regex negative-lookaheads.

**Recommended rewriter shape (use ast.NodeTransformer):**

```python
# scripts/_phase12_rename.py
# Source: stdlib ast.NodeTransformer pattern — https://docs.python.org/3/library/ast.html
import ast
from pathlib import Path

class TradewindsToMostlyrightTransformer(ast.NodeTransformer):
    def visit_ImportFrom(self, node: ast.ImportFrom) -> ast.AST:
        if node.module and node.module.startswith("tradewinds"):
            node.module = node.module.replace("tradewinds", "mostlyright", 1)
        return node

    def visit_Import(self, node: ast.Import) -> ast.AST:
        for alias in node.names:
            if alias.name == "tradewinds" or alias.name.startswith("tradewinds."):
                alias.name = alias.name.replace("tradewinds", "mostlyright", 1)
        return node
```

But `ast.unparse()` does NOT preserve comments or formatting. The simplest cross-platform approach that DOES preserve formatting is line-based regex rewrite restricted to import-statement lines:

```python
# Restricted to lines matching ^(from|import)\s+tradewinds.
# Preserves comments and other lines verbatim.
IMPORT_FROM_RE = re.compile(r"^(\s*from\s+)tradewinds(\.|\s)")
IMPORT_BARE_RE = re.compile(r"^(\s*import\s+)tradewinds(\.|\s|$)")

def rewrite_line(line: str) -> str:
    line = IMPORT_FROM_RE.sub(r"\1mostlyright\2", line, count=1)
    line = IMPORT_BARE_RE.sub(r"\1mostlyright\2", line, count=1)
    return line
```

**Recommendation: use the line-based regex rewriter restricted to lines matching `^(from|import)\s+tradewinds`** — preserves comments + docstrings + lift citations untouched by construction. ast-walker overkill for this scope. [VERIFIED via test: `git mv packages/core/src/tradewinds packages/core/src/mostlyright` round-trips cleanly]

### Pattern 2: TS Rewriter Design (W3)

**What:** `sed` (via Python wrapper for portability) replacing `from "@tradewinds/` → `from "@mostlyright/`.

**When:** Wave 3.

**Why sed is safe here:** The pattern `from "@tradewinds/` is uniquely identified by the literal leading `from "` token and the `@`-scoped npm path. False positives are not possible inside string literals or comments because no in-repo string or comment uses that exact prefix outside imports (verified via grep).

**Recommended:**

```python
# scripts/_phase12_rename_ts.py
# Same Python driver as above, restricted to:
#   from\s+"@tradewinds/  → from "@mostlyright/
import re
TS_IMPORT_RE = re.compile(r'from\s+"@tradewinds/')

def rewrite_ts_line(line: str) -> str:
    return TS_IMPORT_RE.sub('from "@mostlyright/', line)
```

**Also rename in `package.json` files:** `"name": "@tradewinds/X"` → `"name": "@mostlyright/X"` and workspace deps `"@tradewinds/X": "workspace:*"` → `"@mostlyright/X": "workspace:*"`. These are W1, not W3.

### Pattern 3: Cache back-compat shim (W4 — already specified in CONTEXT.md)

**What:** New `_internal/_cache_dir.py` with `resolve_cache_dir()` reading `MOSTLYRIGHT_CACHE_DIR` first, falling back to `TRADEWINDS_CACHE_DIR` with `DeprecationWarning`.

**Sites to migrate (the 4 direct readers identified):**
1. `packages/core/src/{mostlyright}/discovery.py:122` — `os.environ.get("TRADEWINDS_CACHE_DIR")`
2. `packages/weather/tests/test_cache.py:613` — `os.environ["TRADEWINDS_CACHE_DIR"] = cache_dir` (test-only)
3. `packages/markets/src/{mostlyright}/markets/_trades_cache.py:71` — `os.environ.get("TRADEWINDS_CACHE_DIR")`
4. `packages/weather/src/{mostlyright}/weather/cache.py:141` — `os.environ.get("TRADEWINDS_CACHE_DIR")`

The 58 `monkeypatch.setenv("TRADEWINDS_CACHE_DIR", ...)` test sites do NOT need migration to `MOSTLYRIGHT_CACHE_DIR` — they exercise the legacy code path the shim must preserve. **Recommendation: keep 5-8 monkeypatch sites on the legacy var for deprecation-path coverage; rewrite the remaining ~50 to `MOSTLYRIGHT_CACHE_DIR` for forward-looking signal.** This matches CONTEXT.md guidance ("planner picks; recommendation: leave 1-2 tests on legacy + add new tests on canonical").

### Anti-Patterns to Avoid

- **`sed -i 's/tradewinds/mostlyright/g' **/*.py`** — DOES catastrophic damage. Will rename `mostlyright_v1` → `mostlyright_v1` (no-op, good) BUT will rename `monorepo-v0.14.1/src/mostlyright` references (in comments) to `monorepo-v0.14.1/src/mostlyright/mostlyright/` (broken). It will also rename `tradewinds.dev` → `mostlyright.dev` (intentional but breaks the test_export_schemas.py assertion that asserts `$id.startswith("https://tradewinds.dev/schemas/")` without coordinated test update). **Use the import-line-restricted regex.**
- **Renaming `TradewindsError` → `MostlyrightError` by string replace** — needs to be class-rename, not text-replace. The class name appears in error messages, docstrings, and exported symbol lists. Recommend: do this as a focused commit within W2 Batch A, separate from the bulk import rewrite, so codex review can audit the rename surface.
- **Skipping `uv.lock` regen** — the lockfile pins the workspace member names; mismatched names will cause `uv sync` to fail. Run `rm uv.lock && uv lock` as the explicit W1 step (NOT `uv lock --upgrade-package tradewinds` — that won't migrate the project name).
- **Skipping `pnpm-lock.yaml` regen** — same story for TS. Run `pnpm install` after package.json edits; pnpm resolves `workspace:*` paths from package names.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| AST-aware Python rewrite | libcst / bowler | stdlib `re` restricted to import-statement-prefix patterns | Scope is narrow; the 4 preserve-list edge cases are simpler as explicit allow-list than as ast-walker conditionals |
| TS import rewrite | ts-morph / jscodeshift | restricted `sed`-equivalent regex | Single pattern, unique prefix, ~5MB dep avoided |
| Lockfile regen | hand-edit uv.lock or pnpm-lock.yaml | `rm uv.lock && uv lock` / `pnpm install` | Hand-editing lockfiles is the #1 way to silently corrupt a release |
| Validating zero `tradewinds` remain | hand-curated grep | explicit allow-list of preserved literals + bash one-liner | The grep MUST allow `mostlyright_v1`, `MostlyRight*`, `monorepo-v0.14.1`, `mostlyright==0.14.1`, `.planning/`, `node_modules/`, `dist/`, `.git/` |

**Key insight:** Phase 12's hardest problem is not "doing the rename" — it's "asserting the rename is done correctly without false-positive failures on legitimately preserved literals." The audit query `grep -rn 'tradewinds' returns 0` is too coarse. Use:

```bash
# Recommended W7 verification:
grep -rn 'tradewinds' packages/ packages-ts/ tests/ scripts/ docs/ README.md CLAUDE.md \
  --include='*.py' --include='*.ts' --include='*.tsx' --include='*.json' --include='*.toml' \
  --include='*.md' --include='*.yml' \
  | grep -v 'mostlyright_v1\|MostlyRight\|monorepo-v0.14.1\|mostlyright==0.14.1\|tradewinds-legacy'
# Expected: 0 lines
```

## Runtime State Inventory

This is a rename phase; the inventory applies.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| **Stored data** | `~/.tradewinds/cache/v1/` parquet cache on developer machines + CI ephemeral runners (none in git). User-side migration: `mv ~/.tradewinds ~/.mostlyright` (documented in new `docs/cache-migration.md`). | DOCUMENT in `docs/cache-migration.md`; the shim ALSO recognizes legacy `TRADEWINDS_CACHE_DIR` env var for one release. No code-driven on-disk migration (CONTEXT explicit decision). |
| **Live service config** | None — tradewinds has no hosted backend per PROJECT.md. No Datadog/n8n/Tailscale/Cloudflare-Tunnel config to update. | None |
| **OS-registered state** | None — no pm2 saved processes, no systemd units, no Windows Task Scheduler entries. The pre-commit + pre-push git hooks ARE registered per-checkout via `pre-commit install`; they reference `.pre-commit-config.yaml` which is in-repo (no name-baked references). | None for in-tree; operator pre-flight OP1 renames `~/Documents/GitHub/mostlyright` → `mostlyright-legacy` to clear the import-path collision. |
| **Secrets and env vars** | `TRADEWINDS_CACHE_DIR` (sole env var owned by this codebase). `TW_HOSTED_URL` (Phase 7 hosted-strategy seam env var) — **PRESERVED** (no rename; that env is the Phase 7-style feature gate, not a rebrand vector). `TRADEWINDS_TS_LIVE` (TS drift workflow flag) — needs rename to `MOSTLYRIGHT_TS_LIVE` in `drift-rotate-ts.yml`. PyPI / npm trusted-publisher OIDC config is the operator pre-flight (OP2/OP3/OP4), NOT a code edit. | Code rename: `TRADEWINDS_CACHE_DIR` → `MOSTLYRIGHT_CACHE_DIR` (shim handles both). `TRADEWINDS_TS_LIVE` → `MOSTLYRIGHT_TS_LIVE` in W6. `TW_HOSTED_URL` UNCHANGED (rename is `tradewinds` → `mostlyright`, not `tw` → `mr`; the `TW_` prefix is intentionally cryptic per Phase 7). |
| **Build artifacts / installed packages** | `dist/`, `*.egg-info/`, `node_modules/`, `packages-ts/*/dist/`, `__pycache__/` are all in `.gitignore` and regenerated. The `pnpm-lock.yaml` + `uv.lock` ARE in git and must regenerate via `pnpm install` / `rm uv.lock && uv lock`. Old PyPI wheels under names `tradewinds*` and old npm packages under `@tradewinds/*` stay published indefinitely (CONTEXT — operator follow-up; out of phase scope). Editable installs in active developer venvs need a fresh `uv sync` after W1. | Regenerate `uv.lock` + `pnpm-lock.yaml` in W1. Operator: `uv sync --all-packages` in fresh venv post-merge to refresh editable installs. Old wheels: out-of-scope. |

**The canonical question — "After every file in the repo is updated, what runtime systems still have the old string cached, stored, or registered?"** Answer:

1. Existing user caches at `~/.tradewinds/cache/v1/` — handled by W4 shim + `docs/cache-migration.md`.
2. Old PyPI/npm wheels published under `tradewinds*` — out of scope (operator handles via PyPI transfer or deletion).
3. Developer venvs with editable `tradewinds` installs — re-run `uv sync --all-packages` after W1 merge (documented in Phase 12 README).
4. CI runners — ephemeral; next run picks up the new lockfile.
5. `git log --follow` history for moved files — preserved by `git mv` discipline (verified §Architecture W1).

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `uv` CLI | W1 lockfile regen + wheel build verification | ✓ | 0.11.3 | — |
| `pnpm` CLI | W1 lockfile regen + W3 typecheck/test | ✓ | (9.x via packageManager pin) | — |
| `git` | W1 `git mv` directory rename | ✓ | (system) | — |
| `python` (3.11+) | W2 rewriter script | ✓ | 3.11+ in venv | — |
| Node 20+ | W3 typecheck | ✓ | (system) | — |
| `act` (local GH Actions runner) | W6 dry-run | ? | optional | Manual YAML review (W6 acceptable) |
| `grep` (BSD or GNU) | Verification gates throughout | ✓ | (system) | — |

**Missing dependencies with no fallback:** None — Phase 12 uses only stdlib + existing tooling.

**Missing dependencies with fallback:** `act` (planner can use manual YAML review for W6 if `act` not installed; CI itself acts as the final gate on workflow correctness).

## Common Pitfalls

### Pitfall 1: Schema `$id` URL not in the audit
**What goes wrong:** All canonical schema JSON files emit `"$id": "https://tradewinds.dev/schemas/<name>.json"`. The exporter literal lives at `scripts/export_schemas.py:205`. The test at `tests/test_export_schemas.py:168` asserts `$id.startswith("https://tradewinds.dev/schemas/")`. The TS validators at `packages-ts/core/src/schemas/validators/*.js` embed the `$id` as a literal string AND a `sourceURL` directive. Skipping this rewrite breaks the assertion AND leaves a `tradewinds.dev` literal in committed code AND will trigger schema-drift.yml on the regenerated schema files.

**Why it happens:** `tradewinds.dev` doesn't match the import-statement regex pattern; only a docs-pass would catch it. The audit cited "85 docs mentions" but `scripts/export_schemas.py` is a script, not docs.

**How to avoid:** W2 Batch C (scripts/) rewrites `scripts/export_schemas.py`. W7 re-runs `python scripts/export_schemas.py && pnpm codegen` and commits the regenerated `schemas/` + `packages-ts/*/src/**/generated/` outputs. Update the test assertion in lockstep. **Decision needed:** `mostlyright.dev`, `tradewinds.dev` (preserve as placeholder), or drop the URL entirely. [ASSUMED — defer to planner discretion; recommendation `mostlyright.dev` to match the rename]

**Warning signs:** schema-drift.yml fails in CI; `test_export_schemas.py::test_each_schema_payload_self_describes` fails.

### Pitfall 2: Preserve list ("legitimate `mostlyright` literals")
**What goes wrong:** A naive verification grep `grep -rn 'tradewinds'` returns 0 — but ANOTHER naive grep `grep -rn 'mostlyright'` returns 1000+ AND includes legitimate existing literals that PREDATE Phase 12:
- `mostlyright_v1` parser_name schema enum (`packages/core/src/{mostlyright}/core/schemas/observation_ledger.py:27` + JSON spec) — LINEAGE-01 load-bearing
- `mostlyright==0.14.1` parity citations in docstrings + tests
- `monorepo-v0.14.1/src/mostlyright/...` lift-source paths
- `MostlyRightClient` / `MostlyRightMCPError` deprecation aliases (intentional for mostly-light migration)
- `"MostlyRight stores as float cents [0, 100]"` etc. in candle.json `$comment`
- `MostlyRight code` in `forecast.json` description

**Why it happens:** tradewinds was LIFTED from mostlyright v0.14.1; existing prose intentionally cites the legacy SDK by name as part of provenance documentation. Renaming tradewinds → mostlyright re-uses the same word but with a different meaning.

**How to avoid:** Build the W2 rewriter with an allow-list (preserve list). Restrict the rename to import statements and module references (`tradewinds.` paths) by construction — comments/docstrings/literal strings are NOT touched. The W7 verification grep uses `grep -v 'mostlyright_v1\|MostlyRight\|monorepo-v0.14.1\|mostlyright==0.14.1\|tradewinds-legacy'` to exclude legitimate `mostlyright`-prefixed matches.

**Warning signs:** Codex review iter-1 flags "rename-broke-LINEAGE-01" — parser_name enum no longer matches schema validator.

### Pitfall 3: PEP 420 namespace package — sibling distros must NOT ship `__init__.py` at namespace root
**What goes wrong:** Only `packages/core/src/{mostlyright}/__init__.py` exists. `packages/weather/src/{mostlyright}/` and `packages/markets/src/{mostlyright}/` MUST NOT have an `__init__.py` at the renamed namespace root (only at `weather/__init__.py` and `markets/__init__.py` one level down). If `git mv` accidentally creates one (or the IDE auto-generates one), `uv build --all-packages` will fail PKG-04 (`tests/test_wheel_layout.py`) — two wheels can't both ship `__init__.py` at namespace root.

**Why it happens:** PEP 420 implicit namespace packages have no marker file at the root; IDEs and code-formatters sometimes add empty `__init__.py` because "every Python directory needs one."

**How to avoid:** W1 post-rename verification: `find packages/weather/src/mostlyright packages/markets/src/mostlyright -name '__init__.py'` returns ONLY `weather/__init__.py` and `markets/__init__.py` (not at namespace root). Run `uv build --all-packages` + unzip wheels + assert no two wheels ship namespace-root `__init__.py`.

**Warning signs:** `uv build` produces 4 wheels instead of 3 (workspace root would silently publish); or `test_wheel_layout.py` fails.

### Pitfall 4: hatchling wheel target ([tool.hatch.build.targets.wheel] packages)
**What goes wrong:** Each `packages/*/pyproject.toml` carries `[tool.hatch.build.targets.wheel] packages = ["src/tradewinds"]`. This MUST be updated to `["src/mostlyright"]` in W1; otherwise hatchling will fail to find the package and `uv build` will produce an empty wheel.

**Why it happens:** Easy to miss in the pyproject.toml diff; the build error surfaces only at wheel-build time, after the import rewrites in W2.

**How to avoid:** Explicit W1 task — for each of the 3 pyproject.toml files: (1) `[project] name`, (2) `[tool.hatch.build.targets.wheel] packages`, (3) inter-package version pin (`"tradewinds>=0.1.0rc1,<0.2"` → `"mostlyright>=0.1.0rc1,<0.2"`), (4) [tool.uv.sources] keys. Verification: `uv build --all-packages` succeeds + 3 wheels emitted.

**Warning signs:** `uv build` emits empty wheels (no .py files inside); `uv sync` succeeds but `python -c "import mostlyright"` fails with ModuleNotFoundError.

### Pitfall 5: Inter-package version pins drift across pyproject.toml files
**What goes wrong:** `tradewinds-weather` and `tradewinds-markets` both declare `"tradewinds>=0.1.0rc1,<0.2"` as a runtime dep. The METADATA check (`scripts/check_wheel_metadata.py` + `wheel-metadata-check.yml`) verifies this pin exists. If only `[project] name` is updated but `dependencies = [...]` block still says `"tradewinds>=...,<..."`, the wheel will publish with a stale pin, and `pip install mostlyright-weather` will pull the OLD `tradewinds` distro from PyPI as a transitive dep.

**Why it happens:** Multiple toml fields reference the package name; one is easy to miss.

**How to avoid:** Run `grep -n 'tradewinds' packages/*/pyproject.toml` after the W1 edits — should return 0 lines (except in comments — which the planner can decide to clean up).

**Warning signs:** wheel-metadata-check.yml fails post-W1 with "missing Requires-Dist pin for mostlyright"; OR a downstream user reports `pip install mostlyright-weather` pulled both `mostlyright` AND `tradewinds`.

### Pitfall 6: `git mv` directory rename + file mode preservation
**What goes wrong:** A multi-step rename (`git rm packages/core/src/tradewinds && mkdir packages/core/src/mostlyright && cp -r ... && git add ...`) breaks `git log --follow` for every file inside. Future developers cannot trace `_internal/_pairs.py`'s parity-lift history.

**Why it happens:** Easy to do this accidentally if someone resolves a "directory rename merge conflict" by deleting + re-adding instead of accepting both sides.

**How to avoid:** Use ONLY `git mv` for the W1 directory rename. Verification: after W7 merge, `git log --follow packages/core/src/mostlyright/_internal/_pairs.py` shows the full pre-rename history including the Wave-2 v0.14.1 parity lift commit. [VERIFIED: `git mv packages/core/src/tradewinds packages/core/src/mostlyright` round-trips cleanly via test in this research session]

**Warning signs:** `git log --follow` shows only post-Phase-12 commits; codex review flags "blame discontinuity."

### Pitfall 7: pre-commit hooks fire false-positive on the rename diff
**What goes wrong:** `.pre-commit-config.yaml` runs ruff-fix, ruff-format, trailing-whitespace, end-of-file-fixer, check-yaml, check-toml, check-added-large-files, pytest-fast (pre-push). None of these have a built-in "package name must match directory name" check, but ruff's `I` (isort) rule WILL reorder imports if the W2 rewrite leaves them out of alphabetical order. **Recommendation:** run `ruff check --fix` as the LAST step of each W2 batch so the formatter normalizes the rewritten imports.

**Why it happens:** The Phase 12 rewriter changes import-line tokens; ruff-isort may reorder them within `from X import a, b, c` groups.

**How to avoid:** Bake `ruff check --fix && ruff format` into each W2 batch's commit script. Pre-commit will then no-op.

**Warning signs:** Pre-commit hook fails on commit with "ruff would reformat"; planner re-runs ruff and amends.

### Pitfall 8: Schema codegen idempotency under rename
**What goes wrong:** `scripts/export_schemas.py` reads `tradewinds.*` symbols via dynamic import (`from tradewinds.core.schemas import ...`). Post-W2, those imports rewrite to `from mostlyright.core.schemas import ...`. The exporter's OUTPUT (under `schemas/json/*.json`) is determined by Python source structures — which are byte-identical post-rename (only import paths changed). Therefore `schemas/json/*.json` should be byte-identical after the rename UNLESS the exporter literal `tradewinds.dev` is updated.

**Why it happens:** If the literal updates but the codegen output doesn't refresh, schema-drift.yml fails on the next push.

**How to avoid:** W7 task — `uv run python scripts/export_schemas.py && pnpm codegen && git diff schemas/ packages-ts/*/src/**/generated/`. Commit any diffs. (CONTEXT.md mentions this in W6; recommend moving to W7 since W6 is workflow YAML edits.)

**Warning signs:** schema-drift.yml fails on PR; post-rename codegen produces a diff in `packages-ts/*/src/**/generated/*.ts` (the AUTO-GENERATED headers say `@tradewinds/codegen` and refresh to `@mostlyright/codegen`).

### Pitfall 9: ~/Documents/GitHub/mostlyright path collision (operator pre-flight)
**What goes wrong:** The user has a legacy `~/Documents/GitHub/mostlyright` directory (the source repo lifted from). After Phase 12, `mostlyright` becomes a Python package name. If a developer runs `cd ~/Documents/GitHub/mostlyright && python -c "import mostlyright"` they'll get THAT directory in `sys.path[0]` and the import shadows the renamed tradewinds-now-mostlyright package. Operator MUST rename to `mostlyright-legacy` before any wave runs.

**Why it happens:** Python's automatic `sys.path[0] = current working dir` injects the CWD ahead of site-packages.

**How to avoid:** Operator pre-flight OP1. Phase 12 README documents that this rename happened.

**Warning signs:** Developer reports "`import mostlyright` is finding the wrong package"; `python -c "import mostlyright; print(mostlyright.__file__)"` shows the legacy path, not the new tradewinds-now-mostlyright path.

### Pitfall 10: CI workflow filenames vs. trusted-publisher OIDC binding
**What goes wrong:** PyPI/npm OIDC trusted publishers bind to {repo, workflow filename, environment}. The filenames `release.yml` and `release-ts.yml` STAY (per CONTEXT decision). But the trusted-publisher REGISTRATION on PyPI/npm references the project name (`tradewinds` vs `mostlyright`). Operator must register NEW pending publishers for `mostlyright`, `mostlyright-weather`, `mostlyright-markets` (PyPI) + `@mostlyright/core`, `@mostlyright/weather`, `@mostlyright/markets`, `mostlyright` meta (npm). Old `tradewinds*` publishers stay orphaned.

**Why it happens:** Trusted publishing is registered out-of-band on pypi.org/npmjs.com, not in the repo.

**How to avoid:** Operator pre-flight OP2 + OP3 + OP4 (CONTEXT.md). Phase 12 README documents the pending-publisher registrations and the operator confirmation lines required in the PR description.

**Warning signs:** Post-merge `release.yml` run fails with "trusted publisher not found for mostlyright" — the operator forgot OP2.

### Pitfall 11: Stale developer venv after W1
**What goes wrong:** Developers with active `uv sync` editable installs have `tradewinds*` registered in their venv's `site-packages/`. After W1, the lockfile updates, but the venv still has the OLD package names registered. A `uv run pytest` call after W1 may pick up phantom `tradewinds` imports from the stale venv even though source is now `mostlyright`.

**Why it happens:** Editable installs persist in the venv until explicitly removed.

**How to avoid:** Phase 12 README documents the post-merge developer step: `rm -rf .venv && uv sync --all-packages`. Recommend also running `uv pip list | grep -i 'tradewinds\|mostlyright'` post-sync to verify only `mostlyright*` is present.

**Warning signs:** "ImportError: cannot import 'research' from 'mostlyright'" despite source being correct; check for ghost `tradewinds*.egg-info/` or `tradewinds*.dist-info/` in the venv.

## Code Examples

### W1: Atomic directory + pyproject rename (Python)

```bash
# 1. git mv the 3 source directories (preserves blame)
git mv packages/core/src/tradewinds packages/core/src/mostlyright
git mv packages/weather/src/tradewinds packages/weather/src/mostlyright
git mv packages/markets/src/tradewinds packages/markets/src/mostlyright

# 2. Rewrite each pyproject.toml — 4 fields per file
#    [project] name = "tradewinds-X" → "mostlyright-X"
#    dependencies = [..."tradewinds>=0.1.0rc1,<0.2"...] → ...mostlyright>=0.1.0rc1,<0.2...
#    optional-dependencies blocks referencing tradewinds-weather etc.
#    [tool.hatch.build.targets.wheel] packages = ["src/tradewinds"] → ["src/mostlyright"]

# 3. Rewrite root pyproject.toml
#    [project] dependencies = ["tradewinds", "tradewinds-weather", "tradewinds-markets"]
#       → ["mostlyright", "mostlyright-weather", "mostlyright-markets"]
#    [tool.uv.sources] tradewinds = { workspace = true } → mostlyright = { workspace = true }
#    (same for weather + markets)

# 4. Regenerate uv lockfile (CRITICAL — don't try to upgrade-package; the name moved)
rm uv.lock
uv lock

# 5. Verify wheel builds (PEP 420 namespace check)
uv build --all-packages
unzip -l dist/mostlyright-0.1.0rc1-py3-none-any.whl | head -20
# Expect: src/mostlyright/__init__.py, src/mostlyright/research.py, ...
# Expect: NO __init__.py at src/mostlyright/ from the weather/markets wheels
```

### W1: Atomic npm package rename (TypeScript)

```bash
# 1. Rewrite 5 package.json files:
#    packages-ts/core/package.json: "name": "@tradewinds/core" → "@mostlyright/core"
#    packages-ts/weather/package.json: "name": "@tradewinds/weather" → "@mostlyright/weather"
#    packages-ts/markets/package.json: "name": "@tradewinds/markets" → "@mostlyright/markets"
#    packages-ts/codegen/package.json: "name": "@tradewinds/codegen" → "@mostlyright/codegen"
#    packages-ts/meta/package.json: "name": "tradewinds" → "mostlyright"

# 2. Rewrite workspace deps (workspace:* paths use package name, NOT path)
#    packages-ts/meta/package.json:
#      "@tradewinds/core": "workspace:*" → "@mostlyright/core": "workspace:*"
#      (same for weather + markets)
#    packages-ts/weather/package.json:
#      peerDependencies: "@tradewinds/core" → "@mostlyright/core"
#      devDependencies: "@tradewinds/core": "workspace:*" → "@mostlyright/core": "workspace:*"
#    packages-ts/markets/package.json:
#      (same as weather)

# 3. Update .changeset/config.json fixed group:
#    "fixed": [["@tradewinds/core", "@tradewinds/weather", "@tradewinds/markets", "tradewinds"]]
#      → [["@mostlyright/core", "@mostlyright/weather", "@mostlyright/markets", "mostlyright"]]

# 4. Update root package.json `size-limit` entries that name @tradewinds/* packages

# 5. Regenerate pnpm lockfile
pnpm install
# pnpm install will rewrite workspace:* refs via the new package names automatically.

# 6. Verify typecheck + test still pass (TS imports still say @tradewinds — they'll RED;
#    documented expected RED state, W3 fixes this)
```

### W2 Batch A: Python import rewrite (driver script)

```python
# scripts/_phase12_rename.py — driver for W2 Batches A/B/C
# Run: python scripts/_phase12_rename.py --batch A
#
# Source: stdlib re module, line-oriented regex restricted to import statements.
# DOES NOT use ast — preserves comments, docstrings, and lift-source citations
# (which mention `mostlyright` legitimately) by construction.

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

IMPORT_FROM_RE = re.compile(r"^(\s*from\s+)tradewinds(\.|\s)")
IMPORT_BARE_RE = re.compile(r"^(\s*import\s+)tradewinds(\.|\s|$)")

# Path roots per batch
BATCHES = {
    "A": [Path("packages/")],
    "B": [Path("tests/")],
    "C": [Path("scripts/")],
}

def rewrite_file(path: Path) -> int:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    n_changed = 0
    new_lines = []
    for line in lines:
        new = IMPORT_FROM_RE.sub(r"\1mostlyright\2", line, count=1)
        new = IMPORT_BARE_RE.sub(r"\1mostlyright\2", new, count=1)
        if new != line:
            n_changed += 1
        new_lines.append(new)
    if n_changed:
        path.write_text("".join(new_lines), encoding="utf-8")
    return n_changed

def main(batch: str) -> None:
    roots = BATCHES[batch]
    total = 0
    files = 0
    for root in roots:
        for py in root.rglob("*.py"):
            n = rewrite_file(py)
            if n:
                files += 1
                total += n
                print(f"  {py}: {n} lines")
    print(f"\nBatch {batch}: rewrote {total} lines across {files} files.")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch", choices=["A", "B", "C"], required=True)
    args = ap.parse_args()
    main(args.batch)
```

### W4: Cache back-compat shim (specified in CONTEXT.md, reproduced for completeness)

```python
# packages/core/src/mostlyright/_internal/_cache_dir.py
"""Resolve the on-disk cache directory.

Resolution order (highest precedence first):
1. ``MOSTLYRIGHT_CACHE_DIR`` env var (canonical, post-Phase-12).
2. ``TRADEWINDS_CACHE_DIR`` env var (legacy; emits DeprecationWarning;
   scheduled for removal in v0.3).
3. Default: ``~/.mostlyright/cache/v1/``.
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

### W7 Verification grep (with preserve-list)

```bash
# Excludes:
#   - .planning/ (audit trail, intentionally preserved)
#   - node_modules/ / dist/ / .git/ (regenerated or non-source)
#   - mostlyright_v1 (LINEAGE-01 parser_name schema enum)
#   - MostlyRight  (deprecation alias classes + docstring citations)
#   - monorepo-v0.14.1 (lift-source path citations)
#   - mostlyright==0.14.1 (parity-citation literals)
#   - mostlyright-legacy (operator's renamed legacy folder docs)

grep -rn 'tradewinds' \
  packages/ packages-ts/ tests/ scripts/ docs/ README.md CLAUDE.md .github/workflows/ \
  --include='*.py' --include='*.ts' --include='*.tsx' --include='*.json' \
  --include='*.toml' --include='*.md' --include='*.yml' --include='*.yaml' \
  | grep -v 'mostlyright_v1\|MostlyRight\|monorepo-v0.14.1\|mostlyright==0.14.1\|tradewinds-legacy\|\.planning/'
# Expected output: 0 lines.

# Symmetric check on mostlyright (sanity — should have many legitimate hits):
grep -rln 'mostlyright' packages/ packages-ts/ 2>/dev/null | wc -l
# Expected: nonzero (every renamed file).
```

## State of the Art

| Old (pre-Phase-12) | Current (post-Phase-12) | When | Impact |
|---|---|---|---|
| `tradewinds` PyPI distro | `mostlyright` PyPI distro | W1 + operator OP2 | Old name orphaned on PyPI (operator follow-up) |
| `tradewinds-weather`, `tradewinds-markets` | `mostlyright-weather`, `mostlyright-markets` | W1 + operator OP2 | Same |
| `@tradewinds/{core,weather,markets,codegen}` + `tradewinds` meta | `@mostlyright/{core,weather,markets,codegen}` + `mostlyright` meta | W1 + operator OP3+OP4 | Same on npm |
| `from tradewinds import research` | `from mostlyright import research` | W2 | 1044 sites rewrite |
| `from "@tradewinds/core"` | `from "@mostlyright/core"` | W3 | 61 quoted-import sites rewrite |
| `TRADEWINDS_CACHE_DIR` env var | `MOSTLYRIGHT_CACHE_DIR` env var + back-compat | W4 | One-release deprecation window; v0.3 removes the legacy branch |
| `~/.tradewinds/cache/v1/` | `~/.mostlyright/cache/v1/` | W4 | User-side `mv` documented; no auto-migration |

**Deprecated/outdated (preserved intentionally — these are NOT renamed):**
- `mostlyright==0.14.1`: parity-citation literal (50+ docstrings). Stays.
- `monorepo-v0.14.1`: lift-source path. Stays.
- `MostlyRightClient`, `MostlyRightMCPError`: deprecation aliases for `mostly-light` migration. Stay (scheduled for v0.3 removal — separate decision).
- `mostlyright_v1`: parser_name schema enum value (LINEAGE-01). Stays.
- `helloiamvu/tradewinds` GitHub URL: explicitly preserved in this phase (operator may rename repo out-of-band).

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `tradewinds.dev` is a placeholder URL with no DNS / wire significance; rename to `mostlyright.dev` is safe | §Pitfall 1 | If `tradewinds.dev` IS bound to a live DNS record or hosting (unlikely per `local-first SDK; no hosted backend`), renaming would break any external schema validator that follows `$id`. Recommendation: confirm with user. |
| A2 | The W2 line-restricted regex rewrite catches all production import sites with no false negatives | §Architecture W2 | A multi-line `from tradewinds.X import (\n  a,\n  b,\n)` style import where the second-line items reference `tradewinds.` inside (rare; not seen in codebase) would not match. Recommend: post-rewrite, run `grep -rn 'tradewinds\.' packages/ tests/ scripts/ --include='*.py'` to catch survivors. |
| A3 | The `TRADEWINDS_TS_LIVE` env var in `drift-rotate-ts.yml` is the only TS-side env var to migrate | §Runtime State env vars | If other TS code reads custom env vars, missing them would silently fail. Confirmed via grep: only `TRADEWINDS_TS_LIVE` matched the `tradewinds`-prefixed env var pattern in TS. |
| A4 | `TW_HOSTED_URL` stays unchanged | §Runtime State env vars | TW prefix is Phase 7 convention, not a brand reference. If user wants it renamed to `MR_HOSTED_URL`, that's a separate decision. Recommendation: confirm with user during planning. |
| A5 | The 4 direct `os.environ.get("TRADEWINDS_CACHE_DIR")` sites are exhaustive | §W4 architecture | Verified via grep `os.(environ.get\|environ\[\|getenv)\s*\(?\s*["']TRADEWINDS_CACHE_DIR`. If indirect access (e.g., `os.environ.copy()` then dict lookup) exists, the shim won't catch it. Spot-check during W4. |
| A6 | The `mostlyright_v1` parser_name enum value is preserved verbatim (no rename to `legacy_v1` or similar) | §Preserve list | LINEAGE-01 schema spec uses this exact literal; any change would require a schema vN+1 bump per CROSS-SDK-SYNC §1.4. Confirmed by reading observation_ledger.py:27. |
| A7 | The `MostlyRightClient` / `MostlyRightMCPError` deprecation aliases remain importable post-Phase-12 (no rename to `TradewindsLegacyClient` or similar) | §Preserve list | These exist as `mostly-light` migration shims per CORE-04. Renaming would break the migration contract. Phase 12 leaves them alone. |
| A8 | Phase 12 retains `mostlyright.dev` (or similar placeholder) in `$id` — does NOT drop the URL entirely | §Pitfall 1 | Test asserts the prefix; dropping requires test update. Recommendation in W6/W7. |
| A9 | The `git mv` approach for the 3 source directories preserves `git log --follow` history | §Pitfall 6 | Verified via session test (git mv + revert worked cleanly with no `??` git status entries). |
| A10 | The actual scope counts from `grep` (1044 / 30 / 61 / 75) supersede the audit estimates (1044 / 30 / 77 / 204) | §Summary | The audit was likely written against a different commit; planner should use the verified numbers. |

## Open Questions (RESOLVED)

1. **`tradewinds.dev` → `mostlyright.dev` or drop the URL?**
   - What we know: It's a placeholder `$id` URL with no DNS binding (per local-first SDK design); 19 occurrences across schemas + validators + test assertion + 2 specs/*.json files.
   - What's unclear: User preference. Renaming maintains the schema $id pattern; dropping requires test rewrite.
   - **RESOLVED:** Rename to `mostlyright.dev` for minimum diff. Implemented in `12-02-PLAN.md` Batch C (Python: `scripts/export_schemas.py` $id literal + `tests/test_export_schemas.py` assertion update) and `12-03-PLAN.md` Task 2 (TS: schemas/json + generated validators regenerated via `pnpm codegen`).

2. **`TRADEWINDS_TS_LIVE` env var rename?**
   - What we know: One occurrence in `drift-rotate-ts.yml` (CI workflow); not documented in user-facing docs.
   - What's unclear: Whether to rename to `MOSTLYRIGHT_TS_LIVE` (consistent) or leave (deprioritize since it's CI-only).
   - **RESOLVED:** Rename to `MOSTLYRIGHT_TS_LIVE` for consistency; 1-line edit. Implemented in `12-06-PLAN.md` truth #4 + Task 1 Step substitution.

3. **Operator confirmation lines in the PR description (RENAME-09)?**
   - What we know: CONTEXT.md says "PR description references confirmation" but doesn't spell out the template.
   - What's unclear: What confirmation lines exactly does the operator post?
   - **RESOLVED:** Phase 12 README (`12-rename-to-mostlyright/README.md`) provides this 4-line operator checklist that the operator pastes into the merged-vision → main PR description:
     ```
     - [ ] OP1: `mv ~/Documents/GitHub/mostlyright ~/Documents/GitHub/mostlyright-legacy` (confirmed)
     - [ ] OP2: 3 PyPI pending publishers registered for mostlyright/mostlyright-weather/mostlyright-markets (confirmed)
     - [ ] OP3: @mostlyright npm scope claimed (confirmed)
     - [ ] OP4: 4 npm OIDC pending publishers registered (confirmed)
     ```
     Implemented in `12-07-PLAN.md` Task 2 (README write step + verification regex `expect 4` for the 4-line checklist).

4. **Should W6 also rename existing test fixture names?**
   - What we know: 5-fixture parity test reads from `tests/fixtures/parity/` (directory path unchanged in CONTEXT). But the fixture filenames + JSON contents may reference `tradewinds` strings.
   - What's unclear: Whether parity fixture .parquet/.json bytes contain literal `tradewinds` strings (in column names? source IDs?). Probably not — they contain station codes + temperatures.
   - **RESOLVED:** W7 final verification grep in `12-07-PLAN.md` Task 1 Step 8 covers `tests/` (which includes `tests/fixtures/parity/`); the preserve-list allows expected legitimate hits. The TS parity recordings under `packages-ts/meta/tests/parity/` are similarly covered. Likely 0 hits; if any appear, they fall under the preserve-list exemption or are addressed by the same Task 1 final-grep gate before claiming parity-green.

## CI Workflow Edit Inventory (for W6 planning)

| File | Tradewinds refs | What changes |
|------|----------|--------------|
| `release.yml` | Lines 10 (comment), 100-153 (3 jobs × `tradewinds` / `tradewinds-weather` / `tradewinds-markets`) | `uv build --package tradewinds` → `--package mostlyright`; PyPI URLs `pypi.org/project/tradewinds/...` → `pypi.org/project/mostlyright/...`; job names + comments |
| `release-ts.yml` | Lines 10-15 (comment), 113-153 (4 publish steps × `@tradewinds/core` etc.) | `pnpm publish` working-directory unchanged (paths stay); step name comments + scope refs in comments |
| `test.yml` | Lines 67-70 (doctest paths), 107-109 (comment), 121-123 (uv sync invocations), 144-163 (coverage paths + comments) | `packages/core/src/tradewinds/...` → `packages/core/src/mostlyright/...`; `uv sync --package tradewinds` → `--package mostlyright` (×3); comments + coverage scope path |
| `test-ts.yml` | Line 58 (comment) | comment refs to `@tradewinds/core/internal/...` |
| `schema-drift.yml` | Lines 15-23, 31-39 (path filters) | Path filters `packages/core/src/tradewinds/...` → `packages/core/src/mostlyright/...` (×8) |
| `release-testpypi.yml` | Same pattern as release.yml | TestPyPI URLs + uv build --package args |
| `wheel-metadata-check.yml` | Line 6 (comment) | Comment ref to `tradewinds >=0.1.0,<0.2` |
| `drift-rotate.yml` | Line 4 (comment) | "tradewinds.research()" |
| `drift-rotate-ts.yml` | Lines 47, 50 (`--filter tradewinds`), env var `TRADEWINDS_TS_LIVE` line ~42 | `pnpm --filter tradewinds drift-capture` → `--filter mostlyright drift-capture`; `TRADEWINDS_TS_LIVE` → `MOSTLYRIGHT_TS_LIVE` |
| `parity-ticket-check.yml` | Comment refs (lines 1-15) | Trigger paths file `.github/parity-trigger-paths.json` needs in-file rewrites — see `parity_paths.json` row below |
| `.github/parity-trigger-paths.json` | Lines 4-17 (python_paths array) | All `packages/core/src/tradewinds/...` path globs → `packages/core/src/mostlyright/...` (×11) |

**Total CI edits estimated:** ~75 lines across 10 files (matches the `grep -rn 'tradewinds' .github/workflows/` count of 75).

## Validation Architecture

Per CONTEXT.md: Nyquist NOT enabled (`workflow.nyquist_validation_enabled: false` in `.planning/config.json`). Section skipped.

## Sources

### Primary (HIGH confidence)
- [12-CONTEXT.md](.planning/phases/12-rename-to-mostlyright/12-CONTEXT.md) — user-locked decisions + 9-wave structure
- [REQUIREMENTS.md RENAME-01..10](.planning/REQUIREMENTS.md) — requirement IDs
- [ROADMAP.md Phase 12](.planning/ROADMAP.md) — phase placement + dependencies (Phase 11 closing)
- [REVIEW-DISCIPLINE.md](.planning/REVIEW-DISCIPLINE.md) — mixed PR routing (codex `high` + python-architect + ts-architect parallel) + never-skip path list
- [CROSS-SDK-SYNC.md §1](.planning/CROSS-SDK-SYNC.md) — schema codegen flow + drift gate
- [CLAUDE.md](CLAUDE.md) — branch workflow + TDD + hooks-mandatory + parity-gate-untouchable
- [packages/{core,weather,markets}/pyproject.toml](packages/) — current 3 distribution names, hatchling wheel target lines, inter-package version pins
- [packages-ts/{core,weather,markets,meta,codegen}/package.json](packages-ts/) — current 5 npm package names, workspace deps pattern
- [pyproject.toml](pyproject.toml) — workspace root deps + [tool.uv.sources]
- [pnpm-workspace.yaml](pnpm-workspace.yaml) — TS workspace pattern
- [.github/workflows/release.yml + release-ts.yml + test.yml + test-ts.yml + schema-drift.yml + 5 others](.github/workflows/) — CI surface
- [scripts/export_schemas.py](scripts/export_schemas.py) — schema exporter + `tradewinds.dev` `$id` literal
- [tests/test_export_schemas.py](tests/test_export_schemas.py) — `$id.startswith("https://tradewinds.dev/")` assertion
- [packages/weather/src/tradewinds/weather/cache.py](packages/weather/src/tradewinds/weather/cache.py) — DEFAULT_ROOT + env var read site
- [packages/core/src/tradewinds/__init__.py](packages/core/src/tradewinds/__init__.py) — PEP 420 namespace declaration via `pkgutil.extend_path`
- [.changeset/config.json](.changeset/config.json) — `fixed` group with 4 TS package names
- [.pre-commit-config.yaml](.pre-commit-config.yaml) — ruff + format + check-yaml/toml + pytest-fast hook

### Secondary (MEDIUM confidence — verified via grep against worktree HEAD)
- Audit numbers refreshed: `from tradewinds`=1044, `import tradewinds`=30, TS `from "@tradewinds/`=61, `TRADEWINDS_CACHE_DIR`=75, docs/=85, CLAUDE.md=20, workflows/=75, packages-ts/*/README.md github.com refs=5
- Preserve-list scope: 20 `MostlyRight*` class-name refs, `mostlyright_v1` in 1 enum spec + 1 schema JSON + 2 TS generated outputs, `monorepo-v0.14.1` lift citations in 20+ docstrings
- `~/.tradewinds` hardcoded paths: 5 source files + 4 doc files (verified)
- 4 direct `os.environ.get("TRADEWINDS_CACHE_DIR")` reader sites identified

### Tertiary (LOW confidence — flagged for validation)
- The exact number of ruff-isort reorderings post-W2 batch rewrite (Pitfall 7) — not directly measurable without running the batches; recommendation to run ruff post-rewrite is defensive.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all versions verified against worktree configuration
- Architecture: HIGH — git mv + ast/regex rewriter approach validated by inspection of file structure + a session test of `git mv` round-trip
- Pitfalls: HIGH — 11 pitfalls each verified by grep evidence in the worktree

**Research date:** 2026-05-25
**Valid until:** Until Phase 12 starts execution (the audit numbers shift with each commit to the worktree).

---

*Phase: 12-rename-to-mostlyright*
*Research captured 2026-05-25 via /gsd-research-phase + grep verification against worktree HEAD*

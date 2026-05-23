---
phase: 04-coverage-docs-cicd-release
type: execute
duration: Days 42-45 (4 working days + half-day Wave 5 dry-run before tag)
waves: 5
depends_on:
  - phase-03-mode-2-integration-migration-gate
  - phase-03-1-international-station-expansion-observations-daily-extremes
  - phase-03-2-multi-forecast-live-path-hrrr-gfs-nbm-via-noaa-bdp
  - phase-03-3-polymarket-integration-discovery-settlement
  - phase-03-4-qc-engine-alpha-sidecar-crosscheck
  - phase-03-5-transforms-dsl-preprocessing-primitives
  - phase-03-6-discovery-api-public-settlement-dataversion
branch_strategy: per-wave off main; sub-branches per parallel task; two-reviewer loop (Codex high + python-architect) per branch; wave merges to phase-4/integration; phase-4/integration → main with --no-ff
requirements:
  - PKG-01
  - DOCS-01
  - DOCS-02
  - DOCS-03
  - CI-01
  - CI-02
  - CI-03
  - CI-04
  - CI-05
autonomous: false  # Operator must register 3 PyPI pending publishers + set up GH environment before Wave 5; external README timer needed for DOCS-02 SC
files_modified:
  # Wave 1
  - pyproject.toml                                                    # coverage.run/coverage.report blocks + version refs
  - packages/core/pyproject.toml                                      # version 0.1.0a1 → 0.1.0 (rc1 first)
  - packages/weather/pyproject.toml                                   # version 0.1.0a1 → 0.1.0 (rc1 first)
  - packages/markets/pyproject.toml                                   # version 0.1.0a1 → 0.1.0 (rc1 first)
  - packages/core/src/tradewinds/research.py                          # NumPy-style doctest example (+SKIP for network)
  - packages/core/src/tradewinds/core/temporal/knowledge_view.py      # doctest example (in-memory)
  - packages/core/src/tradewinds/core/temporal/leakage.py             # doctest example (in-memory)
  - packages/core/src/tradewinds/core/validator.py                    # doctest example (in-memory)
  - packages/core/src/tradewinds/snapshot.py                          # switch _internal/_toon import → core.formats._toon
  - packages/core/src/tradewinds/_internal/models/_base.py            # switch _internal/_toon import → core.formats._toon
  - packages/core/src/tradewinds/_internal/_toon.py                   # DELETE (duplicate)
  - tests/test_packaging.py                                           # extend version pin assertions for 0.1.0 final
  - CHANGELOG.md                                                      # Phases 2 → 3.6 + 4 closeout entries
  # Wave 2
  - README.md                                                         # expand 46 → ~120 lines for DOCS-02
  - docs/adapters/iem.md                                              # NEW
  - docs/adapters/awc.md                                              # NEW
  - docs/adapters/cli.md                                              # NEW
  - docs/adapters/ghcnh.md                                            # NEW
  # Wave 3
  - .github/workflows/test.yml                                        # NEW — push + PR matrix + cov + doctests + lint + mypy soft
  - .github/workflows/release.yml                                     # NEW — v* tag trusted publishing
  - .github/workflows/release-testpypi.yml                            # NEW — rc* tag TestPyPI dry-run
  - scripts/check_wheel_metadata.py                                   # NEW — CI-02 wheel METADATA grep
  - tests/smoke_post_publish.py                                       # NEW — post-publish wheel install + import
  # Wave 4
  - tests/fixtures/README.md                                          # NEW — two-tier policy
  - tests/fixtures/drift/.gitkeep                                     # NEW — scaffold directory
  - tests/fixtures/drift/capture_drift.py                             # NEW — captures against current research()
  - tests/fixtures/drift/compare.py                                   # NEW — diffs parity vs drift
  - tests/test_drift.py                                               # NEW — soft assertion (skipped if drift/ empty)
  - .github/workflows/drift-rotate.yml                                # NEW — weekly Monday 07:00 UTC cron
  # Wave 5
  - .planning/STATE.md                                                # post-ship status update + v0.1.0 close-out
must_haves:
  truths:
    - "tradewinds.core.* branch coverage is ≥90% per pytest --cov-branch --cov-fail-under=90 (Phase 4 HARD GATE)."
    - "scripts/check_wheel_metadata.py exists and exits non-zero when any built wheel's Requires-Dist on a sibling tradewinds-* package is missing >=0.1.0 OR <0.2."
    - "All 3 distributions (tradewinds, tradewinds-weather, tradewinds-markets) publish at v0.1.0 final to pypi.org via OIDC trusted publishing — confirmed by pip index versions tradewinds tradewinds-weather tradewinds-markets."
    - "v0.1.0rc1 published to test.pypi.org first; smoke install + import + research() smoke green BEFORE the v0.1.0 final tag is created."
    - ".github/workflows/test.yml runs on every push + PR with Python 3.11/3.12/3.13 on ubuntu + 3.12 on macOS; pytest -m 'not live' green; coverage gate enforced; doctests green on 4 public-surface modules; ruff check + ruff format --check both green; mypy --strict packages/core/src/tradewinds/core/ runs with continue-on-error: true (soft gate per Open Q2 default)."
    - ".github/workflows/release.yml triggers on v* tag, runs uv build --all-packages, runs scripts/check_wheel_metadata.py, runs the in-CI install-and-import smoke against all 3 dist files, then uv publish — all three distros uploaded by a single uv publish call."
    - ".github/workflows/drift-rotate.yml runs weekly (Mondays 07:00 UTC), captures current research() output for the same 5 case inputs as tests/fixtures/parity/, diffs against parity, opens an issue labelled drift+phase-4 on any mismatch."
    - "README.md works end-to-end in <5 minutes for a fresh installer timed by an external person (not Vu, not Robert) — pip install + smoke test + research() call all succeed within budget."
    - "Adapter knowledge-resource pages exist for iem, awc, cli, ghcnh (4 files in docs/adapters/) each covering schema, gotchas, timezone handling, source-pairing rules, cache layout."
    - "research(), KnowledgeView, LeakageDetector, validate_dataframe carry NumPy-style docstrings with executable >>> doctest examples (+SKIP on the network-bound research() example)."
    - "tests/fixtures/parity/ remains BYTE-IDENTICAL to its Phase 1 freeze; tests/fixtures/README.md documents the never-re-record discipline + drift watchdog policy."
    - "Three PyPI pending publishers are registered before Wave 3 merges to phase-4/integration (operator gate)."
    - "Pre-commit hooks (ruff check --fix + ruff format + pre-commit-hooks) remain green on every commit in Phase 4; no commit lands with --no-verify."
  artifacts:
    - path: .github/workflows/test.yml
      provides: "CI test workflow — matrix on 3.11/3.12/3.13 + macOS 3.12, pytest -m 'not live' + coverage gate + doctests + lint + soft mypy"
    - path: .github/workflows/release.yml
      provides: "Production release workflow — v* tag → uv build --all-packages → wheel METADATA check → smoke install → uv publish to pypi.org"
    - path: .github/workflows/release-testpypi.yml
      provides: "TestPyPI dry-run workflow — rc* tag → identical pipeline to release.yml but publishes to test.pypi.org"
    - path: .github/workflows/drift-rotate.yml
      provides: "Weekly Monday 07:00 UTC cron — captures drift fixtures, diffs vs parity, opens GH issue on mismatch"
    - path: scripts/check_wheel_metadata.py
      provides: "Standalone CLI — reads dist/*.whl, extracts .dist-info/METADATA, asserts cross-package Requires-Dist pins carry both >=0.1.0 and <0.2"
    - path: tests/fixtures/README.md
      provides: "Two-tier fixture policy doc — parity/ frozen + never-re-recorded; drift/ rotated weekly via cron"
    - path: tests/fixtures/drift/capture_drift.py
      provides: "Drift capture recipe pointed at tradewinds.research() (not mostlyright.client.pairs)"
    - path: tests/fixtures/drift/compare.py
      provides: "Differ — np.allclose + dtypes.equals; soft-fail on mismatch; writes drift-report.md"
    - path: tests/test_drift.py
      provides: "Pytest assertion exercising drift compare; skipped on fresh clones (no drift/ files)"
    - path: docs/adapters/iem.md
      provides: "IEM (ASOS + MOS + CLI mirror) adapter doc — schema, gotchas, timezones, pairing, cache"
    - path: docs/adapters/awc.md
      provides: "AWC METAR JSON adapter doc — Sept 2025 endpoint migration, visibility M1/4 pitfall, US-only coverage"
    - path: docs/adapters/cli.md
      provides: "NWS CLI settlement source doc — preliminary/final/correction dedup, station_tz, cli_data_quality enum, settlement_finality"
    - path: docs/adapters/ghcnh.md
      provides: "NCEI GHCNh adapter doc — pipe-separated PSV format, historical depth, international coverage"
    - path: README.md
      provides: "120-line quickstart — install (3 pkgs), smoke (__version__), research() call, packages table, cache + env vars, links to docs/"
    - path: CHANGELOG.md
      provides: "Phases 2 → 3.6 closeout entries + Phase 4 entry + v0.1.0 release row"
    - path: pyproject.toml
      provides: "[tool.coverage.run] branch=true + source_pkgs + omit; [tool.coverage.report] fail_under=90 + exclude_lines"
    - path: packages/core/pyproject.toml
      provides: "version = '0.1.0' (bumped from '0.1.0a1' in lockstep with weather + markets)"
    - path: packages/weather/pyproject.toml
      provides: "version = '0.1.0' (bumped)"
    - path: packages/markets/pyproject.toml
      provides: "version = '0.1.0' (bumped)"
  key_links:
    - from: .github/workflows/release.yml
      to: scripts/check_wheel_metadata.py
      via: "uv run python scripts/check_wheel_metadata.py dist/ — runs after uv build --all-packages, BEFORE upload step"
    - from: .github/workflows/release.yml
      to: PyPI trusted publishers (3 projects, account-scoped pending until first publish)
      via: "OIDC handshake on environment: pypi — operator-registered with workflow=release.yml + env=pypi character-for-character matching"
    - from: pyproject.toml [tool.coverage.run]
      to: tradewinds.core.* branch-coverage gate
      via: "fail_under = 90 + omit for lifted _toon.py — projection 86% → 94% after exclusion (Wave 1 verifies empirical)"
    - from: .github/workflows/drift-rotate.yml
      to: tests/fixtures/drift/ + tests/fixtures/parity/
      via: "weekly cron captures into drift/, runs compare.py against parity/, opens GH issue on mismatch (soft watchdog, never blocks CI)"
    - from: README.md quickstart
      to: tradewinds.research() + 3 distributions on PyPI
      via: "pip install tradewinds tradewinds-weather tradewinds-markets → python -c 'import tradewinds; tradewinds.__version__' → research() — <5 min external timer"
---

<objective>
Ship v0.1.0 to PyPI. The code is done (11/12 phases on main, 1451 tests green, three distros structurally correct, parity gate green). What remains is gating infrastructure — coverage, doctests, CI — plus the actual publish.

**Purpose** — close the last five Phase 4 ROADMAP Success Criteria + the nine outstanding requirements (PKG-01, DOCS-01..03, CI-01..05). The single hard-blocker is the `tradewinds.core.*` branch-coverage gate (currently 86%, target ≥90%). The single load-bearing risk is name squatting on PyPI before our three pending publishers register. Everything else is mechanical: write workflow YAML, write 4 adapter docs, expand the README, scaffold the drift tier, tag-and-publish.

**Output** — three wheels on pypi.org at v0.1.0 (`tradewinds`, `tradewinds-weather`, `tradewinds-markets`), test.yml + release.yml + release-testpypi.yml + drift-rotate.yml live on `main`, README quickstart timed under 5 min by an external person, four adapter docs published, two-tier fixture policy in force.
</objective>

<execution_context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/REQUIREMENTS.md
@.planning/STATE.md
@.planning/REVIEW-DISCIPLINE.md
@.planning/phases/04-coverage-docs-cicd-release/RESEARCH.md
@CLAUDE.md
</execution_context>

<phase_summary>

**Goal:** Tag v0.1.0 and publish all three distributions to PyPI within 4-5 working days. Coverage gate is the only hard blocker; everything else (docs, CI YAML, release workflow) is mechanical.

**The release-mechanics insight:** Phase 4 is not architecture work. Almost everything is solved by existing tooling — `uv build --all-packages` already produces the three wheels (verified at `tests/test_wheel_layout.py`), `tests/test_packaging.py` already asserts cross-package pins at pyproject level, `tests/fixtures/parity/` already holds the 5 frozen byte-equivalent fixtures from Day 0.5. Phase 4 wires these into GH Actions YAML, closes the one coverage gap (`_toon.py` exclusion), scaffolds the drift watchdog, and runs the publish.

**Wave structure (5 waves, Days 42-45):**

| Wave | Day | Branch | Goal | Parallel lanes |
|------|-----|--------|------|----------------|
| 1 | Day 42 | `phase-4/wave-1-coverage-doctest-version` | Coverage gap closure + doctest scaffolding + version bumps + CHANGELOG | 3 sub-branches (independent files) |
| 2 | Day 43 | `phase-4/wave-2-docs` | README expansion + 4 adapter pages | 2 sub-branches (README || 4 adapter pages) |
| 3 | Day 44 | `phase-4/wave-3-ci-workflows` | test.yml + release.yml + release-testpypi.yml + check_wheel_metadata.py | 2 sub-branches (script || workflows) |
| 4 | Day 44.5 | `phase-4/wave-4-drift-fixtures` | Two-tier fixture docs + drift scaffolding + drift-rotate.yml | 1 lane (small surface) |
| 5 | Day 45 | `phase-4/wave-5-release` | rc1 → TestPyPI → verify → v0.1.0 → prod PyPI → STATE.md close-out | 1 lane (atomic + operator gates) |

**Branch flow per wave (post-Phase-1 convention):**
- Wave branch off `main` (NOT `merged-vision` — that pattern was abandoned after Phase 1).
- Sub-branches off the wave branch for parallel tasks.
- Two-reviewer loop (Codex `high` + python-architect) per sub-branch before merge to wave branch.
- Each wave merges to `phase-4/integration` after the full test suite passes.
- `phase-4/integration` merges to `main` with `git merge --no-ff` after Wave 5 completes (one big PR).
- No direct commits to `main`. No `--no-verify` on any commit.

**Operator gates (cannot be automated — must complete before listed wave starts):**
- **Before Wave 3 merges to `phase-4/integration`:** Operator registers 3 PyPI pending publishers (account → Publishing → Add pending publisher, one per distribution). See Open Question Q-04 + Wave 5 Task 5.1 for exact form values. **5 minutes of UI work; 0 minutes of code; load-bearing for the release.** Name-squatting risk window = time between Wave 1 and registration; recommend doing this Day 42.
- **Before Wave 5 starts:** Operator creates GH repo Environment named `pypi` (Settings → Environments → New environment), optionally adds `helloiamvu` as required reviewer (recommended — accidental tag pushes don't auto-publish).
- **Before Wave 5 v0.1.0 final tag:** External person (not Vu, not Robert) clones the rc1 published wheels from TestPyPI and runs the README quickstart with a stopwatch. <5 min OR loop on README until it lands.

</phase_summary>

<wave id="1" name="Coverage gap closure + doctest scaffolding + version bumps + CHANGELOG">

**Day:** Day 42
**Branch:** `phase-4/wave-1-coverage-doctest-version` off `main` (commit `fcdc83e`)
**Parallelism:** 3 sub-branches (coverage || doctests || version+CHANGELOG) — independent files, no overlap.
**Estimated effort:** 1 day with 3-lane parallelism.
**Delivers:** ≥90% branch coverage on `tradewinds.core.*` (HARD GATE), DOCS-01 (NumPy doctests), version preparation for Wave 5 tag

### Goal

Close the coverage gap from 86% → ≥90% on `tradewinds.core.*` (the only hard blocker for v0.1.0 ship). Add NumPy-style doctest examples to the four ROADMAP-named public symbols. Bump all three pyproject versions from `0.1.0a1` to `0.1.0` in lockstep (the rc1 tag in Wave 5 uses the same `0.1.0` version — PyPI immutable filenames mean no version churn between rc1 and final). Catch up CHANGELOG.md from Phase 2 through Phase 4.

### Dependencies

- Phase 3.6 merged to `main` (✓ per STATE.md, commit `fcdc83e`).
- **Open Question Q-05 must be resolved before this wave starts** (verify whether `tradewinds==0.1.0a1` already exists on PyPI via `pip index versions tradewinds tradewinds-weather tradewinds-markets`). If alpha1 is published, the pending-publisher flow becomes a per-project trusted publisher registration in Wave 5 (simpler). If not, Wave 5 must do pending publisher first.

### Tasks

#### Task 1.1: Coverage gap closure — `_toon.py` exclusion + verify ≥90% [sub-branch A]

- **Branch:** `phase-4/wave-1-coverage-doctest-version/coverage` off `phase-4/wave-1-coverage-doctest-version`.
- **Files:**
  - EDIT: `/Users/helloiamvu/Documents/GitHub/tradewinds/.claude/worktrees/jolly-spence-35a47d/pyproject.toml` (workspace root — add `[tool.coverage.run]` + `[tool.coverage.report]` blocks).
  - EDIT: `/Users/helloiamvu/Documents/GitHub/tradewinds/.claude/worktrees/jolly-spence-35a47d/packages/core/src/tradewinds/snapshot.py` (switch `from tradewinds._internal._toon import ...` → `from tradewinds.core.formats._toon import ...`).
  - EDIT: `/Users/helloiamvu/Documents/GitHub/tradewinds/.claude/worktrees/jolly-spence-35a47d/packages/core/src/tradewinds/_internal/models/_base.py` (same import swap).
  - DELETE: `/Users/helloiamvu/Documents/GitHub/tradewinds/.claude/worktrees/jolly-spence-35a47d/packages/core/src/tradewinds/_internal/_toon.py` (duplicate of `core/formats/_toon.py`; only 2 callers — both fixed above).
- **Action — Coverage approach decision (RESEARCH §"Coverage Approach"):** option (b) **coverage-omit** for `core/formats/_toon.py` + `core/formats/_toon_list_codec.py` (lifted from mostlyright v0.15.0 — RESEARCH-confirmed exemption per ROADMAP SC #1 "lifted code retains monorepo coverage"). The higher-level wrapper `core/formats/toon.py` (currently 85% covered) STAYS in scope. The legacy duplicate `_internal/_toon.py` gets DELETED (Open Question Q-06 recommendation), not omitted — only 2 callers (`snapshot.py:358`, `_internal/models/_base.py:47`) need import-site updates.

  Append to workspace root `pyproject.toml`:
  ```toml
  [tool.coverage.run]
  branch = true
  source_pkgs = ["tradewinds"]
  omit = [
      # Lifted TOON encoders — retain mostlyright v0.15.0 coverage per
      # ROADMAP Phase 4 SC #1 "lifted code retains monorepo coverage".
      # The wrapper at core/formats/toon.py (85% covered) STAYS in scope.
      "*/tradewinds/core/formats/_toon.py",
      "*/tradewinds/core/formats/_toon_list_codec.py",
  ]

  [tool.coverage.report]
  fail_under = 90
  show_missing = true
  skip_covered = false
  exclude_lines = [
      "pragma: no cover",
      "if TYPE_CHECKING:",
      "raise NotImplementedError",
      "if __name__ == .__main__.:",
      "@overload",
  ]
  ```

- **Action — Parity safety check (mandatory before commit):** Both files being edited are parity-adjacent. `snapshot.py` is on the settlement-snapshot path; `_internal/models/_base.py` is on the v0.14.1 lift surface. Run the 5 parity fixtures BEFORE committing the import swap:
  ```bash
  uv run pytest tests/test_parity.py -v
  ```
  All 5 cases MUST pass with `np.allclose(rtol=0, atol=0)` AND `dtypes.equals(expected_dtypes)`. If any case drifts, revert the import swap (the byte-equivalent TOON encoder output is the same between `core/formats/_toon.py` and `_internal/_toon.py` — both are the same lifted source — but verify empirically).

- **Action — Verify coverage actually clears 90% (RESEARCH §A4 risk):** Run the full suite with coverage:
  ```bash
  uv run pytest -m "not live" --cov=tradewinds.core --cov-branch --cov-report=term-missing --cov-fail-under=90
  ```
  - If exits 0 → coverage gate clears (projected 86% → ~94% after exclusion).
  - If exits non-zero with coverage in [86%, 90%) → secondary gap is `validator.py` (currently 93%; 7 missed lines + 7 BrPart). Add 3-5 tests under `packages/core/tests/core/test_validator.py` covering `allow_source_drift` edge cases + per-row source-null detection paths (the missing branches are defensive guards around malformed inputs per RESEARCH).
  - If exits non-zero with coverage <86% → something regressed; STOP and escalate.

- **Atomic commits (3):**
  1. `refactor(phase-4): swap _internal/_toon imports → core.formats._toon (parity-clean)` — touches `snapshot.py` + `_internal/models/_base.py`; parity gate runs as commit prereq.
  2. `chore(phase-4): delete _internal/_toon.py duplicate (CORE-05 cleanup)` — DELETE of the now-unreferenced duplicate; `grep -r "_internal._toon\|_internal/_toon" packages/` MUST return empty before commit.
  3. `feat(PKG-01): coverage config — branch=true, fail_under=90, omit lifted TOON encoders` — adds `[tool.coverage.*]` blocks to workspace `pyproject.toml`; runs full coverage measure and confirms ≥90%.

- **Codex review priority:** HIGH (parity-adjacent imports; coverage gate config is the load-bearing HARD GATE per ROADMAP Phase 4 SC #1; pyproject changes are on REVIEW-DISCIPLINE.md's never-skip list).

- **Test bar:**
  - `uv run pytest tests/test_parity.py -v` — all 5 fixtures green with `np.allclose(rtol=0, atol=0)`.
  - `uv run pytest -m "not live" --cov=tradewinds.core --cov-branch --cov-fail-under=90` — exit 0.
  - `grep -r "_internal\._toon\|_internal/_toon" packages/` returns empty.
  - `grep -r "from tradewinds.core.formats._toon" packages/core/src/tradewinds/snapshot.py packages/core/src/tradewinds/_internal/models/_base.py` returns both swapped lines.

#### Task 1.2: Doctest scaffolding for 4 public-surface modules [sub-branch B]

- **Branch:** `phase-4/wave-1-coverage-doctest-version/doctests` off `phase-4/wave-1-coverage-doctest-version`.
- **Files (edit existing — append `Examples` section to existing NumPy-style docstrings):**
  - `/Users/helloiamvu/Documents/GitHub/tradewinds/.claude/worktrees/jolly-spence-35a47d/packages/core/src/tradewinds/research.py` (the `research()` function — lines 876-942 per RESEARCH; add Examples with `# doctest: +SKIP` because network).
  - `/Users/helloiamvu/Documents/GitHub/tradewinds/.claude/worktrees/jolly-spence-35a47d/packages/core/src/tradewinds/core/temporal/knowledge_view.py` (`KnowledgeView.__init__` — lines 34-79; in-memory example, NO network).
  - `/Users/helloiamvu/Documents/GitHub/tradewinds/.claude/worktrees/jolly-spence-35a47d/packages/core/src/tradewinds/core/temporal/leakage.py` (`assert_no_leakage` and/or `LeakageDetector.check`; in-memory).
  - `/Users/helloiamvu/Documents/GitHub/tradewinds/.claude/worktrees/jolly-spence-35a47d/packages/core/src/tradewinds/core/validator.py` (`validate_dataframe` — show one valid + one `SourceMismatchError`-raising case; in-memory).

- **Action — Why explicit modules, NOT `addopts = "--doctest-modules"` (RESEARCH §"Doctest Strategy" Pitfall 5):** `--doctest-modules` recursively imports every `.py` it discovers, which means `_internal/_pairs.py` (lifted from v0.14.1), `_v02/` (Phase 2 leftovers), and other lifted modules get scanned. Lifted code may carry doctests that use old-API forms. We run doctests as a separate CI step with explicit module paths only — wired in Wave 3 task 3.1. This task ships the doctest CONTENT; Wave 3 wires the CI step.

- **Action — `KnowledgeView` doctest (use RESEARCH §"Code Examples" verbatim):**
  ```python
  Examples
  --------
  >>> import pandas as pd
  >>> from tradewinds.core import KnowledgeView, TimePoint
  >>> df = pd.DataFrame({
  ...     "knowledge_time": pd.to_datetime([
  ...         "2025-01-01T00:00:00Z",
  ...         "2025-01-02T00:00:00Z",
  ...         "2025-01-03T00:00:00Z",
  ...     ], utc=True),
  ...     "value": [10, 20, 30],
  ... })
  >>> view = KnowledgeView(df, TimePoint.from_iso("2025-01-02T12:00:00Z"))
  >>> len(view.dataframe())
  2
  ```

- **Action — `research()` doctest (network — must use `+SKIP`):**
  ```python
  Examples
  --------
  >>> import tradewinds as tw
  >>> df = tw.research("KNYC", "2025-01-06", "2025-01-12")  # doctest: +SKIP
  >>> list(df.columns)  # doctest: +SKIP
  ['date', 'station', 'cli_high_f', 'cli_low_f', 'obs_high_f', 'obs_low_f', 'obs_high_at', 'obs_low_at']
  ```

- **Action — `LeakageDetector` doctest (in-memory, must show both PASS and RAISE paths):**
  ```python
  Examples
  --------
  >>> import pandas as pd
  >>> from tradewinds.core import TimePoint, assert_no_leakage
  >>> df = pd.DataFrame({
  ...     "knowledge_time": pd.to_datetime(["2025-01-01T00:00:00Z"], utc=True),
  ...     "value": [10],
  ... })
  >>> assert_no_leakage(df, TimePoint.from_iso("2025-01-02T00:00:00Z"))  # passes silently
  ```

- **Action — `validate_dataframe` doctest:**
  ```python
  Examples
  --------
  >>> import pandas as pd
  >>> from tradewinds.core import validate_dataframe
  >>> df = pd.DataFrame({"date": pd.to_datetime(["2025-01-06"]), "station": ["KNYC"]})
  >>> df.attrs["source"] = "iem.archive"
  >>> reg = validate_dataframe(df, "schema.observation.v1")  # doctest: +SKIP
  >>> # Real example requires full canonical columns; see tests/core/test_validator.py
  ```

- **Action — Local verification (Wave 1 ships content; Wave 3 wires CI):**
  ```bash
  uv run pytest --doctest-modules \
      packages/core/src/tradewinds/research.py \
      packages/core/src/tradewinds/core/temporal/knowledge_view.py \
      packages/core/src/tradewinds/core/temporal/leakage.py \
      packages/core/src/tradewinds/core/validator.py
  ```
  All must exit 0 locally before commit.

- **Atomic commits (4 — one per module):**
  1. `docs(DOCS-01): NumPy-style doctest example for KnowledgeView.__init__`.
  2. `docs(DOCS-01): NumPy-style doctest example for LeakageDetector + assert_no_leakage`.
  3. `docs(DOCS-01): NumPy-style doctest example for validate_dataframe`.
  4. `docs(DOCS-01): NumPy-style doctest example for research() (+SKIP — network)`.

- **Codex review priority:** MEDIUM (docstring-only; cannot break parity; can fail doctest if a `>>>` example has a typo).

- **Test bar:** `uv run pytest --doctest-modules <4 paths above>` exits 0; doctest output matches `Expected` block exactly; ELLIPSIS/NORMALIZE_WHITESPACE not required because in-memory examples are deterministic.

#### Task 1.3: Version bumps to 0.1.0 + CHANGELOG catch-up [sub-branch C]

- **Branch:** `phase-4/wave-1-coverage-doctest-version/version-changelog` off `phase-4/wave-1-coverage-doctest-version`.
- **Files:**
  - EDIT: `/Users/helloiamvu/Documents/GitHub/tradewinds/.claude/worktrees/jolly-spence-35a47d/packages/core/pyproject.toml` — `version = "0.1.0a1"` → `version = "0.1.0"`.
  - EDIT: `/Users/helloiamvu/Documents/GitHub/tradewinds/.claude/worktrees/jolly-spence-35a47d/packages/weather/pyproject.toml` — `version = "0.1.0a1"` → `version = "0.1.0"`.
  - EDIT: `/Users/helloiamvu/Documents/GitHub/tradewinds/.claude/worktrees/jolly-spence-35a47d/packages/markets/pyproject.toml` — `version = "0.1.0a1"` → `version = "0.1.0"`.
  - EDIT: `/Users/helloiamvu/Documents/GitHub/tradewinds/.claude/worktrees/jolly-spence-35a47d/tests/test_packaging.py` — update version-pin assertions to lock all three at `0.1.0` final (currently lock `0.1.0a1`). Both lower-bound (`>=0.1.0`) and upper-bound (`<0.2`) pins MUST be present in dependency declarations between the three packages — `tests/test_packaging.py:test_*_pins_core_to_matching_alpha` (lines 159-195 per RESEARCH) — extend tests so the asserted lower bound is `>=0.1.0` (not the alpha form) and upper bound is `<0.2`.
  - EDIT: `/Users/helloiamvu/Documents/GitHub/tradewinds/.claude/worktrees/jolly-spence-35a47d/CHANGELOG.md` — append entries for Phases 2, 2.1, 3, 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, and Phase 4 closeout. The file currently has entries through Phase 1.5 (74 lines per RESEARCH) and must be brought current before tag.

- **Action — Pitfall 1 guard (RESEARCH §"Common Pitfalls" #1):** the three pyproject versions MUST be bumped in lockstep IN A SINGLE COMMIT. The `Verify tag matches version` step in `release.yml` (Wave 3) asserts that the git tag matches `packages/core/pyproject.toml` `[project] version`. If any of weather/markets diverges from core, the wheel filename will mismatch the tag and PyPI's filename immutability bites.

  Verify lockstep with:
  ```bash
  grep -h 'version =' packages/core/pyproject.toml packages/weather/pyproject.toml packages/markets/pyproject.toml | sort -u | wc -l
  # Must equal 1 (all three versions identical).
  ```

- **Action — CHANGELOG.md structure (Keep a Changelog format):** Append to the existing file. For each completed phase since Phase 1.5 closeout, add one section under `## [0.1.0]` (the target unreleased section). Group by phase number. Reference RESEARCH §"Current Repo State" + the per-phase SUMMARY.md files in each `.planning/phases/*/` directory (read them; do not invent entries).

  Suggested structure (NOT VERBATIM — fill from per-phase SUMMARY.md):
  ```markdown
  ## [0.1.0] — 2026-07-05

  ### Added — Phase 2 (Core Primitives + Catalog Adapters)
  - `tradewinds.core.{KnowledgeView, LeakageDetector, validate_dataframe}` (CORE-01, CORE-02, CORE-07, CORE-08).
  - Three canonical schemas registered eagerly: `schema.observation.v1`, `schema.forecast.iem_mos.v1`, `schema.settlement.cli.v1` (CORE-03).
  - `TradewindsError` exception hierarchy + `MostlyRightMCPError` deprecation alias (CORE-04).
  - Five format serializers (dataframe / json / parquet / toon / csv) with roundtrip tests (CORE-05).
  - Four weather catalog adapters (iem, awc, cli, ghcnh) emitting canonical-schema rows with `event_time` + `knowledge_time` + `source` + `retrieved_at` overlay columns (CATALOG-01..05).
  - `KALSHI_SETTLEMENT_STATIONS` constant + `kalshi_nhigh`/`kalshi_nlow` contract specs (MARKETS-01..03).

  ### Added — Phase 2.1 (Sprint 2o Lineage Refactor)
  - {one bullet per LINEAGE-NN requirement — read .planning/phases/02.1*/SUMMARY.md}

  ### Added — Phase 3 (Mode 2 Integration + Migration Gate)
  - {bullets per RESEARCH-NN, CACHE-NN, MIGRATION-NN requirements}

  ### Added — Phase 3.1 (International Station Expansion + Daily Extremes)
  - {INTL-01..05}

  ### Added — Phase 3.2 (Multi-Forecast HRRR + GFS + NBM via NOAA BDP)
  - {NWP-01..06}

  ### Added — Phase 3.3 (Polymarket Discovery + Settlement)
  - {POLY-01..05}

  ### Added — Phase 3.4 (QC Engine Alpha + Sidecar + Crosscheck)
  - {QC-01..05}

  ### Added — Phase 3.5 (Transforms DSL + Preprocessing Primitives)
  - {TRANSFORM-01..04}

  ### Added — Phase 3.6 (Discovery API + Public Settlement + DataVersion)
  - {DISCOVERY-01..03, SETTLEMENT-API-01, VERSION-01}

  ### Added — Phase 4 (Coverage, Docs, CI/CD, Release)
  - tradewinds.core.* branch coverage gate at ≥90% via `[tool.coverage.report] fail_under = 90` (PKG-01 prereq).
  - NumPy-style doctests on `research()`, `KnowledgeView`, `LeakageDetector`, `validate_dataframe` (DOCS-01).
  - 4-adapter knowledge-resource pages at `docs/adapters/{iem,awc,cli,ghcnh}.md` (DOCS-03).
  - README quickstart expanded for <5-min fresh-installer flow (DOCS-02).
  - GH Actions: `test.yml` (push + PR matrix), `release.yml` (v* trusted publishing), `release-testpypi.yml` (rc* dry-run), `drift-rotate.yml` (weekly cron) (CI-01, CI-02, CI-04, CI-05).
  - `scripts/check_wheel_metadata.py` (CI-02) inspects built wheels' `Requires-Dist` for sibling-pin compliance.
  - Two-tier fixture policy documented in `tests/fixtures/README.md` (CI-05).
  - **Released as `0.1.0` to PyPI for all three distributions: `tradewinds`, `tradewinds-weather`, `tradewinds-markets` (PKG-01).**

  ### Removed
  - `packages/core/src/tradewinds/_internal/_toon.py` — duplicate of `core/formats/_toon.py`; only 2 internal callers; deleted in Wave 1.
  ```

- **Atomic commits (3):**
  1. `chore(PKG-01): bump all three pyproject versions 0.1.0a1 → 0.1.0` — touches 3 pyproject.toml files in one commit (Pitfall 1 lockstep guard).
  2. `test(PKG-03): extend version-pin assertions to lock at 0.1.0` — updates `tests/test_packaging.py`; full packaging test green.
  3. `docs(phase-4): CHANGELOG entries for Phases 2 → 3.6 + Phase 4 plan` — fills in the 9 missing phase entries from per-phase SUMMARY.md files.

- **Codex review priority:** HIGH (pyproject dependency floors are on REVIEW-DISCIPLINE.md never-skip list; CHANGELOG entries describe what users see at install time and must accurately reflect shipped functionality).

- **Test bar:**
  - `uv run pytest tests/test_packaging.py -v` — all assertions green at new version.
  - `grep -h 'version =' packages/core/pyproject.toml packages/weather/pyproject.toml packages/markets/pyproject.toml | sort -u | wc -l` → 1.
  - `uv build --all-packages` produces exactly 3 wheels with `0.1.0` in filenames (NOT `0.1.0a1`).
  - CHANGELOG.md syntactically valid Keep-a-Changelog format; each phase has at least one bullet.

### Wave 1 Success Criteria

- [ ] `uv run pytest -m "not live" --cov=tradewinds.core --cov-branch --cov-fail-under=90` exits 0 (HARD GATE for ROADMAP Phase 4 SC #1).
- [ ] `uv run pytest tests/test_parity.py` — all 5 byte-equivalent fixtures green (Phase 1 gate preserved).
- [ ] `uv run pytest --doctest-modules <4 explicit module paths>` exits 0.
- [ ] `packages/{core,weather,markets}/pyproject.toml` all carry `version = "0.1.0"` (lockstep).
- [ ] `tests/test_packaging.py` green at `0.1.0` final.
- [ ] `_internal/_toon.py` deleted; `grep -r "_internal._toon" packages/` empty.
- [ ] CHANGELOG.md has entries for all 9 phases since Phase 1.5 + Phase 4 plan entry.
- [ ] Wave 1 branch merges to `phase-4/integration` with full test suite green (`pytest packages/ tests/ -m "not live"`).

</wave>

<wave id="2" name="README quickstart + 4 adapter doc pages">

**Day:** Day 43
**Branch:** `phase-4/wave-2-docs` off updated `phase-4/integration` (after Wave 1 merges).
**Parallelism:** 2 sub-branches (README || 4 adapter pages — independent files).
**Estimated effort:** 1 day.
**Delivers:** DOCS-02 (README quickstart), DOCS-03 (4 adapter knowledge-resource pages)

### Goal

Expand README.md from the current 46 lines (alpha1 quickstart) to ~120 lines covering: install, smoke, first `research()` call with expected-output block, packages table, caching + env vars, links to docs/. Write 4 adapter knowledge-resource pages in `docs/adapters/` covering schema, gotchas, timezone handling, source-pairing rules, cache layout — one page per source ID family.

### Dependencies

- Wave 1 merged to `phase-4/integration` (we want the bumped version + the import cleanups visible to README install examples).
- No external dependencies.

### Tasks

#### Task 2.1: README.md expansion to <5-min quickstart [sub-branch A]

- **Branch:** `phase-4/wave-2-docs/readme` off `phase-4/wave-2-docs`.
- **Files:**
  - EDIT: `/Users/helloiamvu/Documents/GitHub/tradewinds/.claude/worktrees/jolly-spence-35a47d/README.md` (46 → ~120 lines).

- **Action — Section structure (RESEARCH §"README Quickstart" verbatim, adapted):**
  1. **Header** — 1-liner what-this-is + badges row (PyPI version, Python versions, License, CI status).
  2. **Quickstart (< 5 minutes)** — 3 sub-sections:
     - 1. Install (30 sec): `pip install tradewinds tradewinds-weather tradewinds-markets` + uv equivalent.
     - 2. Smoke test (10 sec): `python -c "import tradewinds; print(tradewinds.__version__)"` → expected `0.1.0`.
     - 3. First research call (3 min): `import tradewinds as tw; df = tw.research("KNYC", "2025-01-06", "2025-01-12"); print(df.head())` + expected DataFrame block copy-pasted from `tests/fixtures/parity/case_1_KNYC_2025-01-06_2025-01-12.parquet` (first 5 rows, real values — RESEARCH §"README Quickstart").
  3. **What You Get** — bullets covering DataFrame columns + settlement-window joins + byte-equivalent v0.14.1 parity + source-identity enforcement + temporal-safety primitives.
  4. **Packages** — 3-row table: `tradewinds` (core + research + temporal), `tradewinds-weather` (catalog adapters + cache + fetchers), `tradewinds-markets` (Kalshi + Polymarket contract specs).
  5. **Caching, configuration, env vars** — brief mention of `TRADEWINDS_CACHE_DIR`, `filelock`, cache-skip rules (LST current-month, 30-day volatile window, `*.live` never cached).
  6. **More** — links to `docs/adapters/`, `docs/design.md`, `.planning/REQUIREMENTS.md`.
  7. **License** — MIT (one line).

- **Action — Pick the right `research()` example window:** RESEARCH §"External-Person Timing" confirms 1-week KNYC window completes in <50s after Phase 1.5 PERF-04. Use `KNYC` `2025-01-06` `2025-01-12` (matches `tests/fixtures/parity/case_1` — identical input means the README expected-output block can be copy-pasted from the parity fixture for byte accuracy).

- **Action — Mark example output as illustrative, not test-runnable:** the README is NOT collected by `--doctest-modules` (Wave 3's CI step only targets 4 specific .py modules). However, the README output block should be byte-accurate against the parity fixture so a fresh installer can verify reality matches docs:
  ```python
  >>> df = tw.research("KNYC", "2025-01-06", "2025-01-12")
  >>> print(df.head())
  # (paste actual first 5 rows from tests/fixtures/parity/case_1_*.parquet here)
  ```

- **Action — External-person timing gate scheduling (RESEARCH §"External-Person Timing", ROADMAP SC #2):** identify a willing external timer (NOT Vu, NOT Robert) and schedule a Wave 5 dry-run (after rc1 is up on TestPyPI). Pick someone with `pip` and Python 3.11+ on their machine but no `tradewinds` familiarity. Provide a stopwatch instruction and an expected-output checklist. If the timer exceeds 5 min, the planner loops on README until the bottleneck is fixed:
  - Install >2 min → reduce dep tree or document `[parquet]` extra more prominently.
  - First `research()` >3 min → use a smaller window or pre-warm the parity fixture as a `tradewinds.research.from_parity_fixture("case_1")` shortcut (preferable as a `tradewinds-examples` extras).

- **Atomic commit:** `docs(DOCS-02): expand README to <5-min quickstart (install + smoke + research + packages)`.

- **Codex review priority:** MEDIUM (prose; not on REVIEW-DISCIPLINE.md never-skip list, but the install commands + version strings + the parity-fixture output block are all factually load-bearing — if the install command is wrong, every fresh user fails; if the output block doesn't match the actual parity fixture, the README lies).

- **Test bar:**
  - `wc -l README.md` returns a count in `[100, 140]` (target ~120; allow 20% headroom).
  - Visual inspection: pasted parity output rows match `tests/fixtures/parity/case_1_KNYC_2025-01-06_2025-01-12.parquet` head().
  - `markdownlint README.md` (if available) returns clean.
  - **External timer dry-run** scheduled for Wave 5 — recorded in `phase-4/integration` PR description as a blocker for `phase-4/integration` → `main` merge.

#### Task 2.2: Four adapter doc pages — iem.md, awc.md, cli.md, ghcnh.md [sub-branch B]

- **Branch:** `phase-4/wave-2-docs/adapter-pages` off `phase-4/wave-2-docs`.
- **Files (all NEW):**
  - CREATE: `/Users/helloiamvu/Documents/GitHub/tradewinds/.claude/worktrees/jolly-spence-35a47d/docs/adapters/iem.md`
  - CREATE: `/Users/helloiamvu/Documents/GitHub/tradewinds/.claude/worktrees/jolly-spence-35a47d/docs/adapters/awc.md`
  - CREATE: `/Users/helloiamvu/Documents/GitHub/tradewinds/.claude/worktrees/jolly-spence-35a47d/docs/adapters/cli.md`
  - CREATE: `/Users/helloiamvu/Documents/GitHub/tradewinds/.claude/worktrees/jolly-spence-35a47d/docs/adapters/ghcnh.md`

- **Action — Page template (RESEARCH §"Page Template" verbatim) per page (~80-150 lines each):**

  ```markdown
  # {Adapter Name}

  ## Overview
  - **Source ID:** `{e.g., iem.archive}` / `{e.g., iem.live}`
  - **Provider:** {Iowa Environmental Mesonet / NOAA AWC / NWS / NCEI}
  - **License:** {public-domain via NWS / NOAA}
  - **Endpoint:** {URL pattern + post-Sept-2025 migration note for AWC}
  - **Catalog module:** `tradewinds.weather.catalog.{adapter}`
  - **Fetcher module:** `tradewinds.weather._fetchers.{adapter}`
  - **Parser module:** `tradewinds.weather._{adapter}`

  ## Canonical Schema
  Output rows conform to `schema.{observation|settlement}.v1`. Per-source field mappings:

  | Canonical column | Source field | Notes |
  |------------------|--------------|-------|
  | `temp_c` | `tmpf` (in °F, converted in `_internal._convert`) | |
  | ... | ... | ... |

  ## Gotchas
  - {endpoint migrations}
  - {data quality quirks — e.g., GHCNh PSV uses pipe-separated, NOT tab}
  - {rate limits — IEM = 1 req/sec etiquette per `.planning/research/SOURCE-LIMITS.md`}
  - {known data gaps — AWC `hours=168` ceiling = 7 days only}
  - {missing-data sentinels — IEM `M` → `pd.NA`, NOT 0 or np.nan (Pitfall 8)}

  ## Timezone Handling
  - {source returns UTC / local / mixed?}
  - {tradewinds normalizes to UTC at parse time — cite the conversion function in source}
  - {DST handling for daily-extremes / settlement-window callers}

  ## Source-Pairing Rules
  - Priority vs other sources: {AWC > IEM > GHCNh on observation merge; CLI is settlement-only}
  - Tie-break: strict-`>` first-seen-wins per v0.14.1 parity (lifted at `_internal/merge/observations.py`)
  - US-only vs international coverage: {AWC US-CONUS only; IEM > GHCNh for non-US after Phase 3.1}

  ## Cache Layout
  - Parquet at `~/.tradewinds/cache/v1/{path}/{station}/{year}/{month}.parquet`
  - Cache-skip rules: LST current-month, 30-day volatile window, `*.live` never cached
  - `filelock`-guarded per CACHE-02; cloud-sync FS auto-detected (iCloud/Dropbox → `SoftFileLock` fallback)

  ## See Also
  - `docs/adapters/{other}.md` cross-references
  - Source-of-truth code: `packages/weather/src/tradewinds/weather/catalog/{adapter}.py`
  - `.planning/research/SOURCE-LIMITS.md` (Phase 1.5 spike output)
  ```

- **Action — Page-specific content (NOT generic; read the actual code):**

  - **`iem.md`** — IEM as vendor (3 source IDs: `iem.archive` + `iem.live` for observations; CLI hosted as JSON mirror at `iem.cli.mirror`). Cite `_fetchers/iem_asos.py` 365-day chunker (Phase 1.5). Pitfall 8 (`M` sentinel). Endpoint: `https://mesonet.agron.iastate.edu/api/1/`. Cross-reference `cli.md` for the CLI product source-of-truth.
  - **`awc.md`** — Source ID: `awc.live`. Post-Sept-2025 endpoint migration: `/cgi-bin/data/metar.php` → `/api/data/metar` (the LIFT-FIX in `_fetchers/awc.py` per Phase 1). US-CONUS only. `hours=168` (7 days) ceiling on the API. Visibility `M1/4` prefix handling in `_awc.py:88`. Pitfall: no `awc.archive` in v0.1 (R9 — IEM provides historical depth).
  - **`cli.md`** — Source ID: `cli.archive`. Settlement source for Kalshi NHIGH/NLOW. Lives at IEM's mirror but the DATA is NWS CLI. `REPORT_TYPE_PRIORITY` dedup (prelim/final/correction; lifted from v0.14.1 `pairs.py`). `cli_data_quality` enum (Pitfall 6, REMARKS regex). `settlement_finality` enum (Pitfall 16). Station-local IANA tz mapping at `catalog/_cli_station_tz.py`. DST-boundary issuance handling.
  - **`ghcnh.md`** — Source ID: `ghcnh.archive`. NCEI Global Hourly. Pipe-separated PSV format (NOT tab). Historical depth, low LIVE_V1 priority (GHCNh=1 < IEM=2 < AWC=3). International coverage post-Phase 3.1. NCEI excluded from live priority per CLAUDE.md ("NCEI excluded from live due to latency").

- **Action — Cross-reference discipline:** every page ends with a "See Also" block linking to the other 3 adapters + relevant source modules. The IEM↔CLI cross-reference is mandatory (RESEARCH §"Adapter Docs" overlap issue) — `iem.md` notes the CLI JSON mirror lives on IEM infrastructure; `cli.md` notes the CLI product comes from NWS but is fetched via IEM.

- **Atomic commits (4 — one per page):**
  1. `docs(DOCS-03): adapter knowledge-resource page for IEM (iem.archive + iem.live)`.
  2. `docs(DOCS-03): adapter knowledge-resource page for AWC METAR JSON (post-Sept-2025 endpoint)`.
  3. `docs(DOCS-03): adapter knowledge-resource page for NWS CLI (cli.archive, settlement source)`.
  4. `docs(DOCS-03): adapter knowledge-resource page for NCEI GHCNh (international historical)`.

- **Codex review priority:** MEDIUM (prose-heavy but the schema mapping tables + source-priority numbers + Pitfall references must be technically accurate against code — `awc:3 / iem:2 / ghcnh:1` per CLAUDE.md and `_internal/merge/observations.py`; a typo here is on REVIEW-DISCIPLINE.md never-skip list).

- **Test bar:**
  - All 4 files exist; `wc -l docs/adapters/*.md` reports each in `[60, 180]`.
  - Schema mapping tables actually match what `packages/weather/src/tradewinds/weather/catalog/{adapter}.py` emits — verify by `grep -A3 "schema.observation.v1" packages/weather/src/tradewinds/weather/catalog/iem.py` and confirming the columns table is accurate.
  - Source-priority numbers in pairing-rules sections match `_internal/merge/observations.py` SOURCE_PRIORITY constant (AWC=3, IEM=2, GHCNh=1).
  - No broken cross-references (each "See Also" target file exists).

### Wave 2 Success Criteria

- [ ] README.md expanded from 46 → ~120 lines covering install → smoke → research → packages → caching → links.
- [ ] 4 files exist at `docs/adapters/{iem,awc,cli,ghcnh}.md`, each with the 7-section template.
- [ ] External-person README timing dry-run scheduled and tracked in `phase-4/integration` PR description.
- [ ] Wave 2 branch merges to `phase-4/integration` with full test suite green.

</wave>

<wave id="3" name="GH Actions workflows + check_wheel_metadata.py script">

**Day:** Day 44
**Branch:** `phase-4/wave-3-ci-workflows` off updated `phase-4/integration`.
**Parallelism:** 2 sub-branches (workflows || script — independent files, but workflows reference the script so workflows depend on script merging first within the wave branch).
**Estimated effort:** 1 day.
**Delivers:** CI-01 (test on push + release on tag), CI-02 (METADATA grep), CI-03 (pre-commit unchanged — already configured), CI-04 (`pytest -m "not live"` in CI; `@pytest.mark.live` excluded), DOCS-01 wiring (doctest CI step).

### Goal

Create the three GH Actions workflows (`test.yml` for CI on push + PR, `release.yml` for v* tag → prod PyPI trusted publishing, `release-testpypi.yml` for rc* tag → TestPyPI dry-run) and the standalone `scripts/check_wheel_metadata.py` (CI-02). All three workflows share infrastructure patterns: `astral-sh/setup-uv@v6`, `actions/checkout@v5`, OIDC trusted publishing (no API tokens), `uv build --all-packages` (NOT bare `uv build` — Pitfall 3).

### Dependencies

- Wave 1 merged (coverage gate + doctests + bumped versions must be in place — `test.yml` runs them).
- Wave 2 merged (README + adapter docs — no workflow dependency, but `phase-4/integration` accumulation order).
- **OPERATOR GATE (cannot merge to `phase-4/integration` without):** PyPI pending publishers for all 3 distributions registered (Open Question Q-04). See Wave 5 Task 5.1 for the registration form values. Phase 4 plan recommends operator does this Day 42 (parallel to Wave 1) to shrink the name-squatting risk window. If alpha1 is already on PyPI (Open Question Q-05), pending publishers become per-project trusted publishers — simpler, but still requires the operator UI registration.

### Tasks

#### Task 3.0: `scripts/check_wheel_metadata.py` standalone CLI [sub-branch A, kicks off wave]

- **Branch:** `phase-4/wave-3-ci-workflows/wheel-metadata-script` off `phase-4/wave-3-ci-workflows`. Merge into wave branch BEFORE workflows sub-branch starts (workflows reference this script).
- **Files:**
  - CREATE: `/Users/helloiamvu/Documents/GitHub/tradewinds/.claude/worktrees/jolly-spence-35a47d/scripts/check_wheel_metadata.py` (~100 LOC).
  - CREATE: `/Users/helloiamvu/Documents/GitHub/tradewinds/.claude/worktrees/jolly-spence-35a47d/tests/test_check_wheel_metadata.py` (~80 LOC).

- **Action — Script content (RESEARCH §"METADATA Grep CI" verbatim):**
  Write the script per the RESEARCH-provided source (lines 705-774). Key behavior:
  1. Takes `dist/` directory as single positional arg; usage: `check_wheel_metadata.py <dist-dir>`.
  2. For each `*.whl` in the directory: opens via `zipfile.ZipFile`, locates `*.dist-info/METADATA`, decodes UTF-8.
  3. Parses `Requires-Dist:` lines matching pattern `^Requires-Dist:\s*(tradewinds(?:-weather|-markets)?)\s*\(?(.*?)\)?$` (multiline regex).
  4. For each sibling `tradewinds-*` dep: asserts both `>=\s*0\.1\.0(?:\D|$)` AND `<\s*0\.2(?:\D|$)` present.
  5. Exits 1 with `ERROR: {wheel}: {dep} missing {bound} ({spec})` per violation; exits 0 on success.
  6. Self-references are skipped (`tradewinds` wheel's own line is not checked).

- **Action — Test the script before committing it:**
  ```bash
  # First commit: write the script.
  # Then run uv build --all-packages locally.
  uv build --all-packages
  uv run python scripts/check_wheel_metadata.py dist/
  # Expected: "OK: 3 wheel(s) pass METADATA check" with exit code 0.
  ```

- **Action — Write test:** `tests/test_check_wheel_metadata.py` covers:
  - PASS case: synthesize a `.whl`-like zip with valid `METADATA` containing `Requires-Dist: tradewinds-weather (>=0.1.0,<0.2)`; script returns 0.
  - FAIL case (missing lower bound): `Requires-Dist: tradewinds-weather (<0.2)`; script returns 1 with stderr line about missing `>=0.1.0`.
  - FAIL case (missing upper bound): `Requires-Dist: tradewinds-weather (>=0.1.0)`; script returns 1 with stderr line about missing `<0.2`.
  - FAIL case (loose pin): `Requires-Dist: tradewinds-weather`; script returns 1 for both bounds.
  - Edge: no `tradewinds-*` deps in METADATA at all → returns 0 (the core wheel itself).

- **Atomic commits (2):**
  1. `feat(CI-02): scripts/check_wheel_metadata.py — built-wheel Requires-Dist grep`.
  2. `test(CI-02): unit tests for check_wheel_metadata script (PASS + missing-lower + missing-upper + loose)`.

- **Codex review priority:** HIGH (release-gate enforcement script; if the regex is wrong, the CI step exits 0 on bad wheels and the bad wheels still publish; if the regex is too strict, valid wheels block the release. Both have downstream consequences. On REVIEW-DISCIPLINE.md never-skip list as "anything touching pyproject.toml dependency floors" via its CI enforcement role).

- **Test bar:**
  - `uv run pytest tests/test_check_wheel_metadata.py -v` — all 5 cases green.
  - `uv build --all-packages && uv run python scripts/check_wheel_metadata.py dist/` exits 0.

#### Task 3.1: `.github/workflows/test.yml` — CI on push + PR [sub-branch B, part 1]

- **Branch:** `phase-4/wave-3-ci-workflows/workflows` off `phase-4/wave-3-ci-workflows` (after Task 3.0 merges).
- **Files:**
  - CREATE: `/Users/helloiamvu/Documents/GitHub/tradewinds/.claude/worktrees/jolly-spence-35a47d/.github/workflows/test.yml`.

- **Action — Content (RESEARCH §"Test Workflow" verbatim, lines 818-889):** assemble three jobs:

  **Job 1 — `test`** (matrix: ubuntu 3.11 + ubuntu 3.12 + ubuntu 3.13 + macOS 3.12 per Open Question Q-07 default):
  - `actions/checkout@v5`
  - `astral-sh/setup-uv@v6` with `enable-cache: true`
  - `uv python install ${{ matrix.python-version }}`
  - `uv sync --all-extras --dev`
  - Run tests with coverage:
    ```bash
    uv run pytest -m "not live" \
      --cov=tradewinds.core \
      --cov-branch \
      --cov-report=term-missing \
      --cov-fail-under=90
    ```
  - Run doctests (4 explicit modules per Wave 1 Task 1.2):
    ```bash
    uv run pytest --doctest-modules \
      packages/core/src/tradewinds/research.py \
      packages/core/src/tradewinds/core/temporal/knowledge_view.py \
      packages/core/src/tradewinds/core/temporal/leakage.py \
      packages/core/src/tradewinds/core/validator.py
    ```

  **Job 2 — `lint`** (ubuntu only, fast):
  - `ruff check .`
  - `ruff format --check .`

  **Job 3 — `mypy`** (ubuntu only; **`continue-on-error: true` per Open Question Q-02 recommendation — soft gate for v0.1.0**):
  - `uv run mypy --strict packages/core/src/tradewinds/core/`

- **Action — Trigger config:**
  ```yaml
  on:
    push:
      branches: [main, "phase-*/integration", "phase-*/wave-*"]
    pull_request:
      branches: [main]
  concurrency:
    group: test-${{ github.ref }}
    cancel-in-progress: true
  ```

- **Action — `@pytest.mark.live` exclusion (CI-04):** Default `addopts` in workspace `pyproject.toml` already includes `-m 'not live'` (verified). The explicit `-m "not live"` in the workflow command is redundant but defensive (RESEARCH §"Test Workflow") — keep it so the workflow is config-independent.

- **Action — One-shot mypy probe before merging:** as a pre-merge step on this sub-branch, run `uv run mypy --strict packages/core/src/tradewinds/core/` locally. Count issues. If clean (0-2 issues), flip `continue-on-error: false` (promote to required gate). If many issues (20+), leave as soft gate and file a v0.2 follow-up issue: "Tighten mypy --strict on tradewinds.core/". Document the decision in the commit message.

- **Atomic commit:** `feat(CI-01+CI-04): test.yml — push+PR matrix (3.11/3.12/3.13 + macOS) + coverage gate + doctests + lint + soft mypy`.

- **Codex review priority:** HIGH (workflow YAML — wrong matrix or wrong fail-under value silently downgrades the gate; on REVIEW-DISCIPLINE.md never-skip list as "schema fragments / threshold numbers" — `--cov-fail-under=90` is the load-bearing literal).

- **Test bar:**
  - `actionlint test.yml` (if available locally) returns clean. Otherwise visual review against the trusted-publishing-examples reference repo.
  - YAML syntactically valid (`yq . .github/workflows/test.yml > /dev/null` exits 0).
  - **CI dry-run verification:** push the wave branch and confirm `test.yml` actually fires and goes green. If it fails on the matrix (e.g., 3.11-specific issue), fix on the branch before merging to `phase-4/integration`. Same goes for the coverage gate triggering at >90%.

#### Task 3.2: `.github/workflows/release.yml` — v* tag → prod PyPI [sub-branch B, part 2]

- **Branch:** continues `phase-4/wave-3-ci-workflows/workflows`.
- **Files:**
  - CREATE: `/Users/helloiamvu/Documents/GitHub/tradewinds/.claude/worktrees/jolly-spence-35a47d/.github/workflows/release.yml`.
  - CREATE: `/Users/helloiamvu/Documents/GitHub/tradewinds/.claude/worktrees/jolly-spence-35a47d/tests/smoke_post_publish.py` (used in workflow's smoke step).

- **Action — Workflow content (RESEARCH §"Recommended `release.yml`" verbatim, lines 540-604):** two jobs:

  **Job 1 — `build`:**
  - `actions/checkout@v5`
  - `astral-sh/setup-uv@v6`
  - `uv python install 3.13`
  - **Verify tag matches version (Pitfall 1):**
    ```bash
    TAG="${GITHUB_REF_NAME#v}"
    VERSION=$(uv run python -c "import tomllib, pathlib; print(tomllib.loads(pathlib.Path('packages/core/pyproject.toml').read_text())['project']['version'])")
    test "$TAG" = "$VERSION" || (echo "Tag $TAG != core version $VERSION" && exit 1)
    ```
  - `uv build --all-packages` (NOT bare `uv build` — Pitfall 3).
  - Sanity: `test $(ls dist/*.whl | wc -l) -eq 3`.
  - **Verify wheel METADATA (CI-02 — uses Task 3.0 script):** `uv run python scripts/check_wheel_metadata.py dist/`.
  - **Smoke install all 3 wheels** (RESEARCH §"Smoke tests"):
    ```bash
    uv run --isolated --no-project \
      --with dist/tradewinds-*.whl \
      --with dist/tradewinds_weather-*.whl \
      --with dist/tradewinds_markets-*.whl \
      python -c "import tradewinds; import tradewinds.weather; import tradewinds.markets; print(tradewinds.__version__)"
    ```
  - `actions/upload-artifact@v4` → `dist/`.

  **Job 2 — `publish`** (`needs: build`, `environment: pypi`, `permissions: id-token: write, contents: read`):
  - `astral-sh/setup-uv@v6`
  - `actions/download-artifact@v4` → `dist/`
  - `uv publish` (defaults: uploads all 6 files in `dist/` — 3 wheels + 3 sdists; OIDC token authenticates against the 3 trusted publishers registered on pypi.org).

- **Action — Trigger:**
  ```yaml
  on:
    push:
      tags:
        - v*
  concurrency:
    group: release-${{ github.ref }}
    cancel-in-progress: false  # Don't cancel mid-release!
  ```

- **Action — `tests/smoke_post_publish.py` content (~30 LOC):** minimal post-publish smoke that the publish job CAN optionally run after upload (currently not wired — see Pitfall 4 + Pitfall 6 mitigation in Wave 5 below). Content:
  ```python
  """Post-publish smoke: install from PyPI + import + minimal research() shape check."""
  import subprocess, sys
  subprocess.check_call([sys.executable, "-m", "pip", "install",
      "tradewinds", "tradewinds-weather", "tradewinds-markets"])
  import tradewinds
  assert tradewinds.__version__ == "0.1.0", f"Got {tradewinds.__version__}"
  print("post-publish smoke: OK")
  ```

- **Action — Pitfall 2 mitigation (environment name match):** Document at the top of `release.yml` in a YAML comment:
  ```yaml
  # CRITICAL: `environment: pypi` MUST match the environment name registered
  # in pypi.org pending publisher form (operator step, Wave 5 prereq).
  # See .planning/phases/04-coverage-docs-cicd-release/PLAN.md Wave 5 Task 5.1.
  # Mismatch silently fails OIDC handshake with "no matching trusted publisher".
  ```

- **Atomic commit:** `feat(CI-01+PKG-01): release.yml — v* tag → uv build --all-packages → METADATA check → smoke → uv publish (OIDC trusted publishing)`.

- **Codex review priority:** HIGH (release-gate workflow; wrong on-tag pattern OR wrong `environment:` value silently breaks publish; `uv build` (bare) vs `uv build --all-packages` is Pitfall 3 with zero-wheel publish failure; all release-mechanics literals on REVIEW-DISCIPLINE.md never-skip list).

- **Test bar:**
  - YAML syntactically valid.
  - **Cannot fully test until Wave 5 — but partial verification:** verify the `Verify tag matches version` step with a hand-rolled local test:
    ```bash
    export GITHUB_REF_NAME=v0.1.0
    TAG="${GITHUB_REF_NAME#v}"
    VERSION=$(uv run python -c "import tomllib, pathlib; print(tomllib.loads(pathlib.Path('packages/core/pyproject.toml').read_text())['project']['version'])")
    test "$TAG" = "$VERSION" && echo OK
    ```
    Should print `OK` after Wave 1 version bump.

#### Task 3.3: `.github/workflows/release-testpypi.yml` — rc* tag → TestPyPI dry-run [sub-branch B, part 3]

- **Branch:** continues `phase-4/wave-3-ci-workflows/workflows`.
- **Files:**
  - CREATE: `/Users/helloiamvu/Documents/GitHub/tradewinds/.claude/worktrees/jolly-spence-35a47d/.github/workflows/release-testpypi.yml`.

- **Action — Identical to `release.yml` (Task 3.2) except:**
  1. Trigger: `tags: ["*rc*"]` (any tag containing `rc` — matches `v0.1.0rc1`, `v0.1.0rc2`, etc.).
  2. Environment: `testpypi` (separate GH environment with separate pending-publisher registration on test.pypi.org).
  3. Publish step: `uv publish --publish-url https://test.pypi.org/legacy/`.
  4. Skip the `Verify tag matches version` step OR loosen it to allow `0.1.0rc1` matching `0.1.0` (the pyproject doesn't carry an `rc1` suffix; the tag does). Actually — easier: pyproject stays at `0.1.0` for both rc1 AND final; the wheel filename is `tradewinds-0.1.0rc1-...` IFF the version-bump step in this workflow injects the rc suffix; OR easier still: keep pyproject at `0.1.0` and use this workflow to publish `0.1.0` wheels to TestPyPI under a tag NAMED `v0.1.0rc1` but with the same `0.1.0` version. TestPyPI doesn't enforce semantic version uniqueness against production — but does enforce filename immutability within TestPyPI. So if we publish `0.1.0` to TestPyPI under `v0.1.0rc1` tag, we cannot republish `0.1.0` after fixing a bug. Either we (a) bump pyproject to `0.1.0rc1` temporarily and revert before final tag, or (b) accept that TestPyPI runs are one-shot per version.

  **DECISION (per Open Question Q-04, recommend rc1 → TestPyPI workflow):** Use approach (a) — when tagging `v0.1.0rc1`, FIRST bump pyproject versions to `0.1.0rc1` in a temporary commit on the release branch, tag, publish to TestPyPI, then revert pyproject to `0.1.0` and create the `v0.1.0` tag for production. This is Wave 5 task work; this workflow file is the YAML that fires on the rc tag.

- **Atomic commit:** `feat(CI-01+PKG-01): release-testpypi.yml — rc* tag → TestPyPI dry-run`.

- **Codex review priority:** MEDIUM (parallel workflow; same considerations as release.yml but operates on TestPyPI which has fewer downstream consequences).

- **Test bar:** YAML syntactically valid; trigger pattern `*rc*` matches `v0.1.0rc1` (test with `gh workflow list` or manual trigger).

### Wave 3 Success Criteria

- [ ] `.github/workflows/test.yml` lives on `phase-4/integration`; first-push run on the wave branch went green.
- [ ] `.github/workflows/release.yml` lives on `phase-4/integration`; tag-matches-version step locally verified at v0.1.0.
- [ ] `.github/workflows/release-testpypi.yml` lives on `phase-4/integration`.
- [ ] `scripts/check_wheel_metadata.py` exists; `uv build --all-packages && uv run python scripts/check_wheel_metadata.py dist/` exits 0.
- [ ] `tests/test_check_wheel_metadata.py` green.
- [ ] **OPERATOR GATE COMPLETE:** All 3 PyPI pending publishers registered (verified by operator UI check) — recorded in `phase-4/integration` PR description.
- [ ] Wave 3 branch merges to `phase-4/integration` with full test suite green + actionlint clean on all 3 workflow files.

</wave>

<wave id="4" name="Two-tier fixtures policy + drift scaffolding + drift-rotate workflow">

**Day:** Day 44.5 (half-day; Wave 3 finishes morning, Wave 4 lands afternoon)
**Branch:** `phase-4/wave-4-drift-fixtures` off updated `phase-4/integration`.
**Parallelism:** 1 lane (small surface; tight coupling between drift capture + compare + workflow).
**Estimated effort:** half-day.
**Delivers:** CI-05 (two-tier fixture set with weekly cron-rotated drift)

### Goal

Document the immutability discipline of `tests/fixtures/parity/` in a `tests/fixtures/README.md`. Scaffold `tests/fixtures/drift/` with capture + compare scripts pointed at the CURRENT `tradewinds.research()` implementation (NOT at `mostlyright.client.pairs()` like the parity capture). Wire `.github/workflows/drift-rotate.yml` for a weekly Monday 07:00 UTC cron that captures, diffs against parity, and opens a GH issue on mismatch.

### Dependencies

- Wave 3 merged (drift-rotate.yml uses the same `setup-uv@v6` + cache patterns as test.yml; consistency matters more than strict dependency).
- `tests/fixtures/parity/` exists (verified — 5 parquets + expected_dtypes.json + capture_fixtures.py).

### Tasks

#### Task 4.1: Two-tier policy doc + drift directory scaffold

- **Branch:** `phase-4/wave-4-drift-fixtures` (single lane).
- **Files (all NEW):**
  - CREATE: `/Users/helloiamvu/Documents/GitHub/tradewinds/.claude/worktrees/jolly-spence-35a47d/tests/fixtures/README.md` (~50 lines per RESEARCH §"Recommended tests/fixtures/README.md").
  - CREATE: `/Users/helloiamvu/Documents/GitHub/tradewinds/.claude/worktrees/jolly-spence-35a47d/tests/fixtures/drift/.gitkeep` (placeholder so empty dir is tracked).
  - CREATE: `/Users/helloiamvu/Documents/GitHub/tradewinds/.claude/worktrees/jolly-spence-35a47d/tests/fixtures/drift/capture_drift.py` (~80 LOC; adapted from `tests/fixtures/parity/capture_fixtures.py`).
  - CREATE: `/Users/helloiamvu/Documents/GitHub/tradewinds/.claude/worktrees/jolly-spence-35a47d/tests/fixtures/drift/compare.py` (~100 LOC; np.allclose + dtypes.equals comparison).
  - CREATE: `/Users/helloiamvu/Documents/GitHub/tradewinds/.claude/worktrees/jolly-spence-35a47d/tests/test_drift.py` (~50 LOC; soft pytest assertion).

- **Action — `tests/fixtures/README.md` (RESEARCH §"Recommended tests/fixtures/README.md" verbatim):** state explicitly:
  - `parity/` = FROZEN, NEVER re-record (RESEARCH §"Current State (Tier 1: parity/)"). Re-capture only under a new directory if mostlyright's `client.pairs()` contract changes (e.g., `parity_v0_15/`).
  - `drift/` = ROTATED WEEKLY via cron. Compared against parity; differences logged but DO NOT fail CI (watchdog, not gate).
  - Document the rotation policy: if drift has >0 mismatches for 2 consecutive weeks, file an issue and either update tradewinds to match upstream OR quarantine the case.

- **Action — `capture_drift.py` (RESEARCH-implied, adapted from parity capture):** points at `tradewinds.research()` (NOT `mostlyright.client.pairs()`). For each of the 5 parity cases (same `(station, from_date, to_date)` tuples — `KNYC` 2025-01-06→12, `KMDW` 2025-04-01→30, `KLAX` 2025-03-01→31, `KMIA` 2024-12-01→2025-11-30, `KMSY` 2024-09-08→22), call `research()`, write to `tests/fixtures/drift/case_N_{station}_{from}_{to}.parquet`.

- **Action — `compare.py`:** for each case file present in BOTH parity and drift directories, load both parquets, run `np.allclose(parity, drift, rtol=0, atol=0)` (or per-column allclose for numeric, equals for string/datetime), `parity.dtypes.equals(drift.dtypes)`. Aggregate mismatches into `drift-report.md` (markdown table: case → first mismatching column → sample row → numeric delta). Exit non-zero on any mismatch (so the workflow's `continue-on-error: true` step triggers the issue-opening fallback path).

- **Action — `tests/test_drift.py`:** marked with `pytest.mark.skipif(not (Path("tests/fixtures/drift") / "case_1_KNYC_2025-01-06_2025-01-12.parquet").exists(), reason="No drift fixtures captured yet; cron job populates this directory weekly")`. When fixtures exist, runs `compare.py`'s logic in-process and asserts zero mismatches (soft assertion; the CRON-driven workflow is the canonical surfacing path, this is just a local convenience).

- **Atomic commits (5 — one per file):**
  1. `docs(CI-05): tests/fixtures/README.md — two-tier policy (parity frozen / drift cron-rotated)`.
  2. `chore(CI-05): scaffold tests/fixtures/drift/ directory`.
  3. `feat(CI-05): tests/fixtures/drift/capture_drift.py — captures current research() output for 5 cases`.
  4. `feat(CI-05): tests/fixtures/drift/compare.py — diffs parity vs drift, writes drift-report.md`.
  5. `test(CI-05): tests/test_drift.py — soft pytest assertion (skipped on fresh clones)`.

- **Codex review priority:** HIGH (CI-05 deliverable; the parity/drift discipline is parity-critical-adjacent — if compare.py incorrectly reports "no drift" when drift exists, upstream API changes silently corrupt research output downstream. On REVIEW-DISCIPLINE.md never-skip list as "fixture rows / threshold numbers" — np.allclose tolerances are load-bearing literals).

- **Test bar:**
  - `tests/fixtures/README.md` exists and explicitly states "NEVER RE-RECORD" for parity.
  - `tests/fixtures/drift/.gitkeep` exists.
  - `capture_drift.py` is runnable (imports succeed; running it locally with no network → fails on `tradewinds.research()` network call, which is expected behavior — the cron-runner has network).
  - `compare.py` is runnable with synthetic test fixtures (manually construct a 2-row drift parquet matching case_1 parity, assert compare.py reports 0 mismatches; then introduce a 1-cell change, assert compare.py reports 1 mismatch and exits non-zero).
  - `uv run pytest tests/test_drift.py` skips with the documented reason on a fresh clone (drift/ has only `.gitkeep`).

#### Task 4.2: `.github/workflows/drift-rotate.yml`

- **Branch:** continues `phase-4/wave-4-drift-fixtures`.
- **Files:**
  - CREATE: `/Users/helloiamvu/Documents/GitHub/tradewinds/.claude/worktrees/jolly-spence-35a47d/.github/workflows/drift-rotate.yml`.

- **Action — Content (RESEARCH §"Recommended drift-rotate.yml" verbatim, lines 977-1033):**
  - Trigger: `schedule: cron: "0 7 * * 1"` (Mondays 07:00 UTC — Sunday evening Pacific, Monday morning Tokyo) + `workflow_dispatch: {}` (manual trigger for testing).
  - `permissions: contents: write, pull-requests: write` (needs to commit drift fixtures + open issues).
  - Job `rotate`:
    1. `actions/checkout@v5`, `astral-sh/setup-uv@v6`.
    2. `uv python install 3.12`, `uv sync --all-extras`.
    3. Run `tests/fixtures/drift/capture_drift.py --output-dir tests/fixtures/drift/`.
    4. Run `tests/fixtures/drift/compare.py --parity tests/fixtures/parity/ --drift tests/fixtures/drift/ --output drift-report.md` with `continue-on-error: true` (the failure is the signal that drift exists; we want the next step to run).
    5. **If compare.outcome == 'failure':** `actions/github-script@v7` opens an issue titled `Drift detected: {YYYY-MM-DD}` labelled `drift,phase-4` with `drift-report.md` content as body.
    6. Commit drift fixtures to a new branch `drift/YYYY-MM-DD` and push (manual review before merge to main).

- **Action — Pitfall 7 mitigation (RESEARCH §"Common Pitfalls" #7):** before merging, manually trigger the workflow via `gh workflow run drift-rotate.yml` with intentionally mismatched drift fixtures (manually copy `case_1` parity, modify one cell, save as drift). Confirm:
  - `compare.py` exits non-zero.
  - The `if: steps.compare.outcome == 'failure'` condition fires.
  - An issue is actually opened (not silently swallowed).
  - The issue body contains the modified cell + delta.

  Then revert the test fixture before merging the wave.

- **Atomic commit:** `feat(CI-05): drift-rotate.yml — weekly Monday 07:00 UTC capture + diff + auto-issue`.

- **Codex review priority:** HIGH (CI-05 deliverable; soft-failure pattern is easy to over-soften per Pitfall 7; the issue-opening step is the load-bearing watchdog surface).

- **Test bar:**
  - YAML syntactically valid.
  - `actionlint drift-rotate.yml` clean.
  - **Manual trigger test:** push wave branch, `gh workflow run drift-rotate.yml --ref phase-4/wave-4-drift-fixtures`, confirm workflow runs and (with synthetic drift) opens an issue.

### Wave 4 Success Criteria

- [ ] `tests/fixtures/README.md` exists; documents parity/ frozen + drift/ cron-rotated.
- [ ] `tests/fixtures/drift/{capture_drift,compare}.py` exist and runnable.
- [ ] `tests/test_drift.py` exists with `skipif` guard for fresh clones.
- [ ] `.github/workflows/drift-rotate.yml` exists; manual trigger test confirms compare.outcome → issue path works.
- [ ] Wave 4 branch merges to `phase-4/integration` with full test suite green.

</wave>

<wave id="5" name="Pre-publish dry-run (rc1 → TestPyPI) → v0.1.0 tag → prod PyPI → STATE.md close-out">

**Day:** Day 45 (full day; staged execution)
**Branch:** `phase-4/wave-5-release` off updated `phase-4/integration` (after Waves 1-4 all merged).
**Parallelism:** 1 lane (atomic release sequence; operator gates).
**Estimated effort:** 1 day (most of which is wait time on CI + operator UI work + external timer).
**Delivers:** PKG-01 (3 distros at v0.1.0 on PyPI), STATE.md close-out

### Goal

Execute the ship sequence: register PyPI pending publishers (operator), set up GH `pypi` and `testpypi` environments (operator), tag `v0.1.0rc1` → publish to TestPyPI → smoke-test from TestPyPI → external README timer → tag `v0.1.0` → publish to prod PyPI → verify all 3 distros live → STATE.md close-out.

### Dependencies

- Waves 1-4 all merged to `phase-4/integration`.
- Operator gates (recorded in `phase-4/integration` PR description as blocking):
  1. **PyPI pending publishers** for `tradewinds`, `tradewinds-weather`, `tradewinds-markets` registered on pypi.org (Open Question Q-04 + RESEARCH §"What the User (Vu / helloiamvu) Must Do MANUALLY on pypi.org BEFORE Wave 5"). 5 min UI work.
  2. **Separate pending publishers** for the same 3 projects on TEST.pypi.org (TestPyPI account is separate). 5 min UI work.
  3. **GH repo Environments:** create `pypi` and `testpypi` environments. Optionally require `helloiamvu` as reviewer on the `pypi` environment. 2 min UI work.
- **Pre-flight:** confirm `pip index versions tradewinds tradewinds-weather tradewinds-markets` for current PyPI state (Open Question Q-05). If alpha1 is published, pending publishers are unnecessary (per-project trusted publishers register directly on the existing PyPI project).

### Tasks

#### Task 5.1: rc1 → TestPyPI dry-run

- **Branch:** `phase-4/wave-5-release/rc1-testpypi-dryrun` off `phase-4/wave-5-release`.
- **Files (temporary; reverted at end of Wave 5):**
  - EDIT: `packages/{core,weather,markets}/pyproject.toml` — temporarily bump `version = "0.1.0"` → `version = "0.1.0rc1"` (3 files in lockstep).
- **Action:**
  1. **Operator confirmation step (cannot proceed without):** confirm in this branch's PR description that all 6 pending publishers (3 prod + 3 test) are registered AND both `pypi` + `testpypi` GH environments exist. Block merge to `phase-4/wave-5-release` until confirmed.
  2. Commit version bump: `chore(release): v0.1.0rc1 (TestPyPI dry-run)`.
  3. Tag the branch HEAD: `git tag v0.1.0rc1 && git push origin v0.1.0rc1`. This triggers `release-testpypi.yml`.
  4. Watch the workflow run: `gh run watch`. Expected steps that must pass: checkout → setup-uv → uv build --all-packages (3 wheels) → check_wheel_metadata (OK: 3 wheels) → install + import smoke → publish to TestPyPI.
  5. Verify on TestPyPI: visit https://test.pypi.org/project/tradewinds/, https://test.pypi.org/project/tradewinds-weather/, https://test.pypi.org/project/tradewinds-markets/ — confirm all 3 show `0.1.0rc1`.
  6. **Fresh-venv install + smoke from TestPyPI:**
     ```bash
     # On a clean Python 3.12 venv:
     pip install \
       --index-url https://test.pypi.org/simple/ \
       --extra-index-url https://pypi.org/simple/ \
       tradewinds==0.1.0rc1 tradewinds-weather==0.1.0rc1 tradewinds-markets==0.1.0rc1
     python -c "import tradewinds; print(tradewinds.__version__)"
     # Expected: 0.1.0rc1
     python -c "import tradewinds as tw; df = tw.research('KNYC', '2025-01-06', '2025-01-12'); print(df.head())"
     # Expected: 7-row DataFrame matching tests/fixtures/parity/case_1
     ```

- **Codex review priority:** HIGH (first publish to TestPyPI is the canary; any failure here predicts failures at v0.1.0 final).
- **Test bar:**
  - `release-testpypi.yml` exits 0.
  - All 3 projects visible at v0.1.0rc1 on TestPyPI.
  - Fresh-venv install + smoke succeeds.

#### Task 5.2: External README timing dry-run

- **Branch:** continues `phase-4/wave-5-release` (no code changes, just verification).
- **Action:**
  1. Engage the external timer identified in Wave 2 Task 2.1.
  2. Give them: the README.md + a stopwatch + a clean Python 3.12+ environment with no `tradewinds` installed.
  3. Have them follow README steps 1-3 verbatim, recording elapsed time.
  4. Expected: total time <5 min (ROADMAP Phase 4 SC #2 HARD GATE).
  5. If >5 min: iterate on README (reduce dep tree, smaller research window, clearer prose) until the gate clears. Loop until external timer reports success.

- **Codex review priority:** MEDIUM (no code; the verification IS the gate).
- **Test bar:** external timer report (recorded in `phase-4/integration` PR description with timestamp + timer's name + elapsed seconds) shows <300 seconds total.

#### Task 5.3: v0.1.0 → prod PyPI

- **Branch:** `phase-4/wave-5-release/v0.1.0-final` off `phase-4/wave-5-release` (after Task 5.1 + 5.2 green).
- **Files:**
  - EDIT: `packages/{core,weather,markets}/pyproject.toml` — revert `version = "0.1.0rc1"` → `version = "0.1.0"` (3 files in lockstep).
- **Action:**
  1. Commit: `chore(release): revert version to 0.1.0 final for prod PyPI tag`.
  2. **PR review:** Codex `high` + python-architect on this branch. The release tag is the load-bearing literal.
  3. Tag the branch HEAD: `git tag v0.1.0 && git push origin v0.1.0`. This triggers `release.yml`.
  4. Watch: `gh run watch`. Expected steps: build job (`uv build --all-packages` → `check_wheel_metadata.py` → smoke) → publish job (`environment: pypi` gate; if required-reviewer set, manual approval) → `uv publish` to pypi.org.
  5. **Verify all 3 distros live:**
     ```bash
     pip index versions tradewinds
     pip index versions tradewinds-weather
     pip index versions tradewinds-markets
     # Each must show 0.1.0.
     ```
  6. **Fresh-venv install from prod PyPI:**
     ```bash
     pip install tradewinds tradewinds-weather tradewinds-markets
     python -c "import tradewinds; print(tradewinds.__version__)"
     # Expected: 0.1.0
     ```
  7. **Pitfall 6 mitigation (RESEARCH §"Common Pitfalls" #6):** the TestPyPI dry-run already happened in Task 5.1. If despite that, this step surfaces a problem (e.g., subtle environment difference between TestPyPI and prod), recovery is `pip search` confirmation that 0.1.0 is live + yank-and-bump to 0.1.0.post1.

- **Codex review priority:** HIGH (final release; on REVIEW-DISCIPLINE.md never-skip list as "version bumps" + workflow trigger).
- **Test bar:**
  - `release.yml` exits 0; all jobs green.
  - `pip index versions tradewinds tradewinds-weather tradewinds-markets` all show `0.1.0` listed.
  - Fresh-venv install succeeds.

#### Task 5.4: STATE.md close-out + merge `phase-4/integration` → `main`

- **Branch:** `phase-4/wave-5-release/state-closeout` off `phase-4/wave-5-release`.
- **Files:**
  - EDIT: `/Users/helloiamvu/Documents/GitHub/tradewinds/.claude/worktrees/jolly-spence-35a47d/.planning/STATE.md` — add v0.1.0 close-out entry with date, all 3 PyPI URLs, completed requirement IDs, next-phase pointer (Phase 5 MCP).
- **Action:**
  1. Add entry to STATE.md:
     ```markdown
     ## 2026-07-XX — v0.1.0 SHIPPED
     - tradewinds==0.1.0: https://pypi.org/project/tradewinds/0.1.0/
     - tradewinds-weather==0.1.0: https://pypi.org/project/tradewinds-weather/0.1.0/
     - tradewinds-markets==0.1.0: https://pypi.org/project/tradewinds-markets/0.1.0/
     - All 9 Phase 4 requirements green: PKG-01, DOCS-01..03, CI-01..05.
     - Total v0.1.0 requirements green: 54 / 54.
     - Phase 4 SC #1-5: green.
     - External README timer: {N seconds} (gate <300).
     - tradewinds.core.* branch coverage: {final %} (gate ≥90%).
     - Next: Phase 5 MCP Data Platform (post-v0.1.0; depends on Phase 2 + Phase 4 CI/CD).
     ```
  2. Commit: `chore(phase-4): STATE.md v0.1.0 ship close-out`.
  3. Open PR `phase-4/integration` → `main` with title `release: tradewinds v0.1.0 — 3 distros on PyPI`. Body summarizes all 5 waves + closes the 9 requirements + cross-references the published PyPI URLs.
  4. Codex `high` + python-architect on the integration PR per REVIEW-DISCIPLINE.md (the merge to `main` is the ultimate gate).
  5. `git merge --no-ff` to `main`.

- **Codex review priority:** HIGH (final merge to main; close-out of v0.1.0).
- **Test bar:**
  - STATE.md updated with all 3 PyPI URLs.
  - `phase-4/integration → main` PR merged with `--no-ff`.
  - `main` HEAD references v0.1.0 published wheels.

### Wave 5 Success Criteria

- [ ] v0.1.0rc1 published to TestPyPI for all 3 distros; fresh-venv install + smoke green.
- [ ] External README timer reports <5 min (ROADMAP Phase 4 SC #2 HARD GATE).
- [ ] v0.1.0 published to prod PyPI for all 3 distros; fresh-venv install + smoke green.
- [ ] STATE.md close-out entry present.
- [ ] `phase-4/integration → main` PR merged with `--no-ff`.
- [ ] All 9 Phase 4 requirements marked `[x]` in REQUIREMENTS.md.

</wave>

<cross_cutting_concerns>

### 1. Coverage gate (RESEARCH §"Coverage Approach", ROADMAP Phase 4 SC #1)

**Decided:** option (b) **coverage-omit** for `core/formats/_toon.py` + `core/formats/_toon_list_codec.py` (lifted from mostlyright v0.15.0). Higher-level `core/formats/toon.py` wrapper (currently 85%) stays in scope. Legacy duplicate `_internal/_toon.py` is DELETED, not omitted (only 2 internal callers per RESEARCH grep, both fixed in Wave 1 Task 1.1).

**Why option (b) and not (a) "add tests":** the omitted files are LIFTED, not in-house code. ROADMAP Phase 4 SC #1 explicitly grants the "lifted code retains monorepo coverage" exemption. Adding ~40 statements × ~10 tests to encoder code we don't own and don't ship as public API is busywork. The wrapper at `core/formats/toon.py` (85%, in-scope, our code) is the right surface for any future coverage additions.

**Fallback if Wave 1 measurement disproves the 86% → ~94% projection (RESEARCH §A4 risk):** the secondary gap is `validator.py` (93%; 7 missed + 7 BrPart). Add 3-5 tests in `tests/core/test_validator.py` covering `allow_source_drift` edge cases. Documented in Wave 1 Task 1.1 action notes.

### 2. Branch flow (RESEARCH §"Project Constraints" + Open Question Q-08)

**Decided:** branch off `main`, NOT `merged-vision`. The `merged-vision` pattern was abandoned after Phase 1; Phases 2-3.6 branched off `main` directly per STATE.md commit `fcdc83e`. Phase 4 follows the post-Phase-1 convention:
- Wave branches: `phase-4/wave-N-{name}` off `main`.
- Sub-branches: `phase-4/wave-N-{name}/{task}` off the wave branch.
- Integration branch: `phase-4/integration` accumulates each wave's merge.
- Final PR: `phase-4/integration → main` with `git merge --no-ff` after Wave 5 completes.
- One big PR to `main`, NOT 5 small PRs.

### 3. Operator gates (release-mechanics only — recorded in `phase-4/integration` PR description)

Three operator UI tasks cannot be automated:

1. **PyPI pending publishers** (×3 — prod) — block: Wave 3 cannot merge to `phase-4/integration` without operator confirmation that registration is complete. Form values:
   - PyPI project name: `tradewinds`, `tradewinds-weather`, `tradewinds-markets` (one registration per project)
   - Owner: `helloiamvu`
   - Repository: `tradewinds`
   - Workflow filename: `release.yml`
   - Environment name: `pypi`
2. **TestPyPI pending publishers** (×3) — block: Wave 5 Task 5.1 cannot proceed without these (rc1 publish to TestPyPI fails OIDC handshake). Same form values as above but on test.pypi.org, with `Workflow filename: release-testpypi.yml` and `Environment name: testpypi`.
3. **GH repo Environments** — create `pypi` and `testpypi` in Settings → Environments. Optionally require `helloiamvu` as reviewer on `pypi` environment (recommended — accidental tag pushes don't auto-publish to prod).

Operator timing: do all 7 UI tasks Day 42 (parallel to Wave 1 execution) so the name-squatting risk window is minimal.

### 4. Review discipline (REVIEW-DISCIPLINE.md, Phase 4 sub-branches)

- Every Phase 4 sub-branch runs Codex `high` + python-architect. Codex effort is `high` for ALL sub-branches per REVIEW-DISCIPLINE.md (no `medium`/`low` tier).
- Phase 4 has many "release-mechanics" changes that LOOK like docs but are NOT skip-eligible per REVIEW-DISCIPLINE.md never-skip list:
  - `pyproject.toml` dependency floors (Wave 1 Task 1.3) — never-skip
  - Coverage threshold literals (`fail_under = 90` in Wave 1 Task 1.1) — never-skip (threshold number)
  - Pre-commit / pre-push config — never-skip
  - GH Actions workflow YAML with publish-step semantics — never-skip equivalent (load-bearing release infrastructure)
- Trivial-skip eligible only:
  - README prose rewording (NOT the install commands, NOT the expected-output block, NOT the version strings)
  - Adapter doc page prose (NOT the schema mapping tables, NOT the source-priority numbers, NOT the Pitfall references)
  - CHANGELOG markdown formatting fixes
  - STATE.md prose

### 5. Pre-commit + pre-push hooks (CI-03, CLAUDE.md)

Already in place — `.pre-commit-config.yaml` ships ruff + ruff-format + pre-commit-hooks + local pytest as pre-push (RESEARCH §"Pre-commit Status"). Phase 4 work for CI-03 is:
- No edits to the hooks themselves (already configured).
- Verify hooks documented in CONTRIBUTING.md (already partially done per RESEARCH).
- **Optionally** bump `ruff-pre-commit` from `v0.5.0` to current `~v0.15.x` (CLAUDE.md mentions ruff `>=0.13,<1`). This is independent of any other Phase 4 work; can ship as a separate trivial commit if desired.
- **Mandatory:** no `--no-verify` on any commit in Phase 4. If pre-commit fails, fix the underlying issue.

### 6. Test bar (per-wave + phase ship)

- **Wave 1:** ≥90% branch coverage on `tradewinds.core.*` (HARD GATE); 5 parity fixtures green; 4 doctests green; version lockstep verified.
- **Wave 2:** README expanded to ~120 lines; 4 adapter pages exist; external timer dry-run scheduled.
- **Wave 3:** `test.yml` + `release.yml` + `release-testpypi.yml` + `check_wheel_metadata.py` all live; CI dry-run on wave branch green; operator gate confirmed.
- **Wave 4:** drift scaffolding live; manual trigger test confirms issue-opening path; `tests/fixtures/README.md` documents immutability.
- **Wave 5:** rc1 on TestPyPI green; external README timer <5 min; v0.1.0 on prod PyPI green; STATE.md updated; `main` merged.

### 7. Three-distribution lockstep (Pitfall 1, Pitfall 3, Pitfall 4)

Three discipline points that MUST hold across Phase 4:

- **Lockstep version bumps** — all 3 pyproject.toml files change in one commit (Wave 1 Task 1.3, Wave 5 Tasks 5.1 + 5.3).
- **`uv build --all-packages`, NEVER bare `uv build`** — Workflows MUST use `--all-packages` (Wave 3 Tasks 3.2 + 3.3); local builds in Wave 5 verification MUST use `--all-packages`.
- **No `__init__.py` at namespace root** — `tests/test_wheel_layout.py:test_only_core_ships_namespace_root` enforces this. Already green per Phase 1; Wave 4 + Wave 5 must keep it green (any new file under `packages/{weather,markets}/src/tradewinds/` is suspect).

</cross_cutting_concerns>

<open_questions_and_blocking_decisions>

### Open Q-01 — Codecov: yes or no?

- **State:** OPEN; RESEARCH default = NO for v0.1.0.
- **Default:** **NO.** The inline `--cov-fail-under=90` is sufficient as the local gate. Codecov.io adds external SaaS dep + cost + auth setup for trend-over-time reporting we don't yet need.
- **If operator overrides to YES:** Wave 3 Task 3.1 adds a `codecov/codecov-action@v5` step to `test.yml` after the coverage run. Adds a GH repo secret (`CODECOV_TOKEN`) for private repos; public repos can use tokenless upload (verify current docs at Wave 3 time).
- **Recommendation:** stick with NO. Re-evaluate at v0.2.

### Open Q-02 — `mypy --strict` on `core/`: required gate or soft warning?

- **State:** OPEN; CI-03 says "**optional** mypy --strict on core/".
- **Default:** **soft gate (`continue-on-error: true`)** for v0.1.0.
- **Decision rule (Wave 3 Task 3.1):** run a one-shot probe locally before merging `test.yml`. Count issues:
  - 0-2 issues → flip `continue-on-error: false` (promote to required gate).
  - 3+ issues → stay soft; file v0.2 issue "Tighten mypy --strict on tradewinds.core/".
- **Recommendation:** soft default. The codebase has type hints but no enforced mypy history; promoting to required now risks blocking the release on type-hint nits.

### Open Q-03 — v0.1.0 vs v0.1.0rc1 first tag?

- **State:** OPEN; RESEARCH recommendation = rc1 first.
- **Default:** **YES — do rc1 first** per RESEARCH §"Open Questions" #4.
- **Why:** PyPI filename immutability means a bad v0.1.0 cannot be re-uploaded; yank-and-bump to `0.1.0.post1` is the only recovery. TestPyPI rc1 dry-run catches wheel-layout / METADATA bugs before they're immutable on prod. Cost: one extra tag (mechanical).
- **Plan reflects this:** Wave 5 Task 5.1 = rc1 → TestPyPI; Task 5.3 = v0.1.0 → prod PyPI. Pyproject versions bump rc1 (temporary) → 0.1.0 (final) per Task 5.1 + Task 5.3 action notes.
- **If operator overrides to NO rc1:** skip Task 5.1; combine 5.2 + 5.3 directly against prod. Risk: any wheel-layout regression yanks the v0.1.0 release.

### Open Q-04 — Three PyPI pending-publisher registrations (operator gate)

- **State:** REQUIRED before Wave 3 merges. Timing analogous to Phase 2 Wave 5's A1 Kalshi-mapping operator confirmation.
- **What:** operator registers 3 pending publishers on pypi.org (prod) + 3 on test.pypi.org (TestPyPI) — see Cross-Cutting Concerns §3 for exact form values.
- **Why before Wave 3:** Wave 3 ships `release.yml` referencing `environment: pypi`. The pending publisher links GitHub repo → workflow file → environment → PyPI project. If publishers aren't registered before tag time, OIDC handshake fails with "no matching trusted publisher" (Pitfall 2).
- **Why early (Day 42):** RESEARCH §"Risk: Name Squatting" — a pending publisher does NOT reserve the name. Anyone else can register `tradewinds-weather` on PyPI before our first publish. Mitigate by minimizing the window between PR description claim and actual registration. Operator does the 7 UI tasks Day 42.
- **If alpha1 already on PyPI** (Open Question Q-05 affirmative): pending publishers UNNECESSARY; instead, register **per-project trusted publishers** on the existing PyPI project pages (Account → Publishing → Add trusted publisher on each project page). Simpler.

### Open Q-05 — Are tradewinds==0.1.0a1 already on PyPI?

- **State:** OPEN; CHANGELOG.md line 65 says "Phase 1 prepublish hygiene" but does NOT confirm an actual `uv publish` happened.
- **Resolution at Wave 1 start:**
  ```bash
  pip index versions tradewinds tradewinds-weather tradewinds-markets
  ```
  - If output shows `0.1.0a1` for all 3 → trusted publishers are per-project (Open Q-04 simpler path).
  - If output shows "no matching distribution" → pending publishers required for first publish (Open Q-04 default path).
- **Recommendation:** verify Day 42 as the first Wave 1 step. Document the result in the wave branch's commit message + the `phase-4/integration` PR description.

### Open Q-06 — Drift fixture cadence (weekly OK?)

- **State:** OPEN; ROADMAP SC #5 says "weekly cron-rotated."
- **Default:** **weekly** per RESEARCH §"Open Questions" #3. Monday 07:00 UTC (Sunday evening Pacific, Monday morning Tokyo).
- **Adjust if:** drift issues are noisy (>1 issue/week with no real drift) → reduce to every other week. If drift issues are scarce despite known upstream changes (e.g., AWC API redesign) → tighten to daily. Reassess at v0.2.

### Open Q-07 — macOS in CI matrix: 3.12 only, or full 3.11/3.12/3.13?

- **State:** OPEN; RESEARCH default = 3.12 only on macOS.
- **Default:** **3.12 only on macOS** per RESEARCH §"Open Questions" #7. Ubuntu carries the version matrix; macOS is a smoke check that filelock + httpx + cache work on the dev's actual platform (Darwin 24.6.0 ARM64 per env).
- **If operator overrides to full matrix:** Wave 3 Task 3.1 expands `include` block in `test.yml`. Risk: macOS runners are 3-4x slower than Ubuntu; flakiness adds CI noise.

### Open Q-08 — Branch flow inside Phase 4: per-wave branches or one phase-4 branch?

- **State:** RESOLVED. Per CLAUDE.md + RESEARCH §"Project Constraints" + post-Phase-1 convention: per-wave branches + `phase-4/integration` accumulator + final PR to `main`. Plan reflects this throughout.

</open_questions_and_blocking_decisions>

<goal_backward_verification>

Each ROADMAP §"Phase 4 Success Criteria" mapped to wave + task that achieves it:

| ROADMAP SC | Achieved by Wave + Task | Verification |
|------------|--------------------------|--------------|
| **SC-1:** CI reports ≥90% branch coverage on `tradewinds.core.*` (HARD GATE — Day 12); 80% line coverage on `catalog/` and adapter wrappers; lifted `_vendor/` retains monorepo-v0.14.1 coverage | **Wave 1 Task 1.1** (coverage-omit lifted `_toon.py` + delete `_internal/_toon.py` duplicate + add `[tool.coverage.*]` blocks); **Wave 3 Task 3.1** (`test.yml` enforces `--cov-fail-under=90` on every push + PR) | `uv run pytest -m "not live" --cov=tradewinds.core --cov-branch --cov-fail-under=90` exits 0; CI report confirms |
| **SC-2:** README quickstart works end-to-end in <5 minutes for a fresh installer, timed by an external person; `pytest --doctest-modules` passes on NumPy-style docstrings for `research()`, `KnowledgeView`, `Validator`, `LeakageDetector`; one adapter knowledge-resource page per adapter in `docs/adapters/` | **Wave 1 Task 1.2** (4 doctest scaffolds); **Wave 2 Task 2.1** (README expansion); **Wave 2 Task 2.2** (4 adapter doc pages); **Wave 3 Task 3.1** (CI step runs the 4 doctests); **Wave 5 Task 5.2** (external timer dry-run) | External timer report <300 sec recorded in PR description; `docs/adapters/{iem,awc,cli,ghcnh}.md` all exist; `pytest --doctest-modules <4 paths>` exits 0 in CI |
| **SC-3:** Three PyPI distributions tagged and published at v0.1.0: `tradewinds`, `tradewinds-weather`, `tradewinds-markets`; trusted publishing configured per package; GH Actions workflow `release.yml` triggers on `v*` tag and publishes via `astral-sh/trusted-publishing-examples` pattern | **Wave 1 Task 1.3** (lockstep version bump); **Wave 3 Task 3.2** (`release.yml`); **Wave 5 Task 5.3** (v0.1.0 tag + prod PyPI publish) | `pip index versions tradewinds tradewinds-weather tradewinds-markets` all show `0.1.0` |
| **SC-4:** Pre-publish METADATA grep CI step inspects each built wheel's `Requires-Dist` and fails the build if explicit version range for sibling `tradewinds-*` packages is missing (`tradewinds-weather>=0.1.0,<0.2` etc.); `pytest -m "not live"` runs in CI on every push; `@pytest.mark.live` tests excluded from CI; pre-commit hooks enforced, no `--no-verify` | **Wave 3 Task 3.0** (`scripts/check_wheel_metadata.py`); **Wave 3 Task 3.1** (`test.yml` runs `pytest -m "not live"`); **Wave 3 Task 3.2** (`release.yml` calls the script after `uv build --all-packages`); CI-03 (pre-commit already configured, RESEARCH §"Pre-commit Status" — no Phase 4 work needed beyond verification) | `scripts/check_wheel_metadata.py dist/` exits 0 in `release.yml` build job; `test.yml` runs `pytest -m "not live"`; no commits in Phase 4 land with `--no-verify` |
| **SC-5:** Two-tier fixture structure in place: `tests/fixtures/parity/` (frozen, never re-recorded — 5 byte-equivalent fixtures from Day 0.5) + `tests/fixtures/drift/` (weekly cron-rotated, compared against parity set); rotation policy documented in `tests/fixtures/README.md` | **Wave 4 Task 4.1** (`tests/fixtures/README.md` + `drift/` scaffold + capture/compare scripts + `tests/test_drift.py`); **Wave 4 Task 4.2** (`drift-rotate.yml` weekly cron) | `tests/fixtures/README.md` documents both tiers; `drift-rotate.yml` manual-trigger test confirms compare → issue path works |

**Cross-check — every requirement ID maps to at least one wave/task:**

| Req ID | Wave | Task |
|--------|------|------|
| PKG-01 | 5 | 5.1, 5.3 (3 wheels on PyPI at v0.1.0) |
| DOCS-01 | 1 | 1.2 (4 doctests added) |
| DOCS-01 | 3 | 3.1 (CI step runs the 4 doctests) |
| DOCS-02 | 2 | 2.1 (README expansion) |
| DOCS-02 | 5 | 5.2 (external timer dry-run) |
| DOCS-03 | 2 | 2.2 (4 adapter doc pages) |
| CI-01 | 3 | 3.1 (test.yml on push + PR) |
| CI-01 | 3 | 3.2 (release.yml on v* tag) |
| CI-01 | 3 | 3.3 (release-testpypi.yml on rc* tag) |
| CI-02 | 3 | 3.0 (check_wheel_metadata.py) |
| CI-02 | 3 | 3.2 (release.yml uses the script) |
| CI-03 | n/a | pre-commit already configured (RESEARCH §"Pre-commit Status"); Phase 4 verifies + CONTRIBUTING.md updates only |
| CI-04 | 3 | 3.1 (test.yml runs `pytest -m "not live"`) |
| CI-05 | 4 | 4.1, 4.2 (two-tier fixtures + drift cron) |

All 9 Phase 4 requirements assigned. No orphans.

</goal_backward_verification>

<verification>

**Continuous verification (every wave merge):**

1. `pytest packages/ tests/ -m "not live"` — full test suite green.
2. `pytest tests/test_parity.py` — 5 byte-equivalent fixtures green (Phase 1 gate preserved across Phase 4 edits).
3. `pytest -m "not live" --cov=tradewinds.core --cov-branch --cov-fail-under=90` — coverage gate green from Wave 1 onward.
4. `ruff check .` + `ruff format --check .` — no lint or format drift.
5. `grep -h 'version =' packages/{core,weather,markets}/pyproject.toml | sort -u | wc -l` returns `1` (lockstep) from Wave 1 onward.
6. No commit lands with `--no-verify` (REVIEW-DISCIPLINE.md + CLAUDE.md mandate).

**Phase 4 ship gate (end of Wave 5, before `phase-4/integration → main`):**

1. All 9 Phase 4 requirements green (per goal_backward_verification table).
2. All 5 ROADMAP §"Phase 4 Success Criteria" green.
3. `pip index versions tradewinds tradewinds-weather tradewinds-markets` all show `0.1.0` on pypi.org.
4. Fresh-venv install + smoke from prod PyPI succeeds (`pip install tradewinds tradewinds-weather tradewinds-markets && python -c "import tradewinds; tradewinds.__version__"`).
5. External README timer report <300 sec recorded.
6. `test.yml` CI green on `phase-4/integration` HEAD across all 4 matrix entries (ubuntu 3.11/3.12/3.13 + macOS 3.12).
7. `tests/fixtures/parity/` byte-identical to its Phase 1 freeze (`sha256sum tests/fixtures/parity/*.parquet` matches Phase 1 SUMMARY).
8. STATE.md has v0.1.0 ship close-out entry.

</verification>

<success_criteria>

Phase 4 is complete when:

- All 9 phase requirements (PKG-01, DOCS-01..03, CI-01..05) marked `[x]` in REQUIREMENTS.md.
- `main` branch contains the `phase-4/integration` merge with `--no-ff`.
- All 3 distributions (`tradewinds`, `tradewinds-weather`, `tradewinds-markets`) live at `0.1.0` on pypi.org.
- `tradewinds.core.*` branch coverage ≥90% enforced in CI.
- README quickstart timed under 5 min by external person.
- `tests/fixtures/parity/` byte-identical to its Phase 1 freeze.
- `.github/workflows/{test.yml,release.yml,release-testpypi.yml,drift-rotate.yml}` all live.
- `scripts/check_wheel_metadata.py` exists and is wired into `release.yml`.
- `docs/adapters/{iem,awc,cli,ghcnh}.md` all exist.
- STATE.md has v0.1.0 ship close-out entry with the 3 PyPI URLs.
- **v0.1.0 SHIPPED.** Phase 5 (MCP Data Platform) can start the next morning.

</success_criteria>

<output>

Wave-merge SUMMARY files will be created per wave at `.planning/phases/04-coverage-docs-cicd-release/SUMMARY-wave-{N}.md` documenting:
- Files created/modified
- Atomic commits made
- Codex review outcomes (per sub-branch)
- Open questions resolved (e.g., Q-05 PyPI alpha1 status at Wave 1 start; Q-02 mypy issue count at Wave 3)
- Test counts + coverage % before/after
- Operator gate completions (PyPI publishers registered, GH environments created)

Phase-level SUMMARY at `.planning/phases/04-coverage-docs-cicd-release/SUMMARY.md` after Wave 5 merge, covering:
- Total LOC added (target: ~300 LOC YAML + ~250 LOC docs + ~280 LOC scripts + ~50 LOC test fixtures = ~880 LOC; almost no source code changed)
- Total test count (target: 1451 retained + ~5 new validator tests if coverage gap needed them + 5 check_wheel_metadata tests = ~1461)
- `tradewinds.core.*` final branch coverage (target ≥90%)
- External README timer report (target <300 sec)
- PyPI publish timestamps for all 3 distros
- Operator UI tasks completed log (3 prod publishers + 3 test publishers + 2 GH environments)
- Decisions recorded: Q-01 (codecov no), Q-02 (mypy soft), Q-03 (rc1 yes), Q-06 (weekly drift), Q-07 (macOS 3.12 only)
- v0.1.0 ship date

</output>

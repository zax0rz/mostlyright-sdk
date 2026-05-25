---
phase: 16-v1.0-production-release
type: execute
depends_on: [13-pypi-publication-pipeline, 14-npm-publication-pipeline, 15-docs-autogen-landing-site]
# Phase 13 W0 (org create + repo transfer to mostlyright/mostlyright-sdk) is a HARD prerequisite.
# Phase 16 W0 (cleanup wave: untrack .planning, prune dev artifacts, stub README) is BUNDLED with Phase 13 W0 — whichever ships first owns the commit.
requirements:
  - RELEASE-01
  - RELEASE-02
  - RELEASE-03
  - RELEASE-04
  - RELEASE-05
  - RELEASE-06
  - RELEASE-07
  - RELEASE-08
  - RELEASE-09
  - RELEASE-10
tags:
  - release
  - v1.0
  - polish
  - governance
must_haves:
  truths:
    - "All 3 PyPI distros + 4 npm packages published at 1.0.0 on `latest` dist-tag"
    - "Root README rewritten as user-facing marketing copy; 8 per-package READMEs polished"
    - "CHANGELOG.md, CONTRIBUTING.md, CODE_OF_CONDUCT.md, SECURITY.md committed at repo root"
    - "External user clock-timed through quickstart at <5 min wall time, no blockers"
    - ".planning/RELEASE-RUNBOOK.md links Phase 13 + 14 + 15 runbooks for routine post-1.0 release"
    - "STATE closeout declares v1.0 production-shipped"
  artifacts:
    - path: "README.md (rewritten)"
      provides: "User-facing marketing copy + 60s quickstart + API surface map + badges"
    - path: "CHANGELOG.md"
      provides: "[1.0.0] + [0.1.0] + [0.1.0rc1] sections (Keep-A-Changelog)"
    - path: "CONTRIBUTING.md"
      provides: "Fork + branch + review-discipline + test gate + PR process"
    - path: "CODE_OF_CONDUCT.md"
      provides: "Contributor Covenant 2.1 verbatim with maintainer contact"
    - path: "SECURITY.md"
      provides: "Vuln report process + supported-versions table + disclosure timeline"
    - path: ".planning/RELEASE-RUNBOOK.md"
      provides: "Top-level release runbook linking Phase 13/14/15 RUNBOOKs"
  key_links:
    - from: "git tag v1.0.0"
      to: ".github/workflows/release.yml + docs-publish.yml"
      via: "GH Actions tag-trigger fires both publishes"
    - from: "git tag vts-1.0.0"
      to: ".github/workflows/release-ts.yml + docs-publish.yml"
      via: "same — npm publish + docs regen"
---

<objective>
W0 (NEW 2026-05-25) — **Pre-public cleanup wave (BUNDLED with Phase 13 W0; whichever phase ships first owns the commit).** Untrack `.planning/` from git (kept locally; `.gitignore` already excludes it). Prune dev-only artifacts (`spike/`, `.scratch/`, any debug shell scripts not part of the documented workflow). Stub root README.md to production-grade (the full W1 rewrite supersedes this stub). Goal: the repo is safe to make public AS-IS before W1 prose lands. If Phase 13 W0 already shipped this cleanup, W0-T1 here is a no-op verify.

W1 — Rewrite prose: root README.md (marketing copy + 60s quickstart + API map + badges pointing at `mostlyright/mostlyright-sdk`) + 8 per-package READMEs.

W2 — Governance files: CHANGELOG.md sections, CONTRIBUTING.md, CODE_OF_CONDUCT.md, SECURITY.md, LICENSE confirmation.

W3 — Lockstep version bump 0.1.0 → 1.0.0 across all 8 packages (3 PyPI + 4 npm publishable + 1 npm private codegen); single PR `release/v1.0.0`; merge; push `v1.0.0` + `vts-1.0.0` tags; monitor release.yml + release-ts.yml + docs-publish.yml; verify PyPI + npm `latest` + https://mostlyright.md/docs/sdk/.

W4 — External validation: recruit external user, clock-time quickstart, fix any blockers as `1.0.1` patches within 72h; write `.planning/RELEASE-RUNBOOK.md`; STATE.md closeout declares v1.0 production-shipped.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/16-v1.0-production-release/16-CONTEXT.md
@.planning/phases/13-pypi-publication-pipeline/RUNBOOK.md  # assumes Phase 13 shipped
@.planning/phases/14-npm-publication-pipeline/RUNBOOK.md  # assumes Phase 14 shipped
@.planning/phases/15-docs-autogen-landing-site/15-SUMMARY.md  # assumes Phase 15 shipped
@README.md  # current — to be rewritten
@CHANGELOG.md  # seeded by Phase 13 W1
@CLAUDE.md  # source for the value-prop paragraph
@LICENSE
@.planning/REVIEW-DISCIPLINE.md  # cited from CONTRIBUTING.md
</context>

<tasks>

<task type="auto" depends_on="">
  <name>W0 Task 1: Pre-public cleanup wave (bundled with Phase 13 W0 — idempotent)</name>
  <files>
    .gitignore (verify .planning/ + spike/ + .scratch/ already listed; append if missing),
    README.md (stub if not already production-grade),
    .planning/phases/16-v1.0-production-release/16-W0-CLEANUP.md (NEW; inventory of files removed + commit SHA)
  </files>
  <read_first>
    .gitignore (current state),
    git ls-files .planning/ | wc -l  (count of tracked planning files BEFORE cleanup),
    .planning/phases/13-pypi-publication-pipeline/13-W0-ORG-TRANSFER.md (if shipped, this wave is verify-only)
  </read_first>
  <action>
    Step 1 — idempotency check. If Phase 13 W0 already shipped the cleanup commit, skip to Step 5 (verify-only).
      git log --oneline | grep -E 'cleanup: prepare repo for public transfer' && echo "ALREADY SHIPPED in Phase 13 W0; this task is verify-only" && exit 0

    Step 2 — confirm .gitignore covers untrackable trees. Required entries (append if missing):
      .planning/
      spike/
      .scratch/
      *.pyc
      __pycache__/
      .pytest_cache/
      node_modules/
      dist/
      *.parquet
      .DS_Store

    Step 3 — untrack `.planning/` (keep locally; .gitignore prevents re-add):
      git rm -r --cached .planning/

    Step 4 — prune dev-only artifacts. Inventory (operator confirms each):
      - spike/ (if tracked)
      - .scratch/ (if tracked)
      - any *.local.* files
      - any "DRAFT-" or "TODO-" prefixed top-level docs that are not part of the documented workflow
      For each: `git rm <path>`

    Step 5 — stub root README.md to production-grade IF the Phase 16 W1 rewrite hasn't merged yet:
      cat > README.md <<'EOF'
      # mostlyright

      Local-first SDK for prediction-market weather settlement research.

      - PyPI: `pip install mostlyright`
      - npm:  `npm install @mostlyright/core`
      - Docs: https://mostlyright.md/docs/sdk/

      Full README + quickstart shipping with v1.0 (Phase 16).
      EOF
      # NOTE: This stub is replaced wholesale by W1-T1. The stub exists so Phase 13 W0 (which precedes Phase 16 W1) can transfer the repo with a public-grade README.

    Step 6 — write inventory log:
      cat > .planning/phases/16-v1.0-production-release/16-W0-CLEANUP.md <<'EOF'
      # Phase 16 W0 — Cleanup inventory
      Date: <fill at execution>
      Commit SHA: <fill after commit>
      Untracked: .planning/ (N files), spike/ (N files), .scratch/ (N files)
      .gitignore entries added: <list>
      README.md stubbed: yes/no (yes if W1 not yet merged)
      Phase 13 W0 bundling note: <commit SHA if bundled, else "stand-alone W0 commit">
      EOF

    Step 7 — commit (single atomic commit; this IS the public-prep commit):
      git checkout -b cleanup/prepare-public-transfer  # if not already on a branch from Phase 13 W0
      git add .gitignore README.md .planning/phases/16-v1.0-production-release/16-W0-CLEANUP.md
      git commit -m "cleanup: prepare repo for public transfer (Phase 13 W0 / Phase 16 W0)"
      git push origin cleanup/prepare-public-transfer
      gh pr create --title "cleanup: prepare repo for public transfer" --body "Phase 13 W0 + Phase 16 W0 bundled. Untrack .planning/, prune dev artifacts, stub README. See .planning/phases/16-v1.0-production-release/16-W0-CLEANUP.md for inventory."
      # Review loop: codex `high` + python-architect per .planning/REVIEW-DISCIPLINE.md
  </action>
  <verify>
    <automated>
    # .planning/ no longer tracked (still exists locally)
    test "$(git ls-files .planning/ | wc -l)" = "0"
    # .gitignore covers the right trees
    grep -qE '^\.planning/$' .gitignore
    grep -qE '^(spike/|\.scratch/)$' .gitignore || true   # optional
    # cleanup PR committed
    git log --oneline -10 | grep -qE 'cleanup: prepare repo for public transfer'
    # Inventory log committed
    test -f .planning/phases/16-v1.0-production-release/16-W0-CLEANUP.md
    </automated>
  </verify>
  <done>
    `.planning/` untracked (still on disk for local planning work; .gitignore prevents accidental re-add). Dev-only artifacts pruned. Stub README in place. Repo safe for the Phase 13 W0 OP0c transfer. Cleanup PR merged to main.
  </done>
</task>

<task type="auto" depends_on="W0-T1">
  <name>W1 Task 1: Rewrite root README.md as user-facing marketing copy</name>
  <files>README.md</files>
  <read_first>
    CLAUDE.md (## Project section — canonical value prop),
    docs/cache-migration.md + docs/live-streaming.md + docs/ingest-strategies.md (concept examples to cite),
    Existing well-respected SDK READMEs to mirror tone:
      - https://github.com/pandas-dev/pandas/blob/main/README.md
      - https://github.com/encode/httpx/blob/master/README.md
      - https://github.com/astral-sh/ruff/blob/main/README.md
  </read_first>
  <action>
    Rewrite README.md with this structure:

    ```markdown
    # mostlyright

    [![PyPI](https://img.shields.io/pypi/v/mostlyright?label=pypi%3A%20mostlyright)](https://pypi.org/project/mostlyright/)
    [![npm](https://img.shields.io/npm/v/@mostlyright/core?label=npm%3A%20%40mostlyright%2Fcore)](https://www.npmjs.com/package/@mostlyright/core)
    [![CI](https://github.com/mostlyright/mostlyright-sdk/actions/workflows/test.yml/badge.svg)](https://github.com/mostlyright/mostlyright-sdk/actions/workflows/test.yml)
    [![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

    > Local-first SDK for prediction-market weather settlement research. No hosted backend.

    `research(contract, station, from_date, to_date)` returns clean, leakage-free, source-identified training pairs that backtest the same way they trade — and any train/infer source mismatch errors loudly instead of silently corrupting a model.

    Available in **Python** ([PyPI](https://pypi.org/project/mostlyright/)) and **TypeScript** ([npm](https://www.npmjs.com/package/@mostlyright/core)). Same APIs, same canonical schemas, row-equivalent output.

    ## Quickstart

    <details open><summary><b>Python</b></summary>

    ```bash
    pip install 'mostlyright[research]'
    ```

    ```python
    import mostlyright as mr

    # 5-day window of Kalshi NYC high/low contract pairs:
    df = mr.research(station="KNYC", from_date="2025-01-06", to_date="2025-01-12")
    print(df.head())
    ```

    </details>

    <details><summary><b>TypeScript</b></summary>

    ```bash
    npm install @mostlyright/core
    ```

    ```ts
    import { research } from "@mostlyright/core";

    const rows = await research("KNYC", "2025-01-06", "2025-01-12");
    console.log(rows[0]);
    ```

    </details>

    ## What you get

    - **Direct public-API access** (AWC, IEM, GHCNh, NWS CLI, Kalshi, Polymarket) — no API keys, no hosted service.
    - **Source-identified rows** — every observation carries the `source` ID it came from (AWC live METAR / IEM ASOS archive / GHCNh / NWS CLI). Train/infer source mismatches raise `SourceMismatchError`.
    - **Temporal safety** — `KnowledgeView` filters by `as_of` time; `LeakageDetector` catches future-data contamination in features.
    - **Local parquet cache** — `~/.mostlyright/cache/v1/` (Python) / `~/.mostlyright/cache-ts/` (TS). Byte-equivalent on re-runs.
    - **Live ticker** — `mostlyright.live.stream(station, source="awc")` async generator for real-time observation ticks (30s polite floor AWC, 60s IEM).
    - **Production-grade backtests** — 1971+ tests, parity-fixture gate against `mostlyright==0.14.1` byte-equivalent, codex + Python-architect + TS-architect review discipline.

    ## API surface (one-line per function)

    ```
    research(station, from_date, to_date, *, sources=None, contract=None) → DataFrame
    discover(city) | discover(station) → DataFrame   # what's available?
    live.stream(station, *, source) → AsyncGenerator # real-time ticks
    live.latest(station, *, source) → ObservationRow # one-shot
    weather.obs(station, from_date, to_date, *, strategy="auto") → DataFrame
    markets.kalshi_trades.{candles, fills, orderbook}(...)
    markets.polymarket_trades.{history, snapshot}(...)
    markets.polymarket_discover() | polymarket_settle(event_id)
    snapshot.settlement_date_for(utc_moment, station) → date
    snapshot.settlement_window_utc(settlement_date, station) → (start, end)
    core.KnowledgeView(df, as_of) | LeakageDetector | assert_no_leakage
    transforms.{lag, diff, rolling, calendar_features, spread, wind_chill, heat_index}
    qc.{QCEngine, crosscheck_iem_ghcnh}
    ```

    ## Documentation

    Full reference at **[mostlyright.md/docs/sdk/](https://mostlyright.md/docs/sdk/)**:

    - [Python quickstart](https://mostlyright.md/docs/sdk/quickstart-python/) (60-second install + first call)
    - [TypeScript quickstart](https://mostlyright.md/docs/sdk/quickstart-typescript/)
    - [Concepts: temporal safety](https://mostlyright.md/docs/sdk/concepts/temporal-safety/)
    - [Concepts: source identity](https://mostlyright.md/docs/sdk/concepts/source-identity/)
    - [Python API reference](https://mostlyright.md/docs/sdk/python/) (auto-generated)
    - [TypeScript API reference](https://mostlyright.md/docs/sdk/typescript/) (auto-generated)
    - [Cross-SDK parity table](https://mostlyright.md/docs/sdk/parity/)
    - [Migration: tradewinds → mostlyright (v0.0.x → 1.0.0)](https://mostlyright.md/docs/sdk/migration/v0.0.x/)
    - [Migration: cache directory + env var](https://mostlyright.md/docs/sdk/migration/cache/)

    ## Contributing

    See [CONTRIBUTING.md](CONTRIBUTING.md). Bug reports and PRs welcome.

    Internal docs: `.planning/` for roadmap + per-phase plans, `CLAUDE.md` for project-context guide.

    ## License

    [MIT](LICENSE). © 2026 Mostly Right.
    ```

    NB: do NOT include hype words. The prose above is the maximum marketing tone Phase 16 ships.

    Commit:
      git add README.md
      git commit -m "phase16 W1: rewrite root README.md as v1.0 user-facing marketing copy"
  </action>
  <verify>
    <automated>
    test -f README.md
    grep -c '^# mostlyright' README.md  # expect 1
    grep -c 'pip install' README.md  # expect >=1
    grep -c 'npm install' README.md  # expect >=1
    grep -c 'mostlyright.md/docs/sdk' README.md  # expect >=5 (multiple doc links)
    grep -c 'shields.io' README.md  # expect >=3 (badge URLs)
    wc -l README.md | awk '$1 < 200 {exit 0} {exit 1}'  # marketing copy stays tight, <200 lines
    </automated>
  </verify>
  <done>
    Root README rewritten as user-facing marketing copy with badges + 60s quickstart (both SDKs) + API surface map + doc links. <200 lines. No hype words.
  </done>
</task>

<task type="auto" depends_on="W1-T1">
  <name>W1 Task 2: Polish 8 per-package READMEs</name>
  <files>
    packages/core/README.md,
    packages/weather/README.md,
    packages/markets/README.md,
    packages-ts/codegen/README.md,
    packages-ts/core/README.md,
    packages-ts/weather/README.md,
    packages-ts/markets/README.md,
    packages-ts/meta/README.md
  </files>
  <read_first>
    Each existing per-package README (8 files; Phase 12 W7 cleaned the tradewinds refs already)
  </read_first>
  <action>
    Each per-package README must be SELF-CONTAINED so a user landing on PyPI or npm sees:
      1. Package title + one-line description
      2. Install command (this specific package)
      3. 5-line quickstart specific to this package's surface
      4. Link to the full docs at mostlyright.md/docs/sdk/

    NOT redundant with the root README — each package README focuses on what THAT package exports.

    Example for packages/core/README.md:
      # mostlyright

      Core SDK for prediction-market weather research. Includes `research()`, `discover()`, temporal-safety primitives, and exception hierarchy.

      Part of the [Mostly Right](https://mostlyright.md) project. For the full SDK including weather data sources, install [`mostlyright[research]`](https://pypi.org/project/mostlyright/) which brings `mostlyright-weather` in transitively.

      ## Install

      ```bash
      pip install mostlyright            # core only
      pip install 'mostlyright[research]'  # core + weather (recommended)
      ```

      ## Quickstart

      ```python
      from mostlyright import research
      df = research("KNYC", "2025-01-06", "2025-01-12")
      print(df.head())
      ```

      ## Documentation

      Full API reference: [mostlyright.md/docs/sdk/python/](https://mostlyright.md/docs/sdk/python/)

      ## License

      MIT

    Example for packages-ts/core/README.md:
      # @mostlyright/core

      Core types, schemas, and primitives for the Mostly Right TypeScript SDK. Includes `research()`, temporal-safety primitives (`KnowledgeView`, `LeakageDetector`), and the canonical schema registry.

      Part of [Mostly Right](https://mostlyright.md). For the full SDK install the convenience meta-package [`mostlyright`](https://www.npmjs.com/package/mostlyright) which re-exports the three scoped packages.

      ## Install

      ```bash
      npm install @mostlyright/core
      ```

      ## Quickstart

      ```ts
      import { research } from "@mostlyright/core";
      const rows = await research("KNYC", "2025-01-06", "2025-01-12");
      console.log(rows[0]);
      ```

      ## Documentation

      Full API reference: [mostlyright.md/docs/sdk/typescript/](https://mostlyright.md/docs/sdk/typescript/)

      ## License

      MIT

    Apply analogous structure to weather + markets + codegen + meta READMEs, adjusting the quickstart for each package's surface.

    Commit:
      git add packages/*/README.md packages-ts/*/README.md
      git commit -m "phase16 W1: polish 8 per-package READMEs for v1.0 PyPI + npm landing"
  </action>
  <verify>
    <automated>
    for f in packages/core/README.md packages/weather/README.md packages/markets/README.md packages-ts/codegen/README.md packages-ts/core/README.md packages-ts/weather/README.md packages-ts/markets/README.md packages-ts/meta/README.md; do
      test -f "$f" || { echo "missing: $f"; exit 1; }
      grep -c 'mostlyright.md/docs/sdk' "$f" >/dev/null || { echo "no docs link: $f"; exit 1; }
      grep -cE '^## (Install|Quickstart)' "$f" | awk '$1 >= 2 {exit 0} {exit 1}' || { echo "missing structure: $f"; exit 1; }
    done
    </automated>
  </verify>
  <done>
    8 per-package READMEs polished + self-contained + linked to mostlyright.md/docs/sdk/. PyPI + npm landing pages render correctly.
  </done>
</task>

<task type="auto" depends_on="W1-T2">
  <name>W2 Task 1: Governance files (CONTRIBUTING + CODE_OF_CONDUCT + SECURITY)</name>
  <files>
    CONTRIBUTING.md (NEW),
    CODE_OF_CONDUCT.md (NEW),
    SECURITY.md (NEW)
  </files>
  <read_first>
    .planning/REVIEW-DISCIPLINE.md (cited from CONTRIBUTING.md),
    CLAUDE.md (project structure for contributor onboarding),
    https://www.contributor-covenant.org/version/2/1/code_of_conduct/ (verbatim source for CODE_OF_CONDUCT.md)
  </read_first>
  <action>
    Step 1 — CONTRIBUTING.md:
      # Contributing to Mostlyright

      Thank you for your interest in contributing to Mostlyright.

      ## Quick start

      1. **Fork** the repository on GitHub: https://github.com/mostlyright/mostlyright-sdk
      2. **Branch** from `main`: `git checkout -b your-feature-branch`
      3. **Install** workspace + dev deps: `uv sync` (Python) + `pnpm install` (TypeScript)
      4. **Test** locally: `uv run pytest -m "not live"` + `CI=1 pnpm -r run test`
      5. **Commit** with a descriptive message; pre-commit hooks run automatically
      6. **PR** against `main`; review discipline applies

      ## Review discipline

      Every PR runs the two-reviewer loop (codex + Python Architect for Python-only PRs, +TypeScript Architect for mixed PRs) before merge. See [.planning/REVIEW-DISCIPLINE.md](.planning/REVIEW-DISCIPLINE.md) for severity gate, never-skip path list, and trivial-skip rules.

      ## Test discipline

      TDD required. 80% line coverage minimum on new code. 90% branch coverage on `mostlyright.core` (the load-bearing safety layer).

      Live tests are gated behind `@pytest.mark.live` and excluded from CI; run them manually before publishing.

      ## What's stable vs internal

      Public API surface lives at `mostlyright.*` (Python) and `@mostlyright/{core,weather,markets}` (TypeScript). Subject to SemVer guarantees starting v1.0.

      `mostlyright._internal.*` (Python) and `@mostlyright/*/internal/*` (TypeScript) are internal — no SemVer guarantees. Do not import from these in external code.

      `_vendor/` paths are lifted from `mostlyright==0.14.1` and pinned for parity; do not modify without re-running the parity gate.

      ## Out-of-scope contributions

      - Repo rename / package rename (operator-gated, see Phase 12 closeout)
      - Hosted backend (intentionally never; the project is local-first by design)
      - ECMWF Tier-2 forecasts before v1.x (paid + hosted-only)

      ## Where to ask questions

      - Bug reports: GitHub Issues
      - Security: see [SECURITY.md](SECURITY.md)
      - Code of Conduct: see [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)

    Step 2 — CODE_OF_CONDUCT.md: download verbatim from https://www.contributor-covenant.org/version/2/1/code_of_conduct/code_of_conduct.md, replace `[INSERT CONTACT METHOD]` with maintainer email or GH private security advisory URL.

    Step 3 — SECURITY.md:
      # Security Policy

      ## Supported versions

      | Version | Supported |
      |---------|-----------|
      | 1.0.x | ✓ active development |
      | 0.1.x | ✓ security fixes only (through 2026-11-25) |
      | 0.0.x (legacy `tradewinds*` packages) | ✗ EOL |

      Security patches for the supported branches are released as soon as a fix is verified.

      ## Reporting a vulnerability

      **DO NOT** open a public GitHub issue for security vulnerabilities.

      Report privately via one of:

      1. **GitHub Security Advisory** (preferred): https://github.com/mostlyright/mostlyright-sdk/security/advisories/new
      2. **Email**: `<maintainer-email>` (PGP key fingerprint on request)

      Include:
      - Affected version(s)
      - Reproduction steps
      - Impact assessment

      ## Disclosure timeline

      Standard 90-day disclosure window from acknowledged private report to public disclosure. We may negotiate a shorter or longer window for actively exploited vulnerabilities.

      Acknowledgement of receipt within 72 hours. Patch released and CVE assigned (where applicable) before public disclosure.

      ## Out of scope

      - Vulnerabilities in upstream public APIs (AWC, IEM, GHCNh, NWS CLI, Kalshi, Polymarket) — report to the respective provider.
      - Vulnerabilities in transitive dependencies — report to the dependency upstream first; we'll bump the floor in our `pyproject.toml` / `package.json` once a fix is available.
      - Vulnerabilities in the legacy `tradewinds*` PyPI/npm packages — those are EOL; users should migrate to `mostlyright*`.

    Step 4 — commit:
      git add CONTRIBUTING.md CODE_OF_CONDUCT.md SECURITY.md
      git commit -m "phase16 W2: governance files (CONTRIBUTING + CODE_OF_CONDUCT + SECURITY)"
  </action>
  <verify>
    <automated>
    test -f CONTRIBUTING.md
    test -f CODE_OF_CONDUCT.md
    test -f SECURITY.md
    grep -c 'REVIEW-DISCIPLINE.md' CONTRIBUTING.md  # expect 1
    grep -c 'Contributor Covenant' CODE_OF_CONDUCT.md  # expect 1
    grep -c 'security/advisories' SECURITY.md  # expect 1
    </automated>
  </verify>
  <done>
    3 governance files committed at repo root. CONTRIBUTING.md cites review discipline, CODE_OF_CONDUCT.md adopts Contributor Covenant 2.1, SECURITY.md documents 90-day disclosure + supported-versions table.
  </done>
</task>

<task type="auto" depends_on="W2-T1">
  <name>W2 Task 2: Expand CHANGELOG.md with [1.0.0] + [0.1.0] sections</name>
  <files>CHANGELOG.md</files>
  <read_first>
    CHANGELOG.md (Phase 13 W1 seed),
    .planning/STATE.md (per-phase closeout sections — source for changelog entries)
  </read_first>
  <action>
    Expand the CHANGELOG.md seeded by Phase 13 W1. New shape after Phase 16:

      # Changelog

      All notable changes to this project will be documented in this file.
      The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
      and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

      ## [Unreleased]

      ## [1.0.0] — 2026-MM-DD

      First production-stable release. **No code changes from 0.1.0** — this release SIGNALS API stability under SemVer.

      ### Added
      - User-facing documentation at https://mostlyright.md/docs/sdk/ (auto-generated from source)
      - Root README marketing copy + 8 per-package READMEs
      - CHANGELOG.md, CONTRIBUTING.md, CODE_OF_CONDUCT.md, SECURITY.md at repo root
      - Status badges (PyPI, npm, CI, license)

      ### Promoted
      - All 7 publishable packages (3 PyPI + 4 npm) bumped 0.1.0 → 1.0.0 in lockstep

      ## [0.1.0] — 2026-MM-DD (prod PyPI + npm)

      First production-ready release. 1971+ Python tests, 1355+ TS tests. Parity-fixture gate against `mostlyright==0.14.1` byte-equivalent.

      ### Added (vs `mostlyright==0.14.1`)
      - **Phase 1**: parity lift; 5-fixture byte-equivalent gate; 3 PyPI wheels
      - **Phase 1.5**: yearly-chunk fetcher (12x payload throughput); cross-source parallelism
      - **Phase 2**: temporal safety primitives (KnowledgeView, LeakageDetector); canonical schemas; source-identity validator
      - **Phase 2.1**: per-source observation ledger (silver-tier); read-time merge policy
      - **Phase 3.x**: Mode 2 source-explicit dispatch; international station expansion (60 ICAOs); HRRR/GFS/NBM forecast live path; Polymarket discovery + settlement; QC engine alpha; transforms DSL; discovery API + DataVersion
      - **Phase 6**: pandas 3 readiness + opt-in polars backend (TradewindsResult wrapper)
      - **Phase 7**: ingest auto-planner (`tw.weather.obs()` smart routing)
      - **Phase 8**: Polymarket US coverage + per-issuer settlement invariants
      - **Phase 9**: Markets trade history (Kalshi candles/fills/orderbook + Polymarket history/snapshot)
      - **Phase 10**: Composable `research()` (multi-contract basis-trade selector layer)
      - **Phase 11**: Live streaming iterator (`mostlyright.live.stream` / `live.latest`)
      - **TS-W0..TS-W7**: Full TypeScript SDK port (paired with Python)

      ### Changed
      - **Phase 12**: Package renamed from `tradewinds*` to `mostlyright*` across PyPI + npm + cache + schema $id. Zero behavior change.

      ### Migration from `tradewinds*`
      - `pip uninstall tradewinds tradewinds-weather tradewinds-markets` then `pip install 'mostlyright[research]==1.0.0'`
      - `npm uninstall @tradewinds/core @tradewinds/weather @tradewinds/markets tradewinds` then `npm install @mostlyright/core` (or `mostlyright` meta)
      - `mv ~/.tradewinds ~/.mostlyright` (byte-equivalent parquet, no schema change)
      - `TRADEWINDS_CACHE_DIR` env var → `MOSTLYRIGHT_CACHE_DIR` (one-release back-compat with DeprecationWarning; removed in v0.3 of mostlyright)

      ## [0.1.0rc1] — 2026-MM-DD (TestPyPI / npm next)

      Release candidate for the 0.1.0 soak window. See [0.1.0] for the full changeset.

    Commit:
      git add CHANGELOG.md
      git commit -m "phase16 W2: expand CHANGELOG with [1.0.0] + [0.1.0] full sections"
  </action>
  <verify>
    <automated>
    grep -c '^## \[1.0.0\]' CHANGELOG.md  # expect 1
    grep -c '^## \[0.1.0\]' CHANGELOG.md  # expect 1
    grep -c '^## \[0.1.0rc1\]' CHANGELOG.md  # expect 1
    grep -c 'mostlyright==0.14.1' CHANGELOG.md  # expect >=1 (parity citation preserved)
    grep -c 'mv ~/.tradewinds ~/.mostlyright' CHANGELOG.md  # expect >=1 (migration command preserved)
    </automated>
  </verify>
  <done>
    CHANGELOG.md has [Unreleased] + [1.0.0] + [0.1.0] + [0.1.0rc1] sections. [1.0.0] declares zero code change from 0.1.0. [0.1.0] aggregates Phase 1..11 closeouts. Migration commands preserved.
  </done>
</task>

<task type="auto" depends_on="W2-T2">
  <name>W3 Task 1: Lockstep version bump 0.1.0 → 1.0.0 across all 8 packages</name>
  <files>
    packages/core/pyproject.toml,
    packages/weather/pyproject.toml,
    packages/markets/pyproject.toml,
    pyproject.toml,
    uv.lock,
    packages-ts/codegen/package.json,
    packages-ts/core/package.json,
    packages-ts/weather/package.json,
    packages-ts/markets/package.json,
    packages-ts/meta/package.json,
    pnpm-lock.yaml,
    CHANGELOG.md (set the [1.0.0] date)
  </files>
  <read_first>
    .changeset/config.json (fixed group),
    packages/core/pyproject.toml (current `version = "0.1.0"` + inter-package pin `mostlyright>=0.1.0,<0.2`)
  </read_first>
  <action>
    Step 1 — Python bump (mirror Phase 13 W4 pattern):
      python3 -c "
      from pathlib import Path
      for p in [Path('packages/core/pyproject.toml'), Path('packages/weather/pyproject.toml'), Path('packages/markets/pyproject.toml'), Path('pyproject.toml')]:
          t = p.read_text()
          t = t.replace('version = \"0.1.0\"', 'version = \"1.0.0\"')
          t = t.replace('mostlyright>=0.1.0,<0.2', 'mostlyright>=1.0.0,<2.0')
          t = t.replace('mostlyright-weather>=0.1.0,<0.2', 'mostlyright-weather>=1.0.0,<2.0')
          t = t.replace('mostlyright-markets>=0.1.0,<0.2', 'mostlyright-markets>=1.0.0,<2.0')
          p.write_text(t)
      "
      uv lock
      uv sync --all-packages

    Step 2 — TS bump via Changesets `pnpm changeset version` (mirror Phase 14 W4 pattern):
      pnpm changeset  # interactive: pick "major" for the fixed group, summary "v1.0 production-stable promotion"
      pnpm changeset version
      # Confirm: 4 publishable package.json versions are 1.0.0; codegen stays "private": true
      pnpm install  # regen pnpm-lock.yaml

    Step 3 — local sanity:
      uv build --all-packages
      ls dist/mostlyright-1.0.0-py3-none-any.whl dist/mostlyright_weather-1.0.0-py3-none-any.whl dist/mostlyright_markets-1.0.0-py3-none-any.whl
      pnpm -r run build
      pnpm -r run typecheck
      CI=1 pnpm -r run test  # full suite green
      pnpm size-limit  # bundle gates still green at 1.0

    Step 4 — set CHANGELOG.md [1.0.0] date to today's date.

    Step 5 — commit + open PR (NOT directly to main per CLAUDE.md branch workflow):
      git checkout -b release/v1.0.0
      git add packages/*/pyproject.toml pyproject.toml uv.lock packages-ts/*/package.json package.json pnpm-lock.yaml .changeset/ CHANGELOG.md
      git commit -m "release(v1.0.0): bump 7 publishable packages 0.1.0 -> 1.0.0 + CHANGELOG date"
      git push origin release/v1.0.0
      gh pr create --title "release(v1.0.0): production-stable promotion" \
                   --body "Lockstep version bump 0.1.0 -> 1.0.0 across all 7 publishable packages (3 PyPI + 4 npm). No code change. See CHANGELOG.md [1.0.0]. Triggers release.yml + release-ts.yml + docs-publish.yml on merge + tag."

    Step 6 — 1-reviewer codex pass (review discipline trivial-skip exemption: version-bump prose):
      Spawn codex review --base main; expect PASS (the diff IS just version-bump prose + CHANGELOG date).

    Step 7 — merge PR after codex PASS:
      gh pr merge release/v1.0.0 --squash
  </action>
  <verify>
    <automated>
    grep -h '^version = ' packages/core/pyproject.toml packages/weather/pyproject.toml packages/markets/pyproject.toml | sort -u  # expect single line: version = "1.0.0"
    grep -h '"version":' packages-ts/{core,weather,markets,meta}/package.json | sort -u  # expect single line: "version": "1.0.0",
    ls dist/mostlyright-1.0.0-py3-none-any.whl dist/mostlyright_weather-1.0.0-py3-none-any.whl dist/mostlyright_markets-1.0.0-py3-none-any.whl 2>&1 | wc -l | awk '$1 == 3 {exit 0} {exit 1}'
    grep -A1 '^## \[1.0.0\]' CHANGELOG.md | grep -cE '202[6-9]-[01][0-9]-[0-3][0-9]'  # expect 1 (date set)
    git log --oneline main -1 | grep -q 'release(v1.0.0)'
    </automated>
  </verify>
  <done>
    7 publishable packages at 1.0.0 in lockstep. Local builds + tests + size-limit green. `release/v1.0.0` PR merged to main.
  </done>
</task>

<task type="auto" depends_on="W3-T1">
  <name>W3 Task 2: Push v1.0.0 + vts-1.0.0 tags + monitor publishes</name>
  <files>(no file edits — tag + push only)</files>
  <read_first>
    .github/workflows/release.yml,
    .github/workflows/release-ts.yml,
    .github/workflows/docs-publish.yml,
    .planning/phases/13-pypi-publication-pipeline/RUNBOOK.md,
    .planning/phases/14-npm-publication-pipeline/RUNBOOK.md
  </read_first>
  <action>
    Step 1 — pull merged main locally:
      git checkout main && git pull origin main

    Step 2 — tag both:
      git tag v1.0.0 -m "v1.0.0 — production-stable Python SDK"
      git tag vts-1.0.0 -m "vts-1.0.0 — production-stable TypeScript SDK"
      git push origin v1.0.0 vts-1.0.0

    Step 3 — monitor (parallel; 3 workflows fire):
      gh run watch --workflow=release.yml          # 3 PyPI publishes
      gh run watch --workflow=release-ts.yml       # 4 npm publishes
      gh run watch --workflow=docs-publish.yml     # 2 docs regen PRs (one per SDK)
      # All 3 workflows must pass.

    Step 4 — verify PyPI:
      curl -fsS 'https://pypi.org/pypi/mostlyright/1.0.0/json' > /dev/null
      curl -fsS 'https://pypi.org/pypi/mostlyright-weather/1.0.0/json' > /dev/null
      curl -fsS 'https://pypi.org/pypi/mostlyright-markets/1.0.0/json' > /dev/null

    Step 5 — verify npm:
      for pkg in @mostlyright/core @mostlyright/weather @mostlyright/markets mostlyright; do
        curl -fsS "https://registry.npmjs.org/${pkg}" | jq -r '."dist-tags".latest' | grep -q '^1.0.0$' || exit 1
      done

    Step 6 — merge docs-publish PRs on landing repo:
      gh pr list --repo Tarabcak/mostly-right-landing | grep '1.0.0'
      gh pr merge --repo Tarabcak/mostly-right-landing <python-pr-number> --squash
      gh pr merge --repo Tarabcak/mostly-right-landing <ts-pr-number> --squash

    Step 7 — verify Cloudflare Pages deploy:
      sleep 60
      curl -sfL https://mostlyright.md/docs/sdk/python/ | grep -c 'mostlyright'  # expect >=1
      curl -sfL https://mostlyright.md/docs/sdk/typescript/ | grep -c 'mostlyright'  # expect >=1
  </action>
  <verify>
    <automated>
    git ls-remote --tags origin v1.0.0 | wc -l | grep -q '^1$'
    git ls-remote --tags origin vts-1.0.0 | wc -l | grep -q '^1$'
    curl -fsS 'https://pypi.org/pypi/mostlyright/1.0.0/json' > /dev/null
    curl -fsS 'https://pypi.org/pypi/mostlyright-weather/1.0.0/json' > /dev/null
    curl -fsS 'https://pypi.org/pypi/mostlyright-markets/1.0.0/json' > /dev/null
    curl -fsS 'https://registry.npmjs.org/@mostlyright/core' | jq -r '."dist-tags".latest' | grep -q '^1.0.0$'
    curl -fsS 'https://registry.npmjs.org/@mostlyright/weather' | jq -r '."dist-tags".latest' | grep -q '^1.0.0$'
    curl -fsS 'https://registry.npmjs.org/@mostlyright/markets' | jq -r '."dist-tags".latest' | grep -q '^1.0.0$'
    curl -fsS 'https://registry.npmjs.org/mostlyright' | jq -r '."dist-tags".latest' | grep -q '^1.0.0$'
    </automated>
  </verify>
  <done>
    v1.0.0 + vts-1.0.0 published to PyPI + npm `latest`. Docs regen PRs merged + Cloudflare deployed.
  </done>
</task>

<task type="manual" depends_on="W3-T2">
  <name>W4 Task 1: External validation (clock-timed <5 min quickstart)</name>
  <files>.planning/phases/16-v1.0-production-release/16-W4-EXTERNAL-VALIDATION.md (NEW)</files>
  <read_first>
    README.md (the quickstart the external user runs from)
  </read_first>
  <action>
    Step 1 — recruit ≥1 external user. Constraints:
      - NOT the maintainer
      - NOT a Phase 13/14 soak installer (fresh eyes)
      - Has Python 3.12 + Node 20 already installed
      - Has never used mostlyright OR tradewinds

    Step 2 — Give them ONLY the URL to https://github.com/mostlyright/mostlyright-sdk (root README). No out-of-band help.

    Step 3 — Clock the wall time for the combined quickstart:
      1. `pip install 'mostlyright[research]==1.0.0'`
      2. First successful Python `research()` call returning a DataFrame
      3. `npm install @mostlyright/core`
      4. First successful TS `research()` call returning rows

    Target: <5 min combined.

    Step 4 — Log feedback in 16-W4-EXTERNAL-VALIDATION.md:
      - User profile + setup (Python version, Node version, OS)
      - Wall time per step
      - Any blockers (error messages, missing extras, "wait, how do I X" questions)
      - Recommended fixes (file as GH issues; tag `phase16-quickstart-blocker`)

    Step 5 — Triage blockers:
      - **Wall time >5 min** → file 1.0.1 patches to remove friction within 72 hours
      - **Wall time <5 min, no blockers** → declare v1.0 production-ready for marketing
      - **Critical bugs (e.g. `import mostlyright` raises)** → emergency 1.0.1; do NOT declare ready until patched

    Step 6 — commit:
      git add .planning/phases/16-v1.0-production-release/16-W4-EXTERNAL-VALIDATION.md
      git commit -m "phase16 W4: external user clock-timed quickstart validation"
  </action>
  <verify>
    <automated>
    test -f .planning/phases/16-v1.0-production-release/16-W4-EXTERNAL-VALIDATION.md
    grep -cE 'Wall time:' .planning/phases/16-v1.0-production-release/16-W4-EXTERNAL-VALIDATION.md  # expect >=4 (one per step)
    grep -cE '^(Result|Outcome|Conclusion): (PASS|GREEN|<5min|ready)' .planning/phases/16-v1.0-production-release/16-W4-EXTERNAL-VALIDATION.md  # expect >=1
    </automated>
  </verify>
  <done>
    External user validated; quickstart <5 min for both SDKs; no critical blockers; v1.0 declared production-ready.
  </done>
</task>

<task type="auto" depends_on="W4-T1">
  <name>W4 Task 2: Write .planning/RELEASE-RUNBOOK.md + STATE.md closeout</name>
  <files>
    .planning/RELEASE-RUNBOOK.md (NEW),
    .planning/STATE.md (Phase 16 closeout appended)
  </files>
  <read_first>
    .planning/phases/13-pypi-publication-pipeline/RUNBOOK.md,
    .planning/phases/14-npm-publication-pipeline/RUNBOOK.md,
    .planning/STATE.md (Phase 12, 13, 14, 15 closeout shapes)
  </read_first>
  <action>
    Step 1 — write .planning/RELEASE-RUNBOOK.md (top-level summary linking Phase 13/14/15 runbooks):
      # Release Runbook (post-v1.0)

      For routine v1.x and v0.x patch releases. References per-channel runbooks for full details.

      ## Coordinated multi-package release (v1.x or v0.1.x patch)

      1. **Open release PR**: branch `release/v<X.Y.Z>` off main; bump 7 publishable package versions in lockstep:
         - Python: `packages/{core,weather,markets}/pyproject.toml` + `pyproject.toml` workspace root
         - TypeScript: `pnpm changeset` then `pnpm changeset version` (fixed-group lockstep)
         - Regen lockfiles: `uv lock` + `pnpm install`
      2. **CHANGELOG.md**: add `[X.Y.Z]` section above `[Unreleased]`
      3. **Codex review pass** (1-reviewer trivial-skip exemption for version-bump-only diffs)
      4. **Merge to main**
      5. **Push tags**:
         - Python: `git tag v<X.Y.Z> && git push origin v<X.Y.Z>` (fires release.yml + docs-publish.yml)
         - TypeScript: `git tag vts-<X.Y.Z> && git push origin vts-<X.Y.Z>` (fires release-ts.yml + docs-publish.yml)
      6. **Monitor** all 3 workflows green
      7. **Approve** the 2 docs-publish.yml PRs on landing repo; Cloudflare auto-deploys
      8. **Verify** PyPI + npm `latest` resolve to new version; mostlyright.md/docs/sdk/ updated

      ## Per-SDK runbooks (full details)

      - **Python**: see [`phases/13-pypi-publication-pipeline/RUNBOOK.md`](phases/13-pypi-publication-pipeline/RUNBOOK.md)
      - **TypeScript**: see [`phases/14-npm-publication-pipeline/RUNBOOK.md`](phases/14-npm-publication-pipeline/RUNBOOK.md)
      - **Docs**: see [`phases/15-docs-autogen-landing-site/15-CONTEXT.md`](phases/15-docs-autogen-landing-site/15-CONTEXT.md)

      ## Patch release (security fix, hotfix)

      Same flow as above but skip the soak window. rc tags route to TestPyPI / npm `next` and DO NOT trigger docs-publish.yml (so soak doesn't churn docs).

      ## Emergency rollback

      - **PyPI**: artifacts can be **yanked** (UI or `twine yank`) but NEVER deleted. Yank only if shipping a P0 bug; otherwise cut a new patch.
      - **npm**: `npm deprecate @mostlyright/<pkg>@<version> "<reason>"` (unpublish only works <24h after publish for scoped public packages)
      - **docs**: revert the landing repo PR; Cloudflare re-deploys previous state in <1 min

      ## Supported versions policy

      See [SECURITY.md](../SECURITY.md) for the table; in short: latest minor of latest major + security fixes for 1 major back (6 months).

    Step 2 — append Phase 16 closeout to STATE.md (mirror Phase 13/14/15 shape):
      ## Phase 16 closeout (2026-MM-DD) — v1.0.0 Production Release

      All 7 publishable packages (3 PyPI + 4 npm) published at 1.0.0 on `latest` dist-tag.

      **Requirements shipped (10/10):** RELEASE-01..RELEASE-10

      **Files added at repo root:**
      - README.md (rewritten as user-facing marketing copy + 60s quickstart + API surface map + badges)
      - CHANGELOG.md [1.0.0] section
      - CONTRIBUTING.md
      - CODE_OF_CONDUCT.md (Contributor Covenant 2.1)
      - SECURITY.md (90-day disclosure + supported-versions table)
      - .planning/RELEASE-RUNBOOK.md (links Phase 13/14/15 RUNBOOKs)

      **External validation:** <wall time>, <0 blockers / N blockers triaged>

      **Versions live:**
      - https://pypi.org/project/mostlyright/1.0.0/
      - https://pypi.org/project/mostlyright-weather/1.0.0/
      - https://pypi.org/project/mostlyright-markets/1.0.0/
      - https://www.npmjs.com/package/@mostlyright/core/v/1.0.0
      - https://www.npmjs.com/package/@mostlyright/weather/v/1.0.0
      - https://www.npmjs.com/package/@mostlyright/markets/v/1.0.0
      - https://www.npmjs.com/package/mostlyright/v/1.0.0

      **Docs live:** https://mostlyright.md/docs/sdk/ regenerated against 1.0.0

      **Operator follow-ups (post-1.0; optional):**
      1. Transfer or delete orphaned `tradewinds*` PyPI distros + `@tradewinds/*` npm packages (legacy names from pre-Phase-12).
      2. Tag a `support/v0.1` branch on `mostlyright/mostlyright-sdk` for 6-month security-fix backports per SECURITY.md.
      3. Archive `helloiamvu/mostlyright-legacy` (the operator's local folder pre-rename, per Phase 12 OP1) once 1.0 has soaked.

      **v1.x ready:** v1.0 SHIPS the surface; v1.x feature work (ECMWF Tier-2, hosted-backend MCP, polars-default) starts immediately.

    Step 3 — commit:
      git checkout -b phase16/closeout
      git add .planning/RELEASE-RUNBOOK.md .planning/STATE.md
      git commit -m "phase16 W4: .planning/RELEASE-RUNBOOK.md + STATE closeout (v1.0 production-shipped)"
      git push origin phase16/closeout
      gh pr create --title "phase16 closeout: v1.0 production-shipped" --body "Closes Phase 16. See STATE.md for full closeout details and RELEASE-RUNBOOK.md for routine post-1.0 release flow."
      # Merge after codex PASS
      gh pr merge phase16/closeout --squash
  </action>
  <verify>
    <automated>
    test -f .planning/RELEASE-RUNBOOK.md
    grep -cE '^## (Coordinated|Per-SDK|Patch release|Emergency)' .planning/RELEASE-RUNBOOK.md  # expect >=4
    grep -c 'phases/13' .planning/RELEASE-RUNBOOK.md  # expect >=1 (links to Phase 13 RUNBOOK)
    grep -c 'phases/14' .planning/RELEASE-RUNBOOK.md  # expect >=1
    grep -c 'phases/15' .planning/RELEASE-RUNBOOK.md  # expect >=1
    grep -c '^## Phase 16 closeout' .planning/STATE.md  # expect 1
    grep -c 'v1.0 production-shipped\|v1.0.0' .planning/STATE.md  # expect >=1
    </automated>
  </verify>
  <done>
    .planning/RELEASE-RUNBOOK.md committed at repo root linking Phase 13/14/15 RUNBOOKs. STATE.md closeout declares v1.0 production-shipped. Phase 16 PR merged.
  </done>
</task>

</tasks>

<verification>
  <automated>
    # PHASE 16 ACCEPTANCE GATE
    test -f README.md
    test -f CHANGELOG.md
    grep -c '^## \[1.0.0\]' CHANGELOG.md | grep -q '^1$'
    test -f CONTRIBUTING.md
    test -f CODE_OF_CONDUCT.md
    test -f SECURITY.md
    test -f .planning/RELEASE-RUNBOOK.md
    git ls-remote --tags origin v1.0.0 | wc -l | grep -q '^1$'
    git ls-remote --tags origin vts-1.0.0 | wc -l | grep -q '^1$'
    curl -fsS 'https://pypi.org/pypi/mostlyright/1.0.0/json' > /dev/null
    curl -fsS 'https://registry.npmjs.org/@mostlyright/core' | jq -r '."dist-tags".latest' | grep -q '^1.0.0$'
    grep -c '^## Phase 16 closeout' .planning/STATE.md | grep -q '^1$'
  </automated>
</verification>

<success_criteria>
- All 7 publishable packages (3 PyPI + 4 npm) at v1.0.0 on `latest`.
- Root README + 8 per-package READMEs rewritten as user-facing marketing copy.
- CHANGELOG + CONTRIBUTING + CODE_OF_CONDUCT + SECURITY at repo root.
- External user clock-timed quickstart at <5 min combined; no critical blockers.
- https://mostlyright.md/docs/sdk/ regenerated against 1.0.0.
- .planning/RELEASE-RUNBOOK.md links Phase 13/14/15 RUNBOOKs.
- STATE.md declares v1.0 production-shipped.
</success_criteria>

<output>
After completion, create `.planning/phases/16-v1.0-production-release/16-SUMMARY.md` documenting:
- All 7 PyPI + npm URLs at v1.0.0
- Docs site URL + last-deploy timestamp
- External validation wall time + blockers triaged (if any)
- W1..W4 commit SHAs
- v1.x feature work entry points (link to ROADMAP Phase 5+ items)
</output>

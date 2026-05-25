---
phase: 13-pypi-publication-pipeline
type: execute
depends_on: []  # Phase 12 already merged; this phase exercises the rename-renamed workflows
requirements:
  - PYPI-00  # W0: org + cleanup + transfer (NEW 2026-05-25)
  - PYPI-01
  - PYPI-02
  - PYPI-03
  - PYPI-04
  - PYPI-05
  - PYPI-06
  - PYPI-07
  - PYPI-08
tags:
  - pypi
  - release
  - operator-gated
  - cicd
must_haves:
  truths:
    - "All 3 PyPI distros (`mostlyright`, `mostlyright-weather`, `mostlyright-markets`) published at v0.1.0 on prod pypi.org with green CI"
    - "`pip install mostlyright[research]==0.1.0` works in a clean Python 3.12 venv; `python -c 'import mostlyright; mostlyright.research(\"KNYC\", \"2025-01-06\", \"2025-01-12\").head()'` succeeds"
    - "External installer (not the maintainer) timed quickstart at <5 min"
    - "RUNBOOK.md committed; routine future releases follow the documented playbook"
  artifacts:
    - path: ".planning/phases/13-pypi-publication-pipeline/RUNBOOK.md"
      provides: "Routine PyPI release playbook (pre-flight + in-flight + post-publish checklists)"
    - path: ".planning/phases/13-pypi-publication-pipeline/OPERATOR-PREFLIGHT.md"
      provides: "OP1 + OP2 checklist (3 PyPI + 3 TestPyPI publishers + 2 GH Environments)"
    - path: "CHANGELOG.md  # NEW at repo root, seeded with [0.1.0rc1] and [0.1.0] sections"
      provides: "Per-version changelog aggregating phase closeouts; Phase 16 expands to [1.0.0]"
  key_links:
    - from: "git tag v*rc*"
      to: ".github/workflows/release-testpypi.yml"
      via: "GH Actions tag trigger; 3 jobs publish to test.pypi.org via OIDC"
    - from: "git tag v* (non-rc)"
      to: ".github/workflows/release.yml"
      via: "GH Actions tag trigger; version-guard preflight + 3 jobs publish to prod pypi.org via OIDC"
---

<objective>
W0 (NEW 2026-05-25) — **Operator org + repo prep (BLOCKING all later waves):** (a) operator creates `mostlyright` GitHub org, (b) cleanup commit on `main` removes `.planning/` from tracking + dev artifacts (paired with Phase 16 W0), (c) operator transfers `helloiamvu/tradewinds` → `mostlyright/mostlyright-sdk`. Document each step in OPERATOR-PREFLIGHT.md before W1 publisher registration (PyPI OIDC bindings are keyed to `(owner, repo)` so they MUST be registered AFTER the transfer).

W1 — Operator pre-flight (OP1 recommended + OP2 REQUIRED): register 3 PyPI + 3 TestPyPI pending publishers **against `mostlyright/mostlyright-sdk`**, create GH Environments `pypi` + `testpypi` on the new repo. Write operator-confirmation checklist file.

W2 — `v0.1.0rc1` TestPyPI dry-run: bump versions across the 3 pyproject.toml files (already at 0.1.0rc1 from Phase 1), seed CHANGELOG.md `[0.1.0rc1]` section, push tag to `mostlyright/mostlyright-sdk`, monitor release-testpypi.yml, install-from-TestPyPI smoke test in a clean venv.

W3 — Soak: ≥1 week on TestPyPI with at least one external installer confirming the quickstart works end-to-end (clock-timed <5 min).

W4 — `v0.1.0` prod PyPI promotion: bump versions to `0.1.0` (drop `rc1`), seed CHANGELOG.md `[0.1.0]` section, push tag, monitor release.yml, install-from-prod-PyPI smoke test. Write `RUNBOOK.md` documenting the routine for future 0.1.x / 0.2.x releases.

Output: 3 wheels on prod pypi.org at v0.1.0 (publishers bound to `mostlyright/mostlyright-sdk`); clean-venv smoke install works; external installer confirms quickstart works; RUNBOOK.md committed.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/13-pypi-publication-pipeline/13-CONTEXT.md
@.planning/phases/12-rename-to-mostlyright/README.md
@.github/workflows/release.yml
@.github/workflows/release-testpypi.yml
@scripts/check_wheel_metadata.py
@CLAUDE.md
@README.md

# CRITICAL operator pre-flight reminders:
#   - OIDC trusted-publisher binding is keyed to (owner, repo, workflow filename, environment name)
#   - PyPI filename immutability: once `mostlyright-0.1.0rc1-py3-none-any.whl` is on TestPyPI, you CANNOT re-upload it under the same version. Bump to rc2 if you need to retry.
#   - prod PyPI is FOREVER: published artifacts cannot be deleted (only yanked, which keeps the file accessible)
</context>

<tasks>

<task type="manual" depends_on="">
  <name>W0 Task 1: Operator org + cleanup + repo transfer (BLOCKING — added 2026-05-25)</name>
  <files>.planning/phases/13-pypi-publication-pipeline/13-W0-ORG-TRANSFER.md (NEW)</files>
  <read_first>
    .planning/phases/16-v1.0-production-release/16-PLAN.md (cleanup wave — Phase 16 W0; bundle whichever phase ships first),
    CLAUDE.md (commit + branch rules; never commit directly to main)
  </read_first>
  <action>
    Step 1 — write 13-W0-ORG-TRANSFER.md with this exact structure:

      ## Operator pre-flight: org + cleanup + transfer (BLOCKING)

      ### OP0a — Create `mostlyright` GitHub org
        - Visit https://github.com/organizations/new (free tier OK for v1.0; v1.x may upgrade for SSO/team controls)
        - Org name: `mostlyright` — confirm name is available
        - Owner email: operator's primary github email
        - No teams needed yet (single-maintainer for v1.0)
        - Verify: `gh api orgs/mostlyright -q .login` returns `mostlyright` (after creation)

      ### OP0b — Cleanup commit on `main` (BEFORE transfer)
        - Branch from `main`: `git checkout -b cleanup/prepare-public-transfer`
        - Untrack planning artifacts (keep locally; `.gitignore` already lists `.planning/`):
            git rm -r --cached .planning/
        - Remove dev-only artifacts (inventory TBD by Phase 16 W0; minimal set: `spike/`, `.scratch/`, any local-only debug scripts)
        - Replace root README.md with public-facing copy (Phase 16 W1 owns the rewrite; if not yet merged, stub with `# mostlyright\n\nProduction docs coming via Phase 15. Quick start: \`pip install mostlyright\`.`)
        - Commit + open PR titled `cleanup: prepare repo for public transfer (Phase 13 W0)`
        - Review loop: codex `high` + python-architect per .planning/REVIEW-DISCIPLINE.md
        - Merge to `main` BEFORE OP0c

      ### OP0c — Transfer `helloiamvu/tradewinds` → `mostlyright/mostlyright-sdk`
        - Visit https://github.com/helloiamvu/tradewinds/settings → bottom of page → Transfer ownership
        - New owner: `mostlyright`
        - New repo name: `mostlyright-sdk`
        - Confirm: type `helloiamvu/tradewinds` to authorize, click Transfer
        - GitHub auto-redirects `helloiamvu/tradewinds` → `mostlyright/mostlyright-sdk` for 1 year per https://docs.github.com/en/repositories/creating-and-managing-repositories/renaming-a-repository#about-renaming-repositories
        - Local clone update: `git remote set-url origin git@github.com:mostlyright/mostlyright-sdk.git`
        - Verify: `gh repo view mostlyright/mostlyright-sdk -q .url` returns `https://github.com/mostlyright/mostlyright-sdk`

      ### Confirmation checklist (operator marks these in PR description)
      - [ ] OP0a: `mostlyright` GitHub org created
      - [ ] OP0b: cleanup PR merged to `main` on `helloiamvu/tradewinds` (last commit before transfer)
      - [ ] OP0c: repo transferred to `mostlyright/mostlyright-sdk`
      - [ ] Local `origin` remote updated to new URL
      - [ ] CI workflows visible + passing under new repo URL (canary: re-trigger most recent workflow run from Actions tab)

    Step 2 — commit:
      git add .planning/phases/13-pypi-publication-pipeline/13-W0-ORG-TRANSFER.md
      git commit -m "phase13 W0: operator org + cleanup + transfer checklist"
  </action>
  <verify>
    <automated>
    test -f .planning/phases/13-pypi-publication-pipeline/13-W0-ORG-TRANSFER.md
    grep -cE '^- \[ \] OP0[abc]' .planning/phases/13-pypi-publication-pipeline/13-W0-ORG-TRANSFER.md  # expect 3
    grep -c 'mostlyright/mostlyright-sdk' .planning/phases/13-pypi-publication-pipeline/13-W0-ORG-TRANSFER.md  # expect >=3
    grep -c 'github.com/organizations/new' .planning/phases/13-pypi-publication-pipeline/13-W0-ORG-TRANSFER.md  # expect >=1
    </automated>
  </verify>
  <done>
    13-W0-ORG-TRANSFER.md exists with OP0a/OP0b/OP0c steps + verification commands + confirmation checklist. Operator can execute org + cleanup + transfer without ad-hoc help. NO subsequent wave runs until OP0a + OP0b + OP0c all checked off.
  </done>
</task>

<task type="auto" depends_on="W0-T1" wait_for="OP0_TRANSFER_CONFIRMED">
  <name>W1 Task 1: Document operator pre-flight + checklist file</name>
  <files>.planning/phases/13-pypi-publication-pipeline/OPERATOR-PREFLIGHT.md (NEW)</files>
  <read_first>
    .planning/phases/12-rename-to-mostlyright/README.md (OP1-OP4 source format),
    .github/workflows/release.yml (workflow filename + env name to bind publishers to),
    .github/workflows/release-testpypi.yml (same for TestPyPI)
  </read_first>
  <action>
    Step 1 — write OPERATOR-PREFLIGHT.md with this structure (verbatim):
      - Pre-flight summary: 6 manual steps (OP1 recommended + OP2a + OP2b + OP2c three sub-steps for environments)
      - **Pre-condition: W0 OP0a/OP0b/OP0c all checked off (org created, cleanup merged, repo transferred to `mostlyright/mostlyright-sdk`). All PyPI publisher bindings below MUST use the new repo coordinates.**
      - Step-by-step instructions for each, including URLs, field-by-field values to enter on pypi.org / test.pypi.org / GH Settings → Environments
      - For each PyPI publisher form, the exact values are:
          * PyPI Project Name: `mostlyright` (or `-weather` / `-markets`)
          * Owner: `mostlyright`
          * Repository name: `mostlyright-sdk`
          * Workflow filename: `release.yml` (prod) or `release-testpypi.yml` (TestPyPI)
          * Environment name: `pypi` (prod) or `testpypi` (TestPyPI)
      - Verification commands for each step (e.g. `curl -s https://pypi.org/pypi/mostlyright/json | jq '.info.name'` returns 404 = name available, 200 = need transfer; OIDC binding self-verifies only on first publish attempt)
      - 4-line PR-description-ready operator-confirmation checklist:
        - [ ] OP1: `mv ~/Documents/GitHub/mostlyright ~/Documents/GitHub/mostlyright-legacy` (recommended)
        - [ ] OP2a: 3 prod PyPI publishers registered (owner=mostlyright, repo=mostlyright-sdk, workflow=release.yml, env=pypi)
        - [ ] OP2b: 3 TestPyPI publishers registered (owner=mostlyright, repo=mostlyright-sdk, workflow=release-testpypi.yml, env=testpypi)
        - [ ] OP2c: GH Environments `pypi` (required reviewer = operator) + `testpypi` created on `mostlyright/mostlyright-sdk`
    Step 2 — commit:
      git add .planning/phases/13-pypi-publication-pipeline/OPERATOR-PREFLIGHT.md
      git commit -m "phase13 W1: operator pre-flight checklist for PyPI publishers"
  </action>
  <verify>
    <automated>
    test -f .planning/phases/13-pypi-publication-pipeline/OPERATOR-PREFLIGHT.md
    grep -cE '^- \[ \] OP[12][a-c]?:' .planning/phases/13-pypi-publication-pipeline/OPERATOR-PREFLIGHT.md  # expect >=4
    grep -c 'https://pypi.org/manage/account/publishing/' .planning/phases/13-pypi-publication-pipeline/OPERATOR-PREFLIGHT.md  # expect >=1
    grep -c 'https://test.pypi.org/manage/account/publishing/' .planning/phases/13-pypi-publication-pipeline/OPERATOR-PREFLIGHT.md  # expect >=1
    </automated>
  </verify>
  <done>
    Operator-facing checklist exists with URLs + field values + verification commands + 4-line PR-description block. Operator can execute pre-flight without ad-hoc Slack threads.
  </done>
</task>

<task type="auto" depends_on="W1-T1">
  <name>W1 Task 2: Seed CHANGELOG.md at repo root</name>
  <files>CHANGELOG.md (NEW at repo root)</files>
  <read_first>
    .planning/STATE.md (Phase 11 + Phase 12 closeout sections — source for [0.1.0rc1] entry)
  </read_first>
  <action>
    Write CHANGELOG.md following Keep-A-Changelog format:
      # Changelog
      All notable changes to this project will be documented in this file.
      The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
      and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

      ## [Unreleased]
      ### Added
      - (next 0.1.x / 0.2.x changes land here)

      ## [0.1.0rc1] — 2026-MM-DD (TestPyPI soak)
      ### Added
      - (aggregate from Phase 1..12 STATE closeouts)
      ### Changed
      - Phase 12: package renamed from `tradewinds*` to `mostlyright*` across PyPI + npm + cache + schema $id.
      ### Migration
      - `pip uninstall tradewinds tradewinds-weather tradewinds-markets` + `pip install mostlyright[research]==0.1.0rc1`
      - `mv ~/.tradewinds ~/.mostlyright` (byte-equivalent parquet)
      - `TRADEWINDS_CACHE_DIR` → `MOSTLYRIGHT_CACHE_DIR` (one-release back-compat with DeprecationWarning)

    Commit:
      git add CHANGELOG.md
      git commit -m "phase13 W1: seed CHANGELOG.md (Keep-A-Changelog, [Unreleased] + [0.1.0rc1])"
  </action>
  <verify>
    <automated>
    test -f CHANGELOG.md
    grep -c '^## \[Unreleased\]' CHANGELOG.md  # expect 1
    grep -c '^## \[0.1.0rc1\]' CHANGELOG.md  # expect 1
    grep -c 'mostlyright' CHANGELOG.md  # expect >=3
    </automated>
  </verify>
  <done>
    CHANGELOG.md exists at repo root with [Unreleased] + [0.1.0rc1] sections aggregating Phase 1..12 closeouts; migration notes documented.
  </done>
</task>

<task type="auto" depends_on="W1-T1,W1-T2" wait_for="OPERATOR_PREFLIGHT_CONFIRMED">
  <name>W2 Task 1: Tag v0.1.0rc1 and monitor release-testpypi.yml</name>
  <files>(no in-repo file edits — tag + push only)</files>
  <read_first>
    .github/workflows/release-testpypi.yml (verify the workflow triggers on `v*rc*` and routes to env `testpypi`),
    packages/core/pyproject.toml + packages/weather/pyproject.toml + packages/markets/pyproject.toml (confirm `version = "0.1.0rc1"` on all 3)
  </read_first>
  <action>
    Step 1 — operator gate: confirm OPERATOR-PREFLIGHT.md OP1-OP2c all checked off. If not, STOP and prompt operator.

    Step 2 — version sanity check:
      grep -h '^version = ' packages/core/pyproject.toml packages/weather/pyproject.toml packages/markets/pyproject.toml | sort -u
      # Expected output: `version = "0.1.0rc1"` (single line, all 3 agree)
      # If divergent, fix in a separate commit BEFORE tagging.

    Step 3 — tag and push:
      git tag v0.1.0rc1 -m "v0.1.0rc1 — TestPyPI soak (Phase 13 W2)"
      git push origin v0.1.0rc1

    Step 4 — monitor:
      gh run watch --workflow=release-testpypi.yml
      # Wait for all 3 jobs green: publish-core / publish-weather / publish-markets
      # If any fail: dump logs via `gh run view --log <id>`, file fix on `main`, bump to rc2, restart from Step 2

    Step 5 — verify wheels landed:
      curl -s 'https://test.pypi.org/pypi/mostlyright/json' | jq -r '.releases | keys[]' | grep 0.1.0rc1
      curl -s 'https://test.pypi.org/pypi/mostlyright-weather/json' | jq -r '.releases | keys[]' | grep 0.1.0rc1
      curl -s 'https://test.pypi.org/pypi/mostlyright-markets/json' | jq -r '.releases | keys[]' | grep 0.1.0rc1
  </action>
  <verify>
    <automated>
    git tag -l v0.1.0rc1 | grep -c v0.1.0rc1  # expect 1
    git ls-remote --tags origin v0.1.0rc1 | wc -l  # expect 1 (tag pushed)
    # Network-dependent — only verifies if pypi.test reachable from runner:
    curl -fsS 'https://test.pypi.org/pypi/mostlyright/0.1.0rc1/json' > /dev/null  # expect exit 0
    </automated>
  </verify>
  <done>
    3 wheels published to test.pypi.org under version 0.1.0rc1. release-testpypi.yml all 3 jobs green.
  </done>
</task>

<task type="auto" depends_on="W2-T1">
  <name>W2 Task 2: Clean-venv smoke install + quickstart from TestPyPI</name>
  <files>(no in-repo edits — out-of-tree smoke test)</files>
  <read_first>
    README.md (the quickstart the smoke test will reproduce — `pip install mostlyright[research]==0.1.0rc1` + 3-line research() invocation)
  </read_first>
  <action>
    Step 1 — clean venv:
      cd /tmp && rm -rf phase13-smoke && python3 -m venv phase13-smoke && source phase13-smoke/bin/activate

    Step 2 — install from TestPyPI with prod fallback for transitive deps:
      pip install --index-url https://test.pypi.org/simple/ \
                  --extra-index-url https://pypi.org/simple/ \
                  'mostlyright[research]==0.1.0rc1'
      # --extra-index-url ensures transitive deps (pandas, httpx, jsonschema, etc.) resolve from prod PyPI;
      # without it the install fails because TestPyPI doesn't mirror the wider ecosystem.

    Step 3 — version sanity:
      python -c "import mostlyright; print(mostlyright.__version__)"
      # Expected: 0.1.0rc1

    Step 4 — quickstart smoke (mirrors README):
      python -c "import mostlyright as mr; df = mr.research('KNYC', '2025-01-06', '2025-01-12'); print(df.head()); assert len(df) > 0"

    Step 5 — exit venv + cleanup:
      deactivate && rm -rf /tmp/phase13-smoke

    If any step fails: document the failure mode in 13-W2-SMOKE.md and decide between (a) fix on main + bump to rc2, or (b) escalate the rc1 as a TestPyPI-only artifact and proceed with rc2 as the soak candidate.
  </action>
  <verify>
    <automated>
    # Smoke is operator-run; no in-repo automation. Verification = artifact existence + commit.
    test -f .planning/phases/13-pypi-publication-pipeline/13-W2-SMOKE.md  # smoke transcript log
    grep -c 'mostlyright[[:space:]]*==[[:space:]]*0.1.0rc1' .planning/phases/13-pypi-publication-pipeline/13-W2-SMOKE.md  # expect >=1
    grep -c 'PASS\|GREEN\|smoke green' .planning/phases/13-pypi-publication-pipeline/13-W2-SMOKE.md  # expect >=1
    </automated>
  </verify>
  <done>
    Clean Python 3.12 venv installs `mostlyright[research]==0.1.0rc1` from TestPyPI; quickstart works end-to-end. Transcript captured in 13-W2-SMOKE.md.
  </done>
</task>

<task type="manual" depends_on="W2-T2">
  <name>W3 Task 1: ≥1 week soak with external-installer feedback</name>
  <files>.planning/phases/13-pypi-publication-pipeline/13-W3-SOAK-LOG.md (NEW)</files>
  <read_first>
    .planning/phases/13-pypi-publication-pipeline/13-W2-SMOKE.md (smoke result that establishes baseline)
  </read_first>
  <action>
    Step 1 — recruit ≥1 external installer (not the maintainer). Ideal candidate profiles: (a) quant familiar with pandas + Python who never used tradewinds/mostlyright, (b) developer with no domain knowledge (proves the install + quickstart works without insider context).

    Step 2 — give them ONLY: the URL to the README on GitHub (no out-of-band help), a clock to time the quickstart, and a request to file any blocker as a GH issue.

    Step 3 — log feedback in 13-W3-SOAK-LOG.md:
      - Installer name/role + when they ran the smoke
      - Quickstart wall-clock time (target: <5 min for `pip install` + first research() call returning data)
      - Any blockers, error messages, missing extras, undocumented assumptions
      - Whether they hit cache-migration issues from the Phase 12 back-compat shim (TRADEWINDS_CACHE_DIR DeprecationWarning surfacing)

    Step 4 — soak gate: ≥7 calendar days elapsed since rc1 publish AND ≥1 external installer reports no blockers. If blockers found, file fixes on main, bump to rc2, restart W2.
  </action>
  <verify>
    <automated>
    test -f .planning/phases/13-pypi-publication-pipeline/13-W3-SOAK-LOG.md
    grep -cE '^- (Installer|External|Tester):' .planning/phases/13-pypi-publication-pipeline/13-W3-SOAK-LOG.md  # expect >=1
    grep -cE '^- Time-to-first-research\(\):' .planning/phases/13-pypi-publication-pipeline/13-W3-SOAK-LOG.md  # expect >=1
    # Calendar gate (manual operator verification): rc1 tag committed ≥7 days ago
    test $(( ($(date +%s) - $(git log -1 --format=%ct v0.1.0rc1 2>/dev/null || echo 0)) / 86400 )) -ge 7  # expect TRUE
    </automated>
  </verify>
  <done>
    ≥7 days soak; ≥1 external installer confirmed quickstart works; no blockers; soak log committed.
  </done>
</task>

<task type="auto" depends_on="W3-T1">
  <name>W4 Task 1: Bump versions 0.1.0rc1 → 0.1.0 and update CHANGELOG</name>
  <files>
    packages/core/pyproject.toml,
    packages/weather/pyproject.toml,
    packages/markets/pyproject.toml,
    CHANGELOG.md
  </files>
  <read_first>
    packages/core/pyproject.toml (locate the `version = ...` line + `optional-dependencies` blocks that pin `mostlyright-weather>=0.1.0rc1,<0.2`),
    packages/weather/pyproject.toml + packages/markets/pyproject.toml (same — inter-package pins),
    CHANGELOG.md (the [Unreleased] section)
  </read_first>
  <action>
    Step 1 — bump 3 pyproject.toml files via a Python script (mirrors Phase 12 W1 substitution pattern):
      python3 -c "
      from pathlib import Path
      for p in [Path('packages/core/pyproject.toml'), Path('packages/weather/pyproject.toml'), Path('packages/markets/pyproject.toml'), Path('pyproject.toml')]:
          t = p.read_text()
          t = t.replace('version = \"0.1.0rc1\"', 'version = \"0.1.0\"')
          t = t.replace('mostlyright>=0.1.0rc1,<0.2', 'mostlyright>=0.1.0,<0.2')
          t = t.replace('mostlyright-weather>=0.1.0rc1,<0.2', 'mostlyright-weather>=0.1.0,<0.2')
          t = t.replace('mostlyright-markets>=0.1.0rc1,<0.2', 'mostlyright-markets>=0.1.0,<0.2')
          p.write_text(t)
      "

    Step 2 — promote CHANGELOG [Unreleased] → [0.1.0]:
      - Insert `## [0.1.0] — 2026-MM-DD (prod PyPI)` after `## [Unreleased]`
      - Move any [Unreleased] entries into [0.1.0]
      - Leave [Unreleased] empty (next 0.1.x / 0.2.x changes go here)

    Step 3 — regen uv.lock:
      uv lock
      uv sync --all-packages

    Step 4 — local sanity:
      uv build --all-packages
      ls dist/mostlyright-0.1.0-py3-none-any.whl dist/mostlyright_weather-0.1.0-py3-none-any.whl dist/mostlyright_markets-0.1.0-py3-none-any.whl

    Step 5 — commit:
      git add packages/*/pyproject.toml pyproject.toml uv.lock CHANGELOG.md
      git commit -m "release(v0.1.0): bump 3 PyPI distros 0.1.0rc1 -> 0.1.0 + CHANGELOG"
  </action>
  <verify>
    <automated>
    grep -h '^version = ' packages/core/pyproject.toml packages/weather/pyproject.toml packages/markets/pyproject.toml | sort -u  # expect single line: version = "0.1.0"
    grep -c '^## \[0.1.0\]' CHANGELOG.md  # expect 1
    test -f dist/mostlyright-0.1.0-py3-none-any.whl
    test -f dist/mostlyright_weather-0.1.0-py3-none-any.whl
    test -f dist/mostlyright_markets-0.1.0-py3-none-any.whl
    </automated>
  </verify>
  <done>
    3 pyproject.toml at v0.1.0; CHANGELOG promoted; uv.lock regenerated; 3 wheels build cleanly under new version.
  </done>
</task>

<task type="auto" depends_on="W4-T1">
  <name>W4 Task 2: Tag v0.1.0 + monitor release.yml + smoke install from prod PyPI</name>
  <files>(no in-repo file edits — tag + push + out-of-tree smoke)</files>
  <read_first>
    .github/workflows/release.yml (version-guard preflight + 3 publish jobs)
  </read_first>
  <action>
    Step 1 — push tag:
      git tag v0.1.0 -m "v0.1.0 — first production PyPI release (Phase 13 W4)"
      git push origin v0.1.0

    Step 2 — monitor release.yml:
      gh run watch --workflow=release.yml
      # Wait for: version-guard PASS + publish-core PASS + publish-weather PASS + publish-markets PASS
      # check_wheel_metadata.py CI-04 gate runs inside publish-weather + publish-markets — must pass.

    Step 3 — verify on prod PyPI:
      curl -fsS 'https://pypi.org/pypi/mostlyright/0.1.0/json' > /dev/null
      curl -fsS 'https://pypi.org/pypi/mostlyright-weather/0.1.0/json' > /dev/null
      curl -fsS 'https://pypi.org/pypi/mostlyright-markets/0.1.0/json' > /dev/null

    Step 4 — clean-venv smoke install from prod PyPI:
      cd /tmp && rm -rf phase13-prod-smoke && python3 -m venv phase13-prod-smoke && source phase13-prod-smoke/bin/activate
      pip install 'mostlyright[research]==0.1.0'  # NO --index-url override; pulls from prod PyPI default
      python -c "import mostlyright as mr; print(mr.__version__); df = mr.research('KNYC', '2025-01-06', '2025-01-12'); print(df.head())"
      deactivate && rm -rf /tmp/phase13-prod-smoke

    Step 5 — log result in 13-W4-PROD-SMOKE.md (mirror W2 smoke log shape).
  </action>
  <verify>
    <automated>
    git ls-remote --tags origin v0.1.0 | wc -l  # expect 1
    curl -fsS 'https://pypi.org/pypi/mostlyright/0.1.0/json' > /dev/null  # expect exit 0
    test -f .planning/phases/13-pypi-publication-pipeline/13-W4-PROD-SMOKE.md
    grep -c 'PASS\|GREEN\|smoke green' .planning/phases/13-pypi-publication-pipeline/13-W4-PROD-SMOKE.md  # expect >=1
    </automated>
  </verify>
  <done>
    3 wheels live on prod pypi.org at v0.1.0; clean-venv smoke install + quickstart works; W4 prod-smoke log committed.
  </done>
</task>

<task type="auto" depends_on="W4-T2">
  <name>W4 Task 3: Write RUNBOOK.md + STATE closeout</name>
  <files>
    .planning/phases/13-pypi-publication-pipeline/RUNBOOK.md (NEW),
    .planning/STATE.md (Phase 13 closeout section appended)
  </files>
  <read_first>
    .planning/STATE.md (Phase 12 closeout shape — match format)
  </read_first>
  <action>
    Step 1 — write RUNBOOK.md for routine future PyPI releases (0.1.1 / 0.2.0 / 1.0.0):
      sections:
        - Header note: repo coordinates are `mostlyright/mostlyright-sdk` (operator transferred from `helloiamvu/tradewinds` in W0). All `gh` commands assume `origin = git@github.com:mostlyright/mostlyright-sdk.git`.
        - Pre-flight checklist (8 items): pull main, parity gate green, version-bump PR opened, CHANGELOG section drafted, all 3 pyproject.toml in lockstep, uv.lock regenerated, local `uv build` clean, PR merged
        - Tag + push: `git tag v<N.N.N> && git push origin v<N.N.N>` (rc tags route to release-testpypi.yml; non-rc tags route to release.yml)
        - In-flight monitoring: `gh run watch --workflow=release.yml` and Actions tab Environments approval gate (Settings → Environments → `pypi` on `mostlyright/mostlyright-sdk`)
        - Post-publish verification: clean-venv smoke install + import + research() call (5 lines reproduced verbatim from W2-T2)
        - Rollback / yank policy: prod PyPI artifacts can be yanked (`twine` or pypi.org UI), never deleted. Yank a version only if it ships a P0 bug; cut a new patch instead.

    Step 2 — append Phase 13 closeout to STATE.md (mirror Phase 12 closeout shape: shipped/preserve-list/test-delta/files-added/operator-followups).

    Step 3 — single W4 commit:
      git add .planning/phases/13-pypi-publication-pipeline/RUNBOOK.md .planning/STATE.md .planning/phases/13-pypi-publication-pipeline/13-W4-PROD-SMOKE.md
      git commit -m "phase13 W4: prod PyPI smoke + RUNBOOK.md + STATE closeout"
  </action>
  <verify>
    <automated>
    test -f .planning/phases/13-pypi-publication-pipeline/RUNBOOK.md
    grep -cE '^## (Pre-flight|In-flight|Post-publish|Rollback)' .planning/phases/13-pypi-publication-pipeline/RUNBOOK.md  # expect >=4
    grep -c '^## Phase 13 closeout' .planning/STATE.md  # expect 1
    git log --oneline -1 | grep -q 'phase13 W4'
    </automated>
  </verify>
  <done>
    RUNBOOK.md documents routine future PyPI releases. STATE.md closeout section appended. Phase 13 ready to merge to main.
  </done>
</task>

</tasks>

<verification>
  <automated>
    # WAVE 13 ACCEPTANCE GATE — all must pass before Phase 14 starts
    test -f .planning/phases/13-pypi-publication-pipeline/13-W0-ORG-TRANSFER.md
    test -f .planning/phases/13-pypi-publication-pipeline/OPERATOR-PREFLIGHT.md
    test -f CHANGELOG.md
    # New-repo binding check: origin must point at mostlyright-sdk after W0
    git remote get-url origin | grep -q 'mostlyright/mostlyright-sdk'
    grep -c '^## \[0.1.0\]' CHANGELOG.md | grep -q '^1$'
    git ls-remote --tags origin v0.1.0rc1 | wc -l | grep -q '^1$'
    git ls-remote --tags origin v0.1.0 | wc -l | grep -q '^1$'
    curl -fsS 'https://pypi.org/pypi/mostlyright/0.1.0/json' > /dev/null
    curl -fsS 'https://pypi.org/pypi/mostlyright-weather/0.1.0/json' > /dev/null
    curl -fsS 'https://pypi.org/pypi/mostlyright-markets/0.1.0/json' > /dev/null
    test -f .planning/phases/13-pypi-publication-pipeline/RUNBOOK.md
    grep -c '^## Phase 13 closeout' .planning/STATE.md | grep -q '^1$'
  </automated>
</verification>

<success_criteria>
- All 3 PyPI distros (`mostlyright`, `mostlyright-weather`, `mostlyright-markets`) published at v0.1.0 on prod pypi.org with green CI.
- `pip install mostlyright[research]==0.1.0` works in a clean Python 3.12 venv; quickstart runs end-to-end.
- External installer timed quickstart at <5 min.
- TestPyPI rc1 wheels published and soaked ≥1 week before prod promotion.
- RUNBOOK.md documents routine future-release flow.
- STATE.md closeout section appended in standard Phase-N format.
</success_criteria>

<output>
After completion, create `.planning/phases/13-pypi-publication-pipeline/13-SUMMARY.md` documenting:
- 3 PyPI publishers + 3 TestPyPI publishers registered (with dates of confirmation)
- TestPyPI rc1 publish: 3 wheel URLs + timestamps
- Soak window: rc1 publish date → 0.1.0 publish date (gap ≥7 calendar days)
- External installer feedback summary
- Prod PyPI 0.1.0 publish: 3 wheel URLs + timestamps + verification curl results
- RUNBOOK.md TOC
- W1..W4 commit SHAs in order
- Ready-for-Phase-14 confirmation
</output>

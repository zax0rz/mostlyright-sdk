---
phase: 14-npm-publication-pipeline
type: execute
depends_on: [13-pypi-publication-pipeline]  # Python publishes first; TS schemas codegen-shared. Phase 13 W0 (org create + repo transfer to mostlyrightmd/mostlyright-sdk) is a HARD prerequisite — npm OIDC publishers MUST bind to the new repo.
requirements:
  - NPM-01
  - NPM-02
  - NPM-03
  - NPM-04
  - NPM-05
  - NPM-06
  - NPM-07
  - NPM-08
  - NPM-09
tags:
  - npm
  - release
  - operator-gated
  - cicd
  - typescript
must_haves:
  truths:
    - "All 4 npm packages (`@mostlyrightmd/{core,weather,markets}` + unscoped meta `mostlyright`) published at vts-0.1.0 on npm with `latest` dist-tag"
    - "`npm install @mostlyrightmd/core` in clean Node 20 + pnpm 9 project resolves to 0.1.0; smoke import works"
    - "Browser smoke via `packages-ts/examples/chrome-extension-mvp/` rebuilt against latest works in Chrome MV3 SW"
    - "size-limit gates green on every publish (core ≤25KB / weather ≤35KB / markets ≤10KB / meta ≤70KB min+gzip)"
    - "scripts/release-ts-preflight.mjs Phase 12 iter-1 CRITICAL fix verified: peerDependencies['@mostlyrightmd/core'] rewritten on each publish"
    - "RUNBOOK.md committed"
  artifacts:
    - path: ".planning/phases/14-npm-publication-pipeline/RUNBOOK.md"
      provides: "Routine npm release playbook"
    - path: ".planning/phases/14-npm-publication-pipeline/OPERATOR-PREFLIGHT.md"
      provides: "OP3 + OP4 checklist (`@mostlyrightmd` scope + 4 OIDC publishers + 1 GH Environment)"
  key_links:
    - from: "git tag vts-*rc*"
      to: ".github/workflows/release-ts.yml"
      via: "GH Actions tag trigger; 4 packages publish to npm `--tag next` via OIDC"
    - from: "git tag vts-* (non-rc)"
      to: ".github/workflows/release-ts.yml"
      via: "same workflow; dist-tag routes to `latest` per release-ts.yml dist_tag step"
---

<objective>
**Pre-condition: Phase 13 W0 closed (mostlyrightmd GitHub org created, repo transferred to `mostlyrightmd/mostlyright-sdk`). All npm OIDC publishers below MUST be registered AFTER the transfer, against the new repo coordinates.**

W1 — Operator pre-flight (OP3 + OP4): claim `@mostlyrightmd` npm scope **under the mostlyrightmd GitHub org's linked npm account**, register 4 npm OIDC pending publishers bound to `mostlyrightmd/mostlyright-sdk`, create GH Environment `npm` on the new repo. Write operator-confirmation checklist.

W2 — `vts-0.1.0rc1` npm `next` dry-run: run `pnpm changeset` for the bump, push tag, monitor release-ts.yml, install-from-npm-next smoke in clean Node 20 + pnpm 9 project, rebuild + load `examples/chrome-extension-mvp/` against rc1 IIFE bundle.

W3 — Soak: ≥1 week on npm `next` with external installer confirming both Node and browser smoke work.

W4 — `vts-0.1.0` npm `latest` promotion: `pnpm changeset version` to 0.1.0, push tag, monitor release-ts.yml `--tag latest`, clean-project smoke install + browser smoke, verify size-limit gates, verify release-ts-preflight.mjs peer-key rewrite fires. Write RUNBOOK.md.

Output: 4 packages on npm `latest` at vts-0.1.0; clean-project smoke + browser smoke both green; RUNBOOK.md committed.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/14-npm-publication-pipeline/14-CONTEXT.md
@.planning/phases/13-pypi-publication-pipeline/RUNBOOK.md  # if Phase 13 already shipped
@.planning/phases/12-rename-to-mostlyright/README.md
@.github/workflows/release-ts.yml
@scripts/release-ts-preflight.mjs
@.changeset/config.json
@.changeset/README.md
@packages-ts/examples/chrome-extension-mvp/README.md
@CLAUDE.md
</context>

<tasks>

<task type="auto" depends_on="">
  <name>W1 Task 1: Document operator pre-flight + checklist file</name>
  <files>.planning/phases/14-npm-publication-pipeline/OPERATOR-PREFLIGHT.md (NEW)</files>
  <read_first>
    .planning/phases/12-rename-to-mostlyright/README.md (OP3+OP4 source format),
    .github/workflows/release-ts.yml (workflow filename + env name to bind publishers to),
    .changeset/config.json (fixed-group declaration — confirm the 4 names match what publishers register)
  </read_first>
  <action>
    Step 1 — write OPERATOR-PREFLIGHT.md:
      - Pre-condition: Phase 13 W0 OP0a/OP0b/OP0c all checked (org `mostlyright` created, repo transferred to `mostlyrightmd/mostlyright-sdk`). If not yet shipped, STOP and wait.
      - Pre-flight summary: 6 manual steps (OP3 scope claim + 4 OP4a publisher registrations + OP4b GH env)
      - Field-by-field values for each npmjs.com pending-publisher form:
        - Package name: `@mostlyrightmd/core` / `@mostlyrightmd/weather` / `@mostlyrightmd/markets` / `mostlyright`
        - GitHub owner: `mostlyrightmd` (NOT helloiamvu — repo was transferred in Phase 13 W0)
        - Repository: `mostlyright-sdk` (NOT tradewinds — renamed during transfer)
        - Workflow filename: `release-ts.yml`
        - Environment name: `npm`
      - OP3 scope-claim instructions (with screenshot citations):
        * Log into npmjs.com with the same operator account that owns the `mostlyright` GH org
        * Visit https://www.npmjs.com/settings/{operator-username}/orgs (or hit "Create New Organization" if no npm org exists yet)
        * Create npm scope `@mostlyrightmd` (free tier OK for v1.0; paid tier later for private packages)
        * Set scope visibility = public
        * Documented org link: this scope is "owned by the operator" but conceptually linked to the GitHub `mostlyrightmd` org — future team handoff plan: invite collaborators to npm org rather than transfer ownership
        * Fallback if `@mostlyrightmd` is squatted: unscoped names per `.planning/research/TS-SDK-DESIGN.md` §13.1 (P0 fork point)
      - OP4b GH Environment creation steps: Settings → Environments → New → `npm` → Required reviewers = operator. (Note: settings live at https://github.com/mostlyrightmd/mostlyright-sdk/settings/environments/new)
      - Verification commands:
        - `curl -s 'https://registry.npmjs.org/-/v1/search?text=@mostlyrightmd/core' | jq` (returns empty before first publish; populated after)
        - `gh api repos/mostlyrightmd/mostlyright-sdk/environments` (lists configured environments; replaces the pre-transfer `helloiamvu/tradewinds` form)
      - 5-line PR-description-ready operator-confirmation checklist:
        - [ ] OP3: `@mostlyrightmd` npm scope claimed (public access; linked to the mostlyright GH org's operator account)
        - [ ] OP4a-i: `@mostlyrightmd/core` OIDC publisher registered (owner=mostlyrightmd, repo=mostlyright-sdk)
        - [ ] OP4a-ii: `@mostlyrightmd/weather` OIDC publisher registered (owner=mostlyrightmd, repo=mostlyright-sdk)
        - [ ] OP4a-iii: `@mostlyrightmd/markets` OIDC publisher registered (owner=mostlyrightmd, repo=mostlyright-sdk)
        - [ ] OP4a-iv: `mostlyright` (meta) OIDC publisher registered (owner=mostlyrightmd, repo=mostlyright-sdk)
        - [ ] OP4b: GH Environment `npm` created on `mostlyrightmd/mostlyright-sdk` with required reviewer

    Step 2 — commit:
      git add .planning/phases/14-npm-publication-pipeline/OPERATOR-PREFLIGHT.md
      git commit -m "phase14 W1: operator pre-flight checklist for npm publishers + @mostlyrightmd scope"
  </action>
  <verify>
    <automated>
    test -f .planning/phases/14-npm-publication-pipeline/OPERATOR-PREFLIGHT.md
    grep -cE '^- \[ \] OP[34][a-z-]*[iv]*:' .planning/phases/14-npm-publication-pipeline/OPERATOR-PREFLIGHT.md  # expect >=5
    grep -c 'release-ts.yml' .planning/phases/14-npm-publication-pipeline/OPERATOR-PREFLIGHT.md  # expect >=2
    grep -c '@mostlyright' .planning/phases/14-npm-publication-pipeline/OPERATOR-PREFLIGHT.md  # expect >=5
    </automated>
  </verify>
  <done>
    Operator-facing checklist exists with field-by-field publisher form values + scope-claim instructions + GH Environment steps + verification commands.
  </done>
</task>

<task type="auto" depends_on="W1-T1" wait_for="OPERATOR_PREFLIGHT_CONFIRMED">
  <name>W2 Task 1: Create rc1 changeset + push vts-0.1.0rc1 tag</name>
  <files>
    .changeset/*.md (NEW changeset markdown via `pnpm changeset`),
    packages-ts/*/package.json (version bumped 0.0.0 → 0.1.0-rc.1 by `pnpm changeset version`),
    package.json + pnpm-lock.yaml (updated by changeset version)
  </files>
  <read_first>
    .changeset/config.json (fixed group),
    .changeset/README.md (workflow doc — Phase 12 iter-1 already updated),
    .github/workflows/release-ts.yml (dist_tag step that routes rc → next)
  </read_first>
  <action>
    Step 1 — operator gate: confirm OPERATOR-PREFLIGHT.md OP3 + OP4a-i..iv + OP4b all checked. If not, STOP.

    Step 2 — pnpm changeset (interactive):
      pnpm changeset
      # Pick all 4 packages in the fixed group (changesets-cli auto-selects via fixed-group rule)
      # Bump type: minor (0.0.0 → 0.1.0)
      # Summary: "Initial release candidate for soak on npm next channel. Phase 11 (live streaming) + Phase 12 (rename) shipped. See CHANGELOG.md."

    Step 3 — promote rc1:
      pnpm changeset pre enter rc
      pnpm changeset version
      # version bump 0.0.0 → 0.1.0-rc.1 lockstep across 4 packages
      # Examine git diff: 4 package.json + CHANGELOG.md files + pnpm-lock.yaml updated

    Step 4 — local build + test sanity:
      pnpm -r run build
      pnpm -r run typecheck
      CI=1 pnpm -r run test
      pnpm size-limit  # bundle gates green

    Step 5 — commit + tag:
      git add packages-ts .changeset/ pnpm-lock.yaml
      git commit -m "release(vts-0.1.0-rc.1): npm rc1 soak release"
      git tag vts-0.1.0-rc.1 -m "vts-0.1.0-rc.1 — npm next-channel soak"
      git push origin main vts-0.1.0-rc.1
      # Note: changesets uses `0.1.0-rc.1` semver-compliant pre-release format.
      # release-ts.yml dist_tag step matches /rc/ → routes to `--tag next`.

    Step 6 — monitor:
      gh run watch --workflow=release-ts.yml
      # Wait for: pnpm build PASS, version-guard PASS, 4 publish steps PASS (--tag next), provenance attestation emitted.
  </action>
  <verify>
    <automated>
    grep -h '"version":' packages-ts/core/package.json packages-ts/weather/package.json packages-ts/markets/package.json packages-ts/meta/package.json | sort -u  # expect single line: "version": "0.1.0-rc.1",
    git ls-remote --tags origin vts-0.1.0-rc.1 | wc -l  # expect 1
    # Network-dependent post-publish:
    curl -fsS 'https://registry.npmjs.org/@mostlyrightmd/core' | jq -r '."dist-tags".next' | grep -c '0.1.0-rc.1'  # expect 1
    curl -fsS 'https://registry.npmjs.org/@mostlyrightmd/weather' | jq -r '."dist-tags".next' | grep -c '0.1.0-rc.1'  # expect 1
    </automated>
  </verify>
  <done>
    4 packages published to npm `next` channel at 0.1.0-rc.1. release-ts.yml all jobs green; provenance attestation emitted.
  </done>
</task>

<task type="auto" depends_on="W2-T1">
  <name>W2 Task 2: Clean Node 20 + pnpm 9 smoke install + browser smoke</name>
  <files>(no in-repo edits — out-of-tree smoke tests; transcript logged)</files>
  <read_first>
    packages-ts/examples/chrome-extension-mvp/README.md (browser smoke procedure)
  </read_first>
  <action>
    Step 1 — clean Node project:
      cd /tmp && rm -rf phase14-smoke && mkdir phase14-smoke && cd phase14-smoke
      pnpm init -y
      pnpm add @mostlyrightmd/core@next

    Step 2 — version + ESM import:
      node -e "import('@mostlyrightmd/core').then(m => console.log(Object.keys(m).length))"
      # Expected: a positive number; named exports include research, KnowledgeView, etc.

    Step 3 — research() smoke (Node fetch path):
      cat > smoke.mjs <<'EOF'
      import { research } from '@mostlyrightmd/core';
      const rows = await research('KNYC', '2025-01-06', '2025-01-12');
      console.log('rows:', rows.length, '/ first:', rows[0]);
      EOF
      node smoke.mjs
      # Expected: rows array populated

    Step 4 — exit + cleanup:
      cd / && rm -rf /tmp/phase14-smoke

    Step 5 — browser smoke via examples/chrome-extension-mvp/:
      cd packages-ts/examples/chrome-extension-mvp/
      # Edit src to import from `@mostlyrightmd/core` (NOT the in-repo workspace path);
      # publish the extension's package.json with a real dep `"@mostlyrightmd/core": "next"` so pnpm install pulls from npm.
      pnpm install
      pnpm run build  # produces extension dist/
      # Load dist/ as unpacked extension in Chrome MV3 (manual operator step)
      # Click the action button on a kalshi.com page — verify the AWC live METAR overlay renders
      # Document in 14-W2-BROWSER-SMOKE.md: Chrome version, extension manifest_version, AWC response timestamp, screenshot
  </action>
  <verify>
    <automated>
    test -f .planning/phases/14-npm-publication-pipeline/14-W2-SMOKE.md  # node smoke transcript
    test -f .planning/phases/14-npm-publication-pipeline/14-W2-BROWSER-SMOKE.md  # browser smoke transcript
    grep -c 'PASS\|GREEN\|smoke green' .planning/phases/14-npm-publication-pipeline/14-W2-SMOKE.md  # expect >=1
    grep -c 'PASS\|GREEN\|browser smoke green' .planning/phases/14-npm-publication-pipeline/14-W2-BROWSER-SMOKE.md  # expect >=1
    </automated>
  </verify>
  <done>
    Node 20 + pnpm 9 clean install of `@mostlyrightmd/core@next` works; ESM + research() smoke pass. Browser smoke via Chrome MV3 SW + kalshi.com overlay works. Both transcripts committed.
  </done>
</task>

<task type="manual" depends_on="W2-T2">
  <name>W3 Task 1: ≥1 week soak with external installer feedback</name>
  <files>.planning/phases/14-npm-publication-pipeline/14-W3-SOAK-LOG.md (NEW)</files>
  <read_first>
    .planning/phases/14-npm-publication-pipeline/14-W2-SMOKE.md + 14-W2-BROWSER-SMOKE.md (baseline)
  </read_first>
  <action>
    Step 1 — recruit ≥1 external installer (not the maintainer). Ideal profiles: (a) frontend dev familiar with TS + Vite/Next who never used mostlyright/tradewinds, (b) Chrome extension dev who can validate the IIFE bundle in MV3 SW.

    Step 2 — give them ONLY: the URL to README on GitHub + URL to docs/ts-quickstart.md + clock to time both Node + browser quickstarts. Request to file blockers as GH issues.

    Step 3 — log feedback in 14-W3-SOAK-LOG.md:
      - Installer name/role + Node + Chrome versions used
      - Quickstart wall-clock time (target: <5 min for `pnpm add @mostlyrightmd/core@next` + first research() call returning data)
      - Any blockers: missing peer deps, browser CSP violations, bundle size surprises, TS type errors
      - Whether they hit cache-migration issues from Phase 12 back-compat shim

    Step 4 — soak gate: ≥7 calendar days elapsed since vts-0.1.0-rc.1 publish AND ≥1 external installer reports no blockers on both Node and browser. If blockers found, file fixes on main, bump to rc2, restart W2.
  </action>
  <verify>
    <automated>
    test -f .planning/phases/14-npm-publication-pipeline/14-W3-SOAK-LOG.md
    grep -cE '^- (Installer|External|Tester):' .planning/phases/14-npm-publication-pipeline/14-W3-SOAK-LOG.md  # expect >=1
    grep -c 'Node' .planning/phases/14-npm-publication-pipeline/14-W3-SOAK-LOG.md  # expect >=1
    grep -c 'browser\|Chrome\|MV3' .planning/phases/14-npm-publication-pipeline/14-W3-SOAK-LOG.md  # expect >=1
    test $(( ($(date +%s) - $(git log -1 --format=%ct vts-0.1.0-rc.1 2>/dev/null || echo 0)) / 86400 )) -ge 7
    </automated>
  </verify>
  <done>
    ≥7 days soak; ≥1 external installer confirmed Node + browser quickstarts work; no blockers; soak log committed.
  </done>
</task>

<task type="auto" depends_on="W3-T1">
  <name>W4 Task 1: Promote vts-0.1.0-rc.1 → vts-0.1.0 + push tag + monitor release-ts.yml</name>
  <files>
    packages-ts/*/package.json (version bumped 0.1.0-rc.1 → 0.1.0 by `pnpm changeset version`),
    .changeset/*.md (consumed by version step),
    CHANGELOG.md per package + repo root,
    pnpm-lock.yaml
  </files>
  <read_first>
    .changeset/config.json (fixed group),
    .github/workflows/release-ts.yml (dist_tag step routes non-rc → `--tag latest`)
  </read_first>
  <action>
    Step 1 — exit pre-release mode:
      pnpm changeset pre exit
      pnpm changeset version
      # Bumps 0.1.0-rc.1 → 0.1.0 lockstep across 4 packages.

    Step 2 — local build + test + size-limit sanity:
      pnpm -r run build
      pnpm -r run typecheck
      CI=1 pnpm -r run test
      pnpm size-limit

    Step 3 — verify release-ts-preflight.mjs locally (sanity — the workflow re-runs in CI):
      node scripts/release-ts-preflight.mjs
      # Expected: 'Rewrote packages-ts/weather peerDependencies[@mostlyrightmd/core]: ... → ^0.1.0' x2 (weather + markets), then 'Preflight green; safe to publish.'
      # If the script throws because peer key absent → P0 STOP; fix the preflight before tagging.

    Step 4 — commit + tag + push:
      git add packages-ts .changeset/ CHANGELOG.md pnpm-lock.yaml
      git commit -m "release(vts-0.1.0): npm latest-channel promotion"
      git tag vts-0.1.0 -m "vts-0.1.0 — first production npm release (Phase 14 W4)"
      git push origin main vts-0.1.0

    Step 5 — monitor release-ts.yml:
      gh run watch --workflow=release-ts.yml
      # Verify: dist_tag step outputs `latest` (NOT next); 4 publish steps PASS; OIDC provenance attestation emitted; size-limit step green.
  </action>
  <verify>
    <automated>
    grep -h '"version":' packages-ts/core/package.json packages-ts/weather/package.json packages-ts/markets/package.json packages-ts/meta/package.json | sort -u  # expect single line: "version": "0.1.0",
    git ls-remote --tags origin vts-0.1.0 | wc -l  # expect 1
    # Post-publish (network-dependent):
    curl -fsS 'https://registry.npmjs.org/@mostlyrightmd/core' | jq -r '."dist-tags".latest' | grep -c '^0.1.0$'  # expect 1
    curl -fsS 'https://registry.npmjs.org/@mostlyrightmd/weather' | jq -r '."dist-tags".latest' | grep -c '^0.1.0$'  # expect 1
    curl -fsS 'https://registry.npmjs.org/@mostlyrightmd/markets' | jq -r '."dist-tags".latest' | grep -c '^0.1.0$'  # expect 1
    curl -fsS 'https://registry.npmjs.org/mostlyright' | jq -r '."dist-tags".latest' | grep -c '^0.1.0$'  # expect 1
    </automated>
  </verify>
  <done>
    4 packages live on npm at vts-0.1.0 with `latest` dist-tag. release-ts.yml all jobs green. preflight rewrote peer keys correctly.
  </done>
</task>

<task type="auto" depends_on="W4-T1">
  <name>W4 Task 2: Prod-channel smoke install + browser smoke + RUNBOOK.md + STATE closeout</name>
  <files>
    .planning/phases/14-npm-publication-pipeline/RUNBOOK.md (NEW),
    .planning/phases/14-npm-publication-pipeline/14-W4-PROD-SMOKE.md (NEW),
    .planning/STATE.md (Phase 14 closeout appended)
  </files>
  <read_first>
    .planning/phases/13-pypi-publication-pipeline/RUNBOOK.md (mirror Python format),
    .planning/STATE.md (Phase 13 closeout shape)
  </read_first>
  <action>
    Step 1 — clean Node project smoke install (NO @next, expects to resolve from `latest`):
      cd /tmp && rm -rf phase14-prod-smoke && mkdir phase14-prod-smoke && cd phase14-prod-smoke
      pnpm init -y
      pnpm add @mostlyrightmd/core  # No @next; resolves to latest
      node -e "import('@mostlyrightmd/core').then(m => console.log(Object.keys(m).length))"
      cd / && rm -rf /tmp/phase14-prod-smoke

    Step 2 — browser smoke from npm `latest`:
      Update packages-ts/examples/chrome-extension-mvp/package.json:
        "dependencies": { "@mostlyrightmd/core": "latest" }  # was @next
      pnpm install
      pnpm run build
      Load in Chrome MV3 manually; verify kalshi.com overlay still renders.

    Step 3 — write RUNBOOK.md:
      sections (mirror Phase 13 RUNBOOK.md):
        - Pre-flight checklist (9 items): pull main, parity gate green, all tests green, pnpm changeset prompted with bump type, CHANGELOG entries drafted, fixed-group lockstep verified, pnpm-lock.yaml regenerated, local size-limit green, PR merged
        - Tag + push: `git tag vts-<N.N.N>` (rc → next, non-rc → latest)
        - In-flight monitoring: `gh run watch --workflow=release-ts.yml` + Actions tab Environments approval gate
        - Post-publish verification (Node + Browser): copy from W2-T2 + W4-T2 commands
        - Rollback / deprecate policy: `npm deprecate @mostlyrightmd/core@0.1.0 "<reason>"` instead of unpublish (which fails after 24h grace window for non-private scopes)
        - Provenance verification: `npm view @mostlyrightmd/core@0.1.0 --json | jq '.attestations'` shows the OIDC attestation block

    Step 4 — append Phase 14 closeout to STATE.md (mirror Phase 13 + 12 closeout shapes).

    Step 5 — commit:
      git add .planning/phases/14-npm-publication-pipeline/ .planning/STATE.md
      git commit -m "phase14 W4: npm prod smoke + RUNBOOK.md + STATE closeout"
  </action>
  <verify>
    <automated>
    test -f .planning/phases/14-npm-publication-pipeline/RUNBOOK.md
    grep -cE '^## (Pre-flight|In-flight|Post-publish|Rollback|Provenance)' .planning/phases/14-npm-publication-pipeline/RUNBOOK.md  # expect >=5
    test -f .planning/phases/14-npm-publication-pipeline/14-W4-PROD-SMOKE.md
    grep -c '^## Phase 14 closeout' .planning/STATE.md  # expect 1
    git log --oneline -1 | grep -q 'phase14 W4'
    </automated>
  </verify>
  <done>
    Prod-channel Node + browser smoke green. RUNBOOK.md committed. STATE.md closeout appended. Phase 14 ready to merge to main.
  </done>
</task>

</tasks>

<verification>
  <automated>
    # WAVE 14 ACCEPTANCE GATE — all must pass before Phase 15 starts
    test -f .planning/phases/14-npm-publication-pipeline/OPERATOR-PREFLIGHT.md
    # Phase 13 W0 prerequisite check: origin must be mostlyrightmd/mostlyright-sdk
    git remote get-url origin | grep -q 'mostlyrightmd/mostlyright-sdk'
    git ls-remote --tags origin vts-0.1.0-rc.1 | wc -l | grep -q '^1$'
    git ls-remote --tags origin vts-0.1.0 | wc -l | grep -q '^1$'
    curl -fsS 'https://registry.npmjs.org/@mostlyrightmd/core' | jq -r '."dist-tags".latest' | grep -q '^0.1.0$'
    curl -fsS 'https://registry.npmjs.org/@mostlyrightmd/weather' | jq -r '."dist-tags".latest' | grep -q '^0.1.0$'
    curl -fsS 'https://registry.npmjs.org/@mostlyrightmd/markets' | jq -r '."dist-tags".latest' | grep -q '^0.1.0$'
    curl -fsS 'https://registry.npmjs.org/mostlyright' | jq -r '."dist-tags".latest' | grep -q '^0.1.0$'
    test -f .planning/phases/14-npm-publication-pipeline/RUNBOOK.md
    grep -c '^## Phase 14 closeout' .planning/STATE.md | grep -q '^1$'
  </automated>
</verification>

<success_criteria>
- All 4 npm packages (`@mostlyrightmd/{core,weather,markets}` + unscoped meta `mostlyright`) published at vts-0.1.0 on npm with `latest` dist-tag.
- `npm install @mostlyrightmd/core` in clean Node 20 + pnpm 9 project resolves to 0.1.0; smoke import works.
- Browser smoke via Chrome MV3 SW + kalshi.com overlay works against the published `latest` bundle.
- size-limit gates green on every publish.
- scripts/release-ts-preflight.mjs Phase 12 iter-1 CRITICAL fix verified (peer-key rewrite fires on each publish).
- Soak ≥1 week on `next` before promotion to `latest`.
- RUNBOOK.md committed; STATE.md closeout appended.
</success_criteria>

<output>
After completion, create `.planning/phases/14-npm-publication-pipeline/14-SUMMARY.md` documenting:
- npm scope claim date + 4 OIDC publishers registered
- vts-0.1.0-rc.1 publish: 4 npm URLs + provenance attestation hashes + size-limit numbers
- Soak window: rc1 publish → 0.1.0 publish (gap ≥7 days)
- External installer feedback summary (Node + Browser)
- vts-0.1.0 publish: 4 npm URLs + provenance + size-limit numbers + verification curl results
- RUNBOOK.md TOC
- W1..W4 commit SHAs in order
- Ready-for-Phase-15 confirmation
</output>

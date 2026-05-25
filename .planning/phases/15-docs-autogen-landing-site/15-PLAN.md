---
phase: 15-docs-autogen-landing-site
type: execute
depends_on: [13-pypi-publication-pipeline, 14-npm-publication-pipeline]
requirements:
  - DOCS-04
  - DOCS-05
  - DOCS-06
  - DOCS-07
  - DOCS-08
  - DOCS-09
  - DOCS-10
tags:
  - docs
  - landing-site
  - autogen
  - cicd
must_haves:
  truths:
    - "`pnpm dev` in `mostly-right-landing/` serves the new SDK docs section with both Python and TS sub-trees populated"
    - "A test `v0.1.1` (or `vts-0.1.1`) tag fires `docs-publish.yml` → PR opens on landing repo → Cloudflare Pages auto-deploys → https://mostlyright.md/docs/sdk/ updates"
    - "Hand-curated quickstart MDX renders correctly with working code-fences + cross-SDK links"
    - "Cross-SDK parity table auto-regenerated from `.planning/CROSS-SDK-SYNC.md` on tag"
    - "`mostly-right-landing/CLAUDE.md` documents the ingestion flow"
  artifacts:
    - path: "docs/sphinx/conf.py"
      provides: "Sphinx config consuming mostlyright public surface"
    - path: "packages-ts/typedoc.json"
      provides: "TypeDoc config walking 4 published TS packages"
    - path: ".github/workflows/docs-publish.yml"
      provides: "Tag-triggered docs regen + PR-against-landing"
    - path: "scripts/generate_parity_table.py"
      provides: "CROSS-SDK-SYNC.md → parity.mdx generator"
    - path: "mostly-right-landing/src/content/docs/docs/sdk/index.mdx"
      provides: "SDK section root + hand-curated structure"
  key_links:
    - from: "git tag v* | vts-* (non-rc only)"
      to: ".github/workflows/docs-publish.yml"
      via: "GH Actions tag trigger; builds docs locally then opens PR on landing repo via PAT"
    - from: ".planning/CROSS-SDK-SYNC.md"
      to: "mostly-right-landing/src/content/docs/docs/sdk/parity.mdx"
      via: "scripts/generate_parity_table.py reads YAML frontmatter + emits MDX table"
---

<objective>
W1 — Wire Sphinx for Python: `docs/sphinx/conf.py` + autodoc + sphinx-markdown-builder + smoke `make markdown` produces MDX-compatible output for `mostlyright.research` + `mostlyright.live` + `mostlyright.discover` etc.

W2 — Wire TypeDoc for TypeScript: root `packages-ts/typedoc.json` walks the 4 published packages; smoke `pnpm typedoc` produces MDX output. Verify JSDoc on `.d.ts` (post-`tsup --dts` build) is rich enough; add docstrings where thin.

W3 — Wire `.github/workflows/docs-publish.yml`: on `v*` or `vts-*` non-rc tag, build the relevant doc tree, open a PR against `Tarabcak/mostly-right-landing/main`. Requires `MOSTLY_RIGHT_LANDING_PAT` secret.

W4 — Hand-curated MDX in landing repo + parity-table generator + landing CLAUDE.md update + verification (push a no-op `v0.1.0.post1` tag → confirm docs PR opens → Cloudflare auto-deploy).
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/15-docs-autogen-landing-site/15-CONTEXT.md
@.planning/CROSS-SDK-SYNC.md
@packages/core/src/mostlyright/research.py  # docstring quality reference
@packages/core/src/mostlyright/live/_stream.py
@packages/core/src/mostlyright/discover.py
@packages-ts/core/src/index.ts  # JSDoc quality reference
@docs/cache-migration.md
@docs/live-streaming.md
@CLAUDE.md
</context>

<tasks>

<task type="auto" depends_on="">
  <name>W1 Task 1: Wire Sphinx for Python docs</name>
  <files>
    docs/sphinx/conf.py (NEW),
    docs/sphinx/index.rst (NEW),
    docs/sphinx/Makefile (NEW),
    docs/sphinx/_templates/autosummary/module.rst (NEW; clean Markdown-friendly autosummary template),
    pyproject.toml (workspace root — add [dependency-groups.docs] section),
    scripts/build_python_docs.sh (NEW)
  </files>
  <read_first>
    packages/core/src/mostlyright/__init__.py (the public surface autodoc walks),
    packages/core/src/mostlyright/research.py (docstring quality reference)
  </read_first>
  <action>
    Step 1 — add [dependency-groups.docs] to pyproject.toml workspace root:
      docs = [
          "sphinx>=8.0,<9",
          "myst-parser>=4.0,<5",
          "sphinx-markdown-builder>=0.6,<1",
          "furo>=2024.8",
          "sphinx-autodoc-typehints>=2.5",
      ]

    Step 2 — create docs/sphinx/conf.py:
      project = "mostlyright"
      author = "Mostly Right"
      release = "0.1.0"
      extensions = [
          "sphinx.ext.autodoc",
          "sphinx.ext.autosummary",
          "sphinx.ext.napoleon",  # NumPy-style docstrings
          "sphinx.ext.intersphinx",
          "sphinx_autodoc_typehints",
          "myst_parser",
          "sphinx_markdown_builder",
      ]
      autosummary_generate = True
      napoleon_numpy_docstring = True
      napoleon_use_param = True
      autodoc_typehints = "description"  # keeps signatures clean in MDX
      intersphinx_mapping = {
          "python": ("https://docs.python.org/3", None),
          "pandas": ("https://pandas.pydata.org/docs/", None),
          "numpy": ("https://numpy.org/doc/stable/", None),
      }
      html_theme = "furo"  # only matters for local preview; landing uses Starlight styles
      markdown_anchor_sections = True  # stable per-heading anchors for cross-links
      markdown_anchor_signatures = True  # stable per-function anchors

      # Configure for Starlight ingestion: emit each module as a separate MDX
      # file under sdk/python/ tree.
      markdown_http_base = "/docs/sdk/python"

      # Filter what gets documented: only the canonical public surface.
      autodoc_default_options = {
          "members": True,
          "undoc-members": False,  # skip undocumented (forces us to write docstrings)
          "private-members": False,
          "special-members": False,
          "inherited-members": False,
          "show-inheritance": True,
      }

    Step 3 — create docs/sphinx/index.rst (entry point):
      Mostlyright Python SDK
      ======================

      .. autosummary::
         :toctree: api
         :recursive:

         mostlyright
         mostlyright.research
         mostlyright.discover
         mostlyright.live
         mostlyright.snapshot
         mostlyright.core
         mostlyright.weather
         mostlyright.markets

    Step 4 — create docs/sphinx/Makefile (standard Sphinx Makefile + extra `markdown` target).

    Step 5 — create scripts/build_python_docs.sh wrapper:
      #!/bin/bash
      set -euo pipefail
      cd "$(dirname "$0")/../docs/sphinx"
      uv sync --group docs
      uv run sphinx-build -b markdown . _build/markdown
      echo "Markdown output: $(pwd)/_build/markdown"

    Step 6 — smoke build:
      bash scripts/build_python_docs.sh
      # Verify _build/markdown/api/ has populated MDX files
      # Spot-check: docs/sphinx/_build/markdown/api/mostlyright.research.md should contain `research()` signature + docstring

    Step 7 — verify autodoc finds gaps:
      # If sphinx-build reports "no documentation for ..." warnings, audit the surface and either:
      #   (a) add docstrings in source (preferred; ships with the next SDK release), OR
      #   (b) add to the autodoc skip list (last resort)

    Step 8 — commit:
      git add docs/sphinx pyproject.toml scripts/build_python_docs.sh
      git commit -m "phase15 W1: Sphinx + autodoc + sphinx-markdown-builder for Python docs"
  </action>
  <verify>
    <automated>
    test -f docs/sphinx/conf.py
    test -f docs/sphinx/index.rst
    test -f scripts/build_python_docs.sh
    grep -c '^docs = ' pyproject.toml  # expect 1 ([dependency-groups.docs] header inferred separately)
    bash scripts/build_python_docs.sh 2>&1 | tail -5  # must not error
    test -d docs/sphinx/_build/markdown/api
    find docs/sphinx/_build/markdown/api -name '*.md' | wc -l | awk '$1 >= 5 {exit 0} {exit 1}'  # expect ≥5 module files
    grep -l 'def research' docs/sphinx/_build/markdown/api/*.md | head -1  # expect at least 1 file documenting research()
    </automated>
  </verify>
  <done>
    Sphinx config + Makefile + smoke wrapper committed; `bash scripts/build_python_docs.sh` produces MDX files for the full mostlyright public surface.
  </done>
</task>

<task type="auto" depends_on="W1-T1">
  <name>W2 Task 1: Wire TypeDoc for TypeScript docs</name>
  <files>
    packages-ts/typedoc.json (NEW),
    package.json (root — add typedoc + plugin devDeps + typedoc script),
    scripts/build_ts_docs.sh (NEW),
    packages-ts/*/src/index.ts (audit for JSDoc gaps; add where thin)
  </files>
  <read_first>
    packages-ts/core/src/index.ts (JSDoc quality reference),
    packages-ts/core/tsup.config.ts (verify dts: true so .d.ts is emitted)
  </read_first>
  <action>
    Step 1 — add devDeps to root package.json:
      "devDependencies": {
        ...existing...
        "typedoc": "^0.27",
        "typedoc-plugin-markdown": "^4.3",
      }

    Step 2 — create packages-ts/typedoc.json:
      {
        "$schema": "https://typedoc.org/schema.json",
        "name": "Mostlyright TypeScript SDK",
        "out": "../docs-ts-build/markdown",
        "entryPoints": [
          "core/src/index.ts",
          "weather/src/index.ts",
          "markets/src/index.ts",
          "meta/src/index.ts"
        ],
        "entryPointStrategy": "resolve",
        "plugin": ["typedoc-plugin-markdown"],
        "readme": "none",
        "githubPages": false,
        "hideGenerator": true,
        "excludePrivate": true,
        "excludeProtected": true,
        "excludeInternal": true,
        "includeVersion": true,
        "sort": ["alphabetical"],
        "outputFileStrategy": "modules"
      }

    Step 3 — add root script:
      "scripts": {
        ...existing...
        "docs:ts": "pnpm -r run build && pnpm typedoc --options packages-ts/typedoc.json"
      }

    Step 4 — create scripts/build_ts_docs.sh wrapper:
      #!/bin/bash
      set -euo pipefail
      cd "$(dirname "$0")/.."
      pnpm install
      pnpm -r run build  # produces .d.ts that TypeDoc consumes
      pnpm typedoc --options packages-ts/typedoc.json
      echo "Markdown output: $(pwd)/packages-ts/../docs-ts-build/markdown"

    Step 5 — smoke build:
      bash scripts/build_ts_docs.sh

    Step 6 — audit JSDoc gaps:
      # Spot-check the output MDX files for missing function descriptions
      # Add JSDoc to source files where thin (e.g. /** @param {string} station ... */)
      # Re-run build to verify

    Step 7 — commit:
      git add packages-ts/typedoc.json package.json scripts/build_ts_docs.sh pnpm-lock.yaml
      # Plus any source files where JSDoc was added
      git add packages-ts/**/src/index.ts  # if changed
      git commit -m "phase15 W2: TypeDoc + plugin-markdown for TS docs"
  </action>
  <verify>
    <automated>
    test -f packages-ts/typedoc.json
    test -f scripts/build_ts_docs.sh
    grep -c '"typedoc":' package.json  # expect 1 (devDep) + 1 (script) = 2 occurrences
    bash scripts/build_ts_docs.sh 2>&1 | tail -5  # must not error
    test -d docs-ts-build/markdown
    find docs-ts-build/markdown -name '*.md' | wc -l | awk '$1 >= 4 {exit 0} {exit 1}'  # expect ≥4 (one per package + sub-pages)
    grep -l 'research' docs-ts-build/markdown/**/*.md | head -1  # expect at least 1 file documenting research()
    </automated>
  </verify>
  <done>
    TypeDoc config + smoke wrapper committed; `bash scripts/build_ts_docs.sh` produces MDX files for all 4 published TS packages.
  </done>
</task>

<task type="auto" depends_on="W2-T1">
  <name>W3 Task 1: Wire .github/workflows/docs-publish.yml + parity table generator</name>
  <files>
    .github/workflows/docs-publish.yml (NEW),
    scripts/generate_parity_table.py (NEW)
  </files>
  <read_first>
    .planning/CROSS-SDK-SYNC.md (source format for parity table),
    .github/workflows/release.yml (tag-trigger pattern + permissions to mirror),
    Phase 13 + 14 RUNBOOKs (release flow this workflow extends)
  </read_first>
  <action>
    Step 1 — scripts/generate_parity_table.py:
      Reads `.planning/CROSS-SDK-SYNC.md`, extracts the parity-ticket registry (table of [Python surface, TS surface, status, ticket, notes]), emits a Markdown table written to argv[1].

      Usage: `python scripts/generate_parity_table.py mostly-right-landing/src/content/docs/docs/sdk/parity.mdx`

      Output MDX template (header + frontmatter for Starlight):
        ---
        title: SDK Parity
        description: Cross-SDK feature parity table for Mostlyright Python + TypeScript.
        ---

        Generated from `.planning/CROSS-SDK-SYNC.md` on every `v*` / `vts-*` non-rc tag.

        | Surface | Python | TypeScript | Status | Ticket |
        |---|---|---|---|---|
        | research() | ✓ 1.0 | ✓ 1.0 | parity | — |
        | ... | ... | ... | ... | ... |

    Step 2 — .github/workflows/docs-publish.yml:
      name: Docs publish (auto-PR to landing repo)
      on:
        push:
          tags:
            - "v*"
            - "!v*rc*"
            - "vts-*"
            - "!vts-*rc*"
        workflow_dispatch:
          inputs:
            tag:
              description: "Tag to regenerate docs from (e.g. v0.1.0, vts-0.1.0)"
              required: true

      permissions:
        contents: read

      jobs:
        regen-docs:
          name: Regenerate docs + open PR
          runs-on: ubuntu-latest
          steps:
            - uses: actions/checkout@v4
              with:
                fetch-depth: 0

            - name: Determine SDK target from tag
              id: target
              run: |
                TAG="${{ github.event.inputs.tag || github.ref_name }}"
                if echo "$TAG" | grep -q '^v'; then
                  echo "sdk=python" >> "$GITHUB_OUTPUT"
                elif echo "$TAG" | grep -q '^vts-'; then
                  echo "sdk=typescript" >> "$GITHUB_OUTPUT"
                fi

            - name: Install uv (Python docs path)
              if: steps.target.outputs.sdk == 'python'
              uses: astral-sh/setup-uv@v3

            - name: Build Python docs
              if: steps.target.outputs.sdk == 'python'
              run: bash scripts/build_python_docs.sh

            - name: Install pnpm (TS docs path)
              if: steps.target.outputs.sdk == 'typescript'
              uses: pnpm/action-setup@v4
              with:
                version: 10

            - name: Build TS docs
              if: steps.target.outputs.sdk == 'typescript'
              run: bash scripts/build_ts_docs.sh

            - name: Always regen parity table
              run: |
                uv run python scripts/generate_parity_table.py /tmp/parity.mdx
                cat /tmp/parity.mdx | head -20

            - name: Checkout landing repo
              uses: actions/checkout@v4
              with:
                repository: Tarabcak/mostly-right-landing
                token: ${{ secrets.MOSTLY_RIGHT_LANDING_PAT }}
                path: landing

            - name: Sync MDX trees
              run: |
                set -euo pipefail
                if [ "${{ steps.target.outputs.sdk }}" = "python" ]; then
                  rm -rf landing/src/content/docs/docs/sdk/python
                  mkdir -p landing/src/content/docs/docs/sdk/python
                  cp -r docs/sphinx/_build/markdown/api/* landing/src/content/docs/docs/sdk/python/
                fi
                if [ "${{ steps.target.outputs.sdk }}" = "typescript" ]; then
                  rm -rf landing/src/content/docs/docs/sdk/typescript
                  mkdir -p landing/src/content/docs/docs/sdk/typescript
                  cp -r docs-ts-build/markdown/* landing/src/content/docs/docs/sdk/typescript/
                fi
                cp /tmp/parity.mdx landing/src/content/docs/docs/sdk/parity.mdx

            - name: Open PR
              working-directory: landing
              env:
                GH_TOKEN: ${{ secrets.MOSTLY_RIGHT_LANDING_PAT }}
              run: |
                BRANCH="docs/regen-${{ github.event.inputs.tag || github.ref_name }}"
                git checkout -b "$BRANCH"
                git add src/content/docs/docs/sdk
                git -c user.email=docs-bot@mostlyrightmd.md -c user.name="docs-bot" commit -m "docs: regenerate SDK reference for ${{ github.event.inputs.tag || github.ref_name }}"
                git push origin "$BRANCH"
                gh pr create --title "docs: regenerate SDK reference for ${{ github.event.inputs.tag || github.ref_name }}" \
                             --body "Auto-generated by docs-publish.yml on tag push. Approve to deploy via Cloudflare Pages." \
                             --base main \
                             --head "$BRANCH"

    Step 3 — Document `MOSTLY_RIGHT_LANDING_PAT` operator-gated secret (REQUIRED before first run):
      Operator must create a fine-grained GitHub PAT scoped to repository `Tarabcak/mostly-right-landing` with contents:write + pull-requests:write permissions; add to SDK repo secrets as `MOSTLY_RIGHT_LANDING_PAT`. Document in OPERATOR-PREFLIGHT.md for this phase.

    Step 4 — commit:
      git add .github/workflows/docs-publish.yml scripts/generate_parity_table.py
      git commit -m "phase15 W3: docs-publish.yml + parity table generator"
  </action>
  <verify>
    <automated>
    test -f .github/workflows/docs-publish.yml
    test -f scripts/generate_parity_table.py
    # YAML sanity
    uv run python -c "import yaml; yaml.safe_load(open('.github/workflows/docs-publish.yml'))"
    # Parity script smoke (writes to /tmp; no landing PR yet)
    uv run python scripts/generate_parity_table.py /tmp/parity-smoke.mdx
    grep -c '^| Surface' /tmp/parity-smoke.mdx  # expect 1 (header row)
    rm /tmp/parity-smoke.mdx
    </automated>
  </verify>
  <done>
    docs-publish.yml + parity table generator committed. Workflow YAML validates; parity table generator runs locally.
  </done>
</task>

<task type="auto" depends_on="W3-T1">
  <name>W4 Task 1: Hand-curated MDX in landing repo + delete stale placeholders + ingestion doc</name>
  <files>
    ~/Documents/GitHub/mostly-right-landing/src/content/docs/docs/sdk/index.mdx (NEW),
    ~/Documents/GitHub/mostly-right-landing/src/content/docs/docs/sdk/quickstart-python.mdx (NEW),
    ~/Documents/GitHub/mostly-right-landing/src/content/docs/docs/sdk/quickstart-typescript.mdx (NEW),
    ~/Documents/GitHub/mostly-right-landing/src/content/docs/docs/sdk/concepts/temporal-safety.mdx (NEW),
    ~/Documents/GitHub/mostly-right-landing/src/content/docs/docs/sdk/concepts/source-identity.mdx (NEW),
    ~/Documents/GitHub/mostly-right-landing/src/content/docs/docs/sdk/migration/cache.mdx (NEW),
    ~/Documents/GitHub/mostly-right-landing/src/content/docs/docs/sdk/migration/v0.0.x.mdx (NEW),
    ~/Documents/GitHub/mostly-right-landing/CLAUDE.md (append ingestion section),
    ~/Documents/GitHub/mostly-right-landing/src/content/docs/docs/sdk/installation.mdx (DELETE),
    ~/Documents/GitHub/mostly-right-landing/src/content/docs/docs/sdk/therminal-client.mdx (DELETE),
    ~/Documents/GitHub/mostly-right-landing/src/content/docs/docs/sdk/weather-live.mdx (DELETE)
  </files>
  <read_first>
    docs/cache-migration.md (Phase 12 W4 source for migration/cache.mdx),
    docs/live-streaming.md (Phase 11 source — links from quickstart),
    README.md (current root — quickstart inspiration)
  </read_first>
  <action>
    This task runs in the LANDING repo (~/Documents/GitHub/mostly-right-landing), NOT the SDK repo. Branch: `phase15/sdk-docs-bootstrap`.

    Step 1 — delete stale placeholders:
      cd ~/Documents/GitHub/mostly-right-landing
      git checkout -b phase15/sdk-docs-bootstrap
      git rm src/content/docs/docs/sdk/installation.mdx
      git rm src/content/docs/docs/sdk/therminal-client.mdx
      git rm src/content/docs/docs/sdk/weather-live.mdx

    Step 2 — write hand-curated MDX files. Use Starlight's `<Tabs>` + `<TabItem>` components for Python/TS side-by-side blocks. Frontmatter requires `title` + `description`.

      `sdk/index.mdx`: SDK section root with intro + sidebar overview + links to quickstart/concepts/migration/python/typescript subpages.

      `sdk/quickstart-python.mdx`: <60s install + first call. ```bash pip install 'mostlyright[research]==0.1.0' ``` then ```python from mostlyright import research; df = research('KNYC', '2025-01-06', '2025-01-12'); print(df.head()) ```

      `sdk/quickstart-typescript.mdx`: <60s install + first call. ```bash pnpm add @mostlyrightmd/core ``` then ```ts import { research } from '@mostlyrightmd/core'; const rows = await research('KNYC', '2025-01-06', '2025-01-12'); console.log(rows[0]); ```

      `sdk/concepts/temporal-safety.mdx`: KnowledgeView + LeakageDetector explained (2-3 paragraphs each + code example from existing tests).

      `sdk/concepts/source-identity.mdx`: Mode 1 vs Mode 2 + SourceMismatchError example.

      `sdk/migration/cache.mdx`: import + adapt from SDK repo `docs/cache-migration.md`; convert markdown to MDX (only diff: frontmatter).

      `sdk/migration/v0.0.x.mdx`: `pip uninstall tradewinds tradewinds-weather tradewinds-markets` + `pip install mostlyright[research]==0.1.0`; npm equivalent (`npm uninstall @tradewinds/core && npm install @mostlyrightmd/core`); env var rename + cache mv.

    Step 3 — append to mostly-right-landing/CLAUDE.md:
      ## Docs ingestion from mostlyright SDK

      Auto-generated MDX lands under `src/content/docs/docs/sdk/{python,typescript}/` via a CI workflow in the SDK repo
      (`.github/workflows/docs-publish.yml`). On every `v*` or `vts-*` non-rc tag in the SDK repo, the workflow:

      1. Builds Sphinx (`v*`) or TypeDoc (`vts-*`) output as MDX
      2. Regenerates `sdk/parity.mdx` from the SDK repo's `.planning/CROSS-SDK-SYNC.md`
      3. Opens a PR on this repo titled `docs: regenerate SDK reference for <tag>`
      4. Maintainer approves → Cloudflare Pages auto-deploys

      To override an auto-generated page: add its path to `.docsoverrides` at the repo root. The workflow skips paths listed there.

      To preview docs locally before SDK release: `pnpm dev` after pulling the workflow PR locally.

    Step 4 — `pnpm dev` smoke (verifies landing builds with new structure):
      cd ~/Documents/GitHub/mostly-right-landing
      pnpm install
      pnpm dev &
      sleep 5
      curl -s http://localhost:4321/docs/sdk/ | grep -c 'Mostlyright'  # expect >=1
      curl -s http://localhost:4321/docs/sdk/quickstart-python/ | grep -c 'pip install'  # expect >=1
      curl -s http://localhost:4321/docs/sdk/concepts/temporal-safety/ | grep -c 'KnowledgeView'  # expect >=1
      pkill -f "astro dev"

    Step 5 — commit on landing branch + push:
      cd ~/Documents/GitHub/mostly-right-landing
      git add -A
      git commit -m "phase15 W4: bootstrap SDK docs section (replace 3 placeholder MDXs with curated structure)"
      git push origin phase15/sdk-docs-bootstrap

    Step 6 — Open landing PR manually (NOT via docs-publish.yml — this is the hand-curated bootstrap; auto-gen takes over from this baseline):
      gh pr create --title "phase15: bootstrap SDK docs section" \
                   --body "Replaces 3 placeholder MDX files with curated SDK docs structure. Auto-generated python/ and typescript/ subtrees will land via docs-publish.yml on the next SDK tag." \
                   --base main
  </action>
  <verify>
    <automated>
    cd ~/Documents/GitHub/mostly-right-landing
    test -f src/content/docs/docs/sdk/index.mdx
    test -f src/content/docs/docs/sdk/quickstart-python.mdx
    test -f src/content/docs/docs/sdk/quickstart-typescript.mdx
    test -f src/content/docs/docs/sdk/concepts/temporal-safety.mdx
    test -f src/content/docs/docs/sdk/concepts/source-identity.mdx
    test -f src/content/docs/docs/sdk/migration/cache.mdx
    test -f src/content/docs/docs/sdk/migration/v0.0.x.mdx
    test ! -f src/content/docs/docs/sdk/therminal-client.mdx  # deleted
    test ! -f src/content/docs/docs/sdk/installation.mdx  # deleted
    test ! -f src/content/docs/docs/sdk/weather-live.mdx  # deleted
    grep -c '## Docs ingestion' CLAUDE.md  # expect >=1
    # pnpm dev smoke (only run interactively; cannot loop in automated verify)
    </automated>
  </verify>
  <done>
    Landing repo SDK docs section bootstrapped with 7 hand-curated MDX files + ingestion doc in CLAUDE.md. Stale placeholders deleted. `pnpm dev` renders all new pages correctly. Branch `phase15/sdk-docs-bootstrap` opened as PR against landing main.
  </done>
</task>

<task type="auto" depends_on="W4-T1">
  <name>W4 Task 2: End-to-end verification + STATE closeout</name>
  <files>
    .planning/phases/15-docs-autogen-landing-site/15-W4-E2E.md (NEW),
    .planning/STATE.md (Phase 15 closeout appended)
  </files>
  <read_first>
    .planning/STATE.md (Phase 13 + 14 closeout shape)
  </read_first>
  <action>
    Step 1 — manual trigger of docs-publish.yml against v0.1.0 (the Phase 13 tag):
      gh workflow run docs-publish.yml -f tag=v0.1.0
      gh run watch --workflow=docs-publish.yml
      # Verify: build PASS, parity gen PASS, PR opens on landing repo

    Step 2 — review + merge the landing PR (operator action; not bot-automated):
      gh pr list --repo Tarabcak/mostly-right-landing | head -3
      gh pr view --repo Tarabcak/mostly-right-landing <pr-number>
      # Spot-check the diff: docs/sdk/python/ populated; parity.mdx regenerated
      gh pr merge --repo Tarabcak/mostly-right-landing <pr-number> --squash

    Step 3 — verify Cloudflare Pages deploy:
      sleep 60  # cloudflare typically deploys in <1 min
      curl -sfL https://mostlyright.md/docs/sdk/python/ | grep -c 'mostlyright.research'  # expect >=1

    Step 4 — same loop for vts-0.1.0:
      gh workflow run docs-publish.yml -f tag=vts-0.1.0
      gh run watch --workflow=docs-publish.yml
      # ... merge + verify ...
      curl -sfL https://mostlyright.md/docs/sdk/typescript/ | grep -c 'research'  # expect >=1

    Step 5 — write 15-W4-E2E.md transcript with workflow run URLs + landing PR URLs + Cloudflare deploy URLs + final mostlyright.md/docs/sdk/ URLs.

    Step 6 — append Phase 15 closeout to STATE.md.

    Step 7 — commit:
      git add .planning/phases/15-docs-autogen-landing-site/15-W4-E2E.md .planning/STATE.md
      git commit -m "phase15 W4: e2e verification (v0.1.0 + vts-0.1.0 → docs deploy) + STATE closeout"
  </action>
  <verify>
    <automated>
    test -f .planning/phases/15-docs-autogen-landing-site/15-W4-E2E.md
    grep -c 'https://mostlyright.md/docs/sdk' .planning/phases/15-docs-autogen-landing-site/15-W4-E2E.md  # expect >=2 (python + typescript)
    grep -c '^## Phase 15 closeout' .planning/STATE.md  # expect 1
    git log --oneline -1 | grep -q 'phase15 W4'
    </automated>
  </verify>
  <done>
    End-to-end docs flow verified: both v0.1.0 + vts-0.1.0 tags fired the workflow → landing PRs opened + merged → Cloudflare deployed → docs live at https://mostlyright.md/docs/sdk/. STATE closeout appended.
  </done>
</task>

</tasks>

<verification>
  <automated>
    # WAVE 15 ACCEPTANCE GATE — all must pass before Phase 16 starts
    test -f docs/sphinx/conf.py
    test -f packages-ts/typedoc.json
    test -f .github/workflows/docs-publish.yml
    test -f scripts/generate_parity_table.py
    # YAML sanity
    uv run python -c "import yaml; yaml.safe_load(open('.github/workflows/docs-publish.yml'))"
    # Smoke: both doc builds work locally
    bash scripts/build_python_docs.sh >/dev/null 2>&1
    bash scripts/build_ts_docs.sh >/dev/null 2>&1
    # E2E: landing site has new docs section (network-dependent)
    curl -sfL https://mostlyright.md/docs/sdk/python/ > /dev/null
    curl -sfL https://mostlyright.md/docs/sdk/typescript/ > /dev/null
    # STATE closeout
    grep -c '^## Phase 15 closeout' .planning/STATE.md | grep -q '^1$'
  </automated>
</verification>

<success_criteria>
- Sphinx + TypeDoc both produce MDX output locally via `bash scripts/build_{python,ts}_docs.sh`.
- `docs-publish.yml` fires on `v*` and `vts-*` non-rc tags, builds docs, regenerates parity table, opens PR against landing repo.
- Hand-curated quickstart + concept + migration MDX files committed in landing repo.
- Cross-SDK parity table auto-regenerated from `.planning/CROSS-SDK-SYNC.md`.
- `mostly-right-landing/CLAUDE.md` documents ingestion + override flow.
- E2E flow verified: both v0.1.0 + vts-0.1.0 tags → docs live at https://mostlyright.md/docs/sdk/{python,typescript}/.
- STATE closeout appended.
</success_criteria>

<output>
After completion, create `.planning/phases/15-docs-autogen-landing-site/15-SUMMARY.md` documenting:
- Sphinx + TypeDoc setup notes (any JSDoc gaps surfaced)
- docs-publish.yml workflow run URLs (Python + TS)
- Landing PRs opened + merged (URLs)
- Cloudflare Pages deploy URLs
- Final https://mostlyright.md/docs/sdk/ TOC
- W1..W4 commit SHAs in both SDK repo and landing repo
- Ready-for-Phase-16 confirmation
</output>

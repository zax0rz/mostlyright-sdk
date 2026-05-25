# Phase 15: Docs Auto-Generation + Landing Site Integration — Context

**Gathered:** 2026-05-25
**Status:** Ready for planning
**Source:** User brief — "then docs and then prepare a production repo with full copy"

<domain>
## Phase Boundary

Generate API reference documentation from source-of-truth — Sphinx + sphinx-autodoc for Python (consumes NumPy-style docstrings), TypeDoc for TypeScript (consumes JSDoc/TSDoc on `.d.ts` surfaces) — emit MDX, push into `mostly-right-landing/src/content/docs/docs/sdk/` (Starlight ingestion path), deploy via Cloudflare Pages on every `v*` / `vts-*` non-rc tag.

**What this phase ships in the SDK repo (`helloiamvu/tradewinds`):**
- `docs/sphinx/conf.py` + Makefile + `docs/sphinx/index.rst` — Sphinx doc-build infra
- `packages-ts/typedoc.json` (single root config that walks the 4 published packages) — TypeDoc config
- `scripts/build_python_docs.sh` + `scripts/build_ts_docs.sh` — convenience local wrappers
- `.github/workflows/docs-publish.yml` — fires on `v*` and `vts-*` non-rc tags; runs Sphinx + TypeDoc; opens a PR against `mostly-right-landing/main` with regenerated MDX tree
- New optional dev-deps: `sphinx>=8.0,<9`, `myst-parser>=4`, `sphinx-markdown-builder>=0.6`, `furo` (light theme; styling overridden by Starlight on landing), `typedoc>=0.27`, `typedoc-plugin-markdown>=4`

**What this phase ships in the landing repo (`Tarabcak/mostly-right-landing`):**
- New `src/content/docs/docs/sdk/python/` tree — Sphinx-emitted MDX for the full Python public surface
- New `src/content/docs/docs/sdk/typescript/` tree — TypeDoc-emitted MDX for the 4 npm packages
- `src/content/docs/docs/sdk/quickstart-python.mdx` (hand-curated, <60s install→first call)
- `src/content/docs/docs/sdk/quickstart-typescript.mdx` (hand-curated)
- `src/content/docs/docs/sdk/concepts/temporal-safety.mdx` (hand-curated; KnowledgeView + LeakageDetector)
- `src/content/docs/docs/sdk/concepts/source-identity.mdx` (hand-curated; Mode 1 vs Mode 2)
- `src/content/docs/docs/sdk/migration/cache.mdx` (links the SDK repo's `docs/cache-migration.md` shipped in Phase 12 W4)
- `src/content/docs/docs/sdk/migration/v0.0.x.mdx` (legacy `tradewinds*` → `mostlyright*` install commands)
- `src/content/docs/docs/sdk/parity.mdx` (cross-SDK parity table from `.planning/CROSS-SDK-SYNC.md`)
- `src/content/docs/docs/sdk/index.mdx` (lands at https://mostlyright.md/docs/sdk/ as the SDK section root)
- Delete: 3 stale placeholder MDX files (`installation.mdx`, `therminal-client.mdx`, `weather-live.mdx`)
- `mostly-right-landing/CLAUDE.md` updated: how-to-ingest section
- `mostly-right-landing/astro.config.mjs` sidebar regenerated to include the new SDK section

**What this phase does NOT ship:**
- v1.0 marketing copy / repo README rewrite — Phase 16 owns root README, per-package READMEs, CONTRIBUTING etc.
- Hosted-API docs (the existing OpenAPI bundle at `docs/_generated/openapi.json`) — already on landing site; this phase doesn't touch it
- Branded landing-site visual redesign — separate landing-team workstream

**Out of scope:**
- Real-time docs preview (`pnpm dev` in landing repo against a draft branch) — leave to operator workflow
- Docs-versioning UI (showing 0.1.0 vs 1.0.0 docs side-by-side) — defer to v1.x when API drift across versions becomes a real concern
- Internationalized docs — single English-only build for now

</domain>

<decisions>
## Implementation Decisions (LOCKED)

### Generator pick (LOCKED — Sphinx for Python, TypeDoc for TS)

- **Python: Sphinx + sphinx-autodoc + myst-parser + sphinx-markdown-builder** — consumes the NumPy-style docstrings already in `mostlyright.research`, `mostlyright.live.stream`, `mostlyright.discover`, etc. Emits MDX-compatible Markdown via the Markdown builder. Alternatives (pdoc, mkdocstrings) considered + rejected: pdoc has thinner support for cross-references + sphinx's autodoc is the established Python ecosystem standard.
- **TypeScript: TypeDoc + typedoc-plugin-markdown** — consumes JSDoc/TSDoc on the `.d.ts` surface that `tsup --dts` already builds. typedoc-plugin-markdown emits MDX-compatible output. Alternative (api-extractor) considered + rejected: api-extractor's MDX output is less mature.

### Output destination (LOCKED — push to landing repo as PR, not direct commit)

- Auto-generated MDX lands at `mostly-right-landing/src/content/docs/docs/sdk/{python,typescript}/`.
- CI does NOT push directly to the landing repo's `main`. Instead, the `docs-publish.yml` workflow opens a PR titled `docs: regenerate SDK reference for <tag>`. Operator approves; merge fires Cloudflare Pages build.
- Rationale: prevents auto-published docs from going live with a regression in the auto-gen pipeline; gives operator a 5-second review window per release. Trade-off: small latency between SDK tag-push and docs going live (typically <1 hour).

### Tag trigger (LOCKED — non-rc tags only)

- `v*` Python non-rc → regenerate Python docs section + push PR
- `vts-*` TS non-rc → regenerate TS docs section + push PR
- rc tags do NOT trigger docs publish (avoids docs churn during soak windows). Operator can manually run the workflow via `gh workflow run docs-publish.yml -f tag=vts-0.1.0-rc.1` if needed.

### Sidebar nav (LOCKED — Starlight's astro-collection)

- Starlight uses the file-tree under `src/content/docs/` as the default sidebar. Putting docs under `docs/sdk/python/` automatically gets a "Python" sub-section in the SDK group.
- Manual sidebar override only needed if we want specific ordering inside auto-generated trees — for now, accept lexicographic.

### Hand-curated vs auto-generated boundary (LOCKED)

| Path | Source | Update Trigger |
|------|--------|----------------|
| `docs/sdk/index.mdx` | hand | manual |
| `docs/sdk/quickstart-{python,typescript}.mdx` | hand | manual (per major version) |
| `docs/sdk/concepts/*.mdx` | hand | manual |
| `docs/sdk/migration/*.mdx` | hand | manual + auto on tag (cache.mdx links existing SDK repo doc) |
| `docs/sdk/parity.mdx` | generated from `.planning/CROSS-SDK-SYNC.md` | tag |
| `docs/sdk/python/**` | Sphinx | tag (`v*`) |
| `docs/sdk/typescript/**` | TypeDoc | tag (`vts-*`) |

Operator override: any auto-generated page can be hand-edited by adding it to a `.docsoverrides` file in the landing repo — `docs-publish.yml` skips paths listed there. Used sparingly (e.g. when sphinx output for a specific function is broken and you need a quick hand-edit before the next SDK tag).

### Claude's Discretion

- Sphinx vs sphinx-rtd-theme vs furo — planner picks (furo is recommended; Starlight overrides styling anyway so the theme only matters for the local `make html` preview).
- Whether to ship a `docs/sphinx/_templates/` directory that overrides Sphinx's autosummary template to emit cleaner MDX — planner picks based on how the initial smoke-build comes out.
- Whether the cross-SDK parity table is generated by a Python script or a TS script — Python recommended (it's already the canonical source for the schema codegen).
- Whether `docs-publish.yml` runs Sphinx + TypeDoc in the SDK repo (preferred — keeps the dev-deps local) or in the landing repo (alternative — lighter SDK CI but pulls a Python venv into a JS-only repo). Planner picks (recommended: SDK repo).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning:**

### In-repo truth
- `packages/core/src/mostlyright/research.py` — NumPy-style docstrings example (the canonical surface that Sphinx documents)
- `packages/core/src/mostlyright/live/_stream.py` — Phase 11 live module; docstrings + type hints to consume
- `packages/core/src/mostlyright/discover.py` — Phase 10 discover module
- `packages-ts/core/src/index.ts` — TS public surface entry; JSDoc on exported types
- `tsup.config.ts` per package — confirms dts: true so TypeDoc has .d.ts to walk
- `docs/cache-migration.md` (Phase 12 W4) — example migration doc that will be linked from landing
- `docs/live-streaming.md` (Phase 11) — example concept doc
- `docs/ingest-strategies.md` (Phase 7) — example concept doc

### Landing repo truth (read-only at planning time)
- `~/Documents/GitHub/mostly-right-landing/astro.config.mjs` — Starlight integration config
- `~/Documents/GitHub/mostly-right-landing/src/content/docs/docs/` — current docs structure (3 SDK placeholder MDX files to delete)
- `~/Documents/GitHub/mostly-right-landing/package.json` — `astro` + `@astrojs/starlight` versions for compat

### External docs
- Sphinx + Markdown Builder: https://github.com/clayrisser/sphinx-markdown-builder
- myst-parser: https://myst-parser.readthedocs.io/
- TypeDoc Markdown plugin: https://typedoc-plugin-markdown.org/
- Starlight content: https://starlight.astro.build/guides/authoring-content/

### Cross-phase dependencies
- Phase 13 + Phase 14 RUNBOOKs: triggered by the same `v*` / `vts-*` tags; docs-publish.yml is a third workflow on the same tag trigger
- `.planning/CROSS-SDK-SYNC.md` — parity-ticket registry; source for the parity.mdx table

</canonical_refs>

<specifics>
## Specific Concrete Requirements

From REQUIREMENTS.md DOCS-04..DOCS-10:

| Req | Wave |
|-----|------|
| DOCS-04: Sphinx + autodoc wired | W1 |
| DOCS-05: TypeDoc wired | W2 |
| DOCS-06: auto-gen tree at `docs/sdk/{python,typescript}/` | W1 + W2 outputs |
| DOCS-07: `.github/workflows/docs-publish.yml` opens PR against landing | W3 |
| DOCS-08: hand-curated quickstart/concepts/migration MDX | W4 |
| DOCS-09: cross-SDK parity table generator | W4 |
| DOCS-10: landing repo CLAUDE.md ingestion doc | W4 |

### Success Criteria (from ROADMAP)

1. `pnpm dev` in `mostly-right-landing/` serves the new SDK docs section at http://localhost:4321/docs/sdk/ with both Python and TypeScript sub-trees populated.
2. A test `v0.1.1` Python tag fires `docs-publish.yml` → PR lands on `mostly-right-landing/main` with regenerated MDX → Cloudflare Pages auto-deploys → https://mostlyright.md/docs/sdk/python/ updates within 1 hour.
3. Hand-curated quickstart MDX renders correctly (code-fences highlight, links to API ref work).
4. Cross-SDK parity table is auto-regenerated from `.planning/CROSS-SDK-SYNC.md` and pages stale on every tag.

</specifics>

<deferred>
## Deferred Ideas (explicitly out of scope per user brief)

- **Real-time docs preview against a draft branch** — leave to operator's manual `pnpm dev` workflow.
- **Docs-versioning UI** (0.1 vs 1.0 side-by-side) — defer to v1.x.
- **Internationalized docs** — single English-only.
- **Hand-written tutorials** (beyond quickstart + concepts) — defer to v1.x.
- **Search index tuning** — Starlight ships sane defaults; defer custom search to v1.x.
- **Brand styling overrides for SDK docs** — leave to landing-team workstream.

</deferred>

---

*Phase: 15-docs-autogen-landing-site*
*Context captured: 2026-05-25*

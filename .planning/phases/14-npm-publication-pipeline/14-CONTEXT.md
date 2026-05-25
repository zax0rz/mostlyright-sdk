# Phase 14: npm Publication Pipeline — Context

**Gathered:** 2026-05-25
**Status:** Ready for planning
**Source:** User brief — "What we need to plan next is probably pypi, npm, then docs and then prepare a production repo with full copy"

<domain>
## Phase Boundary

Stand up the npm publish pipeline end-to-end for the 5 TypeScript packages (`@mostlyright/core`, `@mostlyright/weather`, `@mostlyright/markets`, `@mostlyright/codegen`, unscoped meta `mostlyright`), close out operator pre-flight OP3 + OP4 deferred from Phase 12, run a `vts-0.1.0rc1` `npm dist-tag next` dry-run, soak ≥1 week, and promote `vts-0.1.0` to npm `latest`.

**What this phase ships:**
- 1 npm scope claim: `@mostlyright` (operator OP3)
- 4 npm OIDC pending-publisher registrations (operator OP4): `@mostlyright/{core,weather,markets}` + unscoped meta `mostlyright`. **`@mostlyright/codegen` is NOT published** — it's `"private": true` in package.json (build-only).
- GH repo Environment `npm` (operator-gated, GH UI, mirrors Python's `pypi` posture)
- `vts-0.1.0rc1` git tag → release-ts.yml fires → 4 packages on npm with `--tag next` dist-tag
- Clean Node 20 + pnpm 9 project smoke install: `npm install @mostlyright/core@next`
- Browser smoke test: `packages-ts/examples/chrome-extension-mvp/` rebuilt against `@mostlyright/core@next` IIFE bundle, loaded in Chrome MV3 SW
- ≥1 week soak on npm `next` channel with external installer feedback
- `vts-0.1.0` git tag → release-ts.yml fires with `--tag latest` → 4 packages on npm `latest`
- size-limit gates green on every publish (core ≤25KB / weather ≤35KB / markets ≤10KB / meta ≤70KB min+gzip)
- Changesets `fixed` group lockstep: all 4 packages bump together
- New `.planning/phases/14-npm-publication-pipeline/RUNBOOK.md` for routine future TS releases

**What this phase does NOT ship (deferred):**
- `vts-1.0.0` final tag — Phase 16 owns that promotion after the rc1 → 0.1.0 cycle proves out
- Docs auto-generation tied to release tags — Phase 15
- npm scope transfer from any orphaned `@tradewinds/*` packages — operator handles out-of-band
- ECMWF dataset publishing on the TS side — v0.2+

**Out of scope:**
- TypeScript Architect's iter-1 CRITICAL finding (release-ts-preflight.mjs peer-key rewrite) — already shipped in Phase 12 review-iter1; this phase verifies it still fires correctly on each publish.
- TS bundle size-limit policy change — current gates stay; Phase 16 may relax for v1.0.

</domain>

<decisions>
## Implementation Decisions (LOCKED)

### Version progression (LOCKED — 3-step soak; mirrors Phase 13 + Python pattern)

1. **`vts-0.1.0rc1`** → release-ts.yml `--tag next` → `npm install @mostlyright/core@next`. Soak ≥1 week. External installer (not maintainer) confirms `npm install @mostlyright/core@next` in clean Node 20 + pnpm 9 project + browser smoke via `examples/chrome-extension-mvp/` working.
2. **`vts-0.1.0`** (final) → release-ts.yml `--tag latest` → default `npm install @mostlyright/core`. Soak ≥2 weeks. Real users install from default channel.
3. **`vts-1.0.0`** is Phase 16's promotion — depends on Phase 13 + 14 + 15 closing first.

### Workflow filename + environment name pinning (LOCKED — operator-bound to OIDC)

- npm release workflow filename: `.github/workflows/release-ts.yml` (stays from TS-W7; renamed-internally-only by Phase 12 W6)
- GH environment name: `npm` (mirror Python's `pypi`)
- OIDC trusted-publisher bindings on npmjs.com keyed to **(owner, repo, workflow filename, environment name, package name)** for each of the 4 publishers — changing ANY of those 5 invalidates the binding. Phase 12 W6 preserved the first 3; this phase does NOT re-touch them.

### Dist-tag policy (LOCKED — rc routes to `next`, non-rc to `latest`)

release-ts.yml has this routing logic already (verified Phase 12 review):
- tag matches `vts-*rc*` → `pnpm publish --tag next` (4 packages)
- tag matches `vts-*` (non-rc) → `pnpm publish --tag latest` (4 packages)

Users wanting to soak rc explicitly opt in via `npm install @mostlyright/core@next`. Default `npm install @mostlyright/core` resolves to `latest` dist-tag = the last non-rc publish.

### Changesets lockstep (LOCKED — fixed group of 4)

`.changeset/config.json` declares the fixed group: `["@mostlyright/core", "@mostlyright/weather", "@mostlyright/markets", "mostlyright"]`. `@mostlyright/codegen` is build-only + `"private": true` so it's not in the fixed group and doesn't publish.

Operator runs `pnpm changeset` (interactive prompt for changeset markdown), then `pnpm changeset version` (rewrites all 4 package.json versions in lockstep). The version-bump PR lands on main; tag follows.

### scripts/release-ts-preflight.mjs (LOCKED — Phase 12 iter-1 CRITICAL fix preserved)

Phase 12 review-iter1 fixed the script to rewrite `peerDependencies['@mostlyright/core']` (not the old `@tradewinds/core` key). Phase 14 verifies the preflight still fires correctly on each tagged publish — if it silently no-ops again the published `@mostlyright/weather` + `@mostlyright/markets` would carry `peerDependencies['@mostlyright/core']: '^0.0.0'` and break every consumer install under pnpm strict-peer-dependencies. The preflight emits a hard error if the key is missing.

### Operator pre-flight (REQUIRED before any in-repo wave executes)

Phase 12 closeout deferred OP3 + OP4. Phase 14 W1 documents + tracks them; no in-repo PR work proceeds until the operator confirms:

- **OP3** (REQUIRED): Claim `@mostlyright` npm scope on npmjs.com under the project owner's account. Set scope to public access (mirrors PyPI public-by-default posture). If `@mostlyright` is unavailable, fall back to unscoped `mostlyright-core` / `mostlyright-weather` / `mostlyright-markets` per `.planning/research/TS-SDK-DESIGN.md` §13.1 — this is a P0 fork point.
- **OP4a** (REQUIRED): Register 4 npm OIDC pending publishers on npmjs.com:
  - `@mostlyright/core` → repo + workflow `release-ts.yml` + env `npm`
  - `@mostlyright/weather` → same
  - `@mostlyright/markets` → same
  - `mostlyright` (unscoped meta) → same
- **OP4b** (REQUIRED): Create GH repo Environment `npm`. Set required reviewer = operator.

### Claude's Discretion

- Exact RUNBOOK.md format — mirror Phase 13 RUNBOOK.md; both flow through the same multi-package + version-guard + dist-tag pattern.
- Whether to add a `tests/npm-install-smoke.sh` shell wrapper that the CI runs against the last rc — planner picks; tradeoff: extra CI latency vs catching install-time regressions on every PR.
- Whether to include the Chrome MV3 example smoke as a GH Actions matrix job — planner picks; manual operator-run is acceptable for v0.1; CI matrix lands in Phase 16 with v1.0 hardening.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning:**

### In-repo workflow truth
- `.github/workflows/release-ts.yml` — npm publish workflow (4 publish steps, dist-tag routing, OIDC provenance)
- `scripts/release-ts-preflight.mjs` — preflight that rewrites peerDependencies['@mostlyright/core'] (Phase 12 iter-1 CRITICAL fix)
- `.changeset/config.json` — Changesets fixed-group declaration
- `.size-limit.config.js` (or equivalent in root package.json) — bundle size gates
- `packages-ts/examples/chrome-extension-mvp/` — browser smoke harness

### Operator-facing surface (external)
- npmjs.com Trusted Publishers UI: https://www.npmjs.com/login then "Trusted Publishers" tab
- npm OIDC docs: https://docs.npmjs.com/generating-provenance-statements
- GH Environments docs: https://docs.github.com/en/actions/managing-workflow-runs-and-deployments/managing-deployments/managing-environments-for-deployment

### Cross-phase dependencies
- Phase 12 closeout: `.planning/phases/12-rename-to-mostlyright/README.md` — OP3 + OP4 source
- Phase 12 review-iter1: scripts/release-ts-preflight.mjs peer-key fix (CRITICAL closed)
- Phase 13 RUNBOOK.md: mirror format for routine release operations
- TS-W7 plan: `.planning/phases/ts-w7-docs-npm-publish/` — original npm publish design

### Wrapped commands
- `pnpm changeset` (interactive prompt; writes a markdown changeset file)
- `pnpm changeset version` (rewrites all 4 package.json versions per fixed-group declaration)
- `git tag vts-0.1.0rc1 && git push origin vts-0.1.0rc1` (npm next publish trigger)
- `git tag vts-0.1.0 && git push origin vts-0.1.0` (npm latest publish trigger)
- `npm install @mostlyright/core@next` (smoke install from npm next channel)
- `npm install @mostlyright/core` (smoke install from npm latest)
- `pnpm -r run build` (local pre-flight; CI re-runs in release-ts.yml)
- `pnpm size-limit` (local size-limit verification)

</canonical_refs>

<specifics>
## Specific Concrete Requirements

From REQUIREMENTS.md NPM-01..NPM-09:

| Req | Wave |
|-----|------|
| NPM-01: `@mostlyright` scope claimed | W1 (operator pre-flight) |
| NPM-02: 4 npm OIDC publishers registered + env `npm` | W1 (operator pre-flight) |
| NPM-03: `vts-0.1.0rc1` tag → release-ts.yml `--tag next` green | W2 |
| NPM-04: `npm install @mostlyright/core@next` works in clean Node 20 + pnpm 9 project | W2 |
| NPM-05: Browser smoke via `examples/chrome-extension-mvp/` | W2 |
| NPM-06: ≥1 week soak with external installer feedback | W3 (calendar gate) |
| NPM-07: `vts-0.1.0` tag → release-ts.yml `--tag latest` green; size-limit gates green | W4 |
| NPM-08: `pnpm changeset` workflow + release-ts-preflight.mjs verification | W4 |
| NPM-09: RUNBOOK.md documents routine future TS-release flow | W4 |

### Success Criteria (from ROADMAP)

1. All 4 npm packages (`@mostlyright/{core,weather,markets}` + unscoped meta `mostlyright`) published at vts-0.1.0 on npm with `latest` dist-tag.
2. `npm install @mostlyright/core` (no @next) in clean Node 20 project resolves to 0.1.0; TS types load via `dist/index.d.ts`; smoke import works.
3. Browser smoke via `packages-ts/examples/chrome-extension-mvp/` rebuilt against latest works in Chrome MV3 service worker.
4. size-limit gates green on every publish.
5. RUNBOOK.md committed.

</specifics>

<deferred>
## Deferred Ideas (explicitly out of scope per user brief)

- **vts-1.0.0 production promotion** — Phase 16 owns this after rc1 → 0.1.0 soak proves API stability.
- **npm scope conflict resolution** — if `@mostlyright` is taken, fall back to unscoped `mostlyright-core` / `mostlyright-weather` / `mostlyright-markets`; operator decision at OP3 time.
- **npm package transfer from orphaned `@tradewinds/*` names** — operator handles out-of-band.
- **Multi-Node CI matrix** — currently `node-version: 20` only; multi-version matrix lands in Phase 16.
- **TS bundle signing (npm provenance is in)** — already on via `pnpm publish --provenance`; sigstore-equivalent already covered.

</deferred>

---

*Phase: 14-npm-publication-pipeline*
*Context captured: 2026-05-25*

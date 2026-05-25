# Phase 16: v1.0.0 Production Release — Context

**Gathered:** 2026-05-25
**Status:** Ready for planning
**Source:** User brief — "prepare a production repo with full copy etc.... i want to bring this to v1.0 production"

<domain>
## Phase Boundary

Final stretch from "v0.1.0 published + docs live" → "v1.0.0 production-shipped". Three concerns:

1. **Repo polish**: rewrite root README + per-package READMEs as user-facing marketing copy; add CHANGELOG + CONTRIBUTING + CODE_OF_CONDUCT + SECURITY at repo root.
2. **Version bump lockstep**: bump all 8 packages (3 PyPI + 5 npm, where `@mostlyright/codegen` stays `"private": true` so 4 actually publish) from 0.1.0 → 1.0.0 in a single PR; tag `v1.0.0` + `vts-1.0.0`.
3. **External validation**: clock-time an external user through the README quickstart end-to-end (<5 min target); fix blockers as `1.0.1` patches within 72h.

**What this phase ships:**
- Rewritten root `README.md` (user-facing marketing copy + 60s quickstart + API surface map + links to mostlyright.md/docs/sdk)
- Rewritten per-package READMEs (8 packages: `packages/{core,weather,markets}/README.md` + `packages-ts/{codegen,core,weather,markets,meta}/README.md`)
- NEW `CHANGELOG.md` Keep-A-Changelog format with `[1.0.0]` + `[0.1.0]` + `[0.1.0rc1]` + `[Unreleased]` sections (extends the file Phase 13 W1 seeded)
- NEW `CONTRIBUTING.md` (fork → branch → review-discipline → test gate → PR)
- NEW `CODE_OF_CONDUCT.md` (Contributor Covenant 2.1 verbatim with maintainer email)
- NEW `SECURITY.md` (vuln-report process + supported-versions table + 90-day disclosure timeline)
- `LICENSE` confirmed MIT (already present from v0.1)
- Lockstep version bump PR `release/v1.0.0`: `packages/*/pyproject.toml` + `packages-ts/*/package.json` + `uv.lock` + `pnpm-lock.yaml` + `CHANGELOG.md` all updated to 1.0.0
- `v1.0.0` Python tag + `vts-1.0.0` TS tag pushed → release.yml + release-ts.yml fire → PyPI `latest` + npm `latest` get 1.0.0
- New `.planning/RELEASE-RUNBOOK.md` (top-level summary linking Phase 13 + 14 + 15 runbooks for routine post-1.0 releases)
- Status badges in README (PyPI, npm, CI, license, codecov %, test count)

**What this phase does NOT ship (out of scope):**
- v1.x feature work (e.g. ECMWF Tier-2, hosted-backend MCP, polars-default backend). Phase 16 is mechanical — same code as 0.1.0, just promoted.
- API surface changes (no breaking changes between 0.1.0 → 1.0.0; promoting to 1.0.0 SIGNALS API stability, doesn't introduce new API).
- Repo rename `helloiamvu/tradewinds` → `helloiamvu/mostlyright` — operator may do out-of-band; in-repo URLs left pointing at the current repo until then.
- New CI/CD infrastructure — release.yml + release-ts.yml + docs-publish.yml are all in place from Phases 4/13/14/15; Phase 16 just fires them via tag-push.
- v0.1.x patch backports — separate `support/v0.1` branch may be opened by the operator later if 0.1.x security patches are needed.

</domain>

<decisions>
## Implementation Decisions (LOCKED)

### Version progression (LOCKED — direct 0.1.0 → 1.0.0)

Per user dismissal of the rc option for v1.0: bump 0.1.0 → 1.0.0 directly. No rc.1 soak intermediate; the 0.1.0 release already had its rc1 soak in Phase 13/14. The 1.0 promotion is a SemVer signal of API stability, NOT new code.

If Phase 13/14 surfaced any 0.1.0 hotfixes during prod soak, those land as `0.1.1` patches BEFORE the 1.0 bump (operator decision; default behavior).

### "no breaking changes between 0.1.0 → 1.0.0" (LOCKED — invariant)

Phase 16 is mechanically:
- Version bump
- Polish prose
- Add governance files (CONTRIBUTING, CODE_OF_CONDUCT, SECURITY)

NOT:
- API additions (those would justify a 0.2.0, not 1.0.0)
- API removals (those would justify a 2.0.0)
- Deprecation removal (the v0.3 removal of `TRADEWINDS_CACHE_DIR` back-compat shim happens at v0.3, not v1.0)

This means a consumer with `pip install mostlyright==0.1.0` can `pip install mostlyright==1.0.0` and observe zero behavior change. The 1.0 release is a TRUST signal: "we're confident enough in this surface to commit to SemVer-style API stability."

### Repo URL stability (LOCKED — operator-gated)

In-repo references to `github.com/helloiamvu/tradewinds` stay unchanged in Phase 16. Repo rename is an operator out-of-band decision (Settings → Rename). After rename, GitHub redirects keep old URLs working. Phase 16's README badges + repository fields stay pointing at `helloiamvu/tradewinds` unless operator confirms the rename has occurred (in which case a follow-up `1.0.1` patch updates URLs).

### CODE_OF_CONDUCT source (LOCKED — Contributor Covenant 2.1)

Adopt https://www.contributor-covenant.org/version/2/1/code_of_conduct/code_of_conduct.md verbatim with the `[INSERT CONTACT METHOD]` placeholder replaced with maintainer email (or GH private security advisory link if maintainer prefers).

### SECURITY.md supported-versions table (LOCKED — 1-major-back support)

| Version | Supported | EOL date |
|---------|-----------|----------|
| 1.0.x | ✓ active | TBD (1+ year) |
| 0.1.x | ✓ security only (6 months) | 2026-11-25 |
| 0.0.x (legacy `tradewinds*`) | ✗ EOL | already EOL |

Disclosure timeline: standard 90 days from private report → public disclosure.

### External validation criterion (LOCKED — <5 min quickstart)

Recruit ≥1 external user (NOT maintainer, NOT the Phase 13/14 soak installers — fresh eyes). Give them only the URL to the rewritten root README. Clock-time them through:
1. `pip install 'mostlyright[research]==1.0.0'`
2. First `research()` call
3. `npm install @mostlyright/core` (Node)
4. First TS `research()` call

Target: combined <5 min wall time. Blockers (any error message, any "wait, how do I X?" Slack message) get filed as GH issues. If wall time > 5min, file a 1.0.1 patch that fixes the friction before declaring v1.0 ready for marketing.

### Claude's Discretion

- Exact tone of root README marketing copy — planner picks; mirror what well-respected SDK READMEs (pandas, httpx, ruff) do. Avoid hype words ("revolutionary", "blazing fast"). State the problem then the solution.
- Whether to add a CI workflow that auto-bumps the `[Unreleased]` CHANGELOG section to `[X.Y.Z]` on every release tag — planner picks; not required for 1.0 but nice for routine future releases.
- Badge selection: at minimum PyPI version + npm version + CI status. Optional: codecov %, license, downloads, contributors. Avoid badge-bloat (>6 badges in README header is noise).
- Whether the `release/v1.0.0` PR routes through the review-discipline 3-reviewer loop or is treated as a "version bump only" trivial-skip. Recommendation: 1-reviewer codex pass (the diff IS just version-bump prose), no architects.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning:**

### In-repo truth
- `README.md` (current) — to be rewritten
- `packages/core/README.md` + `packages/weather/README.md` + `packages/markets/README.md` — current state (Phase 12 W7 cleaned up the `tradewinds` references)
- `packages-ts/{codegen,core,weather,markets,meta}/README.md` — current state (same)
- `CLAUDE.md` — `## Project` section has the canonical 1-paragraph value prop to extract for README marketing copy
- `LICENSE` — confirm MIT (no changes needed)
- `CHANGELOG.md` — already seeded by Phase 13 W1 with [Unreleased] + [0.1.0rc1]
- `.planning/REVIEW-DISCIPLINE.md` — CONTRIBUTING.md cites this

### Cross-phase dependencies
- Phase 13 RUNBOOK.md — referenced by `.planning/RELEASE-RUNBOOK.md`
- Phase 14 RUNBOOK.md — referenced by `.planning/RELEASE-RUNBOOK.md`
- Phase 15 outputs at https://mostlyright.md/docs/sdk/ — root README links here
- Phase 13 + 14 RUNBOOK pre-flight checklists — Phase 16 uses them on the v1.0.0 tag push

### External references
- Keep-A-Changelog: https://keepachangelog.com/en/1.1.0/
- Contributor Covenant 2.1: https://www.contributor-covenant.org/version/2/1/code_of_conduct/
- shields.io badge generator: https://shields.io/

### Wrapped commands
- `pnpm changeset` + `pnpm changeset version` (TS lockstep bump per Phase 14)
- `uv lock` (Python lockfile regen)
- `git tag v1.0.0 && git tag vts-1.0.0 && git push origin v1.0.0 vts-1.0.0`

</canonical_refs>

<specifics>
## Specific Concrete Requirements

From REQUIREMENTS.md RELEASE-01..RELEASE-10:

| Req | Wave |
|-----|------|
| RELEASE-01: root README marketing copy + badges | W1 |
| RELEASE-02: per-package READMEs (8 files) | W1 |
| RELEASE-03: CHANGELOG `[1.0.0]` + `[0.1.0]` sections | W2 |
| RELEASE-04: CONTRIBUTING.md | W2 |
| RELEASE-05: CODE_OF_CONDUCT.md | W2 |
| RELEASE-06: SECURITY.md | W2 |
| RELEASE-07: lockstep version bump 0.1.0 → 1.0.0 (8 packages) | W3 |
| RELEASE-08: `v1.0.0` + `vts-1.0.0` tags fire release workflows | W3 |
| RELEASE-09: external user <5 min quickstart confirmed | W4 |
| RELEASE-10: STATE closeout + RELEASE-RUNBOOK.md | W4 |

### Success Criteria (from ROADMAP)

1. All 4 npm packages + 3 PyPI distros at v1.0.0 on PyPI/npm `latest`.
2. https://mostlyright.md/docs/sdk/ regenerated against 1.0.0.
3. Root README + 8 per-package READMEs rewritten as user-facing marketing copy.
4. CHANGELOG + CONTRIBUTING + CODE_OF_CONDUCT + SECURITY at repo root.
5. External user timed through quickstart at <5 min wall time, no blockers.
6. `.planning/RELEASE-RUNBOOK.md` documents routine post-1.0 release flow linking Phase 13/14/15 runbooks.

</specifics>

<deferred>
## Deferred Ideas (explicitly out of scope per user brief)

- **v1.x feature work** — ECMWF Tier-2, hosted-backend MCP, polars-default. These ship as `1.x.0` / `1.x.x` after 1.0.0 lands.
- **Breaking API changes** — would justify v2.0; deferred indefinitely.
- **v0.3 deprecation removal** (`TRADEWINDS_CACHE_DIR` back-compat shim) — happens at v0.3, NOT v1.0. v1.0 still carries the shim.
- **GitHub repo rename** `helloiamvu/tradewinds` → `helloiamvu/mostlyright` — operator out-of-band.
- **Marketing site refresh** — landing-team workstream; Phase 16 just polishes the SDK repo.

</deferred>

---

*Phase: 16-v1.0-production-release*
*Context captured: 2026-05-25*

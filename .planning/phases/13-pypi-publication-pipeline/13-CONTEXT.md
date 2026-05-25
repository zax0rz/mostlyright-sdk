# Phase 13: PyPI Publication Pipeline — Context

**Gathered:** 2026-05-25
**Status:** Ready for planning
**Source:** User brief — "What we need to plan next is probably pypi, npm, then docs and then prepare a production repo with full copy"

<domain>
## Phase Boundary

Stand up the PyPI publish pipeline end-to-end for the 3 Python distributions (`mostlyright`, `mostlyright-weather`, `mostlyright-markets`), close out operator pre-flight OP1 + OP2 deferred from Phase 12, run a `v0.1.0rc1` TestPyPI dry-run, soak ≥1 week, and promote `v0.1.0` to production PyPI.

**What this phase ships:**
- **W0 operator pre-flight (NEW — added 2026-05-25):** (a) operator creates `mostlyright` GitHub org, (b) repo cleanup commit on `main` (untrack `.planning/`, prune dev artifacts, write production-grade root README — paired with Phase 16; see X-ref), (c) operator transfers `helloiamvu/tradewinds` → `mostlyright/mostlyright-sdk`. All subsequent waves bind to the **new** repo coordinates.
- 3 PyPI pending-publisher registrations against `mostlyright/mostlyright-sdk` (operator-gated, manual on pypi.org)
- 3 TestPyPI pending-publisher registrations against `mostlyright/mostlyright-sdk` (operator-gated, manual on test.pypi.org)
- GH repo Environments `pypi` + `testpypi` on the NEW repo (operator-gated, GH UI)
- `v0.1.0rc1` git tag pushed to `mostlyright/mostlyright-sdk` → release-testpypi.yml fires → 3 wheels on test.pypi.org
- Clean-venv smoke test of `pip install --index-url https://test.pypi.org/simple/ mostlyright==0.1.0rc1`
- ≥1 week soak on TestPyPI with external installer feedback
- `v0.1.0` git tag → release.yml fires → 3 wheels on prod pypi.org
- CI-04 `check_wheel_metadata.py` Requires-Dist pin gate green on both publishes
- New `.planning/phases/13-pypi-publication-pipeline/RUNBOOK.md` for routine future releases (under new org)

**What this phase does NOT ship (deferred):**
- `v1.0.0` final tag — Phase 16 owns that promotion after the rc1 → 0.1.0 cycle proves out
- npm publishing — Phase 14 mirrors this playbook for the TS side
- Docs auto-generation tied to release tags — Phase 15
- Repo polish / README rewrite — Phase 16
- Operator's local `~/Documents/GitHub/mostlyright` folder rename (OP1) — operator manual, blocks nothing in-repo but recommended before re-cloning for the post-rename workflow

**Out of scope:**
- ECMWF dataset publishing (operator-gated; v0.2+ infrastructure)
- Hosted-backend publishing (intentionally never — local-first SDK design)
- TestPyPI as a permanent install channel (rc tags only; users always install from prod PyPI)

</domain>

<decisions>
## Implementation Decisions (LOCKED)

### Version progression (LOCKED — 3-step soak)

1. **`v0.1.0rc1`** → release-testpypi.yml → `https://test.pypi.org/project/mostlyright/`. Soak ≥1 week. External installer (not the maintainer) confirms `pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ mostlyright[research]==0.1.0rc1` works end-to-end and the quickstart from the in-repo README runs in <5 min.
2. **`v0.1.0`** (final) → release.yml → `https://pypi.org/project/mostlyright/`. Soak ≥2 weeks. Real users install from prod PyPI; bugs file under `0.1.x` patch releases.
3. **`v1.0.0`** is Phase 16's promotion — depends on Phase 13 + 14 + 15 closing first.

Per CLAUDE.md "Data + parity rules": pandas pinned to 2.x for the parity gate. The `0.1.0rc1` build inherits this pin from `packages/*/pyproject.toml`. The rc1 wheel published on TestPyPI must match the on-disk `uv build` output byte-for-byte — `uv build --all-packages` is the single source of truth; CI just re-runs it.

### Workflow filename + environment name pinning (LOCKED — operator-bound to OIDC)

- Python release workflow filename: `.github/workflows/release.yml` (stays from Phase 4; renamed-internally-only by Phase 12 W6)
- Python release-testpypi workflow filename: `.github/workflows/release-testpypi.yml` (same)
- GH environment names: `pypi` (production) + `testpypi` (dry-run)
- OIDC trusted-publisher bindings on pypi.org / test.pypi.org are keyed to **(owner, repo, workflow filename, environment name)** — changing ANY of those 4 invalidates the binding. Phase 12 W6 preserved workflow filename + env names; **W0 of this phase changes (owner, repo) from `helloiamvu/tradewinds` → `mostlyright/mostlyright-sdk` via a GitHub repo transfer.** Pending-publisher registrations therefore MUST be done AFTER the transfer completes, against the new repo coordinates. A repo transfer auto-redirects git pushes but does NOT carry over OIDC bindings — they're registered fresh against the new owner/repo.

### TestPyPI vs prod PyPI separation (LOCKED — separate publishers, separate environments)

- **3 prod PyPI publishers**: register on pypi.org bound to release.yml + env `pypi`. Permanent after first publish.
- **3 TestPyPI publishers**: register on test.pypi.org bound to release-testpypi.yml + env `testpypi`. Permanent after first publish.
- GH Environments: `pypi` requires reviewer approval (operator self-approves); `testpypi` may or may not require approval (rec: yes, prevents accidental rc-tag pushes from auto-publishing).

### Soak duration (LOCKED — minimum 1 week TestPyPI, minimum 2 weeks prod 0.1.0)

- **rc1 → 0.1.0 soak**: ≥1 week on TestPyPI. External installer (not the maintainer) confirms install + quickstart works end-to-end. If bugs found, fix on `main`, bump to `rc2`, re-publish.
- **0.1.0 → 1.0.0 soak**: ≥2 weeks on prod PyPI. Real users install; bugs file under `0.1.x` patch releases. Phase 16 only promotes to 1.0.0 after this soak proves API stability.

### Operator pre-flight (REQUIRED before any in-repo wave executes)

Phase 12 closeout deferred these. Phase 13 W0 + W1 document + track them; no in-repo PR work proceeds until the operator confirms:

**W0 — org + repo prep (NEW, BLOCKING, ordered):**
- **OP0a** (REQUIRED, ordered first): Operator creates `mostlyright` GitHub organization at https://github.com/organizations/new. Personal account on the org. Org owner = operator. No teams needed for v1.0.
- **OP0b** (REQUIRED, ordered second): Cleanup commit on `main` of `helloiamvu/tradewinds` BEFORE transfer — this is the "production-grade" pass that prepares the repo to be public:
  - `git rm -r --cached .planning/` (untrack, keep locally; `.gitignore` already prevents re-add)
  - Prune dev-only artifacts (`spike/`, `agents/`, `.scratch/`, etc. — full inventory in Phase 16 W0)
  - Replace root `README.md` with public-facing copy (Phase 16 W1 owns the rewrite; W0 of Phase 13 only stubs it if Phase 16 hasn't merged)
  - Single PR titled `cleanup: prepare repo for public transfer (Phase 13 W0)`
  - **Bundled with Phase 16 W0**: the cleanup wave is documented in Phase 16 and re-asserted here; whichever phase merges first owns the commit.
- **OP0c** (REQUIRED, ordered third): Operator transfers `helloiamvu/tradewinds` → `mostlyright/mostlyright-sdk` via GitHub Settings → General → Transfer ownership. New repo URL: `https://github.com/mostlyright/mostlyright-sdk`. Local clone `git remote set-url origin git@github.com:mostlyright/mostlyright-sdk.git`. The old URL `helloiamvu/tradewinds` auto-redirects for 1 year per GitHub policy, but planning artifacts in this repo should be updated to the new URL.

**W1 — publisher + environment registration (REQUIRED, after W0):**
- **OP1** (recommended, not blocking): `mv ~/Documents/GitHub/mostlyright ~/Documents/GitHub/mostlyright-legacy` — prevents Python `sys.path[0] = cwd` collision when running scripts from another directory near the rename boundary.
- **OP2a** (REQUIRED): Register 3 PyPI pending publishers on pypi.org, **bound to `mostlyright/mostlyright-sdk`** (NOT helloiamvu/tradewinds):
  - `mostlyright` → owner `mostlyright`, repo `mostlyright-sdk`, workflow `release.yml`, env `pypi`
  - `mostlyright-weather` → same
  - `mostlyright-markets` → same
- **OP2b** (REQUIRED): Register 3 TestPyPI pending publishers on test.pypi.org with the same shape but workflow `release-testpypi.yml` + env `testpypi`.
- **OP2c** (REQUIRED): Create GH repo Environments `pypi` + `testpypi` on `mostlyright/mostlyright-sdk`. Set `pypi` to require reviewer approval; `testpypi` optional.

### Claude's Discretion

- Exact RUNBOOK.md structure — pick the format that mirrors how Phase 12 README documents OP1-OP4 (operator-confirmation checklist, post-publish verification, links to release workflows).
- Whether to include a `scripts/release-preflight.sh` shell wrapper that bundles the version-bump + CHANGELOG-update + tag-push sequence — planner picks; recommended only if it doesn't duplicate the version-guard preflight already in release.yml.
- Whether to introduce a `tests/test_pypi_install_smoke.py` that the CI matrix runs against the latest published rc — planner picks; tradeoff: extra CI latency vs catching install-time regressions immediately.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning:**

### In-repo workflow truth
- `.github/workflows/release.yml` — production PyPI publish (3 jobs, version-guard preflight)
- `.github/workflows/release-testpypi.yml` — TestPyPI dry-run (3 jobs, no version-guard because rc tags don't need lockstep with non-rc versions)
- `.github/workflows/wheel-metadata-check.yml` — CI-04 Requires-Dist gate (run on every push, fails build if sibling-pin missing)
- `scripts/check_wheel_metadata.py` — the gate script the above two workflows invoke

### Operator-facing surface (external)
- pypi.org Trusted Publishers UI: https://pypi.org/manage/account/publishing/
- test.pypi.org Trusted Publishers UI: https://test.pypi.org/manage/account/publishing/
- PyPI trusted-publishers docs: https://docs.pypi.org/trusted-publishers/adding-a-publisher/
- GH Environments docs: https://docs.github.com/en/actions/managing-workflow-runs-and-deployments/managing-deployments/managing-environments-for-deployment

### Cross-phase dependencies
- Phase 12 closeout: `.planning/phases/12-rename-to-mostlyright/README.md` — operator OP1-OP4 checklist source
- Phase 4 plan: `.planning/phases/04-coverage-docs-cicd-release/PLAN.md` — original Python CI/CD design (workflows authored there; Phase 13 operates them)
- CLAUDE.md "Commands" section — `uv build` invocation that produces the wheels release.yml uploads

### Wrapped commands
- `git tag v0.1.0rc1 && git push origin v0.1.0rc1` (TestPyPI publish trigger)
- `git tag v0.1.0 && git push origin v0.1.0` (prod PyPI publish trigger)
- `uv build --all-packages` (local pre-flight; CI re-runs in `release.yml`/`release-testpypi.yml`)
- `pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ mostlyright[research]==0.1.0rc1` (smoke install from TestPyPI)
- `pip install mostlyright[research]==0.1.0` (smoke install from prod PyPI)

</canonical_refs>

<specifics>
## Specific Concrete Requirements

From REQUIREMENTS.md PYPI-00..PYPI-08:

| Req | Wave |
|-----|------|
| PYPI-00: org created + cleanup commit landed + repo transferred to `mostlyright/mostlyright-sdk` | **W0 (operator pre-flight, NEW)** |
| PYPI-01: 3 PyPI publishers registered against `mostlyright/mostlyright-sdk` | W1 (operator pre-flight) |
| PYPI-02: 3 TestPyPI publishers registered against `mostlyright/mostlyright-sdk` | W1 (operator pre-flight) |
| PYPI-03: rc1 tag → release-testpypi.yml green | W2 |
| PYPI-04: `pip install` from TestPyPI works in clean venv + smoke | W2 |
| PYPI-05: ≥1 week soak with external installer feedback | W3 (calendar gate) |
| PYPI-06: v0.1.0 tag → release.yml green | W4 |
| PYPI-07: `pip install` from prod PyPI works | W4 |
| PYPI-08: RUNBOOK.md documents routine future-release flow | W4 |

### Success Criteria (from ROADMAP)

1. All 3 PyPI distros published at v0.1.0 on prod pypi.org with green CI.
2. `pip install mostlyright[research]==0.1.0` works in a clean Python 3.12 venv; quickstart from README runs end-to-end in <5 min for an external installer.
3. RUNBOOK.md committed; routine future releases (0.1.1, 0.2.0, etc.) follow the documented playbook without ad-hoc Slack threads.

### Test additions
- New `tests/test_pypi_install_smoke.py` (optional per planner discretion) — invoked by CI matrix against the latest rc or final published wheel.

</specifics>

<deferred>
## Deferred Ideas (explicitly out of scope per user brief)

- **v1.0.0 production promotion** — Phase 16 owns this after rc1 → 0.1.0 soak proves API stability.
- **PyPI namespace coordination** — `mostlyright*` names assumed available on PyPI; if any are squatted, operator handles via PyPI Trademark Policy form (out-of-band, blocks all PYPI-* reqs).
- **PyPI package transfer from old `tradewinds*` names** — orphaned per Phase 12 closeout; operator may transfer or delete out-of-band.
- **Multi-Python-version CI matrix** — currently `python-version: "3.12"` only in release.yml; multi-version matrix lands in Phase 16 with v1.0 hardening.
- **Wheel signing (sigstore / cosign)** — not required for PyPI 0.1; defer to v1.0 hardening if PSF or downstream consumers require it.

</deferred>

---

*Phase: 13-pypi-publication-pipeline*
*Context captured: 2026-05-25*

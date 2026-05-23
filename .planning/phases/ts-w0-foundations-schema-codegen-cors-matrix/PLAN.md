# Phase TS-W0 — Foundations + Schema Codegen + CORS Matrix + Sync Process

**Status:** Stub (run `/gsd-plan-phase ts-w0` to expand into full task breakdown with waves + dependencies + commit boundaries).
**Milestone:** TypeScript v0.1.0 (`@tradewinds/*` on npm)
**Lane:** Rob (primary author) + Vu (Python codegen + sync-process review)
**Depends on:** Python v0.1.0 final (canonical schemas + station registry + Kalshi map must be frozen)
**Blocks:** Every other TS-W phase

## Goal

Establish the TypeScript workspace, build/test/lint tooling, the Python→TS codegen pipeline, and the **cross-SDK sync process enforcement** so every subsequent TS phase consumes Python schemas + station registry + Kalshi map from a single source of truth AND every future Python↔TS PR is governed by the parity-ticket workflow defined in [`.planning/CROSS-SDK-SYNC.md`](../../CROSS-SDK-SYNC.md). Capture empirical CORS posture per upstream endpoint before any fetcher port — this gates which sources are usable in non-extension web-app consumers.

This phase is the spine of long-term dual-SDK maintenance. Everything that ships here is binding for every PR that follows.

## Requirements

- TS-PKG-01, TS-PKG-02 (workspace + per-package build)
- TS-CODEGEN-01, TS-CODEGEN-02 (Python exporter + TS codegen consumer)
- TS-CORS-01 (empirical CORS matrix)
- TS-CI-01 (`test-ts.yml` + `schema-drift.yml` + `parity-ticket-check.yml`)
- **TS-SYNC-01** (NEW): Cross-SDK sync process enforced via [`CROSS-SDK-SYNC.md`](../../CROSS-SDK-SYNC.md), `parity-ticket-check.yml` workflow, and a populated `.github/PULL_REQUEST_TEMPLATE.md` with the parity-ticket section.
- **TS-SYNC-02** (NEW): `scripts/parity_status.py` ships and reports open parity tickets per milestone (used by release-readiness gate).
- **TS-SYNC-03** (NEW): `.github/ISSUE_TEMPLATE/parity_ticket.md` issue template ships, matching the template in CROSS-SDK-SYNC.md §2.2 exactly.

## Success Criteria

1. **Workspace builds clean.** `pnpm install && pnpm codegen && pnpm -r build && pnpm -r test --run` from clean clone exits 0 (no network).
2. **Exporter is deterministic with Group A / Group B output discipline per CROSS-SDK-SYNC.md §1.2.**
   - **Group A (always emitted, always byte-identical between runs):** `schemas/json/{observation,forecast.iem_mos,settlement.cli,observation_ledger,observation_qc}.v1.json` + `schemas/stations.json` + `schemas/kalshi-settlement-stations.json` + `schemas/source-priority.json` + `schemas/EXPORT_MANIFEST.json` (9 files). Two consecutive runs MUST produce byte-identical output.
   - **Group B (gated on Python source artifact existing; deterministic in BOTH states — emitted-when-present OR `{"gated": true, "reason": ...}`-when-absent):** `schemas/polymarket-city-stations.json` (gated on Python Phase 3.1 INTL-02 `markets._per_event_station` materialization) + `schemas/qc-alpha-rules.json` (gated on Python Phase 3.4 QC-01 `tradewinds.qc.ALPHA_RULES` materialization). At TS-W0 time these Python sources do NOT exist in `packages/`, so the exporter emits the gated-stub form; `EXPORT_MANIFEST.json` records the stub. Two consecutive runs produce byte-identical output IN WHICHEVER STATE — emitted OR gated-stub — the source artifact currently is.
   - **`--check` mode** (CI uses it): asserts second-run output matches first-run output byte-for-byte across BOTH Group A and Group B (gated-stubs included in the equality check); does NOT treat Group-B absence-when-source-missing as drift (per CROSS-SDK-SYNC §1.2 gating rule).
3. **Codegen consumes + commits artifacts.** `@tradewinds/codegen` reads `schemas/` and emits typed station registry + Kalshi map + ajv-standalone validators into `packages-ts/*/src/**/generated/`; CI `schema-drift.yml` fails on uncommitted diff. Generated files carry `// AUTO-GENERATED ... DO NOT EDIT` headers.
4. **CORS posture documented.** `.planning/research/TS-CORS-MATRIX.md` documents empirical CORS posture (Access-Control-Allow-Origin headers + workaround per endpoint) captured from a real browser fetch, not theorized — for AWC, IEM ASOS, IEM CLI, GHCNh, Polymarket Gamma.
5. **Sync process enforced.**
   - `.planning/CROSS-SDK-SYNC.md` committed and referenced from CLAUDE.md + ROADMAP.md.
   - `.github/PULL_REQUEST_TEMPLATE.md` includes a parity-ticket prompt (`Parity-Ticket: #` line OR `python_only: true` / `typescript_only: true` justification).
   - `.github/ISSUE_TEMPLATE/parity_ticket.md` matches CROSS-SDK-SYNC.md §2.2 template byte-for-byte.
   - `.github/workflows/parity-ticket-check.yml` runs on PR open/synchronize, inspects diff against the parity-ticket-required surface list, and fails when neither `Parity-Ticket:` reference nor paired-language diff nor `*_only` opt-out is present.
   - `scripts/parity_status.py --milestone <name>` lists open parity tickets for that milestone (reads from `gh issue list` with `parity-ticket` label OR from `.planning/parity-tickets/*.md` if file-based fallback is configured).
6. **CI workflow `test-ts.yml` green:** biome check + `tsc --noEmit` + vitest with `@vitest/coverage-v8` + `size-limit` bundle gate on all 5 TS packages.

## Waves (to be detailed via `/gsd-plan-phase ts-w0`)

- **Wave 1**: Workspace scaffold (`pnpm-workspace.yaml`, root `package.json`, `tsconfig.base.json`, 5 package skeletons with hello-world tests).
- **Wave 2**: Python exporter (`scripts/export_schemas.py`) + deterministic-output unit test + `--check` mode + commit `schemas/` artifacts. Exporter emits Group A (always; 9 files per SC#2) and Group B (gated; 2 files — `qc-alpha-rules.json`, `polymarket-city-stations.json`) per CROSS-SDK-SYNC.md §1.2. At TS-W0 time, Group B Python sources (Phase 3.1 INTL-02 `_per_event_station` + Phase 3.4 QC-01 `ALPHA_RULES`) do NOT yet exist in `packages/`, so Wave 2 ships those outputs in their `{"gated": true, "reason": "Python source <path> not yet materialized in packages/"}` form, with the same gated-stub bytes committed. When Python Phases 3.1/3.4 land later, the exporter automatically emits the real artifact (a separate paired-PR per CROSS-SDK-SYNC §6 Recipe B, NOT a TS-W0 deliverable). The deterministic-output unit test asserts byte-equality across two runs in WHICHEVER state Group B is currently in. Catalog-sources manifest (`schemas/catalog-sources.json`) is OUT of scope here (lands with MCP in Phase 5 per CROSS-SDK-SYNC.md §3.3) — but the exporter's plugin architecture must accommodate adding it later without rewriting.
- **Wave 3**: `@tradewinds/codegen` package (reads `schemas/`, emits TS types + ajv-standalone validators + station/Kalshi/priority/qc-rules data modules into `generated/` folders) + `prebuild` hook wired into each consumer package's `tsup` config.
- **Wave 4**: CI workflows: `test-ts.yml` + `schema-drift.yml` + **`parity-ticket-check.yml`** (NEW); size-limit configs; lefthook pre-commit. The parity-ticket workflow uses `actions/github-script` or a small Python helper to parse PR body + diff and apply the rules in CROSS-SDK-SYNC.md §2.1 + §6.
- **Wave 5**: CORS empirical test — write a small HTML/JS harness, run it in Chrome/Firefox/Safari against each upstream endpoint, record actual `Access-Control-Allow-Origin` header + per-endpoint workaround; commit `.planning/research/TS-CORS-MATRIX.md`.
- **Wave 6** (NEW): Sync-process artifacts:
  - `.github/PULL_REQUEST_TEMPLATE.md` updated with the parity-ticket prompt block.
  - `.github/ISSUE_TEMPLATE/parity_ticket.md` issue template (mirrors CROSS-SDK-SYNC.md §2.2 template).
  - `scripts/parity_status.py` CLI (lists open parity tickets per milestone; consumed by release-readiness checks).
  - CLAUDE.md updated to reference CROSS-SDK-SYNC.md as the binding sync contract.
  - ROADMAP.md updated to flag CROSS-SDK-SYNC.md as a load-bearing document.

## Sync-process enforcement details

The `parity-ticket-check.yml` workflow MUST:

1. Trigger on `pull_request` open/synchronize/reopen.
2. Compute the file diff between PR head and base.
3. Match changed files against the surface list in CROSS-SDK-SYNC.md §2.1 (encoded as a glob list in the workflow or in `.github/parity-trigger-paths.json`):
   - `packages/core/src/tradewinds/research.py`
   - `packages/core/src/tradewinds/snapshot.py`
   - `packages/core/src/tradewinds/mode2.py`
   - `packages/core/src/tradewinds/transforms.py`
   - `packages/core/src/tradewinds/qc.py`
   - `packages/core/src/tradewinds/discovery.py`
   - `packages/core/src/tradewinds/international.py`
   - `packages/core/src/tradewinds/forecasts.py`
   - `packages/markets/src/tradewinds/markets/**/*.py` (excl. tests)
   - `packages/core/src/tradewinds/core/**/*.py`
   - `packages/weather/src/tradewinds/weather/catalog/**/*.py`
   - `packages/weather/src/tradewinds/weather/_fetchers/**/*.py`
   - Symmetric paths under `packages-ts/`.
4. If matched, inspect PR body for ONE of:
   - `Parity-Ticket: #NNNN` line (then HEAD-fetch the issue and verify it has `parity-ticket` label + correct milestone).
   - Paired-language diff (i.e., the same PR also touches the mirror path under the other lane).
   - `python_only: true` or `typescript_only: true` with at least one sentence of justification on the same line or the line below.
5. Post a sticky comment with the result. Fail the check on missing requirement.

The workflow MUST be tunable via a `.github/parity-trigger-paths.json` config so the path list can drift independently of the workflow code.

## Out of Scope

- Any fetcher implementation (deferred to TS-W1).
- Cache layer (deferred to TS-W3).
- Validator implementation beyond running the codegen-emitted ajv standalone code (full validator semantics land in TS-W3).
- npm publish (TS-W7).
- **MCP sync workflow** (`mcp-sdk-sync.yml`) — deferred to Python Phase 5 PLAN-01 per CROSS-SDK-SYNC.md §3.5. The exporter Wave 2 leaves an extension seam so Phase 5 can add `public-surface.json` without retrofitting.
- **`ts-architect` reviewer agent** definition — that's a REVIEW-DISCIPLINE.md edit, not a TS-W0 deliverable; tracked as open question §8.3 of CROSS-SDK-SYNC.md.

## Review panel

Standard 2-reviewer (codex `high` + Python Architect) per REVIEW-DISCIPLINE.md. Codegen drift is parity-critical — schema export determinism must be tested before the pipeline lands. Sync-process artifacts (`parity-ticket-check.yml`, PR template, issue template, `parity_status.py`) reviewed jointly by Vu + Rob since they bind both lanes.

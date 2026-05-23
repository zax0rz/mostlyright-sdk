# Phase TS-W7 — Docs + npm Publish

**Status:** Stub (run `/gsd-plan-phase ts-w7`).
**Milestone:** TypeScript v0.1.0
**Lane:** Rob (primary) + Vu (review + npm OIDC registration)
**Depends on:** Phase TS-W6
**Blocks:** TS v0.1.0 ship

## Goal

Ship `@tradewinds/core` + `@tradewinds/weather` + `@tradewinds/markets` + `tradewinds` meta to npm at v0.1.0. Mirror Python Phase 4 discipline: external-timer quickstart, drift fixtures rotated, trusted publishing via npm OIDC.

## Requirements

- TS-BUNDLE-01 (size-limit gates per package)
- TS-RELEASE-01 (Changesets + npm OIDC trusted publishing)
- TS-DOCS-01 (typedoc API reference)
- TS-DOCS-02 (README quickstart <5min external timer)
- TS-DOCS-03 (`docs/chrome-extension-integration.md`)
- TS-CI-02 (`release-ts.yml` + `drift-rotate-ts.yml`)

## Success Criteria

1. README quickstart (Node sample + browser sample) timed by an external person at < 5 minutes. Typedoc-generated API reference committed under `docs/ts-api/`. `docs/chrome-extension-integration.md` documents Rob's integration path end-to-end (manifest, service worker import, content-script ↔ service-worker `chrome.runtime.sendMessage`, IIFE alternative).
2. Changesets configured (`@changesets/cli` + `.changeset/config.json`); `release-ts.yml` workflow fires on `vts-*` tag, builds + tests + publishes 4 packages to npm via OIDC trusted publishing.
3. `vts-0.1.0rc1` tag → npm `--tag next` publish; soak for ≥1 week with internal Chrome-extension use; then `vts-0.1.0` tag → npm `--tag latest`.
4. `npm install @tradewinds/core @tradewinds/weather @tradewinds/markets` in a clean directory works; `npm install tradewinds` (meta) works.
5. Chrome-extension end-to-end smoke test (separate repo or `examples/chrome-extension-mvp/`) green against `latest` published packages. `size-limit` gates green for all 4 packages.
6. **Release-readiness gate via `scripts/parity_status.py`** (shipped TS-W0): `scripts/parity_status.py --milestone "TS v0.1.0"` reports zero open P0 parity tickets before the `vts-0.1.0` tag is cut. P1 tickets either resolved or explicitly deferred to `TS v0.1.x` per CROSS-SDK-SYNC §2.5. Release workflow refuses to publish on non-empty P0 list (hard gate).

## Waves

- **Wave 1**: README + quickstart samples (Node + browser); typedoc config + generation; `docs/chrome-extension-integration.md`.
- **Wave 2**: Changesets setup + `release-ts.yml` + `drift-rotate-ts.yml` workflows.
- **Wave 3**: Register 4 npm OIDC pending publishers (operator-gated; user does this on npmjs.com).
- **Wave 4**: Tag `vts-0.1.0rc1` → publish to `--tag next` → soak.
- **Wave 5**: External README timer.
- **Wave 6**: Tag `vts-0.1.0` → publish to `--tag latest` → Chrome-extension smoke test against published packages.

## Outstanding follow-ups (operator-gated)

Mirror Python Phase 4 closeout playbook:
1. Register 4 npm OIDC pending publishers on npmjs.com (one per package, scoped to `helloiamvu/tradewinds` + workflow `release-ts.yml` + environment `npm`).
2. Confirm npm scope `@tradewinds` is available; if not, fall back to unscoped `tradewinds-core`/`tradewinds-weather`/`tradewinds-markets` per TS-SDK-DESIGN.md §13.1.
3. External-person README quickstart timer (<5 min target).

## Out of Scope

- Migration guide from `mostlyright` (no JS equivalent exists).
- Polars/Arrow integration docs (`apache-arrow` adapter is opt-in; document as separate page in v0.2).
- TS analog of `mostly-light/strategies/kxhigh` byte-equivalent migration — no JS strategy runtime exists; TS parity gate against Python `research()` covers the equivalent assurance.

#!/bin/bash
# Phase 15 W2 — TypeDoc markdown build wrapper.
#
# Runs `pnpm -r run build` (to materialize the `.d.ts` files TypeDoc walks)
# then invokes TypeDoc against `packages-ts/typedoc.json`. Output lands in
# `docs-ts-build/markdown/` at the repo root. The `docs-ts-build/markdown/`
# tree is consumed by `.github/workflows/docs-publish.yml` (Phase 15 W3) —
# copied into the `mostly-right-landing` repo on every `vts-*` non-rc tag.
#
# Usage (local):
#   bash scripts/build_ts_docs.sh
#
# CI (docs-publish.yml) calls this script identically.
set -euo pipefail

cd "$(dirname "$0")/.."

# `pnpm install --frozen-lockfile` ensures the workspace dev-deps (typedoc +
# plugin-markdown) resolve to the exact lockfile-pinned versions. Matches the
# pattern in release-ts.yml + test-ts.yml + schema-drift.yml (all enforce
# --frozen-lockfile per the pre-public audit's supply-chain reproducibility
# requirement; see commit de3e883). Phase 15 W2 second-reviewer caught the
# original `pnpm install` (no flag) as a CI drift risk.
pnpm install --frozen-lockfile

# `pnpm -r run build` produces `.d.ts` for every package — TypeDoc reads
# the .ts sources directly (entryPointStrategy: "resolve"), but a successful
# build also catches type errors that would surface as half-rendered MDX.
pnpm -r run build

# `--options packages-ts/typedoc.json` points TypeDoc at the root TS config.
# Output dir (`docs-ts-build/markdown`) is set inside typedoc.json relative
# to that config file.
pnpm typedoc --options packages-ts/typedoc.json

echo "Markdown output: $(pwd)/docs-ts-build/markdown"

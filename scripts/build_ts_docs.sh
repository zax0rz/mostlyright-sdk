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

# `pnpm install` ensures the workspace dev-deps (typedoc + plugin-markdown)
# resolve cleanly, including when this script runs in a clean CI checkout.
pnpm install

# `pnpm -r run build` produces `.d.ts` for every package — TypeDoc reads
# the .ts sources directly (entryPointStrategy: "resolve"), but a successful
# build also catches type errors that would surface as half-rendered MDX.
pnpm -r run build

# `--options packages-ts/typedoc.json` points TypeDoc at the root TS config.
# Output dir (`docs-ts-build/markdown`) is set inside typedoc.json relative
# to that config file.
pnpm typedoc --options packages-ts/typedoc.json

echo "Markdown output: $(pwd)/docs-ts-build/markdown"

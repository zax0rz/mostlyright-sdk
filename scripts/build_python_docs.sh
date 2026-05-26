#!/bin/bash
# Phase 15 W1 — Sphinx markdown build wrapper.
#
# Runs the Sphinx Markdown builder against `docs/sphinx/`, materializing
# MDX-friendly Markdown under `docs/sphinx/_build/markdown/`. The
# `_build/markdown/api/` subtree is consumed by `.github/workflows/docs-publish.yml`
# (Phase 15 W3) — copied into the `mostly-right-landing` repo on every `v*`
# non-rc tag.
#
# Usage (local):
#   bash scripts/build_python_docs.sh
#
# CI (docs-publish.yml) calls this script identically.
set -euo pipefail

cd "$(dirname "$0")/../docs/sphinx"

# `uv sync --group docs` installs sphinx + autodoc + markdown-builder on top
# of the workspace's editable install. We need the workspace install (not
# `--no-install-project`) because Sphinx autodoc has to import every
# `mostlyright.*` submodule to read its docstrings.
uv sync --group docs

# `-b markdown` selects sphinx-markdown-builder.
# `-W` is intentionally OMITTED for now — Phase 15 W1 Step 7 audits the
# autodoc gap warnings and tightens this in a follow-up; failing on first
# warning would block the very initial smoke build.
uv run sphinx-build -b markdown . _build/markdown

echo "Markdown output: $(pwd)/_build/markdown"
echo "API tree: $(pwd)/_build/markdown/api"

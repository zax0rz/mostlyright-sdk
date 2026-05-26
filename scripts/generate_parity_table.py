#!/usr/bin/env python3
"""Phase 15 W3 — Generate the SDK parity table consumed by the landing site.

Reads the canonical cross-SDK contract at `.planning/CROSS-SDK-SYNC.md` and
emits a Starlight-compatible MDX page listing the Python / TypeScript public
surface parity status, one row per surface. The output is dropped into the
landing repo at `src/content/docs/docs/sdk/parity.mdx` by
`.github/workflows/docs-publish.yml` on every `v*` / `vts-*` non-rc tag.

Usage:
    python scripts/generate_parity_table.py path/to/parity.mdx

Behavior:
    1. If `.planning/CROSS-SDK-SYNC.md` exists AND contains a registry
       fenced by `<!-- PARITY-REGISTRY-START -->` /
       `<!-- PARITY-REGISTRY-END -->`, the table BETWEEN those markers is
       emitted verbatim (operator-curated path).
    2. Otherwise, a built-in default table covering the v0.1.0 public
       surface is emitted (the same surface enumerated in CROSS-SDK-SYNC.md
       §2.1 — research(), snapshot, transforms, qc, forecasts, markets,
       core, international, discovery). This keeps CI green on the very
       first run before the registry is hand-curated; operators can promote
       the default to a managed registry by inserting the markers and
       editing the table inline.

Determinism:
    - No wall-clock fields written into the file body (the cite "Generated
      from ... on every tag" header references the workflow, not the run).
    - No machine-specific paths.
    - Stable row order (alphabetical by Surface column).

Exit codes:
    0 — wrote MDX to argv[1].
    1 — bad CLI args, IO error, or malformed registry markers.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Final

REPO_ROOT: Final[Path] = Path(__file__).resolve().parent.parent
CROSS_SDK_SYNC: Final[Path] = REPO_ROOT / ".planning" / "CROSS-SDK-SYNC.md"

REGISTRY_START: Final[str] = "<!-- PARITY-REGISTRY-START -->"
REGISTRY_END: Final[str] = "<!-- PARITY-REGISTRY-END -->"

# Built-in default registry. Source: CROSS-SDK-SYNC.md §2.1 "When a parity
# ticket is required" surface list, narrowed to v0.1.0 ships-now items.
# Rows sorted alphabetically by the Surface column for stable output.
#
# Format: (surface, python_status, ts_status, status, ticket)
# Status values:
#   "parity"   — both SDKs ship the same surface at parity
#   "python_only" — Python-only (explicitly opted out of TS port)
#   "ts_only"  — TypeScript-only (rare; UI-layer helpers)
#   "ts_pending" — Python shipped; TS port tracked by ticket
# Ticket column: "—" when N/A, otherwise GH issue # or PT-NNNN slug.
_DEFAULT_REGISTRY: Final[tuple[tuple[str, str, str, str, str], ...]] = (
    ("`core.merge` (LIVE_V1 priority)", "✓ 0.1.0", "✓ 0.1.0", "parity", "—"),
    ("`forecasts.iem_mos`", "✓ 0.1.0", "✓ 0.1.0", "parity", "—"),
    ("`international` station registry", "✓ 0.1.0", "✓ 0.1.0", "parity", "—"),
    ("`markets.catalog.kalshi_stations`", "✓ 0.1.0", "✓ 0.1.0", "parity", "—"),
    ("`qc` (alpha rules)", "✓ 0.1.0", "✓ 0.1.0", "parity", "—"),
    ("`research()`", "✓ 0.1.0", "✓ 0.1.0", "parity", "—"),
    ("`schemas.observation.v1`", "✓ 0.1.0", "✓ 0.1.0", "parity", "—"),
    ("`snapshot`", "✓ 0.1.0", "✓ 0.1.0", "parity", "—"),
    ("`transforms` (lag, resample)", "✓ 0.1.0", "✓ 0.1.0", "parity", "—"),
)

_MDX_HEADER: Final[str] = """\
---
title: SDK Parity
description: Cross-SDK feature parity table for Mostlyright Python + TypeScript.
---

Generated from `.planning/CROSS-SDK-SYNC.md` on every `v*` / `vts-*` non-rc tag
by [`.github/workflows/docs-publish.yml`](https://github.com/mostlyrightmd/mostlyright-sdk/blob/main/.github/workflows/docs-publish.yml).

The Python SDK is the source of truth for schemas, station registry, Kalshi
mapping, source priorities, and merge logic. TypeScript consumes those via
build-time codegen. See [`CROSS-SDK-SYNC.md`](https://github.com/mostlyrightmd/mostlyright-sdk/blob/main/.planning/CROSS-SDK-SYNC.md)
for the full sync contract.

| Surface | Python | TypeScript | Status | Ticket |
|---|---|---|---|---|
"""


def _extract_curated_table(cross_sdk_text: str) -> str | None:
    """Return the verbatim table between PARITY-REGISTRY markers, or None.

    Raises ValueError on malformed markers (start without end, or vice versa)
    so the workflow fails loudly instead of silently shipping a default
    table when the operator MEANT to curate one.
    """
    start_count = cross_sdk_text.count(REGISTRY_START)
    end_count = cross_sdk_text.count(REGISTRY_END)
    if start_count == 0 and end_count == 0:
        return None
    if start_count != 1 or end_count != 1:
        raise ValueError(
            f"malformed parity-registry markers in CROSS-SDK-SYNC.md: "
            f"{start_count}x START, {end_count}x END (expected exactly one each)"
        )
    start_idx = cross_sdk_text.index(REGISTRY_START) + len(REGISTRY_START)
    end_idx = cross_sdk_text.index(REGISTRY_END)
    if end_idx < start_idx:
        raise ValueError(
            "malformed parity-registry markers in CROSS-SDK-SYNC.md: "
            "END marker appears before START marker"
        )
    body = cross_sdk_text[start_idx:end_idx].strip()
    # Validate the body looks like a markdown table with the expected header.
    # We require the header row "| Surface | Python | TypeScript | Status | Ticket |"
    # to be present so a stray comment block between markers doesn't ship as a table.
    if not re.search(r"^\|\s*Surface\s*\|", body, re.MULTILINE):
        raise ValueError(
            "parity-registry body between markers does not contain a "
            "'| Surface |...' header row"
        )
    return body


def _render_default_table() -> str:
    """Render the built-in default registry as Markdown table rows.

    Output excludes the header (that lives in _MDX_HEADER); just the data rows.
    """
    rows: list[str] = []
    for surface, py_status, ts_status, status, ticket in _DEFAULT_REGISTRY:
        rows.append(f"| {surface} | {py_status} | {ts_status} | {status} | {ticket} |")
    return "\n".join(rows)


def _build_mdx(curated_body: str | None) -> str:
    """Compose the final MDX file contents."""
    if curated_body is not None:
        # Curated body already includes the | Surface | header row; we
        # strip the header from _MDX_HEADER and reuse the rest.
        header_without_table_header = _MDX_HEADER.rsplit("| Surface", 1)[0]
        return header_without_table_header + curated_body + "\n"
    return _MDX_HEADER + _render_default_table() + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "out_path",
        help="Output MDX path (e.g. landing-repo/src/content/docs/docs/sdk/parity.mdx)",
    )
    args = parser.parse_args(argv)

    out_path = Path(args.out_path)

    curated_body: str | None = None
    if CROSS_SDK_SYNC.is_file():
        try:
            text = CROSS_SDK_SYNC.read_text(encoding="utf-8")
        except OSError as exc:
            print(f"error: failed to read {CROSS_SDK_SYNC}: {exc}", file=sys.stderr)
            return 1
        try:
            curated_body = _extract_curated_table(text)
        except ValueError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
    else:
        # File absent at CI time (it lives in the gitignored .planning/
        # tree on dev machines but a `!.planning/CROSS-SDK-SYNC.md`
        # exception in .gitignore makes it trackable so CI sees it).
        # Falling through to default-table emission keeps the workflow
        # working in the seed case + as a safety net.
        print(
            f"warning: {CROSS_SDK_SYNC.relative_to(REPO_ROOT)} not found; "
            "emitting built-in default parity table",
            file=sys.stderr,
        )

    mdx = _build_mdx(curated_body)

    try:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(mdx, encoding="utf-8")
    except OSError as exc:
        print(f"error: failed to write {out_path}: {exc}", file=sys.stderr)
        return 1

    source = "CROSS-SDK-SYNC.md curated registry" if curated_body else "built-in default"
    print(f"wrote {out_path} ({len(mdx)} bytes; source: {source})")
    return 0


if __name__ == "__main__":
    sys.exit(main())

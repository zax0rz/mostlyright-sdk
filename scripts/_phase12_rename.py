"""Phase 12 (rename mostlyright -> mostlyright) Python import rewriter.

Line-restricted regex matches ONLY production import statements:
    from mostlyright(.|space) -> from mostlyright\\1
    import mostlyright(.|space|EOL) -> import mostlyright\\1

PRESERVES (by construction — not matched by the regex):
    - "mostlyright==0.14.1" parity citations in docstrings
    - "MostlyRight*" deprecation aliases
    - "mostlyright_v1" parser_name enum
    - "monorepo-v0.14.1" lift-source citations
    - "TRADEWINDS_CACHE_DIR" env-var monkeypatch sites (W4 migrates)
    - URL literals like "https://mostlyright.dev/..." (W2 Batch C handles manually)

Usage:
    python scripts/_phase12_rename.py --batch A    # packages/
    python scripts/_phase12_rename.py --batch B    # tests/
    python scripts/_phase12_rename.py --batch C    # scripts/
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

IMPORT_FROM_RE = re.compile(r"^(\s*from\s+)mostlyright(\.|\s)")
IMPORT_BARE_RE = re.compile(r"^(\s*import\s+)mostlyright(\.|\s|$)")

BATCHES: dict[str, list[Path]] = {
    "A": [Path("packages")],
    "B": [Path("tests")],
    "C": [Path("scripts")],
}


def rewrite_line(line: str) -> str:
    new = IMPORT_FROM_RE.sub(r"\1mostlyright\2", line, count=1)
    new = IMPORT_BARE_RE.sub(r"\1mostlyright\2", new, count=1)
    return new


def rewrite_file(path: Path) -> int:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    new_lines = [rewrite_line(line) for line in lines]
    n_changed = sum(1 for old, new in zip(lines, new_lines, strict=True) if old != new)
    if n_changed:
        path.write_text("".join(new_lines), encoding="utf-8")
    return n_changed


def main(batch: str) -> None:
    roots = BATCHES[batch]
    total, files = 0, 0
    for root in roots:
        for py in root.rglob("*.py"):
            n = rewrite_file(py)
            if n:
                files += 1
                total += n
                print(f"  {py}: {n} lines")
    print(f"\nBatch {batch}: {total} lines across {files} files.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch", choices=["A", "B", "C"], required=True)
    main(ap.parse_args().batch)

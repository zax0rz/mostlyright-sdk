"""Pre-publish METADATA check (Phase 2 Wave 5 PKG-03).

Every sibling-package wheel under ``dist/`` must declare an explicit
``Requires-Dist: tradewinds >=0.1.0a1,<0.2`` (or stricter) so a downstream
user cannot silently install a core/weather/markets combo across an
incompatible boundary.

Usage::

    uv build --all
    uv run python scripts/check_wheel_metadata.py

Exits 0 when every wheel in ``dist/`` passes. Exits 1 with a descriptive
message per offending wheel otherwise.
"""

from __future__ import annotations

import re
import sys
import zipfile
from pathlib import Path

#: Per-package wheel-name-prefix -> list of regex patterns that MUST match in
#: the wheel's METADATA Requires-Dist lines. Multiple patterns are AND-ed.
#:
#: We accept any ``>=0.1.0..., <0.2`` form to leave room for alpha/beta
#: revisions (``>=0.1.0a1``, ``>=0.1.0b0``, etc.). The hard requirement is
#: that the upper bound is ``<0.2`` so a future major bump (0.2.0) does not
#: silently get pulled.
#: hatchling normalizes ``"tradewinds>=0.1.0a1,<0.2"`` into the canonical
#: METADATA line ``Requires-Dist: tradewinds<0.2,>=0.1.0a1`` (upper bound
#: first). We accept either order — the requirement is that BOTH the
#: ``<0.2`` upper bound AND a ``>=0.1.0`` lower bound are present.
_UPPER_PATTERN = r"<\s*0\.2"
_LOWER_PATTERN = r">=\s*0\.1\.0[a-z0-9]*"
_REQUIRES_LINE = r"Requires-Dist:\s+tradewinds"

REQUIRED_PINS: dict[str, list[str]] = {
    "tradewinds_weather": [
        # Single line containing the Requires-Dist + BOTH bounds (any order).
        rf"{_REQUIRES_LINE}.*({_UPPER_PATTERN}.*{_LOWER_PATTERN}|{_LOWER_PATTERN}.*{_UPPER_PATTERN})",
    ],
    "tradewinds_markets": [
        rf"{_REQUIRES_LINE}.*({_UPPER_PATTERN}.*{_LOWER_PATTERN}|{_LOWER_PATTERN}.*{_UPPER_PATTERN})",
    ],
}


def check_wheel(wheel_path: Path) -> list[str]:
    """Return a list of error messages (empty when the wheel passes)."""
    errors: list[str] = []
    # Wheel filenames: ``<pkg>-<version>-<python>-<abi>-<platform>.whl``.
    # Splitting on "-" gives ["<pkg>", "<version>", ...].
    pkg_name = wheel_path.name.split("-")[0]
    pins = REQUIRED_PINS.get(pkg_name)
    if pins is None:
        # Not a sibling-package wheel we gate on.
        return errors
    with zipfile.ZipFile(wheel_path) as z:
        metadata_path = next((name for name in z.namelist() if name.endswith("METADATA")), None)
        if metadata_path is None:
            errors.append(f"{wheel_path.name}: no METADATA file in wheel")
            return errors
        content = z.read(metadata_path).decode()
    for pattern in pins:
        if not re.search(pattern, content):
            errors.append(f"{wheel_path.name}: missing pin matching /{pattern}/")
    return errors


def main() -> int:
    dist = Path(__file__).resolve().parent.parent / "dist"
    if not dist.exists():
        print(
            "ERROR: dist/ directory does not exist. Run `uv build --all` first.",
            file=sys.stderr,
        )
        return 1
    wheels = sorted(dist.glob("*.whl"))
    if not wheels:
        print("ERROR: dist/ contains no wheels.", file=sys.stderr)
        return 1
    all_errors: list[str] = []
    checked = 0
    for wheel in wheels:
        wheel_errors = check_wheel(wheel)
        if wheel.name.split("-")[0] in REQUIRED_PINS:
            checked += 1
        all_errors.extend(wheel_errors)
    if all_errors:
        for err in all_errors:
            print(f"ERROR: {err}", file=sys.stderr)
        return 1
    print(f"OK: checked {checked} sibling-package wheel(s); all pins present.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

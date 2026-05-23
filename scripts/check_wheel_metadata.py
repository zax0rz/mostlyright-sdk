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
# codex iter-5 HIGH fix: parse Requires-Dist with packaging.requirements
# instead of regex-substring matching. The old regex `<\s*0\.2` matched
# `<0.20` too — letting an incompatible 0.20.x upper bound silently slip
# through. Semantic comparison via SpecifierSet handles PEP 440
# normalization + bound semantics correctly.
from packaging.requirements import InvalidRequirement, Requirement
from packaging.specifiers import SpecifierSet

#: Distributions we gate on (wheel filename prefix). Map -> the SpecifierSet
#: that the wheel's `Requires-Dist: tradewinds <specifier>` line MUST
#: SATISFY. ``"<0.2"`` is the load-bearing upper bound — the gate exists
#: precisely to keep a future 0.2.x core from being pulled by an
#: under-specified weather/markets wheel.
REQUIRED_TRADEWINDS_SPECIFIER: dict[str, SpecifierSet] = {
    "tradewinds_weather": SpecifierSet(">=0.1.0a1,<0.2"),
    "tradewinds_markets": SpecifierSet(">=0.1.0a1,<0.2"),
}


def _find_tradewinds_requirement(metadata: str) -> Requirement | None:
    """Return the parsed `Requires-Dist: tradewinds <specifier>` from the
    wheel's METADATA, or None if absent.

    Iterates Requires-Dist lines, parses each with packaging.Requirement,
    and returns the first one whose ``name == "tradewinds"``. Skips
    Requires-Dist lines we can't parse (e.g. ones with environment
    markers we don't care about; the parser handles markers but a
    malformed one would otherwise blow up).
    """
    for line in metadata.splitlines():
        if not line.startswith("Requires-Dist:"):
            continue
        spec_text = line[len("Requires-Dist:") :].strip()
        try:
            req = Requirement(spec_text)
        except InvalidRequirement:
            continue
        if req.name.replace("_", "-") == "tradewinds":
            return req
    return None


def check_wheel(wheel_path: Path) -> list[str]:
    """Return a list of error messages (empty when the wheel passes)."""
    errors: list[str] = []
    # Wheel filenames: ``<pkg>-<version>-<python>-<abi>-<platform>.whl``.
    # Splitting on "-" gives ["<pkg>", "<version>", ...].
    pkg_name = wheel_path.name.split("-")[0]
    required = REQUIRED_TRADEWINDS_SPECIFIER.get(pkg_name)
    if required is None:
        # Not a sibling-package wheel we gate on.
        return errors
    with zipfile.ZipFile(wheel_path) as z:
        metadata_path = next((name for name in z.namelist() if name.endswith("METADATA")), None)
        if metadata_path is None:
            errors.append(f"{wheel_path.name}: no METADATA file in wheel")
            return errors
        content = z.read(metadata_path).decode()
    req = _find_tradewinds_requirement(content)
    if req is None:
        errors.append(f"{wheel_path.name}: missing Requires-Dist: tradewinds line")
        return errors
    # The wheel's specifier MUST be at least as strict as the required
    # range. Two correctness checks:
    #   1. <0.2 is present (no 0.2+ slipping through).
    #   2. >=0.1.0... lower bound is present (no 0.0.x pulled).
    wheel_spec = str(req.specifier)
    # Check upper bound: every spec in wheel must EXCLUDE 0.2.0 + 0.2.0a1.
    # Use SpecifierSet membership: if 0.2.0 satisfies the wheel's spec,
    # the upper bound is missing or too loose.
    if req.specifier.contains("0.2.0", prereleases=True):
        errors.append(
            f"{wheel_path.name}: Requires-Dist: tradewinds {wheel_spec!s} "
            f"allows 0.2.0 (upper bound missing or too loose; required "
            f"<0.2). Fix the pyproject.toml dep to '>=0.1.0a1,<0.2'."
        )
    # Lower bound: 0.0.9 must NOT satisfy.
    if req.specifier.contains("0.0.9", prereleases=True):
        errors.append(
            f"{wheel_path.name}: Requires-Dist: tradewinds {wheel_spec!s} "
            f"allows 0.0.x (lower bound missing or too loose; required "
            f">=0.1.0a1). Fix the pyproject.toml dep to '>=0.1.0a1,<0.2'."
        )
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
        if wheel.name.split("-")[0] in REQUIRED_TRADEWINDS_SPECIFIER:
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

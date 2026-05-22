"""PKG-02 + PKG-04: PEP 420 namespace integrity after ``uv build``.

The three-package split relies on Python's implicit namespace-package
(PEP 420) rules: only ``tradewinds`` (core) ships a top-level
``tradewinds/__init__.py``; ``tradewinds-weather`` and
``tradewinds-markets`` ship subdirectories WITHOUT their own namespace-root
``__init__.py``. If a sibling distribution ever shipped a top-level
``__init__.py``, the first one installed would shadow the others and
``import tradewinds.weather`` would break depending on install order.

We build with ``uv build --all-packages`` (the command PLAN.md Task 4.1
verifies and Task 4.2 prepares for publish). This used to emit a 4th
``tradewinds_workspace-0.0.0`` wheel from the workspace root; the root
pyproject now sets ``[tool.uv] package = false`` so the workspace is
recognized as not-a-publishable-package, and ``--all-packages`` returns
exactly the three publishable wheels. This test guards both halves:
the wheel-layout invariants AND the absence of a workspace artifact
(codex Wave 4 iter-2 HIGH on tests/test_wheel_layout.py).
"""

from __future__ import annotations

import shutil
import subprocess
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
DIST = ROOT / "dist"


@pytest.fixture(scope="module")
def built_wheels() -> dict[str, Path]:
    """Build the workspace once per module run via ``uv build --all-packages``.

    Cleans ``dist/`` first so a stale 0.0.1 wheel cannot satisfy the
    pattern globs below and mask a missed version bump, AND so any
    previously-built ``tradewinds_workspace-*.whl`` from before the
    ``[tool.uv] package = false`` fix cannot slip into the wheel
    inventory.
    """
    if shutil.which("uv") is None:  # pragma: no cover - dev tooling gate
        pytest.skip("uv not on PATH; wheel-layout test requires `uv build`")
    if DIST.exists():
        for wheel in DIST.glob("*.whl"):
            wheel.unlink()
        for sdist in DIST.glob("*.tar.gz"):
            sdist.unlink()
    subprocess.run(
        ["uv", "build", "--all-packages"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    wheels = list(DIST.glob("*.whl"))
    by_name: dict[str, Path] = {}
    for wheel in wheels:
        if wheel.name.startswith("tradewinds_weather-"):
            by_name["weather"] = wheel
        elif wheel.name.startswith("tradewinds_markets-"):
            by_name["markets"] = wheel
        elif wheel.name.startswith("tradewinds-"):
            by_name["core"] = wheel
        else:
            # Surface any unrecognized wheel (e.g. tradewinds_workspace-*)
            # so the count assertion below fails with a clear name.
            by_name[f"UNEXPECTED:{wheel.name}"] = wheel
    return by_name


def _names(wheel: Path) -> list[str]:
    with zipfile.ZipFile(wheel) as z:
        return z.namelist()


def test_exactly_three_published_wheels(built_wheels: dict[str, Path]) -> None:
    """Exactly three wheels, no workspace artifact, no leftovers.

    A previous version of this test only checked the three expected names
    were present; ``uv build --all-packages`` produced a 4th
    ``tradewinds_workspace-0.0.0`` wheel that slipped through (codex Wave
    4 iter-1 HIGH). Now we assert ``dist/`` has exactly three .whl files
    and they are precisely the named packages.
    """
    assert set(built_wheels.keys()) == {
        "core",
        "weather",
        "markets",
    }, f"expected exactly core+weather+markets wheels, got {sorted(built_wheels)}"

    # Belt-and-suspenders: the fixture set the right keys, but re-glob
    # dist/ in case anything else (e.g. a stray workspace wheel from a
    # parallel `uv build --all-packages` call) sneaks in.
    all_wheels = list(DIST.glob("*.whl"))
    assert len(all_wheels) == 3, (
        f"dist/ must contain exactly 3 wheels after a clean build; got "
        f"{[w.name for w in all_wheels]}"
    )
    assert not list(DIST.glob("tradewinds_workspace-*.whl")), (
        "workspace meta-package wheel slipped into dist/; "
        "the root pyproject is a workspace marker only — not for publish"
    )


def test_alpha_versions_in_wheel_filenames(built_wheels: dict[str, Path]) -> None:
    assert "0.1.0a1" in built_wheels["core"].name, built_wheels["core"].name
    assert "0.1.0a1" in built_wheels["weather"].name, built_wheels["weather"].name
    assert "0.0.1" in built_wheels["markets"].name, built_wheels["markets"].name


def test_only_core_ships_namespace_root(built_wheels: dict[str, Path]) -> None:
    core_names = _names(built_wheels["core"])
    weather_names = _names(built_wheels["weather"])
    markets_names = _names(built_wheels["markets"])

    assert (
        "tradewinds/__init__.py" in core_names
    ), "core wheel MUST ship tradewinds/__init__.py (it owns the namespace root)"
    assert "tradewinds/__init__.py" not in weather_names, (
        "weather wheel must NOT ship tradewinds/__init__.py — install-order "
        "shadowing would break `import tradewinds.weather` (PEP 420; PKG-02)"
    )
    assert "tradewinds/__init__.py" not in markets_names, (
        "markets wheel must NOT ship tradewinds/__init__.py — install-order "
        "shadowing would break `import tradewinds.markets` (PEP 420; PKG-02)"
    )


def test_sibling_subpackages_present(built_wheels: dict[str, Path]) -> None:
    weather_names = _names(built_wheels["weather"])
    markets_names = _names(built_wheels["markets"])
    assert (
        "tradewinds/weather/__init__.py" in weather_names
    ), "weather wheel must ship tradewinds/weather/__init__.py (the subpackage marker)"
    assert (
        "tradewinds/markets/__init__.py" in markets_names
    ), "markets wheel must ship tradewinds/markets/__init__.py"

"""PKG-02 + PKG-04: PEP 420 namespace integrity after ``uv build``.

The three-package split relies on Python's implicit namespace-package
(PEP 420) rules: only ``tradewinds`` (core) ships a top-level
``tradewinds/__init__.py``; ``tradewinds-weather`` and
``tradewinds-markets`` ship subdirectories WITHOUT their own namespace-root
``__init__.py``. If a sibling distribution ever shipped a top-level
``__init__.py``, the first one installed would shadow the others and
``import tradewinds.weather`` would break depending on install order.

This test builds the wheels with ``uv build --all-packages`` and asserts:
1. Three wheels land in ``dist/`` (core, weather, markets).
2. Only the core wheel ships ``tradewinds/__init__.py`` at the top level.
3. Both sibling wheels ship their subpackage ``__init__.py`` (so they are
   real packages once their root is provided by core).
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
    """Build all three packages once per module run.

    Cleans ``dist/`` first so a stale 0.0.1 wheel cannot satisfy the
    pattern globs below and mask a missed version bump.
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
    return by_name


def _names(wheel: Path) -> list[str]:
    with zipfile.ZipFile(wheel) as z:
        return z.namelist()


def test_three_wheels_produced(built_wheels: dict[str, Path]) -> None:
    assert set(built_wheels.keys()) == {
        "core",
        "weather",
        "markets",
    }, f"expected core+weather+markets wheels, got {sorted(built_wheels)}"


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

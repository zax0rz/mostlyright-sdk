"""PKG-02/03/05/06: pyproject.toml pin-bound + version assertions.

These tests are the gate that prevents a future contributor from quietly
floating ``pandas`` past 3.0 or ``pyarrow`` past 24.0 across the three
packages. The parity fixtures in ``tests/fixtures/parity/`` were captured
against pandas 2.x; lifting the cap without re-capturing those fixtures
silently invalidates every historical Kalshi NHIGH/NLOW settlement.

Sources of truth: CLAUDE.md "Data + parity rules" + PLAN.md Wave 4
behavior contract.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

ROOT = Path(__file__).parents[1]


def _pyproject(pkg: str) -> dict:
    return tomllib.loads((ROOT / "packages" / pkg / "pyproject.toml").read_text())


def _deps(pkg: str) -> list[str]:
    """Runtime + optional-extras dependency strings concatenated."""
    project = _pyproject(pkg)["project"]
    runtime = list(project.get("dependencies", []))
    extras = project.get("optional-dependencies", {}) or {}
    for extra_deps in extras.values():
        runtime.extend(extra_deps)
    return runtime


def test_pandas_upper_bound_core() -> None:
    deps = _deps("core")
    assert any("pandas>=2.2,<3.0" in d for d in deps), (
        "core must pin pandas<3.0 (parity fixtures captured on pandas 2.x; "
        "see CLAUDE.md 'Data + parity rules')"
    )


def test_pandas_upper_bound_weather() -> None:
    deps = _deps("weather")
    assert any(
        "pandas>=2.2,<3.0" in d for d in deps
    ), "weather must pin pandas<3.0 (parity fixtures captured on pandas 2.x)"


def test_pyarrow_upper_bound_core() -> None:
    deps = _deps("core")
    assert any(
        "pyarrow>=17.0,<24.0" in d for d in deps
    ), "core must pin pyarrow<24.0 (PKG-06; soft upper avoids future ABI surprise)"


def test_pyarrow_upper_bound_weather() -> None:
    deps = _deps("weather")
    assert any(
        "pyarrow>=17.0,<24.0" in d for d in deps
    ), "weather must pin pyarrow<24.0 (PKG-06; cache.py imports pyarrow at module load)"


def test_core_version_is_alpha1() -> None:
    assert _pyproject("core")["project"]["version"] == "0.1.0a1"


def test_weather_version_is_alpha1() -> None:
    assert _pyproject("weather")["project"]["version"] == "0.1.0a1"


def test_markets_version_is_zero() -> None:
    # Markets is a namespace placeholder until Sprint 0.5; do NOT bump.
    assert _pyproject("markets")["project"]["version"] == "0.0.1"


def test_weather_pins_core_to_matching_alpha() -> None:
    # PKG-03: prevent a user from mixing tradewinds 0.0.x with
    # tradewinds-weather 0.1.0a1 (or vice versa) across the parity gate.
    runtime_deps = _pyproject("weather")["project"].get("dependencies", [])
    assert any(
        d.startswith("tradewinds") and ">=0.1.0a1" in d and "<0.2" in d for d in runtime_deps
    ), (
        "tradewinds-weather runtime deps must constrain tradewinds to "
        "matching alpha (>=0.1.0a1,<0.2) — see PKG-03 in PLAN.md Wave 4"
    )


def test_core_research_extra_pins_weather_to_matching_alpha() -> None:
    # Mirror of PKG-03 on the other side: `tradewinds[research]` must pull
    # a matching-alpha tradewinds-weather, not any 0.x.
    extras = _pyproject("core")["project"].get("optional-dependencies", {})
    research = extras.get("research", [])
    assert any(
        d.startswith("tradewinds-weather") and ">=0.1.0a1" in d and "<0.2" in d for d in research
    ), (
        "tradewinds[research] extra must constrain tradewinds-weather to "
        "matching alpha (>=0.1.0a1,<0.2)"
    )

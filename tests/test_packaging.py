"""PKG-02/03/05/06: pyproject.toml pin-bound + version assertions.

These tests are the gate that prevents a future contributor from quietly
floating ``pandas`` past 3.0 or ``pyarrow`` past 24.0 in any one of the
three packages' runtime deps OR any one of their optional extras.
The parity fixtures in ``tests/fixtures/parity/`` were captured against
pandas 2.x; lifting the cap anywhere silently invalidates every historical
Kalshi NHIGH/NLOW settlement.

Each location (runtime + each ``[project.optional-dependencies]`` extra) is
asserted SEPARATELY. Collapsing them all into one list would let a cap
loss in ``[research]`` slip through as long as ``[parquet]`` still has it.

Sources of truth: CLAUDE.md "Data + parity rules" + PLAN.md Wave 4
behavior contract + codex iter-1 REVISE on Wave 4.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

ROOT = Path(__file__).parents[1]

EXPECTED_BOUNDS = {
    "pandas": "pandas>=2.2,<3.0",
    "pyarrow": "pyarrow>=17.0,<24.0",
}


def _pyproject(pkg: str) -> dict:
    return tomllib.loads((ROOT / "packages" / pkg / "pyproject.toml").read_text())


def _project(pkg: str) -> dict:
    return _pyproject(pkg)["project"]


def _runtime_deps(pkg: str) -> list[str]:
    return list(_project(pkg).get("dependencies", []))


def _extras(pkg: str) -> dict[str, list[str]]:
    return _project(pkg).get("optional-dependencies", {}) or {}


def _dep_locations(pkg: str) -> list[tuple[str, list[str]]]:
    """Yield ``(label, deps)`` pairs for runtime + every extra, separately."""
    locations: list[tuple[str, list[str]]] = [(f"{pkg}.runtime", _runtime_deps(pkg))]
    for extra_name, extra_deps in _extras(pkg).items():
        locations.append((f"{pkg}[{extra_name}]", list(extra_deps)))
    return locations


def _names_in(deps: list[str]) -> set[str]:
    """Extract bare package name from each PEP 508 dependency line."""
    out: set[str] = set()
    for dep in deps:
        token = dep
        for sep in ("[", "(", "<", ">", "=", "!", "~", ";", " "):
            token = token.split(sep, 1)[0]
        out.add(token.strip().lower())
    return out


def test_pandas_cap_present_everywhere_it_is_mentioned() -> None:
    """Every dep-location that mentions ``pandas`` must use the exact <3.0 cap.

    Catches a future contributor who adds ``"pandas>=2.2"`` (no cap) to a
    new optional extra; a global collapse-then-any-match check would miss
    this because some OTHER extra still has the cap.
    """
    missing: list[str] = []
    for pkg in ("core", "weather", "markets"):
        for label, deps in _dep_locations(pkg):
            if "pandas" not in _names_in(deps):
                continue
            if not any(EXPECTED_BOUNDS["pandas"] in d for d in deps):
                missing.append(label)
    assert not missing, (
        f"these dep-locations mention pandas but lack the exact "
        f"`{EXPECTED_BOUNDS['pandas']}` cap (parity gate would break): {missing}"
    )


def test_pyarrow_cap_present_everywhere_it_is_mentioned() -> None:
    """Same idea, for pyarrow's <24.0 cap (PKG-06)."""
    missing: list[str] = []
    for pkg in ("core", "weather", "markets"):
        for label, deps in _dep_locations(pkg):
            if "pyarrow" not in _names_in(deps):
                continue
            if not any(EXPECTED_BOUNDS["pyarrow"] in d for d in deps):
                missing.append(label)
    assert not missing, (
        f"these dep-locations mention pyarrow but lack the exact "
        f"`{EXPECTED_BOUNDS['pyarrow']}` cap: {missing}"
    )


def test_pandas_cap_in_specific_known_locations() -> None:
    """Spot-check: the 4 locations that MUST mention pandas with the cap.

    Belt-and-suspenders against the cap-everywhere test passing vacuously
    if a contributor accidentally deleted the pandas dep line entirely.
    """
    expected_locations = {
        ("core", "parquet"),
        ("core", "research"),
        ("weather", "parquet"),
        ("markets", "parquet"),
    }
    for pkg, extra in expected_locations:
        deps = _extras(pkg).get(extra, [])
        assert any(
            EXPECTED_BOUNDS["pandas"] in d for d in deps
        ), f"{pkg}[{extra}] must include `{EXPECTED_BOUNDS['pandas']}`; got {deps}"


def test_pyarrow_cap_in_specific_known_locations() -> None:
    """Spot-check the 4 places that MUST mention pyarrow with the cap.

    Note: weather lists pyarrow in RUNTIME (cache.py imports it at module
    load — see weather/pyproject.toml comment from Wave 1.4 codex P2).
    """
    expected_runtime = {"weather"}
    expected_extras = {
        ("core", "parquet"),
        ("core", "research"),
        ("markets", "parquet"),
    }
    for pkg in expected_runtime:
        deps = _runtime_deps(pkg)
        assert any(
            EXPECTED_BOUNDS["pyarrow"] in d for d in deps
        ), f"{pkg} runtime must include `{EXPECTED_BOUNDS['pyarrow']}`; got {deps}"
    for pkg, extra in expected_extras:
        deps = _extras(pkg).get(extra, [])
        assert any(
            EXPECTED_BOUNDS["pyarrow"] in d for d in deps
        ), f"{pkg}[{extra}] must include `{EXPECTED_BOUNDS['pyarrow']}`; got {deps}"


def test_core_version_is_alpha1() -> None:
    assert _project("core")["version"] == "0.1.0a1"


def test_weather_version_is_alpha1() -> None:
    assert _project("weather")["version"] == "0.1.0a1"


def test_markets_version_is_zero() -> None:
    # Markets is a namespace placeholder until Sprint 0.5; do NOT bump.
    assert _project("markets")["version"] == "0.0.1"


def test_weather_pins_core_to_matching_alpha() -> None:
    # PKG-03: prevent a user from mixing tradewinds 0.0.x with
    # tradewinds-weather 0.1.0a1 (or vice versa) across the parity gate.
    runtime_deps = _runtime_deps("weather")
    assert any(
        d.startswith("tradewinds") and ">=0.1.0a1" in d and "<0.2" in d for d in runtime_deps
    ), (
        "tradewinds-weather runtime deps must constrain tradewinds to "
        "matching alpha (>=0.1.0a1,<0.2) — see PKG-03 in PLAN.md Wave 4"
    )


def test_core_research_extra_pins_weather_to_matching_alpha() -> None:
    # Mirror of PKG-03 on the other side: `tradewinds[research]` must pull
    # a matching-alpha tradewinds-weather, not any 0.x.
    research = _extras("core").get("research", [])
    assert any(
        d.startswith("tradewinds-weather") and ">=0.1.0a1" in d and "<0.2" in d for d in research
    ), (
        "tradewinds[research] extra must constrain tradewinds-weather to "
        "matching alpha (>=0.1.0a1,<0.2)"
    )

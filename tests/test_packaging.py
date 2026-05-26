"""PKG-02/03/05/06: pyproject.toml pin-bound + version assertions.

These tests are the gate that prevents a future contributor from quietly
floating ``pandas`` past 4.0 or ``pyarrow`` past 24.0 in any one of the
three packages' runtime deps OR any one of their optional extras.

Phase 6 (PANDAS3-02): the cap was lifted from ``<3.0`` to ``<4.0``. Byte
equivalence against pandas 3.x is enforced by the dual-pandas CI matrix
+ ``tests/fixtures/parity/coerce_pd3.py`` invertible bridge +
``ulp_drift_pd3.json`` measurement artifact (PLAN.md W1-T4..W1-T5).
The new upper bound still keeps a future pandas 4.x ABI break from
silently invalidating the parity-pinned cache.

Each location (runtime + each ``[project.optional-dependencies]`` extra) is
asserted SEPARATELY. Collapsing them all into one list would let a cap
loss in ``[research]`` slip through as long as ``[parquet]`` still has it.

Sources of truth: CLAUDE.md "Data + parity rules" + PLAN.md Wave 4
behavior contract (Phase 1 v0.1.0) + Phase 6 PLAN.md W1-T3 cap-lift.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

ROOT = Path(__file__).parents[1]

EXPECTED_BOUNDS = {
    "pandas": "pandas>=2.2,<4.0",
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
        assert any(EXPECTED_BOUNDS["pandas"] in d for d in deps), (
            f"{pkg}[{extra}] must include `{EXPECTED_BOUNDS['pandas']}`; got {deps}"
        )


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
        assert any(EXPECTED_BOUNDS["pyarrow"] in d for d in deps), (
            f"{pkg} runtime must include `{EXPECTED_BOUNDS['pyarrow']}`; got {deps}"
        )
    for pkg, extra in expected_extras:
        deps = _extras(pkg).get(extra, [])
        assert any(EXPECTED_BOUNDS["pyarrow"] in d for d in deps), (
            f"{pkg}[{extra}] must include `{EXPECTED_BOUNDS['pyarrow']}`; got {deps}"
        )


def test_all_three_packages_at_same_version() -> None:
    # PKG-01: lockstep version bump across all 3 PyPI distros. The release
    # workflow tags a single SHA and publishes all 3 at the same version
    # number; this test fails loudly if the bump ever drifts.
    core_version = _project("core")["version"]
    assert _project("weather")["version"] == core_version, (
        f"mostlyrightmd-weather version must match core; "
        f"core={core_version}, weather={_project('weather')['version']}"
    )
    assert _project("markets")["version"] == core_version, (
        f"mostlyrightmd-markets version must match core; "
        f"core={core_version}, markets={_project('markets')['version']}"
    )


def test_all_three_packages_at_0_1_x() -> None:
    # PKG-01: 0.1.x line. v0.2.0 bumps this assertion. v1.0.0 also bumps.
    core_version = _project("core")["version"]
    assert core_version.startswith("0.1."), (
        f"core version must be in the 0.1.x line until v0.2 / v1.0 is cut; got {core_version}"
    )


def test_markets_pins_core_to_0_1_range() -> None:
    # PKG-03: prevent a user from mixing mostlyright 0.0.x with
    # mostlyrightmd-markets 0.1.x (or vice versa). The Kalshi resolvers
    # use mostlyright.markets.catalog (this package) but the wider
    # settlement pipeline reads mostlyright.core.* schemas; a stale core
    # would silently serve the wrong column set.
    runtime_deps = _runtime_deps("markets")
    assert any(
        d.startswith("mostlyrightmd") and ">=0.1.0" in d and "<0.2" in d for d in runtime_deps
    ), (
        "mostlyrightmd-markets runtime deps must constrain mostlyright to "
        "the 0.1.x line (>=0.1.0,<0.2) — see PKG-03"
    )


def test_weather_pins_core_to_0_1_range() -> None:
    # PKG-03: prevent a user from mixing mostlyright 0.0.x with
    # mostlyrightmd-weather 0.1.x across the parity gate.
    runtime_deps = _runtime_deps("weather")
    assert any(
        d.startswith("mostlyrightmd") and ">=0.1.0" in d and "<0.2" in d for d in runtime_deps
    ), (
        "mostlyrightmd-weather runtime deps must constrain mostlyright to "
        "the 0.1.x line (>=0.1.0,<0.2) — see PKG-03"
    )


def test_core_research_extra_pins_weather_to_0_1_range() -> None:
    # Mirror of PKG-03 on the other side: `mostlyrightmd[research]` must pull
    # a 0.1.x mostlyrightmd-weather, not any 0.x.
    research = _extras("core").get("research", [])
    assert any(
        d.startswith("mostlyrightmd-weather") and ">=0.1.0" in d and "<0.2" in d for d in research
    ), (
        "mostlyrightmd[research] extra must constrain mostlyrightmd-weather to "
        "the 0.1.x line (>=0.1.0,<0.2)"
    )

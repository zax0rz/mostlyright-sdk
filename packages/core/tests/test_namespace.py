"""Verify the split-distribution namespace works.

The ``mostlyright`` namespace is shared across three PyPI distributions:
- ``mostlyright`` (core, this package): owns the ``__init__.py`` with pkgutil declaration
- ``mostlyright-weather``: ships ``mostlyright/weather/`` without a namespace-root ``__init__.py``
- ``mostlyright-markets``: ships ``mostlyright/markets/`` without a namespace-root ``__init__.py``

If this test fails after a change to ``packages/core/src/mostlyright/__init__.py``,
check that the pkgutil ``extend_path`` line is still present. Removing it breaks
``import mostlyright.weather`` for users who installed both distributions.
"""

import mostlyright


def test_core_importable():
    assert mostlyright.__version__ == "0.1.0rc1"


def test_path_extended_for_split_distribution():
    """pkgutil.extend_path must extend __path__ to discover sibling distributions."""
    paths = list(mostlyright.__path__)
    assert len(paths) >= 1, "mostlyright.__path__ is empty — namespace declaration removed?"
    # Expect at least core's path; in dev install also weather + markets paths.
    assert any("packages/core" in p for p in paths), f"core src not in __path__: {paths}"


def test_weather_subpackage_importable():
    """``import mostlyright.weather`` must succeed when mostlyright-weather is installed."""
    import mostlyright.weather

    assert mostlyright.weather.__version__ == "0.1.0rc1"


def test_markets_subpackage_importable():
    """``import mostlyright.markets`` must succeed when mostlyright-markets is installed."""
    import mostlyright.markets

    assert mostlyright.markets.__version__ == "0.0.1"

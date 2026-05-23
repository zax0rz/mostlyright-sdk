"""Verify the split-distribution namespace works.

The ``tradewinds`` namespace is shared across three PyPI distributions:
- ``tradewinds`` (core, this package): owns the ``__init__.py`` with pkgutil declaration
- ``tradewinds-weather``: ships ``tradewinds/weather/`` without a namespace-root ``__init__.py``
- ``tradewinds-markets``: ships ``tradewinds/markets/`` without a namespace-root ``__init__.py``

If this test fails after a change to ``packages/core/src/tradewinds/__init__.py``,
check that the pkgutil ``extend_path`` line is still present. Removing it breaks
``import tradewinds.weather`` for users who installed both distributions.
"""

import tradewinds


def test_core_importable():
    assert tradewinds.__version__ == "0.1.0rc1"


def test_path_extended_for_split_distribution():
    """pkgutil.extend_path must extend __path__ to discover sibling distributions."""
    paths = list(tradewinds.__path__)
    assert len(paths) >= 1, "tradewinds.__path__ is empty — namespace declaration removed?"
    # Expect at least core's path; in dev install also weather + markets paths.
    assert any("packages/core" in p for p in paths), f"core src not in __path__: {paths}"


def test_weather_subpackage_importable():
    """``import tradewinds.weather`` must succeed when tradewinds-weather is installed."""
    import tradewinds.weather

    assert tradewinds.weather.__version__ == "0.1.0rc1"


def test_markets_subpackage_importable():
    """``import tradewinds.markets`` must succeed when tradewinds-markets is installed."""
    import tradewinds.markets

    assert tradewinds.markets.__version__ == "0.0.1"

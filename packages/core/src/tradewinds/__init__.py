"""tradewinds — local-first SDK for prediction-market weather settlement research.

Sprint 0 v0.1.0 ships:
- ``tradewinds.research(station, from_date, to_date, ...)`` — the v0.14.1 ``pairs()`` join,
  lifted from monorepo-v0.14.1, calling AWC + IEM + GHCNh + NWS CLI directly.
- ``tradewinds.snapshot`` — settlement-window math (LST, market_close_utc).

Adjacent surfaces:
- ``tradewinds.weather`` — observations + climate + forecasts (sibling package ``tradewinds-weather``).
- ``tradewinds.markets`` — Kalshi + Polymarket metadata (sibling package ``tradewinds-markets``,
  ships v0.1.0 in Sprint 0.5).

Namespace note: ``tradewinds`` is a split-distribution namespace package. Core owns this
``__init__.py``; sibling distributions ``tradewinds-weather`` and ``tradewinds-markets`` ship
subdirectories (``tradewinds/weather/``, ``tradewinds/markets/``) WITHOUT their own
namespace-root ``__init__.py``. The pkgutil declaration below extends ``__path__`` so Python's
import machinery finds those subpackages from whichever site-packages location installed them.
"""

# Split-distribution namespace: extend __path__ to discover sibling packages' contributions.
__path__ = __import__("pkgutil").extend_path(__path__, __name__)

__version__ = "0.1.0a1"

from tradewinds.research import research

__all__ = ["__version__", "research"]

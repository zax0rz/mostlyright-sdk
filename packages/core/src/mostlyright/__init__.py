"""mostlyright — local-first SDK for prediction-market weather settlement research.

Sprint 0 v0.1.0 ships:
- ``mostlyright.research(station, from_date, to_date, ...)`` — the v0.14.1 ``pairs()`` join,
  lifted from monorepo-v0.14.1, calling AWC + IEM + GHCNh + NWS CLI directly.
- ``mostlyright.snapshot`` — settlement-window math (LST, market_close_utc).

Adjacent surfaces:
- ``mostlyright.weather`` — observations + climate + forecasts (sibling package ``mostlyrightmd-weather``).
- ``mostlyright.markets`` — Kalshi + Polymarket metadata (sibling package ``mostlyrightmd-markets``,
  ships v0.1.0 in Sprint 0.5).

Namespace note: ``mostlyright`` is a split-distribution namespace package. Core owns this
``__init__.py``; sibling distributions ``mostlyrightmd-weather`` and ``mostlyrightmd-markets`` ship
subdirectories (``mostlyright/weather/``, ``mostlyright/markets/``) WITHOUT their own
namespace-root ``__init__.py``. The pkgutil declaration below extends ``__path__`` so Python's
import machinery finds those subpackages from whichever site-packages location installed them.
"""

# Split-distribution namespace: extend __path__ to discover sibling packages' contributions.
__path__ = __import__("pkgutil").extend_path(__path__, __name__)

__version__ = "0.1.0rc1"

from mostlyright.discover import discover
from mostlyright.research import research
from mostlyright.stations import CATALOG, Station, StationCatalog

__all__ = [
    "CATALOG",
    "Station",
    "StationCatalog",
    "__version__",
    "discover",
    "live",
    "research",
]


# Lazy `mostlyright.live` access (Phase 11). Both `discover` and `research`
# above already eagerly import `mostlyright.core` (which pulls pandas via
# `core.validator`), so the eager-pandas path is pre-existing and NOT a
# Phase 11 regression. Even so, we expose `live` through a module-level
# `__getattr__` hook so `import mostlyright` doesn't pull in
# `mostlyright.weather` (via the live module's deferred fetcher imports
# that fire on first use, not first attribute access). First access via
# `mostlyright.live.stream(...)` resolves and caches the submodule.
def __getattr__(name: str):
    if name == "live":
        import mostlyright.live as _live

        # Cache on the module so subsequent accesses skip __getattr__.
        globals()["live"] = _live
        return _live
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

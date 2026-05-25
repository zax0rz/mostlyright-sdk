"""polars compatibility shim (Phase 6 W3).

Single source of truth for whether the optional ``[polars]`` extra is
available. Callers should use :func:`require_polars` to fetch the polars
module with a structured install-hint error instead of letting raw
``ImportError`` propagate.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from tradewinds.core.exceptions import SourceUnavailableError

if TYPE_CHECKING:
    pass


__all__ = ["HAS_POLARS", "from_pandas", "require_polars"]


def _try_import_polars() -> Any:
    try:
        import polars as pl

        return pl
    except ImportError:
        return None


_pl = _try_import_polars()
HAS_POLARS: bool = _pl is not None


def require_polars() -> Any:
    """Return the ``polars`` module or raise ``SourceUnavailableError``.

    Mirrors the install-hint pattern of ``tradewinds.weather.forecast_nwp``'s
    ``[nwp]`` gate.
    """
    if _pl is None:
        raise SourceUnavailableError(
            "polars backend requested but the optional [polars] extra "
            "is not installed. Install with: pip install tradewinds[polars]"
        )
    return _pl


def from_pandas(df: Any) -> Any:
    """Convert a pandas DataFrame to a polars DataFrame.

    Raises ``SourceUnavailableError`` if polars is not installed.
    """
    pl = require_polars()
    return pl.from_pandas(df)

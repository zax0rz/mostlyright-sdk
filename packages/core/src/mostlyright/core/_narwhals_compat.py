"""narwhals compatibility shim for cross-backend operations (Phase 6 W2).

narwhals is the unified API over pandas/polars/pyarrow that the
cleanly-portable modules go through. The shim documents the project's
narwhals usage patterns so callers don't sprout one-off
``nw.from_native(...)`` calls scattered across the surface.

Usage::

    from mostlyright.core._narwhals_compat import to_narwhals, to_native

    nw_df = to_narwhals(df)            # pandas OR polars OR narwhals
    result = nw_df.with_columns(...)   # narwhals operations
    out = to_native(result)            # back to the input backend

When narwhals is not installed, ``to_narwhals`` raises
``SourceUnavailableError`` with an install hint (mirrors the ``[nwp]``
pattern). Callers that want eager-skip should call
:func:`HAS_NARWHALS` first.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from mostlyright.core.exceptions import SourceUnavailableError

if TYPE_CHECKING:
    pass


__all__ = [
    "HAS_NARWHALS",
    "require_narwhals",
    "to_narwhals",
    "to_native",
]


def _try_import_narwhals() -> Any:
    try:
        import narwhals as nw

        return nw
    except ImportError:
        return None


_nw = _try_import_narwhals()
HAS_NARWHALS: bool = _nw is not None


def require_narwhals() -> Any:
    """Return the ``narwhals`` module or raise with an install hint."""
    if _nw is None:
        raise SourceUnavailableError(
            "narwhals is required for cross-backend operations. "
            "Install with: pip install mostlyright[polars]"
        )
    return _nw


def to_narwhals(df: Any) -> Any:
    """Wrap any supported frame (pandas / polars) in a narwhals proxy.

    Already-narwhals inputs pass through unchanged. Raises
    ``SourceUnavailableError`` if narwhals is not installed.
    """
    nw = require_narwhals()
    # narwhals.from_native is idempotent on its own DataFrame wrapper.
    if isinstance(df, (nw.DataFrame, nw.LazyFrame)):
        return df
    return nw.from_native(df, eager_only=True)


def to_native(nw_df: Any) -> Any:
    """Unwrap a narwhals frame back to its native pandas/polars frame."""
    nw = require_narwhals()
    if isinstance(nw_df, (nw.DataFrame, nw.LazyFrame)):
        return nw_df.to_native()
    return nw_df


def is_polars(df: Any) -> bool:
    """Return True if ``df`` is a polars DataFrame (cheap import-free check).

    Uses module-name string matching to avoid importing polars when the
    optional extra is absent. Safe to call on any object.
    """
    cls = type(df)
    module = getattr(cls, "__module__", "")
    return module.startswith("polars.") and cls.__name__ == "DataFrame"


def is_pandas(df: Any) -> bool:
    """Return True if ``df`` is a pandas DataFrame."""
    cls = type(df)
    module = getattr(cls, "__module__", "")
    return module.startswith("pandas.") and cls.__name__ == "DataFrame"


def to_pandas_if_polars(df: Any) -> tuple[Any, bool]:
    """Convert ``df`` to pandas if it is polars; return ``(df, was_polars)``.

    Used at module-entry shims to keep the parity-tested pandas body
    intact while accepting polars input. The boolean lets the caller
    decide whether to convert the result back to polars at the
    out-boundary.
    """
    if is_polars(df):
        return df.to_pandas(), True
    return df, False


def pandas_to_polars(df: Any) -> Any:
    """Convert a pandas DataFrame to polars via ``pl.from_pandas``.

    Raises ``SourceUnavailableError`` (via ``require_polars``) when
    polars is absent.
    """
    from mostlyright.core._polars_compat import require_polars

    pl = require_polars()
    return pl.from_pandas(df)


def pandas_series_to_polars(s: Any) -> Any:
    """Convert a pandas Series to polars Series."""
    from mostlyright.core._polars_compat import require_polars

    pl = require_polars()
    return pl.from_pandas(s)

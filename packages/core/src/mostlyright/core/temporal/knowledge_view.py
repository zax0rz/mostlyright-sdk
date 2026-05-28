"""KnowledgeView — temporal filtering by ``knowledge_time``.

A plain wrapper class (not a pandas accessor, not a DataFrame subclass)
that exposes a ``dataframe()`` view filtered by ``knowledge_time <= as_of``.
This is the structural temporal-safety primitive the mostlyright research()
Mode 2 dispatch uses to render leakage-free training tables — any row
whose ``knowledge_time`` is later than the asserted as-of cutoff is
silently dropped from the view (and would be loud via :class:`LeakageDetector`).

Design constraints (CORE-07):

- Uses ``__slots__`` for memory predictability.
- Does NOT register a pandas accessor (verified by acceptance test).
- Validates input shape eagerly — raises :class:`SchemaValidationError`
  if ``knowledge_time`` is missing or not tz-aware UTC.

See ``docs/design.md`` §M (KnowledgeView semantics).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from mostlyright.core.exceptions import SchemaValidationError
from mostlyright.core.result import MostlyRightResult
from mostlyright.core.temporal.timepoint import TimePoint

if TYPE_CHECKING:
    import pandas as pd


__all__ = ["KnowledgeView"]


class KnowledgeView:
    """A filtered, knowledge-time-bounded view over a DataFrame.

    Construction validates the shape of the input DataFrame. After
    construction, :meth:`dataframe` returns a defensive copy of the rows
    where ``knowledge_time <= as_of``.

    Examples
    --------
    Build a 3-row DataFrame with a tz-aware UTC ``knowledge_time`` column
    and view only the rows knowable as of ``2025-01-02T12:00:00Z``:

    >>> import pandas as pd
    >>> from mostlyright.core import KnowledgeView, TimePoint
    >>> df = pd.DataFrame({
    ...     "knowledge_time": pd.to_datetime([
    ...         "2025-01-01T00:00:00Z",
    ...         "2025-01-02T00:00:00Z",
    ...         "2025-01-03T00:00:00Z",
    ...     ], utc=True),
    ...     "value": [10, 20, 30],
    ... })
    >>> view = KnowledgeView(df, TimePoint("2025-01-02T12:00:00Z"))
    >>> len(view.dataframe())
    2
    """

    __slots__ = ("_as_of", "_df")

    def __init__(self, df: pd.DataFrame | MostlyRightResult, as_of: TimePoint) -> None:
        import pandas as pd

        # Phase 6 W0-T5: accept MostlyRightResult; unwrap to pandas.
        # Polars-mode callers flow through frame_as_pandas() because the
        # KnowledgeView body uses pd.api.types and df.loc[mask].copy().
        if isinstance(df, MostlyRightResult):
            df = df.frame_as_pandas()

        if "knowledge_time" not in df.columns:
            raise SchemaValidationError(
                "KnowledgeView requires 'knowledge_time' column",
                schema_id="<runtime>",
                violations=[{"column": "knowledge_time", "rule": "required"}],
            )
        if not isinstance(as_of, TimePoint):
            raise TypeError(f"as_of must be a TimePoint, got {type(as_of).__name__}")
        col = df["knowledge_time"]
        if not pd.api.types.is_datetime64_any_dtype(col):
            raise SchemaValidationError(
                "knowledge_time must be a datetime64 column",
                schema_id="<runtime>",
                violations=[{"column": "knowledge_time", "rule": "datetime_dtype"}],
            )
        if getattr(col.dt, "tz", None) is None:
            raise SchemaValidationError(
                "knowledge_time must be tz-aware UTC",
                schema_id="<runtime>",
                violations=[{"column": "knowledge_time", "rule": "tz_aware_utc"}],
            )
        self._df = df
        self._as_of = as_of

    def dataframe(self) -> pd.DataFrame:
        """Return a defensive copy of the rows where ``knowledge_time <= as_of``."""
        cutoff = self._as_of.to_utc()
        mask = self._df["knowledge_time"] <= cutoff
        return self._df.loc[mask].copy()

    @property
    def as_of(self) -> TimePoint:
        """The as-of cutoff supplied at construction."""
        return self._as_of

    def __repr__(self) -> str:
        return f"KnowledgeView(rows={len(self._df)}, as_of={self._as_of.to_utc().isoformat()})"

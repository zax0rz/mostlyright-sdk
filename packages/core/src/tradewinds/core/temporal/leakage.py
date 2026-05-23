"""LeakageDetector — loud assertion of as-of leakage absence.

Where :class:`KnowledgeView` silently filters, ``assert_no_leakage`` raises
:class:`LeakageError` when one or more rows have ``knowledge_time > as_of``.
The error payload follows the design.md §D contract: it carries the count
of violating rows and a sample (capped at 10) so callers can surface the
problem without dumping the entire offending DataFrame.

Used by:
- The audit path of ``research()`` Mode 2 dispatch (loud failure).
- Validator's optional leakage check (when caller asks for it).
- Test fixtures verifying KnowledgeView's filter behaviour.

See ``docs/design.md`` §M (leakage semantics) + §D (LeakageError payload).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pandas as pd

from tradewinds.core.exceptions import LeakageError, SchemaValidationError
from tradewinds.core.temporal.timepoint import TimePoint

if TYPE_CHECKING:
    pass


__all__ = ["LeakageDetector", "assert_no_leakage"]


_SAMPLE_CAP = 10


def assert_no_leakage(df: pd.DataFrame, as_of: TimePoint) -> None:
    """Raise :class:`LeakageError` if any row's ``knowledge_time > as_of``.

    Args:
        df: DataFrame with a tz-aware UTC ``knowledge_time`` column.
        as_of: The as-of cutoff. Rows with strictly greater ``knowledge_time``
            count as leakage.

    Raises:
        SchemaValidationError: if ``knowledge_time`` is missing or not tz-aware UTC.
        TypeError: if ``as_of`` is not a :class:`TimePoint`.
        LeakageError: if ≥1 rows have ``knowledge_time > as_of``. Payload
            carries ``violating_count`` and a sample (≤10) of violations.
    """
    if "knowledge_time" not in df.columns:
        raise SchemaValidationError(
            "assert_no_leakage requires 'knowledge_time' column",
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

    cutoff = as_of.to_utc()
    mask = col > cutoff
    n = int(mask.sum())
    if n == 0:
        return

    sample = df.loc[mask].head(_SAMPLE_CAP)
    sample_violations: list[dict[str, object]] = []
    for idx, row in sample.iterrows():
        ts = row["knowledge_time"]
        ts_iso = pd.Timestamp(ts).isoformat()
        sample_violations.append({"row_idx": int(idx), "knowledge_time": ts_iso})

    raise LeakageError(
        f"Found {n} row(s) with knowledge_time > as_of",
        as_of=cutoff.isoformat(),
        violating_count=n,
        sample_violations=sample_violations,
    )


class LeakageDetector:
    """Convenience wrapper for repeated detection against a fixed ``as_of``."""

    __slots__ = ("_as_of",)

    def __init__(self, as_of: TimePoint) -> None:
        if not isinstance(as_of, TimePoint):
            raise TypeError(f"as_of must be a TimePoint, got {type(as_of).__name__}")
        self._as_of = as_of

    @property
    def as_of(self) -> TimePoint:
        return self._as_of

    def check(self, df: pd.DataFrame) -> None:
        """Run :func:`assert_no_leakage` against the bound ``as_of``."""
        assert_no_leakage(df, self._as_of)

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

from mostlyright.core.exceptions import (
    IssuedAtMissingError,
    LeakageError,
    SchemaValidationError,
)
from mostlyright.core.result import TradewindsResult
from mostlyright.core.temporal.timepoint import TimePoint

if TYPE_CHECKING:
    pass


__all__ = [
    "LeakageDetector",
    "assert_issued_at_populated",
    "assert_no_leakage",
]


_SAMPLE_CAP = 10
#: Smaller cap for the issued_at assertion — leakage payloads should fit on
#: one screen when surfaced through MCP, and a forecast frame missing
#: ``issued_at`` is a structural bug rather than a per-row data issue. Phase
#: 20 OM-04.
_ISSUED_AT_SAMPLE_CAP = 5


def assert_no_leakage(df: pd.DataFrame | TradewindsResult, as_of: TimePoint) -> None:
    """Raise :class:`LeakageError` if any row's ``knowledge_time > as_of``.

    Phase 6 W0-T6: accepts either a raw DataFrame or a
    :class:`TradewindsResult`; wrapped polars frames are converted to
    pandas via :meth:`TradewindsResult.frame_as_pandas` because the body
    of this function uses ``pd.Timestamp`` + ``iterrows`` semantics.

    Args:
        df: DataFrame with a tz-aware UTC ``knowledge_time`` column, OR
            a :class:`TradewindsResult` wrapping such a frame.
        as_of: The as-of cutoff. Rows with strictly greater ``knowledge_time``
            count as leakage.

    Raises:
        SchemaValidationError: if ``knowledge_time`` is missing or not tz-aware UTC.
        TypeError: if ``as_of`` is not a :class:`TimePoint`.
        LeakageError: if ≥1 rows have ``knowledge_time > as_of``. Payload
            carries ``violating_count`` and a sample (≤10) of violations.

    Examples
    --------
    A leak-free frame passes silently:

    >>> import pandas as pd
    >>> from mostlyright.core import TimePoint, assert_no_leakage
    >>> df = pd.DataFrame({
    ...     "knowledge_time": pd.to_datetime(["2025-01-01T00:00:00Z"], utc=True),
    ...     "value": [10],
    ... })
    >>> assert_no_leakage(df, TimePoint("2025-01-02T00:00:00Z"))

    A row past the cutoff raises :class:`LeakageError`:

    >>> from mostlyright.core import LeakageError
    >>> leaky = pd.DataFrame({
    ...     "knowledge_time": pd.to_datetime(["2025-01-03T00:00:00Z"], utc=True),
    ...     "value": [99],
    ... })
    >>> try:
    ...     assert_no_leakage(leaky, TimePoint("2025-01-02T00:00:00Z"))
    ... except LeakageError as err:
    ...     print(err.violating_count)
    1
    """
    if isinstance(df, TradewindsResult):
        df = df.frame_as_pandas()
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


def assert_issued_at_populated(df: pd.DataFrame | TradewindsResult) -> None:
    """Raise :class:`IssuedAtMissingError` if any row has null ``issued_at``.

    Forecast rows MUST carry their model-run time to be leakage-safe; a
    missing ``issued_at`` means we cannot verify the cycle predated the
    ``as_of`` cutoff in :func:`research`. For Open-Meteo this should be
    impossible by construction (the fetcher derives ``issued_at`` per row),
    so this check is a defensive net.

    Mirrors structural conventions of :func:`assert_no_leakage`:
    :class:`TradewindsResult` (and any duck-typed ``.df`` carrier)
    unwrap, column-existence guard, sample-cap.

    Phase 20 OM-04.
    """
    if isinstance(df, TradewindsResult):
        df = df.frame_as_pandas()
    elif hasattr(df, "df") and not hasattr(df, "columns"):
        # Duck-type for non-TradewindsResult wrappers (e.g. test doubles).
        df = df.df

    if "issued_at" not in df.columns:
        raise SchemaValidationError(
            "assert_issued_at_populated requires 'issued_at' column",
            schema_id="schema.forecast.station.v1",
            violations=[{"column": "issued_at", "rule": "required"}],
        )

    if len(df) == 0:
        return  # empty frame vacuously satisfies

    nulls_mask = df["issued_at"].isna()
    violating_count = int(nulls_mask.sum())
    if violating_count == 0:
        return

    null_indices = df.index[nulls_mask].tolist()
    samples = [{"row_idx": int(idx)} for idx in null_indices[:_ISSUED_AT_SAMPLE_CAP]]

    raise IssuedAtMissingError(
        f"{violating_count} row(s) have null issued_at; cannot verify leakage-safety",
        violating_count=violating_count,
        sample_violations=samples,
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

    def check(self, df: pd.DataFrame | TradewindsResult) -> None:
        """Run :func:`assert_no_leakage` against the bound ``as_of``.

        Accepts either a raw DataFrame or a :class:`TradewindsResult`
        wrapper (unwrapped inside :func:`assert_no_leakage`).
        """
        assert_no_leakage(df, self._as_of)

    def check_issued_at(self, df: pd.DataFrame | TradewindsResult) -> None:
        """Raise :class:`IssuedAtMissingError` if any row has null ``issued_at``.

        Phase 20 OM-04 extension. Independent of ``as_of`` — the bound
        cutoff is irrelevant when the row carries no model-run time at
        all.
        """
        assert_issued_at_populated(df)

"""Unit + property tests for KnowledgeView."""

from __future__ import annotations

from datetime import UTC, datetime

import pandas as pd
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from mostlyright.core.exceptions import SchemaValidationError
from mostlyright.core.temporal.knowledge_view import KnowledgeView
from mostlyright.core.temporal.timepoint import TimePoint

# CORE-08 constrained datetime range.
_MIN = datetime(2018, 1, 1, tzinfo=UTC)
_MAX = datetime(2027, 12, 31, 23, 59, 59, tzinfo=UTC)


def _df_with_knowledge_times(events: list[datetime]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "knowledge_time": pd.to_datetime(events, utc=True),
            "value": list(range(len(events))),
        }
    )


# ----------------------------------------------------------------------
# Construction validation
# ----------------------------------------------------------------------
class TestKnowledgeViewConstruction:
    def test_missing_knowledge_time_column_raises(self) -> None:
        df = pd.DataFrame({"value": [1, 2]})
        with pytest.raises(SchemaValidationError) as exc:
            KnowledgeView(df, TimePoint("2025-01-01T00:00:00+00:00"))
        assert "knowledge_time" in str(exc.value)

    def test_naive_timestamps_raise(self) -> None:
        df = pd.DataFrame({"knowledge_time": pd.to_datetime(["2025-01-01", "2025-01-02"])})
        with pytest.raises(SchemaValidationError):
            KnowledgeView(df, TimePoint("2025-01-01T00:00:00+00:00"))

    def test_non_datetime_column_raises(self) -> None:
        df = pd.DataFrame({"knowledge_time": ["a", "b", "c"]})
        with pytest.raises(SchemaValidationError):
            KnowledgeView(df, TimePoint("2025-01-01T00:00:00+00:00"))

    def test_non_timepoint_as_of_raises(self) -> None:
        df = _df_with_knowledge_times([datetime(2025, 1, 1, tzinfo=UTC)])
        with pytest.raises(TypeError):
            KnowledgeView(df, "2025-01-01")  # type: ignore[arg-type]

    def test_uses_slots(self) -> None:
        """CORE-07 — KnowledgeView must use __slots__ for memory predictability."""
        df = _df_with_knowledge_times([datetime(2025, 1, 1, tzinfo=UTC)])
        kv = KnowledgeView(df, TimePoint("2025-01-01T00:00:00+00:00"))
        with pytest.raises(AttributeError):
            kv.arbitrary_attribute = 1  # type: ignore[attr-defined]


# ----------------------------------------------------------------------
# Filter semantics
# ----------------------------------------------------------------------
class TestKnowledgeViewFilter:
    def test_strict_less_equal_cutoff(self) -> None:
        """Rows with knowledge_time == as_of are KEPT (<=, not <)."""
        df = _df_with_knowledge_times(
            [
                datetime(2025, 1, 1, tzinfo=UTC),
                datetime(2025, 1, 2, tzinfo=UTC),
            ]
        )
        kv = KnowledgeView(df, TimePoint("2025-01-01T00:00:00+00:00"))
        out = kv.dataframe()
        assert len(out) == 1
        assert out.iloc[0]["value"] == 0

    def test_empty_when_all_after_cutoff(self) -> None:
        df = _df_with_knowledge_times(
            [
                datetime(2025, 6, 1, tzinfo=UTC),
                datetime(2025, 7, 1, tzinfo=UTC),
            ]
        )
        kv = KnowledgeView(df, TimePoint("2025-01-01T00:00:00+00:00"))
        assert kv.dataframe().empty

    def test_full_when_all_at_or_before_cutoff(self) -> None:
        df = _df_with_knowledge_times(
            [
                datetime(2024, 6, 1, tzinfo=UTC),
                datetime(2024, 7, 1, tzinfo=UTC),
            ]
        )
        kv = KnowledgeView(df, TimePoint("2025-01-01T00:00:00+00:00"))
        assert len(kv.dataframe()) == 2

    def test_returned_dataframe_is_defensive_copy(self) -> None:
        df = _df_with_knowledge_times([datetime(2024, 6, 1, tzinfo=UTC)])
        kv = KnowledgeView(df, TimePoint("2025-01-01T00:00:00+00:00"))
        out = kv.dataframe()
        out.iloc[0, out.columns.get_loc("value")] = 999
        # Original untouched.
        assert df.iloc[0]["value"] == 0

    def test_as_of_property(self) -> None:
        df = _df_with_knowledge_times([datetime(2024, 6, 1, tzinfo=UTC)])
        as_of = TimePoint("2025-01-01T00:00:00+00:00")
        kv = KnowledgeView(df, as_of)
        assert kv.as_of is as_of

    def test_dst_boundary_2024_march(self) -> None:
        """DST spring-forward — 2024-03-10 02:00 EST → 03:00 EDT in US zones."""
        df = _df_with_knowledge_times(
            [
                datetime(2024, 3, 10, 6, tzinfo=UTC),
                datetime(2024, 3, 10, 7, tzinfo=UTC),
                datetime(2024, 3, 10, 8, tzinfo=UTC),
            ]
        )
        kv = KnowledgeView(df, TimePoint("2024-03-10T07:00:00+00:00"))
        assert len(kv.dataframe()) == 2

    def test_dst_boundary_2024_november(self) -> None:
        """DST fall-back — 2024-11-03 02:00 EDT → 01:00 EST."""
        df = _df_with_knowledge_times(
            [
                datetime(2024, 11, 3, 5, tzinfo=UTC),
                datetime(2024, 11, 3, 6, tzinfo=UTC),
                datetime(2024, 11, 3, 7, tzinfo=UTC),
            ]
        )
        kv = KnowledgeView(df, TimePoint("2024-11-03T06:00:00+00:00"))
        assert len(kv.dataframe()) == 2


# ----------------------------------------------------------------------
# Property tests (Hypothesis, CORE-08 constrained range)
# ----------------------------------------------------------------------
@given(
    events=st.lists(
        st.datetimes(
            min_value=_MIN.replace(tzinfo=None),
            max_value=_MAX.replace(tzinfo=None),
            timezones=st.just(UTC),
        ),
        min_size=0,
        max_size=50,
    ),
    as_of=st.datetimes(
        min_value=_MIN.replace(tzinfo=None),
        max_value=_MAX.replace(tzinfo=None),
        timezones=st.just(UTC),
    ),
)
@settings(max_examples=200, deadline=2000)
def test_property_filter_correctness(events, as_of):
    """Every row in the filtered output has knowledge_time <= as_of, and
    the count equals the manual mask count."""
    df = pd.DataFrame(
        {
            "knowledge_time": pd.to_datetime(events, utc=True)
            if events
            else pd.Series([], dtype="datetime64[ns, UTC]"),
        }
    )
    as_of_tp = TimePoint(as_of.isoformat())
    kv = KnowledgeView(df, as_of_tp)
    out = kv.dataframe()
    # Every row in out has knowledge_time <= as_of.
    if not out.empty:
        assert (out["knowledge_time"] <= as_of_tp.to_utc()).all()
    # Count equals manual filter.
    if df.empty:
        assert out.empty
    else:
        expected = int((df["knowledge_time"] <= as_of_tp.to_utc()).sum())
        assert len(out) == expected


@given(
    events=st.lists(
        st.datetimes(
            min_value=_MIN.replace(tzinfo=None),
            max_value=_MAX.replace(tzinfo=None),
            timezones=st.just(UTC),
        ),
        min_size=1,
        max_size=50,
    ),
)
@settings(max_examples=100, deadline=2000)
def test_property_idempotent_construction(events):
    """Constructing twice with same args yields the same filtered output."""
    df = _df_with_knowledge_times(events)
    as_of = TimePoint("2025-01-01T00:00:00+00:00")
    kv1 = KnowledgeView(df, as_of)
    kv2 = KnowledgeView(df, as_of)
    pd.testing.assert_frame_equal(kv1.dataframe(), kv2.dataframe())


# ----------------------------------------------------------------------
# Pandas-accessor non-registration (CORE-07)
# ----------------------------------------------------------------------
def test_no_pandas_accessor_registered():
    """KnowledgeView must NOT register itself as a pandas DataFrame accessor."""
    # Importing the module is enough; verify no accessor leaked through.
    assert not hasattr(pd.DataFrame, "knowledge_view")
    assert not hasattr(pd.DataFrame, "KnowledgeView")

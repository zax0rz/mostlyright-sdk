"""Unit + property tests for LeakageDetector + assert_no_leakage."""

from __future__ import annotations

from datetime import UTC, datetime

import pandas as pd
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from mostlyright.core.exceptions import LeakageError, SchemaValidationError
from mostlyright.core.temporal.leakage import LeakageDetector, assert_no_leakage
from mostlyright.core.temporal.timepoint import TimePoint

# CORE-08 constrained datetime range.
_MIN = datetime(2018, 1, 1, tzinfo=UTC)
_MAX = datetime(2027, 12, 31, 23, 59, 59, tzinfo=UTC)


def _df(events: list[datetime]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "knowledge_time": pd.to_datetime(events, utc=True),
            "value": list(range(len(events))),
        }
    )


# ----------------------------------------------------------------------
# Happy path
# ----------------------------------------------------------------------
def test_no_leakage_returns_silently():
    df = _df([datetime(2024, 1, 1, tzinfo=UTC), datetime(2024, 6, 1, tzinfo=UTC)])
    as_of = TimePoint("2025-01-01T00:00:00+00:00")
    assert_no_leakage(df, as_of)  # no raise


def test_empty_dataframe_returns_silently():
    df = pd.DataFrame({"knowledge_time": pd.Series([], dtype="datetime64[ns, UTC]")})
    as_of = TimePoint("2025-01-01T00:00:00+00:00")
    assert_no_leakage(df, as_of)  # no raise


def test_strict_greater_than_cutoff():
    """knowledge_time == as_of is NOT leakage (matches KnowledgeView semantics)."""
    df = _df([datetime(2025, 1, 1, tzinfo=UTC)])
    as_of = TimePoint("2025-01-01T00:00:00+00:00")
    assert_no_leakage(df, as_of)  # no raise


# ----------------------------------------------------------------------
# Error path
# ----------------------------------------------------------------------
class TestLeakageRaises:
    def test_single_row_after_cutoff_raises(self):
        df = _df([datetime(2025, 6, 1, tzinfo=UTC)])
        as_of = TimePoint("2025-01-01T00:00:00+00:00")
        with pytest.raises(LeakageError) as exc:
            assert_no_leakage(df, as_of)
        assert exc.value.violating_count == 1
        assert exc.value.as_of == "2025-01-01T00:00:00+00:00"

    def test_sample_violations_capped_at_10(self):
        df = _df([datetime(2025, 6, i + 1, tzinfo=UTC) for i in range(25)])
        as_of = TimePoint("2025-01-01T00:00:00+00:00")
        with pytest.raises(LeakageError) as exc:
            assert_no_leakage(df, as_of)
        assert exc.value.violating_count == 25
        assert len(exc.value.sample_violations) == 10

    def test_sample_violations_payload_shape(self):
        df = _df([datetime(2025, 6, 1, tzinfo=UTC)])
        as_of = TimePoint("2025-01-01T00:00:00+00:00")
        with pytest.raises(LeakageError) as exc:
            assert_no_leakage(df, as_of)
        sv = exc.value.sample_violations[0]
        assert set(sv.keys()) == {"row_idx", "knowledge_time"}
        assert sv["row_idx"] == 0
        assert sv["knowledge_time"].startswith("2025-06-01")

    def test_to_dict_is_json_safe(self):
        df = _df([datetime(2025, 6, 1, tzinfo=UTC)])
        as_of = TimePoint("2025-01-01T00:00:00+00:00")
        with pytest.raises(LeakageError) as exc:
            assert_no_leakage(df, as_of)
        import json

        payload = exc.value.to_dict()
        # Round-trip via json.dumps.
        roundtripped = json.loads(json.dumps(payload))
        assert roundtripped["violating_count"] == 1
        assert roundtripped["error_code"] == "LEAKAGE_DETECTED"


# ----------------------------------------------------------------------
# Validation
# ----------------------------------------------------------------------
def test_missing_knowledge_time_column_raises_schema_error():
    df = pd.DataFrame({"value": [1, 2]})
    as_of = TimePoint("2025-01-01T00:00:00+00:00")
    with pytest.raises(SchemaValidationError):
        assert_no_leakage(df, as_of)


def test_naive_knowledge_time_raises_schema_error():
    df = pd.DataFrame({"knowledge_time": pd.to_datetime(["2025-01-01"])})
    as_of = TimePoint("2025-01-01T00:00:00+00:00")
    with pytest.raises(SchemaValidationError):
        assert_no_leakage(df, as_of)


def test_non_datetime_knowledge_time_raises_schema_error():
    df = pd.DataFrame({"knowledge_time": ["a", "b"]})
    as_of = TimePoint("2025-01-01T00:00:00+00:00")
    with pytest.raises(SchemaValidationError):
        assert_no_leakage(df, as_of)


def test_non_timepoint_as_of_raises_typeerror():
    df = _df([datetime(2025, 1, 1, tzinfo=UTC)])
    with pytest.raises(TypeError):
        assert_no_leakage(df, "2025-01-01")  # type: ignore[arg-type]


# ----------------------------------------------------------------------
# LeakageDetector wrapper
# ----------------------------------------------------------------------
class TestLeakageDetector:
    def test_check_no_leakage_returns_silently(self):
        d = LeakageDetector(TimePoint("2025-01-01T00:00:00+00:00"))
        d.check(_df([datetime(2024, 6, 1, tzinfo=UTC)]))

    def test_check_raises_on_leakage(self):
        d = LeakageDetector(TimePoint("2025-01-01T00:00:00+00:00"))
        with pytest.raises(LeakageError):
            d.check(_df([datetime(2025, 6, 1, tzinfo=UTC)]))

    def test_uses_slots(self):
        d = LeakageDetector(TimePoint("2025-01-01T00:00:00+00:00"))
        with pytest.raises(AttributeError):
            d.arbitrary_attr = 1  # type: ignore[attr-defined]

    def test_non_timepoint_raises_typeerror(self):
        with pytest.raises(TypeError):
            LeakageDetector("2025-01-01")  # type: ignore[arg-type]

    def test_as_of_property(self):
        as_of = TimePoint("2025-01-01T00:00:00+00:00")
        d = LeakageDetector(as_of)
        assert d.as_of is as_of


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
        min_size=1,
        max_size=50,
    ),
    as_of=st.datetimes(
        min_value=_MIN.replace(tzinfo=None),
        max_value=_MAX.replace(tzinfo=None),
        timezones=st.just(UTC),
    ),
)
@settings(max_examples=200, deadline=2000)
def test_property_count_matches_strict_greater(events, as_of):
    """The error's violating_count == count of rows with knowledge_time > as_of."""
    df = _df(events)
    as_of_tp = TimePoint(as_of.isoformat())
    expected = int((df["knowledge_time"] > as_of_tp.to_utc()).sum())
    if expected == 0:
        assert_no_leakage(df, as_of_tp)
    else:
        with pytest.raises(LeakageError) as exc:
            assert_no_leakage(df, as_of_tp)
        assert exc.value.violating_count == expected
        # Sample is capped at 10.
        assert len(exc.value.sample_violations) == min(10, expected)

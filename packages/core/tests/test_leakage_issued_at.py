"""Phase 20 OM-04: LeakageDetector.check_issued_at + assert_issued_at_populated."""

from __future__ import annotations

import pandas as pd
import pytest
from mostlyright.core.exceptions import (
    IssuedAtMissingError,
    SchemaValidationError,
)
from mostlyright.core.temporal.leakage import (
    LeakageDetector,
    assert_issued_at_populated,
)
from mostlyright.core.temporal.timepoint import TimePoint


def _make_df(issued_at_values: list) -> pd.DataFrame:
    """Build a 1-column DataFrame with the supplied issued_at values."""
    return pd.DataFrame(
        {
            "issued_at": pd.to_datetime(issued_at_values, utc=True),
        }
    )


def test_assert_issued_at_populated_passes_when_all_populated() -> None:
    df = _make_df(["2024-06-01T00:00:00Z", "2024-06-01T06:00:00Z"])
    # Should not raise
    assert_issued_at_populated(df)


def test_assert_issued_at_populated_raises_on_single_null() -> None:
    df = _make_df(["2024-06-01T00:00:00Z", None])
    with pytest.raises(IssuedAtMissingError) as exc_info:
        assert_issued_at_populated(df)
    assert exc_info.value.violating_count == 1
    assert len(exc_info.value.sample_violations) >= 1


def test_assert_issued_at_populated_raises_with_multiple_nulls() -> None:
    df = _make_df([None, "2024-06-01T00:00:00Z", None, None])
    with pytest.raises(IssuedAtMissingError) as exc_info:
        assert_issued_at_populated(df)
    assert exc_info.value.violating_count == 3


def test_assert_issued_at_populated_raises_schema_error_when_column_missing() -> None:
    df = pd.DataFrame({"some_other_col": [1, 2, 3]})
    with pytest.raises(SchemaValidationError):
        assert_issued_at_populated(df)


def test_assert_issued_at_populated_unwraps_tradewinds_result() -> None:
    """Mirror of assert_no_leakage L82-83 — unwrap .df attribute if present."""
    df = _make_df(["2024-06-01T00:00:00Z"])

    class FakeResult:
        pass

    res = FakeResult()
    res.df = df
    # Should not raise; should unwrap via duck-type
    assert_issued_at_populated(res)


def test_assert_issued_at_populated_empty_dataframe_no_raise() -> None:
    df = pd.DataFrame({"issued_at": pd.to_datetime([], utc=True)})
    assert_issued_at_populated(df)


def test_leakage_detector_check_issued_at_wraps() -> None:
    df = _make_df([None])
    detector = LeakageDetector(as_of=TimePoint("2024-06-01T17:00:00Z"))
    with pytest.raises(IssuedAtMissingError):
        detector.check_issued_at(df)


def test_assert_issued_at_populated_sample_violations_capped() -> None:
    # 10 null rows — sample_violations cap is 5 for this assertion.
    df = _make_df([None] * 10)
    with pytest.raises(IssuedAtMissingError) as exc_info:
        assert_issued_at_populated(df)
    assert exc_info.value.violating_count == 10
    assert len(exc_info.value.sample_violations) <= 5


def test_parity_module_present_under_unified_schema() -> None:
    """Smoke check — the repo's parity test file must exist; full parity
    runs via the verify step (``uv run pytest tests/test_parity.py``)."""
    from pathlib import Path

    # packages/core/tests/test_leakage_issued_at.py
    # → repo root is parents[3].
    repo_root = Path(__file__).resolve().parents[3]
    parity_path = repo_root / "tests" / "test_parity.py"
    assert parity_path.exists(), f"missing parity gate: {parity_path}"

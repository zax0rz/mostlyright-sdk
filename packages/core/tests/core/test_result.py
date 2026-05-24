"""Tests for ``tradewinds.core.result.TradewindsResult`` (Phase 6 W0)."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import UTC, datetime

import pandas as pd
import pytest
from tradewinds.core import (
    KnowledgeView,
    LeakageError,
    SourceMismatchError,
    TimePoint,
    TradewindsResult,
    assert_no_leakage,
    validate_dataframe,
)
from tradewinds.core.temporal.leakage import LeakageDetector

# ----------------------- dataclass shape -----------------------


def test_result_minimal_construction() -> None:
    df = pd.DataFrame({"value": [1, 2]})
    result = TradewindsResult(
        frame=df,
        source="iem.live",
        retrieved_at=datetime(2025, 1, 1, tzinfo=UTC),
    )
    assert result.source == "iem.live"
    assert result.schema_id is None
    assert result.qc is None
    assert result.data_version is None


def test_result_is_frozen() -> None:
    df = pd.DataFrame({"value": [1]})
    result = TradewindsResult(
        frame=df,
        source="iem.live",
        retrieved_at=datetime(2025, 1, 1, tzinfo=UTC),
    )
    with pytest.raises(FrozenInstanceError):
        result.source = "awc.live"  # type: ignore[misc]


def test_result_rejects_empty_source() -> None:
    df = pd.DataFrame({"value": [1]})
    with pytest.raises(ValueError, match="non-empty string"):
        TradewindsResult(
            frame=df,
            source="",
            retrieved_at=datetime(2025, 1, 1, tzinfo=UTC),
        )


def test_result_rejects_naive_retrieved_at() -> None:
    df = pd.DataFrame({"value": [1]})
    with pytest.raises(ValueError, match="tz-aware"):
        TradewindsResult(
            frame=df,
            source="iem.live",
            retrieved_at=datetime(2025, 1, 1),  # naive
        )


def test_result_rejects_non_datetime_retrieved_at() -> None:
    df = pd.DataFrame({"value": [1]})
    with pytest.raises(TypeError, match="must be a datetime"):
        TradewindsResult(
            frame=df,
            source="iem.live",
            retrieved_at="2025-01-01T00:00:00Z",  # type: ignore[arg-type]
        )


# ----------------------- frame_as_pandas + legacy_df_with_attrs -----------------------


def test_frame_as_pandas_returns_pandas_as_is() -> None:
    df = pd.DataFrame({"a": [1, 2, 3]})
    result = TradewindsResult(
        frame=df,
        source="iem.live",
        retrieved_at=datetime(2025, 1, 1, tzinfo=UTC),
    )
    out = result.frame_as_pandas()
    assert isinstance(out, pd.DataFrame)
    # Same object — no copy needed for pandas case.
    assert out is df


def test_legacy_df_with_attrs_stamps_all_provenance_fields() -> None:
    df = pd.DataFrame({"value": [1, 2]})
    ts = datetime(2025, 3, 4, 5, 6, 7, tzinfo=UTC)
    result = TradewindsResult(
        frame=df,
        source="awc.live",
        retrieved_at=ts,
        schema_id="schema.observation.v1",
        qc={"rules_fired": {"r1": 0}},
    )
    legacy = result.legacy_df_with_attrs()
    assert legacy.attrs["source"] == "awc.live"
    # Codex iter-1 P2 fix: legacy attrs carry the tz-aware datetime
    # (not an ISO string) so Schema.register() can consume it.
    assert legacy.attrs["retrieved_at"] == ts
    assert legacy.attrs["qc"] == {"rules_fired": {"r1": 0}}
    assert legacy.attrs["schema_id"] == "schema.observation.v1"
    # Underlying frame untouched.
    assert "source" not in df.attrs


def test_legacy_df_with_attrs_omits_optional_fields_when_unset() -> None:
    df = pd.DataFrame({"value": [1]})
    result = TradewindsResult(
        frame=df,
        source="iem.live",
        retrieved_at=datetime(2025, 1, 1, tzinfo=UTC),
    )
    legacy = result.legacy_df_with_attrs()
    assert legacy.attrs["source"] == "iem.live"
    assert "qc" not in legacy.attrs
    assert "data_version" not in legacy.attrs
    assert "schema_id" not in legacy.attrs


def test_legacy_df_with_attrs_returns_copy() -> None:
    # mutating the legacy view's attrs MUST NOT mutate the wrapper's frame.
    df = pd.DataFrame({"value": [1]})
    result = TradewindsResult(
        frame=df,
        source="iem.live",
        retrieved_at=datetime(2025, 1, 1, tzinfo=UTC),
    )
    legacy = result.legacy_df_with_attrs()
    legacy.attrs["source"] = "tampered"
    legacy_again = result.legacy_df_with_attrs()
    assert legacy_again.attrs["source"] == "iem.live"


# ----------------------- to_dict -----------------------


def test_to_dict_is_json_safe() -> None:
    import json

    result = TradewindsResult(
        frame=pd.DataFrame({"value": [1]}),
        source="iem.live",
        retrieved_at=datetime(2025, 1, 1, tzinfo=UTC),
        schema_id="schema.observation.v1",
        qc={"rules_fired": {"r1": 0}},
    )
    payload = result.to_dict()
    encoded = json.dumps(payload)  # must not raise
    assert json.loads(encoded) == payload
    assert payload["source"] == "iem.live"
    assert payload["schema_id"] == "schema.observation.v1"
    assert "qc" in payload


# ----------------------- validator unwrap dispatch -----------------------


def test_validator_accepts_tradewinds_result() -> None:
    """Validator unwraps TradewindsResult and validates byte-identically."""
    df = pd.DataFrame(
        {
            "date": pd.to_datetime(["2025-01-06"]).date,
            "station_code": ["KNYC"],
            "observation_date": pd.to_datetime(["2025-01-06"]).date,
            "high_temp_f": [40.0],
            "low_temp_f": [20.0],
            "report_type": ["DAILY_CLIMATE_RECORD"],
            "report_type_priority": [4],
            "retrieved_at": [datetime(2025, 1, 6, 12, 0, tzinfo=UTC)],
            "source": ["nws_cli"],
        }
    )

    # Direct call MUST raise the same source-identity error as wrapped call
    # when source doesn't match the registered canonical source.
    df.attrs["source"] = "awc.live"  # mismatch
    df.attrs["retrieved_at"] = datetime(2025, 1, 6, 12, 0, tzinfo=UTC).isoformat()
    with pytest.raises(SourceMismatchError):
        validate_dataframe(df, "schema.observation.v1")

    # Wrapped: same error.
    df2 = df.copy()
    # Reset attrs because the wrapper supplies them.
    df2.attrs.clear()
    result = TradewindsResult(
        frame=df2,
        source="awc.live",  # still a mismatch
        retrieved_at=datetime(2025, 1, 6, 12, 0, tzinfo=UTC),
    )
    with pytest.raises(SourceMismatchError):
        validate_dataframe(result, "schema.observation.v1")


# ----------------------- KnowledgeView unwrap dispatch -----------------------


def test_knowledge_view_accepts_tradewinds_result() -> None:
    df = pd.DataFrame(
        {
            "knowledge_time": pd.to_datetime(
                ["2025-01-01T00:00:00Z", "2025-01-03T00:00:00Z"], utc=True
            ),
            "value": [1, 2],
        }
    )
    result = TradewindsResult(
        frame=df,
        source="iem.live",
        retrieved_at=datetime(2025, 1, 4, tzinfo=UTC),
    )
    view = KnowledgeView(result, TimePoint("2025-01-02T00:00:00Z"))
    out = view.dataframe()
    assert len(out) == 1
    assert int(out.iloc[0]["value"]) == 1


# ----------------------- assert_no_leakage unwrap dispatch -----------------------


def test_assert_no_leakage_accepts_tradewinds_result() -> None:
    df = pd.DataFrame(
        {
            "knowledge_time": pd.to_datetime(["2025-01-03T00:00:00Z"], utc=True),
            "value": [99],
        }
    )
    result = TradewindsResult(
        frame=df,
        source="iem.live",
        retrieved_at=datetime(2025, 1, 4, tzinfo=UTC),
    )
    with pytest.raises(LeakageError):
        assert_no_leakage(result, TimePoint("2025-01-02T00:00:00Z"))


def test_leakage_detector_check_accepts_tradewinds_result() -> None:
    df = pd.DataFrame(
        {
            "knowledge_time": pd.to_datetime(["2025-01-01T00:00:00Z"], utc=True),
            "value": [42],
        }
    )
    result = TradewindsResult(
        frame=df,
        source="iem.live",
        retrieved_at=datetime(2025, 1, 4, tzinfo=UTC),
    )
    detector = LeakageDetector(TimePoint("2025-01-02T00:00:00Z"))
    # No leak: must not raise.
    detector.check(result)

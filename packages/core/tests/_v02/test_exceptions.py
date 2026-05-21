"""Unit tests for the structured exception hierarchy."""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest
from tradewinds._v02.exceptions import (
    LeakageError,
    MostlyRightMCPError,
    PayloadTooLargeError,
    SchemaValidationError,
    SourceMismatchError,
    SourceUnavailableError,
    TemporalDriftError,
)


def _roundtrip(payload: dict) -> dict:
    """Assert the payload survives json.dumps -> json.loads and return the result."""
    text = json.dumps(payload)
    return json.loads(text)


# ---------------------------------------------------------------------------
# Base
# ---------------------------------------------------------------------------
class TestMostlyRightMCPError:
    def test_defaults(self):
        err = MostlyRightMCPError("boom")
        assert str(err) == "boom"
        assert err.message == "boom"
        assert err.error_code == "MOSTLYRIGHT_MCP_ERROR"
        assert err.source is None
        assert err.request_id is None

    def test_all_kwargs(self):
        err = MostlyRightMCPError(
            "boom",
            error_code="CUSTOM_CODE",
            source="iem.archive",
            request_id="req-123",
        )
        assert err.error_code == "CUSTOM_CODE"
        assert err.source == "iem.archive"
        assert err.request_id == "req-123"

    def test_to_dict_roundtrip(self):
        err = MostlyRightMCPError("boom", source="iem.archive", request_id="r1")
        payload = err.to_dict()
        rt = _roundtrip(payload)
        assert rt["error_code"] == "MOSTLYRIGHT_MCP_ERROR"
        assert rt["message"] == "boom"
        assert rt["source"] == "iem.archive"
        assert rt["request_id"] == "r1"

    def test_is_exception(self):
        with pytest.raises(MostlyRightMCPError):
            raise MostlyRightMCPError("boom")


# ---------------------------------------------------------------------------
# SourceUnavailableError
# ---------------------------------------------------------------------------
class TestSourceUnavailableError:
    def test_all_attributes(self):
        err = SourceUnavailableError(
            "503 from IEM",
            source="iem.archive",
            http_status=503,
            retryable=True,
            retry_after_s=12.5,
            underlying="HTTPError(503)",
            url="https://example.test/path",
            request_id="r-9",
        )
        assert err.error_code == "SOURCE_UNAVAILABLE"
        assert err.source == "iem.archive"
        assert err.http_status == 503
        assert err.retryable is True
        assert err.retry_after_s == 12.5
        assert err.underlying == "HTTPError(503)"
        assert err.url == "https://example.test/path"
        assert err.request_id == "r-9"

    def test_to_dict_roundtrip(self):
        err = SourceUnavailableError(
            "503",
            source="iem.archive",
            http_status=503,
            retryable=True,
            retry_after_s=12.5,
            underlying="HTTPError(503)",
            url="https://example.test/path",
        )
        rt = _roundtrip(err.to_dict())
        assert rt["error_code"] == "SOURCE_UNAVAILABLE"
        assert rt["http_status"] == 503
        assert rt["retryable"] is True
        assert rt["retry_after_s"] == 12.5
        assert rt["underlying"] == "HTTPError(503)"
        assert rt["url"] == "https://example.test/path"

    def test_defaults_optional_fields(self):
        err = SourceUnavailableError("nope")
        d = err.to_dict()
        assert d["retryable"] is False
        assert d["http_status"] is None
        assert d["retry_after_s"] is None
        assert d["underlying"] == ""
        assert d["url"] is None
        # And serializable.
        _roundtrip(d)


# ---------------------------------------------------------------------------
# SchemaValidationError
# ---------------------------------------------------------------------------
class TestSchemaValidationError:
    def test_all_attributes(self):
        violations = [
            {"row_idx": 0, "column": "temp_c", "expected": "float", "actual": "str",
             "rule": "dtype"},
            {"row_idx": 1, "column": "event_time", "expected": "tz=UTC",
             "actual": "naive", "rule": "tz"},
        ]
        sample = violations[:1]
        err = SchemaValidationError(
            "validation failed",
            schema_id="schema.observation.v1",
            violations=violations,
            quarantine_count=3,
            sample_violations=sample,
            source="iem.archive",
        )
        assert err.error_code == "SCHEMA_VALIDATION_FAILED"
        assert err.schema_id == "schema.observation.v1"
        assert err.violations == violations
        assert err.quarantine_count == 3
        assert err.sample_violations == sample

    def test_defaults(self):
        err = SchemaValidationError("bad", schema_id="s")
        assert err.violations == []
        assert err.sample_violations == []
        assert err.quarantine_count == 0

    def test_to_dict_with_pandas_types(self):
        """Violations containing pd.Timestamp + NaN must serialize JSON-safely."""
        ts = pd.Timestamp("2026-05-21T12:00:00", tz="UTC")
        violations = [
            {
                "row_idx": np.int64(7),
                "column": "event_time",
                "expected": ts,
                "actual": float("nan"),
                "rule": "non_null",
                "extra": {"nested_ts": ts, "nested_na": pd.NaT},
            }
        ]
        err = SchemaValidationError(
            "bad",
            schema_id="schema.observation.v1",
            violations=violations,
            sample_violations=violations,
        )
        d = err.to_dict()
        rt = _roundtrip(d)
        # Pandas Timestamp -> ISO string
        assert rt["violations"][0]["expected"].startswith("2026-05-21T12:00:00")
        # NaN -> null
        assert rt["violations"][0]["actual"] is None
        # numpy int -> python int
        assert rt["violations"][0]["row_idx"] == 7
        # Nested NaT -> null
        assert rt["violations"][0]["extra"]["nested_na"] is None
        # Sample preserved similarly.
        assert rt["sample_violations"][0]["actual"] is None


# ---------------------------------------------------------------------------
# SourceMismatchError
# ---------------------------------------------------------------------------
class TestSourceMismatchError:
    def test_all_attributes(self):
        err = SourceMismatchError(
            "source drift detected",
            schema_source="iem.archive",
            data_source="awc.live",
            role="observations",
            catalog_warning="known_bad: iem.archive vs awc.live",
        )
        assert err.error_code == "SOURCE_MISMATCH"
        assert err.schema_source == "iem.archive"
        assert err.data_source == "awc.live"
        assert err.role == "observations"
        assert err.catalog_warning == "known_bad: iem.archive vs awc.live"

    def test_to_dict_roundtrip(self):
        err = SourceMismatchError(
            "mismatch",
            schema_source="iem.archive",
            data_source="awc.live",
            role="forecasts",
        )
        rt = _roundtrip(err.to_dict())
        assert rt["schema_source"] == "iem.archive"
        assert rt["data_source"] == "awc.live"
        assert rt["role"] == "forecasts"
        assert rt["catalog_warning"] is None

    def test_valid_roles_are_long_form(self):
        # Sanity guard for design.md §R role-name vocabulary.
        assert {
            "observations",
            "forecasts",
            "settlement",
        } == SourceMismatchError.VALID_ROLES


# ---------------------------------------------------------------------------
# LeakageError
# ---------------------------------------------------------------------------
class TestLeakageError:
    def test_all_attributes(self):
        sample = [{"row_idx": 0, "knowledge_time": "2026-05-22T01:00:00+00:00"}]
        err = LeakageError(
            "leakage detected",
            as_of="2026-05-21T00:00:00+00:00",
            violating_count=7,
            sample_violations=sample,
            source="iem.archive",
        )
        assert err.error_code == "LEAKAGE_DETECTED"
        assert err.as_of == "2026-05-21T00:00:00+00:00"
        assert err.violating_count == 7
        assert err.sample_violations == sample

    def test_to_dict_roundtrip(self):
        ts = pd.Timestamp("2026-05-22T01:00:00", tz="UTC")
        err = LeakageError(
            "leakage",
            as_of="2026-05-21T00:00:00+00:00",
            violating_count=2,
            sample_violations=[{"row_idx": 1, "knowledge_time": ts}],
        )
        rt = _roundtrip(err.to_dict())
        assert rt["as_of"] == "2026-05-21T00:00:00+00:00"
        assert rt["violating_count"] == 2
        assert rt["sample_violations"][0]["knowledge_time"].startswith(
            "2026-05-22T01:00:00"
        )

    def test_defaults(self):
        err = LeakageError("l", as_of="2026-01-01T00:00:00+00:00", violating_count=0)
        assert err.sample_violations == []


# ---------------------------------------------------------------------------
# TemporalDriftError
# ---------------------------------------------------------------------------
class TestTemporalDriftError:
    def test_all_attributes(self):
        err = TemporalDriftError(
            "drift",
            schema_id="schema.observation.v1",
            asserted_range=("2026-04-01T00:00:00+00:00", "2026-04-30T23:59:59+00:00"),
            violating_rows=12,
            sample_violations=[{"row_idx": 5, "retrieved_at": "2026-05-22T00:00:00+00:00"}],
        )
        assert err.error_code == "TEMPORAL_DRIFT"
        assert err.schema_id == "schema.observation.v1"
        assert err.asserted_range == (
            "2026-04-01T00:00:00+00:00",
            "2026-04-30T23:59:59+00:00",
        )
        assert err.violating_rows == 12
        assert len(err.sample_violations) == 1

    def test_to_dict_roundtrip(self):
        err = TemporalDriftError(
            "drift",
            schema_id="s",
            asserted_range=("a", "b"),
            violating_rows=3,
        )
        rt = _roundtrip(err.to_dict())
        # asserted_range serializes as a list (JSON has no tuple).
        assert rt["asserted_range"] == ["a", "b"]
        assert rt["violating_rows"] == 3
        assert rt["sample_violations"] == []


# ---------------------------------------------------------------------------
# PayloadTooLargeError
# ---------------------------------------------------------------------------
class TestPayloadTooLargeError:
    def test_all_attributes(self):
        err = PayloadTooLargeError(
            "payload too large",
            declared_size=60 * 1024 * 1024,
            limit=50 * 1024 * 1024,
            accepted_modes=["file-path"],
        )
        assert err.error_code == "PAYLOAD_TOO_LARGE"
        assert err.declared_size == 60 * 1024 * 1024
        assert err.limit == 50 * 1024 * 1024
        assert err.accepted_modes == ["file-path"]

    def test_to_dict_roundtrip(self):
        err = PayloadTooLargeError(
            "too big",
            declared_size=1_000_000,
            limit=500_000,
            accepted_modes=["file-path"],
        )
        rt = _roundtrip(err.to_dict())
        assert rt["declared_size"] == 1_000_000
        assert rt["limit"] == 500_000
        assert rt["accepted_modes"] == ["file-path"]

    def test_defaults(self):
        err = PayloadTooLargeError("x", declared_size=1, limit=2)
        assert err.accepted_modes == []


# ---------------------------------------------------------------------------
# Hierarchy
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "cls,kwargs",
    [
        (SourceUnavailableError, {}),
        (SchemaValidationError, {"schema_id": "s"}),
        (SourceMismatchError, {"schema_source": "a", "data_source": "b"}),
        (LeakageError, {"as_of": "t", "violating_count": 0}),
        (
            TemporalDriftError,
            {"schema_id": "s", "asserted_range": ("a", "b"), "violating_rows": 0},
        ),
        (PayloadTooLargeError, {"declared_size": 1, "limit": 2}),
    ],
)
def test_all_subclass_base(cls, kwargs):
    err = cls("msg", **kwargs)
    assert isinstance(err, MostlyRightMCPError)
    assert isinstance(err, Exception)
    # And every to_dict survives a json round-trip.
    _roundtrip(err.to_dict())

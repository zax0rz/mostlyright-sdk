"""Phase 21 21-09: DataAvailabilityError typed exception.

Tests follow the existing exception pattern in mostlyright.core.exceptions:
``to_dict()`` returns a JSON-safe payload keyed on ``error_code`` /
``message`` / ``source`` / per-subclass fields. The ``reason`` enum is
shared lockstep with the TypeScript SDK — drift would invalidate every
cross-SDK ``except DataAvailabilityError as e: if e.reason == ...`` branch.
"""

from __future__ import annotations

import json

import pytest
from mostlyright.core import exceptions as exc_mod
from mostlyright.core.exceptions import (
    DATA_AVAILABILITY_REASONS,
    DataAvailabilityError,
    MostlyRightError,
)


def test_data_availability_error_constructs_with_all_fields() -> None:
    exc = DataAvailabilityError(
        reason="out_of_window",
        hint="AWC only serves last 168h",
        source="awc",
    )
    assert exc.reason == "out_of_window"
    assert exc.hint == "AWC only serves last 168h"
    assert exc.source == "awc"


def test_data_availability_error_to_dict_payload() -> None:
    exc = DataAvailabilityError(
        reason="model_unavailable",
        hint="hosted ingest API ships in v0.2.x",
        source="nwp-stub",
    )
    d = exc.to_dict()
    assert d["error_code"] == "DATA_AVAILABILITY"
    assert d["reason"] == "model_unavailable"
    assert d["hint"] == "hosted ingest API ships in v0.2.x"
    assert d["source"] == "nwp-stub"
    # Default message derives from reason + hint when not explicitly passed.
    assert d["message"] == "[model_unavailable] hosted ingest API ships in v0.2.x"
    # JSON round-trip safe.
    assert json.loads(json.dumps(d))["reason"] == "model_unavailable"


def test_data_availability_error_is_tradewinds_subclass() -> None:
    """Back-compat: code that catches MostlyRightError catches this too."""
    exc = DataAvailabilityError(reason="rate_limited", hint="back off")
    assert isinstance(exc, MostlyRightError)
    assert isinstance(exc, Exception)


def test_data_availability_error_rejects_unknown_reason() -> None:
    with pytest.raises(ValueError, match="unknown reason"):
        DataAvailabilityError(reason="totally_made_up", hint="x")


def test_data_availability_error_defaults_source_to_none() -> None:
    exc = DataAvailabilityError(reason="cache_miss", hint="no cached value")
    assert exc.source is None
    # Empty hint rejected.
    with pytest.raises(TypeError, match="hint is required"):
        DataAvailabilityError(reason="cache_miss", hint="")


def test_data_availability_error_exported_in_all() -> None:
    assert "DataAvailabilityError" in exc_mod.__all__
    assert "DATA_AVAILABILITY_REASONS" in exc_mod.__all__
    # Reason enum matches TS lockstep — drift here invalidates cross-SDK branches.
    assert DATA_AVAILABILITY_REASONS == (
        "model_unavailable",
        "out_of_window",
        "cache_miss",
        "source_404",
        "source_5xx",
        "rate_limited",
    )

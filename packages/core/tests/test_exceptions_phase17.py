"""Phase 17 FORECAST-07: HistoricalDepthError + DeprecatedModelWarning.

Tests follow the existing exception pattern in mostlyright.core.exceptions:
``to_dict()`` returns a JSON-safe payload keyed on ``error_code`` /
``message`` / ``source`` / per-subclass fields. Datetime fields are
ISO-formatted strings to survive ``json.dumps`` without further coercion.
"""

from __future__ import annotations

import json
import warnings
from datetime import UTC, datetime

import pytest
from mostlyright.core.exceptions import (
    DeprecatedModelWarning,
    HistoricalDepthError,
    MostlyRightError,
    NwpError,
)


def test_historical_depth_error_is_nwp_error_subclass() -> None:
    exc = HistoricalDepthError(
        "hrrr: cycle 2010-01-01 older than archive depth 2014-07-30",
        model="hrrr",
        requested_cycle=datetime(2010, 1, 1, tzinfo=UTC),
        archive_depth=datetime(2014, 7, 30, tzinfo=UTC),
    )
    assert isinstance(exc, NwpError)
    assert isinstance(exc, MostlyRightError)
    assert exc.model == "hrrr"
    assert exc.requested_cycle == datetime(2010, 1, 1, tzinfo=UTC)
    assert exc.archive_depth == datetime(2014, 7, 30, tzinfo=UTC)


def test_historical_depth_error_to_dict_populated() -> None:
    exc = HistoricalDepthError(
        "msg",
        model="gfs",
        requested_cycle=datetime(2019, 1, 1, tzinfo=UTC),
        archive_depth=datetime(2021, 1, 1, tzinfo=UTC),
    )
    d = exc.to_dict()
    assert d["error_code"] == "NWP_HISTORICAL_DEPTH"
    assert d["message"] == "msg"
    assert d["source"] == "nwp.gfs"
    assert d["model"] == "gfs"
    assert d["requested_cycle"] == "2019-01-01T00:00:00+00:00"
    assert d["archive_depth"] == "2021-01-01T00:00:00+00:00"
    # Survives json round-trip.
    assert json.loads(json.dumps(d))["model"] == "gfs"


def test_historical_depth_error_msc_live_only_archive_none() -> None:
    exc = HistoricalDepthError(
        "hrdps: MSC Datamart 24h retention",
        model="hrdps",
        requested_cycle=datetime(2026, 1, 1, tzinfo=UTC),
        archive_depth=None,
    )
    d = exc.to_dict()
    assert d["archive_depth"] is None
    assert d["model"] == "hrdps"
    assert d["source"] == "nwp.hrdps"


def test_deprecated_model_warning_is_deprecation_warning() -> None:
    assert issubclass(DeprecatedModelWarning, DeprecationWarning)


def test_deprecated_model_warning_filterable_as_error() -> None:
    with warnings.catch_warnings():
        warnings.filterwarnings("error", category=DeprecatedModelWarning)
        with pytest.raises(DeprecatedModelWarning, match="NAM retires"):
            warnings.warn(
                "NAM retires 2026-08-31; use HRRR/RAP/RRFS",
                category=DeprecatedModelWarning,
                stacklevel=2,
            )

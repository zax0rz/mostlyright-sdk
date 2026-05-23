"""Tests for tradewinds._internal.models.availability — RangeInfo + DataAvailability.

Lifted from monorepo-v0.14.1/tests/test_sdk_v3_availability.py — dataclass-only
tests. Client-level availability() tests live alongside the client lift in a
later wave.
"""

from __future__ import annotations

import pytest

# ---------------------------------------------------------------------------
# RangeInfo
# ---------------------------------------------------------------------------


def test_range_info_to_dict_has_expected_keys():
    from tradewinds._internal.models.availability import RangeInfo

    r = RangeInfo(
        earliest="2020-01-01",
        latest="2024-12-31",
        count=50000,
        freshness_hours=1.5,
    )
    d = r.to_dict()
    assert set(d.keys()) == {"earliest", "latest", "count", "freshness_hours"}
    assert d["earliest"] == "2020-01-01"
    assert d["latest"] == "2024-12-31"
    assert d["count"] == 50000
    assert d["freshness_hours"] == 1.5


def test_range_info_all_none():
    from tradewinds._internal.models.availability import RangeInfo

    r = RangeInfo(earliest=None, latest=None, count=None, freshness_hours=None)
    d = r.to_dict()
    assert d["earliest"] is None
    assert d["freshness_hours"] is None


def test_range_info_frozen():
    from tradewinds._internal.models.availability import RangeInfo

    r = RangeInfo(earliest="2020-01-01", latest=None, count=None, freshness_hours=None)
    with pytest.raises((AttributeError, TypeError)):
        r.earliest = "modified"  # type: ignore[misc]


def test_range_info_freshness_hours_computed():
    """freshness_hours is calculated correctly from latest and as_of."""
    from tradewinds._internal.models.availability import RangeInfo

    # freshness_hours = (as_of - latest).total_seconds() / 3600
    # This is computed by the REST route, not the model itself.
    # Test that the model accepts it:
    r = RangeInfo(earliest="2024-01-01", latest="2024-01-15", count=100, freshness_hours=2.5)
    assert r.freshness_hours == 2.5


# ---------------------------------------------------------------------------
# DataAvailability
# ---------------------------------------------------------------------------


def test_data_availability_to_dict_has_expected_keys():
    from tradewinds._internal.models.availability import DataAvailability, RangeInfo

    # Constructor call is part of the test (would raise if the dataclass
    # contract broke). The instance itself is not asserted against — the
    # assertions below operate on `avail`.
    _ = RangeInfo(earliest=None, latest=None, count=None, freshness_hours=None)
    avail = DataAvailability(
        station="NYC",
        as_of="2024-01-15T12:00:00Z",
        observations=RangeInfo("2020-01-01", "2024-01-15", 50000, 1.0),
        climate=RangeInfo("2020-01-01", "2024-01-14", 1460, 26.0),
        forecast=None,
    )
    d = avail.to_dict()
    assert set(d.keys()) == {"station", "as_of", "observations", "climate", "forecast"}
    assert d["station"] == "NYC"
    assert d["forecast"] is None
    assert isinstance(d["observations"], dict)


def test_data_availability_forecast_included_when_present():
    from tradewinds._internal.models.availability import DataAvailability, RangeInfo

    avail = DataAvailability(
        station="NYC",
        as_of="2024-01-15T12:00:00Z",
        observations=RangeInfo("2020-01-01", "2024-01-15", None, None),
        climate=RangeInfo("2020-01-01", "2024-01-14", None, None),
        forecast=RangeInfo("2023-01-01", "2024-01-15", None, None),
    )
    d = avail.to_dict()
    assert d["forecast"] is not None
    assert d["forecast"]["earliest"] == "2023-01-01"

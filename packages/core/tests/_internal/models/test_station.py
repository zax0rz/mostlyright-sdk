"""Tests for mostlyright._internal.models.station — StationInfo + helpers.

Lifted from monorepo-v0.14.1/tests/test_sdk_stations.py. Tests that depend on
the ``_stations`` module (registry tests, _STATION_REGISTRY contents) are
gated behind skipif until a later wave lifts ``mostlyright._internal._stations``.
"""

from __future__ import annotations

import importlib.util

import pytest


def _has_stations_module() -> bool:
    try:
        return importlib.util.find_spec("mostlyright._internal._stations") is not None
    except ModuleNotFoundError:
        return False


_HAS_STATIONS = _has_stations_module()


# ---------------------------------------------------------------------------
# _utc_offset_hours — no registry dependency
# ---------------------------------------------------------------------------


def test_utc_offset_eastern_standard():
    from mostlyright._internal.models.station import _utc_offset_hours

    assert _utc_offset_hours("America/New_York") == -5


def test_utc_offset_central_standard():
    from mostlyright._internal.models.station import _utc_offset_hours

    assert _utc_offset_hours("America/Chicago") == -6


def test_utc_offset_mountain_standard():
    from mostlyright._internal.models.station import _utc_offset_hours

    assert _utc_offset_hours("America/Denver") == -7


def test_utc_offset_pacific_standard():
    from mostlyright._internal.models.station import _utc_offset_hours

    assert _utc_offset_hours("America/Los_Angeles") == -8


def test_utc_offset_arizona_no_dst():
    from mostlyright._internal.models.station import _utc_offset_hours

    # Arizona stays on UTC-7 year-round (same as Mountain Standard)
    assert _utc_offset_hours("America/Phoenix") == -7


def test_utc_offset_hawaii_no_dst():
    from mostlyright._internal.models.station import _utc_offset_hours

    assert _utc_offset_hours("Pacific/Honolulu") == -10


# ---------------------------------------------------------------------------
# StationInfo dataclass — no registry dependency
# ---------------------------------------------------------------------------


def test_station_info_dataclass_frozen():
    from mostlyright._internal.models.station import StationInfo

    s = StationInfo(
        code="NYC",
        name="Central Park, New York",
        icao="KNYC",
        timezone="America/New_York",
        utc_offset_standard=-5,
        latitude=40.7789,
        longitude=-73.9692,
        kalshi_traded=True,
    )
    with pytest.raises((AttributeError, TypeError)):
        s.code = "MODIFIED"  # type: ignore[misc]


def test_station_info_to_dict_has_expected_keys():
    from mostlyright._internal.models.station import StationInfo

    s = StationInfo(
        code="NYC",
        name="Central Park, New York",
        icao="KNYC",
        timezone="America/New_York",
        utc_offset_standard=-5,
        latitude=40.7789,
        longitude=-73.9692,
        kalshi_traded=True,
    )
    d = s.to_dict()
    assert set(d.keys()) == {
        "code",
        "name",
        "icao",
        "timezone",
        "utc_offset_standard",
        "latitude",
        "longitude",
        "kalshi_traded",
    }


def test_station_info_kalshi_traded_default_true():
    from mostlyright._internal.models.station import StationInfo

    s = StationInfo(
        code="NYC",
        name="Central Park, New York",
        icao="KNYC",
        timezone="America/New_York",
        utc_offset_standard=-5,
        latitude=40.7789,
        longitude=-73.9692,
    )
    assert s.kalshi_traded is True


# ---------------------------------------------------------------------------
# Registry — requires mostlyright._internal._stations (later wave)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    not _HAS_STATIONS,
    reason="mostlyright._internal._stations not yet lifted; registry empty.",
)
class TestStationRegistry:
    """Registry tests — gated until ``_stations`` lifts."""

    def test_registry_is_nonempty(self):
        from mostlyright._internal.models.station import _STATION_REGISTRY

        assert len(_STATION_REGISTRY) > 0

    def test_station_nyc_metadata(self):
        from mostlyright._internal.models.station import _STATION_REGISTRY

        s = _STATION_REGISTRY["NYC"]
        assert s.code == "NYC"
        assert s.icao == "KNYC"
        assert s.timezone == "America/New_York"
        assert s.utc_offset_standard == -5
        assert s.latitude == pytest.approx(40.7789, abs=0.01)
        assert s.longitude < 0  # west
        assert s.kalshi_traded is True

    def test_station_phx_utc_offset_minus7_no_dst(self):
        from mostlyright._internal.models.station import _STATION_REGISTRY

        # PHX is in Phoenix, Arizona — America/Phoenix — UTC-7, no DST
        s = _STATION_REGISTRY["PHX"]
        assert s.utc_offset_standard == -7
        assert s.timezone == "America/Phoenix"

    def test_station_den_utc_offset_minus7(self):
        from mostlyright._internal.models.station import _STATION_REGISTRY

        # Denver is Mountain Standard (UTC-7)
        s = _STATION_REGISTRY["DEN"]
        assert s.utc_offset_standard == -7
        assert s.timezone == "America/Denver"

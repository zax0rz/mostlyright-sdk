# Lifted from monorepo-v0.14.1/tests/test_sdk_stations.py (registry-specific subset)
# Source SHA: 514fcdab227e845145ca32b989355647466231d9
# Lift date: 2026-05-22
# Modifications:
#   - import-rename: mostlyright._stations -> tradewinds._internal._stations
#   - subset to tests that exercise STATIONS dict + StationInfo dataclass only
#     (client/capabilities/schema tests deferred to later waves)
"""Tests for tradewinds._internal._stations — STATIONS registry + StationInfo.

Exercises the lifted ingest/SDK station registry (the 20 Kalshi-traded
stations). Distinct from packages/core/tests/_internal/models/test_station.py,
which exercises the public ``StationInfo`` SDK model.
"""

from __future__ import annotations

import pytest
from tradewinds._internal._stations import STATIONS, StationInfo

# ---------------------------------------------------------------------------
# StationInfo dataclass
# ---------------------------------------------------------------------------


def test_station_info_dataclass_frozen() -> None:
    s = STATIONS["NYC"]
    with pytest.raises((AttributeError, TypeError)):
        s.code = "MODIFIED"  # type: ignore[misc]


def test_station_info_fields() -> None:
    s = StationInfo(
        code="NYC",
        ghcnh_id="USW00094728",
        icao="KNYC",
        name="Central Park, New York",
        tz="America/New_York",
        latitude=40.7789,
        longitude=-73.9692,
    )
    assert s.code == "NYC"
    assert s.ghcnh_id == "USW00094728"
    assert s.icao == "KNYC"
    assert s.tz == "America/New_York"


# ---------------------------------------------------------------------------
# STATIONS registry contents
# ---------------------------------------------------------------------------


def test_stations_registry_is_nonempty() -> None:
    assert len(STATIONS) > 0


def test_stations_registry_has_20_entries() -> None:
    # The v0.14.1 ingest registry hosts the 20 Kalshi-traded stations.
    assert len(STATIONS) == 20


def test_stations_nyc_metadata() -> None:
    s = STATIONS["NYC"]
    assert s.code == "NYC"
    assert s.icao == "KNYC"
    assert s.tz == "America/New_York"
    assert s.ghcnh_id == "USW00094728"
    assert s.latitude == pytest.approx(40.7789, abs=0.01)
    assert s.longitude < 0  # west


def test_stations_atl_metadata() -> None:
    s = STATIONS["ATL"]
    assert s.code == "ATL"
    assert s.icao == "KATL"
    assert s.tz == "America/New_York"
    assert s.ghcnh_id == "USW00013874"


def test_stations_lax_pacific_tz() -> None:
    s = STATIONS["LAX"]
    assert s.icao == "KLAX"
    assert s.tz == "America/Los_Angeles"


def test_stations_phx_arizona_no_dst_tz() -> None:
    # PHX is in Phoenix, Arizona — America/Phoenix — UTC-7, no DST
    s = STATIONS["PHX"]
    assert s.tz == "America/Phoenix"
    assert s.icao == "KPHX"


def test_stations_den_mountain_tz() -> None:
    s = STATIONS["DEN"]
    assert s.tz == "America/Denver"
    assert s.icao == "KDEN"


def test_stations_dfw_central_tz() -> None:
    s = STATIONS["DFW"]
    assert s.tz == "America/Chicago"
    assert s.icao == "KDFW"


def test_stations_msy_central_tz() -> None:
    # New Orleans (KMSY) — used in the case-5 KMSY parity fixture.
    s = STATIONS["MSY"]
    assert s.code == "MSY"
    assert s.icao == "KMSY"
    assert s.tz == "America/Chicago"


def test_stations_all_icaos_start_with_k() -> None:
    for code, s in STATIONS.items():
        assert s.icao.startswith("K"), f"{code} icao={s.icao!r} should start with 'K'"


def test_stations_all_codes_match_key() -> None:
    for code, s in STATIONS.items():
        assert s.code == code


def test_stations_all_longitudes_negative() -> None:
    # All 20 stations are in the contiguous US + west — all longitudes < 0.
    for code, s in STATIONS.items():
        assert s.longitude < 0, f"{code} longitude={s.longitude} should be west"


def test_stations_all_ghcnh_ids_start_with_usw() -> None:
    # Every Kalshi-traded station is a US first-order station (GHCN-h USW prefix).
    for code, s in STATIONS.items():
        assert s.ghcnh_id.startswith("USW"), (
            f"{code} ghcnh_id={s.ghcnh_id!r} should start with 'USW'"
        )

# Lifted from monorepo-v0.14.1/tests/test_sdk_stations.py (registry-specific subset)
# Source SHA: 514fcdab227e845145ca32b989355647466231d9
# Lift date: 2026-05-22
# Modifications:
#   - import-rename: mostlyright._stations -> mostlyright._internal._stations
#   - subset to tests that exercise STATIONS dict + StationInfo dataclass only
#     (client/capabilities/schema tests deferred to later waves)
"""Tests for mostlyright._internal._stations — STATIONS registry + StationInfo.

Exercises the lifted ingest/SDK station registry (the 20 Kalshi-traded
stations). Distinct from packages/core/tests/_internal/models/test_station.py,
which exercises the public ``StationInfo`` SDK model.
"""

from __future__ import annotations

import pytest
from mostlyright._internal._stations import STATIONS, StationInfo, is_us_station

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


def test_stations_registry_has_66_entries() -> None:
    # Phase 3.1 expanded the v0.14.1 20-US registry to cover Polymarket intl
    # markets; Phase 22 added the 5 missing Kalshi settlement stations → 66
    # (25 US + 41 intl).
    assert len(STATIONS) == 66
    us = [s for s in STATIONS.values() if s.country == "US"]
    intl = [s for s in STATIONS.values() if s.country != "US"]
    assert len(us) == 25
    assert len(intl) == 41


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


def test_stations_us_icaos_start_with_k() -> None:
    # The original v0.14.1 invariant applies to the 20 US stations only;
    # Phase 3.1 added 40 intl stations whose ICAOs start with EG/LF/RJ/...
    for code, s in STATIONS.items():
        if s.country != "US":
            continue
        assert s.icao.startswith("K"), f"{code} icao={s.icao!r} should start with 'K'"


def test_stations_all_codes_match_key() -> None:
    for code, s in STATIONS.items():
        assert s.code == code


def test_stations_us_longitudes_negative() -> None:
    # All 20 US stations are in the contiguous US + west — all longitudes < 0.
    # Intl stations span the globe (e.g. EGLL ~0, RJTT +139) so this invariant
    # is US-only.
    for code, s in STATIONS.items():
        if s.country != "US":
            continue
        assert s.longitude < 0, f"{code} longitude={s.longitude} should be west"


def test_stations_us_ghcnh_ids_start_with_usw() -> None:
    # Every Kalshi-traded US station is a US first-order station (GHCN-h USW prefix).
    # Intl stations carry ``ghcnh_id=""`` (NCEI is US-only).
    for code, s in STATIONS.items():
        if s.country != "US":
            continue
        assert s.ghcnh_id.startswith("USW"), (
            f"{code} ghcnh_id={s.ghcnh_id!r} should start with 'USW'"
        )


# ---------------------------------------------------------------------------
# Phase 3.1 — International station registry
# ---------------------------------------------------------------------------


def test_international_stations_have_tz() -> None:
    """Every non-US station has a non-empty IANA timezone."""
    intl = [s for s in STATIONS.values() if s.country != "US"]
    assert len(intl) >= 40
    for s in intl:
        assert s.tz, f"{s.icao}: missing tz"
        # IANA names always contain a "/" (region/city).
        assert "/" in s.tz, f"{s.icao}: tz {s.tz!r} not in IANA Region/City form"


def test_international_stations_have_empty_ghcnh_id() -> None:
    """NCEI GHCNh is US-only — intl entries must carry ``ghcnh_id=''``."""
    for s in STATIONS.values():
        if s.country == "US":
            continue
        assert s.ghcnh_id == "", (
            f"{s.icao}: intl station must have empty ghcnh_id, got {s.ghcnh_id!r}"
        )


def test_paris_has_lfpg_and_lfpb() -> None:
    """Paris ships both CDG (LFPG) and Le Bourget (LFPB) for the per-event split."""
    assert "LFPG" in STATIONS
    assert "LFPB" in STATIONS
    assert STATIONS["LFPG"].tz == "Europe/Paris"
    assert STATIONS["LFPB"].tz == "Europe/Paris"
    assert STATIONS["LFPG"].country == "FR"


def test_tokyo_haneda_tz() -> None:
    s = STATIONS["RJTT"]
    assert s.icao == "RJTT"
    assert s.tz == "Asia/Tokyo"
    assert s.country == "JP"


def test_intl_lats_within_bounds() -> None:
    """Every intl station's latitude is in the physically valid range."""
    for s in STATIONS.values():
        if s.country == "US":
            continue
        assert -90.0 <= s.latitude <= 90.0, f"{s.icao}: lat={s.latitude} out of range"
        assert -180.0 <= s.longitude <= 180.0, f"{s.icao}: lon={s.longitude} out of range"


def test_is_us_station_true_for_us_icaos() -> None:
    assert is_us_station("KNYC") is True
    assert is_us_station("KATL") is True
    assert is_us_station("KSEA") is True


def test_is_us_station_false_for_intl_icaos() -> None:
    assert is_us_station("EGLL") is False
    assert is_us_station("LFPG") is False
    assert is_us_station("RJTT") is False


def test_is_us_station_false_for_unknown() -> None:
    """Defense in depth: an unknown K* ICAO must NOT be classified as US."""
    assert is_us_station("KZZZ") is False
    assert is_us_station("") is False
    # Non-K prefix that happens to be unknown.
    assert is_us_station("ZZZZ") is False

# Lifted from monorepo-v0.14.1/tests/test_sdk_snapshot.py
# Source SHA: 514fcdab227e845145ca32b989355647466231d9
# Lift date: 2026-05-22
# Modifications:
#   - import-rename: mostlyright.snapshot -> mostlyright.snapshot
#   - import-rename: mostlyright.models.observation -> mostlyright._internal.models.observation
#   - import-rename: mostlyright.versioning -> mostlyright._internal.versioning
#   - to_toon test runs unconditionally; mostlyright._internal._toon is in-tree
"""Tests for src/mostlyright/snapshot.py — DataSnapshot + settlement window logic.

TDD: Tests written FIRST. Implementation follows.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from mostlyright._internal.models.observation import Observation

from mostlyright._internal.versioning import DataVersion
from mostlyright.snapshot import (
    _lst_offset,
    _parse_as_of,
    _station_code_normalized,
    build_snapshot,
    cli_available_at,
    settlement_date_for,
    settlement_window_utc,
)

# ---------------------------------------------------------------------------
# Helper factories
# ---------------------------------------------------------------------------


def _obs(
    station: str = "NYC",
    observed_at: str = "2024-07-04T12:00:00Z",
    obs_type: str = "METAR",
    source: str = "awc",
    temp_f: float | None = 75.0,
    temp_c: float | None = 23.9,
) -> dict:
    """Minimal valid observation dict for Observation.from_dict()."""
    return {
        "station_code": station,
        "observed_at": observed_at,
        "observation_type": obs_type,
        "source": source,
        "temp_c": temp_c,
        "dewpoint_c": None,
        "temp_f": temp_f,
        "dewpoint_f": None,
        "wind_dir_degrees": None,
        "wind_speed_kt": None,
        "wind_gust_kt": None,
        "altimeter_inhg": None,
        "sea_level_pressure_mb": None,
        "sky_cover_1": None,
        "sky_base_1_ft": None,
        "sky_cover_2": None,
        "sky_base_2_ft": None,
        "sky_cover_3": None,
        "sky_base_3_ft": None,
        "sky_cover_4": None,
        "sky_base_4_ft": None,
        "visibility_miles": None,
        "weather_codes": None,
        "precip_1hr_inches": None,
        "peak_wind_gust_kt": None,
        "peak_wind_dir": None,
        "peak_wind_time": None,
        "snow_depth_inches": None,
        "qc_field": None,
        "raw_metar": None,
    }


def _make_obs(observed_at: str, station: str = "NYC") -> Observation:
    """Create an Observation from dict."""
    from mostlyright._internal.models.observation import Observation

    return Observation.from_dict(_obs(station=station, observed_at=observed_at))


def _climate(date: str = "2024-07-04", report_type: str = "final") -> dict:
    return {
        "station_code": "NYC",
        "observation_date": date,
        "high_temp_f": 85.0,
        "low_temp_f": 65.0,
        "report_type": report_type,
        "source": "iem",
        "product_id": None,
        "issued_at": None,
    }


# ---------------------------------------------------------------------------
# _station_code_normalized
# ---------------------------------------------------------------------------


class TestStationCodeNormalized:
    def test_three_letter(self) -> None:
        assert _station_code_normalized("nyc") == "NYC"

    def test_four_letter_k_prefix(self) -> None:
        assert _station_code_normalized("KNYC") == "NYC"

    def test_four_letter_no_k(self) -> None:
        assert _station_code_normalized("KATL") == "ATL"

    def test_lowercase_k_prefix(self) -> None:
        assert _station_code_normalized("katl") == "ATL"


# ---------------------------------------------------------------------------
# _lst_offset
# ---------------------------------------------------------------------------


class TestLstOffset:
    def test_eastern_standard(self) -> None:
        offset = _lst_offset("NYC")
        assert offset == timedelta(hours=-5)

    def test_central_standard(self) -> None:
        offset = _lst_offset("ORD")
        assert offset == timedelta(hours=-6)

    def test_mountain_standard(self) -> None:
        offset = _lst_offset("DEN")
        assert offset == timedelta(hours=-7)

    def test_pacific_standard(self) -> None:
        offset = _lst_offset("LAX")
        assert offset == timedelta(hours=-8)

    def test_tus_is_arizona_no_dst(self) -> None:
        # Tucson is in Arizona — America/Phoenix, UTC-7 always (no DST)
        offset = _lst_offset("TUS")
        assert offset == timedelta(hours=-7)

    def test_unknown_station_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="Unknown station timezone"):
            _lst_offset("ZZZ")

    def test_tz_override_for_unknown_station(self) -> None:
        offset = _lst_offset("ZZZ", tz_override="America/Chicago")
        assert offset == timedelta(hours=-6)

    def test_k_prefix_stripped(self) -> None:
        offset_bare = _lst_offset("NYC")
        offset_k = _lst_offset("KNYC")
        assert offset_bare == offset_k

    def test_southern_hemisphere_returns_standard_time_not_dst(self) -> None:
        """Sydney (YSSY) is on AEDT (+11) in January but AEST (+10) is the LST.

        Phase 3.1 caught: the original Jan-reference implementation returned the
        Jan offset directly, which for southern-hemisphere stations is their
        DST offset, not LST. Settlement-window math would be off by 1 hour.
        Fix: if Jan reports DST != 0, fall back to July (= their winter).
        """
        offset = _lst_offset("YSSY")
        assert offset == timedelta(hours=10), f"Sydney LST should be AEST UTC+10, got {offset}"

    def test_southern_hemisphere_buenos_aires_standard_time(self) -> None:
        # Buenos Aires is on America/Argentina/Buenos_Aires (UTC-3, no DST in
        # current era — Argentina dropped DST in 2009). January is fine here
        # because there's no DST shift; the fallback should still produce -3.
        offset = _lst_offset("SAEZ")
        assert offset == timedelta(hours=-3)

    def test_northern_hemisphere_intl_returns_january_offset(self) -> None:
        # London (EGLL) — GMT in January, BST (UTC+1) in July. LST = GMT (UTC+0).
        offset = _lst_offset("EGLL")
        assert offset == timedelta(hours=0)


# ---------------------------------------------------------------------------
# _parse_as_of
# ---------------------------------------------------------------------------


class TestParseAsOf:
    def test_z_suffix(self) -> None:
        dt = _parse_as_of("2024-07-04T12:00:00Z")
        assert dt.tzinfo is not None
        assert dt == datetime(2024, 7, 4, 12, 0, 0, tzinfo=UTC)

    def test_plus_offset(self) -> None:
        dt = _parse_as_of("2024-07-04T07:00:00-05:00")
        assert dt == datetime(2024, 7, 4, 12, 0, 0, tzinfo=UTC)

    def test_naive_datetime_assumed_utc(self) -> None:
        naive = datetime(2024, 7, 4, 12, 0, 0)
        dt = _parse_as_of(naive)
        assert dt.tzinfo == UTC

    def test_aware_datetime_converted_to_utc(self) -> None:
        eastern = datetime(2024, 7, 4, 7, 0, 0, tzinfo=timezone(timedelta(hours=-5)))
        dt = _parse_as_of(eastern)
        assert dt == datetime(2024, 7, 4, 12, 0, 0, tzinfo=UTC)


# ---------------------------------------------------------------------------
# settlement_date_for
# ---------------------------------------------------------------------------


class TestSettlementDateFor:
    def test_nyc_midnight_utc_is_prior_lst_day(self) -> None:
        # 2024-07-04 00:00 UTC = 2024-07-03 19:00 LST (UTC-5) → July 3
        result = settlement_date_for("2024-07-04T00:00:00Z", "NYC")
        assert result == "2024-07-03"

    def test_nyc_after_midnight_lst_next_day(self) -> None:
        # 2024-07-04 05:00 UTC = 2024-07-04 00:00 LST (UTC-5) → July 4
        result = settlement_date_for("2024-07-04T05:00:00Z", "NYC")
        assert result == "2024-07-04"

    def test_nyc_dst_summer_still_uses_lst(self) -> None:
        # During EDT (UTC-4), but LST is UTC-5
        # 2024-07-04 04:59 UTC = 2024-07-03 23:59 LST → July 3
        result = settlement_date_for("2024-07-04T04:59:59Z", "NYC")
        assert result == "2024-07-03"

    def test_chicago_uses_central_standard_offset(self) -> None:
        # 2024-07-04 06:00 UTC = 2024-07-04 00:00 CST (UTC-6)
        result = settlement_date_for("2024-07-04T06:00:00Z", "ORD")
        assert result == "2024-07-04"

    def test_los_angeles_uses_pacific_offset(self) -> None:
        # 2024-07-04 08:00 UTC = 2024-07-04 00:00 PST (UTC-8)
        result = settlement_date_for("2024-07-04T08:00:00Z", "LAX")
        assert result == "2024-07-04"

    def test_k_prefix_station(self) -> None:
        result = settlement_date_for("2024-07-04T05:00:00Z", "KNYC")
        assert result == "2024-07-04"


# ---------------------------------------------------------------------------
# settlement_window_utc
# ---------------------------------------------------------------------------


class TestSettlementWindowUtc:
    def test_nyc_window_jul_4(self) -> None:
        start, end = settlement_window_utc("2024-07-04", "NYC")
        # midnight LST = 05:00 UTC (UTC-5)
        assert start == datetime(2024, 7, 4, 5, 0, tzinfo=UTC)
        assert end == datetime(2024, 7, 5, 5, 0, tzinfo=UTC)

    def test_chicago_window(self) -> None:
        start, end = settlement_window_utc("2024-07-04", "ORD")
        # midnight CST = 06:00 UTC (UTC-6)
        assert start == datetime(2024, 7, 4, 6, 0, tzinfo=UTC)
        assert end == datetime(2024, 7, 5, 6, 0, tzinfo=UTC)

    def test_window_is_24h(self) -> None:
        start, end = settlement_window_utc("2024-12-25", "NYC")
        assert (end - start) == timedelta(hours=24)

    def test_dst_transition_window_unchanged(self) -> None:
        # 2024-03-10 is the DST spring-forward date for US Eastern
        # LST window is still UTC-5 (standard time)
        start, end = settlement_window_utc("2024-03-10", "NYC")
        assert start == datetime(2024, 3, 10, 5, 0, tzinfo=UTC)
        assert end == datetime(2024, 3, 11, 5, 0, tzinfo=UTC)


# ---------------------------------------------------------------------------
# cli_available_at
# ---------------------------------------------------------------------------


class TestCliAvailableAt:
    def test_nyc_jul_4_default_delay(self) -> None:
        # window_end = 2024-07-05 05:00 UTC, delay = 10h
        result = cli_available_at("2024-07-04", "NYC")
        expected = datetime(2024, 7, 5, 15, 0, tzinfo=UTC)
        assert result == expected

    def test_custom_delay(self) -> None:
        result = cli_available_at("2024-07-04", "NYC", delay_hours=4.0)
        expected = datetime(2024, 7, 5, 9, 0, tzinfo=UTC)
        assert result == expected


# ---------------------------------------------------------------------------
# build_snapshot
# ---------------------------------------------------------------------------


class TestBuildSnapshot:
    def test_empty_observations(self) -> None:
        snap = build_snapshot(
            station="NYC",
            as_of="2024-07-04T20:00:00Z",
            observations=[],
            all_climate=[],
        )
        assert snap.station == "NYC"
        assert snap.settlement_date == "2024-07-04"
        assert snap.observations == []
        assert snap.climate is None
        assert isinstance(snap.version, DataVersion)
        assert snap.version.observation_count == 0
        assert snap.version.latest_observation is None
        assert snap.forecasts is None  # stub

    def test_version_field_in_to_dict(self) -> None:
        snap = build_snapshot(
            station="NYC",
            as_of="2024-07-04T20:00:00Z",
            observations=[],
            all_climate=[],
        )
        d = snap.to_dict()
        assert d["data_version"] == "empty"

    def test_observations_filtered_to_window_lower_bound(self) -> None:
        # Obs at 2024-07-03T22:00Z is BEFORE the NYC window start (2024-07-04T05:00Z)
        obs_before_window = _make_obs("2024-07-03T22:00:00Z")
        obs_in_window = _make_obs("2024-07-04T10:00:00Z")
        snap = build_snapshot(
            station="NYC",
            as_of="2024-07-04T20:00:00Z",
            observations=[obs_before_window, obs_in_window],
            all_climate=[],
        )
        assert len(snap.observations) == 1
        assert snap.observations[0].observed_at == "2024-07-04T10:00:00Z"

    def test_observations_filtered_to_as_of(self) -> None:
        obs_before = _make_obs("2024-07-04T10:00:00Z")
        obs_after = _make_obs("2024-07-04T22:00:00Z")
        snap = build_snapshot(
            station="NYC",
            as_of="2024-07-04T20:00:00Z",
            observations=[obs_before, obs_after],
            all_climate=[],
        )
        assert len(snap.observations) == 1
        assert snap.observations[0].observed_at == "2024-07-04T10:00:00Z"

    def test_version_latest_observation(self) -> None:
        obs1 = _make_obs("2024-07-04T10:00:00Z")
        obs2 = _make_obs("2024-07-04T15:00:00Z")
        snap = build_snapshot(
            station="NYC",
            as_of="2024-07-04T20:00:00Z",
            observations=[obs1, obs2],
            all_climate=[],
        )
        assert isinstance(snap.version, DataVersion)
        assert snap.version.latest_observation == "2024-07-04T15:00:00Z"
        assert snap.version.observation_count == 2
        d = snap.to_dict()
        assert d["data_version"] == "2024-07-04T15:00:00Z"

    def test_version_same_obs_different_as_of(self) -> None:
        """Same observations at different as_of → same version token."""
        obs = [_make_obs("2024-07-04T10:00:00Z"), _make_obs("2024-07-04T15:00:00Z")]
        snap1 = build_snapshot(
            station="NYC",
            as_of="2024-07-04T20:00:00Z",
            observations=obs,
            all_climate=[],
        )
        snap2 = build_snapshot(
            station="NYC",
            as_of="2024-07-04T21:00:00Z",
            observations=obs,
            all_climate=[],
        )
        assert snap1.version.version == snap2.version.version

    def test_climate_withheld_before_publication(self) -> None:
        # Settlement window for NYC July 5: starts 2024-07-05T05:00Z.
        # as_of = 2024-07-05T06:00Z → settlement_date = "2024-07-05".
        # CLI for July 5 not published until 2024-07-06T15:00Z (default 10h delay).
        snap = build_snapshot(
            station="NYC",
            as_of="2024-07-05T06:00:00Z",
            observations=[],
            all_climate=[_climate("2024-07-05", "final")],
        )
        assert snap.climate is None

    def test_climate_included_after_publication(self) -> None:
        # Use delay_hours=-1: July 4 window_end = 2024-07-05T05:00Z
        # → threshold = 2024-07-05T04:00Z.
        # as_of = 2024-07-05T04:30Z → settlement_date = July 4 ✓
        # as_of (04:30Z) >= threshold (04:00Z) → climate included.
        snap = build_snapshot(
            station="NYC",
            as_of="2024-07-05T04:30:00Z",
            observations=[],
            all_climate=[_climate("2024-07-04", "final")],
            cli_publication_delay_hours=-1,
        )
        assert snap.climate is not None
        assert snap.climate["report_type"] == "final"

    def test_climate_prefers_highest_priority_report(self) -> None:
        snap = build_snapshot(
            station="NYC",
            as_of="2024-07-05T04:30:00Z",
            observations=[],
            all_climate=[
                _climate("2024-07-04", "preliminary"),
                _climate("2024-07-04", "final"),
                _climate("2024-07-04", "estimated"),
            ],
            cli_publication_delay_hours=-1,
        )
        assert snap.climate is not None
        assert snap.climate["report_type"] == "final"

    def test_window_start_end_utc_format(self) -> None:
        snap = build_snapshot(
            station="NYC",
            as_of="2024-07-04T20:00:00Z",
            observations=[],
            all_climate=[],
        )
        assert snap.window_start_utc == "2024-07-04T05:00:00Z"
        assert snap.window_end_utc == "2024-07-05T05:00:00Z"

    def test_k_prefix_station_normalized(self) -> None:
        snap = build_snapshot(
            station="KNYC",
            as_of="2024-07-04T20:00:00Z",
            observations=[],
            all_climate=[],
        )
        assert snap.station == "NYC"

    def test_unknown_station_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown station timezone"):
            build_snapshot(
                station="ZZZ",
                as_of="2024-07-04T20:00:00Z",
                observations=[],
                all_climate=[],
            )

    def test_tz_override_for_unknown_station(self) -> None:
        snap = build_snapshot(
            station="ZZZ",
            as_of="2024-07-04T20:00:00Z",
            observations=[],
            all_climate=[],
            tz_override="America/Chicago",
        )
        assert snap.station == "ZZZ"
        # CST window start = 06:00 UTC
        assert snap.window_start_utc == "2024-07-04T06:00:00Z"

    def test_to_dict_serializable(self) -> None:
        import json

        snap = build_snapshot(
            station="NYC",
            as_of="2024-07-04T20:00:00Z",
            observations=[_make_obs("2024-07-04T10:00:00Z")],
            all_climate=[],
        )
        d = snap.to_dict()
        # Verify JSON-serializable (no datetime objects, no Observation objects)
        serialized = json.dumps(d)
        loaded = json.loads(serialized)
        assert loaded["station"] == "NYC"
        assert loaded["settlement_date"] == "2024-07-04"
        assert len(loaded["observations"]) == 1
        assert loaded["data_version"] == "2024-07-04T10:00:00Z"

    def test_to_toon_returns_string(self) -> None:
        """Always runs; mostlyright._internal._toon is in-tree (no find_spec gating).

        Rob PR #2 C3: previously gated behind ``find_spec`` so CI never
        invoked ``to_toon()`` even when the module was missing - CI green
        could ship a runtime ImportError. This test must always execute.
        """
        snap = build_snapshot(
            station="NYC",
            as_of="2024-07-04T20:00:00Z",
            observations=[],
            all_climate=[],
        )
        toon = snap.to_toon()
        assert isinstance(toon, str)
        assert "NYC" in toon
        assert "2024-07-04" in toon

    def test_cli_publication_delay_hours_stored(self) -> None:
        snap = build_snapshot(
            station="NYC",
            as_of="2024-07-04T20:00:00Z",
            observations=[],
            all_climate=[],
            cli_publication_delay_hours=4.0,
        )
        assert snap.cli_publication_delay_hours == 4.0

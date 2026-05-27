"""Phase 20 PLAN-05: Live mode dispatch + cycle-math fallback issued_at."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock

import httpx
import pandas as pd
from mostlyright.weather._fetchers._open_meteo import (
    OPEN_METEO_LIVE_URL,
    OPEN_METEO_PREVIOUS_RUNS_URL,
    OPEN_METEO_SINGLE_RUNS_URL,
    fetch_open_meteo,
)
from mostlyright.weather._fetchers._open_meteo_models import (
    CYCLE_HOURS,
    PUBLISH_LAG,
    floor_to_cycle,
)


def _make_mock_client(payload: dict, status_code: int = 200) -> MagicMock:
    client = MagicMock(spec=httpx.Client)
    response = MagicMock()
    response.status_code = status_code
    response.json.return_value = payload
    response.raise_for_status.return_value = None
    client.get.return_value = response
    return client


def _live_response_payload(times: list[str], temps: list[float]) -> dict:
    return {
        "latitude": 40.78,
        "longitude": -73.97,
        "hourly_units": {"time": "iso8601", "temperature_2m": "C"},
        "hourly": {"time": times, "temperature_2m": temps},
    }


def test_live_mode_returns_dataframe() -> None:
    payload = _live_response_payload(["2026-05-28T00:00", "2026-05-28T01:00"], [18.5, 19.0])
    client = _make_mock_client(payload)
    df = fetch_open_meteo(
        "KNYC",
        "2026-05-28",
        "2026-05-28",
        model="gfs_global",
        mode="live",
        client=client,
    )
    assert isinstance(df, pd.DataFrame)
    assert len(df) == 2


def test_live_mode_hits_live_endpoint() -> None:
    payload = _live_response_payload(["2026-05-28T00:00"], [18.5])
    client = _make_mock_client(payload)
    fetch_open_meteo(
        "KNYC",
        "2026-05-28",
        "2026-05-28",
        model="gfs_global",
        mode="live",
        client=client,
    )
    url = client.get.call_args[0][0]
    assert url == OPEN_METEO_LIVE_URL
    assert url != OPEN_METEO_PREVIOUS_RUNS_URL
    assert url != OPEN_METEO_SINGLE_RUNS_URL


def test_live_mode_source_tag() -> None:
    payload = _live_response_payload(["2026-05-28T00:00"], [18.5])
    client = _make_mock_client(payload)
    df = fetch_open_meteo(
        "KNYC",
        "2026-05-28",
        "2026-05-28",
        model="gfs_global",
        mode="live",
        client=client,
    )
    assert df["source"].iloc[0] == "open_meteo.live"


def test_live_mode_issued_at_populated() -> None:
    payload = _live_response_payload(["2026-05-28T00:00", "2026-05-28T06:00"], [18.5, 22.0])
    client = _make_mock_client(payload)
    df = fetch_open_meteo(
        "KNYC",
        "2026-05-28",
        "2026-05-28",
        model="gfs_global",
        mode="live",
        client=client,
    )
    assert df["issued_at"].notna().all()


def test_live_mode_issued_at_follows_cycle_math_formula_gfs() -> None:
    """Live GFS uses publish_lag=6h, cycle_hours=(0,6,12,18). The derived
    issued_at must equal floor_to_cycle(now - 6h, gfs_cycles)."""
    payload = _live_response_payload(["2026-05-28T12:00"], [22.0])
    client = _make_mock_client(payload)
    before = datetime.now(UTC)
    df = fetch_open_meteo(
        "KNYC",
        "2026-05-28",
        "2026-05-28",
        model="gfs_global",
        mode="live",
        client=client,
    )
    after = datetime.now(UTC)
    issued = df["issued_at"].iloc[0]

    earliest_now = before - PUBLISH_LAG["gfs_global"]
    latest_now = after - PUBLISH_LAG["gfs_global"]
    expected_lower = floor_to_cycle(earliest_now, CYCLE_HOURS["gfs_global"])
    expected_upper = floor_to_cycle(latest_now, CYCLE_HOURS["gfs_global"])
    issued_pd = pd.Timestamp(issued).to_pydatetime()
    assert expected_lower <= issued_pd <= expected_upper


def test_live_mode_hourly_model_uses_2h_lag_hrrr() -> None:
    payload = _live_response_payload(["2026-05-28T12:00"], [22.0])
    client = _make_mock_client(payload)
    before = datetime.now(UTC)
    df = fetch_open_meteo(
        "KNYC",
        "2026-05-28",
        "2026-05-28",
        model="ncep_hrrr_conus",
        mode="live",
        client=client,
    )
    issued = pd.Timestamp(df["issued_at"].iloc[0]).to_pydatetime()
    # HRRR has publish_lag=2h
    expected_floor = floor_to_cycle(
        before - PUBLISH_LAG["ncep_hrrr_conus"],
        CYCLE_HOURS["ncep_hrrr_conus"],
    )
    # The actual issued_at should be within 1 hour of the expected (clock skew)
    assert abs((issued - expected_floor).total_seconds()) <= 3600


def test_live_mode_response_without_previous_day_suffixes_parses() -> None:
    """Live response uses bare temperature_2m, not temperature_2m_previous_day1."""
    payload = {
        "latitude": 40.78,
        "longitude": -73.97,
        "hourly_units": {"time": "iso8601", "temperature_2m": "C"},
        "hourly": {
            "time": ["2026-05-28T00:00"],
            "temperature_2m": [18.5],
        },
    }
    client = _make_mock_client(payload)
    df = fetch_open_meteo(
        "KNYC",
        "2026-05-28",
        "2026-05-28",
        model="gfs_global",
        mode="live",
        client=client,
    )
    assert df["temp_c"].iloc[0] == 18.5


def test_live_mode_allow_leakage_ignored() -> None:
    """allow_leakage is only meaningful for seamless mode; live ignores it."""
    payload = _live_response_payload(["2026-05-28T00:00"], [18.5])
    client = _make_mock_client(payload)
    df = fetch_open_meteo(
        "KNYC",
        "2026-05-28",
        "2026-05-28",
        model="gfs_global",
        mode="live",
        allow_leakage=True,
        client=client,
    )
    assert df["source"].iloc[0] == "open_meteo.live"

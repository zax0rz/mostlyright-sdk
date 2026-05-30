"""Phase 20 OM-01: fetch_open_meteo() Previous Runs + Single Runs + seamless opt-in."""

from __future__ import annotations

import re
from unittest.mock import MagicMock

import httpx
import pandas as pd
import pytest
from mostlyright.core.exceptions import OpenMeteoSeamlessLeakageError
from mostlyright.weather._fetchers._open_meteo import (
    OPEN_METEO_PREVIOUS_RUNS_URL,
    OPEN_METEO_SEAMLESS_URL,
    OPEN_METEO_SINGLE_RUNS_URL,
    fetch_open_meteo,
)


def _make_mock_client(payload: dict, status_code: int = 200) -> MagicMock:
    """MagicMock simulating httpx.Client for fetcher tests."""
    client = MagicMock(spec=httpx.Client)
    response = MagicMock()
    response.status_code = status_code
    response.json.return_value = payload
    response.headers = {}
    if status_code >= 400:
        request_obj = MagicMock()
        response_obj = MagicMock()
        response_obj.status_code = status_code
        response_obj.headers = {}
        response.raise_for_status.side_effect = httpx.HTTPStatusError(
            f"HTTP {status_code}",
            request=request_obj,
            response=response_obj,
        )
    else:
        response.raise_for_status.return_value = None
    client.get.return_value = response
    return client


_SAMPLE_PREVIOUS_RUNS_PAYLOAD: dict = {
    "latitude": 40.78,
    "longitude": -73.97,
    "elevation": 51.0,
    "hourly_units": {
        "time": "iso8601",
        "temperature_2m_previous_day1": "°C",
        "dew_point_2m_previous_day1": "°C",
        "wind_speed_10m_previous_day1": "m/s",
        "shortwave_radiation_previous_day1": "W/m²",
        "cape_previous_day1": "J/kg",
    },
    "hourly": {
        "time": [
            "2024-06-01T00:00",
            "2024-06-01T01:00",
            "2024-06-01T02:00",
            "2024-06-01T23:00",
        ],
        "temperature_2m_previous_day1": [18.5, 19.0, 19.2, 26.8],
        "dew_point_2m_previous_day1": [12.0, 12.5, 13.0, 14.5],
        "wind_speed_10m_previous_day1": [2.3, 2.5, 2.7, 3.1],
        "shortwave_radiation_previous_day1": [0.0, 0.0, 0.0, 220.5],
        "cape_previous_day1": [50.0, 60.0, 75.0, 1200.0],
    },
}


def test_fetch_open_meteo_basic_training_mode() -> None:
    client = _make_mock_client(_SAMPLE_PREVIOUS_RUNS_PAYLOAD)
    df = fetch_open_meteo(
        "NYC",
        "2024-06-01",
        "2024-06-01",
        model="gfs_global",
        mode="training",
        client=client,
    )
    assert isinstance(df, pd.DataFrame)
    assert len(df) == 4


def test_fetch_open_meteo_source_identity_previous_runs() -> None:
    client = _make_mock_client(_SAMPLE_PREVIOUS_RUNS_PAYLOAD)
    df = fetch_open_meteo(
        "NYC",
        "2024-06-01",
        "2024-06-01",
        model="gfs_global",
        mode="training",
        client=client,
    )
    assert (df["source"] == "open_meteo.previous_runs").all()


def test_fetch_open_meteo_issued_at_populated() -> None:
    client = _make_mock_client(_SAMPLE_PREVIOUS_RUNS_PAYLOAD)
    df = fetch_open_meteo(
        "NYC",
        "2024-06-01",
        "2024-06-01",
        model="gfs_global",
        mode="training",
        client=client,
    )
    assert df["issued_at"].notna().all()


def test_fetch_open_meteo_issued_at_conservative_lower_bound() -> None:
    """NYC 2024-06-01T23:00Z, GFS previous_day1 → issued_at = 2024-05-31T18:00Z."""
    client = _make_mock_client(_SAMPLE_PREVIOUS_RUNS_PAYLOAD)
    df = fetch_open_meteo(
        "NYC",
        "2024-06-01",
        "2024-06-01",
        model="gfs_global",
        mode="training",
        client=client,
    )
    h23_rows = df[df["valid_at"] == pd.Timestamp("2024-06-01T23:00:00Z")]
    assert len(h23_rows) == 1
    assert h23_rows["issued_at"].iloc[0] == pd.Timestamp("2024-05-31T18:00:00Z")


def test_fetch_open_meteo_temp_c_no_conversion_needed() -> None:
    """Open-Meteo serves Celsius natively; temp_c == temperature_2m_previous_day1."""
    client = _make_mock_client(_SAMPLE_PREVIOUS_RUNS_PAYLOAD)
    df = fetch_open_meteo(
        "NYC",
        "2024-06-01",
        "2024-06-01",
        model="gfs_global",
        mode="training",
        client=client,
    )
    h23 = df[df["valid_at"] == pd.Timestamp("2024-06-01T23:00:00Z")].iloc[0]
    assert h23["temp_c"] == 26.8


def test_fetch_open_meteo_single_runs_when_issued_at_provided() -> None:
    """When caller passes issued_at=..., fetcher uses Single Runs API."""
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        return httpx.Response(
            200,
            json={
                "latitude": 40.78,
                "longitude": -73.97,
                "elevation": 51.0,
                "hourly_units": {"time": "iso8601", "temperature_2m": "°C"},
                "hourly": {
                    "time": ["2024-06-01T12:00"],
                    "temperature_2m": [22.0],
                },
            },
        )

    transport = httpx.MockTransport(handler)
    client = httpx.Client(transport=transport)
    df = fetch_open_meteo(
        "NYC",
        "2024-06-01",
        "2024-06-01",
        model="gfs_global",
        mode="training",
        issued_at="2024-06-01T12:00",
        client=client,
    )
    assert any("single-runs-api.open-meteo.com" in u for u in calls)
    assert (df["source"] == "open_meteo.single_run").all()
    assert (df["issued_at"] == pd.Timestamp("2024-06-01T12:00:00Z")).all()


def test_fetch_open_meteo_single_runs_omits_date_params() -> None:
    """Single-Runs API rejects start_date/end_date; fetcher must not send them.

    Regression test for https://github.com/mostlyrightmd/mostlyright-sdk/issues/40.
    """
    captured_params: list[dict[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured_params.append(dict(httpx.QueryParams(request.url.query)))
        # Return 168 hours of data (full horizon from run=)
        hours = [
            (pd.Timestamp("2024-06-01T06:00") + pd.Timedelta(hours=i)).isoformat()
            for i in range(168)
        ]
        temps = list(range(168))
        return httpx.Response(
            200,
            json={
                "latitude": 40.78,
                "longitude": -73.97,
                "elevation": 51.0,
                "hourly_units": {"time": "iso8601", "temperature_2m": "°C"},
                "hourly": {"time": hours, "temperature_2m": temps},
            },
        )

    transport = httpx.MockTransport(handler)
    client = httpx.Client(transport=transport)
    df = fetch_open_meteo(
        "KNYC",
        "2024-06-01",
        "2024-06-02",
        model="ncep_hrrr_conus",
        mode="training",
        issued_at="2024-06-01T06:00",
        client=client,
    )
    assert len(captured_params) == 1
    qp = captured_params[0]
    # Single-Runs: run= must be present, date params must NOT
    assert qp.get("run") == "2024-06-01T06:00", f"expected run= param, got {qp}"
    assert "start_date" not in qp, f"start_date must not be sent to Single-Runs API: {qp}"
    assert "end_date" not in qp, f"end_date must not be sent to Single-Runs API: {qp}"
    assert not df.empty


def test_fetch_open_meteo_single_runs_clips_response_to_date_range() -> None:
    """Single-Runs returns full 168h horizon; fetcher must clip to [from_date, to_date].

    Regression test for https://github.com/mostlyrightmd/mostlyright-sdk/issues/40.
    """

    def handler(request: httpx.Request) -> httpx.Response:
        # Return 168 hours starting from the run, spanning Jun 1-8
        hours = [
            (pd.Timestamp("2024-06-01T06:00") + pd.Timedelta(hours=i)).isoformat()
            for i in range(168)
        ]
        temps = list(range(168))
        return httpx.Response(
            200,
            json={
                "latitude": 40.78,
                "longitude": -73.97,
                "elevation": 51.0,
                "hourly_units": {"time": "iso8601", "temperature_2m": "°C"},
                "hourly": {"time": hours, "temperature_2m": temps},
            },
        )

    transport = httpx.MockTransport(handler)
    client = httpx.Client(transport=transport)
    # Request only Jun 1-2, but Single-Runs will return Jun 1-8
    df = fetch_open_meteo(
        "KNYC",
        "2024-06-01",
        "2024-06-02",
        model="ncep_hrrr_conus",
        mode="training",
        issued_at="2024-06-01T06:00",
        client=client,
    )
    assert not df.empty
    # All valid_at should be within Jun 1 00:00 UTC to Jun 3 00:00 UTC (exclusive)
    lo = pd.Timestamp("2024-06-01", tz="UTC")
    hi = pd.Timestamp("2024-06-03", tz="UTC")
    assert df["valid_at"].min() >= lo, f"min valid_at {df['valid_at'].min()} before {lo}"
    assert df["valid_at"].max() < hi, f"max valid_at {df['valid_at'].max()} after {hi}"


def test_fetch_open_meteo_seamless_without_opt_in_raises() -> None:
    client = MagicMock(spec=httpx.Client)
    with pytest.raises(OpenMeteoSeamlessLeakageError) as exc_info:
        fetch_open_meteo(
            "NYC",
            "2024-06-01",
            "2024-06-01",
            model="gfs_global",
            mode="seamless",
            client=client,
        )
    assert "historical-forecast-api" in exc_info.value.endpoint_url
    assert exc_info.value.model == "gfs_global"
    # Security-critical: NO HTTP request before the raise.
    assert not client.get.called


def test_fetch_open_meteo_seamless_with_opt_in_allows_null_issued_at() -> None:
    client = _make_mock_client(
        {
            "latitude": 40.78,
            "longitude": -73.97,
            "elevation": 51.0,
            "hourly_units": {"time": "iso8601", "temperature_2m": "°C"},
            "hourly": {
                "time": ["2024-06-01T23:00"],
                "temperature_2m": [27.9],
            },
        }
    )
    df = fetch_open_meteo(
        "NYC",
        "2024-06-01",
        "2024-06-01",
        model="gfs_global",
        mode="seamless",
        allow_leakage=True,
        client=client,
    )
    assert (df["source"] == "open_meteo.seamless").all()
    # Seamless rows have NULL issued_at by design — LeakageDetector rejects
    # them downstream whenever as_of is asserted.
    assert df["issued_at"].isna().all()


def test_fetch_open_meteo_unknown_model_raises() -> None:
    with pytest.raises(ValueError, match=r"model must be one of"):
        fetch_open_meteo(
            "NYC",
            "2024-06-01",
            "2024-06-01",
            model="bogus_model",
            mode="training",
        )


def test_fetch_open_meteo_unknown_mode_raises() -> None:
    with pytest.raises(ValueError, match=r"mode must be one of"):
        fetch_open_meteo(
            "NYC",
            "2024-06-01",
            "2024-06-01",
            model="gfs_global",
            mode="weird",  # type: ignore[arg-type]
        )


def test_fetch_open_meteo_404_silently_skipped() -> None:
    client = _make_mock_client({}, status_code=404)
    df = fetch_open_meteo(
        "NYC",
        "2024-06-01",
        "2024-06-01",
        model="gfs_global",
        mode="training",
        client=client,
    )
    assert df.empty
    # Empty DataFrame must still carry the canonical columns + dtypes so
    # downstream schema validation passes.
    assert "issued_at" in df.columns
    assert "temp_c" in df.columns
    assert "source" in df.columns


def test_fetch_open_meteo_url_uses_previous_runs_endpoint_lowercase_model() -> None:
    """Issue-#17 analog: ``models`` URL param must be lowercase."""
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        return httpx.Response(200, json=_SAMPLE_PREVIOUS_RUNS_PAYLOAD)

    transport = httpx.MockTransport(handler)
    client = httpx.Client(transport=transport)
    fetch_open_meteo(
        "NYC",
        "2024-06-01",
        "2024-06-01",
        model="gfs_global",
        mode="training",
        client=client,
    )
    assert calls
    url = calls[0]
    assert "previous-runs-api.open-meteo.com" in url
    m = re.search(r"[?&]models=([^&]+)", url)
    assert m is not None
    models_param = m.group(1)
    assert models_param == models_param.lower()
    assert models_param == "gfs_global"


def test_fetch_open_meteo_empty_response_returns_empty_df() -> None:
    client = _make_mock_client(
        {
            "latitude": 40.78,
            "longitude": -73.97,
            "elevation": 51.0,
            "hourly_units": {"time": "iso8601"},
            "hourly": {"time": []},
        }
    )
    df = fetch_open_meteo(
        "NYC",
        "2024-06-01",
        "2024-06-01",
        model="gfs_global",
        mode="training",
        client=client,
    )
    assert df.empty
    expected_cols = {
        "station",
        "issued_at",
        "valid_at",
        "forecast_hour",
        "model",
        "source",
        "temp_c",
        "apparent_temp_c",
        "shortwave_radiation_wm2",
        "cape_jkg",
        "retrieved_at",
    }
    assert expected_cols.issubset(set(df.columns))


def test_fetch_open_meteo_dtype_coercion() -> None:
    client = _make_mock_client(_SAMPLE_PREVIOUS_RUNS_PAYLOAD)
    df = fetch_open_meteo(
        "NYC",
        "2024-06-01",
        "2024-06-01",
        model="gfs_global",
        mode="training",
        client=client,
    )
    assert str(df["temp_c"].dtype) == "Float64"
    assert str(df["weather_code"].dtype) == "Int64"
    assert str(df["station"].dtype) in ("string", "string[python]")
    assert df["valid_at"].dt.tz is not None


def test_fetch_open_meteo_endpoint_constants_are_distinct() -> None:
    assert OPEN_METEO_PREVIOUS_RUNS_URL != OPEN_METEO_SINGLE_RUNS_URL
    assert OPEN_METEO_PREVIOUS_RUNS_URL != OPEN_METEO_SEAMLESS_URL
    assert OPEN_METEO_SINGLE_RUNS_URL != OPEN_METEO_SEAMLESS_URL


def test_fetch_open_meteo_retry_after_capped_at_60s(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``Retry-After: 1000`` must be capped at 60s."""
    sleep_calls: list[float] = []
    monkeypatch.setattr(
        "mostlyright.weather._fetchers._open_meteo.time.sleep",
        lambda s: sleep_calls.append(s),
    )

    # First call: 429 with Retry-After: 1000; second call: 200
    request_obj = MagicMock()
    response_429 = MagicMock()
    response_429.status_code = 429
    response_429.headers = {"Retry-After": "1000"}
    response_429.raise_for_status.side_effect = httpx.HTTPStatusError(
        "429", request=request_obj, response=response_429
    )

    response_200 = MagicMock()
    response_200.status_code = 200
    response_200.json.return_value = _SAMPLE_PREVIOUS_RUNS_PAYLOAD
    response_200.headers = {}
    response_200.raise_for_status.return_value = None

    client = MagicMock(spec=httpx.Client)
    client.get.side_effect = [response_429, response_200]

    df = fetch_open_meteo(
        "NYC",
        "2024-06-01",
        "2024-06-01",
        model="gfs_global",
        mode="training",
        client=client,
    )
    assert isinstance(df, pd.DataFrame)
    # Every sleep call must respect the 60s cap.
    assert sleep_calls, "expected at least one sleep call from retry path"
    assert all(s <= 60.0 for s in sleep_calls), f"sleep_calls={sleep_calls}"


def test_fetch_open_meteo_precip_probability_converted_to_fraction() -> None:
    """Open-Meteo serves probability as percent (0..100); schema is fraction (0..1)."""
    payload = {
        "latitude": 40.78,
        "longitude": -73.97,
        "elevation": 51.0,
        "hourly_units": {"time": "iso8601"},
        "hourly": {
            "time": ["2024-06-01T12:00"],
            "precipitation_probability_previous_day1": [85.0],  # 85%
        },
    }
    client = _make_mock_client(payload)
    df = fetch_open_meteo(
        "NYC",
        "2024-06-01",
        "2024-06-01",
        model="gfs_global",
        mode="training",
        client=client,
    )
    assert df["precip_probability"].iloc[0] == pytest.approx(0.85)


def test_fetch_open_meteo_unknown_station_raises() -> None:
    with pytest.raises(ValueError, match=r"unknown station"):
        fetch_open_meteo(
            "ZZZZ",
            "2024-06-01",
            "2024-06-01",
            model="gfs_global",
            mode="training",
        )

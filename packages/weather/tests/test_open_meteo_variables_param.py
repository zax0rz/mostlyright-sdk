"""Issue #64 Fix 3: variables= param trims the OM hourly variable list.

The pairs join in ``research()`` only consumes temperature, precipitation,
and precipitation_probability — over-fetching 18 variables triples the
weighted Open-Meteo call cost. ``fetch_open_meteo(variables=...)`` lets the
caller (``_fetch_open_meteo_range``) request only the columns it actually
needs while the standalone DataFrame API keeps the full 18-variable default.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import httpx
from mostlyright.weather._fetchers._open_meteo import (
    _OM_VARIABLES_TO_FETCH,
    fetch_open_meteo,
)


def _hourly_param(url: str) -> list[str]:
    """Extract the hourly= query value, URL-decoded into a list of names."""
    qp = httpx.QueryParams(httpx.URL(url).query)
    raw = qp.get("hourly", "")
    assert raw, f"no hourly= in {url!r}"
    return raw.split(",")


def test_default_variables_unchanged_full_18() -> None:
    """Standalone API: bare call still requests the full 18-variable set."""
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        return httpx.Response(
            200,
            json={
                "latitude": 40.78,
                "longitude": -73.97,
                "elevation": 51.0,
                "hourly_units": {"time": "iso8601"},
                "hourly": {"time": []},
            },
        )

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
    requested = _hourly_param(calls[0])
    # 18 variables with _previous_day1 suffix
    assert len(requested) == len(_OM_VARIABLES_TO_FETCH)
    assert all(v.endswith("_previous_day1") for v in requested)


def test_variables_param_trims_request_previous_runs() -> None:
    """variables=('temperature_2m', 'precipitation', 'precipitation_probability')
    must produce exactly 3 hourly params with the previous_day1 suffix."""
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        return httpx.Response(
            200,
            json={
                "latitude": 40.78,
                "longitude": -73.97,
                "elevation": 51.0,
                "hourly_units": {"time": "iso8601"},
                "hourly": {"time": []},
            },
        )

    transport = httpx.MockTransport(handler)
    client = httpx.Client(transport=transport)
    fetch_open_meteo(
        "NYC",
        "2024-06-01",
        "2024-06-01",
        model="gfs_global",
        mode="training",
        variables=("temperature_2m", "precipitation", "precipitation_probability"),
        client=client,
    )
    requested = _hourly_param(calls[0])
    assert sorted(requested) == sorted(
        [
            "temperature_2m_previous_day1",
            "precipitation_previous_day1",
            "precipitation_probability_previous_day1",
        ]
    )


def test_variables_param_rejects_unknown_variable() -> None:
    """Unknown variable name must raise ValueError before any HTTP request."""
    import pytest

    client = MagicMock(spec=httpx.Client)
    with pytest.raises(ValueError, match=r"unknown.*variable"):
        fetch_open_meteo(
            "NYC",
            "2024-06-01",
            "2024-06-01",
            model="gfs_global",
            mode="training",
            variables=("temperature_2m", "bogus_variable_42"),
            client=client,
        )
    assert not client.get.called


def test_variables_param_single_runs_no_suffix() -> None:
    """Single-Runs API uses bare variable names (no _previous_day1 suffix)."""
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
                    "time": ["2024-06-01T06:00"],
                    "temperature_2m": [22.0],
                },
            },
        )

    transport = httpx.MockTransport(handler)
    client = httpx.Client(transport=transport)
    fetch_open_meteo(
        "NYC",
        "2024-06-01",
        "2024-06-01",
        model="gfs_global",
        mode="training",
        issued_at="2024-06-01T06:00",
        variables=("temperature_2m",),
        client=client,
    )
    requested = _hourly_param(calls[0])
    assert requested == ["temperature_2m"]

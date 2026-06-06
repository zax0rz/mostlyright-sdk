"""Issue #64 Fix 2: chunk windows >14 days so per-call weighted cost stays ≤1.x.

Open-Meteo's free tier bills by weighted call cost where every 14 days *or*
every 10 variables doubles the weight. A 1-year window with the default 18
variables is a ~47-weighted single call, exhausting the 600/min budget after
~13 stations. The fetcher's own docstring warns "longer windows must chunk
client-side" — these tests pin that behaviour.
"""

from __future__ import annotations

import httpx
import pandas as pd
from mostlyright.weather._fetchers._open_meteo import fetch_open_meteo


def _payload_for_window(from_date: str, to_date: str) -> dict:
    """Build a minimal Open-Meteo payload covering [from_date, to_date]."""
    start = pd.Timestamp(from_date)
    end = pd.Timestamp(to_date) + pd.Timedelta(days=1)
    hours = []
    cur = start
    while cur < end:
        hours.append(cur.strftime("%Y-%m-%dT%H:%M"))
        cur = cur + pd.Timedelta(hours=1)
    n = len(hours)
    return {
        "latitude": 40.78,
        "longitude": -73.97,
        "elevation": 51.0,
        "hourly_units": {
            "time": "iso8601",
            "temperature_2m_previous_day1": "°C",
        },
        "hourly": {
            "time": hours,
            "temperature_2m_previous_day1": [20.0] * n,
        },
    }


def test_window_under_14_days_single_call() -> None:
    """A 7-day window should produce exactly one HTTP call."""
    calls: list[dict[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        qp = dict(httpx.QueryParams(request.url.query))
        calls.append(qp)
        return httpx.Response(200, json=_payload_for_window(qp["start_date"], qp["end_date"]))

    transport = httpx.MockTransport(handler)
    client = httpx.Client(transport=transport)
    fetch_open_meteo(
        "NYC",
        "2024-06-01",
        "2024-06-07",
        model="gfs_global",
        mode="training",
        variables=("temperature_2m",),
        client=client,
    )
    assert len(calls) == 1
    assert calls[0]["start_date"] == "2024-06-01"
    assert calls[0]["end_date"] == "2024-06-07"


def test_window_over_14_days_is_chunked() -> None:
    """A 30-day window must be split into ≤14-day chunks (3 calls)."""
    calls: list[dict[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        qp = dict(httpx.QueryParams(request.url.query))
        calls.append(qp)
        return httpx.Response(200, json=_payload_for_window(qp["start_date"], qp["end_date"]))

    transport = httpx.MockTransport(handler)
    client = httpx.Client(transport=transport)
    df = fetch_open_meteo(
        "NYC",
        "2024-06-01",
        "2024-06-30",
        model="gfs_global",
        mode="training",
        variables=("temperature_2m",),
        client=client,
    )
    # ceil(30 / 14) == 3 chunks
    assert len(calls) >= 2
    assert len(calls) <= 3
    # Every chunk must span at most 14 days.
    for qp in calls:
        start = pd.Timestamp(qp["start_date"])
        end = pd.Timestamp(qp["end_date"])
        assert (end - start).days <= 13, (
            f"chunk {qp['start_date']}..{qp['end_date']} exceeds 14 days"
        )
    # Concatenation must still cover the whole 30 days.
    chunk_starts = sorted(qp["start_date"] for qp in calls)
    chunk_ends = sorted(qp["end_date"] for qp in calls)
    assert chunk_starts[0] == "2024-06-01"
    assert chunk_ends[-1] == "2024-06-30"
    # The merged DataFrame must contain rows across the full range.
    assert not df.empty
    assert df["valid_at"].min() <= pd.Timestamp("2024-06-02", tz="UTC")
    assert df["valid_at"].max() >= pd.Timestamp("2024-06-29", tz="UTC")


def test_single_runs_mode_not_chunked() -> None:
    """Single-Runs uses run=, returns full 168h horizon; chunking does not apply."""
    calls: list[dict[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        qp = dict(httpx.QueryParams(request.url.query))
        calls.append(qp)
        hours = [
            (pd.Timestamp("2024-06-01T06:00") + pd.Timedelta(hours=i)).isoformat()
            for i in range(168)
        ]
        return httpx.Response(
            200,
            json={
                "latitude": 40.78,
                "longitude": -73.97,
                "elevation": 51.0,
                "hourly_units": {"time": "iso8601", "temperature_2m": "°C"},
                "hourly": {"time": hours, "temperature_2m": list(range(168))},
            },
        )

    transport = httpx.MockTransport(handler)
    client = httpx.Client(transport=transport)
    fetch_open_meteo(
        "NYC",
        "2024-06-01",
        "2024-06-30",  # asking for 30 days; Single-Runs returns 7 days from run=
        model="gfs_global",
        mode="training",
        issued_at="2024-06-01T06:00",
        client=client,
    )
    # Single-Runs uses run= once; no client-side chunking.
    assert len(calls) == 1
    assert calls[0].get("run") == "2024-06-01T06:00"


def test_chunked_window_preserves_source_attrs() -> None:
    """Issue #64 / codex P2: a >14-day Previous-Runs window is fetched in
    multiple chunks and concatenated; pd.concat drops df.attrs, so the combined
    frame must be re-stamped with the documented source-identity / retrieved_at
    provenance (else validate_dataframe's source_attr_required fails)."""

    def handler(request: httpx.Request) -> httpx.Response:
        qp = dict(httpx.QueryParams(request.url.query))
        return httpx.Response(200, json=_payload_for_window(qp["start_date"], qp["end_date"]))

    transport = httpx.MockTransport(handler)
    client = httpx.Client(transport=transport)
    df = fetch_open_meteo(
        "NYC",
        "2024-06-01",
        "2024-06-30",  # 30 days -> 3 chunks -> pd.concat
        model="gfs_global",
        mode="training",
        variables=("temperature_2m",),
        client=client,
    )
    # Provenance attrs must survive the multi-chunk concat.
    assert df.attrs.get("source") == "open_meteo.previous_runs"
    assert df.attrs.get("retrieved_at") is not None


def test_single_runs_polite_delay_uses_fixed_horizon_not_window() -> None:
    """Issue #64 / codex P2: Single-Runs sends only run= and returns a fixed
    ~168h horizon, so its weight-aware polite delay must use that 7-day span —
    NOT the (here year-long) requested window. Otherwise an exact-cycle long
    request sleeps for tens of seconds after a single API call."""
    from unittest.mock import patch

    def handler(request: httpx.Request) -> httpx.Response:
        hours = []
        cur = pd.Timestamp("2024-01-01")
        for _ in range(168):
            hours.append(cur.strftime("%Y-%m-%dT%H:%M"))
            cur += pd.Timedelta(hours=1)
        return httpx.Response(
            200,
            json={
                "latitude": 40.78,
                "longitude": -73.97,
                "elevation": 51.0,
                "hourly_units": {"time": "iso8601", "temperature_2m": "°C"},
                "hourly": {"time": hours, "temperature_2m": [20.0] * 168},
            },
        )

    transport = httpx.MockTransport(handler)
    client = httpx.Client(transport=transport)
    sleeps: list[float] = []
    with patch("mostlyright.weather._fetchers._open_meteo.time.sleep", side_effect=sleeps.append):
        fetch_open_meteo(
            "NYC",
            "2024-01-01",
            "2024-12-31",  # ~1 year requested, but Single-Runs returns fixed horizon
            model="gfs_global",
            mode="training",
            issued_at="2024-01-01T06:00",
            variables=("temperature_2m",),
            client=client,
        )
    # With the fixed 7-day horizon + 3 vars the weighted cost is 1 -> one 0.2s
    # polite sleep. The buggy window-scaled path would sleep ~5s (cost ~26).
    assert sleeps, "expected a polite delay sleep"
    assert max(sleeps) <= 0.5, f"polite delay scaled by requested window: {max(sleeps)}s"

"""Phase 17 PLAN-09 Task 2 — forecast_nwp(cycle_range_start, cycle_range_end).

Closes the PLAN-07 placeholder ``NotImplementedError`` and exercises the
actual multi-cycle iteration + concat.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import patch

import pandas as pd
from mostlyright.weather.forecast_nwp import forecast_nwp


def _row(cycle: datetime, fxx: int = 1) -> dict:
    """One canonical schema.forecast_nwp.v1 row."""
    return {
        "station": "KNYC",
        "model": "hrrr",
        "mirror": "aws_bdp",
        "grid_kind": "ncep_native",
        "issued_at": pd.Timestamp(cycle),
        "valid_at": pd.Timestamp(cycle) + pd.Timedelta(hours=fxx),
        "forecast_hour": fxx,
        "grid_dist_km": 0.5,
        "temp_k_2m": 280.0,
        "dewpoint_k_2m": 273.0,
        "relative_humidity_pct_2m": 80.0,
        "wind_u_ms_10m": 1.0,
        "wind_v_ms_10m": 0.0,
        "wind_gust_ms": 3.0,
        "precip_mm_1h": 0.0,
        "pressure_pa_surface": 101_000.0,
        "pressure_pa_mslp": 101_500.0,
        "qc_status": "clean",
        "retrieved_at": pd.Timestamp(cycle) + pd.Timedelta(minutes=10),
        "source": "noaa_bdp",
    }


def test_forecast_nwp_cycle_range_iterates_and_concats() -> None:
    """forecast_nwp(cycle_range_start, cycle_range_end) iterates cycles via
    cycle_range() and concatenates the per-cycle DataFrames."""
    start = datetime(2025, 6, 1, 0, 0, tzinfo=UTC)
    end = datetime(2025, 6, 1, 6, 0, tzinfo=UTC)

    # HRRR is hourly → cycle_range returns 7 cycles (00..06 inclusive).
    expected_cycles = [datetime(2025, 6, 1, h, 0, tzinfo=UTC) for h in range(7)]
    per_cycle_calls: list[datetime] = []

    real_forecast_nwp = forecast_nwp

    def _fake_single(*args, **kwargs):
        cycle = kwargs.get("cycle")
        # Only intercept the per-cycle recursive call (no range kwargs).
        if cycle is not None and kwargs.get("cycle_range_start") is None:
            per_cycle_calls.append(cycle)
            return pd.DataFrame([_row(cycle)])
        return real_forecast_nwp(*args, **kwargs)

    with (
        patch(
            "mostlyright.weather._fetchers._nwp_cycle_chunks.check_historical_depth",
            return_value=None,
        ),
        patch(
            "mostlyright.weather.forecast_nwp.forecast_nwp",
            side_effect=_fake_single,
        ),
    ):
        df = real_forecast_nwp(
            station="KNYC",
            model="hrrr",
            cycle_range_start=start,
            cycle_range_end=end,
        )

    assert isinstance(df, pd.DataFrame)
    assert len(df) == 7, f"expected 7 concatenated rows; got {len(df)}"
    assert per_cycle_calls == expected_cycles, (
        f"per-cycle calls drift: {per_cycle_calls!r} vs {expected_cycles!r}"
    )


def test_forecast_nwp_cycle_range_empty_returns_empty_df() -> None:
    """Empty cycle range (start > end) returns an empty DataFrame without
    hitting the network. ``check_historical_depth`` is NOT called because
    the cycles_to_fetch short-circuit fires first."""
    start = datetime(2025, 6, 2, 0, 0, tzinfo=UTC)
    end = datetime(2025, 6, 1, 0, 0, tzinfo=UTC)  # reversed → empty

    df = forecast_nwp(
        station="KNYC",
        model="hrrr",
        cycle_range_start=start,
        cycle_range_end=end,
    )
    assert isinstance(df, pd.DataFrame)
    assert df.empty


def test_forecast_nwp_single_cycle_path_still_works() -> None:
    """REGRESSION — single-cycle invocation (cycle=...) must NOT raise the
    PLAN-09 placeholder NotImplementedError. The function may still raise
    other errors (live HTTP, missing [nwp] extra) — those are expected and
    out of scope for this regression check."""
    cycle = datetime(2025, 6, 1, 12, 0, tzinfo=UTC)

    try:
        forecast_nwp(station="KNYC", model="hrrr", cycle=cycle, fxx=1)
    except NotImplementedError as exc:
        if "PLAN-09" in str(exc):
            raise AssertionError(f"PLAN-09 placeholder still in place: {exc!r}") from exc
        # Any OTHER NotImplementedError — re-raise so we see it (none
        # expected for HRRR single cycle).
        raise
    except Exception:
        # Single-cycle path will hit live HTTP or [nwp] extra → expected.
        # The test's only assertion is that the PLAN-09 placeholder
        # NotImplementedError is gone (handled above).
        pass

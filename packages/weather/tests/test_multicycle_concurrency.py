"""Phase 24-02: concurrent multi-cycle fan-out in forecast_nwp.

The ``cycle_range_start/end`` path is the dominant backfill cost — a
multi-day HRRR backfill is thousands of serial recursive
``forecast_nwp(cycle=_c)`` calls. Fan them out across a bounded pool while
keeping output byte-identical:

* same rows in cycle_range ORDER regardless of completion order (indexed
  collection, not append-on-complete),
* per-cycle failures (NwpModelNotAvailableError / NoLiveForNwpError /
  GribIntegrityError) still swallowed-and-continued,
* ``check_historical_depth`` pre-flight still runs for EVERY cycle before
  any fetch fires.

The per-cycle recursive ``forecast_nwp`` call is faked (patched on the
module global) so these run without the ``[nwp]`` extra or any network.
"""

from __future__ import annotations

import threading
import time
from datetime import UTC, datetime
from typing import Any
from unittest.mock import patch

import pandas as pd
from mostlyright.core.exceptions import GribIntegrityError
from mostlyright.weather.forecast_nwp import forecast_nwp


def _row(cycle: datetime) -> dict[str, Any]:
    return {
        "station": "KNYC",
        "model": "hrrr",
        "mirror": "aws_bdp",
        "grid_kind": "ncep_native",
        "issued_at": pd.Timestamp(cycle),
        "valid_at": pd.Timestamp(cycle) + pd.Timedelta(hours=1),
        "forecast_hour": 1,
        "grid_dist_km": 0.5,
        "temp_k_2m": 280.0,
        "qc_status": "clean",
        "retrieved_at": pd.Timestamp(cycle),
        "source": "noaa_bdp",
    }


def _run_range(fake_single: Any, depth_spy: Any = None):  # type: ignore[no-untyped-def]
    real = forecast_nwp
    depth = depth_spy or (lambda *a, **k: None)
    start = datetime(2026, 5, 1, 0, 0, tzinfo=UTC)
    end = datetime(2026, 5, 1, 4, 0, tzinfo=UTC)  # hrrr hourly -> 5 cycles

    def _dispatch(*args: Any, **kwargs: Any) -> Any:
        cycle = kwargs.get("cycle")
        if cycle is not None and kwargs.get("cycle_range_start") is None:
            return fake_single(cycle)
        return real(*args, **kwargs)

    with (
        patch(
            "mostlyright.weather._fetchers._nwp_cycle_chunks.check_historical_depth",
            side_effect=depth,
        ),
        patch("mostlyright.weather.forecast_nwp.forecast_nwp", side_effect=_dispatch),
    ):
        return real(
            station="KNYC",
            model="hrrr",
            cycle_range_start=start,
            cycle_range_end=end,
        )


def test_concurrent_multicycle_rows_in_cycle_order() -> None:
    expected = [datetime(2026, 5, 1, h, 0, tzinfo=UTC) for h in range(5)]
    inflight = {"cur": 0, "max": 0}
    lock = threading.Lock()

    def fake_single(cycle: datetime) -> pd.DataFrame:
        with lock:
            inflight["cur"] += 1
            inflight["max"] = max(inflight["max"], inflight["cur"])
        # Earlier cycles sleep LONGER so completion order != cycle order.
        time.sleep(0.02 * (5 - cycle.hour))
        with lock:
            inflight["cur"] -= 1
        return pd.DataFrame([_row(cycle)])

    df = _run_range(fake_single)
    assert len(df) == 5
    # Deterministic: rows must be in cycle_range order despite reversed
    # completion order (proves indexed concat, not append-on-complete).
    issued = [ts.to_pydatetime() for ts in df["issued_at"]]
    assert issued == expected, f"row order drifted: {issued!r}"
    # Sanity: the cycles actually ran concurrently.
    assert inflight["max"] >= 2, "multi-cycle loop ran serially"


def test_per_cycle_failure_is_skipped_and_continues() -> None:
    def fake_single(cycle: datetime) -> pd.DataFrame:
        if cycle.hour == 2:
            raise GribIntegrityError("bad cycle", model="hrrr", variable="TMP")
        return pd.DataFrame([_row(cycle)])

    df = _run_range(fake_single)
    # 5 cycles, the hour-2 cycle failed -> 4 rows, others preserved + ordered.
    assert len(df) == 4
    hours = [ts.to_pydatetime().hour for ts in df["issued_at"]]
    assert hours == [0, 1, 3, 4]


def test_check_historical_depth_runs_for_all_cycles_before_any_fetch() -> None:
    events: list[str] = []
    lock = threading.Lock()

    def depth_spy(model: str, cycle: datetime) -> None:
        with lock:
            events.append(f"depth:{cycle.hour}")

    def fake_single(cycle: datetime) -> pd.DataFrame:
        with lock:
            events.append(f"fetch:{cycle.hour}")
        return pd.DataFrame([_row(cycle)])

    _run_range(fake_single, depth_spy=depth_spy)

    depth_events = [e for e in events if e.startswith("depth:")]
    fetch_events = [e for e in events if e.startswith("fetch:")]
    assert len(depth_events) == 5, "pre-flight must check every cycle"
    assert len(fetch_events) == 5
    last_depth = max(i for i, e in enumerate(events) if e.startswith("depth:"))
    first_fetch = min(i for i, e in enumerate(events) if e.startswith("fetch:"))
    assert last_depth < first_fetch, "a fetch fired before pre-flight finished"

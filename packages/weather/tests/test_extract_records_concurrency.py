"""Phase 24-01: concurrency tests for ``_extract_records``.

The per-variable fetch+decode loop must fan out across a bounded
``ThreadPoolExecutor`` while staying byte-identical to the serial
implementation: same ``column_values``, same ``distances_km`` (first
variable in ``variable_map`` order wins per station), and the same
exception precedence — the FIRST failure in ``variable_map`` order is
raised regardless of type (transport vs integrity), so the post-join
reducer can never let a later transport error mask an earlier integrity
error and silently fall back to another mirror.

These tests fake the leaf HTTP + cfgrib seams so they run without the
``[nwp]`` extra installed:

* ``forecast_nwp.fetch_byte_range`` — leaf byte-range GET.
* ``forecast_nwp._cfgrib_variable_name`` — maps a decoded ds to a name.
* ``_nwp_extract.open_grib2_dataset`` / ``extract_stations`` — decode +
  per-station value extraction.
"""

from __future__ import annotations

import threading
import time
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

import httpx
import pytest
from mostlyright.core.exceptions import GribIntegrityError
from mostlyright.weather._fetchers import _nwp_extract
from mostlyright.weather._fetchers._nwp_archive import build_fetch_plan
from mostlyright.weather._fetchers._nwp_idx import IdxRecord
from mostlyright.weather.forecast_nwp import _extract_records, _MirrorTransportFailed

# variable_map order is load-bearing for distances_km first-wins reduce.
VARIABLE_MAP: dict[str, tuple[str, str]] = {
    "temp_k_2m": ("TMP", "2 m above ground"),
    "dewpoint_k_2m": ("DPT", "2 m above ground"),
    "relative_humidity_pct_2m": ("RH", "2 m above ground"),
    "wind_u_ms_10m": ("UGRD", "10 m above ground"),
    "wind_v_ms_10m": ("VGRD", "10 m above ground"),
    "wind_gust_ms": ("GUST", "surface"),
}


def _records_for(variable_map: dict[str, tuple[str, str]]) -> list[IdxRecord]:
    """One mid-file IdxRecord per variable, each with a distinct byte range."""
    out: list[IdxRecord] = []
    for i, (variable, level) in enumerate(variable_map.values()):
        start = i * 100
        out.append(
            IdxRecord(
                record_no=i + 1,
                byte_offset=start,
                byte_end=start + 99,
                reference_date="d=2026010100",
                variable=variable,
                level=level,
                forecast_period="1 hour fcst",
            )
        )
    return out


def _plan() -> Any:
    return build_fetch_plan(
        model="hrrr",
        mirror="aws_bdp",
        cycle=datetime(2026, 5, 23, 12, tzinfo=UTC),
        fxx=1,
    )


def _install_fakes(
    monkeypatch: pytest.MonkeyPatch,
    *,
    values: dict[str, list[tuple[float | None, float | None]]],
    fetch_side_effect: Any = None,
    decode_raises_for: set[str] | None = None,
    delay_for: dict[str, float] | None = None,
    inflight: dict[str, int] | None = None,
) -> None:
    """Patch the leaf fetch + cfgrib seams used by ``_extract_records``.

    Args:
        values: variable-id (``"TMP"`` etc.) -> per-station ``(value, dist)``.
        fetch_side_effect: optional ``{variable: Exception}`` raised by the
            faked ``fetch_byte_range`` for that variable.
        decode_raises_for: set of variable ids whose ``open_grib2_dataset``
            raises (drives GribIntegrityError).
        delay_for: variable -> seconds to sleep inside the worker (to force
            completion order != map order).
        inflight: mutable dict collecting ``{"max": N}`` high-water-mark of
            concurrent workers (proves real concurrency).
    """
    delay_for = delay_for or {}
    lock = threading.Lock()
    state = {"cur": 0, "max": 0}

    def fake_fetch_byte_range(plan: Any, *, start: int, end: int, client: Any) -> bytes:
        variable = VARIABLE_BY_OFFSET[start]
        if inflight is not None:
            with lock:
                state["cur"] += 1
                state["max"] = max(state["max"], state["cur"])
        try:
            if delay_for.get(variable):
                time.sleep(delay_for[variable])
            if fetch_side_effect and variable in fetch_side_effect:
                raise fetch_side_effect[variable]
            return variable.encode("utf-8")
        finally:
            if inflight is not None:
                with lock:
                    state["cur"] -= 1
                    inflight["max"] = state["max"]

    def fake_open(path: str) -> Any:
        with open(path, "rb") as fh:
            variable = fh.read().decode("utf-8")
        if decode_raises_for and variable in decode_raises_for:
            raise ValueError(f"cfgrib boom for {variable}")
        return SimpleNamespace(_variable=variable, close=lambda: None)

    def fake_cfgrib_name(ds: Any, key: tuple[str, str], *, model: str) -> str:
        return ds._variable

    def fake_extract(
        ds: Any, *, variable: str, station_coords: list[tuple[float, float]]
    ) -> list[tuple[float | None, float | None]]:
        return values[variable]

    monkeypatch.setattr("mostlyright.weather.forecast_nwp.fetch_byte_range", fake_fetch_byte_range)
    monkeypatch.setattr("mostlyright.weather.forecast_nwp._cfgrib_variable_name", fake_cfgrib_name)
    monkeypatch.setattr(_nwp_extract, "open_grib2_dataset", fake_open)
    monkeypatch.setattr(_nwp_extract, "extract_stations", fake_extract)


# Reverse lookup: byte_offset -> variable id (records use 100-byte stride).
VARIABLE_BY_OFFSET: dict[int, str] = {
    i * 100: variable for i, (variable, _level) in enumerate(VARIABLE_MAP.values())
}


def _run(
    monkeypatch: pytest.MonkeyPatch,
    *,
    variable_map: dict[str, tuple[str, str]] = VARIABLE_MAP,
    n_stations: int = 2,
    **fake_kwargs: Any,
) -> tuple[dict[str, list[float | None]], list[float | None]]:
    column_values: dict[str, list[float | None]] = {
        col: [None] * n_stations for col in variable_map
    }
    distances_km: list[float | None] = [None] * n_stations
    _install_fakes(monkeypatch, **fake_kwargs)
    client = httpx.Client(transport=httpx.MockTransport(lambda req: httpx.Response(200)))
    try:
        _extract_records(
            plan=_plan(),
            filtered_records=_records_for(variable_map),
            variable_map=variable_map,
            station_coords=[(40.0, -74.0)] * n_stations,
            column_values=column_values,
            distances_km=distances_km,
            model="hrrr",
            client=client,
        )
    finally:
        client.close()
    return column_values, distances_km


class TestConcurrencyOutputEquivalence:
    def test_column_values_match_per_variable(self, monkeypatch: pytest.MonkeyPatch) -> None:
        values = {
            "TMP": [(280.0, 5.0), (281.0, 6.0)],
            "DPT": [(270.0, 9.0), (271.0, 9.5)],
            "RH": [(50.0, 5.0), (55.0, 6.0)],
            "UGRD": [(1.0, 5.0), (2.0, 6.0)],
            "VGRD": [(3.0, 5.0), (4.0, 6.0)],
            "GUST": [(10.0, 5.0), (11.0, 6.0)],
        }
        column_values, _ = _run(monkeypatch, values=values)
        assert column_values["temp_k_2m"] == [280.0, 281.0]
        assert column_values["dewpoint_k_2m"] == [270.0, 271.0]
        assert column_values["wind_gust_ms"] == [10.0, 11.0]

    def test_distances_km_first_variable_in_map_order_wins(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # TMP (first in map order) -> dist 5.0; DPT -> dist 9.0. Even though
        # TMP's worker is delayed so DPT finishes first, the post-join reduce
        # must keep TMP's distance for station 0 (map-order first-wins).
        values = {
            "TMP": [(280.0, 5.0)],
            "DPT": [(270.0, 9.0)],
            "RH": [(50.0, 7.0)],
            "UGRD": [(1.0, 8.0)],
            "VGRD": [(3.0, 8.5)],
            "GUST": [(10.0, 8.9)],
        }
        for _ in range(5):
            _, distances_km = _run(
                monkeypatch,
                n_stations=1,
                values=values,
                delay_for={"TMP": 0.05},
            )
            assert distances_km == [5.0]

    def test_none_value_does_not_set_distance(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # First variable yields None for station 0; the next variable with a
        # real value should supply the distance.
        values = {
            "TMP": [(None, None)],
            "DPT": [(270.0, 9.0)],
            "RH": [(50.0, 7.0)],
            "UGRD": [(1.0, 8.0)],
            "VGRD": [(3.0, 8.5)],
            "GUST": [(10.0, 8.9)],
        }
        column_values, distances_km = _run(monkeypatch, n_stations=1, values=values)
        assert column_values["temp_k_2m"] == [None]
        assert distances_km == [9.0]


class TestConcurrencyBound:
    def test_runs_workers_concurrently(self, monkeypatch: pytest.MonkeyPatch) -> None:
        values = {v: [(1.0, 1.0)] for v in ("TMP", "DPT", "RH", "UGRD", "VGRD", "GUST")}
        inflight: dict[str, int] = {"max": 0}
        _run(
            monkeypatch,
            n_stations=1,
            values=values,
            delay_for={v: 0.05 for v in values},
            inflight=inflight,
        )
        assert inflight["max"] >= 2, "expected concurrent fan-out, ran serially"

    def test_max_workers_capped_at_nomads_cap(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("mostlyright.weather.forecast_nwp.NOMADS_CONCURRENCY_CAP", 4)
        values = {v: [(1.0, 1.0)] for v in ("TMP", "DPT", "RH", "UGRD", "VGRD", "GUST")}
        inflight: dict[str, int] = {"max": 0}
        _run(
            monkeypatch,
            n_stations=1,
            values=values,
            delay_for={v: 0.05 for v in values},
            inflight=inflight,
        )
        assert inflight["max"] <= 4, f"exceeded NOMADS cap: {inflight['max']}"

    def test_max_workers_capped_at_n_vars_when_fewer_than_cap(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("mostlyright.weather.forecast_nwp.NOMADS_CONCURRENCY_CAP", 4)
        small_map = {
            "temp_k_2m": ("TMP", "2 m above ground"),
            "dewpoint_k_2m": ("DPT", "2 m above ground"),
        }
        values = {"TMP": [(1.0, 1.0)], "DPT": [(2.0, 2.0)]}
        inflight: dict[str, int] = {"max": 0}
        _run(
            monkeypatch,
            variable_map=small_map,
            n_stations=1,
            values=values,
            delay_for={"TMP": 0.05, "DPT": 0.05},
            inflight=inflight,
        )
        assert inflight["max"] <= 2


class TestExceptionPrecedence:
    def test_earlier_transport_failure_wins_over_later_decode_failure(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # DPT (index 1 in map order) transport-fails; RH (index 2) decode-fails.
        # DPT's transport error wins because it is FIRST in variable_map order,
        # NOT because transport dominates integrity by type. The outer mirror
        # loop then falls back. See the inverse test below for the decode-first
        # case, where the precedence must flip.
        values = {v: [(1.0, 1.0)] for v in ("TMP", "DPT", "RH", "UGRD", "VGRD", "GUST")}
        with pytest.raises(_MirrorTransportFailed):
            _run(
                monkeypatch,
                n_stations=1,
                values=values,
                fetch_side_effect={"DPT": httpx.RequestError("conn reset")},
                decode_raises_for={"RH"},
            )

    def test_earlier_decode_failure_wins_over_later_transport_failure(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Inverse of the case above and the regression guard for the post-join
        # reducer: TMP (index 0, FIRST in map order) decode-fails while DPT
        # (index 1) transport-fails. The serial loop raised the first failure
        # in map order regardless of type, so the GribIntegrityError on TMP
        # must surface. A reducer that bucketed by type and preferred transport
        # would raise _MirrorTransportFailed here, triggering a silent mirror
        # fallback that masks TMP's corrupt upstream bytes — exactly the bug
        # this test exists to prevent.
        values = {v: [(1.0, 1.0)] for v in ("TMP", "DPT", "RH", "UGRD", "VGRD", "GUST")}
        with pytest.raises(GribIntegrityError):
            _run(
                monkeypatch,
                n_stations=1,
                values=values,
                decode_raises_for={"TMP"},
                fetch_side_effect={"DPT": httpx.RequestError("conn reset")},
            )

    def test_decode_only_failure_raises_grib_integrity(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        values = {v: [(1.0, 1.0)] for v in ("TMP", "DPT", "RH", "UGRD", "VGRD", "GUST")}
        with pytest.raises(GribIntegrityError):
            _run(
                monkeypatch,
                n_stations=1,
                values=values,
                decode_raises_for={"RH"},
            )

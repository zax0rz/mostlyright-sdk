"""Phase 24-02: module-level concurrency cap on leaf NWP HTTP calls.

The per-variable fan-out (24-01) and the multi-cycle fan-out (24-02) both
issue NOMADS-bound byte-range requests. A single module-level
``threading.BoundedSemaphore(NOMADS_CONCURRENCY_CAP)`` acquired *only*
around each leaf HTTP call keeps the COMBINED in-flight request count under
the cap (Herbie #371 IP-ban guard / SOURCE-LIMITS Option C).

The permit must wrap only the network transfer — never be held across an
``executor.submit``/``.result()`` boundary (that would deadlock nested
pools) and never held while the caller decodes the bytes.
"""

from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from typing import Any

import httpx
from mostlyright.weather._fetchers._nwp_archive import (
    NOMADS_CONCURRENCY_CAP,
    build_fetch_plan,
    fetch_byte_range,
)


def _plan() -> Any:
    return build_fetch_plan(
        model="hrrr",
        mirror="aws_bdp",
        cycle=datetime(2026, 5, 23, 12, tzinfo=UTC),
        fxx=1,
    )


def _counting_transport(inflight: dict[str, int], lock: threading.Lock, *, sleep_s: float):
    def handler(request: httpx.Request) -> httpx.Response:
        with lock:
            inflight["cur"] += 1
            inflight["max"] = max(inflight["max"], inflight["cur"])
        if sleep_s:
            time.sleep(sleep_s)
        with lock:
            inflight["cur"] -= 1
        return httpx.Response(
            206,
            headers={"Content-Range": "bytes 0-9/100"},
            content=b"0123456789",
        )

    return httpx.MockTransport(handler)


def test_byte_range_fetch_in_flight_bounded_by_cap() -> None:
    inflight = {"cur": 0, "max": 0}
    lock = threading.Lock()
    client = httpx.Client(transport=_counting_transport(inflight, lock, sleep_s=0.03))
    plan = _plan()

    def call() -> bytes:
        return fetch_byte_range(plan, start=0, end=9, client=client)

    n = NOMADS_CONCURRENCY_CAP * 3
    try:
        with ThreadPoolExecutor(max_workers=n) as ex:
            results = [f.result() for f in [ex.submit(call) for _ in range(n)]]
    finally:
        client.close()

    assert all(r == b"0123456789" for r in results)
    assert inflight["max"] <= NOMADS_CONCURRENCY_CAP, (
        f"observed {inflight['max']} concurrent leaf fetches > cap {NOMADS_CONCURRENCY_CAP}"
    )
    # Sanity: we actually exercised concurrency (else the cap is vacuous).
    assert inflight["max"] >= 2


def test_permit_released_before_return_no_deadlock() -> None:
    # A fast (non-sleeping) handler: if a permit leaked per call, the
    # (cap + many) sequential calls would block forever on acquire. Their
    # completion proves the permit is released before the bytes return.
    inflight = {"cur": 0, "max": 0}
    lock = threading.Lock()
    client = httpx.Client(transport=_counting_transport(inflight, lock, sleep_s=0.0))
    plan = _plan()
    try:
        for _ in range(NOMADS_CONCURRENCY_CAP * 5):
            assert fetch_byte_range(plan, start=0, end=9, client=client) == b"0123456789"
    finally:
        client.close()

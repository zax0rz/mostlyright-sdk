"""Phase 11 — `tradewinds.live.stream` async-generator unit tests (14 tests).

All tests monkeypatch `asyncio.sleep` to a no-op so the polite-floor cadence
doesn't slow the suite. Per-source fetch is mocked at module-level so the
network is never hit.

1. Stream yields observations
2. Default source is AWC
3. source='iem' invokes IEM fetcher
4. Dedup: same observation served twice → only first yielded
5. New observation (later observed_at) → second row yielded
6. Unknown source raises ValueError before first poll
7. Default poll_seconds for AWC = 30s
8. Default poll_seconds for IEM = 60s
9. poll_seconds below AWC floor raises ValueError
10. poll_seconds above floor accepted
11. Empty tick → loop continues, no exception
12. break out of `async for` cancels cleanly
13. AWC row source field = "awc.live"
14. IEM row source field = "iem.live"
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from tradewinds.live import POLITE_FLOORS_S, stream


def _awc_metar(obs_time: int) -> dict[str, Any]:
    return {
        "icaoId": "KNYC",
        "obsTime": obs_time,
        "metarType": "METAR",
        "temp": 20.0,
        "dewp": 10.0,
        "rawOb": "KNYC 251200Z 18010KT 10SM CLR 20/10 A3010",
    }


async def _collect_n(agen: Any, n: int) -> list[Any]:
    """Drive an async generator and collect up to n items, then aclose() it."""
    items: list[Any] = []
    try:
        async for x in agen:
            items.append(x)
            if len(items) >= n:
                break
    finally:
        await agen.aclose()
    return items


def _run(coro: Any) -> Any:
    return asyncio.run(coro)


@pytest.fixture
def no_sleep(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    """Replace asyncio.sleep with a no-op that records call counts."""
    sleep_calls: list[float] = []

    async def fake_sleep(s: float) -> None:
        sleep_calls.append(s)

    monkeypatch.setattr("tradewinds.live._stream.asyncio.sleep", fake_sleep)
    return sleep_calls


# ----------------------------------------------------------------------
# Tests
# ----------------------------------------------------------------------


def test_stream_yields_observations(monkeypatch: pytest.MonkeyPatch, no_sleep: list[float]) -> None:
    """async for row in stream(...) yields parsed observation rows."""

    def fake_awc(stations: list[str], hours: int) -> list[dict[str, Any]]:
        return [_awc_metar(1748174400)]

    monkeypatch.setattr(
        "tradewinds.weather._fetchers.awc.fetch_awc_metars",
        fake_awc,
    )
    rows = _run(_collect_n(stream("KNYC"), 1))
    assert len(rows) == 1
    assert rows[0]["station_code"] == "NYC"


def test_stream_default_source_awc(monkeypatch: pytest.MonkeyPatch, no_sleep: list[float]) -> None:
    """No source= kwarg → AWC path."""
    called = {"awc": False, "iem": False}

    def fake_awc(stations: list[str], hours: int) -> list[dict[str, Any]]:
        called["awc"] = True
        return [_awc_metar(1748174400)]

    async def fake_iem_latest(station: str) -> list[Any]:
        called["iem"] = True
        return []

    monkeypatch.setattr(
        "tradewinds.weather._fetchers.awc.fetch_awc_metars",
        fake_awc,
    )
    monkeypatch.setattr(
        "tradewinds.live._latest._fetch_iem_latest",
        fake_iem_latest,
    )
    _run(_collect_n(stream("KNYC"), 1))
    assert called["awc"] is True
    assert called["iem"] is False


def test_stream_iem_source(monkeypatch: pytest.MonkeyPatch, no_sleep: list[float]) -> None:
    """source='iem' invokes IEM dispatch."""
    called = {"awc": False, "iem": False}

    def fake_awc(*args: Any, **kwargs: Any) -> list[Any]:
        called["awc"] = True
        return []

    async def fake_iem_latest(station: str) -> list[dict[str, Any]]:
        called["iem"] = True
        # Build a minimal IEM-tagged observation row.
        return [
            {
                "station_code": "NYC",
                "observed_at": "2026-05-25T12:00:00Z",
                "observation_type": "METAR",
                "source": "iem.live",
            }
        ]

    monkeypatch.setattr(
        "tradewinds.weather._fetchers.awc.fetch_awc_metars",
        fake_awc,
    )
    monkeypatch.setattr(
        "tradewinds.live._latest._fetch_iem_latest",
        fake_iem_latest,
    )
    rows = _run(_collect_n(stream("KNYC", source="iem"), 1))
    assert called["iem"] is True
    assert called["awc"] is False
    assert rows[0]["source"] == "iem.live"


def test_stream_dedup_by_observed_at(
    monkeypatch: pytest.MonkeyPatch, no_sleep: list[float]
) -> None:
    """Same observation served twice in a row → only first yielded."""

    def fake_awc(stations: list[str], hours: int) -> list[dict[str, Any]]:
        return [_awc_metar(1748174400)]  # constant — same obsTime every tick

    monkeypatch.setattr(
        "tradewinds.weather._fetchers.awc.fetch_awc_metars",
        fake_awc,
    )
    # Collect 1 row; we want to prove that even though the stream polled
    # multiple ticks, only one row was yielded (dedup invariant).
    rows = _run(_collect_n(stream("KNYC"), 1))
    assert len(rows) == 1
    # No.2 — drive the generator more aggressively and prove the next poll
    # of the SAME obsTime does not yield.

    async def collect_two_with_polls(agen: Any) -> list[Any]:
        items: list[Any] = []
        # First yield should come immediately.
        first = await agen.__anext__()
        items.append(first)
        # Now keep polling — the next yield should never come (same obsTime).
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(agen.__anext__(), timeout=0.05)
        await agen.aclose()
        return items

    rows2 = _run(collect_two_with_polls(stream("KNYC")))
    assert len(rows2) == 1


def test_stream_yields_new_observation_when_obs_time_advances(
    monkeypatch: pytest.MonkeyPatch, no_sleep: list[float]
) -> None:
    """Second poll returns NEWER obsTime → second row yielded."""
    counter = {"i": 0}

    def fake_awc(stations: list[str], hours: int) -> list[dict[str, Any]]:
        counter["i"] += 1
        # Tick N returns obsTime = 1748174400 + 60*N (advances by 60s each tick).
        return [_awc_metar(1748174400 + 60 * counter["i"])]

    monkeypatch.setattr(
        "tradewinds.weather._fetchers.awc.fetch_awc_metars",
        fake_awc,
    )
    rows = _run(_collect_n(stream("KNYC"), 2))
    assert len(rows) == 2
    assert rows[0]["observed_at"] != rows[1]["observed_at"]
    assert rows[0]["observed_at"] < rows[1]["observed_at"]


def test_stream_unknown_source_raises() -> None:
    """source='bogus' raises ValueError BEFORE first poll."""

    async def drive() -> None:
        async for _ in stream("KNYC", source="bogus"):
            return

    with pytest.raises(ValueError, match="unknown live source"):
        _run(drive())


def test_stream_polite_floor_awc_30s_default(
    monkeypatch: pytest.MonkeyPatch, no_sleep: list[float]
) -> None:
    """No poll_seconds= → uses AWC floor of 30s."""
    counter = {"i": 0}

    def fake_awc(stations: list[str], hours: int) -> list[dict[str, Any]]:
        counter["i"] += 1
        # Advance obsTime each poll so the dedup invariant doesn't suppress
        # the 2nd yield, letting us observe a sleep call between yields.
        return [_awc_metar(1748174400 + 60 * counter["i"])]

    monkeypatch.setattr(
        "tradewinds.weather._fetchers.awc.fetch_awc_metars",
        fake_awc,
    )
    _run(_collect_n(stream("KNYC"), 2))
    assert no_sleep, "expected at least one sleep call"
    assert no_sleep[0] == POLITE_FLOORS_S["awc"] == 30.0


def test_stream_polite_floor_iem_60s_default(
    monkeypatch: pytest.MonkeyPatch, no_sleep: list[float]
) -> None:
    """No poll_seconds=, source='iem' → uses IEM floor of 60s."""
    counter = {"i": 0}

    async def fake_iem(station: str) -> list[dict[str, Any]]:
        counter["i"] += 1
        return [
            {
                "station_code": "NYC",
                "observed_at": f"2026-05-25T12:0{counter['i']}:00Z",
                "observation_type": "METAR",
                "source": "iem.live",
            }
        ]

    monkeypatch.setattr(
        "tradewinds.live._latest._fetch_iem_latest",
        fake_iem,
    )
    _run(_collect_n(stream("KNYC", source="iem"), 2))
    assert no_sleep[0] == POLITE_FLOORS_S["iem"] == 60.0


def test_stream_raises_below_polite_floor() -> None:
    """poll_seconds=10 with AWC raises ValueError (below 30s floor)."""

    async def drive() -> None:
        async for _ in stream("KNYC", poll_seconds=10):
            return

    with pytest.raises(ValueError, match="below polite floor"):
        _run(drive())


def test_stream_accepts_above_polite_floor(
    monkeypatch: pytest.MonkeyPatch, no_sleep: list[float]
) -> None:
    """poll_seconds=120 with AWC works."""
    counter = {"i": 0}

    def fake_awc(stations: list[str], hours: int) -> list[dict[str, Any]]:
        counter["i"] += 1
        return [_awc_metar(1748174400 + 60 * counter["i"])]

    monkeypatch.setattr(
        "tradewinds.weather._fetchers.awc.fetch_awc_metars",
        fake_awc,
    )
    rows = _run(_collect_n(stream("KNYC", poll_seconds=120), 2))
    assert len(rows) == 2
    assert no_sleep[0] == 120.0


def test_stream_rejects_nan_poll_seconds() -> None:
    """poll_seconds=NaN must NOT slip through the polite-floor comparison.

    Regression for iter-2 codex finding: `poll_seconds < floor` returns
    False for NaN (all NaN comparisons are False). Without an explicit
    `math.isfinite` guard, `NaN` would bypass the floor and downstream
    `asyncio.sleep(NaN)` would fire immediately, hammering the upstream.
    """
    import math

    async def drive() -> None:
        async for _ in stream("KNYC", poll_seconds=math.nan):
            return

    with pytest.raises(ValueError, match="not a finite number"):
        _run(drive())


def test_stream_rejects_infinite_poll_seconds() -> None:
    """poll_seconds=Infinity is also rejected (same `math.isfinite` guard)."""
    import math

    async def drive() -> None:
        async for _ in stream("KNYC", poll_seconds=math.inf):
            return

    with pytest.raises(ValueError, match="not a finite number"):
        _run(drive())


def test_stream_empty_tick_does_not_abort(
    monkeypatch: pytest.MonkeyPatch, no_sleep: list[float]
) -> None:
    """First poll returns [], second returns a METAR → stream yields once."""
    counter = {"i": 0}

    def fake_awc(stations: list[str], hours: int) -> list[dict[str, Any]]:
        counter["i"] += 1
        if counter["i"] == 1:
            return []  # empty
        return [_awc_metar(1748174400)]  # valid on the 2nd poll

    monkeypatch.setattr(
        "tradewinds.weather._fetchers.awc.fetch_awc_metars",
        fake_awc,
    )
    rows = _run(_collect_n(stream("KNYC"), 1))
    assert len(rows) == 1
    assert counter["i"] >= 2  # the first poll was empty, second yielded


def test_stream_cancellation_via_break(
    monkeypatch: pytest.MonkeyPatch, no_sleep: list[float]
) -> None:
    """async for + break cleanly exits the generator (no zombie tasks)."""

    def fake_awc(stations: list[str], hours: int) -> list[dict[str, Any]]:
        return [_awc_metar(1748174400)]

    monkeypatch.setattr(
        "tradewinds.weather._fetchers.awc.fetch_awc_metars",
        fake_awc,
    )

    async def drive_and_break() -> int:
        n = 0
        agen = stream("KNYC")
        async for _ in agen:
            n += 1
            break  # exit on first yield
        await agen.aclose()
        return n

    n = _run(drive_and_break())
    assert n == 1


def test_stream_source_tag_on_row_awc(
    monkeypatch: pytest.MonkeyPatch, no_sleep: list[float]
) -> None:
    """AWC stream rows carry source='awc.live'."""

    def fake_awc(stations: list[str], hours: int) -> list[dict[str, Any]]:
        return [_awc_metar(1748174400)]

    monkeypatch.setattr(
        "tradewinds.weather._fetchers.awc.fetch_awc_metars",
        fake_awc,
    )
    rows = _run(_collect_n(stream("KNYC"), 1))
    assert rows[0]["source"] == "awc.live"


def test_stream_source_tag_on_row_iem(
    monkeypatch: pytest.MonkeyPatch, no_sleep: list[float]
) -> None:
    """IEM stream rows carry source='iem.live'."""

    async def fake_iem(station: str) -> list[dict[str, Any]]:
        return [
            {
                "station_code": "NYC",
                "observed_at": "2026-05-25T12:00:00Z",
                "observation_type": "METAR",
                "source": "iem.live",
            }
        ]

    monkeypatch.setattr(
        "tradewinds.live._latest._fetch_iem_latest",
        fake_iem,
    )
    rows = _run(_collect_n(stream("KNYC", source="iem"), 1))
    assert rows[0]["source"] == "iem.live"

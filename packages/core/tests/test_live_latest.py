"""Phase 11 — `mostlyright.live.latest` unit tests (8 tests).

Tests mock the per-source fetcher to avoid hitting the network. Each test
verifies one observable property of the one-shot latest() surface:

1. AWC poll returns a parsed observation row with source="awc.live"
2. Default source is AWC (no source= kwarg)
3. source="iem" routes to IEM fetcher (not AWC)
4. Unknown source raises ValueError
5. Empty fetcher response raises NoLiveDataError
6. NoLiveDataError.to_dict() carries station + source
7. Multiple METARs → returns the one with largest observed_at
8. Unparseable METARs are skipped; valid one is returned
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest
from mostlyright.core.exceptions import NoLiveDataError
from mostlyright.live import latest


def _run(coro: Any) -> Any:
    """Run an async coroutine in a fresh event loop and return its result."""
    return asyncio.run(coro)


def _awc_metar(
    obs_time: int, raw_ob: str = "KNYC 251200Z 18010KT 10SM CLR 20/10 A3010"
) -> dict[str, Any]:
    """Minimal AWC METAR dict that `awc_to_observation` will accept."""
    return {
        "icaoId": "KNYC",
        "obsTime": obs_time,
        "metarType": "METAR",
        "temp": 20.0,
        "dewp": 10.0,
        "rawOb": raw_ob,
    }


def _iem_csv_row(station: str = "NYC", valid: str = "2026-05-25 12:00") -> dict[str, str]:
    """Minimal IEM CSV row dict that `iem_to_observation` will accept."""
    return {
        "station": station,
        "valid": valid,
        "tmpf": "68.0",
        "dwpf": "50.0",
        "drct": "180",
        "sknt": "10",
        "gust": "M",
        "alti": "30.10",
        "mslp": "M",
        "vsby": "10.00",
        "skyc1": "CLR",
        "skyl1": "M",
        "skyc2": "M",
        "skyl2": "M",
        "skyc3": "M",
        "skyl3": "M",
        "skyc4": "M",
        "skyl4": "M",
        "wxcodes": "",
        "metar": "KNYC 251200Z 18010KT 10SM CLR 20/10 A3010",
    }


# ----------------------------------------------------------------------
# Tests
# ----------------------------------------------------------------------


def test_latest_awc_returns_observation_row(monkeypatch: pytest.MonkeyPatch) -> None:
    """AWC poll returns one parsed observation row tagged source=awc.live."""

    def fake_fetch_awc(stations: list[str], hours: int) -> list[dict[str, Any]]:
        return [_awc_metar(1748174400)]  # 2025-05-25T12:00:00Z

    monkeypatch.setattr(
        "mostlyright.weather._fetchers.awc.fetch_awc_metars",
        fake_fetch_awc,
    )
    row = _run(latest("KNYC"))
    assert row["station_code"] == "NYC"
    assert row["source"] == "awc.live"
    assert "observed_at" in row
    assert row["temp_c"] is not None


def test_latest_awc_default_source(monkeypatch: pytest.MonkeyPatch) -> None:
    """No source= kwarg → defaults to AWC."""
    called = {"awc": False, "iem": False}

    def fake_awc(stations: list[str], hours: int) -> list[dict[str, Any]]:
        called["awc"] = True
        return [_awc_metar(1748174400)]

    def fake_iem(*args: Any, **kwargs: Any) -> list[Any]:
        called["iem"] = True
        return []

    monkeypatch.setattr(
        "mostlyright.weather._fetchers.awc.fetch_awc_metars",
        fake_awc,
    )
    monkeypatch.setattr(
        "mostlyright.weather._fetchers.iem_asos.download_iem_asos",
        fake_iem,
    )
    _run(latest("KNYC"))  # no source= kwarg
    assert called["awc"] is True
    assert called["iem"] is False


def test_latest_iem_source_selectable(monkeypatch: pytest.MonkeyPatch) -> None:
    """source='iem' invokes IEM path, not AWC."""
    called = {"awc": False, "iem": False}

    def fake_awc(*args: Any, **kwargs: Any) -> list[Any]:
        called["awc"] = True
        return []

    # Patch the high-level IEM fetch to bypass actual HTTP + filesystem
    async def fake_iem_latest(station: str) -> list[dict[str, Any]]:
        called["iem"] = True
        from mostlyright.weather._iem import iem_to_observation

        obs = iem_to_observation(_iem_csv_row(), observation_type_override="METAR")
        assert obs is not None
        obs["source"] = "iem.live"
        return [obs]

    monkeypatch.setattr(
        "mostlyright.weather._fetchers.awc.fetch_awc_metars",
        fake_awc,
    )
    monkeypatch.setattr(
        "mostlyright.live._latest._fetch_iem_latest",
        fake_iem_latest,
    )
    row = _run(latest("KNYC", source="iem"))
    assert called["awc"] is False
    assert called["iem"] is True
    assert row["source"] == "iem.live"


def test_latest_unknown_source_raises() -> None:
    """source='ghcnh' raises ValueError."""
    with pytest.raises(ValueError, match="unknown live source"):
        _run(latest("KNYC", source="ghcnh"))


def test_latest_empty_response_raises_no_live_data(monkeypatch: pytest.MonkeyPatch) -> None:
    """Empty fetcher response → NoLiveDataError."""

    def fake_fetch(stations: list[str], hours: int) -> list[Any]:
        return []

    monkeypatch.setattr(
        "mostlyright.weather._fetchers.awc.fetch_awc_metars",
        fake_fetch,
    )
    with pytest.raises(NoLiveDataError) as exc_info:
        _run(latest("KNYC"))
    assert "KNYC" in str(exc_info.value)


def test_latest_no_live_data_error_carries_station_and_source(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """NoLiveDataError.to_dict() includes station + source on payload."""

    def fake_fetch(stations: list[str], hours: int) -> list[Any]:
        return []

    monkeypatch.setattr(
        "mostlyright.weather._fetchers.awc.fetch_awc_metars",
        fake_fetch,
    )
    with pytest.raises(NoLiveDataError) as exc_info:
        _run(latest("knyc"))  # lowercase to verify normalization
    payload = exc_info.value.to_dict()
    assert payload["station"] == "KNYC"
    assert payload["source"] == "awc.live"
    assert payload["error_code"] == "NO_LIVE_DATA"


def test_latest_returns_most_recent_when_multiple(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fetcher returns 3 METARs at different times → latest() picks the largest observed_at."""

    def fake_fetch(stations: list[str], hours: int) -> list[dict[str, Any]]:
        return [
            _awc_metar(1748170800),  # earlier
            _awc_metar(1748174400),  # latest (largest obsTime)
            _awc_metar(1748171800),  # middle
        ]

    monkeypatch.setattr(
        "mostlyright.weather._fetchers.awc.fetch_awc_metars",
        fake_fetch,
    )
    row = _run(latest("KNYC"))
    # The chosen row must be the one corresponding to 1748174400 — the
    # largest input obsTime. observed_at strings sort chronologically,
    # so this row's observed_at exceeds the other two.
    assert row["observed_at"] == "2025-05-25T12:00:00Z"


def test_latest_strips_unparseable_metars(monkeypatch: pytest.MonkeyPatch) -> None:
    """Mixed valid+invalid METARs → only valid one is returned."""

    def fake_fetch(stations: list[str], hours: int) -> list[dict[str, Any]]:
        bad = {"icaoId": "", "obsTime": 0}  # blank icao → awc_to_observation returns None
        good = _awc_metar(1748174400)
        return [bad, good]

    monkeypatch.setattr(
        "mostlyright.weather._fetchers.awc.fetch_awc_metars",
        fake_fetch,
    )
    row = _run(latest("KNYC"))
    assert row["station_code"] == "NYC"
    assert row["source"] == "awc.live"


def test_latest_iem_construction_does_not_raise(monkeypatch: pytest.MonkeyPatch) -> None:
    """End-to-end IEM path: constructs StationInfo + invokes parser without raising.

    Regression test for the iter-1 codex finding: `_fetch_iem_latest` was
    constructing `StationInfo(tz="UTC")` which raised `TypeError` because
    the dataclass requires `timezone`/`utc_offset_standard`/`latitude`/`longitude`
    (not `tz`). The bug never surfaced earlier because the IEM source tests
    mocked `_fetch_iem_latest` itself rather than its dependencies.

    Here we mock at the LAYER BELOW — `download_iem_asos` + `parse_iem_file` —
    so the StationInfo construction inside `_fetch_iem_latest` actually runs.
    """
    from pathlib import Path
    from pathlib import Path as _PathType  # noqa: F401  (Path imported in outer scope)

    captured: dict[str, Any] = {}

    def fake_download(
        station: Any,
        start: Any,
        end: Any,
        dest_dir: Path,
        **kwargs: Any,
    ) -> list[Path]:
        # Verify the StationInfo construction worked (no TypeError raised)
        # AND that the fields download_iem_asos reads are correctly populated.
        assert station.code == "NYC"
        assert station.icao == "KNYC"
        # Sentinel values for the remaining required fields — must not crash.
        assert station.timezone == "UTC"
        captured["start"] = start
        captured["end"] = end
        return []  # empty CSV → latest() will raise NoLiveDataError

    def fake_parse(path: Path, observation_type_override: str | None = None) -> list[Any]:
        return []

    monkeypatch.setattr(
        "mostlyright.weather._fetchers.iem_asos.download_iem_asos",
        fake_download,
    )
    monkeypatch.setattr(
        "mostlyright.weather._iem.parse_iem_file",
        fake_parse,
    )
    with pytest.raises(NoLiveDataError):
        _run(latest("KNYC", source="iem"))

    # Window assertion. After iter-2 we passed (today, today). After iter-4
    # codex P2 (previous-day fallback), the window is (yesterday, today) so
    # the [yesterday 00:00Z, today 24:00Z) span catches a minutes-old METAR
    # even right after the 00:00 UTC rollover. Asserting both:
    # - start == yesterday (proves the previous-day inclusion)
    # - end == today      (proves we did NOT regress to (today, tomorrow))
    from datetime import UTC
    from datetime import date as _date
    from datetime import datetime as _dt

    today_utc = _dt.now(UTC).date()
    yesterday_utc = _date.fromordinal(today_utc.toordinal() - 1)
    assert captured["start"] == yesterday_utc
    assert captured["end"] == today_utc


def test_latest_iem_fetches_metar_and_speci(monkeypatch: pytest.MonkeyPatch) -> None:
    """Regression for iter-3 codex finding: IEM strips the SPECI keyword
    from raw METAR text and serves SPECIs ONLY via report_type=4. Without
    a separate report_type=4 fetch, the IEM live path silently misses
    intra-hour specials and `_pick_most_recent` could return a stale METAR.

    Fix issues BOTH report_type=3 and report_type=4 per poll. This test
    captures the report_type values passed to `download_iem_asos` and
    asserts BOTH appear.
    """
    from pathlib import Path

    seen_report_types: list[int] = []

    def fake_download(
        station: Any,
        start: Any,
        end: Any,
        dest_dir: Path,
        **kwargs: Any,
    ) -> list[Path]:
        seen_report_types.append(kwargs.get("report_type"))
        return []

    def fake_parse(path: Path, observation_type_override: str | None = None) -> list[Any]:
        return []

    monkeypatch.setattr(
        "mostlyright.weather._fetchers.iem_asos.download_iem_asos",
        fake_download,
    )
    monkeypatch.setattr(
        "mostlyright.weather._iem.parse_iem_file",
        fake_parse,
    )
    with pytest.raises(NoLiveDataError):
        _run(latest("KNYC", source="iem"))

    assert 3 in seen_report_types  # routine METAR fetch
    assert 4 in seen_report_types  # SPECI fetch — the regression target

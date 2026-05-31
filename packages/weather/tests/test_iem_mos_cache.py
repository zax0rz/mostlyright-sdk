"""Phase 24-03: per-runtime disk cache + 404 negative-cache for IEM MOS.

``fetch_iem_mos`` GETs every runtime live and sleeps ``_MOS_POLITE_DELAY_S``
per runtime — including 1s per 404. For a historical backfill every runtime
is immutable, so a warm re-run should fire ZERO GETs and ZERO sleeps.

These tests isolate the cache root under a tmp dir and freeze
``datetime.now`` so the freshness guard (COMPLETION_LAG) is deterministic.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import httpx
import pytest
from mostlyright.weather._fetchers import _iem_mos
from mostlyright.weather._fetchers._iem_mos import fetch_iem_mos

# A frozen "now" far after the requested windows so every runtime is
# strictly older than now - COMPLETION_LAG (i.e. cacheable).
_FROZEN_NOW = datetime(2026, 5, 28, 12, 0, 0, tzinfo=UTC)

_SAMPLE_PAYLOAD = {
    "data": [
        {
            "runtime": "2026-05-01T00:00:00Z",
            "ftime": "2026-05-01T06:00:00Z",
            "station": "KNYC",
            "tmp": 68.0,
            "dpt": 50.0,
            "wsp": 10.0,
            "wdr": 270,
            "pop12": 25.0,
        }
    ]
}


def _freeze_now(monkeypatch: pytest.MonkeyPatch, when: datetime = _FROZEN_NOW) -> None:
    class _Frozen(datetime):
        @classmethod
        def now(cls, tz: Any = None) -> datetime:  # type: ignore[override]
            return when if tz is None else when.astimezone(tz)

    monkeypatch.setattr(_iem_mos, "datetime", _Frozen)


def _spy_sleep(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    calls: list[float] = []
    monkeypatch.setattr(_iem_mos.time, "sleep", lambda s: calls.append(s))
    return calls


def _mock_client(payload: dict | None = None, status: int = 200) -> MagicMock:
    mock = MagicMock()

    def _get(_url: str, params: dict | None = None) -> MagicMock:
        resp = MagicMock()
        resp.status_code = status
        if status == 200:
            resp.json = MagicMock(return_value=payload or {"data": []})
            resp.raise_for_status = MagicMock()
        else:
            resp.raise_for_status = MagicMock(
                side_effect=httpx.HTTPStatusError(f"{status}", request=None, response=None)  # type: ignore[arg-type]
            )
        return resp

    mock.get = MagicMock(side_effect=_get)
    return mock


def _isolate_cache(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    # Canonical env var is MOSTLYRIGHT_CACHE_DIR (see _cache_dir.py). Point
    # the cache root at a tmp dir so tests never touch ~/.mostlyright/cache.
    monkeypatch.setenv("MOSTLYRIGHT_CACHE_DIR", str(tmp_path))
    monkeypatch.delenv("TRADEWINDS_CACHE_DIR", raising=False)


def test_cold_miss_fires_get_writes_cache_and_sleeps(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _isolate_cache(monkeypatch, tmp_path)
    _freeze_now(monkeypatch)
    sleeps = _spy_sleep(monkeypatch)
    client = _mock_client(_SAMPLE_PAYLOAD)

    df = fetch_iem_mos("KNYC", "2026-05-01", "2026-05-01", model="nbe", client=client)

    # nbe post-cutover hours {0,6,12,18} -> 4 runtimes in the single-day window.
    assert client.get.call_count == 4
    assert len(sleeps) == 4
    assert not df.empty
    # A parquet was written somewhere under the forecasts/iem_mos tier.
    written = list(tmp_path.rglob("forecasts/iem_mos/**/*.parquet"))
    assert written, "cold miss did not write a per-runtime parquet"


def test_warm_hit_skips_get_and_sleep(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _isolate_cache(monkeypatch, tmp_path)
    _freeze_now(monkeypatch)
    sleeps = _spy_sleep(monkeypatch)

    cold_client = _mock_client(_SAMPLE_PAYLOAD)
    df_cold = fetch_iem_mos("KNYC", "2026-05-01", "2026-05-01", model="nbe", client=cold_client)

    warm_client = _mock_client(_SAMPLE_PAYLOAD)
    sleeps.clear()
    df_warm = fetch_iem_mos("KNYC", "2026-05-01", "2026-05-01", model="nbe", client=warm_client)

    assert warm_client.get.call_count == 0, "warm hit re-fetched over HTTP"
    assert sleeps == [], "warm hit paid the politeness sleep"
    assert len(df_warm) == len(df_cold)


def test_404_negative_cache_for_past_runtime(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _isolate_cache(monkeypatch, tmp_path)
    _freeze_now(monkeypatch)
    sleeps = _spy_sleep(monkeypatch)

    cold_client = _mock_client(status=404)
    df_cold = fetch_iem_mos("KNYC", "2026-05-01", "2026-05-01", model="nbe", client=cold_client)
    assert cold_client.get.call_count == 4
    assert df_cold.empty

    warm_client = _mock_client(status=404)
    sleeps.clear()
    df_warm = fetch_iem_mos("KNYC", "2026-05-01", "2026-05-01", model="nbe", client=warm_client)
    assert warm_client.get.call_count == 0, "404 negative-cache did not suppress re-GET"
    assert sleeps == [], "404 negative-cache did not suppress the sleep"
    assert df_warm.empty


def test_near_now_runtime_bypasses_cache(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _isolate_cache(monkeypatch, tmp_path)
    # Freeze now to early in the requested day so every runtime ({1,7,13,19}Z
    # pre-cutover) is within COMPLETION_LAG of now (still maturing) -> none
    # cacheable -> all fetched live, none written to cache.
    _freeze_now(monkeypatch, when=datetime(2026, 5, 1, 2, 0, 0, tzinfo=UTC))
    _spy_sleep(monkeypatch)
    client = _mock_client(_SAMPLE_PAYLOAD)

    fetch_iem_mos("KNYC", "2026-05-01", "2026-05-01", model="nbe", client=client)

    assert client.get.call_count > 0, "near-now runtime should still fetch live"
    written = list(tmp_path.rglob("forecasts/iem_mos/**/*"))
    assert [p for p in written if p.is_file()] == [], "near-now runtime must not be cached"


def test_warm_output_equivalent_to_cold(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _isolate_cache(monkeypatch, tmp_path)
    _freeze_now(monkeypatch)
    _spy_sleep(monkeypatch)

    cold = fetch_iem_mos(
        "KNYC", "2026-05-01", "2026-05-02", model="nbe", client=_mock_client(_SAMPLE_PAYLOAD)
    )
    warm = fetch_iem_mos(
        "KNYC", "2026-05-01", "2026-05-02", model="nbe", client=_mock_client(_SAMPLE_PAYLOAD)
    )

    assert list(cold.columns) == list(warm.columns)
    assert [str(d) for d in cold.dtypes] == [str(d) for d in warm.dtypes]
    assert cold.attrs["source"] == warm.attrs["source"] == "iem.archive"

    sort_cols = ["issued_at", "valid_at"]
    cold_sorted = cold.sort_values(sort_cols).reset_index(drop=True)
    warm_sorted = warm.sort_values(sort_cols).reset_index(drop=True)
    import pandas.testing as pdt

    pdt.assert_frame_equal(cold_sorted, warm_sorted, check_like=True)

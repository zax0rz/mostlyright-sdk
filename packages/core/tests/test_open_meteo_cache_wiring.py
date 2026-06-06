"""Issue #64 Fix 1: ``_fetch_open_meteo_range`` reads and writes the
Phase-20 forecast cache.

Previous-runs / single-runs / seamless forecast data is immutable, but the
cache built in Phase 20 OM-06 had no production caller. A second call to
``research(..., forecast_source="open_meteo")`` with the same args must
serve the cached parquet rather than re-fetching.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import patch

import pandas as pd
import pytest
from mostlyright._internal._stations import STATIONS


def _fake_om_payload_df(from_date: str, to_date: str) -> pd.DataFrame:
    """Build a minimal Open-Meteo response DataFrame across [from_date, to_date]."""
    rows: list[dict[str, Any]] = []
    cur = pd.Timestamp(from_date, tz="UTC")
    end = pd.Timestamp(to_date, tz="UTC") + pd.Timedelta(days=1)
    while cur < end:
        rows.append(
            {
                "station": "KNYC",
                "issued_at": cur - pd.Timedelta(days=1),
                "valid_at": cur,
                "forecast_hour": 24,
                "model": "gfs_global",
                "source": "open_meteo.previous_runs",
                "temp_c": 20.0,
                "dew_point_c": None,
                "wind_speed_ms": None,
                "wind_dir_deg": None,
                "precip_probability": 0.10,
                "sky_cover_pct": None,
                "apparent_temp_c": None,
                "shortwave_radiation_wm2": None,
                "direct_radiation_wm2": None,
                "cape_jkg": None,
                "precipitation_mm": 0.5,
                "cloud_cover_pct": None,
                "surface_pressure_hpa": None,
                "pressure_msl_hpa": None,
                "freezing_level_m": None,
                "snow_depth_m": None,
                "visibility_m": None,
                "wind_gusts_ms": None,
                "weather_code": None,
                "retrieved_at": pd.Timestamp.now(tz="UTC"),
            }
        )
        cur = cur + pd.Timedelta(hours=1)
    return pd.DataFrame(rows)


def test_fetch_open_meteo_range_writes_forecast_cache(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """First call must hit fetch_open_meteo AND populate the cache parquet."""
    monkeypatch.setenv("MOSTLYRIGHT_CACHE_DIR", str(tmp_path))
    from mostlyright.research import _fetch_open_meteo_range

    info = STATIONS["NYC"]
    df = _fake_om_payload_df("2024-06-01", "2024-06-02")

    call_count = {"n": 0}

    def fake_fetch(*args: Any, **kwargs: Any) -> pd.DataFrame:
        call_count["n"] += 1
        return df

    with patch(
        "mostlyright.weather._fetchers._open_meteo.fetch_open_meteo",
        side_effect=fake_fetch,
    ):
        out = _fetch_open_meteo_range(info, "2024-06-01", "2024-06-02", model="gfs_global")

    assert call_count["n"] >= 1
    assert out  # produced some dates
    # Cache file must exist for the 2024-06 partition.
    from mostlyright.weather.cache import forecast_cache_path

    cache_file = forecast_cache_path("KNYC", "open_meteo.previous_runs", "gfs_global", 2024, 6)
    assert cache_file.exists(), f"expected cache parquet at {cache_file}"


def test_fetch_open_meteo_range_second_call_uses_cache(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Second call with the same args must serve from cache (no fetch_open_meteo)."""
    monkeypatch.setenv("MOSTLYRIGHT_CACHE_DIR", str(tmp_path))
    from mostlyright.research import _fetch_open_meteo_range

    info = STATIONS["NYC"]
    df = _fake_om_payload_df("2024-06-01", "2024-06-02")

    call_count = {"n": 0}

    def fake_fetch(*args: Any, **kwargs: Any) -> pd.DataFrame:
        call_count["n"] += 1
        return df

    with patch(
        "mostlyright.weather._fetchers._open_meteo.fetch_open_meteo",
        side_effect=fake_fetch,
    ):
        _fetch_open_meteo_range(info, "2024-06-01", "2024-06-02", model="gfs_global")
        first_n = call_count["n"]
        # Second call — exactly the same args.
        out2 = _fetch_open_meteo_range(info, "2024-06-01", "2024-06-02", model="gfs_global")

    assert first_n >= 1
    # Second call must NOT increment call_count — cache hit.
    assert call_count["n"] == first_n, (
        f"second call refetched: count went {first_n} -> {call_count['n']}"
    )
    # And it must still return non-empty groups.
    assert out2


def test_fetch_open_meteo_range_trims_to_three_pairs_variables(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Research path must request only the 3 pairs-join variables, not all 18."""
    monkeypatch.setenv("MOSTLYRIGHT_CACHE_DIR", str(tmp_path))
    from mostlyright.research import _fetch_open_meteo_range

    info = STATIONS["NYC"]
    df = _fake_om_payload_df("2024-06-01", "2024-06-02")

    captured: list[dict[str, Any]] = []

    def fake_fetch(*args: Any, **kwargs: Any) -> pd.DataFrame:
        captured.append(dict(kwargs))
        return df

    with patch(
        "mostlyright.weather._fetchers._open_meteo.fetch_open_meteo",
        side_effect=fake_fetch,
    ):
        _fetch_open_meteo_range(info, "2024-06-01", "2024-06-02", model="gfs_global")

    assert captured, "expected fetch_open_meteo to be called"
    vars_passed = captured[0].get("variables")
    assert vars_passed is not None, "expected variables= kwarg on the research path"
    assert set(vars_passed) == {
        "temperature_2m",
        "precipitation",
        "precipitation_probability",
    }


def test_fetch_open_meteo_range_partial_cache_hit(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """If June and August are missing but July is cached, the fetch span covers [June, August].
    Only June and August records are added from the fetch result, and July is served from cache,
    ensuring no duplicate July records are added to all_rows.
    """
    monkeypatch.setenv("MOSTLYRIGHT_CACHE_DIR", str(tmp_path))
    from mostlyright.research import _fetch_open_meteo_range
    from mostlyright.weather.cache import forecast_cache_path, write_forecast_cache

    info = STATIONS["NYC"]
    model = "gfs_global"
    source = "open_meteo.previous_runs"

    # Pre-cache July 2024
    july_cached_rows = [
        {
            "station": "KNYC",
            "issued_at": pd.Timestamp("2024-07-15T12:00:00Z"),
            "valid_at": pd.Timestamp("2024-07-16T12:00:00Z"),
            "model": model,
            "source": source,
            "temp_c": 25.0,
            "precip_probability": 0.0,
            "precipitation_mm": 0.0,
        }
    ]
    write_forecast_cache(
        "KNYC",
        source,
        model,
        2024,
        7,
        july_cached_rows,
        from_date="2024-07-01",
        to_date="2024-07-31",
    )

    # June & August fetched data
    june_rows = _fake_om_payload_df("2024-06-15", "2024-06-15")
    august_rows = _fake_om_payload_df("2024-08-15", "2024-08-15")
    # The fetcher returns the whole fetched DataFrame including July data
    july_fetched_rows = _fake_om_payload_df("2024-07-15", "2024-07-15")
    df_fetched = pd.concat([june_rows, july_fetched_rows, august_rows], ignore_index=True)

    captured: list[dict[str, Any]] = []

    def fake_fetch(*args: Any, **kwargs: Any) -> pd.DataFrame:
        captured.append(kwargs)
        return df_fetched

    with patch(
        "mostlyright.weather._fetchers._open_meteo.fetch_open_meteo",
        side_effect=fake_fetch,
    ):
        # Request June to August
        out = _fetch_open_meteo_range(info, "2024-06-01", "2024-08-31", model=model)

    assert len(captured) == 1
    # Check that June and August caches are written
    assert forecast_cache_path("KNYC", source, model, 2024, 6).exists()
    assert forecast_cache_path("KNYC", source, model, 2024, 8).exists()

    # The returned July date must correspond to the CACHED July data (temp_c=25.0 -> temperature_f=77.0)
    # and NOT the fetched July data (temp_c=20.0 -> temperature_f=68.0).
    july_fcst_rows = out.get("2024-07-16", [])
    assert july_fcst_rows, "July forecast rows must exist"
    # Ensure there is exactly 1 July row, not duplicates
    assert len(july_fcst_rows) == 1
    assert july_fcst_rows[0]["temperature_f"] == pytest.approx(77.0)


def test_fetch_open_meteo_range_handles_nat(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Rows with pd.NaT valid_at or issued_at must be handled gracefully without crashing."""
    monkeypatch.setenv("MOSTLYRIGHT_CACHE_DIR", str(tmp_path))
    from mostlyright.research import _fetch_open_meteo_range

    info = STATIONS["NYC"]
    model = "gfs_global"

    df_with_nat = _fake_om_payload_df("2024-06-01", "2024-06-02")
    # Inject NaT values
    df_with_nat.loc[0, "valid_at"] = pd.NaT
    df_with_nat.loc[1, "issued_at"] = pd.NaT

    def fake_fetch(*args: Any, **kwargs: Any) -> pd.DataFrame:
        return df_with_nat

    with patch(
        "mostlyright.weather._fetchers._open_meteo.fetch_open_meteo",
        side_effect=fake_fetch,
    ):
        out = _fetch_open_meteo_range(info, "2024-06-01", "2024-06-02", model=model)

    # Should run to completion and produce some non-empty results for the non-NaT valid_at rows
    assert out


# ---------------------------------------------------------------------------
# Coverage metadata tests (fix/66)
# ---------------------------------------------------------------------------


def test_forecast_cache_partial_month_triggers_refetch(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Cache June 1-2, then request June 15-20 → cache miss, full month re-fetched."""
    monkeypatch.setenv("MOSTLYRIGHT_CACHE_DIR", str(tmp_path))
    from mostlyright.research import _fetch_open_meteo_range
    from mostlyright.weather.cache import forecast_cache_path, write_forecast_cache

    info = STATIONS["NYC"]
    model = "gfs_global"
    source = "open_meteo.previous_runs"

    # Simulate broken PR #66 state: partition with metadata covering only June 1-2.
    partial_rows = [
        {
            "station": "KNYC",
            "issued_at": pd.Timestamp("2024-05-31T12:00:00Z"),
            "valid_at": pd.Timestamp("2024-06-01T12:00:00Z"),
            "model": model,
            "source": source,
            "temp_c": 20.0,
            "precip_probability": 0.0,
            "precipitation_mm": 0.0,
        }
    ]
    write_forecast_cache(
        "KNYC", source, model, 2024, 6, partial_rows, from_date="2024-06-01", to_date="2024-06-02"
    )

    # Full-month fetch returns data covering June 1-30.
    full_june_df = _fake_om_payload_df("2024-06-01", "2024-06-30")
    call_count = {"n": 0}

    def fake_fetch(*args: Any, **kwargs: Any) -> pd.DataFrame:
        call_count["n"] += 1
        return full_june_df

    with patch(
        "mostlyright.weather._fetchers._open_meteo.fetch_open_meteo",
        side_effect=fake_fetch,
    ):
        out = _fetch_open_meteo_range(info, "2024-06-15", "2024-06-20", model=model)

    assert call_count["n"] == 1, "expected exactly one network fetch"
    assert out, "expected non-empty result for June 15-20"

    # Partition must be overwritten with full-month metadata.
    import pyarrow.parquet as pq
    from mostlyright.weather.cache import _FORECAST_CACHE_FROM_KEY, _FORECAST_CACHE_TO_KEY

    table = pq.read_table(forecast_cache_path("KNYC", source, model, 2024, 6))
    md = table.schema.metadata or {}
    assert md.get(_FORECAST_CACHE_FROM_KEY) == b"2024-06-01"
    assert md.get(_FORECAST_CACHE_TO_KEY) == b"2024-06-30"


def test_forecast_cache_full_month_hit_no_refetch(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Full-month partition → any subrange request is served from cache, no network call."""
    monkeypatch.setenv("MOSTLYRIGHT_CACHE_DIR", str(tmp_path))
    from mostlyright.research import _fetch_open_meteo_range
    from mostlyright.weather.cache import write_forecast_cache

    info = STATIONS["NYC"]
    model = "gfs_global"
    source = "open_meteo.previous_runs"

    # Pre-cache all of June with full-month metadata.
    june_rows = [
        {
            "station": "KNYC",
            "issued_at": pd.Timestamp(f"2024-06-{d:02d}T00:00:00Z") - pd.Timedelta(days=1),
            "valid_at": pd.Timestamp(f"2024-06-{d:02d}T12:00:00Z"),
            "model": model,
            "source": source,
            "temp_c": float(d),
            "precip_probability": 0.0,
            "precipitation_mm": 0.0,
        }
        for d in range(1, 31)
    ]
    write_forecast_cache(
        "KNYC", source, model, 2024, 6, june_rows, from_date="2024-06-01", to_date="2024-06-30"
    )

    call_count = {"n": 0}

    def fake_fetch(*args: Any, **kwargs: Any) -> pd.DataFrame:
        call_count["n"] += 1
        return _fake_om_payload_df("2024-06-01", "2024-06-30")

    with patch(
        "mostlyright.weather._fetchers._open_meteo.fetch_open_meteo",
        side_effect=fake_fetch,
    ):
        out = _fetch_open_meteo_range(info, "2024-06-01", "2024-06-20", model=model)

    assert call_count["n"] == 0, "full-month cache hit should not trigger any network fetch"
    assert out, "expected non-empty result"


def test_forecast_cache_backwards_compat_no_metadata(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Partition written without range metadata (old code) → treated as miss, re-fetched, repaired."""
    monkeypatch.setenv("MOSTLYRIGHT_CACHE_DIR", str(tmp_path))
    from mostlyright.research import _fetch_open_meteo_range
    from mostlyright.weather.cache import (
        _FORECAST_CACHE_FROM_KEY,
        _FORECAST_CACHE_TO_KEY,
        forecast_cache_path,
        write_forecast_cache,
    )

    info = STATIONS["NYC"]
    model = "gfs_global"
    source = "open_meteo.previous_runs"

    # Write partition the old way — no from_date/to_date kwargs → no range metadata.
    old_rows = [
        {
            "station": "KNYC",
            "issued_at": pd.Timestamp("2024-06-01T00:00:00Z"),
            "valid_at": pd.Timestamp("2024-06-01T12:00:00Z"),
            "model": model,
            "source": source,
            "temp_c": 20.0,
            "precip_probability": 0.0,
            "precipitation_mm": 0.0,
        }
    ]
    write_forecast_cache("KNYC", source, model, 2024, 6, old_rows)

    # Verify: no metadata in the file we just wrote.
    import pyarrow.parquet as pq

    old_table = pq.read_table(forecast_cache_path("KNYC", source, model, 2024, 6))
    assert _FORECAST_CACHE_FROM_KEY not in (old_table.schema.metadata or {})

    full_june_df = _fake_om_payload_df("2024-06-01", "2024-06-30")
    call_count = {"n": 0}

    def fake_fetch(*args: Any, **kwargs: Any) -> pd.DataFrame:
        call_count["n"] += 1
        return full_june_df

    with patch(
        "mostlyright.weather._fetchers._open_meteo.fetch_open_meteo",
        side_effect=fake_fetch,
    ):
        _fetch_open_meteo_range(info, "2024-06-01", "2024-06-15", model=model)

    assert call_count["n"] == 1, "old partition without metadata must trigger re-fetch"

    # After re-fetch, partition must have range metadata.
    new_table = pq.read_table(forecast_cache_path("KNYC", source, model, 2024, 6))
    md = new_table.schema.metadata or {}
    assert md.get(_FORECAST_CACHE_FROM_KEY) == b"2024-06-01"
    assert md.get(_FORECAST_CACHE_TO_KEY) == b"2024-06-30"


def test_forecast_cache_current_month_never_cached(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Current UTC month is never written to or served from cache."""
    monkeypatch.setenv("MOSTLYRIGHT_CACHE_DIR", str(tmp_path))
    from datetime import UTC, datetime

    from mostlyright.research import _fetch_open_meteo_range
    from mostlyright.weather.cache import forecast_cache_path

    info = STATIONS["NYC"]
    model = "gfs_global"
    source = "open_meteo.previous_runs"

    now = datetime.now(UTC)
    cur_year, cur_month = now.year, now.month
    from_iso = f"{cur_year}-{cur_month:02d}-01"
    to_iso = f"{cur_year}-{cur_month:02d}-05"

    df = _fake_om_payload_df(from_iso, to_iso)

    def fake_fetch(*args: Any, **kwargs: Any) -> pd.DataFrame:
        return df

    with patch(
        "mostlyright.weather._fetchers._open_meteo.fetch_open_meteo",
        side_effect=fake_fetch,
    ):
        _fetch_open_meteo_range(info, from_iso, to_iso, model=model)

    # No cache file should be written for the current UTC month.
    cache_file = forecast_cache_path("KNYC", source, model, cur_year, cur_month)
    assert not cache_file.exists(), "current UTC month must never be cached"

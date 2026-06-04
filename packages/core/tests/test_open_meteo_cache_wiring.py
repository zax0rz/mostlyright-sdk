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
    write_forecast_cache("KNYC", source, model, 2024, 7, july_cached_rows)

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

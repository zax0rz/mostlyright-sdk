"""Phase 17 PLAN-09: research(include_forecast=True) Mode 1 + Mode 2 wiring.

Mode 1 = IEM MOS (parity-compatible additive ``fcst_*`` columns).
Mode 2 = NWP per-model (``forecast_models=["hrrr"]`` adds ``fcst_*_nwp_<model>``).

Tests use ``unittest.mock.patch`` so they run offline. The 5 byte-equivalent
parity fixtures (``tests/test_parity.py``) cover ``include_forecast=False``
end-to-end.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import mostlyright
import pandas as pd
import pytest


# ----------------------------------------------------------------------
# Fixtures: mock observation + climate row builders that bypass HTTP.
# ----------------------------------------------------------------------
def _fake_obs_row(station: str, observed_at: str, temp_f: float) -> dict[str, Any]:
    return {
        "station_code": station,
        "observed_at": observed_at,
        "temp_f": temp_f,
        "dewpoint_f": temp_f - 10.0,
        "wind_speed_kt": 5.0,
        "wind_gust_kt": None,
        "precip_1hr_inches": None,
        "source": "iem.archive",
        "report_type_priority": 1,
        "raw_metar": "KNYC ...",
    }


def _fake_climate_row(station: str, date_iso: str, high_f: float, low_f: float) -> dict[str, Any]:
    return {
        "station_code": station,
        "observation_date": date_iso,
        "high_temp_f": high_f,
        "low_temp_f": low_f,
        "report_type": "PR",
        "report_type_priority": 4,
        "source": "iem",
    }


def _fake_iem_mos_df() -> pd.DataFrame:
    """Two MOS rows whose valid_at lands inside the KNYC 2025-01-06 settlement window."""
    return pd.DataFrame(
        [
            {
                "station": "KNYC",
                "issued_at": pd.Timestamp("2025-01-06T00:00:00Z"),
                "valid_at": pd.Timestamp("2025-01-06T18:00:00Z"),
                "forecast_hour": 18,
                "model": "NBE",
                "temp_c": 5.0,  # 41 F
                "dew_point_c": -2.0,
                "wind_speed_ms": 3.0,
                "wind_dir_deg": 180,
                "precip_probability": 0.25,
                "sky_cover_pct": None,
                "source": "iem.archive",
                "retrieved_at": pd.Timestamp("2025-01-06T01:00:00Z"),
            },
            {
                "station": "KNYC",
                "issued_at": pd.Timestamp("2025-01-06T00:00:00Z"),
                "valid_at": pd.Timestamp("2025-01-06T21:00:00Z"),
                "forecast_hour": 21,
                "model": "NBE",
                "temp_c": 7.0,  # 44.6 F
                "dew_point_c": -1.0,
                "wind_speed_ms": 4.0,
                "wind_dir_deg": 190,
                "precip_probability": 0.30,
                "sky_cover_pct": None,
                "source": "iem.archive",
                "retrieved_at": pd.Timestamp("2025-01-06T01:00:00Z"),
            },
        ]
    )


def _fake_nwp_df() -> pd.DataFrame:
    """HRRR-style row for KNYC 2025-01-06."""
    return pd.DataFrame(
        [
            {
                "station": "KNYC",
                "model": "hrrr",
                "mirror": "aws_bdp",
                "grid_kind": "ncep_native",
                "issued_at": pd.Timestamp("2025-01-06T12:00:00Z"),
                "valid_at": pd.Timestamp("2025-01-06T18:00:00Z"),
                "forecast_hour": 6,
                "grid_dist_km": 0.5,
                "temp_k_2m": 280.0,  # ~ 44.3 F
                "dewpoint_k_2m": 273.0,
                "relative_humidity_pct_2m": 80.0,
                "wind_u_ms_10m": 1.0,
                "wind_v_ms_10m": 0.0,
                "wind_gust_ms": 3.0,
                "precip_mm_1h": 0.0,
                "pressure_pa_surface": 101_000.0,
                "pressure_pa_mslp": 101_500.0,
                "qc_status": "clean",
                "retrieved_at": pd.Timestamp("2025-01-06T13:00:00Z"),
                "source": "noaa_bdp",
            },
            {
                "station": "KNYC",
                "model": "hrrr",
                "mirror": "aws_bdp",
                "grid_kind": "ncep_native",
                "issued_at": pd.Timestamp("2025-01-06T12:00:00Z"),
                "valid_at": pd.Timestamp("2025-01-06T21:00:00Z"),
                "forecast_hour": 9,
                "grid_dist_km": 0.5,
                "temp_k_2m": 285.0,  # ~ 53.3 F
                "dewpoint_k_2m": 275.0,
                "relative_humidity_pct_2m": 75.0,
                "wind_u_ms_10m": 2.0,
                "wind_v_ms_10m": 1.0,
                "wind_gust_ms": 4.0,
                "precip_mm_1h": 0.0,
                "pressure_pa_surface": 101_000.0,
                "pressure_pa_mslp": 101_500.0,
                "qc_status": "clean",
                "retrieved_at": pd.Timestamp("2025-01-06T13:00:00Z"),
                "source": "noaa_bdp",
            },
        ]
    )


# ----------------------------------------------------------------------
# Tests
# ----------------------------------------------------------------------
def test_research_include_forecast_mode_1_populates_fcst_columns(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Any
) -> None:
    """Mode 1 — research(include_forecast=True) returns DataFrame with fcst_*
    columns populated from the mocked IEM MOS rows."""
    monkeypatch.setenv("MOSTLYRIGHT_CACHE_DIR", str(tmp_path))

    obs_rows = [
        _fake_obs_row("NYC", "2025-01-06T18:00:00Z", 40.0),
        _fake_obs_row("NYC", "2025-01-06T19:00:00Z", 42.0),
    ]
    climate_rows = [_fake_climate_row("NYC", "2025-01-06", 45.0, 30.0)]

    with (
        patch(
            "mostlyright.research._fetch_observations_range",
            return_value=obs_rows,
        ),
        patch(
            "mostlyright.research._fetch_climate_range",
            return_value=climate_rows,
        ),
        patch("mostlyright.research._all_caches_warm", return_value=True),
        patch(
            "mostlyright.weather._fetchers._iem_mos.fetch_iem_mos",
            return_value=_fake_iem_mos_df(),
        ),
    ):
        df = mostlyright.research("KNYC", "2025-01-06", "2025-01-06", include_forecast=True)

    assert not df.empty
    for col in (
        "fcst_high_f",
        "fcst_low_f",
        "fcst_model",
        "fcst_issued_at",
        "fcst_pop_6hr_pct",
        "fcst_qpf_6hr_in",
    ):
        assert col in df.columns, f"missing fcst column {col!r}"
    # At least one row should have a populated fcst_high_f from the mocked
    # IEM MOS rows projected into the settlement window.
    assert df["fcst_high_f"].notna().any(), (
        f"expected fcst_high_f populated; got {df['fcst_high_f'].tolist()!r}"
    )


def test_research_include_forecast_false_preserves_parity_baseline(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Any
) -> None:
    """PARITY — research(include_forecast=False) returns DataFrame with fcst_* NULL.

    This is the byte-equivalent baseline against v0.14.1; any drift in fcst_*
    population when include_forecast=False would break the 5 parity fixtures.
    """
    monkeypatch.setenv("MOSTLYRIGHT_CACHE_DIR", str(tmp_path))

    obs_rows = [
        _fake_obs_row("NYC", "2025-01-06T18:00:00Z", 40.0),
    ]
    climate_rows = [_fake_climate_row("NYC", "2025-01-06", 45.0, 30.0)]

    with (
        patch(
            "mostlyright.research._fetch_observations_range",
            return_value=obs_rows,
        ),
        patch(
            "mostlyright.research._fetch_climate_range",
            return_value=climate_rows,
        ),
        patch("mostlyright.research._all_caches_warm", return_value=True),
    ):
        df = mostlyright.research("KNYC", "2025-01-06", "2025-01-06")

    assert "fcst_high_f" in df.columns
    assert df["fcst_high_f"].isna().all()
    assert df["fcst_low_f"].isna().all()
    assert df["fcst_model"].isna().all()
    assert df["fcst_issued_at"].isna().all()
    assert df["fcst_pop_6hr_pct"].isna().all()
    assert df["fcst_qpf_6hr_in"].isna().all()
    # Mode 2 columns MUST NOT appear when include_forecast=False — additive
    # promise.
    nwp_cols = [c for c in df.columns if c.startswith("fcst_") and "_nwp_" in c]
    assert nwp_cols == [], f"unexpected NWP columns leaked: {nwp_cols!r}"


def test_research_include_forecast_mode_2_adds_nwp_columns(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Any
) -> None:
    """Mode 2 — research(include_forecast=True, forecast_models=['hrrr']) adds
    fcst_high_f_nwp_hrrr + fcst_low_f_nwp_hrrr columns alongside Mode 1
    columns."""
    monkeypatch.setenv("MOSTLYRIGHT_CACHE_DIR", str(tmp_path))

    obs_rows = [_fake_obs_row("NYC", "2025-01-06T18:00:00Z", 40.0)]
    climate_rows = [_fake_climate_row("NYC", "2025-01-06", 45.0, 30.0)]

    with (
        patch(
            "mostlyright.research._fetch_observations_range",
            return_value=obs_rows,
        ),
        patch(
            "mostlyright.research._fetch_climate_range",
            return_value=climate_rows,
        ),
        patch("mostlyright.research._all_caches_warm", return_value=True),
        patch(
            "mostlyright.weather._fetchers._iem_mos.fetch_iem_mos",
            return_value=_fake_iem_mos_df(),
        ),
        patch(
            "mostlyright.weather.forecast_nwp.forecast_nwp",
            return_value=_fake_nwp_df(),
        ),
    ):
        df = mostlyright.research(
            "KNYC",
            "2025-01-06",
            "2025-01-06",
            include_forecast=True,
            forecast_models=["hrrr"],
        )

    assert not df.empty
    assert "fcst_high_f_nwp_hrrr" in df.columns
    assert "fcst_low_f_nwp_hrrr" in df.columns
    high_vals = df["fcst_high_f_nwp_hrrr"].dropna().tolist()
    assert high_vals, "expected fcst_high_f_nwp_hrrr populated from mocked NWP"
    # 285 K → ~ 53.33 F
    assert abs(high_vals[0] - 53.33) < 0.5


def test_research_backward_compat_no_kwargs(monkeypatch: pytest.MonkeyPatch, tmp_path: Any) -> None:
    """research(station, from_date, to_date) — bare positional call still works."""
    monkeypatch.setenv("MOSTLYRIGHT_CACHE_DIR", str(tmp_path))

    obs_rows = [_fake_obs_row("NYC", "2025-01-06T18:00:00Z", 40.0)]
    climate_rows = [_fake_climate_row("NYC", "2025-01-06", 45.0, 30.0)]

    with (
        patch(
            "mostlyright.research._fetch_observations_range",
            return_value=obs_rows,
        ),
        patch(
            "mostlyright.research._fetch_climate_range",
            return_value=climate_rows,
        ),
        patch("mostlyright.research._all_caches_warm", return_value=True),
    ):
        df = mostlyright.research("KNYC", "2025-01-06", "2025-01-06")
    assert isinstance(df, pd.DataFrame)
    assert "station" in df.columns
    assert "cli_high_f" in df.columns

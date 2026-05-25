"""Unit tests for IEMAdapter."""

from __future__ import annotations

from datetime import UTC, datetime

import pandas as pd
import pytest
from mostlyright.weather.catalog import get_adapter
from mostlyright.weather.catalog.iem import IEMAdapter


def _row(**overrides):
    """A synthetic IEM parser-output dict (post-iem_to_observation)."""
    base = {
        "station_code": "KNYC",
        "observed_at": "2025-01-01T12:00:00Z",
        "observation_type": "METAR",
        "source": "iem",
        "temp_c": 1.0,
        "dewpoint_c": -1.0,
        "temp_f": 33.8,
        "dewpoint_f": 30.2,
        "wind_dir_degrees": 180,
        "wind_speed_kt": 3,
        "wind_gust_kt": None,
        "altimeter_inhg": 30.1,
        "sea_level_pressure_mb": 1013.0,
        "sky_cover_1": "CLR",
        "sky_base_1_ft": None,
        "sky_cover_2": None,
        "sky_base_2_ft": None,
        "sky_cover_3": None,
        "sky_base_3_ft": None,
        "sky_cover_4": None,
        "sky_base_4_ft": None,
        "visibility_miles": 10.0,
        "precip_1hr_inches": 0.0,
        "raw_metar": "METAR KNYC 011200Z ...",
    }
    base.update(overrides)
    return base


def test_from_rows_basic_projection():
    df = IEMAdapter.from_rows(
        [_row(), _row(station_code="KORD", observed_at="2025-01-01T13:00:00Z")],
        source="iem.archive",
        retrieved_at=datetime(2025, 1, 1, 14, tzinfo=UTC),
    )
    # Canonical columns present.
    assert "station" in df.columns
    assert "event_time" in df.columns
    assert "knowledge_time" in df.columns
    assert "source" in df.columns
    assert "retrieved_at" in df.columns
    # Per-row source.
    assert (df["source"] == "iem.archive").all()
    # df.attrs carries source.
    assert df.attrs["source"] == "iem.archive"


def test_event_time_is_tz_aware_utc():
    df = IEMAdapter.from_rows([_row()])
    assert df["event_time"].dt.tz is not None
    assert str(df["event_time"].dt.tz) == "UTC"


def test_knowledge_time_offset_15min():
    df = IEMAdapter.from_rows([_row()])
    delta = df["knowledge_time"].iloc[0] - df["event_time"].iloc[0]
    assert delta == pd.Timedelta(minutes=15)


def test_empty_rows_yields_empty_df():
    df = IEMAdapter.from_rows([])
    assert df.empty
    assert df.attrs["source"] == "iem.archive"


def test_invalid_source_raises():
    with pytest.raises(ValueError, match="does not support source"):
        IEMAdapter.from_rows([_row()], source="bogus")


def test_supports_iem_live():
    df = IEMAdapter.from_rows([_row()], source="iem.live")
    assert df.attrs["source"] == "iem.live"


def test_fetch_observations_not_implemented():
    a = IEMAdapter()
    with pytest.raises(NotImplementedError, match="Mode-2"):
        a.fetch_observations("iem.archive", "KNYC", "2025-01-01", "2025-01-02")


def test_fetch_forecasts_iem_archive_wired_via_iem_mos() -> None:
    """Phase 17 PLAN-08: the Phase-2 ``NotImplementedError`` stub is gone.

    ``iem.archive`` now wires through :func:`fetch_iem_mos` and returns
    a DataFrame matching ``schema.forecast.iem_mos.v1``.
    """
    from unittest.mock import patch

    with patch("mostlyright.weather._fetchers._iem_mos.fetch_iem_mos") as mock_fetch:
        mock_fetch.return_value = pd.DataFrame()
        a = IEMAdapter()
        df = a.fetch_forecasts("iem.archive", "KNYC", "2025-01-01", "2025-01-02")
        assert isinstance(df, pd.DataFrame)
        mock_fetch.assert_called_once_with(
            "KNYC", "2025-01-01", "2025-01-02", model="nbe"
        )


def test_fetch_forecasts_iem_live_deferred_to_v02() -> None:
    """``iem.live`` MOS still deferred — error message points at iem.archive."""
    a = IEMAdapter()
    with pytest.raises(NotImplementedError, match="iem.live MOS deferred to v0.2"):
        a.fetch_forecasts("iem.live", "KNYC", "2025-01-01", "2025-01-02")


def test_registered_in_catalog():
    a = get_adapter("iem.archive")
    assert isinstance(a, IEMAdapter)
    b = get_adapter("iem.live")
    assert isinstance(b, IEMAdapter)


def test_pitfall_8_missing_data_preservation():
    """IEM ``M`` → parser yields ``None``; adapter preserves it (not 0/NaN)."""
    # Simulate parser output with missing temp_c (M → None).
    df = IEMAdapter.from_rows([_row(temp_c=None)])
    assert df["temp_c"].iloc[0] is None or pd.isna(df["temp_c"].iloc[0])


# ----------------------------------------------------------------------
# Unit conversion correctness (codex Phase 2 review HIGH finding fix)
# ----------------------------------------------------------------------
def test_wind_speed_kt_converted_to_ms():
    """Parser yields knots; canonical column is m/s. 1 kt = 0.514444 m/s."""
    df = IEMAdapter.from_rows([_row(wind_speed_kt=10)])
    # 10 kt = 10 * 1852/3600 m/s ≈ 5.1444 m/s
    val = df["wind_speed_ms"].iloc[0]
    assert val == pytest.approx(5.1444, abs=1e-3)


def test_wind_gust_kt_converted_to_ms():
    df = IEMAdapter.from_rows([_row(wind_gust_kt=20)])
    val = df["wind_gust_ms"].iloc[0]
    assert val == pytest.approx(10.2889, abs=1e-3)


def test_visibility_miles_converted_to_metres():
    """Parser yields statute miles; canonical column is metres. 1 mi = 1609.344 m."""
    df = IEMAdapter.from_rows([_row(visibility_miles=10.0)])
    val = df["visibility_m"].iloc[0]
    assert val == pytest.approx(16093.44, abs=1e-2)


def test_sky_base_ft_converted_to_metres():
    """Parser yields feet; canonical column is metres. 1 ft = 0.3048 m."""
    df = IEMAdapter.from_rows([_row(sky_base_1_ft=1000)])
    val = df["sky_base_1_m"].iloc[0]
    assert val == pytest.approx(304.8, abs=1e-3)


def test_precip_inches_converted_to_mm():
    """Parser yields precip_1hr_inches; canonical column is precip_mm_1h. 1 in = 25.4 mm."""
    df = IEMAdapter.from_rows([_row(precip_1hr_inches=0.5)])
    assert "precip_mm_1h" in df.columns
    val = df["precip_mm_1h"].iloc[0]
    assert val == pytest.approx(12.7, abs=1e-3)


def test_none_preserved_through_conversion():
    """Missing-data sentinels survive unit conversion as None (not 0.0)."""
    df = IEMAdapter.from_rows([_row(wind_speed_kt=None, visibility_miles=None)])
    assert pd.isna(df["wind_speed_ms"].iloc[0])
    assert pd.isna(df["visibility_m"].iloc[0])


# ----------------------------------------------------------------------
# Adapter -> Validator integration (codex iter-4 HIGH fix)
# ----------------------------------------------------------------------
def test_adapter_output_passes_validator():
    """The full adapter -> validator chain must validate cleanly."""
    from mostlyright.core import validate_dataframe

    df = IEMAdapter.from_rows([_row(), _row(observed_at="2025-01-01T13:00:00Z")])
    reg = validate_dataframe(df, "schema.observation.v1")
    assert reg.source == "iem.archive"
    assert reg.rows == 2


def test_adapter_single_row_all_nulls_validator_dtype():
    """A single METAR row with no gust / no cloud-base must still produce a
    schema-conformant DataFrame (float64 dtype enforced via coerce_canonical_dtypes).
    """
    from mostlyright.core import validate_dataframe

    df = IEMAdapter.from_rows(
        [
            _row(
                wind_gust_kt=None,
                sky_base_1_ft=None,
                sky_base_2_ft=None,
                sky_base_3_ft=None,
                sky_base_4_ft=None,
                sky_cover_2=None,
                sky_cover_3=None,
                sky_cover_4=None,
            )
        ]
    )
    assert df["wind_gust_ms"].dtype == "float64"
    assert df["sky_base_1_m"].dtype == "float64"
    # Validator must accept.
    reg = validate_dataframe(df, "schema.observation.v1")
    assert reg.rows == 1

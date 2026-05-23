"""Unit tests for IEMAdapter."""

from __future__ import annotations

from datetime import UTC, datetime

import pandas as pd
import pytest
from tradewinds.weather.catalog import get_adapter
from tradewinds.weather.catalog.iem import IEMAdapter


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


def test_fetch_forecasts_deferred_to_phase_3():
    a = IEMAdapter()
    with pytest.raises(NotImplementedError, match="deferred to Phase 3"):
        a.fetch_forecasts("iem.archive", "KNYC", "2025-01-01", "2025-01-02")


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

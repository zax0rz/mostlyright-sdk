"""Unit tests for GHCNhAdapter."""

from __future__ import annotations

from datetime import UTC, datetime

import pandas as pd
import pytest
from tradewinds.weather.catalog import get_adapter
from tradewinds.weather.catalog.ghcnh import GHCNhAdapter


def _row(**overrides):
    base = {
        "station_code": "KNYC",
        "observed_at": "2025-01-01T12:00:00Z",
        "observation_type": "METAR",
        "temp_c": 1.0,
        "dewpoint_c": -1.0,
        "wind_dir_degrees": 180,
        "wind_speed_kt": 3,
        "wind_gust_kt": None,
        "sea_level_pressure_mb": 1013.0,
        "visibility_miles": 10.0,
        "sky_cover_1": None,
        "sky_base_1_ft": None,
        "sky_cover_2": None,
        "sky_base_2_ft": None,
        "sky_cover_3": None,
        "sky_base_3_ft": None,
        "sky_cover_4": None,
        "sky_base_4_ft": None,
        "raw_metar": None,
    }
    base.update(overrides)
    return base


def test_from_rows_basic():
    df = GHCNhAdapter.from_rows([_row()], source="ghcnh.archive")
    assert df.attrs["source"] == "ghcnh.archive"


def test_knowledge_time_offset_6h():
    df = GHCNhAdapter.from_rows([_row()])
    delta = df["knowledge_time"].iloc[0] - df["event_time"].iloc[0]
    assert delta == pd.Timedelta(hours=6)


def test_unsupported_source_raises():
    with pytest.raises(ValueError):
        GHCNhAdapter.from_rows([_row()], source="ghcnh.live")


def test_fetch_observations_not_implemented():
    a = GHCNhAdapter()
    with pytest.raises(NotImplementedError):
        a.fetch_observations("ghcnh.archive", "KNYC", "2025-01-01", "2025-01-02")


def test_registered_in_catalog():
    a = get_adapter("ghcnh.archive")
    assert isinstance(a, GHCNhAdapter)


def test_empty_input():
    df = GHCNhAdapter.from_rows([])
    assert df.empty
    assert df.attrs["source"] == "ghcnh.archive"


def test_retrieved_at_propagates():
    when = datetime(2025, 1, 1, 13, tzinfo=UTC)
    df = GHCNhAdapter.from_rows([_row()], retrieved_at=when)
    assert df.attrs["retrieved_at"] == when

"""Unit tests for AWCAdapter."""

from __future__ import annotations

from datetime import UTC, datetime

import pandas as pd
import pytest
from mostlyright.weather.catalog import get_adapter
from mostlyright.weather.catalog.awc import AWCAdapter


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
        "sky_cover_1": "CLR",
        "sky_base_1_ft": None,
        "sky_cover_2": None,
        "sky_base_2_ft": None,
        "sky_cover_3": None,
        "sky_base_3_ft": None,
        "sky_cover_4": None,
        "sky_base_4_ft": None,
        "raw_metar": "METAR KNYC 011200Z ...",
    }
    base.update(overrides)
    return base


def test_from_rows_basic():
    df = AWCAdapter.from_rows([_row()], source="awc.live")
    assert df.attrs["source"] == "awc.live"
    assert "event_time" in df.columns
    assert "knowledge_time" in df.columns


def test_knowledge_time_offset_5min():
    df = AWCAdapter.from_rows([_row()])
    delta = df["knowledge_time"].iloc[0] - df["event_time"].iloc[0]
    assert delta == pd.Timedelta(minutes=5)


def test_only_supports_awc_live():
    """AWCAdapter does NOT support an archive source."""
    with pytest.raises(ValueError):
        AWCAdapter.from_rows([_row()], source="awc.archive")


def test_fetch_observations_not_implemented():
    a = AWCAdapter()
    with pytest.raises(NotImplementedError):
        a.fetch_observations("awc.live", "KNYC", "2025-01-01", "2025-01-02")


def test_registered_in_catalog():
    a = get_adapter("awc.live")
    assert isinstance(a, AWCAdapter)


def test_empty_input():
    df = AWCAdapter.from_rows([])
    assert df.empty
    assert df.attrs["source"] == "awc.live"


def test_retrieved_at_propagates():
    when = datetime(2025, 1, 1, 13, tzinfo=UTC)
    df = AWCAdapter.from_rows([_row()], retrieved_at=when)
    assert df.attrs["retrieved_at"] == when


def test_retrieved_at_naive_rejected():
    """Naive retrieved_at must raise — not produce a cryptic pandas error."""
    with pytest.raises(ValueError, match="tz-aware"):
        AWCAdapter.from_rows([_row()], retrieved_at=datetime(2025, 1, 1, 13))


def test_adapter_output_passes_validator_with_drift():
    """AWC output must pass validator when caller supplies allow_source_drift.

    The canonical schema is registered to iem.archive; AWC counts as drift
    and requires an explicit reason string.
    """
    from mostlyright.core import validate_dataframe

    df = AWCAdapter.from_rows([_row()])
    reg = validate_dataframe(
        df,
        "schema.observation.v1",
        allow_source_drift="AWC live observations (different canonical source)",
    )
    assert reg.source == "awc.live"
    events = [e["event"] for e in reg.audit_log()]
    assert "source_drift_allowed" in events

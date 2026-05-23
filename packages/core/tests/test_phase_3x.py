"""Smoke tests for the Phase 3.1-3.6 architectural seams."""

from __future__ import annotations

import pandas as pd
import pytest


# ----------------------------------------------------------------------
# Phase 3.1 — International + daily_extremes
# ----------------------------------------------------------------------
def test_international_stations_count():
    from tradewinds.international import INTERNATIONAL_STATIONS

    # v0.1.0 scope: 40+ international ICAOs (Paris splits into 3 stations,
    # major hubs in Europe/Asia/Oceania/Americas).
    assert len(INTERNATIONAL_STATIONS) >= 40


def test_paris_split_present():
    """Paris LFPG / LFPB / LFPO all present for per-event resolution."""
    from tradewinds.international import INTERNATIONAL_STATIONS

    assert "LFPG" in INTERNATIONAL_STATIONS
    assert "LFPB" in INTERNATIONAL_STATIONS
    assert "LFPO" in INTERNATIONAL_STATIONS


def test_deferred_stations():
    from tradewinds.international import DEFERRED_STATIONS

    assert "VHHH" in DEFERRED_STATIONS  # Hong Kong
    assert "RCTP" in DEFERRED_STATIONS  # Taipei


def test_daily_extremes_basic():
    from tradewinds.international import daily_extremes

    df = pd.DataFrame(
        {
            "event_time": pd.to_datetime(
                ["2025-01-01T12:00:00Z", "2025-01-01T18:00:00Z", "2025-01-02T06:00:00Z"],
                utc=True,
            ),
            "temp_c": [5.0, 12.0, -3.0],
            "temp_f": [41.0, 53.6, 26.6],
        }
    )
    out = daily_extremes(df, station_tz="UTC")
    assert len(out) == 2
    jan_1 = out[out["local_date"].astype(str) == "2025-01-01"]
    assert jan_1["temp_max_c"].iloc[0] == 12.0
    assert jan_1["temp_min_c"].iloc[0] == 5.0


def test_daily_extremes_tz_aware():
    """Tokyo timezone (UTC+9): UTC noon Jan 1 → JST 21:00 same day."""
    from tradewinds.international import daily_extremes

    df = pd.DataFrame(
        {
            "event_time": pd.to_datetime(
                ["2025-01-01T15:00:00Z", "2025-01-01T20:00:00Z"], utc=True
            ),
            "temp_c": [10.0, 5.0],
        }
    )
    out = daily_extremes(df, station_tz="Asia/Tokyo")
    # Both events fall on Jan 2 in JST (00:00 + 05:00).
    assert len(out) == 1
    assert str(out["local_date"].iloc[0]) == "2025-01-02"


def test_daily_extremes_empty():
    from tradewinds.international import daily_extremes

    df = pd.DataFrame({"event_time": pd.Series([], dtype="datetime64[ns, UTC]")})
    out = daily_extremes(df, station_tz="UTC")
    assert out.empty


# ----------------------------------------------------------------------
# Phase 3.2 — NWP forecast seam
# ----------------------------------------------------------------------
def test_nwp_models():
    from tradewinds.forecasts import SUPPORTED_NWP_MODELS

    assert frozenset({"hrrr", "gfs", "nbm"}) == SUPPORTED_NWP_MODELS


def test_nwp_unknown_model_raises():
    from tradewinds.forecasts import forecast_nwp

    with pytest.raises(ValueError, match="NWP model must be one of"):
        forecast_nwp("KNYC", "bogus")


def test_nwp_dispatch_seam_raises():
    """v0.1.0 dispatch seam — NWP fetch wiring lands in 3.2 alpha."""
    from tradewinds.forecasts import forecast_nwp

    # Either SourceUnavailableError (no cfgrib) or NotImplementedError.
    with pytest.raises((Exception,)):
        forecast_nwp("KNYC", "hrrr")


# ----------------------------------------------------------------------
# Phase 3.3 — Polymarket
# ----------------------------------------------------------------------
def test_polymarket_event_id_validation():
    from tradewinds.markets.polymarket import (
        PolymarketEventError,
        polymarket_settle,
    )

    with pytest.raises(PolymarketEventError, match="UUID4"):
        polymarket_settle("not-a-uuid")


def test_polymarket_description_oversize_raises():
    from tradewinds.markets.polymarket import (
        PolymarketEventError,
        polymarket_settle,
    )

    huge = "x" * (16 * 1024 + 1)
    with pytest.raises(PolymarketEventError, match="16 KB cap"):
        polymarket_settle(
            "01234567-89ab-4cde-8f01-23456789abcd",
            description=huge,
        )


def test_polymarket_disallowed_url_raises():
    from tradewinds.markets.polymarket import (
        PolymarketEventError,
        polymarket_settle,
    )

    desc = "Resolves via https://malicious.example.com/data"
    with pytest.raises(PolymarketEventError, match="not in allowlist"):
        polymarket_settle(
            "01234567-89ab-4cde-8f01-23456789abcd",
            description=desc,
        )


def test_polymarket_allowed_url_passes_to_settlement():
    """Wunderground URL passes the boundary; settlement engine raises
    NotImplementedError (Phase 3.3 wiring)."""
    from tradewinds.markets.polymarket import polymarket_settle

    with pytest.raises(NotImplementedError):
        polymarket_settle(
            "01234567-89ab-4cde-8f01-23456789abcd",
            description="Resolves via https://www.wunderground.com/data",
        )


# ----------------------------------------------------------------------
# Phase 3.4 — QC engine
# ----------------------------------------------------------------------
def test_qc_engine_temp_out_of_range():
    from tradewinds.qc import QCEngine

    df = pd.DataFrame(
        {
            "temp_c": [10.0, 100.0, -100.0],  # second + third are bogus
            "dew_point_c": [5.0, 5.0, 5.0],
        }
    )
    out = QCEngine().apply(df)
    assert out["obs_qc_status"].iloc[0] == 0  # clean
    # Row 1: temp 100 fires temp-out-of-range (bit 0).
    assert out["obs_qc_status"].iloc[1] & 1 == 1
    # Row 2: temp -100 fires bit 0 too.
    assert out["obs_qc_status"].iloc[2] & 1 == 1


def test_qc_engine_dewpoint_exceeds_temp():
    from tradewinds.qc import QCEngine

    df = pd.DataFrame({"temp_c": [10.0], "dew_point_c": [20.0]})
    out = QCEngine().apply(df)
    # Bit 1 = dewpoint > temp.
    assert out["obs_qc_status"].iloc[0] & 2 == 2


def test_qc_engine_alpha_rules_count():
    """Exactly 5 alpha rules registered in v0.1.0."""
    from tradewinds.qc import ALPHA_RULES

    assert len(ALPHA_RULES) == 5


def test_qc_engine_sidecar_rows():
    from tradewinds.qc import QCEngine

    df = pd.DataFrame(
        {
            "station": ["KNYC"],
            "event_time": pd.to_datetime(["2025-01-01T12:00:00Z"], utc=True),
            "source": ["iem.archive"],
            "temp_c": [100.0],
            "dew_point_c": [5.0],
        }
    )
    engine = QCEngine()
    df = engine.apply(df)
    sidecar = engine.build_sidecar_rows(df)
    assert len(sidecar) == 1
    assert sidecar[0]["rule_id"] == "temp_c.out_of_range"
    assert sidecar[0]["flag"] == "flagged"


def test_crosscheck_iem_ghcnh():
    from tradewinds.qc import crosscheck_iem_ghcnh

    iem = pd.DataFrame(
        {
            "station": ["KNYC", "KNYC"],
            "event_time": pd.to_datetime(
                ["2025-01-01T12:00:00Z", "2025-01-01T13:00:00Z"], utc=True
            ),
            "temp_c": [5.0, 10.0],
        }
    )
    ghcnh = pd.DataFrame(
        {
            "station": ["KNYC", "KNYC"],
            "event_time": pd.to_datetime(
                ["2025-01-01T12:00:00Z", "2025-01-01T13:00:00Z"], utc=True
            ),
            "temp_c": [5.5, 15.0],  # second row disagrees by 5C
        }
    )
    out = crosscheck_iem_ghcnh(iem, ghcnh, tol_c=2.0)
    assert len(out) == 1
    assert out["delta_c"].iloc[0] == 5.0


# ----------------------------------------------------------------------
# Phase 3.5 — Transforms
# ----------------------------------------------------------------------
def test_lag():
    from tradewinds.transforms import lag

    df = pd.DataFrame({"x": [1, 2, 3, 4]})
    out = lag(df, "x", periods=1)
    assert pd.isna(out.iloc[0])
    assert out.iloc[1] == 1


def test_diff():
    from tradewinds.transforms import diff

    df = pd.DataFrame({"x": [10, 12, 15, 14]})
    out = diff(df, "x")
    assert out.iloc[1] == 2
    assert out.iloc[3] == -1


def test_rolling_mean():
    from tradewinds.transforms import rolling

    df = pd.DataFrame({"x": [1.0, 2.0, 3.0, 4.0]})
    out = rolling(df, "x", window=2, fn="mean")
    assert out.iloc[1] == 1.5
    assert out.iloc[3] == 3.5


def test_calendar_features():
    from tradewinds.transforms import calendar_features

    df = pd.DataFrame({"d": pd.to_datetime(["2025-06-15T12:00:00Z"], utc=True)})
    out = calendar_features(df, "d")
    assert "month_sin" in out.columns
    assert "month_cos" in out.columns
    assert "dow_sin" in out.columns
    assert "hour_sin" in out.columns


def test_wind_chill():
    from tradewinds.transforms import wind_chill

    # Standard NWS example: 0F + 15 mph wind → wind chill ~-19F.
    val = wind_chill(0.0, 15.0)
    assert val is not None
    assert -22 < val < -17


def test_heat_index():
    from tradewinds.transforms import heat_index

    val = heat_index(90.0, 70.0)
    assert val is not None
    assert val > 90.0  # heat index > temp at high humidity


def test_clip_outliers():
    from tradewinds.transforms import clip_outliers

    df = pd.DataFrame({"x": [1.0, 2.0, 3.0, 4.0, 100.0]})
    out = clip_outliers(df, "x", std=1.0)
    # 100 should be clipped to mu + 1*sigma.
    assert out.iloc[-1] < 100.0


# ----------------------------------------------------------------------
# Phase 3.6 — Discovery + DataVersion
# ----------------------------------------------------------------------
def test_describe_observation_ledger():
    from tradewinds.discovery import describe

    out = describe("schema.observation_ledger.v1")
    assert "schema.observation_ledger.v1" in out
    assert "Canonical source" in out


def test_describe_unknown_raises():
    from tradewinds.discovery import describe

    with pytest.raises(ValueError, match="Unknown schema_id"):
        describe("schema.nonexistent.v1")


def test_feature_catalog():
    from tradewinds.discovery import feature_catalog

    catalog = feature_catalog()
    assert "lag" in catalog
    assert "calendar_features" in catalog


def test_data_version_deterministic():
    from tradewinds.discovery import DataVersion

    v1 = DataVersion.from_components(
        sdk_version="0.1.0a1",
        schema_ids=("schema.observation.v1",),
        sources=("iem.archive",),
        code_sha="abc123",
        data_sha="def456",
    )
    v2 = DataVersion.from_components(
        sdk_version="0.1.0a1",
        schema_ids=("schema.observation.v1",),
        sources=("iem.archive",),
        code_sha="abc123",
        data_sha="def456",
    )
    assert v1.token == v2.token
    assert len(v1.token) == 64  # SHA-256 hex


def test_data_version_changes_on_input_change():
    from tradewinds.discovery import DataVersion

    v1 = DataVersion.from_components(
        sdk_version="0.1.0a1",
        schema_ids=("schema.observation.v1",),
        sources=("iem.archive",),
        code_sha="abc123",
        data_sha="def456",
    )
    v2 = DataVersion.from_components(
        sdk_version="0.1.0a2",  # different version
        schema_ids=("schema.observation.v1",),
        sources=("iem.archive",),
        code_sha="abc123",
        data_sha="def456",
    )
    assert v1.token != v2.token


def test_availability_unknown_station():
    from tradewinds.discovery import availability

    out = availability("ZZZZZ_NONEXISTENT_STATION")
    assert out["months_cached"] == 0

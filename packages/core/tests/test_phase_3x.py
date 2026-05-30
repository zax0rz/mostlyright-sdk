"""Smoke tests for the Phase 3.1-3.6 architectural seams."""

from __future__ import annotations

import pandas as pd
import pytest


# ----------------------------------------------------------------------
# Phase 3.1 — International + daily_extremes
# ----------------------------------------------------------------------
def test_international_stations_count():
    from mostlyright.international import INTERNATIONAL_STATIONS

    # v0.1.0 scope: 40+ international ICAOs (Paris splits into 3 stations,
    # major hubs in Europe/Asia/Oceania/Americas).
    assert len(INTERNATIONAL_STATIONS) >= 40


def test_paris_split_present():
    """Paris LFPG / LFPB / LFPO all present for per-event resolution."""
    from mostlyright.international import INTERNATIONAL_STATIONS

    assert "LFPG" in INTERNATIONAL_STATIONS
    assert "LFPB" in INTERNATIONAL_STATIONS
    assert "LFPO" in INTERNATIONAL_STATIONS


def test_deferred_stations():
    from mostlyright.international import DEFERRED_STATIONS

    # Phase 23: Hong Kong settles against HKO (the Observatory, weather.gov.hk
    # v0.2 source) and Taipei moved to RCSS (Songshan, CWA source). The old
    # VHHH/RCTP airport ICAOs stay registry records but no longer front a
    # deferred market.
    assert "HKO" in DEFERRED_STATIONS  # Hong Kong
    assert "RCSS" in DEFERRED_STATIONS  # Taipei
    assert "VHHH" not in DEFERRED_STATIONS
    assert "RCTP" not in DEFERRED_STATIONS


def test_daily_extremes_empty_cache_returns_empty_list(monkeypatch):
    """No cached rows for the window → empty list (no rows, no errors)."""
    from datetime import date

    from mostlyright import international
    from mostlyright.weather import cache as cache_mod

    # daily_extremes() imports cache.read_cache lazily; patching the module
    # attribute is sufficient because the lazy import binds to the module.
    monkeypatch.setattr(cache_mod, "read_cache", lambda *a, **kw: None)
    out = international.daily_extremes("RJTT", date(2025, 1, 1), date(2025, 1, 2))
    assert out == []


# ----------------------------------------------------------------------
# Phase 3.2 — NWP forecast real implementation
# ----------------------------------------------------------------------
def test_nwp_models():
    # Phase 17 Wave 2 expanded SUPPORTED_NWP_MODELS from 3 to 24
    # (NCEP + ECMWF + MSC + HAFS + legacy). The original 3 are still
    # members; the closed-set discipline is preserved (see Phase 17
    # Wave 1 tests for the full enum length assertion).
    from mostlyright.forecasts import SUPPORTED_NWP_MODELS

    assert {"hrrr", "gfs", "nbm"}.issubset(SUPPORTED_NWP_MODELS)


def test_nwp_unknown_model_raises():
    from mostlyright.forecasts import forecast_nwp

    with pytest.raises(ValueError, match="NWP model must be one of"):
        forecast_nwp("KNYC", "bogus")


def test_nwp_reserved_ecmwf_model_raises_specific_error():
    """ECMWF Tier-2 ids predeclared in the enum raise NwpModelNotAvailableError."""
    from mostlyright.core.exceptions import NwpModelNotAvailableError
    from mostlyright.forecasts import forecast_nwp

    with pytest.raises(NwpModelNotAvailableError) as exc_info:
        forecast_nwp("KNYC", "ecmwf_ifs_hres")
    assert exc_info.value.model == "ecmwf_ifs_hres"


def test_nwp_dispatch_requires_extra_or_runs():
    """Without [nwp], surfaces SourceUnavailableError with install hint.

    The full live path (cfgrib + xarray + sklearn) is covered by the
    network-bound, ``@pytest.mark.live``-gated tests in
    ``packages/weather/tests/test_forecast_nwp.py``.
    """
    import importlib.util

    from mostlyright.core.exceptions import SourceUnavailableError
    from mostlyright.forecasts import forecast_nwp

    has_extra = all(
        importlib.util.find_spec(m) is not None for m in ("cfgrib", "xarray", "sklearn")
    )
    if has_extra:
        pytest.skip("path exercised by live tests when [nwp] is installed")
    with pytest.raises(SourceUnavailableError) as exc_info:
        forecast_nwp("KNYC", "hrrr")
    assert "[nwp]" in str(exc_info.value)


# ----------------------------------------------------------------------
# Phase 3.3 — Polymarket
# ----------------------------------------------------------------------
def test_polymarket_event_id_validation():
    from mostlyright.markets.polymarket import (
        PolymarketEventError,
        polymarket_settle,
    )

    with pytest.raises(PolymarketEventError, match=r"\[A-Za-z0-9_-\]"):
        polymarket_settle("not a valid id with spaces!")


def test_polymarket_description_oversize_raises():
    from mostlyright.markets.polymarket import (
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
    from mostlyright.markets.polymarket import (
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
    """Wunderground URL passes the boundary; real settlement now needs an event payload.

    With the real Phase 3.3 implementation the function attempts an HTTP
    fetch to Gamma when no `event=` is provided. Without an event, the
    description-only check still passes URL validation but settlement
    needs the slug for the resolution date — assert that path raises
    something sensible (not NotImplementedError anymore).
    """

    # Test the description-validation path WITHOUT triggering an HTTP
    # call by passing an event with no slug — the validator passes the
    # URL but the slug-date parser raises PolymarketSettlementError.
    from mostlyright.markets.polymarket import PolymarketSettlementError, polymarket_settle

    # Title has no high/low keyword, so the architect iter-1 HIGH-3
    # ambiguity-guard fires before the slug-date parser. Use a "highest"
    # title to bypass it and hit the slug-date check.
    with pytest.raises(PolymarketSettlementError, match="no resolution date in slug"):
        polymarket_settle(
            "01234567-89ab-4cde-8f01-23456789abcd",
            description="Resolves via https://www.wunderground.com/data",
            event={"slug": "no-date-here", "city": "london", "title": "highest temp in London"},
        )


# ----------------------------------------------------------------------
# Phase 3.4 — QC engine
# ----------------------------------------------------------------------
def test_qc_engine_temp_out_of_range():
    from mostlyright.qc import QCEngine

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
    from mostlyright.qc import QCEngine

    df = pd.DataFrame({"temp_c": [10.0], "dew_point_c": [20.0]})
    out = QCEngine().apply(df)
    # Bit 1 = dewpoint > temp.
    assert out["obs_qc_status"].iloc[0] & 2 == 2


def test_qc_engine_alpha_rules_count():
    """Exactly 5 alpha rules registered in v0.1.0."""
    from mostlyright.qc import ALPHA_RULES

    assert len(ALPHA_RULES) == 5


def test_qc_engine_sidecar_rows():
    from mostlyright.qc import QCEngine

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
    from mostlyright.qc import crosscheck_iem_ghcnh

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
    from mostlyright.transforms import lag

    df = pd.DataFrame({"x": [1, 2, 3, 4]})
    out = lag(df, "x", periods=1)
    assert pd.isna(out.iloc[0])
    assert out.iloc[1] == 1


def test_diff():
    from mostlyright.transforms import diff

    df = pd.DataFrame({"x": [10, 12, 15, 14]})
    out = diff(df, "x")
    assert out.iloc[1] == 2
    assert out.iloc[3] == -1


def test_rolling_mean():
    from mostlyright.transforms import rolling

    df = pd.DataFrame({"x": [1.0, 2.0, 3.0, 4.0]})
    out = rolling(df, "x", window=2, fn="mean")
    assert out.iloc[1] == 1.5
    assert out.iloc[3] == 3.5


def test_calendar_features():
    from mostlyright.transforms import calendar_features

    df = pd.DataFrame({"d": pd.to_datetime(["2025-06-15T12:00:00Z"], utc=True)})
    out = calendar_features(df, "d")
    assert "month_sin" in out.columns
    assert "month_cos" in out.columns
    assert "dow_sin" in out.columns
    assert "hour_sin" in out.columns


def test_wind_chill():
    from mostlyright.transforms import wind_chill

    # Standard NWS example: 0F + 15 mph wind → wind chill ~-19F.
    val = wind_chill(0.0, 15.0)
    assert val is not None
    assert -22 < val < -17


def test_heat_index():
    from mostlyright.transforms import heat_index

    val = heat_index(90.0, 70.0)
    assert val is not None
    assert val > 90.0  # heat index > temp at high humidity


def test_clip_outliers():
    from mostlyright.transforms import clip_outliers

    df = pd.DataFrame({"x": [1.0, 2.0, 3.0, 4.0, 100.0]})
    out = clip_outliers(df, "x", std=1.0)
    # 100 should be clipped to mu + 1*sigma.
    assert out.iloc[-1] < 100.0


# ----------------------------------------------------------------------
# Phase 3.6 — Discovery + DataVersion
# ----------------------------------------------------------------------
def test_describe_observation_ledger():
    from mostlyright.discovery import describe

    out = describe("schema.observation_ledger.v1")
    assert "schema.observation_ledger.v1" in out
    assert "Canonical source" in out


def test_describe_unknown_raises():
    from mostlyright.discovery import describe

    with pytest.raises(ValueError, match="Unknown schema_id"):
        describe("schema.nonexistent.v1")


def test_feature_catalog():
    from mostlyright.discovery import feature_catalog

    catalog = feature_catalog()
    assert "lag" in catalog
    assert "calendar_features" in catalog


def test_data_version_deterministic():
    from mostlyright.discovery import DataVersion

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
    from mostlyright.discovery import DataVersion

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
    from mostlyright.discovery import availability

    out = availability("ZZZZZ_NONEXISTENT_STATION")
    assert out["months_cached"] == 0

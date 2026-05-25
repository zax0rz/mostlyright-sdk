"""Phase 7 PLAN-02 signature contract + dispatch tests for mostlyright.weather.obs."""

from __future__ import annotations

from typing import get_args
from unittest.mock import patch

import pandas as pd
import pytest


def test_obs_importable_from_tradewinds_weather():
    from mostlyright.weather import obs

    assert callable(obs)


def test_obs_importable_from_obs_module():
    from mostlyright.weather.obs import Source, Strategy, obs

    assert callable(obs)
    assert "iem" in get_args(Source)
    assert "ghcnh" in get_args(Source)
    assert "awc" in get_args(Source)
    assert set(get_args(Strategy)) == {"auto", "exact_window", "warm_cache", "hosted"}


def test_obs_signature_has_required_kwonly_params():
    import inspect

    from mostlyright.weather.obs import obs

    sig = inspect.signature(obs)
    params = sig.parameters

    assert "station" in params
    assert "start" in params
    assert "end" in params
    for name in ("source", "strategy", "as_dataframe"):
        assert params[name].kind == inspect.Parameter.KEYWORD_ONLY, f"{name} must be keyword-only"

    # B-6: ships as "auto" from PLAN-02 onward; never churns.
    assert params["source"].default is None
    assert params["strategy"].default == "auto"
    assert params["as_dataframe"].default is True


def test_obs_invalid_source_raises_value_error():
    from mostlyright.weather.obs import obs

    with pytest.raises(ValueError, match="source must be"):
        obs("KNYC", "2024-03-01", "2024-03-31", source="bogus")  # type: ignore[arg-type]


def test_obs_invalid_strategy_raises_value_error():
    from mostlyright.weather.obs import obs

    with pytest.raises(ValueError, match="strategy must be"):
        obs("KNYC", "2024-03-01", "2024-03-31", strategy="bogus")  # type: ignore[arg-type]


def test_obs_hosted_raises_not_implemented_with_documented_message():
    from mostlyright.weather.obs import obs

    with pytest.raises(NotImplementedError, match=r"hosted strategy deferred to v0\.2\.x"):
        obs("KNYC", "2024-03-01", "2024-03-31", strategy="hosted")


def test_obs_warm_cache_with_source_raises_value_error():
    """warm_cache + source!=None must raise ValueError (B-3: post-merge filter
    would corrupt priority semantics)."""
    from mostlyright.weather.obs import obs

    with pytest.raises(ValueError, match="warm_cache strategy requires source=None"):
        obs("KNYC", "2024-03-01", "2024-03-31", source="iem", strategy="warm_cache")


def test_obs_auto_dispatches_to_resolved_strategy(monkeypatch, tmp_path):
    """PLAN-07-04: auto routes through _resolve_strategy then dispatches once."""
    from mostlyright.weather.obs import obs

    monkeypatch.setenv("TRADEWINDS_CACHE_DIR", str(tmp_path))
    monkeypatch.delenv("TW_HOSTED_URL", raising=False)

    with (
        patch(
            "mostlyright.weather.obs._resolve_strategy", return_value="exact_window"
        ) as mock_resolve,
        patch("mostlyright._exact_fetch._exact_fetch_observations", return_value=[]),
    ):
        result = obs("KNYC", "2024-03-01", "2024-03-31", strategy="auto")
    assert mock_resolve.called
    assert result is not None


def test_obs_source_iem_skips_awc_and_ghcnh_fetchers():
    """source='iem' must NOT call fetch_awc_metars or download_ghcnh."""
    from mostlyright.weather.obs import obs

    with (
        patch("mostlyright._exact_fetch.download_iem_asos", return_value=[]) as mock_iem,
        patch("mostlyright._exact_fetch.fetch_awc_metars", return_value=[]) as mock_awc,
        patch("mostlyright._exact_fetch.download_ghcnh") as mock_ghcnh,
        patch("mostlyright._exact_fetch.parse_iem_file", return_value=[]),
        patch("mostlyright._exact_fetch.parse_ghcnh_file", return_value=[]),
    ):
        _ = obs(
            "KNYC",
            "2024-03-01",
            "2024-03-31",
            source="iem",
            strategy="exact_window",
        )

    assert mock_iem.called
    mock_awc.assert_not_called()
    mock_ghcnh.assert_not_called()


def test_obs_source_none_invokes_all_three_fetchers():
    """source=None invokes all three fetchers (real names: fetch_awc_metars, etc.)."""
    from datetime import date, timedelta

    from mostlyright.weather.obs import obs

    today = date.today()
    start_iso = (today - timedelta(days=3)).isoformat()
    end_iso = today.isoformat()

    with (
        patch("mostlyright._exact_fetch.download_iem_asos", return_value=[]) as mock_iem,
        patch("mostlyright._exact_fetch.fetch_awc_metars", return_value=[]) as mock_awc,
        patch("mostlyright._exact_fetch.download_ghcnh") as mock_ghcnh,
        patch("mostlyright._exact_fetch.parse_iem_file", return_value=[]),
        patch("mostlyright._exact_fetch.parse_ghcnh_file", return_value=[]),
    ):
        _ = obs(
            "KNYC",
            start_iso,
            end_iso,
            source=None,
            strategy="exact_window",
        )

    assert mock_iem.called
    assert mock_awc.called
    assert mock_ghcnh.called


def _fake_raw_metars():
    """Two raw METAR-shaped rows on 2024-03-15 UTC.

    settlement_date_for normalizes "NYC" to LST 2024-03-15 (UTC-5; afternoon UTC
    rows land in the same LST day), so the aggregator emits a single daily row
    with obs_high_f=60, obs_low_f=40, obs_count=2.
    """
    return [
        {
            "station_code": "NYC",
            "observed_at": "2024-03-15T18:00:00Z",
            "observation_type": "METAR",
            "source": "iem",
            "temp_f": 60.0,
        },
        {
            "station_code": "NYC",
            "observed_at": "2024-03-15T12:00:00Z",
            "observation_type": "METAR",
            "source": "iem",
            "temp_f": 40.0,
        },
    ]


def test_obs_as_dataframe_true_returns_aggregated_dataframe():
    from mostlyright.weather.obs import obs

    with patch(
        "mostlyright._exact_fetch._exact_fetch_observations",
        return_value=_fake_raw_metars(),
    ):
        result = obs(
            "KNYC",
            "2024-03-15",
            "2024-03-15",
            source="iem",
            strategy="exact_window",
            as_dataframe=True,
        )
    assert isinstance(result, pd.DataFrame)
    assert len(result) == 1
    # Aggregation contract: daily rows with obs_* columns.
    assert list(result.columns)[:3] == ["date", "station", "obs_high_f"]
    assert result.iloc[0]["obs_high_f"] == 60.0
    assert result.iloc[0]["obs_low_f"] == 40.0
    assert result.iloc[0]["obs_count"] == 2
    assert result.iloc[0]["station"] == "NYC"


def test_obs_as_dataframe_false_returns_aggregated_list_of_dicts():
    from mostlyright.weather.obs import obs

    with patch(
        "mostlyright._exact_fetch._exact_fetch_observations",
        return_value=_fake_raw_metars(),
    ):
        result = obs(
            "KNYC",
            "2024-03-15",
            "2024-03-15",
            source="iem",
            strategy="exact_window",
            as_dataframe=False,
        )
    assert isinstance(result, list)
    assert len(result) == 1
    row = result[0]
    assert row["date"] == "2024-03-15"
    assert row["station"] == "NYC"
    assert row["obs_high_f"] == 60.0
    assert row["obs_low_f"] == 40.0
    assert row["obs_count"] == 2

"""Phase 7 PLAN-02 signature contract + dispatch tests for tradewinds.weather.obs."""

from __future__ import annotations

from typing import get_args
from unittest.mock import patch

import pandas as pd
import pytest


def test_obs_importable_from_tradewinds_weather():
    from tradewinds.weather import obs

    assert callable(obs)


def test_obs_importable_from_obs_module():
    from tradewinds.weather.obs import Source, Strategy, obs

    assert callable(obs)
    assert "iem" in get_args(Source)
    assert "ghcnh" in get_args(Source)
    assert "awc" in get_args(Source)
    assert set(get_args(Strategy)) == {"auto", "exact_window", "warm_cache", "hosted"}


def test_obs_signature_has_required_kwonly_params():
    import inspect

    from tradewinds.weather.obs import obs

    sig = inspect.signature(obs)
    params = sig.parameters

    assert "station" in params
    assert "start" in params
    assert "end" in params
    for name in ("source", "strategy", "as_dataframe"):
        assert params[name].kind == inspect.Parameter.KEYWORD_ONLY, (
            f"{name} must be keyword-only"
        )

    # B-6: ships as "auto" from PLAN-02 onward; never churns.
    assert params["source"].default is None
    assert params["strategy"].default == "auto"
    assert params["as_dataframe"].default is True


def test_obs_invalid_source_raises_value_error():
    from tradewinds.weather.obs import obs

    with pytest.raises(ValueError, match="source must be"):
        obs("KNYC", "2024-03-01", "2024-03-31", source="bogus")  # type: ignore[arg-type]


def test_obs_invalid_strategy_raises_value_error():
    from tradewinds.weather.obs import obs

    with pytest.raises(ValueError, match="strategy must be"):
        obs("KNYC", "2024-03-01", "2024-03-31", strategy="bogus")  # type: ignore[arg-type]


def test_obs_hosted_raises_not_implemented_with_documented_message():
    from tradewinds.weather.obs import obs

    with pytest.raises(
        NotImplementedError, match="hosted strategy deferred to v0.2.x"
    ):
        obs("KNYC", "2024-03-01", "2024-03-31", strategy="hosted")


def test_obs_warm_cache_with_source_raises_value_error():
    """warm_cache + source!=None must raise ValueError (B-3: post-merge filter
    would corrupt priority semantics)."""
    from tradewinds.weather.obs import obs

    with pytest.raises(ValueError, match="warm_cache strategy requires source=None"):
        obs("KNYC", "2024-03-01", "2024-03-31",
            source="iem", strategy="warm_cache")


def test_obs_auto_raises_not_implemented_pending_plan_04():
    from tradewinds.weather.obs import obs

    with pytest.raises(NotImplementedError, match="PLAN-07-04"):
        obs("KNYC", "2024-03-01", "2024-03-31", strategy="auto")


def test_obs_source_iem_skips_awc_and_ghcnh_fetchers():
    """source='iem' must NOT call fetch_awc_metars or download_ghcnh."""
    from tradewinds.weather.obs import obs

    with patch(
        "tradewinds._exact_fetch.download_iem_asos", return_value=[]
    ) as mock_iem, patch(
        "tradewinds._exact_fetch.fetch_awc_metars", return_value=[]
    ) as mock_awc, patch(
        "tradewinds._exact_fetch.download_ghcnh"
    ) as mock_ghcnh, patch(
        "tradewinds._exact_fetch.parse_iem_file", return_value=[]
    ), patch(
        "tradewinds._exact_fetch.parse_ghcnh_file", return_value=[]
    ):
        _ = obs(
            "KNYC", "2024-03-01", "2024-03-31",
            source="iem", strategy="exact_window",
        )

    assert mock_iem.called
    mock_awc.assert_not_called()
    mock_ghcnh.assert_not_called()


def test_obs_source_none_invokes_all_three_fetchers():
    """source=None invokes all three fetchers (real names: fetch_awc_metars, etc.)."""
    from datetime import date, timedelta

    from tradewinds.weather.obs import obs

    today = date.today()
    start_iso = (today - timedelta(days=3)).isoformat()
    end_iso = today.isoformat()

    with patch(
        "tradewinds._exact_fetch.download_iem_asos", return_value=[]
    ) as mock_iem, patch(
        "tradewinds._exact_fetch.fetch_awc_metars", return_value=[]
    ) as mock_awc, patch(
        "tradewinds._exact_fetch.download_ghcnh"
    ) as mock_ghcnh, patch(
        "tradewinds._exact_fetch.parse_iem_file", return_value=[]
    ), patch(
        "tradewinds._exact_fetch.parse_ghcnh_file", return_value=[]
    ):
        _ = obs(
            "KNYC", start_iso, end_iso,
            source=None, strategy="exact_window",
        )

    assert mock_iem.called
    assert mock_awc.called
    assert mock_ghcnh.called


def test_obs_as_dataframe_true_returns_dataframe():
    from tradewinds.weather.obs import obs

    fake_rows = [
        {"date": "2024-03-15", "station": "KNYC", "source": "iem",
         "obs_high_f": 60.0, "obs_low_f": 40.0},
    ]
    with patch(
        "tradewinds._exact_fetch._exact_fetch_observations", return_value=fake_rows
    ):
        result = obs(
            "KNYC", "2024-03-15", "2024-03-15",
            source="iem", strategy="exact_window", as_dataframe=True,
        )
    assert isinstance(result, pd.DataFrame)
    assert len(result) == 1


def test_obs_as_dataframe_false_returns_list_of_dicts():
    from tradewinds.weather.obs import obs

    fake_rows = [
        {"date": "2024-03-15", "station": "KNYC", "source": "iem",
         "obs_high_f": 60.0, "obs_low_f": 40.0},
    ]
    with patch(
        "tradewinds._exact_fetch._exact_fetch_observations", return_value=fake_rows
    ):
        result = obs(
            "KNYC", "2024-03-15", "2024-03-15",
            source="iem", strategy="exact_window", as_dataframe=False,
        )
    assert isinstance(result, list)
    assert result == fake_rows

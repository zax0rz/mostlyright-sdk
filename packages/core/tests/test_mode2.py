"""Unit tests for tradewinds.mode2 (Phase 3 Mode 2 dispatch seam)."""

from __future__ import annotations

import pandas as pd
import pytest
from tradewinds.core.exceptions import SourceMismatchError
from tradewinds.mode2 import (
    _VALID_OBSERVATION_SOURCES,
    assert_source_identity,
    research_by_source,
)


def test_valid_sources_documented():
    """Mode 2 supports the v0.14.1 observation sources + ghcnh alias."""
    # `ghcnh` and `ghcnh.archive` are both accepted (parser emits the
    # bare `ghcnh`; Mode 2 maps `.archive` as an alias).
    expected = frozenset({"iem.archive", "iem.live", "awc.live", "ghcnh", "ghcnh.archive"})
    assert expected == _VALID_OBSERVATION_SOURCES


def test_unknown_source_raises():
    with pytest.raises(ValueError, match="Mode 2 source must be one of"):
        research_by_source("KNYC", "bogus.source", "2025-01-01", "2025-01-31")


def test_research_by_source_returns_dataframe_with_source_attrs(tmp_path, monkeypatch) -> None:
    """Mode 2 real impl: returns DataFrame with per-row source + attrs.

    Patches the underlying fetcher to return synthetic rows tagged
    `iem.archive` so the test doesn't hit the network.
    """
    import importlib

    monkeypatch.setenv("TRADEWINDS_CACHE_DIR", str(tmp_path))
    research_module = importlib.import_module("tradewinds.research")
    synthetic_obs = [
        {
            "station_code": "KNYC",
            "observed_at": "2025-01-06T12:00:00+00:00",
            "source": "iem.archive",
            "temp_c": 5.0,
        },
        {
            "station_code": "KNYC",
            "observed_at": "2025-01-06T13:00:00+00:00",
            "source": "awc.live",  # filtered out by source mask
            "temp_c": 6.0,
        },
    ]
    monkeypatch.setattr(
        research_module, "_fetch_observations_range", lambda *a, **kw: synthetic_obs
    )
    monkeypatch.setattr(research_module, "_all_caches_warm", lambda *a, **kw: True)

    df = research_by_source("KNYC", "iem.archive", "2025-01-06", "2025-01-12")
    # Only the iem.archive row should survive the filter.
    assert len(df) == 1
    assert (df["source"] == "iem.archive").all()
    assert df.attrs.get("source") == "iem.archive"
    assert df.attrs.get("retrieved_at") is not None


def test_research_by_source_empty_carries_attrs(tmp_path, monkeypatch) -> None:
    """Even when no rows match, the empty DataFrame carries provenance."""
    import importlib

    monkeypatch.setenv("TRADEWINDS_CACHE_DIR", str(tmp_path))
    research_module = importlib.import_module("tradewinds.research")
    monkeypatch.setattr(research_module, "_fetch_observations_range", lambda *a, **kw: [])
    monkeypatch.setattr(research_module, "_all_caches_warm", lambda *a, **kw: True)
    df = research_by_source("KNYC", "iem.archive", "2025-01-06", "2025-01-12")
    assert df.empty
    assert df.attrs.get("source") == "iem.archive"


def test_research_by_source_ghcnh_alias(tmp_path, monkeypatch) -> None:
    """`ghcnh` and `ghcnh.archive` are interchangeable (parser emits bare form)."""
    import importlib

    monkeypatch.setenv("TRADEWINDS_CACHE_DIR", str(tmp_path))
    research_module = importlib.import_module("tradewinds.research")
    synthetic_obs = [
        {
            "station_code": "KNYC",
            "observed_at": "2025-01-06T12:00:00+00:00",
            "source": "ghcnh",
            "temp_c": 5.0,
        },
    ]
    monkeypatch.setattr(
        research_module, "_fetch_observations_range", lambda *a, **kw: synthetic_obs
    )
    monkeypatch.setattr(research_module, "_all_caches_warm", lambda *a, **kw: True)
    # Caller asks for `ghcnh.archive`; parser emitted `ghcnh`. Alias.
    df = research_by_source("KNYC", "ghcnh.archive", "2025-01-06", "2025-01-12")
    assert len(df) == 1
    assert (df["source"] == "ghcnh.archive").all()


def test_research_by_source_as_dataframe_false(tmp_path, monkeypatch) -> None:
    import importlib

    monkeypatch.setenv("TRADEWINDS_CACHE_DIR", str(tmp_path))
    research_module = importlib.import_module("tradewinds.research")
    raw = [
        {
            "station_code": "KNYC",
            "observed_at": "2025-01-06T12:00:00+00:00",
            "source": "iem.archive",
            "temp_c": 5.0,
        }
    ]
    monkeypatch.setattr(research_module, "_fetch_observations_range", lambda *a, **kw: raw)
    monkeypatch.setattr(research_module, "_all_caches_warm", lambda *a, **kw: True)
    out = research_by_source("KNYC", "iem.archive", "2025-01-06", "2025-01-12", as_dataframe=False)
    assert isinstance(out, list)
    assert len(out) == 1
    assert out[0]["source"] == "iem.archive"


def test_assert_source_identity_happy():
    df = pd.DataFrame({"source": ["iem.archive", "iem.archive"]})
    assert_source_identity(df, "iem.archive")  # no raise


def test_assert_source_identity_mismatch_raises():
    df = pd.DataFrame({"source": ["iem.archive", "awc.live"]})
    with pytest.raises(SourceMismatchError) as exc:
        assert_source_identity(df, "iem.archive")
    assert exc.value.role == "observations"
    assert "awc.live" in str(exc.value)


def test_assert_source_identity_no_source_column_is_noop():
    """If df has no source column, assert_source_identity passes (let
    Validator handle that case)."""
    df = pd.DataFrame({"other": [1, 2]})
    assert_source_identity(df, "iem.archive")


def test_assert_source_identity_empty_df():
    df = pd.DataFrame({"source": []})
    assert_source_identity(df, "iem.archive")

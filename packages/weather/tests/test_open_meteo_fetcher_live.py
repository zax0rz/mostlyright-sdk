"""Phase 20 OM-01 LIVE TESTS — real Open-Meteo Previous Runs API.

Excluded from CI per CLAUDE.md (``@pytest.mark.live``). Run manually
before each publish::

    uv run pytest packages/weather/tests/test_open_meteo_fetcher_live.py -m live -v

If GFS data for 2024-06-01 has been rotated out of the Previous Runs
archive (unlikely but possible), the live test may fail. The unit-mocked
tests in :mod:`test_open_meteo_fetcher` are the deterministic regression.
"""

from __future__ import annotations

import pandas as pd
import pytest
from mostlyright.weather import fetch_open_meteo


@pytest.mark.live
def test_live_fetch_open_meteo_nyc_20240601_returns_non_empty() -> None:
    df = fetch_open_meteo(
        "NYC",
        "2024-06-01",
        "2024-06-01",
        model="gfs_global",
        mode="training",
    )
    assert isinstance(df, pd.DataFrame)
    assert len(df) > 0


@pytest.mark.live
def test_live_fetch_open_meteo_all_rows_have_issued_at() -> None:
    df = fetch_open_meteo(
        "NYC",
        "2024-06-01",
        "2024-06-01",
        model="gfs_global",
        mode="training",
    )
    assert df["issued_at"].notna().all()


@pytest.mark.live
def test_live_fetch_open_meteo_source_identity() -> None:
    df = fetch_open_meteo(
        "NYC",
        "2024-06-01",
        "2024-06-01",
        model="gfs_global",
        mode="training",
    )
    assert (df["source"] == "open_meteo.previous_runs").all()


@pytest.mark.live
def test_live_fetch_open_meteo_nyc_h23_conservative_floor_matches_formula() -> None:
    """The 23:00 UTC ``valid_at`` row must have ``issued_at`` ==
    2024-05-31T18:00Z per the conservative-floor formula (NYC GFS worked
    example from ``20-RESEARCH.md`` §Issued-at derivation math).
    """
    df = fetch_open_meteo(
        "NYC",
        "2024-06-01",
        "2024-06-01",
        model="gfs_global",
        mode="training",
    )
    h23 = df[df["valid_at"] == pd.Timestamp("2024-06-01T23:00:00Z")]
    assert len(h23) == 1
    expected_issued_at = pd.Timestamp("2024-05-31T18:00:00Z")
    assert h23["issued_at"].iloc[0] == expected_issued_at


@pytest.mark.live
def test_live_fetch_open_meteo_valid_at_tz_aware() -> None:
    df = fetch_open_meteo(
        "NYC",
        "2024-06-01",
        "2024-06-01",
        model="gfs_global",
        mode="training",
    )
    assert df["valid_at"].dt.tz is not None

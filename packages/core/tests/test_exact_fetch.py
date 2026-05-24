"""Phase 7 PLAN-01: _exact_fetch_observations orchestration.

Verifies:
  - All three fetchers (IEM ASOS, AWC, GHCNh) are invoked when source=None.
  - source="iem" skips AWC and GHCNh entirely (fetcher-boundary enforcement).
  - source="awc" skips IEM and GHCNh entirely.
  - source="ghcnh" skips IEM and AWC entirely.
  - IEM is called with exact_window=True under a separate `iem_asos_exact/`
    dest_dir namespace (B-5).
  - The function does NOT write to the canonical observations parquet cache.
  - merge_observations is called with a single positional list (NO source_priority kwarg).

All fetchers are mocked. No network.
"""

from __future__ import annotations

from unittest.mock import patch


def _info():
    from tradewinds._internal._stations import StationInfo

    return StationInfo(
        code="NYC",
        ghcnh_id="USW00094728",
        icao="KNYC",
        name="Central Park",
        tz="America/New_York",
        latitude=40.78,
        longitude=-73.97,
    )


def test_exact_fetch_module_importable():
    from tradewinds._exact_fetch import _exact_fetch_observations

    assert callable(_exact_fetch_observations)


def test_exact_fetch_source_none_invokes_all_three(tmp_path, monkeypatch):
    monkeypatch.setenv("TRADEWINDS_CACHE_DIR", str(tmp_path))
    from tradewinds._exact_fetch import _exact_fetch_observations

    with (
        patch("tradewinds._exact_fetch.download_iem_asos", return_value=[]) as mock_iem,
        patch("tradewinds._exact_fetch.fetch_awc_metars", return_value=[]) as mock_awc,
        patch("tradewinds._exact_fetch.download_ghcnh") as mock_ghcnh,
        patch("tradewinds._exact_fetch.parse_iem_file", return_value=[]),
        patch("tradewinds._exact_fetch.parse_ghcnh_file", return_value=[]),
        patch("tradewinds._exact_fetch.awc_to_observation", return_value=None),
    ):
        # Use a historical window so AWC is skipped if too old; but force it
        # to NOT be too old by using a recent window (within 7 days). We're
        # mocking AWC anyway so the time gate doesn't matter for invocation count.
        from datetime import date, timedelta

        today = date.today()
        start_iso = (today - timedelta(days=3)).isoformat()
        end_iso = today.isoformat()
        _ = _exact_fetch_observations(_info(), start_iso, end_iso, source=None)

    assert mock_iem.called
    assert mock_awc.called
    # GHCNh may or may not be called depending on year-range; for a single
    # very recent week it loops over [current_year] once.
    assert mock_ghcnh.called


def test_exact_fetch_source_iem_skips_other_fetchers(tmp_path, monkeypatch):
    monkeypatch.setenv("TRADEWINDS_CACHE_DIR", str(tmp_path))
    from tradewinds._exact_fetch import _exact_fetch_observations

    with (
        patch("tradewinds._exact_fetch.download_iem_asos", return_value=[]) as mock_iem,
        patch("tradewinds._exact_fetch.fetch_awc_metars", return_value=[]) as mock_awc,
        patch("tradewinds._exact_fetch.download_ghcnh") as mock_ghcnh,
        patch("tradewinds._exact_fetch.parse_iem_file", return_value=[]),
    ):
        _ = _exact_fetch_observations(_info(), "2024-03-01", "2024-03-31", source="iem")

    assert mock_iem.called
    mock_awc.assert_not_called()
    mock_ghcnh.assert_not_called()


def test_exact_fetch_source_awc_skips_other_fetchers(tmp_path, monkeypatch):
    monkeypatch.setenv("TRADEWINDS_CACHE_DIR", str(tmp_path))
    from datetime import date, timedelta

    from tradewinds._exact_fetch import _exact_fetch_observations

    today = date.today()
    start_iso = (today - timedelta(days=3)).isoformat()
    end_iso = today.isoformat()

    with (
        patch("tradewinds._exact_fetch.download_iem_asos") as mock_iem,
        patch("tradewinds._exact_fetch.fetch_awc_metars", return_value=[]) as mock_awc,
        patch("tradewinds._exact_fetch.download_ghcnh") as mock_ghcnh,
    ):
        _ = _exact_fetch_observations(_info(), start_iso, end_iso, source="awc")

    mock_iem.assert_not_called()
    assert mock_awc.called
    mock_ghcnh.assert_not_called()


def test_exact_fetch_source_ghcnh_skips_other_fetchers(tmp_path, monkeypatch):
    monkeypatch.setenv("TRADEWINDS_CACHE_DIR", str(tmp_path))
    from tradewinds._exact_fetch import _exact_fetch_observations

    with (
        patch("tradewinds._exact_fetch.download_iem_asos") as mock_iem,
        patch("tradewinds._exact_fetch.fetch_awc_metars") as mock_awc,
        patch("tradewinds._exact_fetch.download_ghcnh") as mock_ghcnh,
        patch("tradewinds._exact_fetch.parse_ghcnh_file", return_value=[]),
    ):
        _ = _exact_fetch_observations(_info(), "2024-03-01", "2024-03-31", source="ghcnh")

    mock_iem.assert_not_called()
    mock_awc.assert_not_called()
    assert mock_ghcnh.called


def test_exact_fetch_iem_called_with_exact_window_true_and_separate_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("TRADEWINDS_CACHE_DIR", str(tmp_path))
    from tradewinds._exact_fetch import _exact_fetch_observations

    with (
        patch("tradewinds._exact_fetch.download_iem_asos", return_value=[]) as mock_iem,
        patch("tradewinds._exact_fetch.parse_iem_file", return_value=[]),
    ):
        _ = _exact_fetch_observations(_info(), "2024-03-01", "2024-03-31", source="iem")

    assert mock_iem.called
    # At least one call must pass exact_window=True
    saw_exact = False
    saw_exact_dir = False
    for call in mock_iem.call_args_list:
        kwargs = call.kwargs
        if kwargs.get("exact_window") is True:
            saw_exact = True
        # 4th positional arg is dest_dir
        if len(call.args) >= 4:
            dest_dir = call.args[3]
            if "iem_asos_exact" in str(dest_dir):
                saw_exact_dir = True
    assert saw_exact, "expected at least one download_iem_asos call with exact_window=True"
    assert saw_exact_dir, "expected dest_dir under sources/iem_asos_exact/"


def test_exact_fetch_does_not_write_canonical_parquet(tmp_path, monkeypatch):
    """The function imports neither write_cache nor cache_path — verifiable via source."""
    monkeypatch.setenv("TRADEWINDS_CACHE_DIR", str(tmp_path))
    import tradewinds._exact_fetch as mod

    src = __import__("pathlib").Path(mod.__file__).read_text(encoding="utf-8")
    # No write to canonical parquet cache — search for the call expression,
    # not the substring (which appears in explanatory comments).
    assert "write_cache(" not in src
    # No use of cache_path helper that would build canonical paths.
    assert "cache_path(" not in src
    # No source_priority KWARG — merge_observations takes a single positional.
    # Look for the kwarg-call shape so the explanatory comment text doesn't trip
    # the check.
    assert "source_priority=" not in src


def test_exact_fetch_returns_merged_rows(tmp_path, monkeypatch):
    """merge_observations is called and its output returned."""
    monkeypatch.setenv("TRADEWINDS_CACHE_DIR", str(tmp_path))
    from tradewinds._exact_fetch import _exact_fetch_observations

    fake_rows = [
        {
            "station_code": "NYC",
            "observed_at": "2024-03-15T12:00:00Z",
            "observation_type": "METAR",
            "source": "iem",
            "temperature_f": 60.0,
        }
    ]

    with (
        patch("tradewinds._exact_fetch.download_iem_asos", return_value=[tmp_path / "fake.csv"]),
        patch("tradewinds._exact_fetch.parse_iem_file", return_value=fake_rows),
    ):
        result = _exact_fetch_observations(_info(), "2024-03-15", "2024-03-15", source="iem")

    assert isinstance(result, list)
    assert len(result) == 1
    assert result[0]["source"] == "iem"
    assert result[0]["station_code"] == "NYC"

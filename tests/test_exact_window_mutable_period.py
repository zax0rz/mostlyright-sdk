"""Mutable-period invariants for exact_window strategy.

Iron law: exact_window queries that cross the current LST month MUST NOT
write the canonical ``observations/{STATION}/{YYYY}/{MM}.parquet`` for that
month, because the current month is still mutable (incomplete data).
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pytest


def _canonical_parquet_paths(cache_dir: Path) -> list[Path]:
    """All files under v1/observations/{STATION}/{YYYY}/{MM}.parquet."""
    return list((cache_dir / "v1" / "observations").rglob("*.parquet"))


def _iem_asos_exact_paths(cache_dir: Path) -> list[Path]:
    """All files under v1/sources/iem_asos_exact/{STATION}/.

    Per B-5 fix: exact-window CSVs live in a physically separate directory
    (sources/iem_asos_exact/) from canonical yearly CSVs (sources/iem_asos/).
    No filename infix is used to distinguish them — separation is at the
    directory level only. The ``_partial`` infix from ``_iem_cache_filename``
    (iem_asos.py:75-93) still applies when chunk_end > today_utc, but it
    is the EXISTING infix, not a new ``_exact`` one.
    """
    return list((cache_dir / "v1" / "sources" / "iem_asos_exact").rglob("iem_*.csv"))


def _canonical_iem_paths(cache_dir: Path) -> list[Path]:
    """All files under v1/sources/iem_asos/{STATION}/ — canonical yearly namespace."""
    return list((cache_dir / "v1" / "sources" / "iem_asos").rglob("iem_*.csv"))


@pytest.mark.live
def test_exact_window_crossing_current_lst_month_does_not_write_canonical(
    tmp_path, monkeypatch
):
    """exact_window across the current LST month must not pollute canonical cache."""
    cache_dir = tmp_path / "tw_cache"
    cache_dir.mkdir()
    monkeypatch.setenv("TRADEWINDS_CACHE_DIR", str(cache_dir))

    from tradewinds.weather import obs

    today = date.today()
    # Window spans last 14 days — guaranteed to include current LST month
    # (and likely span the month boundary).
    start = today - timedelta(days=14)
    end = today

    _ = obs(
        "KNYC", start.isoformat(), end.isoformat(),
        source="iem", strategy="exact_window",
    )

    canonical = _canonical_parquet_paths(cache_dir)
    assert canonical == [], (
        "exact_window must NOT write canonical observations/{STATION}/{YYYY}/{MM}.parquet"
        f" — found: {canonical}"
    )

    # Per B-5: exact_window IEM CSVs go to sources/iem_asos_exact/, NOT
    # sources/iem_asos/. Verify the canonical-iem-source dir is untouched.
    canonical_iem = _canonical_iem_paths(cache_dir)
    assert canonical_iem == [], (
        "exact_window must NOT write to canonical sources/iem_asos/ directory"
        f" — found: {canonical_iem}"
    )


@pytest.mark.live
def test_exact_window_partial_infix_for_mutable_month(tmp_path, monkeypatch):
    """When exact_window query touches a still-mutable date, the IEM CSV cache
    uses the EXISTING ``_partial`` filename infix (from ``_iem_cache_filename``
    at iem_asos.py:75-93) when chunk_end > today_utc, AND the file lives
    under the separate ``sources/iem_asos_exact/`` directory namespace (per B-5).
    There is NO ``_exact`` or ``_partial_exact`` filename infix — separation is
    at the directory level only.
    """
    cache_dir = tmp_path / "tw_cache"
    cache_dir.mkdir()
    monkeypatch.setenv("TRADEWINDS_CACHE_DIR", str(cache_dir))

    from tradewinds.weather import obs

    today = date.today()
    # Query that overshoots today_utc so the chunk gets the _partial infix.
    start = today - timedelta(days=3)
    end = today + timedelta(days=1)

    _ = obs(
        "KNYC", start.isoformat(), end.isoformat(),
        source="iem", strategy="exact_window",
    )

    # Any IEM CSVs written for this query must (a) live under
    # sources/iem_asos_exact/ and (b) use the EXISTING ``_partial`` infix
    # (the same infix the canonical fetcher uses for chunk_end > today_utc).
    exact_csvs = _iem_asos_exact_paths(cache_dir)
    if exact_csvs:  # only check if anything was cached at all
        has_partial_infix = any("_partial_" in p.name for p in exact_csvs)
        assert has_partial_infix, (
            "Expected the existing _partial_ filename infix on at least one "
            "cached exact-window IEM CSV when chunk overshoots today_utc; "
            f"got: {[p.name for p in exact_csvs]}"
        )
        # B-5 sanity: no `_exact` or `_partial_exact` invented infix
        for p in exact_csvs:
            assert "_exact_" not in p.name and "_partial_exact_" not in p.name, (
                f"B-5: exact-window separation is at the directory level "
                f"(sources/iem_asos_exact/), NOT filename infix. Found: {p.name}"
            )

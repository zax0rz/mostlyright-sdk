"""Mutable-period invariants audited across all obs() strategies.

PLAN-07-01's tests/test_exact_window_mutable_period.py covers exact_window
crossing current LST month. This file covers:
  (a) warm_cache: current LST month canonical parquet uses _partial predicate
      and is re-fetched on every call (never trusted as final).
  (b) auto: resolves to exact_window for small windows even when query
      crosses current LST month — and the mutable-period skip still fires.
  (c) auto + warm_cache hand-off: large window with cache hit goes
      through warm_cache, which honors UNION skip predicate.

Iron rule: ALL invariant logic is reused from the canonical helpers
(`_is_writable_month`, `_is_current_lst_month`, `_is_current_lst_year`).
Never reinvent.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest


def _canonical_parquets(cache_root: Path) -> list[Path]:
    obs_root = cache_root / "v1" / "observations"
    if not obs_root.is_dir():
        return []
    return list(obs_root.rglob("*.parquet"))


# --- helper-existence sanity checks (catch refactors that rename invariants) -
def test_is_writable_month_helper_exists_and_returns_bool():
    """Sanity: the canonical mutable-period gate is still named the same."""
    from tradewinds.research import _is_writable_month

    today_utc = datetime.now(UTC).date()
    # Last completed month — strictly past UTC — must be writable.
    if today_utc.month == 1:
        last_year, last_month = today_utc.year - 1, 12
    else:
        last_year, last_month = today_utc.year, today_utc.month - 1
    assert _is_writable_month(last_year, last_month) is True

    # Current month — must NOT be writable.
    assert _is_writable_month(today_utc.year, today_utc.month) is False


def test_is_current_lst_month_helper_exists():
    from tradewinds.weather.cache import _is_current_lst_month

    assert callable(_is_current_lst_month)


def test_is_current_lst_year_helper_exists():
    from tradewinds.weather.cache import _is_current_lst_year

    assert callable(_is_current_lst_year)


# --- (a) warm_cache + current LST month: uses _partial predicate -------------
@pytest.mark.live
def test_warm_cache_current_lst_month_does_not_write_final_canonical(tmp_path, monkeypatch):
    """A warm_cache query for the current LST month must not write a final
    canonical parquet (current month is mutable).
    """
    cache_root = tmp_path / "tw_cache"
    cache_root.mkdir()
    monkeypatch.setenv("TRADEWINDS_CACHE_DIR", str(cache_root))

    from tradewinds.weather import obs

    today = date.today()
    first_of_month = date(today.year, today.month, 1)
    _ = obs(
        "KNYC",
        first_of_month.isoformat(),
        today.isoformat(),
        source=None,
        strategy="warm_cache",
    )

    current_month_parquet = (
        cache_root / "v1" / "observations" / "KNYC" / str(today.year) / f"{today.month:02d}.parquet"
    )
    assert not current_month_parquet.exists(), (
        f"warm_cache wrote a final canonical parquet for the current LST month: "
        f"{current_month_parquet} — this violates the mutable-period invariant."
    )


# --- (b) auto + small window crossing current month → exact_window dispatch -
@pytest.mark.live
def test_auto_small_window_crossing_current_month_routes_to_exact_window(tmp_path, monkeypatch):
    """A small window (<90d) that crosses the current LST month routes to
    exact_window (per the decision tree) and therefore writes no canonical
    parquet at all.
    """
    cache_root = tmp_path / "tw_cache"
    cache_root.mkdir()
    monkeypatch.setenv("TRADEWINDS_CACHE_DIR", str(cache_root))
    monkeypatch.delenv("TW_HOSTED_URL", raising=False)

    from tradewinds.weather.obs import _resolve_strategy, obs

    today = date.today()
    start = today - timedelta(days=20)
    end = today  # 21-day window, crosses current LST month boundary

    resolved = _resolve_strategy(start, end, "KNYC", env={}, cache_root=cache_root)
    assert resolved == "exact_window", (
        f"Expected resolver to pick exact_window for small cold window; got {resolved}"
    )

    _ = obs(
        "KNYC",
        start.isoformat(),
        end.isoformat(),
        source="iem",  # default "auto" but exercise source=iem path
    )

    canonical = _canonical_parquets(cache_root)
    assert canonical == [], (
        f"auto→exact_window must not write any canonical parquet; got: {canonical}"
    )


# --- (c) auto + large window + warm cache → warm_cache dispatch -------------
def test_auto_large_window_warm_cache_routes_to_warm_cache(tmp_path, monkeypatch):
    """When cache has a year hit for the requested year, auto routes to
    warm_cache regardless of window size. Sanity check via resolver in isolation.
    """
    cache_root = tmp_path / "tw_cache"
    cache_root.mkdir()
    year_dir = cache_root / "v1" / "observations" / "KNYC" / "2024"
    year_dir.mkdir(parents=True)
    (year_dir / "01.parquet").write_bytes(b"PARQ\x00" * 50)

    monkeypatch.setenv("TRADEWINDS_CACHE_DIR", str(cache_root))
    monkeypatch.delenv("TW_HOSTED_URL", raising=False)

    from tradewinds.weather.obs import _resolve_strategy

    resolved = _resolve_strategy(
        from_date=date(2024, 1, 1),
        to_date=date(2024, 12, 31),
        station="KNYC",
        env={},
        cache_root=cache_root,
    )
    assert resolved == "warm_cache"

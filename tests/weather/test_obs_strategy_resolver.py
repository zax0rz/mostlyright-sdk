"""Phase 7 PLAN-04 decision-matrix unit tests for _resolve_strategy.

The decision tree has 3 inputs (window-size, cache-state, env-var) which
yield 2x2x2 = 8 cells; we exercise 6 representative transitions plus
boundary + end-to-end coverage.
"""

from __future__ import annotations

from datetime import date

import pytest


@pytest.fixture
def empty_cache(tmp_path):
    """Cache root that exists but has no parquets."""
    return tmp_path / "empty_cache"


@pytest.fixture
def warm_cache(tmp_path):
    """Cache root with a parquet for (KNYC, 2024) seeded."""
    root = tmp_path / "warm_cache"
    year_dir = root / "v1" / "observations" / "KNYC" / "2024"
    year_dir.mkdir(parents=True)
    (year_dir / "03.parquet").write_bytes(b"PARQ\x00" * 100)  # bogus parquet bytes
    return root


# --- Case 1: small window + no cache + no env -> exact_window ----------------
def test_resolver_small_window_cold_no_env_returns_exact_window(empty_cache):
    from tradewinds.weather.obs import _resolve_strategy

    result = _resolve_strategy(
        from_date=date(2024, 3, 1),
        to_date=date(2024, 3, 31),  # 31 days < 90
        station="KNYC",
        env={},
        cache_root=empty_cache,
    )
    assert result == "exact_window"


# --- Case 2: small window + cache hit + no env -> warm_cache -----------------
def test_resolver_small_window_warm_no_env_returns_warm_cache(warm_cache):
    from tradewinds.weather.obs import _resolve_strategy

    result = _resolve_strategy(
        from_date=date(2024, 3, 1),
        to_date=date(2024, 3, 31),
        station="KNYC",
        env={},
        cache_root=warm_cache,
    )
    assert result == "warm_cache"


# --- Case 3: small window + any state + env set -> hosted --------------------
def test_resolver_env_set_overrides_everything_to_hosted(empty_cache):
    from tradewinds.weather.obs import _resolve_strategy

    result = _resolve_strategy(
        from_date=date(2024, 3, 1),
        to_date=date(2024, 3, 31),
        station="KNYC",
        env={"TW_HOSTED_URL": "https://api.example.com"},
        cache_root=empty_cache,
    )
    assert result == "hosted"


# --- Case 4: large window + no cache + no env -> warm_cache (fallback) -------
def test_resolver_large_window_cold_no_env_returns_warm_cache_fallback(empty_cache):
    from tradewinds.weather.obs import _resolve_strategy

    result = _resolve_strategy(
        from_date=date(2024, 1, 1),
        to_date=date(2024, 12, 31),  # 366 days >= 90
        station="KNYC",
        env={},
        cache_root=empty_cache,
    )
    assert result == "warm_cache"


# --- Case 5: large window + cache hit + no env -> warm_cache -----------------
def test_resolver_large_window_warm_no_env_returns_warm_cache(warm_cache):
    from tradewinds.weather.obs import _resolve_strategy

    result = _resolve_strategy(
        from_date=date(2024, 1, 1),
        to_date=date(2024, 12, 31),
        station="KNYC",
        env={},
        cache_root=warm_cache,
    )
    assert result == "warm_cache"


# --- Case 6: large window + warm cache + env set -> hosted (env wins) --------
def test_resolver_large_window_warm_env_set_returns_hosted(warm_cache):
    from tradewinds.weather.obs import _resolve_strategy

    result = _resolve_strategy(
        from_date=date(2024, 1, 1),
        to_date=date(2024, 12, 31),
        station="KNYC",
        env={"TW_HOSTED_URL": "https://api.example.com"},
        cache_root=warm_cache,
    )
    assert result == "hosted"


# --- Bonus: exactly 90 days is "large" (boundary check) ---------------------
def test_resolver_exactly_90_day_window_is_large(empty_cache):
    from tradewinds.weather.obs import _resolve_strategy

    # 90 days exactly: from 2024-01-01 to 2024-03-30 = 90 days inclusive.
    result = _resolve_strategy(
        from_date=date(2024, 1, 1),
        to_date=date(2024, 3, 30),
        station="KNYC",
        env={},
        cache_root=empty_cache,
    )
    # window_days = 90; rule says `window_days < 90`, so 90 is NOT small.
    assert result == "warm_cache"


# --- W-2: multi-year window with warm cache in the SECOND year --------------
def test_resolver_multi_year_window_sees_cache_in_either_year(tmp_path):
    """A Dec->Nov window touching two years finds warm cache in either year."""
    from tradewinds.weather.obs import _resolve_strategy

    root = tmp_path / "mixed_cache"
    # Seed cache in 2025 only (not 2024).
    year_dir = root / "v1" / "observations" / "KMIA" / "2025"
    year_dir.mkdir(parents=True)
    (year_dir / "06.parquet").write_bytes(b"PARQ\x00")

    result = _resolve_strategy(
        from_date=date(2024, 12, 1),
        to_date=date(2025, 11, 30),
        station="KMIA",
        env={},
        cache_root=root,
    )
    # Cache exists in 2025 (one of the years touched) → warm_cache.
    assert result == "warm_cache"


# --- Hosted dispatch: end-to-end check via obs() ----------------------------
def test_obs_auto_with_env_set_raises_hosted_not_implemented(monkeypatch, empty_cache):
    from tradewinds.weather.obs import obs

    monkeypatch.setenv("TW_HOSTED_URL", "https://api.example.com")
    monkeypatch.setenv("TRADEWINDS_CACHE_DIR", str(empty_cache))
    with pytest.raises(NotImplementedError, match="hosted strategy deferred to v0.2.x"):
        obs("KNYC", "2024-03-01", "2024-03-31", strategy="auto")


# --- _has_cached_year lives in cache.py (I-4) -------------------------------
def test_has_cached_year_lives_in_cache_module(tmp_path):
    from tradewinds.weather.cache import _has_cached_year

    # Empty cache returns False.
    assert _has_cached_year("KNYC", 2024, cache_root=tmp_path) is False

    # Seed a parquet → True.
    year_dir = tmp_path / "v1" / "observations" / "KNYC" / "2024"
    year_dir.mkdir(parents=True)
    (year_dir / "03.parquet").write_bytes(b"PARQ\x00")
    assert _has_cached_year("KNYC", 2024, cache_root=tmp_path) is True

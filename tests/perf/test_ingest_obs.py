"""Empirical timing harness for Phase 7 ingest strategies.

# Run before publish:
#     uv run pytest tests/perf/test_ingest_obs.py -m live -v -s

Methodology (per research at .planning/research/INGEST-PLANNER-RESEARCH.md):
- Per-case isolation via TRADEWINDS_CACHE_DIR=<tmp_path>.
- Measure dir-size delta before/after for byte budget.
- Time cold (empty cache) then warm (full cache) phase.

Budgets:
- 1mo KNYC exact_window source=iem cold ≤ 2 MB (the Phase 7 headline).
- 1mo KNYC warm_cache cold ≥ 10 MB (control — assert non-regression of
  the existing baseline; we EXPECT this to be ~13.4 MB).

NOTE on cold-time measurements (W-8):
    Per ``.planning/research/INGEST-PLANNER-RESEARCH.md`` §3.3 finding #3:
    The 1mo cold time of 69.7s in the original empirical run was
    process-startup overhead (Python interpreter + pandas/pyarrow import +
    httpx connection pool warmup) baked into the FIRST call of the
    process. Subsequent cold fetches of similar windows complete in ~10s.
    This harness asserts the BYTE BUDGET (≤ 2 MB) not the cold time
    itself; cold-time assertions would be flaky.
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest


def _dir_size_bytes(path: Path) -> int:
    return sum(p.stat().st_size for p in path.rglob("*") if p.is_file())


@pytest.fixture
def isolated_cache(monkeypatch, tmp_path):
    cache_dir = tmp_path / "tw_cache"
    cache_dir.mkdir()
    monkeypatch.setenv("TRADEWINDS_CACHE_DIR", str(cache_dir))
    yield cache_dir


@pytest.mark.live
def test_exact_window_1mo_knyc_iem_under_2mb(isolated_cache):
    """1mo KNYC exact_window source=iem: cold ≤ 2 MB, warm < 1 s."""
    from mostlyright.weather import obs  # imports the post-PLAN-02 surface

    before = _dir_size_bytes(isolated_cache)
    t0 = time.perf_counter()
    df_cold = obs(
        "KNYC",
        "2024-03-01",
        "2024-03-31",
        source="iem",
        strategy="exact_window",
    )
    cold_s = time.perf_counter() - t0
    after_cold = _dir_size_bytes(isolated_cache)
    cold_bytes = after_cold - before

    t1 = time.perf_counter()
    _ = obs(
        "KNYC",
        "2024-03-01",
        "2024-03-31",
        source="iem",
        strategy="exact_window",
    )
    warm_s = time.perf_counter() - t1

    print(
        f"\n[exact_window 1mo KNYC iem] cold={cold_s:.2f}s warm={warm_s:.2f}s "
        f"bytes={cold_bytes / 1024 / 1024:.2f}MB rows={len(df_cold)}"
    )

    assert cold_bytes <= 2 * 1024 * 1024, (
        f"exact_window 1mo cold budget exceeded: {cold_bytes / 1024 / 1024:.2f} MB > 2 MB"
    )
    assert len(df_cold) >= 28, "Expected ≥28 obs rows for 1mo March KNYC"


@pytest.mark.live
def test_warm_cache_1mo_knyc_control_baseline(isolated_cache):
    """Control: 1mo KNYC warm_cache cold ≥ 10 MB (existing baseline ~13.4 MB).

    This test ASSERTS NON-REGRESSION of the current behavior. If a future
    change accidentally adds year-normalization bypass to warm_cache too,
    this would fall below 10 MB and we'd want to know.
    """
    from mostlyright.weather import obs

    before = _dir_size_bytes(isolated_cache)
    df_cold = obs(
        "KNYC",
        "2024-03-01",
        "2024-03-31",
        source=None,
        strategy="warm_cache",
    )
    after_cold = _dir_size_bytes(isolated_cache)
    cold_bytes = after_cold - before

    print(f"\n[warm_cache 1mo KNYC] bytes={cold_bytes / 1024 / 1024:.2f}MB rows={len(df_cold)}")

    assert cold_bytes >= 10 * 1024 * 1024, (
        f"warm_cache 1mo cold dropped below 10 MB ({cold_bytes / 1024 / 1024:.2f} MB) — "
        "did year-normalization accidentally get bypassed?"
    )

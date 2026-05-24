"""Phase 1.5 PERF-04 live performance gate.

Live (``@pytest.mark.live``) tests excluded from CI per CLAUDE.md testing
playbook. Run manually pre-merge to ``main``::

    uv run pytest -m live tests/test_live_perf.py -v

These tests guard the empirical performance budget specified in
``.planning/ROADMAP.md`` Phase 1.5: KNYC 5-year backfill <= 12 minutes wall
time at unchanged 1 req/sec politeness (PR #85 measured 10 min; 20% headroom).
"""

from __future__ import annotations

import pytest

# Per-station wall-time baselines (seconds). Derived from
# ``.planning/research/SOURCE-LIMITS.md`` PERF-05 spike + PR #85 empirical
# measurements. Update when the spike is re-run (typically v0.2 milestone).
STATION_BASELINES_SECONDS = {
    "KNYC": 12 * 60,  # PR #85 measured 10 min; 20% headroom -> 12 min
    "KMDW": 12 * 60,  # other-station regression slot
    "KLAX": 12 * 60,
    "KMIA": 12 * 60,
}


@pytest.mark.live
def test_knyc_5yr_backfill_under_12min(tmp_path, monkeypatch) -> None:
    """KNYC 5-year backfill wall-time gate + sanity checks.

    PERF-01 + PERF-03 + PERF-04 combined wall-time gate. Uses a per-test
    isolated cache so a populated user cache cannot mask a regression.
    """
    import time

    monkeypatch.setenv("TRADEWINDS_CACHE_DIR", str(tmp_path / "cache"))

    from tradewinds import research

    t0 = time.monotonic()
    df = research(station="KNYC", from_date="2020-01-01", to_date="2024-12-31")
    wall_time = time.monotonic() - t0

    assert wall_time <= STATION_BASELINES_SECONDS["KNYC"], (
        f"KNYC 5-year backfill took {wall_time:.1f}s (gate {STATION_BASELINES_SECONDS['KNYC']}s)."
    )

    # Shape sanity: 5 years of daily settlement rows ~= 1826 (one extra for the
    # leap year). Allow a wide-ish range to absorb fixture drift.
    assert len(df) > 1500, f"unexpectedly few rows: {len(df)}"


@pytest.mark.live
@pytest.mark.parametrize("station", ["KMDW"])
def test_other_station_regression_within_baseline(tmp_path, monkeypatch, station) -> None:
    """Other-station regression -- picks one of {KMDW, KLAX, KMIA}.

    Per CONTEXT.md "no fixed cross-station threshold": the gate is the
    per-station baseline. Update STATION_BASELINES_SECONDS when re-running the
    PERF-05 spike at production load.
    """
    import time

    monkeypatch.setenv("TRADEWINDS_CACHE_DIR", str(tmp_path / "cache"))

    from tradewinds import research

    t0 = time.monotonic()
    research(station=station, from_date="2024-01-01", to_date="2024-12-31")
    wall_time = time.monotonic() - t0

    baseline = STATION_BASELINES_SECONDS[station]
    assert wall_time <= baseline, (
        f"{station} 1-year backfill took {wall_time:.1f}s (gate {baseline}s)."
    )


@pytest.mark.live
def test_prefetch_parallelism_ratio_under_check(tmp_path, monkeypatch) -> None:
    """PERF-04 parallelism check: ``wall_time <= max(per_source_t_i) * 1.2``.

    PLAN-03 §success_criteria item 4 (and architect iter-1 HIGH-5): the
    parallelism check is mandated by the plan but ``research()`` returns a
    DataFrame and never surfaces ``per_source_times``. This test exercises
    ``_prefetch_sources`` directly to assert the ratio holds against real
    upstream endpoints.

    Failure mode the test catches: a regression that secretly serializes the
    4 workers (e.g. someone replaces ``ex.submit`` with direct calls in
    submit order) would have wall_time ~= sum(per_source) >> max(per_source).
    """
    import sys

    monkeypatch.setenv("TRADEWINDS_CACHE_DIR", str(tmp_path / "cache"))

    import tradewinds.research  # noqa: F401 — populates sys.modules

    research_mod = sys.modules["tradewinds.research"]
    from tradewinds._internal._stations import STATIONS

    info = STATIONS["NYC"]
    # Use a fully past year so prefetch actually runs (post-iter-1 fix skips
    # the current UTC year to avoid double-fetch).
    result = research_mod._prefetch_sources(info, "2024-01-01", "2024-12-31", "2025-01-01")

    per_source = result["per_source_times"]
    wall_time = result["wall_time"]

    assert per_source, "per_source_times empty"
    max_source = max(per_source.values())

    # 1.2x tolerance per PLAN-03 + CONTEXT.md "Parallelism check threshold".
    # The PERF-04 wiring is sound iff wall_time stays bounded by the slowest
    # worker plus thread overhead.
    assert wall_time <= max_source * 1.2, (
        f"Serial stall detected: wall_time={wall_time:.2f}s, "
        f"max(per_source)={max_source:.2f}s, "
        f"ratio={wall_time / max_source:.2f} (gate <= 1.2). "
        f"per_source_times={per_source}"
    )

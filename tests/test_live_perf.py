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
        f"KNYC 5-year backfill took {wall_time:.1f}s "
        f"(gate {STATION_BASELINES_SECONDS['KNYC']}s)."
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
    assert (
        wall_time <= baseline
    ), f"{station} 1-year backfill took {wall_time:.1f}s (gate {baseline}s)."

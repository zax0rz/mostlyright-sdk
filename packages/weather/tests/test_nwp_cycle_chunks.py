"""Phase 17 PLAN-07: NWP cycle-range chunkers + historical-depth guard."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from mostlyright.core.exceptions import HistoricalDepthError
from mostlyright.weather._fetchers._nwp_cycle_chunks import (
    CYCLE_FREQ_HOURS,
    CYCLE_HOURS,
    NWP_HISTORICAL_DEPTH,
    check_historical_depth,
    cycle_range,
)

DAY_START = datetime(2026, 5, 24, 0, tzinfo=UTC)
DAY_END = datetime(2026, 5, 24, 23, tzinfo=UTC)

ALL_MODELS = (
    # NCEP family (3 v0.1.0 + 8 Phase 17 PLAN-03)
    "hrrr",
    "gfs",
    "nbm",
    "hrrrak",
    "gefs",
    "gdas",
    "rap",
    "rrfs",
    "rtma",
    "urma",
    "cfs",
    # ECMWF family (PLAN-04)
    "ecmwf_ifs_hres",
    "ecmwf_ifs_ens",
    "ecmwf_aifs_single",
    "ecmwf_aifs_ens",
    # MSC Canadian family (PLAN-05)
    "hrdps",
    "rdps",
    "gdps",
    "geps",
    "reps",
    # HAFS + legacy (PLAN-06)
    "hafs",
    "nam",
    "href",
    "hiresw",
)


# ---------------------------------------------------------------------------
# cycle_range — cardinality per cadence
# ---------------------------------------------------------------------------


def test_cycle_range_hrrr_hourly_returns_24_cycles() -> None:
    """HRRR runs every hour — 24 cycles in a 24h window."""
    cycles = cycle_range("hrrr", DAY_START, DAY_END)
    assert len(cycles) == 24
    assert cycles[0].hour == 0
    assert cycles[-1].hour == 23


def test_cycle_range_gfs_6hourly_returns_4_cycles() -> None:
    """GFS runs at 00 / 06 / 12 / 18 Z."""
    cycles = cycle_range("gfs", DAY_START, DAY_END)
    assert [c.hour for c in cycles] == [0, 6, 12, 18]


def test_cycle_range_hrrrak_3hourly_returns_8_cycles() -> None:
    """HRRRAK runs every 3 hours."""
    cycles = cycle_range("hrrrak", DAY_START, DAY_END)
    assert [c.hour for c in cycles] == [0, 3, 6, 9, 12, 15, 18, 21]


def test_cycle_range_ecmwf_ifs_hres_6hourly() -> None:
    cycles = cycle_range("ecmwf_ifs_hres", DAY_START, DAY_END)
    assert [c.hour for c in cycles] == [0, 6, 12, 18]


def test_cycle_range_gdps_12hourly_returns_2_cycles() -> None:
    """GDPS / GEPS / HiResW run twice daily (00 / 12 Z)."""
    cycles = cycle_range("gdps", DAY_START, DAY_END)
    assert [c.hour for c in cycles] == [0, 12]


def test_cycle_range_hafs_6hourly() -> None:
    cycles = cycle_range("hafs", DAY_START, DAY_END)
    assert [c.hour for c in cycles] == [0, 6, 12, 18]


# ---------------------------------------------------------------------------
# cycle_range — edge cases
# ---------------------------------------------------------------------------


def test_cycle_range_start_after_end_returns_empty() -> None:
    assert cycle_range("hrrr", DAY_END, DAY_START) == []


def test_cycle_range_naive_start_rejected() -> None:
    with pytest.raises(ValueError, match="UTC-aware"):
        cycle_range("hrrr", datetime(2026, 5, 24, 0), DAY_END)


def test_cycle_range_naive_end_rejected() -> None:
    with pytest.raises(ValueError, match="UTC-aware"):
        cycle_range("hrrr", DAY_START, datetime(2026, 5, 24, 23))


def test_cycle_range_unknown_model_raises() -> None:
    with pytest.raises(ValueError, match="unknown model"):
        cycle_range("not_a_model", DAY_START, DAY_END)


# ---------------------------------------------------------------------------
# NWP_HISTORICAL_DEPTH — per-model AWS BDP archive depth
# ---------------------------------------------------------------------------


def test_nwp_historical_depth_hrrr_2014() -> None:
    assert NWP_HISTORICAL_DEPTH["hrrr"] == datetime(2014, 7, 30, tzinfo=UTC)


def test_nwp_historical_depth_gfs_2021() -> None:
    assert NWP_HISTORICAL_DEPTH["gfs"] == datetime(2021, 1, 1, tzinfo=UTC)


def test_nwp_historical_depth_msc_live_only_is_none() -> None:
    for m in ("hrdps", "rdps", "gdps", "geps", "reps"):
        assert NWP_HISTORICAL_DEPTH[m] is None, m


# ---------------------------------------------------------------------------
# check_historical_depth — guard
# ---------------------------------------------------------------------------


def test_check_historical_depth_predepth_raises() -> None:
    with pytest.raises(HistoricalDepthError) as exc_info:
        check_historical_depth("hrrr", datetime(2010, 1, 1, tzinfo=UTC))
    assert exc_info.value.model == "hrrr"
    assert exc_info.value.archive_depth == datetime(2014, 7, 30, tzinfo=UTC)


def test_check_historical_depth_postdepth_passes() -> None:
    # Should not raise.
    check_historical_depth("hrrr", datetime(2026, 1, 1, tzinfo=UTC))


def test_check_historical_depth_msc_historical_raises() -> None:
    """Live-only models (MSC family, archive_depth=None) raise for
    truly historical cycles. Phase 17 Wave 3 iter-5: a CURRENT cycle
    is now accepted (see ``test_check_historical_depth_msc_live_passes``)
    so the assertion targets a 30-day-old cycle that is unambiguously
    outside ``LIVE_CYCLE_WINDOW``.
    """
    from datetime import timedelta

    historical = datetime.now(UTC) - timedelta(days=30)
    with pytest.raises(HistoricalDepthError) as exc_info:
        check_historical_depth("hrdps", historical)
    assert exc_info.value.archive_depth is None


def test_check_historical_depth_msc_live_passes() -> None:
    """Phase 17 Wave 3 iter-5 review: live-only models must accept
    recent cycles. Previously ``check_historical_depth`` raised for ANY
    cycle when ``archive_depth=None`` — incorrectly rejecting current
    cycles the mirror still holds.
    """
    from datetime import timedelta

    one_hour_ago = datetime.now(UTC) - timedelta(hours=1)
    # Should NOT raise.
    check_historical_depth("hrdps", one_hour_ago)


# ---------------------------------------------------------------------------
# Registry completeness — every Phase 17 model in all three dicts
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("model", ALL_MODELS)
def test_model_registered_in_all_three_dicts(model: str) -> None:
    assert model in CYCLE_FREQ_HOURS, f"{model} missing from CYCLE_FREQ_HOURS"
    assert model in CYCLE_HOURS, f"{model} missing from CYCLE_HOURS"
    assert model in NWP_HISTORICAL_DEPTH, f"{model} missing from NWP_HISTORICAL_DEPTH"


def test_all_24_models_covered() -> None:
    assert len(ALL_MODELS) == 24
    assert set(CYCLE_FREQ_HOURS.keys()) == set(ALL_MODELS)
    assert set(CYCLE_HOURS.keys()) == set(ALL_MODELS)
    assert set(NWP_HISTORICAL_DEPTH.keys()) == set(ALL_MODELS)

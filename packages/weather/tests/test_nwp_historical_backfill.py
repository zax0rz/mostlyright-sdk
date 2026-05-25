"""Phase 17 PLAN-07: forecast_nwp historical-depth + cycle_range signature."""

from __future__ import annotations

import inspect
from datetime import UTC, datetime

import pytest

from mostlyright.core.exceptions import HistoricalDepthError


def test_forecast_nwp_signature_accepts_cycle_range_kwargs() -> None:
    from mostlyright.weather.forecast_nwp import forecast_nwp

    sig = inspect.signature(forecast_nwp)
    assert "cycle_range_start" in sig.parameters
    assert "cycle_range_end" in sig.parameters
    assert sig.parameters["cycle_range_start"].default is None
    assert sig.parameters["cycle_range_end"].default is None


def test_cycle_and_cycle_range_start_mutually_exclusive() -> None:
    from mostlyright.weather.forecast_nwp import forecast_nwp

    with pytest.raises(ValueError, match="mutually exclusive"):
        forecast_nwp(
            "KNYC",
            "hrrr",
            cycle=datetime(2026, 5, 24, 12, tzinfo=UTC),
            cycle_range_start=datetime(2026, 5, 24, 0, tzinfo=UTC),
            cycle_range_end=datetime(2026, 5, 24, 23, tzinfo=UTC),
        )


def test_cycle_range_start_requires_end() -> None:
    from mostlyright.weather.forecast_nwp import forecast_nwp

    with pytest.raises(ValueError, match="requires cycle_range_end"):
        forecast_nwp(
            "KNYC",
            "hrrr",
            cycle_range_start=datetime(2026, 5, 24, 0, tzinfo=UTC),
        )


def test_historical_cycle_predepth_raises() -> None:
    """A pre-archive cycle (HRRR < 2014-07-30) must surface
    :class:`HistoricalDepthError` before any network attempt.
    """
    from mostlyright.weather.forecast_nwp import forecast_nwp

    with pytest.raises(HistoricalDepthError) as exc_info:
        forecast_nwp(
            "KNYC",
            "hrrr",
            cycle=datetime(2010, 1, 1, tzinfo=UTC),
        )
    assert exc_info.value.archive_depth == datetime(2014, 7, 30, tzinfo=UTC)


def test_msc_model_always_raises_historical_depth() -> None:
    """MSC family is live-only on Datamart (24h retention) — every
    cycle raises ``HistoricalDepthError(archive_depth=None)``. (This
    fires in the public ``mostlyright.forecasts.forecast_nwp`` MSC
    bypass; the weather impl reuses :func:`check_historical_depth` and
    would emit the same error if reached directly.)
    """
    from mostlyright.weather.forecast_nwp import forecast_nwp

    with pytest.raises(HistoricalDepthError) as exc_info:
        forecast_nwp(
            "CYUL",
            "hrdps",
            cycle=datetime(2026, 5, 24, 12, tzinfo=UTC),
        )
    assert exc_info.value.archive_depth is None


def test_cycle_range_iteration_placeholder_not_implemented() -> None:
    """PLAN-09 wires the multi-cycle iteration body; PLAN-07 ships the
    range-builder + signature only.
    """
    from mostlyright.weather.forecast_nwp import forecast_nwp

    with pytest.raises(NotImplementedError, match="PLAN-09"):
        forecast_nwp(
            "KNYC",
            "hrrr",
            cycle_range_start=datetime(2026, 5, 24, 0, tzinfo=UTC),
            cycle_range_end=datetime(2026, 5, 24, 23, tzinfo=UTC),
        )

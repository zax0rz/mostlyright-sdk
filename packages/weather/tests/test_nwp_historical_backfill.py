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
    """cycle_range_start without cycle_range_end is half-specified —
    iter-1 unified the message with the end-alone case.
    """
    from mostlyright.weather.forecast_nwp import forecast_nwp

    with pytest.raises(ValueError, match="must both be provided"):
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


@pytest.mark.live
def test_cycle_range_iteration_placeholder_closed() -> None:
    """PLAN-09 Task 2 wires the multi-cycle iteration body. The PLAN-07
    placeholder ``NotImplementedError(match="PLAN-09")`` is now closed —
    the function iterates, fetches per-cycle, and concatenates.

    Without a live mirror or mocking, the call surface raises a
    downstream error (HistoricalDepthError for archive-floor pre-dates,
    or NoLiveForNwpError when mirrors are exhausted). We assert the
    PLAN-09 placeholder is GONE — anything else is acceptable.

    Marked ``live`` because the iteration body issues a real httpx
    byte-range fetch against the NWP archive mirror that can hang under
    network-restricted CI conditions (pre-push hook regression caught
    2026-05-27).
    """
    from mostlyright.weather.forecast_nwp import forecast_nwp

    try:
        forecast_nwp(
            "KNYC",
            "hrrr",
            cycle_range_start=datetime(2026, 5, 24, 0, tzinfo=UTC),
            cycle_range_end=datetime(2026, 5, 24, 23, tzinfo=UTC),
        )
    except NotImplementedError as exc:
        if "PLAN-09" in str(exc):
            raise AssertionError(f"PLAN-09 placeholder must be closed; still got: {exc!r}") from exc
        raise
    except Exception:
        # Any other downstream exception (HTTP, archive depth, missing
        # cfgrib) is fine — proves the placeholder was removed.
        pass


# Phase 17 Wave 3 iter-1 codex review hardening.


def test_cycle_range_end_alone_rejected() -> None:
    """cycle_range_end without cycle_range_start must NOT silently fall
    through to the default single-cycle path (codex iter-1 HIGH #2).
    """
    from mostlyright.weather.forecast_nwp import forecast_nwp

    with pytest.raises(ValueError, match="must both be provided"):
        forecast_nwp(
            "KNYC",
            "hrrr",
            cycle_range_end=datetime(2026, 5, 24, 23, tzinfo=UTC),
        )


@pytest.mark.live
def test_public_forecasts_wrapper_forwards_cycle_range_kwargs() -> None:
    """The public ``mostlyright.forecasts.forecast_nwp`` wrapper must
    forward cycle_range_start/end (codex iter-1 HIGH #1: without
    forwarding, callers would get ``TypeError("unexpected keyword
    argument")``).

    PLAN-09 Task 2 closes the placeholder, so the end-to-end check is
    now "the wrapper forwards the kwargs and we don't see TypeError or
    the PLAN-09 placeholder" rather than "we hit the placeholder".

    Marked ``live`` because the (now-implemented) iteration body issues
    a real httpx byte-range fetch against the NWP archive mirror that
    can hang under network-restricted CI conditions (pre-push hook
    regression caught 2026-05-27).
    """
    import inspect

    from mostlyright.forecasts import forecast_nwp as public_forecast_nwp

    sig = inspect.signature(public_forecast_nwp)
    assert "cycle_range_start" in sig.parameters
    assert "cycle_range_end" in sig.parameters

    # End-to-end: calling the public wrapper with the kwargs must reach
    # the (now-implemented) iteration code path. Any TypeError ("unexpected
    # keyword argument") would mean the wrapper failed to forward; any
    # NotImplementedError mentioning PLAN-09 would mean the placeholder
    # is still in place. Other downstream errors are out of scope.
    try:
        public_forecast_nwp(
            "KNYC",
            "hrrr",
            cycle_range_start=datetime(2026, 5, 24, 0, tzinfo=UTC),
            cycle_range_end=datetime(2026, 5, 24, 23, tzinfo=UTC),
        )
    except TypeError as exc:
        raise AssertionError(
            f"public wrapper failed to forward cycle_range_* kwargs: {exc!r}"
        ) from exc
    except NotImplementedError as exc:
        if "PLAN-09" in str(exc):
            raise AssertionError(f"PLAN-09 placeholder must be closed; still got: {exc!r}") from exc
        raise
    except Exception:
        # Downstream HTTP / archive-depth errors are expected (no live
        # mirror here). The kwarg-forwarding + placeholder-closed
        # invariants are already verified above.
        pass


# ---------------------------------------------------------------------------
# Phase 17 Wave 3 iter-5 review: live-only model live-cycle acceptance.
#
# Models with ``NWP_HISTORICAL_DEPTH[model] is None`` (HAFS, HREF, HiResW,
# the MSC family) previously raised ``HistoricalDepthError`` for ANY cycle
# — even an explicit current/live cycle the caller actually wanted. The
# fix: ``check_historical_depth`` now accepts cycles within
# ``LIVE_CYCLE_WINDOW`` (7 days) of wall-clock now() for live-only models,
# and raises only for truly historical requests.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("model", ["hafs", "href", "hiresw"])
def test_live_only_model_accepts_current_cycle(model: str) -> None:
    """A 1-hour-old cycle on a live-only model (depth=None) must NOT
    raise ``HistoricalDepthError`` — these models are served by NOMADS
    with short retention and the caller is asking for bytes the mirror
    still holds.
    """
    from datetime import timedelta

    from mostlyright.weather._fetchers._nwp_cycle_chunks import (
        check_historical_depth,
    )

    one_hour_ago = datetime.now(UTC) - timedelta(hours=1)
    # Should NOT raise.
    check_historical_depth(model, one_hour_ago)


@pytest.mark.parametrize("model", ["hafs", "href", "hiresw"])
def test_live_only_model_rejects_historical_cycle(model: str) -> None:
    """A 30-day-old cycle on a live-only model must still raise
    ``HistoricalDepthError`` — the bytes are gone from the mirror and
    historical backfill is not supported for these families.
    """
    from datetime import timedelta

    from mostlyright.weather._fetchers._nwp_cycle_chunks import (
        check_historical_depth,
    )

    thirty_days_ago = datetime.now(UTC) - timedelta(days=30)
    with pytest.raises(HistoricalDepthError) as exc_info:
        check_historical_depth(model, thirty_days_ago)
    assert exc_info.value.archive_depth is None
    assert exc_info.value.model == model

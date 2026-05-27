"""Pure-function cycle math for Open-Meteo issued_at derivation (Phase 20 OM-03).

Implements:

- ``floor_to_cycle(value, cycle_hours)`` -- snap a datetime down to the
  most recent cycle hour. Deterministic building block for all
  ``issued_at`` derivation.
- ``issued_at_from_previous_day(valid_at, N, cycle_hours)`` -- conservative
  lower bound for the cycle that produced a Previous Runs API
  ``_previous_dayN`` value (Phase 20 D-05).
- ``issued_at_from_live_cycle_math(now_utc, publish_lag, cycle_hours)`` --
  cycle-math fallback for Live Forecast API when Metadata API is
  unavailable (Phase 20 D-06).

All functions accept and return tz-aware UTC datetimes only. Naive
datetimes are rejected at entry to defend against TZ-confusion bugs.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta


def floor_to_cycle(
    value: datetime,
    cycle_hours: tuple[int, ...],
) -> datetime:
    """Snap ``value`` down to the most recent cycle-hour ≤ value.

    Args:
        value: tz-aware UTC datetime.
        cycle_hours: sorted tuple of UTC cycle hours (e.g. ``(0, 6, 12, 18)``
            for GFS, ``tuple(range(24))`` for HRRR hourly).

    Returns:
        A datetime aligned to one of ``cycle_hours`` on the same calendar
        day as ``value`` if any cycle ≤ ``value.hour`` exists; otherwise
        the latest cycle of the prior UTC day.

    Raises:
        ValueError: if ``cycle_hours`` is empty or ``value`` is naive.
    """
    if not cycle_hours:
        raise ValueError("cycle_hours must be non-empty")
    if value.tzinfo is None:
        raise ValueError("floor_to_cycle requires tz-aware UTC datetime")
    if value.tzinfo != UTC:
        value = value.astimezone(UTC)

    sorted_cycles = sorted(cycle_hours)
    candidates = [h for h in sorted_cycles if h <= value.hour]
    if candidates:
        target_hour = candidates[-1]
        return value.replace(hour=target_hour, minute=0, second=0, microsecond=0)
    target_hour = sorted_cycles[-1]
    prior = value - timedelta(days=1)
    return prior.replace(hour=target_hour, minute=0, second=0, microsecond=0)


def issued_at_from_previous_day(
    valid_at: datetime,
    N: int,
    cycle_hours: tuple[int, ...],
) -> datetime:
    """Conservative lower bound for the cycle producing ``_previous_dayN``.

    Per Open-Meteo substack: ``_previous_dayN`` is a seamless stitched
    stream of forecasts whose initialization was AT LEAST N*24h before
    ``valid_at``. The exact cycle is not recoverable from the response.
    Returns a datetime that is PROVABLY <= the actual cycle.

    Use this as ``issued_at`` for :class:`LeakageDetector`. May
    under-estimate the true cycle but NEVER over-estimates - no leakage
    risk.

    Args:
        valid_at: tz-aware UTC datetime of the forecast value.
        N: day-offset suffix, 1..7 (Open-Meteo only supports up to day 7).
        cycle_hours: per-model UTC cycle hours.

    Returns:
        Conservative ``issued_at`` lower bound.

    Raises:
        ValueError: if N out of 1..7 or cycle_hours empty.
    """
    if N < 1 or N > 7:
        raise ValueError(f"N must be in 1..7 (Open-Meteo previous_dayN limit); got {N}")
    upper_bound = valid_at - timedelta(hours=N * 24)
    return floor_to_cycle(upper_bound, cycle_hours)


def issued_at_from_live_cycle_math(
    now_utc: datetime,
    publish_lag: timedelta,
    cycle_hours: tuple[int, ...],
) -> datetime:
    """Cycle-math fallback for Live Forecast API ``issued_at`` (Phase 20 D-06).

    Open-Meteo's Live API response does NOT include ``model_run_time`` or
    any cycle metadata. The Metadata API endpoint URL is not publicly
    documented as of 2026-05-27 (deferred follow-up). This function
    provides a CONSERVATIVE LOWER BOUND:
    ``floor_to_cycle(now - publish_lag, cycle_hours)``.

    The actual cycle in the response may be MORE recent than this bound
    but NEVER less - no leakage risk.

    Args:
        now_utc: current UTC time.
        publish_lag: per-family conservative delay between cycle init
            and API availability (6h global, 4h mid-scale, 2h
            regional/mesoscale).
        cycle_hours: per-model UTC cycle hours.

    Returns:
        Conservative ``issued_at`` lower bound.
    """
    candidate = now_utc - publish_lag
    return floor_to_cycle(candidate, cycle_hours)


__all__ = [
    "floor_to_cycle",
    "issued_at_from_live_cycle_math",
    "issued_at_from_previous_day",
]

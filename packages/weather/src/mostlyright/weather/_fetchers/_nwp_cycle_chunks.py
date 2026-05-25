"""Cycle-range chunkers for NWP historical backfill (Phase 17 FORECAST-08).

Mirrors :func:`._iem_chunks.yearly_chunks_inclusive` for NWP cycle iteration.
Per-model cycle frequency + cycle-hour allow-list + AWS BDP archive depth
are all enumerated here so historical backfill is one ``cycle_range()``
call away.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from mostlyright.core.exceptions import HistoricalDepthError

#: Per-model cycle cadence in hours.
#:
#: - Hourly (1h): HRRR, NBM, RAP, RTMA, URMA, RRFS — analysis + nowcast.
#: - 3-hourly (3h): HRRRAK.
#: - 6-hourly (6h): GFS, GDAS, GEFS, CFS, ECMWF, HAFS, HRDPS, RDPS,
#:   REPS, NAM, HREF.
#: - 12-hourly (12h): GDPS, GEPS, HiResW.
CYCLE_FREQ_HOURS: dict[str, int] = {
    # Hourly
    "hrrr": 1,
    "nbm": 1,
    "rap": 1,
    "rtma": 1,
    "urma": 1,
    "rrfs": 1,
    # 3-hourly
    "hrrrak": 3,
    # 6-hourly
    "gfs": 6,
    "gdas": 6,
    "gefs": 6,
    "cfs": 6,
    "ecmwf_ifs_hres": 6,
    "ecmwf_ifs_ens": 6,
    "ecmwf_aifs_single": 6,
    "ecmwf_aifs_ens": 6,
    "hafs": 6,
    "hrdps": 6,
    "rdps": 6,
    "reps": 6,
    "nam": 6,
    "href": 6,
    # 12-hourly
    "gdps": 12,
    "geps": 12,
    "hiresw": 12,
}


#: Per-model allowed cycle-hour set. Used by :func:`cycle_range` to skip
#: non-canonical hours when iterating a UTC date range. A ``cur.hour`` not
#: in this tuple is skipped silently.
CYCLE_HOURS: dict[str, tuple[int, ...]] = {
    "hrrr": tuple(range(24)),
    "hrrrak": (0, 3, 6, 9, 12, 15, 18, 21),
    "nbm": tuple(range(24)),
    "rap": tuple(range(24)),
    "rtma": tuple(range(24)),
    "urma": tuple(range(24)),
    "rrfs": tuple(range(24)),
    "gfs": (0, 6, 12, 18),
    "gdas": (0, 6, 12, 18),
    "gefs": (0, 6, 12, 18),
    "cfs": (0, 6, 12, 18),
    "ecmwf_ifs_hres": (0, 6, 12, 18),
    "ecmwf_ifs_ens": (0, 6, 12, 18),
    "ecmwf_aifs_single": (0, 6, 12, 18),
    "ecmwf_aifs_ens": (0, 6, 12, 18),
    "hafs": (0, 6, 12, 18),
    "hrdps": (0, 6, 12, 18),
    "rdps": (0, 6, 12, 18),
    "reps": (0, 6, 12, 18),
    "nam": (0, 6, 12, 18),
    "href": (0, 6, 12, 18),
    "gdps": (0, 12),
    "geps": (0, 12),
    "hiresw": (0, 12),
}


#: AWS BDP archive depth per model — earliest cycle the public mirror
#: holds. ``None`` means "live-only" (no archive: MSC Datamart 24h
#: retention, NOMADS-only legacy without AWS mirror). Caller cycles
#: before this date raise :class:`HistoricalDepthError`.
NWP_HISTORICAL_DEPTH: dict[str, datetime | None] = {
    "hrrr": datetime(2014, 7, 30, tzinfo=UTC),
    "hrrrak": datetime(2018, 1, 1, tzinfo=UTC),
    "gfs": datetime(2021, 1, 1, tzinfo=UTC),
    "gdas": datetime(2021, 1, 1, tzinfo=UTC),
    "gefs": datetime(2017, 1, 1, tzinfo=UTC),
    "nbm": datetime(2020, 1, 1, tzinfo=UTC),
    "rap": datetime(2020, 1, 1, tzinfo=UTC),
    "rrfs": datetime(2024, 1, 1, tzinfo=UTC),
    "rtma": datetime(2024, 1, 1, tzinfo=UTC),
    "urma": datetime(2024, 1, 1, tzinfo=UTC),
    "cfs": datetime(2011, 1, 1, tzinfo=UTC),
    "ecmwf_ifs_hres": datetime(2022, 1, 1, tzinfo=UTC),
    "ecmwf_ifs_ens": datetime(2022, 1, 1, tzinfo=UTC),
    "ecmwf_aifs_single": datetime(2024, 2, 25, 6, tzinfo=UTC),
    "ecmwf_aifs_ens": datetime(2024, 2, 25, 6, tzinfo=UTC),
    "nam": datetime(2024, 1, 1, tzinfo=UTC),
    # Live-only (no archive on the listed mirror):
    "hrdps": None,
    "rdps": None,
    "gdps": None,
    "geps": None,
    "reps": None,
    "hafs": None,
    "href": None,
    "hiresw": None,
}


def cycle_range(model: str, start_dt: datetime, end_dt: datetime) -> list[datetime]:
    """Return UTC cycles for ``model`` in ``[start_dt, end_dt]`` inclusive.

    Args:
        model: Phase 17 model id (one of :data:`CYCLE_HOURS` keys).
        start_dt: Lower bound (UTC-aware).
        end_dt: Upper bound (UTC-aware).

    Returns:
        Ordered list of cycle datetimes that match the model's
        :data:`CYCLE_HOURS` allow-list. Empty list if ``start_dt > end_dt``.

    Raises:
        ValueError: ``model`` unknown OR either datetime naive.
    """
    if model not in CYCLE_HOURS:
        raise ValueError(f"unknown model {model!r}; supported: {sorted(CYCLE_HOURS)}")
    if start_dt.tzinfo is None or end_dt.tzinfo is None:
        raise ValueError(
            "start_dt and end_dt must be UTC-aware; "
            f"got start_dt.tzinfo={start_dt.tzinfo!r}, "
            f"end_dt.tzinfo={end_dt.tzinfo!r}"
        )
    if start_dt > end_dt:
        return []
    hours = CYCLE_HOURS[model]
    out: list[datetime] = []
    start_utc = start_dt.astimezone(UTC)
    # Ceiling instead of floor: if start_dt has minutes/seconds, round
    # UP to the next hour so the returned cycle list is strictly inside
    # ``[start_dt, end_dt]``. Flooring would include the previous hour
    # which sits OUTSIDE the requested window (codex iter-4 finding).
    if start_utc.minute or start_utc.second or start_utc.microsecond:
        cur = start_utc.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    else:
        cur = start_utc.replace(minute=0, second=0, microsecond=0)
    end_utc = end_dt.astimezone(UTC)
    while cur <= end_utc:
        if cur.hour in hours:
            out.append(cur)
        cur += timedelta(hours=1)
    return out


#: Live-cycle tolerance for ``depth=None`` (live-only) models — cycles
#: newer than ``now() - LIVE_CYCLE_WINDOW`` are accepted; older cycles
#: raise :class:`HistoricalDepthError`. Phase 17 Wave 3 iter-5 review:
#: live-only models (HAFS, HREF, HiResW, MSC family on NOMADS-only paths)
#: previously raised for ANY explicit cycle, which incorrectly rejected
#: current cycles the caller actually wanted to fetch. The 7-day window
#: covers the typical NOMADS retention floor while still rejecting truly
#: historical backfill requests.
LIVE_CYCLE_WINDOW: timedelta = timedelta(days=7)


def check_historical_depth(model: str, requested_cycle: datetime) -> None:
    """Raise :class:`HistoricalDepthError` if ``requested_cycle`` is older
    than the model's AWS BDP depth.

    For live-only models (``archive_depth=None`` in
    :data:`NWP_HISTORICAL_DEPTH`), the rule is "recent cycles OK,
    historical cycles raise". A cycle within :data:`LIVE_CYCLE_WINDOW`
    of wall-clock ``now()`` is treated as live and passes through; any
    older cycle raises :class:`HistoricalDepthError` because the mirror
    no longer holds the bytes.

    Args:
        model: Phase 17 model id.
        requested_cycle: Cycle the caller asked for (UTC-aware).

    Raises:
        HistoricalDepthError: pre-depth cycle for an archived model, OR
            an older-than-:data:`LIVE_CYCLE_WINDOW` cycle for a live-only
            model (``archive_depth=None``).
        ValueError: ``model`` unknown.
    """
    if model not in NWP_HISTORICAL_DEPTH:
        raise ValueError(f"unknown model {model!r}; supported: {sorted(NWP_HISTORICAL_DEPTH)}")
    depth = NWP_HISTORICAL_DEPTH[model]
    if depth is None:
        # Phase 17 Wave 3 iter-5 review: live-only models accept current
        # cycles, reject truly historical ones. Without this branch
        # callers asking for an explicit *live* cycle (e.g. HAFS during
        # an active storm, HREF for today) would see HistoricalDepthError
        # even though the mirror has the bytes — the old behavior was a
        # blanket reject regardless of cycle freshness.
        now_utc = datetime.now(UTC)
        live_floor = now_utc - LIVE_CYCLE_WINDOW
        if requested_cycle < live_floor:
            raise HistoricalDepthError(
                f"{model}: live-only (NOMADS-only with no AWS BDP archive); "
                f"requested cycle {requested_cycle.isoformat()} is older than "
                f"the {LIVE_CYCLE_WINDOW.days}-day live-cycle window "
                f"(floor {live_floor.isoformat()}). Historical backfill is "
                "not supported for live-only models; use a recent cycle.",
                model=model,
                requested_cycle=requested_cycle,
                archive_depth=None,
            )
        # Recent cycle on a live-only model: pass through and let the
        # downstream fetcher try the mirror.
        return
    if requested_cycle < depth:
        raise HistoricalDepthError(
            f"{model}: requested cycle {requested_cycle.isoformat()} is "
            f"earlier than AWS BDP depth {depth.isoformat()}. Older "
            "cycles are deferred to a v0.2 hosted-mirror follow-up.",
            model=model,
            requested_cycle=requested_cycle,
            archive_depth=depth,
        )


__all__ = [
    "CYCLE_FREQ_HOURS",
    "CYCLE_HOURS",
    "LIVE_CYCLE_WINDOW",
    "NWP_HISTORICAL_DEPTH",
    "check_historical_depth",
    "cycle_range",
]

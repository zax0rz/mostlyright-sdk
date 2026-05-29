"""Phase 3.1 — International station expansion + daily_extremes rollup.

Phase 3.1 v0.1.0 scope: expand the v0.14.1 20-US station registry to 60
(20 US + 40 international ICAOs), add the per-event station resolver for
multi-airport cities (Paris LFPG/LFPB split), add ``daily_extremes()``
rollup with station-local IANA calendar day semantics, and surface
whole-°C source-precision for international stations.

The full STATIONS dict lives in ``_internal/_stations.py``; this module
exposes the public extension surface — ``daily_extremes(station, from_date,
to_date)`` + ``DeferredMarketError`` for sources we can't ship until v0.2
(Taipei CWA, HK HKO).
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from datetime import date as _date
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from mostlyright._internal._stations import STATIONS, is_us_station
from mostlyright.core.exceptions import MostlyRightError

logger = logging.getLogger(__name__)


__all__ = [
    "DEFERRED_STATIONS",
    "INTERNATIONAL_STATIONS",
    "DeferredMarketError",
    "daily_extremes",
]


class DeferredMarketError(MostlyRightError):
    """A market resolves to a station whose data source is deferred to v0.2.

    Currently raised for Taipei (RCSS, CWA client) and Hong Kong (HKO,
    ``weather.gov.hk`` client). v0.2 will land both clients and remove the
    deferral.
    """

    default_error_code = "DEFERRED_MARKET"


#: Phase 3.1 international ICAOs — 40 stations covering the markets
#: Polymarket lists as of v0.1.0 scope. Each entry maps the ICAO to its
#: IANA timezone (needed for station-local calendar-day extremes).
#:
#: This mapping is the legacy shape (icao -> tz string); the full
#: ``StationInfo`` (with lat/lon/country) lives in ``_internal/_stations``.
#: Kept as a thin convenience view so callers that only need the tz lookup
#: do not have to construct ``StationInfo``.
INTERNATIONAL_STATIONS: dict[str, str] = {
    icao: s.tz for icao, s in STATIONS.items() if s.country != "US"
}


#: Markets routed to stations whose data source is deferred to v0.2.
#: Phase 23 reconciled Hong Kong to its actual Polymarket settlement station,
#: HKO (the HK Observatory) — no airport ICAO, sourced from ``weather.gov.hk``,
#: so ALL HK markets now defer (previously HK-high routed via VHHH METAR).
#: Taipei moved RCTP→RCSS (Songshan); RCSS defers all markets (CWA is the sole
#: issuer there). VHHH/RCTP remain registry weather stations but no longer
#: front any deferred market.
DEFERRED_STATIONS: frozenset[str] = frozenset({"HKO", "RCSS"})

#: Minimum hourly observations per local day for tmin/tmax/tmean to be
#: published. Below this threshold the row still ships (so consumers see
#: the gap) but the aggregated temps are set to None and a ``low_coverage``
#: WARNING is logged.
_LOW_COVERAGE_THRESHOLD = 12


def _round_half_up(value: float, places: int) -> float:
    """Round ``value`` to ``places`` decimal places using HALF_UP rounding.

    Python's built-in ``round()`` uses banker's rounding (HALF_EVEN), which
    disagrees with the issuer-side convention for daily extremes
    (international issuers publish whole °C with HALF_UP). Use ``Decimal``
    for explicit HALF_UP semantics so 2.5 rounds to 3, not 2.
    """
    quantum = Decimal(10) ** -places
    return float(Decimal(str(value)).quantize(quantum, rounding=ROUND_HALF_UP))


def _resolve_tz(station: str) -> str:
    """Return the IANA timezone for ``station`` (ICAO or NWS code).

    Looks up the StationInfo entry by direct key or by .icao attribute so
    callers can pass either ``"NYC"``, ``"KNYC"``, or ``"EGLL"``.

    Raises:
        KeyError: when no registry entry matches.
    """
    info = STATIONS.get(station)
    if info is not None:
        return info.tz
    for s in STATIONS.values():
        if s.icao == station:
            return s.tz
    raise KeyError(
        f"Unknown station {station!r}. Expected one of the 66 STATIONS entries (25 US + 41 intl)."
    )


def _month_range(start: _date, end: _date) -> list[tuple[int, int]]:
    """Return inclusive ``[(year, month), ...]`` covering ``[start, end]``."""
    if start > end:
        return []
    out: list[tuple[int, int]] = []
    y, m = start.year, start.month
    while (y, m) <= (end.year, end.month):
        out.append((y, m))
        m += 1
        if m == 13:
            m = 1
            y += 1
    return out


def _utc_month_envelope(
    local_from: _date,
    local_to: _date,
    tz: Any,
) -> list[tuple[int, int]]:
    """Return UTC-keyed ``(year, month)`` tuples covering a local-date range.

    The observation cache is keyed by **UTC** year/month
    (``cache/<icao>/<UTC-year>/<UTC-month>.parquet``), but
    ``daily_extremes()`` aggregates by **station-local** calendar day.
    For any non-UTC station, the UTC observations that compose the local
    day at the *edges* of the requested window can live in the adjacent
    UTC month — e.g. Tokyo (UTC+9) local Feb 1 spans UTC Jan 31 15:00 →
    UTC Feb 1 14:59, so reading only ``(2025, 2)`` from cache would silently
    miss the leading 9 hours of the local day.

    This helper resolves the UTC envelope by converting the local-day
    boundary moments (``[local_from 00:00, local_to+1 day 00:00)``) to
    UTC, then iterating UTC months from the floor of the start to the
    ceiling of the end. Both endpoints are inclusive.

    Args:
        local_from: First station-local calendar date in the window.
        local_to: Last station-local calendar date in the window
            (inclusive).
        tz: ``zoneinfo.ZoneInfo`` for the station.

    Returns:
        List of ``(year, month)`` UTC-keyed cache months to read.
    """
    from datetime import UTC, datetime, time, timedelta

    # Local-day window endpoints. The end is exclusive — we want every
    # UTC instant in [local_from 00:00, local_to+1day 00:00) so the
    # tmax/tmin aggregate sees the full closing local day.
    start_local = datetime.combine(local_from, time.min, tzinfo=tz)
    end_local = datetime.combine(local_to + timedelta(days=1), time.min, tzinfo=tz)

    # Translate to UTC for cache-month lookup.
    start_utc = start_local.astimezone(UTC)
    end_utc = end_local.astimezone(UTC)

    # Floor start, ceiling end so we never drop a partially-overlapping
    # UTC month. ``end_utc`` is exclusive at the day level but inclusive
    # at the month level — if it lands at the very top of a month
    # (e.g. 2025-02-01 00:00 UTC) we still want to read 2025-02 to catch
    # rows stamped exactly at that boundary by upstream sources.
    out: list[tuple[int, int]] = []
    y, m = start_utc.year, start_utc.month
    end_y, end_m = end_utc.year, end_utc.month
    while (y, m) <= (end_y, end_m):
        out.append((y, m))
        m += 1
        if m == 13:
            m = 1
            y += 1
    return out


def _parse_observed_at(observed_at: str) -> Any:
    """Parse an ``"YYYY-MM-DDTHH:MM:SSZ"`` string to a UTC-aware datetime.

    Returns ``None`` on parse failure so callers can drop the row.
    Local import of ``datetime`` so the module stays cheap to import.
    """
    from datetime import UTC, datetime

    if not observed_at:
        return None
    s = observed_at
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt


def daily_extremes(
    station: str,
    from_date: _date,
    to_date: _date,
    *,
    merge: str = "live_v1",
    backend: str = "pandas",
    return_type: str = "list",
) -> list[dict[str, Any]]:
    """Roll up cached hourly observations to per-local-day temperature extremes.

    Reads from the parquet cache (``mostlyright.weather.cache.read_cache``)
    one calendar month at a time, converts each row's ``observed_at`` from
    UTC to the station's IANA local date, and aggregates per
    ``(station, local_date)``.

    The function never touches the network — it is purely a rollup over
    whatever observations the cache already has. Callers are expected to
    have run :func:`mostlyright.research` (or another fetcher) first to warm
    the cache.

    Args:
        station: 4-letter ICAO (e.g. ``"EGLL"``, ``"KNYC"``) or 3-letter
            NWS code (``"NYC"``). Resolved to a StationInfo to look up the
            IANA timezone and the country (which gates rounding precision).
        from_date: Inclusive local-calendar-day start.
        to_date: Inclusive local-calendar-day end.
        merge: Merge policy. Only ``"live_v1"`` is supported in v0.1.0;
            anything else raises ``ValueError``.

    Returns:
        ``list[dict]`` with one entry per local calendar day in
        ``[from_date, to_date]`` that had at least one cached observation.
        Each dict matches the ``schema.daily_extreme.v1`` JSON Schema:

        - ``station`` (str, ICAO)
        - ``local_date`` (str, ``YYYY-MM-DD``)
        - ``n_obs`` (int)
        - ``tmin_c`` / ``tmax_c`` / ``tmean_c`` (float or None)
        - ``precip_inches`` (float)
        - ``source_tmin`` / ``source_tmax`` (str or None)
        - ``country`` (str, informational)

        Days with ``n_obs < 12`` have ``tmin_c=tmax_c=tmean_c=None`` and a
        WARNING is logged with the ``low_coverage`` keyword.

    Raises:
        ValueError: invalid ``merge`` policy.
        KeyError: ``station`` not in the registry.

    Examples:
        >>> from datetime import date
        >>> # After warming the cache via research(), roll up two days.
        >>> rows = daily_extremes("EGLL", date(2025, 1, 1), date(2025, 1, 2))  # doctest: +SKIP
        >>> [r["local_date"] for r in rows]  # doctest: +SKIP
        ['2025-01-01', '2025-01-02']
    """
    if merge != "live_v1":
        raise ValueError(
            f"daily_extremes(merge={merge!r}) unsupported in v0.1.0; only 'live_v1' is implemented."
        )

    # Resolve registry entry — we need tz, country, and the ICAO for the
    # cache key (cache is keyed by ICAO).
    info = STATIONS.get(station)
    if info is None:
        for s in STATIONS.values():
            if s.icao == station:
                info = s
                break
    if info is None:
        raise KeyError(
            f"Unknown station {station!r}. "
            f"Expected one of the 66 STATIONS entries (25 US + 41 intl)."
        )

    # Local imports — pandas + cache may not be importable in bare installs
    # (pandas is in the `parquet` extra), and we want this module's import
    # cost to stay near zero.
    from zoneinfo import ZoneInfo

    from mostlyright.weather.cache import read_cache

    tz = ZoneInfo(info.tz)
    is_us = is_us_station(info.icao)
    # Phase 18 PREC-03: integer-°F lattice rationale.
    # US data is integer-°F native; Tgroup-encoded tenths-°C is a coded
    # representation, not independent precision. After Phase 18 PREC-01 +
    # PREC-02 recovery, temp_c values for US stations land on the integer-°F
    # lattice (e.g. 10.0=50°F, 11.1=52°F, 12.2=54°F). tmin/tmax = min/max of
    # those lattice values are themselves on the lattice — rounding to 0.1°C
    # HALF_UP is a no-op, so tmin_c/tmax_c at 0.1°C is the source-truth
    # representation. tmean_c IS an off-lattice average; 0.1°C HALF_UP
    # rounding is an honest expression of the constituent grain. International
    # stations round to whole °C per ICAO body group convention.
    # See .planning/phases/18-precision-fix-asos-integer-fahrenheit/18-CONTEXT.md.
    precision = 1 if is_us else 0  # 0.1°C for US (lattice + tmean), whole °C for intl.

    # Gather hourly rows from cache, month by month. The cache is keyed by
    # UTC year/month — for non-UTC stations the local-day window straddles
    # adjacent UTC months at the edges, so we resolve the proper UTC-month
    # envelope from the local window + tz instead of naively iterating local
    # months. ``read_cache`` already handles the current-LST-month skip + the
    # file-doesn't-exist case (returns None for both).
    rows: list[dict[str, Any]] = []
    for year, month in _utc_month_envelope(from_date, to_date, tz):
        cached = read_cache(info.icao, year, month)
        if cached:
            rows.extend(cached)

    # Bucket rows by station-local calendar date. Filter to the requested
    # window. Drop rows without a parseable timestamp.
    by_local_date: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        dt = _parse_observed_at(row.get("observed_at", ""))
        if dt is None:
            continue
        local_d = dt.astimezone(tz).date()
        if local_d < from_date or local_d > to_date:
            continue
        by_local_date.setdefault(local_d.isoformat(), []).append(row)

    # Aggregate per-day. Iterate sorted dates so output is stable.
    import contextlib

    out: list[dict[str, Any]] = []
    for local_date in sorted(by_local_date):
        day_rows = by_local_date[local_date]
        temps: list[tuple[float, str | None]] = []
        precip_sum = 0.0
        for r in day_rows:
            t = r.get("temp_c")
            if t is not None:
                with contextlib.suppress(TypeError, ValueError):
                    temps.append((float(t), r.get("source")))
            p = r.get("precip_1hr_inches")
            if p is not None:
                with contextlib.suppress(TypeError, ValueError):
                    precip_sum += float(p)

        n_obs = len(temps)
        tmin_c: float | None
        tmax_c: float | None
        tmean_c: float | None
        source_tmin: str | None
        source_tmax: str | None

        if n_obs == 0:
            tmin_c = tmax_c = tmean_c = None
            source_tmin = source_tmax = None
        elif n_obs < _LOW_COVERAGE_THRESHOLD:
            tmin_c = tmax_c = tmean_c = None
            source_tmin = source_tmax = None
            logger.warning(
                "daily_extremes low_coverage station=%s local_date=%s n_obs=%d "
                "(threshold=%d); tmin/tmax/tmean nulled",
                info.icao,
                local_date,
                n_obs,
                _LOW_COVERAGE_THRESHOLD,
            )
        else:
            min_row = min(temps, key=lambda x: x[0])
            max_row = max(temps, key=lambda x: x[0])
            mean_raw = sum(t for t, _ in temps) / n_obs
            tmin_c = _round_half_up(min_row[0], precision)
            tmax_c = _round_half_up(max_row[0], precision)
            tmean_c = _round_half_up(mean_raw, precision)
            source_tmin = min_row[1]
            source_tmax = max_row[1]

        out.append(
            {
                "station": info.icao,
                "local_date": local_date,
                "n_obs": n_obs,
                "tmin_c": tmin_c,
                "tmax_c": tmax_c,
                "tmean_c": tmean_c,
                "precip_inches": round(precip_sum, 4),
                "source_tmin": source_tmin,
                "source_tmax": source_tmax,
                "country": info.country,
            }
        )

    # Phase 6 W3-T2 (codex iter-3 P2): daily_extremes' DEFAULT return is
    # list[dict] (preserves v0.1.0 zero-behaviour-change). Backend/return
    # kwargs are OPT-IN: callers must explicitly pass return_type='wrapper'
    # (and optionally backend='polars') to get a MostlyRightResult.
    if return_type == "list" and backend == "pandas":
        return out

    from mostlyright.core._backend_dispatch import (
        validate_backend_kwargs,
        wrap_result,
    )

    if return_type == "list":
        # backend='polars' with return_type='list' is incoherent — polars
        # frames cannot exist without a wrapper to carry provenance.
        raise ValueError(
            "daily_extremes: backend='polars' requires return_type='wrapper'; "
            "got return_type='list'"
        )

    # Architect iter-1 CRITICAL-1 fix: pass through the caller's
    # return_type so a request for return_type="dataframe" actually
    # delivers a raw DataFrame instead of being silently upgraded to a
    # MostlyRightResult. validate_backend_kwargs is the gate that rejects
    # backend="polars" + return_type="dataframe" upfront.
    validate_backend_kwargs(backend, return_type)  # type: ignore[arg-type]

    import pandas as pd

    df = pd.DataFrame(out)
    # Codex iter-3 P2 fix: stamp df.attrs BEFORE wrap_result so the
    # return_type='dataframe' path (which returns df unchanged) still
    # carries the v0.1.0 provenance contract that the other 4 public
    # entry points preserve. wrap_result with return_type='dataframe'
    # is a no-op, so attrs must be stamped here.
    src = f"daily_extremes.{merge}"
    retrieved_at = datetime.now(UTC)
    df.attrs["source"] = src
    df.attrs["retrieved_at"] = retrieved_at
    df.attrs["schema_id"] = "schema.daily_extreme.v1"
    return wrap_result(
        df,
        backend=backend,  # type: ignore[arg-type]
        return_type=return_type,  # type: ignore[arg-type]
        source=src,
        retrieved_at=retrieved_at,
        schema_id="schema.daily_extreme.v1",
    )

"""``mostlyright.research`` - local-first orchestrator for the v0.14.1 ``pairs()`` join.

Public surface:

.. code-block:: python

    mostlyright.research(
        station="KNYC",
        from_date="2025-01-06",
        to_date="2025-01-12",
    )

returns a Pandas ``DataFrame`` with one row per settlement date in the
inclusive range, joining:

- NWS CLI climate observations (the Kalshi NHIGH/NLOW settlement source),
- METAR observation aggregates from IEM ASOS, AWC (when in-window), and GHCNh,
- Kalshi-style market close timestamp (4:30 PM LST in UTC).

This is byte-equivalent to ``mostlyright==0.14.1``'s ``client.pairs(...)``
for the 5 Phase 1 parity fixtures (verified in Wave 3).

NEW module - replaces the v0.14.1 ``client.pairs()`` hosted-API call with a
local pipeline composed from Wave 1 outputs:

- :func:`mostlyright.snapshot.settlement_date_for` for LST settlement-date math.
- :func:`mostlyright.weather._fetchers.iem_asos.download_iem_asos`,
  ``iem_cli.download_cli``, ``ghcnh.download_ghcnh``, ``awc.fetch_awc_metars``
  for raw-data acquisition.
- :func:`mostlyright.weather._iem.parse_iem_file`,
  ``_ghcnh.parse_ghcnh_file``, ``_climate.parse_cli_response``,
  ``_awc.awc_to_observation`` for parsing.
- :func:`mostlyright._internal.merge.merge_observations` /
  ``merge_climate`` for per-key dedup with v0.14.1 priority rules.
- :func:`mostlyright.weather.cache.read_cache` / ``write_cache`` /
  ``read_climate_cache`` / ``write_climate_cache`` for the local-first
  parquet cache (skips current LST month/year automatically).
- :func:`mostlyright._internal._pairs.build_pairs` and ``pairs_to_dataframe``
  for the actual row assembly (LIFTED verbatim from v0.14.1 ``pairs.py``).

Phase 1 scope (Wave 2): ``include_forecast=False`` only. Forecast wiring
ships in Phase 3 (multi-forecast live path). Calling with
``include_forecast=True`` raises ``NotImplementedError`` so users do not
silently get a stale stub.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime, timedelta
from datetime import date as _date
from pathlib import Path
from typing import Any

import pandas as pd

from mostlyright._internal._pairs import (
    build_pairs,
    date_range,
    pairs_to_dataframe,
)
from mostlyright._internal._stations import STATIONS, StationInfo, is_us_station
from mostlyright.snapshot import (
    _station_code_normalized,
    settlement_date_for,
)

logger = logging.getLogger(__name__)

# AWC live serves at most ~168 hours (7 days). The PLAN.md task spec
# (Phase 1 Wave 2 Task 2.1) gates AWC fetches to months that overlap that
# window - older months are IEM-ASOS + GHCNh only because AWC simply will
# not return their observations.
_AWC_LOOKBACK_HOURS = 168


def _resolve_station(station: str) -> StationInfo:
    """Resolve ``station`` (e.g. ``"KNYC"`` or ``"NYC"``) to ``StationInfo``.

    Accepts both the 3-letter NWS code (``"NYC"``) and the 4-letter ICAO
    (``"KNYC"``) - they are normalized via
    :func:`mostlyright.snapshot._station_code_normalized` (strips a leading
    ``"K"`` when the input is exactly 4 letters).

    Raises:
        ValueError: when ``station`` is not in the 20-station Phase 1
            registry, OR when ``station`` resolves to an international
            entry (Phase 3.1 expanded STATIONS to 60 — but ``research()``
            still ships only the v0.14.1 Kalshi US-only join in v0.1.0
            because NWS CLI (settlement source) is US-only and the
            settlement-window math (``snapshot._lst_offset``) is calibrated
            for US standard-time offsets). Intl callers should use
            :func:`mostlyright.international.daily_extremes` after warming
            the cache with their own observation fetcher; full intl
            ``research()`` ships in a follow-up phase.
    """
    code = _station_code_normalized(station)
    info = STATIONS.get(code)
    if info is None:
        raise ValueError(
            f"Unknown station: {station!r} (normalized {code!r}). "
            f"v0.1.0 supports the 20 Kalshi-traded stations from "
            f"``mostlyright._internal._stations.STATIONS``."
        )
    if not is_us_station(info.icao):
        raise ValueError(
            f"research() v0.1.0 supports only the 20 US Kalshi-traded stations; "
            f"got {station!r} (intl ICAO {info.icao!r}, country={info.country!r}). "
            f"For international weather aggregates use "
            f"mostlyright.international.daily_extremes(station, from_date, to_date) "
            f"after warming the observation cache."
        )
    return info


def _sources_root() -> Path:
    """Return the root directory for raw-source downloads (IEM CSV, CLI JSON, GHCNh PSV).

    Sits alongside the parquet cache under the same ``MOSTLYRIGHT_CACHE_DIR``
    (or ``$HOME/.mostlyright/cache/`` fallback) so a single cache wipe clears
    both layers. ``cache._cache_root()`` is the single source of truth - we
    deliberately do not duplicate the env-var lookup here.
    """
    # Local import to avoid an import cycle at module load (cache imports
    # from ``mostlyright._internal`` for path validators).
    from mostlyright.weather.cache import CACHE_VERSION, _cache_root

    return _cache_root() / CACHE_VERSION / "sources"


def _month_range(start_iso: str, end_iso: str) -> list[tuple[int, int]]:
    """Return inclusive list of (year, month) tuples covering ``[start, end]``.

    Both bounds are YYYY-MM-DD ISO strings. Empty result when ``start > end``.
    """
    start = _date.fromisoformat(start_iso)
    end = _date.fromisoformat(end_iso)
    if start > end:
        return []
    out: list[tuple[int, int]] = []
    y, m = start.year, start.month
    end_y, end_m = end.year, end.month
    while (y, m) <= (end_y, end_m):
        out.append((y, m))
        m += 1
        if m == 13:
            m = 1
            y += 1
    return out


def _month_window(year: int, month: int) -> tuple[_date, _date]:
    """Return ``(first_day, last_day)`` of the calendar month."""
    first = _date(year, month, 1)
    next_first = _date(year + 1, 1, 1) if month == 12 else _date(year, month + 1, 1)
    last = next_first - timedelta(days=1)
    return first, last


def _month_overlaps_awc_window(year: int, month: int, *, now: datetime | None = None) -> bool:
    """True iff the month's UTC range overlaps ``[now - 168h, now]``.

    Used to gate AWC fetches: AWC's ``hours=168`` endpoint only returns the
    last ~7 days of METARs (see ``spike/SPIKE_REPORT.md``). Months entirely
    before that window get zero AWC contribution; calling the AWC fetcher
    for them is wasted I/O and noisy logs.
    """
    now = now or datetime.now(UTC)
    window_start = now - timedelta(hours=_AWC_LOOKBACK_HOURS)
    month_start = datetime(year, month, 1, tzinfo=UTC)
    next_y, next_m = (year + 1, 1) if month == 12 else (year, month + 1)
    month_end = datetime(next_y, next_m, 1, tzinfo=UTC)
    return month_start < now and month_end > window_start


def _observed_at_month(observed_at: str) -> tuple[int, int] | None:
    """Extract ``(year, month)`` from an ``"YYYY-MM-DDTHH:MM:SSZ"`` timestamp.

    Returns ``None`` if the input is malformed (callers drop the row).
    Pure string slice - no datetime parsing - matches v0.14.1 which compared
    ISO strings lexicographically and never round-tripped through datetime.
    """
    if not observed_at or len(observed_at) < 7:
        return None
    try:
        return int(observed_at[0:4]), int(observed_at[5:7])
    except ValueError:
        return None


def _fetch_iem_month(
    info: StationInfo,
    year: int,
    month: int,
    dest_dir: Path,
    *,
    skip_source_cache: bool = False,
) -> tuple[list[dict[str, Any]], bool]:
    """Download + parse IEM ASOS METAR + SPECI rows for one (station, year, month).

    Fetches both ``report_type=3`` (METAR) and ``report_type=4`` (SPECI) so
    the merge layer can dedupe per-``observation_type`` and the parity-fixture
    coverage matches v0.14.1's server-side ingest (which gathered both).

    Args:
        skip_source_cache: When ``True``, force ``download_iem_asos`` to
            re-fetch the underlying ``sources/iem_asos/.../iem_YYYYMM_*.csv``
            even when a local copy exists. Callers pass ``True`` for the
            station's current LST month so a second call within the same
            month doesn't aggregate stale METARs from an earlier IEM CSV
            snapshot (codex iter-3 P2). The parquet cache layer already
            no-ops the current LST month, but it can't help if the
            underlying CSV is stale.

    Returns:
        ``(rows, iem_ok)`` — ``iem_ok`` is ``True`` **only when BOTH** IEM
        ASOS report types downloaded successfully (HTTP-wise) for this
        month. Callers use the flag to gate cache writes: any partial
        failure (METAR succeeded but SPECI failed, or vice versa) must NOT
        write the parquet cache because future calls would hit the
        incomplete cache and never retry the missing half — losing
        off-cycle SPECI extremes in stormy months matters for byte parity
        against v0.14.1's server-side ingest (codex iter-3 P2; this is the
        stricter follow-up to the iter-2 "neither-succeeded" gate).
    """
    # Local import: weather sibling package may not be importable from a
    # bare ``mostlyright`` install (no ``[parquet]`` extra), but ``research()``
    # cannot run without it - we let the ImportError surface at call time.
    from mostlyright.weather._fetchers.iem_asos import download_iem_asos
    from mostlyright.weather._iem import parse_iem_file

    first, last = _month_window(year, month)
    rows: list[dict[str, Any]] = []
    success_count = 0
    for report_type, override in ((3, "METAR"), (4, "SPECI")):
        try:
            paths = download_iem_asos(
                info,
                first,
                last,
                dest_dir,
                report_type=report_type,
                skip_cache=skip_source_cache,
            )
        except Exception as exc:
            logger.warning(
                "IEM ASOS download failed for %s %04d-%02d report_type=%d: %s",
                info.code,
                year,
                month,
                report_type,
                exc,
            )
            continue
        success_count += 1
        for p in paths:
            # Phase 1.5 PERF-01 boundary filter: ``download_iem_asos`` now returns
            # yearly chunks (one CSV covering all of ``year``). Without filtering,
            # the per-month merge loop in ``_fetch_observations_range`` would see
            # Jan-Dec IEM rows mixed with the month's AWC/GHCNh slice, which
            # changes the merge composition (and therefore tie-break order on
            # strict-> priority comparisons) at month boundaries. Filtering parsed
            # rows back to ``(year, month)`` here restores the exact merge input
            # set the monthly-chunker era produced — preserves the 5-fixture parity
            # gate. The yearly-vs-monthly perf win is in the network layer (one
            # request per year, not 12); orchestrator restructuring to a year-at-
            # a-time fetch loop is Plan 03 territory (PERF-04).
            for row in parse_iem_file(p, observation_type_override=override):
                if _observed_at_month(row.get("observed_at", "")) == (year, month):
                    rows.append(row)
    # Require BOTH report types to succeed before claiming the month is
    # safely cacheable. Partial success would otherwise poison the cache
    # with METAR-only or SPECI-only data and skip future retries.
    return rows, success_count == 2


def _fetch_awc_for_window(icao: str, hours: int = _AWC_LOOKBACK_HOURS) -> list[dict[str, Any]]:
    """Fetch AWC METARs for the last ``hours`` and convert to observation rows.

    Returns a list of observation-schema dicts (post-``awc_to_observation``).
    Empty list when the AWC endpoint is unhappy - matches the fetcher's
    "never raise, degrade gracefully" contract.
    """
    from mostlyright.weather._awc import awc_to_observation
    from mostlyright.weather._fetchers.awc import fetch_awc_metars

    raw = fetch_awc_metars([icao], hours=hours)
    out: list[dict[str, Any]] = []
    for m in raw:
        obs = awc_to_observation(m)
        if obs is not None:
            out.append(obs)
    return out


def _fetch_ghcnh_year(
    info: StationInfo,
    year: int,
    dest_dir: Path,
    *,
    skip_source_cache: bool = False,
) -> list[dict[str, Any]]:
    """Download + parse a GHCNh PSV for ``(info, year)`` and return rows.

    GHCNh is annual-granularity, so callers cache the parsed rows for the
    year and slice by month at the caller site.

    Args:
        skip_source_cache: When ``True``, force ``download_ghcnh`` to
            re-fetch the PSV even when a local copy exists. NCEI republishes
            ``GHCNh_<id>_<YEAR>.psv`` as new months land, so for the
            station's current LST year the source cache would otherwise
            stay pinned to the early-year snapshot (codex iter-4 symmetric
            extension of the iter-3 IEM ASOS / IEM CLI source-cache fixes).
    """
    import httpx

    from mostlyright.weather._fetchers.ghcnh import download_ghcnh
    from mostlyright.weather._ghcnh import parse_ghcnh_file

    try:
        path = download_ghcnh(info.ghcnh_id, year, dest_dir, skip_cache=skip_source_cache)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            logger.info("GHCNh %s %d: no data (404), skipping", info.ghcnh_id, year)
            return []
        raise
    return parse_ghcnh_file(path)


def _is_writable_month(year: int, month: int, *, now: datetime | None = None) -> bool:
    """True iff ``(year, month)`` is strictly in the past in UTC.

    ``write_cache`` already no-ops the station's current **LST** month, but
    that predicate lags UTC for negative-offset stations (the v0.1.0
    registry is all US, UTC-5 .. UTC-10). At month boundaries — when UTC
    has rolled into the next month but LST is still in the previous month
    — the LST-only gate lets the orchestrator write a parquet for the
    new UTC month with only the few hours of data IEM has so far. Once
    LST catches up, ``read_cache`` would treat that partial file as
    complete and return stale aggregates (codex iter-2 P2).

    This stricter UTC-based predicate gates writes at the orchestrator
    layer so the partial-month race cannot happen regardless of the
    station's timezone offset.
    """
    now = now or datetime.now(UTC)
    return (year, month) < (now.year, now.month)


def _ensure_ghcnh_year(
    cache: dict[int, list[dict[str, Any]]],
    info: StationInfo,
    year: int,
    dest_dir: Path,
    *,
    skip_source_cache: bool = False,
) -> list[dict[str, Any]]:
    """Lazy per-year GHCNh loader.

    Populates ``cache[year]`` on first miss and returns the cached list on
    subsequent calls. Used by :func:`_fetch_observations_range` to defer
    every GHCNh HTTP/PSV parse until a month cache miss actually requires
    it, preserving the documented local-first contract: a fully-cached
    range never touches NCEI (codex iter-2 P2).

    ``skip_source_cache`` is forwarded to :func:`_fetch_ghcnh_year` so the
    PSV is re-downloaded when the caller has decided the year's local copy
    may be stale (e.g. the station's current LST year, which NCEI
    republishes as new months land — iter-4 architect finding).
    """
    if year not in cache:
        cache[year] = _fetch_ghcnh_year(info, year, dest_dir, skip_source_cache=skip_source_cache)
    return cache[year]


def _fetch_observations_range(
    info: StationInfo,
    from_date_iso: str,
    extended_to_iso: str,
    *,
    now: datetime | None = None,
    prefetched_awc_rows: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Return merged, sorted observation rows covering ``[from_date, extended_to]``.

    Per-month flow:

    1. Try the parquet cache (``read_cache``). On hit, extend the result and
       skip the network round-trip entirely — including GHCNh and AWC,
       so a fully-cached range stays purely local.
    2. On miss, gather raw rows from IEM ASOS (always), AWC (only when the
       month overlaps the last 168h), and GHCNh (annual, fetched lazily
       per-year on first miss).
    3. Merge via :func:`merge_observations` (AWC > IEM > GHCNh priority on
       ties; first-seen wins at equal priority - v0.14.1 byte-faithful
       semantics).
    4. **Pre-sort by ``observed_at`` before caching.** Risk R2 mitigation:
       float averaging in ``_obs_aggregates`` is non-associative; sorting
       deterministically keeps the parity fixtures byte-stable.
    5. Write the cache iff (a) IEM ASOS succeeded at least once for the
       month AND (b) the month is strictly in the past UTC. Both gates
       protect against poisoning the cache with incomplete data — see
       :func:`_is_writable_month` and :func:`_fetch_iem_month`.

    Args:
        prefetched_awc_rows: Phase 1.5 PERF-04 — when ``research()`` runs the
            parallel prefetch pool, AWC rows are fetched concurrently with
            IEM/GHCNh/CLI cache-warming and passed in here. Bypasses the
            lazy ``_fetch_awc_for_window`` call. ``None`` preserves the legacy
            lazy behavior for any non-orchestrator callers.
    """
    from mostlyright._internal.merge import merge_observations
    from mostlyright.weather.cache import read_cache, write_cache

    sources_root = _sources_root()
    iem_dir = sources_root / "iem_asos"
    ghcnh_dir = sources_root / "ghcnh"

    months = _month_range(from_date_iso, extended_to_iso)

    # Lazy by-year GHCNh cache. Populated on the first miss for a given year;
    # a fully-cached range never touches NCEI.
    ghcnh_by_year: dict[int, list[dict[str, Any]]] = {}

    # AWC: when the orchestrator prefetched rows in parallel (PERF-04), use
    # them directly; otherwise preserve the legacy lazy fetch (at most one
    # call across the whole orchestrator run, only on a cache miss for a
    # month that overlaps the 168h lookback).
    awc_rows: list[dict[str, Any]] | None = prefetched_awc_rows

    def _awc_for_month(year: int, month: int) -> list[dict[str, Any]]:
        """Return the AWC observation rows that belong to ``(year, month)``."""
        nonlocal awc_rows
        if not _month_overlaps_awc_window(year, month, now=now):
            return []
        if awc_rows is None:
            awc_rows = _fetch_awc_for_window(info.icao)
        return [
            r
            for r in awc_rows
            if r.get("station_code") == info.code
            and _observed_at_month(r.get("observed_at", "")) == (year, month)
        ]

    result: list[dict[str, Any]] = []
    for year, month in months:
        cached = read_cache(info.icao, year, month)
        if cached is not None:
            result.extend(cached)
            continue

        # Cache miss: pull IEM + AWC + GHCNh for the month. GHCNh is fetched
        # lazily here so a fully-cached range never hits NCEI.
        #
        # Source-cache skip predicate is a UNION of:
        #   - the station's current LST month (live observations still
        #     landing - codex iter-3 P2);
        #   - any month that is NOT strictly in the past UTC (the new UTC
        #     tail month at LST<UTC rollover - codex iter-4 P2). Without
        #     this leg, a query that extends `extended_to` into the new UTC
        #     month while LST is still in the previous month reuses the
        #     stale `iem_<new-UTC-YYYYMM>_*.csv` from the prior call.
        # The same union applies to the annual GHCNh PSV (NCEI republishes
        # as new months land - iter-4 architect finding).
        from mostlyright.weather.cache import (
            _is_current_lst_month,
            _is_current_lst_year,
        )

        month_is_writable_utc = _is_writable_month(year, month, now=now)
        skip_iem_source = _is_current_lst_month(info.icao, year, month) or not month_is_writable_utc
        iem_rows, iem_ok = _fetch_iem_month(
            info, year, month, iem_dir, skip_source_cache=skip_iem_source
        )

        # GHCNh PSV is annual; the year is "mutable" iff it is the station's
        # current LST year OR not strictly in the UTC past.
        _now = now or datetime.now(UTC)
        year_is_writable_utc = year < _now.year
        # Phase 3.1 adapter-coverage gate: NCEI GHCNh ships only US first-order
        # stations (USW00*). For international ICAOs the PSV doesn't exist
        # (404), and the IEM ASOS network already carries global METAR/AWOS
        # at primary precision — fetching GHCNh would just generate noise.
        if not is_us_station(info.icao):
            if year not in ghcnh_by_year:
                logger.info(
                    "skip GHCNh fetch for non-US station %s (year=%d); "
                    "GHCNh is US-only, IEM covers international observations",
                    info.icao,
                    year,
                )
                ghcnh_by_year[year] = []
            ghcnh_month: list[dict[str, Any]] = []
        else:
            skip_ghcnh_source = _is_current_lst_year(info.icao, year) or not year_is_writable_utc
            ghcnh_year_rows = _ensure_ghcnh_year(
                ghcnh_by_year,
                info,
                year,
                ghcnh_dir,
                skip_source_cache=skip_ghcnh_source,
            )
            ghcnh_month = [
                r
                for r in ghcnh_year_rows
                if r.get("station_code") == info.code
                and _observed_at_month(r.get("observed_at", "")) == (year, month)
            ]

        awc_month = _awc_for_month(year, month)

        # PLAN.md Task 2.1 step 3 [HIGH]: pre-sort by (observed_at, source)
        # BEFORE merge_observations. The merge layer uses first-seen-wins at
        # equal priority AND returns ``list(best.values())`` (dict insertion
        # order), so input order is load-bearing for BOTH tie-break
        # determinism AND survivor ordering. Sorting AFTER the merge (the
        # prior implementation) re-orders survivors but cannot influence
        # which row won the equal-priority tie. R2 mitigation: also keeps
        # non-associative IEEE float adds in downstream _obs_aggregates
        # byte-stable across runs.
        combined = awc_month + iem_rows + ghcnh_month
        combined.sort(key=lambda r: (r.get("observed_at") or "", r.get("source") or ""))
        merged = merge_observations(combined)

        # Cache-write gate: IEM must have succeeded (otherwise we'd freeze a
        # partial AWC+GHCNh slice as authoritative) AND the month must be
        # strictly in the UTC past (otherwise we'd freeze a not-yet-complete
        # month at the UTC/LST boundary). ``write_cache`` itself also no-ops
        # the LST current month and any ``.live`` source — these orchestrator
        # gates are additional, not redundant.
        if iem_ok and _is_writable_month(year, month, now=now):
            write_cache(info.icao, year, month, merged, source="iem")
        else:
            logger.info(
                "skip cache write for %s %04d-%02d (iem_ok=%s, writable=%s)",
                info.code,
                year,
                month,
                iem_ok,
                _is_writable_month(year, month, now=now),
            )

        result.extend(merged)

    return result


def _fetch_climate_range(
    info: StationInfo,
    from_date_iso: str,
    to_date_iso: str,
) -> list[dict[str, Any]]:
    """Return merged climate rows for the inclusive ``[from_date, to_date]`` years.

    Annual cache layer: one parquet per (station, year). Cache miss triggers
    one IEM CLI download per year. Parse via
    :func:`mostlyright.weather._climate.parse_cli_response` then merge via
    :func:`merge_climate` (highest ``report_type_priority`` with STRICT > -
    overnight final wins, which IS the Kalshi settlement source).
    """
    import httpx

    from mostlyright.weather._climate import parse_cli_response
    from mostlyright.weather._fetchers.iem_cli import download_cli
    from mostlyright.weather.cache import (
        _is_current_lst_year,
        read_climate_cache,
        write_climate_cache,
    )

    sources_root = _sources_root()
    cli_dir = sources_root / "iem_cli"

    start = _date.fromisoformat(from_date_iso)
    end = _date.fromisoformat(to_date_iso)
    if start > end:
        return []

    _now = datetime.now(UTC)
    result: list[dict[str, Any]] = []
    for year in range(start.year, end.year + 1):
        cached = read_climate_cache(info.icao, year)
        if cached is not None:
            result.extend(cached)
            continue

        # Source-cache skip predicate (union, mirrors the observation path):
        #   - station's current LST year (overnight finals + corrections
        #     still landing - codex iter-3 P2);
        #   - any year not strictly in the past UTC (year-rollover window
        #     where LST and UTC may straddle a year boundary - iter-4
        #     architect/codex extension).
        # Without the union a call straddling Dec 31 UTC / Dec 31 LST
        # in a different timezone could pin the stale source JSON.
        skip_cli_source = _is_current_lst_year(info.icao, year) or year >= _now.year
        try:
            path = download_cli(
                info.icao,
                year,
                cli_dir,
                skip_cache=skip_cli_source,
            )
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                logger.info("IEM CLI %s %d: no data (404), skipping", info.icao, year)
                continue
            raise

        try:
            data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning(
                "IEM CLI %s %d: failed to read cache file %s: %s",
                info.icao,
                year,
                path,
                exc,
            )
            continue
        if not isinstance(data, list):
            logger.warning(
                "IEM CLI %s %d: unexpected payload shape %s",
                info.icao,
                year,
                type(data).__name__,
            )
            continue

        parsed = parse_cli_response(data, info.code)
        from mostlyright._internal.merge import merge_climate

        merged = merge_climate(parsed)
        # Climate cache write gate (mirror of `_is_writable_month` for the
        # observation path). ``write_climate_cache`` already no-ops the
        # station's current LST year, but for negative-offset stations LST
        # lags UTC across year boundaries: if `from_date`/`to_date` straddle
        # Dec 31 LST while UTC has rolled into the new year, the new-year
        # parquet would otherwise persist whatever partial CLI snapshot was
        # available at that moment. Once LST catches up, ``read_climate_cache``
        # would serve that partial file as authoritative (codex iter-5).
        if year < _now.year:
            write_climate_cache(info.icao, year, merged, source="iem")
        else:
            logger.info(
                "skip climate cache write for %s %04d (year not strictly past UTC, _now=%s)",
                info.icao,
                year,
                _now.isoformat(),
            )
        result.extend(merged)

    return result


def _all_caches_warm(
    info: StationInfo,
    from_date_iso: str,
    to_date_iso: str,
    extended_to_iso: str,
) -> bool:
    """True iff every (year, month) parquet and every climate-year parquet is hit.

    PERF-04 gate: when this returns True, the PERF-04 prefetch is skipped so
    a fully-cached re-run still fires zero HTTP requests
    (TestFetchObservationsRangeCacheGating regression).
    """
    from mostlyright.weather.cache import read_cache, read_climate_cache

    months = _month_range(from_date_iso, extended_to_iso)
    if any(read_cache(info.icao, y, m) is None for y, m in months):
        return False
    from_d = _date.fromisoformat(from_date_iso)
    to_d = _date.fromisoformat(to_date_iso)
    return all(
        read_climate_cache(info.icao, y) is not None for y in range(from_d.year, to_d.year + 1)
    )


def _prefetch_sources(
    info: StationInfo,
    from_date_iso: str,
    to_date_iso: str,
    extended_to_iso: str,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Phase 1.5 PERF-04 — concurrent fan-out of the 4 source-fetch operations.

    Implements Option C from ``.planning/research/SOURCE-LIMITS.md`` (no shared
    ``threading.Lock``; ``max_workers=4``; each fetcher preserves its own
    politeness delay). Empirically validated at the production-target N=4
    concurrency: zero 503s, zero errors on the smoke spike.

    Four workers:

    - ``iem.archive`` — warms the IEM ASOS yearly-chunk CSV cache for the full
      ``[from_date.year, extended_to.year]`` range, both report types.
    - ``cli.archive`` — warms the IEM CLI annual JSON cache for the
      ``[from_date.year, to_date.year]`` range.
    - ``ghcnh.archive`` — warms the GHCNh annual PSV cache for the
      ``[from_date.year, extended_to.year]`` range.
    - ``awc.live`` — fetches AWC METARs for the last 168h (in-memory, no disk
      cache). Returned to the caller so ``_fetch_observations_range`` can
      bypass its lazy fetch.

    Pitfall 6 timing pattern (PLAN-03 / RESEARCH Pitfall 6): ``submitted_at[name]``
    captured IMMEDIATELY after ``ex.submit()`` so per-source timing measures
    actual work, not iteration-order accident. Exceptions propagate via
    ``f.result()`` — no try/except wrapping per worker.

    Returns:
        ``{"awc_rows": list[dict] | None, "per_source_times": dict[str, float],
        "wall_time": float, "submitted_at": dict[str, float]}``.

        ``awc_rows`` is ``None`` if the AWC worker raised (degraded gracefully —
        the fetcher's contract is "never raise" but defense-in-depth here).
    """
    import concurrent.futures
    import time

    sources_root = _sources_root()
    iem_dir = sources_root / "iem_asos"
    cli_dir = sources_root / "iem_cli"
    ghcnh_dir = sources_root / "ghcnh"

    from_d = _date.fromisoformat(from_date_iso)
    extended_to = _date.fromisoformat(extended_to_iso)
    to_d = _date.fromisoformat(to_date_iso)
    _now = now or datetime.now(UTC)

    # Codex/architect iter-1 HIGH-3/4: prefetching the current UTC year with
    # ``skip_cache=True`` would write to the ``_partial`` namespace, and the
    # sequential ``_fetch_iem_month`` fallback would then re-fetch into the
    # canonical namespace — doubling network load for every current-year call.
    # The cleanest fix: only prefetch years strictly past UTC. The current
    # year falls through to the existing sequential lazy path, which still
    # handles per-month skip_source_cache correctly via its own predicate.
    # ``_PREFETCH_NETWORK_ERRORS``: tight whitelist of recoverable network
    # exceptions for the _warm_* helpers. Anything outside this tuple
    # propagates via f.result() per the docstring contract — programming bugs
    # MUST surface (codex/architect iter-1 HIGH-1/2).

    def _warm_iem_asos() -> None:
        """Warm IEM ASOS yearly-chunk cache for years STRICTLY past UTC.

        ``download_iem_asos`` normalizes the caller's start to ``date(year, 1, 1)``
        (Plan 01 PERF-02 cache-idempotence). Issuing one call per past year
        here primes the canonical cache so the per-month ``_fetch_iem_month``
        calls in ``_fetch_observations_range`` hit on every month after the
        first. The current UTC year is intentionally NOT prefetched — see
        block comment above.
        """
        import httpx

        # Local import: weather sibling may not be present in bare installs.
        from mostlyright.weather._fetchers.iem_asos import download_iem_asos

        for year in range(from_d.year, min(extended_to.year, _now.year - 1) + 1):
            year_start = _date(year, 1, 1)
            year_end_inclusive = _date(year, 12, 31)
            for rt in (3, 4):
                try:
                    download_iem_asos(
                        info,
                        year_start,
                        year_end_inclusive,
                        iem_dir,
                        report_type=rt,
                        skip_cache=False,
                    )
                except (httpx.HTTPStatusError, httpx.RequestError, OSError) as exc:
                    # Recoverable network/disk error: log + let the sequential
                    # fallback retry per its own predicate.
                    logger.warning(
                        "PERF-04 prefetch IEM ASOS %s %d rt=%d failed: %s",
                        info.code,
                        year,
                        rt,
                        exc,
                    )

    def _warm_iem_cli() -> None:
        """Warm IEM CLI annual JSON cache for years STRICTLY past UTC."""
        import httpx

        from mostlyright.weather._fetchers.iem_cli import download_cli

        for year in range(from_d.year, min(to_d.year, _now.year - 1) + 1):
            try:
                download_cli(info.icao, year, cli_dir, skip_cache=False)
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code != 404:
                    logger.warning(
                        "PERF-04 prefetch CLI %s %d failed: %s",
                        info.icao,
                        year,
                        exc,
                    )
            except (httpx.RequestError, OSError) as exc:
                logger.warning(
                    "PERF-04 prefetch CLI %s %d failed: %s",
                    info.icao,
                    year,
                    exc,
                )

    def _warm_ghcnh() -> None:
        """Warm GHCNh annual PSV cache for years STRICTLY past UTC.

        Phase 3.1: short-circuit for non-US stations. NCEI GHCNh is US-only;
        the PSV doesn't exist for international ICAOs, so prefetching would
        only produce 404s.
        """
        import httpx

        from mostlyright.weather._fetchers.ghcnh import download_ghcnh

        if not is_us_station(info.icao):
            logger.info(
                "PERF-04 prefetch GHCNh: skipping non-US station %s",
                info.icao,
            )
            return
        for year in range(from_d.year, min(extended_to.year, _now.year - 1) + 1):
            try:
                download_ghcnh(info.ghcnh_id, year, ghcnh_dir, skip_cache=False)
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code != 404:
                    logger.warning(
                        "PERF-04 prefetch GHCNh %s %d failed: %s",
                        info.ghcnh_id,
                        year,
                        exc,
                    )
            except (httpx.RequestError, OSError) as exc:
                logger.warning(
                    "PERF-04 prefetch GHCNh %s %d failed: %s",
                    info.ghcnh_id,
                    year,
                    exc,
                )

    # AWC-window relevance: AWC's 168h endpoint only returns data for months
    # overlapping the last ~7 days (see ``_month_overlaps_awc_window``). For
    # queries entirely outside that window, the prefetch worker should NO-OP
    # — matching the lazy ``_awc_for_month`` short-circuit and avoiding
    # unnecessary HTTP. Returning None (vs []) signals "no prefetch fired"
    # so ``_fetch_observations_range`` falls through to its legacy lazy path.
    months_overlap_awc = any(
        _month_overlaps_awc_window(y, m, now=now)
        for y, m in _month_range(from_date_iso, extended_to_iso)
    )

    def _fetch_awc() -> list[dict[str, Any]] | None:
        """Fetch AWC METARs for the last 168h (in-memory; no disk cache).

        Returns ``None`` when the query window has no AWC overlap so the
        lazy ``_awc_for_month`` short-circuit stays the source of truth.
        Returns ``[]`` (not None) on network failure so the orchestrator
        does not fall back to a second lazy fetch (which would also fail).
        Programming bugs propagate.
        """
        import httpx

        if not months_overlap_awc:
            return None
        try:
            return _fetch_awc_for_window(info.icao)
        except (httpx.HTTPStatusError, httpx.RequestError, OSError) as exc:
            logger.warning("PERF-04 prefetch AWC %s failed: %s", info.icao, exc)
            return []

    submitted_at: dict[str, float] = {}
    futures: dict[concurrent.futures.Future, str] = {}
    per_source_times: dict[str, float] = {}
    awc_rows: list[dict[str, Any]] | None = None

    t_start = time.monotonic()
    # max_workers=4 per SOURCE-LIMITS.md Option C: no shared lock; each fetcher
    # preserves its own politeness delay; spike confirmed zero 503s at this load.
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
        for name, fn in (
            ("iem.archive", _warm_iem_asos),
            ("awc.live", _fetch_awc),
            ("ghcnh.archive", _warm_ghcnh),
            ("cli.archive", _warm_iem_cli),
        ):
            f = ex.submit(fn)
            # Pitfall 6 (PLAN-03): capture submitted_at IMMEDIATELY after submit()
            # — NOT inside the as_completed loop where the first iterated future
            # would inflate the timing for whichever source happens to be iterated
            # first.
            submitted_at[name] = time.monotonic()
            futures[f] = name

        for f in concurrent.futures.as_completed(futures):
            name = futures[f]
            per_source_times[name] = time.monotonic() - submitted_at[name]
            # Exceptions propagate via f.result() (no try/except wrapping per
            # worker) — preserves the orchestrator's degraded-graceful contract
            # while still surfacing programming bugs in the helpers above. The
            # network-error catches are inside the _warm_* helpers themselves.
            result = f.result()
            if name == "awc.live":
                awc_rows = result

    wall_time = time.monotonic() - t_start
    return {
        "awc_rows": awc_rows,
        "per_source_times": per_source_times,
        "wall_time": wall_time,
        "submitted_at": submitted_at,
    }


# ----------------------------------------------------------------------
# Phase 17 PLAN-09: research(include_forecast=True) helpers
# ----------------------------------------------------------------------
def _fetch_iem_mos_range(
    info: StationInfo,
    from_date: str,
    to_date: str,
    *,
    model: str = "nbe",
) -> dict[str, list[dict[str, Any]]]:
    """Mode 1 — fetch IEM MOS forecasts grouped by settlement date (ISO).

    Wraps ``mostlyright.weather._fetchers._iem_mos.fetch_iem_mos`` and pivots
    its tabular DataFrame to the ``{date_iso: [forecast_row, ...]}`` shape
    that ``build_pairs(forecasts_by_date=...)`` expects. Each row in the
    grouped output carries both the canonical IEM MOS columns AND the
    legacy ``temperature_f`` / ``valid_at`` / ``issued_at`` keys that
    ``_aggregate_fcst_temps_iem`` + ``_select_best_run`` consume.

    Returns an empty dict when IEM MOS yields zero rows (defensive — keeps
    downstream callers null-safe).
    """
    from mostlyright.weather._fetchers._iem_mos import fetch_iem_mos

    df = fetch_iem_mos(info.icao, from_date, to_date, model=model)
    groups: dict[str, list[dict[str, Any]]] = {}
    if df is None or df.empty:
        return groups
    # Phase 17 Wave 4 iter-1 review HIGH: bucket by LST settlement date
    # (not raw UTC date). A valid_at of 2025-01-07T02:00Z for a US station
    # belongs to the 2025-01-06 settlement window — raw UTC bucketing
    # would silently drop the row from settlement-date keyed lookups.
    for _, row in df.iterrows():
        ftime = row.get("valid_at")
        if ftime is None or (isinstance(ftime, float) and ftime != ftime):
            continue
        try:
            ftime_dt = pd.to_datetime(ftime, utc=True)
        except Exception:
            continue
        try:
            date_iso = settlement_date_for(
                ftime_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
                info.code,
            )
        except Exception:  # noqa: BLE001 — defensive against unknown station/tz
            date_iso = ftime_dt.strftime("%Y-%m-%d")
        # Build a forecast row that build_pairs_row understands. IEM MOS
        # already carries ``valid_at``; we also normalize it to the
        # ISO-string form ``_aggregate_fcst_temps_iem`` compares against.
        issued_at = row.get("issued_at")
        try:
            issued_iso = (
                pd.to_datetime(issued_at, utc=True).strftime("%Y-%m-%dT%H:%M:%SZ")
                if issued_at is not None
                else None
            )
        except Exception:
            issued_iso = None
        try:
            valid_iso = ftime_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        except Exception:
            valid_iso = None
        temp_c = row.get("temp_c")
        temperature_f: float | None = None
        if temp_c is not None and not (isinstance(temp_c, float) and temp_c != temp_c):
            try:
                temperature_f = float(temp_c) * 9.0 / 5.0 + 32.0
            except (TypeError, ValueError):
                temperature_f = None
        pop_prob = row.get("precip_probability")
        pop_6hr_pct: float | None = None
        if pop_prob is not None and not (isinstance(pop_prob, float) and pop_prob != pop_prob):
            try:
                pop_6hr_pct = float(pop_prob) * 100.0
            except (TypeError, ValueError):
                pop_6hr_pct = None
        fcst_row: dict[str, Any] = {
            "model": row.get("model"),
            "issued_at": issued_iso,
            "valid_at": valid_iso,
            "temperature_f": temperature_f,
            "pop_6hr_pct": pop_6hr_pct,
            "qpf_6hr_in": None,  # IEM MOS doesn't expose qpf in the v1 schema
        }
        groups.setdefault(date_iso, []).append(fcst_row)
    return groups


def _fetch_nwp_models_range(
    info: StationInfo,
    from_date: str,
    to_date: str,
    forecast_models: list[str],
) -> dict[str, dict[str, list[dict[str, Any]]]]:
    """Mode 2 — fetch per-model NWP forecasts (one 12Z cycle per day).

    Iterates each model in ``forecast_models``, fetches a single
    representative 12Z cycle per LST date in ``[from_date, to_date]``, and
    returns ``{model: {date_iso: [forecast_row, ...]}}``. Per-cycle
    exceptions are logged and the iteration continues — a single
    upstream failure does not abort the whole batch.

    Cycle-per-day is a simplifying choice for v0.1.0 Mode 2 — the user
    can still get sub-daily by calling ``forecast_nwp`` directly. Phase
    17 CONTEXT decision 7 records this choice.
    """
    from mostlyright.weather.forecast_nwp import forecast_nwp

    groups: dict[str, dict[str, list[dict[str, Any]]]] = {}
    try:
        from_dt = datetime.fromisoformat(from_date).replace(tzinfo=UTC)
        to_dt = datetime.fromisoformat(to_date).replace(tzinfo=UTC, hour=23, minute=59, second=59)
    except ValueError as exc:
        raise ValueError(
            f"_fetch_nwp_models_range: from_date / to_date must be ISO "
            f"YYYY-MM-DD; got from_date={from_date!r} to_date={to_date!r}"
        ) from exc

    for model in forecast_models:
        groups[model] = {}
        cur = from_dt.replace(hour=12, minute=0, second=0, microsecond=0)
        while cur <= to_dt:
            date_iso = cur.strftime("%Y-%m-%d")
            try:
                df = forecast_nwp(
                    station=info.icao,
                    model=model,
                    cycle=cur,
                    fxx=12,
                )
                if df is not None and not df.empty:
                    groups[model][date_iso] = df.to_dict(orient="records")
            except Exception as exc:
                logger.warning(
                    "research: NWP %s cycle %s failed: %s",
                    model,
                    cur.isoformat(),
                    exc,
                )
            cur += timedelta(days=1)
    return groups


# ----------------------------------------------------------------------
# Phase 3.4: opt-in QC engine wiring
# ----------------------------------------------------------------------
def _run_qc_and_write_sidecar(
    *,
    info: StationInfo,
    raw_obs: list[dict[str, Any]],
    from_date: str,
    to_date: str,
) -> dict[str, Any]:
    """Run the QCEngine + IEM-vs-GHCNh crosscheck against raw observations.

    Returns a summary dict suitable for ``df.attrs["qc"]``::

        {
            "rules_fired": {"temp_out_of_range": 3, "dewpoint_gt_temp": 1, ...},
            "rows_flagged": 4,
            "rows_total": 1200,
            "crosscheck_disagreements": 0,
            "sidecar_paths": [...],   # list of parquet paths written
        }

    Never raises — QC is best-effort and must not break the wrapping
    ``research()`` call. Errors are caught and surfaced in the summary
    via an ``error`` key.

    The QC engine reads observation rows but DOES NOT mutate them — the
    parity gate's "Mode 1 row contents are byte-identical to v0.14.1
    pairs() output" invariant is preserved.
    """
    summary: dict[str, Any] = {
        "rules_fired": {},
        "rows_flagged": 0,
        "rows_total": len(raw_obs),
        "crosscheck_disagreements": 0,
        "sidecar_paths": [],
    }
    if not raw_obs:
        return summary
    try:
        import pandas as pd

        from mostlyright.qc import QCEngine, crosscheck_iem_ghcnh
    except ImportError as exc:
        summary["error"] = f"QC dependency unavailable: {exc}"
        return summary

    try:
        obs_df = pd.DataFrame(raw_obs)
    except Exception as exc:
        summary["error"] = f"QC DataFrame construction failed: {exc}"
        return summary

    # Architect iter-1 HIGH-1: production parsers (_iem.py, _ghcnh.py,
    # _awc.py) emit `station_code` + `observed_at`, but the QC engine
    # and crosscheck functions read `station` + `event_time`. Normalize
    # column names here so the engine sees what it expects. This is
    # NON-DESTRUCTIVE to raw_obs (we work on the DataFrame copy).
    if obs_df.empty:
        # Nothing to QC; return the skeleton summary unchanged.
        return summary
    obs_df = obs_df.copy()
    if "station" not in obs_df.columns and "station_code" in obs_df.columns:
        obs_df["station"] = obs_df["station_code"]
    if "event_time" not in obs_df.columns and "observed_at" in obs_df.columns:
        obs_df["event_time"] = obs_df["observed_at"]

    engine = QCEngine()
    try:
        # Codex iter-1 P2 + architect iter-1 HIGH-1: map production
        # parser column names → QC engine column names. Production
        # observation rows (from _iem.py / _ghcnh.py / _awc.py) use
        # `dewpoint_c`, `wind_speed_kt`, `wind_dir_degrees`,
        # `sea_level_pressure_mb`, `temp_c`. The QC engine reads
        # `dew_point_c`, `wind_speed_ms`, `wind_dir_deg`, `slp_hpa`,
        # `temp_c`. Map non-destructively (add derived columns only
        # when missing) so the alpha rules can fire on real data.
        #
        # Where the unit also differs (kt → m/s), apply the conversion.
        if "temp_c" not in obs_df.columns and "tmpf" in obs_df.columns:
            obs_df["temp_c"] = pd.to_numeric(obs_df["tmpf"], errors="coerce").apply(
                lambda f: (f - 32.0) * 5.0 / 9.0 if pd.notna(f) else None
            )
        if "dew_point_c" not in obs_df.columns:
            if "dewpoint_c" in obs_df.columns:
                obs_df["dew_point_c"] = obs_df["dewpoint_c"]
            elif "dwpf" in obs_df.columns:
                obs_df["dew_point_c"] = pd.to_numeric(obs_df["dwpf"], errors="coerce").apply(
                    lambda f: (f - 32.0) * 5.0 / 9.0 if pd.notna(f) else None
                )
        if "wind_speed_ms" not in obs_df.columns and "wind_speed_kt" in obs_df.columns:
            obs_df["wind_speed_ms"] = pd.to_numeric(obs_df["wind_speed_kt"], errors="coerce").apply(
                lambda kt: kt * 0.514444 if pd.notna(kt) else None
            )
        if "wind_dir_deg" not in obs_df.columns and "wind_dir_degrees" in obs_df.columns:
            obs_df["wind_dir_deg"] = obs_df["wind_dir_degrees"]
        if "slp_hpa" not in obs_df.columns and "sea_level_pressure_mb" in obs_df.columns:
            # 1 mb == 1 hPa; rename only.
            obs_df["slp_hpa"] = obs_df["sea_level_pressure_mb"]
        flagged = engine.apply(obs_df)
        # Tally per-rule firings + total flagged rows.
        if "obs_qc_status" in flagged.columns:
            mask = flagged["obs_qc_status"] != 0
            summary["rows_flagged"] = int(mask.sum())
            for rule in engine.rules:
                bit = 1 << rule.bit_position
                fired = (flagged["obs_qc_status"] & bit) != 0
                count = int(fired.sum())
                if count > 0:
                    summary["rules_fired"][rule.rule_id] = count

        sidecar_rows = engine.build_sidecar_rows(flagged)
    except Exception as exc:
        summary["error"] = f"QC engine apply failed: {exc}"
        return summary

    # Optional: IEM-vs-GHCNh crosscheck. Only runs if both sources are
    # present in the raw observations (downstream Mode 1 path doesn't
    # actually carry the source column in every row, so we only flag
    # when partitionable).
    try:
        if "source" in obs_df.columns and "event_time" in obs_df.columns:
            iem_df = obs_df.loc[obs_df["source"].astype(str).str.startswith("iem")]
            ghcnh_df = obs_df.loc[obs_df["source"].astype(str).str.startswith("ghcnh")]
            if not iem_df.empty and not ghcnh_df.empty and "temp_c" in obs_df.columns:
                disagreements = crosscheck_iem_ghcnh(iem_df, ghcnh_df, tol_c=2.0)
                summary["crosscheck_disagreements"] = len(disagreements)
    except Exception as exc:
        summary["crosscheck_error"] = str(exc)

    # Write per-month sidecars. Group sidecar_rows by the (year, month)
    # of observed_at so each parquet file corresponds to one calendar
    # month — matches the cache layout. Best-effort writes; ignore
    # failures (write_qc_sidecar logs + returns None).
    try:
        from mostlyright.weather.qc_sidecar import write_qc_sidecar

        per_month: dict[tuple[int, int], list[dict[str, Any]]] = {}
        for row in sidecar_rows:
            observed_at = str(row.get("observed_at") or "")
            if len(observed_at) < 7:
                continue
            try:
                year = int(observed_at[:4])
                month = int(observed_at[5:7])
            except ValueError:
                continue
            per_month.setdefault((year, month), []).append(row)
        for (year, month), batch in per_month.items():
            path = write_qc_sidecar(batch, station=info.icao, year=year, month=month)
            if path is not None:
                summary["sidecar_paths"].append(str(path))
    except ImportError as exc:
        summary["sidecar_error"] = f"qc_sidecar unavailable: {exc}"

    return summary


def research(
    station: str | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
    *,
    city: str | None = None,
    contract: str | None = None,
    contracts: list[str] | tuple[str, ...] | None = None,
    station_override: str | None = None,
    sources: list[str] | tuple[str, ...] | None = None,
    source: str | None = None,
    include_trades: bool = False,
    include_forecast: bool = False,
    forecast_model: str | None = None,
    forecast_models: list[str] | None = None,
    as_dataframe: bool = True,
    tz_override: str | None = None,
    qc: bool = False,
    backend: str = "pandas",
    return_type: str = "dataframe",
) -> Any:
    """Return joined observation + climate + (optional) forecast rows for a date range.

    This is the v0.1.0 public surface for the Phase 1 parity gate: when
    ``include_forecast=False`` the output is byte-equivalent to
    ``mostlyright==0.14.1``'s ``client.pairs(station, from_date, to_date)``
    on the 5 Phase 1 fixtures.

    Args:
        station: 3-letter NWS code (``"NYC"``) or 4-letter ICAO (``"KNYC"``).
            Normalized via :func:`_station_code_normalized`. Must be one of
            the 20 Kalshi-traded stations from
            :data:`mostlyright._internal._stations.STATIONS`. International
            expansion lands in Phase 3.1.
        from_date: Inclusive start (``YYYY-MM-DD`` in LST). Per-station LST
            settlement-date semantics - see
            :func:`mostlyright.snapshot.settlement_date_for`.
        to_date: Inclusive end (``YYYY-MM-DD`` in LST). The observation
            fetch extends one calendar day past ``to_date`` so the last LST
            settlement window's pre-midnight UTC tail observations are
            included.
        include_forecast: When ``True``, attach forecast columns. **Phase 1
            scope is ``False`` only**; calling with ``True`` raises
            :class:`NotImplementedError`. Forecast wiring ships in Phase 3.2
            (multi-forecast live path).
        forecast_model: Filter IEM MOS records to this model name before
            run selection. Passed through to
            :func:`mostlyright._internal._pairs.build_pairs`. Ignored when
            ``include_forecast=False``.
        as_dataframe: When ``True`` (default) return a Pandas DataFrame
            indexed by ``date``. When ``False`` return the raw
            ``list[dict]`` rows produced by ``build_pairs``.
        tz_override: IANA timezone name override for stations not yet in
            :data:`mostlyright.snapshot._STATION_TZ`. Passed through to
            settlement-date math; rarely needed for the 20-station Phase 1
            registry (all entries are covered).

    Returns:
        DataFrame (or ``list[dict]`` when ``as_dataframe=False``) with one
        row per settlement date in ``[from_date, to_date]``. Columns:

        ``date`` (index when DataFrame), ``station``, ``cli_high_f``,
        ``cli_low_f``, ``cli_report_type``, ``obs_high_f``, ``obs_low_f``,
        ``obs_mean_f``, ``obs_mean_dewpoint_f``, ``obs_max_wind_kt``,
        ``obs_max_gust_kt``, ``obs_total_precip_in``, ``obs_count``,
        ``fcst_high_f``, ``fcst_low_f``, ``fcst_model``,
        ``fcst_issued_at``, ``fcst_pop_6hr_pct``, ``fcst_qpf_6hr_in``,
        ``market_close_utc``.

        With ``include_forecast=False`` the ``fcst_*`` columns are present
        with ``None`` values (matches the parity fixtures' null-dtype
        columns).

    Raises:
        NotImplementedError: when ``include_forecast=True`` in Phase 1.
        ValueError: when ``station`` is not in the v0.1.0 registry, or when
            ``from_date``/``to_date`` are not ISO-8601 dates.

    Examples
    --------
    Fetch one week of joined observation + climate rows for KNYC. The call
    hits public APIs (AWC, IEM, GHCNh, NWS CLI) directly, so the doctest is
    network-bound and skipped by default — invoke manually before publish:

    >>> import mostlyright as tw
    >>> df = tw.research("KNYC", "2025-01-06", "2025-01-12")  # doctest: +SKIP
    >>> list(df.columns)[:4]  # doctest: +SKIP
    ['station', 'cli_high_f', 'cli_low_f', 'cli_report_type']
    """
    # Phase 6 codex iter-2 P2 fix: validate backend / return_type kwargs
    # BEFORE any network fetch or cache write. A typo in the new kwargs
    # otherwise hits live APIs + mutates the parquet cache before raising.
    from mostlyright.core._backend_dispatch import validate_backend_kwargs

    validate_backend_kwargs(backend, return_type)  # type: ignore[arg-type]

    # Phase 10 selector validation. Backwards-compat: the original
    # `station, from_date, to_date` positional signature still works —
    # detected when `station` is provided AND no new selector is.
    # New selectors (`city=`, `contract=`, `contracts=`) dispatch to
    # the composable code path; passing >1 selector raises here.
    _has_city = city is not None and city != ""
    _has_contract = contract is not None and contract != ""
    _has_contracts = contracts is not None and len(contracts) > 0
    _has_station = station is not None and station != ""
    _selector_count = sum([_has_station, _has_city, _has_contract, _has_contracts])
    if _selector_count == 0:
        raise ValueError(
            "research(): exactly one of station=, city=, contract=, contracts= must be provided"
        )
    if _selector_count > 1:
        provided = [
            n
            for n, v in (
                ("station", _has_station),
                ("city", _has_city),
                ("contract", _has_contract),
                ("contracts", _has_contracts),
            )
            if v
        ]
        raise ValueError(f"research(): selectors are mutually exclusive; got {provided!r}")

    # `sources=` (plural) vs `source=` (singular) are mutually exclusive.
    if sources is not None and source is not None:
        raise ValueError("research(): sources= and source= are mutually exclusive")

    # Iter-1 codex HIGH: sources= / source= are validated at the
    # mutual-exclusion boundary but the actual data-selection wiring lands
    # in v0.3. The station-path silently runs the full multi-source merge
    # regardless of these kwargs, which would be silent data-selection
    # corruption. Surface a clear NotImplementedError pointing callers at
    # `mostlyright.mode2.research_by_source` (the Mode-2-pin path) until
    # the kwargs are wired into the station-path dispatch.
    if sources is not None or source is not None:
        raise NotImplementedError(
            "research(): sources= and source= validation surface is shipped in "
            "Phase 10 v0.2 but the data-selection wiring lands in v0.3. For "
            "Mode 2 single-source pinning today, use "
            "`mostlyright.mode2.research_by_source(station, source, ...)` "
            "directly. Mode 1 multi-source subset (sources=[...]) ships in v0.3."
        )

    # `station_override=` only makes sense when paired with `contract=`.
    if station_override is not None and not _has_contract:
        raise ValueError(
            "research(): station_override= requires contract= "
            "(not standalone station=/city=/contracts=)"
        )

    # `include_trades=True` requires a contract/contracts selector. The
    # station/city paths don't carry an issuer:ticker, so there's nothing
    # to fetch trades for.
    if include_trades and not (_has_contract or _has_contracts):
        raise ValueError(
            "research(): include_trades=True requires contract= or contracts= "
            "(station/city selectors have no trade timeseries to attach)"
        )

    # Phase 10 v0.2 scope: the new selectors (city/contract/contracts) are
    # validated at the dispatch boundary but the actual multi-station /
    # multi-issuer join + trade-attachment is deferred to v0.3. Surface a
    # clear NotImplementedError with the actionable workaround so quants
    # can still proceed via the station-path immediately.
    if _has_city or _has_contract or _has_contracts:
        raise NotImplementedError(
            "research(): the city=/contract=/contracts= selectors are validated "
            "(mutual exclusion + station_override semantics + include_trades "
            "preconditions) in Phase 10 v0.2 but the multi-station / "
            "multi-issuer JOIN + trade-attachment lands in v0.3. For now, "
            "use `discover(city=...)` to find the station and then call "
            "`research(station=..., from_date=..., to_date=...)` directly. "
            "Selector dispatch + validation surface is stable; the data-join "
            "implementation is the v0.3 deliverable."
        )

    # ── Backwards-compat station path ─────────────────────────────────
    # station-path validation: from_date + to_date REQUIRED.
    if from_date is None or to_date is None:
        raise ValueError("research(station=...) requires both from_date and to_date")

    info = _resolve_station(station)

    # Phase 17 PLAN-09: include_forecast=True wires Mode 1 (IEM MOS) +
    # optional Mode 2 (per-NWP-model). Mode 1 emits the additive
    # ``fcst_*`` columns the v0.14.1 schema reserves; Mode 2 emits
    # ``fcst_*_nwp_<model>`` columns on top. include_forecast=False
    # leaves both dicts empty so build_pairs() sees forecasts_by_date=None
    # AND nwp_forecasts_by_model_date=None — byte-equivalent baseline.
    iem_mos_by_date: dict[str, list[dict[str, Any]]] = {}
    nwp_by_model_date: dict[str, dict[str, list[dict[str, Any]]]] = {}
    if include_forecast:
        iem_mos_by_date = _fetch_iem_mos_range(info, from_date, to_date)
        if forecast_models:
            nwp_by_model_date = _fetch_nwp_models_range(
                info, from_date, to_date, list(forecast_models)
            )

    # Inclusive settlement dates (LST). Validates the ISO format eagerly.
    dates = date_range(from_date, to_date)

    # Extend the observation fetch one calendar day so the last LST settlement
    # window's pre-midnight UTC tail is captured. Climate is per-LST-day, so
    # the climate fetch only needs the original [from, to] year range.
    extended_to = (_date.fromisoformat(to_date) + timedelta(days=1)).isoformat()

    # Phase 1.5 PERF-04: concurrent fan-out of the 4 source-fetch operations
    # (IEM ASOS, IEM CLI, GHCNh, AWC) BEFORE the sequential assembly. The
    # prefetch warms on-disk caches and captures AWC rows in-memory; the
    # subsequent _fetch_observations_range + _fetch_climate_range calls hit
    # the warmed caches and run sequentially on local CPU. Parity preserved
    # because the on-disk cache contents are byte-identical to the sequential
    # path (same fetchers, same URLs, same response bodies).
    #
    # Skip the prefetch entirely when BOTH the observation-parquet and
    # climate-parquet caches are fully populated for the requested window —
    # preserves the local-first "fully-cached range never touches the network"
    # invariant the cache-gating tests guard. The sequential path below then
    # reads from parquet without ever consulting the source-CSV layer.
    awc_rows: list[dict[str, Any]] | None = None
    if not _all_caches_warm(info, from_date, to_date, extended_to):
        prefetch = _prefetch_sources(info, from_date, to_date, extended_to)
        awc_rows = prefetch["awc_rows"]

    raw_obs = _fetch_observations_range(
        info,
        from_date,
        extended_to,
        prefetched_awc_rows=awc_rows,
    )
    raw_climate = _fetch_climate_range(info, from_date, to_date)

    # Phase 3.4: opt-in QC. Runs the QCEngine + IEM-vs-GHCNh crosscheck
    # against raw_obs WITHOUT mutating the rows themselves (parity gate
    # invariant: Mode 1 must NEVER alter observation row contents). The
    # QC summary is stashed on the returned DataFrame's df.attrs and the
    # sidecar parquet is written to ~/.mostlyright/cache/v1/observations_qc/
    # for later join.
    qc_summary: dict[str, Any] | None = None
    if qc:
        qc_summary = _run_qc_and_write_sidecar(
            info=info,
            raw_obs=raw_obs,
            from_date=from_date,
            to_date=to_date,
        )

    # PLAN.md Pitfall-1 fix: group observations by ``settlement_date_for``,
    # NOT by ``observed_at[:10]`` - the latter would drop the pre-midnight
    # UTC tail into the wrong LST settlement day.
    obs_by_date: dict[str, list[dict[str, Any]]] = {d: [] for d in dates}
    for r in raw_obs:
        observed_at = r.get("observed_at")
        if not observed_at:
            continue
        settle_date = settlement_date_for(observed_at, info.code, tz_override=tz_override)
        bucket = obs_by_date.get(settle_date)
        if bucket is not None:
            bucket.append(r)

    climate_by_date: dict[str, dict[str, Any] | None] = {}
    for r in raw_climate:
        obs_date = r.get("observation_date")
        if obs_date:
            climate_by_date[obs_date] = r

    # PLAN-09: when include_forecast=False, pass None for both forecast
    # dicts so build_pairs/build_pairs_row hit the parity-preserving paths
    # (no fcst_* population beyond the default-None scaffolding). When
    # include_forecast=True, hand over the IEM MOS Mode 1 dict and (if
    # forecast_models was provided) the Mode 2 per-model NWP dict.
    rows = build_pairs(
        info.code,
        dates,
        obs_by_date,
        climate_by_date,
        forecasts_by_date=iem_mos_by_date if include_forecast else None,
        forecast_model=forecast_model,
        tz_override=tz_override,
        nwp_forecasts_by_model_date=nwp_by_model_date if include_forecast else None,
    )
    # Phase 6 W3-T2 + W3-T3: backend / return_type already validated at
    # the top of research() (codex iter-2 P2 fix). Here we only need the
    # wrap_result helper to convert + wrap the pandas result if the
    # caller opted into a non-default backend or return_type.
    from mostlyright.core._backend_dispatch import wrap_result

    result = pairs_to_dataframe(rows) if as_dataframe else rows
    # Phase 3.4: surface qc summary on df.attrs when the qc=True opt-in
    # ran. Mode 1 parity rows themselves are unchanged (only attrs).
    if qc_summary is not None and as_dataframe:
        import contextlib

        with contextlib.suppress(AttributeError):
            result.attrs["qc"] = qc_summary

    # Phase 6 W3-T2: when as_dataframe=False the caller wants raw list[dict] —
    # backend/return_type kwargs do not apply. Same when backend kwarg is the
    # default (pandas + dataframe) — return unchanged for zero-overhead.
    if not as_dataframe or (backend == "pandas" and return_type == "dataframe"):
        return result

    # Wrapper / polars conversion path. result.attrs carries source +
    # retrieved_at populated by mode2/upstream adapters; the wrapper
    # surfaces them as explicit fields. Codex iter-3 P2 fix: pass
    # through retrieved_at from attrs (if the pipeline stamped one)
    # so the wrapper provenance matches what the adapters captured,
    # not datetime.now() at wrap time. research() doesn't currently
    # stamp this (pairs are heterogeneous), so the fallback to now()
    # is acceptable here — but future pairs-level provenance work
    # should populate result.attrs["retrieved_at"] for consistency.
    return wrap_result(
        result,
        backend=backend,  # type: ignore[arg-type]
        return_type=return_type,  # type: ignore[arg-type]
        source=str(result.attrs.get("source", "mostlyright.research")),
        retrieved_at=result.attrs.get("retrieved_at"),
        schema_id=None,  # research() returns heterogeneous pairs, not a single schema
        qc=qc_summary,
    )


__all__ = ["research"]

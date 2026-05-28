"""IEM ASOS historical METAR fetcher — yearly-chunked CSV downloads.

Wraps ``https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py`` for arbitrary
date ranges. The IEM ``asos.py`` endpoint accepts day1/day2 date filters but treats
``day2`` as EXCLUSIVE — to include observations on the caller's inclusive ``end``
date, every chunk extends ``day2`` to the first day of the following year. Over-fetch
beyond the caller's end date is harmless: the parser is idempotent and dedup happens
downstream.

Phase 1.5 PERF-01/02/03 — lifts mostlyright PR #85 (commit ``cf9eb85``, 2026-05-12):

- **PERF-01 chunk size:** monthly → 365-day calendar-aligned via the shared
  :mod:`~mostlyright.weather._fetchers._iem_chunks` helper (leap-year safe).
- **PERF-02 cache filename + partial namespace:** cache key encodes the full chunk
  window (``iem_{start_iso}_{end_iso}_{suffix}.csv``); ``skip_cache=True`` OR
  ``chunk_end > today_utc`` routes to the ``_partial_`` infix namespace that backfill
  never reads (closes three cache-poisoning paths PR #85 documented).
- **PERF-03 timeout** lives in :mod:`mostlyright._internal._http` (separate concern).

mostlyright-specific deviation from PR #85 verbatim
==================================================

PR #85's :func:`yearly_chunks_exclusive_end` uses ``chunk_start = max(current, start)``,
which floats the chunk's start with the caller. That works for PR #85's "one big
backfill" caller pattern but defeats cache idempotence when mostlyright'
``research.py`` calls this fetcher month-by-month — each different start date
produces a different cache filename, forcing 12 full-year fetches per year.

Resolution: this fetcher normalizes the caller's ``start`` to ``date(start.year, 1, 1)``
before invoking the chunker. Cache filename becomes year-stable
(``iem_YYYY-01-01_YYYY+1-01-01_<suffix>.csv``) so a per-month caller hits the cache
on every month after the first. Over-fetch is documented-safe (the parser is
idempotent; downstream filters by date). The chunker module itself remains PR-#85
verbatim — see :mod:`mostlyright.weather._fetchers._iem_chunks`.

Conventions
===========

- IEM is a university server — keep a polite 1.0s delay between requests.
- ``report_type``: ``3`` = METAR (routine), ``4`` = SPECI (special). IEM strips the
  ``SPECI`` keyword from raw METAR text, so callers that want observation_type
  tagging should issue both report types in turn and pass the corresponding
  ``observation_type_override`` to ``parse_iem_file``.

Out of scope here: parsing (see ``mostlyright.weather._iem``), parquet staging/merge,
gap-fill orchestration.
"""

from __future__ import annotations

import logging
import time
from datetime import UTC, date, datetime
from pathlib import Path

from mostlyright._internal._bounds import validate_icao_for_path
from mostlyright._internal._http import download_with_retry
from mostlyright._internal.models.station import StationInfo
from mostlyright.weather._fetchers._iem_chunks import yearly_chunks_exclusive_end

log = logging.getLogger(__name__)

IEM_BASE_URL = "https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py"

# Polite delay (seconds) between consecutive IEM HTTP requests. IEM runs on Iowa
# State infrastructure; v0.14.1 used 1.0s and has not been throttled. IEM published
# a 1-sec/IP throttle on 2026-04-21 — see .planning/research/SOURCE-LIMITS.md.
IEM_POLITE_DELAY = 1.0

# IEM report_type codes: (HTTP param int, on-disk suffix).
# 3 = METAR (routine hourly), 4 = SPECI (special / off-cycle).
_REPORT_TYPE_SUFFIX: dict[int, str] = {3: "metar", 4: "speci"}


def _iem_cache_filename(
    chunk_start: date,
    chunk_end: date,
    suffix: str,
    *,
    partial: bool,
) -> str:
    """Build a cache filename encoding the full chunk window.

    Pattern:
      - canonical: ``iem_{start_iso}_{end_iso}_{suffix}.csv``
      - partial:   ``iem_{start_iso}_{end_iso}_partial_{suffix}.csv``

    The ``_partial`` infix is part of the filename (not a sibling dir) so the
    canonical-cache lookup ``dest.exists()`` cleanly misses partial files —
    backfill never reads partials. PERF-02 / Pitfall 3 (OR-not-AND) gates this.
    """
    partial_infix = "_partial" if partial else ""
    return f"iem_{chunk_start.isoformat()}_{chunk_end.isoformat()}{partial_infix}_{suffix}.csv"


def _build_iem_url(
    station: StationInfo,
    start: date,
    end: date,
    report_type: int,
) -> str:
    """Build the IEM ASOS download URL for one (chunk, report_type) request.

    Param shape and ordering are preserved byte-for-byte from v0.14.1's
    ``ingest/sources/iem_gap_fill.py::_build_iem_url`` so URL snapshots stay
    diff-stable across the lift. ``station.code`` is the 3-letter no-K-prefix
    identifier (e.g. ``"NYC"``, not ``"KNYC"``) — IEM ASOS expects the bare code.

    Args:
        station: Station whose ``.code`` is used as ``station=...``.
        start: Inclusive first date of the request window.
        end: EXCLUSIVE last date (already adjusted by :func:`yearly_chunks_exclusive_end`).
        report_type: ``3`` for METAR, ``4`` for SPECI.

    Returns:
        Fully-qualified URL (no trailing newline, no anchor).
    """
    params = (
        f"station={station.code}"
        f"&data=all&tz=Etc/UTC&format=comma&latlon=no&elev=no"
        f"&missing=M&trace=T&direct=no&report_type={report_type}"
        f"&year1={start.year}&month1={start.month}&day1={start.day}"
        f"&year2={end.year}&month2={end.month}&day2={end.day}"
    )
    return f"{IEM_BASE_URL}?{params}"


def download_iem_asos(
    station: StationInfo,
    start: date,
    end: date,
    dest_dir: Path,
    *,
    skip_cache: bool = False,
    report_type: int = 3,
    exact_window: bool = False,
) -> list[Path]:
    """Download yearly chunks of IEM ASOS data, returning local CSV paths.

    The caller's inclusive ``[start, end]`` is normalized to ``[date(start.year,1,1),
    end]`` and split into per-calendar-year EXCLUSIVE-end chunks (PERF-01). Each
    chunk's response is cached at
    ``dest_dir / station.code / iem_{start_iso}_{end_iso}_{partial?}_{suffix}.csv``.

    Phase 7 ``exact_window`` mode
    -----------------------------
    When ``exact_window=True``, the year-normalization is BYPASSED — the URL
    uses the caller's ``start``/``end`` directly (day-granular ``day1=``/``day2=``).
    For a 1-month KNYC query, this drops the cold-fetch budget from ~13 MB
    (full-year CSV) to ~2 MB. Callers are responsible for pointing ``dest_dir``
    at a SEPARATE directory namespace (e.g. ``sources/iem_asos_exact``) so the
    canonical yearly-cache filenames are never poisoned (B-5: directory-level
    separation, NOT filename infix). The ``_partial`` mutable-period gate is
    preserved — chunks whose end exceeds today UTC still route to the
    ``_partial`` infix.

    A chunk is treated as **partial** (and routed to the ``_partial_`` namespace
    that backfill never reads) when either:

    - ``skip_cache=True``: the caller has declared the source view stale (e.g. live
      freshness sweep). Without ``_partial`` namespacing, the fresh response would
      overwrite a canonical cache file with potentially-truncated data — PERF-02
      OR-branch A.
    - ``chunk_end > today_utc``: the chunk extends past the current UTC date, so
      IEM's response cannot be complete yet (today's METARs are still landing).
      UTC, not local: the cutoff uses ``datetime.now(timezone.utc).date()``. A
      naive ``date.today()`` would silently truncate data for non-UTC hosts at the
      day boundary (Europe/Prague is UTC+1/+2; "today" there for the first hours
      of UTC midnight is the NEXT UTC day) — PERF-02 OR-branch B / Pitfall 2.

    The two conditions are joined by **OR**, not AND (Pitfall 3): each independently
    can poison the cache.

    Args:
        station: Station to download. ``station.code`` (3-letter, no K prefix) is
            sent to IEM; ``station.icao`` is unused here but kept on the dataclass
            so callers can use one type for fetcher + parser flows.
        start: Inclusive first date in the desired range. Normalized to
            ``date(start.year, 1, 1)`` internally so per-month callers hit the
            same yearly cache key.
        end: INCLUSIVE last date in the desired range. The IEM endpoint's
            end-exclusive quirk is handled internally by the yearly chunker.
        dest_dir: Root directory for cached CSVs. A per-station subdirectory
            (``station.code``) is created automatically.
        skip_cache: When ``True``, route every chunk to the ``_partial`` namespace
            (the canonical cache is left untouched; live sweeps cannot poison
            backfill).
        report_type: ``3`` for METAR (default), ``4`` for SPECI. Callers that need
            both should invoke this twice and pass the matching
            ``observation_type_override`` to ``parse_iem_file``.
        exact_window: When ``True``, Phase 7 path — skip year-normalization and
            issue a single day-granular request for the caller's exact
            ``[start, end]``. Callers must point ``dest_dir`` at a separate
            namespace (e.g. ``sources/iem_asos_exact``) to avoid polluting the
            canonical yearly-cache directory.

    Returns:
        List of local file paths — one entry per yearly chunk. Both cached and
        freshly-downloaded paths are included; order matches the natural chunking
        from :func:`yearly_chunks_exclusive_end`.

    Raises:
        ValueError: If ``report_type`` is not in ``{3, 4}`` or ``station.code`` is
            not a safe ICAO (path-traversal guard).
        httpx.HTTPStatusError: Propagated from ``download_with_retry`` for
            persistent 5xx exhaustion or 404 responses.
    """
    if report_type not in _REPORT_TYPE_SUFFIX:
        raise ValueError(f"report_type must be 3 (METAR) or 4 (SPECI), got {report_type!r}")
    # Defense-in-depth: validate station.code at the URL/path boundary BEFORE it goes
    # into the IEM URL param or the per-station cache subdirectory. StationInfo.code
    # is supposed to be a curated 3-letter no-K-prefix ICAO from the registry, but
    # the check at the boundary catches any registry corruption or mis-call.
    validate_icao_for_path(station.code, field="station.code")
    # Reversed-range guard (codex iter-1 HIGH): the underlying chunker honors
    # ``start > end -> []``, but the mostlyright-specific year-normalization
    # below would mask an inverted same-year range and fire a full-year
    # download. Mirror the chunker invariant at the caller boundary.
    if start > end:
        return []
    suffix = _REPORT_TYPE_SUFFIX[report_type]
    if exact_window:
        # Phase 7: skip year-normalization entirely; one day-granular chunk
        # for the caller's exact [start, end]. IEM treats day2 as EXCLUSIVE,
        # so extend by 1 day to mirror the chunker's contract — preserves the
        # downstream code path (filename / partial gate / URL builder) without
        # special-casing it.
        from datetime import timedelta as _td

        chunks = [(start, end + _td(days=1))]
    else:
        # mostlyright-specific: normalize start to Jan 1 of its year so per-month
        # callers share a yearly cache key. PR #85's chunker uses
        # max(current, start), which floats the chunk_start with the caller —
        # fine for one-shot backfills, wasteful for mostlyright' per-month
        # research.py loop. See module docstring "Deviation".
        normalized_start = date(start.year, 1, 1)
        chunks = yearly_chunks_exclusive_end(normalized_start, end)
    today_utc = datetime.now(UTC).date()
    paths: list[Path] = []
    for chunk_start, chunk_end in chunks:
        # OR not AND (Pitfall 3): either condition independently can poison the
        # cache. UTC not local (Pitfall 2): date.today() truncates on non-UTC hosts.
        chunk_is_partial = skip_cache or chunk_end > today_utc
        filename = _iem_cache_filename(chunk_start, chunk_end, suffix, partial=chunk_is_partial)
        dest = dest_dir / station.code / filename
        if dest.exists() and not chunk_is_partial:
            log.info("IEM ASOS cache hit: %s", dest)
            paths.append(dest)
            continue
        url = _build_iem_url(station, chunk_start, chunk_end, report_type)
        download_with_retry(url, dest)
        time.sleep(IEM_POLITE_DELAY)
        paths.append(dest)
    return paths

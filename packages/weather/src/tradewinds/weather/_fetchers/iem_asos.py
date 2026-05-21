"""IEM ASOS historical METAR fetcher — monthly-chunked CSV downloads.

Wraps ``https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py`` for
arbitrary date ranges. The IEM ``asos.py`` endpoint accepts day1/day2 date
filters but treats ``day2`` as EXCLUSIVE — to include observations on the
caller's inclusive ``end`` date, every monthly chunk extends ``day2`` to the
first day of the following month. Over-fetch beyond the caller's end date is
harmless: the parser is idempotent and dedup happens downstream.

Net-new code lifted-in-pattern from monorepo-v0.14.1
``ingest/sources/iem_gap_fill.py``:
- ``_build_iem_url`` — exact param shape and ordering preserved.
- ``_monthly_chunks`` — splits arbitrary ranges into per-month requests.
- ``download_iem_asos`` — the public surface; one CSV per (month, report_type).

Conventions:
- IEM is a university server — keep a polite 1.0s delay between requests.
- The cache key is ``dest_dir / station.code / iem_<YYYYMM>_<suffix>.csv``;
  pass ``skip_cache=True`` to force a re-download (used by live sweeps).
- ``report_type``: ``3`` = METAR (routine), ``4`` = SPECI (special). IEM
  strips the ``SPECI`` keyword from raw METAR text, so callers that want
  observation_type tagging should issue both report types in turn and pass
  the corresponding ``observation_type_override`` to ``parse_iem_file``.

Out of scope here: parsing (see ``tradewinds.weather._iem``), parquet
staging/merge, gap-fill orchestration.
"""

from __future__ import annotations

import logging
import time
from datetime import date
from pathlib import Path

from tradewinds._internal._http import download_with_retry
from tradewinds._internal.models.station import StationInfo

log = logging.getLogger(__name__)

IEM_BASE_URL = "https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py"

# Polite delay (seconds) between consecutive IEM HTTP requests. IEM runs on
# Iowa State infrastructure; v0.14.1 uses 1.0s and has not been throttled.
IEM_POLITE_DELAY = 1.0

# IEM report_type codes: (HTTP param int, on-disk suffix).
# 3 = METAR (routine hourly), 4 = SPECI (special / off-cycle).
_REPORT_TYPE_SUFFIX: dict[int, str] = {3: "metar", 4: "speci"}


def _monthly_chunks(start: date, end: date) -> list[tuple[date, date]]:
    """Split a date range into monthly chunks with EXCLUSIVE end dates.

    IEM's ``day2`` parameter is exclusive: ``day2=2025-02-01`` is required to
    include observations from ``2025-01-31``. So every returned chunk ends on
    the first day of the *next* month, even when that overshoots the caller's
    inclusive ``end``. Over-fetch is fine — the IEM CSV parser is idempotent
    and downstream dedup handles redundant rows.

    The first chunk's ``start`` is clamped to ``start`` (not the 1st of the
    month) so we don't request data preceding the caller's window.

    Args:
        start: Inclusive first date in the desired range.
        end: Inclusive last date in the desired range.

    Returns:
        List of ``(chunk_start, chunk_end_exclusive)`` tuples, one per month
        touched by ``[start, end]``. Empty if ``end < start``.

    Examples:
        >>> _monthly_chunks(date(2025, 1, 5), date(2025, 1, 20))
        [(date(2025, 1, 5), date(2025, 2, 1))]
        >>> _monthly_chunks(date(2025, 1, 31), date(2025, 2, 15))
        [(date(2025, 1, 31), date(2025, 2, 1)), (date(2025, 2, 1), date(2025, 3, 1))]
    """
    chunks: list[tuple[date, date]] = []
    if end < start:
        return chunks
    current = date(start.year, start.month, 1)
    while current <= end:
        chunk_start = max(current, start)
        if current.month == 12:
            next_month_1st = date(current.year + 1, 1, 1)
        else:
            next_month_1st = date(current.year, current.month + 1, 1)
        chunks.append((chunk_start, next_month_1st))
        current = next_month_1st
    return chunks


def _build_iem_url(
    station: StationInfo,
    start: date,
    end: date,
    report_type: int,
) -> str:
    """Build the IEM ASOS download URL for one (chunk, report_type) request.

    Param shape and ordering are preserved byte-for-byte from v0.14.1's
    ``ingest/sources/iem_gap_fill.py::_build_iem_url`` so URL snapshots stay
    diff-stable across the lift. ``station.code`` is the 3-letter
    no-K-prefix identifier (e.g. ``"NYC"``, not ``"KNYC"``) — the IEM ASOS
    endpoint expects the bare code.

    Args:
        station: Station whose ``.code`` is used as ``station=...``.
        start: Inclusive first date of the request window.
        end: EXCLUSIVE last date (already adjusted by ``_monthly_chunks``).
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
) -> list[Path]:
    """Download monthly chunks of IEM ASOS data, returning local CSV paths.

    Splits ``[start, end]`` into monthly chunks, issues one HTTP request per
    chunk for ``report_type``, and writes the response to
    ``dest_dir / station.code / iem_<YYYYMM>_<suffix>.csv``. Existing files
    are returned as-is unless ``skip_cache=True``.

    Args:
        station: Station to download. ``station.code`` (3-letter, no K prefix)
            is sent to IEM; ``station.icao`` is unused here but kept on the
            dataclass so callers can use one type for fetcher + parser flows.
        start: Inclusive first date in the desired range.
        end: INCLUSIVE last date in the desired range. The IEM endpoint's
            end-exclusive quirk is handled internally by ``_monthly_chunks``.
        dest_dir: Root directory for cached CSVs. A per-station subdirectory
            (``station.code``) is created automatically.
        skip_cache: When ``True``, always re-download even if the destination
            file already exists. Used by live freshness sweeps.
        report_type: ``3`` for METAR (default), ``4`` for SPECI. Callers that
            need both should invoke this twice and pass the matching
            ``observation_type_override`` to ``parse_iem_file``.

    Returns:
        List of local file paths — one entry per monthly chunk. Both cached
        and freshly-downloaded paths are included; order matches the natural
        chronological chunking from ``_monthly_chunks``.

    Raises:
        ValueError: If ``report_type`` is not in ``{3, 4}``.
        httpx.HTTPStatusError: Propagated from ``download_with_retry`` for
            persistent 5xx exhaustion or 404 responses.
    """
    if report_type not in _REPORT_TYPE_SUFFIX:
        raise ValueError(f"report_type must be 3 (METAR) or 4 (SPECI), got {report_type!r}")
    suffix = _REPORT_TYPE_SUFFIX[report_type]
    chunks = _monthly_chunks(start, end)
    paths: list[Path] = []
    for chunk_start, chunk_end in chunks:
        filename = f"iem_{chunk_start.strftime('%Y%m')}_{suffix}.csv"
        dest = dest_dir / station.code / filename
        if dest.exists() and not skip_cache:
            log.info("IEM ASOS cache hit: %s", dest)
            paths.append(dest)
            continue
        url = _build_iem_url(station, chunk_start, chunk_end, report_type)
        download_with_retry(url, dest)
        time.sleep(IEM_POLITE_DELAY)
        paths.append(dest)
    return paths

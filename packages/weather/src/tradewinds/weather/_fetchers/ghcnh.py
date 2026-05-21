"""NCEI GHCNh per-year PSV fetcher.

Downloads NOAA's Global Historical Climatology Network - Hourly (GHCNh)
station-year PSV files from the NCEI public archive. One PSV per
station-year; ~10k stations worldwide, no API key required.

URL pattern (verified against monorepo-v0.14.1/ingest/sources/ghcnh_backfill.py)::

    https://www.ncei.noaa.gov/oa/global-historical-climatology-network/
        hourly/access/by-year/<YEAR>/psv/GHCNh_<station_id>_<YEAR>.psv

``station_id`` is the GHCNh identifier (typically the joined USAF-WBAN
form like ``"744860-94789"`` for KJFK, or an NCEI 11-character id).
The fetcher does not validate or transform the id — pass whatever the
upstream catalog uses.

Polite delay: 1 s between requests. NCEI is a government server; the
v0.14.1 backfill runner enforced this and we preserve it. The delay
fires AFTER a successful download so that range-mode pacing is on the
upstream-hit path only; cache hits and 404s do not pay the tax.

Caching: existing local files are returned without an HTTP round-trip
unless ``skip_cache=True`` is passed.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path

import httpx
from tradewinds._internal._http import download_with_retry

log = logging.getLogger(__name__)

GHCNH_BASE_URL = "https://www.ncei.noaa.gov/oa/global-historical-climatology-network/hourly/access"
"""NCEI GHCNh public archive base URL (no trailing slash)."""

NCEI_POLITE_DELAY = 1.0
"""Seconds to sleep between successful NCEI HTTP requests."""


def _ghcnh_filename(station_id: str, year: int) -> str:
    """Build the PSV filename for a station-year. Matches v0.14.1 exactly."""
    return f"GHCNh_{station_id}_{year}.psv"


def _ghcnh_url(station_id: str, year: int) -> str:
    """Build the full GHCNh URL for a station-year. Matches v0.14.1 exactly."""
    filename = _ghcnh_filename(station_id, year)
    return f"{GHCNH_BASE_URL}/by-year/{year}/psv/{filename}"


def download_ghcnh(
    station_id: str,
    year: int,
    dest_dir: Path,
    *,
    skip_cache: bool = False,
) -> Path:
    """Download a NOAA GHCNh PSV file for one station-year.

    The file is stored at ``dest_dir / station_id / GHCNh_<station_id>_<year>.psv``
    (mirrors v0.14.1's per-station subdirectory layout). The PSV write itself
    is atomic via ``download_with_retry`` (writes to ``.tmp`` and renames).

    Parameters
    ----------
    station_id:
        GHCNh station identifier (e.g. ``"744860-94789"`` for KJFK). The
        caller is responsible for mapping local station codes to GHCNh ids.
    year:
        Calendar year to fetch (e.g. ``2024``). NCEI provides one PSV per
        station-year under ``by-year/<year>/psv/``.
    dest_dir:
        Root directory for cached downloads. The per-station subdirectory
        is created if it does not exist.
    skip_cache:
        If ``True``, re-download even when a local copy exists. Defaults
        to ``False`` (cache-first, polite to NCEI).

    Returns
    -------
    Path
        Path to the local PSV file.

    Raises
    ------
    httpx.HTTPStatusError
        On 404 (no data for this station-year) or after exhausting
        transient retries (500/502/503/504). Callers wanting the
        404-skip behavior should use :func:`download_ghcnh_range`.
    """
    filename = _ghcnh_filename(station_id, year)
    dest = dest_dir / station_id / filename

    if dest.exists() and not skip_cache:
        return dest

    url = _ghcnh_url(station_id, year)
    download_with_retry(url, dest)
    # Polite delay only after a real network round-trip succeeded.
    time.sleep(NCEI_POLITE_DELAY)
    return dest


def download_ghcnh_range(
    station_id: str,
    start_year: int,
    end_year: int,
    dest_dir: Path,
    *,
    skip_cache: bool = False,
) -> list[Path]:
    """Download GHCNh PSVs for a contiguous year range.

    Iterates ``[start_year, end_year]`` inclusive. Years that return 404
    (no data for that station-year) are logged at WARNING and skipped;
    every other ``HTTPStatusError`` bubbles up so transient archive
    failures stop the run loudly.

    Parameters
    ----------
    station_id:
        GHCNh station identifier.
    start_year, end_year:
        Inclusive year range. ``end_year < start_year`` returns ``[]``.
    dest_dir:
        Root directory for cached downloads.
    skip_cache:
        If ``True``, re-download every year even when locally cached.

    Returns
    -------
    list[Path]
        Paths to the local PSV files (one per year that produced data),
        in chronological order. 404 years are omitted from the list.
    """
    paths: list[Path] = []
    for year in range(start_year, end_year + 1):
        try:
            path = download_ghcnh(
                station_id,
                year,
                dest_dir,
                skip_cache=skip_cache,
            )
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                log.warning(
                    "GHCNh %s %d: no data (404), skipping",
                    station_id,
                    year,
                )
                continue
            raise
        paths.append(path)
    return paths

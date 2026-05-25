"""IEM CLI (NWS climate) historical fetcher — settlement-grade source.

Sprint 0 Wave 3B (Lane F). NEW code. Wraps:

- ``mostlyright._internal._http.download_with_retry`` — atomic write + 5xx retry.
- ``mostlyright.weather._climate.parse_cli_response`` (consumed downstream).

URL pattern + cache layout lifted READ-ONLY from monorepo-v0.14.1
``ingest/sources/climate_sync.py::download_cli`` (see also Day 0.7 spike at
``spike/research_spike.py::fetch_iem_cli``).

Granularity is whole-year (one HTTP request per station-year). Callers that
want a window filter the parsed records to their date range — IEM's cli.py
endpoint does not support partial-year requests.

Settlement-grade. Kalshi NHIGH/NLOW contracts settle on the ``high`` and
``low`` fields in each record, so cache writes are byte-faithful to the JSON
array returned by IEM (post-``{"results": [...]}``-unwrap).
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path

import httpx
from filelock import FileLock
from mostlyright._internal._bounds import validate_icao_for_path
from mostlyright._internal._http import download_with_retry

# Match cache.py's lock timeout so concurrent downloaders surface deadlocks
# rather than hanging forever.
_IEM_CLI_LOCK_TIMEOUT_SECONDS = 30

log = logging.getLogger(__name__)

# IEM cli.py JSON endpoint. URL constant kept here so live smoke tests in
# ``tests/_climate/test_climate.py`` can import it once Wave 3B is merged.
IEM_CLI_BASE_URL = "https://mesonet.agron.iastate.edu/json/cli.py"

# Polite delay between requests — IEM runs on a university server. Matches
# v0.14.1's ``IEM_CLI_POLITE_DELAY`` (1.0s).
IEM_CLI_POLITE_DELAY = 1.0


def _cache_path(station_icao: str, year: int, dest_dir: Path) -> Path:
    """Cache key: ``<dest_dir>/<icao>/cli_<year>.json``."""
    return dest_dir / station_icao / f"cli_{year}.json"


def download_cli(
    station_icao: str,
    year: int,
    dest_dir: Path,
    *,
    skip_cache: bool = False,
) -> Path:
    """Download IEM CLI JSON for one station-year.

    URL: ``https://mesonet.agron.iastate.edu/json/cli.py?station={icao}&year={year}``

    Response may be wrapped as ``{"results": [...]}`` — we unwrap and save the
    inner list as a clean JSON array so downstream parsers always see the same
    shape. Saves via atomic ``.tmp``-then-rename.

    Caches: skip if ``<dest_dir>/<icao>/cli_<year>.json`` exists and
    ``skip_cache=False``.

    Args:
        station_icao: 4-letter ICAO, e.g. ``"KNYC"``. Used verbatim in the
            ``station`` URL param and the cache subdir.
        year: 4-digit year. One HTTP request per year — caller chunks if
            needed.
        dest_dir: Cache root. The per-station subdir is created on demand.
        skip_cache: If True, re-download even when the local file exists.

    Returns:
        Path to the local cached file (the unwrapped JSON array).

    Raises:
        httpx.HTTPStatusError: 404 (no data for that year) or 5xx after
            ``MAX_RETRIES`` attempts. Caller decides whether to continue
            (see :func:`download_cli_range`).
        ValueError: IEM returned a response that is neither a list nor a
            dict containing a ``"results"`` list.
    """
    # Rob C1/H8: validate at the boundary BEFORE the string flows into the
    # URL param or the cache path. STATION_CODE_RE rejects any path-separator
    # or shell-special character; the regex anchors require a strict ICAO.
    validate_icao_for_path(station_icao, field="station_icao")
    dest = _cache_path(station_icao, year, dest_dir)
    if dest.exists() and not skip_cache:
        return dest

    url = f"{IEM_CLI_BASE_URL}?station={station_icao}&year={year}"

    # Rob H5: two concurrent `download_cli` calls for the same station-year
    # both write to the same `cli_<year>_raw.json` staging file and could read
    # each other's partial data. Serialize the entire download -> read ->
    # parse -> atomic-replace block on a FileLock keyed on the final dest.
    # Lock sidecar lives next to dest; `filelock` creates it if missing.
    dest.parent.mkdir(parents=True, exist_ok=True)
    lock = FileLock(str(dest) + ".lock", timeout=_IEM_CLI_LOCK_TIMEOUT_SECONDS)
    with lock:
        # Re-check under the lock: another process may have just finished
        # writing the same dest while we were blocked on the lock acquisition.
        if dest.exists() and not skip_cache:
            return dest

        # Stage the raw response next to the final cache file.
        # download_with_retry writes atomically (.tmp then rename), so a
        # partial fetch never appears under raw_path. We then unwrap and
        # rewrite to dest atomically.
        raw_path = dest_dir / station_icao / f"cli_{year}_raw.json"
        download_with_retry(url, raw_path)

        try:
            raw_text = raw_path.read_text(encoding="utf-8", errors="replace")
            data = json.loads(raw_text)

            if isinstance(data, dict) and "results" in data:
                data = data["results"]

            if not isinstance(data, list):
                raise ValueError(
                    f"Unexpected IEM CLI response shape for {station_icao} {year}: "
                    f"{type(data).__name__}"
                )

            tmp = dest.with_suffix(".json.tmp")
            tmp.write_text(json.dumps(data))
            # Codex W3B P2: Path.replace() overwrites existing files
            # atomically on both POSIX and Windows; Path.rename() raises
            # FileExistsError on Windows when dest exists, breaking the
            # skip_cache=True force-refresh path.
            tmp.replace(dest)
        finally:
            # Always drop the raw staging file: on success it's redundant
            # with dest; on failure it's a partial/corrupt response we don't
            # want to leak back as a fake cache hit on the next call.
            raw_path.unlink(missing_ok=True)

    time.sleep(IEM_CLI_POLITE_DELAY)
    return dest


def download_cli_range(
    station_icao: str,
    start_year: int,
    end_year: int,
    dest_dir: Path,
    *,
    skip_cache: bool = False,
) -> list[Path]:
    """Download CLI JSON for an inclusive year range.

    Skips 404s (IEM "no data for this year") with an info log so multi-year
    backfills do not abort when a station has gaps. Other HTTP errors
    propagate.

    Args:
        station_icao: 4-letter ICAO, e.g. ``"KNYC"``.
        start_year: Inclusive lower bound.
        end_year: Inclusive upper bound. Must be ``>= start_year``.
        dest_dir: Cache root (same layout as :func:`download_cli`).
        skip_cache: Forwarded to :func:`download_cli` for each year.

    Returns:
        Paths for the years that downloaded successfully (or were cache
        hits). Years that 404'd are absent from the list — callers should
        treat the result as a sparse manifest.
    """
    if end_year < start_year:
        raise ValueError(f"end_year ({end_year}) must be >= start_year ({start_year})")

    # Validate once up front so a bad string fails fast (per-year loop would
    # also catch it on the first iteration, but this keeps the error site
    # next to the public argument).
    validate_icao_for_path(station_icao, field="station_icao")

    paths: list[Path] = []
    for year in range(start_year, end_year + 1):
        try:
            path = download_cli(station_icao, year, dest_dir, skip_cache=skip_cache)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                log.info("%s CLI %d: no data (404), skipping", station_icao, year)
                continue
            raise
        paths.append(path)

    return paths

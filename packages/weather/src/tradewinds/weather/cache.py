"""Local parquet cache for tradewinds weather observations and climate.

NEW module (no v0.14.1 reference). v0.14.1 is a hosted-client SDK — merging
and caching happen server-side there. The tradewinds local-first SDK ships
caching client-side so re-runs of ``research()`` against the same date range
hit a local parquet file instead of re-fetching from IEM/AWC/GHCNh.

Path layout (CACHE-01)::

    $HOME/.tradewinds/cache/v1/observations/<STATION>/<YYYY>/<MM>.parquet
    $HOME/.tradewinds/cache/v1/climate/<STATION>/<YYYY>.parquet

Override the root via the ``TRADEWINDS_CACHE_DIR`` environment variable.

Safety guarantees (CACHE-07):
    - **Atomic write:** write to a sibling ``.tmp`` file inside a FileLock,
      then ``os.rename`` to the final path. A crash mid-write never leaves a
      truncated parquet at the read path.
    - **FileLock-guarded:** two concurrent ``write_cache`` workers serialize
      on a ``.lock`` sidecar file. Verified by the multiprocess test.
    - **LST-current-month-skip:** the current calendar month in the station's
      Local Standard Time is mutable (observations still arriving). Writes
      to that (year, month) are no-ops, and reads return ``None`` even if a
      stale file exists. Climate cache applies the same rule at year
      granularity. This prevents serving incomplete data on re-runs.

Parquet options (CACHE-01):
    Every write uses ``version="2.6"`` and ``coerce_timestamps="us"`` so the
    byte output is stable across pyarrow versions and microsecond-resolution
    timestamps survive roundtrip without nanosecond inflation.

This module is **parser-agnostic** — it operates on already-parsed
``list[dict]`` rows. Importing a parser (``_iem``, ``_awc``, etc.) would
couple cache failures to fetcher failures; keeping the cache pure lets
``research()`` swap fetchers without touching the cache layer.
"""

from __future__ import annotations

import logging
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING

import pyarrow as pa
import pyarrow.parquet as pq
from filelock import FileLock

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

CACHE_VERSION = "v1"
DEFAULT_ROOT = Path.home() / ".tradewinds" / "cache"

# FileLock timeout in seconds. 30s is long enough to swallow a slow parquet
# write under concurrent load but short enough to surface a deadlock rather
# than hang forever.
LOCK_TIMEOUT_SECONDS = 30


# ---------------------------------------------------------------------------
# Dependency shims for sibling Wave 1 tasks
# ---------------------------------------------------------------------------
# Task 1.1 will land ``_lst_offset`` in ``tradewinds._internal._stations``.
# Task 1.2 will land ``OBSERVATION_SCHEMA``/``CLIMATE_SCHEMA`` in
# ``tradewinds._internal.merge._schemas``. Until those sibling sub-branches
# merge into ``phase-1/wave-1``, this module ships with safe fallbacks so the
# cache layer can be developed and tested in parallel. Per PLAN.md Task 1.4
# <depends_on>: "Task 1.1 ... Task 1.2 ... MUST merge LAST in Wave 1." When
# merging cache last, the real implementations are already present and the
# fallbacks become dead code (harmless).
def _lst_offset(station: str) -> timedelta:
    """Return the Local Standard Time offset for ``station`` (no DST).

    Imported lazily from ``tradewinds._internal._stations`` once Task 1.1
    lands. The fallback below derives the offset from a hardcoded mapping of
    the 20 Kalshi-traded stations using a January reference date so DST is
    never in effect. Sufficient for unit testing the cache's LST-month-skip
    logic without taking a hard dependency on Task 1.1.
    """
    try:
        # Real implementation lands in Task 1.1 sibling branch.
        from tradewinds._internal._stations import _lst_offset as _real_lst_offset

        return _real_lst_offset(station)
    except ImportError:
        # Fallback: derive offset from IANA tz using a January reference date.
        from zoneinfo import ZoneInfo

        # Whitelist of 20 Kalshi-traded stations -> IANA tz. Sourced from
        # tradewinds._internal.models.station._build_registry expectations.
        _STATION_TZ: dict[str, str] = {
            "KNYC": "America/New_York",
            "NYC": "America/New_York",
            "KLAX": "America/Los_Angeles",
            "LAX": "America/Los_Angeles",
            "KMSY": "America/Chicago",
            "MSY": "America/Chicago",
            "KMIA": "America/New_York",
            "MIA": "America/New_York",
            "KORD": "America/Chicago",
            "ORD": "America/Chicago",
            "KDEN": "America/Denver",
            "DEN": "America/Denver",
            "KPHX": "America/Phoenix",
            "PHX": "America/Phoenix",
            "KBOS": "America/New_York",
            "BOS": "America/New_York",
            "KSEA": "America/Los_Angeles",
            "SEA": "America/Los_Angeles",
            "KATL": "America/New_York",
            "ATL": "America/New_York",
        }
        tz = _STATION_TZ.get(station)
        if tz is None:
            raise ValueError(
                f"Unknown station {station!r}; expected an ICAO code from the "
                "Kalshi-traded whitelist (e.g. 'KNYC', 'KLAX')."
            ) from None
        jan_ref = datetime(2024, 1, 15, 12, 0, tzinfo=ZoneInfo(tz))
        offset = jan_ref.utcoffset() or timedelta(0)
        return offset


def _observation_schema() -> pa.Schema | None:
    """Return the pyarrow OBSERVATION_SCHEMA from Task 1.2, or None.

    None means "let pyarrow infer the schema from the rows" — sufficient for
    cache roundtrip during Wave 1 development. Task 1.4 merges last in Wave
    1; when that merge happens the schema is available and used explicitly.
    """
    try:
        from tradewinds._internal.merge._schemas import OBSERVATION_SCHEMA

        return OBSERVATION_SCHEMA
    except ImportError:
        return None


def _climate_schema() -> pa.Schema | None:
    """Return the pyarrow CLIMATE_SCHEMA from Task 1.2/1.3, or None."""
    try:
        from tradewinds._internal.merge._schemas import CLIMATE_SCHEMA

        return CLIMATE_SCHEMA
    except ImportError:
        return None


# ---------------------------------------------------------------------------
# Path layout
# ---------------------------------------------------------------------------
def _cache_root() -> Path:
    """Resolve the cache root from the env var or fall back to the default.

    Resolved on each call (not cached at import time) so tests can monkeypatch
    ``TRADEWINDS_CACHE_DIR`` between cases without a module reload.
    """
    override = os.environ.get("TRADEWINDS_CACHE_DIR")
    if override:
        return Path(override).expanduser()
    return DEFAULT_ROOT


def cache_path(station: str, year: int, month: int) -> Path:
    """Return the parquet cache path for the (station, year, month) tuple.

    Example::

        cache_path("KNYC", 2025, 1)
        # -> Path("$HOME/.tradewinds/cache/v1/observations/KNYC/2025/01.parquet")

    The month is zero-padded to two digits so a lexicographic directory listing
    matches chronological order.
    """
    return (
        _cache_root()
        / CACHE_VERSION
        / "observations"
        / station
        / f"{year:04d}"
        / f"{month:02d}.parquet"
    )


def climate_cache_path(station: str, year: int) -> Path:
    """Return the parquet cache path for annual climate data.

    Example::

        climate_cache_path("KNYC", 2025)
        # -> Path("$HOME/.tradewinds/cache/v1/climate/KNYC/2025.parquet")
    """
    return _cache_root() / CACHE_VERSION / "climate" / station / f"{year:04d}.parquet"


# ---------------------------------------------------------------------------
# Current-LST-month / -year predicates
# ---------------------------------------------------------------------------
def _now_lst(station: str) -> datetime:
    """Return the current datetime in the station's Local Standard Time."""
    return datetime.now(UTC) + _lst_offset(station)


def _is_current_lst_month(station: str, year: int, month: int) -> bool:
    """True if (year, month) is the current month in the station's LST.

    The current month is mutable — observations are still arriving from
    AWC/IEM/GHCNh. Caching it would serve stale data on subsequent reads.
    """
    now_lst = _now_lst(station)
    return now_lst.year == year and now_lst.month == month


def _is_current_lst_year(station: str, year: int) -> bool:
    """True if ``year`` is the current year in the station's LST.

    Climate cache is annual; the current year is mutable until 31 Dec
    rolls over in LST.
    """
    now_lst = _now_lst(station)
    return now_lst.year == year


# ---------------------------------------------------------------------------
# Live-endpoint check
# ---------------------------------------------------------------------------
def _is_live_source(source: str | None) -> bool:
    """True if ``source`` is a ``*.live`` endpoint (never cached).

    Live endpoints return the single most recent observation and would be
    misleading to cache: the next call wants the *next* observation, not the
    one in cache.
    """
    return bool(source) and source.endswith(".live")


# ---------------------------------------------------------------------------
# Atomic write helper
# ---------------------------------------------------------------------------
def _atomic_write(path: Path, table: pa.Table) -> None:
    """Write ``table`` to ``path`` atomically and under a FileLock.

    Crash-safety contract:
        1. The lock is acquired before any disk write.
        2. Parquet bytes are flushed to ``path.with_suffix('.tmp')`` first.
        3. ``os.rename(tmp, path)`` is atomic on POSIX filesystems —
           ``read_cache`` callers either see the old file or the new file,
           never a half-written one.
        4. If the rename fails, the lock context manager will still release
           the lock; the tmp file is left behind for a human to inspect.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    # Lock sidecar is co-located with the destination — `filelock` creates it
    # if missing. Use a per-path lock so writes to different stations/months
    # parallelize. The 30s timeout is generous enough for a multi-MB parquet
    # write under load, short enough to surface a deadlock.
    lock = FileLock(str(path) + ".lock", timeout=LOCK_TIMEOUT_SECONDS)
    with lock:
        pq.write_table(table, tmp, version="2.6", coerce_timestamps="us")
        # `os.replace` is atomic across both POSIX and Windows (unlike
        # `os.rename` on Windows which can fail if the destination exists).
        os.replace(tmp, path)


# ---------------------------------------------------------------------------
# Observation cache: read / write / invalidate
# ---------------------------------------------------------------------------
def read_cache(station: str, year: int, month: int) -> list[dict] | None:
    """Return cached observation rows for ``(station, year, month)`` or None.

    Returns ``None`` when:
        - the cache file does not exist
        - (year, month) is the station's current LST month (file may be stale)
        - a concurrent ``invalidate()`` removes the file between the
          ``exists()`` check and the read (treated as cache-miss; the caller
          re-fetches transparently)

    Returns ``list[dict]`` otherwise. The list is materialised eagerly from
    pyarrow - callers can iterate freely without holding a file handle.
    """
    if _is_current_lst_month(station, year, month):
        logger.debug(
            "cache read: skipping current LST month for %s %04d-%02d",
            station,
            year,
            month,
        )
        return None
    path = cache_path(station, year, month)
    if not path.exists():
        return None
    # Rob H3: TOCTOU race - `invalidate()` (lock-guarded) can unlink the file
    # between `exists()` and `pq.read_table()`. Treat the race as a cache miss
    # rather than locking reads (which would serialize all concurrent readers).
    # Catches FileNotFoundError + pyarrow.lib.ArrowIOError (both subclass OSError).
    try:
        table = pq.read_table(path)
    except (FileNotFoundError, OSError):
        return None
    return table.to_pylist()


def write_cache(
    station: str,
    year: int,
    month: int,
    rows: list[dict],
    *,
    source: str | None = None,
) -> None:
    """Atomically write ``rows`` to the observation cache.

    No-op (does NOT raise) when:
        - (year, month) is the station's current LST month
        - ``source`` ends with ``.live`` — live endpoints are never cached

    The ``source`` kwarg is optional. The standard call site (``research()``)
    passes the fetcher's endpoint identifier (e.g. ``"iem.asos"``,
    ``"awc.live"``) so the cache can gate writes uniformly without each
    fetcher having its own no-cache branch.
    """
    if _is_live_source(source):
        logger.debug(
            "cache write: skipping live source %r for %s %04d-%02d",
            source,
            station,
            year,
            month,
        )
        return
    if _is_current_lst_month(station, year, month):
        logger.debug(
            "cache write: skipping current LST month for %s %04d-%02d",
            station,
            year,
            month,
        )
        return
    schema = _observation_schema()
    table = pa.Table.from_pylist(rows, schema=schema)
    _atomic_write(cache_path(station, year, month), table)


def invalidate(station: str, year: int, month: int) -> bool:
    """Remove the cache entry for ``(station, year, month)``.

    Returns ``True`` if a file was removed, ``False`` if the file did not
    exist. Acquires the same FileLock as ``write_cache`` so an invalidation
    racing a write either runs strictly before or strictly after — never
    mid-rename.
    """
    path = cache_path(station, year, month)
    lock = FileLock(str(path) + ".lock", timeout=LOCK_TIMEOUT_SECONDS)
    with lock:
        if path.exists():
            path.unlink()
            return True
        return False


# ---------------------------------------------------------------------------
# Climate cache: read / write / invalidate (annual granularity)
# ---------------------------------------------------------------------------
def read_climate_cache(station: str, year: int) -> list[dict] | None:
    """Return cached climate rows for ``(station, year)`` or None.

    Returns ``None`` when:
        - the cache file does not exist
        - ``year`` is the station's current LST year (file may be stale)
        - a concurrent ``invalidate_climate()`` removes the file between the
          ``exists()`` check and the read (cache-miss semantics; caller
          re-fetches transparently)
    """
    if _is_current_lst_year(station, year):
        logger.debug(
            "climate cache read: skipping current LST year for %s %04d",
            station,
            year,
        )
        return None
    path = climate_cache_path(station, year)
    if not path.exists():
        return None
    # Rob H3: same TOCTOU race as read_cache (see comment there).
    try:
        table = pq.read_table(path)
    except (FileNotFoundError, OSError):
        return None
    return table.to_pylist()


def write_climate_cache(
    station: str,
    year: int,
    rows: list[dict],
    *,
    source: str | None = None,
) -> None:
    """Atomically write ``rows`` to the annual climate cache.

    No-op (does NOT raise) when:
        - ``year`` is the station's current LST year
        - ``source`` ends with ``.live``
    """
    if _is_live_source(source):
        logger.debug(
            "climate cache write: skipping live source %r for %s %04d",
            source,
            station,
            year,
        )
        return
    if _is_current_lst_year(station, year):
        logger.debug(
            "climate cache write: skipping current LST year for %s %04d",
            station,
            year,
        )
        return
    schema = _climate_schema()
    table = pa.Table.from_pylist(rows, schema=schema)
    _atomic_write(climate_cache_path(station, year), table)


def invalidate_climate(station: str, year: int) -> bool:
    """Remove the climate cache entry for ``(station, year)``.

    Returns ``True`` if removed, ``False`` if absent.
    """
    path = climate_cache_path(station, year)
    lock = FileLock(str(path) + ".lock", timeout=LOCK_TIMEOUT_SECONDS)
    with lock:
        if path.exists():
            path.unlink()
            return True
        return False


__all__ = [
    "CACHE_VERSION",
    "DEFAULT_ROOT",
    "cache_path",
    "climate_cache_path",
    "invalidate",
    "invalidate_climate",
    "read_cache",
    "read_climate_cache",
    "write_cache",
    "write_climate_cache",
]

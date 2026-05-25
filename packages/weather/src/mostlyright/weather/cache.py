"""Local parquet cache for mostlyright weather observations and climate.

NEW module (no v0.14.1 reference). v0.14.1 is a hosted-client SDK — merging
and caching happen server-side there. The mostlyright local-first SDK ships
caching client-side so re-runs of ``research()`` against the same date range
hit a local parquet file instead of re-fetching from IEM/AWC/GHCNh.

Path layout (CACHE-01)::

    $HOME/.mostlyright/cache/v1/observations/<STATION>/<YYYY>/<MM>.parquet
    $HOME/.mostlyright/cache/v1/climate/<STATION>/<YYYY>.parquet

Override the root via the ``MOSTLYRIGHT_CACHE_DIR`` environment variable.

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
from mostlyright._internal._bounds import (
    assert_path_under,
    validate_icao_for_path,
)

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

CACHE_VERSION = "v1"
DEFAULT_ROOT = Path.home() / ".mostlyright" / "cache"

# FileLock timeout in seconds. 30s is long enough to swallow a slow parquet
# write under concurrent load but short enough to surface a deadlock rather
# than hang forever.
LOCK_TIMEOUT_SECONDS = 30


# ---------------------------------------------------------------------------
# LST offset resolution
# ---------------------------------------------------------------------------
# Wave 1 originally shipped a 10-station whitelist fallback here, expecting
# Task 1.1 to land ``_lst_offset`` under ``mostlyright._internal._stations``.
# The actual lift kept ``_lst_offset`` in ``mostlyright.snapshot`` (where it
# always lived in v0.14.1) - so the fallback became permanently active and
# raised ``ValueError`` for the 11 stations missing from its hardcoded map
# (KAUS, KDCA, KDFW, KHOU, KLAS, KMDW, KMSP, KOKC, KPHL, KSAT, KSFO). That
# silently broke ``research()`` for half the advertised registry once
# Wave 2 wired the public API through this cache layer.
#
# Resolution (Wave 2 codex iter-1 P1): delegate directly to
# ``mostlyright.snapshot._lst_offset``, which lifts the full 20-station tz
# map from v0.14.1 verbatim and ALSO accepts a ``tz_override`` argument
# (already supported by the v0.1.0 public surface). The import is local so
# ``mostlyright.weather.cache`` does not pull ``snapshot`` at module import
# time - keeping the dependency one-directional (weather depends on core,
# never the reverse).
def _lst_offset(station: str) -> timedelta:
    """Return the Local Standard Time offset for ``station`` (no DST).

    Thin wrapper over :func:`mostlyright.snapshot._lst_offset` - the canonical
    home of the 20-station tz map (lifted verbatim from
    ``monorepo-v0.14.1/src/mostlyright/snapshot.py``). Accepts both the
    3-letter NWS code and the 4-letter ICAO; the snapshot helper normalizes
    internally via ``_station_code_normalized``.

    Raises:
        ValueError: when ``station`` is unknown to the snapshot tz registry
            (matches the snapshot helper's contract; the orchestrator
            ``research()`` rejects unknown stations earlier with the same
            error class).
    """
    from mostlyright.snapshot import _lst_offset as _snapshot_lst_offset

    return _snapshot_lst_offset(station)


def _observation_schema() -> pa.Schema | None:
    """Return the pyarrow OBSERVATION_SCHEMA from Task 1.2, or None.

    None means "let pyarrow infer the schema from the rows" — sufficient for
    cache roundtrip during Wave 1 development. Task 1.4 merges last in Wave
    1; when that merge happens the schema is available and used explicitly.
    """
    try:
        from mostlyright._internal.merge._schemas import OBSERVATION_SCHEMA

        return OBSERVATION_SCHEMA
    except ImportError:
        return None


def _climate_schema() -> pa.Schema | None:
    """Return the pyarrow CLIMATE_SCHEMA from Task 1.2/1.3, or None."""
    try:
        from mostlyright._internal.merge._schemas import CLIMATE_SCHEMA

        return CLIMATE_SCHEMA
    except ImportError:
        return None


# ---------------------------------------------------------------------------
# Path layout
# ---------------------------------------------------------------------------
def _cache_root() -> Path:
    """Resolve the cache root from the env var or fall back to the default.

    Returns the cache ROOT (without ``/v1``). Callers append ``CACHE_VERSION``.
    Delegates to :func:`mostlyright._internal._cache_dir.resolve_cache_root_without_v1`
    (Phase 12 W4 + review-iter1 refactor) — single source of truth for the
    canonical → legacy + warn → default resolution order across all 3 legacy
    ``_cache_root()`` helpers.

    Resolved on each call (not cached at import time) so tests can monkeypatch
    the env var between cases without a module reload.
    """
    from mostlyright._internal._cache_dir import resolve_cache_root_without_v1

    return resolve_cache_root_without_v1()


def cache_path(station: str, year: int, month: int) -> Path:
    """Return the parquet cache path for the (station, year, month) tuple.

    Example::

        cache_path("KNYC", 2025, 1)
        # -> Path("$HOME/.mostlyright/cache/v1/observations/KNYC/2025/01.parquet")

    The month is zero-padded to two digits so a lexicographic directory listing
    matches chronological order.

    Validates ``station`` against STATION_CODE_RE (Rob C1) and asserts the
    resolved path stays under the cache root (defense-in-depth backstop -
    Rob C1).
    """
    validate_icao_for_path(station, field="station")
    root = _cache_root()
    raw = root / CACHE_VERSION / "observations" / station / f"{year:04d}" / f"{month:02d}.parquet"
    assert_path_under(raw, root, field="cache_path")
    return raw


def climate_cache_path(station: str, year: int) -> Path:
    """Return the parquet cache path for annual climate data.

    Example::

        climate_cache_path("KNYC", 2025)
        # -> Path("$HOME/.mostlyright/cache/v1/climate/KNYC/2025.parquet")

    Same validation contract as :func:`cache_path` (Rob C1).
    """
    validate_icao_for_path(station, field="station")
    root = _cache_root()
    raw = root / CACHE_VERSION / "climate" / station / f"{year:04d}.parquet"
    assert_path_under(raw, root, field="climate_cache_path")
    return raw


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


def _has_cached_year(
    station: str,
    year: int,
    cache_root: Path | None = None,
) -> bool:
    """True iff any monthly observation parquet exists for ``(station, year)``.

    Looks under ``$MOSTLYRIGHT_CACHE_DIR/v1/observations/{STATION}/{year}/*.parquet``.
    Used by the Phase 7 ``obs(strategy="auto")`` resolver in
    ``mostlyright.weather.obs`` to decide whether to dispatch to ``warm_cache``
    or ``exact_window``. Placed here (not in obs.py) so the parquet-layout
    contract has a single source of truth (I-4).
    """
    if cache_root is None:
        cache_root = _cache_root()
    year_dir = cache_root / CACHE_VERSION / "observations" / station.upper() / str(year)
    if not year_dir.is_dir():
        return False
    return any(year_dir.glob("*.parquet"))


__all__ = [
    "CACHE_VERSION",
    "DEFAULT_ROOT",
    "_has_cached_year",
    "cache_path",
    "climate_cache_path",
    "invalidate",
    "invalidate_climate",
    "read_cache",
    "read_climate_cache",
    "write_cache",
    "write_climate_cache",
]

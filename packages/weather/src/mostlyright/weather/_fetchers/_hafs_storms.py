"""HAFS active-storm resolver (Phase 17 PLAN-06, FORECAST-14).

Port of Herbie's ``hafs.py`` ``Storms()`` pattern. NOMADS publishes a
directory listing of currently-active hurricane/cyclone storm IDs under
``inphfsa/``; we GET the listing, regex-extract ``messageN`` filenames,
GET each message file to parse ``"center storm_id storm_name extra..."``.

The active-storms cache TTL is 1 hour (NOMADS friendliness per Herbie
issue #371). Historical HAFS access requires the caller to pass
``storm_id`` directly — Storms() only knows currently-active storms.
"""

from __future__ import annotations

import re
import threading
from datetime import UTC, datetime, timedelta

import httpx
from mostlyright._internal._http import HTTP_TIMEOUT
from mostlyright.core.exceptions import StormNotFoundError

#: NOMADS directory listing of currently-active HAFS storms.
_STORM_LIST_URL: str = "https://nomads.ncep.noaa.gov/pub/data/nccf/com/hafs/prod/inphfsa/"

#: Cache lifetime for the active-storms map. 1 hour matches the
#: typical operational cadence at which storms enter/exit the list.
_STORM_LIST_TTL: timedelta = timedelta(hours=1)

_MESSAGE_RE = re.compile(r"message\d+")

# Single-process in-memory cache keyed on "active". Lock-guarded for
# concurrent callers; per-request httpx.Client is closed on exit.
_storm_cache: dict[str, tuple[datetime, dict[str, str]]] = {}
_cache_lock = threading.Lock()


def _now() -> datetime:
    """Indirection for test-time mocking of the cache-clock."""
    return datetime.now(UTC)


def get_active_storms(
    *,
    client: httpx.Client | None = None,
    bust_cache: bool = False,
) -> dict[str, str]:
    """Return ``{storm_id: storm_name}`` (lowercase) for active HAFS storms.

    Cached for :data:`_STORM_LIST_TTL`. Pass ``bust_cache=True`` to skip
    the cache and re-fetch.

    Concurrency: the cache lock is held through the network I/O — a
    deliberate "single-flight" pattern. Two concurrent callers on a cold
    cache will not both fan out to NOMADS (that would double the request
    count past the load-bearing :data:`_NOMADS_CONCURRENCY_CAP` per
    Herbie issue #371). The second caller blocks briefly on the lock,
    then reads the cache the first caller just populated. The 1h TTL
    means at most one fetch per hour per process anyway.

    Args:
        client: Optional :class:`httpx.Client` to reuse a connection.
        bust_cache: If true, ignore any cached value and re-fetch.

    Returns:
        New dict (caller cannot mutate the cache by mutating the return
        value) mapping storm_id (e.g. ``"09l"``) to storm_name
        (e.g. ``"laura"``).
    """
    with _cache_lock:
        # Re-check cache inside the lock (defends against the
        # thundering-herd cache fill).
        cached = _storm_cache.get("active")
        if cached is not None and not bust_cache:
            fetch_time, storms = cached
            if (_now() - fetch_time) < _STORM_LIST_TTL:
                return dict(storms)

        close_client = False
        if client is None:
            client = httpx.Client(timeout=HTTP_TIMEOUT)
            close_client = True

        try:
            resp = client.get(_STORM_LIST_URL)
            resp.raise_for_status()
            # NOMADS returns an HTML directory listing — regex out messageN
            # filenames in document order (sorted for determinism).
            messages = sorted(set(_MESSAGE_RE.findall(resp.text)))

            storms = {}
            for message in messages:
                mresp = client.get(_STORM_LIST_URL + message)
                mresp.raise_for_status()
                # Format: "<center> <storm_id> <storm_name> <extra...>"
                parts = re.split(r"\s+", mresp.text.strip(), maxsplit=3)
                if len(parts) >= 3:
                    _center, storm_id, storm_name = parts[0], parts[1], parts[2]
                    storms[storm_id.lower()] = storm_name.lower()

            _storm_cache["active"] = (_now(), storms)
            return dict(storms)
        finally:
            if close_client:
                client.close()


def resolve_storm(
    query: str,
    *,
    client: httpx.Client | None = None,
    bust_cache: bool = False,
) -> str:
    """Resolve a storm query (id or name) to canonical lowercase storm_id.

    Raises:
        StormNotFoundError: ``query`` matches no currently-active storm.
            For historical storms, pass ``storm_id`` directly to
            ``forecast_nwp`` (e.g. ``storm="09l"``).
    """
    q = query.lower().strip()
    storms = get_active_storms(client=client, bust_cache=bust_cache)
    if q in storms:
        return q
    name_to_id = {name: sid for sid, name in storms.items()}
    if q in name_to_id:
        return name_to_id[q]
    raise StormNotFoundError(
        f"storm {query!r} not in active HAFS storms (only currently-active "
        "storms can be resolved by name; for historical storms pass storm_id "
        "directly, e.g. storm='09l')",
        query=query,
        active_storms=sorted(storms.keys()),
    )


def _clear_cache_for_tests() -> None:
    """Drop the cached active-storms map. Test-only."""
    with _cache_lock:
        _storm_cache.clear()


__all__ = [
    "_STORM_LIST_TTL",
    "_STORM_LIST_URL",
    "_clear_cache_for_tests",
    "get_active_storms",
    "resolve_storm",
]

"""AWC METAR HTTP fetcher — live observations from aviationweather.gov.

The AWC live endpoint (``https://aviationweather.gov/api/data/metar``) serves
only recent observations — at most the last ~168 hours (7 days). For historical
multi-day fetches use ``mostlyright.weather._fetchers.iem`` (IEM ASOS), which
has arbitrary historical depth.

Sprint 0 Day 0.7 spike confirmed reachability (artifacts in the maintainer planning
repo at ``research/spike-archive/``):
- ``research_spike.py::fetch_awc_live`` proved the endpoint works for the
  last 7 days with no auth.
- ``SPIKE_REPORT.md`` documents the AWC live limitation: cannot reach
  arbitrary historical dates.

URL pattern lifted from ``monorepo-v0.14.1/ingest/sources/awc_poller.py``
(``AWC_METAR_URL`` + ``fetch_latest``). The v0.14.1 implementation is async
(``httpx.AsyncClient``); this version is sync (``httpx.Client``) to stay
consistent with ``mostlyright._internal._http.download_with_retry``.

Return contract: list of raw AWC METAR dicts. Empty list on 4xx, timeout, or
exhausted retries — never raises (matches v0.14.1 ``fetch_latest`` behaviour
so the orchestrator in :mod:`mostlyright.weather.observations` can degrade
gracefully when AWC is down). The caller composes with
:func:`mostlyright.weather._awc.awc_to_observation` to produce schema-valid
observation dicts.
"""

from __future__ import annotations

import logging
import time
from typing import Any

import httpx
from mostlyright._internal._http import (
    BASE_DELAY,
    HTTP_TIMEOUT,
    MAX_RETRIES,
    TRANSIENT_CODES,
)

log = logging.getLogger(__name__)

AWC_METAR_URL = "https://aviationweather.gov/api/data/metar"

# AWC live serves at most ~168 hours (7 days). Beyond that the endpoint either
# silently truncates or returns an empty list — use IEM ASOS for history.
AWC_MAX_HOURS = 168


def fetch_awc_metars(station_icaos: list[str], hours: int = 168) -> list[dict[str, Any]]:
    """Fetch recent METAR observations from AWC for one or more stations.

    Args:
        station_icaos: list of ICAO codes (e.g. ``["KNYC", "KLAX"]``). At least
            one required; comma-joined into the ``ids`` query param.
        hours: lookback window in hours. AWC limits beyond ~168 (7 days);
            values above are still sent but the endpoint truncates server-side.

    Returns:
        Raw AWC METAR dicts (passed to :func:`mostlyright.weather._awc.awc_to_observation`
        by callers). Empty list on:

        - empty ``station_icaos`` (no request issued),
        - 4xx response (permanent client error — e.g. malformed station list),
        - network/timeout error after all retries exhausted,
        - 5xx response after all retries exhausted,
        - non-list JSON body (defensive — AWC should always return a list).

    Retries 5xx with exponential backoff (``BASE_DELAY`` → ``2*BASE_DELAY`` →
    …, ``MAX_RETRIES`` attempts). Logs warnings on transient errors.
    """
    if not station_icaos:
        return []

    ids_csv = ",".join(station_icaos)
    params = {
        "ids": ids_csv,
        "format": "json",
        "taf": "false",
        "hours": str(hours),
    }

    delay = BASE_DELAY
    with httpx.Client(timeout=HTTP_TIMEOUT) as client:
        for attempt in range(MAX_RETRIES):
            try:
                response = client.get(AWC_METAR_URL, params=params)
            except httpx.RequestError as exc:
                log.warning(
                    "AWC fetch failed (attempt %d/%d): %s",
                    attempt + 1,
                    MAX_RETRIES,
                    exc,
                )
                if attempt < MAX_RETRIES - 1:
                    time.sleep(delay)
                    delay *= 2
                    continue
                return []

            if response.status_code in TRANSIENT_CODES:
                log.warning(
                    "AWC HTTP %d for stations %s (attempt %d/%d)",
                    response.status_code,
                    ids_csv,
                    attempt + 1,
                    MAX_RETRIES,
                )
                if attempt < MAX_RETRIES - 1:
                    time.sleep(delay)
                    delay *= 2
                    continue
                return []

            if response.status_code >= 400:
                # 4xx: permanent client error (404 not-found, 400 bad ids, etc.)
                # Match v0.14.1 awc_poller.fetch_latest: log + return [], do not
                # raise. Callers want graceful degradation when AWC is unhappy.
                log.error(
                    "AWC HTTP %d for stations %s",
                    response.status_code,
                    ids_csv,
                )
                return []

            try:
                data = response.json()
            except ValueError:
                log.error("AWC returned invalid JSON for stations %s", ids_csv)
                return []

            if not isinstance(data, list):
                log.error(
                    "AWC returned non-list JSON for stations %s: %s",
                    ids_csv,
                    type(data).__name__,
                )
                return []

            return data

    return []

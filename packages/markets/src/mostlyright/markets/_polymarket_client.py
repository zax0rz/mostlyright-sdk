"""Polymarket Gamma API REST client — Phase 3.3.

Public read-only API at ``https://gamma-api.polymarket.com``. No auth
required, no API key, no rate limiting beyond a polite per-request
sleep (0.2s ≈ 300 req/min ceiling). Cloudfront returns 403 on blank
``User-Agent`` so the client always sets one. Paginated via
``offset += limit`` until the upstream returns fewer rows than
``limit`` (the cursor signal for end-of-data on the Gamma endpoint).

The client is deliberately narrow — only what
:mod:`mostlyright.markets.polymarket` needs for v0.1.0 discovery +
settlement. Order book, fills, and paid-feed endpoints are out of
scope (deferred to ``MARKETS-04`` Sprint 0.5+).

Pattern lifted from mostlyright ``sprint2/2t-impl-bundle:src/mostlyright/
markets/polymarket_client.py`` — kept the rate-limit + UA + paginate
loop verbatim; dropped the asyncio.Lock (mostlyright is sync-only in
v0.1) and the persistent cache layer (not needed for live discovery).
"""

from __future__ import annotations

import logging
import time
from typing import Any

import httpx
from mostlyright._internal._http import HTTP_TIMEOUT

log = logging.getLogger(__name__)


#: Polymarket Gamma API base URL — read-only public REST endpoint.
#: Hosts: ``/events``, ``/events/{id}``, ``/markets``.
GAMMA_API_BASE: str = "https://gamma-api.polymarket.com"


#: Polymarket CLOB API base URL — read-only public REST endpoint hosting
#: ``/prices-history``. Separate hostname from Gamma (Phase 9 architect
#: iter-1 CRITICAL: the prices-history endpoint moved from Gamma to CLOB
#: at some point and the `market` query parameter on this endpoint is the
#: CLOB token id (ERC-1155 asset id), NOT the Gamma market/condition id).
CLOB_API_BASE: str = "https://clob.polymarket.com"


#: Politeness sleep between requests (~300 req/min ceiling). Polymarket
#: doesn't publish a hard limit but this is well below where any sane
#: WAF would start rate-limiting and avoids the 429 cliff entirely.
_REQUEST_DELAY_S: float = 0.2


#: Per-page batch size for `/events` pagination. Polymarket's max is 500
#: but 100 keeps individual payloads small enough that a Cloudfront
#: hiccup doesn't trigger a 30 MB retry.
_EVENTS_LIMIT: int = 100


#: Safety cap on total events scanned per discovery call. 10k events
#: covers the entire Polymarket catalogue with headroom for v0.1.
_EVENTS_MAX: int = 10_000


#: Required user-agent header. Cloudfront returns 403 on a blank UA.
_USER_AGENT: str = "mostlyright-sdk/0.1 (+https://github.com/mostlyrightmd/mostlyright-sdk)"


def get_json(
    path: str,
    *,
    params: dict[str, Any] | None = None,
    client: httpx.Client | None = None,
    timeout: float = HTTP_TIMEOUT,
    sleep_between: float = _REQUEST_DELAY_S,
    base_url: str = GAMMA_API_BASE,
) -> Any:
    """Generic ``GET`` against a Polymarket public endpoint; returns parsed JSON.

    Phase 9 addition (TRADES-04..05): exposes the shared HTTP path so
    the trades surface can reuse the User-Agent + politeness + timeout
    discipline already established for events / event-by-id fetchers.

    Args:
        path: Path under ``base_url`` (must start with ``/``).
        params: Optional query parameters.
        client: Optional shared ``httpx.Client``.
        timeout: Per-request timeout in seconds.
        sleep_between: Per-request polite sleep (tests pass ``0``).
        base_url: Polymarket host base. Defaults to :data:`GAMMA_API_BASE`;
            callers needing the CLOB endpoint (``/prices-history``) pass
            :data:`CLOB_API_BASE` explicitly.

    Returns:
        Parsed JSON payload (``dict`` / ``list``).

    Raises:
        httpx.HTTPStatusError: Non-2xx response.
        httpx.RequestError: Connection failure.
    """
    owns_client = client is None
    if owns_client:
        client = httpx.Client(
            timeout=timeout,
            headers={"User-Agent": _USER_AGENT, "Accept": "application/json"},
        )
    try:
        response = client.get(f"{base_url}{path}", params=params)
        response.raise_for_status()
        if sleep_between > 0:
            time.sleep(sleep_between)
        return response.json()
    finally:
        if owns_client and client is not None:
            client.close()


def fetch_events(
    *,
    active_only: bool = True,
    closed: bool = False,
    client: httpx.Client | None = None,
    timeout: float = HTTP_TIMEOUT,
    sleep_between: float = _REQUEST_DELAY_S,
    max_events: int = _EVENTS_MAX,
) -> list[dict[str, Any]]:
    """Page through ``/events`` and return the deduplicated event list.

    Args:
        active_only: When True (default), include only events whose
            ``active`` field is truthy.
        closed: When True, include events whose ``closed`` field is
            truthy. Default False to surface only live markets.
        client: Optional ``httpx.Client`` for connection reuse. A fresh
            client is created (and closed) per call if omitted.
        timeout: Per-request timeout in seconds.
        sleep_between: Seconds to ``time.sleep`` between successive
            requests. Set to ``0`` in tests.
        max_events: Hard ceiling on the total number of events returned;
            page loop stops once this many events accumulated.

    Returns:
        List of event payloads (dicts), deduplicated by slug, in upstream
        order. Each payload is the raw Gamma API event — caller is
        responsible for projection / filtering.

    Raises:
        httpx.HTTPStatusError: Non-2xx response after the request was made.
        httpx.RequestError: Connection / DNS / TLS failure.
    """
    owns_client = client is None
    if owns_client:
        client = httpx.Client(
            timeout=timeout,
            headers={"User-Agent": _USER_AGENT, "Accept": "application/json"},
        )
    try:
        seen_slugs: set[str] = set()
        out: list[dict[str, Any]] = []
        offset = 0
        while offset < max_events:
            params: dict[str, Any] = {
                "limit": _EVENTS_LIMIT,
                "offset": offset,
                "closed": "true" if closed else "false",
            }
            if active_only:
                params["active"] = "true"
            response = client.get(f"{GAMMA_API_BASE}/events", params=params)
            response.raise_for_status()
            page = response.json()
            if not isinstance(page, list):
                # Defensive: Gamma occasionally wraps responses in {"data": [...]}.
                # If shape ever changes, fail loudly rather than silently empty out.
                raise ValueError(
                    f"Polymarket /events returned non-list payload: {type(page).__name__}"
                )
            if not page:
                break
            for event in page:
                slug = event.get("slug")
                if not slug or slug in seen_slugs:
                    continue
                seen_slugs.add(slug)
                out.append(event)
            if len(page) < _EVENTS_LIMIT:
                # Last page (smaller than the batch limit) — done.
                break
            offset += _EVENTS_LIMIT
            if sleep_between > 0:
                time.sleep(sleep_between)
        return out
    finally:
        if owns_client and client is not None:
            client.close()


def fetch_event_by_id(
    event_id: str,
    *,
    client: httpx.Client | None = None,
    timeout: float = HTTP_TIMEOUT,
) -> dict[str, Any]:
    """Fetch a single Polymarket event by id from ``/events/{id}``.

    Args:
        event_id: Polymarket event id. The caller has already validated
            this against :data:`mostlyright.markets.polymarket._EVENT_ID_RE`
            so we don't re-validate here — assume well-formed.
        client: Optional ``httpx.Client`` for connection reuse.
        timeout: Per-request timeout in seconds.

    Returns:
        Raw event payload dict.

    Raises:
        httpx.HTTPStatusError: Non-2xx (Gamma returns 404 for unknown ids).
        httpx.RequestError: Connection failure.
    """
    owns_client = client is None
    if owns_client:
        client = httpx.Client(
            timeout=timeout,
            headers={"User-Agent": _USER_AGENT, "Accept": "application/json"},
        )
    try:
        response = client.get(f"{GAMMA_API_BASE}/events/{event_id}")
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError(
                f"Polymarket /events/{event_id} returned non-dict payload: {type(payload).__name__}"
            )
        return payload
    finally:
        if owns_client and client is not None:
            client.close()


__all__ = [
    "GAMMA_API_BASE",
    "fetch_event_by_id",
    "fetch_events",
]

"""Phase 11 — `stream()` async generator.

Continuous poll loop over a single source. Yields each fresh observation
exactly once (dedup by ``observed_at``), then sleeps for the polite-floor
cadence before polling again.

Cancellation via ``break`` out of ``async for`` (or ``aclose()`` on the
iterator) terminates the loop cleanly — the polite-floor sleep is an
``asyncio.sleep`` and propagates ``CancelledError``.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from typing import Any

from tradewinds._internal._bounds import validate_icao_for_path
from tradewinds.live._latest import _fetch_latest, _pick_most_recent
from tradewinds.live._sources import (
    validate_poll_seconds,
    validate_source,
)

log = logging.getLogger(__name__)


async def stream(
    station: str,
    *,
    source: str | None = None,
    poll_seconds: float | None = None,
) -> AsyncIterator[dict[str, Any]]:
    """Yield fresh observations for ``station`` from a SINGLE source.

    The loop:

    1. Validate ``source`` + ``poll_seconds`` (raises ValueError BEFORE first poll).
    2. Poll once.
    3. If the most-recent observation's ``observed_at`` differs from the last
       one yielded, yield it. Otherwise skip (dedup).
    4. ``await asyncio.sleep(poll_seconds)``.
    5. Loop.

    Empty responses (network error, fetcher returned ``[]``) DO NOT abort the
    stream — they're treated as "nothing fresh yet" and the loop continues
    after the polite-floor sleep. To get a single-shot failure path, use
    :func:`latest`.

    Args:
        station: ICAO (``"KNYC"``) or 3-letter US ID (``"NYC"``).
        source: One of ``"awc"`` (default) or ``"iem"``.
        poll_seconds: Override the polite-floor cadence. Must be ``>=`` the
            per-source floor (AWC=30, IEM=60). When ``None``, uses the floor.

    Yields:
        One observation dict per fresh tick. ``source`` field is
        ``"awc.live"`` or ``"iem.live"``.

    Raises:
        ValueError: When ``source`` is unsupported or ``poll_seconds`` is
            below the polite floor (raised BEFORE the first poll).
    """
    src = validate_source(source)
    cadence = validate_poll_seconds(poll_seconds, src)
    # Validate the station upfront — `_fetch_latest` raises ValueError on a
    # malformed ICAO (e.g. ``"KN&data=foo"`` for IEM). Running this guard
    # BEFORE entering the poll loop means caller code gets the diagnostic
    # immediately instead of an empty stream that silently spins. We use the
    # same path-component validator the fetcher uses internally so the two
    # checks agree on what's malformed.
    icao = station.strip().upper()
    if len(icao) == 3:
        icao = f"K{icao}"
    validate_icao_for_path(icao[1:] if icao.startswith("K") and len(icao) == 4 else icao)
    last_observed_at: str | None = None

    while True:
        try:
            rows = await _fetch_latest(station, src)
        except asyncio.CancelledError:
            raise
        # Only swallow transient/runtime errors from the fetcher path.
        # ValueError + TypeError + AssertionError are programmer-error
        # signals (bad station codes, contract violations from upstream-
        # response munging, dispatch-table holes) and must NOT be silently
        # converted to empty ticks — the caller would be stuck in an
        # infinite empty-yield loop instead of getting the diagnostic.
        except (ValueError, TypeError, AssertionError):
            raise
        except Exception:  # noqa: BLE001 — transient fetcher exceptions must NOT abort
            log.exception(
                "live.stream: poll failed for station=%s source=%s — continuing",
                station,
                src,
            )
            rows = []
        picked = _pick_most_recent(rows)
        if picked is not None:
            current = picked.get("observed_at")
            if current and current != last_observed_at:
                last_observed_at = current
                yield picked
        await asyncio.sleep(cadence)


__all__ = ["stream"]

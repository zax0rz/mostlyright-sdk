"""Phase 3.3 — Polymarket discovery + settlement (US + international).

Phase 3.3 v0.1.0 scope: dispatch seam.

- :func:`polymarket_discover()` — Gamma API discovery (no auth required).
- :func:`polymarket_settle(event_id)` — settlement engine using internal
  ``daily_extremes()`` as the resolution source.
- Resolution-source URL allowlist: ``wunderground.com``, ``weather.gov``.
- Strict UUID4 validation on event_id (16 KB description cap +
  netloc allowlist — codex-flagged security-adjacent path).

Taipei + Hong Kong-lowest markets raise
:class:`tradewinds.international.DeferredMarketError`; v0.2 enables those
sources via CWA + HKO clients.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING
from urllib.parse import urlparse

from tradewinds.core.exceptions import TradewindsError

if TYPE_CHECKING:
    import pandas as pd


__all__ = [
    "RESOLUTION_SOURCE_ALLOWLIST",
    "polymarket_discover",
    "polymarket_settle",
]


#: Netloc allowlist for Polymarket resolution-source URLs. Anything else
#: raises ``ValueError`` to prevent silent settlement against an unknown
#: source.
RESOLUTION_SOURCE_ALLOWLIST: frozenset[str] = frozenset(
    {"wunderground.com", "www.wunderground.com", "weather.gov", "www.weather.gov"}
)

#: Polymarket event_id pattern — UUID4 format only.
_EVENT_ID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-4[0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$"
)

#: Maximum length of a Polymarket event description we'll parse for
#: resolution-source URL (security-adjacent — codex-flagged).
_MAX_DESCRIPTION_BYTES = 16 * 1024


class PolymarketEventError(TradewindsError):
    """Polymarket event payload is malformed (bad UUID, bad URL, oversized)."""

    default_error_code = "POLYMARKET_EVENT_INVALID"


def polymarket_discover() -> pd.DataFrame:
    """Discover active Polymarket weather markets via the Gamma API.

    Returns:
        DataFrame with one row per active weather market, columns
        ``event_id``, ``title``, ``resolution_source_type``,
        ``resolution_source_url``, ``end_time``.

    Raises:
        NotImplementedError: Phase 3.3 fetch wiring lands when the
            Polymarket client module is finalized.
    """
    raise NotImplementedError(
        "Polymarket discovery (Gamma API) lands in Phase 3.3 alpha. "
        "The dispatch seam + UUID + URL allowlist guards are in place; "
        "live HTTP wiring is next."
    )


def polymarket_settle(event_id: str, *, description: str | None = None) -> dict:
    """Resolve a Polymarket weather event to its settlement payload.

    Args:
        event_id: UUID4 event identifier (validated at the boundary).
        description: Polymarket event description; used to extract the
            resolution-source URL when present. Capped at 16 KB.

    Returns:
        Settlement payload with ``station``, ``settlement_date``,
        ``resolution_source_type``, ``resolution_source_url``.

    Raises:
        PolymarketEventError: invalid event_id format, oversized description,
            or resolution URL outside the allowlist.
        NotImplementedError: live settlement wiring lands in Phase 3.3.
    """
    # Strict UUID4 validation — security-adjacent boundary check.
    if not isinstance(event_id, str) or not _EVENT_ID_RE.match(event_id):
        raise PolymarketEventError(
            f"event_id must be a UUID4 string; got {event_id!r}",
        )
    if description is not None:
        if not isinstance(description, str):
            raise PolymarketEventError(
                "description must be a string or None; " f"got {type(description).__name__}",
            )
        if len(description.encode("utf-8")) > _MAX_DESCRIPTION_BYTES:
            raise PolymarketEventError(
                "description exceeds 16 KB cap (Polymarket markets carry "
                "concise descriptions; oversized payloads indicate an "
                "issuer error or hostile input)",
            )
        # Extract URLs and verify the allowlist.
        urls = re.findall(r'https?://[^\s<>"\')]+', description)
        for url in urls:
            try:
                netloc = urlparse(url).netloc.lower()
            except ValueError as exc:
                raise PolymarketEventError(f"unparseable resolution-source URL {url!r}") from exc
            if netloc and netloc not in RESOLUTION_SOURCE_ALLOWLIST:
                raise PolymarketEventError(
                    f"resolution-source URL {url!r} not in allowlist "
                    f"{sorted(RESOLUTION_SOURCE_ALLOWLIST)}"
                )

    raise NotImplementedError(
        "Polymarket settlement engine lands in Phase 3.3 alpha. "
        "Boundary validation passes; settlement-lookup wiring is next."
    )

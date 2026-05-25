"""tradewinds.live — single-source ticker surface.

`live.stream()` is an async generator that polls a SINGLE source (AWC or IEM)
on a polite-floor cadence and yields the most-recent observation per tick.
`live.latest()` is a one-shot version of the same fetch path.

This is intentionally distinct from `tradewinds.research()`:

|                | research()           | live.stream() / latest() |
|----------------|----------------------|--------------------------|
| Role           | DATABASE (training)  | TICKER (real-time)       |
| Sources        | AWC + IEM + GHCNh + CLI (fused) | ONE of AWC \\| IEM |
| Cache writes   | yes (parquet)        | no                       |
| QC             | yes (Phase 3.4)      | no                       |
| Loop semantics | none (point-in-time) | async generator          |

See `docs/live-streaming.md` for usage patterns.
"""

from __future__ import annotations

from tradewinds.core.exceptions import LiveStreamError, NoLiveDataError
from tradewinds.live._latest import latest
from tradewinds.live._sources import (
    POLITE_FLOORS_S,
    SUPPORTED_SOURCES,
    validate_source,
)
from tradewinds.live._stream import stream

__all__ = [
    "POLITE_FLOORS_S",
    "SUPPORTED_SOURCES",
    "LiveStreamError",
    "NoLiveDataError",
    "latest",
    "stream",
    "validate_source",
]

"""Historical fetcher modules for tradewinds.weather.

Sprint 0 Wave 3B (Lane F) — NET-NEW code (not lifted). Each submodule wraps a
public-API endpoint with chunking, retries, and on-disk caching, returning
local file paths that the corresponding parser (in ``tradewinds.weather``)
can ingest.

Modules:
- ``iem_asos`` — historical IEM ASOS METAR (CSV) fetcher with monthly chunking.

Out of scope here: GHCNh/AWC/CLI fetchers, cache invalidation (Wave 4),
observation/climate orchestration (Wave 4).
"""

from __future__ import annotations

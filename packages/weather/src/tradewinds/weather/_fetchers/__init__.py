"""Historical fetcher modules for tradewinds.weather (Sprint 0 Wave 3B).

NEW code (not lifted from monorepo-v0.14.1) — each fetcher wraps a parser
from ``tradewinds.weather`` plus ``tradewinds._internal._http.download_with_retry``
to produce a polite, cached, retry-aware historical download path.

Modules land here one per data source (see roadmap/sprint0.md Wave 3B):

- ``iem_cli`` — IEM CLI (NWS climate) settlement-grade highs/lows.
- ``iem_asos`` — IEM ASOS historical METAR (other lanes).
- ``awc`` — AWC live (no historical depth; sanity only).
- ``ghcnh`` — NCEI GHCNh hourly archives (other lanes).
"""

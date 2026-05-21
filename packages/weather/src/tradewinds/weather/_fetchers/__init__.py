"""Historical range fetchers for weather data sources.

Sprint 0 Day 1-2 (Lane F) — net-new code. Each fetcher downloads raw
upstream artifacts for a station-year (or station-range) and returns
the local file path(s). Parsing is handled separately by the sibling
parser modules (tradewinds.weather._awc, _iem, _ghcnh, _climate).

Modules:
- ``ghcnh`` — NCEI GHCNh per-year PSV downloader
- ``awc`` — historical AWC range fetcher (added by sibling wave)
- ``iem`` — historical IEM range fetcher (added by sibling wave)
- ``climate`` — NWS CLI range fetcher (added by sibling wave)
"""

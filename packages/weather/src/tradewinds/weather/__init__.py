"""tradewinds.weather — direct public-API access for AWC, IEM, GHCNh, NWS CLI.

Sprint 0 Day 1 (Lane V) lifts these PARSER modules from monorepo-v0.14.1/src/mostlyright/weather/:
- ``_awc`` — AWC METAR parser
- ``_iem`` — IEM METAR parser
- ``_climate`` — NWS CLI climate parser (Kalshi settlement source)
- ``_ghcnh`` — NCEI GHCNh parser
- ``_bounds`` — METAR QC bounds (impossible-value rejection)
- ``live`` — WeatherLive direct-API entry point (single-observation)
- ``forecasts`` — IEM MOS forecasts (deepened in Sprint 1)

Sprint 0 Day 1-2 (Lane F) ADDS these HISTORICAL FETCHER modules (net-new code, not lifted):
- ``_fetchers.awc`` — historical multi-day AWC range fetcher
- ``_fetchers.iem`` — historical IEM range fetcher
- ``_fetchers.ghcnh`` — historical GHCNh range fetcher
- ``_fetchers.climate`` — NWS CLI range fetcher

Sprint 0 Day 2 (Lane F) ADDS:
- ``observations.fetch(station, from_date, to_date)`` — fans out to AWC/IEM/GHCNh, applies observation LIVE_V1
- ``climate.fetch(station, from_date, to_date)`` — calls NWS CLI, applies climate LIVE_V1
- ``cache`` — local parquet cache with LST-aware current-month-skip

(See roadmap/sprint0.md for the full plan.)
"""

__version__ = "0.0.1"
__all__ = ["__version__"]

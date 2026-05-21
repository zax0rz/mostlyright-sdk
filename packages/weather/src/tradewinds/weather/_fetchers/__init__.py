"""HTTP fetcher modules for tradewinds.weather data sources.

Sprint 0 Wave 3B (Lane F, net-new code — NOT lifted):

- ``awc`` — AWC live METAR fetcher (last ~168 hours, no historical depth)
- ``iem`` — IEM ASOS historical METAR fetcher (Wave 3B-2, parallel agent)
- ``cli`` — NWS CLI settlement fetcher via IEM ``json/cli.py`` (Wave 3B-3, parallel)
- ``ghcnh`` — GHCNh archived METAR fetcher (Wave 3B-4, parallel)

Each fetcher returns RAW response dicts / strings. Callers compose with the
parsers in :mod:`tradewinds.weather` (``_awc``, ``_iem``, ``_climate``,
``_ghcnh``) to produce schema-valid observation / climate dicts.

Fetchers do NOT call the parsers directly — parser composition lives in
``tradewinds.weather.observations.fetch()`` (Wave 4) so the cache layer can
sit between raw bytes and parsed observations.
"""

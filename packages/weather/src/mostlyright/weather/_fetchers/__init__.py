"""HTTP fetcher modules for mostlyright.weather data sources.

Sprint 0 Wave 3B (Lane F, net-new code — NOT lifted from mostlyright==0.14.1):

- ``awc`` — AWC live METAR fetcher (last ~168 hours, no historical depth).
- ``iem_asos`` — IEM ASOS historical METAR (CSV) with monthly chunking + cache.
- ``iem_cli`` — NWS CLI settlement fetcher via IEM ``json/cli.py``. Year granularity.
- ``ghcnh`` — NOAA GHCNh historical PSV fetcher with annual cache.

Each fetcher returns either RAW response dicts (AWC) or local file paths
(IEM ASOS / IEM CLI / GHCNh after ``download_with_retry`` atomic write).
Callers compose with parsers in :mod:`mostlyright.weather` (``_awc``, ``_iem``,
``_climate``, ``_ghcnh``) to produce schema-valid observation / climate dicts.

Fetchers do NOT call the parsers directly — parser composition lives in
``mostlyright.weather.observations.fetch()`` (Wave 4) so the cache layer can
sit between raw bytes and parsed observations.
"""

from __future__ import annotations

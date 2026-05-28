"""Public StationInfo model and registry for SDK consumers.

Exposes metadata for every registry station. ``kalshi_traded`` is derived
from the registry's venue tags (``"kalshi" in venues``) rather than assumed
true for all entries — see ``mostlyright._internal._stations``. Distinct from
`ingest.stations.StationInfo` which exposes ingest-internal fields (ghcnh_id).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

# January reference date — DST is never in effect for US zones in January
_JAN_REF = datetime(2024, 1, 15, 12, 0)


def _utc_offset_hours(iana_tz: str) -> int:
    """Derive standard UTC offset (hours, integer) from an IANA timezone name.

    Uses a January reference date so DST is never in effect for US zones.
    Works for any IANA name without requiring _STATION_TZ lookup.

    Args:
        iana_tz: IANA timezone name (e.g. "America/New_York").

    Returns:
        Integer UTC offset in hours (e.g. -5 for Eastern Standard Time).
    """
    tz = ZoneInfo(iana_tz)
    aware = _JAN_REF.replace(tzinfo=tz)
    offset_td = aware.utcoffset()
    return int(offset_td.total_seconds() / 3600) if offset_td is not None else 0


@dataclass(frozen=True)
class StationInfo:
    """Public station metadata for SDK consumers.

    Attributes:
        code: 3-letter NWS station code (e.g. "NYC").
        name: Full station name (e.g. "Central Park, New York").
        icao: 4-letter ICAO identifier (e.g. "KNYC").
        timezone: IANA timezone name (e.g. "America/New_York").
        utc_offset_standard: Standard (non-DST) UTC offset in hours (e.g. -5).
        latitude: WGS84 latitude (decimal degrees).
        longitude: WGS84 longitude (decimal degrees, negative = west).
        kalshi_traded: True if this station has active Kalshi NHIGH/NLOW markets.
    """

    code: str
    name: str
    icao: str
    timezone: str
    utc_offset_standard: int
    latitude: float
    longitude: float
    kalshi_traded: bool = True

    def to_dict(self) -> dict[str, Any]:
        """Serialize to JSON-compatible dict."""
        return {
            "code": self.code,
            "name": self.name,
            "icao": self.icao,
            "timezone": self.timezone,
            "utc_offset_standard": self.utc_offset_standard,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "kalshi_traded": self.kalshi_traded,
        }


def _build_registry() -> dict[str, StationInfo]:
    """Build public StationInfo registry from the shared STATIONS dict.

    Imports from ``mostlyright._internal._stations`` (ships in the wheel) instead
    of ``ingest.stations``. The previous lazy-try pattern silently produced an
    empty registry on pip-installed systems because ``ingest/`` isn't in
    the wheel — see Vu PR #33 R2 P1.

    Derives utc_offset_standard directly from the IANA timezone name — NOT
    from snapshot._lst_offset(), which raises ValueError for unknown stations.
    """
    # TODO(wave3-stations-lift): swap to actual `mostlyright._internal._stations`
    # once a later wave lifts mostlyright._stations. Until then, calling this
    # function raises ImportError; module-level eager build below is guarded.
    from mostlyright._internal._stations import STATIONS as _SHARED_STATIONS

    registry: dict[str, StationInfo] = {}
    for code, s in _SHARED_STATIONS.items():
        registry[code] = StationInfo(
            code=code,
            name=s.name,
            icao=s.icao,
            timezone=s.tz,
            utc_offset_standard=_utc_offset_hours(s.tz),
            latitude=s.latitude,
            longitude=s.longitude,
            kalshi_traded="kalshi" in s.venues,
        )
    return registry


# TODO(wave3-stations-lift): the eager registry build below depends on
# `mostlyright._internal._stations`, which a later wave will lift. Guarded so
# the module remains importable in Wave 2 — `_STATION_REGISTRY` is `{}` until
# `_stations` lands. Byte-faithful equivalent: `_STATION_REGISTRY = _build_registry()`.
try:
    _STATION_REGISTRY: dict[str, StationInfo] = _build_registry()
except ImportError:
    _STATION_REGISTRY = {}

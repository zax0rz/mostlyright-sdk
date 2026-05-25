"""mostlyright.markets.catalog — prediction market contract specs.

Phase 2 (MARKETS-01..03) ships Kalshi NHIGH/NLOW settlement specs +
the 20-city station whitelist. Polymarket lands in Phase 3.3.
"""

from mostlyright.markets.catalog import kalshi_nhigh, kalshi_nlow
from mostlyright.markets.catalog.kalshi_stations import (
    KALSHI_SETTLEMENT_STATIONS,
    KNOWN_WRONG_STATIONS,
    StationCitation,
)

__all__ = [
    "KALSHI_SETTLEMENT_STATIONS",
    "KNOWN_WRONG_STATIONS",
    "StationCitation",
    "kalshi_nhigh",
    "kalshi_nlow",
]

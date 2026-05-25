"""DataAvailability and RangeInfo models for SDK consumers.

availability() answers: "What date ranges actually have data for station X?"
Agents use this before building training loops to avoid empty-result queries.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class RangeInfo:
    """Available date range for one data type.

    Attributes:
        earliest: ISO date string (YYYY-MM-DD) of first available record.
            None if no data exists.
        latest: ISO date string (YYYY-MM-DD) of last available record.
            None if no data exists.
        count: Total number of records. None if count is too expensive to compute.
        freshness_hours: Hours since latest record was ingested, relative to
            as_of. None if latest is None.
    """

    earliest: str | None
    latest: str | None
    count: int | None
    freshness_hours: float | None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to JSON-compatible dict."""
        return {
            "earliest": self.earliest,
            "latest": self.latest,
            "count": self.count,
            "freshness_hours": self.freshness_hours,
        }


@dataclass(frozen=True)
class DataAvailability:
    """Data availability summary for a station.

    Attributes:
        station: Normalized station code.
        as_of: UTC ISO 8601 string when this check was made.
        observations: Availability of METAR/SPECI hourly records.
        climate: Availability of NWS CLI daily records.
        forecast: Availability of forecast records. None if forecast parquet
            not present (sprint2/forecast-backfill not yet merged).
    """

    station: str
    as_of: str
    observations: RangeInfo
    climate: RangeInfo
    forecast: RangeInfo | None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to JSON-compatible dict."""
        return {
            "station": self.station,
            "as_of": self.as_of,
            "observations": self.observations.to_dict(),
            "climate": self.climate.to_dict(),
            "forecast": self.forecast.to_dict() if self.forecast else None,
        }

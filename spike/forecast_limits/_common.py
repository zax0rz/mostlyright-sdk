"""Shared helpers for forecast_limits probes.

Tiny convenience wrappers over ``spike.source_limits._common`` so each
probe script gets a ``recent_cycle_utc()`` + a ``Trial`` recipe shape
without duplicating the timing/percentile machinery.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from spike.source_limits._common import (
    RequestResult,
    SpikeResult,
    fan_out,
    percentile,
    render_markdown_row,
)

__all__ = [
    "RequestResult",
    "SpikeResult",
    "Trial",
    "fan_out",
    "percentile",
    "recent_cycle_utc",
    "render_markdown_row",
]


@dataclass(frozen=True)
class Trial:
    """One probe URL recipe.

    Attributes:
        label: Short tag for the markdown table row.
        description: Free-form note for human review.
        url: Full URL to GET (or HEAD/Range per the probe's fetch_fn).
        expected_bytes_floor: Sanity guard — probes that return fewer
            bytes than this are flagged as suspect (likely 404 HTML
            error pages misclassified as 2xx).
    """

    label: str
    description: str
    url: str
    expected_bytes_floor: int = 0


def recent_cycle_utc(*, hours_back: int = 6, frequency_hours: int = 6) -> datetime:
    """Return a recent UTC cycle snapped to a ``frequency_hours`` boundary.

    The default 6h-back + 6h-frequency picks the most-recently-published
    cycle for 4x/day models (GFS / ECMWF / GEFS). Hourly models (HRRR /
    NBM / RAP) can pass ``frequency_hours=1`` to get the most recent
    hourly cycle ~6h ago.
    """
    now = datetime.now(UTC) - timedelta(hours=hours_back)
    snapped_hour = (now.hour // frequency_hours) * frequency_hours
    return now.replace(hour=snapped_hour, minute=0, second=0, microsecond=0)

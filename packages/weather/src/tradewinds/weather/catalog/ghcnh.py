"""GHCNh catalog adapter (CATALOG-04).

Wraps :func:`tradewinds.weather._ghcnh.parse_ghcnh_row` into a class that
satisfies the ``WeatherAdapter`` Protocol and emits a canonical
``schema.observation.v1`` DataFrame with overlay columns.

GHCNh is the lowest-priority observation source in the v0.14.1 merge
policy (AWC=3 > IEM=2 > GHCNh=1). It carries QC-accepted hourly records
that are loud about their own quality via the ``_is_qc_accepted`` helper.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import ClassVar

import pandas as pd
from tradewinds.weather._ghcnh import parse_ghcnh_row

#: GHCNh publishes with a longer lag than ASOS/AWC (hour-summary archive).
#: Treat as known 6 hours after the observation hour ends.
GHCNH_LAG = timedelta(hours=6)


_OBSERVATION_PROJECTION: dict[str, str] = {
    "station_code": "station",
    "observed_at": "event_time",
    "observation_type": "observation_type",
    "temp_c": "temp_c",
    "dewpoint_c": "dew_point_c",
    "wind_speed_kt": "wind_speed_ms",
    "wind_dir_degrees": "wind_dir_deg",
    "wind_gust_kt": "wind_gust_ms",
    "sea_level_pressure_mb": "slp_hpa",
    "visibility_miles": "visibility_m",
    "sky_cover_1": "sky_cover_1",
    "sky_base_1_ft": "sky_base_1_m",
    "sky_cover_2": "sky_cover_2",
    "sky_base_2_ft": "sky_base_2_m",
    "sky_cover_3": "sky_cover_3",
    "sky_base_3_ft": "sky_base_3_m",
    "sky_cover_4": "sky_cover_4",
    "sky_base_4_ft": "sky_base_4_m",
    "raw_metar": "metar_raw",
}


class GHCNhAdapter:
    """GHCNh observation adapter."""

    SUPPORTED_SOURCES: ClassVar[list[str]] = ["ghcnh.archive"]

    def fetch_observations(
        self,
        source: str,
        station: str,
        from_date: str,
        to_date: str,
    ) -> pd.DataFrame:
        """Phase 3 Mode-2 entry point. v0.1: NotImplementedError."""
        raise NotImplementedError(
            "GHCNhAdapter.fetch_observations is the Phase 3 Mode-2 entry "
            "point. v0.1 callers should use tradewinds.research() "
            "(Mode 1 parity)."
        )

    @staticmethod
    def from_rows(
        rows: list[dict[str, object]],
        *,
        source: str = "ghcnh.archive",
        retrieved_at: datetime | None = None,
    ) -> pd.DataFrame:
        """Project GHCNh parser rows to a canonical observation DataFrame."""
        if retrieved_at is None:
            retrieved_at = datetime.now(UTC)
        if source not in GHCNhAdapter.SUPPORTED_SOURCES:
            raise ValueError(
                f"GHCNhAdapter does not support source={source!r}; "
                f"supported: {GHCNhAdapter.SUPPORTED_SOURCES}"
            )

        cols = [*list(_OBSERVATION_PROJECTION.values()), "source", "retrieved_at", "knowledge_time"]
        if not rows:
            df = pd.DataFrame({c: [] for c in cols})
        else:
            projected = [
                {dst: row.get(src) for src, dst in _OBSERVATION_PROJECTION.items()} for row in rows
            ]
            df = pd.DataFrame(projected)

        df["event_time"] = pd.to_datetime(df["event_time"], utc=True, errors="coerce")
        df["source"] = source
        df["retrieved_at"] = pd.Timestamp(retrieved_at).tz_convert("UTC")
        df["knowledge_time"] = df["event_time"] + GHCNH_LAG
        df.attrs["source"] = source
        df.attrs["retrieved_at"] = retrieved_at
        return df


__all__ = ["GHCNhAdapter", "parse_ghcnh_row"]


from tradewinds.weather.catalog import register_adapter  # noqa: E402

for _sid in GHCNhAdapter.SUPPORTED_SOURCES:
    register_adapter(_sid, GHCNhAdapter)

"""AWC catalog adapter (CATALOG-02).

Wraps :func:`tradewinds.weather._awc.awc_to_observation` into a class that
satisfies the ``WeatherAdapter`` Protocol and emits a canonical
``schema.observation.v1`` DataFrame with overlay columns.

Source IDs: ``"awc.live"`` (the only AWC source — historical archive is
not exposed via AWC's public endpoint as of Sept 2025 endpoint migration).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import ClassVar

import pandas as pd
from tradewinds.weather._awc import awc_to_observation

#: AWC observations are reported live; treat as known 5 minutes after valid
#: time (faster than IEM since AWC pushes to its API immediately).
AWC_LAG = timedelta(minutes=5)


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


class AWCAdapter:
    """AWC observation adapter."""

    SUPPORTED_SOURCES: ClassVar[list[str]] = ["awc.live"]

    def fetch_observations(
        self,
        source: str,
        station: str,
        from_date: str,
        to_date: str,
    ) -> pd.DataFrame:
        """Phase 3 Mode-2 entry point. v0.1: NotImplementedError."""
        raise NotImplementedError(
            "AWCAdapter.fetch_observations is the Phase 3 Mode-2 entry point. "
            "v0.1 callers should use tradewinds.research() (Mode 1 parity)."
        )

    @staticmethod
    def from_rows(
        rows: list[dict[str, object]],
        *,
        source: str = "awc.live",
        retrieved_at: datetime | None = None,
    ) -> pd.DataFrame:
        """Project AWC parser output rows to a canonical observation DataFrame.

        ``df.attrs["source"]`` is set to the supplied ``source``.
        """
        if retrieved_at is None:
            retrieved_at = datetime.now(UTC)
        if source not in AWCAdapter.SUPPORTED_SOURCES:
            raise ValueError(
                f"AWCAdapter does not support source={source!r}; "
                f"supported: {AWCAdapter.SUPPORTED_SOURCES}"
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
        df["knowledge_time"] = df["event_time"] + AWC_LAG
        df.attrs["source"] = source
        df.attrs["retrieved_at"] = retrieved_at
        return df


__all__ = ["AWCAdapter", "awc_to_observation"]


from tradewinds.weather.catalog import register_adapter  # noqa: E402

for _sid in AWCAdapter.SUPPORTED_SOURCES:
    register_adapter(_sid, AWCAdapter)

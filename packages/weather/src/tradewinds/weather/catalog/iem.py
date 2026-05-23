"""IEM catalog adapter (CATALOG-01).

Wraps :func:`tradewinds.weather._iem.iem_to_observation` (and ``parse_iem_file``)
into a class that satisfies the ``WeatherAdapter`` Protocol and emits a
canonical ``schema.observation.v1`` DataFrame with overlay columns.

Source IDs handled:
- ``"iem.archive"`` — historical CSV pulls (the v0.14.1 parity baseline)
- ``"iem.live"`` — same parser, current-month staging cache (no semantic
  difference at the parser level; the source ID drives Validator dispatch)

MOS forecast leg deferred to Phase 3 per the Phase 2 PLAN Open Q1 resolution.
``fetch_forecasts()`` raises :class:`NotImplementedError`.

Pitfall 8 (codex cross-ref): IEM's missing-data sentinel ``M`` is converted
to ``pd.NA`` by the underlying parser. The adapter preserves that — values
flowing through ``from_rows`` are not silently coerced.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import ClassVar

import pandas as pd
from tradewinds.weather._iem import iem_to_observation

#: Knowledge-time lag for METAR/SPECI reports. METAR is broadcast hourly;
#: SPECI is unscheduled. We treat both as "known" 15 minutes after the
#: observation valid time per design.md §"Definitions".
IEM_METAR_LAG = timedelta(minutes=15)

#: Per-row projection from parser output column → canonical schema column.
_OBSERVATION_PROJECTION: dict[str, str] = {
    "station_code": "station",
    "observed_at": "event_time",
    "observation_type": "observation_type",
    "temp_c": "temp_c",
    "dewpoint_c": "dew_point_c",
    "wind_speed_kt": "wind_speed_ms",  # caller converts; here we passthrough
    "wind_dir_degrees": "wind_dir_deg",
    "wind_gust_kt": "wind_gust_ms",
    "sea_level_pressure_mb": "slp_hpa",
    "visibility_miles": "visibility_m",
    # precip and sky_cover passthrough; precip_in column maps directly
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


class IEMAdapter:
    """IEM ASOS observation adapter."""

    SUPPORTED_SOURCES: ClassVar[list[str]] = ["iem.archive", "iem.live"]

    def fetch_observations(
        self,
        source: str,
        station: str,
        from_date: str,
        to_date: str,
    ) -> pd.DataFrame:
        """Fetch observations from IEM ASOS.

        v0.1.0: NOT YET WIRED. ``research()`` and ``snapshot`` continue to
        call ``_fetchers/iem_asos.py`` directly. The adapter contract is in
        place for Phase 3 Mode-2 dispatch.
        """
        raise NotImplementedError(
            "IEMAdapter.fetch_observations is the Phase 3 Mode-2 entry point. "
            "v0.1 callers should use tradewinds.research() (Mode 1 parity)."
        )

    def fetch_forecasts(
        self,
        source: str,
        station: str,
        from_date: str,
        to_date: str,
    ) -> pd.DataFrame:
        """MOS forecast leg — deferred to Phase 3 (Open Q1 resolution)."""
        raise NotImplementedError(
            "MOS forecasts deferred to Phase 3; see Open Q1 resolution in "
            "Phase 2 PLAN.md (parser confirmed absent in packages/weather/ "
            "on 2026-05-21)."
        )

    @staticmethod
    def from_rows(
        rows: list[dict[str, object]],
        *,
        source: str = "iem.archive",
        retrieved_at: datetime | None = None,
    ) -> pd.DataFrame:
        """Project parser output rows to a canonical observation DataFrame.

        The IEM parser (``iem_to_observation``) returns dicts with the
        legacy v0.14.1 column names (``station_code``, ``observed_at``,
        ``wind_speed_kt``, etc.). This method projects to ``schema.observation.v1``
        column names and adds overlay columns:
        ``source`` (per-row), ``retrieved_at``, ``knowledge_time``,
        ``event_time``.

        ``df.attrs["source"]`` is set to the supplied ``source`` so the
        Validator's source-identity invariant can be checked downstream.

        Args:
            rows: Parser output (each dict from :func:`iem_to_observation`).
            source: Source ID for ``df.attrs["source"]``. Default ``"iem.archive"``.
            retrieved_at: Pull wall-clock (UTC). Defaults to ``datetime.now(UTC)``.

        Returns:
            A DataFrame with canonical observation columns + overlay columns
            and ``df.attrs["source"] = source``.
        """
        if retrieved_at is None:
            retrieved_at = datetime.now(UTC)
        if source not in IEMAdapter.SUPPORTED_SOURCES:
            raise ValueError(
                f"IEMAdapter does not support source={source!r}; "
                f"supported: {IEMAdapter.SUPPORTED_SOURCES}"
            )

        if not rows:
            df = _empty_observation_df()
        else:
            projected: list[dict[str, object]] = []
            for row in rows:
                p: dict[str, object] = {}
                for src_key, dst_key in _OBSERVATION_PROJECTION.items():
                    p[dst_key] = row.get(src_key)
                projected.append(p)
            df = pd.DataFrame(projected)

        df["event_time"] = pd.to_datetime(df["event_time"], utc=True, errors="coerce")
        df["source"] = source
        df["retrieved_at"] = pd.Timestamp(retrieved_at).tz_convert("UTC")
        df["knowledge_time"] = df["event_time"] + IEM_METAR_LAG
        df.attrs["source"] = source
        df.attrs["retrieved_at"] = retrieved_at
        return df


def _empty_observation_df() -> pd.DataFrame:
    """Return an empty DataFrame with the canonical schema column set."""
    cols = [*list(_OBSERVATION_PROJECTION.values()), "source", "retrieved_at", "knowledge_time"]
    return pd.DataFrame({c: [] for c in cols})


# Re-export the row parser so adapter callers can keep using the v0.14.1
# entry point if they need raw dicts (e.g. parity tests).
__all__ = ["IEMAdapter", "iem_to_observation"]


# Self-register at module import — keyed by EVERY supported source ID.
from tradewinds.weather.catalog import register_adapter  # noqa: E402

for _sid in IEMAdapter.SUPPORTED_SOURCES:
    register_adapter(_sid, IEMAdapter)

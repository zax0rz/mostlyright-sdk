"""IEM catalog adapter (CATALOG-01).

Wraps :func:`mostlyright.weather._iem.iem_to_observation` (and ``parse_iem_file``)
into a class that satisfies the ``WeatherAdapter`` Protocol and emits a
canonical ``schema.observation.v1`` DataFrame with overlay columns + correct
SI units (m/s, metres, mm — see ``_obs_projection.PROJECTION_SPEC``).

Source IDs handled:
- ``"iem.archive"`` — historical CSV pulls (the v0.14.1 parity baseline)
- ``"iem.live"`` — same parser, current-month staging cache (no semantic
  difference at the parser level; the source ID drives Validator dispatch)

MOS forecast leg deferred to Phase 3 per the Phase 2 PLAN Open Q1 resolution.
``fetch_forecasts()`` raises :class:`NotImplementedError`.

Pitfall 8 (codex cross-ref): IEM's missing-data sentinel ``M`` is converted
to ``None`` by the underlying parser. The projection in
:mod:`mostlyright.weather.catalog._obs_projection` preserves ``None`` through
unit conversion.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import ClassVar

import pandas as pd
from mostlyright.weather._iem import iem_to_observation
from mostlyright.weather.catalog._obs_projection import (
    add_overlay_columns,
    empty_observation_df,
    project_row,
)

#: Knowledge-time lag for METAR/SPECI reports. METAR is broadcast hourly;
#: SPECI is unscheduled. We treat both as "known" 15 minutes after the
#: observation valid time per design.md §"Definitions".
IEM_METAR_LAG = timedelta(minutes=15)


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
            "v0.1 callers should use mostlyright.research() (Mode 1 parity)."
        )

    def fetch_forecasts(
        self,
        source: str,
        station: str,
        from_date: str,
        to_date: str,
    ) -> pd.DataFrame:
        """Fetch IEM MOS forecasts via :func:`fetch_iem_mos` (Phase 17 PLAN-08).

        Replaces the Phase-2 ``NotImplementedError`` stub. The default
        model is ``nbe`` (preferred for US stations); other supported
        models (gfs / lav / met / ecm) are reachable via direct
        :func:`fetch_iem_mos` calls.

        Args:
            source: ``"iem.archive"`` (historical) or ``"iem.live"``
                (v0.2 — currently raises NotImplementedError).
            station: ICAO code.
            from_date: ISO YYYY-MM-DD lower bound (inclusive).
            to_date: ISO YYYY-MM-DD upper bound (inclusive).

        Returns:
            DataFrame matching ``schema.forecast.iem_mos.v1``.

        Raises:
            ValueError: unknown ``source``.
            NotImplementedError: ``source="iem.live"``.
        """
        from mostlyright.weather._fetchers._iem_mos import fetch_iem_mos

        if source == "iem.archive":
            return fetch_iem_mos(station, from_date, to_date, model="nbe")
        if source == "iem.live":
            raise NotImplementedError(
                "iem.live MOS deferred to v0.2; use source='iem.archive'."
            )
        raise ValueError(
            f"source must be one of {{'iem.archive', 'iem.live'}}; got {source!r}"
        )

    @staticmethod
    def from_rows(
        rows: list[dict[str, object]],
        *,
        source: str = "iem.archive",
        retrieved_at: datetime | None = None,
    ) -> pd.DataFrame:
        """Project parser-output rows to a canonical observation DataFrame.

        Applies the shared canonical-units projection
        (:mod:`mostlyright.weather.catalog._obs_projection`): knots → m/s,
        miles → metres, feet → metres, inches → mm. ``None`` (IEM ``M``
        sentinel) passes through unchanged.
        """
        if retrieved_at is None:
            retrieved_at = datetime.now(UTC)
        if source not in IEMAdapter.SUPPORTED_SOURCES:
            raise ValueError(
                f"IEMAdapter does not support source={source!r}; "
                f"supported: {IEMAdapter.SUPPORTED_SOURCES}"
            )

        if not rows:
            df = empty_observation_df()
        else:
            df = pd.DataFrame([project_row(row) for row in rows])

        return add_overlay_columns(
            df, source=source, retrieved_at=retrieved_at, lag=pd.Timedelta(IEM_METAR_LAG)
        )


__all__ = ["IEMAdapter", "iem_to_observation"]


from mostlyright.weather.catalog import register_adapter  # noqa: E402

for _sid in IEMAdapter.SUPPORTED_SOURCES:
    register_adapter(_sid, IEMAdapter)

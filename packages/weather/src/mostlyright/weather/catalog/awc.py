"""AWC catalog adapter (CATALOG-02).

Wraps :func:`mostlyright.weather._awc.awc_to_observation` into a class that
satisfies the ``WeatherAdapter`` Protocol and emits a canonical
``schema.observation.v1`` DataFrame with overlay columns + correct SI units
(see :mod:`mostlyright.weather.catalog._obs_projection`).

Source IDs: ``"awc.live"`` (the only AWC source — historical archive is
not exposed via AWC's public endpoint as of Sept 2025 endpoint migration).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import ClassVar

import pandas as pd
from mostlyright.weather._awc import awc_to_observation
from mostlyright.weather.catalog._obs_projection import (
    add_overlay_columns,
    empty_observation_df,
    project_row,
)

#: AWC observations are reported live; treat as known 5 minutes after valid
#: time (faster than IEM since AWC pushes to its API immediately).
AWC_LAG = timedelta(minutes=5)


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
            "v0.1 callers should use mostlyright.research() (Mode 1 parity)."
        )

    @staticmethod
    def from_rows(
        rows: list[dict[str, object]],
        *,
        source: str = "awc.live",
        retrieved_at: datetime | None = None,
    ) -> pd.DataFrame:
        """Project AWC parser-output rows to a canonical observation DataFrame
        with SI units (knots → m/s, miles → metres, feet → metres, inches → mm).
        """
        if retrieved_at is None:
            retrieved_at = datetime.now(UTC)
        if source not in AWCAdapter.SUPPORTED_SOURCES:
            raise ValueError(
                f"AWCAdapter does not support source={source!r}; "
                f"supported: {AWCAdapter.SUPPORTED_SOURCES}"
            )

        if not rows:
            df = empty_observation_df()
        else:
            df = pd.DataFrame([project_row(row) for row in rows])

        return add_overlay_columns(
            df, source=source, retrieved_at=retrieved_at, lag=pd.Timedelta(AWC_LAG)
        )


__all__ = ["AWCAdapter", "awc_to_observation"]


from mostlyright.weather.catalog import register_adapter  # noqa: E402

for _sid in AWCAdapter.SUPPORTED_SOURCES:
    register_adapter(_sid, AWCAdapter)

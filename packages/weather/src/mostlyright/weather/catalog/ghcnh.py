"""GHCNh catalog adapter (CATALOG-04).

Wraps :func:`tradewinds.weather._ghcnh.parse_ghcnh_row` into a class that
satisfies the ``WeatherAdapter`` Protocol and emits a canonical
``schema.observation.v1`` DataFrame with overlay columns + correct SI units
(see :mod:`tradewinds.weather.catalog._obs_projection`).

GHCNh is the lowest-priority observation source in the v0.14.1 merge
policy (AWC=3 > IEM=2 > GHCNh=1). It carries QC-accepted hourly records
that are loud about their own quality via the ``_is_qc_accepted`` helper.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import ClassVar

import pandas as pd
from tradewinds.weather._ghcnh import parse_ghcnh_row
from tradewinds.weather.catalog._obs_projection import (
    add_overlay_columns,
    empty_observation_df,
    project_row,
)

#: GHCNh publishes with a longer lag than ASOS/AWC (hour-summary archive).
#: Treat as known 6 hours after the observation hour ends.
GHCNH_LAG = timedelta(hours=6)


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
        """Project GHCNh parser rows to a canonical observation DataFrame
        with SI units (knots → m/s, miles → metres, feet → metres, inches → mm).
        """
        if retrieved_at is None:
            retrieved_at = datetime.now(UTC)
        if source not in GHCNhAdapter.SUPPORTED_SOURCES:
            raise ValueError(
                f"GHCNhAdapter does not support source={source!r}; "
                f"supported: {GHCNhAdapter.SUPPORTED_SOURCES}"
            )

        if not rows:
            df = empty_observation_df()
        else:
            df = pd.DataFrame([project_row(row) for row in rows])

        return add_overlay_columns(
            df, source=source, retrieved_at=retrieved_at, lag=pd.Timedelta(GHCNH_LAG)
        )


__all__ = ["GHCNhAdapter", "parse_ghcnh_row"]


from tradewinds.weather.catalog import register_adapter  # noqa: E402

for _sid in GHCNhAdapter.SUPPORTED_SOURCES:
    register_adapter(_sid, GHCNhAdapter)

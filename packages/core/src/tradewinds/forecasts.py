"""Phase 3.2 — Multi-forecast live path (HRRR + GFS + NBM via NOAA BDP).

Phase 3.2 v0.1.0 scope: dispatch seam for the three NWP models tradewinds
ships in v0.1. Live-path only — historical NWP backfill + ECMWF Tier-2
defer to v0.2 (require hosted infrastructure that local-first can't host).

The actual byte-range + cfgrib decode + BallTree station extraction
lives in the ``[nwp]`` optional extra (Phase 3.2 wiring lands when
cfgrib + xarray + scikit-learn are installed via ``pip install
tradewinds-weather[nwp]``).

Surface:

- :func:`forecast_nwp(station, model, ...)` — dispatch entry point.
- :data:`SUPPORTED_NWP_MODELS` — frozen set of model IDs.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from tradewinds.core.exceptions import SourceUnavailableError

if TYPE_CHECKING:
    import pandas as pd


__all__ = ["SUPPORTED_NWP_MODELS", "forecast_nwp"]


#: NWP models tradewinds ships in v0.1.
SUPPORTED_NWP_MODELS: frozenset[str] = frozenset({"hrrr", "gfs", "nbm"})


def forecast_nwp(
    station: str,
    model: str,
    *,
    valid_time: str | None = None,
    cycle: str | None = None,
) -> pd.DataFrame:
    """Fetch an NWP forecast from NOAA Big Data Program direct-fetch.

    Args:
        station: ICAO code.
        model: One of ``"hrrr"``, ``"gfs"``, ``"nbm"``.
        valid_time: ISO 8601 forecast valid-time. Defaults to next cycle.
        cycle: Model cycle to read (``"00z"``, ``"06z"``, ``"12z"``, ``"18z"``).

    Returns:
        DataFrame conforming to ``schema.forecast.nwp.v1`` (lands in Phase
        3.2 — currently NotImplementedError).

    Raises:
        ValueError: ``model`` not in :data:`SUPPORTED_NWP_MODELS`.
        SourceUnavailableError: NWP optional extra not installed.
        NotImplementedError: Phase 3.2 fetch wiring lands when the
            ``[nwp]`` extra is finalized.
    """
    if model not in SUPPORTED_NWP_MODELS:
        raise ValueError(f"NWP model must be one of {sorted(SUPPORTED_NWP_MODELS)}; got {model!r}")

    try:
        import cfgrib  # noqa: F401
    except ImportError as exc:
        raise SourceUnavailableError(
            f"NWP forecast for model={model!r} requires the [nwp] optional "
            "extra. Install with: pip install tradewinds-weather[nwp]",
            source=f"nwp.{model}",
            retryable=False,
            underlying=str(exc),
        ) from None

    raise NotImplementedError(
        f"NWP forecast fetch for model={model!r} lands in Phase 3.2 alpha. "
        "The dispatch seam is in place; byte-range + cfgrib decode + "
        "BallTree station extraction wires in next."
    )

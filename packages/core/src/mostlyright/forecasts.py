"""Phase 3.2 — Multi-forecast live path (HRRR + GFS + NBM via NOAA BDP).

Public dispatch surface for mostlyright NWP forecasts. The real fetch
+ decode + station-extraction pipeline lives in
:mod:`mostlyright.weather.forecast_nwp` (shipped by the sibling
``mostlyright-weather`` distribution) so this module stays importable
without the ``[nwp]`` optional extra installed.

Live-path only in v0.1.0 — historical NWP backfill + ECMWF Tier-2
defer to v0.2 (both require hosted infrastructure local-first cannot
host). ECMWF Tier-2 model ids are reserved in
``schema.forecast_nwp.v1`` and raise
:class:`mostlyright.core.exceptions.NwpModelNotAvailableError` when
called.

Surface:

- :func:`forecast_nwp(station, model, ...)` — dispatch entry point.
- :data:`SUPPORTED_NWP_MODELS` — frozen set of model ids we ship.

The ``[nwp]`` optional extra
(``pip install mostlyright-weather[nwp]``) adds ``cfgrib``, ``xarray``,
and ``scikit-learn``. Calling :func:`forecast_nwp` without it raises
:class:`mostlyright.core.exceptions.SourceUnavailableError` carrying the
install hint.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from mostlyright.core.exceptions import (
    NwpModelNotAvailableError,
    SourceUnavailableError,
)
from mostlyright.core.schemas.forecast_nwp import NWP_MODEL_VALUES

if TYPE_CHECKING:
    from datetime import datetime

    import httpx
    import pandas as pd


__all__ = ["SUPPORTED_NWP_MODELS", "forecast_nwp"]


#: NWP models mostlyright ships in v0.1.0. ECMWF Tier-2 (4 models) is
#: predeclared in :data:`mostlyright.core.schemas.forecast_nwp.NWP_MODEL_VALUES`
#: and raises :class:`NwpModelNotAvailableError` when requested in v0.1.
SUPPORTED_NWP_MODELS: frozenset[str] = frozenset({"hrrr", "gfs", "nbm"})


def forecast_nwp(
    station: str | list[str],
    model: str,
    *,
    cycle: datetime | None = None,
    fxx: int = 1,
    mirror: str | None = None,
    client: httpx.Client | None = None,
) -> pd.DataFrame:
    """Fetch an NWP forecast from NOAA Big Data Program direct-fetch.

    Thin re-export of :func:`mostlyright.weather.forecast_nwp.forecast_nwp`
    so the canonical user-facing import path stays ``mostlyright.forecasts``
    (matching :func:`mostlyright.research`).

    Args:
        station: Single ICAO/NWS code or a list of them.
        model: One of :data:`SUPPORTED_NWP_MODELS` (``"hrrr"``, ``"gfs"``,
            ``"nbm"``). ECMWF Tier-2 values raise
            :class:`NwpModelNotAvailableError`.
        cycle: Model run cycle (UTC, tz-aware). Default: latest cycle
            whose run + ``fxx`` is at least 90 minutes in the past.
        fxx: Forecast hour ahead of ``cycle``. Default ``1``.
        mirror: Force a specific NOAA BDP mirror (``"aws_bdp"`` or
            ``"nomads"``). Default: try AWS then NOMADS.
        client: Reuse an ``httpx.Client`` for connection pooling.

    Returns:
        DataFrame matching ``schema.forecast_nwp.v1``.

    Raises:
        ValueError: ``model`` not in :data:`SUPPORTED_NWP_MODELS` and
            not a reserved ECMWF id; ``fxx`` is negative; ``cycle`` is
            naive; ``mirror`` outside the supported set.
        NwpModelNotAvailableError: ``model`` is a reserved ECMWF id.
        SourceUnavailableError: ``[nwp]`` optional extra not installed.
        NoLiveForNwpError: every wired NOAA BDP mirror failed.
        GribIntegrityError: a fetched record decoded with structural
            failures.
    """
    # Validate against the closed public enum first so callers get a
    # clean ValueError for typos before we try to import the weather
    # package (which may not have [nwp] installed).
    if model not in NWP_MODEL_VALUES and model not in SUPPORTED_NWP_MODELS:
        raise ValueError(
            f"NWP model must be one of {sorted(SUPPORTED_NWP_MODELS)} "
            f"(or reserved in {sorted(NWP_MODEL_VALUES)} for v0.2); "
            f"got {model!r}"
        )
    # Surface NwpModelNotAvailableError eagerly for reserved models so a
    # user without [nwp] still gets the right error (rather than
    # SourceUnavailableError about missing cfgrib).
    if model in NWP_MODEL_VALUES and model not in SUPPORTED_NWP_MODELS:
        raise NwpModelNotAvailableError(
            f"NWP model {model!r} is reserved in schema.forecast_nwp.v1 "
            "but not implemented in v0.1.0 (deferred to v0.2 — ECMWF "
            "Tier-2 requires hosted infrastructure).",
            model=model,
            available_in="v0.2",
        )

    try:
        from mostlyright.weather.forecast_nwp import (
            forecast_nwp as _impl,
        )
    except ImportError as exc:
        raise SourceUnavailableError(
            f"mostlyright.weather.forecast_nwp is not available: {exc}. "
            "Install mostlyright-weather: pip install mostlyright-weather",
            source=f"nwp.{model}",
            retryable=False,
            underlying=str(exc),
        ) from None

    return _impl(
        station,
        model,
        cycle=cycle,
        fxx=fxx,
        mirror=mirror,
        client=client,
    )

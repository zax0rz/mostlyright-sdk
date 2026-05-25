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
    DeprecatedModelWarning,
    NwpModelNotAvailableError,
    SourceUnavailableError,
)
from mostlyright.core.schemas.forecast_nwp import NWP_MODEL_VALUES

if TYPE_CHECKING:
    from datetime import datetime

    import httpx
    import pandas as pd


__all__ = ["SUPPORTED_NWP_MODELS", "forecast_nwp"]


#: NWP models that the public ``mostlyright.forecast_nwp`` surface
#: actually wires end-to-end. Phase 17 PLAN-03 expanded this from
#: ``{hrrr, gfs, nbm}`` to the full NCEP family (HRRRAK + GEFS + GDAS +
#: RAP + RRFS + RTMA + URMA + CFS) — 11 total.
#:
#: ECMWF Tier-2 (4 models), MSC Canadian family (5), and HAFS / legacy
#: NAM / HREF / HiResW (4) are predeclared in
#: :data:`mostlyright.core.schemas.forecast_nwp.NWP_MODEL_VALUES` and
#: raise :class:`NwpModelNotAvailableError` until their Wave-2 plans
#: (PLAN-04 / -05 / -06) land their fetch + decode wiring. The
#: internal SSRF allow-list :data:`mostlyright.weather._fetchers._nwp_archive.SUPPORTED_NWP_MODELS`
#: covers the full 24-name predeclared enum so URL construction is safe
#: when those plans flip the public-surface bit one model at a time.
SUPPORTED_NWP_MODELS: frozenset[str] = frozenset(
    {
        # v0.1.0 (Phase 3.2)
        "hrrr",
        "gfs",
        "nbm",
        # Phase 17 PLAN-04 ECMWF family
        "ecmwf_ifs_hres",
        "ecmwf_ifs_ens",
        "ecmwf_aifs_single",
        "ecmwf_aifs_ens",
        # Phase 17 PLAN-03 NCEP family
        "hrrrak",
        "gefs",
        "gdas",
        "rap",
        "rrfs",
        "rtma",
        "urma",
        "cfs",
        # Phase 17 PLAN-05 MSC Canadian family (24h Datamart retention guards
        # against historical use via HistoricalDepthError)
        "hrdps",
        "rdps",
        "gdps",
        "geps",
        "reps",
        # Phase 17 PLAN-06 HAFS + legacy (NAM/HREF/HiResW retire 2026-08-31)
        "hafs",
        "nam",
        "href",
        "hiresw",
    }
)


#: NWP models that have end-to-end fetch + decode wiring on the public
#: surface today. The :data:`SUPPORTED_NWP_MODELS` set above is the full
#: predeclared catalog (24 entries) — Phase 17 PLAN-03 wires NCEP,
#: PLAN-04/-05/-06 wire ECMWF/MSC/HAFS one plan at a time. Models in
#: ``SUPPORTED_NWP_MODELS`` but NOT in ``_WIRED_NWP_MODELS`` raise
#: :class:`NwpModelNotAvailableError` from :func:`forecast_nwp` so
#: callers see a clean error instead of falling through to a
#: half-wired fetch path. Update this set as later plans flip the
#: end-to-end wiring on for their model families.
_WIRED_NWP_MODELS: frozenset[str] = frozenset(
    {
        # v0.1.0 (Phase 3.2)
        "hrrr",
        "gfs",
        "nbm",
        # Phase 17 PLAN-03 NCEP family
        "hrrrak",
        "gefs",
        "gdas",
        "rap",
        "rrfs",
        "rtma",
        "urma",
        "cfs",
    }
)


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

    # Phase 17 PLAN-05: surface MSC Canadian family's HistoricalDepthError
    # at the public dispatch surface BEFORE the wired-models gate, so
    # callers get the right error class (retention-window, not "model
    # not available") even when the [nwp] extra isn't installed. PLAN-09
    # will wire the per-variable MSC fetcher in research integration.
    if model in {"hrdps", "rdps", "gdps", "geps", "reps"}:
        from datetime import UTC as _UTC
        from datetime import datetime as _dt

        from mostlyright.core.exceptions import HistoricalDepthError

        requested_cycle = (
            cycle
            if cycle is not None and getattr(cycle, "tzinfo", None) is not None
            else _dt.now(_UTC)
        )
        raise HistoricalDepthError(
            f"{model}: MSC Datamart has 24h retention; historical backfill "
            "not supported. Use a live cycle within the last 24 hours.",
            model=model,
            requested_cycle=requested_cycle,
            archive_depth=None,
        )

    # Phase 17 PLAN-06 / Wave-2 iter-1 review: legacy-model deprecation
    # warning. NAM / HREF / HiResW retire 2026-08-31 per NWS scn26-47.
    # Emit BEFORE the _WIRED_NWP_MODELS gate below so callers see the
    # deprecation signal even when the model isn't wired end-to-end yet
    # (the gate would otherwise raise NwpModelNotAvailableError first and
    # the warning would be unreachable). Stacklevel=2 so the warning
    # points at the user's call site.
    if model in {"nam", "href", "hiresw"}:
        import warnings as _warnings

        _warnings.warn(
            f"{model} retires 2026-08-31 per NWS scn26-47 (Herbie #540). "
            "Use HRRR / RAP / RRFS instead.",
            category=DeprecatedModelWarning,
            stacklevel=2,
        )

    # Surface NwpModelNotAvailableError eagerly for predeclared-but-not-
    # yet-wired models so a user calling, e.g., ``forecast_nwp("KNYC",
    # "ecmwf_ifs_hres")`` sees a clean reserved-model error rather than
    # falling through to a half-wired fetch path. ``SUPPORTED_NWP_MODELS``
    # is the full predeclared catalog (24 entries); ``_WIRED_NWP_MODELS``
    # is the strict subset with end-to-end fetch+decode wiring today.
    # PLAN-04 / -05 / -06 flip later families into the wired set.
    if model in SUPPORTED_NWP_MODELS and model not in _WIRED_NWP_MODELS:
        raise NwpModelNotAvailableError(
            f"NWP model {model!r} is reserved in schema.forecast_nwp.v1 "
            "but not yet wired end-to-end (Phase 17 PLAN-04 / -05 / -06 "
            "land ECMWF / MSC / HAFS / legacy fetch + decode).",
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

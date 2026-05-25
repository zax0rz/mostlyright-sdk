"""MSC Datamart per-variable fetcher (Phase 17 PLAN-05, FORECAST-13).

Canadian models (HRDPS / RDPS / GDPS / GEPS / REPS) at
``https://dd.weather.gc.ca``. Architectural distinction from NCEP / ECMWF:
MSC publishes ONE GRIB2 file per ``(variable, level, fxx)`` rather than
a single multi-variable GRIB2 + ``.idx`` companion. There is no byte-
range subsetting; callers fetch each variable file in full.

MSC Datamart has a **24-hour retention window** per CONTEXT decision 5.
Any historical-backfill attempt raises
:class:`mostlyright.core.exceptions.HistoricalDepthError` with
``archive_depth=None`` (no archive — purely live).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from mostlyright.core.exceptions import HistoricalDepthError

#: MSC models — Canadian Datamart family. Mirrors PLAN-05 of Phase 17.
MSC_MODELS: frozenset[str] = frozenset({"hrdps", "rdps", "gdps", "geps", "reps"})

#: MSC Datamart root URL.
_MSC_ROOT: str = "https://dd.weather.gc.ca"


@dataclass(frozen=True)
class MscFetchPlan:
    """Fetch plan for MSC models — one URL per variable; no ``.idx``.

    Attributes:
        model: One of :data:`MSC_MODELS`.
        cycle: Model run datetime (UTC-aware).
        fxx: Forecast hour.
        variable_urls: ``{canonical_column: full_grib2_url}`` for the
            variables the caller requested.
        member: Ensemble member for GEPS / REPS (e.g. ``"allmbrs"`` for
            GEPS raw layout, ``"m001"`` for REPS). ``None`` for the
            deterministic models (HRDPS / RDPS / GDPS).
    """

    model: str
    cycle: datetime
    fxx: int
    variable_urls: dict[str, str]
    member: str | None = None


def _hrdps_url(cycle: datetime, fxx: int, variable: str, level: str) -> str:
    return (
        f"{_MSC_ROOT}/{cycle:%Y%m%d}/WXO-DD/model_hrdps/continental/2.5km/"
        f"{cycle:%H}/{fxx:03d}/"
        f"{cycle:%Y%m%dT%H}Z_MSC_HRDPS_{variable}_{level}_RLatLon0.0225_PT{fxx:03d}H.grib2"
    )


def _rdps_url(cycle: datetime, fxx: int, variable: str, level: str) -> str:
    return (
        f"{_MSC_ROOT}/{cycle:%Y%m%d}/WXO-DD/model_rdps/10km/{cycle:%H}/{fxx:03d}/"
        f"{cycle:%Y%m%dT%H}Z_MSC_RDPS_{variable}_{level}_RLatLon0.09_PT{fxx:03d}H.grib2"
    )


def _gdps_url(cycle: datetime, fxx: int, variable: str, level: str) -> str:
    return (
        f"{_MSC_ROOT}/{cycle:%Y%m%d}/WXO-DD/model_gem_global/15km/grib2/lat_lon/"
        f"{cycle:%H}/{fxx:03d}/"
        f"CMC_glb_{variable}_{level}_latlon.15x.15_{cycle:%Y%m%d%H}_P{fxx:03d}.grib2"
    )


def _geps_url(
    cycle: datetime,
    fxx: int,
    variable: str,
    level: str,
    member: str = "allmbrs",
) -> str:
    if member in {"allmbrs", "raw"}:
        return (
            f"{_MSC_ROOT}/{cycle:%Y%m%d}/WXO-DD/ensemble/geps/grib2/raw/"
            f"{cycle:%H}/{fxx:03d}/"
            f"CMC_geps-raw_{variable}_{level}_latlon0p5x0p5_"
            f"{cycle:%Y%m%d%H}_P{fxx:03d}_allmbrs.grib2"
        )
    return (
        f"{_MSC_ROOT}/{cycle:%Y%m%d}/WXO-DD/ensemble/geps/grib2/products/"
        f"{cycle:%H}/{fxx:03d}/"
        f"CMC_geps-prod_{variable}_{level}_latlon0p5x0p5_"
        f"{cycle:%Y%m%d%H}_P{fxx:03d}_all-products.grib2"
    )


def _reps_url(
    cycle: datetime,
    fxx: int,
    variable: str,
    level: str,
    member: str = "m001",
) -> str:
    return (
        f"{_MSC_ROOT}/{cycle:%Y%m%d}/WXO-DD/ensemble/reps/10km/grib2/"
        f"{cycle:%H}/{fxx:03d}/"
        f"{cycle:%Y%m%dT%H}Z_MSC_REPS_{variable}_{level}_RLatLon0.09_PT{fxx:03d}H_{member}.grib2"
    )


_MSC_URL_BUILDERS = {
    "hrdps": _hrdps_url,
    "rdps": _rdps_url,
    "gdps": _gdps_url,
    "geps": _geps_url,
    "reps": _reps_url,
}


def build_msc_fetch_plan(
    *,
    model: str,
    cycle: datetime,
    fxx: int,
    variables: list[str],
    member: str | None = None,
) -> MscFetchPlan:
    """Build :class:`MscFetchPlan` with one URL per requested variable.

    Raises:
        ValueError: ``model`` not in :data:`MSC_MODELS`, ``cycle`` naive,
            or ``fxx`` negative.
        KeyError: A canonical variable name is not in the model's
            variable map (e.g. ``"wind_gust_ms"`` on RDPS).
    """
    if model not in MSC_MODELS:
        raise ValueError(f"model must be one of {sorted(MSC_MODELS)}; got {model!r}")
    if cycle.tzinfo is None or cycle.tzinfo.utcoffset(cycle) is None:
        raise ValueError(f"cycle must be timezone-aware (UTC); got naive {cycle!r}")
    if fxx < 0:
        raise ValueError(f"fxx must be non-negative; got {fxx}")

    # Late import to avoid the module-import cycle (_nwp_grids/__init__
    # imports per-model variable maps; this module is imported by
    # forecast_nwp.py which also pulls _nwp_grids).
    from ._nwp_grids import get_variable_map

    var_map = get_variable_map(model)
    builder = _MSC_URL_BUILDERS[model]
    urls: dict[str, str] = {}
    for canonical in variables:
        if canonical not in var_map:
            raise KeyError(
                f"variable {canonical!r} not in MSC {model} variable map; "
                f"available: {sorted(var_map.keys())}"
            )
        variable, level = var_map[canonical]
        if model in {"geps", "reps"}:
            effective_member = member or ("allmbrs" if model == "geps" else "m001")
            urls[canonical] = builder(cycle, fxx, variable, level, effective_member)
        else:
            urls[canonical] = builder(cycle, fxx, variable, level)

    return MscFetchPlan(
        model=model,
        cycle=cycle,
        fxx=fxx,
        variable_urls=urls,
        member=member if model in {"geps", "reps"} else None,
    )


def raise_msc_historical_depth(model: str, requested_cycle: datetime) -> None:
    """Raise :class:`HistoricalDepthError` for MSC historical attempts.

    MSC Datamart has a 24-hour retention window — no historical access.
    ``archive_depth`` is ``None`` (live-only signal).
    """
    raise HistoricalDepthError(
        f"{model}: MSC Datamart has 24h retention; historical backfill "
        "not supported. Use a live cycle within the last 24 hours.",
        model=model,
        requested_cycle=requested_cycle,
        archive_depth=None,
    )


__all__ = [
    "MSC_MODELS",
    "MscFetchPlan",
    "build_msc_fetch_plan",
    "raise_msc_historical_depth",
]

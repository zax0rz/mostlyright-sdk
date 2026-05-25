"""NOAA Big Data Program archive client — mirror URLs + byte-range fetcher.

Resolves model+cycle+forecast-hour to a GRIB2 URL (and its ``.idx``
companion) on a chosen mirror, fetches the ``.idx`` text, then issues
``Range: bytes=START-END`` requests against the GRIB2 file to materialise
only the records we need.

URL templates are hardcoded and gated by a closed mirror enum (SSRF
defense layer 1 + 2 per RESEARCH §"Pattern 5"). Caller-supplied model
keys are validated against :data:`SUPPORTED_NWP_MODELS`; mirror keys
against :data:`SUPPORTED_NWP_MIRRORS`. URL construction goes only through
``_build_grib2_url(model, mirror, ...)`` which returns ``None`` on any
unknown combination so the caller can fall back to the next mirror.

Pattern lifted from mostlyright ``sprint2/2r-impl-bundle:ingest/sources/
nwp_archive.py``. The lift keeps mostlyright's mirror-allowlist
discipline but drops the ledger/poller paths (which require hosted infra
mostlyright does not have — see ROADMAP Phase 3.2 "Out of scope").
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal

import httpx
from mostlyright._internal._http import HTTP_TIMEOUT

from ._url_transitions import GFS_V16_CUTOVER, LEGACY_MODELS_RETIRE

log = logging.getLogger(__name__)


#: NWP models mostlyright serves. Phase 17 Wave 2 expands from 3 to 24:
#: NCEP family (HRRR + GFS + NBM + PLAN-03's 8) + ECMWF family
#: (PLAN-04's 4) + MSC Canadian family (PLAN-05's 5) + NOMADS-only family
#: (PLAN-06's HAFS + NAM + HREF + HiResW). Final length 24, mirrors
#: :data:`mostlyright.core.schemas.forecast_nwp.NWP_MODEL_VALUES`.
SUPPORTED_NWP_MODELS: frozenset[str] = frozenset(
    {
        # v0.1.0
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
        # Phase 17 PLAN-05 MSC Canadian family
        "hrdps",
        "rdps",
        "gdps",
        "geps",
        "reps",
        # Phase 17 PLAN-06 NOMADS-only family (NAM/HREF/HiResW retire 2026-08-31)
        "hafs",
        "nam",
        "href",
        "hiresw",
    }
)


#: Mirrors that mostlyright is permitted to fetch from. AWS BDP first
#: (canonical NOAA-funded archive, public no-auth, stable); NOMADS second
#: (smaller but lands fresh cycles before AWS replicates). Phase 17 Wave 2
#: adds the 4 ECMWF Open Data mirrors and the MSC Datamart mirror.
SUPPORTED_NWP_MIRRORS: frozenset[str] = frozenset(
    {
        "aws_bdp",
        "nomads",
        # Phase 17 PLAN-04 ECMWF Open Data mirrors
        "ecmwf_gcp",
        "ecmwf_aws",
        "ecmwf_data_portal",
        "ecmwf_azure",
        # Phase 17 PLAN-05 MSC Datamart
        "msc",
    }
)


#: NOMADS concurrency cap per Herbie issue #371 IP-ban evidence
#: (Phase 17 FORECAST-09). Any code that fans out NOMADS-bound requests
#: MUST gate concurrency to ``<= NOMADS_CONCURRENCY_CAP``. AWS BDP and
#: other mirrors have no such cap.
NOMADS_CONCURRENCY_CAP: int = 4


#: Per-model mirror priority order (Phase 17 FORECAST-02). Replaces the
#: 3-model global :data:`DEFAULT_MIRROR_CHAIN` so Wave 2 model families
#: (HRRRAK, GEFS, RAP, ECMWF, MSC, HAFS, NAM, ...) can plug in their own
#: mirror chains without touching call-sites. Wave 2 extends this dict.
SOURCES_BY_MODEL: dict[str, tuple[str, ...]] = {
    # Phase 3.2
    "hrrr": ("aws_bdp", "nomads"),
    "gfs": ("aws_bdp", "nomads"),
    "nbm": ("aws_bdp", "nomads"),
    # Phase 17 PLAN-03 NCEP family
    "hrrrak": ("aws_bdp", "nomads"),
    "gefs": ("aws_bdp", "nomads"),
    "gdas": ("aws_bdp", "nomads"),
    "rap": ("aws_bdp", "nomads"),
    "rrfs": ("aws_bdp",),  # AWS-only
    "rtma": ("aws_bdp", "nomads"),
    "urma": ("aws_bdp", "nomads"),
    "cfs": ("aws_bdp", "nomads"),
    # Phase 17 PLAN-04 ECMWF family — GCP first per HERBIE-PATTERNS §2
    "ecmwf_ifs_hres": ("ecmwf_gcp", "ecmwf_aws", "ecmwf_data_portal", "ecmwf_azure"),
    "ecmwf_ifs_ens": ("ecmwf_gcp", "ecmwf_aws", "ecmwf_data_portal", "ecmwf_azure"),
    "ecmwf_aifs_single": ("ecmwf_gcp", "ecmwf_aws", "ecmwf_data_portal", "ecmwf_azure"),
    "ecmwf_aifs_ens": ("ecmwf_gcp", "ecmwf_aws", "ecmwf_data_portal", "ecmwf_azure"),
    # Phase 17 PLAN-05 MSC Canadian — MSC Datamart only
    "hrdps": ("msc",),
    "rdps": ("msc",),
    "gdps": ("msc",),
    "geps": ("msc",),
    "reps": ("msc",),
    # Phase 17 PLAN-06 NOMADS-only family (NAM has aws_bdp mirror)
    "hafs": ("nomads",),
    "nam": ("aws_bdp", "nomads"),
    "href": ("nomads",),
    "hiresw": ("nomads",),
}


#: Per-model ``.idx`` suffix fallback chain (Phase 17 FORECAST-03). NCEP
#: models publish a single ``.idx`` companion; ECMWF publishes ``.index``
#: (JSON-lines); HRRR also occasionally emits ``.grb2.inv`` / ``.inv``.
#: Callers try each suffix in order — first 2xx wins. MSC models are NOT
#: present — MSC uses per-variable files with no ``.idx`` companion (see
#: :mod:`._msc_archive`).
IDX_SUFFIX_BY_MODEL: dict[str, tuple[str, ...]] = {
    "hrrr": (".idx",),
    "gfs": (".idx",),
    "nbm": (".idx",),
    # NCEP family
    "hrrrak": (".idx",),
    "gefs": (".idx",),
    "gdas": (".idx",),
    "rap": (".idx",),
    "rrfs": (".idx",),
    "rtma": (".idx",),
    "urma": (".idx",),
    "cfs": (".idx",),
    # ECMWF family — eccodes JSON-lines
    "ecmwf_ifs_hres": (".index",),
    "ecmwf_ifs_ens": (".index",),
    "ecmwf_aifs_single": (".index",),
    "ecmwf_aifs_ens": (".index",),
    # NOMADS-only family
    "hafs": (".idx",),
    "nam": (".idx",),
    "href": (".idx",),
    "hiresw": (".idx",),
}


#: Per-model idx parser style (Phase 17 FORECAST-04). NCEP / HAFS / legacy
#: family use the wgrib2 colon-text format; ECMWF uses eccodes JSON-lines.
IDX_STYLE_BY_MODEL: dict[str, str] = {
    "hrrr": "wgrib2",
    "gfs": "wgrib2",
    "nbm": "wgrib2",
    # NCEP family
    "hrrrak": "wgrib2",
    "gefs": "wgrib2",
    "gdas": "wgrib2",
    "rap": "wgrib2",
    "rrfs": "wgrib2",
    "rtma": "wgrib2",
    "urma": "wgrib2",
    "cfs": "wgrib2",
    # ECMWF family
    "ecmwf_ifs_hres": "eccodes",
    "ecmwf_ifs_ens": "eccodes",
    "ecmwf_aifs_single": "eccodes",
    "ecmwf_aifs_ens": "eccodes",
    # NOMADS-only family
    "hafs": "wgrib2",
    "nam": "wgrib2",
    "href": "wgrib2",
    "hiresw": "wgrib2",
}


#: Per-model mirror base URLs. Each URL is the *root* (no trailing slash);
#: model-specific URL builders below append the cycle/forecast-hour suffix.
_ECMWF_MIRRORS: dict[str, str] = {
    "ecmwf_gcp": "https://storage.googleapis.com/ecmwf-open-data",
    "ecmwf_aws": "https://ecmwf-forecasts.s3.eu-central-1.amazonaws.com",
    "ecmwf_data_portal": "https://data.ecmwf.int/forecasts",
    "ecmwf_azure": "https://ai4edataeuwest.blob.core.windows.net/ecmwf",
}


_MIRROR_URLS_BY_MODEL: dict[str, dict[str, str]] = {
    "hrrr": {
        "aws_bdp": "https://noaa-hrrr-bdp-pds.s3.amazonaws.com",
        "nomads": "https://nomads.ncep.noaa.gov/pub/data/nccf/com/hrrr/prod",
    },
    "gfs": {
        "aws_bdp": "https://noaa-gfs-bdp-pds.s3.amazonaws.com",
        "nomads": "https://nomads.ncep.noaa.gov/pub/data/nccf/com/gfs/prod",
    },
    "nbm": {
        "aws_bdp": "https://noaa-nbm-pds.s3.amazonaws.com",
        "nomads": "https://nomads.ncep.noaa.gov/pub/data/nccf/com/blend/prod",
    },
    # Phase 17 PLAN-03 NCEP family
    "hrrrak": {
        "aws_bdp": "https://noaa-hrrr-bdp-pds.s3.amazonaws.com",
        "nomads": "https://nomads.ncep.noaa.gov/pub/data/nccf/com/hrrr/prod",
    },
    "gefs": {
        "aws_bdp": "https://noaa-gefs-pds.s3.amazonaws.com",
        "nomads": "https://nomads.ncep.noaa.gov/pub/data/nccf/com/gens/prod",
    },
    "gdas": {
        "aws_bdp": "https://noaa-gfs-bdp-pds.s3.amazonaws.com",
        "nomads": "https://nomads.ncep.noaa.gov/pub/data/nccf/com/gfs/prod",
    },
    "rap": {
        "aws_bdp": "https://noaa-rap-pds.s3.amazonaws.com",
        "nomads": "https://nomads.ncep.noaa.gov/pub/data/nccf/com/rap/prod",
    },
    "rrfs": {"aws_bdp": "https://noaa-rrfs-pds.s3.amazonaws.com"},
    "rtma": {
        "aws_bdp": "https://noaa-rtma-pds.s3.amazonaws.com",
        "nomads": "https://nomads.ncep.noaa.gov/pub/data/nccf/com/rtma/prod",
    },
    "urma": {
        "aws_bdp": "https://noaa-urma-pds.s3.amazonaws.com",
        "nomads": "https://nomads.ncep.noaa.gov/pub/data/nccf/com/urma/prod",
    },
    "cfs": {
        "aws_bdp": "https://noaa-cfs-pds.s3.amazonaws.com",
        "nomads": "https://nomads.ncep.noaa.gov/pub/data/nccf/com/cfs/prod",
    },
    # Phase 17 PLAN-04 ECMWF family — all 4 models share the same 4 mirrors
    "ecmwf_ifs_hres": _ECMWF_MIRRORS,
    "ecmwf_ifs_ens": _ECMWF_MIRRORS,
    "ecmwf_aifs_single": _ECMWF_MIRRORS,
    "ecmwf_aifs_ens": _ECMWF_MIRRORS,
    # Phase 17 PLAN-06 NOMADS-only family
    "hafs": {"nomads": "https://nomads.ncep.noaa.gov/pub/data/nccf/com/hafs/prod"},
    "nam": {
        "aws_bdp": "https://noaa-nam-pds.s3.amazonaws.com",
        "nomads": "https://nomads.ncep.noaa.gov/pub/data/nccf/com/nam/prod",
    },
    "href": {"nomads": "https://nomads.ncep.noaa.gov/pub/data/nccf/com/href/prod"},
    "hiresw": {"nomads": "https://nomads.ncep.noaa.gov/pub/data/nccf/com/hiresw/prod"},
    # MSC family (PLAN-05) — handled by _msc_archive.py per-variable URLs;
    # not in this dict. SOURCES_BY_MODEL["hrdps"] = ("msc",) gates dispatch.
}


#: Default mirror order tried when caller passes ``mirror=None``.
DEFAULT_MIRROR_CHAIN: tuple[str, ...] = ("aws_bdp", "nomads")


#: Date GFS reorganised paths to add ``/atmos/`` subdir (v16.0 cutover).
#: Pitfall 4 in 03.2-RESEARCH.md — pre-cutover GFS fetches must NOT include
#: ``/atmos/`` in the path. Aliased from :mod:`._url_transitions` so the
#: single source of truth lives in the transitions catalog (Phase 17
#: FORECAST-06). Stored tz-aware so the comparison against a caller-supplied
#: UTC-aware ``cycle`` does not raise a mixed-naive/aware ``TypeError``.
_GFS_V16_CUTOVER = GFS_V16_CUTOVER


@dataclass(frozen=True)
class NwpFetchPlan:
    """A resolved fetch plan: GRIB2 + ``.idx`` URLs for a (model, cycle, fxx).

    Attributes:
        model: One of :data:`SUPPORTED_NWP_MODELS`.
        mirror: One of :data:`SUPPORTED_NWP_MIRRORS`.
        cycle: Model run datetime (UTC, hour 00/06/12/18 for GFS; 00..23
            hourly for HRRR; 01..23 odd hours for NBM core cycles).
        fxx: Forecast hour (0 = analysis; positive = lead time hours).
        grib2_url: Full URL to the GRIB2 file.
        idx_url: Full URL to the ``.idx`` companion.
    """

    model: str
    mirror: str
    cycle: datetime
    fxx: int
    grib2_url: str
    idx_url: str


def _hrrr_path(cycle: datetime, fxx: int) -> str:
    """HRRR surface-field GRIB2 path relative to a mirror root.

    Returns the sfcf product (``wrfsfcf{fxx:02d}.grib2``) — surface 2-m
    temperature + dewpoint + winds + precip, which is what mostlyright
    extracts. Subhourly + pressure-level products are out of scope for
    v0.1.0.
    """
    return f"/hrrr.{cycle:%Y%m%d}/conus/hrrr.t{cycle:%H}z.wrfsfcf{fxx:02d}.grib2"


def _gfs_path(cycle: datetime, fxx: int) -> str:
    """GFS 0.25-degree GRIB2 path; handles pre-/post-v16.0 cutover.

    See Pitfall 4 in 03.2-RESEARCH.md for the date split.
    """
    if cycle >= _GFS_V16_CUTOVER:
        return f"/gfs.{cycle:%Y%m%d}/{cycle:%H}/atmos/gfs.t{cycle:%H}z.pgrb2.0p25.f{fxx:03d}"
    return f"/gfs.{cycle:%Y%m%d}/{cycle:%H}/gfs.t{cycle:%H}z.pgrb2.0p25.f{fxx:03d}"


def _nbm_path(cycle: datetime, fxx: int) -> str:
    """NBM CO product GRIB2 path (CONUS, 13-km grid).

    NBM v4 / v5 share the same path layout; the cutover only changed
    field availability (Pitfall 5).
    """
    return f"/blend.{cycle:%Y%m%d}/{cycle:%H}/core/blend.t{cycle:%H}z.core.f{fxx:03d}.co.grib2"


# ---------------------------------------------------------------------------
# Phase 17 PLAN-03: NCEP family URL builders
# ---------------------------------------------------------------------------


def _hrrrak_path(cycle: datetime, fxx: int) -> str:
    """HRRRAK (Alaska polar stereo) GRIB2 path."""
    return f"/hrrr.{cycle:%Y%m%d}/alaska/hrrr.t{cycle:%H}z.wrfsfcf{fxx:02d}.ak.grib2"


def _gefs_path(cycle: datetime, fxx: int, *, member: str = "c00") -> str:
    """GEFS — handles two URL-shape transitions (2018-07-27, 2020-09-23)."""
    from ._url_transitions import GEFS_FORMAT_2018, GEFS_FORMAT_2020

    if cycle >= GEFS_FORMAT_2020:
        return (
            f"/gefs.{cycle:%Y%m%d}/{cycle:%H}/atmos/pgrb2ap5/"
            f"ge{member}.t{cycle:%H}z.pgrb2a.0p50.f{fxx:03d}"
        )
    if cycle >= GEFS_FORMAT_2018:
        return f"/gefs.{cycle:%Y%m%d}/{cycle:%H}/pgrb2a/ge{member}.t{cycle:%H}z.pgrb2af{fxx:02d}"
    return f"/gefs.{cycle:%Y%m%d}/{cycle:%H}/ge{member}.t{cycle:%H}z.pgrb2af{fxx:03d}"


def _gdas_path(cycle: datetime, fxx: int) -> str:
    """GDAS — shares GFS bucket + post-v16 layout."""
    return f"/gdas.{cycle:%Y%m%d}/{cycle:%H}/atmos/gdas.t{cycle:%H}z.pgrb2.0p25.f{fxx:03d}"


def _rap_path(cycle: datetime, fxx: int, *, product: str = "awp130pgrb") -> str:
    """RAP (Rapid Refresh) 13-km CONUS."""
    return f"/rap.{cycle:%Y%m%d}/rap.t{cycle:%H}z.{product}f{fxx:02d}.grib2"


def _rrfs_path(
    cycle: datetime,
    fxx: int,
    *,
    product: str = "prslev",
    resolution: str = "conus_3km",
    domain: str = "conus",
) -> str:
    """RRFS deterministic CONUS."""
    return f"/rrfs_a/rrfs.{cycle:%Y%m%d}/{product}.{resolution}.f{fxx:03d}.{domain}.grib2"


def _rtma_path(cycle: datetime, fxx: int, *, product: str = "ges") -> str:
    """RTMA 2.5-km analysis."""
    return f"/rtma2p5.{cycle:%Y%m%d}/rtma2p5.t{cycle:%H}z.2dvar{product}_ndfd.grb2_wexp"


def _urma_path(cycle: datetime, fxx: int, *, product: str = "ges") -> str:
    """URMA 2.5-km analysis."""
    return f"/urma2p5.{cycle:%Y%m%d}/urma2p5.t{cycle:%H}z.2dvar{product}_ndfd.grb2_wexp"


def _cfs_path(
    cycle: datetime,
    fxx: int,
    *,
    member: str = "01",
    kind: str = "flxf",
    valid_date: str = "",
) -> str:
    """CFS 6-hourly product.

    ``valid_date`` is ``%Y%m%d`` of the valid time. If not supplied, it
    is derived from ``cycle + fxx hours`` so default ``forecast_nwp``
    calls (no per-model kwargs) produce a well-formed URL — per Phase 17
    Wave-2 iter-1 review: an empty ``valid_date`` would emit a malformed
    URL.
    """
    from datetime import timedelta

    if not valid_date:
        valid_date = (cycle + timedelta(hours=fxx)).strftime("%Y%m%d")
    return (
        f"/cfs.{cycle:%Y%m%d}/{cycle:%H}/6hrly_grib_{member}/"
        f"{kind}{valid_date}.{member}.{cycle:%Y%m%d%H}.grb2"
    )


# ---------------------------------------------------------------------------
# Phase 17 PLAN-04: ECMWF family URL builders (eccodes idx style)
# ---------------------------------------------------------------------------


def _ecmwf_ifs_path(
    cycle: datetime,
    fxx: int,
    *,
    product: str = "oper",
    ftype: str = "fc",
) -> str:
    """ECMWF IFS HRES + ENS — honors path+resolution date transitions."""
    from ._url_transitions import (
        ECMWF_IFS_PATH_TRANSITION,
        ECMWF_IFS_RESOLUTION_TRANSITION,
    )

    resolution = "0p25" if cycle >= ECMWF_IFS_RESOLUTION_TRANSITION else "0p4-beta"
    filename = f"{cycle:%Y%m%d%H%M%S}-{fxx}h-{product}-{ftype}.grib2"
    if cycle >= ECMWF_IFS_PATH_TRANSITION:
        return f"/{cycle:%Y%m%d}/{cycle:%H}z/ifs/{resolution}/{product}/{filename}"
    return f"/{cycle:%Y%m%d}/{cycle:%H}z/{resolution}/{product}/{filename}"


def _ecmwf_aifs_path(
    cycle: datetime,
    fxx: int,
    *,
    product: str = "oper",
    ftype: str = "fc",
) -> str:
    """ECMWF AIFS single — 3 phase transitions (pre / experimental / operational)."""
    from ._url_transitions import (
        ECMWF_AIFS_EXPERIMENTAL_START,
        ECMWF_AIFS_OPERATIONAL_START,
    )

    filename = f"{cycle:%Y%m%d%H%M%S}-{fxx}h-{product}-{ftype}.grib2"
    if cycle >= ECMWF_AIFS_OPERATIONAL_START:
        return f"/{cycle:%Y%m%d}/{cycle:%H}z/aifs-single/0p25/{product}/{filename}"
    if cycle >= ECMWF_AIFS_EXPERIMENTAL_START:
        return f"/{cycle:%Y%m%d}/{cycle:%H}z/aifs-single/0p25/experimental/{product}/{filename}"
    return f"/{cycle:%Y%m%d}/{cycle:%H}z/aifs/0p25/{product}/{filename}"


def _ecmwf_aifs_ens_path(
    cycle: datetime,
    fxx: int,
    *,
    product: str = "enfo",
    ftype: str = "ef",
) -> str:
    """ECMWF AIFS ENS — always /aifs-ens/ path."""
    filename = f"{cycle:%Y%m%d%H%M%S}-{fxx}h-{product}-{ftype}.grib2"
    return f"/{cycle:%Y%m%d}/{cycle:%H}z/aifs-ens/0p25/{product}/{filename}"


# ---------------------------------------------------------------------------
# Phase 17 PLAN-06: HAFS + legacy URL builders
# ---------------------------------------------------------------------------


def _hafs_path(
    cycle: datetime,
    fxx: int,
    *,
    storm: str = "",
    flavor: str = "a",
    product: str = "storm.atm",
) -> str:
    """HAFS path. ``storm`` is resolved via :mod:`._hafs_storms.resolve_storm`."""
    return (
        f"/hfs{flavor}.{cycle:%Y%m%d}/{cycle:%H}/"
        f"{storm}.{cycle:%Y%m%d%H}.hfs{flavor}.{product}.f{fxx:03d}.grb2"
    )


def _nam_path(cycle: datetime, fxx: int, *, product: str = "conusnest.hiresf") -> str:
    """NAM path (retiring 2026-08-31 per NWS scn26-47)."""
    return f"/nam.{cycle:%Y%m%d}/nam.t{cycle:%H}z.{product}{fxx:02d}.tm00.grib2"


def _href_path(
    cycle: datetime,
    fxx: int,
    *,
    domain: str = "conus",
    product: str = "mean",
) -> str:
    """HREF path (NOMADS-only; retiring 2026-08-31)."""
    return f"/href.{cycle:%Y%m%d}/ensprod/href.t{cycle:%H}z.{domain}.{product}.f{fxx:02d}.grib2"


def _hiresw_path(
    cycle: datetime,
    fxx: int,
    *,
    product: str = "arw_2p5km",
    domain: str = "conus",
    member: str = "",
) -> str:
    """HiResW path (NOMADS-only; retiring 2026-08-31)."""
    return f"/hiresw.{cycle:%Y%m%d}/hiresw.t{cycle:%H}z.{product}.f{fxx:02d}.{domain}{member}.grib2"


_PATH_BUILDERS = {
    "hrrr": _hrrr_path,
    "gfs": _gfs_path,
    "nbm": _nbm_path,
    # PLAN-03 NCEP family
    "hrrrak": _hrrrak_path,
    "gefs": _gefs_path,
    "gdas": _gdas_path,
    "rap": _rap_path,
    "rrfs": _rrfs_path,
    "rtma": _rtma_path,
    "urma": _urma_path,
    "cfs": _cfs_path,
    # PLAN-04 ECMWF family
    "ecmwf_ifs_hres": _ecmwf_ifs_path,
    "ecmwf_ifs_ens": _ecmwf_ifs_path,
    "ecmwf_aifs_single": _ecmwf_aifs_path,
    "ecmwf_aifs_ens": _ecmwf_aifs_ens_path,
    # PLAN-06 HAFS + legacy
    "hafs": _hafs_path,
    "nam": _nam_path,
    "href": _href_path,
    "hiresw": _hiresw_path,
    # MSC family (PLAN-05) has per-variable URLs — handled in _msc_archive.py,
    # not via _PATH_BUILDERS. SOURCES_BY_MODEL["hrdps"] = ("msc",) gates dispatch.
}


def _build_grib2_url(
    model: str, mirror: str, cycle: datetime, fxx: int, **per_model_kwargs: Any
) -> str | None:
    """Return the GRIB2 URL for ``(model, mirror, cycle, fxx)`` or ``None``.

    Returns ``None`` if either ``model`` or ``mirror`` is unsupported so
    the caller can transparently try the next mirror in the chain.
    Per-model kwargs (``member`` / ``product`` / ``storm`` / ``flavor`` /
    ``domain`` / ``resolution`` / ``valid_date`` / ``kind`` / ``ftype``)
    are threaded to the model's path builder.
    """
    if model not in SUPPORTED_NWP_MODELS or mirror not in SUPPORTED_NWP_MIRRORS:
        return None
    if model not in _MIRROR_URLS_BY_MODEL:
        return None
    root = _MIRROR_URLS_BY_MODEL[model].get(mirror)
    if root is None:
        return None
    path = _PATH_BUILDERS[model](cycle, fxx, **per_model_kwargs)
    return f"{root}{path}"


def build_fetch_plan(
    *,
    model: str,
    mirror: str,
    cycle: datetime,
    fxx: int,
    **per_model_kwargs: Any,
) -> NwpFetchPlan:
    """Resolve a single (model, mirror, cycle, fxx) to a ``NwpFetchPlan``.

    Per-model keyword arguments (``member`` / ``product`` / ``storm`` /
    ``flavor`` / ``domain`` / ``resolution`` / ``valid_date`` / ``kind`` /
    ``ftype``) are forwarded to the model-specific path builder so Phase 17
    Wave 2 callers can disambiguate GEFS ensemble members, ECMWF products,
    HAFS storms, NAM nest domains, etc.

    Raises:
        ValueError: ``model`` or ``mirror`` not in the supported enums,
            ``fxx`` negative, or ``cycle`` naive.
        mostlyright.core.exceptions.NwpModelRetiredError: NAM / HREF /
            HiResW cycle on or after ``LEGACY_MODELS_RETIRE``
            (2026-08-31) per NWS scn26-47.
    """
    if model not in SUPPORTED_NWP_MODELS:
        raise ValueError(f"model must be one of {sorted(SUPPORTED_NWP_MODELS)}; got {model!r}")
    if mirror not in SUPPORTED_NWP_MIRRORS:
        raise ValueError(f"mirror must be one of {sorted(SUPPORTED_NWP_MIRRORS)}; got {mirror!r}")
    if fxx < 0:
        raise ValueError(f"fxx must be non-negative; got {fxx}")
    # Phase 17 Wave-2 iter-1 review: RTMA / URMA are analysis products
    # (single time, no forecast hour). The URL builders ignore ``fxx`` and
    # always return the analysis file, so a nonzero ``fxx`` would silently
    # shift the row builder's ``valid_at`` by ``fxx`` hours while the
    # GRIB bytes are still the analysis cycle. Reject loud here so the
    # caller sees the mistake instead of getting mislabeled rows.
    if model in {"rtma", "urma"} and fxx != 0:
        raise ValueError(
            f"{model} is an analysis product (no forecast hour); fxx must be 0, got {fxx}"
        )
    if cycle.tzinfo is None or cycle.tzinfo.utcoffset(cycle) is None:
        raise ValueError(f"cycle must be timezone-aware (UTC); got naive {cycle!r}")
    # Normalize to UTC. NOAA paths use the UTC cycle hour (t12z etc.);
    # a caller passing 2026-05-23 14:00+02:00 means the 12z cycle, NOT
    # a (non-existent) t14z cycle. Without normalization the path
    # builder would format the local hour into the URL and silently
    # fetch the wrong cycle (Codex iter-1 P2).
    cycle_utc = cycle.astimezone(UTC)
    # Phase 17 PLAN-06: legacy-model retirement guard. NAM / HREF / HiResW
    # retire 2026-08-31 per NWS scn26-47 (Herbie #540). Aborts loud so
    # backtests don't silently produce empty forecasts post-retirement.
    if model in {"nam", "href", "hiresw"} and cycle_utc >= LEGACY_MODELS_RETIRE:
        from mostlyright.core.exceptions import NwpModelRetiredError

        raise NwpModelRetiredError(
            f"{model} retired on {LEGACY_MODELS_RETIRE.date()} per NWS scn26-47. "
            "Use HRRR / RAP / RRFS instead.",
            model=model,
            retired_on=LEGACY_MODELS_RETIRE,
            replacement_suggestions=["hrrr", "rap", "rrfs"],
        )
    grib2_url = _build_grib2_url(model, mirror, cycle_utc, fxx, **per_model_kwargs)
    if grib2_url is None:  # pragma: no cover — guarded above
        raise ValueError(f"could not build URL for model={model!r} mirror={mirror!r}")
    # Phase 17 FORECAST-03: idx suffix comes from the per-model registry so
    # ECMWF (".index") and other models can plug in without code changes
    # here. Wave 1 ships ".idx" for all NCEP models — byte-identical to the
    # pre-refactor hardcoded suffix. The Wave 2 fallback-chain (try each
    # suffix in order; first 2xx wins) lands when ECMWF goes live.
    idx_suffix = IDX_SUFFIX_BY_MODEL.get(model, (".idx",))[0]
    return NwpFetchPlan(
        model=model,
        mirror=mirror,
        cycle=cycle_utc,
        fxx=fxx,
        grib2_url=grib2_url,
        idx_url=grib2_url + idx_suffix,
    )


def fetch_idx_text(
    plan: NwpFetchPlan,
    *,
    client: httpx.Client | None = None,
    timeout: float = HTTP_TIMEOUT,
) -> str:
    """Fetch the ``.idx`` text companion for a plan.

    Args:
        plan: The fetch plan whose ``.idx`` to retrieve.
        client: Optional ``httpx.Client`` for connection reuse. If
            ``None``, a fresh client is constructed (and closed) per call.
        timeout: Per-request timeout in seconds.

    Returns:
        Decoded ``.idx`` body (UTF-8). Empty string only if upstream
        returns 200 OK with an empty body.

    Raises:
        httpx.HTTPStatusError: Non-2xx response.
        httpx.RequestError: Connection / DNS / TLS failure.
    """
    if client is None:
        with httpx.Client(timeout=timeout) as fresh:
            response = fresh.get(plan.idx_url)
    else:
        response = client.get(plan.idx_url, timeout=timeout)
    response.raise_for_status()
    return response.text


def fetch_grib2_content_length(
    plan: NwpFetchPlan,
    *,
    client: httpx.Client | None = None,
    timeout: float = HTTP_TIMEOUT,
) -> int:
    """One-shot HEAD on the GRIB2 URL — returns ``Content-Length`` as int.

    Used to resolve the byte-end for the LAST record (Pitfall 1 from
    03.2-RESEARCH.md). The result is meant to be cached per
    ``(model_run, mirror)`` by callers — the call here is intentionally
    single-shot and not retried.

    Raises:
        httpx.HTTPStatusError: Non-2xx response.
        ValueError: ``Content-Length`` header missing or non-integer.
    """
    if client is None:
        with httpx.Client(timeout=timeout) as fresh:
            response = fresh.head(plan.grib2_url)
    else:
        response = client.head(plan.grib2_url, timeout=timeout)
    response.raise_for_status()
    cl = response.headers.get("content-length")
    if cl is None:
        raise ValueError(f"HEAD {plan.grib2_url} returned 2xx but no Content-Length header")
    try:
        return int(cl)
    except ValueError as exc:
        raise ValueError(f"HEAD {plan.grib2_url} Content-Length not integer: {cl!r}") from exc


def fetch_byte_range(
    plan: NwpFetchPlan,
    *,
    start: int,
    end: int,
    client: httpx.Client | None = None,
    timeout: float = HTTP_TIMEOUT,
) -> bytes:
    """Fetch ``bytes={start}-{end}`` of the GRIB2 file at ``plan.grib2_url``.

    Both endpoints are inclusive per the HTTP ``Range`` spec (RFC 7233 §2.1).

    Args:
        plan: Fetch plan whose GRIB2 to slice.
        start: Inclusive start byte (>= 0).
        end: Inclusive end byte (>= start).
        client: Optional ``httpx.Client`` for connection reuse.
        timeout: Per-request timeout in seconds.

    Returns:
        Raw bytes of the requested range. S3 honours ``Range`` requests
        with HTTP 206 Partial Content.

    Raises:
        ValueError: ``start < 0`` or ``end < start``.
        httpx.HTTPStatusError: Server returned non-2xx (S3 returns 416 for
            unsatisfiable ranges; 5xx for transient backend failures).
        RuntimeError: Server returned 200 OK with the full file body
            instead of 206 Partial Content — Phase 17 FORECAST-05 /
            Herbie core.py:1108-1115. Some mirrors (misconfigured S3-
            compatible endpoints) silently ignore the ``Range:`` header;
            this guard aborts loud so disk usage doesn't balloon 1000x.
            See :func:`assert_range_honored`.
    """
    if start < 0:
        raise ValueError(f"start must be >= 0 (got {start})")
    if end < start:
        raise ValueError(f"end must be >= start (got start={start}, end={end})")
    headers = {"Range": f"bytes={start}-{end}"}
    # Stream so we can inspect the status before reading the body — a 200 OK
    # full-body response could be hundreds of MB; we abort before reading.
    if client is None:
        with (
            httpx.Client(timeout=timeout) as fresh,
            fresh.stream("GET", plan.grib2_url, headers=headers) as response,
        ):
            response.raise_for_status()
            assert_range_honored(response, url=plan.grib2_url)
            return response.read()
    with client.stream("GET", plan.grib2_url, headers=headers, timeout=timeout) as response:
        response.raise_for_status()
        assert_range_honored(response, url=plan.grib2_url)
        return response.read()


MirrorKey = Literal["aws_bdp", "nomads"]


def assert_range_honored(response: httpx.Response, *, url: str = "") -> None:
    """Raise ``RuntimeError`` if a byte-range request was not honored.

    Phase 17 FORECAST-05 / Herbie ``core.py:1108-1115`` guard. A compliant
    server returns ``206 Partial Content`` for a ``Range:`` request. Some
    mirrors (proxies, misconfigured S3-compatible endpoints, ECMWF Azure
    sometimes) silently return ``200 OK`` with the FULL file body — which
    can balloon disk usage 1000x for a quant expecting a small byte slice.

    Call this immediately after :func:`fetch_byte_range` (or any other
    ``Range:`` request) before reading the body, and abort hard on mismatch.

    Args:
        response: The :class:`httpx.Response` from a ``Range:`` request.
        url: Optional URL for the error message (defaults to the
            response's recorded URL — useful when the caller wants to
            log the original request URL rather than any post-redirect
            URL the response carries).

    Raises:
        RuntimeError: ``response.status_code != 206``.
    """
    if response.status_code != 206:
        raise RuntimeError(
            f"Range request not honored (status={response.status_code}) "
            f"for {url or response.url}. Server returned full file instead "
            "of partial content; aborting. See Phase 17 FORECAST-05."
        )


__all__ = [
    "DEFAULT_MIRROR_CHAIN",
    "IDX_STYLE_BY_MODEL",
    "IDX_SUFFIX_BY_MODEL",
    "NOMADS_CONCURRENCY_CAP",
    "SOURCES_BY_MODEL",
    "SUPPORTED_NWP_MIRRORS",
    "SUPPORTED_NWP_MODELS",
    "MirrorKey",
    "NwpFetchPlan",
    "assert_range_honored",
    "build_fetch_plan",
    "fetch_byte_range",
    "fetch_grib2_content_length",
    "fetch_idx_text",
]

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
from typing import Literal

import httpx
from mostlyright._internal._http import HTTP_TIMEOUT

from ._url_transitions import GFS_V16_CUTOVER

log = logging.getLogger(__name__)


#: NWP models mostlyright ships in v0.1.0. ECMWF Tier-2 (4 models) is
#: predeclared in the public schema enum but raises
#: :class:`mostlyright.core.exceptions.NwpModelNotAvailableError` until
#: v0.2 lands hosted ECMWF support. Phase 17 Wave 2 extends this set with
#: NCEP / ECMWF / MSC / NOMADS-only families.
SUPPORTED_NWP_MODELS: frozenset[str] = frozenset({"hrrr", "gfs", "nbm"})


#: Mirrors that mostlyright is permitted to fetch from. AWS BDP first
#: (canonical NOAA-funded archive, public no-auth, stable); NOMADS second
#: (smaller but lands fresh cycles before AWS replicates).
SUPPORTED_NWP_MIRRORS: frozenset[str] = frozenset({"aws_bdp", "nomads"})


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
    "hrrr": ("aws_bdp", "nomads"),
    "gfs": ("aws_bdp", "nomads"),
    "nbm": ("aws_bdp", "nomads"),
}


#: Per-model ``.idx`` suffix fallback chain (Phase 17 FORECAST-03). NCEP
#: models publish a single ``.idx`` companion; ECMWF publishes ``.index``
#: (JSON-lines); HRRR also occasionally emits ``.grb2.inv`` / ``.inv``.
#: Callers try each suffix in order — first 2xx wins.
IDX_SUFFIX_BY_MODEL: dict[str, tuple[str, ...]] = {
    "hrrr": (".idx",),
    "gfs": (".idx",),
    "nbm": (".idx",),
}


#: Per-model idx parser style (Phase 17 FORECAST-04). NCEP family uses
#: the wgrib2 colon-text format parsed by :func:`._nwp_idx.parse_idx`;
#: ECMWF uses the eccodes JSON-lines format (parser body lands in PLAN-04).
IDX_STYLE_BY_MODEL: dict[str, str] = {
    "hrrr": "wgrib2",
    "gfs": "wgrib2",
    "nbm": "wgrib2",
}


#: Per-model mirror base URLs. Each URL is the *root* (no trailing slash);
#: model-specific URL builders below append the cycle/forecast-hour suffix.
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


_PATH_BUILDERS = {
    "hrrr": _hrrr_path,
    "gfs": _gfs_path,
    "nbm": _nbm_path,
}


def _build_grib2_url(model: str, mirror: str, cycle: datetime, fxx: int) -> str | None:
    """Return the GRIB2 URL for ``(model, mirror, cycle, fxx)`` or ``None``.

    Returns ``None`` if either ``model`` or ``mirror`` is unsupported so
    the caller can transparently try the next mirror in the chain.
    """
    if model not in SUPPORTED_NWP_MODELS or mirror not in SUPPORTED_NWP_MIRRORS:
        return None
    root = _MIRROR_URLS_BY_MODEL[model].get(mirror)
    if root is None:
        return None
    path = _PATH_BUILDERS[model](cycle, fxx)
    return f"{root}{path}"


def build_fetch_plan(
    *,
    model: str,
    mirror: str,
    cycle: datetime,
    fxx: int,
) -> NwpFetchPlan:
    """Resolve a single (model, mirror, cycle, fxx) to a ``NwpFetchPlan``.

    Raises:
        ValueError: ``model`` or ``mirror`` not in the supported enums,
            or ``fxx`` is negative, or ``cycle`` is naive (not UTC-aware).
    """
    if model not in SUPPORTED_NWP_MODELS:
        raise ValueError(f"model must be one of {sorted(SUPPORTED_NWP_MODELS)}; got {model!r}")
    if mirror not in SUPPORTED_NWP_MIRRORS:
        raise ValueError(f"mirror must be one of {sorted(SUPPORTED_NWP_MIRRORS)}; got {mirror!r}")
    if fxx < 0:
        raise ValueError(f"fxx must be non-negative; got {fxx}")
    if cycle.tzinfo is None or cycle.tzinfo.utcoffset(cycle) is None:
        raise ValueError(f"cycle must be timezone-aware (UTC); got naive {cycle!r}")
    # Normalize to UTC. NOAA paths use the UTC cycle hour (t12z etc.);
    # a caller passing 2026-05-23 14:00+02:00 means the 12z cycle, NOT
    # a (non-existent) t14z cycle. Without normalization the path
    # builder would format the local hour into the URL and silently
    # fetch the wrong cycle (Codex iter-1 P2).
    cycle_utc = cycle.astimezone(UTC)
    grib2_url = _build_grib2_url(model, mirror, cycle_utc, fxx)
    if grib2_url is None:  # pragma: no cover — guarded above
        raise ValueError(f"could not build URL for model={model!r} mirror={mirror!r}")
    return NwpFetchPlan(
        model=model,
        mirror=mirror,
        cycle=cycle_utc,
        fxx=fxx,
        grib2_url=grib2_url,
        idx_url=grib2_url + ".idx",
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
    """
    if start < 0:
        raise ValueError(f"start must be >= 0 (got {start})")
    if end < start:
        raise ValueError(f"end must be >= start (got start={start}, end={end})")
    headers = {"Range": f"bytes={start}-{end}"}
    if client is None:
        with httpx.Client(timeout=timeout) as fresh:
            response = fresh.get(plan.grib2_url, headers=headers)
    else:
        response = client.get(plan.grib2_url, headers=headers, timeout=timeout)
    response.raise_for_status()
    return response.content


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

"""Public NWP-forecast surface (Phase 3.2 — live HRRR/GFS/NBM).

End-to-end pipeline:

1. Validate ``(model, mirror)`` against the closed enums in
   :mod:`tradewinds.weather._fetchers._nwp_archive`. Reserved ECMWF
   models raise :class:`NwpModelNotAvailableError`.
2. Resolve ``cycle`` (default: latest cycle whose lead time covers the
   requested ``fxx``).
3. For each mirror in the fallback chain: fetch the ``.idx`` text, do a
   HEAD for ``Content-Length``, parse + filter to the model's
   ``VARIABLE_MAP`` records, fetch each record via ``Range: bytes=..``,
   write the concatenated bytes to a one-message-per-file GRIB2 in a
   temp directory, decode with cfgrib, extract per-station values with
   the cached BallTree, populate the canonical DataFrame.
4. Run inline physics-bounds QC; tag each row with
   ``qc_status ∈ {clean, flagged, suspect}``.
5. Validate the assembled DataFrame against ``schema.forecast_nwp.v1``.

If all wired mirrors fail, raise :class:`NoLiveForNwpError` carrying the
mirror chain. If any byte-range fetch returns bytes that fail GRIB2
structural checks, raise :class:`GribIntegrityError`.

This module imports ``cfgrib`` / ``xarray`` / ``sklearn`` lazily inside
:func:`forecast_nwp` so the module imports cleanly even without the
``[nwp]`` extra installed. The optional-extra hint is surfaced via
:class:`SourceUnavailableError`.
"""

from __future__ import annotations

import logging
import math
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any

import httpx
from tradewinds._internal._http import HTTP_TIMEOUT
from tradewinds._internal._stations import STATIONS
from tradewinds.core.exceptions import (
    GribIntegrityError,
    NoLiveForNwpError,
    NwpModelNotAvailableError,
    SourceUnavailableError,
)
from tradewinds.core.schemas.forecast_nwp import (
    NWP_MIRROR_VALUES,
    NWP_MODEL_VALUES,
)

from ._fetchers._nwp_archive import (
    DEFAULT_MIRROR_CHAIN,
    SUPPORTED_NWP_MIRRORS,
    SUPPORTED_NWP_MODELS,
    NwpFetchPlan,
    build_fetch_plan,
    fetch_byte_range,
    fetch_grib2_content_length,
    fetch_idx_text,
)
from ._fetchers._nwp_grids import get_grid_kind, get_variable_map
from ._fetchers._nwp_idx import (
    IdxRecord,
    compute_byte_end,
    filter_records,
    parse_idx,
)

if TYPE_CHECKING:
    import pandas as pd

log = logging.getLogger(__name__)


#: Models declared in the public schema enum that v0.1.0 does NOT serve.
#: Calling :func:`forecast_nwp` with one raises
#: :class:`NwpModelNotAvailableError` — never returns an empty DataFrame
#: (anti-pattern noted in 03.2-RESEARCH.md).
_RESERVED_MODELS: frozenset[str] = frozenset(NWP_MODEL_VALUES) - SUPPORTED_NWP_MODELS


#: cfgrib's canonical short-name for each GRIB2 ``(variable, level)`` pair
#: in the tradewinds variable maps. Lifted from cfgrib's CF / GRIB2 short-
#: name table; used to project per-record xarray datasets back to the
#: canonical tradewinds column name.
_GRIB_VAR_TO_CFGRIB_NAME: dict[tuple[str, str], str] = {
    ("TMP", "2 m above ground"): "t2m",
    ("DPT", "2 m above ground"): "d2m",
    ("RH", "2 m above ground"): "r2",
    ("UGRD", "10 m above ground"): "u10",
    ("VGRD", "10 m above ground"): "v10",
    ("GUST", "surface"): "gust",
    ("GUST", "10 m above ground"): "i10fg",
    ("APCP", "surface"): "tp",
    ("PRES", "surface"): "sp",
    ("MSLMA", "mean sea level"): "mslma",
    ("PRMSL", "mean sea level"): "prmsl",
}


# ----------------------------------------------------------------------
# Physics-bounds QC (alpha — Phase 3.4 lands the full registry)
# ----------------------------------------------------------------------
def _qc_status_for_row(row: dict[str, Any]) -> str:
    """Inline physics-bounds check; returns the row's ``qc_status`` verdict.

    A row goes ``"suspect"`` if it violates a hard physics floor /
    ceiling (negative absolute temperature, sub-Martian surface
    pressure, etc. — impossible on Earth so the row is almost certainly
    a decode bug). ``"flagged"`` covers values outside the conservative
    operational window but physically possible (very high wind gust,
    very high precip rate). ``"clean"`` is the default when all checks
    pass or the column is null.
    """
    suspect = False
    flagged = False

    t = row.get("temp_k_2m")
    if t is not None and not _is_nan(t):
        # Kelvin: world record extremes ~ 184 K (-89 C) to 330 K (57 C).
        # Hard suspect: ≤ 0 K (non-physical) or ≥ 400 K (Venus).
        if t <= 0.0 or t >= 400.0:
            suspect = True
        elif t < 180.0 or t > 340.0:
            flagged = True

    dp = row.get("dewpoint_k_2m")
    if dp is not None and not _is_nan(dp):
        if dp <= 0.0 or dp >= 400.0:
            suspect = True
        # Dewpoint > temperature is physically impossible at the same point.
        if t is not None and not _is_nan(t) and not _is_nan(dp) and dp > t + 1.0:
            flagged = True

    rh = row.get("relative_humidity_pct_2m")
    if rh is not None and not _is_nan(rh):
        if rh < 0.0 or rh > 105.0:
            flagged = True
        if rh < -5.0 or rh > 110.0:
            suspect = True

    gust = row.get("wind_gust_ms")
    if gust is not None and not _is_nan(gust):
        if gust < 0.0:
            suspect = True
        elif gust > 90.0:  # ~ 200 mph
            flagged = True

    precip = row.get("precip_mm_1h")
    if precip is not None and not _is_nan(precip):
        if precip < 0.0:
            suspect = True
        elif precip > 305.0:  # ~ world hourly record
            flagged = True

    p_surf = row.get("pressure_pa_surface")
    if p_surf is not None and not _is_nan(p_surf):
        if p_surf <= 0.0:
            suspect = True
        elif p_surf < 50_000.0 or p_surf > 110_000.0:
            flagged = True

    p_mslp = row.get("pressure_pa_mslp")
    if p_mslp is not None and not _is_nan(p_mslp):
        if p_mslp <= 0.0:
            suspect = True
        elif p_mslp < 87_000.0 or p_mslp > 108_500.0:
            flagged = True

    if suspect:
        return "suspect"
    if flagged:
        return "flagged"
    return "clean"


def _is_nan(v: Any) -> bool:
    """Return True if ``v`` is a float NaN (or None)."""
    if v is None:
        return True
    try:
        return math.isnan(float(v))
    except (TypeError, ValueError):
        return False


# ----------------------------------------------------------------------
# Cycle selection
# ----------------------------------------------------------------------
def _default_cycle_for(model: str, *, fxx: int, now: datetime | None = None) -> datetime:
    """Pick a cycle hour the user is likely to mean by "the latest one".

    The constraint we want: the f``fxx`` file of the returned cycle is
    already uploaded by ``now``. Concretely we require

        cycle + fxx*1h <= now - 90min

    (90 min covers HRRR/GFS/NBM run + upload windows with some safety).
    Rearranged: ``cycle <= now - 90min - fxx*1h``. We then floor to the
    model's cycle grid — hourly for HRRR/NBM, 6-hourly for GFS.

    Worked example (HRRR, ``now = 2026-05-23 12:00 UTC``, ``fxx = 1``)::

        upper bound = 12:00 - 1h30m - 1h = 09:30
        floored hourly = 09:00
        valid_at = 09:00 + 1h = 10:00  (2h before now — clear of backoff)

    Args:
        model: One of ``SUPPORTED_NWP_MODELS``.
        fxx: Forecast hour the caller is asking for.
        now: Override wall-clock for tests. Defaults to ``datetime.now(UTC)``.
    """
    if now is None:
        now = datetime.now(UTC)
    if now.tzinfo is None:
        now = now.replace(tzinfo=UTC)
    cycle_step_h = 6 if model == "gfs" else 1
    backoff = timedelta(minutes=90)
    upper_bound = now - backoff - timedelta(hours=fxx)
    # Floor to the model's cycle grid (top of the eligible hour).
    floored_hour = (upper_bound.hour // cycle_step_h) * cycle_step_h
    return upper_bound.replace(hour=floored_hour, minute=0, second=0, microsecond=0)


# ----------------------------------------------------------------------
# Decode + extract
# ----------------------------------------------------------------------
def _resolve_stations(stations: list[str]) -> list[tuple[str, float, float]]:
    """Map ICAO / NWS codes to ``(input_string, lat, lon)`` triples.

    Stations not in the registry are skipped with a warning rather than
    raising — a quant fetching ``["KNYC", "EGLL"]`` from HRRR cares
    about losing EGLL (out-of-domain) but doesn't want KNYC dropped.

    **Alias dedup:** ``["NYC", "KNYC"]`` resolve to the same
    :class:`StationInfo`. Without dedup the function would emit two
    rows per fetch with the same lat/lon but different ``station``
    labels — silent double-count when a downstream user unions runs.
    First occurrence of each canonical info wins; aliases later in the
    input are dropped with a logged warning.

    Returns:
        Resolved (station_id, lat, lon) triples in input order. The
        ``station_id`` is the original input string (preserved verbatim
        so downstream joins on the user's chosen label still work).
    """
    out: list[tuple[str, float, float]] = []
    seen_canonical: set[str] = set()
    for s in stations:
        info = STATIONS.get(s)
        if info is None:
            for v in STATIONS.values():
                if v.icao == s:
                    info = v
                    break
        if info is None:
            log.warning("forecast_nwp: skipping unknown station %r", s)
            continue
        # Use ICAO as the canonical identity — ``code`` may be a
        # 3-letter NWS abbreviation for US, but every registry entry
        # carries an ICAO (US or international).
        canonical = info.icao
        if canonical in seen_canonical:
            log.warning(
                "forecast_nwp: dropping alias %r — already resolved as %r",
                s,
                canonical,
            )
            continue
        seen_canonical.add(canonical)
        out.append((s, info.latitude, info.longitude))
    return out


def _try_fetch_records_for_mirror(
    *,
    model: str,
    mirror: str,
    cycle: datetime,
    fxx: int,
    variable_map: dict[str, tuple[str, str]],
    client: httpx.Client,
) -> tuple[NwpFetchPlan, list[IdxRecord], int] | None:
    """Resolve a fetch plan + ``.idx`` + content length on one mirror.

    Returns ``None`` if the mirror failed (caller falls back to the next
    one in the chain). Returns a tuple ``(plan, records, content_length)``
    on success — caller does the per-record byte-range fetch.
    """
    plan = build_fetch_plan(model=model, mirror=mirror, cycle=cycle, fxx=fxx)
    try:
        idx_text = fetch_idx_text(plan, client=client)
        records = compute_byte_end(
            parse_idx(idx_text),
            content_length=fetch_grib2_content_length(plan, client=client),
        )
        content_length = (
            records[-1].byte_end + 1 if records and records[-1].byte_end is not None else 0
        )
    except (httpx.HTTPStatusError, httpx.RequestError) as exc:
        log.info(
            "forecast_nwp: mirror %s failed for %s cycle %s fxx %d: %s",
            mirror,
            model,
            cycle.isoformat(),
            fxx,
            exc,
        )
        return None
    filtered = filter_records(records, variable_map)
    return plan, filtered, content_length


def forecast_nwp(
    station: str | list[str],
    model: str,
    *,
    cycle: datetime | None = None,
    fxx: int = 1,
    mirror: str | None = None,
    client: httpx.Client | None = None,
) -> pd.DataFrame:
    """Fetch NWP forecast values for one or more stations from NOAA BDP.

    Args:
        station: Single ICAO/NWS code or a list of them. Unknown codes
            are skipped with a logged warning (not raised) so a partial
            list still returns a partial DataFrame.
        model: One of :data:`SUPPORTED_NWP_MODELS` (``"hrrr"``, ``"gfs"``,
            ``"nbm"``). ECMWF Tier-2 values raise
            :class:`NwpModelNotAvailableError`.
        cycle: Model run cycle (UTC, tz-aware). Default: the most recent
            cycle whose ``run + fxx`` clears a 90-minute upload backoff.
        fxx: Forecast hour ahead of ``cycle``. Default ``1`` (next hour).
        mirror: Force a specific mirror (``"aws_bdp"`` or ``"nomads"``).
            Default: try AWS first then NOMADS.
        client: Reuse an ``httpx.Client`` for connection pooling. A
            fresh client is created (and closed) per call if omitted.

    Returns:
        ``pd.DataFrame`` matching ``schema.forecast_nwp.v1`` — one row
        per (station, variable subset) for the given cycle/fxx. Empty
        DataFrame (with the canonical columns) if every requested
        station is unknown OR the model variable map matches no records
        in the upstream ``.idx`` (genuinely missing variables).

    Raises:
        NwpModelNotAvailableError: ``model`` is reserved (ECMWF Tier-2).
        ValueError: ``model`` or ``mirror`` is not in the supported set;
            ``fxx`` is negative; ``cycle`` is naive.
        SourceUnavailableError: the ``[nwp]`` optional extra
            (``cfgrib`` + ``xarray`` + ``sklearn``) is not installed.
        NoLiveForNwpError: every wired mirror failed (typically while
            the upstream is still uploading a cycle).
        GribIntegrityError: at least one fetched record decoded with
            structural failures (Pitfall 1 territory — cfgrib raises
            for a truncated final-record byte range).
    """
    # Public schema enum split: tradewinds-served vs reserved (ECMWF).
    if model in _RESERVED_MODELS:
        raise NwpModelNotAvailableError(
            f"NWP model {model!r} is reserved in schema.forecast_nwp.v1 "
            "but not implemented in v0.1.0 (deferred to v0.2 — ECMWF "
            "Tier-2 requires hosted infrastructure).",
            model=model,
            available_in="v0.2",
        )
    if model not in SUPPORTED_NWP_MODELS:
        raise ValueError(
            f"model must be one of {sorted(SUPPORTED_NWP_MODELS)} "
            f"(or reserved in {sorted(NWP_MODEL_VALUES)} for v0.2); "
            f"got {model!r}"
        )
    if mirror is not None and mirror not in SUPPORTED_NWP_MIRRORS:
        raise ValueError(
            f"mirror must be one of {sorted(SUPPORTED_NWP_MIRRORS)} "
            f"(or reserved in {sorted(NWP_MIRROR_VALUES)} for v0.2); "
            f"got {mirror!r}"
        )

    # Lazy-import the heavy deps so the module imports without [nwp].
    try:
        from . import _fetchers  # noqa: F401 — package guard
        from ._fetchers import _nwp_extract
    except ImportError as exc:  # pragma: no cover — unexpected, modules ship in same wheel
        raise SourceUnavailableError(
            f"NWP forecast wiring failed to import: {exc}",
            source=f"nwp.{model}",
            retryable=False,
            underlying=str(exc),
        ) from exc
    try:
        import xarray  # noqa: F401
        from sklearn.neighbors import BallTree  # noqa: F401
    except ImportError as exc:
        raise SourceUnavailableError(
            f"NWP forecast for model={model!r} requires the [nwp] optional "
            "extra. Install with: pip install tradewinds-weather[nwp]",
            source=f"nwp.{model}",
            retryable=False,
            underlying=str(exc),
        ) from None
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
    import pandas as pd

    if fxx < 0:
        raise ValueError(f"fxx must be non-negative; got {fxx}")
    if cycle is None:
        cycle = _default_cycle_for(model, fxx=fxx)
    if cycle.tzinfo is None or cycle.tzinfo.utcoffset(cycle) is None:
        raise ValueError(f"cycle must be timezone-aware (UTC); got naive {cycle!r}")

    station_list: list[str] = [station] if isinstance(station, str) else list(station)
    resolved = _resolve_stations(station_list)
    grid_kind = get_grid_kind(model)
    variable_map = get_variable_map(model)

    if not resolved:
        return _empty_dataframe(model=model, grid_kind=grid_kind)

    mirrors_to_try = (mirror,) if mirror is not None else DEFAULT_MIRROR_CHAIN

    owns_client = client is None
    if owns_client:
        client = httpx.Client(timeout=HTTP_TIMEOUT)
    try:
        plan: NwpFetchPlan | None = None
        filtered_records: list[IdxRecord] = []
        for m in mirrors_to_try:
            attempt = _try_fetch_records_for_mirror(
                model=model,
                mirror=m,
                cycle=cycle,
                fxx=fxx,
                variable_map=variable_map,
                client=client,
            )
            if attempt is None:
                continue
            plan, filtered_records, _ = attempt
            break
        if plan is None:
            raise NoLiveForNwpError(
                f"All mirrors failed for model={model!r} cycle={cycle.isoformat()}",
                model=model,
                mirrors_tried=list(mirrors_to_try),
            )

        station_coords: list[tuple[float, float]] = [(lat, lon) for _, lat, lon in resolved]
        column_values: dict[str, list[float | None]] = {
            col: [None] * len(resolved) for col in variable_map
        }
        distances_km: list[float | None] = [None] * len(resolved)

        with tempfile.TemporaryDirectory(prefix="tradewinds_nwp_") as tmpdir:
            tmp = Path(tmpdir)
            # Group records by (variable, level). Codex iter-1 P2:
            # NCEP .idx files can list MULTIPLE records with the same
            # (variable, level) but different forecast_period strings —
            # most commonly for accumulated fields like APCP:surface
            # which can ship a "0-1 hour acc" and "1-2 hour acc" window
            # in the same file. The old single-entry dict silently kept
            # the last one, which could decode the wrong accumulation
            # window. Now we keep the full list per key and raise
            # GribIntegrityError when ambiguous so the caller can audit
            # rather than silently get the wrong precip total.
            record_groups: dict[tuple[str, str], list[IdxRecord]] = {}
            for rec in filtered_records:
                record_groups.setdefault((rec.variable, rec.level), []).append(rec)
            for col, key in variable_map.items():
                group = record_groups.get(key)
                if not group:
                    rec = None
                elif len(group) == 1:
                    rec = group[0]
                else:
                    raise GribIntegrityError(
                        f"ambiguous .idx records for {key}: "
                        f"{[r.forecast_period for r in group]} — "
                        "tradewinds v0.1 picks one record per (variable, level); "
                        "for accumulated fields with multiple windows, "
                        "extend VARIABLE_MAP to a (variable, level, forecast_period) "
                        "tuple or pin the desired window via Phase 3.4 QC engine.",
                        model=model,
                        variable=key[0],
                    )
                if rec is None or rec.byte_end is None:
                    # Variable missing from this cycle's .idx — column
                    # stays null for every station. NOT a fatal error.
                    continue
                try:
                    payload = fetch_byte_range(
                        plan,
                        start=rec.byte_offset,
                        end=rec.byte_end,
                        client=client,
                    )
                except (httpx.HTTPStatusError, httpx.RequestError) as exc:
                    raise GribIntegrityError(
                        f"byte-range fetch failed for {key} on {plan.mirror}",
                        model=model,
                        variable=key[0],
                        byte_offset=rec.byte_offset,
                        byte_end=rec.byte_end,
                        underlying=str(exc),
                    ) from exc
                record_path = (
                    tmp / f"{rec.record_no}_{rec.variable}_{rec.level.replace(' ', '_')}.grib2"
                )
                record_path.write_bytes(payload)
                try:
                    ds = _nwp_extract.open_grib2_dataset(str(record_path))
                except Exception as exc:  # cfgrib raises a variety; coerce.
                    raise GribIntegrityError(
                        f"cfgrib failed to decode {key} (mirror={plan.mirror})",
                        model=model,
                        variable=key[0],
                        byte_offset=rec.byte_offset,
                        byte_end=rec.byte_end,
                        underlying=str(exc),
                    ) from exc
                try:
                    cfgrib_name = _cfgrib_variable_name(ds, key, model=model)
                    extracted = _nwp_extract.extract_stations(
                        ds, variable=cfgrib_name, station_coords=station_coords
                    )
                finally:
                    ds.close()
                for i, (value, dist_km) in enumerate(extracted):
                    column_values[col][i] = value
                    if distances_km[i] is None:
                        distances_km[i] = dist_km

        retrieved_at = datetime.now(UTC)
        rows: list[dict[str, Any]] = []
        valid_at = cycle + timedelta(hours=fxx)
        # Codex iter-1 P2: pandas infers `object` dtype when a column
        # is all-None. The schema declares these as `float64`; emit
        # `float('nan')` explicitly so even an all-missing column
        # (e.g. NBM has no `pressure_pa_surface`) round-trips through
        # the schema validator with the right dtype.
        nullable_numeric_cols = (
            "temp_k_2m",
            "dewpoint_k_2m",
            "relative_humidity_pct_2m",
            "wind_u_ms_10m",
            "wind_v_ms_10m",
            "wind_gust_ms",
            "precip_mm_1h",
            "pressure_pa_surface",
            "pressure_pa_mslp",
        )
        for i, (station_id, _, _) in enumerate(resolved):
            row: dict[str, Any] = {
                "station": station_id,
                "model": model,
                "mirror": plan.mirror,
                "grid_kind": grid_kind,
                "issued_at": cycle,
                "valid_at": valid_at,
                "forecast_hour": fxx,
                "grid_dist_km": distances_km[i] if distances_km[i] is not None else float("nan"),
            }
            for col in variable_map:
                val = column_values[col][i]
                row[col] = float("nan") if val is None else val
            # Ensure every schema column is present even if model lacks
            # that variable map entry (e.g. NBM has no pressure_pa_surface).
            for col in nullable_numeric_cols:
                row.setdefault(col, float("nan"))
            row["qc_status"] = _qc_status_for_row(row)
            row["retrieved_at"] = retrieved_at
            rows.append(row)
        df = pd.DataFrame(rows)
        # Codex iter-1 P2: validator (tradewinds.core.validator) checks
        # df.attrs["source"] against the schema's registered source on
        # every canonical DataFrame. Stamp it here so callers that
        # validate the documented schema.forecast_nwp.v1 result do not
        # hit `source_attr_required`.
        df.attrs["source"] = "noaa_bdp"
        # Coerce nullable numeric columns to float64 even if every row
        # turned out NaN — pandas otherwise leaves the column as
        # `object` (silent dtype drift).
        for col in nullable_numeric_cols:
            if col in df.columns:
                df[col] = df[col].astype("float64")
        return df
    finally:
        if owns_client and client is not None:
            client.close()


def _cfgrib_variable_name(ds: Any, key: tuple[str, str], *, model: str) -> str:
    """Look up the cfgrib short-name a record decodes to.

    cfgrib normalises GRIB2 variable + level to a short-name (``"t2m"``
    for TMP at 2 m) and exposes it as a data-var on the dataset. We
    consult :data:`_GRIB_VAR_TO_CFGRIB_NAME` first, then fall back to
    "the single data-var in this single-message dataset" so unknown
    mappings still work for one-record fetches.

    ``model`` is required so any ``GribIntegrityError`` raised here
    carries the same model context as one raised from the caller —
    keeps ``to_dict()["model"]`` non-empty for MCP serialization.
    """
    canonical = _GRIB_VAR_TO_CFGRIB_NAME.get(key)
    if canonical is not None and canonical in ds.data_vars:
        return canonical
    data_vars = list(ds.data_vars)
    if len(data_vars) == 1:
        return data_vars[0]
    if canonical is not None:
        # cfgrib accepted the GRIB2 record but used a different short-name
        # than the table predicted (e.g. RRFS rename). Raise so the table
        # gets updated rather than silently returning the wrong field.
        raise GribIntegrityError(
            f"cfgrib short-name table miss for {key}: expected {canonical!r}, "
            f"got data_vars={data_vars}",
            model=model,
            variable=key[0],
        )
    raise GribIntegrityError(
        f"cfgrib decoded multiple data_vars for single-record file {key}: {data_vars}",
        model=model,
        variable=key[0],
    )


def _empty_dataframe(*, model: str, grid_kind: str) -> pd.DataFrame:
    """Return an empty DataFrame whose columns match ``schema.forecast_nwp.v1``."""
    import pandas as pd

    df = pd.DataFrame(
        {
            "station": pd.Series(dtype="object"),
            "model": pd.Series(dtype="object"),
            "mirror": pd.Series(dtype="object"),
            "grid_kind": pd.Series(dtype="object"),
            "issued_at": pd.Series(dtype="datetime64[ns, UTC]"),
            "valid_at": pd.Series(dtype="datetime64[ns, UTC]"),
            "forecast_hour": pd.Series(dtype="int64"),
            "grid_dist_km": pd.Series(dtype="float64"),
            "temp_k_2m": pd.Series(dtype="float64"),
            "dewpoint_k_2m": pd.Series(dtype="float64"),
            "relative_humidity_pct_2m": pd.Series(dtype="float64"),
            "wind_u_ms_10m": pd.Series(dtype="float64"),
            "wind_v_ms_10m": pd.Series(dtype="float64"),
            "wind_gust_ms": pd.Series(dtype="float64"),
            "precip_mm_1h": pd.Series(dtype="float64"),
            "pressure_pa_surface": pd.Series(dtype="float64"),
            "pressure_pa_mslp": pd.Series(dtype="float64"),
            "qc_status": pd.Series(dtype="object"),
            "retrieved_at": pd.Series(dtype="datetime64[ns, UTC]"),
        }
    )
    # Codex iter-1 P2: source attr stamped even on empty path so
    # downstream validators see it.
    df.attrs["source"] = "noaa_bdp"
    return df


__all__ = ["forecast_nwp"]

"""IEM MOS (Model Output Statistics) fetcher — JSON from mesonet.agron.iastate.edu.

The parity-compatible forecast source for ``research(include_forecast=True)``
Mode 1. Output matches ``schema.forecast.iem_mos.v1``.

Per-model coverage: NBE (preferred for US), GFS, LAV, MET, ECM.
Endpoint: ``https://mesonet.agron.iastate.edu/api/1/mos.json``.
Polite floor: 1 req/sec per IEM CLAUDE.md guideline (reused from iem_asos).
"""

from __future__ import annotations

import logging
import time
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pandas as pd
from mostlyright._internal._http import HTTP_TIMEOUT

log = logging.getLogger(__name__)

_IEM_MOS_URL = "https://mesonet.agron.iastate.edu/api/1/mos.json"

#: MOS models IEM exposes through the JSON endpoint.
SUPPORTED_MOS_MODELS: frozenset[str] = frozenset({"nbe", "gfs", "lav", "met", "ecm"})

#: Conversion factor from knots to metres per second (canonical column unit
#: is ``wind_speed_ms`` per :mod:`mostlyright.core.schemas.forecast`).
_KT_TO_MS: float = 0.5144444

#: IEM polite-floor delay between MOS GETs (reused convention from iem_asos).
_MOS_POLITE_DELAY_S: float = 1.0

#: NBE runtime-cycle transition: IEM moved NBE from {01,07,13,19}Z to
#: {00,06,12,18}Z on 2026-05-05. Historical backfills that span this
#: cutover need both sets covered.
_NBE_CYCLE_CUTOVER: datetime = datetime(2026, 5, 5, tzinfo=UTC)


def _runtime_hours_for(model: str, from_dt: datetime, to_dt: datetime) -> tuple[int, ...]:
    """Return the runtime-hours tuple for ``model`` in ``[from_dt, to_dt]``.

    NBE: ``{01,07,13,19}Z`` pre-cutover, ``{00,06,12,18}Z`` post-cutover.
    Ranges that span the cutover get the UNION so neither half silently
    returns empty 404s (Phase 17 Wave 3 iter-4 review).

    All other models default to ``{00,06,12,18}Z`` (GFS / LAV / MET / ECM
    follow the standard 6-hourly NCEP cycle).
    """
    if model == "nbe":
        pre = from_dt < _NBE_CYCLE_CUTOVER
        post = to_dt >= _NBE_CYCLE_CUTOVER
        if pre and post:
            return (0, 1, 6, 7, 12, 13, 18, 19)
        if pre:
            return (1, 7, 13, 19)
        return (0, 6, 12, 18)
    return (0, 6, 12, 18)


#: Canonical column list matching ``schema.forecast.iem_mos.v1.COLUMNS``.
#: Returned empty DataFrame uses these so dtype inference is consistent
#: across empty / populated paths.
_CANONICAL_COLUMNS: tuple[str, ...] = (
    "station",
    "issued_at",
    "valid_at",
    "forecast_hour",
    "model",
    "temp_c",
    "dew_point_c",
    "wind_speed_ms",
    "wind_dir_deg",
    "precip_probability",
    "sky_cover_pct",
    "source",
    "retrieved_at",
)


def _f_to_c(temp_f: float | None) -> float | None:
    """Fahrenheit → Celsius, ``None`` passthrough."""
    if temp_f is None:
        return None
    return (float(temp_f) - 32.0) * 5.0 / 9.0


def _kt_to_ms(kt: float | None) -> float | None:
    """Knots → m/s, ``None`` passthrough."""
    if kt is None:
        return None
    return float(kt) * _KT_TO_MS


def _pct_to_unit(pct: float | None) -> float | None:
    """Percent (0-100) → probability (0-1), ``None`` passthrough."""
    if pct is None:
        return None
    return float(pct) / 100.0


def _maybe_float(row: dict[str, Any], key: str) -> float | None:
    """Pull a numeric field from an IEM MOS row, treating ``M`` / blank /
    null as missing.
    """
    v = row.get(key)
    if v is None or v == "" or v == "M":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _parse_dt(value: str | None) -> datetime | None:
    """Parse an ISO datetime from IEM MOS, returning UTC-aware or ``None``."""
    if not value:
        return None
    try:
        # IEM sometimes returns trailing 'Z' — normalise to UTC offset.
        normalized = value.replace("Z", "+00:00")
        dt = datetime.fromisoformat(normalized)
    except (TypeError, ValueError):
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def _parse_mos_row(
    row: dict[str, Any],
    *,
    station: str,
    model: str,
    retrieved_at: datetime,
) -> dict[str, Any] | None:
    """Project one IEM MOS row to the canonical schema. Returns ``None``
    when both ``runtime`` and ``ftime`` are unparseable (the row is
    structurally invalid).
    """
    issued_at = _parse_dt(row.get("runtime") or row.get("model_runtime"))
    valid_at = _parse_dt(row.get("ftime") or row.get("valid_time"))
    if issued_at is None or valid_at is None:
        return None
    forecast_hour = round((valid_at - issued_at).total_seconds() / 3600)
    return {
        "station": station,
        "issued_at": issued_at,
        "valid_at": valid_at,
        "forecast_hour": forecast_hour,
        "model": model.upper(),
        "temp_c": _f_to_c(_maybe_float(row, "tmp")),
        "dew_point_c": _f_to_c(_maybe_float(row, "dpt")),
        "wind_speed_ms": _kt_to_ms(_maybe_float(row, "wsp")),
        "wind_dir_deg": (round(d) if (d := _maybe_float(row, "wdr")) is not None else None),
        "precip_probability": _pct_to_unit(_maybe_float(row, "pop12")),
        "sky_cover_pct": None,  # IEM MOS doesn't expose a single sky-cover %
        "source": "iem.archive",
        "retrieved_at": retrieved_at,
    }


def fetch_iem_mos(
    station: str,
    from_date: str,
    to_date: str,
    *,
    model: str = "nbe",
    client: httpx.Client | None = None,
    timeout: float = HTTP_TIMEOUT,
) -> pd.DataFrame:
    """Fetch IEM MOS forecasts for ``station`` + ``model`` in
    ``[from_date, to_date]`` (inclusive, ISO ``YYYY-MM-DD``).

    Iterates the 00 / 06 / 12 / 18 Z runtimes in the requested date
    range, GETs each as ``runtime`` query parameter, and accumulates the
    returned per-ftime rows into a single DataFrame matching
    ``schema.forecast.iem_mos.v1``.

    Args:
        station: ICAO code (e.g. ``"KNYC"``).
        from_date: ISO ``YYYY-MM-DD`` lower bound (inclusive).
        to_date: ISO ``YYYY-MM-DD`` upper bound (inclusive).
        model: One of :data:`SUPPORTED_MOS_MODELS`. Default ``"nbe"``.
        client: Optional :class:`httpx.Client` to reuse.
        timeout: Per-request timeout in seconds.

    Returns:
        DataFrame with the canonical columns. Empty (with columns) if
        IEM returns no MOS rows in the requested window.

    Raises:
        ValueError: ``model`` not in :data:`SUPPORTED_MOS_MODELS` or
            date strings malformed.
        httpx.HTTPError: IEM unreachable / non-2xx (404 is silently
            skipped — many runtimes have no data and that's normal).
    """
    if model not in SUPPORTED_MOS_MODELS:
        raise ValueError(f"model must be one of {sorted(SUPPORTED_MOS_MODELS)}; got {model!r}")
    try:
        from_dt = datetime.fromisoformat(from_date).replace(tzinfo=UTC)
        to_dt = datetime.fromisoformat(to_date).replace(tzinfo=UTC, hour=23, minute=59, second=59)
    except ValueError as exc:
        raise ValueError(
            f"from_date / to_date must be ISO YYYY-MM-DD; "
            f"got from_date={from_date!r} to_date={to_date!r}"
        ) from exc

    close_client = client is None
    if client is None:
        client = httpx.Client(timeout=timeout)

    rows: list[dict[str, Any]] = []
    retrieved_at = datetime.now(UTC)
    try:
        # Phase 17 Wave 3 iter-4 review: model-aware runtime hours.
        # NBE cycle hours moved from {01,07,13,19}Z to {00,06,12,18}Z on
        # 2026-05-05; pre-cutover historical backfills would 404 on every
        # canonical-hour request and silently return an empty DataFrame.
        # The safe strategy is to iterate BOTH hour sets when the cycle
        # transition is in or near the requested window. The 404-skip
        # path absorbs the wrong-runtime requests at the cost of ~1
        # extra GET per day per side.
        runtimes: list[datetime] = []
        hours = _runtime_hours_for(model, from_dt, to_dt)
        cur = from_dt.replace(hour=0, minute=0, second=0, microsecond=0)
        while cur <= to_dt:
            for h in hours:
                rt = cur.replace(hour=h)
                if from_dt <= rt <= to_dt:
                    runtimes.append(rt)
            cur = cur + timedelta(days=1)

        for rt in runtimes:
            params = {
                "station": station,
                # IEM /api/1/mos.json regex ^(AVN|GFS|...|NBE|...)$ is
                # uppercase-only; sending lowercase returns HTTP 422
                # (issue #17). Mirrors the schema-column upper() at L153.
                "model": model.upper(),
                "runtime": rt.isoformat(),
            }
            resp = client.get(_IEM_MOS_URL, params=params)
            if resp.status_code == 404:
                log.debug(
                    "IEM MOS 404 for %s %s runtime=%s",
                    station,
                    model,
                    rt.isoformat(),
                )
                time.sleep(_MOS_POLITE_DELAY_S)
                continue
            resp.raise_for_status()
            payload = resp.json()
            for raw_row in payload.get("data", []):
                projected = _parse_mos_row(
                    raw_row,
                    station=station,
                    model=model,
                    retrieved_at=retrieved_at,
                )
                if projected is not None:
                    rows.append(projected)
            time.sleep(_MOS_POLITE_DELAY_S)
    finally:
        if close_client:
            client.close()

    if not rows:
        empty = pd.DataFrame(columns=list(_CANONICAL_COLUMNS))
        empty.attrs["source"] = "iem.archive"
        empty.attrs["retrieved_at"] = retrieved_at
        return _coerce_canonical_dtypes(empty)
    df = pd.DataFrame(rows, columns=list(_CANONICAL_COLUMNS))
    df.attrs["source"] = "iem.archive"
    df.attrs["retrieved_at"] = retrieved_at
    return _coerce_canonical_dtypes(df)


def _coerce_canonical_dtypes(df: pd.DataFrame) -> pd.DataFrame:
    """Coerce IEM MOS columns to the canonical
    ``schema.forecast.iem_mos.v1`` dtypes (Phase 17 Wave 3 iter-2 review).

    Uses pandas nullable dtypes (``Int64``, ``Float64``, ``string``) so
    missing fields survive without forcing the column to ``object``.
    Empty DataFrames also get the right per-column dtype so
    :func:`validate_dataframe` accepts them.
    """
    df["station"] = df["station"].astype("string")
    df["model"] = df["model"].astype("string")
    df["source"] = df["source"].astype("string")
    df["issued_at"] = pd.to_datetime(df["issued_at"], utc=True, errors="coerce")
    df["valid_at"] = pd.to_datetime(df["valid_at"], utc=True, errors="coerce")
    df["retrieved_at"] = pd.to_datetime(df["retrieved_at"], utc=True, errors="coerce")
    df["forecast_hour"] = pd.to_numeric(df["forecast_hour"], errors="coerce").astype("Int64")
    df["wind_dir_deg"] = pd.to_numeric(df["wind_dir_deg"], errors="coerce").astype("Int64")
    df["sky_cover_pct"] = pd.to_numeric(df["sky_cover_pct"], errors="coerce").astype("Int64")
    for fcol in ("temp_c", "dew_point_c", "wind_speed_ms", "precip_probability"):
        df[fcol] = pd.to_numeric(df[fcol], errors="coerce").astype("Float64")
    return df


__all__ = ["SUPPORTED_MOS_MODELS", "fetch_iem_mos"]

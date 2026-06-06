"""Open-Meteo forecast fetcher (Phase 20 OM-01).

Three modes covered:

- ``mode="training"`` (default) → Previous Runs API with conservative
  ``issued_at`` lower bound; OR Single Runs API when caller specifies
  ``issued_at=...``.
- ``mode="seamless"`` → Historical Forecast API; requires
  ``allow_leakage=True`` opt-in (raises
  :class:`OpenMeteoSeamlessLeakageError` otherwise).
- ``mode="live"`` → Live Forecast API
  (``https://api.open-meteo.com/v1/forecast``). Per D-06: ``issued_at``
  derived via cycle-math fallback only (Metadata API integration is a
  follow-up). Tagged ``source="open_meteo.live"``; NOT cached (rolling
  cycle).

All returned rows match ``schema.forecast.station.v1`` with non-null
``issued_at`` (seamless mode rows have NULL ``issued_at`` BY DESIGN — the
:class:`LeakageDetector` rejects them downstream whenever ``as_of`` is
asserted).

Origin: Phase 20 — addresses Tarabcak/mostlyright#70 (legacy seamless-feed
leakage bug). See ``20-RESEARCH.md`` §Legacy bug reproduction for the
exact NYC 2024-06-01 case the regression suite reproduces.

Limits (documented):
- Single-station per call (no station chunking).
- Single-model per call (no multi-model batching; Open-Meteo supports
  comma-separated ``models=`` but Phase 20 ships one model at a time).
- Single-day-lookback Previous Runs (only ``_previous_day1`` suffix is
  requested; multi-day lookback is a follow-up).
- 14-day Open-Meteo per-call cap; longer windows must chunk client-side.
"""

from __future__ import annotations

import logging
import time
from datetime import UTC, date, datetime, timedelta
from math import ceil
from typing import Any, Literal

import httpx
import pandas as pd
from mostlyright._internal._http import HTTP_TIMEOUT
from mostlyright._internal._stations import STATIONS
from mostlyright.core.exceptions import OpenMeteoSeamlessLeakageError

from ._open_meteo_models import (
    CYCLE_HOURS,
    OPEN_METEO_MODELS,
    issued_at_from_previous_day,
)

log = logging.getLogger(__name__)

#: Endpoint URLs (see ``20-RESEARCH.md`` §Endpoint reference).
OPEN_METEO_PREVIOUS_RUNS_URL = "https://previous-runs-api.open-meteo.com/v1/forecast"
OPEN_METEO_SINGLE_RUNS_URL = "https://single-runs-api.open-meteo.com/v1/forecast"
OPEN_METEO_SEAMLESS_URL = "https://historical-forecast-api.open-meteo.com/v1/forecast"
OPEN_METEO_LIVE_URL = "https://api.open-meteo.com/v1/forecast"

#: Polite floor — 5 req/s single-worker (tighter than the documented 600/min).
_OM_POLITE_DELAY_S: float = 0.2

#: Open-Meteo per-call weight thresholds (free tier billing model).
_OM_MAX_DAYS_PER_CALL: int = 14
_OM_VAR_FREE_BUDGET: int = 10

#: Single-Runs returns a fixed ~168h (7-day) horizon from ``run=`` regardless
#: of the requested window, so its weighted cost / polite delay uses this fixed
#: span — NOT the (possibly year-long) caller window.
_OM_SINGLE_RUNS_HORIZON_DAYS: int = 7

#: Retry-After cap (mirrors ``_kalshi_client._RETRY_AFTER_CAP_SECONDS``).
_RETRY_AFTER_CAP_SECONDS: float = 60.0
_MAX_RETRIES: int = 3

Mode = Literal["training", "seamless", "live"]
_VALID_MODES: frozenset[str] = frozenset({"training", "seamless", "live"})

#: Open-Meteo hourly variable names to request. See ``20-RESEARCH.md``
#: §Endpoint reference for the canonical Open-Meteo → schema column
#: mapping.
_OM_VARIABLES_TO_FETCH: tuple[str, ...] = (
    "temperature_2m",
    "dew_point_2m",
    "apparent_temperature",
    "wind_speed_10m",
    "wind_direction_10m",
    "wind_gusts_10m",
    "precipitation",
    "precipitation_probability",
    "cloud_cover",
    "surface_pressure",
    "pressure_msl",
    "shortwave_radiation",
    "direct_radiation",
    "cape",
    "freezing_level_height",
    "snow_depth",
    "visibility",
    "weather_code",
)

#: Open-Meteo variable → StationForecastSchema column.
_OM_VAR_TO_COLUMN: dict[str, str] = {
    "temperature_2m": "temp_c",
    "dew_point_2m": "dew_point_c",
    "apparent_temperature": "apparent_temp_c",
    "wind_speed_10m": "wind_speed_ms",
    "wind_direction_10m": "wind_dir_deg",
    "wind_gusts_10m": "wind_gusts_ms",
    "precipitation": "precipitation_mm",
    "precipitation_probability": "precip_probability",  # /100 to fraction
    "cloud_cover": "cloud_cover_pct",
    "surface_pressure": "surface_pressure_hpa",
    "pressure_msl": "pressure_msl_hpa",
    "shortwave_radiation": "shortwave_radiation_wm2",
    "direct_radiation": "direct_radiation_wm2",
    "cape": "cape_jkg",
    "freezing_level_height": "freezing_level_m",
    "snow_depth": "snow_depth_m",
    "visibility": "visibility_m",
    "weather_code": "weather_code",
}

#: Canonical column order — matches ``StationForecastSchema.COLUMNS`` from
#: PLAN-01.
_CANONICAL_COLUMNS: tuple[str, ...] = (
    "station",
    "issued_at",
    "valid_at",
    "forecast_hour",
    "model",
    "source",
    # IEM MOS core (nullable for OM rows)
    "temp_c",
    "dew_point_c",
    "wind_speed_ms",
    "wind_dir_deg",
    "precip_probability",
    "sky_cover_pct",
    # OM extras
    "apparent_temp_c",
    "shortwave_radiation_wm2",
    "direct_radiation_wm2",
    "cape_jkg",
    "precipitation_mm",
    "cloud_cover_pct",
    "surface_pressure_hpa",
    "pressure_msl_hpa",
    "freezing_level_m",
    "snow_depth_m",
    "visibility_m",
    "wind_gusts_ms",
    "weather_code",
    # Provenance
    "retrieved_at",
)


def _chunk_date_range(
    from_date: str,
    to_date: str,
    max_days: int = _OM_MAX_DAYS_PER_CALL,
) -> list[tuple[str, str]]:
    """Split [from_date, to_date] into ≤max_days-day chunks."""
    start = date.fromisoformat(from_date)
    end = date.fromisoformat(to_date)
    chunks: list[tuple[str, str]] = []
    cur = start
    while cur <= end:
        chunk_end = min(cur + timedelta(days=max_days - 1), end)
        chunks.append((cur.isoformat(), chunk_end.isoformat()))
        cur = chunk_end + timedelta(days=1)
    return chunks


def _weighted_call_cost(num_vars: int, num_days: int) -> float:
    """Open-Meteo weighted call cost: ceil(vars/10) * ceil(days/14)."""
    return float(ceil(num_vars / _OM_VAR_FREE_BUDGET) * ceil(num_days / _OM_MAX_DAYS_PER_CALL))


def _validate_variables(variables: tuple[str, ...] | None) -> tuple[str, ...]:
    """Validate caller-supplied variables; return full default set when None."""
    if variables is None:
        return _OM_VARIABLES_TO_FETCH
    unknown = [v for v in variables if v not in _OM_VAR_TO_COLUMN]
    if unknown:
        raise ValueError(
            f"unknown OM variable(s) — {unknown!r}; allowed: {sorted(_OM_VAR_TO_COLUMN)}"
        )
    return tuple(variables)


def _station_to_lat_lon(station: str) -> tuple[float, float]:
    """Resolve an ICAO (or 3-letter US) station to ``(latitude, longitude)``.

    Phase 20 ships the existing 60-station registry; international expansion
    is out of scope. Unknown stations raise :class:`ValueError`.
    """
    # Try the registry key first (3-letter US codes)
    entry = STATIONS.get(station)
    if entry is None:
        # Then by .icao attribute (4-letter international codes)
        for info in STATIONS.values():
            if info.icao == station:
                entry = info
                break
    if entry is None:
        raise ValueError(f"unknown station {station!r}; not in STATIONS registry")
    return entry.latitude, entry.longitude


def _parse_retry_after_seconds(value: str | None) -> float:
    """Parse a ``Retry-After`` header value, capped at 60s.

    Mirrors ``_kalshi_client._parse_retry_after_seconds`` semantics: a
    delta-seconds integer is the typical Open-Meteo response. Non-numeric
    values (HTTP-date format) return 0.
    """
    if value is None:
        return 0.0
    try:
        seconds = float(value)
    except (TypeError, ValueError):
        return 0.0
    return min(max(seconds, 0.0), _RETRY_AFTER_CAP_SECONDS)


def _dispatch_endpoint(
    mode: str,
    *,
    allow_leakage: bool,
    model: str,
    issued_at: str | None = None,
) -> str:
    """Pick the endpoint URL or raise on a banned combination (D-04).

    Priority for ``mode='training'`` (D-04):
      1. If ``issued_at`` is set → Single Runs API.
      2. Else → Previous Runs API.

    For ``mode='seamless'`` without ``allow_leakage=True``, raises BEFORE
    any HTTP request is issued.
    """
    if mode == "training":
        if issued_at is not None:
            return OPEN_METEO_SINGLE_RUNS_URL
        return OPEN_METEO_PREVIOUS_RUNS_URL
    if mode == "seamless":
        if not allow_leakage:
            raise OpenMeteoSeamlessLeakageError(
                "Open-Meteo seamless endpoint is banned for training data "
                "(see Tarabcak/mostlyright#70). Pass allow_leakage=True to "
                "opt in; LeakageDetector will still reject these rows when "
                "as_of is asserted.",
                model=model,
                endpoint_url=OPEN_METEO_SEAMLESS_URL,
            )
        return OPEN_METEO_SEAMLESS_URL
    if mode == "live":
        return OPEN_METEO_LIVE_URL
    raise ValueError(f"mode must be one of {sorted(_VALID_MODES)}; got {mode!r}")


def _build_hourly_param(
    endpoint: str,
    variables: tuple[str, ...] = _OM_VARIABLES_TO_FETCH,
) -> str:
    """Build the comma-separated ``hourly=...`` URL param.

    Previous Runs API: suffix every variable with ``_previous_day1``
    (Day-1 lookback — the primary Phase 20 target).
    Single Runs / Seamless: no suffix (exact-cycle / seamless stream).
    """
    if endpoint == OPEN_METEO_PREVIOUS_RUNS_URL:
        return ",".join(f"{v}_previous_day1" for v in variables)
    # Single Runs / Seamless / Live: bare variable names (no suffix).
    return ",".join(variables)


def _parse_value(value: Any) -> float | None:
    """Convert an Open-Meteo cell to float | None.

    Open-Meteo serves ``null`` for missing data (no ``"M"`` sentinel like IEM).
    """
    if value is None:
        return None
    if isinstance(value, float) and pd.isna(value):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _parse_om_row(
    *,
    idx: int,
    time_iso: str,
    station: str,
    model: str,
    source: str,
    issued_at: datetime | None,
    retrieved_at: datetime,
    hourly_payload: dict[str, list],
) -> dict[str, Any]:
    """Project one ``(time, idx)`` tuple from the Open-Meteo response.

    Returns a dict matching ``schema.forecast.station.v1``. Open-Meteo
    extras are populated from the response; IEM MOS-only core columns
    (e.g. ``sky_cover_pct``) are left null.
    """
    valid_at = datetime.fromisoformat(time_iso.replace("Z", "+00:00"))
    if valid_at.tzinfo is None:
        valid_at = valid_at.replace(tzinfo=UTC)

    if issued_at is not None:
        forecast_hour = round((valid_at - issued_at).total_seconds() / 3600)
    else:
        # Seamless rows: forecast_hour undefined; set to 0 by convention.
        forecast_hour = 0

    row: dict[str, Any] = {
        "station": station,
        "issued_at": issued_at,
        "valid_at": valid_at,
        "forecast_hour": forecast_hour,
        "model": model,
        "source": source,
        # IEM-MOS-only column (Open-Meteo has no direct analog)
        "sky_cover_pct": None,
        "retrieved_at": retrieved_at,
    }

    # Populate every OM variable. The same `temperature_2m → temp_c`
    # mapping covers the IEM MOS core columns that Open-Meteo also
    # provides (temp_c, dew_point_c, wind_speed_ms, wind_dir_deg,
    # precip_probability).
    for om_var, column in _OM_VAR_TO_COLUMN.items():
        # Try both with and without _previous_day1 suffix to support
        # Previous Runs (suffix) and Single Runs / Seamless (no suffix).
        suffixed = f"{om_var}_previous_day1"
        if suffixed in hourly_payload:
            series = hourly_payload[suffixed]
        else:
            series = hourly_payload.get(om_var)

        value = None if series is None or idx >= len(series) else _parse_value(series[idx])

        # precipitation_probability comes in 0..100 percent; convert to
        # the 0..1 fraction the unified schema expects.
        if column == "precip_probability" and value is not None:
            value = value / 100.0

        row[column] = value

    return row


def _coerce_canonical_dtypes(df: pd.DataFrame) -> pd.DataFrame:
    """Pin every column to its canonical dtype for schema validation.

    Mirrors ``_iem_mos._coerce_canonical_dtypes`` semantics: nullable
    Int64/Float64/string dtypes so missing data does not collapse the
    column to ``object``.
    """
    if "station" in df.columns:
        df["station"] = df["station"].astype("string")
    if "model" in df.columns:
        df["model"] = df["model"].astype("string")
    if "source" in df.columns:
        df["source"] = df["source"].astype("string")

    for ts_col in ("issued_at", "valid_at", "retrieved_at"):
        if ts_col in df.columns:
            df[ts_col] = pd.to_datetime(df[ts_col], utc=True, errors="coerce").astype(
                "datetime64[ns, UTC]"
            )

    int_cols = (
        "forecast_hour",
        "wind_dir_deg",
        "sky_cover_pct",
        "cloud_cover_pct",
        "freezing_level_m",
        "visibility_m",
        "weather_code",
    )
    for col in int_cols:
        if col in df.columns:
            # Round fractional values before Int64 cast: pandas' safe-cast raises
            # TypeError on non-integer floats, which would silently drop rows when
            # the upstream API returns fractional values in an int-schema column.
            df[col] = pd.to_numeric(df[col], errors="coerce").round().astype("Int64")

    float_cols = (
        "temp_c",
        "dew_point_c",
        "wind_speed_ms",
        "precip_probability",
        "apparent_temp_c",
        "shortwave_radiation_wm2",
        "direct_radiation_wm2",
        "cape_jkg",
        "precipitation_mm",
        "surface_pressure_hpa",
        "pressure_msl_hpa",
        "snow_depth_m",
        "wind_gusts_ms",
    )
    for col in float_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").astype("Float64")

    return df


def _empty_df() -> pd.DataFrame:
    """Return an empty DataFrame with all canonical columns + dtypes."""
    df = pd.DataFrame(columns=list(_CANONICAL_COLUMNS))
    return _coerce_canonical_dtypes(df)


def _project_payload_to_dataframe(
    payload: dict[str, Any],
    *,
    station: str,
    model: str,
    endpoint: str,
    issued_at_str: str | None,
    retrieved_at: datetime,
) -> pd.DataFrame:
    """Project the Open-Meteo JSON response into a schema-conformant DataFrame."""
    hourly = payload.get("hourly", {})
    times = hourly.get("time", [])
    if not times:
        return _empty_df()

    if endpoint == OPEN_METEO_PREVIOUS_RUNS_URL:
        source = "open_meteo.previous_runs"
    elif endpoint == OPEN_METEO_SINGLE_RUNS_URL:
        source = "open_meteo.single_run"
    elif endpoint == OPEN_METEO_SEAMLESS_URL:
        source = "open_meteo.seamless"
    elif endpoint == OPEN_METEO_LIVE_URL:
        source = "open_meteo.live"
    else:
        raise RuntimeError(f"unexpected endpoint: {endpoint}")

    cycle_hours = CYCLE_HOURS[model]
    rows: list[dict[str, Any]] = []
    for idx, time_iso in enumerate(times):
        valid_at = datetime.fromisoformat(time_iso.replace("Z", "+00:00"))
        if valid_at.tzinfo is None:
            valid_at = valid_at.replace(tzinfo=UTC)

        if source == "open_meteo.previous_runs":
            issued_at_dt = issued_at_from_previous_day(valid_at, N=1, cycle_hours=cycle_hours)
        elif source == "open_meteo.single_run":
            assert issued_at_str is not None, "single_run requires issued_at"
            ts_str = issued_at_str
            if len(ts_str) == 16:  # "YYYY-MM-DDTHH:MM"
                ts_str = ts_str + ":00"
            issued_at_dt = datetime.fromisoformat(ts_str)
            if issued_at_dt.tzinfo is None:
                issued_at_dt = issued_at_dt.replace(tzinfo=UTC)
        elif source == "open_meteo.live":
            # Phase 20 D-06: cycle-math fallback. Metadata API integration
            # is a follow-up. Conservative lower bound = now - publish_lag,
            # floored to the model's cycle hours.
            from ._open_meteo_models import (
                PUBLISH_LAG,
                issued_at_from_live_cycle_math,
            )

            publish_lag = PUBLISH_LAG.get(model)
            if publish_lag is None:
                from datetime import timedelta as _td

                publish_lag = _td(hours=6)
            issued_at_dt = issued_at_from_live_cycle_math(
                now_utc=retrieved_at,
                publish_lag=publish_lag,
                cycle_hours=cycle_hours,
            )
        else:
            # seamless - null by design (cycle unrecoverable)
            issued_at_dt = None

        rows.append(
            _parse_om_row(
                idx=idx,
                time_iso=time_iso,
                station=station,
                model=model,
                source=source,
                issued_at=issued_at_dt,
                retrieved_at=retrieved_at,
                hourly_payload=hourly,
            )
        )

    df = pd.DataFrame(rows, columns=list(_CANONICAL_COLUMNS))
    df.attrs["source"] = source
    df.attrs["retrieved_at"] = retrieved_at
    return _coerce_canonical_dtypes(df)


def fetch_open_meteo(
    station: str,
    from_date: str,
    to_date: str,
    *,
    model: str,
    mode: Mode = "training",
    issued_at: str | None = None,
    allow_leakage: bool = False,
    variables: tuple[str, ...] | None = None,
    client: httpx.Client | None = None,
    timeout: float = HTTP_TIMEOUT,
) -> pd.DataFrame:
    """Fetch Open-Meteo forecasts for one station + one model.

    Args:
        station: ICAO code (e.g. ``"KNYC"``) or 3-letter US NWS code.
        from_date: ISO ``YYYY-MM-DD`` inclusive lower bound on ``valid_at``.
        to_date: ISO ``YYYY-MM-DD`` inclusive upper bound on ``valid_at``.
        model: One of :data:`OPEN_METEO_MODELS` (36 keys).
        mode: ``"training"`` (default) | ``"seamless"`` | ``"live"``.
        issued_at: ISO datetime (e.g. ``"2024-06-01T12:00"``) for Single
            Runs API. When ``mode='training'`` and ``issued_at`` is
            provided, the fetcher uses Single Runs API for byte-exact
            cycle provenance.
        allow_leakage: Required ``True`` when ``mode='seamless'``; raises
            :class:`OpenMeteoSeamlessLeakageError` otherwise.
        variables: Subset of :data:`_OM_VARIABLES_TO_FETCH` to request.
            ``None`` (default) requests all 18. Unknown names raise
            :class:`ValueError` before any HTTP request.
        client: Optional :class:`httpx.Client` (test-injection seam).
        timeout: Per-request timeout in seconds.

    Returns:
        DataFrame matching ``schema.forecast.station.v1``. Empty DataFrame
        (with canonical columns + dtypes) on 404 or empty response.

    Raises:
        ValueError: unknown model, unknown mode, unknown station, or unknown
            variable name (checked before any HTTP request).
        OpenMeteoSeamlessLeakageError: ``mode='seamless'`` without
            ``allow_leakage=True``. Raised BEFORE any HTTP request.
        NotImplementedError: ``mode='live'`` (deferred to PLAN-05).
    """
    vars_to_fetch = _validate_variables(variables)

    if model not in OPEN_METEO_MODELS:
        raise ValueError(
            f"model must be one of {sorted(OPEN_METEO_MODELS)[:5]}... "
            f"(total {len(OPEN_METEO_MODELS)} supported); got {model!r}"
        )
    if mode not in _VALID_MODES:
        raise ValueError(f"mode must be one of {sorted(_VALID_MODES)}; got {mode!r}")

    endpoint = _dispatch_endpoint(
        mode, allow_leakage=allow_leakage, model=model, issued_at=issued_at
    )

    lat, lon = _station_to_lat_lon(station)

    # Chunk date ranges >14 days for every endpoint that bills by start_date/
    # end_date window (Previous Runs, Seamless, Live) — keeps per-call weighted
    # cost low and avoids the free-tier rate limit (#64). Single Runs is the one
    # exception: it sends only run= and returns a fixed ~168h horizon, so it
    # stays a single call (codex P2).
    if endpoint == OPEN_METEO_SINGLE_RUNS_URL:
        chunks = [(from_date, to_date)]
    else:
        chunks = _chunk_date_range(from_date, to_date)

    close_client = client is None
    if client is None:
        client = httpx.Client(timeout=timeout)

    frames: list[pd.DataFrame] = []
    try:
        for chunk_from, chunk_to in chunks:
            params: dict[str, Any] = {
                "latitude": lat,
                "longitude": lon,
                "models": model,
                "hourly": _build_hourly_param(endpoint, vars_to_fetch),
                "timezone": "UTC",
                "timeformat": "iso8601",
            }
            if endpoint == OPEN_METEO_SINGLE_RUNS_URL:
                # Single-Runs API rejects start_date/end_date; use run= only.
                # The response contains the full horizon (up to 168 h); we clip
                # to [from_date, to_date] after parsing (see below).
                params["run"] = issued_at
            else:
                params["start_date"] = chunk_from
                params["end_date"] = chunk_to

            retrieved_at = datetime.now(UTC)
            payload: dict[str, Any] = {}
            for attempt in range(_MAX_RETRIES + 1):
                try:
                    resp = client.get(endpoint, params=params)
                    resp.raise_for_status()
                    payload = resp.json()
                    break
                except httpx.HTTPStatusError as exc:
                    status = getattr(exc.response, "status_code", None)
                    if status == 404:
                        log.debug("open_meteo 404 on %s; skipping", endpoint)
                        payload = {}
                        break
                    if status == 429 and attempt < _MAX_RETRIES:
                        retry_after = _parse_retry_after_seconds(
                            exc.response.headers.get("Retry-After")
                        )
                        sleep_for = max(retry_after, _OM_POLITE_DELAY_S * (attempt + 1))
                        log.warning(
                            "open_meteo 429 — sleeping %.1fs (attempt %d)",
                            sleep_for,
                            attempt + 1,
                        )
                        time.sleep(sleep_for)
                        continue
                    raise

            # Weight-aware polite delay scales with per-call cost. Single-Runs
            # ignores start_date/end_date and returns a FIXED ~168h horizon from
            # run=, so its cost uses that fixed span — not the requested window.
            # Otherwise an exact-cycle multi-month/year request would sleep for
            # tens of seconds after a single API call (codex P2).
            if endpoint == OPEN_METEO_SINGLE_RUNS_URL:
                num_days = _OM_SINGLE_RUNS_HORIZON_DAYS
            else:
                num_days = (date.fromisoformat(chunk_to) - date.fromisoformat(chunk_from)).days + 1
            cost = _weighted_call_cost(len(vars_to_fetch), num_days)
            time.sleep(_OM_POLITE_DELAY_S * ceil(cost))

            if payload:
                frames.append(
                    _project_payload_to_dataframe(
                        payload,
                        station=station,
                        model=model,
                        endpoint=endpoint,
                        issued_at_str=issued_at,
                        retrieved_at=retrieved_at,
                    )
                )
    finally:
        if close_client:
            client.close()

    if not frames:
        return _empty_df()

    df = pd.concat(frames, ignore_index=True) if len(frames) > 1 else frames[0]

    # Single-Runs returns the full horizon from run=; clip to requested window.
    if endpoint == OPEN_METEO_SINGLE_RUNS_URL and not df.empty:
        lo = pd.Timestamp(from_date, tz="UTC")
        hi = pd.Timestamp(to_date, tz="UTC") + pd.Timedelta(days=1)
        df = df[(df["valid_at"] >= lo) & (df["valid_at"] < hi)]

    # Restamp source-identity / fetch provenance (issue #64 / codex P2):
    # BOTH pd.concat (multi-chunk Previous-Runs windows >14 days) and boolean
    # row-masking (the Single-Runs clip above) drop ``df.attrs``. Each per-chunk
    # frame already carries attrs["source"]/["retrieved_at"] from
    # _project_payload_to_dataframe; without re-stamping, chunked/clipped frames
    # return rows lacking the documented provenance and fail
    # validate_dataframe(...)'s source_attr_required check. Use the latest chunk
    # retrieved_at as the combined-frame timestamp.
    df.attrs["source"] = frames[0].attrs.get("source")
    _retrieved = [
        f.attrs.get("retrieved_at") for f in frames if f.attrs.get("retrieved_at") is not None
    ]
    if _retrieved:
        df.attrs["retrieved_at"] = max(_retrieved)

    return df


__all__ = [
    "OPEN_METEO_PREVIOUS_RUNS_URL",
    "OPEN_METEO_SEAMLESS_URL",
    "OPEN_METEO_SINGLE_RUNS_URL",
    "fetch_open_meteo",
]

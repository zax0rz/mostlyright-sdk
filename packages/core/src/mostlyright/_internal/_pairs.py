# Lifted from monorepo-v0.14.1/src/mostlyright/pairs.py (full file minus TOON imports/function)
# Source SHA: e78eed5de3254267304f426c051063e974b7188b
#   (file blob sha; tag SHA is 514fcdab227e845145ca32b989355647466231d9)
# Lift date: 2026-05-22
# Modifications:
#   - import-rename: ``from mostlyright.snapshot`` -> ``from mostlyright.snapshot``
#   - removed ``pairs_to_toon`` function and the ``from mostlyright._toon import ...``
#     import it required (TOON serialization deferred to Phase 2 CORE-05; ``research()``
#     emits DataFrame or list[dict] only in Phase 1).
#   - tz_override fix (codex iter-6 F1, 2026-05-22): ``market_close_utc`` accepts
#     an optional ``tz_override`` and threads it into ``_lst_offset`` so the
#     market-close calculation matches the settlement-window calculation for
#     custom stations OR stations passed with an override. v0.14.1's pairs.py
#     silently dropped the override here, causing ``_lst_offset(station)`` to
#     raise ``ValueError`` for unknown stations before ``settlement_window_utc``
#     could honor the override, and yielding inconsistent cutoffs for known
#     stations with an override. ``build_pairs_row`` now passes the kwarg
#     through. **Parity impact:** zero - all 5 Phase 1 parity fixtures use
#     registry stations with ``tz_override=None``, so the only call sites that
#     change behavior are previously-broken paths (unknown station + override),
#     not the byte-equivalent parity cases.
#   - no other logic changes; build_pairs / _obs_aggregates / _select_best_run /
#     _aggregate_fcst_temps_* / date_range / pairs_to_dataframe surface remains
#     byte-faithful to v0.14.1.
"""Pre-joined forecast + observation + settlement DataFrame keyed by date.

pairs() returns one row per settlement date, joining:
  - observation aggregates (high/low/mean temp, precip, etc.) from METARs
  - climate record (NWS CLI high/low - the Kalshi settlement source)
  - forecast (most-recent model run before market_close_utc, if available)

This is the primary training/feature surface for AI settlement models.

Forecast join:
  - IEM MOS records (`forecast.json`) have `issued_at`; grouped by issued_at to
    pick the most-recent run before market close, then temperature_f values for
    valid_at timestamps within the settlement window are aggregated (max/min).
  - Open-Meteo records (`forecast_series.json`) have no issued_at; all records
    in the settlement window are used. temperature_c is converted to F.
  - If both are available, IEM MOS is preferred. Open-Meteo used as fallback.
  - If forecast data is unavailable, forecast columns are None - the row is
    still returned.

Kalshi markets typically close at 4:30 PM ET (21:30 UTC EST / 20:30 UTC EDT).
We use LST (standard offset) so the UTC close time is consistent year-round.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
from typing import Any

from mostlyright.snapshot import (
    _lst_offset,
    _station_code_normalized,
    settlement_window_utc,
)

# Kalshi market typical close time: 4:30 PM LST
_MARKET_CLOSE_HOUR_LST = 16  # 4 PM
_MARKET_CLOSE_MINUTE_LST = 30  # :30


def market_close_utc(date_str: str, station: str, *, tz_override: str | None = None) -> datetime:
    """Return the UTC time of the Kalshi market close for a settlement date.

    Kalshi NHIGH/NLOW markets typically close at 4:30 PM ET on the day of
    settlement. We use LST (ignoring DST) so the UTC time is consistent.

    Args:
        date_str: Settlement date (YYYY-MM-DD in LST).
        station: Station code.
        tz_override: IANA timezone name override for stations not in the
            known registry (matches ``settlement_window_utc``'s contract;
            kwarg threaded here so both the cutoff and the window agree).
            v0.14.1 pairs.py dropped this argument; iter-6 F1 restores it.

    Returns:
        Aware UTC datetime of market close (4:30 PM LST expressed in UTC).
    """
    from datetime import date as _date

    offset = _lst_offset(station, tz_override=tz_override)
    lst_date = _date.fromisoformat(date_str)
    market_close_lst = datetime(
        lst_date.year,
        lst_date.month,
        lst_date.day,
        _MARKET_CLOSE_HOUR_LST,
        _MARKET_CLOSE_MINUTE_LST,
    )
    # Convert LST -> UTC: subtract offset (offset is negative -> add magnitude)
    return (market_close_lst - offset).replace(tzinfo=UTC)


def _obs_aggregates(observations: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate METAR observations into daily summary features.

    Returns a dict of aggregated values (or None if no data):
      - obs_high_f, obs_low_f: max/min temp_f
      - obs_mean_f: mean temp_f
      - obs_mean_dewpoint_f: mean dewpoint_f
      - obs_max_wind_kt: max wind_speed_kt
      - obs_max_gust_kt: max wind_gust_kt
      - obs_total_precip_in: sum of precip_1hr_inches
      - obs_count: number of observations
    """
    if not observations:
        return {
            "obs_high_f": None,
            "obs_low_f": None,
            "obs_mean_f": None,
            "obs_mean_dewpoint_f": None,
            "obs_max_wind_kt": None,
            "obs_max_gust_kt": None,
            "obs_total_precip_in": None,
            "obs_count": 0,
        }

    def _collect(key: str) -> list[float]:
        """Extract non-None numeric values for ``key`` - narrowed to ``list[float]``
        so static type checkers see that ``max/min/sum`` are safe.
        """
        out: list[float] = []
        for o in observations:
            v = o.get(key)
            if v is not None:
                out.append(v)
        return out

    temps = _collect("temp_f")
    dewps = _collect("dewpoint_f")
    winds = _collect("wind_speed_kt")
    gusts = _collect("wind_gust_kt")
    precips = _collect("precip_1hr_inches")

    def _mean(vals: list[float]) -> float | None:
        return sum(vals) / len(vals) if vals else None

    return {
        "obs_high_f": max(temps) if temps else None,
        "obs_low_f": min(temps) if temps else None,
        "obs_mean_f": _mean(temps),
        "obs_mean_dewpoint_f": _mean(dewps),
        "obs_max_wind_kt": max(winds) if winds else None,
        "obs_max_gust_kt": max(gusts) if gusts else None,
        "obs_total_precip_in": sum(precips) if precips else None,
        "obs_count": len(observations),
    }


def _select_best_run(
    all_records: list[dict[str, Any]],
    before_utc: datetime,
) -> tuple[str | None, list[dict[str, Any]]]:
    """Select all hourly records from the most-recent issued_at <= before_utc.

    Groups records by issued_at (model run timestamp) and returns the entire
    set of records for the latest eligible run. Used for IEM MOS forecasts
    which publish multiple runs per day (00Z, 06Z, 12Z, 18Z).

    Args:
        all_records: All forecast records for the date (each must have issued_at).
        before_utc: Cutoff - typically market close UTC.

    Returns:
        (best_issued_at, records_for_that_run). Returns (None, []) if no run
        was issued before the cutoff.
    """
    cutoff_iso = before_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
    runs: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in all_records:
        issued = r.get("issued_at") or "0000-00-00T00:00:00Z"
        if issued <= cutoff_iso:
            runs[issued].append(r)
    if not runs:
        return None, []
    best_issued = max(runs)
    return best_issued, runs[best_issued]


def _aggregate_fcst_temps_iem(
    run_records: list[dict[str, Any]],
    window_start_iso: str,
    window_end_iso: str,
) -> tuple[float | None, float | None]:
    """Aggregate IEM MOS hourly temperature_f over the settlement window.

    Args:
        run_records: All records from the selected model run.
        window_start_iso: ISO 8601 UTC string of settlement window start.
        window_end_iso: ISO 8601 UTC string of settlement window end.

    Returns:
        (fcst_high_f, fcst_low_f) or (None, None) if no records in window.
    """
    temps = [
        r["temperature_f"]
        for r in run_records
        if r.get("temperature_f") is not None
        and window_start_iso <= r.get("valid_at", "") <= window_end_iso
    ]
    return (max(temps), min(temps)) if temps else (None, None)


def _aggregate_fcst_temps_openmeteo(
    run_records: list[dict[str, Any]],
    window_start_iso: str,
    window_end_iso: str,
) -> tuple[float | None, float | None]:
    """Aggregate Open-Meteo hourly temperature_c (-> F) over the settlement window.

    Open-Meteo stores temperature in Celsius. Conversion: F = C * 9/5 + 32.

    Args:
        run_records: All Open-Meteo hourly records for the date.
        window_start_iso: ISO 8601 UTC string of settlement window start.
        window_end_iso: ISO 8601 UTC string of settlement window end.

    Returns:
        (fcst_high_f, fcst_low_f) or (None, None) if no records in window.
    """
    temps_f = [
        r["temperature_c"] * 9 / 5 + 32
        for r in run_records
        if r.get("temperature_c") is not None
        and window_start_iso <= r.get("valid_at", "") <= window_end_iso
    ]
    return (max(temps_f), min(temps_f)) if temps_f else (None, None)


def build_pairs_row(
    date_str: str,
    station: str,
    observations: list[dict[str, Any]],
    climate: dict[str, Any] | None,
    forecasts: list[dict[str, Any]] | None,
    *,
    forecast_model: str | None = None,
    tz_override: str | None = None,
    nwp_forecasts_by_model: dict[str, list[dict[str, Any]] | None] | None = None,
) -> dict[str, Any]:
    """Build one row of the pairs DataFrame for a single settlement date.

    Args:
        date_str: Settlement date (YYYY-MM-DD in LST).
        station: Station code (normalized).
        observations: Raw observation dicts for the settlement window.
        climate: NWS CLI record for the date (or None). Must be a dict or None
            - non-dict values are treated as None.
        forecasts: All forecast records with valid_at (or None if unavailable).
            IEM MOS records have issued_at; Open-Meteo records do not.
        forecast_model: Filter IEM MOS records to this model before run
            selection. None = no filtering (best available run).
        tz_override: IANA timezone name override for stations not in the known
            timezone map (e.g. "America/Chicago" for a custom station).
        nwp_forecasts_by_model: PLAN-09 Mode 2 — per-model NWP forecast rows
            grouped by date. Keys are NWP model names (e.g. ``"hrrr"``);
            values are lists of canonical ``schema.forecast_nwp.v1`` row
            dicts for ``date_str`` (or None when the model returned nothing).
            For each populated model, the result row gains additive
            ``fcst_high_f_nwp_<model>`` + ``fcst_low_f_nwp_<model>`` columns
            (Kelvin → Fahrenheit). When None or empty, no per-model NWP
            columns are added — preserves the parity contract for
            ``include_forecast=False`` callers.

    Returns:
        Dict with keys: date, station, cli_high_f, cli_low_f, obs_*, fcst_*
        All fcst_* keys are always present (None when no forecast data).
        Optional ``fcst_*_nwp_<model>`` keys appear iff
        ``nwp_forecasts_by_model`` is populated for the date.
    """
    code = _station_code_normalized(station)
    obs_agg = _obs_aggregates(observations)
    # Iter-6 F1 fix: thread tz_override so the market-close cutoff matches
    # the settlement-window calculation a few lines below (and so custom
    # stations using an override do not crash inside _lst_offset).
    market_close = market_close_utc(date_str, code, tz_override=tz_override)

    # Climate: guard against non-dict (e.g. Observation object passed by mistake)
    climate_dict = climate if isinstance(climate, dict) else None

    # Forecast: always emit all fcst_* keys; None when data unavailable
    fcst: dict[str, Any] = {
        "fcst_high_f": None,
        "fcst_low_f": None,
        "fcst_model": None,
        "fcst_issued_at": None,
        "fcst_pop_6hr_pct": None,
        "fcst_qpf_6hr_in": None,
    }
    if forecasts is not None:
        win_start, win_end = settlement_window_utc(date_str, code, tz_override=tz_override)
        win_start_iso = win_start.strftime("%Y-%m-%dT%H:%M:%SZ")
        win_end_iso = win_end.strftime("%Y-%m-%dT%H:%M:%SZ")

        # Separate IEM MOS (has issued_at) from Open-Meteo (no issued_at)
        iem_records = [r for r in forecasts if r.get("issued_at")]
        om_records = [r for r in forecasts if not r.get("issued_at")]

        # Apply forecast_model filter to IEM MOS records before run selection.
        # Phase 17 Wave 4 iter-3 review HIGH: case-insensitive match because
        # _iem_mos.fetch_iem_mos emits ``model.upper()`` (e.g. ``"NBE"``)
        # while the user-facing kwarg is lowercase. A naive ``==`` filter
        # would drop every row and produce all-null forecast columns.
        if forecast_model is not None:
            target_model = forecast_model.upper()
            iem_records = [
                r
                for r in iem_records
                if (m := r.get("model")) is not None
                and str(m).upper() == target_model
            ]

        fcst_high: float | None = None
        fcst_low: float | None = None
        fcst_model: str | None = None
        fcst_issued: str | None = None
        fcst_pop: float | None = None
        fcst_qpf: float | None = None

        if iem_records:
            best_issued, run_records = _select_best_run(iem_records, market_close)
            if run_records:
                fcst_high, fcst_low = _aggregate_fcst_temps_iem(
                    run_records, win_start_iso, win_end_iso
                )
                fcst_model = next((r.get("model") for r in run_records if r.get("model")), None)
                fcst_issued = best_issued
                window_records = [
                    r for r in run_records if win_start_iso <= r.get("valid_at", "") <= win_end_iso
                ]
                pops = [
                    r["pop_6hr_pct"] for r in window_records if r.get("pop_6hr_pct") is not None
                ]
                fcst_pop = max(pops) if pops else None
                qpfs = [r["qpf_6hr_in"] for r in window_records if r.get("qpf_6hr_in") is not None]
                fcst_qpf = sum(qpfs) if qpfs else None

        # Fall back to Open-Meteo if IEM MOS yielded no temperature data
        if fcst_high is None and om_records:
            fcst_high, fcst_low = _aggregate_fcst_temps_openmeteo(
                om_records, win_start_iso, win_end_iso
            )
            fcst_model = next((r.get("model") for r in om_records if r.get("model")), "open-meteo")
            window_om = [
                r for r in om_records if win_start_iso <= r.get("valid_at", "") <= win_end_iso
            ]
            probs = [
                r["precipitation_probability_pct"]
                for r in window_om
                if r.get("precipitation_probability_pct") is not None
            ]
            fcst_pop = max(probs) if probs else None

        fcst.update(
            {
                "fcst_high_f": fcst_high,
                "fcst_low_f": fcst_low,
                "fcst_model": fcst_model,
                "fcst_issued_at": fcst_issued,
                "fcst_pop_6hr_pct": fcst_pop,
                "fcst_qpf_6hr_in": fcst_qpf,
            }
        )

    # PLAN-09 Mode 2: per-model NWP fcst_* columns. Additive — keys only
    # appear when ``nwp_forecasts_by_model`` is populated for the date,
    # so the include_forecast=False parity contract (NO fcst_*_nwp_*
    # columns) is preserved by callers passing ``None``.
    nwp_extra: dict[str, Any] = {}
    if nwp_forecasts_by_model:
        for nwp_model, nwp_rows in nwp_forecasts_by_model.items():
            if not nwp_rows:
                continue
            temps_k: list[float] = []
            for r in nwp_rows:
                v = r.get("temp_k_2m")
                if v is None:
                    continue
                try:
                    f = float(v)
                except (TypeError, ValueError):
                    continue
                # Skip NaN sentinel values forecast_nwp emits when a model
                # lacks the temp variable.
                if f != f:  # NaN check without importing math
                    continue
                temps_k.append(f)
            if not temps_k:
                continue
            high_k = max(temps_k)
            low_k = min(temps_k)
            nwp_extra[f"fcst_high_f_nwp_{nwp_model}"] = (high_k - 273.15) * 9.0 / 5.0 + 32.0
            nwp_extra[f"fcst_low_f_nwp_{nwp_model}"] = (low_k - 273.15) * 9.0 / 5.0 + 32.0

    return {
        "date": date_str,
        "station": code,
        # Settlement source (NWS CLI - Kalshi authoritative)
        "cli_high_f": climate_dict.get("high_temp_f") if climate_dict else None,
        "cli_low_f": climate_dict.get("low_temp_f") if climate_dict else None,
        "cli_report_type": climate_dict.get("report_type") if climate_dict else None,
        # METAR aggregates
        **obs_agg,
        # Forecast (stub if unavailable)
        **fcst,
        # PLAN-09 Mode 2 NWP per-model columns (empty unless populated)
        **nwp_extra,
        # Metadata
        "market_close_utc": market_close.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def date_range(from_date: str, to_date: str) -> list[str]:
    """Return inclusive list of YYYY-MM-DD strings from from_date to to_date.

    Returns empty list when from_date > to_date.
    """
    from datetime import date as _date
    from datetime import timedelta as _td

    start = _date.fromisoformat(from_date)
    end = _date.fromisoformat(to_date)
    result: list[str] = []
    current = start
    while current <= end:
        result.append(current.isoformat())
        current += _td(days=1)
    return result


def pairs_to_dataframe(rows: list[dict[str, Any]]) -> Any:
    """Convert pairs rows to a Pandas DataFrame indexed by date.

    Requires pandas (soft dependency).
    """
    try:
        import pandas as pd
    except ImportError:
        raise ImportError(
            "pandas is required for DataFrame output. Install with: pip install mostlyright[parquet]"
        ) from None

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    if "date" in df.columns:
        # PANDAS3: input is always ISO YYYY-MM-DD strings produced by
        # date_range. Explicit format= locks parsing semantics across
        # pandas 2.x/3.x and avoids the inference-shift risk documented
        # in the pandas 3.0 whatsnew §"Datetime resolution inference".
        # Parity impact: zero — the 5 v0.1.0 fixtures use the same
        # YYYY-MM-DD shape, so format='%Y-%m-%d' is a precision tightening,
        # not a behaviour change.
        df["date"] = pd.to_datetime(df["date"], format="%Y-%m-%d")
        df = df.set_index("date").sort_index()
    return df


def build_pairs(
    station: str,
    dates: list[str],
    observations_by_date: dict[str, list[dict[str, Any]]],
    climate_by_date: dict[str, dict[str, Any] | None],
    forecasts_by_date: dict[str, list[dict[str, Any]] | None] | None = None,
    *,
    forecast_model: str | None = None,
    tz_override: str | None = None,
    nwp_forecasts_by_model_date: (dict[str, dict[str, list[dict[str, Any]] | None]] | None) = None,
) -> list[dict[str, Any]]:
    """Build the pairs DataFrame as a list of row dicts.

    Args:
        station: Station code.
        dates: List of settlement dates (YYYY-MM-DD, LST), in order.
        observations_by_date: Dict mapping date -> list of raw observation dicts.
        climate_by_date: Dict mapping date -> climate record (or None).
        forecasts_by_date: Dict mapping date -> list of forecast records.
            None means forecast data is unavailable (stub). Records with
            issued_at are treated as IEM MOS; records without as Open-Meteo.
        forecast_model: Filter IEM MOS records to this model name before run
            selection. None (default) = no filtering (best available run).
        nwp_forecasts_by_model_date: PLAN-09 Mode 2 — outer dict keyed by
            NWP model name; inner dict keyed by date_iso → list of canonical
            NWP forecast row dicts for that date. None (default) = no NWP
            wiring (parity-preserving — no fcst_*_nwp_* columns emitted).

    Returns:
        List of row dicts, one per date. Pass to pandas.DataFrame() for
        a properly-keyed DataFrame.
    """
    rows = []
    for date in dates:
        obs = observations_by_date.get(date, [])
        climate = climate_by_date.get(date)
        forecasts = (forecasts_by_date or {}).get(date) if forecasts_by_date is not None else None
        # PLAN-09 Mode 2: pull the per-date slice for each NWP model
        # registered in the outer dict. Pass None when no models are wired
        # so build_pairs_row's parity contract (no fcst_*_nwp_* columns
        # when nwp_forecasts_by_model is None or empty) is preserved.
        nwp_by_model_for_date: dict[str, list[dict[str, Any]] | None] | None
        if nwp_forecasts_by_model_date:
            nwp_by_model_for_date = {
                m: by_date.get(date) for m, by_date in nwp_forecasts_by_model_date.items()
            }
        else:
            nwp_by_model_for_date = None
        rows.append(
            build_pairs_row(
                date,
                station,
                obs,
                climate,
                forecasts,
                forecast_model=forecast_model,
                tz_override=tz_override,
                nwp_forecasts_by_model=nwp_by_model_for_date,
            )
        )
    return rows

"""GHCNh PSV parser — parse pipe-separated value files from NCEI's GHCNh dataset.

Applies Quality_Code filtering (raw-only), extracts station codes,
converts units, and emits observation dicts matching specs/observation.json.
"""

from __future__ import annotations

import csv
import math
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from tradewinds._internal._bounds import (
    MAX_RAW_METAR_LEN,
    MAX_VISIBILITY_MILES,
    MAX_WX_CODES_LEN,
    MAX_YEAR,
    MIN_YEAR,
    SKY_BASE_MAX_FT,
    SLP_MAX_MB,
    SLP_MIN_MB,
    STATION_CODE_RE,
    TEMP_MAX_C,
    TEMP_MIN_C,
    bounded_float,
    bounded_float_min,
    bounded_int,
)
from tradewinds._internal._convert import celsius_to_fahrenheit, hpa_to_inhg
from tradewinds.weather._awc import icao_to_station_code, map_cloud_cover

_MS_TO_KT = 1 / 0.514444
_KM_TO_MI = 1 / 1.60934
_M_TO_FT = 3.28084
_MM_TO_IN = 1 / 25.4
_CM_TO_IN = 1 / 2.54

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z?$")
_ALLOWED_QC = frozenset({"0", "1", "4", "5"})

# Source_Station_ID columns to try for station code extraction (priority order)
_SSID_COLUMNS = (
    "temperature_Source_Station_ID",
    "dew_point_temperature_Source_Station_ID",
    "wind_speed_Source_Station_ID",
    "wind_direction_Source_Station_ID",
    "sea_level_pressure_Source_Station_ID",
    "altimeter_Source_Station_ID",
    "visibility_Source_Station_ID",
    "sky_cover_summation_1_Source_Station_ID",
    "sky_cover_summation_2_Source_Station_ID",
    "sky_cover_summation_3_Source_Station_ID",
    "sky_cover_summation_4_Source_Station_ID",
)


def _safe_float(val: str) -> float | None:
    """Parse string to float. Empty/NA -> None, non-finite -> None."""
    if not val or val == "NA":
        return None
    try:
        f = float(val)
        return f if math.isfinite(f) else None
    except (ValueError, OverflowError):
        return None


def _safe_int(val: str) -> int | None:
    """Parse string to int via float. Empty/NA -> None."""
    f = _safe_float(val)
    return round(f) if f is not None else None


def _is_qc_accepted(qc: str) -> bool:
    """Check if a Quality_Code value passes raw-only filtering.

    Accepted: {0, 1, 4, 5} or empty (no QC info).
    Rejected: {2, 3, 6, 7} and letter flags {I, P, R, U}.
    """
    stripped = qc.strip()
    if not stripped:
        return True
    return stripped in _ALLOWED_QC


def _parse_sky_cover(val: str) -> str | None:
    """Parse sky_cover_summation value like 'SCT:04;' -> 'SCT'."""
    if not val:
        return None
    code = val.split(":")[0] if ":" in val else val.rstrip(";")
    return map_cloud_cover(code)


def _parse_sky_baseht(val: str) -> int | None:
    """Parse sky_cover_summation_baseht (meters) -> feet as integer."""
    meters = _safe_float(val)
    if meters is None or meters < 0:
        return None
    feet = round(meters * _M_TO_FT)
    return feet if feet <= SKY_BASE_MAX_FT else None


def _parse_weather_codes(row: dict[str, str]) -> str | None:
    """Parse pres_wx_AW{1-3} columns -> weather codes string.

    GHCNh format: "TS:90", "+RA:02", "BR:10" (METAR text + WMO AW code).
    Extracts METAR text before colon. Filters bare numeric WMO codes.
    """
    codes: list[str] = []
    for i in range(1, 4):
        val = row.get(f"pres_wx_AW{i}", "")
        if not val:
            continue
        # Codex W3A P2: honor per-column Quality_Code filtering. GHCNh uses
        # the same convention as other variables — rejected codes are 3 or P.
        # Without this, flagged present-weather observations pass through even
        # though we filter the matching numeric variables.
        qc = row.get(f"pres_wx_AW{i}_Quality_Code", "")
        if qc and qc.strip() in ("3", "P"):
            continue
        code = val.split(":")[0] if ":" in val else val
        if code and not code.lstrip("+-").isdigit():
            codes.append(code)
    if not codes:
        return None
    result = " ".join(codes)
    return result[:MAX_WX_CODES_LEN]


def ghcnh_station_to_code(source_station_id: str) -> str | None:
    """Extract station code from GHCNh Source_Station_ID.

    "ICAO-KJFK" -> "JFK" (strip prefix, apply ICAO->station conversion).
    "744860-94789" -> None (WMO format, can't extract).
    """
    if not source_station_id or not source_station_id.startswith("ICAO-"):
        return None
    icao = source_station_id[5:]
    code = icao_to_station_code(icao)
    if STATION_CODE_RE.match(code):
        return code
    return None


def _extract_station_code(row: dict[str, str]) -> str | None:
    """Try multiple Source_Station_ID columns to extract station code."""
    for col in _SSID_COLUMNS:
        ssid = row.get(col, "")
        code = ghcnh_station_to_code(ssid)
        if code is not None:
            return code
    return None


def parse_ghcnh_row(row: dict[str, str]) -> dict[str, Any] | None:
    """Parse a single GHCNh PSV row to observation schema dict.

    Takes a dict from csv.DictReader (pipe-delimited). Returns an observation
    dict with exactly 30 fields, or None if the row should be skipped.

    Returns None when:
    - Station code cannot be extracted from any Source_Station_ID column
    - DATE is missing
    - ALL key variables (temp, dewpoint, wind_speed, SLP) fail Quality_Code
    """
    station_code = _extract_station_code(row)
    if station_code is None:
        return None

    date_str = row.get("DATE", "")
    if not date_str or not _DATE_RE.match(date_str):
        return None
    try:
        datetime.fromisoformat(date_str.rstrip("Z"))
    except ValueError:
        return None
    year = int(date_str[:4])
    if not (MIN_YEAR <= year <= MAX_YEAR):
        return None
    observed_at = date_str if date_str.endswith("Z") else date_str + "Z"

    report_type = row.get("temperature_Report_Type", "")
    observation_type = "SPECI" if report_type == "FM16" else "METAR"

    # Per-variable Quality_Code filtering
    temp_ok = _is_qc_accepted(row.get("temperature_Quality_Code", ""))
    dewp_ok = _is_qc_accepted(row.get("dew_point_temperature_Quality_Code", ""))
    wspd_ok = _is_qc_accepted(row.get("wind_speed_Quality_Code", ""))
    wdir_ok = _is_qc_accepted(row.get("wind_direction_Quality_Code", ""))
    wgust_ok = _is_qc_accepted(row.get("wind_gust_Quality_Code", ""))
    slp_ok = _is_qc_accepted(row.get("sea_level_pressure_Quality_Code", ""))
    altim_ok = _is_qc_accepted(row.get("altimeter_Quality_Code", ""))
    vis_ok = _is_qc_accepted(row.get("visibility_Quality_Code", ""))
    precip_ok = _is_qc_accepted(row.get("precipitation_Quality_Code", ""))
    snow_ok = _is_qc_accepted(row.get("snow_depth_Quality_Code", ""))

    if not any((temp_ok, dewp_ok, wspd_ok, slp_ok)):
        return None

    # Temperature (no rounding, bounded)
    temp_c = (
        bounded_float(
            _safe_float(row.get("temperature", "")),
            TEMP_MIN_C,
            TEMP_MAX_C,
            field="temp_c",
        )
        if temp_ok
        else None
    )
    dewp_c = (
        bounded_float(
            _safe_float(row.get("dew_point_temperature", "")),
            TEMP_MIN_C,
            TEMP_MAX_C,
            field="dewpoint_c",
        )
        if dewp_ok
        else None
    )
    temp_f = celsius_to_fahrenheit(temp_c)
    dewp_f = celsius_to_fahrenheit(dewp_c)

    # Wind (m/s -> kt, rounded to integer, bounded by schema)
    wind_dir = bounded_int(_safe_int(row.get("wind_direction", "")), 0, 360) if wdir_ok else None
    wind_speed_ms = _safe_float(row.get("wind_speed", "")) if wspd_ok else None
    wind_gust_ms = _safe_float(row.get("wind_gust", "")) if wgust_ok else None
    wind_speed_kt = bounded_int(
        round(wind_speed_ms * _MS_TO_KT) if wind_speed_ms is not None else None,
        0,
        200,
    )
    wind_gust_kt = bounded_int(
        round(wind_gust_ms * _MS_TO_KT) if wind_gust_ms is not None else None,
        0,
        250,
    )

    # Pressure
    slp = _safe_float(row.get("sea_level_pressure", "")) if slp_ok else None
    if slp is not None and not (SLP_MIN_MB <= slp <= SLP_MAX_MB):
        slp = None
    altim_hpa = _safe_float(row.get("altimeter", "")) if altim_ok else None
    altim_inhg = hpa_to_inhg(altim_hpa)

    # Visibility (km -> miles, non-negative)
    vis_km = _safe_float(row.get("visibility", "")) if vis_ok else None
    vis_miles: float | None = None
    if vis_km is not None and vis_km >= 0:
        vis_miles = min(vis_km * _KM_TO_MI, MAX_VISIBILITY_MILES)

    # Precipitation (mm -> inches, non-negative)
    precip_mm = _safe_float(row.get("precipitation", "")) if precip_ok else None
    precip_inches: float | None = None
    if precip_mm is not None:
        precip_inches = bounded_float_min(precip_mm * _MM_TO_IN, 0.0)

    # Snow depth (cm -> inches, non-negative)
    snow_cm = _safe_float(row.get("snow_depth", "")) if snow_ok else None
    snow_inches: float | None = None
    if snow_cm is not None:
        snow_inches = bounded_float_min(snow_cm * _CM_TO_IN, 0.0)

    # Sky cover (summation layers 1-4, with QC filtering)
    sky_covers: list[str | None] = []
    sky_bases: list[int | None] = []
    for i in range(1, 5):
        cov_qc = _is_qc_accepted(row.get(f"sky_cover_summation_{i}_Quality_Code", ""))
        base_qc = _is_qc_accepted(row.get(f"sky_cover_summation_baseht_{i}_Quality_Code", ""))
        sky_covers.append(
            _parse_sky_cover(row.get(f"sky_cover_summation_{i}", "")) if cov_qc else None
        )
        sky_bases.append(
            _parse_sky_baseht(row.get(f"sky_cover_summation_baseht_{i}", "")) if base_qc else None
        )

    # Weather codes
    weather_codes = _parse_weather_codes(row)

    # Raw METAR from REM column. Codex W3A P2: GHCNh wraps the raw METAR
    # in a "METxxxxMM/DD/YY HH:MM:SS METAR <icao> ..." prefix. Extract just
    # the METAR/SPECI substring so raw_metar starts with "METAR" or "SPECI"
    # per the observation schema contract.
    rem = row.get("REM", "")
    raw_metar: str | None = None
    if rem:
        # Find the first occurrence of "METAR " or "SPECI " and slice from there.
        idx_metar = rem.find("METAR ")
        idx_speci = rem.find("SPECI ")
        if idx_metar >= 0 and (idx_speci < 0 or idx_metar < idx_speci):
            cleaned = rem[idx_metar:]
        elif idx_speci >= 0:
            cleaned = rem[idx_speci:]
        else:
            cleaned = rem  # No METAR/SPECI marker — fall back to raw REM
        # Trim trailing GHCNh annotations like " (RR)" if present at end
        raw_metar = cleaned[:MAX_RAW_METAR_LEN]

    return {
        "station_code": station_code,
        "observed_at": observed_at,
        "observation_type": observation_type,
        "source": "ghcnh",
        "temp_c": temp_c,
        "dewpoint_c": dewp_c,
        "temp_f": temp_f,
        "dewpoint_f": dewp_f,
        "wind_dir_degrees": wind_dir,
        "wind_speed_kt": wind_speed_kt,
        "wind_gust_kt": wind_gust_kt,
        "altimeter_inhg": altim_inhg,
        "sea_level_pressure_mb": slp,
        "sky_cover_1": sky_covers[0],
        "sky_base_1_ft": sky_bases[0],
        "sky_cover_2": sky_covers[1],
        "sky_base_2_ft": sky_bases[1],
        "sky_cover_3": sky_covers[2],
        "sky_base_3_ft": sky_bases[2],
        "sky_cover_4": sky_covers[3],
        "sky_base_4_ft": sky_bases[3],
        "visibility_miles": vis_miles,
        "weather_codes": weather_codes,
        "precip_1hr_inches": precip_inches,
        "peak_wind_gust_kt": None,
        "peak_wind_dir": None,
        "peak_wind_time": None,
        "snow_depth_inches": snow_inches,
        "qc_field": None,
        "raw_metar": raw_metar,
    }


def parse_ghcnh_file(path: Path) -> list[dict[str, Any]]:
    """Read a GHCNh PSV file and return list of valid observation dicts.

    Skips rows rejected by Quality_Code filtering or missing station codes.
    """
    observations: list[dict[str, Any]] = []
    with open(path, newline="", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f, delimiter="|")
        for row in reader:
            obs = parse_ghcnh_row(row)
            if obs is not None:
                observations.append(obs)
    return observations

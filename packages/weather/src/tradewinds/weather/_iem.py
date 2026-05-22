"""IEM METAR CSV parser — parse comma-separated files from Iowa Environmental Mesonet.

IEM provides pre-parsed METAR fields in US/METAR-native units (°F, kt, mi, inHg).
Emits observation dicts matching specs/observation.json with source="iem".
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
    WIND_DIR_BOUNDS,
    WIND_GUST_MAX,
    WIND_SPEED_MAX,
    bounded_float,
    bounded_float_min,
    bounded_int,
)
from tradewinds._internal._convert import fahrenheit_to_celsius
from tradewinds.weather._awc import icao_to_station_code, map_cloud_cover

_TS_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2}) (\d{2}):(\d{2})$")


def _safe_float(val: str) -> float | None:
    """Parse IEM string to float. 'M' or empty → None."""
    if not val or val == "M":
        return None
    try:
        f = float(val)
        return f if math.isfinite(f) else None
    except (ValueError, OverflowError):
        return None


def _safe_int(val: str) -> int | None:
    """Parse IEM string to int via float. 'M' or empty → None."""
    f = _safe_float(val)
    return round(f) if f is not None else None


def _parse_precip(val: str) -> float | None:
    """Parse IEM precipitation. 'T' → 0.0, 'M' → None, numeric passthrough."""
    if not val or val == "M":
        return None
    if val.strip().upper() == "T":
        return 0.0
    return _safe_float(val)


def _parse_timestamp(val: str) -> str | None:
    """Parse IEM timestamp to RFC3339.

    '2025-01-01 00:51' → '2025-01-01T00:51:00Z'
    """
    if not val or val == "M":
        return None
    m = _TS_RE.match(val.strip())
    if not m:
        return None
    try:
        datetime.strptime(val.strip(), "%Y-%m-%d %H:%M")
    except ValueError:
        return None
    year = int(m.group(1))
    if not (MIN_YEAR <= year <= MAX_YEAR):
        return None
    return f"{m.group(1)}-{m.group(2)}-{m.group(3)}T{m.group(4)}:{m.group(5)}:00Z"


def _parse_peak_wind_time(val: str) -> str | None:
    """Parse IEM peak_wind_time to HHMM format.

    '2025-01-01 01:31' → '0131'
    """
    if not val or val == "M":
        return None
    val = val.strip()
    parts = val.split(" ")
    if len(parts) != 2:
        return None
    time_parts = parts[1].split(":")
    if len(time_parts) != 2:
        return None
    try:
        h = int(time_parts[0])
        m = int(time_parts[1])
        if 0 <= h <= 23 and 0 <= m <= 59:
            return f"{h:02d}{m:02d}"
    except ValueError:
        pass
    return None


_VALID_OBS_TYPES = frozenset({"METAR", "SPECI"})


def _detect_obs_type(metar: str) -> str:
    """Detect METAR vs SPECI from raw METAR text first word."""
    if not metar or metar == "M":
        return "METAR"
    words = metar.strip().split(None, 1)
    if words and words[0] == "SPECI":
        return "SPECI"
    return "METAR"


def iem_to_observation(
    row: dict[str, str],
    observation_type_override: str | None = None,
) -> dict[str, Any] | None:
    """Convert a single IEM CSV row to an observation schema dict.

    Takes a dict from csv.DictReader (comma-delimited).
    If observation_type_override is set, uses that instead of detecting
    from raw METAR text. IEM strips the SPECI keyword from raw METAR,
    so callers that request report_type=3 or report_type=4 separately
    should pass the override.
    Returns observation dict with exactly 30 fields, or None if row should
    be skipped (invalid station, bad timestamp, or all key vars missing).
    """
    # Station code
    station_raw = row.get("station", "")
    if not station_raw or station_raw == "M":
        return None
    station_code = icao_to_station_code(station_raw)
    if not STATION_CODE_RE.match(station_code):
        return None

    # Timestamp
    observed_at = _parse_timestamp(row.get("valid", ""))
    if observed_at is None:
        return None

    # Observation type: caller override or detect from raw text
    if (
        observation_type_override is not None
        and observation_type_override not in _VALID_OBS_TYPES
    ):
        raise ValueError(
            f"Invalid observation_type_override: {observation_type_override!r}. "
            f"Must be one of {_VALID_OBS_TYPES}"
        )
    metar_text = row.get("metar", "")
    observation_type = observation_type_override or _detect_obs_type(metar_text)

    # Temperature (IEM gives °F, convert to °C — no rounding, then bound)
    raw_temp_f = _safe_float(row.get("tmpf", ""))
    raw_dewp_f = _safe_float(row.get("dwpf", ""))
    temp_c = bounded_float(
        fahrenheit_to_celsius(raw_temp_f), TEMP_MIN_C, TEMP_MAX_C, field="temp_c"
    )
    dewp_c = bounded_float(
        fahrenheit_to_celsius(raw_dewp_f), TEMP_MIN_C, TEMP_MAX_C, field="dewpoint_c"
    )
    # Consistency: if derived °C is out of bounds, the raw °F is also bogus
    temp_f = raw_temp_f if temp_c is not None else None
    dewp_f = raw_dewp_f if dewp_c is not None else None

    # Wind (already in knots)
    wind_dir = bounded_int(_safe_int(row.get("drct", "")), *WIND_DIR_BOUNDS)
    wind_speed = bounded_int(_safe_int(row.get("sknt", "")), 0, WIND_SPEED_MAX)
    wind_gust = bounded_int(_safe_int(row.get("gust", "")), 0, WIND_GUST_MAX)

    # Pressure (already in native units)
    altim = _safe_float(row.get("alti", ""))  # inHg
    slp = _safe_float(row.get("mslp", ""))  # mb/hPa
    if slp is not None and not (SLP_MIN_MB <= slp <= SLP_MAX_MB):
        slp = None

    # Visibility (already in statute miles)
    vis = _safe_float(row.get("vsby", ""))
    if vis is not None:
        if vis < 0:
            vis = None
        else:
            vis = min(vis, MAX_VISIBILITY_MILES)

    # Sky cover and base heights (IEM gives feet, direct passthrough)
    sky_covers: list[str | None] = []
    sky_bases: list[int | None] = []
    for i in range(1, 5):
        cover_raw = row.get(f"skyc{i}", "")
        base_raw = row.get(f"skyl{i}", "")
        cover = map_cloud_cover(cover_raw) if cover_raw and cover_raw != "M" else None
        base = bounded_int(_safe_int(base_raw), 0, SKY_BASE_MAX_FT)
        sky_covers.append(cover)
        sky_bases.append(base)

    # Weather codes (direct passthrough)
    wx_raw = row.get("wxcodes", "")
    weather_codes: str | None = None
    if wx_raw and wx_raw != "M":
        weather_codes = wx_raw[:MAX_WX_CODES_LEN]

    # Precipitation ('T' = trace → 0.0)
    precip = bounded_float_min(_parse_precip(row.get("p01i", "")), 0.0)

    # Snow depth (already in inches)
    snow = bounded_float_min(_safe_float(row.get("snowdepth", "")), 0.0)

    # Peak wind
    pk_gust = bounded_int(_safe_int(row.get("peak_wind_gust", "")), 0, WIND_GUST_MAX)
    pk_dir = bounded_int(_safe_int(row.get("peak_wind_drct", "")), *WIND_DIR_BOUNDS)
    pk_time = _parse_peak_wind_time(row.get("peak_wind_time", ""))

    # Raw METAR (passthrough, truncate)
    raw_metar: str | None = None
    if metar_text and metar_text != "M":
        raw_metar = metar_text[:MAX_RAW_METAR_LEN]

    # All key vars missing → skip row (check raw values for skip decision)
    if all(v is None for v in (raw_temp_f, raw_dewp_f, wind_speed, slp)):
        return None

    return {
        "station_code": station_code,
        "observed_at": observed_at,
        "observation_type": observation_type,
        "source": "iem",
        "temp_c": temp_c,
        "dewpoint_c": dewp_c,
        "temp_f": temp_f,
        "dewpoint_f": dewp_f,
        "wind_dir_degrees": wind_dir,
        "wind_speed_kt": wind_speed,
        "wind_gust_kt": wind_gust,
        "altimeter_inhg": altim,
        "sea_level_pressure_mb": slp,
        "sky_cover_1": sky_covers[0],
        "sky_base_1_ft": sky_bases[0],
        "sky_cover_2": sky_covers[1],
        "sky_base_2_ft": sky_bases[1],
        "sky_cover_3": sky_covers[2],
        "sky_base_3_ft": sky_bases[2],
        "sky_cover_4": sky_covers[3],
        "sky_base_4_ft": sky_bases[3],
        "visibility_miles": vis,
        "weather_codes": weather_codes,
        "precip_1hr_inches": precip,
        "peak_wind_gust_kt": pk_gust,
        "peak_wind_dir": pk_dir,
        "peak_wind_time": pk_time,
        "snow_depth_inches": snow,
        "qc_field": None,
        "raw_metar": raw_metar,
    }


def parse_iem_file(
    path: Path,
    observation_type_override: str | None = None,
) -> list[dict[str, Any]]:
    """Read an IEM CSV file and return list of valid observation dicts.

    Skips comment lines (starting with #) and rows that fail validation.
    If observation_type_override is set, all rows get that type instead
    of detecting from raw METAR text.
    """
    observations: list[dict[str, Any]] = []
    with open(path, newline="", encoding="utf-8", errors="replace") as f:
        filtered = (line for line in f if not line.startswith("#"))
        reader = csv.DictReader(filtered)
        for row in reader:
            obs = iem_to_observation(
                row, observation_type_override=observation_type_override
            )
            if obs is not None:
                observations.append(obs)
    return observations

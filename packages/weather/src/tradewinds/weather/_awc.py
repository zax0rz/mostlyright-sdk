"""AWC METAR transform — maps AWC JSON response to observation schema dict.

This is THE shared transform. Both the SDK and ingest worker import it.
Output dicts validate against specs/observation.json (additionalProperties: false).
"""

from __future__ import annotations

import math
import re
from datetime import UTC, datetime
from typing import Any

from tradewinds._internal._bounds import (
    MAX_RAW_METAR_LEN,
    MAX_VISIBILITY_MILES,
    MAX_WX_CODES_LEN,
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
from tradewinds._internal._convert import celsius_to_fahrenheit, hpa_to_inhg


def icao_to_station_code(icao: str) -> str:
    """Strip leading K for 4-letter CONUS ICAO codes."""
    upper = icao.strip().upper()
    if upper.startswith("K") and len(upper) == 4:
        return upper[1:]
    return upper


def parse_awc_visibility(vis: Any) -> float | None:
    """Parse AWC visibility: '10+', '1/2', '2 1/4', '3/4', plain numbers.

    Returns miles or None. Caps at 99.99.
    """
    if vis is None:
        return None

    s = str(vis)
    if s == "" or s == "null":
        return None

    # "10+" -> 10
    if s.endswith("+"):
        try:
            n = float(s[:-1])
        except (ValueError, OverflowError):
            return None
        if not math.isfinite(n):
            return None
        return min(n, MAX_VISIBILITY_MILES)

    # Mixed number: "1 1/2", "2 1/4"
    if " " in s and "/" in s:
        parts = s.split(" ", 1)
        if len(parts) != 2:
            return None
        frac_parts = parts[1].split("/")
        if len(frac_parts) != 2:
            return None
        try:
            w = float(parts[0])
            n = float(frac_parts[0])
            d = float(frac_parts[1])
        except (ValueError, OverflowError):
            return None
        if not (math.isfinite(w) and math.isfinite(n) and math.isfinite(d) and d != 0):
            return None
        return min(w + n / d, MAX_VISIBILITY_MILES)

    # Simple fraction: "1/2", "1/4", "3/4", or "M1/4" (below-quarter-mile
    # AWC/METAR convention — codex review W3A P2). The leading 'M' means
    # "less than", which we represent as the same fractional value (the
    # observation schema treats this as the visibility value, not a flag).
    if "/" in s:
        if s.startswith("M") or s.startswith("m"):
            s = s[1:]
        frac_parts = s.split("/")
        if len(frac_parts) != 2:
            return None
        try:
            n = float(frac_parts[0])
            d = float(frac_parts[1])
        except (ValueError, OverflowError):
            return None
        if not (math.isfinite(n) and math.isfinite(d) and d != 0):
            return None
        return min(n / d, MAX_VISIBILITY_MILES)

    # Plain number
    try:
        n = float(s)
    except (ValueError, OverflowError):
        return None
    if not math.isfinite(n):
        return None
    return min(n, MAX_VISIBILITY_MILES)


def map_cloud_cover(cover: str | None) -> str | None:
    """Map AWC cloud cover code to standard abbreviation."""
    if cover is None:
        return None
    upper = cover.upper()
    if upper in ("CLR", "SKC", "FEW", "SCT", "BKN", "OVC", "VV"):
        return upper
    if upper == "CAVOK":
        return "CLR"
    return None


def _cloud_layer(layer: Any) -> tuple[str | None, int | None]:
    """Extract cover and base from a cloud layer dict. Safe against non-dict entries."""
    if not isinstance(layer, dict):
        return None, None
    base = bounded_int(_safe_int(layer.get("base")), 0, SKY_BASE_MAX_FT)
    return map_cloud_cover(layer.get("cover")), base


def _safe_int(v: Any) -> int | None:
    """Convert to int. Returns None on bad input."""
    if v is None:
        return None
    try:
        f = float(v)
        if not math.isfinite(f):
            return None
        return round(f)
    except (ValueError, TypeError, OverflowError):
        return None


def _safe_float(v: Any) -> float | None:
    """Convert to float. Returns None on bad input."""
    if v is None:
        return None
    try:
        f = float(v)
        return f if math.isfinite(f) else None
    except (ValueError, TypeError, OverflowError):
        return None


def _safe_precip(v: Any) -> float | None:
    """Parse precipitation. Trace 'T' → 0.0, numeric passthrough, else None."""
    if v is None:
        return None
    if isinstance(v, str) and v.strip().upper() == "T":
        return 0.0
    return _safe_float(v)


_PK_WND_RE = re.compile(r"PK WND (\d{3})(\d{2,3})/(\d{4})")

# T-group in METAR remarks: T{s}{SSS}{s}{DDD}
# s=0 positive, s=1 negative. SSS/DDD = tenths of °C.
# Example: T02560167 → 25.6°C / 16.7°C. T10390061 → -3.9°C / 6.1°C.
_TGROUP_RE = re.compile(r"\bT([01])(\d{3})([01])(\d{3})\b")


def _parse_peak_wind(
    raw_metar: str | None,
) -> tuple[int | None, int | None, str | None]:
    """Parse PK WND from METAR remarks. Returns (dir, speed_kt, time_hhmm)."""
    if not raw_metar:
        return None, None, None
    match = _PK_WND_RE.search(raw_metar)
    if not match:
        return None, None, None
    direction = int(match.group(1))
    speed = int(match.group(2))
    time_hhmm = match.group(3)
    if not (0 <= direction <= 360) or speed < 0:
        return None, None, None
    return direction, speed, time_hhmm


def _parse_tgroup(raw_metar: str | None) -> tuple[float | None, float | None]:
    """Parse T-group from METAR remarks for tenths-precision temperature.

    ASOS stations always include T-group in remarks. Format: T{s}{SSS}{s}{DDD}
    where s=0 positive, s=1 negative, SSS=temp tenths °C, DDD=dewpoint tenths °C.
    Searches only the remarks section (after RMK) to avoid false positives.
    Returns (temp_c, dewpoint_c) or (None, None) if not found.
    """
    if not raw_metar:
        return None, None
    # T-group is a remarks-only element — search only after RMK.
    # No RMK section = no T-group. Do NOT fallback to full string
    # to avoid false positives on body group patterns.
    rmk_idx = raw_metar.find("RMK")
    if rmk_idx < 0:
        return None, None
    match = _TGROUP_RE.search(raw_metar[rmk_idx:])
    if not match:
        return None, None
    t_sign = -1 if match.group(1) == "1" else 1
    t_val = int(match.group(2)) / 10.0 * t_sign
    d_sign = -1 if match.group(3) == "1" else 1
    d_val = int(match.group(4)) / 10.0 * d_sign
    return t_val, d_val


def awc_to_observation(m: dict[str, Any]) -> dict[str, Any] | None:
    """Convert a parsed AWC METAR dict to an observation schema dict.

    Returns None if icaoId or obsTime is invalid.
    Output matches specs/observation.json (no extra fields).
    """
    icao_id = m.get("icaoId")
    if not isinstance(icao_id, str) or not icao_id:
        return None

    obs_time = m.get("obsTime")
    if not isinstance(obs_time, (int, float)):
        return None

    station_code = icao_to_station_code(icao_id)
    if not STATION_CODE_RE.match(station_code):
        return None

    try:
        dt = datetime.fromtimestamp(obs_time, tz=UTC)
    except (OSError, OverflowError, ValueError):
        return None
    if not (1970 <= dt.year <= 2100):
        return None
    observed_at = dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    metar_type = (m.get("metarType") or "METAR").upper()
    observation_type = "SPECI" if metar_type == "SPECI" else "METAR"

    # Wind direction: handle "VRB" -> None, bounded [0, 360]
    wdir: int | None = None
    raw_wdir = m.get("wdir")
    if raw_wdir is not None:
        if isinstance(raw_wdir, (int, float)):
            wdir = bounded_int(int(raw_wdir), *WIND_DIR_BOUNDS)
        elif raw_wdir != "VRB":
            try:
                parsed = float(raw_wdir)
                if math.isfinite(parsed):
                    wdir = bounded_int(int(parsed), *WIND_DIR_BOUNDS)
            except (ValueError, TypeError):
                pass

    wspd = bounded_int(_safe_int(m.get("wspd")), 0, WIND_SPEED_MAX)
    wgst = bounded_int(_safe_int(m.get("wgst")), 0, WIND_GUST_MAX)

    # Altimeter: AWC altim is in hPa, convert to inHg (no rounding)
    altim = hpa_to_inhg(_safe_float(m.get("altim")))

    # Sea-level pressure (already in mb/hPa)
    slp = _safe_float(m.get("slp"))
    if slp is not None and not (SLP_MIN_MB <= slp <= SLP_MAX_MB):
        slp = None

    # Cloud layers (safe against non-dict entries)
    clouds = m.get("clouds") or []
    cov1, base1 = _cloud_layer(clouds[0]) if len(clouds) > 0 else (None, None)
    cov2, base2 = _cloud_layer(clouds[1]) if len(clouds) > 1 else (None, None)
    cov3, base3 = _cloud_layer(clouds[2]) if len(clouds) > 2 else (None, None)
    cov4, base4 = _cloud_layer(clouds[3]) if len(clouds) > 3 else (None, None)

    # Raw METAR (truncate to 2048)
    raw_ob = m.get("rawOb")
    raw_metar: str | None = None
    if isinstance(raw_ob, str):
        raw_metar = raw_ob[:MAX_RAW_METAR_LEN]

    # Weather codes
    raw_wx = m.get("wxString")
    weather_codes: str | None = None
    if isinstance(raw_wx, str):
        weather_codes = raw_wx[:MAX_WX_CODES_LEN]

    # Temperature: T-group (tenths precision) overrides body group (whole degree).
    # ASOS always includes T-group in remarks. If present, use it.
    # Note: KNYC (Central Park) is NOT an ASOS station — may lack T-group,
    # falling back to whole-degree body group temps from AWC.
    temp_c = _safe_float(m.get("temp"))
    dewp_c = _safe_float(m.get("dewp"))
    tgroup_temp, tgroup_dewp = _parse_tgroup(raw_metar)
    if tgroup_temp is not None:
        temp_c = tgroup_temp
    if tgroup_dewp is not None:
        dewp_c = tgroup_dewp
    temp_c = bounded_float(temp_c, TEMP_MIN_C, TEMP_MAX_C, field="temp_c")
    dewp_c = bounded_float(dewp_c, TEMP_MIN_C, TEMP_MAX_C, field="dewpoint_c")
    temp_f = celsius_to_fahrenheit(temp_c)
    dewpoint_f = celsius_to_fahrenheit(dewp_c)

    # Peak wind from METAR remarks (PK WND dddss/hhmm), bounded
    pk_dir, pk_spd, pk_time = _parse_peak_wind(raw_metar)
    pk_dir = bounded_int(pk_dir, *WIND_DIR_BOUNDS)
    pk_spd = bounded_int(pk_spd, 0, WIND_GUST_MAX)

    # Precipitation (AWC provides 'precip' field; 'T' = trace → 0.0, non-negative)
    precip = bounded_float_min(_safe_precip(m.get("precip")), 0.0)

    # QC field bitmask
    qc_raw = m.get("qcField")
    qc_field = _safe_int(qc_raw)

    return {
        "station_code": station_code,
        "observed_at": observed_at,
        "observation_type": observation_type,
        "source": "awc",
        "temp_c": temp_c,
        "dewpoint_c": dewp_c,
        "temp_f": temp_f,
        "dewpoint_f": dewpoint_f,
        "wind_dir_degrees": wdir,
        "wind_speed_kt": wspd,
        "wind_gust_kt": wgst,
        "altimeter_inhg": altim,
        "sea_level_pressure_mb": slp,
        "sky_cover_1": cov1,
        "sky_base_1_ft": base1,
        "sky_cover_2": cov2,
        "sky_base_2_ft": base2,
        "sky_cover_3": cov3,
        "sky_base_3_ft": base3,
        "sky_cover_4": cov4,
        "sky_base_4_ft": base4,
        "visibility_miles": parse_awc_visibility(m.get("visib")),
        "weather_codes": weather_codes,
        "precip_1hr_inches": precip,
        "peak_wind_gust_kt": pk_spd,
        "peak_wind_dir": pk_dir,
        "peak_wind_time": pk_time,
        "snow_depth_inches": None,  # not available from AWC
        "qc_field": qc_field,
        "raw_metar": raw_metar,
    }

"""Schema-derived bounds and validation helpers.

Constants from specs/observation.json. Shared by AWC, GHCNh, and IEM parsers.
"""

from __future__ import annotations

import logging
import re

log = logging.getLogger(__name__)

# Pressure bounds (observation.json: sea_level_pressure_mb)
SLP_MIN_MB = 870.0
SLP_MAX_MB = 1084.0

# Temperature bounds (°C). World records: -89.2°C (Vostok) / 56.7°C (Death Valley).
TEMP_MIN_C = -90.0
TEMP_MAX_C = 60.0

# String length limits
MAX_RAW_METAR_LEN = 2048
MAX_WX_CODES_LEN = 256

# Visibility (observation.json: visibility_miles max)
MAX_VISIBILITY_MILES = 99.99

# Wind bounds (observation.json: wind_dir_degrees, wind_speed_kt, wind_gust_kt)
WIND_DIR_BOUNDS = (0, 360)
WIND_SPEED_MAX = 200
WIND_GUST_MAX = 250

# Sky (observation.json: sky_base max)
SKY_BASE_MAX_FT = 60000

# Station code regex — security boundary: codes flow into Hive partition paths
STATION_CODE_RE = re.compile(r"^[A-Z]{3,4}$")

# Year range for timestamp validation
MIN_YEAR = 1940
MAX_YEAR = 2100


def bounded_int(val: int | None, lo: int, hi: int) -> int | None:
    """Return val if within [lo, hi], else None."""
    if val is None:
        return None
    return val if lo <= val <= hi else None


def bounded_float(val: float | None, lo: float, hi: float, *, field: str = "") -> float | None:
    """Return val if within [lo, hi], else None. Logs out-of-bounds values."""
    if val is None:
        return None
    if lo <= val <= hi:
        return val
    ctx = f" ({field})" if field else ""
    log.warning(
        "bounded_float%s: %.4f outside [%.1f, %.1f], setting to None",
        ctx,
        val,
        lo,
        hi,
    )
    return None


def bounded_float_min(val: float | None, lo: float) -> float | None:
    """Return val if >= lo, else None."""
    if val is None:
        return None
    return val if val >= lo else None

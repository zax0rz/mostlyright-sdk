"""Schema-derived bounds and validation helpers.

Constants from specs/observation.json. Shared by AWC, GHCNh, and IEM parsers.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

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

# Station code regex - security boundary: codes flow into Hive partition paths.
# Use `\A...\Z` (not `^...$`) so trailing-newline inputs like "KJFK\n" fail to
# match. Python's `$` matches BEFORE a trailing newline; `\Z` requires the
# absolute end of string. Codex review fix.
STATION_CODE_RE = re.compile(r"\A[A-Z]{3,4}\Z")

# GHCNh station identifier regex. The NCEI archive uses two id flavors:
# - ICAO-derived joined USAF-WBAN form, e.g. ``"744860-94789"`` for KJFK
# - 11-character NCEI station ids, alphanumeric
# Either way: alphanumeric + hyphen, length-bounded, anchored. This is a
# SECURITY BOUNDARY identical to STATION_CODE_RE: ids flow into URL params
# and cache paths, so any path-separator character (/, \, ., space) must be
# rejected. Codex/Rob H8 fix.
GHCNH_STATION_ID_RE = re.compile(r"\A[A-Z0-9][A-Z0-9-]{0,31}\Z")

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


# ---------------------------------------------------------------------------
# Path-boundary validators (Rob PR #2 C1/H8 - path traversal hardening)
# ---------------------------------------------------------------------------
#
# Every fetcher and cache helper that uses a caller-supplied station string
# inside a URL parameter OR a filesystem path goes through one of these
# validators FIRST. The downstream parsers already use STATION_CODE_RE; the
# boundary fix is making sure raw fetcher/cache entry points do too.
#
# A station value like ``"../../../tmp/evil"`` would otherwise resolve outside
# the cache root via ``dest_dir / station / file`` -- the validators reject
# anything that does not match the strict regex.


def validate_icao_for_path(value: object, *, field: str = "station") -> str:
    """Return ``value`` validated as a 3-4 letter uppercase ICAO/IATA code.

    Raises ``ValueError`` with the field name for any input that fails
    ``STATION_CODE_RE``. Accepts only ``str``; rejects bytes, None, ints,
    and any value containing path separators, whitespace, or non-ASCII chars.

    Used at every fetcher and cache entry point that puts the station value
    into a URL param or a filesystem path (Rob PR #2 C1/H8).
    """
    if not isinstance(value, str):
        raise ValueError(
            f"{field} must be a str (got {type(value).__name__}); "
            f"unsafe to use in URL or cache path"
        )
    if not STATION_CODE_RE.match(value):
        raise ValueError(
            f"{field}={value!r} does not match STATION_CODE_RE "
            f"(3-4 uppercase letters); refusing to use as URL or path component"
        )
    return value


def validate_ghcnh_id_for_path(value: object, *, field: str = "station_id") -> str:
    """Return ``value`` validated as a GHCNh station identifier.

    Accepts ``str`` matching ``GHCNH_STATION_ID_RE`` (alphanumeric + hyphen,
    1-32 chars, first char alphanumeric). Rejects everything else with
    ``ValueError``. NCEI uses both ICAO-derived (``"744860-94789"``) and 11-
    char native ids; this pattern covers both while still rejecting path
    separators, whitespace, and quoting characters (Rob PR #2 H8).
    """
    if not isinstance(value, str):
        raise ValueError(
            f"{field} must be a str (got {type(value).__name__}); "
            f"unsafe to use in URL or cache path"
        )
    if not GHCNH_STATION_ID_RE.match(value):
        raise ValueError(
            f"{field}={value!r} does not match GHCNH_STATION_ID_RE "
            f"(alphanumeric + hyphen, 1-32 chars); refusing to use as URL "
            f"or path component"
        )
    return value


def assert_path_under(path: Path, root: Path, *, field: str = "path") -> Path:
    """Defense-in-depth: assert ``path`` resolves under ``root``.

    Used after the regex validators above as a second line of defense against
    path-traversal. ``Path.resolve()`` follows symlinks and ``..`` segments;
    ``is_relative_to`` then confirms the resolved path is still inside the
    resolved root. Either filter alone would suffice; both together make a
    path-escape regression require breaking BOTH defenses.

    Returns the resolved path on success; raises ``ValueError`` on escape
    (Rob PR #2 C1).
    """
    resolved = path.resolve()
    rroot = root.resolve()
    if not resolved.is_relative_to(rroot):
        raise ValueError(
            f"{field}={path!r} resolves to {resolved!r}, outside root {rroot!r}; "
            f"refusing path-traversal"
        )
    return resolved

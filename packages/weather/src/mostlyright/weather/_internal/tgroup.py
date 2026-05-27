"""Shared Tgroup parser for ASOS METAR remarks.

Phase 18 PREC-02: extracted from packages/weather/src/mostlyright/weather/_awc.py
so AWC and IEM (and any future consumer) parse Tgroup identically. The Tgroup
is the canonical tenths-°C encoding of the integer-°F ASOS reading; recovering
it from raw METAR remarks is the single source of truth for U.S. ASOS temperature
precision. See .planning/phases/18-precision-fix-asos-integer-fahrenheit/18-CONTEXT.md.
"""

from __future__ import annotations

import re

# T-group in METAR remarks: T{s}{SSS}{s}{DDD}
# s=0 positive, s=1 negative. SSS/DDD = tenths of °C.
# Example: T02560167 -> 25.6°C / 16.7°C. T10390061 -> -3.9°C / 6.1°C.
TGROUP_RE = re.compile(r"\bT([01])(\d{3})([01])(\d{3})\b")


def parse_tgroup(raw_metar: str | None) -> tuple[float | None, float | None]:
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
    match = TGROUP_RE.search(raw_metar[rmk_idx:])
    if not match:
        return None, None
    t_sign = -1 if match.group(1) == "1" else 1
    t_val = int(match.group(2)) / 10.0 * t_sign
    d_sign = -1 if match.group(3) == "1" else 1
    d_val = int(match.group(4)) / 10.0 * d_sign
    return t_val, d_val

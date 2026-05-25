"""Unit conversions for MostlyRight.

CRITICAL: No rounding anywhere. Store float64 as-is.
No _go_round(), no round(), no math.floor(x + 0.5) / multiplier patterns.
"""

from __future__ import annotations

import math
from dataclasses import replace
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mostlyright._internal.models.observation import Observation

_KT_TO_MPH = 1.15078
_KT_TO_MS = 1852.0 / 3600.0  # Exact: 1 knot = 1852 m / 3600 s
_MI_TO_KM = 1.609344  # Exact by definition
_MI_TO_M = 1609.344  # Exact by definition (mile -> metre)
_FT_TO_M = 0.3048  # Exact by definition (foot -> metre)
_IN_TO_MM = 25.4  # Exact by definition
_HPA_TO_INHG = 0.0295299875  # WMO standard conversion factor

# August-Roche-Magnus approximation (Alduchov & Eskridge 1996)
_MAGNUS_A = 17.625
_MAGNUS_B = 243.04  # °C


def kt_to_ms(kt: float | None) -> float | None:
    """Knots to meters per second. No rounding."""
    if kt is None:
        return None
    v = float(kt)
    if not math.isfinite(v):
        return None
    return v * _KT_TO_MS


def kt_to_mph(kt: float | None) -> float | None:
    """Knots to miles per hour. No rounding."""
    if kt is None:
        return None
    v = float(kt)
    if not math.isfinite(v):
        return None
    return v * _KT_TO_MPH


def mi_to_km(mi: float | None) -> float | None:
    """Statute miles to kilometers. No rounding."""
    if mi is None:
        return None
    v = float(mi)
    if not math.isfinite(v):
        return None
    return v * _MI_TO_KM


def mi_to_m(mi: float | None) -> float | None:
    """Statute miles to metres. No rounding. Used by catalog adapters projecting
    AWC/IEM/GHCNh ``visibility_miles`` to the canonical ``visibility_m`` column."""
    if mi is None:
        return None
    v = float(mi)
    if not math.isfinite(v):
        return None
    return v * _MI_TO_M


def ft_to_m(ft: float | None) -> float | None:
    """Feet to metres. No rounding. Used by catalog adapters projecting parser
    ``sky_base_N_ft`` to the canonical ``sky_base_N_m`` column."""
    if ft is None:
        return None
    v = float(ft)
    if not math.isfinite(v):
        return None
    return v * _FT_TO_M


def inches_to_mm(inches: float | None) -> float | None:
    """Inches to millimeters. No rounding."""
    if inches is None:
        return None
    v = float(inches)
    if not math.isfinite(v):
        return None
    return v * _IN_TO_MM


def convert_observation(obs: Observation, units: str) -> Observation:
    """Convert all fields in an Observation to the target unit system.

    Returns a NEW Observation via dataclasses.replace(). No rounding.
    Raises ValueError for unrecognized unit system.
    """
    if units == "raw":
        return obs
    if units == "metric":
        return replace(
            obs,
            wind_speed_kt=kt_to_ms(obs.wind_speed_kt),
            wind_gust_kt=kt_to_ms(obs.wind_gust_kt),
            peak_wind_gust_kt=kt_to_ms(obs.peak_wind_gust_kt),
            visibility_miles=mi_to_km(obs.visibility_miles),
            precip_1hr_inches=inches_to_mm(obs.precip_1hr_inches),
            snow_depth_inches=inches_to_mm(obs.snow_depth_inches),
        )
    if units == "imperial":
        return replace(
            obs,
            wind_speed_kt=kt_to_mph(obs.wind_speed_kt),
            wind_gust_kt=kt_to_mph(obs.wind_gust_kt),
            peak_wind_gust_kt=kt_to_mph(obs.peak_wind_gust_kt),
        )
    raise ValueError(f"Unrecognized unit system: {units!r}")


def celsius_to_fahrenheit(c: float | None) -> float | None:
    """Convert Celsius to Fahrenheit. No rounding."""
    if c is None:
        return None
    try:
        f = float(c)
        if not math.isfinite(f):
            return None
        return f * 9 / 5 + 32
    except (ValueError, TypeError, OverflowError):
        return None


def fahrenheit_to_celsius(f: float | None) -> float | None:
    """Convert Fahrenheit to Celsius. No rounding."""
    if f is None:
        return None
    try:
        val = float(f)
        if not math.isfinite(val):
            return None
        return (val - 32) * 5 / 9
    except (ValueError, TypeError, OverflowError):
        return None


def hpa_to_inhg(hpa: float | None) -> float | None:
    """Convert hectopascals (hPa/mb) to inches of mercury. No rounding."""
    if hpa is None:
        return None
    try:
        f = float(hpa)
        if not math.isfinite(f):
            return None
        return f * _HPA_TO_INHG
    except (ValueError, TypeError, OverflowError):
        return None


def compute_relative_humidity(temp_c: float | None, dewp_c: float | None) -> float | None:
    """Compute RH from temp and dewpoint (Celsius) via Magnus formula.

    Returns value in [0, 100] as raw float64 (no rounding), or None.
    """
    if temp_c is None or dewp_c is None:
        return None
    try:
        t = float(temp_c)
        td = float(dewp_c)
        if not (math.isfinite(t) and math.isfinite(td)):
            return None
        rh = (
            100.0
            * math.exp((_MAGNUS_A * td) / (_MAGNUS_B + td))
            / math.exp((_MAGNUS_A * t) / (_MAGNUS_B + t))
        )
        return max(0.0, min(rh, 100.0))
    except (ValueError, TypeError, OverflowError, ZeroDivisionError):
        return None


def compute_feels_like(
    temp_f: float | None,
    wind_kt: int | None,
    rh: float | None,
) -> float | None:
    """Compute feels-like temperature in Fahrenheit (full NWS algorithm).

    Wind chill at or below 50F with wind > 3 mph.
    Heat index at or above 80F with known RH.
    Plain temp otherwise. No rounding.
    """
    if temp_f is None:
        return None
    try:
        t = float(temp_f)
        # Codex review fix: guard NaN/inf inputs from pandas/parquet where missing
        # numeric fields come back as NaN rather than None. Without this, the result
        # leaks non-finite values (not JSON-safe).
        if not math.isfinite(t):
            return None
        w_mph = float(wind_kt) * _KT_TO_MPH if wind_kt is not None else 0.0
        if not math.isfinite(w_mph):
            return None
        if rh is not None and not math.isfinite(float(rh)):
            rh = None  # Treat non-finite rh as missing (don't feed NaN into heat index)

        # Wind Chill (NWS): valid for temp <= 50F and wind > 3 mph
        if t <= 50.0 and w_mph > 3.0:
            return 35.74 + 0.6215 * t - 35.75 * (w_mph**0.16) + 0.4275 * t * (w_mph**0.16)

        # Heat Index (NWS): requires known RH
        if t >= 80.0 and rh is not None:
            h = float(rh)
            # Step 1: Steadman simplified formula
            simple = 0.5 * (t + 61.0 + (t - 68.0) * 1.2 + h * 0.094)
            if (simple + t) / 2.0 < 80.0:
                return simple

            # Step 2: Rothfusz regression
            hi = (
                -42.379
                + 2.04901523 * t
                + 10.14333127 * h
                - 0.22475541 * t * h
                - 0.00683783 * t * t
                - 0.05481717 * h * h
                + 0.00122874 * t * t * h
                + 0.00085282 * t * h * h
                - 0.00000199 * t * t * h * h
            )

            # Step 3: NWS adjustments
            if h < 13.0 and 80.0 <= t <= 112.0:
                hi -= ((13.0 - h) / 4.0) * math.sqrt((17.0 - abs(t - 95.0)) / 17.0)
            elif h > 85.0 and 80.0 <= t <= 87.0:
                hi += ((h - 85.0) / 10.0) * ((87.0 - t) / 5.0)

            return hi

        return t
    except (ValueError, TypeError, OverflowError):
        return None

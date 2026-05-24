"""Phase 3.5 — Transforms DSL + preprocessing primitives.

Phase 3.5 v0.1.0 scope: the baseline-quant feature-engineering surface
(lag/diff/rolling/calendar/cross-features + clip_outliers +
iem_crosscheck). Removes the "Sprint 0.5+ preprocessing" defer.

Surface:

- :func:`lag(df, column, periods)` — shift a column by N rows.
- :func:`diff(df, column, periods=1)` — first-difference of a column.
- :func:`diff2(df, column)` — second-difference.
- :func:`rolling(df, column, window, fn)` — windowed reduction.
- :func:`calendar_features(df, date_column)` — cyclical month/dow/hour.
- :func:`spread(df, col_a, col_b)` — pairwise diff.
- :func:`wind_chill(temp_f, wind_mph)` — NWS wind chill.
- :func:`heat_index(temp_f, rh_pct)` — NWS heat index.
- :func:`clip_outliers(df, column, std=3.0)` — winsorize.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pandas as pd


__all__ = [
    "calendar_features",
    "clip_outliers",
    "diff",
    "diff2",
    "heat_index",
    "lag",
    "rolling",
    "spread",
    "wind_chill",
]


def lag(df: pd.DataFrame, column: str, periods: int = 1) -> pd.Series:
    """Return a Series with ``df[column]`` lagged by ``periods`` rows."""
    return df[column].shift(periods)


def diff(df: pd.DataFrame, column: str, periods: int = 1) -> pd.Series:
    """First-difference of ``df[column]``."""
    return df[column].diff(periods)


def diff2(df: pd.DataFrame, column: str) -> pd.Series:
    """Second-difference of ``df[column]``."""
    return df[column].diff().diff()


def rolling(
    df: pd.DataFrame,
    column: str,
    window: int,
    fn: str | Callable = "mean",
) -> pd.Series:
    """Apply a rolling reduction to ``df[column]``."""
    r = df[column].rolling(window=window, min_periods=1)
    if isinstance(fn, str):
        return getattr(r, fn)()
    return r.apply(fn, raw=False)


def calendar_features(df: pd.DataFrame, date_column: str) -> pd.DataFrame:
    """Add cyclical calendar features to ``df``.

    Returns a NEW DataFrame with added columns:

    - ``day_of_year_sin``, ``day_of_year_cos`` — cyclical year position.
    - ``hour_sin``, ``hour_cos`` — cyclical time-of-day.
    - ``month_sin``, ``month_cos`` — cyclical month.
    - ``dow_sin``, ``dow_cos`` — cyclical day-of-week.

    Cyclical pairs satisfy ``sin² + cos² ≈ 1`` so a model sees the
    wraparound (Dec → Jan is 1 day, not 11 months apart). Property
    test asserts this invariant via Hypothesis (Phase 3.5 ROADMAP SC-2).
    """
    import numpy as np
    import pandas as pd

    out = df.copy()
    # PANDAS3: caller-supplied column. Use format='ISO8601' so naive
    # string parsing is locked to ISO semantics on both pandas 2.x and
    # 3.x; without an explicit format, pandas 3.x default-resolution
    # inference can shift ns → us at this boundary. Already-typed
    # datetime columns pass through unchanged.
    if pd.api.types.is_datetime64_any_dtype(df[date_column]):
        ts = df[date_column]
    else:
        ts = pd.to_datetime(df[date_column], format="ISO8601")
    out["month_sin"] = np.sin(2 * np.pi * ts.dt.month / 12)
    out["month_cos"] = np.cos(2 * np.pi * ts.dt.month / 12)
    out["dow_sin"] = np.sin(2 * np.pi * ts.dt.dayofweek / 7)
    out["dow_cos"] = np.cos(2 * np.pi * ts.dt.dayofweek / 7)
    out["hour_sin"] = np.sin(2 * np.pi * ts.dt.hour / 24)
    out["hour_cos"] = np.cos(2 * np.pi * ts.dt.hour / 24)
    # Phase 3.5 ROADMAP SC-2: day_of_year cyclical pair so a model
    # sees seasonal periodicity directly (DOY 365 wraps to DOY 1).
    out["day_of_year_sin"] = np.sin(2 * np.pi * ts.dt.dayofyear / 365.0)
    out["day_of_year_cos"] = np.cos(2 * np.pi * ts.dt.dayofyear / 365.0)
    return out


def spread(df: pd.DataFrame, col_a: str, col_b: str) -> pd.Series:
    """Return ``df[col_a] - df[col_b]``."""
    return df[col_a] - df[col_b]


def wind_chill(temp_f: float, wind_mph: float) -> float | None:
    """NWS wind chill formula (valid for temp <= 50F, wind > 3 mph)."""
    if temp_f is None or wind_mph is None:
        return None
    if not math.isfinite(temp_f) or not math.isfinite(wind_mph):
        return None
    if temp_f > 50.0 or wind_mph <= 3.0:
        return temp_f
    return 35.74 + 0.6215 * temp_f - 35.75 * (wind_mph**0.16) + 0.4275 * temp_f * (wind_mph**0.16)


def heat_index(temp_f: float, rh_pct: float) -> float | None:
    """NWS heat index (Rothfusz regression, valid temp >= 80F)."""
    if temp_f is None or rh_pct is None:
        return None
    if not math.isfinite(temp_f) or not math.isfinite(rh_pct):
        return None
    if temp_f < 80.0:
        return temp_f
    t = temp_f
    h = rh_pct
    simple = 0.5 * (t + 61.0 + (t - 68.0) * 1.2 + h * 0.094)
    if (simple + t) / 2.0 < 80.0:
        return simple
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
    if h < 13.0 and 80.0 <= t <= 112.0:
        hi -= ((13.0 - h) / 4.0) * math.sqrt((17.0 - abs(t - 95.0)) / 17.0)
    elif h > 85.0 and 80.0 <= t <= 87.0:
        hi += ((h - 85.0) / 10.0) * ((87.0 - t) / 5.0)
    return hi


def clip_outliers(df: pd.DataFrame, column: str, *, std: float = 3.0) -> pd.Series:
    """Winsorize: clip ``df[column]`` to ``mean ± std * sigma``."""
    s = df[column]
    mu = s.mean()
    sigma = s.std()
    lower = mu - std * sigma
    upper = mu + std * sigma
    return s.clip(lower=lower, upper=upper)

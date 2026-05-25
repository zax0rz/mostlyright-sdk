"""Pandas 2.x / 3.x compatibility helpers (Phase 6 PANDAS3-01).

Pandas 3.0 (Jan 2026) shipped breaking changes that touch mostlyright:

- Default datetime resolution inference for naive string parsing shifts
  from ``ns`` to ``us`` (pandas 3.0 whatsnew §"Datetime resolution
  inference"). Explicit literals like ``dtype="datetime64[ns, UTC]"``
  still work on both versions, but new empty series built from string
  input may pick up the new default.
- The default storage dtype for inferred string columns shifts from
  ``object`` to PyArrow-backed ``string`` (pandas 3.0 whatsnew §"String
  dtype defaults").
- Copy-on-Write is enforced (no more chained-assignment silent reads).

These helpers centralize the version branch so risk-site fixes don't
sprout ad-hoc ``pd.__version__`` checks scattered across adapters.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pandas as pd

if TYPE_CHECKING:
    pass


__all__ = [
    "PANDAS_MAJOR",
    "empty_utc_datetime_series",
    "is_string_like_dtype",
]


def _major_version() -> int:
    """Return the integer major version of the installed pandas."""
    return int(pd.__version__.split(".", 1)[0])


PANDAS_MAJOR: int = _major_version()


def empty_utc_datetime_series() -> pd.Series:
    """Empty tz-aware UTC datetime series compatible with both pandas 2.x and 3.x.

    Pandas 2.x: ``datetime64[ns, UTC]`` is the canonical literal that the
    Validator's ``timestamp_utc`` check accepts. Pandas 3.x: ``datetime64[us, UTC]``
    is the new default resolution inference, but the explicit ``[ns, UTC]``
    literal still works (lossless promotion at construction time).

    The helper keeps the explicit ``[ns, UTC]`` literal because the parity
    contract pins the v0.1.0 ``ns`` resolution; ``coerce_pd3.py`` documents
    the inverse coercion ``ns→us`` that the dual-pandas matrix accepts.
    """
    return pd.Series([], dtype="datetime64[ns, UTC]")


def is_string_like_dtype(s: pd.Series) -> bool:
    """Return True for any storage representation of strings the SDK accepts.

    Covers:
    - pandas 2.x ``object`` dtype with Python ``str`` elements (the v0.1.0
      adapter output shape).
    - pandas 2.x / 3.x ``string`` extension dtype (PyArrow- or numpy-backed).
    - pandas 3.x PyArrow-backed default string dtype (the new pandas 3
      default; ``pd.api.types.is_string_dtype`` returns True).

    The Validator's ``_check_string`` calls this helper to keep the
    object-fallback arm correct under pandas 3 without scattering
    version checks across the dtype dispatch.
    """
    if pd.api.types.is_string_dtype(s):
        return True
    return s.dtype == "object"

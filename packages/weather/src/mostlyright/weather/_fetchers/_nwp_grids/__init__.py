"""Per-model NWP variable maps + station extraction helpers.

Each submodule (``hrrr.py``, ``gfs.py``, ``nbm.py``) declares:

- ``VARIABLE_MAP``: ``{canonical_column: (grib_variable, grib_level)}`` --
  the subset of GRIB2 fields mostlyright extracts. The keys are the
  output DataFrame column names (e.g. ``"temp_k_2m"``); the values
  match the ``(variable, level)`` strings as they appear in the
  ``.idx`` file.
- ``GRID_KIND``: descriptive grid label (``"lambert_conformal"`` etc.)
  recorded on each row for downstream auditing.

The module-level :func:`get_variable_map` and :func:`get_grid_kind`
look these up by model key.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

# Phase 17 PLAN-03 NCEP family
# Phase 17 PLAN-04 ECMWF family (both IFS variants share ecmwf_ifs; both
# AIFS variants share ecmwf_aifs).
# Phase 17 PLAN-05 MSC Canadian family
# Phase 17 PLAN-06 HAFS + legacy
from . import (
    cfs,
    ecmwf_aifs,
    ecmwf_ifs,
    gdas,
    gdps,
    gefs,
    geps,
    gfs,
    hafs,
    hiresw,
    hrdps,
    href,
    hrrr,
    hrrrak,
    nam,
    nbm,
    rap,
    rdps,
    reps,
    rrfs,
    rtma,
    urma,
)

if TYPE_CHECKING:
    pass


_MODULES = {
    "hrrr": hrrr,
    "gfs": gfs,
    "nbm": nbm,
    # PLAN-03 NCEP family
    "hrrrak": hrrrak,
    "gefs": gefs,
    "gdas": gdas,
    "rap": rap,
    "rrfs": rrfs,
    "rtma": rtma,
    "urma": urma,
    "cfs": cfs,
    # PLAN-04 ECMWF family
    "ecmwf_ifs_hres": ecmwf_ifs,
    "ecmwf_ifs_ens": ecmwf_ifs,
    "ecmwf_aifs_single": ecmwf_aifs,
    "ecmwf_aifs_ens": ecmwf_aifs,
    # PLAN-05 MSC Canadian family
    "hrdps": hrdps,
    "rdps": rdps,
    "gdps": gdps,
    "geps": geps,
    "reps": reps,
    # PLAN-06 NOMADS-only family
    "hafs": hafs,
    "nam": nam,
    "href": href,
    "hiresw": hiresw,
}


def get_variable_map(model: str) -> dict[str, tuple[str, str]]:
    """Return the ``{column: (variable, level)}`` map for ``model``.

    Raises:
        KeyError: ``model`` not registered in :data:`_MODULES`.
    """
    return _MODULES[model].VARIABLE_MAP


def get_grid_kind(model: str) -> str:
    """Return the grid-kind label for ``model``."""
    return _MODULES[model].GRID_KIND


__all__ = [
    "cfs",
    "ecmwf_aifs",
    "ecmwf_ifs",
    "gdas",
    "gdps",
    "gefs",
    "geps",
    "get_grid_kind",
    "get_variable_map",
    "gfs",
    "hafs",
    "hiresw",
    "hrdps",
    "href",
    "hrrr",
    "hrrrak",
    "nam",
    "nbm",
    "rap",
    "rdps",
    "reps",
    "rrfs",
    "rtma",
    "urma",
]

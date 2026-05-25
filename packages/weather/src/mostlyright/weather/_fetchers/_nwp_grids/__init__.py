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

from . import gfs, hrrr, nbm

if TYPE_CHECKING:
    pass


_MODULES = {
    "hrrr": hrrr,
    "gfs": gfs,
    "nbm": nbm,
}


def get_variable_map(model: str) -> dict[str, tuple[str, str]]:
    """Return the ``{column: (variable, level)}`` map for ``model``.

    Raises:
        KeyError: ``model`` not in ``{"hrrr", "gfs", "nbm"}``.
    """
    return _MODULES[model].VARIABLE_MAP


def get_grid_kind(model: str) -> str:
    """Return the grid-kind label for ``model``."""
    return _MODULES[model].GRID_KIND


__all__ = ["get_grid_kind", "get_variable_map", "gfs", "hrrr", "nbm"]

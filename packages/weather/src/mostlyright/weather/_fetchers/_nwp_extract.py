"""Station extraction from a decoded NWP GRIB2 dataset.

Encapsulates the cfgrib/xarray/sklearn path so callers can use it without
sprinkling lazy-imports throughout the public surface. Top-level imports
are limited to the standard library + numpy (a transitive dep of xarray
that we let the ``[nwp]`` extra install). The heavy deps (``cfgrib``,
``xarray``, ``sklearn``) are imported inside :func:`open_grib2_dataset`
and :func:`extract_stations`; calling either without
``pip install mostlyright-weather[nwp]`` raises ``ImportError`` with a
hint message — handled higher up in
:mod:`mostlyright.weather.forecast_nwp`.

Pattern lifted from mostlyright ``sprint2/2r-impl-bundle:ingest/sources/
_nwp_grids/hrrr.py:get_balltree`` + ``pick_points`` family. Tradewinds
keeps the module-level BallTree cache (one tree per grid shape) — short-
lived Python processes don't benefit from on-disk persistence.

Pitfalls covered (see 03.2-RESEARCH.md):
- BallTree input must be radians, not degrees (Pitfall 2).
- HRRR/NBM longitudes are 0..360 — wrap to -180..180 before tree build
  (Pitfall 3).
"""

from __future__ import annotations

import logging
import threading
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import xarray as xr

log = logging.getLogger(__name__)


#: Module-level BallTree cache keyed by ``(grid_shape, grid_signature)``.
#: ``grid_signature`` is a coarse hash of the corner cells so we don't
#: hand back a tree built from a different grid that happens to share
#: shape with the current one. See :func:`_grid_signature`.
_BALLTREE_CACHE: dict[tuple[tuple[int, int], int], Any] = {}
_BALLTREE_LOCK = threading.Lock()


def _grid_signature(lat2d: Any, lon2d: Any) -> int:
    """Coarse signature of a grid for cache-key disambiguation.

    Uses the first / last corner cells (after longitude unwrap) so that
    two grids of the same shape but different bounds get different cache
    entries. Does NOT need to be collision-free across the universe — a
    one-in-millions collision would mean a tree fits a grid it shouldn't,
    which would degrade extraction accuracy by ~one cell; the QC fields
    (``grid_dist_km``) would still surface the wrong answer.
    """
    return hash(
        (
            float(lat2d.flat[0]),
            float(lat2d.flat[-1]),
            float(lon2d.flat[0]),
            float(lon2d.flat[-1]),
        )
    )


def _wrap_longitude(lon2d: Any) -> Any:
    """Wrap longitudes from 0..360 to -180..180.

    HRRR / NBM grids carry longitude in 0..360; mostlyright station coords
    use signed -180..180. Without wrap, west-of-Greenwich grid cells end
    up "360° away" from station coords and the BallTree returns a
    dateline-wrap distance of >10,000 km (Pitfall 3).

    Idempotent: applying twice is a no-op for already-signed grids
    because no cell exceeds 180.
    """
    import numpy as np

    return np.where(lon2d > 180.0, lon2d - 360.0, lon2d)


def get_balltree(ds: xr.Dataset) -> tuple[Any, tuple[int, int]]:
    """Build (or retrieve from cache) the haversine BallTree for ``ds``.

    The tree indexes the dataset's flattened ``(latitude, longitude)``
    grid cells in **radians** (required by ``sklearn`` haversine metric).
    Cached per grid signature; subsequent calls for the same grid return
    in O(1).

    Args:
        ds: ``xarray.Dataset`` from
            :func:`open_grib2_dataset`. Must carry 2D ``latitude`` and
            ``longitude`` coords (per the cfgrib-decoded HRRR/GFS/NBM
            outputs).

    Returns:
        ``(tree, grid_shape)`` where ``tree`` is a
        ``sklearn.neighbors.BallTree`` and ``grid_shape`` is the 2-D
        ``(ny, nx)`` shape of the source grid (needed by
        :func:`extract_stations` to unravel flat indices back to row/col).

    Raises:
        ImportError: ``sklearn`` not installed (i.e. ``[nwp]`` extra
            missing). The caller is expected to surface a friendlier
            install hint.
        KeyError: ``ds`` does not carry ``latitude`` / ``longitude`` coords.
    """
    import numpy as np
    from sklearn.neighbors import BallTree

    if "latitude" not in ds or "longitude" not in ds:
        raise KeyError(
            "GRIB2 dataset is missing latitude/longitude coords; cfgrib decode may have failed."
        )

    lat2d = ds["latitude"].values
    lon2d = _wrap_longitude(ds["longitude"].values)
    grid_shape: tuple[int, int]
    if lat2d.ndim == 2:
        grid_shape = lat2d.shape  # type: ignore[assignment]
    elif lat2d.ndim == 1:
        # GFS regular grid: 1-D lat (ny,) + 1-D lon (nx,) → meshgrid.
        lat2d, lon2d = np.meshgrid(lat2d, lon2d, indexing="ij")
        grid_shape = lat2d.shape  # type: ignore[assignment]
    else:
        raise ValueError(f"latitude coord must be 1-D or 2-D; got ndim={lat2d.ndim}")

    sig = _grid_signature(lat2d, lon2d)
    cache_key = (grid_shape, sig)
    with _BALLTREE_LOCK:
        cached = _BALLTREE_CACHE.get(cache_key)
        if cached is not None:
            return cached, grid_shape
        grid_pts = np.column_stack([lat2d.ravel(), lon2d.ravel()])
        tree = BallTree(np.deg2rad(grid_pts), metric="haversine")
        _BALLTREE_CACHE[cache_key] = tree
        return tree, grid_shape


#: Earth radius (km) used to convert haversine angular distance →
#: great-circle kilometres for the ``grid_dist_km`` audit column.
EARTH_RADIUS_KM: float = 6371.0


def extract_stations(
    ds: xr.Dataset,
    *,
    variable: str,
    station_coords: list[tuple[float, float]],
) -> list[tuple[float, float]]:
    """Pull one value of ``variable`` per (lat, lon) station from ``ds``.

    Uses :func:`get_balltree` to find the nearest grid cell for each
    station, then samples ``ds[variable]`` at that cell. The return list
    preserves input order.

    Args:
        ds: cfgrib-decoded ``xarray.Dataset``.
        variable: Variable name to sample (e.g. the cfgrib alias
            corresponding to TMP at 2 m, which depends on the GRIB2
            ``shortName`` mapping cfgrib applies — typically ``"t2m"``
            for TMP at 2 m above ground).
        station_coords: ``[(latitude, longitude), ...]`` station points
            in WGS84 decimal degrees, signed ``-180..180`` longitude.

    Returns:
        ``[(value, dist_km), ...]`` per station. ``value`` is the float
        sample at the nearest cell (model-native units). ``dist_km`` is
        the great-circle distance to that cell.

    Raises:
        ImportError: ``sklearn`` / ``xarray`` not installed.
        KeyError: ``variable`` not in the dataset.
    """
    import numpy as np

    if variable not in ds:
        raise KeyError(f"variable {variable!r} not in dataset; available: {list(ds.data_vars)}")
    tree, grid_shape = get_balltree(ds)
    pts_deg = np.asarray(station_coords, dtype=float)
    pts_rad = np.deg2rad(pts_deg)
    dist_rad, idx_flat = tree.query(pts_rad, k=1)
    iy, ix = np.unravel_index(idx_flat.ravel(), grid_shape)
    field = ds[variable].values
    if field.ndim != 2:
        # Some cfgrib decodes carry a leading time dim — pick first slice.
        field = field.reshape((-1, *field.shape[-2:]))[0]
    samples = field[iy, ix]
    dist_km = dist_rad.ravel() * EARTH_RADIUS_KM
    return [(float(v), float(d)) for v, d in zip(samples, dist_km, strict=True)]


def open_grib2_dataset(path: str) -> xr.Dataset:
    """Open a one-record GRIB2 file via cfgrib.

    Wraps ``xarray.open_dataset(path, engine='cfgrib')``. Records fetched
    via byte-range are expected to be one GRIB2 message per file; opening
    multi-message files requires the ``filter_by_keys`` plumbing the lift
    deliberately omits in v0.1 (one-message-per-file keeps decode trivial).

    Raises:
        ImportError: ``cfgrib`` / ``xarray`` not installed.
    """
    import xarray as xr

    return xr.open_dataset(path, engine="cfgrib")


def reset_cache_for_tests() -> None:
    """Drop the module-level BallTree cache. **Test-only helper.**

    Production code never needs to call this — the cache is bounded by
    the number of distinct grid signatures (typically 3: HRRR, GFS,
    NBM).
    """
    with _BALLTREE_LOCK:
        _BALLTREE_CACHE.clear()


__all__ = [
    "EARTH_RADIUS_KM",
    "extract_stations",
    "get_balltree",
    "open_grib2_dataset",
    "reset_cache_for_tests",
]

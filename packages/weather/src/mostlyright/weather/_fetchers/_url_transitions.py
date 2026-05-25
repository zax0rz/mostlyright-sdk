"""Hardcoded date transitions for NWP URL building (Phase 17 FORECAST-06).

Every Herbie-documented URL-shape transition lives here as a single source
of truth. Add new branches HERE first, then reference the constant.

All datetimes are timezone-aware UTC. The comparison ``cycle >= CONSTANT``
must therefore be performed against a UTC-normalised cycle datetime — see
``_nwp_archive.build_fetch_plan`` for the canonical normalisation.
"""

from __future__ import annotations

from datetime import UTC, datetime

#: GFS v16 cutover — adds ``/atmos/`` to the path.
GFS_V16_CUTOVER = datetime(2021, 3, 23, tzinfo=UTC)

#: GEFS path restructure — ``pgrb2a/`` subdir introduced.
GEFS_FORMAT_2018 = datetime(2018, 7, 27, tzinfo=UTC)

#: GEFS path restructure — ``atmos/pgrb2ap5/`` + ``atmos/pgrb2sp25/``.
GEFS_FORMAT_2020 = datetime(2020, 9, 23, tzinfo=UTC)

#: ECMWF IFS path adds ``/ifs/`` segment.
ECMWF_IFS_PATH_TRANSITION = datetime(2024, 2, 28, 6, tzinfo=UTC)

#: ECMWF IFS resolution 0.4-beta → 0.25.
ECMWF_IFS_RESOLUTION_TRANSITION = datetime(2024, 2, 29, tzinfo=UTC)

#: ECMWF AIFS experimental phase begins.
ECMWF_AIFS_EXPERIMENTAL_START = datetime(2025, 2, 9, 12, tzinfo=UTC)

#: ECMWF AIFS operational phase begins.
ECMWF_AIFS_OPERATIONAL_START = datetime(2025, 2, 25, 6, tzinfo=UTC)

#: NAM / HREF / HiResW retirement per NWS scn26-47 (Herbie issue #540).
LEGACY_MODELS_RETIRE = datetime(2026, 8, 31, tzinfo=UTC)

__all__ = [
    "ECMWF_AIFS_EXPERIMENTAL_START",
    "ECMWF_AIFS_OPERATIONAL_START",
    "ECMWF_IFS_PATH_TRANSITION",
    "ECMWF_IFS_RESOLUTION_TRANSITION",
    "GEFS_FORMAT_2018",
    "GEFS_FORMAT_2020",
    "GFS_V16_CUTOVER",
    "LEGACY_MODELS_RETIRE",
]

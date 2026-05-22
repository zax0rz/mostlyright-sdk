"""Merge policies for observation + climate cache writes.

Lifted from monorepo-v0.14.1/ingest/storage/parquet.py (v0.14.1 SHA
``514fcdab227e845145ca32b989355647466231d9``).

Task 1.2 ships the observation merge half. Task 1.3 (parallel) appends
the climate merge half (``merge_climate``, ``REPORT_TYPE_PRIORITY``) and
will extend the public re-exports below.
"""

from __future__ import annotations

from tradewinds._internal.merge.observations import (
    SOURCE_PRIORITY,
    merge_observations,
)

__all__ = ["SOURCE_PRIORITY", "merge_observations"]

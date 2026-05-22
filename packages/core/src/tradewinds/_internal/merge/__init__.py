"""LIVE_V1 merge policies (observation + climate).

Lifted from monorepo-v0.14.1/ingest/storage/parquet.py (v0.14.1 SHA
``514fcdab227e845145ca32b989355647466231d9``). The v0.14.1 ingest layer
mixed pure dedup logic with parquet I/O in one file; this package
separates the pure policies for SDK consumers.

Phase 1 Wave 1 (parallel sub-branches merged here):
- ``observations`` (Task 1.2) — ``merge_observations`` + ``SOURCE_PRIORITY``
- ``climate`` (Task 1.3) — ``merge_climate`` + ``REPORT_TYPE_PRIORITY``
"""

from __future__ import annotations

from tradewinds._internal.merge.climate import (
    REPORT_TYPE_PRIORITY,
    merge_climate,
)
from tradewinds._internal.merge.observations import (
    SOURCE_PRIORITY,
    merge_observations,
)

__all__ = [
    "REPORT_TYPE_PRIORITY",
    "SOURCE_PRIORITY",
    "merge_climate",
    "merge_observations",
]

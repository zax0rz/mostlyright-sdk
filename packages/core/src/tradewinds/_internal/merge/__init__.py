"""LIVE_V1 merge policies (observation + climate).

Lifted from monorepo-v0.14.1/ingest/storage/parquet.py (the v0.14.1
ingest layer mixed pure dedup logic with parquet I/O in one file;
this package separates the pure policies for SDK consumers).

Wave 1 of phase-01-v0-14-1-parity-lift:
- ``climate`` — ``merge_climate`` + ``REPORT_TYPE_PRIORITY`` (Task 1.3)
- ``observations`` — ``merge_observations`` + ``SOURCE_PRIORITY`` (Task 1.2)
"""

from tradewinds._internal.merge.climate import (
    REPORT_TYPE_PRIORITY,
    merge_climate,
)

__all__ = [
    "REPORT_TYPE_PRIORITY",
    "merge_climate",
]

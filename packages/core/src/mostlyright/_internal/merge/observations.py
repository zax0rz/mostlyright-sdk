"""Observation merge policy (lifted from v0.14.1).

Lifted from monorepo-v0.14.1/ingest/storage/parquet.py:47-48, 246-261.
Source SHA: 514fcdab227e845145ca32b989355647466231d9
Lift date: 2026-05-21
Modifications:
- Renamed ``_dedup_rows`` -> ``merge_observations`` (public API).
- Renamed ``_SOURCE_PRIORITY`` -> ``SOURCE_PRIORITY`` (public).
- Logic is byte-faithful to v0.14.1. Do NOT alter dedup semantics here;
  any drift breaks Phase 1 parity gate (Wave 3 Day 3 fixture compare).
"""

from __future__ import annotations

from typing import Any

# Source priority for dedup tiebreaker: AWC(3) > IEM(2) > GHCNh(1)
SOURCE_PRIORITY: dict[str, int] = {"awc": 3, "iem": 2, "ghcnh": 1}


def merge_observations(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Deduplicate observations by ``(station_code, observed_at, observation_type)``.

    Keeps the row with the highest ``SOURCE_PRIORITY`` for each key. Unknown
    source strings get priority 0 and lose to any known source.

    Tie behavior: strict-``>`` comparison, so the FIRST row seen for a given
    key wins on ties (same source-priority does NOT overwrite). This matches
    the v0.14.1 raw-as-reported semantics.

    Empty input returns an empty list.
    """
    best: dict[tuple[str, str, str], dict[str, Any]] = {}
    for row in rows:
        key = (row["station_code"], row["observed_at"], row["observation_type"])
        priority = SOURCE_PRIORITY.get(row.get("source", ""), 0)
        if key not in best:
            best[key] = row
        else:
            existing_priority = SOURCE_PRIORITY.get(best[key].get("source", ""), 0)
            if priority > existing_priority:
                best[key] = row
    return list(best.values())

"""Climate dedupe policy (LIVE_V1 parity lift).

Lifted from monorepo-v0.14.1/ingest/storage/parquet.py:477-494
Source SHA: 514fcda
Lift date: 2026-05-21
Modifications:
- Renamed ``_dedup_climate_rows`` -> ``merge_climate`` (public surface).
- Promoted to its own module under ``mostlyright._internal.merge``;
  the v0.14.1 source mixes pure dedup with parquet I/O in one file.
- ``REPORT_TYPE_PRIORITY`` is co-located here (lower-layer canonical
  home). The values are byte-identical to the dict in
  ``mostlyright.weather._climate`` (Wave 3A lift). They are NOT
  imported from there because that would create a core -> weather
  cycle: ``mostlyright-weather`` depends on ``mostlyright`` (core).
  Cross-package consumers should re-export the constant from this
  module — there is exactly one canonical definition.

Logic is byte-faithful to mostlyright==0.14.1. ``merge_climate``
reads ``row["report_type_priority"]`` directly (a precomputed float
already populated by ``mostlyright.weather._climate.parse_cli_file``),
matching the v0.14.1 source. ``REPORT_TYPE_PRIORITY`` is exported for
callers that need the mapping (e.g. tests, populating rows ad-hoc).

Climate dedup keeps highest ``report_type_priority`` with STRICT >
(not >=). First-seen wins at equal priority. This preserves the
overnight final, which IS the Kalshi settlement value.
"""

from __future__ import annotations

from typing import Any

# Report type priority mapping. Values match mostlyright.weather._climate
# verbatim (Wave 3A lift from monorepo-v0.14.1/src/mostlyright/weather/_climate.py).
# See module docstring for why this is duplicated rather than imported.
REPORT_TYPE_PRIORITY: dict[str, float] = {
    "final": 3.0,
    "ncei_final": 2.5,
    "correction": 2.0,
    "preliminary": 1.0,
    "estimated": 0.0,
}


def merge_climate(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Deduplicate climate rows by (station_code, observation_date).

    Keeps highest ``report_type_priority`` with STRICT > (not >=).
    First-seen wins at equal priority. This preserves the overnight
    final, which IS the Kalshi settlement value.

    Empty input returns an empty list. Missing ``report_type_priority``
    on a row is treated as 0.0 (cannot overwrite any known priority).

    Byte-faithful port of ``_dedup_climate_rows`` from
    monorepo-v0.14.1/ingest/storage/parquet.py:477-494.
    """
    best: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        key = (row["station_code"], row["observation_date"])
        if key not in best:
            best[key] = row
        else:
            existing_priority = best[key].get("report_type_priority", 0.0)
            new_priority = row.get("report_type_priority", 0.0)
            if new_priority > existing_priority:  # strict >
                best[key] = row
    return list(best.values())

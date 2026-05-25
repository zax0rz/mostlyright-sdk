"""Pyarrow schemas for observation and climate parquet cache.

Lifted from monorepo-v0.14.1/ingest/storage/parquet.py:50-103.
Source SHA: 514fcdab227e845145ca32b989355647466231d9
Lift date: 2026-05-21
Modifications: none (verbatim lift; field order and dtypes preserved).

These schemas are consumed by Wave 1.4 (cache layer) for
``pq.write_table(table, schema=OBSERVATION_SCHEMA, ...)`` and by
``merge_observations`` callers that need a canonical column layout.

Task 1.3 (climate merge) will APPEND ``CLIMATE_SCHEMA`` to this file.
"""

from __future__ import annotations

import pyarrow as pa

# 30-field pyarrow schema matching specs/observation.json
OBSERVATION_SCHEMA = pa.schema(
    [
        pa.field("station_code", pa.string()),
        pa.field("observed_at", pa.string()),
        pa.field("observation_type", pa.string()),
        pa.field("source", pa.string()),
        pa.field("temp_c", pa.float64()),
        pa.field("dewpoint_c", pa.float64()),
        pa.field("temp_f", pa.float64()),
        pa.field("dewpoint_f", pa.float64()),
        pa.field("wind_dir_degrees", pa.int32()),
        pa.field("wind_speed_kt", pa.int32()),
        pa.field("wind_gust_kt", pa.int32()),
        pa.field("altimeter_inhg", pa.float64()),
        pa.field("sea_level_pressure_mb", pa.float64()),
        pa.field("sky_cover_1", pa.string()),
        pa.field("sky_base_1_ft", pa.int32()),
        pa.field("sky_cover_2", pa.string()),
        pa.field("sky_base_2_ft", pa.int32()),
        pa.field("sky_cover_3", pa.string()),
        pa.field("sky_base_3_ft", pa.int32()),
        pa.field("sky_cover_4", pa.string()),
        pa.field("sky_base_4_ft", pa.int32()),
        pa.field("visibility_miles", pa.float64()),
        pa.field("weather_codes", pa.string()),
        pa.field("precip_1hr_inches", pa.float64()),
        pa.field("peak_wind_gust_kt", pa.int32()),
        pa.field("peak_wind_dir", pa.int32()),
        pa.field("peak_wind_time", pa.string()),
        pa.field("snow_depth_inches", pa.float64()),
        pa.field("qc_field", pa.int32()),
        pa.field("raw_metar", pa.string()),
    ]
)


# Phase 2.1 (LINEAGE-01..05): silver-tier observation_ledger.v1 schema.
# Rows-per-source long format — natural key is
# (station_code, observed_at, source, parser_name, as_of_time, ingestion_id).
# Multiple rows per (station_code, observed_at) are valid silver outputs
# (one per contributing source AWC, IEM, GHCNh). Read-time
# ObservationMergePolicy materializes the single-row-per-key gold for
# Mode-1 parity callers.
#
# Source enum extends to ["awc", "iem", "ghcnh", "ncei"] — ncei reserved
# per D-2.1-09; never written in v0.1.0.
#
# 9 additive lineage fields (all nullable):
#   parser_name, parser_version, ingestion_id, as_of_time,
#   source_received_at, qc_status, observation_kind, provenance,
#   observation_quality.
OBSERVATION_LEDGER_SCHEMA = pa.schema(
    [
        # 30 v0.14.1 fields (verbatim).
        *OBSERVATION_SCHEMA,
        # 9 new lineage fields.
        pa.field("parser_name", pa.string()),
        pa.field("parser_version", pa.string()),
        pa.field("ingestion_id", pa.string()),
        pa.field("as_of_time", pa.string()),
        pa.field("source_received_at", pa.string()),
        pa.field("qc_status", pa.string()),
        pa.field("observation_kind", pa.string()),
        pa.field("provenance", pa.string()),
        pa.field("observation_quality", pa.string()),
    ]
)


# QC sidecar — one row per QC rule firing per (station_code, observed_at,
# source) ledger key. Writer hooks land in Phase 3.4; this declaration is
# forward-compat. 13 fields per the Phase 2.1 spec
# (packages/core/src/mostlyright/_internal/specs/observation_qc.json):
# ledger lineage keys + QC system identifiers + detector metadata payload.
QC_SIDECAR_SCHEMA = pa.schema(
    [
        # Ledger lineage keys.
        pa.field("station_code", pa.string()),
        pa.field("observed_at", pa.string()),
        pa.field("observation_kind", pa.string()),
        pa.field("source", pa.string()),
        pa.field("parser_name", pa.string()),
        pa.field("as_of_time", pa.string()),
        pa.field("ingestion_id", pa.string()),
        # QC system identifiers.
        pa.field("qc_system", pa.string()),
        pa.field("qc_version", pa.string()),
        pa.field("rule_id", pa.string()),
        pa.field("field", pa.string()),
        pa.field("flag", pa.string()),
        # Detector payload (JSON-serialized; concrete shape per qc_system).
        pa.field("detector_metadata", pa.string()),
    ]
)


__all__ = [
    "OBSERVATION_LEDGER_SCHEMA",
    "OBSERVATION_SCHEMA",
    "QC_SIDECAR_SCHEMA",
]

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

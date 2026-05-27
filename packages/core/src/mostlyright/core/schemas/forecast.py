"""Phase 20: Unified per-station forecast schema.

``schema.forecast.station.v1`` covers both IEM MOS rows and Open-Meteo rows
in a single column set. ``schema.forecast.iem_mos.v1`` is retained as a
back-compat alias (same class semantics, different ``schema_id``). Both
register via ``core/schemas/__init__.py``.

The unified schema marks IEM MOS core columns (``temp_c``, ``dew_point_c``,
etc.) as nullable because Open-Meteo may not provide all of them. Open-Meteo
extras (``apparent_temp_c``, ``shortwave_radiation_wm2``, ``cape_jkg``, etc.)
are always nullable — IEM MOS rows leave them null; Open-Meteo rows populate
them.

Source discrimination is via the ``source`` column (e.g. ``iem.archive``,
``open_meteo.previous_runs``, ``open_meteo.live``).

Temporal mapping (design.md §A):
- ``event_time = valid_at``
- ``knowledge_time = issued_at``
"""

from __future__ import annotations

from typing import ClassVar

from ..schema import ColumnSpec, Schema


class StationForecastSchema(Schema):
    """``schema.forecast.station.v1`` — unified per-station forecast schema.

    Covers IEM MOS shared core + Open-Meteo extras. Source identity via
    the ``source`` column. Two ``schema_id`` strings register against the
    same column set: ``schema.forecast.station.v1`` (canonical) and
    ``schema.forecast.iem_mos.v1`` (back-compat alias via subclass).

    Phase 20 OM-02.
    """

    schema_id: ClassVar[str] = "schema.forecast.station.v1"
    _registered_source: ClassVar[str] = "open_meteo.previous_runs"

    COLUMNS: ClassVar[list[ColumnSpec]] = [
        # === Identity (all required, nullable=False) ===
        ColumnSpec(name="station", dtype="string", units=None, nullable=False),
        ColumnSpec(
            name="issued_at",
            dtype="timestamp_utc",
            units=None,
            nullable=False,
            notes="model run time (knowledge_time)",
        ),
        ColumnSpec(
            name="valid_at",
            dtype="timestamp_utc",
            units=None,
            nullable=False,
            notes="forecast target time (event_time)",
        ),
        ColumnSpec(
            name="forecast_hour",
            dtype="int64",
            units="hours",
            nullable=False,
            notes="(valid_at - issued_at).total_seconds() / 3600",
        ),
        ColumnSpec(
            name="model",
            dtype="string",
            units=None,
            nullable=False,
            notes="e.g. NBE, GFS, LAV, MET, gfs_global, ecmwf_ifs025",
        ),
        ColumnSpec(
            name="source",
            dtype="string",
            units=None,
            nullable=False,
            notes="iem.archive | open_meteo.previous_runs | open_meteo.single_run | open_meteo.live",
        ),
        # === IEM MOS core (nullable because Open-Meteo may not supply all) ===
        ColumnSpec(name="temp_c", dtype="float64", units="celsius", nullable=True),
        ColumnSpec(name="dew_point_c", dtype="float64", units="celsius", nullable=True),
        ColumnSpec(name="wind_speed_ms", dtype="float64", units="m/s", nullable=True),
        ColumnSpec(name="wind_dir_deg", dtype="int64", units="degrees", nullable=True),
        ColumnSpec(
            name="precip_probability",
            dtype="float64",
            units="probability",
            nullable=True,
            notes="bounded [0, 1]",
        ),
        ColumnSpec(
            name="sky_cover_pct",
            dtype="int64",
            units="percent",
            nullable=True,
            notes="bounded [0, 100]",
        ),
        # === Open-Meteo extras (always nullable; null for iem.archive rows) ===
        ColumnSpec(name="apparent_temp_c", dtype="float64", units="celsius", nullable=True),
        ColumnSpec(name="shortwave_radiation_wm2", dtype="float64", units="W/m^2", nullable=True),
        ColumnSpec(name="direct_radiation_wm2", dtype="float64", units="W/m^2", nullable=True),
        ColumnSpec(name="cape_jkg", dtype="float64", units="J/kg", nullable=True),
        ColumnSpec(name="precipitation_mm", dtype="float64", units="mm", nullable=True),
        ColumnSpec(name="cloud_cover_pct", dtype="int64", units="percent", nullable=True),
        ColumnSpec(name="surface_pressure_hpa", dtype="float64", units="hPa", nullable=True),
        ColumnSpec(name="pressure_msl_hpa", dtype="float64", units="hPa", nullable=True),
        ColumnSpec(name="freezing_level_m", dtype="int64", units="meters", nullable=True),
        ColumnSpec(name="snow_depth_m", dtype="float64", units="meters", nullable=True),
        ColumnSpec(name="visibility_m", dtype="int64", units="meters", nullable=True),
        ColumnSpec(name="wind_gusts_ms", dtype="float64", units="m/s", nullable=True),
        ColumnSpec(
            name="weather_code",
            dtype="int64",
            units="WMO 4677",
            nullable=True,
            notes="WMO weather code (clear, fog, rain, snow, etc.)",
        ),
        # === Provenance ===
        ColumnSpec(
            name="retrieved_at",
            dtype="timestamp_utc",
            units=None,
            nullable=False,
            notes="wall-clock time the row was fetched from upstream",
        ),
    ]

    #: Imperial-mode renames apply to temperature, wind speed, and wind gusts.
    #: ``valid_at`` / ``issued_at`` / ``retrieved_at`` are model-internal
    #: timestamps and keep their canonical names.
    IMPERIAL_RENAMES: ClassVar[dict[str, str]] = {
        "temp_c": "temp_F",
        "dew_point_c": "dew_point_F",
        "apparent_temp_c": "apparent_temp_F",
        "wind_speed_ms": "wind_speed_kt",
        "wind_gusts_ms": "wind_gusts_kt",
    }


class ForecastSchema(StationForecastSchema):
    """Back-compat alias for ``schema.forecast.iem_mos.v1``.

    Same class semantics as :class:`StationForecastSchema`. Retained so
    existing IEM MOS parity fixtures and Phase 17 callers continue to work
    unchanged. New code should reference :class:`StationForecastSchema` and
    the canonical ``schema.forecast.station.v1`` ``schema_id``.

    Phase 20 OM-02.
    """

    schema_id: ClassVar[str] = "schema.forecast.iem_mos.v1"
    _registered_source: ClassVar[str] = "iem.archive"


__all__ = ["ForecastSchema", "StationForecastSchema"]

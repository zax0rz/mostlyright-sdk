"""Canonical METAR/SPECI observation schema (``schema.observation.v1``).

Mirrors the §A "Observations schema" table in ``docs/design.md`` exactly:
20 metric columns, with the imperial-mode rename map preserving the
``mostly-light/metar_parser.py`` 9-column contract as its projection.

Adapters (IEM, AWC) normalise their raw responses to these columns before
emitting rows. ``source``, ``knowledge_time`` and ``retrieved_at`` are
overlay columns added by the schema layer (not part of ``COLUMNS``); they
are stamped on every fetch and validated independently.
"""

from __future__ import annotations

from ..schema import ColumnSpec, Schema


_SKY_COVER_VALUES: tuple[str, ...] = ("CLR", "FEW", "SCT", "BKN", "OVC", "VV")
_OBSERVATION_TYPE_VALUES: tuple[str, ...] = ("METAR", "SPECI")


class ObservationSchema(Schema):
    """``schema.observation.v1`` — canonical METAR/SPECI rows.

    Metric column set per ``docs/design.md`` §A; imperial-mode rename map
    per the same section preserves the existing ``mostly-light`` contract
    (the 9-column anti-duplication projection: ``station, utc_datetime,
    temp_F, dew_point_F, slp_hpa, wind_speed_kt, wind_dir_deg, gust_kt,
    vsby``). ``slp_hpa`` is canonical aviation units and unchanged across
    modes; ``wind_dir_deg`` is dimensionless degrees.
    """

    schema_id = "schema.observation.v1"

    COLUMNS = [
        ColumnSpec(
            name="station",
            dtype="string",
            units=None,
            nullable=False,
            notes="ICAO/ASOS station ID (e.g. KORD)",
        ),
        ColumnSpec(
            name="event_time",
            dtype="timestamp_utc",
            units=None,
            nullable=False,
            notes="observation valid time",
        ),
        ColumnSpec(
            name="observation_type",
            dtype="enum",
            units=None,
            nullable=False,
            enum_values=_OBSERVATION_TYPE_VALUES,
            notes=(
                "METAR | SPECI; defaults METAR when source can't distinguish "
                "(e.g. AWC JSON)"
            ),
        ),
        ColumnSpec(
            name="temp_c",
            dtype="float64",
            units="celsius",
            nullable=True,
            notes="bounded TEMP_MIN_C..TEMP_MAX_C",
        ),
        ColumnSpec(
            name="dew_point_c",
            dtype="float64",
            units="celsius",
            nullable=True,
            notes="bounded",
        ),
        ColumnSpec(
            name="wind_speed_ms",
            dtype="float64",
            units="m/s",
            nullable=True,
            notes="converted from kt",
        ),
        ColumnSpec(
            name="wind_dir_deg",
            dtype="int64",
            units="degrees",
            nullable=True,
            notes="0-360, bounded",
        ),
        ColumnSpec(
            name="wind_gust_ms",
            dtype="float64",
            units="m/s",
            nullable=True,
            notes="converted from kt",
        ),
        ColumnSpec(
            name="slp_hpa",
            dtype="float64",
            units="hPa",
            nullable=True,
            notes=(
                "sea-level pressure (canonical aviation unit, not converted "
                "across modes)"
            ),
        ),
        ColumnSpec(
            name="visibility_m",
            dtype="float64",
            units="meters",
            nullable=True,
            notes="converted from statute miles",
        ),
        ColumnSpec(
            name="precip_mm_1h",
            dtype="float64",
            units="mm",
            nullable=True,
            notes="hourly precip (METAR p01i, converted from inches)",
        ),
        ColumnSpec(
            name="sky_cover_1",
            dtype="enum",
            units=None,
            nullable=True,
            enum_values=_SKY_COVER_VALUES,
            notes="first cloud layer cover code",
        ),
        ColumnSpec(
            name="sky_base_1_m",
            dtype="float64",
            units="meters",
            nullable=True,
            notes="first cloud layer base height (converted from feet)",
        ),
        ColumnSpec(
            name="sky_cover_2",
            dtype="enum",
            units=None,
            nullable=True,
            enum_values=_SKY_COVER_VALUES,
            notes="second layer; null if not present",
        ),
        ColumnSpec(
            name="sky_base_2_m",
            dtype="float64",
            units="meters",
            nullable=True,
        ),
        ColumnSpec(
            name="sky_cover_3",
            dtype="enum",
            units=None,
            nullable=True,
            enum_values=_SKY_COVER_VALUES,
            notes="third layer; null if not present",
        ),
        ColumnSpec(
            name="sky_base_3_m",
            dtype="float64",
            units="meters",
            nullable=True,
        ),
        ColumnSpec(
            name="sky_cover_4",
            dtype="enum",
            units=None,
            nullable=True,
            enum_values=_SKY_COVER_VALUES,
            notes="fourth layer; null if not present",
        ),
        ColumnSpec(
            name="sky_base_4_m",
            dtype="float64",
            units="meters",
            nullable=True,
        ),
        ColumnSpec(
            name="metar_raw",
            dtype="string",
            units=None,
            nullable=True,
            notes=(
                "raw METAR text if source has it; null for AWC JSON "
                "(structured-only)"
            ),
        ),
    ]

    #: Metric → imperial column-name map (docs §A imperial-mode table).
    #: ``station``, ``observation_type``, ``wind_dir_deg``, ``slp_hpa``,
    #: ``sky_cover_N`` and ``metar_raw`` are unchanged across modes.
    IMPERIAL_RENAMES = {
        "event_time": "utc_datetime",
        "temp_c": "temp_F",
        "dew_point_c": "dew_point_F",
        "wind_speed_ms": "wind_speed_kt",
        "wind_gust_ms": "gust_kt",
        "visibility_m": "vsby",
        "precip_mm_1h": "precip_in_1h",
        "sky_base_1_m": "sky_base_1_ft",
        "sky_base_2_m": "sky_base_2_ft",
        "sky_base_3_m": "sky_base_3_ft",
        "sky_base_4_m": "sky_base_4_ft",
    }

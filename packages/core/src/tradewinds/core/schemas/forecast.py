"""IEM MOS forecast schema (``schema.forecast.iem_mos.v1``).

Deliberate subset of mostlyright's full ``FORECAST_FIELDS`` (37 columns),
focused on the columns the kxhigh NHIGH/NLOW strategy actually consumes.
See ``docs/design.md`` §X for the rationale and the list of columns
deliberately omitted from this v0.1 contract; callers needing the full
mostlyright shape should use ``catalog.weather.iem.fetch_mos_raw(...)``,
which is documented as power-user API and not part of the v0.1 contract.

Temporal mapping (§A):
- ``event_time = valid_at``
- ``knowledge_time = issued_at``
"""

from __future__ import annotations

from typing import ClassVar

from ..schema import ColumnSpec, Schema


class ForecastSchema(Schema):
    """``schema.forecast.iem_mos.v1`` — kxhigh-focused MOS forecast rows.

    This is a deliberate SUBSET of mostlyright's ``FORECAST_FIELDS`` per
    ``docs/design.md`` §X. Columns dropped: ``qpf_6hr_in``,
    ``pop_6hr_pct``, ``cloud_cover_code``, ``ceiling_cat``,
    ``visibility_cat``, ``precip_type``, ``thunder_prob_12hr``, and
    lineage / internal fields. The 11 columns retained are exactly those
    the v0.1 catalogue surfaces as canonical contract.
    """

    schema_id = "schema.forecast.iem_mos.v1"

    COLUMNS: ClassVar[list[ColumnSpec]] = [
        ColumnSpec(
            name="station",
            dtype="string",
            units=None,
            nullable=False,
        ),
        ColumnSpec(
            name="issued_at",
            dtype="timestamp_utc",
            units=None,
            nullable=False,
            notes="model run time (from source `runtime` field)",
        ),
        ColumnSpec(
            name="valid_at",
            dtype="timestamp_utc",
            units=None,
            nullable=False,
            notes="forecast target time (from source `ftime`)",
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
            notes="e.g. NBE, GFS, LAV, MET",
        ),
        ColumnSpec(
            name="temp_c",
            dtype="float64",
            units="celsius",
            nullable=True,
        ),
        ColumnSpec(
            name="dew_point_c",
            dtype="float64",
            units="celsius",
            nullable=True,
        ),
        ColumnSpec(
            name="wind_speed_ms",
            dtype="float64",
            units="m/s",
            nullable=True,
        ),
        ColumnSpec(
            name="wind_dir_deg",
            dtype="int64",
            units="degrees",
            nullable=True,
        ),
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
    ]

    #: Forecast imperial-mode renames are the temperature and wind columns
    #: only; ``valid_at`` / ``issued_at`` are model-internal timestamps and
    #: keep their canonical names (no ``utc_datetime`` rename — that alias
    #: lives on the observation schema, where ``event_time`` is the
    #: load-bearing timestamp). See ``docs/design.md`` §A.
    IMPERIAL_RENAMES: ClassVar[dict[str, str]] = {
        "temp_c": "temp_F",
        "dew_point_c": "dew_point_F",
        "wind_speed_ms": "wind_speed_kt",
    }

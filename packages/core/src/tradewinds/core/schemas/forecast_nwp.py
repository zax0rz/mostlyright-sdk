"""NWP forecast schema (``schema.forecast_nwp.v1``) — Phase 3.2.

Distinct from :mod:`tradewinds.core.schemas.forecast` (which describes
IEM MOS forecasts on a per-station-cycle basis). NWP forecasts come from
gridded numerical models (HRRR / GFS / NBM in v0.1.0; ECMWF Tier-2
predeclared in the enum for v0.2) and carry model-native units (Kelvin
for temperature, m/s for wind, mm for precip, Pa for pressure) per
Phase 3.2 lock #4 in ``03.2-RESEARCH.md``.

``mirror`` records which NOAA Big Data Program mirror served the bytes
that produced this row — quants auditing "why does this forecast
disagree?" can trace bytes back to the mirror they came from.
"""

from __future__ import annotations

from typing import ClassVar

from ..schema import ColumnSpec, Schema

#: Models that ship in v0.1.0 + models reserved in the enum for v0.2.
#: Reserving the enum day-one lets a future v0.2 release add ECMWF
#: support without breaking schema-id stability.
NWP_MODEL_VALUES: tuple[str, ...] = (
    "hrrr",
    "gfs",
    "nbm",
    "ecmwf_ifs_hres",
    "ecmwf_ifs_ens",
    "ecmwf_aifs_single",
    "ecmwf_aifs_ens",
)


#: Mirrors that may appear in the ``mirror`` column. Reserves the four
#: ECMWF mirrors so a v0.2 ECMWF lift can add rows without bumping
#: ``schema_id``.
NWP_MIRROR_VALUES: tuple[str, ...] = (
    "aws_bdp",
    "gcp_bdp",
    "azure_bdp",
    "nomads",
    "ecmwf_data_portal",
    "ecmwf_aws",
    "ecmwf_azure",
    "ecmwf_gcp",
)


#: QC status values populated by the inline physics-bounds check in
#: :mod:`tradewinds.weather.forecast_nwp`. ``"clean"`` passed all rules;
#: ``"flagged"`` tripped one or more; ``"suspect"`` tripped a hard
#: physics violation (e.g. negative absolute temperature) that warrants
#: dropping for most use cases.
NWP_QC_STATUS_VALUES: tuple[str, ...] = ("clean", "flagged", "suspect")


class NwpForecastSchema(Schema):
    """``schema.forecast_nwp.v1`` — gridded NWP forecast rows.

    One row per ``(station, model, cycle, fxx, variable_column)`` — the
    variable column itself is encoded as separate float columns rather
    than long-form rows so quants can do model arithmetic without a
    pivot.

    The ``mirror`` column lets a downstream auditor link a row back to
    the bytes that produced it (NOAA BDP mirror chain).
    """

    schema_id = "schema.forecast_nwp.v1"

    #: Canonical source — NOAA BDP archive (the only NWP source
    #: tradewinds ships in v0.1.0).
    _registered_source: ClassVar[str] = "noaa_bdp"

    COLUMNS: ClassVar[list[ColumnSpec]] = [
        ColumnSpec(name="station", dtype="string", units=None, nullable=False),
        ColumnSpec(
            name="model",
            dtype="enum",
            units=None,
            nullable=False,
            enum_values=NWP_MODEL_VALUES,
        ),
        ColumnSpec(
            name="mirror",
            dtype="enum",
            units=None,
            nullable=False,
            enum_values=NWP_MIRROR_VALUES,
            notes="NOAA BDP mirror that served the underlying bytes",
        ),
        ColumnSpec(
            name="grid_kind",
            dtype="string",
            units=None,
            nullable=False,
            notes="grid-projection label (lambert_conformal_conus, regular_latlon_global_0p25, ...)",
        ),
        ColumnSpec(
            name="issued_at",
            dtype="timestamp_utc",
            units=None,
            nullable=False,
            notes="model run / cycle reference time",
        ),
        ColumnSpec(
            name="valid_at",
            dtype="timestamp_utc",
            units=None,
            nullable=False,
            notes="forecast target time = issued_at + forecast_hour",
        ),
        ColumnSpec(
            name="forecast_hour",
            dtype="int64",
            units="hours",
            nullable=False,
            notes="lead time in hours (alias: fxx)",
        ),
        ColumnSpec(
            name="grid_dist_km",
            dtype="float64",
            units="km",
            nullable=False,
            notes="great-circle distance from station to nearest grid cell",
        ),
        # Model-native unit fields ------------------------------------
        ColumnSpec(name="temp_k_2m", dtype="float64", units="K", nullable=True),
        ColumnSpec(name="dewpoint_k_2m", dtype="float64", units="K", nullable=True),
        ColumnSpec(
            name="relative_humidity_pct_2m",
            dtype="float64",
            units="percent",
            nullable=True,
        ),
        ColumnSpec(name="wind_u_ms_10m", dtype="float64", units="m/s", nullable=True),
        ColumnSpec(name="wind_v_ms_10m", dtype="float64", units="m/s", nullable=True),
        ColumnSpec(name="wind_gust_ms", dtype="float64", units="m/s", nullable=True),
        ColumnSpec(name="precip_mm_1h", dtype="float64", units="mm", nullable=True),
        ColumnSpec(name="pressure_pa_surface", dtype="float64", units="Pa", nullable=True),
        ColumnSpec(name="pressure_pa_mslp", dtype="float64", units="Pa", nullable=True),
        # Provenance / QC -----------------------------------------------
        ColumnSpec(
            name="qc_status",
            dtype="enum",
            units=None,
            nullable=False,
            enum_values=NWP_QC_STATUS_VALUES,
            notes="inline physics-bounds verdict; finer-grained QC lands in Phase 3.4",
        ),
        ColumnSpec(
            name="retrieved_at",
            dtype="timestamp_utc",
            units=None,
            nullable=False,
            notes="wall-clock UTC when the bytes were fetched",
        ),
    ]


__all__ = [
    "NWP_MIRROR_VALUES",
    "NWP_MODEL_VALUES",
    "NWP_QC_STATUS_VALUES",
    "NwpForecastSchema",
]

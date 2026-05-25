"""``schema.observation_qc.v1`` — QC sidecar schema (forward-compat).

Phase 2.1 declares this schema; Phase 3.4 lands the QC engine + writer
hooks. One row per QC rule firing per
``(station_code, observed_at, source)`` ledger key.
"""

from __future__ import annotations

from typing import ClassVar

from ..schema import ColumnSpec, Schema

_FLAG_VALUES = ("clean", "flagged", "suspect")
_OBSERVATION_KIND_VALUES = ("METAR", "SPECI")
_SOURCE_VALUES = ("awc", "iem", "ghcnh", "ncei")


class ObservationQCSchema(Schema):
    """``schema.observation_qc.v1`` — QC sidecar (forward-compat)."""

    schema_id = "schema.observation_qc.v1"

    #: Canonical source — QC sidecar writer in Phase 3.4 will tag rows with
    #: the qc_system that produced them; the schema-level _registered_source
    #: is the ledger source whose QC was evaluated.
    _registered_source: ClassVar[str] = "iem.archive"

    COLUMNS: ClassVar[list[ColumnSpec]] = [
        ColumnSpec(name="station_code", dtype="string", units=None, nullable=False),
        ColumnSpec(name="observed_at", dtype="timestamp_utc", units=None, nullable=False),
        ColumnSpec(
            name="observation_kind",
            dtype="enum",
            units=None,
            nullable=True,
            enum_values=_OBSERVATION_KIND_VALUES,
        ),
        ColumnSpec(
            name="source",
            dtype="enum",
            units=None,
            nullable=False,
            enum_values=_SOURCE_VALUES,
        ),
        ColumnSpec(name="parser_name", dtype="string", units=None, nullable=True),
        ColumnSpec(name="as_of_time", dtype="timestamp_utc", units=None, nullable=True),
        ColumnSpec(name="ingestion_id", dtype="string", units=None, nullable=True),
        ColumnSpec(name="qc_system", dtype="string", units=None, nullable=False),
        ColumnSpec(name="qc_version", dtype="string", units=None, nullable=False),
        ColumnSpec(name="rule_id", dtype="string", units=None, nullable=False),
        ColumnSpec(
            name="field",
            dtype="string",
            units=None,
            nullable=False,
            notes="Observation column the rule evaluated (e.g. temp_c).",
        ),
        ColumnSpec(
            name="flag",
            dtype="enum",
            units=None,
            nullable=False,
            enum_values=_FLAG_VALUES,
        ),
        ColumnSpec(
            name="detector_metadata",
            dtype="string",
            units=None,
            nullable=True,
            notes="JSON-serialized detector payload; shape per qc_system.",
        ),
    ]

    IMPERIAL_RENAMES: ClassVar[dict[str, str]] = {}

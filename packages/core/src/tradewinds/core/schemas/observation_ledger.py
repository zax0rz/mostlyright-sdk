"""``schema.observation_ledger.v1`` — silver-tier observation ledger.

Phase 2.1 (LINEAGE-01..05). Rows-per-source long format: one row per
``(station_code, observed_at, source)`` ledger key. Multiple rows per
``(station_code, observed_at)`` are valid silver-tier outputs (one per
contributing source: AWC, IEM, GHCNh). Read-time
``query_time_merge(silver_df, policy=LIVE_V1)`` materializes the
single-row-per-key gold for Mode-1 parity callers.

This is a NEW canonical schema separate from ``schema.observation.v1``
(the v0.14.1 Mode-1 gold-tier shape) — per codex review 2026-05-22 P2
finding "Keep observation.v1 out of the ledger refactor", the existing
gold schema stays unchanged so CORE-03 + parity callers see no breaking
change.
"""

from __future__ import annotations

from typing import ClassVar

from ..schema import ColumnSpec, Schema

_OBSERVATION_KIND_VALUES = ("METAR", "SPECI")
_QC_STATUS_VALUES = ("clean", "flagged", "suspect")
_PROVENANCE_VALUES = ("legacy", "reingested")
_SOURCE_LEDGER_VALUES = ("awc", "iem", "ghcnh", "ncei")
_PARSER_NAME_VALUES = ("mostlyright_v1", "iem", "ncei", "ghcnh")


class ObservationLedgerSchema(Schema):
    """``schema.observation_ledger.v1`` — silver-tier rows-per-source ledger.

    Natural key: ``(station_code, observed_at, source, parser_name,
    as_of_time, ingestion_id)``.

    Multiple rows per ``(station_code, observed_at)`` are valid — one per
    contributing source.
    """

    schema_id = "schema.observation_ledger.v1"

    #: Canonical source for ledger writes — IEM is the v0.14.1 baseline.
    #: Callers from other sources pass ``allow_source_drift`` for AWC/GHCNh.
    _registered_source: ClassVar[str] = "iem.archive"

    COLUMNS: ClassVar[list[ColumnSpec]] = [
        ColumnSpec(name="station_code", dtype="string", units=None, nullable=False),
        ColumnSpec(name="observed_at", dtype="timestamp_utc", units=None, nullable=False),
        ColumnSpec(
            name="observation_type",
            dtype="enum",
            units=None,
            nullable=False,
            enum_values=_OBSERVATION_KIND_VALUES,
        ),
        ColumnSpec(
            name="source",
            dtype="enum",
            units=None,
            nullable=False,
            enum_values=_SOURCE_LEDGER_VALUES,
            notes="ncei reserved per D-2.1-09; never written in v0.1.0.",
        ),
        # Observation payload (30 fields from v0.14.1 — abbreviated; the
        # full ColumnSpec list mirrors OBSERVATION_SCHEMA in
        # _internal/merge/_schemas.py).
        ColumnSpec(name="temp_c", dtype="float64", units="celsius", nullable=True),
        ColumnSpec(name="dewpoint_c", dtype="float64", units="celsius", nullable=True),
        # ... (full set tracked in observation_ledger.json + OBSERVATION_LEDGER_SCHEMA)
        # 9 lineage fields (Phase 2.1 additive — all nullable):
        ColumnSpec(
            name="parser_name",
            dtype="enum",
            units=None,
            nullable=True,
            enum_values=_PARSER_NAME_VALUES,
        ),
        ColumnSpec(name="parser_version", dtype="string", units=None, nullable=True),
        ColumnSpec(name="ingestion_id", dtype="string", units=None, nullable=True),
        ColumnSpec(name="as_of_time", dtype="timestamp_utc", units=None, nullable=True),
        ColumnSpec(name="source_received_at", dtype="string", units=None, nullable=True),
        ColumnSpec(
            name="qc_status",
            dtype="enum",
            units=None,
            nullable=True,
            enum_values=_QC_STATUS_VALUES,
        ),
        ColumnSpec(
            name="observation_kind",
            dtype="enum",
            units=None,
            nullable=True,
            enum_values=_OBSERVATION_KIND_VALUES,
        ),
        ColumnSpec(
            name="provenance",
            dtype="enum",
            units=None,
            nullable=True,
            enum_values=_PROVENANCE_VALUES,
        ),
        ColumnSpec(
            name="observation_quality",
            dtype="enum",
            units=None,
            nullable=True,
            enum_values=_QC_STATUS_VALUES,
            notes=(
                "Lineage row-quality flag per LINEAGE-01; distinct from "
                "qc_status enum slot AND distinct from the obs_qc_status "
                "bitmask column per QC-05."
            ),
        ),
    ]

    IMPERIAL_RENAMES: ClassVar[dict[str, str]] = {}

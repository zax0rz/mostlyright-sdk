"""Canonical schemas shipped with tradewinds v0.1.

The three schemas — observation, forecast, settlement — are the shape
contracts every weather-vertical adapter (IEM, AWC, NWS CLI) normalises
to. See ``docs/design.md`` §A, §X, and §BB.3 for the column-by-column
specification.

Each schema is eagerly registered with the Validator at import time so
``validate_dataframe(df, schema_id)`` works against the canonical IDs
without any explicit register-call boilerplate.
"""

from tradewinds.core.validator import register_schema

from .forecast import ForecastSchema
from .observation import ObservationSchema
from .observation_ledger import ObservationLedgerSchema
from .observation_qc import ObservationQCSchema
from .settlement import SettlementSchema

# Eager registration — Validator can look up each schema by ID immediately.
register_schema(ObservationSchema)
register_schema(ForecastSchema)
register_schema(SettlementSchema)
# Phase 2.1 additions.
register_schema(ObservationLedgerSchema)
register_schema(ObservationQCSchema)

__all__ = [
    "ForecastSchema",
    "ObservationLedgerSchema",
    "ObservationQCSchema",
    "ObservationSchema",
    "SettlementSchema",
]

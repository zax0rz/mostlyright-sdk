"""Canonical schemas shipped with mostlyright v0.1.

The three schemas — observation, forecast, settlement — are the shape
contracts every weather-vertical adapter (IEM, AWC, NWS CLI) normalises
to. See ``docs/design.md`` §A, §X, and §BB.3 for the column-by-column
specification.

Each schema is eagerly registered with the Validator at import time so
``validate_dataframe(df, schema_id)`` works against the canonical IDs
without any explicit register-call boilerplate.
"""

from mostlyright.core.validator import _SCHEMA_REGISTRY, register_schema

from .forecast import ForecastSchema, StationForecastSchema
from .forecast_nwp import NwpForecastSchema
from .observation import ObservationSchema
from .observation_ledger import ObservationLedgerSchema
from .observation_qc import ObservationQCSchema
from .settlement import SettlementSchema

# Eager registration — Validator can look up each schema by ID immediately.
register_schema(ObservationSchema)
# Phase 20 OM-02: register canonical StationForecastSchema FIRST so the
# canonical schema_id wins on any registry-iteration that visits in
# insertion order; ForecastSchema (back-compat alias to
# schema.forecast.iem_mos.v1) registers second.
register_schema(StationForecastSchema)
register_schema(ForecastSchema)
register_schema(SettlementSchema)
# Phase 2.1 additions.
register_schema(ObservationLedgerSchema)
register_schema(ObservationQCSchema)
# Phase 3.2 addition.
register_schema(NwpForecastSchema)

#: Public alias for the validator's registry dict, so callers and tests
#: can look up schemas by id without reaching into ``core.validator``'s
#: underscored internal. Phase 20 OM-02.
SCHEMA_REGISTRY = _SCHEMA_REGISTRY

__all__ = [
    "SCHEMA_REGISTRY",
    "ForecastSchema",
    "NwpForecastSchema",
    "ObservationLedgerSchema",
    "ObservationQCSchema",
    "ObservationSchema",
    "SettlementSchema",
    "StationForecastSchema",
]

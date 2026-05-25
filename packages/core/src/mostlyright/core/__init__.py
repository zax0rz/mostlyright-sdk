"""mostlyright.core — temporal safety + schema + format primitives.

The architectural spine of the mostlyright SDK. Originally ported from
the ``mostlyright-mcp`` wave-1-core branch (lift provenance preserved in
per-module docstrings); promoted from the ``_v02`` reference into the
canonical namespace in Phase 2 of the v0.1.0 plan.

Sub-modules:

- :mod:`mostlyright.core.exceptions` — structured exception hierarchy
  (``TradewindsError`` base + 6 subclasses + JSON-safe ``to_dict``).
  ``MostlyRightMCPError`` remains importable as a deprecation alias.
- :mod:`mostlyright.core.temporal` — UTC-aware ``TimePoint`` wrapper;
  ``KnowledgeView`` + ``LeakageDetector`` (Phase 2 Wave 2).
- :mod:`mostlyright.core.schema` — declarative ``Schema`` framework with
  audit-log seam used by the source-identity ``Validator``.
- :mod:`mostlyright.core.schemas` — three canonical schema instances
  (observation, forecast, settlement).
- :mod:`mostlyright.core.formats` — five lossless format serializers
  (``dataframe`` / ``json`` / ``parquet`` / ``toon`` / ``csv``).
"""

# Importing mostlyright.core.schemas triggers eager registration of the
# three canonical schemas with the Validator (see schemas/__init__.py).
import mostlyright.core.schemas  # noqa: F401
from mostlyright.core.exceptions import (
    LeakageError,
    PayloadTooLargeError,
    SchemaValidationError,
    SourceMismatchError,
    SourceUnavailableError,
    TemporalDriftError,
    TradewindsError,
)
from mostlyright.core.result import TradewindsResult
from mostlyright.core.schema import ColumnSpec, Schema, SchemaRegistration
from mostlyright.core.temporal import (
    KnowledgeView,
    LeakageDetector,
    TimePoint,
    assert_no_leakage,
)
from mostlyright.core.validator import validate_dataframe

__all__ = [
    "ColumnSpec",
    "KnowledgeView",
    "LeakageDetector",
    "LeakageError",
    "PayloadTooLargeError",
    "Schema",
    "SchemaRegistration",
    "SchemaValidationError",
    "SourceMismatchError",
    "SourceUnavailableError",
    "TemporalDriftError",
    "TimePoint",
    "TradewindsError",
    "TradewindsResult",
    "assert_no_leakage",
    "validate_dataframe",
]

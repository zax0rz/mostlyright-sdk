"""tradewinds.core — temporal safety + schema + format primitives.

The architectural spine of the tradewinds SDK. Originally ported from
the ``mostlyright-mcp`` wave-1-core branch (lift provenance preserved in
per-module docstrings); promoted from the ``_v02`` reference into the
canonical namespace in Phase 2 of the v0.1.0 plan.

Sub-modules:

- :mod:`tradewinds.core.exceptions` — structured exception hierarchy
  (``TradewindsError`` base + 6 subclasses + JSON-safe ``to_dict``).
  ``MostlyRightMCPError`` remains importable as a deprecation alias.
- :mod:`tradewinds.core.temporal` — UTC-aware ``TimePoint`` wrapper;
  ``KnowledgeView`` + ``LeakageDetector`` (Phase 2 Wave 2).
- :mod:`tradewinds.core.schema` — declarative ``Schema`` framework with
  audit-log seam used by the source-identity ``Validator``.
- :mod:`tradewinds.core.schemas` — three canonical schema instances
  (observation, forecast, settlement).
- :mod:`tradewinds.core.formats` — five lossless format serializers
  (``dataframe`` / ``json`` / ``parquet`` / ``toon`` / ``csv``).
"""

# Importing tradewinds.core.schemas triggers eager registration of the
# three canonical schemas with the Validator (see schemas/__init__.py).
import tradewinds.core.schemas  # noqa: F401
from tradewinds.core.exceptions import (
    LeakageError,
    PayloadTooLargeError,
    SchemaValidationError,
    SourceMismatchError,
    SourceUnavailableError,
    TemporalDriftError,
    TradewindsError,
)
from tradewinds.core.result import TradewindsResult
from tradewinds.core.schema import ColumnSpec, Schema, SchemaRegistration
from tradewinds.core.temporal import (
    KnowledgeView,
    LeakageDetector,
    TimePoint,
    assert_no_leakage,
)
from tradewinds.core.validator import validate_dataframe

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

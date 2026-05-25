"""Capabilities and schema introspection for the tradewinds SDK.

Provides:
  - _METHOD_INDEX: structured summary of all public SDK methods
  - _SCHEMA_FILES: mapping of entity names to spec filenames
  - _SCHEMA_CACHE: in-process cache of loaded JSON schemas
  - load_schema(): load a JSON schema from specs/ by entity name
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Schema file mapping
# "pairs" is intentionally omitted — specs/settlement-join.json describes the
# observation-settlement join schema, not the pairs() output columns.
# A specs/pairs.json spec is deferred to Sprint 4. Until then, use
# feature_catalog(source_filter="pairs") to inspect pairs columns.
# ---------------------------------------------------------------------------

_SCHEMA_FILES: dict[str, str] = {
    "observation": "observation.json",
    "climate": "climate.json",
    "snapshot": "snapshot.json",
    "data_version": "data_version.json",
    "forecast": "forecast.json",
    "forecast_series": "forecast_series.json",
    "candle": "candle.json",
    "market": "market.json",
    "market_unified": "market_unified.json",
    "synoptic_extremes": "synoptic_extremes.json",
    "omo": "omo.json",
    # brackets.json is available for bracket/range queries
    "brackets": "brackets.json",
    # Phase 3.1 — daily_extreme.v1 resolution schema for daily_extremes() rollup.
    "daily_extreme": "daily_extreme.json",
}

# 5 additional specs ship in ``tradewinds/_internal/specs/`` but are intentionally
# not exposed via ``client.schema()``:
#   - event.json            — Kalshi event metadata (Sprint 3)
#   - series.json           — Kalshi series (Sprint 3)
#   - settlement_record.json — Kalshi settlement records (Sprint 3)
#   - settlement-join.json  — internal observation↔settlement join contract
#   - book_snapshot.json    — order-book snapshot (Sprint 3+)
#
# They ride in the wheel because validation/ and ingest/ test suites use
# them, and that's cheaper than maintaining a separate "tests-only" resource
# bundle. When a Sprint 3 API surfaces them, lift them into ``_SCHEMA_FILES``
# so ``client.schema()`` can reach them publicly. Until then they're
# inspectable but not part of the documented SDK contract.

_SCHEMA_CACHE: dict[str, dict[str, Any]] = {}

# Path to the specs/ directory that ships inside the ``tradewinds`` wheel.
# Before 0.14.1 this pointed at the repo-root ``specs/`` via
# ``parent.parent.parent``, which works for editable / source installs but
# broke in every pip-installed environment — the wheel never shipped the
# specs. Vu caught it with ``client.schema('observation')`` returning
# FileNotFoundError in a clean PyPI install.
#
# Moving specs into the package (``tradewinds/_internal/specs/``) means
# ``Path(__file__).parent / "specs"`` resolves to the packaged copy in
# both wheel and source layouts — single path, no fallback logic.
SPECS_DIR: Path = Path(__file__).parent / "specs"

# Backward-compat alias: the pre-0.14.1 private name. Downstream code
# still imports this; new code should use ``SPECS_DIR``.
_SPECS_DIR: Path = SPECS_DIR


def load_schema(entity: str) -> dict[str, Any]:
    """Load and return the JSON Schema for a data entity.

    Args:
        entity: Entity name (e.g. "observation", "climate").

    Returns:
        Parsed JSON Schema dict.

    Raises:
        ValueError: If entity is not in the supported set.
    """
    if entity not in _SCHEMA_FILES:
        valid = sorted(_SCHEMA_FILES)
        raise ValueError(
            f"Unknown entity {entity!r}. "
            f"Supported: {valid}. "
            f"Note: 'pairs' is not supported — see feature_catalog(source_filter='pairs')."
        )
    # Codex review W2-C P2 fix: dict(...) only copies the top-level mapping;
    # nested objects (properties, $ref blocks) remain shared with _SCHEMA_CACHE.
    # Caller-side mutations would corrupt every subsequent load_schema() call
    # process-wide. Deep-copy so the contract holds.
    if entity in _SCHEMA_CACHE:
        return copy.deepcopy(_SCHEMA_CACHE[entity])

    spec_path = SPECS_DIR / _SCHEMA_FILES[entity]
    with spec_path.open() as f:
        schema = json.load(f)
    _SCHEMA_CACHE[entity] = schema
    return copy.deepcopy(schema)


# ---------------------------------------------------------------------------
# Method index — structured summary of all public SDK methods
# Used by capabilities() to return a machine-readable method index.
# ---------------------------------------------------------------------------

_METHOD_INDEX: list[dict[str, Any]] = [
    {
        "name": "observations",
        "description": "Get weather observations with optional temporal transform DSL.",
        "required_params": ["station"],
        "optional_params": [
            "from_date",
            "to_date",
            "as_of",
            "obs_type",
            "resolution",
            "units",
            "tz",
            "format",
            "columns",
            "features",
            "limit",
            "offset",
            "as_dataframe",
            "save_path",
        ],
    },
    {
        "name": "climate",
        "description": "Get daily climate reports.",
        "required_params": ["station"],
        "optional_params": [
            "from_date",
            "to_date",
            "units",
            "format",
            "columns",
            "limit",
            "offset",
            "as_dataframe",
            "save_path",
        ],
    },
    {
        "name": "climate_gaps",
        "description": "Find gaps in climate history.",
        "required_params": ["station"],
        "optional_params": ["from_date", "to_date", "as_dataframe"],
    },
    {
        "name": "data_version",
        "description": "Return a reproducible version token for the dataset at a point in time.",
        "required_params": ["station", "as_of"],
        "optional_params": ["from_date", "to_date"],
    },
    {
        "name": "snapshot",
        "description": "Return everything an AI agent would have known at UTC moment as_of.",
        "required_params": ["station", "as_of"],
        "optional_params": [
            "cli_publication_delay_hours",
            "include_forecast",
            "tz_override",
            "format",
        ],
    },
    {
        "name": "pairs",
        "description": "Return one row per settlement date joining observations + climate + forecast.",
        "required_params": ["station", "from_date", "to_date"],
        "optional_params": [
            "include_forecast",
            "forecast_model",
            "as_dataframe",
            "format",
        ],
    },
    {
        "name": "forecasts",
        "description": "Historical IEM MOS forecasts (discrete runs with issued_at).",
        "required_params": ["station"],
        "optional_params": [
            "from_date",
            "to_date",
            "model",
            "format",
            "columns",
            "as_dataframe",
            "save_path",
        ],
    },
    {
        "name": "forecast_series",
        "description": "Historical Open-Meteo forecast series (seamless hourly).",
        "required_params": ["station"],
        "optional_params": [
            "from_date",
            "to_date",
            "model",
            "format",
            "columns",
            "as_dataframe",
            "save_path",
        ],
    },
    {
        "name": "feature_catalog",
        "description": "Return all available features with descriptions and metadata.",
        "required_params": [],
        "optional_params": ["include_transforms", "source_filter", "format"],
    },
    {
        "name": "describe",
        "description": "Return an LLM-ready summary of available features for a station.",
        "required_params": ["station"],
        "optional_params": [],
    },
    {
        "name": "availability",
        "description": "Return actual data availability for a station.",
        "required_params": ["station"],
        "optional_params": ["as_of", "data_type"],
    },
    {
        "name": "stations",
        "description": "Return all stations with active Kalshi markets and SDK support.",
        "required_params": [],
        "optional_params": [],
    },
    {
        "name": "station",
        "description": "Return metadata for a single station by code.",
        "required_params": ["code"],
        "optional_params": [],
    },
    {
        "name": "schema",
        "description": "Return the JSON Schema for a data entity.",
        "required_params": ["entity"],
        "optional_params": [],
    },
    {
        "name": "as_tools",
        "description": "Return Anthropic-compatible tool definitions for all callable SDK methods.",
        "required_params": [],
        "optional_params": ["include_market", "include_experimental"],
    },
    {
        "name": "capabilities",
        "description": "Return a structured summary of all SDK methods and their parameters.",
        "required_params": [],
        "optional_params": [],
    },
    {
        "name": "estimate_tokens",
        "description": "Estimate token count for a data query without fetching records.",
        "required_params": ["station", "from_date", "to_date"],
        "optional_params": ["method", "format", "columns"],
    },
    {
        "name": "stream",
        "description": "Async generator yielding new METAR observations from AWC.",
        "required_params": ["station"],
        "optional_params": ["interval", "max_obs", "units", "timeout"],
    },
]

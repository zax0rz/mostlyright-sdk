"""Tests for ``mostlyright._internal._capabilities``.

Lifted from ``monorepo-v0.14.1/tests/test_sdk_stations.py`` (the
``schema()`` + ``capabilities()`` blocks). The original file mixed
``MostlyRightClient``-level tests with module-level tests; only the
module-level tests (``load_schema``, ``_SCHEMA_CACHE``, ``_METHOD_INDEX``,
``_SCHEMA_FILES``) survive the lift — the client-level tests will follow
when ``MostlyRightClient`` is lifted in a later wave.

A spec-loading smoke test is added at the bottom to verify the
``Path(__file__).parent / "specs"`` resolution works in editable installs.
"""

from __future__ import annotations

import pytest
from mostlyright._internal._capabilities import (
    _METHOD_INDEX,
    _SCHEMA_CACHE,
    _SCHEMA_FILES,
    SPECS_DIR,
    load_schema,
)

# ---------------------------------------------------------------------------
# load_schema()
# ---------------------------------------------------------------------------


def test_load_schema_observation_has_required_fields():
    schema = load_schema("observation")
    assert "required" in schema or "properties" in schema


def test_load_schema_climate_returns_dict():
    schema = load_schema("climate")
    assert isinstance(schema, dict)
    assert "$schema" in schema or "properties" in schema


def test_load_schema_unknown_entity_raises_value_error():
    with pytest.raises(ValueError, match="Unknown entity"):
        load_schema("not_a_real_entity")


def test_load_schema_pairs_raises_value_error():
    # "pairs" is explicitly unsupported (specs/pairs.json doesn't exist yet)
    with pytest.raises(ValueError):
        load_schema("pairs")


def test_load_schema_caches_after_first_load():
    _SCHEMA_CACHE.clear()
    load_schema("observation")
    assert "observation" in _SCHEMA_CACHE
    # Second call returns cached version
    result2 = load_schema("observation")
    assert isinstance(result2, dict)


def test_load_schema_returns_copy_not_mutable_original():
    _SCHEMA_CACHE.clear()
    schema1 = load_schema("observation")
    schema1["__test_injection__"] = True
    schema2 = load_schema("observation")
    assert "__test_injection__" not in schema2


# ---------------------------------------------------------------------------
# Phase 3.1 — daily_extreme.v1
# ---------------------------------------------------------------------------


def test_load_schema_daily_extreme_has_required_fields():
    """daily_extreme.v1 ships with station/local_date/n_obs required."""
    schema = load_schema("daily_extreme")
    assert isinstance(schema, dict)
    assert schema["title"].startswith("Daily Extreme")
    assert set(schema["required"]) >= {"station", "local_date", "n_obs"}
    props = schema["properties"]
    # Nullable extremes.
    for col in ("tmin_c", "tmax_c", "tmean_c", "source_tmin", "source_tmax"):
        assert col in props, f"missing column {col}"
    # n_obs must be a non-negative integer.
    assert props["n_obs"]["type"] == "integer"
    assert props["n_obs"]["minimum"] == 0


def test_daily_extreme_in_schema_files_mapping():
    assert "daily_extreme" in _SCHEMA_FILES
    assert _SCHEMA_FILES["daily_extreme"] == "daily_extreme.json"


# ---------------------------------------------------------------------------
# _METHOD_INDEX
# ---------------------------------------------------------------------------


def test_method_index_is_nonempty_list():
    assert isinstance(_METHOD_INDEX, list)
    assert len(_METHOD_INDEX) > 0


def test_method_index_contains_expected_methods():
    method_names = {m["name"] for m in _METHOD_INDEX}
    expected = {
        "observations",
        "climate",
        "climate_gaps",
        "data_version",
        "snapshot",
        "pairs",
        "feature_catalog",
        "describe",
        "availability",
        "stations",
        "station",
        "schema",
        "as_tools",
        "capabilities",
        "estimate_tokens",
        "stream",
    }
    assert expected <= method_names


def test_method_index_entries_have_required_keys():
    for entry in _METHOD_INDEX:
        assert "name" in entry
        assert "description" in entry
        assert "required_params" in entry
        assert "optional_params" in entry
        assert isinstance(entry["required_params"], list)
        assert isinstance(entry["optional_params"], list)


# ---------------------------------------------------------------------------
# _SCHEMA_FILES
# ---------------------------------------------------------------------------


def test_schema_files_excludes_pairs():
    # The "pairs" entity is intentionally absent (see _capabilities.py).
    assert "pairs" not in _SCHEMA_FILES


def test_schema_files_includes_core_entities():
    expected = {
        "observation",
        "climate",
        "snapshot",
        "data_version",
        "forecast",
        "forecast_series",
        "candle",
        "market",
        "market_unified",
        "synoptic_extremes",
        "omo",
        "brackets",
    }
    assert expected <= set(_SCHEMA_FILES)


# ---------------------------------------------------------------------------
# Spec-loading smoke test — verifies SPECS_DIR resolves correctly under
# an editable install (`uv sync` / `pip install -e .`) and every entity
# in _SCHEMA_FILES actually has its JSON shipped in the package.
# ---------------------------------------------------------------------------


def test_specs_dir_is_inside_package():
    assert SPECS_DIR.is_dir(), (
        f"specs/ not found at {SPECS_DIR}. The hatch wheel target may be "
        "missing the JSON spec files."
    )


def test_load_schema_observation_smoke():
    """Smoke test: load_schema('observation') returns a dict with the
    expected JSON Schema top-level keys.
    """
    schema = load_schema("observation")
    assert isinstance(schema, dict)
    assert "$schema" in schema
    assert "type" in schema
    assert "properties" in schema


@pytest.mark.parametrize("entity", sorted(_SCHEMA_FILES))
def test_every_public_entity_loads(entity: str):
    """Every entity in ``_SCHEMA_FILES`` must have its JSON spec shipped
    inside the package and parse as a dict.
    """
    schema = load_schema(entity)
    assert isinstance(schema, dict)

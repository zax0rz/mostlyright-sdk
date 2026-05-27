"""Phase 20 OM-02: JSON Schema codegen output for station.v1 + iem_mos.v1 alias."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import pytest

# packages/core/tests/test_schemas_codegen.py → repo root is parents[3].
PROJECT_ROOT = Path(__file__).resolve().parents[3]
SCHEMAS_DIR = PROJECT_ROOT / "schemas" / "json"
STATION_JSON = SCHEMAS_DIR / "schema.forecast.station.v1.json"
IEM_MOS_JSON = SCHEMAS_DIR / "schema.forecast.iem_mos.v1.json"
EXPORT_SCRIPT = PROJECT_ROOT / "scripts" / "export_schemas.py"

# The exporter currently uses the ``mostlyright.dev`` $id host (Phase 12.1
# transitional). The ``mostlyright.md`` rename will be a separate cross-cutting
# change with its own CI sync; until then, codegen tests assert the host the
# script actually emits.
_BASE_URL = "https://mostlyright.dev/schemas"


@pytest.fixture(scope="module", autouse=True)
def regenerate_schemas() -> None:
    """Re-run export_schemas.py at module load so tests see fresh output."""
    subprocess.run(
        ["uv", "run", "python", str(EXPORT_SCRIPT)],
        cwd=PROJECT_ROOT,
        check=True,
    )


def test_station_v1_json_file_exists() -> None:
    assert STATION_JSON.exists(), f"expected file at {STATION_JSON}"


def test_iem_mos_v1_json_file_exists() -> None:
    assert IEM_MOS_JSON.exists(), f"expected file at {IEM_MOS_JSON}"


def test_station_v1_id_url() -> None:
    data = json.loads(STATION_JSON.read_text())
    assert data["$id"] == f"{_BASE_URL}/schema.forecast.station.v1.json"


def test_iem_mos_v1_id_url() -> None:
    data = json.loads(IEM_MOS_JSON.read_text())
    assert data["$id"] == f"{_BASE_URL}/schema.forecast.iem_mos.v1.json"


def test_station_v1_property_count() -> None:
    data = json.loads(STATION_JSON.read_text())
    # 26 = 7 required identity + 6 IEM MOS core nullable + 13 OM extras nullable
    assert len(data["properties"]) == 26


def test_station_v1_required_columns() -> None:
    data = json.loads(STATION_JSON.read_text())
    assert set(data["required"]) == {
        "station",
        "issued_at",
        "valid_at",
        "forecast_hour",
        "model",
        "source",
        "retrieved_at",
    }


def test_iem_mos_v1_properties_match_station_v1() -> None:
    """The alias must have the same column set (only $id differs)."""
    station = json.loads(STATION_JSON.read_text())
    iem_mos = json.loads(IEM_MOS_JSON.read_text())
    assert station["properties"] == iem_mos["properties"]
    assert station["required"] == iem_mos["required"]


def test_nullable_column_uses_union_type() -> None:
    data = json.loads(STATION_JSON.read_text())
    apparent = data["properties"]["apparent_temp_c"]
    # nullable=True → ["null", "number"] union (sorted) per export_schemas.py
    # _column_to_property.
    type_val = apparent["type"]
    assert isinstance(type_val, list)
    assert "null" in type_val
    assert "number" in type_val


def test_required_column_not_null_union() -> None:
    data = json.loads(STATION_JSON.read_text())
    station_prop = data["properties"]["station"]
    type_val = station_prop["type"]
    # Required: scalar string type, no null
    assert type_val == "string"


def test_export_idempotent() -> None:
    """Running export_schemas.py twice must produce identical bytes."""
    h1 = hashlib.sha256(STATION_JSON.read_bytes()).hexdigest()
    subprocess.run(
        ["uv", "run", "python", str(EXPORT_SCRIPT)],
        cwd=PROJECT_ROOT,
        check=True,
    )
    h2 = hashlib.sha256(STATION_JSON.read_bytes()).hexdigest()
    assert h1 == h2, "export_schemas.py output is non-deterministic"

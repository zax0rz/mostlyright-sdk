"""Canonical schema exporter (TS-W0 Wave 2).

Reads the Python canonical sources under ``packages/`` and emits the
``schemas/`` directory consumed by ``@tradewinds/codegen`` for the TS
SDK. Every output is byte-deterministic so the ``schema-drift.yml`` CI
gate can run the exporter twice and assert ``git diff --exit-code``.

Determinism rules (load-bearing):

- ``json.dumps(..., sort_keys=True, indent=2, ensure_ascii=True)``
  for every file written.
- Trailing newline after each JSON file (POSIX text-file convention).
- No wall-clock fields; no machine-specific paths.
- Enum values are sorted lexicographically in the JSON Schema output.
- The order of ``Schema.COLUMNS`` is preserved (column order is
  semantically meaningful); the property dict per column is keyed
  with ``sort_keys=True`` so internal field order is stable.
- The ``EXPORT_MANIFEST.json`` lists files sorted by ``path`` and
  records each file's SHA-256 of the bytes on disk.

CLI surface:

- ``python scripts/export_schemas.py`` — writes outputs into the
  default ``schemas/`` directory (repo-root sibling of ``scripts/``).
- ``python scripts/export_schemas.py --check`` — runs the exporter
  twice **in memory**, asserts byte-equality across runs, exits 0/1.
- ``python scripts/export_schemas.py --out-dir <path>`` — override
  the output directory (used by ``tests/test_export_schemas.py``).

See ``.planning/CROSS-SDK-SYNC.md`` §1.2 for the full output list +
determinism rules and ``.planning/REQUIREMENTS.md`` TS-CODEGEN-01 for
the acceptance criteria.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Path setup so the exporter is runnable from anywhere.
# ---------------------------------------------------------------------------

_REPO_ROOT: Path = Path(__file__).resolve().parents[1]
_DEFAULT_OUT_DIR: Path = _REPO_ROOT / "schemas"

# Add each packages/<pkg>/src to sys.path so we can `import tradewinds.*`
# without requiring the workspace to be `uv sync`'d first. ``uv run`` /
# ``uv sync`` users will already have these on ``sys.path``; the explicit
# prepend is a no-op in that case but is what lets the exporter run from a
# bare ``python scripts/export_schemas.py`` shell, which the CI workflow
# does as a sanity check.
for _pkg in ("core", "weather", "markets"):
    _src = _REPO_ROOT / "packages" / _pkg / "src"
    if _src.is_dir():
        _src_str = str(_src)
        if _src_str not in sys.path:
            sys.path.insert(0, _src_str)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: JSON Schema dialect emitted on every per-schema file.
_JSON_SCHEMA_DIALECT: str = "https://json-schema.org/draft/2020-12/schema"

#: ColumnSpec.dtype → JSON Schema type / format mapping. ``enum`` is
#: handled inline because the enum values list lives on the ColumnSpec.
_DTYPE_TO_JSON_SCHEMA: dict[str, dict[str, Any]] = {
    "string": {"type": "string"},
    "float64": {"type": "number"},
    "int64": {"type": "integer"},
    "timestamp_utc": {"type": "string", "format": "date-time"},
    "date": {"type": "string", "format": "date"},
    "bool": {"type": "boolean"},
}

#: The five Group A canonical schemas (always emitted from TS-W0).
_GROUP_A_SCHEMA_IDS: tuple[str, ...] = (
    "schema.observation.v1",
    "schema.forecast.iem_mos.v1",
    "schema.settlement.cli.v1",
    "schema.observation_ledger.v1",
    "schema.observation_qc.v1",
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _dumps(payload: Any) -> str:
    """Canonical JSON dump — sorted keys, 2-space indent, trailing newline.

    Returns a ``str`` (not ``bytes``) so callers can hash either form. The
    trailing newline matches POSIX text-file convention and is what every
    POSIX editor / git-friendly tool expects; it also keeps ``git diff``
    output free of "no newline at end of file" markers.
    """
    return json.dumps(payload, sort_keys=True, indent=2, ensure_ascii=True) + "\n"


def _sha256_hex(content: bytes) -> str:
    """Return the SHA-256 hex digest of ``content``."""
    return hashlib.sha256(content).hexdigest()


def _version_from_schema_id(schema_id: str) -> str:
    """Pull the trailing ``v<N>`` segment off a schema_id (or ``""``).

    ``"schema.observation.v1"`` → ``"v1"``. Returns ``""`` if the schema_id
    does not end in a recognisable version tag — the JSON Schema is still
    emitted but downstream consumers can detect the missing version.
    """
    if not schema_id:
        return ""
    tail = schema_id.rsplit(".", 1)[-1]
    if tail.startswith("v") and tail[1:].isdigit():
        return tail
    return ""


# ---------------------------------------------------------------------------
# Per-schema JSON-Schema rendering
# ---------------------------------------------------------------------------


def _column_to_property(column: Any) -> dict[str, Any]:
    """Translate a ColumnSpec into a JSON-Schema property dict.

    Nullable columns are emitted as ``"type": ["null", <scalar>]`` (sorted
    lexicographically) — the draft-2020-12 idiom. The OpenAPI-style
    ``"nullable": true`` sibling is NOT emitted because draft-2020-12 doesn't
    recognise it (ajv standalone in TS-W3 would reject ``null`` values, and
    json-schema-to-typescript would not add ``| null`` to the generated TS
    type). See TS-W0 iter-1 HIGH 1.

    For nullable enum columns, ``null`` is also appended to the ``enum``
    array (after the sorted string values). Under draft-2020-12 ``enum`` is
    enforced independently of ``type`` — without this, a ``null`` value
    would pass the type-check but fail the enum-check (e.g.
    ``"None is not one of ['BKN', 'CLR', ...]"``). ``null`` is placed last
    for deterministic, human-readable output. See TS-W0 iter-2 HIGH.
    """
    dtype = column.dtype
    if dtype == "enum":
        prop: dict[str, Any] = {
            "type": "string",
            "enum": sorted(column.enum_values or ()),
        }
    else:
        base = _DTYPE_TO_JSON_SCHEMA.get(dtype)
        if base is None:
            raise ValueError(f"Unknown ColumnSpec dtype {dtype!r} on column {column.name!r}")
        prop = dict(base)

    # Build the description from notes + units. Both are optional; we want a
    # readable, sortable, deterministic string. Units appear first (matches
    # the convention in ``docs/design.md`` §A) when present.
    desc_parts: list[str] = []
    if column.units:
        desc_parts.append(f"units: {column.units}")
    if column.notes:
        desc_parts.append(column.notes)
    if desc_parts:
        prop["description"] = " — ".join(desc_parts)

    if column.nullable:
        # Promote scalar ``type`` to a sorted [null, scalar] union. ``type``
        # is always a string here (set above from _DTYPE_TO_JSON_SCHEMA or
        # the enum branch); we never need to handle a pre-existing list.
        scalar = prop.get("type")
        if isinstance(scalar, str):
            prop["type"] = sorted([scalar, "null"])
        # For enum columns, ``null`` must also be a member of ``enum`` —
        # draft-2020-12 enforces ``enum`` independently of ``type``. Append
        # ``None`` after the (already sorted) string values for a
        # deterministic, human-readable ordering.
        if dtype == "enum":
            prop["enum"] = [*list(prop["enum"]), None]

    return prop


def _render_schema(schema_cls: Any) -> dict[str, Any]:
    """Render one ``Schema`` subclass into its JSON-Schema dict."""
    schema_id = schema_cls.schema_id
    version = _version_from_schema_id(schema_id)
    properties: dict[str, Any] = {}
    required: list[str] = []
    for column in schema_cls.COLUMNS:
        properties[column.name] = _column_to_property(column)
        if not column.nullable:
            required.append(column.name)

    payload: dict[str, Any] = {
        "$schema": _JSON_SCHEMA_DIALECT,
        "$id": f"https://tradewinds.dev/schemas/{schema_id}.json",
        "title": schema_id,
        "type": "object",
        "version": version,
        "properties": properties,
        "required": sorted(required),
    }
    if getattr(schema_cls, "IMPERIAL_RENAMES", None):
        # Non-standard sibling key — ``properties`` are canonical metric
        # names; ``imperialRenames`` documents the metric→imperial alias
        # map without polluting the JSON-Schema validation surface.
        payload["imperialRenames"] = dict(schema_cls.IMPERIAL_RENAMES)
    return payload


# ---------------------------------------------------------------------------
# Output payload builders
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _OutputFile:
    """A single output file in the schemas/ tree.

    ``rel_path`` is forward-slash-joined and rooted at the schemas/
    output directory.
    ``content`` is the canonical UTF-8 bytes that get written verbatim.
    ``gated`` is True if the file is a stub for a missing Group B source.
    """

    rel_path: str
    content: bytes
    gated: bool = False


def _gated_payload(reason: str) -> str:
    """Canonical-JSON gated-stub payload for missing Group B sources."""
    return _dumps({"gated": True, "reason": reason})


def _build_group_a_schemas() -> list[_OutputFile]:
    """Render the 5 Group A schemas under schemas/json/."""
    from tradewinds.core.schemas import (
        ForecastSchema,
        ObservationLedgerSchema,
        ObservationQCSchema,
        ObservationSchema,
        SettlementSchema,
    )

    by_id: dict[str, Any] = {
        ObservationSchema.schema_id: ObservationSchema,
        ForecastSchema.schema_id: ForecastSchema,
        SettlementSchema.schema_id: SettlementSchema,
        ObservationLedgerSchema.schema_id: ObservationLedgerSchema,
        ObservationQCSchema.schema_id: ObservationQCSchema,
    }
    out: list[_OutputFile] = []
    for schema_id in _GROUP_A_SCHEMA_IDS:
        schema_cls = by_id[schema_id]
        payload = _render_schema(schema_cls)
        rel = f"json/{schema_id}.json"
        out.append(_OutputFile(rel_path=rel, content=_dumps(payload).encode("utf-8")))
    return out


def _build_stations() -> _OutputFile:
    """Emit ``schemas/stations.json`` — all 60+ stations, sorted by ICAO."""
    from tradewinds._internal._stations import STATIONS

    entries: list[dict[str, Any]] = []
    for info in STATIONS.values():
        entries.append(
            {
                "code": info.code,
                "ghcnh_id": info.ghcnh_id or None,
                "icao": info.icao,
                "name": info.name,
                "tz": info.tz,
                "latitude": info.latitude,
                "longitude": info.longitude,
                "country": info.country,
            }
        )
    entries.sort(key=lambda row: row["icao"])
    payload = {"stations": entries}
    return _OutputFile(
        rel_path="stations.json",
        content=_dumps(payload).encode("utf-8"),
    )


def _build_kalshi() -> _OutputFile:
    """Emit ``schemas/kalshi-settlement-stations.json``."""
    from tradewinds.markets.catalog.kalshi_stations import (
        KALSHI_SETTLEMENT_STATIONS,
        KNOWN_WRONG_STATIONS,
    )

    stations: dict[str, dict[str, str]] = {}
    for city in sorted(KALSHI_SETTLEMENT_STATIONS):
        sc = KALSHI_SETTLEMENT_STATIONS[city]
        stations[city] = {"station": sc.station, "citation": sc.citation}
    payload = {
        "stations": stations,
        "known_wrong": sorted(KNOWN_WRONG_STATIONS),
    }
    return _OutputFile(
        rel_path="kalshi-settlement-stations.json",
        content=_dumps(payload).encode("utf-8"),
    )


def _build_source_priority() -> _OutputFile:
    """Emit ``schemas/source-priority.json``."""
    from tradewinds._internal.merge.climate import REPORT_TYPE_PRIORITY
    from tradewinds._internal.merge.observations import SOURCE_PRIORITY
    from tradewinds.core.merge import LIVE_V1

    payload = {
        "observation": dict(SOURCE_PRIORITY),
        "climate": dict(REPORT_TYPE_PRIORITY),
        "live_v1": {
            "name": LIVE_V1.name,
            "source_priority": dict(LIVE_V1.source_priority),
            "secondary_key": list(LIVE_V1.secondary_key),
        },
    }
    return _OutputFile(
        rel_path="source-priority.json",
        content=_dumps(payload).encode("utf-8"),
    )


def _build_polymarket_city_stations() -> _OutputFile:
    """Group B — emit ``schemas/polymarket-city-stations.json`` if source exists."""
    rel = "polymarket-city-stations.json"
    try:
        from tradewinds.markets._per_event_station import load_polymarket_city_stations
    except ImportError:
        return _OutputFile(
            rel_path=rel,
            content=_gated_payload(
                "Python source markets._per_event_station.load_polymarket_city_stations "
                "not materialized in packages/"
            ).encode("utf-8"),
            gated=True,
        )

    try:
        raw = load_polymarket_city_stations()
    except Exception as exc:  # pragma: no cover — defensive
        return _OutputFile(
            rel_path=rel,
            content=_gated_payload(
                "Python source markets._per_event_station.load_polymarket_city_stations "
                f"raised at call time: {type(exc).__name__}"
            ).encode("utf-8"),
            gated=True,
        )

    if not raw:
        return _OutputFile(
            rel_path=rel,
            content=_gated_payload(
                "Python source markets._per_event_station.load_polymarket_city_stations "
                "returned empty payload"
            ).encode("utf-8"),
            gated=True,
        )

    # `raw` is `{city: {measure: station, ...}, ...}` — preserve that shape.
    cities = {city: dict(raw[city]) for city in sorted(raw)}
    payload = {"cities": cities}
    return _OutputFile(rel_path=rel, content=_dumps(payload).encode("utf-8"))


def _build_qc_alpha_rules() -> _OutputFile:
    """Group B — emit ``schemas/qc-alpha-rules.json`` if source exists."""
    rel = "qc-alpha-rules.json"
    try:
        from tradewinds.qc import ALPHA_RULES
    except ImportError:
        return _OutputFile(
            rel_path=rel,
            content=_gated_payload(
                "Python source tradewinds.qc.ALPHA_RULES not materialized in packages/"
            ).encode("utf-8"),
            gated=True,
        )

    rules: list[dict[str, Any]] = []
    for rule in sorted(ALPHA_RULES, key=lambda r: r.bit_position):
        rules.append(
            {
                "rule_id": rule.rule_id,
                "bit_position": rule.bit_position,
                "description": rule.description,
                "field": rule.rule_id.split(".", 1)[0],
            }
        )
    payload = {"schema_version": "v1", "rules": rules}
    return _OutputFile(rel_path=rel, content=_dumps(payload).encode("utf-8"))


# ---------------------------------------------------------------------------
# Manifest assembly
# ---------------------------------------------------------------------------


def _build_manifest(files: list[_OutputFile]) -> _OutputFile:
    """Build the ``EXPORT_MANIFEST.json`` listing every file + SHA-256."""
    entries = [
        {
            "path": f.rel_path,
            "sha256": _sha256_hex(f.content),
            "size_bytes": len(f.content),
            "gated": f.gated,
        }
        for f in files
    ]
    entries.sort(key=lambda e: e["path"])
    payload = {"files": entries}
    return _OutputFile(
        rel_path="EXPORT_MANIFEST.json",
        content=_dumps(payload).encode("utf-8"),
    )


def build_all_outputs() -> list[_OutputFile]:
    """Build every output file as in-memory bytes.

    The list is sorted by ``rel_path`` so the manifest output and
    on-disk write order are deterministic regardless of caller.
    """
    files: list[_OutputFile] = []
    files.extend(_build_group_a_schemas())
    files.append(_build_stations())
    files.append(_build_kalshi())
    files.append(_build_source_priority())
    files.append(_build_polymarket_city_stations())
    files.append(_build_qc_alpha_rules())
    manifest = _build_manifest(files)
    files.append(manifest)
    files.sort(key=lambda f: f.rel_path)
    return files


# ---------------------------------------------------------------------------
# I/O
# ---------------------------------------------------------------------------


def write_outputs(out_dir: Path, files: list[_OutputFile]) -> None:
    """Write every ``_OutputFile`` to ``out_dir`` (creating parents)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    for f in files:
        target = out_dir / f.rel_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(f.content)


def _check_determinism() -> int:
    """Build outputs twice in memory; assert byte-equality. Returns 0/1."""
    run_a = build_all_outputs()
    run_b = build_all_outputs()
    if len(run_a) != len(run_b):
        print(
            f"export_schemas --check FAILED: run A produced {len(run_a)} "
            f"files, run B produced {len(run_b)}",
            file=sys.stderr,
        )
        return 1
    for a, b in zip(run_a, run_b, strict=True):
        if a.rel_path != b.rel_path:
            print(
                f"export_schemas --check FAILED: rel_path mismatch "
                f"{a.rel_path!r} vs {b.rel_path!r}",
                file=sys.stderr,
            )
            return 1
        if a.content != b.content:
            print(
                f"export_schemas --check FAILED: content mismatch for "
                f"{a.rel_path!r} ({len(a.content)} vs {len(b.content)} bytes)",
                file=sys.stderr,
            )
            return 1
    print(f"export_schemas --check OK ({len(run_a)} files byte-identical across runs)")
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="export_schemas",
        description=__doc__.splitlines()[0] if __doc__ else "",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Run the exporter twice in memory; assert byte-equality; exit 0/1.",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=_DEFAULT_OUT_DIR,
        help=f"Output directory (default: {_DEFAULT_OUT_DIR.relative_to(_REPO_ROOT)}).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    if args.check:
        return _check_determinism()
    files = build_all_outputs()
    write_outputs(args.out_dir, files)
    n_gated = sum(1 for f in files if f.gated)
    print(f"export_schemas: wrote {len(files)} files to {args.out_dir} ({n_gated} gated stubs)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

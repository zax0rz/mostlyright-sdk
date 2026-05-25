"""Tests for ``scripts/export_schemas.py`` — the TS-codegen source-of-truth exporter.

The exporter is byte-deterministic by contract (``CROSS-SDK-SYNC.md`` §1.2);
this module is the local guard rail that fails fast before the
``schema-drift.yml`` CI workflow does. See ``REQUIREMENTS.md`` TS-CODEGEN-01.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

#: Repo-root path used to invoke ``scripts/export_schemas.py`` in a subprocess.
_REPO_ROOT: Path = Path(__file__).resolve().parents[1]
_EXPORTER: Path = _REPO_ROOT / "scripts" / "export_schemas.py"

#: The 9 Group A files (5 JSON Schemas + stations + kalshi + source-priority
#: + EXPORT_MANIFEST). ``polymarket-city-stations.json`` and
#: ``qc-alpha-rules.json`` are Group B and are NOT counted here — they may
#: emit real artifacts (when their Python source is materialized) or gated
#: stubs (when it is not), and the exporter still emits the file in either
#: case. Group A is the "always present, always real content" set.
_GROUP_A_RELPATHS: tuple[str, ...] = (
    "json/schema.observation.v1.json",
    "json/schema.forecast.iem_mos.v1.json",
    "json/schema.settlement.cli.v1.json",
    "json/schema.observation_ledger.v1.json",
    "json/schema.observation_qc.v1.json",
    "stations.json",
    "kalshi-settlement-stations.json",
    "source-priority.json",
    "EXPORT_MANIFEST.json",
)


def _run_exporter(out_dir: Path) -> None:
    """Invoke the exporter in a subprocess with the requested ``--out-dir``.

    Using a subprocess (rather than calling ``main()`` directly) catches
    sys.path / import-order surprises that would otherwise hide behind
    pytest's already-imported module cache.
    """
    proc = subprocess.run(
        [sys.executable, str(_EXPORTER), "--out-dir", str(out_dir)],
        capture_output=True,
        text=True,
        check=False,
        cwd=str(_REPO_ROOT),
    )
    if proc.returncode != 0:
        pytest.fail(
            f"export_schemas exited non-zero (rc={proc.returncode})\n"
            f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
        )


def _sha256_hex(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_exporter_deterministic(tmp_path: Path) -> None:
    """Two consecutive runs into separate dirs must produce byte-identical files."""
    out_a = tmp_path / "run_a"
    out_b = tmp_path / "run_b"
    _run_exporter(out_a)
    _run_exporter(out_b)

    files_a = sorted(p.relative_to(out_a) for p in out_a.rglob("*") if p.is_file())
    files_b = sorted(p.relative_to(out_b) for p in out_b.rglob("*") if p.is_file())
    assert files_a == files_b, (
        f"file-set drift between runs: only-in-A={set(files_a) - set(files_b)}, "
        f"only-in-B={set(files_b) - set(files_a)}"
    )

    for rel in files_a:
        a_bytes = (out_a / rel).read_bytes()
        b_bytes = (out_b / rel).read_bytes()
        assert a_bytes == b_bytes, (
            f"byte mismatch for {rel}: {len(a_bytes)} vs {len(b_bytes)} bytes"
        )


def test_group_a_files_present(tmp_path: Path) -> None:
    """All 9 Group A files exist + are non-empty."""
    out = tmp_path / "out"
    _run_exporter(out)
    for rel in _GROUP_A_RELPATHS:
        p = out / rel
        assert p.is_file(), f"Group A file missing: {rel}"
        assert p.stat().st_size > 0, f"Group A file empty: {rel}"


def test_group_a_json_well_formed(tmp_path: Path) -> None:
    """Every emitted JSON file must be parseable JSON."""
    out = tmp_path / "out"
    _run_exporter(out)
    for path in out.rglob("*.json"):
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            pytest.fail(f"emitted JSON not parseable at {path}: {exc}")


def test_export_manifest_records_all_files(tmp_path: Path) -> None:
    """Manifest lists every emitted file with correct SHA-256 + size."""
    out = tmp_path / "out"
    _run_exporter(out)

    manifest_path = out / "EXPORT_MANIFEST.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    entries = {entry["path"]: entry for entry in manifest["files"]}

    # The manifest covers every file under the output root EXCEPT itself
    # (manifest-listing-itself would be a chicken-and-egg loop).
    listed_paths = set(entries)
    emitted_paths: set[str] = set()
    for p in out.rglob("*"):
        if not p.is_file():
            continue
        rel = p.relative_to(out).as_posix()
        if rel == "EXPORT_MANIFEST.json":
            continue
        emitted_paths.add(rel)

    assert listed_paths == emitted_paths, (
        f"manifest path-set mismatch: "
        f"unlisted={emitted_paths - listed_paths}, "
        f"phantom={listed_paths - emitted_paths}"
    )

    for rel, entry in entries.items():
        file_path = out / rel
        assert entry["sha256"] == _sha256_hex(file_path), (
            f"SHA mismatch for {rel}: manifest says {entry['sha256']}, "
            f"file is {_sha256_hex(file_path)}"
        )
        assert entry["size_bytes"] == file_path.stat().st_size


def test_check_mode_passes_on_fresh_run() -> None:
    """``--check`` runs the exporter twice in-memory + asserts byte-equality."""
    proc = subprocess.run(
        [sys.executable, str(_EXPORTER), "--check"],
        capture_output=True,
        text=True,
        check=False,
        cwd=str(_REPO_ROOT),
    )
    assert proc.returncode == 0, (
        f"--check failed (rc={proc.returncode})\nstdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
    )


def test_group_a_schemas_carry_required_keys(tmp_path: Path) -> None:
    """Each emitted JSON Schema declares ``$schema``, ``$id``, ``version``."""
    out = tmp_path / "out"
    _run_exporter(out)
    for rel in _GROUP_A_RELPATHS:
        if not rel.startswith("json/"):
            continue
        payload = json.loads((out / rel).read_text(encoding="utf-8"))
        assert payload.get("$schema") == "https://json-schema.org/draft/2020-12/schema"
        assert payload.get("$id", "").startswith("https://mostlyright.dev/schemas/")
        assert payload.get("type") == "object"
        assert payload.get("version", "").startswith("v"), (
            f"{rel}: version field missing or malformed: {payload.get('version')!r}"
        )
        assert isinstance(payload.get("properties"), dict)
        assert isinstance(payload.get("required"), list)
        # required-list must be sorted (determinism rule).
        assert payload["required"] == sorted(payload["required"])

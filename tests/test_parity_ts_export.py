"""Determinism gate for the TS parity-fixture exporter.

Re-runs `export_for_ts.py` twice; asserts byte-identical output.
Critical: if this drifts, the TS parity gate (Plan 08) starts comparing
against moving ground truth and downstream debugging gets impossible.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

PARITY_DIR = Path(__file__).parent / "fixtures" / "parity"
EXPORTER = PARITY_DIR / "export_for_ts.py"


def test_exporter_exists() -> None:
    assert EXPORTER.exists(), f"Missing exporter script: {EXPORTER}"


def test_export_deterministic(tmp_path: Path) -> None:
    """Two runs of the exporter MUST produce byte-identical output.

    Copies the parquet fixtures into two scratch directories, runs the
    exporter against each, and compares every output file byte-for-byte.
    """
    for run_dir_name in ("run1", "run2"):
        run_dir = tmp_path / run_dir_name
        run_dir.mkdir()
        local_parity = run_dir / "parity"
        local_parity.mkdir()
        for case_pq in PARITY_DIR.glob("case_*.parquet"):
            (local_parity / case_pq.name).write_bytes(case_pq.read_bytes())
        subprocess.run(
            [
                sys.executable,
                str(EXPORTER),
                "--parity-dir",
                str(local_parity),
                "--output-dir",
                str(run_dir / "ts"),
            ],
            check=True,
            capture_output=True,
        )

    run1_ts = tmp_path / "run1" / "ts"
    run2_ts = tmp_path / "run2" / "ts"
    run1_files = sorted(f.name for f in run1_ts.iterdir())
    run2_files = sorted(f.name for f in run2_ts.iterdir())
    assert run1_files == run2_files, (
        f"Different file lists between runs: {run1_files} vs {run2_files}"
    )
    for name in run1_files:
        a = (run1_ts / name).read_bytes()
        b = (run2_ts / name).read_bytes()
        assert a == b, f"Non-deterministic output: {name} differs between runs"


def test_manifest_contains_all_5_cases() -> None:
    manifest_path = PARITY_DIR / "ts" / "manifest.json"
    assert manifest_path.exists(), (
        "Run `python tests/fixtures/parity/export_for_ts.py` to populate ts/"
    )
    manifest = json.loads(manifest_path.read_text())
    assert sorted(manifest.keys()) == [f"case_{n}" for n in range(1, 6)]


def test_case_jsons_match_manifest_sha256() -> None:
    manifest = json.loads((PARITY_DIR / "ts" / "manifest.json").read_text())
    for case_key, meta in manifest.items():
        json_name = f"{case_key}_{meta['station']}_{meta['from']}_{meta['to']}.json"
        json_path = PARITY_DIR / "ts" / json_name
        assert json_path.exists(), f"Missing JSON for {case_key}: {json_path}"
        actual_sha = hashlib.sha256(json_path.read_bytes()).hexdigest()
        assert actual_sha == meta["sha256"], (
            f"SHA mismatch for {case_key}: manifest={meta['sha256']} actual={actual_sha}"
        )


def test_row_counts_match_readme_expectations() -> None:
    """Anchor on parent README.md row-count expectations."""
    manifest = json.loads((PARITY_DIR / "ts" / "manifest.json").read_text())
    expected_row_counts = {
        "case_1": 7,
        "case_2": 30,
        "case_3": 31,
        "case_4": 365,
        "case_5": 15,
    }
    for case_key, expected in expected_row_counts.items():
        actual = manifest[case_key]["row_count"]
        assert actual == expected, (
            f"{case_key} row_count drift: manifest={actual} expected={expected}"
        )

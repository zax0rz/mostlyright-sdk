"""Test entrypoint for the drift watchdog (CI-05).

Runs ``tests/fixtures/drift/compare.py`` if drift fixtures exist. Skipped
on fresh clones (the default — drift/ is gitignored except for .gitkeep
and the scripts). The actual watchdog runs in
``.github/workflows/drift-rotate.yml`` on a weekly schedule; this test
exists so the diff logic itself is exercised locally if a developer
captures a drift set manually.

Soft-fail semantics: even if compare.py finds drift, this test PASSES.
The test's job is to assert that ``compare.py`` runs to completion (exit
0) and produces a parseable report on mismatch. Hard parity-regression
detection is owned by ``tests/test_parity.py``.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

DRIFT_DIR = Path(__file__).resolve().parent / "fixtures" / "drift"
PARITY_DIR = Path(__file__).resolve().parent / "fixtures" / "parity"


def _drift_fixtures_present() -> bool:
    """True iff at least one ``case_*.parquet`` exists under drift/."""
    return any(DRIFT_DIR.glob("case_*.parquet"))


@pytest.mark.skipif(
    not _drift_fixtures_present(),
    reason="No drift fixtures present (fresh clone or pre-first-cron run).",
)
def test_drift_compare_runs() -> None:
    """``compare.py`` exits 0 (soft-fail watchdog) when drift fixtures exist."""
    script = DRIFT_DIR / "compare.py"
    assert script.exists(), f"compare.py missing at {script}"

    result = subprocess.run(
        [sys.executable, str(script)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert (
        result.returncode == 0
    ), f"compare.py exited {result.returncode}\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"


def test_parity_baseline_present() -> None:
    """The frozen parity baseline must always be present (it's checked in)."""
    assert PARITY_DIR.exists(), f"parity baseline missing at {PARITY_DIR}"
    fixtures = list(PARITY_DIR.glob("case_*.parquet"))
    assert len(fixtures) == 5, (
        f"Expected 5 parity fixtures under {PARITY_DIR}, found {len(fixtures)}: "
        f"{[f.name for f in fixtures]}"
    )


def test_drift_scripts_present() -> None:
    """Both drift scripts must exist (capture + compare)."""
    assert (DRIFT_DIR / "capture_drift.py").exists()
    assert (DRIFT_DIR / "compare.py").exists()

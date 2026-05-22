"""One-shot dtype capture for the Phase 1 parity gate.

Reads each of the 5 ``tests/fixtures/parity/case_*.parquet`` byte-equivalent
fixtures (captured at Day 0.5 against ``mostlyright==0.14.1``) and writes
``tests/fixtures/parity/expected_dtypes.json`` - a per-case mapping
``{column: dtype_str}`` that ``tests/test_parity.py`` loads at collection
time as the PARITY-03 dtype ground truth.

Run once after fixture capture (and again whenever the fixtures are
re-captured against a new pandas/pyarrow combination). The JSON is
committed alongside the parquet fixtures.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

CASES: list[tuple[int, str, str, str]] = [
    (1, "KNYC", "2025-01-06", "2025-01-12"),
    (2, "KMDW", "2025-04-01", "2025-04-30"),
    (3, "KLAX", "2025-03-01", "2025-03-31"),
    (4, "KMIA", "2024-12-01", "2025-11-30"),
    (5, "KMSY", "2024-09-08", "2024-09-22"),
]

FIXTURES = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "parity"


def main() -> None:
    out: dict[str, dict[str, str]] = {}
    for n, station, frm, to in CASES:
        path = FIXTURES / f"case_{n}_{station}_{frm}_{to}.parquet"
        df = pd.read_parquet(path)
        df = df.reset_index() if df.index.name else df
        out[f"case_{n}"] = {col: str(dtype) for col, dtype in df.dtypes.items()}
    (FIXTURES / "expected_dtypes.json").write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")
    print(f"Wrote {FIXTURES / 'expected_dtypes.json'} with {len(out)} cases.")


if __name__ == "__main__":
    main()

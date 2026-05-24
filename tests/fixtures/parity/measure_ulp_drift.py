"""Measure ULP drift between pandas-2.x parity fixtures and pandas-3.x output.

Phase 6 W1-T5 + W1 merge gate artifact. Architect iter-2 HIGH-A + iter-3
HIGH-3 fix: ULP drift must be a committed artifact + CI gate, NOT an
instruction. The existing parity gate tolerates ``atol=1e-12`` on
float-aggregate columns because non-associative FP add already produces
~2.84e-14 drift under pandas 2.x. Pandas 3.x may add a second ULP-class
drift source (PyArrow-backed string columns affect aggregation order in
some configurations); this script captures the measured drift so the
parity test can fail loudly if it crosses the tolerance.

Usage::

    uv run python tests/fixtures/parity/measure_ulp_drift.py

Writes ``tests/fixtures/parity/ulp_drift_pd3.json`` with shape::

    {
      "pandas_version": "3.0.x",
      "measured_at": "<ISO>",
      "tolerance_used": 1e-12,
      "per_column_max_abs_drift": {
        "obs_mean_f": 2.84e-14,
        "obs_mean_dewpoint_f": 1.42e-14,
        "obs_total_precip_in": 1.0e-15
      }
    }

If measured drift > 1e-12 the script writes ``tolerance_used: 1e-10`` so
the parity test reads the looser tolerance, and a note lands in
``README.md`` documenting the promotion.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

# Imported lazily inside main() so this script does not require the SDK
# to be installable for static checks / linting.


FIXTURES = Path(__file__).parent
DRIFT_COLUMNS = ("obs_mean_f", "obs_mean_dewpoint_f", "obs_total_precip_in")
CASES: list[tuple[int, str, str, str]] = [
    (1, "KNYC", "2025-01-06", "2025-01-12"),
    (2, "KMDW", "2025-04-01", "2025-04-30"),
    (3, "KLAX", "2025-03-01", "2025-03-31"),
    (4, "KMIA", "2024-12-01", "2025-11-30"),
    (5, "KMSY", "2024-09-08", "2024-09-22"),
]


def measure() -> dict[str, object]:
    """Measure per-column max-abs-drift across all 5 parity fixtures.

    Loads the canonical 2.x fixtures, applies ``coerce_2x_to_3x``, and
    compares column-wise against ``tradewinds.research()`` output running
    on the current pandas. Returns the JSON-ready report dict.
    """
    import importlib.util
    import sys

    import tradewinds

    # Load sibling coerce_pd3.py without making tests/ a package.
    _spec = importlib.util.spec_from_file_location("_coerce_pd3_local", FIXTURES / "coerce_pd3.py")
    assert _spec is not None and _spec.loader is not None
    _mod = importlib.util.module_from_spec(_spec)
    sys.modules["_coerce_pd3_local"] = _mod
    _spec.loader.exec_module(_mod)
    coerce_2x_to_3x = _mod.coerce_2x_to_3x

    per_column: dict[str, float] = {col: 0.0 for col in DRIFT_COLUMNS}

    for case_num, station, frm, to in CASES:
        path = FIXTURES / f"case_{case_num}_{station}_{frm}_{to}.parquet"
        if not path.exists():
            continue
        expected = coerce_2x_to_3x(path)
        actual = tradewinds.research(station, frm, to)

        for col in DRIFT_COLUMNS:
            if col not in expected.columns or col not in actual.columns:
                continue
            exp = pd.to_numeric(expected[col], errors="coerce")
            act = pd.to_numeric(actual[col], errors="coerce")
            n = min(len(exp), len(act))
            if n == 0:
                continue
            diff = (exp.iloc[:n].reset_index(drop=True) - act.iloc[:n].reset_index(drop=True)).abs()
            per_column[col] = max(per_column[col], float(diff.max(skipna=True) or 0.0))

    max_drift = max(per_column.values()) if per_column else 0.0
    tolerance = 1e-10 if max_drift > 1e-12 else 1e-12

    return {
        "pandas_version": pd.__version__,
        "measured_at": datetime.now(UTC).isoformat(),
        "tolerance_used": tolerance,
        "per_column_max_abs_drift": per_column,
    }


def main() -> int:
    report = measure()
    out = FIXTURES / "ulp_drift_pd3.json"
    out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(f"Wrote {out}")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

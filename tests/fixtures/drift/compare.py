"""Diff drift/ vs parity/ — soft-fail watchdog.

Phase 4 CI-05 — runs after ``capture_drift.py`` in the weekly cron. Compares
each ``drift/case_*.parquet`` against the corresponding ``parity/case_*.parquet``
using the SAME tolerance + canonicalization rules as ``tests/test_parity.py``
(see PARITY-02 / PARITY-03):

- ``np.allclose(rtol=0, atol=1e-12)`` on numeric columns (matches the worst
  measured drift of ~2.84e-14 on case 4 with ~35,000x headroom)
- exact equality on integer / object / datetime columns
- ``dtypes.equals(expected_dtypes)`` for the dtype-ground-truth contract

Soft-fail policy
----------------
- If parity/ files don't exist → exit 1 (parity baseline is required).
- If drift/ files don't exist → exit 0 (fresh clone; nothing to diff).
- If diff finds mismatches → write ``drift-report.md`` to this directory
  and exit 0. The workflow that calls this script opens a GH issue from
  the report; CI is **never** failed by a mismatch.
- If a drift/case is missing but parity/case exists → log as a capture
  failure in the report; do not raise.

Usage
-----

    uv run python tests/fixtures/drift/compare.py

Exit codes
----------
- 0 — comparison ran (with or without mismatches; report written on mismatch)
- 1 — parity baseline missing (configuration error, not drift)
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

#: Mirror of CASES in tests/test_parity.py + tests/fixtures/parity/capture_fixtures.py
#: + tests/fixtures/drift/capture_drift.py. Keep all four in lockstep.
CASES: list[tuple[int, str, str, str]] = [
    (1, "KNYC", "2025-01-06", "2025-01-12"),
    (2, "KMDW", "2025-04-01", "2025-04-30"),
    (3, "KLAX", "2025-03-01", "2025-03-31"),
    (4, "KMIA", "2024-12-01", "2025-11-30"),
    (5, "KMSY", "2024-09-08", "2024-09-22"),
]

#: Matches the tolerance band used in tests/test_parity.py:test_parity_case.
ATOL = 1e-12
RTOL = 0.0


def _canon(df: pd.DataFrame) -> pd.DataFrame:
    """Mirror of tests/test_parity.py:_canon — same row order both sides."""
    out = df.reset_index() if df.index.name else df.reset_index(drop=True)
    if "index" in out.columns and "date" in out.columns:
        out = out.drop(columns=["index"])
    return out.sort_values(["date", "station"]).reset_index(drop=True)


def _compare_frames(case_num: int, parity_df: pd.DataFrame, drift_df: pd.DataFrame) -> list[str]:
    """Return a list of mismatch descriptions (empty when frames agree)."""
    findings: list[str] = []
    parity_c = _canon(parity_df)
    drift_c = _canon(drift_df)

    # Shape check first — diverging row counts is the most common drift.
    if parity_c.shape != drift_c.shape:
        findings.append(
            f"case {case_num}: shape mismatch — parity={parity_c.shape}, drift={drift_c.shape}"
        )
        return findings

    # Dtype ground truth.
    parity_dtypes = {col: str(dtype) for col, dtype in parity_c.dtypes.items()}
    drift_dtypes = {col: str(dtype) for col, dtype in drift_c.dtypes.items()}
    if parity_dtypes != drift_dtypes:
        diffs = [
            f"{col}: parity={parity_dtypes.get(col)} drift={drift_dtypes.get(col)}"
            for col in set(parity_dtypes) | set(drift_dtypes)
            if parity_dtypes.get(col) != drift_dtypes.get(col)
        ]
        findings.append(f"case {case_num}: dtype mismatch — {'; '.join(diffs)}")

    # Per-column value comparison.
    common_cols = [c for c in parity_c.columns if c in drift_c.columns]
    for col in common_cols:
        p_series = parity_c[col]
        d_series = drift_c[col]
        if pd.api.types.is_numeric_dtype(p_series) and pd.api.types.is_numeric_dtype(d_series):
            # Tolerance-based comparison on floats; ints fall through to
            # strict equality below via the np.allclose `equal_nan=True`.
            p_arr = p_series.to_numpy()
            d_arr = d_series.to_numpy()
            if not np.allclose(p_arr, d_arr, rtol=RTOL, atol=ATOL, equal_nan=True):
                # Find first divergent index for the report.
                with np.errstate(invalid="ignore"):
                    abs_diff = np.abs(p_arr.astype(float) - d_arr.astype(float))
                max_idx = int(np.nanargmax(abs_diff))
                findings.append(
                    f"case {case_num}: numeric drift on {col!r} — "
                    f"max |diff|={float(abs_diff[max_idx]):.3e} "
                    f"at row {max_idx} (parity={p_arr[max_idx]!r}, "
                    f"drift={d_arr[max_idx]!r})"
                )
        else:
            # Object / datetime / string: strict equality (with NaN treated equal).
            if not p_series.equals(d_series):
                # Locate first divergent row.
                mask = p_series.fillna("__NULL__") != d_series.fillna("__NULL__")
                if mask.any():
                    first_idx = int(mask.idxmax())
                    findings.append(
                        f"case {case_num}: exact mismatch on {col!r} at row "
                        f"{first_idx} (parity={p_series.iloc[first_idx]!r}, "
                        f"drift={d_series.iloc[first_idx]!r})"
                    )

    # Surface column-set diffs.
    extra_in_parity = set(parity_c.columns) - set(drift_c.columns)
    extra_in_drift = set(drift_c.columns) - set(parity_c.columns)
    if extra_in_parity:
        findings.append(f"case {case_num}: columns missing from drift — {sorted(extra_in_parity)}")
    if extra_in_drift:
        findings.append(f"case {case_num}: columns added in drift — {sorted(extra_in_drift)}")

    return findings


def main() -> int:
    here = Path(__file__).resolve().parent
    parity_dir = here.parent / "parity"
    drift_dir = here

    if not parity_dir.exists():
        print(f"ERROR: parity baseline missing at {parity_dir}", file=sys.stderr)
        return 1

    all_findings: list[str] = []
    for case_num, station, frm, to in CASES:
        fname = f"case_{case_num}_{station}_{frm}_{to}.parquet"
        parity_path = parity_dir / fname
        drift_path = drift_dir / fname

        if not parity_path.exists():
            print(f"ERROR: parity fixture missing — {parity_path}", file=sys.stderr)
            return 1
        if not drift_path.exists():
            # Fresh clone or failed capture — log to report, do not raise.
            all_findings.append(f"case {case_num}: drift capture missing ({drift_path.name})")
            continue

        parity_df = pd.read_parquet(parity_path)
        drift_df = pd.read_parquet(drift_path)
        case_findings = _compare_frames(case_num, parity_df, drift_df)
        all_findings.extend(case_findings)
        if not case_findings:
            print(f"case {case_num}: OK")
        else:
            for finding in case_findings:
                print(finding)

    if all_findings:
        report = drift_dir / "drift-report.md"
        lines = [
            "# Drift Report",
            "",
            "Weekly Monday 07:00 UTC cron found drift between `tests/fixtures/drift/`",
            "and the frozen `tests/fixtures/parity/` baseline.",
            "",
            "**Reminder:** `parity/` is the v0.14.1 byte-equivalence ground truth",
            "and MUST NEVER be re-recorded. If the findings below show real",
            "regression in `tradewinds.research()` output, fix the regression.",
            "If the findings show legitimate upstream-API behavior change, the",
            "fix is a tradewinds-side normalization — not a parity refresh.",
            "",
            "## Findings",
            "",
        ]
        for f in all_findings:
            lines.append(f"- {f}")
        lines.append("")
        report.write_text("\n".join(lines))
        print(f"\nWrote {report} with {len(all_findings)} finding(s).")
        # Soft-fail: do NOT non-zero-exit on drift. The workflow opens an
        # issue from the report; CI is never blocked by this script.
        return 0

    # No findings — clean week.
    print("OK: drift matches parity within tolerance.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

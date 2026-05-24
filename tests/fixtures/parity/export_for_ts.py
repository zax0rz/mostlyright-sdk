"""Export Phase 1 parquet parity fixtures as JSON for the TS parity gate.

The TS SDK cannot read parquet in v0.1.0 (parquet-wasm deferred to v0.2 per
TS-SDK-DESIGN.md §1). This script projects each `case_N_*.parquet` to a JSON
file under `tests/fixtures/parity/ts/` consumable by Plan 08's
`packages-ts/meta/tests/parity/parity.test.ts`.

Determinism guarantees:
- `json.dump(... sort_keys=True, indent=2)` — stable byte output.
- No wall-clock or environment-dependent fields.
- Type preservation: int64 → JSON integer; float64 → JSON float;
  NaN → JSON null; datetime64[ns] (date col) → ISO YYYY-MM-DD string.

Two consecutive runs produce byte-identical output. Validated by
`tests/test_parity_ts_export.py::test_export_deterministic`.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path
from typing import Any

import pandas as pd

# (case_num, station, from_date, to_date) — mirrors parent README.md table.
CASES: list[tuple[int, str, str, str]] = [
    (1, "KNYC", "2025-01-06", "2025-01-12"),
    (2, "KMDW", "2025-04-01", "2025-04-30"),
    (3, "KLAX", "2025-03-01", "2025-03-31"),
    (4, "KMIA", "2024-12-01", "2025-11-30"),
    (5, "KMSY", "2024-09-08", "2024-09-22"),
]


def _is_integer_dtype(dtype_str: str) -> bool:
    return dtype_str.startswith("int")


def _is_float_dtype(dtype_str: str) -> bool:
    return dtype_str.startswith("float")


def _is_datetime_dtype(dtype_str: str) -> bool:
    return dtype_str.startswith("datetime")


def _coerce_cell(value: Any, dtype_str: str) -> Any:
    """Project one parquet cell to a JSON-safe native Python type.

    Rules:
    - Date column (`datetime64[ns]`): convert pd.Timestamp → ISO YYYY-MM-DD.
    - NaN / None / NaT: JSON null.
    - Integer dtype: int(value).
    - Float dtype: float(value).
    - Object dtype: pass through (str or None).
    """
    # pd.isna handles NaN, NaT, and None uniformly. Apply BEFORE date coercion
    # so NaT cells in a datetime column emit null rather than crashing the
    # f-string formatter below.
    if value is None:
        return None
    # pd.isna returns array for sequences; guard with scalar check.
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        # Non-scalar value (rare in row iteration) — fall through.
        pass

    if _is_datetime_dtype(dtype_str):
        # Convert pd.Timestamp / np.datetime64 → ISO YYYY-MM-DD.
        ts = pd.Timestamp(value)
        return f"{ts.year:04d}-{ts.month:02d}-{ts.day:02d}"

    if _is_integer_dtype(dtype_str):
        return int(value)

    if _is_float_dtype(dtype_str):
        f = float(value)
        # JSON cannot encode non-finite floats; coerce to null for parity
        # with the TS-side `JSON.parse` behavior.
        if not math.isfinite(f):
            return None
        return f

    # Object dtype — pass through. Strings flow through; None already handled.
    return value


def row_to_dict(row: pd.Series[Any], dtypes: dict[str, str]) -> dict[str, Any]:
    """Project one pandas row to a JSON-safe dict, applying per-column dtype rules."""
    out: dict[str, Any] = {}
    for col in row.index:
        out[col] = _coerce_cell(row[col], dtypes[col])
    return out


def export_case_to_json(
    case_num: int,
    station: str,
    frm: str,
    to: str,
    parity_dir: Path,
    output_dir: Path,
) -> dict[str, Any]:
    """Project one parquet fixture to JSON and return its manifest entry."""
    parquet_path = parity_dir / f"case_{case_num}_{station}_{frm}_{to}.parquet"
    df = pd.read_parquet(parquet_path)

    # Parquet stores `date` as the row index per `pairs_to_dataframe`. Materialize
    # it as a column before iteration.
    if df.index.name == "date":
        df = df.reset_index()

    # Canonicalize row order — mirrors the `_canon` helper from
    # `tests/fixtures/parity/README.md` Day 3 contract.
    df = df.sort_values(by=["date", "station"]).reset_index(drop=True)

    dtypes: dict[str, str] = {col: str(dtype) for col, dtype in df.dtypes.items()}

    rows: list[dict[str, Any]] = [row_to_dict(row, dtypes) for _, row in df.iterrows()]

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"case_{case_num}_{station}_{frm}_{to}.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(rows, f, indent=2, sort_keys=True, separators=(",", ": "))
        f.write("\n")  # trailing newline for POSIX-friendliness

    sha256 = hashlib.sha256(output_path.read_bytes()).hexdigest()

    return {
        "station": station,
        "from": frm,
        "to": to,
        "row_count": len(rows),
        "sha256": sha256,
        "dtypes": dtypes,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Export Phase 1 parquet parity fixtures as JSON for TS parity gate."
    )
    here = Path(__file__).parent
    parser.add_argument(
        "--parity-dir",
        type=Path,
        default=here,
        help="Directory containing case_*.parquet (default: this script's dir).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=here / "ts",
        help="Directory to write case_*.json + manifest.json (default: ./ts/).",
    )
    args = parser.parse_args(argv)

    parity_dir: Path = args.parity_dir
    output_dir: Path = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    manifest: dict[str, Any] = {}
    for case_num, station, frm, to in CASES:
        entry = export_case_to_json(case_num, station, frm, to, parity_dir, output_dir)
        manifest[f"case_{case_num}"] = entry
        print(
            f"  case_{case_num} {station} {frm}..{to} → {entry['row_count']} rows  sha256={entry['sha256'][:12]}…"
        )

    manifest_path = output_dir / "manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, sort_keys=True, separators=(",", ": "))
        f.write("\n")

    print(f"\nWrote {len(CASES)} JSON fixtures + manifest.json to {output_dir}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
